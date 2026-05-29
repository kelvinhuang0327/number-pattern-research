"""
tests/test_p134_apply_fourier_rhythm_3bet.py
=============================================
Verification tests for P134: fourier_rhythm_3bet controlled replay rows applied.

Validates the JSON artifact and live DB state.
P9 anomaly: 1501 bet-1 rows (draw-ext 115000041) → +3002 rows.
DB: 82922 → 85924.
"""

import json
import pathlib
import sqlite3
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

ARTIFACT = (
    REPO_ROOT / "outputs" / "replay" / "p134_apply_fourier_rhythm_3bet_20260528.json"
)
MD_PATH = REPO_ROOT / "docs" / "replay" / "p134_apply_fourier_rhythm_3bet_20260528.md"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_ROWS_BEFORE = 82922
EXPECTED_ROWS_AFTER  = 85924
EXPECTED_ROWS_CURRENT = 94924  # post-P141: +6000 power_orthogonal_5bet rows
EXPECTED_INSERT_ROWS = 3002
EXPECTED_BET1_ROWS   = 1501   # P9 anomaly
EXPECTED_BET2_ROWS   = 1501
EXPECTED_BET3_ROWS   = 1501
EXPECTED_STRATEGY_TOTAL = 4503  # 1501×3
EXPECTED_P131_TOTAL  = 4500
EXPECTED_P132_TOTAL  = 4500
EXPECTED_P133_TOTAL  = 6000
DRAW_EXT_TARGET_DRAW = "115000041"

CONTROLLED_APPLY_ID = "P134_FOURIER_RHYTHM_3BET_POWERLOTTO_V20260528"
STRATEGY_ID         = "fourier_rhythm_3bet"
LOTTERY_TYPE        = "POWER_LOTTO"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT.exists(), f"P134 JSON not found: {ARTIFACT}"
    return json.loads(ARTIFACT.read_text())


@pytest.fixture(scope="module")
def db_conn():
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# 1. Artifact identity
# ---------------------------------------------------------------------------


def test_artifact_exists():
    assert ARTIFACT.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P134"


def test_classification(artifact):
    assert artifact["classification"] == "P134_FOURIER_RHYTHM_3BET_APPLIED"


def test_generated_at_present(artifact):
    assert "generated_at" in artifact and artifact["generated_at"]


def test_worktree_confirmed(artifact):
    assert artifact["repo_worktree_check"]["worktree_confirmed"] is True


# ---------------------------------------------------------------------------
# 2. Authorization
# ---------------------------------------------------------------------------


def test_authorization_present(artifact):
    assert artifact["authorization"]["authorization_present"] is True


def test_apply_allowed(artifact):
    assert artifact["authorization"]["apply_allowed"] is True


def test_authorization_phrase_observed(artifact):
    expected = "P130_AUTHORIZED_APPLY_FOURIER_RHYTHM_3BET_POWERLOTTO_BET2_BET3_V20260528"
    assert artifact["authorization"]["authorization_text_observed"] == expected


def test_exact_required_phrase(artifact):
    assert artifact["authorization"]["exact_required_phrase"] == (
        "P130_AUTHORIZED_APPLY_FOURIER_RHYTHM_3BET_POWERLOTTO_BET2_BET3_V20260528"
    )


# ---------------------------------------------------------------------------
# 3. P9 Anomaly Handling
# ---------------------------------------------------------------------------


def test_anomaly_type(artifact):
    assert artifact["anomaly_handling"]["anomaly_type"] == "P9_1501_ROW_DRAW_EXT"


def test_anomaly_draw_ext_target_draw(artifact):
    assert artifact["anomaly_handling"]["draw_ext_target_draw"] == DRAW_EXT_TARGET_DRAW


def test_anomaly_bet1_rows(artifact):
    assert artifact["anomaly_handling"]["bet1_rows"] == 1501


def test_anomaly_expected_insert_rows(artifact):
    assert artifact["anomaly_handling"]["expected_insert_rows"] == EXPECTED_INSERT_ROWS


def test_anomaly_accepted_as_planned(artifact):
    assert artifact["anomaly_handling"]["accepted_as_planned"] is True


# ---------------------------------------------------------------------------
# 4. Draw-ext 115000041 validation
# ---------------------------------------------------------------------------


def test_draw_ext_bet1_exists_artifact(artifact):
    assert artifact["draw_ext_115000041_validation"]["bet1_exists"] is True


def test_draw_ext_bet2_exists_artifact(artifact):
    assert artifact["draw_ext_115000041_validation"]["bet2_exists"] is True


