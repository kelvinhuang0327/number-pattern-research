"""
tests/test_p126e_apply_biglotto_ts3_markov_4bet_w30.py
=======================================================
Regression tests for P126E: biglotto_ts3_markov_4bet_w30 controlled replay rows.

Validates:
  - Artifact JSON exists with correct classification and field values
  - DB state: 66462 rows, strategy rows = 6000, bet distribution 1500×4
  - P126B/P126C/P126D rows preserved
  - daily539_f4cold_5bet not applied (still 1500 rows)
  - Drift guard passes at 66462
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
ARTIFACT    = REPO_ROOT / "outputs/replay/p126e_apply_biglotto_ts3_markov_4bet_w30_20260528.json"
MD_PATH     = REPO_ROOT / "docs/replay/p126e_apply_biglotto_ts3_markov_4bet_w30_20260528.md"
DB_PATH     = REPO_ROOT / "lottery_api/data/lottery_v2.db"
DRIFT_GUARD = REPO_ROOT / "scripts/replay_lifecycle_drift_guard.py"
PYTHON      = sys.executable

STRATEGY_ID         = "biglotto_ts3_markov_4bet_w30"
LOTTERY_TYPE        = "BIG_LOTTO"
CONTROLLED_APPLY_ID = "P126E_BIGLOTTO_TS3_MARKOV_4BET_W30_20260528"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT.exists(), f"P126E JSON not found: {ARTIFACT}"
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
    assert ARTIFACT.exists(), "P126E JSON artifact must exist"


def test_markdown_exists():
    assert MD_PATH.exists(), "P126E Markdown must exist"


def test_task_id(artifact):
    assert artifact["task_id"] == "P126E"


def test_classification(artifact):
    assert artifact["classification"] == "P126E_BIGLOTTO_TS3_MARKOV_4BET_W30_APPLIED"


def test_generated_at_present(artifact):
    assert artifact.get("generated_at"), "generated_at must be present"


# ---------------------------------------------------------------------------
# 2. Authorization
# ---------------------------------------------------------------------------
def test_authorization_present(artifact):
    assert artifact["authorization"]["authorization_present"] is True


def test_authorization_apply_allowed(artifact):
    assert artifact["authorization"]["apply_allowed"] is True


def test_authorization_strategy_id(artifact):
    assert artifact["authorization"]["strategy_id"] == STRATEGY_ID


def test_authorization_text_observed(artifact):
    obs = artifact["authorization"]["authorization_text_observed"]
    assert obs and obs.startswith(
        f"YES authorize controlled_apply for {STRATEGY_ID} because "
    )


# ---------------------------------------------------------------------------
# 3. DB snapshot before
# ---------------------------------------------------------------------------
def test_db_before_rows(artifact):
    assert artifact["db_snapshot_before"]["replay_rows"] == 61962


def test_db_before_has_bet_index(artifact):
    assert artifact["db_snapshot_before"]["has_bet_index_column"] is True


def test_db_before_has_unique_constraint(artifact):
    assert artifact["db_snapshot_before"]["has_new_unique_constraint"] is True


# ---------------------------------------------------------------------------
# 4. Backup
# ---------------------------------------------------------------------------
def test_backup_created(artifact):
    assert artifact["backup"]["backup_created"] is True


def test_backup_row_count(artifact):
    assert artifact["backup"]["backup_row_count"] == 61962


def test_backup_verification(artifact):
    assert artifact["backup"]["backup_verification"] == "PASS"


def test_backup_path_exists(artifact):
    backup_path = Path(artifact["backup"]["backup_path"])
    assert backup_path.exists(), f"Backup file not found: {backup_path}"


# ---------------------------------------------------------------------------
# 5. Apply scope
# ---------------------------------------------------------------------------
def test_apply_scope_strategy_id(artifact):
    assert artifact["apply_scope"]["strategy_id"] == STRATEGY_ID


def test_apply_scope_lottery_type(artifact):
    assert artifact["apply_scope"]["lottery_type"] == LOTTERY_TYPE


def test_apply_scope_expected_rows(artifact):
    assert artifact["apply_scope"]["expected_insert_rows"] == 4500


def test_apply_scope_actual_rows(artifact):
    assert artifact["apply_scope"]["actual_insert_rows"] == 4500


def test_apply_scope_target_bet_count(artifact):
    assert artifact["apply_scope"]["target_bet_count"] == 4


def test_apply_scope_executed(artifact):
    assert artifact["apply_scope"]["apply_executed"] is True


def test_apply_scope_bet2_rows(artifact):
    assert artifact["apply_scope"]["bet2_rows_inserted"] == 1500


def test_apply_scope_bet3_rows(artifact):
    assert artifact["apply_scope"]["bet3_rows_inserted"] == 1500


def test_apply_scope_bet4_rows(artifact):
    assert artifact["apply_scope"]["bet4_rows_inserted"] == 1500


# ---------------------------------------------------------------------------
# 6. Inserted rows summary
# ---------------------------------------------------------------------------
def test_inserted_rows_total(artifact):
    assert artifact["inserted_rows_summary"]["total_rows_inserted"] == 4500


def test_inserted_rows_dry_run_false(artifact):
    assert artifact["inserted_rows_summary"]["dry_run"] is False


def test_inserted_rows_controlled_apply_id(artifact):
    assert artifact["inserted_rows_summary"]["controlled_apply_id"] == CONTROLLED_APPLY_ID


# ---------------------------------------------------------------------------
# 7. Duplicate guard
# ---------------------------------------------------------------------------
def test_duplicate_guard_constraint_active(artifact):
    assert artifact["duplicate_guard"]["constraint_active"] is True


def test_duplicate_guard_rejected(artifact):
    assert artifact["duplicate_guard"]["duplicate_rejected_in_validation"] is True


def test_duplicate_guard_other_untouched(artifact):
    assert artifact["duplicate_guard"]["other_candidates_untouched"] is True


def test_duplicate_guard_ok(artifact):
    assert artifact["duplicate_guard"]["guard_ok"] is True


# ---------------------------------------------------------------------------
# 8. bet_index validation
# ---------------------------------------------------------------------------
def test_bet_index_bet1(artifact):
    assert artifact["bet_index_validation"]["bet1_count"] == 1500


def test_bet_index_bet2(artifact):
    assert artifact["bet_index_validation"]["bet2_count"] == 1500


def test_bet_index_bet3(artifact):
    assert artifact["bet_index_validation"]["bet3_count"] == 1500


def test_bet_index_bet4(artifact):
    assert artifact["bet_index_validation"]["bet4_count"] == 1500


def test_bet_index_distribution_ok(artifact):
    assert artifact["bet_index_validation"]["distribution_ok"] is True


def test_bet_index_validation_pass(artifact):
    assert artifact["bet_index_validation"]["validation"] == "PASS"


def test_all_rows_big_lotto(artifact):
    assert artifact["bet_index_validation"]["all_rows_big_lotto"] is True


# ---------------------------------------------------------------------------
# 9. DB snapshot after
# ---------------------------------------------------------------------------
def test_db_after_rows(artifact):
    assert artifact["db_snapshot_after"]["replay_rows"] == 66462


def test_db_after_strategy_rows(artifact):
    assert artifact["db_snapshot_after"]["biglotto_ts3_markov_4bet_w30_rows"] == 6000


# ---------------------------------------------------------------------------
# 10. Row preservation check
# ---------------------------------------------------------------------------
def test_row_preservation_before(artifact):
    assert artifact["row_preservation_check"]["rows_before_apply"] == 61962


def test_row_preservation_inserted(artifact):
    assert artifact["row_preservation_check"]["rows_inserted"] == 4500


def test_row_preservation_expected_after(artifact):
    assert artifact["row_preservation_check"]["expected_rows_after"] == 66462


def test_row_preservation_actual_after(artifact):
    assert artifact["row_preservation_check"]["actual_rows_after"] == 66462


def test_row_preservation_ok(artifact):
    assert artifact["row_preservation_check"]["rows_preserved_ok"] is True


# ---------------------------------------------------------------------------
# 11. Previous apply status (P126B/C/D)
# ---------------------------------------------------------------------------
def test_pfr_already_applied(artifact):
    assert artifact["previous_apply_status"]["power_fourier_rhythm_2bet"]["already_applied"] is True


def test_pfr_rows_preserved(artifact):
    assert artifact["previous_apply_status"]["power_fourier_rhythm_2bet"]["rows_preserved"] is True


def test_pfr_total_rows(artifact):
    assert artifact["previous_apply_status"]["power_fourier_rhythm_2bet"]["pfr_total_rows"] == 3000


def test_echo_already_applied(artifact):
    assert artifact["previous_apply_status"]["biglotto_echo_aware_3bet"]["already_applied"] is True


def test_echo_rows_preserved(artifact):
    assert artifact["previous_apply_status"]["biglotto_echo_aware_3bet"]["rows_preserved"] is True


def test_echo_total_rows(artifact):
    assert artifact["previous_apply_status"]["biglotto_echo_aware_3bet"]["echo_total_rows"] == 4500


def test_f4cold_already_applied(artifact):
    assert artifact["previous_apply_status"]["daily539_f4cold_3bet"]["already_applied"] is True


def test_f4cold_rows_preserved(artifact):
    assert artifact["previous_apply_status"]["daily539_f4cold_3bet"]["rows_preserved"] is True


def test_f4cold_total_rows(artifact):
    assert artifact["previous_apply_status"]["daily539_f4cold_3bet"]["f4cold_total_rows"] == 4500


def test_previous_rows_preserved(artifact):
    assert artifact["previous_apply_status"]["previous_rows_preserved"] is True


def test_no_duplicate_previous_rows(artifact):
    assert artifact["previous_apply_status"]["no_duplicate_previous_rows"] is True


# ---------------------------------------------------------------------------
# 12. Blocked / excluded
# ---------------------------------------------------------------------------
def test_daily539_f4cold_5bet_not_applied(artifact):
    assert artifact["blocked_or_excluded"]["daily539_f4cold_5bet_not_applied"] is True


def test_4star_excluded(artifact):
    assert artifact["blocked_or_excluded"]["4_STAR_excluded"] is True


def test_p108_not_run(artifact):
    assert artifact["blocked_or_excluded"]["P108_not_run"] is True


def test_p117_not_run(artifact):
    assert artifact["blocked_or_excluded"]["P117_not_run"] is True


def test_p118_not_run(artifact):
    assert artifact["blocked_or_excluded"]["P118_not_run"] is True


def test_no_scheduler_install(artifact):
    assert artifact["blocked_or_excluded"]["no_scheduler_install"] is True


def test_no_lifecycle_mutation(artifact):
    assert artifact["blocked_or_excluded"]["no_lifecycle_champion_registry_mutation"] is True


# ---------------------------------------------------------------------------
# 13. Rollback reference
# ---------------------------------------------------------------------------
def test_rollback_reference_backup_path(artifact):
    assert artifact["rollback_reference"]["backup_path"], "backup_path must be non-empty"


def test_rollback_reference_rollback_command(artifact):
    cmd = artifact["rollback_reference"]["rollback_command"]
    assert "cp " in cmd and "lottery_v2.db" in cmd


# ---------------------------------------------------------------------------
# 14. Candidate source summary
# ---------------------------------------------------------------------------
def test_candidate_p126a_ok(artifact):
    assert artifact["candidate_source_summary"]["p126a_ok"] is True


def test_candidate_p126b_ok(artifact):
    assert artifact["candidate_source_summary"]["p126b_ok"] is True


def test_candidate_p126c_ok(artifact):
    assert artifact["candidate_source_summary"]["p126c_ok"] is True


def test_candidate_p126d_ok(artifact):
    assert artifact["candidate_source_summary"]["p126d_ok"] is True


def test_candidate_p129b_ok(artifact):
    assert artifact["candidate_source_summary"]["p129b_ok"] is True


# ---------------------------------------------------------------------------
# 15. Live DB checks
# ---------------------------------------------------------------------------
def test_live_db_total_rows(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    assert count == 66462, f"Expected 66462 rows, got {count}"


def test_live_db_strategy_total(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
        (STRATEGY_ID,)
    ).fetchone()[0]
    assert count == 6000, f"Expected 6000 strategy rows, got {count}"


def test_live_db_bet1_count(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=1",
        (STRATEGY_ID,)
    ).fetchone()[0]
    assert count == 1500


def test_live_db_bet2_count(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=2",
        (STRATEGY_ID,)
    ).fetchone()[0]
    assert count == 1500


def test_live_db_bet3_count(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=3",
        (STRATEGY_ID,)
    ).fetchone()[0]
    assert count == 1500


def test_live_db_bet4_count(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=4",
        (STRATEGY_ID,)
    ).fetchone()[0]
    assert count == 1500


def test_live_db_all_lottery_type_biglotto(db_conn):
    wrong = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND lottery_type!=?",
        (STRATEGY_ID, LOTTERY_TYPE)
    ).fetchone()[0]
    assert wrong == 0, f"Found {wrong} rows with wrong lottery_type"


def test_live_db_controlled_apply_id_rows(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
        (CONTROLLED_APPLY_ID,)
    ).fetchone()[0]
    assert count == 4500, f"Expected 4500 P126E rows, got {count}"


def test_live_db_pfr_preserved(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_fourier_rhythm_2bet'"
    ).fetchone()[0]
    assert count == 3000, f"P126B rows changed: {count}"


def test_live_db_echo_preserved(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='biglotto_echo_aware_3bet'"
    ).fetchone()[0]
    assert count == 4500, f"P126C rows changed: {count}"


def test_live_db_f4cold_preserved(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='daily539_f4cold_3bet'"
    ).fetchone()[0]
    assert count == 4500, f"P126D rows changed: {count}"


def test_live_db_f4cold5_not_applied(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='daily539_f4cold_5bet' AND bet_index>1"
    ).fetchone()[0]
    assert count == 0, f"daily539_f4cold_5bet has unexpected extra bet rows: {count}"


# ---------------------------------------------------------------------------
# 16. Drift guard
# ---------------------------------------------------------------------------
def test_drift_guard_passes():
    result = subprocess.run(
        [PYTHON, str(DRIFT_GUARD)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in result.stdout, (
        f"Drift guard FAIL:\n{result.stdout}\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# 17. Markdown content checks
# ---------------------------------------------------------------------------
def test_markdown_has_backup_path(artifact):
    md = MD_PATH.read_text()
    backup_path = artifact["backup"]["backup_path"]
    assert backup_path in md, "Markdown must contain backup path"


def test_markdown_has_rollback_command():
    md = MD_PATH.read_text()
    assert "cp '" in md and "lottery_v2.db" in md, "Markdown must contain rollback command"


def test_markdown_has_classification():
    md = MD_PATH.read_text()
    assert "P126E_BIGLOTTO_TS3_MARKOV_4BET_W30_APPLIED" in md


def test_markdown_has_executive_summary():
    md = MD_PATH.read_text()
    assert "Executive Summary" in md


def test_markdown_has_authorization_section():
    md = MD_PATH.read_text()
    assert "Authorization" in md


def test_markdown_has_nonactions():
    md = MD_PATH.read_text()
    assert "Explicit Non-Actions" in md or "non-actions" in md.lower() or "did **not**" in md
