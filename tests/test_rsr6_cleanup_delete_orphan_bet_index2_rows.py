"""
tests/test_rsr6_cleanup_delete_orphan_bet_index2_rows.py
=========================================================
Verification tests for RSR-6 cleanup execution results.

Validates the cleanup JSON artifact and live DB state after
the authorized deletion of 40 orphan bet_index=2 rows.
"""

import json
import pathlib
import sqlite3

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CLEANUP_JSON = (
    REPO_ROOT
    / "outputs"
    / "replay"
    / "rsr6_cleanup_delete_orphan_bet_index2_rows_20260528.json"
)
CLEANUP_MD = (
    REPO_ROOT
    / "docs"
    / "replay"
    / "rsr6_cleanup_delete_orphan_bet_index2_rows_20260528.md"
)
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
DRIFT_GUARD = REPO_ROOT / "scripts" / "replay_lifecycle_drift_guard.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cleanup_data():
    assert CLEANUP_JSON.exists(), f"Cleanup JSON not found: {CLEANUP_JSON}"
    return json.loads(CLEANUP_JSON.read_text())


@pytest.fixture(scope="module")
def db_conn():
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# 1. JSON artifact presence and identity
# ---------------------------------------------------------------------------


def test_cleanup_json_exists():
    assert CLEANUP_JSON.exists(), "Cleanup JSON artifact must exist"


def test_task_id(cleanup_data):
    assert cleanup_data["task_id"] == "RSR6_CLEANUP"


def test_classification(cleanup_data):
    assert cleanup_data["classification"] == "RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED"


# ---------------------------------------------------------------------------
# 2. Authorization
# ---------------------------------------------------------------------------


def test_authorization_present(cleanup_data):
    assert cleanup_data["authorization"]["authorization_present"] is True


def test_cleanup_allowed(cleanup_data):
    assert cleanup_data["authorization"]["cleanup_allowed"] is True


def test_authorization_phrase_matches(cleanup_data):
    expected = (
        "RSR6_CLEANUP_AUTHORIZED_DELETE_40_ORPHAN_BET_INDEX2_ROWS_POWER_PRECISION_AND_ORTHOGONAL_20260528"
    )
    observed = cleanup_data["authorization"]["authorization_text_observed"]
    assert observed == expected


# ---------------------------------------------------------------------------
# 3. Backup verification
# ---------------------------------------------------------------------------


def test_backup_created(cleanup_data):
    assert cleanup_data["backup"]["backup_created"] is True


def test_backup_row_count(cleanup_data):
    assert cleanup_data["backup"]["backup_row_count"] == 72462


def test_backup_file_exists(cleanup_data):
    backup_path = pathlib.Path(cleanup_data["backup"]["backup_path"])
    assert backup_path.exists(), f"Backup file not found: {backup_path}"


# ---------------------------------------------------------------------------
# 4. DB rows before / after
# ---------------------------------------------------------------------------


def test_db_rows_before(cleanup_data):
    assert cleanup_data["db_snapshot_before"]["total_rows"] == 72462


def test_db_rows_after(cleanup_data):
    assert cleanup_data["db_snapshot_after"]["total_rows"] == 72422


