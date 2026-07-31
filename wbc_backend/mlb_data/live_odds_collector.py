"""
Live MLB Odds Timeline Collector

Captures real-time odds snapshots at scheduled intervals to build
genuine decision-time → closing odds timelines.

Capture schedule per game:
  T_open     = first time odds appear
  T_decision = commence_time - 2 hours
  T_pregame  = commence_time - 5 minutes
  T_close    = final snapshot before first pitch

Storage: data/mlb_context/odds_timeline.jsonl (one row per game, updated incrementally)
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .ids import make_mlb_game_id
from .normalization import canonical_team_name, parse_ts
from .odds_timeline_asset import MLB_ZH_TO_EN, _decimal_to_american

logger = logging.getLogger(__name__)

TIMELINE_PATH = Path("data/mlb_context/odds_timeline.jsonl")
# Slot assignment thresholds (used for setting decision_ts / closing_ts fields)
DECISION_LEAD_MINUTES = 60     # latest snapshot at T-60 or earlier = decision point
PREGAME_LEAD_MINUTES = 5      # kept for scheduler backward-compat (closing window check)
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
# Snapshot label thresholds (used only in _classify_snapshot_type for odds_history labels)
_CLOSING_LABEL_MINUTES = 10
_PREGAME_LABEL_MINUTES = 60
_DECISION_LABEL_MINUTES = 180


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class OddsSnapshot:
    ts: str
    home_ml: int | None
    away_ml: int | None
    ou_line: float | None = None
    source: str = "TSL"
    book: str = "TSL"
    snapshot_type: str = "pregame"

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class GameTimeline:
    game_id: str
    commence_time: str

    opening_home_ml: int | None = None
    opening_away_ml: int | None = None
    opening_ts: str | None = None

    decision_home_ml: int | None = None
    decision_away_ml: int | None = None
    decision_ts: str | None = None

    latest_pregame_home_ml: int | None = None
    latest_pregame_away_ml: int | None = None
    latest_pregame_ts: str | None = None

    closing_home_ml: int | None = None
    closing_away_ml: int | None = None
    closing_ts: str | None = None

    # External closing odds (from The Odds API / Pinnacle)
    # Populated separately — DO NOT overwrite with TSL data.
    external_closing_home_ml: int | None = None
    external_closing_away_ml: int | None = None
    external_closing_ts: str | None = None
    closing_source: str | None = None

    odds_history: list[dict[str, Any]] = field(default_factory=list)

    source: str = "TSL"
    book: str = "TSL"
    market_type: str = "moneyline"
    updated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _load_timelines(path: Path) -> dict[str, GameTimeline]:
    """Load existing timeline JSONL into a dict keyed by game_id."""
    timelines: dict[str, GameTimeline] = {}
    if not path.exists():
        return timelines
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        gid = str(obj.get("game_id", ""))
        if not gid:
            continue
        timelines[gid] = GameTimeline(
            game_id=gid,
            commence_time=str(obj.get("commence_time", "")),
            opening_home_ml=obj.get("opening_home_ml"),
            opening_away_ml=obj.get("opening_away_ml"),
            opening_ts=obj.get("opening_ts"),
            decision_home_ml=obj.get("decision_home_ml"),
            decision_away_ml=obj.get("decision_away_ml"),
            decision_ts=obj.get("decision_ts"),
            latest_pregame_home_ml=obj.get("latest_pregame_home_ml"),
            latest_pregame_away_ml=obj.get("latest_pregame_away_ml"),
            latest_pregame_ts=obj.get("latest_pregame_ts"),
            closing_home_ml=obj.get("closing_home_ml"),
            closing_away_ml=obj.get("closing_away_ml"),
            closing_ts=obj.get("closing_ts"),
            external_closing_home_ml=obj.get("external_closing_home_ml"),
            external_closing_away_ml=obj.get("external_closing_away_ml"),
            external_closing_ts=obj.get("external_closing_ts"),
            closing_source=obj.get("closing_source"),
            odds_history=obj.get("odds_history") or [],
            source=obj.get("source", "TSL"),
            book=obj.get("book", "TSL"),
            market_type=obj.get("market_type", "moneyline"),
            updated_at=obj.get("updated_at", ""),
        )
    return timelines


def _save_timelines(path: Path, timelines: dict[str, GameTimeline]) -> None:
    """Write all timelines back to JSONL (atomic overwrite)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    rows = sorted(timelines.values(), key=lambda t: t.game_id)
    tmp.write_text(
        "\n".join(json.dumps(t.as_dict(), ensure_ascii=False) for t in rows),
        encoding="utf-8",
    )
    tmp.replace(path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# TSL fetch adapter
# ---------------------------------------------------------------------------

def _fetch_tsl_odds(force_closing: bool = False) -> list[dict[str, Any]]:
    """Fetch current MLB odds from TSL crawler. Returns normalized game dicts.

    P26F: force_closing=True bypasses MNL dedup in tsl_odds_history.jsonl so that
    a closing snapshot is always written during the game_time ±2h window.
    """
    try:
        from data.tsl_crawler_v2 import TSLCrawlerV2
        crawler = TSLCrawlerV2(use_mock=False)
        raw_games = crawler.fetch_baseball_games(force_closing=force_closing)
    except Exception as exc:
        logger.error("TSL fetch failed: %s", exc)
        return []

    fetched_at = _now_iso()
    results: list[dict[str, Any]] = []
    for game in raw_games:
        home_zh = str(game.get("homeTeamName", game.get("home_team_name", "")))
        away_zh = str(game.get("awayTeamName", game.get("away_team_name", "")))
        home_en = MLB_ZH_TO_EN.get(home_zh.strip())
        away_en = MLB_ZH_TO_EN.get(away_zh.strip())
        if not home_en or not away_en:
            continue

        game_time = str(game.get("gameTime", game.get("game_time", "")))
        if not game_time:
            continue

        # Extract moneyline odds
        home_ml: int | None = None
        away_ml: int | None = None
        ou_line: float | None = None
        for market in game.get("markets", []) or []:
            code = str(market.get("marketCode", "")).upper()
            if code == "MNL":
                for out in market.get("outcomes", []) or []:
                    name = str(out.get("outcomeName", ""))
                    raw_odds = out.get("odds")
                    ml = _decimal_to_american(raw_odds)
                    if name == home_zh:
                        home_ml = ml
                    elif name == away_zh:
                        away_ml = ml
            elif code == "OU":
                for out in market.get("outcomes", []) or []:
                    sbv = out.get("specialBetValue")
                    if sbv is not None:
                        try:
                            ou_line = float(sbv)
                        except (TypeError, ValueError):
                            pass

        if home_ml is None and away_ml is None:
            continue

        results.append({
            "home_team": home_en,
            "away_team": away_en,
            "game_time": game_time,
            "home_ml": home_ml,
            "away_ml": away_ml,
            "ou_line": ou_line,
            "fetched_at": fetched_at,
            "source": "TSL",
        })

    return results


def _fetch_odds_api(api_key: str | None = None) -> list[dict[str, Any]]:
    """Optional fallback: The Odds API v4. Returns empty list if key missing."""
    if not api_key:
        return []
    import urllib.request
    url = (
        f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/"
        f"?apiKey={api_key}&regions=us&markets=h2h&oddsFormat=american"
    )
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("Odds API fetch failed: %s", exc)
        return []

    fetched_at = _now_iso()
    results: list[dict[str, Any]] = []
    for event in data:
        home_team = canonical_team_name(str(event.get("home_team", "")))
        away_team = canonical_team_name(str(event.get("away_team", "")))
        commence = str(event.get("commence_time", ""))
        home_ml = away_ml = None
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                for outcome in market.get("outcomes", []):
                    if canonical_team_name(str(outcome.get("name", ""))) == home_team:
                        home_ml = int(outcome.get("price", 0))
                    else:
                        away_ml = int(outcome.get("price", 0))
            if home_ml is not None:
                break
        if home_ml is None:
            continue
        results.append({
            "home_team": home_team,
            "away_team": away_team,
            "game_time": commence,
            "home_ml": home_ml,
            "away_ml": away_ml,
            "ou_line": None,
            "fetched_at": fetched_at,
            "source": "OddsAPI",
        })
    return results


# ---------------------------------------------------------------------------
# Timeline update engine
# ---------------------------------------------------------------------------

def _make_game_id_from_snapshot(snap: dict[str, Any]) -> str | None:
    """Build canonical game_id from a fetched snapshot."""
    game_time = str(snap.get("game_time", ""))
    dt = parse_ts(game_time)
    if dt is None:
        return None
    et = dt.astimezone(ZoneInfo("America/New_York"))
    et_date = et.date().isoformat()
    et_start = et.strftime("%I:%M %p").lstrip("0")
    home = str(snap.get("home_team", ""))
    away = str(snap.get("away_team", ""))
    if not home or not away:
        return None
    return make_mlb_game_id(et_date, et_start, away, home)


def _is_duplicate_snapshot(history: list[dict[str, Any]], snap: OddsSnapshot) -> bool:
    """Check if this exact snapshot already exists (idempotency)."""
    for existing in history:
        if (existing.get("ts") == snap.ts
                and existing.get("home_ml") == snap.home_ml
                and existing.get("away_ml") == snap.away_ml):
            return True
    return False


def _classify_snapshot_type(
    snap_ts: datetime,
    commence_ts: datetime,
) -> str:
    """Classify a snapshot timing relative to game start.

    Buckets (per user spec):
      closing  : <= 10 min
      pregame  : 10-60 min
      decision : 60-180 min
      early    : > 180 min
      postgame : after game start
    """
    delta = commence_ts - snap_ts
    minutes = delta.total_seconds() / 60.0
    if minutes < 0:
        return "postgame"
    if minutes <= _CLOSING_LABEL_MINUTES:
        return "closing"
    if minutes <= _PREGAME_LABEL_MINUTES:
        return "pregame"
    if minutes <= _DECISION_LABEL_MINUTES:
        return "decision"
    return "early"


def update_timeline_from_snapshots(
    snapshots: list[dict[str, Any]],
    timeline_path: Path = TIMELINE_PATH,
) -> dict[str, Any]:
    """
    Core update logic. Takes raw fetched snapshots, updates the timeline store.
    Returns a summary dict.
    """
    timelines = _load_timelines(timeline_path)
    now_iso = _now_iso()
    stats = {
        "snapshots_received": len(snapshots),
        "games_updated": 0,
        "snapshots_added": 0,
        "duplicates_skipped": 0,
        "unmatchable": 0,
    }

    for snap in snapshots:
        game_id = _make_game_id_from_snapshot(snap)
        if not game_id:
            stats["unmatchable"] += 1
            continue

        game_time = str(snap.get("game_time", ""))
        commence_ts = parse_ts(game_time)
        fetch_ts_str = str(snap.get("fetched_at", now_iso))
        fetch_ts = parse_ts(fetch_ts_str) or datetime.now(timezone.utc)

        home_ml = snap.get("home_ml")
        away_ml = snap.get("away_ml")
        if home_ml is None and away_ml is None:
            continue

        # Build snapshot record
        snap_record = OddsSnapshot(
            ts=fetch_ts_str,
            home_ml=home_ml,
            away_ml=away_ml,
            ou_line=snap.get("ou_line"),
            source=str(snap.get("source", "TSL")),
            book=str(snap.get("source", "TSL")),
            snapshot_type=_classify_snapshot_type(fetch_ts, commence_ts) if commence_ts else "unknown",
        )

        # Get or create timeline
        if game_id not in timelines:
            timelines[game_id] = GameTimeline(
                game_id=game_id,
                commence_time=game_time,
            )

        tl = timelines[game_id]

        # Idempotency check
        if _is_duplicate_snapshot(tl.odds_history, snap_record):
            stats["duplicates_skipped"] += 1
            continue

        # Append to history
        tl.odds_history.append(snap_record.as_dict())
        tl.odds_history.sort(key=lambda x: str(x.get("ts", "")))
        tl.updated_at = now_iso
        stats["snapshots_added"] += 1

        # Update slot fields based on timing
        if commence_ts is not None:
            delta_minutes = (commence_ts - fetch_ts).total_seconds() / 60.0

            # Opening: first snapshot we have
            if tl.opening_ts is None or fetch_ts_str < tl.opening_ts:
                tl.opening_home_ml = home_ml
                tl.opening_away_ml = away_ml
                tl.opening_ts = fetch_ts_str

            # Decision: latest snapshot before T-2h
            if delta_minutes >= DECISION_LEAD_MINUTES:
                if tl.decision_ts is None or fetch_ts_str > tl.decision_ts:
                    tl.decision_home_ml = home_ml
                    tl.decision_away_ml = away_ml
                    tl.decision_ts = fetch_ts_str

            # Latest pregame: latest snapshot before game start
            if delta_minutes >= 0:
                if tl.latest_pregame_ts is None or fetch_ts_str > tl.latest_pregame_ts:
                    tl.latest_pregame_home_ml = home_ml
                    tl.latest_pregame_away_ml = away_ml
                    tl.latest_pregame_ts = fetch_ts_str

            # Closing: latest pre-game snapshot we have.
            # Using the last captured snapshot before first pitch as the closing
            # line is correct for TSL which stops listing games once started.
            if 0 <= delta_minutes:
                if tl.closing_ts is None or fetch_ts_str > tl.closing_ts:
                    tl.closing_home_ml = home_ml
                    tl.closing_away_ml = away_ml
                    tl.closing_ts = fetch_ts_str

    stats["games_updated"] = sum(
        1 for tl in timelines.values()
        if tl.updated_at == now_iso
    )

    _save_timelines(timeline_path, timelines)
    return stats


def backfill_slots(timeline_path: Path = TIMELINE_PATH) -> dict[str, int]:
    """
    Retroactively recompute decision_ts, closing_ts and snapshot_type labels
    for all timelines by replaying their existing odds_history.

    - closing_ts : latest pre-game snapshot (any delta >= 0)
    - decision_ts: latest snapshot at delta >= DECISION_LEAD_MINUTES
    - snapshot_type: re-labelled per current _classify_snapshot_type thresholds

    Returns {"timelines_updated": N, "closing_filled": N, "decision_filled": N,
             "labels_updated": N}
    """
    timelines = _load_timelines(timeline_path)
    closing_filled = decision_filled = labels_updated = timelines_updated = 0

    for tl in timelines.values():
        commence_ts = parse_ts(tl.commence_time)
        if not commence_ts:
            continue

        best_closing_ts: str | None = None
        best_closing_home: int | None = None
        best_closing_away: int | None = None

        best_decision_ts: str | None = None
        best_decision_home: int | None = None
        best_decision_away: int | None = None

        changed = False
        new_history: list[dict[str, Any]] = []

        for snap in tl.odds_history:
            snap_ts = parse_ts(str(snap.get("ts", "")))
            new_snap = dict(snap)

            if snap_ts is not None:
                delta = (commence_ts - snap_ts).total_seconds() / 60.0
                new_type = _classify_snapshot_type(snap_ts, commence_ts)
                if new_snap.get("snapshot_type") != new_type:
                    new_snap["snapshot_type"] = new_type
                    changed = True
                    labels_updated += 1

                ts_str = str(snap.get("ts", ""))
                h = snap.get("home_ml")
                a = snap.get("away_ml")

                # Closing: any pre-game snapshot — take the latest
                if delta >= 0:
                    if best_closing_ts is None or ts_str > best_closing_ts:
                        best_closing_ts = ts_str
                        best_closing_home = h
                        best_closing_away = a

                # Decision: latest snapshot at >= DECISION_LEAD_MINUTES before start
                if delta >= DECISION_LEAD_MINUTES:
                    if best_decision_ts is None or ts_str > best_decision_ts:
                        best_decision_ts = ts_str
                        best_decision_home = h
                        best_decision_away = a

            new_history.append(new_snap)

        # Apply backfilled closing_ts
        if best_closing_ts is not None and tl.closing_ts != best_closing_ts:
            was_none = tl.closing_ts is None
            tl.closing_ts = best_closing_ts
            tl.closing_home_ml = best_closing_home
            tl.closing_away_ml = best_closing_away
            changed = True
            if was_none:
                closing_filled += 1

        # Apply backfilled decision_ts
        if best_decision_ts is not None and tl.decision_ts != best_decision_ts:
            was_none = tl.decision_ts is None
            tl.decision_ts = best_decision_ts
            tl.decision_home_ml = best_decision_home
            tl.decision_away_ml = best_decision_away
            changed = True
            if was_none:
                decision_filled += 1

        if changed:
            tl.odds_history = new_history
            timelines_updated += 1

    if timelines_updated:
        _save_timelines(timeline_path, timelines)

    return {
        "timelines_updated": timelines_updated,
        "closing_filled": closing_filled,
        "decision_filled": decision_filled,
        "labels_updated": labels_updated,
    }


# ---------------------------------------------------------------------------
# High-level capture function
# ---------------------------------------------------------------------------

def capture_live_odds(
    *,
    timeline_path: Path = TIMELINE_PATH,
    odds_api_key: str | None = None,
    force_closing: bool = False,
) -> dict[str, Any]:
    """
    Main entry point: fetch from all sources with retry, update timeline.

    P26F: force_closing=True is passed when the capture window is in closing mode
    (game_time ±2h), bypassing the MNL dedup filter in tsl_odds_history.jsonl.
    """
    all_snapshots: list[dict[str, Any]] = []

    # Primary: TSL
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            tsl_snaps = _fetch_tsl_odds(force_closing=force_closing)
            all_snapshots.extend(tsl_snaps)
            logger.info("TSL fetch OK: %d snapshots (attempt %d)", len(tsl_snaps), attempt)
            break
        except Exception as exc:
            logger.warning("TSL fetch attempt %d failed: %s", attempt, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)

    # Optional fallback: Odds API
    if odds_api_key:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                api_snaps = _fetch_odds_api(odds_api_key)
                all_snapshots.extend(api_snaps)
                logger.info("Odds API fetch OK: %d snapshots (attempt %d)", len(api_snaps), attempt)
                break
            except Exception as exc:
                logger.warning("Odds API attempt %d failed: %s", attempt, exc)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_SECONDS)

    # P28D: Run TSL market availability monitor after each poll cycle.
    # Uses only normalized TSL snapshots (source="TSL") already in all_snapshots.
    # Empty list is valid — means TSL returned nothing → potential early withdrawal.
    _tsl_monitor_result: dict[str, Any] = {}
    try:
        from .tsl_poll_monitor_adapter import run_tsl_monitor_after_poll
        _tsl_snaps_for_monitor = [s for s in all_snapshots if s.get("source") == "TSL"]
        _tsl_monitor_result = run_tsl_monitor_after_poll(
            tsl_snaps=_tsl_snaps_for_monitor,
            poll_ts=_now_iso(),
            context=f"capture_live_odds force_closing={force_closing}",
        )
    except Exception as _mon_exc:
        logger.warning("TSL monitor skipped: %s", _mon_exc)

    if not all_snapshots:
        logger.warning("No odds snapshots fetched from any source")
        base: dict[str, Any] = {"snapshots_received": 0, "games_updated": 0, "snapshots_added": 0}
        if _tsl_monitor_result:
            base["tsl_monitor"] = _tsl_monitor_result
        return base

    summary = update_timeline_from_snapshots(all_snapshots, timeline_path)

    # Retroactively fill any closing_ts / decision_ts that were missed by
    # earlier captures using the updated slot thresholds.
    backfill_result = backfill_slots(timeline_path)
    if backfill_result["timelines_updated"]:
        logger.info(
            "Slot backfill: %d timelines updated "
            "(closing_filled=%d, decision_filled=%d, labels=%d)",
            backfill_result["timelines_updated"],
            backfill_result["closing_filled"],
            backfill_result["decision_filled"],
            backfill_result["labels_updated"],
        )
        summary["backfill"] = backfill_result

    # External closing odds — single-shot daily strategy (max 2 API credits/day).
    # Fires only once per calendar day, near the first game start, to capture
    # genuine closing lines for CLV without exhausting the FREE plan quota.
    ext_key = odds_api_key or os.environ.get("ODDS_API_KEY")
    if ext_key:
        try:
            from .daily_closing_capture import run_daily_closing_capture
            daily_result = run_daily_closing_capture(
                api_key=ext_key,
                timeline_path=timeline_path,
            )
            summary["external_closing"] = daily_result
            status = daily_result.get("status", "unknown")
            if status == "ok":
                logger.info(
                    "Daily closing capture OK: updated=%d api_calls_today=%d",
                    daily_result.get("games_updated", 0),
                    daily_result.get("api_calls_today", 0),
                )
            else:
                logger.debug(
                    "Daily closing capture: status=%s reason=%s",
                    status,
                    daily_result.get("trigger_reason", ""),
                )
        except Exception as exc:
            logger.warning("Daily closing capture failed: %s", exc)

    if _tsl_monitor_result:
        summary["tsl_monitor"] = _tsl_monitor_result

    logger.info(
        "Odds capture complete: %d snapshots → %d games updated, %d added, %d dupes skipped",
        summary["snapshots_received"],
        summary["games_updated"],
        summary["snapshots_added"],
        summary["duplicates_skipped"],
    )
    return summary
