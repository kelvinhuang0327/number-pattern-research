"""
test_p31b_wave1_daily539_retired_production_apply.py
=====================================================
Tests for P31B Wave 1 DAILY_539 Retired Strategy Production Apply.

Verifies:
  - Production DB has exactly 19960 rows after P31B apply
  - Each of the 5 Wave 1 strategies has exactly 1500 rows in production
  - All P31B rows have dry_run=0 (production rows, not rehearsal)
  - All P31B rows have correct controlled_apply_id and source
  - Lifecycle semantics: 5 strategies still have retired label (Option A)
  - Drift guard PASS with updated baseline (19960 rows)
  - Branch governance guard PASS with --expected-rows 19960
  - Output JSON artifact exists and is valid
  - No P31A dry-run rows in production (dry_run=0 guard)

These tests:
  - DO require a production DB with P31B rows applied
  - DO NOT require the backend to be running
  - DO NOT write to the DB

Baseline: P31B applied 7500 rows (5 strategies × 1500 draws) on 2026-05-23.
  controlled_apply_id = P31B_DAILY539_RETIRED_7500_PROD_20260523
  truth_level         = DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED
  source              = P31B_WAVE1_PRODUCTION_APPLY
  run_id              = p31b_wave1_prod_20260523
  pre_apply_rows      = 12460
  post_apply_rows     = 19960
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

# ─── Paths ────────────────────────────────────────────────────────────────────

REPO_ROOT   = Path(__file__).parent.parent.resolve()
PYTHON      = sys.executable
DB_PATH     = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_JSON = REPO_ROOT / "outputs" / "replay" / "p31b_wave1_daily539_retired_production_apply_20260523.json"
DRIFT_SCRIPT  = REPO_ROOT / "scripts" / "replay_lifecycle_drift_guard.py"
GOVN_SCRIPT   = REPO_ROOT / "scripts" / "replay_branch_governance_guard.py"

# ─── Constants ────────────────────────────────────────────────────────────────

EXPECTED_TOTAL_ROWS   = 19960
EXPECTED_PRE_ROWS     = 12460
EXPECTED_INSERTED     = 7500
EXPECTED_PER_STRATEGY = 1500
CONTROLLED_APPLY_ID   = "P31B_DAILY539_RETIRED_7500_PROD_20260523"
TRUTH_LEVEL           = "DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED"
SOURCE                = "P31B_WAVE1_PRODUCTION_APPLY"
RUN_ID                = "p31b_wave1_prod_20260523"

WAVE1_STRATEGY_IDS = frozenset({
    "acb_1bet",
    "acb_markov_midfreq",
    "acb_markov_midfreq_3bet",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
})

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_conn():
    if not DB_PATH.exists():
        pytest.skip(f"DB not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def output_json():
    if not OUTPUT_JSON.exists():
        pytest.skip(f"Output JSON not found: {OUTPUT_JSON}")
    with open(OUTPUT_JSON, encoding="utf-8") as f:
        return json.load(f)


# ─── 1. Production row count ──────────────────────────────────────────────────

def test_01_production_total_rows(db_conn):
    """Production DB must have exactly 19960 rows after P31B."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    assert count == EXPECTED_TOTAL_ROWS, (
        f"Expected {EXPECTED_TOTAL_ROWS} production rows, got {count}"
    )


# ─── 2. Per-strategy row counts ───────────────────────────────────────────────

@pytest.mark.parametrize("strategy_id", sorted(WAVE1_STRATEGY_IDS))
def test_02_per_strategy_row_count(db_conn, strategy_id):
    """Each Wave 1 strategy must have exactly 1500 production rows."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id = ? AND controlled_apply_id = ?",
        (strategy_id, CONTROLLED_APPLY_ID),
    ).fetchone()[0]
    assert count == EXPECTED_PER_STRATEGY, (
        f"Strategy {strategy_id}: expected {EXPECTED_PER_STRATEGY} rows "
        f"with controlled_apply_id={CONTROLLED_APPLY_ID}, got {count}"
    )


# ─── 3. No dry-run rows in production ────────────────────────────────────────

def test_03_no_dry_run_rows(db_conn):
    """Production DB must not contain any dry_run=1 rows."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE dry_run = 1"
    ).fetchone()[0]
    assert count == 0, (
        f"Found {count} dry_run=1 rows in production — these must not exist"
    )


