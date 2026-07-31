"""
tsl_monitor_alert_formatter.py
P28D.2: Format and emit operator-facing alerts from TSL monitor heartbeat rows.

Reads the four P28D.1 fields from a heartbeat row dict:
  - tsl_monitor_status
  - tsl_monitor_has_withdrawal_early
  - tsl_monitor_new_alerts_count
  - tsl_monitor_alerts_count

Surfaces alerts via structured WARNING log entries. The same message string is
returned for downstream use (e.g. Telegram bot proactive push, future webhook).

Design constraints:
  - Pure functions — no network calls, no file I/O.
  - Always failure-safe: never raises.
  - Backward-compatible: rows missing P28D.1 fields default to no-alert.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Classification label that triggers high-priority wording.
_WITHDRAWAL_EARLY_CLASS: str = "TSL_MARKET_WITHDRAWAL_EARLY"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def should_emit_alert(row: Any) -> bool:
    """
    Return True if this heartbeat row warrants an operator alert.

    Triggers on:
      - tsl_monitor_status == "alert"
      - tsl_monitor_has_withdrawal_early is True

    Always returns False for non-dict inputs and rows missing P28D.1 fields
    (backward-compatible with pre-P28D.1 heartbeat rows).
    """
    if not isinstance(row, dict):
        return False
    tsl_status: str = str(row.get("tsl_monitor_status") or "no_data")
    has_withdrawal: bool = bool(row.get("tsl_monitor_has_withdrawal_early", False))
    return tsl_status == "alert" or has_withdrawal


def format_alert_message(row: Any) -> str:
    """
    Format an operator-facing alert message from a heartbeat row dict.

    Safe to call with any input — non-dict rows are handled gracefully.
    Returns a plain-text multi-line string suitable for logging and
    Telegram messages.
    """
    if not isinstance(row, dict):
        row = {}

    new_count: int = int(row.get("tsl_monitor_new_alerts_count") or 0)
    total_tracked: int = int(row.get("tsl_monitor_alerts_count") or 0)
    has_withdrawal: bool = bool(row.get("tsl_monitor_has_withdrawal_early", False))
    status: str = str(row.get("tsl_monitor_status") or "unknown")
    timestamp: str = str(row.get("timestamp") or "unknown")

    if has_withdrawal:
        priority_tag = "🚨 HIGH"
        alert_type = "早期撤市偵測 (TSL_MARKET_WITHDRAWAL_EARLY)"
    else:
        priority_tag = "ℹ️  INFO"
        alert_type = "市場警示 (TSL monitor alert)"

    lines = [
        f"[TSL Monitor Alert] {priority_tag}",
        f"  alert_type        : {alert_type}",
        f"  tsl_status        : {status}",
        f"  new_alerts        : {new_count}",
        f"  total_tracked     : {total_tracked}",
        f"  withdrawal_early  : {has_withdrawal}",
        f"  timestamp         : {timestamp}",
    ]
    return "\n".join(lines)


def emit_alert_if_needed(row: Any) -> str | None:
    """
    Emit an operator alert if the heartbeat row warrants one.

    If ``should_emit_alert(row)`` is True, formats the message and logs it
    at WARNING level (visible in daemon logs and monitoring tools).  Returns
    the formatted message string so callers (Telegram bot, webhooks) can
    forward it.

    Returns None if no alert was needed or if an internal error occurs.
    Never raises — observability must always be safe.
    """
    try:
        if not should_emit_alert(row):
            return None
        msg = format_alert_message(row)
        logger.warning(msg)
        return msg
    except Exception as exc:  # pragma: no cover
        logger.warning("TSL monitor alert emission failed (non-fatal): %s", exc)
        return None
