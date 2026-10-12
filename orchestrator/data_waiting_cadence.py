"""
Phase 12 — DATA_WAITING Safe Work Cadence Policy

定義 DATA_WAITING 狀態下各種安全任務的執行間隔，
並判斷哪些任務當前「已到期」(due) 而需要被排程器建立。

Cadence table (minutes between consecutive runs)
─────────────────────────────────────────────────
  closing_monitor       — every 20 min  (15-30 min window)
  scheduler_health_check— every 60 min
  artifact_health_check — every 240 min (4 h)
  ops_report            — every 480 min (8 h)

Deduplication
─────────────
Instead of a "one per day" dedupe key, we use a slot-based key:
  f"{task_type}:slot:{slot_index}"
where slot_index = floor(utc_minutes_since_epoch / cadence_minutes).

This means each cadence window gets exactly one slot key, preventing
duplicate tasks within the window while allowing the next window's task
to be created after the interval has elapsed.

Hard rules enforced here
────────────────────────
- Never generates model-patch, strategy-reinforcement, or learning tasks
- Never marks CLV as COMPUTED
- All generated tasks are deterministic / safe-run eligible
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Cadence table (task_type → minutes between runs) ────────────────
CADENCE_MINUTES: dict[str, int] = {
    "closing_monitor": 20,
    "refresh_external_closing": 60,
    "refresh_tsl_closing": 30,
    "closing_availability_audit": 60,
    "manual_review_summary": 120,  # Phase 17: escalation summary (2-hour cadence)
    "scheduler_health_check": 60,
    "artifact_health_check": 240,
    "ops_report": 480,
    # Phase 33: CLV batch accumulation cadences
    "clv_batch_accumulation": 1440,       # 24 h (normal)
    "clv_batch_accumulation_fast": 240,   # 4 h (pending records exist)
}

# ── Phase 16/17 refresh task priority order (highest-priority first) ────
# manual_review_summary > refresh_external_closing > refresh_tsl_closing > closing_availability_audit > closing_monitor
REFRESH_TASK_PRIORITY: list[str] = [
    "manual_review_summary",
    "refresh_external_closing",
    "refresh_tsl_closing",
    "closing_availability_audit",
    "closing_monitor",
]

# ── Task types that are safe to generate during DATA_WAITING ─────────
_DATA_WAITING_SAFE_TYPES: frozenset[str] = frozenset(CADENCE_MINUTES.keys())

# ── Forbidden task types (hard rule — never generate during DATA_WAITING) ──
_FORBIDDEN_TYPES: frozenset[str] = frozenset({
    "model_patch",
    "model_patch_calibration",
    "model_patch_atomic",
    "strategy_reinforcement",
    "strategy-reinforcement",
    "feedback_atomic",
    "clv_reinforcement",
    "calibration_atomic",
    "feature_atomic",
    "regime_atomic",
    "backtest_validity_atomic",
})


# ─────────────────────────────────────────────────────────────────────
# Slot-based deduplication helpers
# ─────────────────────────────────────────────────────────────────────

def _utc_slot_index(task_type: str, now: Optional[datetime] = None) -> int:
    """
    Return the integer slot index for ``task_type`` at ``now``.

    slot_index = floor(utc_epoch_minutes / cadence_minutes)

    Two calls within the same cadence window return the same slot index.
    """
    cadence = CADENCE_MINUTES[task_type]
    ts = now or datetime.now(timezone.utc)
    epoch_minutes = int(ts.timestamp()) // 60
    return epoch_minutes // cadence


def cadence_dedupe_key(task_type: str, now: Optional[datetime] = None) -> str:
    """
    Return the deduplication key for the CURRENT cadence window.

    Example: ``"closing_monitor:slot:74234517"``
    """
    slot = _utc_slot_index(task_type, now)
    return f"{task_type}:slot:{slot}"


# ─────────────────────────────────────────────────────────────────────
# Due-check helpers
# ─────────────────────────────────────────────────────────────────────

def is_safe_task_due(task_type: str, now: Optional[datetime] = None) -> bool:
    """
    Return True when ``task_type`` has not yet run (or been QUEUED) in the
    current cadence slot.

    Checks the orchestrator DB for a non-failed task with this window's dedupe key.
    Returns True (= due) if none found.
    """
    if task_type not in CADENCE_MINUTES:
        raise ValueError(f"Unknown safe task type: {task_type!r}")

    dedupe_key = cadence_dedupe_key(task_type, now)
    try:
        from orchestrator import db
        existing = db.get_nonfailed_task_by_dedupe_key(dedupe_key)
        return existing is None
    except Exception as exc:
        logger.warning("[Cadence] DB check failed for %s: %s", task_type, exc)
        return False  # fail-safe: don't create if we can't confirm


def get_due_safe_tasks(now: Optional[datetime] = None) -> list[str]:
    """
    Return the list of safe task types that are currently due (cadence elapsed,
    no task exists for current slot).

    Ordered by priority: closing_monitor first, then ascending cadence.
    """
    priority_order = [
        "refresh_external_closing",
        "refresh_tsl_closing",
        "closing_availability_audit",
        "closing_monitor",
        "scheduler_health_check",
        "artifact_health_check",
        "ops_report",
    ]
    return [t for t in priority_order if is_safe_task_due(t, now)]


# ─────────────────────────────────────────────────────────────────────
# Guard helpers
# ─────────────────────────────────────────────────────────────────────

def is_forbidden_task_type(task_type: str) -> bool:
    """Return True if task_type must never be generated during DATA_WAITING."""
    return (task_type or "").lower().strip() in _FORBIDDEN_TYPES


def is_data_waiting_safe_type(task_type: str) -> bool:
    """Return True if task_type is in the allowed safe task set."""
    return (task_type or "").lower().strip() in _DATA_WAITING_SAFE_TYPES


# ─────────────────────────────────────────────────────────────────────
# Cadence health check (used by ops report)
# ─────────────────────────────────────────────────────────────────────

def get_cadence_health(
    task_type: str = "closing_monitor",
    now: Optional[datetime] = None,
) -> dict:
    """
    Return a dict describing the cadence health for ``task_type``.

    Keys:
      task_type     — the queried type
      cadence_min   — configured cadence in minutes
      current_slot  — integer slot index
      dedupe_key    — active dedupe key
      task_due      — bool
      existing_task_id  — int or None
      existing_status   — str or None
    """
    if task_type not in CADENCE_MINUTES:
        raise ValueError(f"Unknown safe task type: {task_type!r}")

    ts = now or datetime.now(timezone.utc)
    dedupe_key = cadence_dedupe_key(task_type, ts)
    cadence = CADENCE_MINUTES[task_type]

    existing_id: Optional[int] = None
    existing_status: Optional[str] = None
    task_due = True

    try:
        from orchestrator import db
        existing = db.get_nonfailed_task_by_dedupe_key(dedupe_key)
        if existing:
            existing_id = existing.get("id")
            existing_status = existing.get("status")
            task_due = False
    except Exception as exc:
        logger.warning("[Cadence] DB check failed for health query %s: %s", task_type, exc)

    return {
        "task_type": task_type,
        "cadence_min": cadence,
        "current_slot": _utc_slot_index(task_type, ts),
        "dedupe_key": dedupe_key,
        "task_due": task_due,
        "existing_task_id": existing_id,
        "existing_status": existing_status,
    }
