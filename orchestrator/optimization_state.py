"""
Phase 8 — Optimization State Classifier

Reads real system state and classifies the current optimization opportunity into
one of six states, each with a corresponding set of allowed / blocked task families.

States:
  DATA_WAITING          — CLV records mostly PENDING_CLOSING; no learning yet
  DATA_READY            — enough COMPUTED CLV exists; full learning pipeline allowed
  MODEL_WEAKNESS_DETECTED — Brier / LogLoss / CLV / ROI show weakness; need patch
  SYSTEM_RELIABILITY_ISSUE — scheduler skip, stale daemon, API failure, missing artifacts
  ARCHITECTURE_DEBT     — duplicate modules, stale docs, wiki mismatch
  OPERATOR_UX_GAP       — decision card missing key state fields

Hard rules (must never be loosened):
  - DATA_WAITING always blocks strategy reinforcement and model decisions
  - Learning tasks require DATA_READY; they are blocked otherwise
  - Phase 6 / Phase 7 gates are NEVER weakened by this classifier
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]

# ── State constants ──────────────────────────────────────────────────────────
STATE_DATA_WAITING            = "DATA_WAITING"
STATE_DATA_READY              = "DATA_READY"
STATE_MODEL_WEAKNESS          = "MODEL_WEAKNESS_DETECTED"
STATE_SYSTEM_RELIABILITY      = "SYSTEM_RELIABILITY_ISSUE"
STATE_ARCHITECTURE_DEBT       = "ARCHITECTURE_DEBT"
STATE_OPERATOR_UX_GAP         = "OPERATOR_UX_GAP"

# ── Task family constants (mirror analysis_family values in planner_tick) ──
FAMILY_STRATEGY_REINFORCEMENT = "strategy-reinforcement"
FAMILY_MODEL_VALIDATION       = "model-validation-atomic"
FAMILY_MODEL_PATCH            = "model-patch-atomic"
FAMILY_CALIBRATION            = "calibration-atomic"
FAMILY_FEATURE                = "feature-atomic"
FAMILY_REGIME                 = "regime-atomic"
FAMILY_ODDS                   = "odds-atomic"
FAMILY_FEEDBACK               = "feedback-atomic"
FAMILY_BACKTEST               = "backtest-validity-atomic"
FAMILY_SIMULATION             = "simulation-atomic"
FAMILY_DATA_MONITOR           = "data-monitor"
FAMILY_SYSTEM_RELIABILITY     = "system-reliability"
FAMILY_ARCHITECTURE           = "architecture-cleanup"
FAMILY_OBSERVABILITY          = "observability-ux"
FAMILY_MAINTENANCE            = "maintenance"
# Safe waiting-compatible families (DATA_WAITING state)
FAMILY_CLOSING_MONITOR        = "closing-monitor"
FAMILY_OPS_REPORT             = "ops-report"
FAMILY_SCHEDULER_HEALTH       = "scheduler-health-check"
FAMILY_ARTIFACT_HEALTH        = "artifact-health-check"
FAMILY_WIKI_MAINTENANCE       = "wiki-maintenance"
# Learning variants that should be blocked in all wait states
FAMILY_CLV_REINFORCEMENT      = "clv-reinforcement"

# ── Classification thresholds ────────────────────────────────────────────────
# Minimum computed CLV fraction to be considered DATA_READY
_COMPUTED_CLV_MIN_FRACTION = 0.10   # at least 10% of CLV records must be COMPUTED
_COMPUTED_CLV_MIN_ABSOLUTE = 1      # at least 1 COMPUTED record required

# Model weakness: poor Brier / negative CLV
_BRIER_WEAKNESS_THRESHOLD  = 0.28   # Brier > 0.28 → weak calibration
_CLV_NEGATIVE_THRESHOLD    = -0.010 # avg CLV < -0.010 → model weakness

# System reliability: how long before a scheduler run is "stale"
_SCHEDULER_STALE_MINUTES   = 90     # no run in > 90 min → stale

# Architecture debt: check for duplicate wiki entries
_WIKI_DUPLICATE_THRESHOLD  = 2      # ≥ 2 duplicate module entries → debt

# Paths
_HEARTBEAT_PATH  = _REPO_ROOT / "logs" / "daemon_heartbeat.jsonl"
_MONITOR_STATE_PATH = (
    _REPO_ROOT / "runtime" / "agent_orchestrator" / "closing_monitor_state.json"
)
_STRATEGY_STATE_PATH = (
    _REPO_ROOT / "runtime" / "agent_orchestrator" / "strategy_state.json"
)
_SIM_SUMMARY_PATH = (
    _REPO_ROOT / "runtime" / "agent_orchestrator" / "simulation_summary.json"
)
_DECISION_Q_RPT = (
    _REPO_ROOT / "data" / "wbc_backend" / "reports" / "mlb_decision_quality_report.json"
)
_WIKI_INVENTORY = _REPO_ROOT / "wiki" / "INVENTORY.md"
_WIKI_CLEANUP   = _REPO_ROOT / "wiki" / "CLEANUP_PLAN.md"
_ROI_TRACKING   = _REPO_ROOT / "research" / "roi_tracking.json"


# ─────────────────────────────────────────────
# I/O helpers
# ─────────────────────────────────────────────

def _safe_load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("[OptState] Failed to load %s: %s", path.name, exc)
        return None


def _iter_jsonl(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


# ─────────────────────────────────────────────
# Sub-checks
# ─────────────────────────────────────────────

def _check_clv_readiness(reports_dir: Path | None = None) -> dict[str, Any]:
    """
    Read Phase 6 CLV status.
    Returns: {computed, pending, total, computed_fraction, ready}
    """
    try:
        from orchestrator import phase6_data_registry
        status = phase6_data_registry.get_phase6_status(reports_dir)
        computed = status.get("clv_computed", 0)
        pending  = status.get("clv_pending_closing", 0)
        blocked  = status.get("clv_blocked", 0)
        total    = computed + pending + blocked
        fraction = computed / total if total > 0 else 0.0
        ready = (
            computed >= _COMPUTED_CLV_MIN_ABSOLUTE
            and fraction >= _COMPUTED_CLV_MIN_FRACTION
        )
        return {
            "computed": computed,
            "pending": pending,
            "blocked": blocked,
            "total": total,
            "computed_fraction": round(fraction, 4),
            "ready": ready,
            "all_pending": status.get("all_clv_pending", False),
        }
    except Exception as exc:
        logger.debug("[OptState] CLV readiness check failed: %s", exc)
        return {
            "computed": 0, "pending": 0, "blocked": 0, "total": 0,
            "computed_fraction": 0.0, "ready": False, "all_pending": True,
        }


def _check_model_weakness() -> dict[str, Any]:
    """
    Look for weak Brier / LogLoss / negative avg CLV.
    Returns: {weakness_detected, reasons}
    """
    reasons: list[str] = []

    # Check decision quality report for Brier weakness
    dq = _safe_load_json(_DECISION_Q_RPT)
    if dq:
        brier = dq.get("overall_brier_score") or dq.get("brier_score")
        if isinstance(brier, (int, float)) and brier > _BRIER_WEAKNESS_THRESHOLD:
            reasons.append(
                f"brier_score={brier:.4f} > threshold={_BRIER_WEAKNESS_THRESHOLD}"
            )
        # Check regime-level weakness
        regime_metrics = dq.get("regime_metrics") or {}
        for regime, m in regime_metrics.items():
            b = m.get("brier_score") if isinstance(m, dict) else None
            if isinstance(b, float) and b > _BRIER_WEAKNESS_THRESHOLD + 0.05:
                reasons.append(f"regime={regime!r} brier={b:.4f} (poor)")
                break  # one example is enough

    # Check avg CLV from training memory
    try:
        from orchestrator import training_memory
        clv_summary = training_memory.get_clv_outcome_summary()
        avg_clv = clv_summary.get("avg_clv")
        if avg_clv is not None and avg_clv < _CLV_NEGATIVE_THRESHOLD:
            reasons.append(f"avg_clv={avg_clv:.4f} < {_CLV_NEGATIVE_THRESHOLD} (negative signal)")
    except Exception as exc:
        logger.debug("[OptState] CLV summary check failed: %s", exc)

    # Check ROI tracking
    roi = _safe_load_json(_ROI_TRACKING)
    if roi:
        roi_pct = roi.get("roi_percent") or roi.get("roi_pct")
        if isinstance(roi_pct, (int, float)) and roi_pct < -5.0:
            reasons.append(f"roi_pct={roi_pct:.2f}% (negative ROI)")

    return {"weakness_detected": len(reasons) > 0, "reasons": reasons}


def _check_system_reliability() -> dict[str, Any]:
    """
    Detect scheduler skips, stale daemon, missing critical artifacts.
    Returns: {issue_detected, reasons}
    """
    reasons: list[str] = []
    now = datetime.now(timezone.utc)

    # Check daemon heartbeat staleness
    last_heartbeat: datetime | None = None
    for row in _iter_jsonl(_HEARTBEAT_PATH):
        ts = _parse_ts(row.get("timestamp") or row.get("ts"))
        if ts and (last_heartbeat is None or ts > last_heartbeat):
            last_heartbeat = ts

    if last_heartbeat is None:
        reasons.append("daemon_heartbeat_missing: no heartbeat log found")
    else:
        age_min = (now - last_heartbeat).total_seconds() / 60
        if age_min > _SCHEDULER_STALE_MINUTES:
            reasons.append(
                f"daemon_stale: last heartbeat {age_min:.0f} min ago "
                f"(> {_SCHEDULER_STALE_MINUTES} min threshold)"
            )

    # Check for recent scheduler runs via DB (optional — non-fatal if DB unavailable)
    try:
        from orchestrator import db
        runs = db.list_runs(runner="planner_tick", limit=5)
        if not runs:
            reasons.append("no_recent_planner_runs: planner has never run")
        else:
            # Check if the last run was a skip-storm (>= 3 consecutive SKIPPED)
            last_outcomes = [r.get("outcome", "") for r in runs[:5]]
            skip_streak = 0
            for o in last_outcomes:
                if o == "SKIPPED":
                    skip_streak += 1
                else:
                    break
            if skip_streak >= 3:
                reasons.append(
                    f"planner_skip_storm: {skip_streak} consecutive SKIPPED runs"
                )
    except Exception as exc:
        logger.debug("[OptState] DB run check failed (non-fatal): %s", exc)

    # Check missing critical runtime artifacts
    critical_paths = [
        _STRATEGY_STATE_PATH,
    ]
    for p in critical_paths:
        if not p.exists():
            reasons.append(f"missing_artifact: {p.name}")

    return {"issue_detected": len(reasons) > 0, "reasons": reasons}


def _check_architecture_debt() -> dict[str, Any]:
    """
    Detect duplicate modules, stale docs, wiki mismatch.
    Returns: {debt_detected, reasons}
    """
    reasons: list[str] = []

    # Check CLEANUP_PLAN.md for open items
    if _WIKI_CLEANUP.exists():
        text = _WIKI_CLEANUP.read_text(encoding="utf-8")
        open_items = text.count("[ ]")
        if open_items >= 3:
            reasons.append(
                f"wiki_cleanup_open_items: {open_items} unchecked items in CLEANUP_PLAN.md"
            )

    # Check INVENTORY.md for duplicate module listings
    if _WIKI_INVENTORY.exists():
        text = _WIKI_INVENTORY.read_text(encoding="utf-8")
        # Count duplicate module names (lines starting with "- " or "* ")
        module_names: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("- ", "* ")):
                module_names.append(stripped[2:].split()[0].lower() if stripped[2:] else "")
        seen: dict[str, int] = {}
        for name in module_names:
            if name:
                seen[name] = seen.get(name, 0) + 1
        dupes = [n for n, cnt in seen.items() if cnt >= _WIKI_DUPLICATE_THRESHOLD]
        if dupes:
            reasons.append(
                f"wiki_duplicate_modules: {len(dupes)} duplicate entries ({', '.join(dupes[:3])})"
            )

    return {"debt_detected": len(reasons) > 0, "reasons": reasons}


def _check_operator_ux_gap(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Detect if the decision card is missing key Phase 6 / Phase 7 state.
    If payload is provided, inspect it directly.
    If payload is None, skip the check (returns gap_detected=False) to avoid
    infinite recursion: build_payload() → classify() → build_payload() → …

    Returns: {gap_detected, reasons}
    """
    reasons: list[str] = []

    # Guard: if no payload supplied, skip (caller must provide it explicitly)
    if payload is None:
        return {"gap_detected": False, "reasons": []}

    try:
        phase6 = payload.get("phase6", {})
        phase7 = payload.get("phase7", {})
        phase8 = payload.get("phase8", {})

        if not phase6.get("available"):
            reasons.append("decision_card_missing_phase6: phase6 block unavailable")

        if not phase7.get("available"):
            reasons.append("decision_card_missing_phase7: phase7 block unavailable")

        if not phase8.get("available") and not phase8:
            # Phase 8 block not yet rendered → UX gap (expected on first run)
            reasons.append("decision_card_missing_phase8: governance block not yet rendered")

        # Verify key fields are non-None
        required_phase6_fields = ["clv_computed", "clv_pending_closing", "dates"]
        if phase6.get("available"):
            for field in required_phase6_fields:
                if field not in phase6:
                    reasons.append(f"phase6_missing_field: {field}")

    except Exception as exc:
        logger.debug("[OptState] Operator UX gap check failed (non-fatal): %s", exc)

    return {"gap_detected": len(reasons) > 0, "reasons": reasons}


