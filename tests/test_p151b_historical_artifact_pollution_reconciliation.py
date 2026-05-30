"""Tests for P151B historical artifact pollution reconciliation artifact."""

import json
from pathlib import Path

import pytest

ARTIFACT_PATH = Path(__file__).parent.parent / "outputs/replay/p151b_historical_artifact_pollution_reconciliation_20260529.json"

VALID_CLASSIFICATIONS = {
    "P151B_HISTORICAL_ARTIFACT_POLLUTION_RECONCILED_READY_FOR_P151",
    "P151B_STOP_DIRTY_SCOPE_EXCEEDS_AUTHORIZATION",
    "P151B_STOP_PREFLIGHT_MISMATCH",
}

CANONICAL_REPO = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

AUTHORIZED_RESTORE_FILES = [
    "docs/replay/p145b_manual_on_demand_monitoring_authorization_gate_20260529.md",
    "docs/replay/p146a_observation_only_live_monitoring_runner_20260529.md",
    "outputs/replay/p145b_manual_on_demand_monitoring_authorization_gate_20260529.json",
    "outputs/replay/p146a_observation_only_live_monitoring_runner_20260529.json",
    "outputs/replay/live_monitoring_observation_only/smoke_test/smoke_mock_acb_markov_midfreq_3bet_20260529.json",
]


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_PATH.exists(), f"P151B artifact missing: {ARTIFACT_PATH}"
    return json.loads(ARTIFACT_PATH.read_text())


def test_artifact_exists():
    assert ARTIFACT_PATH.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P151B"


def test_classification_valid(artifact):
    assert artifact["classification"] in VALID_CLASSIFICATIONS


def test_repo_ok(artifact):
    assert artifact["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(artifact):
    assert artifact["repo_branch_check"]["branch_ok"] is True


def test_canonical_repo(artifact):
    assert artifact["canonical_repo"] == CANONICAL_REPO


def test_canonical_branch(artifact):
    assert artifact["canonical_branch"] == CANONICAL_BRANCH


def test_db_rows(artifact):
    assert artifact["db_snapshot"]["rows"] == EXPECTED_DB_ROWS


def test_drift_guard_pass(artifact):
    assert artifact["drift_guard_status"] == "PASS"


def test_restore_authorized(artifact):
    assert artifact["historical_artifact_pollution_assessment"]["restore_authorized_by_p151b"] is True


def test_historical_artifacts_should_remain_as_committed(artifact):
    assert artifact["historical_artifact_pollution_assessment"]["historical_artifacts_should_remain_as_committed"] is True


def test_semantic_diff_detected(artifact):
    assert artifact["historical_artifact_pollution_assessment"]["semantic_diff_detected"] is True


def test_non_actions_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p151b"] is False


def test_non_actions_replay_rows(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p151b"] == 0
    assert artifact["non_actions"]["replay_rows_updated_in_p151b"] == 0
    assert artifact["non_actions"]["replay_rows_deleted_in_p151b"] == 0


def test_non_actions_ui_changes(artifact):
    assert artifact["non_actions"]["ui_changes_executed_in_p151b"] is False


def test_non_actions_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p151b"] is False


def test_non_actions_champion_promotion(artifact):
    assert artifact["non_actions"]["champion_promotion_executed_in_p151b"] is False


def test_non_actions_live_api(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


def test_non_actions_scheduler(artifact):
    assert artifact["non_actions"]["scheduler_installed"] is False


def test_backups_untracked_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


def test_backups_not_deleted(artifact):
    assert artifact["dirty_file_hygiene"]["backups_deleted"] is False


def test_forbidden_files_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["forbidden_files_staged"] is False


def test_p149_artifact_paths(artifact):
    p149 = artifact["actual_p149_artifact_paths"]
    assert "json" in p149
    assert "p149" in p149["json"]


def test_p150_artifact_paths(artifact):
    p150 = artifact["actual_p150_artifact_paths"]
    assert "json" in p150
    assert "p150" in p150["json"]


def test_ready_for_p151_if_reconciled(artifact):
    if artifact["classification"] == "P151B_HISTORICAL_ARTIFACT_POLLUTION_RECONCILED_READY_FOR_P151":
        assert artifact["p151_continuation_readiness"]["ready_for_p151_ui"] is True


def test_restored_files_are_authorized(artifact):
    if artifact["classification"] == "P151B_HISTORICAL_ARTIFACT_POLLUTION_RECONCILED_READY_FOR_P151":
        for f in artifact["restored_files"]:
            assert f in AUTHORIZED_RESTORE_FILES, f"Unexpected restored file: {f}"


def test_no_db_files_staged():
    """Confirm lottery_v2.db is not staged."""
    import subprocess
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        cwd=str(ARTIFACT_PATH.parent.parent.parent),
    )
    staged = r.stdout.strip().splitlines()
    forbidden = [
        f for f in staged
        if "lottery_v2.db" in f
        or "replay_lifecycle_drift_guard.py" in f
        or f.startswith("backups/")
        or f.endswith(".pyc")
    ]
    assert forbidden == [], f"Forbidden files staged: {forbidden}"


def test_actual_p149_json_exists():
    repo = Path(CANONICAL_REPO)
    p = repo / "outputs/replay/p149_replay_product_coverage_audit_20260529.json"
    assert p.exists(), f"P149 JSON missing: {p}"


def test_actual_p150_json_exists():
    repo = Path(CANONICAL_REPO)
    p = repo / "outputs/replay/p150_replay_api_all_strategy_coverage_20260529.json"
    assert p.exists(), f"P150 JSON missing: {p}"


def test_remaining_dirty_is_empty_or_backups_only(artifact):
    """After reconciliation, no non-backups dirty files should remain."""
    if artifact["classification"] == "P151B_HISTORICAL_ARTIFACT_POLLUTION_RECONCILED_READY_FOR_P151":
        remaining = artifact.get("remaining_dirty_files", [])
        non_backup = [f for f in remaining if not f.startswith("backups/")]
        assert non_backup == [], f"Non-backup dirty files remain: {non_backup}"
