#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def fetch_scores_for_date(target_date: str) -> list[dict]:
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=51&date={target_date}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    games: list[dict] = []
    for day in data.get("dates", []):
        for g in day.get("games", []):
            away = g.get("teams", {}).get("away", {})
            home = g.get("teams", {}).get("home", {})
            games.append(
                {
                    "date": target_date,
                    "game_id": g.get("gamePk"),
                    "status": g.get("status", {}).get("detailedState", ""),
                    "away": away.get("team", {}).get("name", ""),
                    "away_score": away.get("score"),
                    "home": home.get("team", {}).get("name", ""),
                    "home_score": home.get("score"),
                    "venue": g.get("venue", {}).get("name", ""),
                }
            )
    return games


def daterange(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-03-05", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=date.today().isoformat(), help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--output",
        default="data/wbc_2026_live_scores.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    if end < start:
        raise ValueError("end date must be >= start date")

    all_games: list[dict] = []
    for day in daterange(start, end):
        all_games.extend(fetch_scores_for_date(day.isoformat()))

    payload = {
        "source": "MLB Stats API",
        "sport_id": 51,
        "start_date": args.start,
        "end_date": args.end,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "games_count": len(all_games),
        "games": all_games,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"output": str(out_path), "games_count": len(all_games)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
