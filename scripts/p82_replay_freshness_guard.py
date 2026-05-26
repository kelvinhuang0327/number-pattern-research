"""
scripts/p82_replay_freshness_guard.py
======================================
P82 Replay Freshness / Source Gap Guard — read-only.

Checks whether monitored strategies have replay rows for the latest draw
in the draws table. Produces a JSON report with gap analysis.

Read-only: no DB writes, no ingestion, no replay row apply.

Usage:
  python scripts/p82_replay_freshness_guard.py [--lottery POWER_LOTTO] [--json-out path.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

# Strategies in each lottery that are expected to have draw-ext rows
# (Batch A applies). Historical-only strategies are allowed to lag.
BATCH_A_STRATEGIES: dict[str, list[str]] = {
    "POWER_LOTTO": [
        "fourier_rhythm_3bet",
        "fourier30_markov30_2bet",
    ],
}

# All monitored strategies per lottery (Batch A + historical backfill)
# Historical-only strategies lagging behind latest draw is EXPECTED.
HISTORICAL_STRATEGIES: dict[str, list[str]] = {
    "POWER_LOTTO": [
        "cold_complement_2bet",
        "midfreq_fourier_2bet",
        "midfreq_fourier_mk_3bet",
        "power_orthogonal_5bet",
        "power_precision_3bet",
        "pp3_freqort_4bet",
        "zonal_entropy_2bet",
    ],
}


def run_freshness_guard(lottery_type: str, db_path: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Latest draw in draws table (use CAST to avoid lexicographic errors)
    c.execute(
        "SELECT draw, date FROM draws WHERE lottery_type=? "
        "ORDER BY CAST(draw AS INTEGER) DESC LIMIT 1",
        (lottery_type,),
    )
    row = c.fetchone()
    if row is None:
        conn.close()
        return {
            "lottery_type": lottery_type,
            "error": f"No draws found for {lottery_type}",
            "classification": "FRESHNESS_ERROR",
        }
    latest_draw = row["draw"]
    latest_draw_date = row["date"]

    # Total replay rows
    c.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    replay_rows_total = c.fetchone()[0]

    # All strategies with rows in replay table for this lottery
    c.execute(
        """SELECT strategy_id, COUNT(*) as cnt, MAX(CAST(target_draw AS INTEGER)) as max_draw_int
           FROM strategy_prediction_replays
           WHERE lottery_type=? AND dry_run=0
           GROUP BY strategy_id
           ORDER BY max_draw_int DESC, cnt DESC""",
        (lottery_type,),
    )
    strategy_rows = c.fetchall()

    # Strategies that have a row for the latest draw
    latest_draw_int = int(latest_draw)
    strategies_all = []
    strategies_with_latest = []
    strategies_without_latest = []

    for sr in strategy_rows:
        sid = sr["strategy_id"]
        strategies_all.append(sid)
        if sr["max_draw_int"] == latest_draw_int:
            strategies_with_latest.append(sid)
        else:
            strategies_without_latest.append(sid)

    # Batch A strategies: expected to have latest draw
    batch_a = BATCH_A_STRATEGIES.get(lottery_type, [])
    historical = HISTORICAL_STRATEGIES.get(lottery_type, [])

    batch_a_covered = [s for s in batch_a if s in strategies_with_latest]
    batch_a_gap = [s for s in batch_a if s not in strategies_with_latest]

    # Historical strategies: gap is expected
    historical_gap = [s for s in historical if s in strategies_without_latest]

    # Coverage pct over Batch A strategies only
    if batch_a:
        batch_a_coverage_pct = round(len(batch_a_covered) / len(batch_a) * 100, 1)
    else:
        batch_a_coverage_pct = None

    # Overall coverage pct (all strategies)
    if strategies_all:
        overall_coverage_pct = round(
            len(strategies_with_latest) / len(strategies_all) * 100, 1
        )
    else:
        overall_coverage_pct = 0.0

    # Draw gap: does latest draw have any replay coverage at all?
    draw_gap_detected = len(strategies_with_latest) == 0

    # Replay gap: Batch A strategies missing latest draw
    replay_gap_detected = len(batch_a_gap) > 0

    # Classification
    if draw_gap_detected:
        classification = "FRESHNESS_DRAW_GAP_CRITICAL"
    elif replay_gap_detected:
        classification = "FRESHNESS_BATCH_A_GAP_WARNING"
    else:
        classification = "FRESHNESS_PASS"

    conn.close()

    return {
        "phase": "P82_REPLAY_FRESHNESS_GUARD",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "lottery_type": lottery_type,
        "db_path": str(db_path),
        "latest_draw": latest_draw,
        "latest_draw_date": latest_draw_date,
        "replay_rows_total": replay_rows_total,
        "strategies_checked": len(strategies_all),
        "strategies_with_latest_draw": strategies_with_latest,
        "strategies_without_latest_draw": strategies_without_latest,
        "batch_a_strategies": batch_a,
        "batch_a_covered": batch_a_covered,
        "batch_a_gap": batch_a_gap,
        "historical_strategies": historical,
        "historical_gap_expected": historical_gap,
        "batch_a_coverage_pct": batch_a_coverage_pct,
        "overall_coverage_pct": overall_coverage_pct,
        "draw_gap_detected": draw_gap_detected,
        "replay_gap_detected": replay_gap_detected,
        "classification": classification,
        "notes": [
            "Batch A strategies: expected to have draw-ext row for latest draw.",
            "Historical-only strategies: gap vs latest draw is EXPECTED (historical backfill only).",
            "draw_gap_detected=True means NO strategy has the latest draw (critical).",
            "replay_gap_detected=True means a Batch A strategy is missing latest draw (warning).",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="P82 Replay Freshness Guard")
    parser.add_argument(
        "--lottery",
        default="POWER_LOTTO",
        choices=["POWER_LOTTO", "BIG_LOTTO", "DAILY_539", "ALL"],
    )
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    lotteries = (
        ["POWER_LOTTO", "BIG_LOTTO", "DAILY_539"]
        if args.lottery == "ALL"
        else [args.lottery]
    )

    results = {}
    any_critical = False
    for lt in lotteries:
        r = run_freshness_guard(lt, db_path)
        results[lt] = r
        print(f"\n[{lt}]")
        print(f"  latest_draw        : {r.get('latest_draw')} ({r.get('latest_draw_date')})")
        print(f"  replay_rows_total  : {r.get('replay_rows_total')}")
        print(f"  strategies_checked : {r.get('strategies_checked')}")
        print(f"  batch_a_covered    : {r.get('batch_a_covered')}")
        print(f"  batch_a_gap        : {r.get('batch_a_gap')}")
        print(f"  draw_gap_detected  : {r.get('draw_gap_detected')}")
        print(f"  replay_gap_detected: {r.get('replay_gap_detected')}")
        print(f"  batch_a_coverage_pct: {r.get('batch_a_coverage_pct')}%")
        print(f"  classification     : {r.get('classification')}")
        if r.get("classification") not in ("FRESHNESS_PASS",):
            any_critical = True

    output = {
        "guard": "P82_REPLAY_FRESHNESS_GUARD",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "db_path": str(db_path),
        "results": results,
        "overall_classification": (
            "FRESHNESS_PASS"
            if not any_critical
            else "FRESHNESS_GAP_DETECTED"
        ),
    }

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(output, indent=2))
        print(f"\nJSON written to: {args.json_out}")

    print(f"\nOverall classification: {output['overall_classification']}")
    sys.exit(0 if output["overall_classification"] == "FRESHNESS_PASS" else 1)


if __name__ == "__main__":
    main()
