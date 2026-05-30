"""
Tests for P149: Replay Product Coverage Audit
"""

import json
import os
import sqlite3

import pytest

REPO_ROOT = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
P149_JSON = os.path.join(
    REPO_ROOT,
    "outputs/replay/p149_replay_product_coverage_audit_20260529.json",
)
P149_MD = os.path.join(
    REPO_ROOT,
    "docs/replay/p149_replay_product_coverage_audit_20260529.md",
)
DB_PATH = os.path.join(REPO_ROOT, "lottery_api/data/lottery_v2.db")
EXPECTED_DB_ROWS = 94924


@pytest.fixture(scope="module")
def artifact():
    assert os.path.exists(P149_JSON), f"P149 JSON artifact not found: {P149_JSON}"
    with open(P149_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_content():
    assert os.path.exists(P149_MD), f"P149 Markdown artifact not found: {P149_MD}"
    with open(P149_MD) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Identity and classification
# ---------------------------------------------------------------------------

def test_p149_json_exists():
    assert os.path.exists(P149_JSON), f"P149 JSON not found: {P149_JSON}"


def test_task_id(artifact):
    assert artifact["task_id"] == "P149", f"Expected task_id='P149', got {artifact['task_id']!r}"


def test_classification(artifact):
    assert artifact["classification"] == "P149_REPLAY_PRODUCT_COVERAGE_AUDIT_READY", (
        f"Unexpected classification: {artifact['classification']!r}"
    )


# ---------------------------------------------------------------------------
# Canonical repo / branch
# ---------------------------------------------------------------------------

def test_repo_ok(artifact):
    assert artifact["repo_branch_check"]["repo_ok"] is True, (
        f"repo_ok is False; actual_repo={artifact['repo_branch_check']['actual_repo']!r}"
    )


def test_branch_ok(artifact):
    assert artifact["repo_branch_check"]["branch_ok"] is True, (
        f"branch_ok is False; actual_branch={artifact['repo_branch_check']['actual_branch']!r}"
    )


# ---------------------------------------------------------------------------
# DB snapshot
# ---------------------------------------------------------------------------

def test_db_rows(artifact):
    assert artifact["db_snapshot"]["row_count"] == EXPECTED_DB_ROWS, (
        f"DB rows = {artifact['db_snapshot']['row_count']}, expected {EXPECTED_DB_ROWS}"
    )


def test_db_rows_live():
    """Also verify live DB row count hasn't changed."""
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()
        count = row[0] if row else -1
    finally:
        conn.close()
    assert count == EXPECTED_DB_ROWS, f"Live DB rows = {count}, expected {EXPECTED_DB_ROWS}"


def test_drift_guard_pass(artifact):
    assert artifact["db_snapshot"]["drift_guard_pass"] is True, "Drift guard did not PASS"


def test_bet_index_column_exists(artifact):
    assert artifact["db_snapshot"]["bet_index_column_exists"] is True, (
        "bet_index column should exist in strategy_prediction_replays"
    )


# ---------------------------------------------------------------------------
# Replay vs champion boundary
# ---------------------------------------------------------------------------

def test_historical_actual_numbers_allowed_for_replay_display(artifact):
    assert artifact["replay_vs_champion_boundary"][
        "historical_actual_numbers_allowed_for_replay_display"
    ] is True


def test_live_monitoring_verified_required_for_champion_evaluation(artifact):
    assert artifact["replay_vs_champion_boundary"][
        "live_monitoring_verified_required_for_champion_evaluation"
    ] is True


def test_p148c_blocks_champion_not_replay(artifact):
    assert artifact["replay_vs_champion_boundary"]["p148c_blocks_champion_not_replay"] is True


# ---------------------------------------------------------------------------
# Strategy inventory audit
# ---------------------------------------------------------------------------

def test_total_strategies_discovered(artifact):
    total = artifact["strategy_inventory_audit"]["total_strategies_discovered"]
    assert total > 0, "Should have discovered at least 1 strategy"


def test_strategies_list_non_empty(artifact):
    assert len(artifact["strategy_inventory_audit"]["strategies_list"]) > 0


def test_registry_strategies_detected(artifact):
    """Registry should have at least 8 ONLINE strategies."""
    registry_count = artifact["strategy_inventory_audit"]["registry_strategy_count"]
    assert registry_count >= 8, f"Expected >= 8 registry strategies, got {registry_count}"


def test_db_strategies_detected(artifact):
    """DB should have at least 13 strategies."""
    db_count = artifact["strategy_inventory_audit"]["db_strategy_count"]
    assert db_count >= 13, f"Expected >= 13 DB strategies, got {db_count}"


def test_in_both_detected(artifact):
    """Should have strategies in both registry and DB."""
    assert len(artifact["strategy_inventory_audit"]["in_both"]) > 0


# ---------------------------------------------------------------------------
# Replay row coverage
# ---------------------------------------------------------------------------

def test_total_replay_rows(artifact):
    assert artifact["replay_row_coverage_summary"]["total_replay_rows"] == EXPECTED_DB_ROWS, (
        f"total_replay_rows = {artifact['replay_row_coverage_summary']['total_replay_rows']}, "
        f"expected {EXPECTED_DB_ROWS}"
    )


def test_strategies_with_replay_rows_nonzero(artifact):
    assert artifact["replay_row_coverage_summary"]["strategies_with_replay_rows"] > 0


# ---------------------------------------------------------------------------
# API capability audit
# ---------------------------------------------------------------------------

def test_api_predicted_numbers_returned(artifact):
    assert artifact["replay_api_capability_audit"]["predicted_numbers_returned"] is True


def test_api_actual_numbers_returned(artifact):
    assert artifact["replay_api_capability_audit"]["actual_numbers_returned"] is True


def test_api_hit_count_returned(artifact):
    assert artifact["replay_api_capability_audit"]["hit_count_returned"] is True


def test_api_truth_level_returned(artifact):
    assert artifact["replay_api_capability_audit"]["truth_level_returned"] is True


def test_api_source_returned(artifact):
    assert artifact["replay_api_capability_audit"]["source_returned"] is True


def test_api_controlled_apply_id_returned(artifact):
    assert artifact["replay_api_capability_audit"]["controlled_apply_id_returned"] is True


def test_api_lifecycle_filter_supported(artifact):
    assert artifact["replay_api_capability_audit"]["lifecycle_filter_supported"] is True


def test_api_gaps_is_list(artifact):
    assert isinstance(artifact["replay_api_capability_audit"]["gaps"], list)


# ---------------------------------------------------------------------------
# Multi-bet display readiness
# ---------------------------------------------------------------------------

def test_bet_index_in_db(artifact):
    assert artifact["multi_bet_display_readiness"]["bet_index_in_db"] is True


def test_multi_bet_strategies_present(artifact):
    assert len(artifact["multi_bet_display_readiness"]["multi_bet_strategies_in_db"]) > 0


def test_bet_index_distribution_has_1(artifact):
    dist = artifact["multi_bet_display_readiness"]["bet_index_distribution"]
    assert "1" in dist, "bet_index=1 should exist in distribution"


# ---------------------------------------------------------------------------
# Truth level display readiness
# ---------------------------------------------------------------------------

def test_truth_level_in_db(artifact):
    assert artifact["truth_level_display_readiness"]["truth_level_in_db"] is True


def test_truth_levels_found_nonempty(artifact):
    assert len(artifact["truth_level_display_readiness"]["truth_levels_found"]) > 0


# ---------------------------------------------------------------------------
# Gap matrix
# ---------------------------------------------------------------------------

def test_gap_matrix_non_empty(artifact):
    assert len(artifact["replay_product_gap_matrix"]) > 0, "Gap matrix should not be empty"


def test_gap_matrix_has_required_fields(artifact):
    for g in artifact["replay_product_gap_matrix"]:
        assert "gap_id" in g, "Each gap should have gap_id"
        assert "area" in g, "Each gap should have area"
        assert "severity" in g, "Each gap should have severity"
        assert "current_state" in g, "Each gap should have current_state"
        assert "expected_state" in g, "Each gap should have expected_state"
        assert "recommended_task" in g, "Each gap should have recommended_task"


def test_gap_severities_valid(artifact):
    valid_severities = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    for g in artifact["replay_product_gap_matrix"]:
        assert g["severity"] in valid_severities, (
            f"gap {g['gap_id']} has invalid severity {g['severity']!r}"
        )


def test_gap_areas_valid(artifact):
    valid_areas = {"catalog", "api", "ui", "data", "test"}
    for g in artifact["replay_product_gap_matrix"]:
        assert g["area"] in valid_areas, (
            f"gap {g['gap_id']} has invalid area {g['area']!r}"
        )


def test_recommended_next_task_present(artifact):
    assert artifact["recommended_next_task"], "recommended_next_task should be non-empty"


# ---------------------------------------------------------------------------
# Non-actions
# ---------------------------------------------------------------------------

def test_no_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p149"] is False, (
        "db_write_in_p149 should be False"
    )


