#!/usr/bin/env python3
"""
P107A: Special3 100-Draw Monitoring Gate
Read-only readiness assessment for re-running the Special3 prospective evaluation
once sufficient prospective draws have accumulated.

This script is read-only. It contains NO INSERT, UPDATE, DELETE, CREATE, DROP,
ALTER, REPLACE, VACUUM, or PRAGMA write statements.
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

HISTORY_END_DRAW = 115000024          # P99 training cutoff (exclusive)
P106_EVALUATED_MIN = 115000028        # First draw evaluated in P106
P106_EVALUATED_MAX = 115000106        # Last draw evaluated in P106
P106_EVALUATED_DRAWS = 63

EXPECTED_REPLAY_ROWS = 54462
THRESHOLD_100_DRAWS = 100

# P106 reference — do not change
P106_REFERENCE = {
    "classification": "P106_SPECIAL3_PROSPECTIVE_EVALUATION_PARTIAL",
    "pr_number": 235,
    "p100_criteria_passed": 5,
    "p100_criteria_total": 6,
    "ensemble_v2_top20_hit_rate": 0.1429,
    "ensemble_v2_top20_threshold": 0.15,
    "best_individual_strategy": "sum_band_frequency",
    "best_individual_strategy_top20_hit_rate": 0.1905,
}


# ---------------------------------------------------------------------------
# DB helpers (read-only)
# ---------------------------------------------------------------------------
def read_db_snapshot(db_path: Path) -> dict:
    """Read current DB state — all SELECT, no writes."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        replay_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]

        def get_type_stats(lottery_type: str):
            row = conn.execute(
                "SELECT COUNT(*), MAX(CAST(draw AS INTEGER)), MIN(CAST(draw AS INTEGER)) "
                "FROM draws WHERE lottery_type=?",
                (lottery_type,),
            ).fetchone()
            return {"count": row[0], "max_draw": row[1], "min_draw": row[2]}

        three_star = get_type_stats("3_STAR")
        four_star = get_type_stats("4_STAR")
        power_lotto = get_type_stats("POWER_LOTTO")

        # Prospective counts
        total_after_p99_cutoff = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR' "
            "AND CAST(draw AS INTEGER) > ?",
            (HISTORY_END_DRAW,),
        ).fetchone()[0]

        additional_after_p106 = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR' "
            "AND CAST(draw AS INTEGER) > ?",
            (P106_EVALUATED_MAX,),
        ).fetchone()[0]

        remaining_needed_for_100 = max(0, THRESHOLD_100_DRAWS - total_after_p99_cutoff)

        return {
            "replay_rows": replay_rows,
            "three_star_count": three_star["count"],
            "three_star_max_draw": str(three_star["max_draw"]) if three_star["max_draw"] else None,
            "four_star_count": four_star["count"],
            "four_star_max_draw": str(four_star["max_draw"]) if four_star["max_draw"] else None,
            "power_lotto_count": power_lotto["count"],
            "power_lotto_max_draw": str(power_lotto["max_draw"]) if power_lotto["max_draw"] else None,
            "total_after_p99_cutoff": total_after_p99_cutoff,
            "additional_after_p106": additional_after_p106,
            "remaining_needed_for_100": remaining_needed_for_100,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------
def determine_classification(snap: dict) -> str:
    if snap["replay_rows"] != EXPECTED_REPLAY_ROWS:
        return "P107A_SPECIAL3_100DRAW_BLOCKED_BY_DB_DRIFT"
    if snap["total_after_p99_cutoff"] >= THRESHOLD_100_DRAWS:
        return "P107A_SPECIAL3_100DRAW_READY"
    return "P107A_SPECIAL3_100DRAW_WAIT_MORE_DRAWS"


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------
def determine_recommendation(snap: dict, classification: str) -> str:
    if classification == "P107A_SPECIAL3_100DRAW_READY":
        return "run_100draw_rerun_next"
    if snap["additional_after_p106"] == 0:
        return "wait_for_more_draws"
    # Some new draws but still < 100 total
    return "wait_for_more_draws"


# ---------------------------------------------------------------------------
# Build artifact
# ---------------------------------------------------------------------------
def build_artifact(snap: dict) -> dict:
    classification = determine_classification(snap)
    recommendation = determine_recommendation(snap, classification)

    return {
        "schema_version": "p107a_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": classification,
        "source_unknown_caveat": True,
        "p106_reference": P106_REFERENCE,
        "history_end_draw": str(HISTORY_END_DRAW),
        "p106_evaluated_range": {
            "min": str(P106_EVALUATED_MIN),
            "max": str(P106_EVALUATED_MAX),
            "evaluated_draws": P106_EVALUATED_DRAWS,
        },
        "current_db_snapshot": {
            "replay_rows": snap["replay_rows"],
            "three_star_count": snap["three_star_count"],
            "three_star_max_draw": snap["three_star_max_draw"],
            "four_star_count": snap["four_star_count"],
            "four_star_max_draw": snap["four_star_max_draw"],
            "power_lotto_count": snap["power_lotto_count"],
            "power_lotto_max_draw": snap["power_lotto_max_draw"],
        },
        "prospective_draw_counts": {
            "total_after_p99_cutoff": snap["total_after_p99_cutoff"],
            "additional_after_p106": snap["additional_after_p106"],
            "remaining_needed_for_100": snap["remaining_needed_for_100"],
        },
        "recommendation": recommendation,
        "db_writes": False,
        "replay_rows_before": EXPECTED_REPLAY_ROWS,
        "replay_rows_after": snap["replay_rows"],
        "no_strategy_promotion": True,
        "no_4star_backtest": True,
        "no_lifecycle_mutation": True,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="P107A: Special3 100-Draw Monitoring Gate (read-only)"
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default=None,
        help="Path to write JSON artifact (optional; also prints to stdout)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=str(DB_PATH),
        help="Path to SQLite DB (default: canonical lottery_v2.db)",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    snap = read_db_snapshot(db_path)
    artifact = build_artifact(snap)

    # Print concise summary
    print("=" * 60)
    print("P107A: Special3 100-Draw Monitoring Gate")
    print("=" * 60)
    print(f"  classification           : {artifact['classification']}")
    print(f"  source_unknown_caveat    : {artifact['source_unknown_caveat']}")
    print(f"  replay_rows              : {snap['replay_rows']}")
    print(f"  3_STAR count / max draw  : {snap['three_star_count']} / {snap['three_star_max_draw']}")
    print(f"  total after P99 cutoff   : {snap['total_after_p99_cutoff']}")
    print(f"  additional after P106    : {snap['additional_after_p106']}")
    print(f"  remaining for 100        : {snap['remaining_needed_for_100']}")
    print(f"  recommendation           : {artifact['recommendation']}")
    print(f"  db_writes                : {artifact['db_writes']}")
    print(f"  no_strategy_promotion    : {artifact['no_strategy_promotion']}")
    print(f"  no_4star_backtest        : {artifact['no_4star_backtest']}")
    print("=" * 60)
    print(f"FINAL: {artifact['classification']}")

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False))
        print(f"JSON written to: {out_path}")

    return artifact


if __name__ == "__main__":
    main()
