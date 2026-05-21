"""
replay_lifecycle_drift_guard.py
================================
Read-only Post-V3 replay lifecycle drift guard.

Validates that the strategy_prediction_replays table has not drifted from
the main-repo P0 baseline established on 2026-05-19 (single-repo stabilization):
  V1  (controlled_apply_id='20260514033100-13acaf34996e') ==    0
  V2  (controlled_apply_id='20260514134953-cf683424')     ==    0
  legacy (controlled_apply_id IS NULL)                    ==  460
  P2B (controlled_apply_id='P2B_20260515')                ==    0
  P2F (controlled_apply_id='P2F_20260515')                ==    0
  P3BC (controlled_apply_id='P3BC_RESOLVE_20260516')      ==    0
  P14D (controlled_apply_id='P14D_BIGLOTTO_TS3_1500_PROD_20260520') == 1500
  P16  (controlled_apply_id='P16_BIGLOTTO_REMAINING_1500_PROD_20260520') == 3000
  total                                                   == 4960

NOTE: The LotteryNew-clean sibling repo had 975 rows (V1+V2+legacy+P2B+P2F+P3BC).
The main repo only has 460 legacy rows. V1/V2/P2B/P2F/P3BC rows are NOT
present — this is expected for P0 single-repo stabilization. Historical
reconstruction (P5-P7) will add rows with controlled_apply_id later.

Also checks:
  - Known V3 CODE_MISSING strategy IDs have 0 rows
  - truth_level values are only from the allowed enum
  - controlled_apply_id distribution matches the baseline

STRICT RULES:
  - NO DB writes
  - NO API calls
  - NO external services
  - NO imports of lottery_api modules (registry read as raw text only)

Usage:
  python3 scripts/replay_lifecycle_drift_guard.py --strict
  python3 scripts/replay_lifecycle_drift_guard.py --strict --json-out outputs/replay/drift_guard_YYYYMMDD.json
"""

import argparse
import datetime
import json
import pathlib
import sqlite3
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

# Baseline for main-repo established on 2026-05-19 (P0 single-repo stabilization).
# Main repo was never the target of V1/V2/P2B/P2F/P3BC apply runs (those happened
# in LotteryNew-clean only). All 460 rows are legacy (controlled_apply_id IS NULL).
# P5-P7 historical reconstruction will add rows with controlled_apply_id values.
BASELINE = {
    "v1_apply_id": "20260514033100-13acaf34996e",
    "v2_apply_id": "20260514134953-cf683424",
    "p2b_apply_id": "P2B_20260515",
    "p2f_apply_id": "P2F_20260515",
    "p3bc_apply_id": "P3BC_RESOLVE_20260516",
    # P14D: Big Lotto ts3_regime_3bet 1500-draw production apply (2026-05-20)
    "p14d_apply_id": "P14D_BIGLOTTO_TS3_1500_PROD_20260520",
    # P16: Big Lotto remaining strategies (biglotto_triple_strike + biglotto_deviation_2bet)
    # 1500 draws each = 3000 rows, with prediction_cutoff_date + prediction_generated_at (2026-05-20)
    "p16_apply_id": "P16_BIGLOTTO_REMAINING_1500_PROD_20260520",
    # P19B: Power Lotto fourier_rhythm_3bet 1500-draw production apply (2026-05-20)
    "p19b_apply_id": "P19B_POWERLOTTO_FOURIER_1500_PROD_20260520",
    # P20: Power Lotto remaining strategies (power_precision_3bet + power_orthogonal_5bet)
    # 1500 draws each = 3000 rows (2026-05-20)
    "p20_apply_id": "P20_POWERLOTTO_REMAINING_1500_PROD_20260520",
    "v1_count": 0,
    "v2_count": 0,
    "legacy_count": 460,
    "p2b_count": 0,
    "p2f_count": 0,
    "p3bc_count": 0,
    "p14d_count": 1500,
    "p16_count": 3000,
    "p19b_count": 1500,
    "p20_count": 3000,
    "total_count": 9460,
}

# Known V3 tombstone strategy IDs — must have 0 rows in replay table
# acb_markov_midfreq_3bet removed from tombstone list: 3 rows inserted via P3BC_RESOLVE_20260516
V3_CODE_MISSING_STRATEGY_IDS = [
    "acb_1bet",
    "acb_markov_midfreq",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
    "h6_gate_mk20_ew85",
]

# Allowed truth_level enum values (NULL is also allowed)
ALLOWED_TRUTH_LEVELS = {
    "REGENERATED_RETROSPECTIVE",
    "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE",
    "OFFICIAL",
    "OFFICIAL_DRAW_RESULT",
    # P14D Big Lotto production backfill (2026-05-20)
    "BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED",
    # P16 Big Lotto remaining strategies backfill (2026-05-20)
    "BIGLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED",
    # P19B Power Lotto fourier_rhythm_3bet production backfill (2026-05-20)
    "POWERLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED",
    # P20 Power Lotto remaining strategies production backfill (2026-05-20)
    "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED",
}


