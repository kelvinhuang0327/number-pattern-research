"""
Daily Single-Shot External Closing Odds Capture

Strategy: consume at most 2 API credits per calendar day (1 primary + 1 retry).

Trigger condition:
  current_time >= earliest_game_start_today - TRIGGER_LEAD_MINUTES
  AND external_closing_fetched_today is False

One API call fetches ALL MLB games in a single request.
State is persisted to STATE_PATH so restarts never double-count.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Any

from .normalization import parse_ts
from .external_closing_odds import capture_external_closing

logger = logging.getLogger(__name__)

TIMELINE_PATH  = Path("data/mlb_context/odds_timeline.jsonl")
STATE_PATH     = Path("data/mlb_context/external_closing_state.json")

# Trigger when within this many minutes of the first game of the day
TRIGGER_LEAD_MINUTES = 10

# If the primary fetch fails, allow one retry after this many seconds
RETRY_AFTER_SECONDS = 300   # 5 minutes

# Policy A: reserve this many OddsAPI calls for the game-day closing trigger window.
# When api_calls_today >= (cap - CLOSING_WINDOW_RESERVE) and a future game's closing
# window has not yet opened, block the current call to preserve quota.
CLOSING_WINDOW_RESERVE = 1

# Accept snapshots captured within ±90 min of game start.
# Expanded from 30 to capture Wave 2 afternoon games (kickoff +35~+101 min after first pitch).
MAX_GAP_MINUTES = 90


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _today_utc() -> str:
    # Use ET (UTC-5) as the game-day clock.
    # MLB games run roughly 16:00–05:00 UTC; midnight Taiwan (UTC+8) = 16:00 UTC
    # falls right at first pitch, so local date.today() incorrectly assigns an
    # early-morning TW fetch (e.g. 00:34 Apr 17 LT = 16:34 UTC Apr 16) to Apr 17,
    # blocking the real Apr 17 trigger at ~18:10 UTC.
    et_now = datetime.now(timezone.utc) - timedelta(hours=5)
    return et_now.date().isoformat()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Timeline helpers
# ---------------------------------------------------------------------------

def _load_rows(timeline_path: Path) -> list[dict[str, Any]]:
    if not timeline_path.exists():
        return []
    rows = []
    for line in timeline_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def _earliest_game_today(timeline_path: Path) -> datetime | None:
    """Return the earliest upcoming game start time that is still within the capture window.

    Only considers games that haven't started more than MAX_GAP_MINUTES ago,
    so completed games from overnight ET sessions don't skew the trigger timing.
    """
    rows = _load_rows(timeline_path)
    now  = _now_utc()
    cutoff = now - timedelta(minutes=MAX_GAP_MINUTES)  # T-30 min hard floor

    candidates: list[datetime] = []
    for row in rows:
        if (row.get("source") or "").startswith("historical"):
            continue
        ct = parse_ts(str(row.get("commence_time", "")))
        if ct is None:
            continue
        # Include only games that haven't started more than MAX_GAP_MINUTES ago
        if ct >= cutoff:
            candidates.append(ct)

    return min(candidates) if candidates else None


def _count_external_closing(timeline_path: Path) -> int:
    rows = _load_rows(timeline_path)
    return sum(
        1 for r in rows
        if not (r.get("source") or "").startswith("historical")
        and r.get("external_closing_home_ml") is not None
    )


def _next_trigger_game(timeline_path: Path) -> datetime | None:
    """Return the earliest game whose closing-trigger window has not yet opened.

    Policy A uses this to detect whether a future closing window still needs a
    quota call reserved.  A game is "not yet triggered" when its start time is
    more than TRIGGER_LEAD_MINUTES in the future — i.e. the daemon would return
    ``skipped_too_early`` if asked to fetch for that game right now.
    """
    rows = _load_rows(timeline_path)
    now  = _now_utc()
    threshold = now + timedelta(minutes=TRIGGER_LEAD_MINUTES)

    candidates: list[datetime] = []
    for row in rows:
        if (row.get("source") or "").startswith("historical"):
            continue
        ct = parse_ts(str(row.get("commence_time", "")))
        if ct is None:
            continue
        if ct > threshold:
            candidates.append(ct)

    return min(candidates) if candidates else None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_daily_closing_capture(
    api_key: str | None = None,
    timeline_path: Path = TIMELINE_PATH,
    state_path: Path = STATE_PATH,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """
    Called on each daemon tick. Executes at most once per calendar day.

    Returns a status dict:
      status: "skipped_already_done" | "skipped_too_early" | "skipped_no_games"
              | "ok" | "failed" | "retry_too_soon"
      api_calls_today: int
      games_updated: int
      trigger_reason: str
    """
    key = api_key or os.environ.get("ODDS_API_KEY") or ""
    if not key:
        return {"status": "skipped_no_api_key", "api_calls_today": 0, "games_updated": 0}

    state = _load_state(state_path)
    today = _today_utc()

    # Reset daily counters if it's a new day
    if state.get("date") != today:
        state = {"date": today, "api_calls_today": 0, "fetched": False,
                 "last_attempt_ts": None, "last_failure_ts": None}

    api_calls = int(state.get("api_calls_today", 0))
    already_fetched = bool(state.get("fetched", False))

    # Hard cap: max 2 calls per day
    if api_calls >= 2:
        logger.info(
            "Daily closing BLOCKED: daily cap reached (api_calls_today=%d/2)", api_calls
        )
        return {
            "status": "skipped_daily_cap_reached",
            "api_calls_today": api_calls,
            "games_updated": 0,
            "trigger_reason": f"cap=2 reached, calls={api_calls}",
        }

    # Already succeeded today
    if already_fetched and not force:
        logger.info("Daily closing: already done today (fetched=True), skipping")
        return {
            "status": "skipped_already_done",
            "api_calls_today": api_calls,
            "games_updated": 0,
            "trigger_reason": "fetched=True for today",
        }

    # Check trigger: must be within TRIGGER_LEAD_MINUTES of first game
    now = _now_utc()
    earliest = _earliest_game_today(timeline_path)
    if earliest is None:
        return {
            "status": "skipped_no_games",
            "api_calls_today": api_calls,
            "games_updated": 0,
            "trigger_reason": "no live games in timeline for today",
        }

    minutes_to_first = (earliest - now).total_seconds() / 60.0
    trigger_threshold = TRIGGER_LEAD_MINUTES  # fire at T-10min

    if not force and minutes_to_first > trigger_threshold:
        logger.info(
            "Daily closing: waiting — %.0fmin to first game, trigger at T-%dmin",
            minutes_to_first, trigger_threshold,
        )
        return {
            "status": "skipped_too_early",
            "api_calls_today": api_calls,
            "games_updated": 0,
            "trigger_reason": f"{minutes_to_first:.1f}min to first game (threshold={trigger_threshold}min)",
        }

    # Policy A: Reserve CLOSING_WINDOW_RESERVE quota calls for future game closing windows.
    # If a future game's trigger window has not yet opened and the remaining quota would
    # be exhausted by this call, block it to preserve at least one call for that window.
    if not force and api_calls >= (2 - CLOSING_WINDOW_RESERVE):
        next_game = _next_trigger_game(timeline_path)
        if next_game is not None:
            mins_to_next = (next_game - now).total_seconds() / 60.0
            logger.info(
                "Daily closing QUOTA RESERVED: api_calls_today=%d/2, "
                "next game closing window in %.0fmin (T-%dmin trigger). "
                "Blocking to preserve closing window quota.",
                api_calls, mins_to_next, TRIGGER_LEAD_MINUTES,
            )
            return {
                "status": "skipped_quota_reserved_for_closing",
                "api_calls_today": api_calls,
                "games_updated": 0,
                "trigger_reason": (
                    f"quota reserved: {api_calls}/2 used, "
                    f"next game closing window in {mins_to_next:.0f}min"
                ),
            }

    # Retry cooldown: if last attempt failed, wait RETRY_AFTER_SECONDS
    last_failure = state.get("last_failure_ts")
    if last_failure and not force:
        lf_dt = parse_ts(last_failure)
        if lf_dt and (now - lf_dt).total_seconds() < RETRY_AFTER_SECONDS:
            wait_left = RETRY_AFTER_SECONDS - (now - lf_dt).total_seconds()
            return {
                "status": "retry_too_soon",
                "api_calls_today": api_calls,
                "games_updated": 0,
                "trigger_reason": f"retry cooldown: {wait_left:.0f}s remaining",
            }

    # ── Execute the fetch ──────────────────────────────────────────────────
    attempt_ts = now.isoformat().replace("+00:00", "Z")
    api_calls += 1
    state["api_calls_today"] = api_calls
    state["last_attempt_ts"] = attempt_ts
    _save_state(state, state_path)  # Policy B: persist quota counter BEFORE API call
                                    # (survives daemon crash mid-request)

    logger.info(
        "Daily closing capture triggered: %.1f min to first game, api_calls_today=%d",
        minutes_to_first, api_calls,
    )

    try:
        result = capture_external_closing(
            api_key=key,
            timeline_path=timeline_path,
            max_gap_minutes=MAX_GAP_MINUTES,
        )
    except Exception as exc:
        logger.error("Daily closing capture failed: %s", exc)
        state["last_failure_ts"] = attempt_ts
        _save_state(state, state_path)
        return {
            "status": "failed",
            "api_calls_today": api_calls,
            "games_updated": 0,
            "error": str(exc),
        }

    updated = result.get("updated", 0)
    fetched = result.get("fetched", 0)
    matched = result.get("matched", 0)
    stale   = result.get("stale_skipped", 0)
    unmatched = result.get("unmatched", 0)

    if result.get("status") == "no_data" or fetched == 0:
        logger.warning("Daily closing: API returned no games (fetched=0)")
        state["last_failure_ts"] = attempt_ts
        _save_state(state, state_path)
        return {
            "status": "failed",
            "api_calls_today": api_calls,
            "games_updated": 0,
            "trigger_reason": "OddsAPI returned 0 games",
        }

    # If every matched game was stale-skipped, the fetch happened too early.
    # Don't mark as done — allow a retry once we're closer to game time.
    if updated == 0 and stale > 0:
        logger.warning(
            "Daily closing: all %d games stale-skipped (fetched too early), will retry",
            stale,
        )
        state["last_failure_ts"] = attempt_ts
        state["last_result"] = {
            "fetched": fetched, "matched": matched,
            "updated": 0, "stale_skipped": stale, "unmatched": unmatched,
        }
        _save_state(state, state_path)
        return {
            "status": "stale_retry",
            "api_calls_today": api_calls,
            "games_updated": 0,
            "games_stale_skipped": stale,
            "trigger_reason": f"all {stale} games fetched too early (>30min before start)",
        }

    # Genuine success: at least one game received external closing odds
    state["fetched"] = True
    state["last_success_ts"] = attempt_ts
    state["last_result"] = {
        "fetched": fetched,
        "matched": matched,
        "updated": updated,
        "stale_skipped": stale,
        "unmatched": unmatched,
    }
    state.pop("last_failure_ts", None)
    _save_state(state, state_path)

    total_ext = _count_external_closing(timeline_path)

    logger.info(
        "Daily closing OK: fetched=%d matched=%d updated=%d stale=%d unmatched=%d "
        "total_with_ext=%d api_calls=%d",
        fetched, matched, updated, stale, unmatched, total_ext, api_calls,
    )

    return {
        "status": "ok",
        "api_calls_today": api_calls,
        "games_updated": updated,
        "games_fetched_from_api": fetched,
        "games_matched": matched,
        "games_stale_skipped": stale,
        "games_unmatched": unmatched,
        "total_games_with_external_closing": total_ext,
        "trigger_reason": f"T{minutes_to_first:+.1f}min to first game",
    }


def get_daily_state(state_path: Path = STATE_PATH) -> dict[str, Any]:
    """Return current daily state for health checks."""
    state = _load_state(state_path)
    today = _today_utc()
    if state.get("date") != today:
        return {"date": today, "api_calls_today": 0, "fetched": False}
    return state
