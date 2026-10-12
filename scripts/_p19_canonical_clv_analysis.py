"""P19-B/C: Canonical forward coverage regeneration + closing-line recheck.

paper_only=true, no network calls, no crawler modification.
Reads only: data/tsl_odds_history.jsonl
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PREGAME_MIN_HOURS_BEFORE: float = 2.0   # fetched_at must be >= 2h before game_time
CLOSING_MAX_HOURS_BEFORE: float = 2.0   # closing = within 2h window before/after game_time
PAIR_TARGET: int = 200


def _parse_dt(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _has_odds(snap: dict[str, Any]) -> bool:
    markets = snap.get("markets", [])
    if not markets:
        return False
    for m in markets:
        outcomes = m.get("outcomes", [])
        for o in outcomes:
            if o.get("odds"):
                return True
    return False


def analyse_history(path: Path) -> dict[str, Any]:
    """Read tsl_odds_history.jsonl and compute forward coverage metrics."""
    snapshots: list[dict] = []
    parse_errors = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            snapshots.append(json.loads(line))
        except Exception:
            parse_errors += 1

    # Group by match_id
    pregame: dict[str, list[dict]] = defaultdict(list)   # ≥2h before game
    closing: dict[str, list[dict]] = defaultdict(list)   # within ±2h of game
    timestamp_errors: list[str] = []
    game_dates: set[str] = set()
    unique_mids: set[str] = set()

    for snap in snapshots:
        mid = snap.get("match_id", "")
        if not mid:
            continue
        unique_mids.add(mid)

        fetched_raw = snap.get("fetched_at", "")
        gt_raw = snap.get("game_time", "")
        gt_date = gt_raw[:10] if gt_raw else ""
        if gt_date:
            game_dates.add(gt_date)

        fetched_dt = _parse_dt(fetched_raw)
        gt_dt = _parse_dt(gt_raw)

        if fetched_dt is None or gt_dt is None:
            timestamp_errors.append(mid)
            continue

        delta_hrs = (gt_dt - fetched_dt).total_seconds() / 3600

        if delta_hrs >= PREGAME_MIN_HOURS_BEFORE:
            pregame[mid].append(snap)
        if -CLOSING_MAX_HOURS_BEFORE <= delta_hrs < CLOSING_MAX_HOURS_BEFORE:
            closing[mid].append(snap)

    # Compute valid pairs: match_id in BOTH pregame AND closing, with odds
    valid_pairs: list[dict] = []
    invalid_pairs: list[dict] = []
    missing_closing: list[str] = []
    missing_pregame: list[str] = []

    all_mids = set(pregame.keys()) | set(closing.keys())
    for mid in all_mids:
        has_pre = mid in pregame
        has_close = mid in closing

        if not has_pre:
            missing_pregame.append(mid)
            invalid_pairs.append({"mid": mid, "reason": "no_pregame_snapshot"})
            continue
        if not has_close:
            missing_closing.append(mid)
            invalid_pairs.append({"mid": mid, "reason": "no_closing_snapshot"})
            continue

        # Pick best pregame (earliest) and best closing (latest before game)
        best_pre = min(pregame[mid], key=lambda s: s.get("fetched_at", ""))
        best_close = max(closing[mid], key=lambda s: s.get("fetched_at", ""))

        pre_has_odds = _has_odds(best_pre)
        close_has_odds = _has_odds(best_close)

        if not pre_has_odds or not close_has_odds:
            invalid_pairs.append({
                "mid": mid,
                "reason": "missing_odds",
                "pre_has_odds": pre_has_odds,
                "close_has_odds": close_has_odds,
            })
            continue

        valid_pairs.append({
            "mid": mid,
            "pregame_fetched_at": best_pre.get("fetched_at"),
            "closing_fetched_at": best_close.get("fetched_at"),
            "game_time": best_pre.get("game_time"),
            "source": best_pre.get("source"),
        })

    valid_pair_count = len(valid_pairs)
    pair_coverage_pct = round(valid_pair_count / PAIR_TARGET * 100, 1)

    return {
        "total_records": len(snapshots),
        "parse_errors": parse_errors,
        "unique_match_ids": len(unique_mids),
        "pregame_candidate_count": len(pregame),
        "closing_candidate_count": len(closing),
        "valid_pair_count": valid_pair_count,
        "invalid_pair_count": len(invalid_pairs),
        "missing_closing_count": len(missing_closing),
        "missing_pregame_count": len(missing_pregame),
        "timestamp_parse_error_count": len(timestamp_errors),
        "pair_target": PAIR_TARGET,
        "pair_coverage_pct": pair_coverage_pct,
        "unique_game_dates": len(game_dates),
        "game_date_range": {
            "first": min(game_dates) if game_dates else None,
            "last": max(game_dates) if game_dates else None,
        },
        "sample_valid_pairs": valid_pairs[:5],
        "sample_invalid_pairs": invalid_pairs[:5],
        "forward_coverage_status": (
            "CANONICAL_FORWARD_COVERAGE_SUFFICIENT"
            if valid_pair_count >= PAIR_TARGET
            else "ACCUMULATION_INSUFFICIENT"
        ),
        "clv_gate_clear_per_data": valid_pair_count >= PAIR_TARGET,
    }


if __name__ == "__main__":
    result = analyse_history(Path("data/tsl_odds_history.jsonl"))
    print(json.dumps(result, indent=2, default=str))