# ─────────────────────────────────────────────
# State → task family mapping
# ─────────────────────────────────────────────

_STATE_ALLOWED_FAMILIES: dict[str, list[str]] = {
    STATE_DATA_WAITING: [
        # Primary safe waiting-compatible families (explicitly listed first)
        FAMILY_CLOSING_MONITOR,
        FAMILY_OPS_REPORT,
        FAMILY_SCHEDULER_HEALTH,
        FAMILY_ARTIFACT_HEALTH,
        FAMILY_WIKI_MAINTENANCE,
        FAMILY_ARCHITECTURE,
        FAMILY_OBSERVABILITY,
        FAMILY_MAINTENANCE,
        # Monitoring
        FAMILY_DATA_MONITOR,
        FAMILY_SYSTEM_RELIABILITY,
        # Read-only simulation (no CLV writes)
        FAMILY_SIMULATION,
    ],
    STATE_DATA_READY: [
        FAMILY_MODEL_VALIDATION,
        FAMILY_MODEL_PATCH,
        FAMILY_STRATEGY_REINFORCEMENT,
        FAMILY_CALIBRATION,
        FAMILY_FEATURE,
        FAMILY_REGIME,
        FAMILY_ODDS,
        FAMILY_FEEDBACK,
        FAMILY_BACKTEST,
        FAMILY_SIMULATION,
        FAMILY_MAINTENANCE,
        FAMILY_OBSERVABILITY,
    ],
    STATE_MODEL_WEAKNESS: [
        FAMILY_MODEL_PATCH,
        FAMILY_MODEL_VALIDATION,
        FAMILY_CALIBRATION,
        FAMILY_FEATURE,
        FAMILY_REGIME,
        FAMILY_BACKTEST,
        FAMILY_FEEDBACK,
        FAMILY_SIMULATION,
        FAMILY_MAINTENANCE,
    ],
    STATE_SYSTEM_RELIABILITY: [
        FAMILY_SYSTEM_RELIABILITY,
        FAMILY_MAINTENANCE,
        FAMILY_DATA_MONITOR,
        FAMILY_OBSERVABILITY,
    ],
    STATE_ARCHITECTURE_DEBT: [
        FAMILY_ARCHITECTURE,
        FAMILY_OBSERVABILITY,
        FAMILY_MAINTENANCE,
        # Also allow non-reinforcement research tasks
        FAMILY_CALIBRATION,
        FAMILY_FEATURE,
        FAMILY_REGIME,
        FAMILY_ODDS,
        FAMILY_BACKTEST,
        FAMILY_SIMULATION,
    ],
    STATE_OPERATOR_UX_GAP: [
        FAMILY_OBSERVABILITY,
        FAMILY_MAINTENANCE,
        FAMILY_DATA_MONITOR,
        FAMILY_SYSTEM_RELIABILITY,
    ],
}

