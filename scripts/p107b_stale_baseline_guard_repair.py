#!/usr/bin/env python3
"""
P107B: Stale Baseline Guard Repair
Read-only script that queries the current accepted DB baseline and
summarises the P107B stale-test repair.

This script is read-only. It contains NO INSERT, UPDATE, DELETE, CREATE,
REPLACE, VACUUM, or PRAGMA write statements.
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

# ── Governance constants ──────────────────────────────────────────────────────
EXPECTED_REPLAY_ROWS = 54462

# Accepted post-P104 baseline (confirmed by P105/P106/P107A)
ACCEPTED_BASELINE = {
    "replay_rows": 54462,
    "three_star_count": 4179,
    "three_star_max_draw": "115000106",
    "four_star_count": 2922,
    "four_star_max_draw": "115000103",
    "power_lotto_count": 1913,
    "power_lotto_max_draw": "115000041",
}

# Stale pre-P104 baselines that were repaired
STALE_BASELINE = {
    "old_three_star_count": 4115,
    "old_three_star_max_draw": "115000024",
    "old_four_star_count": 0,
    "source": "P98/P99 artifacts recorded pre-P104 DB state",
}

# Tests repaired in this P107B pass
REPAIRED_TESTS = [
    {
        "file": "tests/test_p98_special3_oos_permutation_review.py",
        "test": "test_11_no_4star_backtest_metrics",
        "old_assertion": "assert star4_rows == 0",
        "new_assertion": "assert star4_rows == 2922 (P104 accepted baseline)",
        "rationale": "P104 ingested 2922 4_STAR rows; 4_STAR backtest remains unauthorized.",
    },
    {
        "file": "tests/test_p99_special3_prospective_dryrun_plan.py",
        "test": "test_14_special4_data_gap_blocking",
        "old_assertion": "assert star4_count == 0",
        "new_assertion": "assert star4_count == 2922 (P104 accepted baseline)",
        "rationale": (
            "Historical artifact DATA_GAP_BLOCKING remains valid (P99 era). "
            "Live-DB cross-check updated to post-P104 accepted baseline."
        ),
    },
]

VALID_CLASSIFICATIONS = {
    "P107B_STALE_BASELINE_GUARD_REPAIR_READY",
    "P107B_STALE_BASELINE_GUARD_REPAIR_BLOCKED_BY_PREFLIGHT",
    "P107B_STALE_BASELINE_GUARD_REPAIR_BLOCKED_BY_DB_DRIFT",
    "P107B_STALE_BASELINE_GUARD_REPAIR_BLOCKED_BY_TEST_FAILURE",
    "P107B_STALE_BASELINE_GUARD_REPAIR_BLOCKED_BY_FORBIDDEN_FILES_STAGED",
    "P107B_STALE_BASELINE_GUARD_REPAIR_BLOCKED_BY_SCOPE_VIOLATION",
    "P107B_STALE_BASELINE_GUARD_REPAIR_BLOCKED_BY_CONTEXT_CONTAMINATION",
}


# ── DB read ───────────────────────────────────────────────────────────────────

def read_db_snapshot(db_path: Path = DB_PATH) -> dict:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        replay_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]

        def _stat(lt):
            row = conn.execute(
                "SELECT COUNT(*), MAX(CAST(draw AS INTEGER)) FROM draws "
                "WHERE lottery_type=?",
                (lt,),
            ).fetchone()
            return row[0], str(row[1]) if row[1] is not None else None

        s3_count, s3_max = _stat("3_STAR")
        s4_count, s4_max = _stat("4_STAR")
        pl_count, pl_max = _stat("POWER_LOTTO")
    finally:
        conn.close()

    return {
        "replay_rows": replay_rows,
        "three_star_count": s3_count,
        "three_star_max_draw": s3_max,
        "four_star_count": s4_count,
        "four_star_max_draw": s4_max,
        "power_lotto_count": pl_count,
        "power_lotto_max_draw": pl_max,
    }


def _matches_accepted(snap: dict) -> bool:
    for k, v in ACCEPTED_BASELINE.items():
        if snap.get(k) != v:
            return False
    return True


def determine_classification(snap: dict) -> str:
    if snap["replay_rows"] != EXPECTED_REPLAY_ROWS:
        return "P107B_STALE_BASELINE_GUARD_REPAIR_BLOCKED_BY_DB_DRIFT"
    if not _matches_accepted(snap):
        return "P107B_STALE_BASELINE_GUARD_REPAIR_BLOCKED_BY_DB_DRIFT"
    return "P107B_STALE_BASELINE_GUARD_REPAIR_READY"


def build_artifact(snap: dict) -> dict:
    cls = determine_classification(snap)
    return {
        "classification": cls,
        "final_classification": cls,
        "task": "P107B",
        "date": datetime.now(timezone.utc).strftime("%Y%m%d"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repair_scope": "active_tests_only",
        "historical_artifacts_rewritten": False,
        "db_writes": False,
        "replay_rows_before": EXPECTED_REPLAY_ROWS,
        "replay_rows_after": snap["replay_rows"],
        "accepted_current_baseline": ACCEPTED_BASELINE,
        "stale_baselines_repaired": STALE_BASELINE,
        "repaired_tests": REPAIRED_TESTS,
        "current_db_snapshot": snap,
        "governance_confirmations": {
            "four_star_backtest_authorized": False,
            "special3_promotion_authorized": False,
            "lifecycle_mutation": False,
            "source_unknown_caveat_preserved": True,
            "p108_100draw_rerun_performed": False,
            "historical_artifacts_rewritten": False,
        },
        "references": {
            "p105": "Accepted current DB for Special3 evaluation only (Option A)",
            "p106": "Partial prospective evaluation — 5/6 P100 criteria, sum_band_frequency best",
            "p107a": "Wait more draws monitoring gate — 63/100, 37 more needed",
            "p107a_merge_commit": "782e261",
            "p107a_pr": 236,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="P107B: Stale Baseline Guard Repair")
    parser.add_argument("--json-out", help="Path to write JSON artifact")
    parser.add_argument("--db", default=str(DB_PATH), help="Path to DB")
    args = parser.parse_args()

    db_path = Path(args.db)

    snap = read_db_snapshot(db_path)
    artifact = build_artifact(snap)

    print("=" * 60)
    print("P107B: Stale Baseline Guard Repair")
    print("=" * 60)
    print(f"  classification              : {artifact['classification']}")
    print(f"  repair_scope                : {artifact['repair_scope']}")
    print(f"  historical_artifacts_rewritten : {artifact['historical_artifacts_rewritten']}")
    print(f"  db_writes                   : {artifact['db_writes']}")
    print(f"  replay_rows (before/after)  : {artifact['replay_rows_before']} / {snap['replay_rows']}")
    print(f"  3_STAR count / max          : {snap['three_star_count']} / {snap['three_star_max_draw']}")
    print(f"  4_STAR count / max          : {snap['four_star_count']} / {snap['four_star_max_draw']}")
    print(f"  4_STAR backtest authorized  : {artifact['governance_confirmations']['four_star_backtest_authorized']}")
    print(f"  special3 promotion auth     : {artifact['governance_confirmations']['special3_promotion_authorized']}")
    print(f"  tests repaired              : {len(artifact['repaired_tests'])}")
    for t in artifact["repaired_tests"]:
        print(f"    - {t['test']} in {t['file']}")
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
