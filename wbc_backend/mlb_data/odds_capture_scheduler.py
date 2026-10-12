"""
MLB + WBC/NPB Odds Capture Scheduler

Schedules odds captures at critical time points for each MLB, WBC, and NPB game:
  T_open     = when odds first appear (continuous polling)
  T_decision = commence_time - 2 hours
  T_pregame  = commence_time - 5 minutes
  T_close    = commence_time (final snapshot)

P26B extension: determine_capture_windows() now also reads WBC/NPB game_times
from data/tsl_odds_history.jsonl so the daemon triggers closing captures near
each WBC/NPB game start.  MLB logic is unchanged (additive extension).

Integrates with existing AutoScheduler or runs standalone via cron.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .live_odds_collector import (
    DECISION_LEAD_MINUTES,
    PREGAME_LEAD_MINUTES,
    TIMELINE_PATH,
    capture_live_odds,
    _load_timelines,
)

logger = logging.getLogger(__name__)

# Schedule file tracks which captures have been completed
SCHEDULE_PATH = Path("data/mlb_context/odds_capture_schedule.json")

# P26B: source for WBC/NPB game times (read-only; never written by this module)
WBC_NPB_HISTORY_PATH = Path("data/tsl_odds_history.jsonl")

# How far ahead to look for upcoming WBC/NPB games (hours)
WBC_NPB_LOOKAHEAD_HOURS: float = 48.0

# Closing window: capture is triggered for WBC/NPB games within this many minutes
# BEFORE or AFTER game_time.  Negative = after game start.
WBC_NPB_CLOSING_BEFORE_MIN: float = 120.0   # up to 2h before game
WBC_NPB_CLOSING_AFTER_MIN: float = 120.0    # up to 2h after game start


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _load_schedule() -> dict[str, Any]:
    if not SCHEDULE_PATH.exists():
        return {"games": {}, "last_run": None}
    try:
        return json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"games": {}, "last_run": None}


def _save_schedule(schedule: dict[str, Any]) -> None:
    SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    schedule["last_run"] = _now_utc().isoformat().replace("+00:00", "Z")
    SCHEDULE_PATH.write_text(
        json.dumps(schedule, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _parse_ts_utc(s: str | None) -> datetime | None:
    """Parse a timestamp string (any timezone) into a UTC-aware datetime. Returns None on failure."""
    if not s:
        return None
    try:
        from dateutil.parser import parse as dtparse
        dt = dtparse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _load_wbc_npb_game_times(
    source_path: Path = WBC_NPB_HISTORY_PATH,
    lookahead_hours: float = WBC_NPB_LOOKAHEAD_HOURS,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """
    Load upcoming WBC/NPB game times from tsl_odds_history.jsonl.

    Returns a list of dicts (one per unique upcoming match) with:
      - match_id
      - game_time_utc (datetime, UTC-aware)
      - home_team / away_team

    Gracefully returns [] if source_path is missing, empty, or unparseable.
    Never raises — caller must treat missing data as "no WBC/NPB games".
    """
    if not source_path.exists():
        logger.debug("WBC/NPB source not found: %s — skipping WBC window check", source_path)
        return []

    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=lookahead_hours)

    seen: set[str] = set()
    games: list[dict[str, Any]] = []
    try:
        for line in source_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            mid = str(row.get("match_id", ""))
            if not mid or mid in seen:
                continue
            seen.add(mid)
            gt = _parse_ts_utc(row.get("game_time", ""))
            if gt is None:
                continue
            # Include upcoming games AND recently-started games within closing window
            # Lower bound: game_time >= now - WBC_NPB_CLOSING_AFTER_MIN
            earliest = now - timedelta(minutes=WBC_NPB_CLOSING_AFTER_MIN)
            if earliest <= gt <= cutoff:
                games.append({
                    "match_id": mid,
                    "game_time_utc": gt,
                    "home_team": row.get("home_team_name", ""),
                    "away_team": row.get("away_team_name", ""),
                })
    except OSError as exc:
        logger.warning("Could not read WBC/NPB source %s: %s", source_path, exc)
        return []

    logger.debug("Loaded %d upcoming WBC/NPB games from %s", len(games), source_path)
    return games


def get_todays_mlb_schedule() -> list[dict[str, Any]]:
    """
    Get today's MLB games from the existing timeline or TSL crawler.
    Returns list of dicts with game_id, commence_time, home_team, away_team.
    """
    # First check existing timeline for games
    timelines = _load_timelines(TIMELINE_PATH)
    now = _now_utc()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = today_start + timedelta(days=2)

    games: list[dict[str, Any]] = []
    for tl in timelines.values():
        from .normalization import parse_ts
        ct = parse_ts(tl.commence_time)
        if ct and today_start <= ct <= tomorrow_end:
            games.append({
                "game_id": tl.game_id,
                "commence_time": tl.commence_time,
            })

    return games


def determine_capture_windows(
    now: datetime | None = None,
    *,
    wbc_npb_source: Path | None = None,
) -> dict[str, Any]:
    """
    Determine which capture windows should be active right now.

    Returns dict with:
      - "continuous" (bool): always True
      - "decision"  (bool): True if any MLB/WBC/NPB game is 60-120 min away
      - "pregame"   (bool): True if any MLB/WBC/NPB game is 0-30 min away
      - "closing"   (bool): True if any MLB/WBC/NPB game is within ±closing window
      - "_wbc_npb_audit" (list[dict]): audit entries for WBC/NPB triggers
        Each entry: {match_id, home_team, away_team, game_time_utc,
                     minutes_to_game, trigger_types, source}

    P26B extension: also reads WBC/NPB game_times from tsl_odds_history.jsonl
    (via wbc_npb_source, defaults to WBC_NPB_HISTORY_PATH). MLB logic unchanged.
    """
    if now is None:
        now = _now_utc()

    # ── MLB logic (unchanged) ──────────────────────────────────────────────────
    timelines = _load_timelines(TIMELINE_PATH)
    windows: dict[str, Any] = {
        "continuous": True,
        "decision": False,
        "pregame": False,
        "closing": False,
        "_wbc_npb_audit": [],
    }

    from .normalization import parse_ts

    for tl in timelines.values():
        ct = parse_ts(tl.commence_time)
        if ct is None:
            continue
        delta_minutes = (ct - now).total_seconds() / 60.0
        if delta_minutes < 0:
            continue
        if DECISION_LEAD_MINUTES <= delta_minutes <= DECISION_LEAD_MINUTES + 60:
            windows["decision"] = True
        if 0 <= delta_minutes <= 30:
            windows["pregame"] = True
        if 0 <= delta_minutes <= PREGAME_LEAD_MINUTES:
            windows["closing"] = True

    # ── P26B: WBC / NPB extension (additive) ──────────────────────────────────
    src = wbc_npb_source if wbc_npb_source is not None else WBC_NPB_HISTORY_PATH
    wbc_games = _load_wbc_npb_game_times(source_path=src, now=now)

    for game in wbc_games:
        gt: datetime = game["game_time_utc"]
        delta_minutes = (gt - now).total_seconds() / 60.0

        # Skip games that started more than WBC_NPB_CLOSING_AFTER_MIN ago
        if delta_minutes < -WBC_NPB_CLOSING_AFTER_MIN:
            continue

        triggered: list[str] = []

        if DECISION_LEAD_MINUTES <= delta_minutes <= DECISION_LEAD_MINUTES + 60:
            windows["decision"] = True
            triggered.append("decision")

        if 0 <= delta_minutes <= 30:
            windows["pregame"] = True
            triggered.append("pregame")

        # Closing window: game_time - WBC_NPB_CLOSING_BEFORE_MIN  to
        #                 game_time + WBC_NPB_CLOSING_AFTER_MIN
        if -WBC_NPB_CLOSING_AFTER_MIN <= delta_minutes <= WBC_NPB_CLOSING_BEFORE_MIN:
            windows["closing"] = True
            triggered.append("closing")

        if triggered:
            windows["_wbc_npb_audit"].append({
                "match_id": game["match_id"],
                "home_team": game["home_team"],
                "away_team": game["away_team"],
                "game_time_utc": gt.isoformat().replace("+00:00", "Z"),
                "minutes_to_game": round(delta_minutes, 1),
                "trigger_types": triggered,
                "source": str(src),
                "trigger_reason": f"WBC/NPB game triggered windows={triggered} "
                                  f"(delta={delta_minutes:.1f}min)",
            })

    return windows


def should_capture_now() -> bool:
    """Quick check: is there any reason to run a capture right now?"""
    windows = determine_capture_windows()
    # Only check the boolean flags, not the audit list
    return any(windows[k] for k in ("continuous", "decision", "pregame", "closing"))


def run_scheduled_capture(
    *,
    odds_api_key: str | None = None,
    timeline_path: Path = TIMELINE_PATH,
    force: bool = False,
) -> dict[str, Any]:
    """
    Run a scheduled odds capture if appropriate timing.

    This is the function that cron or the scheduler should call.
    It handles:
    1. Checking if capture is needed
    2. Running the capture
    3. Recording what was captured
    4. Returning summary

    Args:
        odds_api_key: Optional API key for The Odds API fallback
        timeline_path: Path to timeline JSONL
        force: If True, capture regardless of timing
    """
    schedule = _load_schedule()
    now = _now_utc()

    if not force and not should_capture_now():
        return {
            "status": "skipped",
            "reason": "no games in capture window",
            "timestamp": now.isoformat().replace("+00:00", "Z"),
        }

    # Determine which windows are active
    windows = determine_capture_windows(now)

    # Run capture
    if odds_api_key is None:
        odds_api_key = os.environ.get("ODDS_API_KEY")

    result = capture_live_odds(
        timeline_path=timeline_path,
        odds_api_key=odds_api_key,
        force_closing=bool(windows.get("closing")),
    )

    # Record capture in schedule
    capture_record = {
        "timestamp": now.isoformat().replace("+00:00", "Z"),
        "windows": windows,
        "result": result,
    }

    if "captures" not in schedule:
        schedule["captures"] = []
    schedule["captures"].append(capture_record)

    # Keep only last 100 capture records
    if len(schedule["captures"]) > 100:
        schedule["captures"] = schedule["captures"][-100:]

    _save_schedule(schedule)

    return {
        "status": "captured",
        "timestamp": now.isoformat().replace("+00:00", "Z"),
        "windows": windows,
        "result": result,
    }


def get_capture_status() -> dict[str, Any]:
    """
    Get current status of odds capture pipeline.
    Shows which games have complete timelines and which are missing data.
    """
    timelines = _load_timelines(TIMELINE_PATH)
    schedule = _load_schedule()

    now = _now_utc()
    from .normalization import parse_ts

    stats = {
        "total_games": len(timelines),
        "games_with_opening": 0,
        "games_with_decision": 0,
        "games_with_pregame": 0,
        "games_with_closing": 0,
        "games_with_full_timeline": 0,
        "games_clv_ready": 0,
        "upcoming_games": 0,
        "last_capture": schedule.get("last_run"),
    }

    for tl in timelines.values():
        has_opening = tl.opening_ts is not None
        has_decision = tl.decision_ts is not None
        has_pregame = tl.latest_pregame_ts is not None
        has_closing = tl.closing_ts is not None

        stats["games_with_opening"] += int(has_opening)
        stats["games_with_decision"] += int(has_decision)
        stats["games_with_pregame"] += int(has_pregame)
        stats["games_with_closing"] += int(has_closing)
        stats["games_with_full_timeline"] += int(
            has_opening and has_decision and has_pregame and has_closing
        )
        stats["games_clv_ready"] += int(has_decision and has_closing)

        ct = parse_ts(tl.commence_time)
        if ct and ct > now:
            stats["upcoming_games"] += 1

    return stats