_STATE_BLOCKED_FAMILIES: dict[str, list[str]] = {
    STATE_DATA_WAITING: [
        # Learning families — require COMPUTED CLV, blocked while all CLV is PENDING
        FAMILY_STRATEGY_REINFORCEMENT,
        FAMILY_MODEL_VALIDATION,
        FAMILY_MODEL_PATCH,
        FAMILY_FEEDBACK,
        FAMILY_CLV_REINFORCEMENT,
        # Calibration / feature changes require settled data
        FAMILY_CALIBRATION,
        FAMILY_FEATURE,
        FAMILY_REGIME,
        FAMILY_BACKTEST,
    ],
    STATE_DATA_READY: [],  # nothing blocked
    STATE_MODEL_WEAKNESS: [
        FAMILY_STRATEGY_REINFORCEMENT,  # don't reinforce a weak model
    ],
    STATE_SYSTEM_RELIABILITY: [
        FAMILY_MODEL_PATCH,
        FAMILY_MODEL_VALIDATION,
        FAMILY_STRATEGY_REINFORCEMENT,
        FAMILY_CALIBRATION,
        FAMILY_FEATURE,
        FAMILY_REGIME,
        FAMILY_ODDS,
        FAMILY_FEEDBACK,
        FAMILY_BACKTEST,
    ],
    STATE_ARCHITECTURE_DEBT: [
        FAMILY_STRATEGY_REINFORCEMENT,  # don't reinforce during cleanup
        FAMILY_MODEL_PATCH,
    ],
    STATE_OPERATOR_UX_GAP: [
        FAMILY_MODEL_PATCH,
        FAMILY_STRATEGY_REINFORCEMENT,
        FAMILY_MODEL_VALIDATION,
    ],
}

