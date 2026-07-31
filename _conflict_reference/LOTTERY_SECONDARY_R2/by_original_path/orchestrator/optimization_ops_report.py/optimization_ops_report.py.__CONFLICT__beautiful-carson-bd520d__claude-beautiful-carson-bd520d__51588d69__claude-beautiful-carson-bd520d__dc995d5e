"""
Phase 9 — Autonomous Optimization Operations Report

Summarises scheduler activity over a time window (8h or 24h) and evaluates
whether the autonomous system is actually improving.

Reads:
  - agent_tasks / agent_task_runs  (via db)
  - training_memory                (patch history, state transitions)
  - optimization_state transitions
  - Phase 6/7/8 summaries

Returns a structured dict and classifies the window into one of:
  EFFECTIVE | PARTIAL | IDLE | DEGRADED | BLOCKED

HARD RULES (never modify):
  - Does not touch model logic
  - Does not weaken Phase 6/7/8 gates
  - Does not fake improvements
  - Does not mark PENDING CLV as COMPUTED
  - Does not delete tasks or reports
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]


# ─────────────────────────────────────────────
# Window classification constants
# ─────────────────────────────────────────────

CLASS_EFFECTIVE = "EFFECTIVE"
CLASS_PARTIAL      = "PARTIAL"
CLASS_IDLE         = "IDLE"
CLASS_DEGRADED     = "DEGRADED"
CLASS_BLOCKED      = "BLOCKED"
CLASS_WAITING_ACTIVE = "WAITING_ACTIVE"

# ─────────────────────────────────────────────
# Improvement dimension constants
# ─────────────────────────────────────────────

DIM_SYSTEM_FUNCTIONALITY    = "system_functionality"
DIM_ARCHITECTURE_QUALITY    = "architecture_quality"
DIM_ANALYSIS_CORRECTNESS    = "analysis_correctness"
DIM_DATA_TRUSTWORTHINESS    = "data_trustworthiness"
DIM_MODEL_LEARNING          = "model_learning"
DIM_OPERATIONAL_RELIABILITY = "operational_reliability"
DIM_STRATEGY_FEEDBACK       = "strategy_feedback"

ALL_DIMENSIONS = {
    DIM_SYSTEM_FUNCTIONALITY,
    DIM_ARCHITECTURE_QUALITY,
    DIM_ANALYSIS_CORRECTNESS,
    DIM_DATA_TRUSTWORTHINESS,
    DIM_MODEL_LEARNING,
    DIM_OPERATIONAL_RELIABILITY,
    DIM_STRATEGY_FEEDBACK,
}

# ── family → dimension mapping ───────────────────────────────────────────
_FAMILY_TO_DIMENSIONS: dict[str, list[str]] = {
    "strategy-reinforcement":     [DIM_STRATEGY_FEEDBACK, DIM_MODEL_LEARNING],
    "model-validation-atomic":    [DIM_MODEL_LEARNING, DIM_ANALYSIS_CORRECTNESS],
    "model-patch-atomic":         [DIM_MODEL_LEARNING, DIM_ANALYSIS_CORRECTNESS],
    "calibration-atomic":         [DIM_MODEL_LEARNING, DIM_ANALYSIS_CORRECTNESS],
    "feature-atomic":             [DIM_MODEL_LEARNING, DIM_DATA_TRUSTWORTHINESS],
    "regime-atomic":              [DIM_MODEL_LEARNING, DIM_ANALYSIS_CORRECTNESS],
    "odds-atomic":                [DIM_DATA_TRUSTWORTHINESS, DIM_ANALYSIS_CORRECTNESS],
    "feedback-atomic":            [DIM_STRATEGY_FEEDBACK],
    "backtest-validity-atomic":   [DIM_ANALYSIS_CORRECTNESS, DIM_DATA_TRUSTWORTHINESS],
    "simulation-atomic":          [DIM_ANALYSIS_CORRECTNESS, DIM_SYSTEM_FUNCTIONALITY],
    "data-monitor":               [DIM_DATA_TRUSTWORTHINESS, DIM_OPERATIONAL_RELIABILITY],
    "system-reliability":         [DIM_OPERATIONAL_RELIABILITY, DIM_SYSTEM_FUNCTIONALITY],
    "architecture-cleanup":       [DIM_ARCHITECTURE_QUALITY],
    "observability-ux":           [DIM_OPERATIONAL_RELIABILITY, DIM_ARCHITECTURE_QUALITY],
    "maintenance":                [DIM_OPERATIONAL_RELIABILITY],
}


def get_task_dimensions(task: dict) -> list[str]:
    """
    Map a task to one or more improvement dimensions based on analysis_family.
    Falls back to title keyword heuristics if family is not mapped.
    Returns [] if no dimension can be determined.
    """
    family = (task.get("analysis_family") or task.get("focus_keys") or "").strip()
    if family in _FAMILY_TO_DIMENSIONS:
        return _FAMILY_TO_DIMENSIONS[family]

    # Heuristic fallback: keywords in title
    title = (task.get("title") or "").lower()
    dims: list[str] = []
    if any(w in title for w in ("patch", "model", "feature", "calibr")):
        dims.append(DIM_MODEL_LEARNING)
    if any(w in title for w in ("strategy", "feedback", "reinforce")):
        dims.append(DIM_STRATEGY_FEEDBACK)
    if any(w in title for w in ("arch", "cleanup", "refactor", "duplicate")):
        dims.append(DIM_ARCHITECTURE_QUALITY)
    if any(w in title for w in ("data", "trust", "closing", "clv")):
        dims.append(DIM_DATA_TRUSTWORTHINESS)
    if any(w in title for w in ("system", "reliab", "daemon", "heartbeat")):
        dims.append(DIM_OPERATIONAL_RELIABILITY)
    if any(w in title for w in ("analysis", "correct", "backtest", "valid")):
        dims.append(DIM_ANALYSIS_CORRECTNESS)
    if any(w in title for w in ("ux", "observab", "decision card", "ops")):
        dims.append(DIM_OPERATIONAL_RELIABILITY)
    return list(dict.fromkeys(dims))  # deduplicate, preserve order


# ─────────────────────────────────────────────
# Data gathering helpers
# ─────────────────────────────────────────────

def _since_iso(hours: int) -> str:
    """ISO timestamp for `hours` ago."""
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def _query_tasks_in_window(since: str) -> list[dict]:
    """Return all agent_tasks created or updated since `since`."""
    try:
        from orchestrator import db
        conn = db.get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM agent_tasks WHERE created_at >= ? OR updated_at >= ? "
                "ORDER BY id DESC LIMIT 500",
                (since, since),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("[OpsReport] task query failed: %s", exc)
        return []


def _query_runs_in_window(since: str) -> list[dict]:
    """Return all agent_task_runs with tick_at >= since."""
    try:
        from orchestrator import db
        return db.list_runs_filtered(since=since, limit=1000)
    except Exception as exc:
        logger.warning("[OpsReport] runs query failed: %s", exc)
        return []


def _count_consecutive_skips(runs: list[dict]) -> int:
    """
    Phase 12: Count consecutive unexplained skips at the head of ``runs``.

    Hard-off and scheduler-disabled skips are deliberately excluded —
    they are protective behaviour, not system degradation.

    Runs must be sorted most-recent-first.
    """
    from orchestrator.scheduler_skip_classifier import count_unexplained_consecutive_skips
    return count_unexplained_consecutive_skips(runs)


def _count_skip_reasons(runs: list[dict]) -> dict[str, int]:
    """Return a summary dict of skip reason counts across all runs."""
    from orchestrator.scheduler_skip_classifier import classify_all_skips
    return classify_all_skips(runs)


def _get_training_memory_summary() -> dict[str, Any]:
    """Read training memory for patch/CLV stats."""
    try:
        from orchestrator import training_memory as tm
        mem = tm.load_memory()
        patch_hist = mem.get("patch_history", [])
        transitions = mem.get("optimization_state_transitions", [])
        clv_outcomes = mem.get("clv_outcomes", [])
        learning_cycles: list[dict] = mem.get("learning_cycles", [])
        latest_learning_cycle = learning_cycles[-1] if learning_cycles else None
        gate_decisions: list[dict] = mem.get("gate_decisions", [])
        latest_gate_decision = gate_decisions[-1] if gate_decisions else None
        patch_evaluations: list[dict] = mem.get("patch_evaluations", [])
        latest_patch_evaluation = patch_evaluations[-1] if patch_evaluations else None
        eval_gate_decisions: list[dict] = mem.get("patch_eval_gate_decisions", [])
        latest_eval_gate_decision = eval_gate_decisions[-1] if eval_gate_decisions else None
        return {
            "patch_total": len(patch_hist),
            "state_transitions": transitions,
            "clv_outcomes": clv_outcomes,
            "difficulty_level": mem.get("difficulty_level", 1),
            "consecutive_successes": mem.get("consecutive_successes", 0),
            "consecutive_failures": mem.get("consecutive_failures", 0),
            "learning_cycles_total": len(learning_cycles),
            "latest_learning_cycle": latest_learning_cycle,
            "gate_decisions_total": len(gate_decisions),
            "latest_gate_decision": latest_gate_decision,
            "patch_evaluations_total": len(patch_evaluations),
            "latest_patch_evaluation": latest_patch_evaluation,
            "eval_gate_decisions_total": len(eval_gate_decisions),
            "latest_eval_gate_decision": latest_eval_gate_decision,
        }
    except Exception as exc:
        logger.warning("[OpsReport] training memory read failed: %s", exc)
        return {}


def _get_human_review_queue_summary() -> dict:
    """Return Phase 24 human review queue summary."""
    try:
        from orchestrator.human_review_queue import get_queue_summary
        return get_queue_summary()
    except Exception as exc:
        logger.debug("[OpsReport] human review queue unavailable: %s", exc)
        return {}


def _get_phase6_summary() -> dict[str, Any]:
    """Read Phase 6 CLV state."""
    try:
        from orchestrator import phase6_data_registry
        s = phase6_data_registry.get_phase6_status()
        return {
            "clv_computed": s.get("clv_computed", 0),
            "clv_pending": s.get("clv_pending_closing", 0),
            "clv_blocked": s.get("clv_blocked", 0),
            "clv_total": s.get("clv_total", 0),
            "all_clv_pending": s.get("all_clv_pending", False),
        }
    except Exception as exc:
        logger.debug("[OpsReport] phase6 summary unavailable: %s", exc)
        return {}


def _get_optimization_state_summary() -> dict[str, Any]:
    """Read current optimization state + history."""
    try:
        from orchestrator import optimization_state as os_mod
        result = os_mod.classify()
        return {
            "current_state": result.get("state"),
            "blocked_families": result.get("blocked_task_families", []),
            "reasons": result.get("reasons", []),
        }
    except Exception as exc:
        logger.debug("[OpsReport] optimization_state unavailable: %s", exc)
        return {}


# ─────────────────────────────────────────────
# Window classification
# ─────────────────────────────────────────────

def classify_window(
    tasks: list[dict],
    runs: list[dict],
    gov_blocked: int,
    consecutive_skips: int,
    opt_state: dict,
    effective_completed: list[dict] | None = None,
) -> str:
    """
    Classify the time window into one of: EFFECTIVE | PARTIAL | IDLE | DEGRADED | BLOCKED

    Rules (priority order):
    1. BLOCKED  — governance blocks all meaningful families AND nothing completed
    2. DEGRADED — ≥3 consecutive skips OR scheduler run failures dominate
    3. IDLE     — scheduler ran but no QUEUED/COMPLETED tasks at all
    4. PARTIAL  — tasks ran but most are pending/blocked or no improvements
    5. EFFECTIVE — at least one *quality-valid* completed task with measurable improvement

    Phase 10: If effective_completed is provided, only those tasks count toward
    EFFECTIVE classification.  Empty-artifact and noop completions do not qualify.
    """
    completed = [t for t in tasks if t.get("status") == "COMPLETED"]
    # Phase 10: restrict to quality-valid completions for effectiveness scoring
    if effective_completed is None:
        effective_completed = completed
    queued = [t for t in tasks if t.get("status") == "QUEUED"]
    running = [t for t in tasks if t.get("status") == "RUNNING"]
    active = completed + queued + running

    # Phase 12: analyse skip reason breakdown
    from orchestrator.scheduler_skip_classifier import (
        all_consecutive_skips_are_protected,
    )
    recent_sorted = sorted(runs, key=lambda r: r.get("tick_at", ""), reverse=True)
    all_skips_protected = all_consecutive_skips_are_protected(recent_sorted)

    # 1. BLOCKED / WAITING_ACTIVE — governance blocks learning families.
    # Distinguish: WAITING_ACTIVE when safe non-learning families remain available.
    # TRUE BLOCKED only when there is no safe work the scheduler can perform.
    blocked_families = opt_state.get("blocked_families", [])
    _safe_families = {
        "closing-monitor", "ops-report", "scheduler-health-check",
        "artifact-health-check", "wiki-maintenance", "architecture-cleanup",
        "observability-ux", "maintenance", "data-monitor", "system-reliability",
        "simulation-atomic",
    }
    allowed_families = set(opt_state.get("allowed_families", []))
    # DATA_WAITING state always keeps safe families allowed — treat as WAITING_ACTIVE.
    _current_state = opt_state.get("current_state", "")
    safe_work_available = (
        bool(allowed_families & _safe_families)
        or _current_state == "DATA_WAITING"
    )

    # Phase 12: If hard-off is protecting all skips AND safe tasks ran on cadence,
    # classify as WAITING_ACTIVE (not BLOCKED, not DEGRADED).
    if all_skips_protected and completed and safe_work_available:
        return CLASS_WAITING_ACTIVE

    if len(blocked_families) >= 4 and not completed:
        if safe_work_available:
            return CLASS_WAITING_ACTIVE
        return CLASS_BLOCKED

    # 2. DEGRADED — persistent unexplained skip storms or API/daemon failures.
    # Phase 12: consecutive_skips already excludes hard-off skips (see _count_consecutive_skips).
    # Additional guard: if ALL consecutive skips are hard-off protected, never DEGRADE.
    if consecutive_skips >= 3 and not all_skips_protected:
        return CLASS_DEGRADED
    error_runs = [r for r in runs if r.get("outcome", "").upper() in ("ERROR", "FAILED", "FAILURE")]
    if len(error_runs) >= 3 and not completed:
        return CLASS_DEGRADED

    # 3. IDLE — scheduler ran (runs exist) but no tasks touched
    if runs and not active:
        return CLASS_IDLE
    if not runs and not active:
        return CLASS_IDLE

    # 4. EFFECTIVE — completed tasks with improvement dimensions (quality-valid only)
    if effective_completed:
        improved = [
            t for t in effective_completed
            if get_task_dimensions(t)
        ]
        has_improvement = len(improved) >= 1
        no_critical_failure = consecutive_skips < 3
        if has_improvement and no_critical_failure:
            return CLASS_EFFECTIVE

    # 5. PARTIAL — tasks exist but not enough completed
    if active:
        return CLASS_PARTIAL

    return CLASS_IDLE


# ─────────────────────────────────────────────
# Top improvements extraction
# ─────────────────────────────────────────────

def _extract_top_improvements(completed_tasks: list[dict], n: int = 5) -> list[dict]:
    """
    Build a list of the most impactful completed tasks with dimension labels.
    """
    results: list[dict] = []
    for t in completed_tasks:
        dims = get_task_dimensions(t)
        if not dims:
            continue
        results.append({
            "task_id": t.get("id"),
            "title": t.get("title", ""),
            "analysis_family": t.get("analysis_family") or t.get("focus_keys", ""),
            "dimensions": dims,
            "completed_at": t.get("completed_at", ""),
        })
    # Sort by completed_at descending, newest first
    results.sort(key=lambda x: x.get("completed_at", ""), reverse=True)
    return results[:n]


def _flag_tasks_without_dimensions(tasks: list[dict]) -> list[dict]:
    """Return COMPLETED tasks that could not be mapped to any dimension."""
    return [
        t for t in tasks
        if t.get("status") == "COMPLETED" and not get_task_dimensions(t)
    ]


# ─────────────────────────────────────────────
# Next focus recommendation
# ─────────────────────────────────────────────

def _recommend_next_focus(
    classification: str,
    opt_state: dict,
    p6: dict,
    mem: dict,
) -> str:
    if classification == CLASS_BLOCKED:
        reasons = opt_state.get("reasons", [])
        return f"Unblock governance first: {reasons[0]}" if reasons else "Investigate governance block."

    if classification == CLASS_WAITING_ACTIVE:
        p = p6.get("clv_pending", 0)
        return (
            f"DATA_WAITING: {p} CLV record(s) PENDING_CLOSING. "
            "Run closing-monitor / odds freshness audit. "
            "Learning blocked until closing odds arrive — safe non-learning tasks are enabled."
        )

    if classification == CLASS_DEGRADED:
        return "Fix scheduler reliability: investigate skip storm or API failure."

    if classification == CLASS_IDLE:
        return "No tasks generated. Check planner_tick configuration and blueprint coverage."

    state = opt_state.get("current_state", "")
    if state == "DATA_WAITING":
        p = p6.get("clv_pending", 0)
        return f"Wait for market settlement ({p} CLV records pending). No learning tasks."

    if state == "MODEL_WEAKNESS_DETECTED":
        failures = mem.get("consecutive_failures", 0)
        return f"Prioritize model-patch tasks. Consecutive failures: {failures}."

    if state == "SYSTEM_RELIABILITY_ISSUE":
        return "Restore system reliability before model tasks."

    clv_c = p6.get("clv_computed", 0)
    if clv_c >= 1:
        return f"Run model validation / strategy reinforcement ({clv_c} COMPUTED CLV available)."

    return "Continue monitoring. Await more data before scheduling learning tasks."


# ─────────────────────────────────────────────
# Phase 15 — Closing availability summary helper
# ─────────────────────────────────────────────

def _get_closing_availability_summary() -> dict[str, Any]:
    """
    Phase 15/16/17 — Pull per-record diagnostic summary from closing_odds_monitor.
    Phase 16 adds: next_refresh_action, refresh_task_due, last_refresh_task,
    source_refresh_blocked_reason.
    Phase 17 adds: last_refresh_action, last_refresh_improved, consecutive_no_improvement,
    escalation_recommended, recommended_escalation_action.
    Read-only. Returns {available: False} on any import or runtime error.
    """
    try:
        from orchestrator.closing_odds_monitor import get_pending_diagnostics
        from orchestrator.planner_tick import _choose_closing_refresh_action
        from orchestrator.data_waiting_cadence import cadence_dedupe_key, is_safe_task_due
        diag = get_pending_diagnostics()
        ss = diag.get("source_summary", {})

        # Phase 16 enrichment
        next_refresh_action = _choose_closing_refresh_action(ss)

        # Is the chosen refresh action currently due (cadence slot open)?
        try:
            refresh_task_due = is_safe_task_due(next_refresh_action)
        except Exception:
            refresh_task_due = None

        # Last completed refresh task from DB
        last_refresh_task: dict | None = None
        try:
            from orchestrator import db
            refresh_types = (
                "refresh_external_closing",
                "refresh_tsl_closing",
                "closing_availability_audit",
                "closing_monitor",
                "manual_review_summary",
            )
            conn = db.get_conn()
            try:
                row = conn.execute(
                    "SELECT id, task_type, status, completed_at FROM agent_tasks "
                    "WHERE task_type IN ({}) "
                    "AND status='COMPLETED' "
                    "ORDER BY completed_at DESC LIMIT 1".format(
                        ",".join("?" * len(refresh_types))
                    ),
                    refresh_types,
                ).fetchone()
            finally:
                conn.close()
            if row:
                last_refresh_task = {
                    "id": row[0],
                    "task_type": row[1],
                    "status": row[2],
                    "completed_at": row[3],
                }
        except Exception:
            last_refresh_task = None

        # Blocked reason (external refresh not wired to live API)
        source_refresh_blocked_reason: str | None = None
        if next_refresh_action == "refresh_external_closing":
            source_refresh_blocked_reason = (
                "External closing data requires a live odds source. "
                "No paid API is configured — running diagnostic only."
            )
        elif next_refresh_action == "manual_review_summary":
            source_refresh_blocked_reason = (
                "Automated refresh exhausted — escalation triggered. "
                "Operator manual review required."
            )

        # Phase 17: refresh feedback
        _last_refresh_action: str | None = None
        _last_refresh_improved: bool | None = None
        _consecutive_no_improvement: int = 0
        _escalation_recommended: bool = False
        _recommended_escalation_action: str = "continue"
        try:
            from orchestrator.closing_refresh_memory import get_refresh_feedback_summary
            rfb = get_refresh_feedback_summary()
            _last_refresh_action = rfb.get("last_refresh_action")
            _last_refresh_improved = rfb.get("last_refresh_improved")
            _consecutive_no_improvement = rfb.get("consecutive_no_improvement", 0)
            _escalation_recommended = rfb.get("escalation_recommended", False)
            _recommended_escalation_action = rfb.get("recommended_escalation_action", "continue")
        except Exception:
            pass

        return {
            "available": True,
            **ss,
            "next_refresh_action": next_refresh_action,
            "refresh_task_due": refresh_task_due,
            "last_refresh_task": last_refresh_task,
            "source_refresh_blocked_reason": source_refresh_blocked_reason,
            # Phase 17 fields
            "last_refresh_action": _last_refresh_action,
            "last_refresh_improved": _last_refresh_improved,
            "consecutive_no_improvement": _consecutive_no_improvement,
            "escalation_recommended": _escalation_recommended,
            "recommended_escalation_action": _recommended_escalation_action,
        }
    except Exception as exc:
        logger.debug("[OpsReport] closing_availability unavailable: %s", exc)
        return {"available": False}


# ─────────────────────────────────────────────
# Main report generator
# ─────────────────────────────────────────────

def generate_report(window: str = "8h") -> dict[str, Any]:
    """
    Generate an operations summary for the given window.

    Args:
        window: "8h" | "24h"

    Returns:
        Full report dict with classification, stats, improvements, recommendations.

    HARD RULES: Read-only. Never modifies DB, memory, or CLV state.
    """
    hours = 24 if "24" in window else 8
    since = _since_iso(hours)
    window_label = f"{hours}h"

    now_str = datetime.now(timezone.utc).isoformat()

    tasks = _query_tasks_in_window(since)
    runs = _query_runs_in_window(since)
    mem = _get_training_memory_summary()
    p6 = _get_phase6_summary()
    opt_state = _get_optimization_state_summary()

    # ── Task breakdown ────────────────────────────────────────────
    created = tasks  # all tasks in window (created_at or updated_at >= since)
    completed = [t for t in tasks if t.get("status") == "COMPLETED"]
    queued = [t for t in tasks if t.get("status") == "QUEUED"]
    running = [t for t in tasks if t.get("status") == "RUNNING"]
    failed = [t for t in tasks if t.get("status") in ("FAILED", "ERROR")]
    archived = [t for t in tasks if t.get("status") == "ARCHIVED"]
    cancelled = [t for t in tasks if t.get("status") == "CANCELLED"]

    # ── Phase 10: Completion quality breakdown ────────────────────
    from orchestrator.task_completion_validator import (
        QUALITY_VALID, QUALITY_DIAGNOSTIC_ONLY, QUALITY_EMPTY_ARTIFACT,
        QUALITY_NOOP, QUALITY_EFFECTIVE_STATES, validate_completion,
    )

    def _resolve_task_quality(task: dict) -> str:
        """
        Return persisted completion_quality, or compute it on-the-fly for tasks
        completed before Phase 10 was deployed (NULL quality field).
        This ensures task #6169 and similar are correctly classified even without
        a backfill pass.
        """
        q = task.get("completion_quality")
        if q:
            return q
        result = {
            "success": True,
            "completed_text": task.get("completed_text") or "",
            "completed_file_path": task.get("completed_file_path"),
            "changed_files": [],
            "execution_log": "",
            "duration_seconds": task.get("duration_seconds") or 0,
        }
        return validate_completion(task, result)["quality"]

    completed_empty_artifact = [
        t for t in completed if _resolve_task_quality(t) == QUALITY_EMPTY_ARTIFACT
    ]
    completed_noop = [
        t for t in completed if _resolve_task_quality(t) == QUALITY_NOOP
    ]
    completed_diagnostic = [
        t for t in completed if _resolve_task_quality(t) == QUALITY_DIAGNOSTIC_ONLY
    ]
    completed_valid = [
        t for t in completed
        if _resolve_task_quality(t) in QUALITY_EFFECTIVE_STATES
    ]
    # Tasks completed before Phase 10 deployed have no quality field →
    # on-the-fly validation above determines their true quality.
    effective_completed = completed_valid

    # ── Patch stats (from training memory) ────────────────────────
    recent_patches = [
        p for p in mem.get("patch_history", [])
        if (p.get("timestamp") or "") >= since
    ] if "patch_history" in mem else []
    # Note: training_memory doesn't separately track "rejected patches" vs "kept" by default.
    # We approximate: "kept" = PASSED outcome, "rejected" = FAILED or below threshold.
    patches_validated = len(recent_patches)
    patches_kept = sum(1 for p in recent_patches if p.get("outcome") in ("PASSED", "SUCCESS", "KEPT"))
    patches_rejected = patches_validated - patches_kept

    # ── Governance data ────────────────────────────────────────────
    # Count governance-blocked runs from run log messages
    gov_blocked_runs = sum(
        1 for r in runs
        if "governance" in (r.get("message") or "").lower()
        or "blocked" in (r.get("message") or "").lower()
    )

    # ── Strategy reinforcements ────────────────────────────────────
    strategy_reinforcements = sum(
        1 for t in completed
        if (t.get("analysis_family") or "") == "strategy-reinforcement"
    )

    # ── System reliability issues ──────────────────────────────────
    system_reliability_issues: list[str] = list(opt_state.get("reasons", []))
    # Also check training memory for failure signals
    if mem.get("consecutive_failures", 0) >= 2:
        system_reliability_issues.append(
            f"consecutive_failures: {mem['consecutive_failures']}"
        )

    # ── Consecutive skips & Phase 12 skip reason breakdown ────────
    recent_runs_sorted = sorted(runs, key=lambda r: r.get("tick_at", ""), reverse=True)
    consecutive_skips = _count_consecutive_skips(recent_runs_sorted)
    # Phase 12: pre-compute skip reasons so both classify_window and the report dict share them
    from orchestrator.scheduler_skip_classifier import (
        classify_all_skips as _classify_all_skips,
        SKIP_HARD_OFF as _SKIP_HARD_OFF,
        SKIP_SCHEDULER_OFF as _SKIP_SCHEDULER_OFF,
    )
    _skip_reasons = _classify_all_skips(runs)
    _hard_off_count = _skip_reasons.get(_SKIP_HARD_OFF, 0) + _skip_reasons.get(_SKIP_SCHEDULER_OFF, 0)

    # ── Classification ────────────────────────────────────────────
    classification = classify_window(
        tasks=tasks,
        runs=runs,
        gov_blocked=gov_blocked_runs,
        consecutive_skips=consecutive_skips,
        opt_state=opt_state,
        effective_completed=effective_completed,
    )

    # ── Top improvements ──────────────────────────────────────────
    top_improvements = _extract_top_improvements(effective_completed)
    tasks_without_dims = _flag_tasks_without_dimensions(tasks)

    # ── Next focus recommendation ─────────────────────────────────
    next_focus = _recommend_next_focus(classification, opt_state, p6, mem)

    # ── Phase 15: closing availability ───────────────────────────
    closing_availability = _get_closing_availability_summary()
    ca = closing_availability
    _pending = ca.get("pending_total", 0)
    _inv_before = ca.get("invalid_before_prediction", 0)
    _inv_same = ca.get("invalid_same_snapshot", 0)
    _missing = ca.get("missing_all_sources", 0)
    closing_sub_classification: str | None = None
    if (
        ca.get("available")
        and _pending > 0
        and (_inv_before + _inv_same) == _pending
        and _missing == 0
    ):
        closing_sub_classification = "DATA_WAITING_WITH_PRE_PREDICTION_ONLY_CLOSING"

    return {
        "window": window_label,
        "since": since,
        "generated_at": now_str,
        "classification": classification,
        # Task counts
        "tasks_created": len(created),
        "tasks_completed": len(completed),
        "tasks_queued": len(queued),
        "tasks_running": len(running),
        "tasks_failed": len(failed),
        "tasks_archived": len(archived),
        "tasks_cancelled": len(cancelled),
        "tasks_rejected": len(failed) + len(cancelled),
        # Phase 10 completion quality breakdown
        "completed_valid_tasks": len(completed_valid),
        "completed_diagnostic_only": len(completed_diagnostic),
        "completed_empty_artifact": len(completed_empty_artifact),
        "completed_noop": len(completed_noop),
        "effective_completed_tasks": len(effective_completed),
        # Governance
        "governance_blocked": gov_blocked_runs,
        "consecutive_skips": consecutive_skips,
        # Patches
        "patches_validated": patches_validated,
        "patches_kept": patches_kept,
        "patches_rejected": patches_rejected,
        # CLV state (from Phase 6 — read-only snapshot)
        "clv_computed": p6.get("clv_computed", 0),
        "clv_pending": p6.get("clv_pending", 0),
        # Strategy
        "strategy_reinforcements": strategy_reinforcements,
        # Improvements
        "top_improvements": top_improvements,
        "tasks_without_dimension": [
            {"id": t.get("id"), "title": t.get("title", ""), "status": t.get("status", "")}
            for t in tasks_without_dims
        ],
        # System health
        "system_reliability_issues": system_reliability_issues,
        "optimization_state": opt_state.get("current_state", "UNKNOWN"),
        "optimization_blocked_families": opt_state.get("blocked_families", []),
        # Recommendation
        "next_recommended_focus": next_focus,
        # Memory metadata
        "difficulty_level": mem.get("difficulty_level", 1),
        "consecutive_failures": mem.get("consecutive_failures", 0),
        "consecutive_successes": mem.get("consecutive_successes", 0),
        # Run counts
        "scheduler_runs": len(runs),
        # Phase 12: skip reason breakdown
        "skip_reasons": _skip_reasons,
        "hard_off_skip_count": _hard_off_count,
        # Phase 15: closing availability
        "closing_availability": closing_availability,
        "closing_sub_classification": closing_sub_classification,
        # Phase 24: human review queue
        "human_review_queue": _get_human_review_queue_summary(),
    }


# ─────────────────────────────────────────────
# Markdown renderer
# ─────────────────────────────────────────────

def render_markdown(report: dict) -> str:
    """Render the report dict as a Markdown document."""
    bar = "=" * 70
    sub = "-" * 50
    lines: list[str] = []

    cl = report["classification"]
    emoji_map = {
        CLASS_EFFECTIVE:      "✅",
        CLASS_PARTIAL:        "⚠️",
        CLASS_IDLE:           "💤",
        CLASS_DEGRADED:       "🔴",
        CLASS_BLOCKED:        "🚫",
        CLASS_WAITING_ACTIVE: "⏳",
    }
    em = emoji_map.get(cl, "❓")

    lines += [
        f"# Phase 9 Autonomous Optimization Ops Report",
        f"",
        f"**Window** : {report['window']}  ",
        f"**Since**  : {report['since']}  ",
        f"**Generated** : {report['generated_at']}  ",
        f"",
        f"## {em} Window Classification: {cl}",
        f"",
    ]

    # ── Task summary ─────────────────────────────────────────────────
    lines += [
        f"## Task Summary",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Created | {report['tasks_created']} |",
        f"| Completed | {report['tasks_completed']} |",
        f"| Queued | {report['tasks_queued']} |",
        f"| Running | {report['tasks_running']} |",
        f"| Failed / Rejected | {report['tasks_rejected']} |",
        f"| Governance blocked (runs) | {report['governance_blocked']} |",
        f"| Consecutive skips (unexplained) | {report['consecutive_skips']} |",
        f"| Hard-off protected skips | {report.get('hard_off_skip_count', 0)} |",
        f"",
    ]

    # ── Phase 12 skip reason breakdown ─────────────────────────────
    skip_reasons = report.get("skip_reasons") or {}
    if skip_reasons:
        lines += [
            f"## Skip Reason Breakdown",
            f"",
            f"| Reason | Count |",
            f"|--------|-------|",
        ]
        for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason} | {count} |")
        hard_off = report.get("hard_off_skip_count", 0)
        if hard_off > 0:
            lines.append(f"")
            lines.append(
                f"> ℹ️ **{hard_off} skip(s) are hard-off protected** — "
                f"not counted as system degradation."
            )
        lines.append(f"")

    # ── Phase 10 completion quality breakdown ────────────────────────
    empty_count = report.get("completed_empty_artifact", 0)
    noop_count = report.get("completed_noop", 0)
    diag_count = report.get("completed_diagnostic_only", 0)
    valid_count = report.get("completed_valid_tasks", 0) - diag_count
    effective_count = report.get("effective_completed_tasks", report.get("tasks_completed", 0))
    if report.get("tasks_completed", 0) > 0:
        lines += [
            f"## Completion Quality",
            f"",
            f"| Quality | Count |",
            f"|---------|-------|",
            f"| Valid (substantive) | {max(valid_count, 0)} |",
            f"| Diagnostic Only | {diag_count} |",
            f"| Empty Artifact | {empty_count} |",
            f"| No-Op | {noop_count} |",
            f"| **Effective total** | **{effective_count}** |",
            f"",
        ]
        if empty_count > 0 or noop_count > 0:
            lines.append(
                f"> ⚠️ **Completion Quality Warning**: {empty_count} empty-artifact "
                f"and {noop_count} no-op completion(s) detected — these are excluded "
                f"from the effective count. LLM provider may not have an active session."
            )
            lines.append("")

    # ── Patch stats ──────────────────────────────────────────────────
    lines += [
        f"## Patch Stats",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Patches validated | {report['patches_validated']} |",
        f"| Patches kept | {report['patches_kept']} |",
        f"| Patches rejected | {report['patches_rejected']} |",
        f"| Strategy reinforcements | {report['strategy_reinforcements']} |",
        f"",
    ]

    # ── CLV data ──────────────────────────────────────────────────────
    lines += [
        f"## CLV Data State",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| CLV COMPUTED | {report['clv_computed']} |",
        f"| CLV PENDING | {report['clv_pending']} |",
        f"",
    ]

    # ── Phase 15/16: Closing Availability ──────────────────────────
    ca = report.get("closing_availability") or {}
    sub_class = report.get("closing_sub_classification")
    if ca.get("available"):
        lines += [
            f"## Closing Odds Availability",
            f"",
        ]
        if sub_class:
            lines.append(f"> ℹ️ **{sub_class}** — closing data exists but pre-dates all predictions.")
            lines.append("")
        lines += [
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Pending total | {ca.get('pending_total', 0)} |",
            f"| Computed total | {ca.get('computed_total', 0)} |",
            f"| Missing all sources | {ca.get('missing_all_sources', 0)} |",
            f"| Invalid (before prediction) | {ca.get('invalid_before_prediction', 0)} |",
            f"| Invalid (same snapshot) | {ca.get('invalid_same_snapshot', 0)} |",
            f"| Stale candidates | {ca.get('stale_candidates', 0)} |",
            f"| Ready to upgrade | {ca.get('ready_to_upgrade', 0)} |",
            f"| Recommended: refresh external | {ca.get('recommended_refresh_external', 0)} |",
            f"| Recommended: refresh TSL | {ca.get('recommended_refresh_tsl', 0)} |",
            f"| Manual review required | {ca.get('manual_review_required', 0)} |",
            f"",
            f"**Next closing action**: {ca.get('next_closing_action', '—')}",
            f"",
        ]
        # Phase 16 refresh fields
        next_refresh = ca.get("next_refresh_action")
        refresh_due = ca.get("refresh_task_due")
        last_refresh = ca.get("last_refresh_task")
        blocked_reason = ca.get("source_refresh_blocked_reason")
        if next_refresh:
            due_str = "YES" if refresh_due else ("NO" if refresh_due is False else "UNKNOWN")
            lines += [
                f"**Phase 16 Refresh Orchestration**:",
                f"",
                f"| Refresh Field | Value |",
                f"|---|---|",
                f"| Next refresh action | `{next_refresh}` |",
                f"| Refresh task due now | {due_str} |",
            ]
            if last_refresh:
                lines.append(
                    f"| Last refresh task | #{last_refresh.get('id')} "
                    f"`{last_refresh.get('task_type')}` @ {(last_refresh.get('completed_at') or '')[:16]} |"
                )
            else:
                lines.append(f"| Last refresh task | *(none)* |")
            lines.append("")
            if blocked_reason:
                lines.append(f"> ⚠️ **Refresh note**: {blocked_reason}")
                lines.append("")

        # Phase 17 refresh feedback
        last_action = ca.get("last_refresh_action")
        last_improved = ca.get("last_refresh_improved")
        consec = ca.get("consecutive_no_improvement", 0)
        esc_recommended = ca.get("escalation_recommended", False)
        esc_action = ca.get("recommended_escalation_action", "continue")
        if last_action is not None or consec > 0:
            improved_str = (
                "YES ✅" if last_improved is True
                else ("NO ❌" if last_improved is False else "—")
            )
            esc_str = "YES ⚠️" if esc_recommended else "NO ✅"
            lines += [
                f"**Phase 17 Refresh Feedback**:",
                f"",
                f"| Refresh Feedback | Value |",
                f"|---|---|",
                f"| Last refresh action | `{last_action or '—'}` |",
                f"| Last improved | {improved_str} |",
                f"| Consecutive no-improvement | {consec} |",
                f"| Escalation recommended | {esc_str} |",
                f"| Recommended escalation action | `{esc_action}` |",
                f"",
            ]

    # ── Phase 24: Human Review Queue ─────────────────────────────────
    hrq = report.get("human_review_queue") or {}
    hrq_pending = hrq.get("pending_count", 0)
    hrq_total = hrq.get("total", 0)
    if hrq_total > 0 or hrq_pending > 0:
        block_flag = "⚠️ BLOCKING PLANNER" if hrq.get("blocked_by_human_review") else "ok"
        lines += [
            f"## Phase 24: Human Review Queue",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total items | {hrq_total} |",
            f"| Pending (blocking) | {hrq_pending} |",
            f"| Approved | {hrq.get('approved_count', 0)} |",
            f"| Rejected | {hrq.get('rejected_count', 0)} |",
            f"| More data requested | {hrq.get('more_data_count', 0)} |",
            f"| Planner status | {block_flag} |",
            f"",
        ]
        if hrq_pending > 0:
            lines.append(
                f"> ⚠️ **{hrq_pending} review(s) PENDING** — planner is blocked until actioned."
            )
            lines.append(f"> Run: `python3 scripts/review_queue.py list`")
            lines.append("")
        latest_rev = hrq.get("latest_review")
        if latest_rev:
            lines += [
                f"**Latest review**: `{latest_rev.get('review_id', '?')}` "
                f"— {latest_rev.get('status', '?')} "
                f"({latest_rev.get('review_type', '?')})",
                f"",
            ]

    # ── Optimization governance ───────────────────────────────────────
    blocked_fam = ", ".join(report["optimization_blocked_families"]) or "(none)"
    lines += [
        f"## Optimization Governance",
        f"",
        f"- **Current state**: {report['optimization_state']}",
        f"- **Blocked families**: {blocked_fam}",
        f"",
    ]
    if report["system_reliability_issues"]:
        lines.append("**System reliability issues:**")
        for issue in report["system_reliability_issues"]:
            lines.append(f"  - {issue}")
        lines.append("")

    # ── Top improvements ─────────────────────────────────────────────
    if report["top_improvements"]:
        lines += [f"## Top Improvements", f""]
        for imp in report["top_improvements"]:
            dims = ", ".join(imp.get("dimensions", []))
            lines.append(
                f"- **{imp['title']}** (ID {imp['task_id']}) — `{imp['analysis_family']}` "
                f"→ {dims}"
            )
        lines.append("")

    # ── Tasks without dimension ──────────────────────────────────────
    no_dim = report.get("tasks_without_dimension", [])
    if no_dim:
        lines += [f"## ⚠️ Tasks Without Dimension (Review Required)", f""]
        for t in no_dim:
            lines.append(f"- ID {t['id']}: {t['title']} ({t['status']})")
        lines.append("")

    # ── Recommendation ───────────────────────────────────────────────
    lines += [
        f"## Next Recommended Focus",
        f"",
        f"{report['next_recommended_focus']}",
        f"",
        f"---",
        f"*Report generated by Phase 9 Autonomous Optimization Ops Reporter*",
    ]

    return "\n".join(lines)
