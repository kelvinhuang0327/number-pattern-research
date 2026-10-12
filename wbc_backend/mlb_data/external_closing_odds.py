"""
External Closing Odds Fetcher

Supplements the TSL (decision-point) odds with real market closing lines
from The Odds API (Pinnacle / best-available).

Design:
  - TSL captures odds at T-60 to T-180 min  → used as decision_home_ml
  - This module fetches odds at T-0 to T-30 min → stored as external_closing_home_ml
  - CLV = implied_prob(external_closing) - implied_prob(decision_home_ml)

Storage contract:
  - Adds fields to existing timeline rows:
      external_closing_home_ml, external_closing_away_ml,
      external_closing_ts, closing_source
  - DOES NOT touch closing_home_ml / closing_ts (TSL-derived)
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .normalization import canonical_team_name, parse_ts
from .ids import make_mlb_game_id
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TIMELINE_PATH = Path("data/mlb_context/odds_timeline.jsonl")
ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/"

# Accept odds captured within ±90 min of game start.
# Quality tiers (by abs(delta_min)):
#   exact_close : 0–15 min  — very close to true closing line
#   near_close  : 15–45 min — good approximation
#   late_close  : 45–90 min — directionally useful, lower confidence
CLOSING_STALE_MINUTES = 90

# Team name mapping: The Odds API full names → canonical upper-case
_OA_TEAM_MAP: dict[str, str] = {
    "Arizona Diamondbacks": "ARIZONA DIAMONDBACKS",
    "Atlanta Braves": "ATLANTA BRAVES",
    "Baltimore Orioles": "BALTIMORE ORIOLES",
    "Boston Red Sox": "BOSTON RED SOX",
    "Chicago Cubs": "CHICAGO CUBS",
    "Chicago White Sox": "CHICAGO WHITE SOX",
    "Cincinnati Reds": "CINCINNATI REDS",
    "Cleveland Guardians": "CLEVELAND GUARDIANS",
    "Colorado Rockies": "COLORADO ROCKIES",
    "Detroit Tigers": "DETROIT TIGERS",
    "Houston Astros": "HOUSTON ASTROS",
    "Kansas City Royals": "KANSAS CITY ROYALS",
    "Los Angeles Angels": "LOS ANGELES ANGELS",
    "Los Angeles Dodgers": "LOS ANGELES DODGERS",
    "Miami Marlins": "MIAMI MARLINS",
    "Milwaukee Brewers": "MILWAUKEE BREWERS",
    "Minnesota Twins": "MINNESOTA TWINS",
    "New York Mets": "NEW YORK METS",
    "New York Yankees": "NEW YORK YANKEES",
    "Oakland Athletics": "OAKLAND ATHLETICS",
    "Philadelphia Phillies": "PHILADELPHIA PHILLIES",
    "Pittsburgh Pirates": "PITTSBURGH PIRATES",
    "San Diego Padres": "SAN DIEGO PADRES",
    "San Francisco Giants": "SAN FRANCISCO GIANTS",
    "Seattle Mariners": "SEATTLE MARINERS",
    "St. Louis Cardinals": "ST. LOUIS CARDINALS",
    "Tampa Bay Rays": "TAMPA BAY RAYS",
    "Texas Rangers": "TEXAS RANGERS",
    "Toronto Blue Jays": "TORONTO BLUE JAYS",
    "Washington Nationals": "WASHINGTON NATIONALS",
    # alternate spellings The Odds API sometimes uses
    "Athletics": "OAKLAND ATHLETICS",
    "Diamondbacks": "ARIZONA DIAMONDBACKS",
}


def _oa_team_name(raw: str) -> str:
    return _OA_TEAM_MAP.get(raw, canonical_team_name(raw))


def _american_from_decimal(dec: float | None) -> int | None:
    """Convert decimal odds to American moneyline."""
    if dec is None:
        return None
    try:
        d = float(dec)
    except (TypeError, ValueError):
        return None
    if d <= 1.0:
        return None
    if d >= 2.0:
        return round((d - 1) * 100)
    else:
        return round(-100 / (d - 1))


def fetch_external_closing_odds(
    api_key: str | None = None,
    *,
    regions: str = "us",
    bookmaker_priority: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch current MLB moneyline odds from The Odds API.

    Returns a list of normalized game dicts:
      {home_team, away_team, game_time, home_ml, away_ml, source, book, fetched_at}

    Falls back to empty list if no API key or request fails.
    """
    key = api_key or os.environ.get("ODDS_API_KEY") or ""
    if not key:
        logger.warning("ODDS_API_KEY not set — external closing odds unavailable")
        return []

    priority = bookmaker_priority or ["pinnacle", "draftkings", "fanduel", "betmgm"]
    url = (
        f"{ODDS_API_BASE}"
        f"?apiKey={key}"
        f"&regions={regions}"
        f"&markets=h2h"
        f"&oddsFormat=american"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "mlb-clv-pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        logger.error("Odds API HTTP error %d: %s", exc.code, exc.reason)
        return []
    except Exception as exc:
        logger.error("Odds API fetch failed: %s", exc)
        return []

    fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    results: list[dict[str, Any]] = []

    for event in raw:
        home_raw = str(event.get("home_team", ""))
        away_raw = str(event.get("away_team", ""))
        home_team = _oa_team_name(home_raw)
        away_team = _oa_team_name(away_raw)
        commence = str(event.get("commence_time", ""))
        if not commence:
            continue

        # Select best bookmaker by priority
        home_ml: int | None = None
        away_ml: int | None = None
        book_used: str = ""

        for bk_key in priority:
            for bookmaker in event.get("bookmakers", []):
                if bookmaker.get("key") != bk_key:
                    continue
                for market in bookmaker.get("markets", []):
                    if market.get("key") != "h2h":
                        continue
                    for outcome in market.get("outcomes", []):
                        name = _oa_team_name(str(outcome.get("name", "")))
                        price = outcome.get("price")
                        if price is None:
                            continue
                        # The Odds API american format returns ints
                        ml = int(price) if isinstance(price, (int, float)) else None
                        if name == home_team:
                            home_ml = ml
                        elif name == away_team:
                            away_ml = ml
                    if home_ml is not None and away_ml is not None:
                        book_used = bk_key
                        break
            if home_ml is not None and away_ml is not None:
                break

        if home_ml is None and away_ml is None:
            continue

        results.append({
            "home_team": home_team,
            "away_team": away_team,
            "game_time": commence,
            "home_ml": home_ml,
            "away_ml": away_ml,
            "source": "OddsAPI",
            "book": book_used,
            "fetched_at": fetched_at,
        })

    logger.info("Odds API: %d games fetched", len(results))
    return results


def _build_game_id(home_team: str, away_team: str, game_time: str) -> str | None:
    """Build canonical MLB game_id from external odds entry."""
    dt = parse_ts(game_time)
    if dt is None:
        return None
    et = dt.astimezone(ZoneInfo("America/New_York"))
    et_date = et.date().isoformat()
    et_start = et.strftime("%I:%M %p").lstrip("0")
    return make_mlb_game_id(et_date, et_start, away_team, home_team)


def _match_game_to_timeline(
    ext_home: str,
    ext_away: str,
    ext_game_time: str,
    timeline_ids: dict[str, Any],
) -> str | None:
    """
    Match an external odds entry to a timeline game_id.

    Strategy (in order):
      1. Exact game_id match via canonical ID builder
      2. Fuzzy: same team pair ± 2h of commence_time (handles minor schedule drift)
    """
    ext_dt = parse_ts(ext_game_time)

    # Strategy 1: exact ID
    exact_id = _build_game_id(ext_home, ext_away, ext_game_time)
    if exact_id and exact_id in timeline_ids:
        return exact_id

    if ext_dt is None:
        return None

    # Strategy 2: team pair + time window ±2h
    home_tok = ext_home.upper()
    away_tok = ext_away.upper()
    window = timedelta(hours=2)

    best: str | None = None
    best_delta = timedelta(days=999)

    for gid, tl in timeline_ids.items():
        tl_home = str(gid).split("-AT-")[-1] if "-AT-" in gid else ""
        tl_away = str(gid).split("-AT-")[0].rsplit("-", 1)[-1] if "-AT-" in gid else ""

        # Fast token check
        if home_tok not in tl_home.upper() and tl_home.upper() not in home_tok:
            continue
        if away_tok not in tl_away.upper() and tl_away.upper() not in away_tok:
            continue

        tl_ct = parse_ts(tl.get("commence_time", ""))
        if tl_ct is None:
            continue
        delta = abs(ext_dt - tl_ct)
        if delta <= window and delta < best_delta:
            best_delta = delta
            best = gid

    return best


def apply_external_closing_odds(
    external_games: list[dict[str, Any]],
    timeline_path: Path = TIMELINE_PATH,
    *,
    max_gap_minutes: float = CLOSING_STALE_MINUTES,
) -> dict[str, int]:
    """
    Merge external closing odds into the timeline JSONL.

    Rules:
      - Only writes external_closing_home_ml / external_closing_away_ml /
        external_closing_ts / closing_source
      - Does NOT touch closing_home_ml or closing_ts (TSL fields)
      - Only updates if the external snapshot is ≤ max_gap_minutes before
        game start (true closing condition)
      - Idempotent: will overwrite if a newer external snapshot exists

    Returns {"matched": N, "stale_skipped": N, "unmatched": N, "updated": N}
    """
    if not timeline_path.exists() or not external_games:
        return {"matched": 0, "stale_skipped": 0, "unmatched": 0, "updated": 0}

    # Load timeline
    lines = timeline_path.read_text(encoding="utf-8").splitlines()
    rows: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    id_to_idx: dict[str, int] = {str(r.get("game_id", "")): i for i, r in enumerate(rows)}
    id_to_row: dict[str, dict[str, Any]] = {str(r.get("game_id", "")): r for r in rows}

    stats = {"matched": 0, "stale_skipped": 0, "unmatched": 0, "updated": 0}

    for ext in external_games:
        ext_home = str(ext.get("home_team", ""))
        ext_away = str(ext.get("away_team", ""))
        ext_game_time = str(ext.get("game_time", ""))
        fetched_at = str(ext.get("fetched_at", ""))

        game_id = _match_game_to_timeline(ext_home, ext_away, ext_game_time, id_to_row)
        if not game_id:
            stats["unmatched"] += 1
            logger.debug("No timeline match for %s @ %s (%s)", ext_away, ext_home, ext_game_time)
            continue

        stats["matched"] += 1
        row = id_to_row[game_id]

        # Staleness check: accept if within ±max_gap_minutes of game start.
        # Positive delta = fetched before start; small negative = game just ticked over.
        commence_ts = parse_ts(str(row.get("commence_time", "")))
        fetch_ts = parse_ts(fetched_at)
        delta: float | None = None
        if commence_ts and fetch_ts:
            delta = (commence_ts - fetch_ts).total_seconds() / 60.0
            if abs(delta) > max_gap_minutes:
                stats["stale_skipped"] += 1
                logger.debug(
                    "Stale external odds for %s: gap=%.1fmin (max=±%s)",
                    game_id, delta, max_gap_minutes,
                )
                continue

        # Quality tier based on how close the fetch was to game start
        if delta is None:
            quality = "unknown"
        elif abs(delta) <= 15:
            quality = "exact_close"
        elif abs(delta) <= 45:
            quality = "near_close"
        else:
            quality = "late_close"

        # Only update if newer than existing external_closing_ts
        existing_ext_ts = str(row.get("external_closing_ts") or "")
        if existing_ext_ts and fetched_at and fetched_at <= existing_ext_ts:
            continue

        row["external_closing_home_ml"] = ext.get("home_ml")
        row["external_closing_away_ml"] = ext.get("away_ml")
        row["external_closing_ts"] = fetched_at
        row["closing_source"] = f"OddsAPI:{ext.get('book', 'unknown')}"
        row["external_closing_quality"] = quality
        stats["updated"] += 1

    if stats["updated"] > 0:
        tmp = timeline_path.with_suffix(".jsonl.tmp")
        tmp.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
            encoding="utf-8",
        )
        tmp.replace(timeline_path)
        logger.info(
            "External closing odds applied: matched=%d updated=%d stale_skipped=%d unmatched=%d",
            stats["matched"], stats["updated"], stats["stale_skipped"], stats["unmatched"],
        )

    return stats


def capture_external_closing(
    api_key: str | None = None,
    timeline_path: Path = TIMELINE_PATH,
    *,
    max_gap_minutes: float = CLOSING_STALE_MINUTES,
) -> dict[str, Any]:
    """
    High-level entry point: fetch + apply in one call.
    Returns combined stats dict.
    """
    games = fetch_external_closing_odds(api_key=api_key)
    if not games:
        return {
            "status": "no_data",
            "fetched": 0,
            "matched": 0,
            "updated": 0,
        }

    merge_stats = apply_external_closing_odds(
        games,
        timeline_path=timeline_path,
        max_gap_minutes=max_gap_minutes,
    )
    return {
        "status": "ok",
        "fetched": len(games),
        **merge_stats,
    }