def test_draw_ext_bet3_exists_artifact(artifact):
    assert artifact["draw_ext_115000041_validation"]["bet3_exists"] is True


def test_draw_ext_all_three_bets_present(artifact):
    assert artifact["draw_ext_115000041_validation"]["all_three_bets_present"] is True


def test_draw_ext_bet1_count(artifact):
    assert artifact["draw_ext_115000041_validation"]["draw_ext_bet1_count"] == 1


def test_draw_ext_bet2_count(artifact):
    assert artifact["draw_ext_115000041_validation"]["draw_ext_bet2_count"] == 1


def test_draw_ext_bet3_count(artifact):
    assert artifact["draw_ext_115000041_validation"]["draw_ext_bet3_count"] == 1


def test_draw_ext_all_bets_live(db_conn):
    for bi in (1, 2, 3):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND target_draw=? AND bet_index=?",
            (STRATEGY_ID, DRAW_EXT_TARGET_DRAW, bi),
        ).fetchone()[0]
        assert cnt == 1, (
            f"{STRATEGY_ID} draw {DRAW_EXT_TARGET_DRAW} bet_index={bi}: expected 1, got {cnt}"
        )


# ---------------------------------------------------------------------------
# 5. DB snapshot before
# ---------------------------------------------------------------------------


def test_db_rows_before(artifact):
    assert artifact["db_snapshot_before"]["replay_rows"] == EXPECTED_ROWS_BEFORE


def test_db_snapshot_bet_index_column(artifact):
    assert artifact["db_snapshot_before"]["has_bet_index_column"] is True


def test_db_snapshot_unique_constraint(artifact):
    assert artifact["db_snapshot_before"]["has_new_unique_constraint"] is True


def test_db_snapshot_draw_ext_bet1_before(artifact):
    assert artifact["db_snapshot_before"]["draw_ext_115000041_bet1_exists"] is True


# ---------------------------------------------------------------------------
# 6. Backup
# ---------------------------------------------------------------------------


def test_backup_created(artifact):
    assert artifact["backup"]["backup_created"] is True


def test_backup_row_count(artifact):
    assert artifact["backup"]["backup_row_count"] == EXPECTED_ROWS_BEFORE


def test_backup_verification_pass(artifact):
    assert artifact["backup"]["backup_verification"] == "PASS"


def test_backup_ok(artifact):
    assert artifact["backup"]["backup_ok"] is True


def test_backup_file_exists(artifact):
    backup_path = pathlib.Path(artifact["backup"]["backup_path"])
    assert backup_path.exists(), f"Backup not found: {backup_path}"


def test_rollback_command_present(artifact):
    assert artifact["backup"]["rollback_command"].startswith("cp '")


# ---------------------------------------------------------------------------
# 7. Source artifacts
# ---------------------------------------------------------------------------


def test_p133_classification_pass(artifact):
    assert artifact["p133_source_summary"]["classification_pass"] is True


def test_p133_classification(artifact):
    assert artifact["p133_source_summary"]["classification"] == "P133_PP3_FREQORT_4BET_APPLIED"


def test_p132_classification_pass(artifact):
    assert artifact["p132_source_summary"]["classification_pass"] is True


def test_p131_classification_pass(artifact):
    assert artifact["p131_source_summary"]["classification_pass"] is True


def test_p130_classification_pass(artifact):
    assert artifact["p130_source_summary"]["classification_pass"] is True


def test_p130_p9_in_safe_candidates(artifact):
    assert artifact["p130_source_summary"]["p9_in_safe_candidates"] is True


def test_p130_p9_estimated_insert_rows(artifact):
    assert artifact["p130_source_summary"]["p9_estimated_insert_rows"] == 3002


# ---------------------------------------------------------------------------
# 8. Apply scope
# ---------------------------------------------------------------------------


def test_apply_scope_strategy_id(artifact):
    assert artifact["apply_scope"]["strategy_id"] == STRATEGY_ID


def test_apply_scope_lottery_type(artifact):
    assert artifact["apply_scope"]["lottery_type"] == LOTTERY_TYPE


def test_apply_scope_target_bet_count(artifact):
    assert artifact["apply_scope"]["target_bet_count"] == 3


def test_apply_scope_expected_insert_rows(artifact):
    assert artifact["apply_scope"]["expected_insert_rows"] == EXPECTED_INSERT_ROWS


def test_apply_scope_actual_insert_rows(artifact):
    assert artifact["apply_scope"]["actual_insert_rows"] == EXPECTED_INSERT_ROWS


def test_apply_scope_bet2_rows(artifact):
    assert artifact["apply_scope"]["bet2_rows_inserted"] == EXPECTED_BET2_ROWS


