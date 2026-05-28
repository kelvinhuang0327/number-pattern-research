"""
tests/test_p126f_apply_daily539_f4cold_5bet.py
==============================================
Regression tests for P126F: daily539_f4cold_5bet controlled replay rows.

Validates:
  - Artifact JSON exists with correct classification and field values
  - DB state: 72462 rows, strategy rows = 7500, bet distribution 1500×5
  - P126B/P126C/P126D/P126E rows preserved
  - Drift guard passes at 72462
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT   = Path(__file__).resolve().parent.parent
ARTIFACT    = REPO_ROOT / "outputs/replay/p126f_apply_daily539_f4cold_5bet_20260528.json"
MD_PATH     = REPO_ROOT / "docs/replay/p126f_apply_daily539_f4cold_5bet_20260528.md"
DB_PATH     = REPO_ROOT / "lottery_api/data/lottery_v2.db"
DRIFT_GUARD = REPO_ROOT / "scripts/replay_lifecycle_drift_guard.py"
PYTHON      = sys.executable

STRATEGY_ID         = "daily539_f4cold_5bet"
LOTTERY_TYPE        = "DAILY_539"
CONTROLLED_APPLY_ID = "P126F_DAILY539_F4COLD_5BET_20260528"

EXPECTED_ROWS_BEFORE    = 66462
EXPECTED_ROWS_AFTER     = 72462
EXPECTED_INSERT_ROWS    = 6000
EXPECTED_STRATEGY_TOTAL = 7500


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT.exists(), f"P126F JSON not found: {ARTIFACT}"
    with ARTIFACT.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def db_conn():
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# 1. Artifact existence and top-level fields
# ---------------------------------------------------------------------------
def test_artifact_exists():
    assert ARTIFACT.exists(), "P126F JSON artifact must exist"


def test_markdown_exists():
    assert MD_PATH.exists(), "P126F Markdown report must exist"


def test_task_id(artifact):
    assert artifact["task_id"] == "P126F"


def test_classification(artifact):
    assert artifact["classification"] == "P126F_DAILY539_F4COLD_5BET_APPLIED"


# ---------------------------------------------------------------------------
# 2. Authorization
# ---------------------------------------------------------------------------
def test_authorization_present(artifact):
    auth = artifact["authorization"]
    assert auth["authorization_present"] is True


def test_authorization_apply_allowed(artifact):
    assert artifact["authorization"]["apply_allowed"] is True


def test_authorization_strategy_id(artifact):
    assert artifact["authorization"]["strategy_id"] == STRATEGY_ID


# ---------------------------------------------------------------------------
# 3. DB snapshot — before
# ---------------------------------------------------------------------------
def test_db_snapshot_before_rows(artifact):
    assert artifact["db_snapshot_before"]["replay_rows"] == EXPECTED_ROWS_BEFORE, (
        f"Expected {EXPECTED_ROWS_BEFORE} rows before apply"
    )


def test_db_snapshot_before_strategy_rows(artifact):
    assert artifact["db_snapshot_before"]["strategy_rows"] == 1500, (
        "Before apply, strategy should have 1500 rows (bet-1 only)"
    )


def test_db_snapshot_before_extra_rows_zero(artifact):
    assert artifact["db_snapshot_before"]["extra_rows"] == 0


def test_db_snapshot_before_has_bet_index(artifact):
    assert artifact["db_snapshot_before"]["has_bet_index_column"] is True


# ---------------------------------------------------------------------------
# 4. DB snapshot — after
# ---------------------------------------------------------------------------
def test_db_snapshot_after_rows(artifact):
    assert artifact["db_snapshot_after"]["replay_rows"] == EXPECTED_ROWS_AFTER


def test_db_snapshot_after_strategy_rows(artifact):
    assert artifact["db_snapshot_after"]["strategy_rows"] == EXPECTED_STRATEGY_TOTAL


def test_db_snapshot_after_extra_rows(artifact):
    assert artifact["db_snapshot_after"]["extra_rows"] == EXPECTED_INSERT_ROWS


# ---------------------------------------------------------------------------
# 5. Apply scope
# ---------------------------------------------------------------------------
def test_apply_scope_strategy_id(artifact):
    assert artifact["apply_scope"]["strategy_id"] == STRATEGY_ID


def test_apply_scope_lottery_type(artifact):
    assert artifact["apply_scope"]["lottery_type"] == LOTTERY_TYPE


def test_apply_scope_expected_insert_rows(artifact):
    assert artifact["apply_scope"]["expected_insert_rows"] == EXPECTED_INSERT_ROWS


def test_apply_scope_actual_insert_rows(artifact):
    assert artifact["apply_scope"]["actual_insert_rows"] == EXPECTED_INSERT_ROWS


def test_apply_scope_controlled_apply_id(artifact):
    assert artifact["apply_scope"]["controlled_apply_id"] == CONTROLLED_APPLY_ID


# ---------------------------------------------------------------------------
# 6. Inserted rows summary
# ---------------------------------------------------------------------------
def test_inserted_rows_total(artifact):
    assert artifact["inserted_rows_summary"]["total_rows_inserted"] == EXPECTED_INSERT_ROWS


def test_inserted_rows_bet2(artifact):
    assert artifact["inserted_rows_summary"]["bet2_rows_inserted"] == 1500


def test_inserted_rows_bet3(artifact):
    assert artifact["inserted_rows_summary"]["bet3_rows_inserted"] == 1500


def test_inserted_rows_bet4(artifact):
    assert artifact["inserted_rows_summary"]["bet4_rows_inserted"] == 1500


def test_inserted_rows_bet5(artifact):
    assert artifact["inserted_rows_summary"]["bet5_rows_inserted"] == 1500


def test_inserted_rows_truth_level(artifact):
    assert artifact["inserted_rows_summary"]["truth_level"] == "REAL"


def test_inserted_rows_dry_run_false(artifact):
    assert artifact["inserted_rows_summary"]["dry_run"] is False


# ---------------------------------------------------------------------------
# 7. Bet index validation
# ---------------------------------------------------------------------------
def test_bet_index_validation_bet1(artifact):
    assert artifact["bet_index_validation"]["bet1_count"] == 1500


def test_bet_index_validation_bet2(artifact):
    assert artifact["bet_index_validation"]["bet2_count"] == 1500


def test_bet_index_validation_bet3(artifact):
    assert artifact["bet_index_validation"]["bet3_count"] == 1500


def test_bet_index_validation_bet4(artifact):
    assert artifact["bet_index_validation"]["bet4_count"] == 1500


def test_bet_index_validation_bet5(artifact):
    assert artifact["bet_index_validation"]["bet5_count"] == 1500


# ---------------------------------------------------------------------------
# 8. Row preservation (prior P126B-E rows intact)
# ---------------------------------------------------------------------------
def test_row_preservation_pass(artifact):
    rp = artifact["row_preservation_check"]
    assert rp["expected_rows_after"] == EXPECTED_ROWS_AFTER
    assert rp["actual_rows_after"] == EXPECTED_ROWS_AFTER


# ---------------------------------------------------------------------------
# 9. Drift guard update
# ---------------------------------------------------------------------------
def test_drift_guard_update_new_total(artifact):
    assert artifact["drift_guard_update"]["new_total"] == EXPECTED_ROWS_AFTER


def test_drift_guard_update_rows_added(artifact):
    assert artifact["drift_guard_update"]["rows_added"] == EXPECTED_INSERT_ROWS


# ---------------------------------------------------------------------------
# 10. All P126A candidates complete
# ---------------------------------------------------------------------------
def test_all_candidates_complete(artifact):
    status = artifact["all_p126_candidates_status"]
    assert status["applied_candidates"] == 5
    assert status["remaining_candidates"] == 0
    assert status["all_complete"] is True


def test_all_candidates_ids(artifact):
    candidates = artifact["all_p126_candidates_status"]["candidates"]
    assert candidates["power_fourier_rhythm_2bet"] == "P126B_APPLIED"
    assert candidates["biglotto_echo_aware_3bet"] == "P126C_APPLIED"
    assert candidates["daily539_f4cold_3bet"] == "P126D_APPLIED"
    assert candidates["biglotto_ts3_markov_4bet_w30"] == "P126E_APPLIED"
    assert candidates["daily539_f4cold_5bet"] == "P126F_APPLIED"


# ---------------------------------------------------------------------------
# 11. Governance
# ---------------------------------------------------------------------------
def test_governance_no_scheduler(artifact):
    assert artifact["governance"]["scheduler_installed"] is False


def test_governance_no_4star(artifact):
    assert artifact["governance"]["4_star_applied"] is False


def test_governance_no_p108(artifact):
    assert artifact["governance"]["p108_applied"] is False


def test_governance_no_p117(artifact):
    assert artifact["governance"]["p117_applied"] is False


def test_governance_no_p118(artifact):
    assert artifact["governance"]["p118_applied"] is False


def test_governance_all_candidates_complete(artifact):
    assert artifact["governance"]["all_5_p126a_candidates_complete"] is True


# ---------------------------------------------------------------------------
# 12. Live DB checks
# ---------------------------------------------------------------------------
def test_live_db_total_rows(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    assert count == EXPECTED_ROWS_AFTER, f"Expected {EXPECTED_ROWS_AFTER} rows, got {count}"


def test_live_db_strategy_total(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
        (STRATEGY_ID,)
    ).fetchone()[0]
    assert count == EXPECTED_STRATEGY_TOTAL, f"Expected {EXPECTED_STRATEGY_TOTAL} strategy rows, got {count}"


def test_live_db_bet_index_distribution(db_conn):
    rows = db_conn.execute(
        "SELECT bet_index, COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id=? GROUP BY bet_index ORDER BY bet_index",
        (STRATEGY_ID,)
    ).fetchall()
    dist = {row[0]: row[1] for row in rows}
    for idx in range(1, 6):
        assert dist.get(idx) == 1500, f"bet_{idx}: expected 1500, got {dist.get(idx)}"


def test_live_db_lottery_type(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id=? AND lottery_type=?",
        (STRATEGY_ID, LOTTERY_TYPE)
    ).fetchone()[0]
    assert count == EXPECTED_STRATEGY_TOTAL


def test_live_db_controlled_apply_id_rows(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id=?",
        (CONTROLLED_APPLY_ID,)
    ).fetchone()[0]
    assert count == EXPECTED_INSERT_ROWS, f"Expected {EXPECTED_INSERT_ROWS} from controlled_apply_id"


def test_live_db_bet_index_column_exists(db_conn):
    cols = [row[1] for row in db_conn.execute("PRAGMA table_info(strategy_prediction_replays)")]
    assert "bet_index" in cols


def test_live_db_no_duplicates(db_conn):
    dup = db_conn.execute(
        "SELECT COUNT(*) FROM ("
        "  SELECT lottery_type, target_draw, strategy_id, bet_index, COUNT(*) AS cnt "
        "  FROM strategy_prediction_replays "
        "  WHERE strategy_id=? "
        "  GROUP BY lottery_type, target_draw, strategy_id, bet_index "
        "  HAVING cnt > 1"
        ")",
        (STRATEGY_ID,)
    ).fetchone()[0]
    assert dup == 0, f"Duplicate rows found for {STRATEGY_ID}: {dup}"


# Prior strategies preserved
def test_live_db_p126b_rows_preserved(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_fourier_rhythm_2bet'"
    ).fetchone()[0]
    assert count == 3000, f"P126B rows not preserved: {count}"


def test_live_db_p126c_rows_preserved(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='biglotto_echo_aware_3bet'"
    ).fetchone()[0]
    assert count == 4500, f"P126C rows not preserved: {count}"


def test_live_db_p126d_rows_preserved(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='daily539_f4cold_3bet'"
    ).fetchone()[0]
    assert count == 4500, f"P126D rows not preserved: {count}"


def test_live_db_p126e_rows_preserved(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='biglotto_ts3_markov_4bet_w30'"
    ).fetchone()[0]
    assert count == 6000, f"P126E rows not preserved: {count}"


# ---------------------------------------------------------------------------
# 13. Drift guard live run
# ---------------------------------------------------------------------------
def test_drift_guard_passes():
    result = subprocess.run(
        [PYTHON, str(DRIFT_GUARD)],
        capture_output=True, text=True, timeout=60, cwd=REPO_ROOT
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, f"Drift guard failed (rc={result.returncode}): {output[-500:]}"
    assert "PASS" in output.upper(), f"Drift guard did not report PASS: {output[-500:]}"
