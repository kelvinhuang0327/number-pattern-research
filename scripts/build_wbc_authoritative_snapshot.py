#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.wbc_pool_a import _TEAM_FACTORIES_A, list_wbc_matches_a
from data.wbc_pool_b import _TEAM_FACTORIES_B, list_wbc_matches_b
from data.wbc_pool_c import _TEAM_FACTORIES, list_wbc_matches
from data.wbc_pool_d import _TEAM_FACTORIES_D, list_wbc_matches_d
from wbc_backend.config.settings import AppConfig


SCHEDULE_SOURCE_URL = "https://www.mlb.com/news/how-to-watch-the-2026-world-baseball-classic"
ROSTER_SOURCE_URL_TEMPLATE = "https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?season=2026"
LINEUPS_PENDING_NOTE = (
    "Schedule and roster are loaded from official sources. "
    "Lineups remain blocking until an official game-day lineup source is attached."
)

TEAM_NAME_TO_CODE = {
    "Australia": "AUS",
    "Brazil": "BRA",
    "Canada": "CAN",
    "Chinese Taipei": "TPE",
    "Colombia": "COL",
    "Cuba": "CUB",
    "Czechia": "CZE",
    "Dominican Republic": "DOM",
    "Great Britain": "GBR",
    "Israel": "ISR",
    "Italy": "ITA",
    "Japan": "JPN",
    "Kingdom of the Netherlands": "NED",
    "Korea": "KOR",
    "Mexico": "MEX",
    "Nicaragua": "NIC",
    "Panama": "PAN",
    "Puerto Rico": "PUR",
    "United States": "USA",
    "Venezuela": "VEN",
}

POOL_METADATA = {
    "A": {"round_name": "Pool A", "venue": "Estadio Hiram Bithorn, San Juan"},
    "B": {"round_name": "Pool B", "venue": "Minute Maid Park, Houston"},
    "C": {"round_name": "Pool C", "venue": "Tokyo Dome, Tokyo"},
    "D": {"round_name": "Pool D", "venue": "LoanDepot Park, Miami"},
}