def test_apply_scope_bet3_rows(artifact):
    assert artifact["apply_scope"]["bet3_rows_inserted"] == EXPECTED_BET3_ROWS


def test_apply_scope_controlled_apply_id(artifact):
    assert artifact["apply_scope"]["controlled_apply_id"] == CONTROLLED_APPLY_ID


def test_apply_scope_apply_executed(artifact):
    assert artifact["apply_scope"]["apply_executed"] is True


def test_apply_scope_adapter_function(artifact):
    assert artifact["apply_scope"]["adapter_function"] == "get_all_bets_fourier_rhythm"


# ---------------------------------------------------------------------------
# 9. Inserted rows summary
# ---------------------------------------------------------------------------


def test_total_rows_inserted(artifact):
    assert artifact["inserted_rows_summary"]["total_rows_inserted"] == EXPECTED_INSERT_ROWS


def test_bet2_rows_inserted(artifact):
    assert artifact["inserted_rows_summary"]["bet2_rows_inserted"] == EXPECTED_BET2_ROWS


def test_bet3_rows_inserted(artifact):
    assert artifact["inserted_rows_summary"]["bet3_rows_inserted"] == EXPECTED_BET3_ROWS


def test_dry_run_false(artifact):
    assert artifact["inserted_rows_summary"]["dry_run"] is False


def test_draw_ext_included(artifact):
    assert artifact["inserted_rows_summary"]["draw_ext_included"] is True


# ---------------------------------------------------------------------------
# 10. Duplicate guard
# ---------------------------------------------------------------------------


def test_duplicate_guard_constraint_active(artifact):
    assert artifact["duplicate_guard"]["constraint_active"] is True


def test_duplicate_guard_rejected(artifact):
    assert artifact["duplicate_guard"]["duplicate_rejected_in_validation"] is True


def test_duplicate_guard_ok(artifact):
    assert artifact["duplicate_guard"]["guard_ok"] is True


def test_p10_p12_not_applied(artifact):
    assert artifact["duplicate_guard"]["p10_p12_not_applied"] is True


# ---------------------------------------------------------------------------
# 11. bet_index validation
# ---------------------------------------------------------------------------


def test_bet1_count(artifact):
    assert artifact["bet_index_validation"]["bet1_count"] == EXPECTED_BET1_ROWS


def test_bet2_count(artifact):
    assert artifact["bet_index_validation"]["bet2_count"] == EXPECTED_BET2_ROWS


def test_bet3_count(artifact):
    assert artifact["bet_index_validation"]["bet3_count"] == EXPECTED_BET3_ROWS


def test_expected_bet1(artifact):
    assert artifact["bet_index_validation"]["expected_bet1"] == 1501


def test_expected_bet2(artifact):
    assert artifact["bet_index_validation"]["expected_bet2"] == 1501


def test_expected_bet3(artifact):
    assert artifact["bet_index_validation"]["expected_bet3"] == 1501


def test_distribution_ok(artifact):
    assert artifact["bet_index_validation"]["distribution_ok"] is True


def test_all_rows_power_lotto(artifact):
    assert artifact["bet_index_validation"]["all_rows_power_lotto"] is True


def test_bet_index_validation_pass(artifact):
    assert artifact["bet_index_validation"]["validation"] == "PASS"


def test_p9_anomaly_note_present(artifact):
    note = artifact["bet_index_validation"]["p9_anomaly_note"]
    assert DRAW_EXT_TARGET_DRAW in note


# ---------------------------------------------------------------------------
# 12. DB snapshot after
# ---------------------------------------------------------------------------


def test_db_rows_after_artifact(artifact):
    assert artifact["db_snapshot_after"]["replay_rows"] == EXPECTED_ROWS_AFTER


def test_db_strategy_rows_after(artifact):
    assert artifact["db_snapshot_after"][f"{STRATEGY_ID}_rows"] == EXPECTED_STRATEGY_TOTAL


def test_db_pp3_rows_after(artifact):
    assert artifact["db_snapshot_after"]["pp3_freqort_4bet_rows"] == EXPECTED_P133_TOTAL


def test_db_acb_rows_after(artifact):
    assert artifact["db_snapshot_after"]["acb_markov_midfreq_3bet_rows"] == EXPECTED_P131_TOTAL


def test_db_midfreq_rows_after(artifact):
    assert artifact["db_snapshot_after"]["midfreq_fourier_mk_3bet_rows"] == EXPECTED_P132_TOTAL


# ---------------------------------------------------------------------------
# 13. Row preservation check
# ---------------------------------------------------------------------------


