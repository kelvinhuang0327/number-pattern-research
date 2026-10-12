#!/usr/bin/env python3
"""
P55 Wave 5 POWER_LOTTO Candidate Planning — Read-only analysis script

Verifies:
  1. DB production rows unchanged (42460)
  2. POWER_LOTTO rows unchanged (9140)
  3. Wave 5 candidate tool files exist
  4. P0 strategy universe accessible
  5. Drift guard available
  6. Wave 5 shortlist strategy IDs are valid identifiers

This script NEVER writes to the DB. It is a read-only analysis and verification
tool for the P55 planning artifacts.

Usage:
    .venv/bin/python scripts/p55_powerlotto_wave5_candidate_planning.py
"""
import sys
import os
import json
import sqlite3

from pathlib import Path


def _p291u_repo_root():
    current = Path(__file__)
    if not current.is_absolute():
        raise FileNotFoundError(f"Source file path is not absolute: {current}")
    for parent in (current.parent, *current.parents):
        if (parent / "lottery_api").is_dir():
            return parent
    raise FileNotFoundError(f"Unable to locate repository root from source file: {current}")


def _p291u_default_db_path():
    db_path = _p291u_repo_root() / "lottery_api" / "data" / "lottery_v2.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Default lottery DB path is missing or non-regular: {db_path}")
    return db_path


def _p291u_resolve_db_path(db_path=None):
    if db_path is None:
        return _p291u_default_db_path()
    path = Path(db_path)
    if not path.is_absolute():
        raise ValueError(f"Explicit DB path must be absolute: {db_path}")
    if not path.is_file():
        raise FileNotFoundError(f"Explicit DB path is missing or non-regular: {path}")
    return path


def _p291u_connect_resolved(db_path, *, uri=False):
    if uri:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return sqlite3.connect(str(db_path))


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

DB_PATH = os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db")

EXPECTED_TOTAL_ROWS = 42460
EXPECTED_PL_ROWS = 9140
EXPECTED_LOTTERY_TYPE = "POWER_LOTTO"

WAVE5_SHORTLIST = [
    "cold_complement_2bet",
    "fourier30_markov30_2bet",
    "zonal_entropy_2bet",
]

WAVE4_STRATEGY_IDS = {
    "midfreq_fourier_mk_3bet",
    "midfreq_fourier_2bet",
    "pp3_freqort_4bet",
}

TOOL_FILES = [
    os.path.join(PROJECT_ROOT, "tools", "power_twin_strike.py"),
    os.path.join(PROJECT_ROOT, "tools", "power_fourier_rhythm.py"),
    os.path.join(PROJECT_ROOT, "tools", "power_scientific_zonal.py"),
]

P0_INVENTORY = os.path.join(
    PROJECT_ROOT, "outputs", "replay", "p0_strategy_universe_inventory_20260517.json"
)

P55_MD = os.path.join(
    PROJECT_ROOT, "docs", "replay", "p55_powerlotto_wave5_candidate_planning_20260525.md"
)

P55_JSON = os.path.join(
    PROJECT_ROOT, "outputs", "replay", "p55_powerlotto_wave5_candidate_planning_20260525.json"
)


def check_production_rows() -> dict:
    """Read-only DB check — count total and POWER_LOTTO rows."""
    _p291u_db_path = _p291u_resolve_db_path()
    conn = _p291u_connect_resolved(_p291u_db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type=?",
            (EXPECTED_LOTTERY_TYPE,),
        )
        pl_total = cur.fetchone()[0]
    finally:
        conn.close()
    return {"total": total, "powerlotto": pl_total}


