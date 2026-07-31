"""
Phase 13 — Autonomous Optimization Readiness Dashboard

Aggregates the state of Phases 6–12 into a single operator-facing readiness
summary.  OBSERVABILITY ONLY — does not trigger pipelines, write learning
state, or consume API credits.

Readiness states (priority order):
  LEARNING_READY   — CLV computed, governance allows learning families
  WAITING_ACTIVE   — CLV pending, but safe work is running on cadence
  SAFE_WORK_ACTIVE — Governance allows safe families; safe tasks ran recently
  BLOCKED          — All meaningful families blocked; no recent safe work
  DEGRADED         — Unexplained skip storm, broken scheduler, or only
                     empty-artifact completions in recent window

Severity:
  GREEN   — LEARNING_READY or WAITING_ACTIVE+healthy cadence
  YELLOW  — WAITING_ACTIVE but cadence lagging
  ORANGE  — BLOCKED or SAFE_WORK_ACTIVE without recent safe completions
  RED     — DEGRADED

HARD RULES:
  - Never modifies learning state
  - Never marks PENDING_CLOSING as COMPUTED
  - Never alters planner/worker behaviour
  - No external API calls
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── Readiness state constants ─────────────────────────────────────────────
RS_LEARNING_READY   = "LEARNING_READY"
RS_WAITING_ACTIVE   = "WAITING_ACTIVE"
RS_SAFE_WORK_ACTIVE = "SAFE_WORK_ACTIVE"
RS_BLOCKED          = "BLOCKED"
RS_DEGRADED         = "DEGRADED"

# ── Severity constants ────────────────────────────────────────────────────
SEV_GREEN  = "GREEN"
SEV_YELLOW = "YELLOW"
SEV_ORANGE = "ORANGE"
SEV_RED    = "RED"

# ── Safe task families (non-learning) ─────────────────────────────────────
_SAFE_FAMILIES: frozenset[str] = frozenset({
    "closing-monitor", "ops-report", "scheduler-health-check",
    "artifact-health-check", "wiki-maintenance", "architecture-cleanup",
    "observability-ux", "maintenance", "data-monitor", "system-reliability",
    "simulation-atomic",
})

# ── Learning families ──────────────────────────────────────────────────────
_LEARNING_FAMILIES: frozenset[str] = frozenset({
    "strategy-reinforcement", "model-validation-atomic", "model-patch-atomic",
    "calibration-atomic", "feature-atomic", "regime-atomic",
    "backtest-validity-atomic", "feedback-atomic", "clv-reinforcement",
})


# ─────────────────────────────────────────────────────────────────────────
# Data-gathering helpers (all read-only / lazy-import)
# ─────────────────────────────────────────────────────────────────────────

def _get_phase6() -> dict[str, Any]:
    try:
        from orchestrator import phase6_data_registry
        s = phase6_data_registry.get_phase6_status()
        return {
            "available": True,
            "clv_computed": s.get("clv_computed", 0),
            "clv_pending_closing": s.get("clv_pending_closing", 0),
            "clv_blocked": s.get("clv_blocked", 0),
            "all_clv_pending": s.get("all_clv_pending", False),
            "registry_rows": s.get("registry_rows", 0),
            "next_required_event": s.get("next_required_event", ""),
        }
    except Exception as exc:
        logger.debug("[Readiness] phase6 unavailable: %s", exc)
        return {"available": False, "error": str(exc)}


def _get_phase7() -> dict[str, Any]:
    try:
        from orchestrator.closing_odds_monitor import get_monitor_state
        state = get_monitor_state() or {}
        return {
            "available": True,
            "last_run_at": state.get("last_run_at"),
            "pending_clv": state.get("total_still_pending", 0),
            "computed_clv": state.get("total_upgraded", 0),
            "stale_closing_rejected": state.get("stale_closing_rejected", 0),
            "learning_unlocked_count": state.get("learning_unlocked_count", 0),
        }
    except Exception as exc:
        logger.debug("[Readiness] phase7 unavailable: %s", exc)
        return {"available": False, "error": str(exc)}


def _get_governance() -> dict[str, Any]:
    try:
        from orchestrator import optimization_state
        result = optimization_state.classify()
        return {
            "available": True,
            "current_state": result.get("state", "UNKNOWN"),
            "reasons": result.get("reasons", []),
            "allowed_families": result.get("allowed_task_families", []),
            "blocked_families": result.get("blocked_task_families", []),
            "recommended_next_action": result.get("recommended_next_action", ""),
        }
    except Exception as exc:
        logger.debug("[Readiness] governance unavailable: %s", exc)
        return {"available": False, "error": str(exc)}


def _get_ops_summary() -> dict[str, Any]:
    try:
        from orchestrator.optimization_ops_report import generate_report
        r = generate_report(window="8h")
        return {
            "available": True,
            "classification": r.get("classification", "UNKNOWN"),
            "tasks_completed": r.get("tasks_completed", 0),
            "effective_completed": r.get("effective_completed_tasks", 0),
            "consecutive_skips": r.get("consecutive_skips", 0),
            "hard_off_skip_count": r.get("hard_off_skip_count", 0),
            "skip_reasons": r.get("skip_reasons", {}),
            "governance_blocked": r.get("governance_blocked", 0),
            "clv_computed": r.get("clv_computed", 0),
            "next_focus": r.get("next_recommended_focus", ""),
        }
    except Exception as exc:
        logger.debug("[Readiness] ops_summary unavailable: %s", exc)
        return {"available": False, "error": str(exc)}


def _get_completion_quality() -> dict[str, Any]:
    try:
        from orchestrator.optimization_ops_report import generate_report
        r = generate_report(window="8h")
        total = r.get("tasks_completed", 0)
        valid = r.get("completed_valid_tasks", total)
        diag  = r.get("completed_diagnostic_only", 0)
        empty = r.get("completed_empty_artifact", 0)
        noop  = r.get("completed_noop", 0)
        eff   = r.get("effective_completed_tasks", total)
        quality_ok = (empty == 0 and noop == 0) or eff > 0
        return {
            "available": True,
            "total_completed": total,
            "completed_valid": valid,
            "completed_diagnostic_only": diag,
            "completed_empty_artifact": empty,
            "completed_noop": noop,
            "effective_completed": eff,
            "quality_ok": quality_ok,
        }
    except Exception as exc:
        logger.debug("[Readiness] completion_quality unavailable: %s", exc)
        return {"available": False, "error": str(exc)}


def _get_safe_work_status() -> dict[str, Any]:
    try:
        from orchestrator.data_waiting_cadence import get_due_safe_tasks, get_cadence_health
        due = get_due_safe_tasks()
        health = get_cadence_health("closing_monitor")
        return {
            "available": True,
            "due_tasks": due,
            "cadence_health": health,
            "closing_monitor_due": "closing_monitor" in due,
        }
    except Exception as exc:
        logger.debug("[Readiness] safe_work_status unavailable: %s", exc)
        return {"available": False, "error": str(exc)}


def _get_skip_health() -> dict[str, Any]:
    try:
        from orchestrator.scheduler_skip_classifier import (
            SKIP_HARD_OFF, SKIP_NO_QUEUED, SKIP_SCHEDULER_OFF,
        )
        ops = _get_ops_summary()
        skip_reasons = ops.get("skip_reasons", {})
        hard_off = skip_reasons.get(SKIP_HARD_OFF, 0) + skip_reasons.get(SKIP_SCHEDULER_OFF, 0)
        unexplained = ops.get("consecutive_skips", 0)
        total_skips = sum(skip_reasons.values())
        all_protected = (total_skips > 0) and (hard_off == total_skips)
        return {
            "available": True,
            "total_skips": total_skips,
            "hard_off_protected": hard_off,
            "unexplained_consecutive": unexplained,
            "all_protected": all_protected,
            "skip_reasons": skip_reasons,
            "skip_health": "HEALTHY" if all_protected or unexplained < 3 else "DEGRADED",
        }
    except Exception as exc:
        logger.debug("[Readiness] skip_health unavailable: %s", exc)
        return {"available": False, "error": str(exc)}


def _get_closing_availability() -> dict[str, Any]:
    """
    Phase 15/16/17 — Return source-level closing odds availability for all PENDING CLV records.
    Phase 16 adds: next_refresh_action, refresh_task_due, last_refresh_task,
    source_refresh_blocked_reason.
    Phase 17 adds: last_refresh_action, last_refresh_improved, consecutive_no_improvement,
    escalation_recommended, recommended_escalation_action.
    Read-only. Safe to call from readiness summary.
    """
    try:
        from orchestrator.closing_odds_monitor import get_pending_diagnostics
        from orchestrator.planner_tick import _choose_closing_refresh_action
        from orchestrator.data_waiting_cadence import is_safe_task_due
        diag = get_pending_diagnostics()
        ss = diag.get("source_summary", {})

        # Phase 16 enrichment
        next_refresh_action = _choose_closing_refresh_action(ss)

        try:
            refresh_task_due = is_safe_task_due(next_refresh_action)
        except Exception:
            refresh_task_due = None

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

        # Phase 17 refresh feedback
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
            "pending_total":                ss.get("pending_total", 0),
            "computed_total":               ss.get("computed_total", 0),
            "missing_all_sources":          ss.get("missing_all_sources", 0),
            "invalid_before_prediction":    ss.get("invalid_before_prediction", 0),
            "invalid_same_snapshot":        ss.get("invalid_same_snapshot", 0),
            "stale_candidates":             ss.get("stale_candidates", 0),
            "recommended_refresh_tsl":      ss.get("recommended_refresh_tsl", 0),
            "recommended_refresh_external": ss.get("recommended_refresh_external", 0),
            "manual_review_required":       ss.get("manual_review_required", 0),
            "ready_to_upgrade":             ss.get("ready_to_upgrade", 0),
            "next_closing_action":          ss.get("next_closing_action", ""),
            # Phase 16 fields
            "next_refresh_action":          next_refresh_action,
            "refresh_task_due":             refresh_task_due,
            "last_refresh_task":            last_refresh_task,
            "source_refresh_blocked_reason": source_refresh_blocked_reason,
            # Phase 17 fields
            "last_refresh_action":          _last_refresh_action,
            "last_refresh_improved":        _last_refresh_improved,
            "consecutive_no_improvement":   _consecutive_no_improvement,
            "escalation_recommended":       _escalation_recommended,
            "recommended_escalation_action": _recommended_escalation_action,
        }
    except Exception as exc:
        logger.debug("[Readiness] closing_availability unavailable: %s", exc)
        return {"available": False, "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────
# Readiness state derivation
# ─────────────────────────────────────────────────────────────────────────

def _derive_readiness_state(
    phase6: dict,
    governance: dict,
    ops: dict,
    completion_quality: dict,
    skip_health: dict,
) -> tuple[str, str, str]:
    """
    Return (readiness_state, severity, reason) from aggregated sub-states.
    """
    # ── 1. DEGRADED ────────────────────────────────────────────────────
    # Unexplained skip storm OR only empty/noop completions
    unexplained = skip_health.get("unexplained_consecutive", 0)
    if unexplained >= 3 and not skip_health.get("all_protected", False):
        return (
            RS_DEGRADED,
            SEV_RED,
            f"Unexplained consecutive skips: {unexplained} — scheduler may be broken",
        )
    # Quality degradation: recent completions are all empty/noop
    total_cq = completion_quality.get("total_completed", 0)
    empty_cq  = completion_quality.get("completed_empty_artifact", 0)
    noop_cq   = completion_quality.get("completed_noop", 0)
    eff_cq    = completion_quality.get("effective_completed", 0)
    if total_cq >= 2 and eff_cq == 0 and (empty_cq + noop_cq) >= 2:
        return (
            RS_DEGRADED,
            SEV_RED,
            f"All {total_cq} recent completions are empty/noop — LLM session may be inactive",
        )

    # ── 2. LEARNING_READY ──────────────────────────────────────────────
    clv_computed = phase6.get("clv_computed", 0)
    allowed = set(governance.get("allowed_families", []))
    learning_families_allowed = bool(allowed & _LEARNING_FAMILIES)
    if clv_computed > 0 and learning_families_allowed:
        return (
            RS_LEARNING_READY,
            SEV_GREEN,
            f"{clv_computed} CLV record(s) computed — learning families are allowed",
        )

    # ── 3. WAITING_ACTIVE / SAFE_WORK_ACTIVE ──────────────────────────
    ops_cls = ops.get("classification", "")
    safe_families_allowed = bool(allowed & _SAFE_FAMILIES)
    eff_completed = ops.get("effective_completed", 0)
    all_clv_pending = phase6.get("all_clv_pending", False)

    if all_clv_pending and ops_cls in ("WAITING_ACTIVE", "EFFECTIVE", "PARTIAL"):
        # Is safe cadence healthy?
        if eff_completed >= 1:
            return (
                RS_WAITING_ACTIVE,
                SEV_GREEN,
                "CLV pending closing; safe work is running on cadence",
            )
        else:
            return (
                RS_WAITING_ACTIVE,
                SEV_YELLOW,
                "CLV pending closing; safe work due but no effective completions yet",
            )

    if safe_families_allowed and not all_clv_pending:
        return (
            RS_SAFE_WORK_ACTIVE,
            SEV_GREEN if eff_completed >= 1 else SEV_ORANGE,
            "Safe non-learning work is active",
        )

    # ── 4. BLOCKED ─────────────────────────────────────────────────────
    blocked = set(governance.get("blocked_families", []))
    if len(blocked) >= 4 and eff_completed == 0:
        return (
            RS_BLOCKED,
            SEV_ORANGE,
            f"Most families blocked ({len(blocked)} blocked); no effective work completed",
        )

    # ── 5. Fallback — WAITING_ACTIVE if DATA_WAITING ──────────────────
    gov_state = governance.get("current_state", "")
    if gov_state == "DATA_WAITING":
        return (
            RS_WAITING_ACTIVE,
            SEV_YELLOW,
            "DATA_WAITING: CLV records pending; awaiting market settlement",
        )

    return (
        RS_SAFE_WORK_ACTIVE,
        SEV_YELLOW,
        "System is operational; awaiting next learning event",
    )


def _next_required_event(
    phase6: dict,
    governance: dict,
    readiness_state: str,
) -> str:
    """Derive the most important next event the operator should wait for."""
    if readiness_state == RS_LEARNING_READY:
        return "Start model learning cycle — CLV data is ready"
    if readiness_state == RS_WAITING_ACTIVE:
        p6_event = phase6.get("next_required_event", "")
        if p6_event:
            return p6_event
        return "Wait for market settlement → closing odds → CLV computation"
    if readiness_state == RS_SAFE_WORK_ACTIVE:
        return "Continue safe-work cadence; monitor for closing odds arrival"
    if readiness_state == RS_BLOCKED:
        return governance.get("recommended_next_action", "Review governance settings")
    if readiness_state == RS_DEGRADED:
        return "Investigate scheduler skip storm; check LLM provider session"
    return "No specific event required"


def _recommended_next_action(
    readiness_state: str,
    governance: dict,
    safe_work: dict,
) -> str:
    """Short, operator-facing action recommendation."""
    if readiness_state == RS_LEARNING_READY:
        return "Switch to safe-run mode and allow model-patch / calibration tasks"
    if readiness_state in (RS_WAITING_ACTIVE, RS_SAFE_WORK_ACTIVE):
        if safe_work.get("closing_monitor_due"):
            return "Run closing-monitor now (cadence slot is open)"
        return "Monitor for closing odds arrival; maintain safe-work cadence"
    if readiness_state == RS_BLOCKED:
        return governance.get("recommended_next_action", "Review blocked families in governance")
    if readiness_state == RS_DEGRADED:
        return "Check scheduler logs, LLM provider, and recent task artifacts"
    return "Monitor system state"


# ─────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────

def get_readiness_summary() -> dict[str, Any]:
    """
    Return a comprehensive readiness dict aggregating Phases 6–12.

    This is the single source of truth for the Phase 13 dashboard.
    Read-only — never writes state.
    """
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    phase6      = _get_phase6()
    phase7      = _get_phase7()
    governance  = _get_governance()
    ops         = _get_ops_summary()
    completion_quality = _get_completion_quality()
    safe_work   = _get_safe_work_status()
    skip_health = _get_skip_health()
    closing_availability = _get_closing_availability()

    readiness_state, severity, reason = _derive_readiness_state(
        phase6=phase6,
        governance=governance,
        ops=ops,
        completion_quality=completion_quality,
        skip_health=skip_health,
    )

    # Phase 15: enrich WAITING_ACTIVE reason with closing availability details
    if readiness_state == RS_WAITING_ACTIVE and closing_availability.get("available"):
        next_action = closing_availability.get("next_closing_action", "")
        if next_action:
            reason = f"{reason} — {next_action}"

    next_event = _next_required_event(phase6, governance, readiness_state)
    next_action = _recommended_next_action(readiness_state, governance, safe_work)
    learning_allowed = readiness_state == RS_LEARNING_READY

    # Phase 20: surface latest sandbox learning cycle from training memory
    latest_learning_cycle: dict | None = None
    try:
        from orchestrator.training_memory import get_latest_learning_cycle
        latest_learning_cycle = get_latest_learning_cycle()
    except Exception as exc:
        logger.debug("[Readiness] latest_learning_cycle unavailable: %s", exc)

    # Phase 21: surface latest patch gate decision from training memory
    latest_gate_decision: dict | None = None
    try:
        from orchestrator.training_memory import get_latest_gate_decision
        latest_gate_decision = get_latest_gate_decision()
    except Exception as exc:
        logger.debug("[Readiness] latest_gate_decision unavailable: %s", exc)

    # Phase 22: surface latest patch evaluation from training memory
    latest_patch_evaluation: dict | None = None
    try:
        from orchestrator.training_memory import get_latest_patch_evaluation
        latest_patch_evaluation = get_latest_patch_evaluation()
    except Exception as exc:
        logger.debug("[Readiness] latest_patch_evaluation unavailable: %s", exc)

    # Phase 23: surface latest patch evaluation gate decision
    latest_eval_gate_decision: dict | None = None
    try:
        from orchestrator.training_memory import get_latest_patch_evaluation_gate_decision
        latest_eval_gate_decision = get_latest_patch_evaluation_gate_decision()
    except Exception as exc:
        logger.debug("[Readiness] latest_eval_gate_decision unavailable: %s", exc)

    # Phase 24: surface human review queue summary
    human_review_queue_summary: dict = {}
    try:
        from orchestrator.human_review_queue import get_queue_summary
        human_review_queue_summary = get_queue_summary()
    except Exception as exc:
        logger.debug("[Readiness] human_review_queue_summary unavailable: %s", exc)

    return {
        "generated_at": now,
        "readiness_state": readiness_state,
        "severity": severity,
        "reason": reason,
        "learning_allowed": learning_allowed,
        "next_required_event": next_event,
        "recommended_next_action": next_action,
        # Sub-system snapshots
        "phase6": phase6,
        "phase7": phase7,
        "governance": governance,
        "ops": ops,
        "completion_quality": completion_quality,
        "safe_work": safe_work,
        "skip_reasons": skip_health.get("skip_reasons", {}),
        "skip_health": skip_health,
        "closing_availability": closing_availability,
        # Phase 20: learning cycle status
        "latest_learning_cycle": latest_learning_cycle,
        # Phase 21: patch gate decision
        "latest_gate_decision": latest_gate_decision,
        # Phase 22: patch evaluation result
        "latest_patch_evaluation": latest_patch_evaluation,
        # Phase 23: patch evaluation decision gate result
        "latest_eval_gate_decision": latest_eval_gate_decision,
        # Phase 24: human review queue
        "human_review_queue": human_review_queue_summary,
        "blocked_by_human_review": human_review_queue_summary.get("blocked_by_human_review", False),
    }


def render_readiness_markdown(summary: dict[str, Any]) -> str:
    """
    Return a human-readable markdown string of the readiness dashboard.
    """
    bar = "=" * 60
    sub = "-" * 60
    SEV_ICON = {
        SEV_GREEN: "🟢", SEV_YELLOW: "🟡",
        SEV_ORANGE: "🟠", SEV_RED: "🔴",
    }
    RS_ICON = {
        RS_LEARNING_READY: "🎓",
        RS_WAITING_ACTIVE: "⏳",
        RS_SAFE_WORK_ACTIVE: "🔧",
        RS_BLOCKED: "🚫",
        RS_DEGRADED: "🔴",
    }

    sev  = summary.get("severity", "?")
    rs   = summary.get("readiness_state", "UNKNOWN")
    icon = f"{SEV_ICON.get(sev, '❓')} {RS_ICON.get(rs, '❓')}"

    lines: list[str] = [
        bar,
        f"  AUTONOMOUS OPTIMIZATION READINESS DASHBOARD",
        f"  {summary.get('generated_at', '')}",
        bar,
        f"",
        f"  {icon}  {rs}  [{sev}]",
        f"  {summary.get('reason', '')}",
        f"",
        sub,
        f"  Learning allowed   : {'YES ✅' if summary.get('learning_allowed') else 'NO ❌'}",
        f"  Next event         : {summary.get('next_required_event', '')}",
        f"  Recommended action : {summary.get('recommended_next_action', '')}",
        f"",
    ]

    # ── Phase 6 ────────────────────────────────────────────────────────
    p6 = summary.get("phase6", {})
    if p6.get("available"):
        lines += [
            sub,
            "  PHASE 6 — CLV DATA PIPELINE",
            sub,
            f"  CLV computed       : {p6.get('clv_computed', 0)}",
            f"  CLV pending        : {p6.get('clv_pending_closing', 0)}",
            f"  Registry rows      : {p6.get('registry_rows', 0)}",
            f"  All CLV pending    : {'YES' if p6.get('all_clv_pending') else 'no'}",
            f"",
        ]

    # ── Phase 7 ────────────────────────────────────────────────────────
    p7 = summary.get("phase7", {})
    if p7.get("available"):
        lines += [
            sub,
            "  PHASE 7 — CLOSING MONITOR",
            sub,
            f"  Last run           : {p7.get('last_run_at') or 'never'}",
            f"  Pending CLV        : {p7.get('pending_clv', 0)}",
            f"  Computed CLV       : {p7.get('computed_clv', 0)}",
            f"  Learning unlocked  : {p7.get('learning_unlocked_count', 0)}",
            f"",
        ]

    # ── Governance ─────────────────────────────────────────────────────
    gov = summary.get("governance", {})
    if gov.get("available"):
        allowed_safe = [f for f in gov.get("allowed_families", []) if f in _SAFE_FAMILIES]
        lines += [
            sub,
            "  PHASE 8 — GOVERNANCE",
            sub,
            f"  Current state      : {gov.get('current_state', 'UNKNOWN')}",
            f"  Allowed safe       : {', '.join(sorted(allowed_safe)) or 'none'}",
            f"  Blocked families   : {len(gov.get('blocked_families', []))}",
            f"",
        ]

    # ── Ops summary ────────────────────────────────────────────────────
    ops = summary.get("ops", {})
    if ops.get("available"):
        lines += [
            sub,
            "  PHASE 9 — OPS SUMMARY (last 8h)",
            sub,
            f"  Classification     : {ops.get('classification', 'UNKNOWN')}",
            f"  Effective completed: {ops.get('effective_completed', 0)} / {ops.get('tasks_completed', 0)}",
            f"  Consecutive skips  : {ops.get('consecutive_skips', 0)} (unexplained)",
            f"  Hard-off protected : {ops.get('hard_off_skip_count', 0)}",
            f"",
        ]

    # ── Completion quality ──────────────────────────────────────────────
    cq = summary.get("completion_quality", {})
    if cq.get("available") and cq.get("total_completed", 0) > 0:
        lines += [
            sub,
            "  PHASE 10 — COMPLETION QUALITY",
            sub,
            f"  Effective          : {cq.get('effective_completed', 0)} / {cq.get('total_completed', 0)}",
            f"  Valid              : {cq.get('completed_valid', 0)}",
            f"  Diagnostic only    : {cq.get('completed_diagnostic_only', 0)}",
            f"  Empty artifact     : {cq.get('completed_empty_artifact', 0)}",
            f"  No-op              : {cq.get('completed_noop', 0)}",
            f"  Quality OK         : {'YES ✅' if cq.get('quality_ok') else 'WARN ⚠️'}",
            f"",
        ]

    # ── Skip health ─────────────────────────────────────────────────────
    sh = summary.get("skip_health", {})
    if sh.get("available"):
        lines += [
            sub,
            "  PHASE 12 — SKIP HEALTH",
            sub,
            f"  Total skips        : {sh.get('total_skips', 0)}",
            f"  Hard-off protected : {sh.get('hard_off_protected', 0)}",
            f"  Unexplained consec : {sh.get('unexplained_consecutive', 0)}",
            f"  Skip health        : {sh.get('skip_health', 'UNKNOWN')}",
            f"",
        ]

    # ── Phase 15/16 Closing Availability ─────────────────────────
    ca = summary.get("closing_availability", {})
    if ca.get("available"):
        lines += [
            sub,
            "  PHASE 15 — CLOSING ODDS AVAILABILITY",
            sub,
            f"  Pending CLV        : {ca.get('pending_total', 0)}",
            f"  Computed CLV       : {ca.get('computed_total', 0)}",
            f"  Missing all sources: {ca.get('missing_all_sources', 0)}",
            f"  Before prediction  : {ca.get('invalid_before_prediction', 0)}",
            f"  Same snapshot      : {ca.get('invalid_same_snapshot', 0)}",
            f"  Stale candidates   : {ca.get('stale_candidates', 0)}",
            f"  Ready to upgrade   : {ca.get('ready_to_upgrade', 0)}",
            f"  Next action        : {ca.get('next_closing_action', '')}",
            f"",
            "  PHASE 16 — CLOSING SOURCE REFRESH ORCHESTRATION",
            sub,
            f"  Next refresh action: {ca.get('next_refresh_action', '—')}",
            f"  Refresh task due   : {'YES' if ca.get('refresh_task_due') else ('NO' if ca.get('refresh_task_due') is False else 'UNKNOWN')}",
        ]
        lr = ca.get("last_refresh_task")
        if lr:
            lines.append(
                f"  Last refresh task  : #{lr.get('id')} {lr.get('task_type')} @ {(lr.get('completed_at') or '')[:16]}"
            )
        else:
            lines.append("  Last refresh task  : (none)")
        blocked = ca.get("source_refresh_blocked_reason")
        if blocked:
            lines.append(f"  Refresh blocked    : {blocked}")
        lines.append(f"")

        # Phase 17 — Refresh feedback
        if ca.get("last_refresh_action") is not None or ca.get("consecutive_no_improvement", 0) > 0:
            improved_str = (
                "YES ✅" if ca.get("last_refresh_improved") is True
                else ("NO ❌" if ca.get("last_refresh_improved") is False else "—")
            )
            esc_str = "YES ⚠️" if ca.get("escalation_recommended") else "NO ✅"
            lines += [
                "  PHASE 17 — REFRESH FEEDBACK",
                sub,
                f"  Last refresh action: {ca.get('last_refresh_action') or '—'}",
                f"  Last improved      : {improved_str}",
                f"  No-improvement run : {ca.get('consecutive_no_improvement', 0)}",
                f"  Escalation status  : {esc_str}",
                f"  Escalation action  : {ca.get('recommended_escalation_action', 'continue')}",
                f"",
            ]

    lines.append(bar)
    return "\n".join(lines)