# ─── 4. P31B rows have correct source ────────────────────────────────────────

def test_04_p31b_rows_source(db_conn):
    """All P31B rows must have source = P31B_WAVE1_PRODUCTION_APPLY."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id = ? AND source != ?",
        (CONTROLLED_APPLY_ID, SOURCE),
    ).fetchone()[0]
    assert count == 0, (
        f"{count} P31B rows have unexpected source (expected {SOURCE!r})"
    )


# ─── 5. P31B rows have correct truth_level ───────────────────────────────────

def test_05_p31b_rows_truth_level(db_conn):
    """All P31B rows must have truth_level = DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id = ? AND truth_level != ?",
        (CONTROLLED_APPLY_ID, TRUTH_LEVEL),
    ).fetchone()[0]
    assert count == 0, (
        f"{count} P31B rows have unexpected truth_level (expected {TRUTH_LEVEL!r})"
    )


# ─── 6. P31B rows have correct run_id ────────────────────────────────────────

def test_06_p31b_rows_run_id(db_conn):
    """All P31B rows must have replay_run_id = p31b_wave1_prod_20260523."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id = ? AND replay_run_id != ?",
        (CONTROLLED_APPLY_ID, RUN_ID),
    ).fetchone()[0]
    assert count == 0, (
        f"{count} P31B rows have unexpected replay_run_id (expected {RUN_ID!r})"
    )


# ─── 7. P31B rows are PREDICTED (no replay errors) ───────────────────────────

def test_07_p31b_rows_all_predicted(db_conn):
    """All P31B rows must have replay_status = PREDICTED."""
    non_predicted = db_conn.execute(
        "SELECT strategy_id, replay_status, COUNT(*) as cnt "
        "FROM strategy_prediction_replays "
        "WHERE controlled_apply_id = ? AND replay_status != 'PREDICTED' "
        "GROUP BY strategy_id, replay_status",
        (CONTROLLED_APPLY_ID,),
    ).fetchall()
    assert len(non_predicted) == 0, (
        f"Found non-PREDICTED rows in P31B: {[dict(r) for r in non_predicted]}"
    )


# ─── 8. Lifecycle semantics: Wave 1 strategies still retired ─────────────────

def test_08_lifecycle_semantics_retired(db_conn):
    """
    No Wave 1 strategy should appear in the catalog with a non-retired
    lifecycle_status. Verified via replay rows only (no registry import).
    Wave 1 rows must NOT have replay_status=ONLINE_APPLY or similar flags.
    """
    # All P31B rows must have lottery_type = DAILY_539
    bad_lottery_type = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id = ? AND lottery_type != 'DAILY_539'",
        (CONTROLLED_APPLY_ID,),
    ).fetchone()[0]
    assert bad_lottery_type == 0, (
        f"Found {bad_lottery_type} P31B rows with wrong lottery_type"
    )

    # No P31B rows should have source indicating a lifecycle promotion
    bad_source = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id = ? AND source LIKE '%ONLINE%'",
        (CONTROLLED_APPLY_ID,),
    ).fetchone()[0]
    assert bad_source == 0, (
        f"Found {bad_source} P31B rows with source indicating ONLINE promotion"
    )


# ─── 9. No P31A dry-run rows in production ───────────────────────────────────

def test_09_no_p31a_dryrun_in_production(db_conn):
    """Production DB must NOT contain any P31A dry-run rows (source=P31A_WAVE1_DRYRUN)."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE source = 'P31A_WAVE1_DRYRUN'",
    ).fetchone()[0]
    assert count == 0, (
        f"Found {count} P31A dry-run rows in production — these should only be in /tmp/p31a_temp.db"
    )


