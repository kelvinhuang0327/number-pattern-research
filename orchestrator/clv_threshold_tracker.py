"""
orchestrator/clv_threshold_tracker.py
Phase 34 — Threshold Crossing Trigger & Learning Recheck

Persists threshold crossing events to disk and generates the correct safe
follow-up task when accumulated production CLV crosses key milestones.

Evidence thresholds (inherited from Phase 32):
  APPROACHING : computed_count >= 30  → trigger `production_clv_investigation`
  SUFFICIENT  : computed_count >= 50  → trigger `production_clv_learning_recheck`

HARD RULES:
  - Do not create production patches.
  - Do not deploy model changes.
  - Do not trigger live betting.
  - Do not call external LLM.
  - Do not bypass human review.
  - 50 only allows patch gate recheck — NOT patch execution.
  - Never mark PENDING records as COMPUTED.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_STATE_PATH = (
    _ROOT / "runtime" / "agent_orchestrator" / "clv_threshold_state.json"
)

# ── Threshold constants (must mirror clv_accumulation_policy.py) ──────────
THRESHOLD_APPROACHING: int = 30   # triggers investigation
THRESHOLD_SUFFICIENT:  int = 50   # triggers patch gate recheck

# ── Event types ───────────────────────────────────────────────────────────
EVENT_CROSSED_APPROACHING: str  = "CROSSED_APPROACHING"
EVENT_CROSSED_SUFFICIENT:  str  = "CROSSED_SUFFICIENT"

# ── Recommended follow-up task types ──────────────────────────────────────
TASK_FOR_APPROACHING: str  = "production_clv_investigation"
TASK_FOR_SUFFICIENT:  str  = "production_clv_learning_recheck"


# ─────────────────────────────────────────────────────────────────────────
# State persistence
# ─────────────────────────────────────────────────────────────────────────

def _load_state(state_path: Path) -> dict:
    """Load threshold state from disk; return default structure if missing."""
    if state_path.exists():
        try:
            raw = state_path.read_text(encoding="utf-8")
            return json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("[ThresholdTracker] Failed to load state (%s): %s", state_path, exc)
    return {
        "last_computed_count": 0,
        "crossed_30": False,
        "crossed_50": False,
        "last_threshold_event": None,
        "events": [],
    }


def _save_state(state: dict, state_path: Path) -> None:
    """Persist threshold state to disk atomically."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(state_path)
    except OSError as exc:
        logger.error("[ThresholdTracker] Failed to save state (%s): %s", state_path, exc)


# ─────────────────────────────────────────────────────────────────────────
# Core logic
# ─────────────────────────────────────────────────────────────────────────