def test_no_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p149"] is False, (
        "controlled_apply_executed_in_p149 should be False"
    )


def test_no_replay_rows_inserted(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p149"] == 0


def test_no_replay_rows_updated(artifact):
    assert artifact["non_actions"]["replay_rows_updated_in_p149"] == 0


def test_no_replay_rows_deleted(artifact):
    assert artifact["non_actions"]["replay_rows_deleted_in_p149"] == 0


def test_no_champion_promotion(artifact):
    assert artifact["non_actions"]["champion_promotion_executed_in_p149"] is False


def test_no_registry_update(artifact):
    assert artifact["non_actions"]["registry_update_executed_in_p149"] is False


def test_no_live_api_called(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


def test_no_scheduler_installed(artifact):
    assert artifact["non_actions"]["scheduler_installed"] is False


# ---------------------------------------------------------------------------
# Dirty file hygiene
# ---------------------------------------------------------------------------

def test_dirty_file_hygiene_status(artifact):
    status = artifact["dirty_file_hygiene"]["status"]
    assert status == "CLEAN", f"Expected CLEAN dirty file hygiene, got {status!r}"


def test_no_unrelated_dirty_files(artifact):
    unrelated = artifact["dirty_file_hygiene"]["unrelated_dirty_files"]
    assert unrelated == [], f"Unrelated dirty files found: {unrelated}"


# ---------------------------------------------------------------------------
# Markdown file
# ---------------------------------------------------------------------------

def test_p149_md_exists():
    assert os.path.exists(P149_MD), f"P149 Markdown not found: {P149_MD}"


def test_md_contains_champion_boundary_section(md_content):
    assert "Why P148C blocks champion but not replay product" in md_content, (
        "Markdown missing 'Why P148C blocks champion but not replay product' section"
    )


def test_md_contains_non_actions(md_content):
    assert (
        "non-actions" in md_content.lower()
        or "Non-actions" in md_content
        or "non_actions" in md_content
    ), "Markdown should mention non-actions"


def test_md_contains_gap_matrix(md_content):
    assert "Gap Matrix" in md_content or "gap_matrix" in md_content.lower(), (
        "Markdown should contain gap matrix section"
    )


def test_md_contains_classification(md_content):
    assert "P149_REPLAY_PRODUCT_COVERAGE_AUDIT_READY" in md_content


# ---------------------------------------------------------------------------
# DB / staging hygiene — no history/runtime/pid files staged
# ---------------------------------------------------------------------------

def test_no_db_file_staged():
    """lottery_v2.db must NOT be staged."""
    import subprocess
    result = subprocess.run(
        ["git", "-C", REPO_ROOT, "diff", "--cached", "--name-only"],
        capture_output=True, text=True
    )
    staged = result.stdout.strip().splitlines()
    db_staged = [f for f in staged if "lottery_v2.db" in f]
    assert not db_staged, f"DB file staged: {db_staged}"


def test_no_pid_or_runtime_files_staged():
    """pid / runtime / pyc files must NOT be staged."""
    import subprocess
    result = subprocess.run(
        ["git", "-C", REPO_ROOT, "diff", "--cached", "--name-only"],
        capture_output=True, text=True
    )
    staged = result.stdout.strip().splitlines()
    bad = [
        f for f in staged
        if f.endswith(".pid") or f.endswith(".pyc") or "__pycache__" in f
        or "backend.pid" in f
    ]
    assert not bad, f"Bad files staged: {bad}"