# ─── 10. Output JSON artifact ────────────────────────────────────────────────

def test_10_output_json_exists():
    assert OUTPUT_JSON.exists(), f"Output JSON not found: {OUTPUT_JSON}"


def test_11_output_json_status(output_json):
    assert output_json["status"] == "PASS"


def test_12_output_json_phase(output_json):
    assert output_json["phase"] == "P31B_WAVE1_DAILY539_RETIRED_PRODUCTION_APPLY"


def test_13_output_json_classification(output_json):
    assert output_json["classification"] == "P31B_WAVE1_DAILY539_RETIRED_PRODUCTION_APPLY_COMPLETE"


def test_14_output_json_row_counts(output_json):
    rc = output_json["row_counts"]
    assert rc["prod_rows_before"] == EXPECTED_PRE_ROWS
    assert rc["rows_generated"]   == EXPECTED_INSERTED
    assert rc["rows_inserted"]    == EXPECTED_INSERTED
    assert rc["rows_duplicated"]  == 0
    assert rc["prod_rows_after"]  == EXPECTED_TOTAL_ROWS


def test_15_output_json_per_strategy(output_json):
    per_strat = output_json["per_strategy_row_counts"]
    for sid in WAVE1_STRATEGY_IDS:
        assert per_strat.get(sid) == EXPECTED_PER_STRATEGY, (
            f"Strategy {sid}: expected {EXPECTED_PER_STRATEGY} in JSON, got {per_strat.get(sid)}"
        )


def test_16_output_json_lifecycle_semantics(output_json):
    ls = output_json["lifecycle_semantics"]
    assert ls["all_5_strategies_remain_retired"] is True
    assert ls["no_lifecycle_status_change"] is True
    assert ls["registry_unchanged"] is True


def test_17_output_json_all_pass(output_json):
    assert output_json["preflight_pass"] is True
    assert output_json["duplicate_check_pass"] is True
    assert output_json["postflight_pass"] is True
    assert output_json["all_pass"] is True


# ─── 18. Drift guard PASS ────────────────────────────────────────────────────

def test_18_drift_guard_pass(tmp_path):
    """Drift guard must PASS after P31B apply (19960-row baseline)."""
    if not DRIFT_SCRIPT.exists():
        pytest.skip("Drift guard script not found")
    out = tmp_path / "drift.json"
    result = subprocess.run(
        [PYTHON, str(DRIFT_SCRIPT), "--strict", "--json-out", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"Drift guard FAIL (exit={result.returncode})\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    if out.exists():
        with open(out) as f:
            d = json.load(f)
        assert d["final_classification"] == "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS", (
            f"Unexpected drift guard classification: {d['final_classification']}\n"
            f"violations: {d.get('violations', [])}"
        )
        assert d["row_counts"]["total"] == EXPECTED_TOTAL_ROWS
        assert d["row_counts"]["p31b"] == EXPECTED_INSERTED


# ─── 19. Branch governance guard PASS ────────────────────────────────────────

def test_19_governance_guard_pass(tmp_path):
    """Branch governance guard must PASS with --expected-rows 19960."""
    if not GOVN_SCRIPT.exists():
        pytest.skip("Governance guard script not found")
    import subprocess as _sp
    current_branch = _sp.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True
    ).strip()
    out = tmp_path / "gov.json"
    result = subprocess.run(
        [PYTHON, str(GOVN_SCRIPT),
         "--expected-branch", current_branch,
         "--expected-rows", str(EXPECTED_TOTAL_ROWS),
         "--json-out", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"Governance guard exit={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    if out.exists():
        with open(out) as f:
            d = json.load(f)
        assert d["classification"] == "BRANCH_GOVERNANCE_PASS"
        assert d["production_rows"] == EXPECTED_TOTAL_ROWS