# ---------------------------------------------------------------------------
# Validation logic
# ---------------------------------------------------------------------------

def run_checks(db_path: pathlib.Path) -> dict:
    """Run all drift checks. Returns a result dict. Never writes to DB."""
    violations = []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # ------------------------------------------------------------------
    # 1. Row count baseline
    # ------------------------------------------------------------------
    v1_count = c.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
        (BASELINE["v1_apply_id"],),
    ).fetchone()[0]

    v2_count = c.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
        (BASELINE["v2_apply_id"],),
    ).fetchone()[0]

    p2b_count = c.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
        (BASELINE["p2b_apply_id"],),
    ).fetchone()[0]

    p2f_count = c.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
        (BASELINE["p2f_apply_id"],),
    ).fetchone()[0]

    p3bc_count = c.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
        (BASELINE["p3bc_apply_id"],),
    ).fetchone()[0]

    p14d_count = c.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
        (BASELINE["p14d_apply_id"],),
    ).fetchone()[0]

    p16_count = c.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
        (BASELINE["p16_apply_id"],),
    ).fetchone()[0]

    p19b_count = c.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
        (BASELINE["p19b_apply_id"],),
    ).fetchone()[0]

    p20_count = c.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
        (BASELINE["p20_apply_id"],),
    ).fetchone()[0]

    legacy_count = c.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id IS NULL"
    ).fetchone()[0]

    total_count = c.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]

    if v1_count != BASELINE["v1_count"]:
        violations.append(
            f"V1 row count mismatch: expected {BASELINE['v1_count']}, got {v1_count}"
        )
    if v2_count != BASELINE["v2_count"]:
        violations.append(
            f"V2 row count mismatch: expected {BASELINE['v2_count']}, got {v2_count}"
        )
    if legacy_count != BASELINE["legacy_count"]:
        violations.append(
            f"legacy row count mismatch: expected {BASELINE['legacy_count']}, got {legacy_count}"
        )
    if p2b_count != BASELINE["p2b_count"]:
        violations.append(
            f"P2B row count mismatch: expected {BASELINE['p2b_count']}, got {p2b_count}"
        )
    if p2f_count != BASELINE["p2f_count"]:
        violations.append(
            f"P2F row count mismatch: expected {BASELINE['p2f_count']}, got {p2f_count}"
        )
    if p3bc_count != BASELINE["p3bc_count"]:
        violations.append(
            f"P3BC row count mismatch: expected {BASELINE['p3bc_count']}, got {p3bc_count}"
        )
    if p14d_count != BASELINE["p14d_count"]:
        violations.append(
            f"P14D row count mismatch: expected {BASELINE['p14d_count']}, got {p14d_count}"
        )
    if p16_count != BASELINE["p16_count"]:
        violations.append(
            f"P16 row count mismatch: expected {BASELINE['p16_count']}, got {p16_count}"
        )
    if p19b_count != BASELINE["p19b_count"]:
        violations.append(
            f"P19B row count mismatch: expected {BASELINE['p19b_count']}, got {p19b_count}"
        )
    if p20_count != BASELINE["p20_count"]:
        violations.append(
            f"P20 row count mismatch: expected {BASELINE['p20_count']}, got {p20_count}"
        )
    if total_count != BASELINE["total_count"]:
        violations.append(
            f"total row count mismatch: expected {BASELINE['total_count']}, got {total_count}"
        )

    row_counts = {
        "v1": v1_count,
        "v2": v2_count,
        "legacy": legacy_count,
        "p2b": p2b_count,
        "p2f": p2f_count,
        "p3bc": p3bc_count,
        "p14d": p14d_count,
        "p16": p16_count,
        "p19b": p19b_count,
        "p20": p20_count,
        "total": total_count,
    }

    # ------------------------------------------------------------------
    # 2. V3 fake row check — each tombstone strategy must have 0 rows
    # ------------------------------------------------------------------
    v3_fake_row_violations = []
    for sid in V3_CODE_MISSING_STRATEGY_IDS:
        count = c.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
            (sid,),
        ).fetchone()[0]
        if count != 0:
            v3_fake_row_violations.append({"strategy_id": sid, "row_count": count})
            violations.append(
                f"V3 tombstone strategy '{sid}' has {count} unexpected rows"
            )

    lifecycle_counts = {
        "v3_code_missing_zero_row_strategies": len(V3_CODE_MISSING_STRATEGY_IDS) - len(v3_fake_row_violations),
        "v3_fake_row_violations": v3_fake_row_violations,
    }

    # ------------------------------------------------------------------
    # 3. truth_level enum check
    # ------------------------------------------------------------------
    truth_level_rows = c.execute(
        "SELECT truth_level, COUNT(*) as cnt FROM strategy_prediction_replays GROUP BY truth_level"
    ).fetchall()

    truth_level_counts = {}
    for row in truth_level_rows:
        tl = row["truth_level"]
        cnt = row["cnt"]
        key = tl if tl is not None else "null"
        truth_level_counts[key] = cnt
        if tl is not None and tl not in ALLOWED_TRUTH_LEVELS:
            violations.append(
                f"Unexpected truth_level value '{tl}' found ({cnt} rows)"
            )

    # Ensure expected keys are present even if count is zero
    for expected_key in ("REGENERATED_RETROSPECTIVE", "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE", "OFFICIAL", "null"):
        if expected_key not in truth_level_counts:
            truth_level_counts[expected_key] = 0

    # ------------------------------------------------------------------
    # 4. controlled_apply_id distribution
    # ------------------------------------------------------------------
    apply_id_rows = c.execute(
        "SELECT controlled_apply_id, COUNT(*) as cnt FROM strategy_prediction_replays GROUP BY controlled_apply_id"
    ).fetchall()

    controlled_apply_id_counts = {}
    for row in apply_id_rows:
        aid = row["controlled_apply_id"]
        key = aid if aid is not None else "null"
        controlled_apply_id_counts[key] = row["cnt"]

    # Check expected apply IDs are present with correct counts
    for aid, expected in [
        (BASELINE["v1_apply_id"], BASELINE["v1_count"]),
        (BASELINE["v2_apply_id"], BASELINE["v2_count"]),
    ]:
        actual = controlled_apply_id_counts.get(aid, 0)
        if actual != expected:
            # Already caught in row_counts section, no double-record
            pass

    # Unexpected apply IDs (not V1, V2, P2B, P2F, P3BC, P14D, P16, P19B, P20, or NULL) are violations
    known_apply_ids = {
        BASELINE["v1_apply_id"], BASELINE["v2_apply_id"],
        BASELINE["p2b_apply_id"], BASELINE["p2f_apply_id"],
        BASELINE["p3bc_apply_id"], BASELINE["p14d_apply_id"],
        BASELINE["p16_apply_id"], BASELINE["p19b_apply_id"],
        BASELINE["p20_apply_id"],
        "null", None,
    }
    for aid_key, cnt in controlled_apply_id_counts.items():
        if aid_key not in known_apply_ids and aid_key is not None:
            violations.append(
                f"Unexpected controlled_apply_id '{aid_key}' found ({cnt} rows)"
            )

    conn.close()

    # ------------------------------------------------------------------
    # Build result
    # ------------------------------------------------------------------
    status = "PASS" if not violations else "FAIL"
    final_classification = (
        "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS"
        if status == "PASS"
        else "REPLAY_LIFECYCLE_DRIFT_GUARD_FAIL"
    )

    return {
        "status": status,
        "checked_at": datetime.datetime.utcnow().isoformat() + "Z",
        "db_path": str(db_path.resolve()),
        "row_counts": row_counts,
        "lifecycle_counts": lifecycle_counts,
        "truth_level_counts": truth_level_counts,
        "controlled_apply_id_counts": controlled_apply_id_counts,
        "violations": violations,
        "final_classification": final_classification,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Post-V3 replay lifecycle drift guard."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if any violation is found.",
    )
    parser.add_argument(
        "--json-out",
        metavar="PATH",
        help="Write JSON result to this path.",
    )
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        return 1

    result = run_checks(DB_PATH)

    # Print summary to stdout
    print(f"Drift guard checked at: {result['checked_at']}")
    print(f"DB: {result['db_path']}")
    print()
    rc = result["row_counts"]
    print(f"Row counts — V1={rc['v1']}  V2={rc['v2']}  legacy={rc['legacy']}  total={rc['total']}")

    lc = result["lifecycle_counts"]
    print(f"V3 tombstone strategies with 0 rows: {lc['v3_code_missing_zero_row_strategies']}/{len(V3_CODE_MISSING_STRATEGY_IDS)}")
    if lc["v3_fake_row_violations"]:
        print(f"  VIOLATIONS: {lc['v3_fake_row_violations']}")

    tlc = result["truth_level_counts"]
    print(f"truth_level — REGENERATED={tlc.get('REGENERATED_RETROSPECTIVE', 0)}  "
          f"ARTIFACT={tlc.get('ARTIFACT_RECONSTRUCTED_RETROSPECTIVE', 0)}  "
          f"null={tlc.get('null', 0)}")

    print()
    if result["violations"]:
        print(f"VIOLATIONS ({len(result['violations'])}):")
        for v in result["violations"]:
            print(f"  - {v}")
    else:
        print("No violations found.")

    print()
    print(f"Final classification: {result['final_classification']}")
    print(f"Status: {result['status']}")

    # Write JSON output if requested
    if args.json_out:
        out_path = pathlib.Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"JSON written to: {out_path}")

    if args.strict and result["status"] == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
