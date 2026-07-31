"""
Phase 17 — Closing Refresh Outcome Memory

Tracks per-action-type refresh outcomes to detect no-improvement streaks
and trigger escalation to manual_review_summary.

Persisted to:
    runtime/agent_orchestrator/closing_refresh_memory.json

Escalation policy (any condition triggers escalation):
  1. same action_type has consecutive_no_improvement >= 3
  2. missing_all_sources > 0 AND missing counts did not decrease AND
     time since first no-improvement run for this action_type > 6 hours
  3. action_type == "refresh_external_closing" AND consecutive_no_improvement >= 2
     (external source is not expected to improve on its own)

Hard rules:
  - Does NOT unlock learning
  - Does NOT mark PENDING_CLOSING as COMPUTED
  - Does NOT call any paid external API
  - Records outcomes only; never modifies CLV state
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_MEMORY_PATH = (
    _REPO_ROOT / "runtime" / "agent_orchestrator" / "closing_refresh_memory.json"
)

# Escalation thresholds
_CONSECUTIVE_NO_IMPROVEMENT_THRESHOLD = 3
_EXTERNAL_CONSECUTIVE_NO_IMPROVEMENT_THRESHOLD = 2  # External source is harder to fix
_MISSING_STALE_HOURS_THRESHOLD = 6  # missing_all_sources unchanged for > 6h → escalate

# Refresh action types (Phase 16 + 17)
REFRESH_ACTION_TYPES = frozenset({
    "refresh_external_closing",
    "refresh_tsl_closing",
    "closing_availability_audit",
    "closing_monitor",
})

_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# Storage helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_memory(memory_path: Path) -> dict[str, Any]:
    """Load memory JSON from disk; return empty structure on any error."""
    if not memory_path.exists():
        return {"history": [], "per_action": {}}
    try:
        raw = memory_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {"history": [], "per_action": {}}
        data.setdefault("history", [])
        data.setdefault("per_action", {})
        return data
    except Exception as exc:
        logger.warning("[ClosingRefreshMemory] load failed (%s), starting fresh", exc)
        return {"history": [], "per_action": {}}


def _save_memory(data: dict[str, Any], memory_path: Path) -> None:
    """Persist memory to disk atomically."""
    try:
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = memory_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(memory_path)
    except Exception as exc:
        logger.error("[ClosingRefreshMemory] save failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Improvement detection
# ─────────────────────────────────────────────────────────────────────────────

def _detect_improvement(
    pending_before: int,
    pending_after: int,
    computed_before: int,
    computed_after: int,
    missing_before: int,
    missing_after: int,
) -> bool:
    """
    Return True if the refresh run improved closing availability.

    Improvement criteria (any):
      - pending_after < pending_before   (fewer pending CLV records)
      - computed_after > computed_before (more COMPUTED CLV records)
      - missing_after < missing_before   (fewer records missing all sources)
    """
    if computed_after > computed_before:
        return True
    if pending_after < pending_before:
        return True
    if missing_after < missing_before:
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Escalation policy
# ─────────────────────────────────────────────────────────────────────────────

def _compute_escalation(
    action_type: str,
    consecutive_no_improvement: int,
    missing_before: int,
    missing_after: int,
    first_no_improvement_at: str | None,
    now_utc: datetime,
) -> tuple[bool, str | None]:
    """
    Evaluate escalation conditions.

    Returns:
        (escalation_recommended: bool, failure_reason: str | None)
    """
    reasons: list[str] = []

    # Condition 1: too many consecutive no-improvement runs
    threshold = (
        _EXTERNAL_CONSECUTIVE_NO_IMPROVEMENT_THRESHOLD
        if action_type == "refresh_external_closing"
        else _CONSECUTIVE_NO_IMPROVEMENT_THRESHOLD
    )
    if consecutive_no_improvement >= threshold:
        reasons.append(
            f"consecutive_no_improvement={consecutive_no_improvement} >= threshold={threshold}"
        )

    # Condition 2: missing_all_sources unchanged for > 6 hours
    if missing_before > 0 and missing_after >= missing_before and first_no_improvement_at:
        try:
            first_dt = datetime.fromisoformat(first_no_improvement_at.replace("Z", "+00:00"))
            stale_hours = (now_utc - first_dt).total_seconds() / 3600.0
            if stale_hours > _MISSING_STALE_HOURS_THRESHOLD:
                reasons.append(
                    f"missing_all_sources={missing_after} unchanged for {stale_hours:.1f}h"
                    f" (threshold={_MISSING_STALE_HOURS_THRESHOLD}h)"
                )
        except (ValueError, TypeError):
            pass

    escalated = len(reasons) > 0
    failure_reason = "; ".join(reasons) if reasons else None
    return escalated, failure_reason


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def record_outcome(
    action_type: str,
    pending_before: int,
    pending_after: int,
    computed_before: int,
    computed_after: int,
    missing_before: int,
    missing_after: int,
    *,
    memory_path: Path | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """
    Record a single refresh run outcome and update escalation state.

    Args:
        action_type:      One of REFRESH_ACTION_TYPES
        pending_before:   pending_total snapshot BEFORE execution
        pending_after:    pending_total snapshot AFTER execution
        computed_before:  computed_total BEFORE
        computed_after:   computed_total AFTER
        missing_before:   missing_all_sources BEFORE
        missing_after:    missing_all_sources AFTER
        memory_path:      Override for testing
        now_utc:          Override for testing

    Returns:
        The outcome record that was persisted:
        {
          "action_type": str,
          "run_at_utc": str,
          "pending_before": int, "pending_after": int,
          "computed_before": int, "computed_after": int,
          "missing_before": int, "missing_after": int,
          "improved": bool,
          "consecutive_no_improvement": int,
          "escalation_recommended": bool,
          "failure_reason": str | None,
        }
    """
    path = memory_path or _DEFAULT_MEMORY_PATH
    now = now_utc or datetime.now(timezone.utc)

    improved = _detect_improvement(
        pending_before, pending_after,
        computed_before, computed_after,
        missing_before, missing_after,
    )

    with _lock:
        data = _load_memory(path)
        per = data["per_action"].setdefault(action_type, {
            "consecutive_no_improvement": 0,
            "escalation_recommended": False,
            "last_run_at_utc": None,
            "last_improved": None,
            "first_no_improvement_at": None,
        })

        # Update consecutive counter
        if improved:
            consecutive = 0
            per["first_no_improvement_at"] = None  # reset streak start
        else:
            consecutive = per.get("consecutive_no_improvement", 0) + 1
            if per.get("first_no_improvement_at") is None:
                per["first_no_improvement_at"] = now.isoformat()

        # Evaluate escalation
        escalation_recommended, failure_reason = _compute_escalation(
            action_type=action_type,
            consecutive_no_improvement=consecutive,
            missing_before=missing_before,
            missing_after=missing_after,
            first_no_improvement_at=per.get("first_no_improvement_at"),
            now_utc=now,
        )

        # Update per_action state
        per["consecutive_no_improvement"] = consecutive
        per["escalation_recommended"] = escalation_recommended
        per["last_run_at_utc"] = now.isoformat()
        per["last_improved"] = improved

        # Build history entry
        entry: dict[str, Any] = {
            "action_type": action_type,
            "run_at_utc": now.isoformat(),
            "pending_before": pending_before,
            "pending_after": pending_after,
            "computed_before": computed_before,
            "computed_after": computed_after,
            "missing_before": missing_before,
            "missing_after": missing_after,
            "improved": improved,
            "consecutive_no_improvement": consecutive,
            "escalation_recommended": escalation_recommended,
            "failure_reason": failure_reason,
        }

        # Keep last 50 history entries
        data["history"].append(entry)
        if len(data["history"]) > 50:
            data["history"] = data["history"][-50:]

        _save_memory(data, path)

    logger.info(
        "[ClosingRefreshMemory] recorded outcome: action=%s improved=%s "
        "consecutive_no_improvement=%d escalation=%s",
        action_type, improved, consecutive, escalation_recommended,
    )
    return entry


def get_escalation_status(
    action_type: str | None = None,
    *,
    memory_path: Path | None = None,
) -> dict[str, Any]:
    """
    Return escalation state for a specific action_type (or the global max).

    Args:
        action_type: If given, return state for that specific type.
                     If None, return the worst-case across all types.
        memory_path: Override for testing.

    Returns:
        {
          "escalation_recommended": bool,
          "consecutive_no_improvement": int,
          "last_run_at_utc": str | None,
          "last_improved": bool | None,
          "recommended_escalation_action": str,  # "manual_review_summary" or "continue"
        }
    """
    path = memory_path or _DEFAULT_MEMORY_PATH
    data = _load_memory(path)
    per = data.get("per_action", {})

    if action_type is not None:
        state = per.get(action_type, {})
        escalated = state.get("escalation_recommended", False)
        return {
            "escalation_recommended": escalated,
            "consecutive_no_improvement": state.get("consecutive_no_improvement", 0),
            "last_run_at_utc": state.get("last_run_at_utc"),
            "last_improved": state.get("last_improved"),
            "recommended_escalation_action": "manual_review_summary" if escalated else "continue",
        }

    # Aggregate: return worst-case across all types
    any_escalated = any(v.get("escalation_recommended", False) for v in per.values())
    max_consecutive = max(
        (v.get("consecutive_no_improvement", 0) for v in per.values()), default=0
    )
    worst_type = max(
        per.items(),
        key=lambda kv: kv[1].get("consecutive_no_improvement", 0),
        default=(None, {}),
    )
    return {
        "escalation_recommended": any_escalated,
        "consecutive_no_improvement": max_consecutive,
        "last_run_at_utc": worst_type[1].get("last_run_at_utc") if worst_type[0] else None,
        "last_improved": worst_type[1].get("last_improved") if worst_type[0] else None,
        "recommended_escalation_action": "manual_review_summary" if any_escalated else "continue",
    }


def get_refresh_feedback_summary(
    *,
    memory_path: Path | None = None,
) -> dict[str, Any]:
    """
    Return a comprehensive refresh feedback summary for readiness/ops reports.

    Returns:
        {
          "available": bool,
          "last_refresh_action": str | None,
          "last_refresh_improved": bool | None,
          "last_refresh_at_utc": str | None,
          "consecutive_no_improvement": int,
          "escalation_recommended": bool,
          "recommended_escalation_action": str,
          "per_action": dict[str, dict],   # full per-action state
        }
    """
    path = memory_path or _DEFAULT_MEMORY_PATH

    try:
        data = _load_memory(path)
        per = data.get("per_action", {})
        history = data.get("history", [])

        # Last run overall
        last_entry = history[-1] if history else None

        # Worst-case escalation state
        esc = get_escalation_status(memory_path=path)

        return {
            "available": True,
            "last_refresh_action": last_entry["action_type"] if last_entry else None,
            "last_refresh_improved": last_entry["improved"] if last_entry else None,
            "last_refresh_at_utc": last_entry["run_at_utc"] if last_entry else None,
            "consecutive_no_improvement": esc["consecutive_no_improvement"],
            "escalation_recommended": esc["escalation_recommended"],
            "recommended_escalation_action": esc["recommended_escalation_action"],
            "per_action": {
                k: {
                    "consecutive_no_improvement": v.get("consecutive_no_improvement", 0),
                    "escalation_recommended": v.get("escalation_recommended", False),
                    "last_run_at_utc": v.get("last_run_at_utc"),
                    "last_improved": v.get("last_improved"),
                }
                for k, v in per.items()
            },
        }
    except Exception as exc:
        logger.debug("[ClosingRefreshMemory] get_refresh_feedback_summary failed: %s", exc)
        return {"available": False, "error": str(exc)}


def reset_action_streak(
    action_type: str,
    *,
    memory_path: Path | None = None,
) -> None:
    """
    Reset the no-improvement streak for an action_type when it finally improves.
    Called automatically by record_outcome() when improved=True; exposed for tests.
    """
    path = memory_path or _DEFAULT_MEMORY_PATH
    with _lock:
        data = _load_memory(path)
        per = data["per_action"].setdefault(action_type, {})
        per["consecutive_no_improvement"] = 0
        per["escalation_recommended"] = False
        per["first_no_improvement_at"] = None
        _save_memory(data, path)
