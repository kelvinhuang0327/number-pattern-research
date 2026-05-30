"""
P147 Champion Evaluation Gate Readiness Audit — pytest test suite.

Tests verify:
- JSON artifact exists with correct structure and values
- DB snapshot matches expected state (live query)
- All 6 champion candidate strategies are BLOCKED
- Zero LIVE_MONITORING_VERIFIED records
- No forbidden files staged
- Markdown artifact contains required sections
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
JSON_PATH = os.path.join(
    REPO_ROOT,
    "outputs/replay/p147_champion_evaluation_gate_readiness_audit_20260529.json",
)
MD_PATH = os.path.join(
    REPO_ROOT,
    "docs/replay/p147_champion_evaluation_gate_readiness_audit_20260529.md",
)
DB_PATH = os.path.join(REPO_ROOT, "lottery_api/data/lottery_v2.db")

EXPECTED_STRATEGIES = {
    "acb_markov_midfreq_3bet",
    "midfreq_fourier_mk_3bet",
    "fourier_rhythm_3bet",
    "pp3_freqort_4bet",
    "power_precision_3bet",
    "power_orthogonal_5bet",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def artifact():
    assert os.path.exists(JSON_PATH), f"P147 JSON not found: {JSON_PATH}"
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_content():
    assert os.path.exists(MD_PATH), f"P147 Markdown not found: {MD_PATH}"
    with open(MD_PATH) as f:
        return f.read()


@pytest.fixture(scope="module")
def db_conn():
    con = sqlite3.connect(DB_PATH)
    yield con
    con.close()


# ---------------------------------------------------------------------------
# JSON artifact tests
# ---------------------------------------------------------------------------


def test_json_exists():
    assert os.path.exists(JSON_PATH), f"P147 JSON artifact missing: {JSON_PATH}"


def test_task_id(artifact):
    assert artifact["task_id"] == "P147"


def test_classification(artifact):
    assert (
        artifact["classification"]
        == "P147_CHAMPION_EVALUATION_BLOCKED_PENDING_LIVE_MONITORING_VERIFIED"
    )


def test_repo_ok(artifact):
    assert artifact["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(artifact):
    assert artifact["repo_branch_check"]["branch_ok"] is True


def test_db_total_rows_artifact(artifact):
    assert artifact["db_snapshot"]["total_rows"] == 94924


def test_db_total_rows_live(db_conn):
    """Query live DB to confirm 94924 rows."""
    cur = db_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    count = cur.fetchone()[0]
    assert count == 94924, f"DB row count is {count}, expected 94924"


def test_bet_index_column_exists(db_conn):
    """Confirm bet_index column exists in live DB."""
    cur = db_conn.cursor()
    cur.execute("PRAGMA table_info(strategy_prediction_replays)")
    cols = [row[1] for row in cur.fetchall()]
    assert "bet_index" in cols, "bet_index column missing from strategy_prediction_replays"


def test_p144d_classification(artifact):
    assert (
        artifact["p144d_source_summary"]["classification"]
        == "P144D_LEGACY_UNVERIFIED_KEEP_GOVERNED_BASELINE_DECISION_RECORDED"
    )


def test_p146b_classification(artifact):
    assert (
        artifact["p146b_source_summary"]["classification"]
        == "P146B_AUTHORIZED_OBSERVATION_ONLY_MONITORING_RUN_COMPLETED"
    )


def test_candidate_strategy_inventory_count(artifact):
    assert len(artifact["candidate_strategy_inventory"]) == 6


def test_candidate_strategies_all_present(artifact):
    found = {s["strategy_id"] for s in artifact["candidate_strategy_inventory"]}
    assert found == EXPECTED_STRATEGIES, f"Missing/extra strategies: {found ^ EXPECTED_STRATEGIES}"


def test_live_monitoring_verified_records_found_zero(artifact):
    assert artifact["monitoring_evidence_audit"]["live_monitoring_verified_records_found"] == 0


def test_live_evidence_available_false(artifact):
    assert artifact["monitoring_evidence_audit"]["live_evidence_available"] is False


def test_champion_evaluation_allowed_false(artifact):
    assert artifact["champion_gate_decision"]["champion_evaluation_allowed"] is False


def test_champion_promotion_allowed_false(artifact):
    assert artifact["champion_gate_decision"]["champion_promotion_allowed"] is False


def test_registry_update_allowed_false(artifact):
    assert artifact["champion_gate_decision"]["registry_update_allowed"] is False


def test_blocked_reason_mentions_live_monitoring_verified(artifact):
    reason = artifact["champion_gate_decision"]["blocked_reason"]
    assert "LIVE_MONITORING_VERIFIED" in reason, (
        f"Expected 'LIVE_MONITORING_VERIFIED' in blocked_reason, got: {reason}"
    )


def test_legacy_unverified_total_rows(artifact):
    assert (
        artifact["legacy_unverified_governed_baseline_policy"]["total_legacy_unverified_rows"]
        == 100
    )


def test_legacy_unverified_excluded_from_champion_eval(artifact):
    assert (
        artifact["legacy_unverified_governed_baseline_policy"]["exclude_from_champion_evaluation"]
        is True
    )


def test_legacy_unverified_does_not_block_live_monitoring(artifact):
    assert (
        artifact["legacy_unverified_governed_baseline_policy"]["live_monitoring_blocked_by_legacy_rows"]
        is False
    )


def test_non_actions_db_write_false(artifact):
    assert artifact["non_actions"]["db_write_in_p147"] is False


def test_non_actions_registry_update_false(artifact):
    assert artifact["non_actions"]["registry_update_executed_in_p147"] is False


def test_non_actions_champion_promotion_false(artifact):
    assert artifact["non_actions"]["champion_promotion_executed_in_p147"] is False


def test_dirty_file_hygiene_backups_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


# ---------------------------------------------------------------------------
# Markdown artifact tests
# ---------------------------------------------------------------------------


def test_markdown_exists(md_content):
    assert len(md_content) > 0, "Markdown file is empty"


def test_markdown_contains_champion_gate_decision(md_content):
    assert "champion gate decision" in md_content.lower(), (
        "Markdown missing 'champion gate decision' section"
    )


def test_markdown_contains_non_actions(md_content):
    assert (
        "non-actions" in md_content.lower() or "non_actions" in md_content.lower()
    ), "Markdown missing 'non-actions' / 'non_actions' section"


def test_markdown_contains_final_classification(md_content):
    assert "P147_CHAMPION_EVALUATION_BLOCKED_PENDING_LIVE_MONITORING_VERIFIED" in md_content


# ---------------------------------------------------------------------------
# Forbidden staging check
# ---------------------------------------------------------------------------


def test_no_forbidden_files_staged():
    """Ensure lottery_v2.db and replay_lifecycle_drift_guard.py are not staged."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    staged_files = result.stdout.strip().splitlines()

    forbidden = ["lottery_v2.db", "replay_lifecycle_drift_guard.py"]
    for f in forbidden:
        assert not any(f in s for s in staged_files), (
            f"Forbidden file staged: {f}. Staged files: {staged_files}"
        )


# ---------------------------------------------------------------------------
# Live DB: zero LIVE_MONITORING_VERIFIED
# ---------------------------------------------------------------------------


def test_live_db_zero_live_monitoring_verified(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE truth_level='LIVE_MONITORING_VERIFIED'"
    )
    count = cur.fetchone()[0]
    assert count == 0, f"Expected 0 LIVE_MONITORING_VERIFIED rows, found {count}"


# ---------------------------------------------------------------------------
# All 6 strategies blocked in matrix
# ---------------------------------------------------------------------------


def test_all_strategies_blocked_in_matrix(artifact):
    matrix = artifact["champion_evaluation_readiness_matrix"]
    assert len(matrix) == 6
    for entry in matrix:
        assert entry["champion_eval_ready"] is False, (
            f"{entry['strategy_id']} has champion_eval_ready=True"
        )
        assert entry["promotion_allowed"] is False, (
            f"{entry['strategy_id']} has promotion_allowed=True"
        )
        assert entry["registry_update_allowed"] is False, (
            f"{entry['strategy_id']} has registry_update_allowed=True"
        )