def main() -> int:
    failures = []
    print("=" * 60)
    print("P55 Wave 5 POWER_LOTTO Candidate Planning — Read-Only Verification")
    print("=" * 60)

    # 1. DB row counts
    try:
        counts = check_production_rows()
        if counts["total"] != EXPECTED_TOTAL_ROWS:
            failures.append(
                f"DB total rows: expected {EXPECTED_TOTAL_ROWS}, got {counts['total']}"
            )
        else:
            print(f"[PASS] Total rows: {counts['total']}")
        if counts["powerlotto"] != EXPECTED_PL_ROWS:
            failures.append(
                f"POWER_LOTTO rows: expected {EXPECTED_PL_ROWS}, got {counts['powerlotto']}"
            )
        else:
            print(f"[PASS] POWER_LOTTO rows: {counts['powerlotto']}")
    except Exception as e:
        failures.append(f"DB check failed: {e}")

    # 2. Wave 5 shortlist IDs are valid Python identifiers
    for sid in WAVE5_SHORTLIST:
        if not sid.replace("_", "").isalnum():
            failures.append(f"Invalid strategy_id format: {sid}")
        else:
            print(f"[PASS] Wave 5 candidate ID valid: {sid}")

    # 3. Wave 5 candidates do NOT overlap with Wave 4
    overlap = set(WAVE5_SHORTLIST) & WAVE4_STRATEGY_IDS
    if overlap:
        failures.append(f"Wave 5 candidates overlap with Wave 4: {overlap}")
    else:
        print("[PASS] No overlap between Wave 5 shortlist and Wave 4 strategies")

    # 4. Wave 5 candidates do NOT overlap with pre-wave champion / row-backed
    pre_wave4_covered = {
        "fourier_rhythm_3bet",
        "power_orthogonal_5bet",
        "power_precision_3bet",
    }
    overlap_pre = set(WAVE5_SHORTLIST) & pre_wave4_covered
    if overlap_pre:
        failures.append(f"Wave 5 candidates overlap with pre-Wave4 row-backed strategies: {overlap_pre}")
    else:
        print("[PASS] No overlap between Wave 5 shortlist and pre-Wave4 strategies")

    # 5. P0 inventory accessible
    if not os.path.exists(P0_INVENTORY):
        failures.append(f"P0 inventory not found: {P0_INVENTORY}")
    else:
        try:
            with open(P0_INVENTORY) as f:
                p0 = json.load(f)
            n_strategies = len(p0.get("strategies", []))
            print(f"[PASS] P0 inventory accessible: {n_strategies} strategies")
        except Exception as e:
            failures.append(f"P0 inventory load failed: {e}")

    # 6. Tool files exist for Wave 5 source strategies
    for tf in TOOL_FILES:
        if not os.path.exists(tf):
            failures.append(f"Wave 5 source tool not found: {tf}")
        else:
            print(f"[PASS] Tool exists: {os.path.basename(tf)}")

    # 7. P55 MD artifact exists
    if not os.path.exists(P55_MD):
        failures.append(f"P55 MD artifact missing: {P55_MD}")
    else:
        print(f"[PASS] P55 MD artifact exists")

    # 8. P55 JSON artifact exists and is valid
    if not os.path.exists(P55_JSON):
        failures.append(f"P55 JSON artifact missing: {P55_JSON}")
    else:
        try:
            with open(P55_JSON) as f:
                p55 = json.load(f)
            assert p55["task"] == "P55", "task != P55"
            assert p55["no_db_write"] is True, "no_db_write must be true"
            assert p55["production_rows"] == EXPECTED_TOTAL_ROWS, (
                f"production_rows mismatch: {p55['production_rows']}"
            )
            assert p55["powerlotto_rows_before"] == EXPECTED_PL_ROWS, (
                f"powerlotto_rows_before mismatch"
            )
            shortlist_ids = [s["strategy_id"] for s in p55["wave5_shortlist"]]
            assert set(shortlist_ids) == set(WAVE5_SHORTLIST), (
                f"Shortlist mismatch: {shortlist_ids} vs {WAVE5_SHORTLIST}"
            )
            print(f"[PASS] P55 JSON artifact valid: task={p55['task']}, "
                  f"rows={p55['production_rows']}, shortlist={shortlist_ids}")
        except Exception as e:
            failures.append(f"P55 JSON validation failed: {e}")

    # 9. No adapter file created (P56 only)
    p56_adapter = os.path.join(
        PROJECT_ROOT, "lottery_api", "models", "p56_wave5_powerlotto_adapters.py"
    )
    if os.path.exists(p56_adapter):
        failures.append(
            f"P56 adapter file found in P55 scope — must not exist until P56: {p56_adapter}"
        )
    else:
        print("[PASS] P56 adapter file does not exist (correct — planning only)")

    # 10. power_twin_strike tool has cold-number logic
    twin_strike_path = os.path.join(PROJECT_ROOT, "tools", "power_twin_strike.py")
    if os.path.exists(twin_strike_path):
        with open(twin_strike_path) as f:
            content = f.read()
        if "cold" in content.lower() and "counter" in content.lower():
            print("[PASS] power_twin_strike.py contains cold-number Counter logic")
        else:
            failures.append("power_twin_strike.py missing expected cold/Counter logic")

    print("=" * 60)
    if failures:
        print(f"RESULT: FAIL — {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    else:
        print("RESULT: ALL CHECKS PASSED")
        print("P55 read-only verification complete. No DB writes performed.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
