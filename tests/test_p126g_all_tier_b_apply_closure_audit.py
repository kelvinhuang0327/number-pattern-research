"""
tests/test_p126g_all_tier_b_apply_closure_audit.py
===================================================
Regression tests for P126G: All Tier-B multi-bet apply closure audit.

Validates:
  - P126G JSON artifact exists with correct classification and all required fields
  - DB state: 72422 rows (post RSR-6 cleanup), bet_index column present
  - all_candidates_completion fields: 5/5 candidates, 18000 total inserted
  - Per-strategy bet_index distribution matches expected
  - Duplicate guard validation PASS
  - Drift guard result PASS
  - blocked_or_excluded includes all required governance fields
  - Markdown contains P126B/C/D/E/F completion summary
  - No additional apply executed in P126G
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
ARTIFACT    = REPO_ROOT / "outputs/replay/p126g_all_tier_b_apply_closure_audit_20260528.json"
MD_PATH     = REPO_ROOT / "docs/replay/p126g_all_tier_b_apply_closure_audit_20260528.md"
DB_PATH     = REPO_ROOT / "lottery_api/data/lottery_v2.db"
DRIFT_GUARD = REPO_ROOT / "scripts/replay_lifecycle_drift_guard.py"
PYTHON      = sys.executable

EXPECTED_TOTAL_ROWS             = 72462   # Historical: DB state when P126G artifact was generated
EXPECTED_TOTAL_ROWS_CURRENT     = 85924   # Post P134 apply (fourier_rhythm_3bet +3002)
EXPECTED_CANDIDATES             = 5
EXPECTED_TOTAL_INSERTED_P126B_F = 18000

STRATEGY_EXPECTED = {
    "power_fourier_rhythm_2bet":    {"total": 3000,  "bets": {1: 1500, 2: 1500}},
    "biglotto_echo_aware_3bet":     {"total": 4500,  "bets": {1: 1500, 2: 1500, 3: 1500}},
    "daily539_f4cold_3bet":         {"total": 4500,  "bets": {1: 1500, 2: 1500, 3: 1500}},
    "biglotto_ts3_markov_4bet_w30": {"total": 6000,  "bets": {1: 1500, 2: 1500, 3: 1500, 4: 1500}},
    "daily539_f4cold_5bet":         {"total": 7500,  "bets": {1: 1500, 2: 1500, 3: 1500, 4: 1500, 5: 1500}},
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT.exists(), f"P126G JSON not found: {ARTIFACT}"
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
    assert ARTIFACT.exists(), "P126G JSON artifact must exist"


def test_markdown_exists():
    assert MD_PATH.exists(), "P126G Markdown report must exist"


def test_task_id(artifact):
    assert artifact["task_id"] == "P126G"


def test_classification(artifact):
    assert artifact["classification"] == "P126G_ALL_TIER_B_MULTI_BET_APPLY_CLOSED"


def test_generated_at_present(artifact):
    assert "generated_at" in artifact and artifact["generated_at"]


# ---------------------------------------------------------------------------
# 2. Repo / worktree check
# ---------------------------------------------------------------------------
def test_worktree_pass(artifact):
    assert artifact["repo_worktree_check"]["pass"] is True


def test_worktree_branch(artifact):
    assert artifact["repo_worktree_check"]["branch"] == "claude/zen-gates-ff6802"


# ---------------------------------------------------------------------------
# 3. DB snapshot
# ---------------------------------------------------------------------------
def test_db_rows(artifact):
    assert artifact["db_snapshot"]["total_rows"] == EXPECTED_TOTAL_ROWS


def test_db_snapshot_pass(artifact):
    assert artifact["db_snapshot"]["pass"] is True


# ---------------------------------------------------------------------------
# 4. Schema check
# ---------------------------------------------------------------------------
def test_schema_bet_index_present(artifact):
    assert artifact["schema_check"]["bet_index_present"] is True


def test_schema_pass(artifact):
    assert artifact["schema_check"]["pass"] is True


# ---------------------------------------------------------------------------
# 5. Source artifact summary
# ---------------------------------------------------------------------------
def test_p126f_artifact_classification(artifact):
    assert artifact["source_artifact_summary"]["p126f"]["classification"] == "P126F_DAILY539_F4COLD_5BET_APPLIED"


def test_p126e_artifact_classification(artifact):
    assert artifact["source_artifact_summary"]["p126e"]["classification"] == "P126E_BIGLOTTO_TS3_MARKOV_4BET_W30_APPLIED"


def test_p126d_artifact_classification(artifact):
    assert artifact["source_artifact_summary"]["p126d"]["classification"] == "P126D_DAILY539_F4COLD_3BET_APPLIED"


def test_p126c_artifact_classification(artifact):
    assert artifact["source_artifact_summary"]["p126c"]["classification"] == "P126C_BIGLOTTO_ECHO_AWARE_3BET_APPLIED"


def test_p126b_artifact_classification(artifact):
    assert artifact["source_artifact_summary"]["p126b"]["classification"] == "P126B_POWER_FOURIER_RHYTHM_2BET_APPLIED"


def test_p129b_artifact_classification(artifact):
    assert artifact["source_artifact_summary"]["p129b"]["classification"] == "P129B_PRODUCTION_BET_INDEX_SCHEMA_MIGRATION_APPLIED"


# ---------------------------------------------------------------------------
# 6. All candidates completion
# ---------------------------------------------------------------------------
def test_total_candidates(artifact):
    assert artifact["all_candidates_completion"]["total_candidates"] == EXPECTED_CANDIDATES


def test_applied_candidates(artifact):
    assert artifact["all_candidates_completion"]["applied_candidates"] == EXPECTED_CANDIDATES


def test_remaining_candidates_zero(artifact):
    assert artifact["all_candidates_completion"]["remaining_candidates"] == 0


def test_baseline_rows_before_p126(artifact):
    assert artifact["all_candidates_completion"]["baseline_rows_before_p126_apply"] == 54462


def test_final_replay_rows(artifact):
    assert artifact["all_candidates_completion"]["final_replay_rows"] == EXPECTED_TOTAL_ROWS


def test_total_inserted_rows(artifact):
    assert artifact["all_candidates_completion"]["total_inserted_rows_from_p126b_to_p126f"] == EXPECTED_TOTAL_INSERTED_P126B_F


def test_p126b_rows(artifact):
    assert artifact["all_candidates_completion"]["p126b_rows"] == 1500


def test_p126c_rows(artifact):
    assert artifact["all_candidates_completion"]["p126c_rows"] == 3000


def test_p126d_rows(artifact):
    assert artifact["all_candidates_completion"]["p126d_rows"] == 3000


def test_p126e_rows(artifact):
    assert artifact["all_candidates_completion"]["p126e_rows"] == 4500


def test_p126f_rows(artifact):
    assert artifact["all_candidates_completion"]["p126f_rows"] == 6000


# ---------------------------------------------------------------------------
# 7. Strategy distribution (artifact)
# ---------------------------------------------------------------------------
def test_strategy_distribution_pass(artifact):
    assert artifact["strategy_distribution"]["pass"] is True


@pytest.mark.parametrize("strategy_id,expected_total", [
    ("power_fourier_rhythm_2bet",    3000),
    ("biglotto_echo_aware_3bet",     4500),
    ("daily539_f4cold_3bet",         4500),
    ("biglotto_ts3_markov_4bet_w30", 6000),
    ("daily539_f4cold_5bet",         7500),
])
def test_strategy_total_rows(artifact, strategy_id, expected_total):
    strategies = artifact["strategy_distribution"]["strategies"]
    assert strategy_id in strategies, f"Strategy {strategy_id} not in distribution"
    assert strategies[strategy_id]["total_rows"] == expected_total


# ---------------------------------------------------------------------------
# 8. Duplicate guard validation
# ---------------------------------------------------------------------------
def test_duplicate_guard_pass(artifact):
    assert artifact["duplicate_guard_validation"]["pass"] is True


def test_duplicate_guard_zero_duplicates(artifact):
    assert artifact["duplicate_guard_validation"]["duplicate_tuples_found"] == 0


# ---------------------------------------------------------------------------
# 9. Drift guard result
# ---------------------------------------------------------------------------
def test_drift_guard_pass(artifact):
    assert artifact["drift_guard_result"]["pass"] is True


def test_drift_guard_classification(artifact):
    assert artifact["drift_guard_result"]["classification"] == "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS"


# ---------------------------------------------------------------------------
# 10. blocked_or_excluded governance
# ---------------------------------------------------------------------------
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
    assert artifact["blocked_or_excluded"]["no_lifecycle_mutation"] is True


def test_blocked_no_additional_apply(artifact):
    assert artifact["blocked_or_excluded"]["no_additional_apply_executed_in_P126G"] is True


def test_blocked_no_db_writes(artifact):
    assert artifact["blocked_or_excluded"]["no_db_writes_in_P126G"] is True


# ---------------------------------------------------------------------------
# 11. Markdown content checks
# ---------------------------------------------------------------------------
def test_markdown_contains_p126b(artifact):
    md = MD_PATH.read_text()
    assert "P126B" in md


def test_markdown_contains_p126c(artifact):
    md = MD_PATH.read_text()
    assert "P126C" in md


def test_markdown_contains_p126d(artifact):
    md = MD_PATH.read_text()
    assert "P126D" in md


def test_markdown_contains_p126e(artifact):
    md = MD_PATH.read_text()
    assert "P126E" in md


def test_markdown_contains_p126f(artifact):
    md = MD_PATH.read_text()
    assert "P126F" in md


def test_markdown_contains_classification(artifact):
    md = MD_PATH.read_text()
    assert "P126G_ALL_TIER_B_MULTI_BET_APPLY_CLOSED" in md


# ---------------------------------------------------------------------------
# 12. Live DB checks
# ---------------------------------------------------------------------------
def test_live_db_total_rows(db_conn):
    count = db_conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    assert count == EXPECTED_TOTAL_ROWS_CURRENT, f"Expected {EXPECTED_TOTAL_ROWS_CURRENT}, got {count}"


def test_live_db_bet_index_column(db_conn):
    cols = [row[1] for row in db_conn.execute("PRAGMA table_info(strategy_prediction_replays)")]
    assert "bet_index" in cols


@pytest.mark.parametrize("strategy_id,expected_total", [
    ("power_fourier_rhythm_2bet",    3000),
    ("biglotto_echo_aware_3bet",     4500),
    ("daily539_f4cold_3bet",         4500),
    ("biglotto_ts3_markov_4bet_w30", 6000),
    ("daily539_f4cold_5bet",         7500),
])
def test_live_db_strategy_rows(db_conn, strategy_id, expected_total):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
        (strategy_id,)
    ).fetchone()[0]
    assert count == expected_total, f"{strategy_id}: expected {expected_total}, got {count}"


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


# ---------------------------------------------------------------------------
# 13. Drift guard live run
# ---------------------------------------------------------------------------
def test_drift_guard_live():
    result = subprocess.run(
        [PYTHON, str(DRIFT_GUARD)],
        capture_output=True, text=True, timeout=60, cwd=REPO_ROOT
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, f"Drift guard failed (rc={result.returncode}): {output[-500:]}"
    assert "PASS" in output.upper(), f"Drift guard did not report PASS: {output[-500:]}"
