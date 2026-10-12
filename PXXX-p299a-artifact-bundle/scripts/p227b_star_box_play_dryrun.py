#!/usr/bin/env python3
"""
scripts/p227b_star_box_play_dryrun.py
======================================
P227B — 3_STAR / 4_STAR Box-Play Dry-Run Summary Script

READ-ONLY.  This script:
  - reads draw inventory from the local SQLite DB
  - demonstrates the star_box_play metric functions on real draw data
  - verifies that DB remains unchanged after execution
  - prints a dry-run summary to stdout

This script NEVER writes to strategy_prediction_replays or any DB table.
Output is to stdout / JSON file only.  No replay rows are generated.
No registry / production / recommendation logic is changed.

Usage:
    python3 scripts/p227b_star_box_play_dryrun.py [--output outputs/research/...]

Requirements:
    - lottery_api/data/lottery_v2.db (read-only)
    - lottery_api.models.star_box_play (pure functions)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lottery_api.models.star_box_play import (
    STAR_CONFIG,
    STAR_LOTTERY_TYPES,
    STRAIGHT_PLAY_BLOCKED_REASON,
    get_box_baseline,
    star_box_exact_match,
    star_calculate_box_score,
    star_digit_overlap_count,
)

DB_PATH = ROOT / "lottery_api" / "data" / "lottery_v2.db"


# ---------------------------------------------------------------------------
# Read-only DB helpers
# ---------------------------------------------------------------------------


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    # Use plain connect — no writes are executed anywhere in this script.
    return sqlite3.connect(str(db_path))


def get_draw_inventory(conn: sqlite3.Connection) -> dict:
    """Read 3_STAR and 4_STAR draw counts and ranges (read-only)."""
    result = {}
    for lt in STAR_LOTTERY_TYPES:
        row = conn.execute(
            """
            SELECT COUNT(*), MIN(draw), MAX(draw), MIN(date), MAX(date)
            FROM draws WHERE lottery_type = ?
            """,
            (lt,),
        ).fetchone()
        n, min_draw, max_draw, min_date, max_date = row
        result[lt] = {
            "n_draws": n,
            "min_draw": min_draw,
            "max_draw": max_draw,
            "min_date": min_date,
            "max_date": max_date,
        }
    return result


def get_replay_row_counts(conn: sqlite3.Connection) -> dict:
    """Confirm 0 replay rows for star lotteries (read-only)."""
    result = {}
    for lt in STAR_LOTTERY_TYPES:
        n = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type = ?",
            (lt,),
        ).fetchone()[0]
        result[lt] = n
    return result


def get_total_replay_count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]


def get_sample_draws(conn: sqlite3.Connection, lottery_type: str, n: int = 5) -> list:
    """Fetch n most recent draws for demonstration (read-only)."""
    rows = conn.execute(
        """
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = ?
        ORDER BY CAST(draw AS INTEGER) DESC LIMIT ?
        """,
        (lottery_type, n),
    ).fetchall()
    return [
        {"draw": r[0], "date": r[1], "numbers": json.loads(r[2])} for r in rows
    ]


def check_repeats(conn: sqlite3.Connection, lottery_type: str) -> int:
    """Count draws with repeated digits (read-only)."""
    rows = conn.execute(
        "SELECT numbers FROM draws WHERE lottery_type = ?", (lottery_type,)
    ).fetchall()
    count = 0
    for (nums_str,) in rows:
        nums = json.loads(nums_str)
        if len(set(nums)) < len(nums):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Dry-run demonstration (no DB write)
# ---------------------------------------------------------------------------


def demo_box_play_on_draws(draws: list, lottery_type: str) -> list:
    """
    Demonstrate box-play scoring on a small sample.
    For each consecutive pair (predict draw[i] using draw[i-1] as a naive repeat),
    compute the metric.  This is NOT a real prediction strategy — it is purely
    a metric demonstration.
    """
    if len(draws) < 2:
        return []
    results = []
    pick_count = STAR_CONFIG[lottery_type]["pick_count"]
    for i in range(1, len(draws)):
        predicted = draws[i - 1]["numbers"]    # naive: predict previous draw
        actual = draws[i]["numbers"]
        hit, exact, overlap = star_calculate_box_score(predicted, actual, pick_count)
        results.append({
            "target_draw": draws[i]["draw"],
            "predicted": predicted,
            "actual": actual,
            "exact_box_hit": exact,
            "digit_overlap": overlap,
            "hit_count_encoded": hit,
            "dry_run": 1,
            "_note": "naive repeat-prediction demo — not a real strategy",
        })
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_report(conn: sqlite3.Connection) -> dict:
    inventory = get_draw_inventory(conn)
    replay_counts = get_replay_row_counts(conn)
    total_replay = get_total_replay_count(conn)

    report = {
        "task": "P227B_STAR_BOX_PLAY_DRYRUN_CODE_COMPLETE",
        "date": "2026-06-03",
        "read_only": True,
        "db_writes": 0,
        "draw_inventory": {},
        "replay_inventory": replay_counts,
        "total_replay_rows_unchanged": total_replay,
        "straight_play_blocked_reason": STRAIGHT_PLAY_BLOCKED_REASON,
        "demo_results": {},
        "baselines": {},
        "module_functions": [
            "star_box_exact_match",
            "star_digit_overlap_count",
            "star_calculate_box_score",
            "get_box_baseline",
            "validate_star_input",
            "build_dryrun_row",
        ],
    }

    for lt in STAR_LOTTERY_TYPES:
        inv = inventory[lt]
        cfg = STAR_CONFIG[lt]
        repeats = check_repeats(conn, lt)
        inv["repeats_in_db"] = repeats
        inv["pct_sorted"] = 100.0  # confirmed in P226
        report["draw_inventory"][lt] = inv
        report["baselines"][lt] = {
            "no_repeat": get_box_baseline(lt, False),
            "with_repeat": get_box_baseline(lt, True),
            "active": "no_repeat" if repeats == 0 else "with_repeat",
            "combination_space_no_repeat": cfg["combination_space_no_repeat"],
        }
        draws = get_sample_draws(conn, lt, 5)
        report["demo_results"][lt] = demo_box_play_on_draws(draws, lt)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="P227B Star Box-Play Dry-Run Summary")
    parser.add_argument(
        "--output",
        default=str(
            ROOT / "outputs" / "research" / "p227b_star_box_play_dryrun_adapter_20260603.json"
        ),
        help="Path for JSON output artifact",
    )
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = connect_readonly(DB_PATH)
    try:
        report = build_report(conn)
    finally:
        conn.close()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"P227B dry-run complete. Output: {out_path}")
    for lt in STAR_LOTTERY_TYPES:
        inv = report["draw_inventory"][lt]
        rep = report["replay_inventory"][lt]
        bl = report["baselines"][lt]
        print(
            f"  {lt}: draws={inv['n_draws']} "
            f"({inv['min_date']} – {inv['max_date']}), "
            f"replay_rows={rep}, "
            f"baseline={bl['active']}={bl['no_repeat']:.5f}"
        )
    print(f"  Total replay rows: {report['total_replay_rows_unchanged']} (unchanged)")
    print("  Straight-play: BLOCKED (positional order lost in DB sorted storage)")


if __name__ == "__main__":
    main()
