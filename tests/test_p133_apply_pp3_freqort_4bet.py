"""
tests/test_p133_apply_pp3_freqort_4bet.py
==========================================
Regression tests for P133: pp3_freqort_4bet (POWER_LOTTO)
Wave-2 controlled apply — bet-2 + bet-3 + bet-4 insert verification.

Validates:
  - P133 JSON artifact exists with correct classification and all required fields
  - Authorization gate: exact phrase present, apply_allowed=True
  - Backup created with 78422 rows before apply
  - 4500 rows inserted (1500 bet-2, 1500 bet-3, 1500 bet-4) for POWER_LOTTO pp3_freqort_4bet
  - DB: 78422 → 82922 rows
  - bet_index distribution: bet1=1500, bet2=1500, bet3=1500, bet4=1500
  - P131 acb_markov_midfreq_3bet rows preserved at 4500
  - P132 midfreq_fourier_mk_3bet rows preserved at 4500
  - Duplicate guard PASS (0 duplicates, P9 not inserted)
  - Drift guard PASS
  - blocked_or_excluded: P9/P10/P12/4_STAR/P108/P117/P118 all confirmed
  - Markdown report exists with correct content
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
REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT  = REPO_ROOT / "outputs/replay/p133_apply_pp3_freqort_4bet_20260528.json"
MD_PATH   = REPO_ROOT / "docs/replay/p133_apply_pp3_freqort_4bet_20260528.md"
DB_PATH   = REPO_ROOT / "lottery_api/data/lottery_v2.db"
DRIFT_GUARD = REPO_ROOT / "scripts/replay_lifecycle_drift_guard.py"
PYTHON    = sys.executable

EXPECTED_DB_ROWS_BEFORE   = 78422
EXPECTED_DB_ROWS_AFTER    = 82922
EXPECTED_INSERT_ROWS      = 4500
EXPECTED_BET2_ROWS        = 1500
EXPECTED_BET3_ROWS        = 1500
EXPECTED_BET4_ROWS        = 1500
EXPECTED_PP3_TOTAL        = 6000   # 1500×4 bets
EXPECTED_P131_TOTAL       = 4500   # acb_markov_midfreq_3bet preserved
EXPECTED_P132_TOTAL       = 4500   # midfreq_fourier_mk_3bet preserved

STRATEGY_ID         = "pp3_freqort_4bet"
LOTTERY_TYPE        = "POWER_LOTTO"
CONTROLLED_APPLY_ID = "P133_PP3_FREQORT_4BET_POWERLOTTO_V20260528"
P131_APPLY_ID       = "P131_ACB_MARKOV_MIDFREQ_3BET_DAILY539_V20260528"
P132_APPLY_ID       = "P132_MIDFREQ_FOURIER_MK_3BET_POWERLOTTO_V20260528"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT.exists(), f"P133 JSON not found: {ARTIFACT}"
    with ARTIFACT.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def db_conn():
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# 1. Artifact existence and top-level identity
# ---------------------------------------------------------------------------
def test_artifact_exists():
    assert ARTIFACT.exists(), "P133 JSON artifact must exist"


def test_markdown_exists():
    assert MD_PATH.exists(), "P133 Markdown report must exist"


def test_task_id(artifact):
    assert artifact["task_id"] == "P133"


def test_classification(artifact):
    assert artifact["classification"] == "P133_PP3_FREQORT_4BET_APPLIED"


def test_generated_at_present(artifact):
    assert "generated_at" in artifact and artifact["generated_at"]


# ---------------------------------------------------------------------------
# 2. Authorization gate
# ---------------------------------------------------------------------------
def test_authorization_present(artifact):
    assert artifact["authorization"]["authorization_present"] is True


def test_apply_allowed(artifact):
    assert artifact["authorization"]["apply_allowed"] is True


def test_authorization_phrase(artifact):
    expected = "P130_AUTHORIZED_APPLY_PP3_FREQORT_4BET_POWERLOTTO_BET2_BET3_BET4_V20260528"
    assert artifact["authorization"]["authorization_text_observed"] == expected


def test_stop_reason_null(artifact):
    assert artifact["authorization"]["stop_reason"] is None


# ---------------------------------------------------------------------------
# 3. Worktree check
# ---------------------------------------------------------------------------
def test_worktree_confirmed(artifact):
    assert artifact["repo_worktree_check"]["worktree_confirmed"] is True


# ---------------------------------------------------------------------------
# 4. DB snapshot before
# ---------------------------------------------------------------------------
def test_db_rows_before(artifact):
    assert artifact["db_snapshot_before"]["replay_rows"] == EXPECTED_DB_ROWS_BEFORE


def test_db_before_has_bet_index(artifact):
    assert artifact["db_snapshot_before"]["has_bet_index_column"] is True


def test_db_before_pp3_rows(artifact):
    assert artifact["db_snapshot_before"]["pp3_freqort_4bet_rows"] == 1500


def test_db_before_p131_acb_rows(artifact):
    assert artifact["db_snapshot_before"]["acb_markov_midfreq_3bet_rows"] == EXPECTED_P131_TOTAL


def test_db_before_p132_midfreq_rows(artifact):
    assert artifact["db_snapshot_before"]["midfreq_fourier_mk_3bet_rows"] == EXPECTED_P132_TOTAL


# ---------------------------------------------------------------------------
# 5. Backup
# ---------------------------------------------------------------------------
def test_backup_created(artifact):
    assert artifact["backup"]["backup_created"] is True


def test_backup_row_count(artifact):
    assert artifact["backup"]["backup_row_count"] == EXPECTED_DB_ROWS_BEFORE


def test_backup_ok(artifact):
    assert artifact["backup"]["backup_ok"] is True


def test_backup_file_exists(artifact):
    backup_path = Path(artifact["backup"]["backup_path"])
    assert backup_path.exists(), f"Backup file not found: {backup_path}"


def test_rollback_command_present(artifact):
    assert artifact["backup"]["rollback_command"]
    assert "cp" in artifact["backup"]["rollback_command"]


# ---------------------------------------------------------------------------
# 6. Source artifact summaries
# ---------------------------------------------------------------------------
def test_p132_classification(artifact):
    assert artifact["p132_source_summary"]["classification"] == "P132_MIDFREQ_FOURIER_MK_3BET_APPLIED"


def test_p132_classification_pass(artifact):
    assert artifact["p132_source_summary"]["classification_pass"] is True


def test_p131_classification(artifact):
    assert artifact["p131_source_summary"]["classification"] == "P131_ACB_MARKOV_MIDFREQ_3BET_APPLIED"


def test_p131_classification_pass(artifact):
    assert artifact["p131_source_summary"]["classification_pass"] is True


def test_p130_classification(artifact):
    assert artifact["p130_source_summary"]["classification"] == "P130_WAVE2_SAFE_CANDIDATES_DRY_RUN_PLAN_READY"


def test_p130_p11_in_safe_candidates(artifact):
    assert artifact["p130_source_summary"]["p11_in_safe_candidates"] is True


def test_p130_p11_apply_ready(artifact):
    assert artifact["p130_source_summary"]["p11_apply_ready"] is True


def test_p130_p11_estimated_rows(artifact):
    assert artifact["p130_source_summary"]["p11_estimated_insert_rows"] == EXPECTED_INSERT_ROWS


def test_p130_p11_conflict_free(artifact):
    assert artifact["p130_source_summary"]["p11_conflict_free"] is True


# ---------------------------------------------------------------------------
# 7. Apply scope
# ---------------------------------------------------------------------------
def test_apply_strategy_id(artifact):
    assert artifact["apply_scope"]["strategy_id"] == STRATEGY_ID


def test_apply_lottery_type(artifact):
    assert artifact["apply_scope"]["lottery_type"] == LOTTERY_TYPE


def test_apply_expected_insert_rows(artifact):
    assert artifact["apply_scope"]["expected_insert_rows"] == EXPECTED_INSERT_ROWS


def test_apply_actual_insert_rows(artifact):
    assert artifact["apply_scope"]["actual_insert_rows"] == EXPECTED_INSERT_ROWS


def test_apply_target_bet_count(artifact):
    assert artifact["apply_scope"]["target_bet_count"] == 4


def test_apply_bet2_rows(artifact):
    assert artifact["apply_scope"]["bet2_rows_inserted"] == EXPECTED_BET2_ROWS


def test_apply_bet3_rows(artifact):
    assert artifact["apply_scope"]["bet3_rows_inserted"] == EXPECTED_BET3_ROWS


def test_apply_bet4_rows(artifact):
    assert artifact["apply_scope"]["bet4_rows_inserted"] == EXPECTED_BET4_ROWS


def test_apply_controlled_apply_id(artifact):
    assert artifact["apply_scope"]["controlled_apply_id"] == CONTROLLED_APPLY_ID


def test_apply_executed(artifact):
    assert artifact["apply_scope"]["apply_executed"] is True


def test_apply_adapter_function(artifact):
    assert artifact["apply_scope"]["adapter_function"] == "get_all_bets_pp3_freqort"


# ---------------------------------------------------------------------------
# 8. Inserted rows summary
# ---------------------------------------------------------------------------
def test_total_rows_inserted(artifact):
    assert artifact["inserted_rows_summary"]["total_rows_inserted"] == EXPECTED_INSERT_ROWS


def test_bet2_rows_inserted(artifact):
    assert artifact["inserted_rows_summary"]["bet2_rows_inserted"] == EXPECTED_BET2_ROWS


def test_bet3_rows_inserted(artifact):
    assert artifact["inserted_rows_summary"]["bet3_rows_inserted"] == EXPECTED_BET3_ROWS


def test_bet4_rows_inserted(artifact):
    assert artifact["inserted_rows_summary"]["bet4_rows_inserted"] == EXPECTED_BET4_ROWS


def test_inserted_not_dry_run(artifact):
    assert artifact["inserted_rows_summary"]["dry_run"] is False


# ---------------------------------------------------------------------------
# 9. Duplicate guard
# ---------------------------------------------------------------------------
def test_duplicate_guard_ok(artifact):
    assert artifact["duplicate_guard"]["guard_ok"] is True


def test_duplicate_guard_other_candidates_untouched(artifact):
    extras = artifact["duplicate_guard"]["other_candidates_extra_inserted"]
    for strategy_id, extra_count in extras.items():
        assert extra_count == 0, f"{strategy_id} had {extra_count} unexpected extra rows"


def test_duplicate_guard_other_wave2_untouched(artifact):
    assert artifact["duplicate_guard"]["other_wave2_untouched"] is True


# ---------------------------------------------------------------------------
# 10. Bet-index validation
# ---------------------------------------------------------------------------
def test_bet_index_bet1_count(artifact):
    assert artifact["bet_index_validation"]["bet1_count"] == 1500


def test_bet_index_bet2_count(artifact):
    assert artifact["bet_index_validation"]["bet2_count"] == 1500


def test_bet_index_bet3_count(artifact):
    assert artifact["bet_index_validation"]["bet3_count"] == 1500


def test_bet_index_bet4_count(artifact):
    assert artifact["bet_index_validation"]["bet4_count"] == 1500


def test_bet_index_distribution_ok(artifact):
    assert artifact["bet_index_validation"]["distribution_ok"] is True


def test_bet_index_all_power_lotto(artifact):
    assert artifact["bet_index_validation"]["all_rows_power_lotto"] is True


def test_bet_index_validation_pass(artifact):
    assert artifact["bet_index_validation"]["validation"] == "PASS"


# ---------------------------------------------------------------------------
# 11. DB snapshot after
# ---------------------------------------------------------------------------
def test_db_rows_after(artifact):
    assert artifact["db_snapshot_after"]["replay_rows"] == EXPECTED_DB_ROWS_AFTER


def test_db_after_pp3_total(artifact):
    assert artifact["db_snapshot_after"]["pp3_freqort_4bet_rows"] == EXPECTED_PP3_TOTAL


def test_db_after_p131_preserved(artifact):
    assert artifact["db_snapshot_after"]["acb_markov_midfreq_3bet_rows"] == EXPECTED_P131_TOTAL


def test_db_after_p132_preserved(artifact):
    assert artifact["db_snapshot_after"]["midfreq_fourier_mk_3bet_rows"] == EXPECTED_P132_TOTAL


def test_db_after_other_wave2_zero(artifact):
    extras = artifact["db_snapshot_after"]["other_wave2_extra"]
    for sid, cnt in extras.items():
        assert cnt == 0, f"{sid} had {cnt} unexpected rows in P133 scope"


# ---------------------------------------------------------------------------
# 12. Row preservation
# ---------------------------------------------------------------------------
def test_row_preservation_before(artifact):
    assert artifact["row_preservation_check"]["rows_before_apply"] == EXPECTED_DB_ROWS_BEFORE


def test_row_preservation_inserted(artifact):
    assert artifact["row_preservation_check"]["rows_inserted"] == EXPECTED_INSERT_ROWS


def test_row_preservation_after(artifact):
    assert artifact["row_preservation_check"]["actual_rows_after"] == EXPECTED_DB_ROWS_AFTER


def test_row_preservation_ok(artifact):
    assert artifact["row_preservation_check"]["rows_preserved_ok"] is True


def test_p131_rows_preserved_flag(artifact):
    assert artifact["row_preservation_check"]["p131_rows_preserved"] is True


def test_p131_acb_total_preserved(artifact):
    assert artifact["row_preservation_check"]["p131_acb_total"] == EXPECTED_P131_TOTAL


def test_p131_acb_bet1(artifact):
    assert artifact["row_preservation_check"]["p131_acb_bet1"] == 1500


def test_p131_acb_bet2(artifact):
    assert artifact["row_preservation_check"]["p131_acb_bet2"] == 1500


def test_p131_acb_bet3(artifact):
    assert artifact["row_preservation_check"]["p131_acb_bet3"] == 1500


def test_p132_rows_preserved_flag(artifact):
    assert artifact["row_preservation_check"]["p132_rows_preserved"] is True


def test_p132_midfreq_total_preserved(artifact):
    assert artifact["row_preservation_check"]["p132_midfreq_total"] == EXPECTED_P132_TOTAL


def test_p132_midfreq_bet1(artifact):
    assert artifact["row_preservation_check"]["p132_midfreq_bet1"] == 1500


def test_p132_midfreq_bet2(artifact):
    assert artifact["row_preservation_check"]["p132_midfreq_bet2"] == 1500


def test_p132_midfreq_bet3(artifact):
    assert artifact["row_preservation_check"]["p132_midfreq_bet3"] == 1500


# ---------------------------------------------------------------------------
# 13. Blocked / excluded governance
# ---------------------------------------------------------------------------
def test_blocked_p9_not_applied(artifact):
    assert artifact["blocked_or_excluded"]["P9_fourier_rhythm_not_applied"] is True


def test_blocked_p10_p12(artifact):
    assert artifact["blocked_or_excluded"]["P10_P12_not_apply_ready_until_re_evaluation"] is True


def test_blocked_4star(artifact):
    assert artifact["blocked_or_excluded"]["4_STAR_excluded"] is True


def test_blocked_p108(artifact):
    assert artifact["blocked_or_excluded"]["P108_not_run"] is True


def test_blocked_p117(artifact):
    assert artifact["blocked_or_excluded"]["P117_not_run"] is True


def test_blocked_p118(artifact):
    assert artifact["blocked_or_excluded"]["P118_not_run"] is True


def test_blocked_no_scheduler(artifact):
    assert artifact["blocked_or_excluded"]["no_scheduler_install"] is True


def test_blocked_no_lifecycle(artifact):
    assert artifact["blocked_or_excluded"]["no_lifecycle_champion_registry_mutation"] is True


def test_blocked_p9_untouched_verified(artifact):
    assert artifact["blocked_or_excluded"]["p9_untouched_verified"] is True


def test_blocked_p10_p12_untouched_verified(artifact):
    assert artifact["blocked_or_excluded"]["p10_p12_untouched_verified"] is True


# ---------------------------------------------------------------------------
# 14. Drift guard update (artifact)
# ---------------------------------------------------------------------------
def test_drift_guard_previous_total(artifact):
    assert artifact["drift_guard_update"]["previous_total"] == EXPECTED_DB_ROWS_BEFORE


def test_drift_guard_new_total(artifact):
    assert artifact["drift_guard_update"]["new_total"] == EXPECTED_DB_ROWS_AFTER


def test_drift_guard_rows_added(artifact):
    assert artifact["drift_guard_update"]["rows_added"] == EXPECTED_INSERT_ROWS


def test_drift_guard_update_required(artifact):
    assert artifact["drift_guard_update"]["update_required"] is True


# ---------------------------------------------------------------------------
# 15. Markdown content
# ---------------------------------------------------------------------------
def test_markdown_contains_classification():
    md = MD_PATH.read_text()
    assert "P133_PP3_FREQORT_4BET_APPLIED" in md


def test_markdown_contains_strategy():
    md = MD_PATH.read_text()
    assert "pp3_freqort_4bet" in md


def test_markdown_contains_rows():
    md = MD_PATH.read_text()
    assert "82922" in md


def test_markdown_contains_p131():
    md = MD_PATH.read_text()
    assert "P131" in md


def test_markdown_contains_p132():
    md = MD_PATH.read_text()
    assert "P132" in md


def test_markdown_contains_backup():
    md = MD_PATH.read_text()
    assert "backup" in md.lower() or "Backup" in md


def test_markdown_contains_rollback():
    md = MD_PATH.read_text()
    assert "rollback" in md.lower() or "Rollback" in md or "cp '" in md


# ---------------------------------------------------------------------------
# 16. Live DB checks
# ---------------------------------------------------------------------------
def test_live_db_total_rows(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    assert count == EXPECTED_DB_ROWS_AFTER, f"Expected {EXPECTED_DB_ROWS_AFTER}, got {count}"


def test_live_db_pp3_total(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
        (STRATEGY_ID,),
    ).fetchone()[0]
    assert count == EXPECTED_PP3_TOTAL, f"{STRATEGY_ID}: expected {EXPECTED_PP3_TOTAL}, got {count}"


def test_live_db_pp3_bet1(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=1",
        (STRATEGY_ID,),
    ).fetchone()[0]
    assert count == 1500, f"{STRATEGY_ID} bet_index=1: expected 1500, got {count}"


def test_live_db_pp3_bet2(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=2",
        (STRATEGY_ID,),
    ).fetchone()[0]
    assert count == 1500, f"{STRATEGY_ID} bet_index=2: expected 1500, got {count}"


def test_live_db_pp3_bet3(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=3",
        (STRATEGY_ID,),
    ).fetchone()[0]
    assert count == 1500, f"{STRATEGY_ID} bet_index=3: expected 1500, got {count}"


def test_live_db_pp3_bet4(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=4",
        (STRATEGY_ID,),
    ).fetchone()[0]
    assert count == 1500, f"{STRATEGY_ID} bet_index=4: expected 1500, got {count}"


def test_live_db_pp3_all_power_lotto(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND lottery_type != 'POWER_LOTTO'",
        (STRATEGY_ID,),
    ).fetchone()[0]
    assert count == 0, f"{STRATEGY_ID} must all be POWER_LOTTO, found {count} non-POWER_LOTTO rows"


def test_live_db_pp3_controlled_apply_id(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index>1 AND controlled_apply_id=?",
        (STRATEGY_ID, CONTROLLED_APPLY_ID),
    ).fetchone()[0]
    assert count == EXPECTED_INSERT_ROWS, f"controlled_apply_id rows: expected {EXPECTED_INSERT_ROWS}, got {count}"


def test_live_db_p131_acb_preserved(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='acb_markov_midfreq_3bet'",
    ).fetchone()[0]
    assert count == EXPECTED_P131_TOTAL, f"P131 acb_markov_midfreq_3bet: expected {EXPECTED_P131_TOTAL}, got {count}"


def test_live_db_p132_midfreq_preserved(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='midfreq_fourier_mk_3bet'",
    ).fetchone()[0]
    assert count == EXPECTED_P132_TOTAL, f"P132 midfreq_fourier_mk_3bet: expected {EXPECTED_P132_TOTAL}, got {count}"


def test_live_db_p9_not_applied(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='fourier_rhythm_3bet' AND bet_index > 1",
    ).fetchone()[0]
    assert count == 0, f"P9 fourier_rhythm_3bet bet_index>1 must be 0, got {count}"


def test_live_db_p10_not_applied(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_precision_3bet' AND bet_index > 1",
    ).fetchone()[0]
    assert count == 0, f"P10 power_precision_3bet bet_index>1 must be 0, got {count}"


def test_live_db_p12_not_applied(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_orthogonal_5bet' AND bet_index > 1",
    ).fetchone()[0]
    assert count == 0, f"P12 power_orthogonal_5bet bet_index>1 must be 0, got {count}"


def test_live_db_no_duplicates(db_conn):
    dup = db_conn.execute(
        "SELECT COUNT(*) FROM ("
        "  SELECT lottery_type, target_draw, strategy_id, bet_index, COUNT(*) AS cnt "
        "  FROM strategy_prediction_replays "
        "  GROUP BY lottery_type, target_draw, strategy_id, bet_index "
        "  HAVING cnt > 1"
        ")"
    ).fetchone()[0]
    assert dup == 0, f"Duplicate rows found: {dup}"


def test_live_db_bet_index_column(db_conn):
    cols = [row[1] for row in db_conn.execute("PRAGMA table_info(strategy_prediction_replays)")]
    assert "bet_index" in cols


# ---------------------------------------------------------------------------
# 17. Drift guard live run
# ---------------------------------------------------------------------------
def test_drift_guard_live():
    result = subprocess.run(
        [PYTHON, str(DRIFT_GUARD)],
        capture_output=True, text=True, timeout=60, cwd=REPO_ROOT
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, f"Drift guard failed (rc={result.returncode}): {output[-500:]}"
    assert "PASS" in output.upper(), f"Drift guard did not report PASS: {output[-500:]}"


# ---------------------------------------------------------------------------
# 18. No forbidden staging check
# ---------------------------------------------------------------------------
def test_no_history_files_in_repo():
    import subprocess as sp
    result = sp.run(
        ["git", "status", "--short"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    staged = result.stdout
    for forbidden in [".history", ".pid", ".runtime"]:
        assert forbidden not in staged, f"Forbidden file pattern '{forbidden}' found in git status"
