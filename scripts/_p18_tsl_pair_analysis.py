"""Temporary P18 TSL odds history CLV pair analysis (paper_only, no network calls)."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def analyse() -> dict:
    path = Path("data/tsl_odds_history.jsonl")
    if not path.exists():
        return {"error": "FILE_NOT_EXIST", "valid_clv_pairs": 0, "tsl_odds_history_exists": False}

    snapshots = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                snapshots.append(json.loads(line))
            except Exception:
                pass

    pregame: dict[str, list] = defaultdict(list)
    closing: dict[str, list] = defaultdict(list)
    game_dates: set[str] = set()
    no_game_time = 0

    for snap in snapshots:
        mid = snap.get("match_id", "")
        fetched_raw = snap.get("fetched_at", "")
        gt_raw = snap.get("game_time", "")
        if not fetched_raw or not gt_raw:
            no_game_time += 1
            continue
        try:
            fetched_dt = datetime.fromisoformat(fetched_raw.replace("Z", "+00:00"))
            gt_dt = datetime.fromisoformat(gt_raw)
            if gt_dt.tzinfo is None:
                gt_dt = gt_dt.replace(tzinfo=timezone.utc)
            delta_hrs = (gt_dt - fetched_dt).total_seconds() / 3600
            if delta_hrs >= 2:
                pregame[mid].append(snap)
            elif -2.0 <= delta_hrs < 2.0:
                closing[mid].append(snap)
        except Exception:
            pass
        gt_date = gt_raw[:10]
        if gt_date:
            game_dates.add(gt_date)

    valid_pair_ids = set(pregame.keys()) & set(closing.keys())
    n_pairs = len(valid_pair_ids)
    return {
        "tsl_odds_history_exists": True,
        "total_records": len(snapshots),
        "unique_match_ids_pregame": len(pregame),
        "unique_match_ids_closing": len(closing),
        "valid_clv_pairs": n_pairs,
        "pair_target": 200,
        "pair_coverage_pct": round(n_pairs / 200 * 100, 1),
        "clv_gate_clear": n_pairs >= 200,
        "unique_game_dates": len(game_dates),
        "no_game_time_records": no_game_time,
        "note": "pregame=fetched>=2h before game, closing=fetched within 2h of game_time",
    }


if __name__ == "__main__":
    result = analyse()
    print(json.dumps(result, indent=2))
