from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.wbc_pool_a import list_wbc_matches_a
from data.wbc_pool_b import list_wbc_matches_b
from data.wbc_pool_c import list_wbc_matches
from data.wbc_pool_d import list_wbc_matches_d

REGISTRY_PATH = Path("data/wbc_backend/reports/prediction_registry.jsonl")
SCORES_PATH = Path("data/wbc_2026_live_scores.json")
OUTPUT_PATH = Path("data/wbc_backend/reports/gate_coverage_gaps.json")

TEAM_NAME_TO_CODE = {
    "Chinese Taipei": "TPE",
    "Australia": "AUS",
    "Czechia": "CZE",
    "Korea": "KOR",
    "South Korea": "KOR",
    "Japan": "JPN",
    "Cuba": "CUB",
    "Panama": "PAN",
    "Puerto Rico": "PUR",
    "Colombia": "COL",
    "Canada": "CAN",
    "Mexico": "MEX",
    "Great Britain": "GBR",
    "United States": "USA",
    "Brazil": "BRA",
    "Italy": "ITA",
    "Kingdom of the Netherlands": "NED",
    "Netherlands": "NED",
    "Venezuela": "VEN",
    "Nicaragua": "NIC",
    "Dominican Republic": "DOM",
    "Israel": "ISR",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _parse_ts(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _schedule_map() -> dict[str, dict[str, str]]:
    games = list_wbc_matches_a() + list_wbc_matches_b() + list_wbc_matches() + list_wbc_matches_d()
    return {g["game_id"]: {"date": g["date"], "away": g["away"], "home": g["home"]} for g in games}


def _live_index() -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[str, list[dict[str, Any]]], list[str]]:
    payload = json.loads(SCORES_PATH.read_text(encoding="utf-8"))
    exact: dict[tuple[str, str, str], dict[str, Any]] = {}
    by_date: dict[str, list[dict[str, Any]]] = {}
    unknown_names: list[str] = []
    for g in payload.get("games", []):
        if str(g.get("status", "")).lower() not in {"final", "completed early"}:
            continue
        away_name = str(g.get("away", ""))
        home_name = str(g.get("home", ""))
        away = TEAM_NAME_TO_CODE.get(away_name)
        home = TEAM_NAME_TO_CODE.get(home_name)
        if not away or not home:
            if not away:
                unknown_names.append(away_name)
            if not home:
                unknown_names.append(home_name)
            continue
        date = str(g.get("date", ""))
        rec = {"date": date, "away": away, "home": home, "raw": g}
        exact[(date, away, home)] = rec
        by_date.setdefault(date, []).append(rec)
    return exact, by_date, sorted(set(unknown_names))


def run() -> dict[str, Any]:
    schedule = _schedule_map()
    registry = _read_jsonl(REGISTRY_PATH)
    exact, by_date, unknown_names = _live_index()

    latest: dict[str, dict[str, Any]] = {}
    for row in registry:
        gid = str(row.get("game_id", "")).upper()
        if gid not in schedule:
            continue
        cur = latest.get(gid)
        if not cur or _parse_ts(str(row.get("recorded_at_utc"))) > _parse_ts(str(cur.get("recorded_at_utc"))):
            latest[gid] = row

    matched = []
    gaps = []
    for gid, row in sorted(latest.items()):
        s = schedule[gid]
        key = (s["date"], s["away"], s["home"])
        if key in exact:
            matched.append(gid)
            continue

        date_games = by_date.get(s["date"], [])
        reason = "pair_not_found_on_date"
        hint = "check date/team mapping"
        if not date_games:
            reason = "no_final_games_on_date"
            hint = "refresh live_scores date range"
        else:
            reversed_hit = any(g["away"] == s["home"] and g["home"] == s["away"] for g in date_games)
            away_present = any(g["away"] == s["away"] or g["home"] == s["away"] for g in date_games)
            home_present = any(g["away"] == s["home"] or g["home"] == s["home"] for g in date_games)
            if reversed_hit:
                reason = "home_away_reversed"
                hint = "verify schedule home/away orientation"
            elif away_present and home_present:
                reason = "teams_found_but_not_paired"
                hint = "possible stale schedule row or duplicated game id"
            elif away_present or home_present:
                reason = "single_team_found_only"
                hint = "check missing team code alias"

        gaps.append(
            {
                "game_id": gid,
                "recorded_at_utc": row.get("recorded_at_utc"),
                "expected": s,
                "reason": reason,
                "hint": hint,
                "live_games_same_date": [{"away": g["away"], "home": g["home"]} for g in date_games],
            }
        )

    result = {
        "n_registry_rows": len(registry),
        "n_latest_games": len(latest),
        "n_matched": len(matched),
        "n_gaps": len(gaps),
        "unknown_live_team_names": unknown_names,
        "matched_game_ids": matched,
        "gaps": gaps,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"coverage report saved: {OUTPUT_PATH}")
    print(json.dumps({"n_latest_games": len(latest), "n_matched": len(matched), "n_gaps": len(gaps)}))
    return result


if __name__ == "__main__":
    run()
