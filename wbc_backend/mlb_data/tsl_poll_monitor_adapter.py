"""
tsl_poll_monitor_adapter.py
P28D: Wires TslMarketAvailabilityMonitor into the TSL poll cycle.

Converts normalized TSL snapshot dicts (as returned by _fetch_tsl_odds())
into the monitor's expected inputs and drives the load → update → save loop.

Design goals:
- Additive: does not modify TSL fetch behavior
- Safe: never raises; failures are logged and the monitor result is empty
- Testable: no live API calls; state_path is injectable for tests
- Persist: writes to DEFAULT_STATE_PATH (data/derived/) at runtime

Root cause addressed: P26K SOURCE_STATE_TRULY_EMPTY — previously there was no
mechanism to detect when TSL silently removed a game from its pre-game list
hours before tip-off. This adapter closes that gap.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .tsl_market_availability_monitor import (
    DEFAULT_STATE_PATH,
    TslMarketAvailabilityMonitor,
)

logger = logging.getLogger(__name__)

# Runtime state path (data/derived/ is gitignored at runtime level)
MONITOR_STATE_PATH: Path = DEFAULT_STATE_PATH


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_match_id(snap: dict[str, Any]) -> str:
    """
    Build a stable match ID from a normalized TSL snapshot dict.

    Uses composite key ``{game_time}|{home_team}|{away_team}``.
    All three components must be non-empty; returns ``""`` if any is missing
    so the caller can skip the snapshot.
    """
    game_time = str(snap.get("game_time") or "").strip()
    home = str(snap.get("home_team") or "").strip()
    away = str(snap.get("away_team") or "").strip()
    if not game_time or not home or not away:
        return ""
    return f"{game_time}|{home}|{away}"


# ---------------------------------------------------------------------------
# Public adapter
# ---------------------------------------------------------------------------


def run_tsl_monitor_after_poll(
    tsl_snaps: list[dict[str, Any]],
    poll_ts: str,
    state_path: Path | str = MONITOR_STATE_PATH,
    context: str = "",
) -> dict[str, Any]:
    """
    Run one TslMarketAvailabilityMonitor cycle against the latest TSL poll result.

    Safe to call with an empty list — an empty ``tsl_snaps`` means TSL returned
    nothing this cycle, which the monitor interprets as all previously-tracked
    matches being absent (potential early withdrawal or source_empty event).

    Parameters
    ----------
    tsl_snaps:
        Normalized snapshot list as returned by ``_fetch_tsl_odds()``.
        Each dict should contain ``game_time``, ``home_team``, ``away_team``.
        May be empty if the TSL fetch failed or returned no games.
    poll_ts:
        ISO 8601 UTC timestamp for this poll cycle (e.g. ``_now_iso()``).
    state_path:
        Path to the monitor's persisted JSON state file.  Inject a tmp path
        in tests to avoid touching the real state.
    context:
        Free-text context string written to ``source_response_context`` when
        a match first disappears (e.g., ``"capture_live_odds cycle_id=42"``).

    Returns
    -------
    dict
        ``{
            "new_alerts": list[dict],   # newly classified events this cycle
            "total_tracked": int,       # total match records in state after update
            "poll_ts": str,             # echoed poll_ts
        }``
        On internal error the dict additionally contains ``"error": str``
        and ``"new_alerts"`` is ``[]``.
    """
    try:
        monitor = TslMarketAvailabilityMonitor(state_path=Path(state_path))
        monitor.load()

        seen_ids: set[str] = set()
        metadata: dict[str, dict[str, Any]] = {}

        for snap in tsl_snaps:
            mid = _make_match_id(snap)
            if not mid:
                continue
            seen_ids.add(mid)
            metadata[mid] = {
                "game_time": str(snap.get("game_time") or ""),
                # All TSL baseball is MLB (the crawler only returns baseball)
                "league": str(snap.get("league") or "MLB"),
                "home_team_name": str(snap.get("home_team") or ""),
                "away_team_name": str(snap.get("away_team") or ""),
            }

        new_alerts = monitor.update(
            seen_match_ids=seen_ids,
            match_metadata=metadata,
            poll_ts=poll_ts,
            context=context,
        )
        monitor.save()

        for alert in new_alerts:
            logger.warning(
                "TSL market alert: classification=%s match_id=%s "
                "hours_before_game=%s game_time=%s",
                alert.get("classification"),
                alert.get("match_id"),
                alert.get("hours_before_game"),
                alert.get("game_time_utc"),
            )

        total = len(monitor.get_state())
        logger.debug(
            "TSL monitor: %d new alerts, %d total tracked (poll_ts=%s)",
            len(new_alerts),
            total,
            poll_ts,
        )

        return {
            "new_alerts": new_alerts,
            "total_tracked": total,
            "poll_ts": poll_ts,
        }

    except Exception as exc:
        logger.warning("TSL monitor update failed (non-fatal): %s", exc)
        return {
            "new_alerts": [],
            "total_tracked": 0,
            "poll_ts": poll_ts,
            "error": str(exc),
        }