def test_db_rows_after_live(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    # RSR-6 cleanup landed at 72422. P131 applied +3000 (→ 75422). P132 applied +3000 (→ 78422).
    assert count == 78422, f"Live DB row count: expected 78422 (post-P132), got {count}"


# ---------------------------------------------------------------------------
# 5. Delete scope
# ---------------------------------------------------------------------------


def test_expected_delete_rows(cleanup_data):
    assert cleanup_data["delete_scope"]["expected_delete_rows"] == 40


def test_actual_deleted_rows(cleanup_data):
    assert cleanup_data["delete_scope"]["actual_deleted_rows"] == 40


def test_selector_strict(cleanup_data):
    assert cleanup_data["delete_scope"]["selector_strict"] is True


def test_affected_strategies(cleanup_data):
    strats = cleanup_data["delete_scope"]["affected_strategies"]
    assert "power_precision_3bet" in strats
    assert "power_orthogonal_5bet" in strats


# ---------------------------------------------------------------------------
# 6. Orphan selector count after cleanup
# ---------------------------------------------------------------------------


def test_orphan_count_after_artifact(cleanup_data):
    assert cleanup_data["orphan_selector_validation_after"]["orphan_count_after"] == 0


def test_orphan_count_is_zero_flag(cleanup_data):
    assert cleanup_data["orphan_selector_validation_after"]["orphan_count_is_zero"] is True


def test_orphan_count_after_live(db_conn):
    count = db_conn.execute(
        """
        SELECT COUNT(*) FROM strategy_prediction_replays
        WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
          AND bet_index = 2
          AND replay_run_id = 6
          AND (source IS NULL OR source = '')
          AND controlled_apply_id IS NULL
          AND provenance_hash IS NULL
          AND truth_level IS NULL
          AND CAST(target_draw AS INTEGER) BETWEEN 99000085 AND 99000104
        """
    ).fetchone()[0]
    assert count == 0, f"Orphan rows still present: {count}"


# ---------------------------------------------------------------------------
# 7. Row preservation (bet_index=1)
# ---------------------------------------------------------------------------


def test_power_precision_bet_index1_preserved(cleanup_data):
    rpc = cleanup_data["row_preservation_check"]
    assert rpc["power_precision_3bet_preserved"] is True
    assert (
        rpc["power_precision_3bet_bet_index1_before"]
        == rpc["power_precision_3bet_bet_index1_after"]
    )


def test_power_orthogonal_bet_index1_preserved(cleanup_data):
    rpc = cleanup_data["row_preservation_check"]
    assert rpc["power_orthogonal_5bet_preserved"] is True
    assert (
        rpc["power_orthogonal_5bet_bet_index1_before"]
        == rpc["power_orthogonal_5bet_bet_index1_after"]
    )


def test_all_bet_index1_preserved(cleanup_data):
    assert cleanup_data["row_preservation_check"]["all_bet_index1_rows_preserved"] is True


def test_power_precision_bet_index1_live(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_precision_3bet' AND bet_index=1"
    ).fetchone()[0]
    assert count > 0, "power_precision_3bet bet_index=1 rows must exist"


def test_power_orthogonal_bet_index1_live(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_orthogonal_5bet' AND bet_index=1"
    ).fetchone()[0]
    assert count > 0, "power_orthogonal_5bet bet_index=1 rows must exist"


# ---------------------------------------------------------------------------
# 8. Non-actions confirmed
# ---------------------------------------------------------------------------


def test_controlled_apply_not_executed(cleanup_data):
    assert cleanup_data["apply_gate_impact_after_cleanup"]["controlled_apply_executed"] is False


def test_replay_rows_not_inserted(cleanup_data):
    assert cleanup_data["apply_gate_impact_after_cleanup"]["replay_rows_inserted"] == 0


def test_blocked_4star(cleanup_data):
    assert cleanup_data["blocked_or_excluded"]["4_STAR_excluded"] is True


def test_blocked_p108(cleanup_data):
    assert cleanup_data["blocked_or_excluded"]["P108_not_run"] is True


def test_blocked_p117(cleanup_data):
    assert cleanup_data["blocked_or_excluded"]["P117_not_run"] is True


def test_blocked_p118(cleanup_data):
    assert cleanup_data["blocked_or_excluded"]["P118_not_run"] is True


def test_blocked_rejected_strategies(cleanup_data):
    assert cleanup_data["blocked_or_excluded"]["rejected_strategies_no_action"] is True


def test_no_scheduler_install(cleanup_data):
    assert cleanup_data["blocked_or_excluded"]["no_scheduler_install"] is True


def test_p126b_p126f_untouched(cleanup_data):
    assert cleanup_data["blocked_or_excluded"]["P126B_P126F_rows_untouched"] is True


# ---------------------------------------------------------------------------
# 9. Apply gate impact
# ---------------------------------------------------------------------------


def test_power_precision_rsr6_cleaned(cleanup_data):
    assert cleanup_data["apply_gate_impact_after_cleanup"]["power_precision_3bet_rsr6_cleaned"] is True


def test_power_orthogonal_rsr6_cleaned(cleanup_data):
    assert cleanup_data["apply_gate_impact_after_cleanup"]["power_orthogonal_5bet_rsr6_cleaned"] is True


def test_apply_re_evaluation_required(cleanup_data):
    assert cleanup_data["apply_gate_impact_after_cleanup"]["apply_ready_re_evaluation_required"] is True


# ---------------------------------------------------------------------------
# 10. Rollback reference in Markdown
# ---------------------------------------------------------------------------


def test_markdown_exists():
    assert CLEANUP_MD.exists(), "Cleanup Markdown must exist"


def test_markdown_has_backup_path(cleanup_data):
    assert CLEANUP_MD.exists()
    md_text = CLEANUP_MD.read_text()
    backup_path = cleanup_data["backup"]["backup_path"]
    assert backup_path in md_text, f"Backup path must appear in Markdown: {backup_path}"


def test_markdown_has_rollback_command(cleanup_data):
    assert CLEANUP_MD.exists()
    md_text = CLEANUP_MD.read_text()
    assert "restore_command" in md_text or "Restore command" in md_text or "cp '" in md_text


# ---------------------------------------------------------------------------
# 11. P126B–P126F rows untouched (live check)
# ---------------------------------------------------------------------------


def test_p126b_rows_intact(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id='P126B_POWER_FOURIER_RHYTHM_2BET_20260528'"
    ).fetchone()[0]
    assert count == 1500, f"P126B rows must be 1500, got {count}"


def test_p126c_rows_intact(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id='P126C_BIGLOTTO_ECHO_AWARE_3BET_20260528'"
    ).fetchone()[0]
    assert count == 3000, f"P126C rows must be 3000, got {count}"


def test_p126d_rows_intact(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id='P126D_DAILY539_F4COLD_3BET_20260528'"
    ).fetchone()[0]
    assert count == 3000, f"P126D rows must be 3000, got {count}"


def test_p126e_rows_intact(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id='P126E_BIGLOTTO_TS3_MARKOV_4BET_W30_20260528'"
    ).fetchone()[0]
    assert count == 4500, f"P126E rows must be 4500, got {count}"


def test_p126f_rows_intact(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id='P126F_DAILY539_F4COLD_5BET_20260528'"
    ).fetchone()[0]
    assert count == 6000, f"P126F rows must be 6000, got {count}"


# ---------------------------------------------------------------------------
# 12. No forbidden staging (sanity: no runtime/pid/history files)
# ---------------------------------------------------------------------------


def test_no_history_files_in_repo():
    import subprocess
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    staged = result.stdout
    for forbidden in [".history", ".pid", ".runtime"]:
        assert forbidden not in staged, f"Forbidden file pattern '{forbidden}' found in git status"
