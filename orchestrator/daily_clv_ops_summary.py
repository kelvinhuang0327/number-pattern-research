"""
orchestrator/daily_clv_ops_summary.py
Phase 35 — Daily CLV Operations Runbook & Alerting

Aggregates production CLV health into a single daily ops snapshot.
Answers the 9 operator questions:

  1. Did new prediction batches arrive?
  2. Were CLV records generated?
  3. Were closing odds matched?
  4. How many CLV records are COMPUTED / PENDING / BLOCKED?
  5. Is evidence_state still INSUFFICIENT / APPROACHING / SUFFICIENT?
  6. Did threshold 30 or 50 cross today?
  7. Are there pending human reviews?
  8. Did any external LLM / GitHub usage occur unexpectedly?
  9. What exact operator action is needed today?

HARD RULES:
  - Read-only — does NOT modify CLV records.
  - Does NOT trigger live betting.
  - Does NOT call external LLM.
  - Does NOT create patch tasks.
  - Observability only.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[1]
_REPORTS_DIR = _ROOT / "data" / "wbc_backend" / "reports"
_THRESHOLD_STATE_PATH = (
    _ROOT / "runtime" / "agent_orchestrator" / "clv_threshold_state.json"
)
_TRAINING_MEMORY_PATH = (
    _ROOT / "runtime" / "agent_orchestrator" / "training_memory.json"
)

# ── Alert severity constants ──────────────────────────────────────────────
SEV_INFO     = "INFO"
SEV_WARN     = "WARN"
SEV_CRITICAL = "CRITICAL"

# Alert codes
CODE_NORMAL_ACCUMULATION          = "NORMAL_ACCUMULATION"
CODE_NO_PENDING_REVIEWS           = "NO_PENDING_REVIEWS"
CODE_NO_UNEXPECTED_LLM            = "NO_UNEXPECTED_LLM"
CODE_PENDING_CLV_STALE            = "PENDING_CLV_STALE"
CODE_EVIDENCE_APPROACHING         = "EVIDENCE_APPROACHING"
CODE_THRESHOLD_EVENT_UNHANDLED    = "THRESHOLD_EVENT_UNHANDLED"
CODE_HUMAN_REVIEW_PENDING         = "HUMAN_REVIEW_PENDING"
CODE_NO_NEW_BATCH                 = "NO_NEW_BATCH"
CODE_COMPUTED_COUNT_DECREASED     = "COMPUTED_COUNT_DECREASED"
CODE_AUDIT_GUARD_NOT_FULL         = "AUDIT_GUARD_NOT_FULL"
CODE_PLANNER_LLM_ATTEMPT          = "PLANNER_LLM_ATTEMPT"
CODE_PATCH_WITHOUT_HUMAN_REVIEW   = "PATCH_WITHOUT_HUMAN_REVIEW"
CODE_CLV_FILE_MISSING_OR_MALFORMED = "CLV_FILE_MISSING_OR_MALFORMED"

# No-new-batch warning threshold (days)
_NO_BATCH_WARN_DAYS = 3


# ─────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────

def _alert(
    severity: str,
    code: str,
    message: str,
    recommended_action: str,
) -> dict:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "recommended_action": recommended_action,
    }


def _get_batch_summary(reports_dir: Path) -> dict:
    """Aggregate batch-level discovery."""
    try:
        from orchestrator.clv_batch_scheduler import discover_batches
        batches = discover_batches(reports_dir)
    except Exception as exc:
        logger.warning("[DailyOps] batch discovery failed: %s", exc)
        return {"available": False, "error": str(exc)}

    if not batches:
        return {
            "available": True,
            "batches_seen": 0,
            "latest_batch_date": None,
            "total_computed": 0,
            "total_pending": 0,
            "batches_needing_clv_generation": 0,
            "batches_needing_closing_monitor": 0,
            "batches_needing_accumulation_update": 0,
        }

    latest_date = max(b["batch_date"] for b in batches)
    return {
        "available": True,
        "batches_seen": len(batches),
        "latest_batch_date": latest_date,
        "total_computed": sum(b.get("computed_count", 0) for b in batches),
        "total_pending": sum(b.get("pending_count", 0) for b in batches),
        "batches_needing_clv_generation": sum(
            1 for b in batches if b.get("needs_clv_generation")
        ),
        "batches_needing_closing_monitor": sum(
            1 for b in batches if b.get("needs_closing_monitor")
        ),
        "batches_needing_accumulation_update": sum(
            1 for b in batches if b.get("needs_accumulation_update")
        ),
        "batches": batches,
    }


def _get_clv_counts(reports_dir: Path, target_date: str | None = None) -> dict:
    """
    Scan CLV JSONL files and return record counts.

    If target_date is given (YYYY-MM-DD), also compute new_computed_today by
    comparing with the previous training_memory count.
    """
    computed: list[dict] = []
    pending:  list[dict] = []
    blocked:  list[dict] = []
    malformed_files: list[str] = []
    clv_files_found = 0

    for path in sorted(reports_dir.glob("clv_validation_records_6u_*.jsonl")):
        clv_files_found += 1
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            malformed_files.append(f"{path.name}: read error ({exc})")
            continue

        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                malformed_files.append(f"{path.name}: JSON parse error")
                continue
            status = row.get("clv_status", "")
            if status == "COMPUTED":
                computed.append(row)
            elif status in ("PENDING_CLOSING", "PENDING"):
                pending.append(row)
            elif status in ("BLOCKED", "NO_CLOSING_ODDS"):
                blocked.append(row)

    # Read persisted count from training memory for delta comparison
    previous_computed_count = 0
    try:
        mem = _TRAINING_MEMORY_PATH.read_text(encoding="utf-8")
        mem_data = json.loads(mem)
        runs = mem_data.get("clv_accumulation_runs", [])
        if runs:
            previous_computed_count = runs[-1].get("computed_count", 0)
    except (OSError, json.JSONDecodeError, KeyError):
        pass

    new_computed_today = max(0, len(computed) - previous_computed_count)

    return {
        "available": True,
        "clv_files_found": clv_files_found,
        "computed_total": len(computed),
        "pending_total": len(pending),
        "blocked_total": len(blocked),
        "new_computed_today": new_computed_today,
        "previous_computed_count": previous_computed_count,
        "malformed_files": malformed_files,
    }


def _get_accumulation_summary(reports_dir: Path) -> dict:
    try:
        from orchestrator.clv_accumulation_policy import get_clv_accumulation_summary
        return get_clv_accumulation_summary(reports_dir=reports_dir)
    except Exception as exc:
        logger.warning("[DailyOps] accumulation summary failed: %s", exc)
        return {"available": False, "error": str(exc)}


def _get_threshold_summary() -> dict:
    try:
        from orchestrator.clv_threshold_tracker import get_threshold_summary
        return get_threshold_summary()
    except Exception as exc:
        logger.warning("[DailyOps] threshold summary failed: %s", exc)
        return {"available": False, "error": str(exc)}


def _get_human_review_summary() -> dict:
    try:
        from orchestrator.human_review_queue import get_queue_summary
        return get_queue_summary()
    except Exception as exc:
        logger.warning("[DailyOps] human review summary failed: %s", exc)
        return {"available": False, "error": str(exc)}


def _get_llm_audit_summary() -> dict:
    try:
        from orchestrator.llm_audit import build_audit_today_summary
        return build_audit_today_summary()
    except Exception as exc:
        logger.warning("[DailyOps] LLM audit summary failed: %s", exc)
        return {"available": False, "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────
# Alert rule engine
# ─────────────────────────────────────────────────────────────────────────

def _evaluate_alerts(
    batch_summary: dict,
    clv_counts: dict,
    accumulation: dict,
    threshold: dict,
    human_review: dict,
    llm_audit: dict,
    *,
    reports_dir: Path,
) -> list[dict]:
    alerts: list[dict] = []
    now = datetime.now(timezone.utc)

    # ── CRITICAL: CLV file missing or malformed ──────────────────────────
    if clv_counts.get("malformed_files"):
        for mf in clv_counts["malformed_files"]:
            alerts.append(_alert(
                SEV_CRITICAL,
                CODE_CLV_FILE_MISSING_OR_MALFORMED,
                f"CLV file issue detected: {mf}",
                "Inspect the affected CLV JSONL file; do NOT modify records.",
            ))

    if clv_counts.get("clv_files_found", 0) == 0 and batch_summary.get("batches_seen", 0) > 0:
        alerts.append(_alert(
            SEV_CRITICAL,
            CODE_CLV_FILE_MISSING_OR_MALFORMED,
            "Prediction registry batches exist but NO CLV validation files found.",
            "Run CLV generation pipeline for existing registry batches.",
        ))

    # ── CRITICAL: COMPUTED count decreased ──────────────────────────────
    prev = clv_counts.get("previous_computed_count", 0)
    curr = clv_counts.get("computed_total", 0)
    if prev > 0 and curr < prev:
        alerts.append(_alert(
            SEV_CRITICAL,
            CODE_COMPUTED_COUNT_DECREASED,
            f"COMPUTED CLV count decreased: {prev} → {curr}. "
            "Records may have been deleted or overwritten.",
            "Immediately audit CLV JSONL files. Do NOT modify records without investigation.",
        ))

    # ── CRITICAL: Planner external LLM attempt detected ─────────────────
    by_role = llm_audit.get("by_role", {})
    planner_attempts = by_role.get("planner", {}).get("attempts", 0)
    if planner_attempts > 0:
        alerts.append(_alert(
            SEV_CRITICAL,
            CODE_PLANNER_LLM_ATTEMPT,
            f"Planner made {planner_attempts} external LLM attempt(s) today. "
            "All planner tasks must be deterministic.",
            "Audit LLM audit log; ensure planner_tick uses only DETERMINISTIC_TASK_TYPES.",
        ))

    # ── CRITICAL: Audit guard coverage not FULL ─────────────────────────
    # If LLM attempts > 0 with an unexpected role (not 'analyst' or 'summarizer')
    unexpected_llm_roles = {
        role for role, stats in by_role.items()
        if stats.get("attempts", 0) > 0
        and role not in ("analyst", "summarizer", "monitor", "reporter")
    }
    if unexpected_llm_roles:
        alerts.append(_alert(
            SEV_CRITICAL,
            CODE_AUDIT_GUARD_NOT_FULL,
            f"Unexpected LLM usage from roles: {sorted(unexpected_llm_roles)}. "
            "Audit guard coverage is not FULL.",
            "Investigate LLM audit log for unauthorized usage roles.",
        ))

    # ── CRITICAL: Production patch task created without human review ─────
    pending_reviews = human_review.get("pending_reviews", [])
    patch_without_review = [
        r for r in pending_reviews
        if r.get("review_type") == "PRODUCTION_PATCH"
    ]
    if patch_without_review:
        alerts.append(_alert(
            SEV_CRITICAL,
            CODE_PATCH_WITHOUT_HUMAN_REVIEW,
            f"{len(patch_without_review)} production patch request(s) pending human review. "
            "No patch may execute without explicit approval.",
            "Review and approve/reject each production patch request in the human review queue.",
        ))

    # ── WARN: Pending CLV stale for > 24h ────────────────────────────────
    # Check batch timestamps — if any batch has pending records and was created > 24h ago
    for b in batch_summary.get("batches", []):
        if b.get("pending_count", 0) > 0 and b.get("needs_closing_monitor"):
            batch_date_str = b.get("batch_date", "")
            try:
                batch_date = datetime.fromisoformat(batch_date_str).replace(tzinfo=timezone.utc)
            except ValueError:
                try:
                    batch_date = datetime.strptime(batch_date_str, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                except ValueError:
                    continue
            age_hours = (now - batch_date).total_seconds() / 3600
            if age_hours > 24:
                alerts.append(_alert(
                    SEV_WARN,
                    CODE_PENDING_CLV_STALE,
                    f"Batch {batch_date_str} has {b['pending_count']} PENDING CLV record(s) "
                    f"older than 24 h ({age_hours:.0f} h).",
                    "Run closing odds update pipeline; check tsl_crawler for odds availability.",
                ))

    # ── WARN: evidence_state = APPROACHING ───────────────────────────────
    ev_state = accumulation.get("evidence_state", "")
    if ev_state == "APPROACHING":
        remaining = accumulation.get("remaining_needed", 0)
        alerts.append(_alert(
            SEV_WARN,
            CODE_EVIDENCE_APPROACHING,
            f"Evidence state is APPROACHING. {remaining} more COMPUTED records needed "
            "before patch gate recheck is allowed.",
            "Continue accumulating CLV records via clv_batch_accumulation tasks. "
            "Do NOT create patch candidates yet.",
        ))

    # ── WARN: Unhandled threshold event ──────────────────────────────────
    pending_events = threshold.get("pending_threshold_events", 0)
    if pending_events > 0:
        latest_ev = threshold.get("latest_event_type", "")
        recommended = threshold.get("recommended_task_type", "")
        alerts.append(_alert(
            SEV_WARN,
            CODE_THRESHOLD_EVENT_UNHANDLED,
            f"{pending_events} unhandled threshold event(s) detected "
            f"(latest: {latest_ev}).",
            f"Create and run deterministic task: '{recommended}' to handle the threshold event.",
        ))

    # ── WARN: Human review pending ────────────────────────────────────────
    pending_count = human_review.get("pending_count", 0)
    if pending_count > 0 and not patch_without_review:
        alerts.append(_alert(
            SEV_WARN,
            CODE_HUMAN_REVIEW_PENDING,
            f"{pending_count} human review item(s) pending decision.",
            "Review pending items in the human review queue and approve or reject.",
        ))

    # ── WARN: No new batch for > N days ──────────────────────────────────
    latest_batch_date = batch_summary.get("latest_batch_date")
    if latest_batch_date:
        try:
            lbd = datetime.strptime(latest_batch_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            days_since = (now - lbd).days
            if days_since >= _NO_BATCH_WARN_DAYS:
                alerts.append(_alert(
                    SEV_WARN,
                    CODE_NO_NEW_BATCH,
                    f"No new prediction registry batch for {days_since} day(s) "
                    f"(latest: {latest_batch_date}).",
                    "Check if WBC games are scheduled. "
                    "Verify tsl_crawler and prediction pipeline are running.",
                ))
        except ValueError:
            pass
    elif batch_summary.get("batches_seen", 0) == 0:
        alerts.append(_alert(
            SEV_WARN,
            CODE_NO_NEW_BATCH,
            "No prediction registry batches found at all.",
            "Verify data pipeline has run at least once successfully.",
        ))

    # ── INFO: Normal accumulation ─────────────────────────────────────────
    if not any(a["code"] in (CODE_COMPUTED_COUNT_DECREASED, CODE_CLV_FILE_MISSING_OR_MALFORMED)
               for a in alerts):
        alerts.append(_alert(
            SEV_INFO,
            CODE_NORMAL_ACCUMULATION,
            f"CLV accumulation proceeding normally. "
            f"Computed: {curr}, Pending: {clv_counts.get('pending_total', 0)}, "
            f"State: {ev_state or 'UNKNOWN'}.",
            "Continue accumulation. No operator action required.",
        ))

    # ── INFO: No pending reviews ──────────────────────────────────────────
    if pending_count == 0:
        alerts.append(_alert(
            SEV_INFO,
            CODE_NO_PENDING_REVIEWS,
            "No human review items pending.",
            "No action required.",
        ))

    # ── INFO: No unexpected LLM usage ────────────────────────────────────
    total_llm = llm_audit.get("attempts", 0) if isinstance(llm_audit, dict) else 0
    if total_llm == 0 and not unexpected_llm_roles:
        alerts.append(_alert(
            SEV_INFO,
            CODE_NO_UNEXPECTED_LLM,
            "No external LLM calls detected today.",
            "No action required.",
        ))

    # Sort: CRITICAL first, then WARN, then INFO
    _order = {SEV_CRITICAL: 0, SEV_WARN: 1, SEV_INFO: 2}
    alerts.sort(key=lambda a: _order.get(a["severity"], 9))
    return alerts


def _derive_operator_next_action(alerts: list[dict], accumulation: dict) -> str:
    """Produce a single-sentence operator action from the highest-severity alert."""
    critical = [a for a in alerts if a["severity"] == SEV_CRITICAL]
    warn     = [a for a in alerts if a["severity"] == SEV_WARN]

    if critical:
        return critical[0]["recommended_action"]
    if warn:
        return warn[0]["recommended_action"]

    ev_state = accumulation.get("evidence_state", "INSUFFICIENT")
    remaining = accumulation.get("remaining_needed", 0)
    if ev_state == "SUFFICIENT":
        return "Evidence is SUFFICIENT. Request human review to authorize patch gate recheck."
    if ev_state == "APPROACHING":
        return (
            f"Evidence is APPROACHING. Continue accumulating CLV records "
            f"({remaining} more needed for SUFFICIENT)."
        )
    return (
        f"Normal accumulation in progress. "
        f"Keep running clv_batch_accumulation tasks ({remaining} records remaining)."
    )


# ─────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────

def get_daily_ops_summary(
    *,
    target_date: str | None = None,
    reports_dir: Path | None = None,
) -> dict:
    """
    Return the complete daily CLV ops summary.

    Parameters
    ----------
    target_date : str, optional
        Override date label (YYYY-MM-DD). Defaults to today UTC.
    reports_dir : Path, optional
        Override reports directory (for testing).

    Returns
    -------
    dict with keys: date, batches, clv, accumulation, threshold,
                    human_review, llm_audit, alerts, operator_next_action
    """
    today = target_date or date.today().isoformat()
    rdir: Path = reports_dir if reports_dir is not None else _REPORTS_DIR

    batch_summary  = _get_batch_summary(rdir)
    clv_counts     = _get_clv_counts(rdir, today)
    accumulation   = _get_accumulation_summary(rdir)
    threshold      = _get_threshold_summary()
    human_review   = _get_human_review_summary()
    llm_audit      = _get_llm_audit_summary()

    alerts = _evaluate_alerts(
        batch_summary,
        clv_counts,
        accumulation,
        threshold,
        human_review,
        llm_audit,
        reports_dir=rdir,
    )

    operator_next_action = _derive_operator_next_action(alerts, accumulation)

    highest_severity = SEV_INFO
    for a in alerts:
        if a["severity"] == SEV_CRITICAL:
            highest_severity = SEV_CRITICAL
            break
        if a["severity"] == SEV_WARN:
            highest_severity = SEV_WARN

    return {
        "date":                 today,
        "generated_at":         datetime.now(timezone.utc).isoformat(),
        "highest_severity":     highest_severity,
        "batches":              batch_summary,
        "clv":                  clv_counts,
        "accumulation":         accumulation,
        "threshold":            threshold,
        "human_review":         human_review,
        "llm_audit":            llm_audit,
        "alerts":               alerts,
        "operator_next_action": operator_next_action,
        # Hard rule constants — always present for test assertions
        "production_mutation":  False,
        "live_bet_submitted":   False,
        "external_llm_called":  False,
        "patch_task_created":   False,
    }


def render_daily_ops_markdown(summary: dict) -> str:
    """Render the daily ops summary as a human-readable Markdown string."""
    bar = "=" * 64
    sub = "-" * 64
    SEV_ICON = {SEV_CRITICAL: "🔴", SEV_WARN: "🟡", SEV_INFO: "🟢"}
    hsev = summary.get("highest_severity", SEV_INFO)
    icon = SEV_ICON.get(hsev, "❓")

    lines = [
        bar,
        f"  DAILY CLV OPS SUMMARY — {summary.get('date', '—')}  {icon} {hsev}",
        bar,
        "",
        f"Generated at : {summary.get('generated_at', '—')[:19].replace('T', ' ')} UTC",
        "",
    ]

    # ── Batch status ──────────────────────────────────────────────────────
    b = summary.get("batches", {})
    lines += [
        sub,
        "  BATCHES",
        sub,
        f"  Batches seen         : {b.get('batches_seen', 0)}",
        f"  Latest batch date    : {b.get('latest_batch_date') or '—'}",
        f"  Need CLV generation  : {b.get('batches_needing_clv_generation', 0)}",
        f"  Need closing monitor : {b.get('batches_needing_closing_monitor', 0)}",
        f"  Need accum. update   : {b.get('batches_needing_accumulation_update', 0)}",
        "",
    ]

    # ── CLV counts ────────────────────────────────────────────────────────
    c = summary.get("clv", {})
    lines += [
        sub,
        "  CLV RECORDS",
        sub,
        f"  COMPUTED total       : {c.get('computed_total', 0)}",
        f"  PENDING total        : {c.get('pending_total', 0)}",
        f"  BLOCKED total        : {c.get('blocked_total', 0)}",
        f"  New computed today   : {c.get('new_computed_today', 0)}",
        "",
    ]

    # ── Accumulation ─────────────────────────────────────────────────────
    acc = summary.get("accumulation", {})
    ev_state = acc.get("evidence_state", "UNKNOWN")
    EV_ICON = {"INSUFFICIENT": "🔴", "APPROACHING": "🟡", "SUFFICIENT": "🟢"}
    ev_icon = EV_ICON.get(ev_state, "❓")
    lines += [
        sub,
        "  ACCUMULATION POLICY",
        sub,
        f"  Evidence state       : {ev_icon} {ev_state}",
        f"  Computed / Target    : {acc.get('computed_count', 0)} / {acc.get('threshold', 50)}",
        f"  Remaining needed     : {acc.get('remaining_needed', 0)}",
        f"  Patch gate recheck   : {'ALLOWED ✅' if acc.get('patch_gate_recheck_allowed') else 'BLOCKED 🚫'}",
        "",
    ]

    # ── Threshold events ─────────────────────────────────────────────────
    thr = summary.get("threshold", {})
    lines += [
        sub,
        "  THRESHOLD CROSSING EVENTS",
        sub,
        f"  Crossed 30           : {'YES ✅' if thr.get('crossed_30') else 'NO'}",
        f"  Crossed 50           : {'YES ✅' if thr.get('crossed_50') else 'NO'}",
        f"  Pending events       : {thr.get('pending_threshold_events', 0)}",
        f"  Latest event type    : {thr.get('latest_event_type') or '—'}",
        "",
    ]

    # ── Human review ─────────────────────────────────────────────────────
    hr = summary.get("human_review", {})
    lines += [
        sub,
        "  HUMAN REVIEW QUEUE",
        sub,
        f"  Pending count        : {hr.get('pending_count', 0)}",
        f"  Approved count       : {hr.get('approved_count', 0)}",
        "",
    ]

    # ── LLM audit ────────────────────────────────────────────────────────
    llm = summary.get("llm_audit", {})
    lines += [
        sub,
        "  LLM AUDIT (today)",
        sub,
        f"  Total events         : {llm.get('total_events', 0)}",
        f"  Attempts             : {llm.get('attempts', 0)}",
        f"  Blocked              : {llm.get('blocked', 0)}",
        "",
    ]

    # ── Alerts ────────────────────────────────────────────────────────────
    alerts = summary.get("alerts", [])
    if alerts:
        lines += [sub, "  ALERTS", sub]
        for a in alerts:
            sev_icon = SEV_ICON.get(a["severity"], "❓")
            lines.append(f"  {sev_icon} [{a['severity']}] {a['code']}")
            lines.append(f"     {a['message']}")
            lines.append(f"     → {a['recommended_action']}")
        lines.append("")

    # ── Operator action ───────────────────────────────────────────────────
    lines += [
        bar,
        f"  OPERATOR NEXT ACTION: {summary.get('operator_next_action', '—')}",
        bar,
    ]

    return "\n".join(lines)