def test_rows_before_apply(artifact):
    assert artifact["row_preservation_check"]["rows_before_apply"] == EXPECTED_ROWS_BEFORE


def test_rows_inserted(artifact):
    assert artifact["row_preservation_check"]["rows_inserted"] == EXPECTED_INSERT_ROWS


def test_expected_rows_after(artifact):
    assert artifact["row_preservation_check"]["expected_rows_after"] == EXPECTED_ROWS_AFTER


def test_actual_rows_after(artifact):
    assert artifact["row_preservation_check"]["actual_rows_after"] == EXPECTED_ROWS_AFTER


def test_rows_preserved_ok(artifact):
    assert artifact["row_preservation_check"]["rows_preserved_ok"] is True


def test_p131_preserved(artifact):
    assert artifact["row_preservation_check"]["p131_rows_preserved"] is True


def test_p131_acb_total(artifact):
    assert artifact["row_preservation_check"]["p131_acb_total"] == EXPECTED_P131_TOTAL


def test_p132_preserved(artifact):
    assert artifact["row_preservation_check"]["p132_rows_preserved"] is True


def test_p132_midfreq_total(artifact):
    assert artifact["row_preservation_check"]["p132_midfreq_total"] == EXPECTED_P132_TOTAL


def test_p133_preserved(artifact):
    assert artifact["row_preservation_check"]["p133_rows_preserved"] is True


def test_p133_pp3_total(artifact):
    assert artifact["row_preservation_check"]["p133_pp3_total"] == EXPECTED_P133_TOTAL


def test_p133_pp3_bet4(artifact):
    assert artifact["row_preservation_check"]["p133_pp3_bet4"] == 1500


# ---------------------------------------------------------------------------
# 14. Blocked / excluded governance
# ---------------------------------------------------------------------------


def test_p10_p12_not_apply_ready(artifact):
    assert artifact["blocked_or_excluded"]["P10_P12_not_apply_ready_until_re_evaluation"] is True


def test_blocked_4star(artifact):
    assert artifact["blocked_or_excluded"]["4_STAR_excluded"] is True


def test_blocked_p108(artifact):
    assert artifact["blocked_or_excluded"]["P108_not_run"] is True


def test_blocked_p117(artifact):
    assert artifact["blocked_or_excluded"]["P117_not_run"] is True


def test_blocked_p118(artifact):
    assert artifact["blocked_or_excluded"]["P118_not_run"] is True


def test_no_scheduler_install(artifact):
    assert artifact["blocked_or_excluded"]["no_scheduler_install"] is True


def test_no_lifecycle_mutation(artifact):
    assert artifact["blocked_or_excluded"]["no_lifecycle_champion_registry_mutation"] is True


def test_p10_p12_untouched_verified(artifact):
    assert artifact["blocked_or_excluded"]["p10_p12_untouched_verified"] is True


# ---------------------------------------------------------------------------
# 15. Wave 2 completion status
# ---------------------------------------------------------------------------


def test_wave2_acb_applied(artifact):
    assert artifact["wave2_completion_status"]["acb_markov_midfreq_3bet_applied"] is True


def test_wave2_midfreq_applied(artifact):
    assert artifact["wave2_completion_status"]["midfreq_fourier_mk_3bet_applied"] is True


def test_wave2_pp3_applied(artifact):
    assert artifact["wave2_completion_status"]["pp3_freqort_4bet_applied"] is True


def test_wave2_fourier_rhythm_applied(artifact):
    assert artifact["wave2_completion_status"]["fourier_rhythm_3bet_applied"] is True


def test_wave2_all_safe_candidates_applied(artifact):
    assert artifact["wave2_completion_status"]["all_safe_candidates_applied"] is True


# ---------------------------------------------------------------------------
# 16. Live DB checks
# ---------------------------------------------------------------------------