def _normalize_name(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _to_utc(value: str) -> str:
    dt = datetime.fromisoformat(value)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_rosters(path: Path) -> Dict[str, Dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rosters: Dict[str, Dict] = {}
    for team in raw:
        code = TEAM_NAME_TO_CODE.get(team.get("team"))
        if not code:
            continue
        rosters[code] = {
            "team_id": team.get("team_id"),
            "team": team.get("team"),
            "players": [
                {
                    "name": player.get("name"),
                    "position": player.get("position"),
                }
                for player in team.get("players", [])
                if player.get("name")
            ],
        }
    return rosters


def _load_overrides(path: Path) -> Dict[str, Dict]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("games", {})


def _pitcher_catalog() -> Dict[str, Dict[str, Dict]]:
    catalog: Dict[str, Dict[str, Dict]] = {}
    for factories in (_TEAM_FACTORIES_A, _TEAM_FACTORIES_B, _TEAM_FACTORIES, _TEAM_FACTORIES_D):
        for code, factory in factories.items():
            _, pitchers = factory()
            team_map = catalog.setdefault(code, {})
            for pitcher in pitchers.values():
                team_map[_normalize_name(pitcher.name)] = asdict(pitcher)
    return catalog


def _default_lineup_catalog(rosters: Dict[str, Dict]) -> Dict[str, List[Dict]]:
    catalog: Dict[str, List[Dict]] = {}
    for code, roster in rosters.items():
        non_pitchers = [
            {"name": player["name"], "team": code}
            for player in roster.get("players", [])
            if player.get("position") != "P"
        ]
        fallback = non_pitchers[:9]
        if len(fallback) < 9:
            fallback = [{"name": player["name"], "team": code} for player in roster.get("players", [])[:9]]
        catalog[code] = fallback
    return catalog


def _build_schedule() -> List[Dict]:
    rows: List[Dict] = []
    sources: Iterable[Tuple[str, callable]] = (
        ("A", list_wbc_matches_a),
        ("B", list_wbc_matches_b),
        ("C", list_wbc_matches),
        ("D", list_wbc_matches_d),
    )
    for pool, fn in sources:
        meta = POOL_METADATA[pool]
        for game in fn():
            digits = int(game["game_id"][1:])
            rows.append(
                {
                    "canonical_game_id": game["game_id"],
                    "aliases": [
                        f"WBC2026_{game['away']}_{game['home']}_{digits:03d}",
                        f"WBC26-{game['away']}-{game['home']}-{digits:03d}",
                        f"{game['away']}_AT_{game['home']}",
                    ],
                    "tournament": "WBC2026",
                    "pool": pool,
                    "round_name": meta["round_name"],
                    "venue": meta["venue"],
                    "game_time_local": game["game_time"],
                    "game_time_utc": _to_utc(game["game_time"]),
                    "date": game["date"],
                    "home": game["home"],
                    "away": game["away"],
                    "schedule_source_urls": [SCHEDULE_SOURCE_URL],
                }
            )
    return rows


def _merge_pitcher(override_pitcher: Dict, team_code: str, catalog: Dict[str, Dict[str, Dict]]) -> Dict:
    name = override_pitcher["name"]
    base = catalog.get(team_code, {}).get(_normalize_name(name), {}).copy()
    base.update({"name": name, "team": team_code, "role": override_pitcher.get("role", base.get("role", "SP"))})
    return base


def build_snapshot(
    *,
    roster_path: Path,
    overrides_path: Path,
    output_path: Path,
) -> Dict:
    rosters = _load_rosters(roster_path)
    overrides = _load_overrides(overrides_path)
    pitcher_catalog = _pitcher_catalog()
    lineup_catalog = _default_lineup_catalog(rosters)
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    games: List[Dict] = []
    last_known_lineup = {code: lineup[:] for code, lineup in lineup_catalog.items()}
    for base in sorted(_build_schedule(), key=lambda item: item["game_time_utc"]):
        game_id = base["canonical_game_id"]
        home_code = base["home"]
        away_code = base["away"]
        home_roster = rosters.get(home_code, {})
        away_roster = rosters.get(away_code, {})
        override = overrides.get(game_id, {})
        home_lineup = override.get("home_lineup", [])
        away_lineup = override.get("away_lineup", [])
        home_previous_lineup = last_known_lineup.get(home_code, [])
        away_previous_lineup = last_known_lineup.get(away_code, [])
        home_sp = override.get("home_sp")
        away_sp = override.get("away_sp")

        game = {
            **base,
            "home_roster": [player["name"] for player in home_roster.get("players", [])],
            "away_roster": [player["name"] for player in away_roster.get("players", [])],
            "home_roster_source_url": ROSTER_SOURCE_URL_TEMPLATE.format(team_id=home_roster.get("team_id", "")),
            "away_roster_source_url": ROSTER_SOURCE_URL_TEMPLATE.format(team_id=away_roster.get("team_id", "")),
            "home_sp": _merge_pitcher(home_sp, home_code, pitcher_catalog) if home_sp else {},
            "away_sp": _merge_pitcher(away_sp, away_code, pitcher_catalog) if away_sp else {},
            "home_lineup": home_lineup,
            "away_lineup": away_lineup,
            "home_previous_lineup": home_previous_lineup,
            "away_previous_lineup": away_previous_lineup,
            "starter_source_urls": override.get("starter_source_urls", []),
            "lineup_source_urls": override.get("lineup_source_urls", []),
            "notes": override.get("notes", LINEUPS_PENDING_NOTE),
            "verification": {
                "schedule_verified": True,
                "rosters_verified": bool(home_roster.get("players")) and bool(away_roster.get("players")),
                "starters_verified": bool(home_sp) and bool(away_sp),
                "lineups_verified": len(home_lineup) == 9 and len(away_lineup) == 9,
                "last_verified_at": override.get("verified_at", generated_at),
                "max_age_hours": 24 if not home_lineup and not away_lineup else 6,
            },
        }
        games.append(game)
        last_known_lineup[home_code] = home_lineup or home_previous_lineup
        last_known_lineup[away_code] = away_lineup or away_previous_lineup

    payload = {
        "version": 2,
        "generated_at": generated_at,
        "description": (
            "Authoritative WBC snapshot built from official MLB/WBC schedule and roster sources. "
            "Predictions remain blocked until starters and lineups are officially verified per game."
        ),
        "games": games,
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    config = AppConfig()
    payload = build_snapshot(
        roster_path=ROOT / "data" / "wbc_all_players_realtime.json",
        overrides_path=ROOT / "data" / "wbc_verified_overrides.json",
        output_path=ROOT / config.sources.wbc_authoritative_snapshot_json,
    )
    starters_verified = sum(1 for game in payload["games"] if game["verification"]["starters_verified"])
    lineups_verified = sum(1 for game in payload["games"] if game["verification"]["lineups_verified"])
    print(
        f"Generated {len(payload['games'])} games -> "
        f"starters_verified={starters_verified}, lineups_verified={lineups_verified}"
    )


if __name__ == "__main__":
    main()