_STATE_RECOMMENDED_ACTIONS: dict[str, str] = {
    STATE_DATA_WAITING: (
        "Wait for market settlement. Run closing odds monitor and data freshness audit. "
        "Safe non-learning tasks (closing-monitor, ops-report, architecture-cleanup) are allowed. "
        "Learning families (model-patch, calibration, strategy-reinforcement) remain blocked "
        "until at least one COMPUTED CLV record exists."
    ),
    STATE_DATA_READY: (
        "Proceed with model validation and strategy feedback. "
        "CLV computed records are available for learning."
    ),
    STATE_MODEL_WEAKNESS: (
        "Generate model patch tasks targeting weak regimes. "
        "Do not reinforce strategy until Brier / CLV improves."
    ),
    STATE_SYSTEM_RELIABILITY: (
        "Fix system reliability issues first (stale daemon, missing artifacts, skip storm). "
        "All model learning tasks are blocked until reliability is restored."
    ),
    STATE_ARCHITECTURE_DEBT: (
        "Run architecture cleanup tasks to reduce module duplication and stale docs. "
        "Resume model work after cleanup."
    ),
    STATE_OPERATOR_UX_GAP: (
        "Update decision card to expose missing governance fields. "
        "Operator visibility must be restored before model tasks resume."
    ),
}