def test_live_db_total_rows(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    assert count == EXPECTED_ROWS_CURRENT, (
        f"DB has {count} rows, expected {EXPECTED_ROWS_CURRENT}"
    )


def test_live_db_strategy_total(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
        (STRATEGY_ID,),
    ).fetchone()[0]
    assert count == EXPECTED_STRATEGY_TOTAL, (
        f"{STRATEGY_ID}: expected {EXPECTED_STRATEGY_TOTAL}, got {count}"
    )


def test_live_db_bet1_count(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=1",
        (STRATEGY_ID,),
    ).fetchone()[0]
    assert count == EXPECTED_BET1_ROWS, f"bet1: expected {EXPECTED_BET1_ROWS}, got {count}"


def test_live_db_bet2_count(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=2",
        (STRATEGY_ID,),
    ).fetchone()[0]
    assert count == EXPECTED_BET2_ROWS, f"bet2: expected {EXPECTED_BET2_ROWS}, got {count}"


def test_live_db_bet3_count(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=3",
        (STRATEGY_ID,),
    ).fetchone()[0]
    assert count == EXPECTED_BET3_ROWS, f"bet3: expected {EXPECTED_BET3_ROWS}, got {count}"


def test_live_db_p131_preserved(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='acb_markov_midfreq_3bet'"
    ).fetchone()[0]
    assert count == EXPECTED_P131_TOTAL, (
        f"acb_markov_midfreq_3bet: expected {EXPECTED_P131_TOTAL}, got {count}"
    )


def test_live_db_p132_preserved(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='midfreq_fourier_mk_3bet'"
    ).fetchone()[0]
    assert count == EXPECTED_P132_TOTAL, (
        f"midfreq_fourier_mk_3bet: expected {EXPECTED_P132_TOTAL}, got {count}"
    )


def test_live_db_p133_preserved(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='pp3_freqort_4bet'"
    ).fetchone()[0]
    assert count == EXPECTED_P133_TOTAL, (
        f"pp3_freqort_4bet: expected {EXPECTED_P133_TOTAL}, got {count}"
    )


def test_live_db_controlled_apply_id_count(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
        (CONTROLLED_APPLY_ID,),
    ).fetchone()[0]
    assert count == EXPECTED_INSERT_ROWS, (
        f"controlled_apply_id rows: expected {EXPECTED_INSERT_ROWS}, got {count}"
    )


def test_live_db_lottery_type_all_power_lotto(db_conn):
    wrong = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id=? AND lottery_type!=?",
        (STRATEGY_ID, LOTTERY_TYPE),
    ).fetchone()[0]
    assert wrong == 0, f"{STRATEGY_ID} has {wrong} non-POWER_LOTTO rows"


def test_live_db_p10_p12_no_bi2_rows(db_conn):
    for sid in ("power_precision_3bet", "power_orthogonal_5bet"):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=2",
            (sid,),
        ).fetchone()[0]
        if sid == "power_precision_3bet":
            assert count == 1500, f"{sid} should have 1500 bi=2 rows post-P140, got {count}"
        else:
            assert count == 1500, f"{sid} post-P141 should have 1500 bi=2 rows, got {count}"


# ---------------------------------------------------------------------------
# 17. Drift guard subprocess test
# ---------------------------------------------------------------------------


def test_drift_guard_pass():
    result = subprocess.run(
        ["python3", "scripts/replay_lifecycle_drift_guard.py"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in result.stdout, (
        f"Drift guard failed:\n{result.stdout}\n{result.stderr}"
    )


def test_drift_guard_total_count():
    result = subprocess.run(
        ["python3", "scripts/replay_lifecycle_drift_guard.py"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert f"total={EXPECTED_ROWS_CURRENT}" in result.stdout, (
        f"Expected total={EXPECTED_ROWS_CURRENT} in drift guard output:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# 18. Markdown checks
# ---------------------------------------------------------------------------


def test_markdown_exists():
    assert MD_PATH.exists()


def test_markdown_has_classification():
    text = MD_PATH.read_text()
    assert "P134_FOURIER_RHYTHM_3BET_APPLIED" in text


def test_markdown_has_strategy_id():
    text = MD_PATH.read_text()
    assert STRATEGY_ID in text


def test_markdown_has_anomaly_section():
    text = MD_PATH.read_text()
    assert "Anomaly" in text or "anomaly" in text.lower()


def test_markdown_has_draw_ext():
    text = MD_PATH.read_text()
    assert DRAW_EXT_TARGET_DRAW in text


def test_markdown_has_wave2_completion():
    text = MD_PATH.read_text()
    assert "Wave 2" in text or "wave2" in text.lower()


def test_markdown_has_row_counts():
    text = MD_PATH.read_text()
    assert str(EXPECTED_ROWS_BEFORE) in text
    assert str(EXPECTED_ROWS_AFTER) in text


def test_markdown_has_controlled_apply_id():
    text = MD_PATH.read_text()
    assert CONTROLLED_APPLY_ID in text


# ---------------------------------------------------------------------------
# 19. No forbidden files staged
# ---------------------------------------------------------------------------


def test_no_forbidden_files_staged():
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    staged = result.stdout
    staged_a = [line[3:] for line in staged.splitlines() if line.startswith("A ")]
    assert not any("lottery_v2.db" in f for f in staged_a), (
        "DB should not be staged before commit"
    )
    for forbidden in [".history", ".pid", ".runtime"]:
        assert forbidden not in staged, f"Forbidden pattern '{forbidden}' in git status"