def detect_threshold_events(
    previous_count: int,
    current_count: int,
) -> list[dict]:
    """
    Return list of new threshold event dicts when crossing key milestones.

    Does NOT persist — call ``update_threshold_state`` for persistence.

    Rules:
    - previous < 30 AND current >= 30  → CROSSED_APPROACHING
    - previous < 50 AND current >= 50  → CROSSED_SUFFICIENT
    - Already past threshold           → no new event
    - Multiple crossings in one step   → both events, APPROACHING first
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    events: list[dict] = []

    if previous_count < THRESHOLD_APPROACHING <= current_count:
        events.append({
            "event_id": str(uuid.uuid4()),
            "threshold": THRESHOLD_APPROACHING,
            "previous_count": previous_count,
            "current_count": current_count,
            "event_type": EVENT_CROSSED_APPROACHING,
            "recommended_task_type": TASK_FOR_APPROACHING,
            "created_at_utc": now_iso,
            "handled": False,
            "generated_task_id": None,
        })

    if previous_count < THRESHOLD_SUFFICIENT <= current_count:
        events.append({
            "event_id": str(uuid.uuid4()),
            "threshold": THRESHOLD_SUFFICIENT,
            "previous_count": previous_count,
            "current_count": current_count,
            "event_type": EVENT_CROSSED_SUFFICIENT,
            "recommended_task_type": TASK_FOR_SUFFICIENT,
            "created_at_utc": now_iso,
            "handled": False,
            "generated_task_id": None,
        })

    return events


def update_threshold_state(
    current_count: int,
    *,
    state_path: Path | None = None,
) -> dict:
    """
    Compare ``current_count`` against persisted state, detect crossings,
    append events, and save.

    Returns the updated state dict including any new events in
    ``state["new_events"]`` (transient, not saved to JSON).
    """
    sp = state_path or _DEFAULT_STATE_PATH
    state = _load_state(sp)
    previous_count = state.get("last_computed_count", 0)

    new_events = detect_threshold_events(previous_count, current_count)

    # Only append truly new event types (dedup: skip if same threshold already
    # exists with handled=False)
    existing_unhandled_types = {
        e["event_type"]
        for e in state.get("events", [])
        if not e.get("handled")
    }
    for ev in new_events:
        if ev["event_type"] in existing_unhandled_types:
            logger.debug(
                "[ThresholdTracker] Skipping duplicate unhandled event %s", ev["event_type"]
            )
            continue
        state.setdefault("events", []).append(ev)
        if ev["event_type"] == EVENT_CROSSED_APPROACHING:
            state["crossed_30"] = True
        if ev["event_type"] == EVENT_CROSSED_SUFFICIENT:
            state["crossed_50"] = True
        state["last_threshold_event"] = ev["event_type"]
        logger.info(
            "[ThresholdTracker] New threshold event: %s (prev=%d, curr=%d)",
            ev["event_type"], previous_count, current_count,
        )

    state["last_computed_count"] = current_count
    # Transient field for callers — not persisted
    state["new_events"] = new_events

    _save_state({k: v for k, v in state.items() if k != "new_events"}, sp)
    return state


def mark_event_handled(
    event_id: str,
    generated_task_id: str | None,
    *,
    state_path: Path | None = None,
) -> bool:
    """
    Mark a threshold event as handled and record the generated task ID.
    Returns True if found and updated, False if not found.
    """
    sp = state_path or _DEFAULT_STATE_PATH
    state = _load_state(sp)
    for ev in state.get("events", []):
        if ev.get("event_id") == event_id:
            ev["handled"] = True
            ev["generated_task_id"] = generated_task_id
            _save_state(state, sp)
            logger.info(
                "[ThresholdTracker] Event %s marked handled → task %s",
                event_id, generated_task_id,
            )
            return True
    logger.warning("[ThresholdTracker] Event %s not found in state", event_id)
    return False


def get_pending_threshold_events(
    *,
    state_path: Path | None = None,
) -> list[dict]:
    """Return list of unhandled threshold events from persisted state."""
    sp = state_path or _DEFAULT_STATE_PATH
    state = _load_state(sp)
    return [e for e in state.get("events", []) if not e.get("handled")]


def get_threshold_summary(
    *,
    current_count: int | None = None,
    state_path: Path | None = None,
) -> dict:
    """
    High-level summary suitable for readiness / ops / decision card surfaces.

    If ``current_count`` is provided and differs from persisted count,
    calls ``update_threshold_state`` first.
    """
    sp = state_path or _DEFAULT_STATE_PATH
    state = _load_state(sp)

    persisted_count = state.get("last_computed_count", 0)
    effective_count = current_count if current_count is not None else persisted_count

    # Auto-update if caller provides a newer count
    if current_count is not None and current_count != persisted_count:
        state = update_threshold_state(current_count, state_path=sp)

    pending_events = [e for e in state.get("events", []) if not e.get("handled")]
    latest_event   = state.get("last_threshold_event")

    # Determine recommended task type from most-recent unhandled event
    recommended_task_type: str | None = None
    generated_task_id: str | None     = None
    if pending_events:
        # SUFFICIENT takes precedence over APPROACHING
        sufficient = [e for e in pending_events if e["event_type"] == EVENT_CROSSED_SUFFICIENT]
        approaching = [e for e in pending_events if e["event_type"] == EVENT_CROSSED_APPROACHING]
        top = (sufficient or approaching)[0]
        recommended_task_type = top["recommended_task_type"]
        generated_task_id     = top.get("generated_task_id")

    return {
        "available":                True,
        "last_computed_count":      effective_count,
        "crossed_30":               state.get("crossed_30", False),
        "crossed_50":               state.get("crossed_50", False),
        "pending_threshold_events": len(pending_events),
        "latest_event_type":        latest_event,
        "recommended_task_type":    recommended_task_type,
        "generated_task_id":        generated_task_id,
        "events":                   state.get("events", []),
    }