# ─────────────────────────────────────────────
# Main classifier
# ─────────────────────────────────────────────

def classify(
    *,
    reports_dir: Path | None = None,
    decision_card_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Classify the current optimization state from real system data.

    Returns:
      state                  : str — one of the six STATE_* constants
      reasons                : list[str]
      allowed_task_families  : list[str]
      blocked_task_families  : list[str]
      recommended_next_action: str
      sub_checks             : dict — raw sub-check results for observability
      classified_at          : str — UTC ISO timestamp
    """
    now_str = datetime.now(timezone.utc).isoformat()

    clv      = _check_clv_readiness(reports_dir)
    weakness = _check_model_weakness()
    system   = _check_system_reliability()
    arch     = _check_architecture_debt()
    ux       = _check_operator_ux_gap(decision_card_payload)

    # ── Priority order (highest to lowest): ─────────────────────────────────
    # 1. SYSTEM_RELIABILITY_ISSUE — fix infra first
    # 2. DATA_WAITING             — no learning without data
    # 3. OPERATOR_UX_GAP         — visibility before action
    # 4. MODEL_WEAKNESS_DETECTED  — patch before reinforcing
    # 5. ARCHITECTURE_DEBT        — cleanup
    # 6. DATA_READY               — normal operation

    reasons: list[str] = []
    state: str

    if system["issue_detected"]:
        state = STATE_SYSTEM_RELIABILITY
        reasons = system["reasons"]
    elif not clv["ready"]:
        state = STATE_DATA_WAITING
        if clv["all_pending"]:
            reasons.append(
                f"all_clv_pending: {clv['pending']} PENDING_CLOSING, 0 COMPUTED"
            )
        elif clv["total"] == 0:
            reasons.append("no_clv_records: Phase 6U has produced no CLV records yet")
        else:
            reasons.append(
                f"insufficient_computed_clv: computed={clv['computed']} / "
                f"total={clv['total']} ({clv['computed_fraction']*100:.1f}% "
                f"< {_COMPUTED_CLV_MIN_FRACTION*100:.0f}% threshold)"
            )
    elif ux["gap_detected"]:
        state = STATE_OPERATOR_UX_GAP
        reasons = ux["reasons"]
    elif weakness["weakness_detected"]:
        state = STATE_MODEL_WEAKNESS
        reasons = weakness["reasons"]
    elif arch["debt_detected"]:
        state = STATE_ARCHITECTURE_DEBT
        reasons = arch["reasons"]
    else:
        state = STATE_DATA_READY
        reasons.append(
            f"clv_computed_available: {clv['computed']} COMPUTED records "
            f"({clv['computed_fraction']*100:.1f}% of total)"
        )

    return {
        "state": state,
        "reasons": reasons,
        "allowed_task_families": _STATE_ALLOWED_FAMILIES[state],
        "blocked_task_families": _STATE_BLOCKED_FAMILIES[state],
        "recommended_next_action": _STATE_RECOMMENDED_ACTIONS[state],
        "sub_checks": {
            "clv": clv,
            "model_weakness": weakness,
            "system_reliability": system,
            "architecture_debt": arch,
            "operator_ux_gap": ux,
        },
        "classified_at": now_str,
    }


# ─────────────────────────────────────────────
# Convenience helpers for planner / card
# ─────────────────────────────────────────────

def is_task_family_allowed(family: str, state_result: dict[str, Any]) -> bool:
    """Return True if *family* is in the allowed list for the current state."""
    return family in state_result.get("allowed_task_families", [])


def is_task_family_blocked(family: str, state_result: dict[str, Any]) -> bool:
    """Return True if *family* is explicitly blocked for the current state."""
    return family in state_result.get("blocked_task_families", [])


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    result = classify()
    print(json.dumps(result, indent=2, ensure_ascii=False))
