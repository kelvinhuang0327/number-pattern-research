"""
P148 Live Monitoring Verified Evidence Collection Gate — pytest test suite.

Tests verify:
- JSON artifact exists with correct structure and values
- DB snapshot matches expected state (live query)
- All 6 champion candidate strategies have 0 LIVE_MONITORING_VERIFIED records
- Evidence contract is complete
- Collection path options are defined
- No forbidden actions were taken
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
    "outputs/replay/p148_live_monitoring_verified_evidence_collection_gate_20260529.json",
)
MD_PATH = os.path.join(
    REPO_ROOT,
    "docs/replay/p148_live_monitoring_verified_evidence_collection_gate_20260529.md",
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
    assert os.path.exists(JSON_PATH), f"P148 JSON not found: {JSON_PATH}"
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_content():
    assert os.path.exists(MD_PATH), f"P148 Markdown not found: {MD_PATH}"
    with open(MD_PATH) as f:
        return f.read()


@pytest.fixture(scope="module")
def db_conn():
    con = sqlite3.connect(DB_PATH)
    yield con
    con.close()


# ---------------------------------------------------------------------------
# JSON artifact existence and top-level fields
# ---------------------------------------------------------------------------


def test_json_exists():
    assert os.path.exists(JSON_PATH), f"P148 JSON artifact missing: {JSON_PATH}"


def test_task_id(artifact):
    assert artifact["task_id"] == "P148"


def test_classification(artifact):
    assert (
        artifact["classification"]
        == "P148_LIVE_MONITORING_VERIFIED_EVIDENCE_COLLECTION_GATE_READY"
    )


# ---------------------------------------------------------------------------
# Repo / branch checks
# ---------------------------------------------------------------------------


def test_repo_ok(artifact):
    assert artifact["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(artifact):
    assert artifact["repo_branch_check"]["branch_ok"] is True


# ---------------------------------------------------------------------------
# DB snapshot — artifact values
# ---------------------------------------------------------------------------


def test_db_total_rows_artifact(artifact):
    assert artifact["db_snapshot"]["total_rows"] == 94924


# ---------------------------------------------------------------------------
# DB snapshot — live queries
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# P147 source summary
# ---------------------------------------------------------------------------


def test_p147_source_classification(artifact):
    assert (
        artifact["p147_source_summary"]["classification"]
        == "P147_CHAMPION_EVALUATION_BLOCKED_PENDING_LIVE_MONITORING_VERIFIED"
    )


def test_p147_champion_evaluation_allowed_false(artifact):
    assert artifact["p147_source_summary"]["champion_evaluation_allowed"] is False


def test_p147_champion_promotion_allowed_false(artifact):
    assert artifact["p147_source_summary"]["champion_promotion_allowed"] is False


def test_p147_registry_update_allowed_false(artifact):
    assert artifact["p147_source_summary"]["registry_update_allowed"] is False


# ---------------------------------------------------------------------------
# Current evidence state
# ---------------------------------------------------------------------------


def test_live_monitoring_verified_records_found_zero(artifact):
    assert artifact["current_evidence_state"]["live_monitoring_verified_records_found"] == 0


def test_champion_evaluation_currently_blocked(artifact):
    assert artifact["current_evidence_state"]["champion_evaluation_currently_blocked"] is True


def test_champion_promotion_allowed_false(artifact):
    assert artifact["current_evidence_state"]["champion_promotion_allowed"] is False


def test_live_db_zero_live_monitoring_verified(db_conn):
    """Live DB query: confirm 0 LIVE_MONITORING_VERIFIED rows."""
    cur = db_conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE truth_level='LIVE_MONITORING_VERIFIED'"
    )
    count = cur.fetchone()[0]
    assert count == 0, f"Expected 0 LIVE_MONITORING_VERIFIED rows, found {count}"


# ---------------------------------------------------------------------------
# Evidence contract
# ---------------------------------------------------------------------------


def test_monitoring_truth_level_required(artifact):
    assert (
        artifact["live_verified_evidence_contract"]["monitoring_truth_level_required"]
        == "LIVE_MONITORING_VERIFIED"
    )


def test_evidence_contract_complete(artifact):
    assert artifact["live_verified_evidence_contract"]["contract_complete"] is True


def test_production_db_write_not_required_for_p148(artifact):
    assert (
        artifact["live_verified_evidence_contract"]["production_db_write_required_for_p148"]
        is False
    )


def test_evidence_contract_file_artifact_first(artifact):
    assert artifact["live_verified_evidence_contract"]["file_artifact_first"] is True


# ---------------------------------------------------------------------------
# Evidence source readiness audit
# ---------------------------------------------------------------------------


def test_fixture_mock_insufficient_for_live_verified(artifact):
    assert (
        artifact["evidence_source_readiness_audit"]["fixture_mock_insufficient_for_live_verified"]
        is True
    )


def test_scheduler_not_required(artifact):
    assert artifact["evidence_source_readiness_audit"]["scheduler_required"] is False


def test_authorization_required_before_execution(artifact):
    assert (
        artifact["evidence_source_readiness_audit"]["authorization_required_before_execution"]
        is True
    )


# ---------------------------------------------------------------------------
# Collection path options
# ---------------------------------------------------------------------------


def test_collection_path_options_count(artifact):
    opts = artifact["collection_path_options"]
    assert len(opts) >= 4


def test_option_a_exists(artifact):
    assert "option_a_manual_draw_result_file_artifact" in artifact["collection_path_options"]


def test_option_b_exists(artifact):
    assert "option_b_local_verified_draw_source_file_artifact" in artifact["collection_path_options"]


def test_option_c_exists(artifact):
    assert "option_c_live_api_after_explicit_authorization" in artifact["collection_path_options"]


def test_option_d_exists(artifact):
    assert "option_d_scheduled_monitoring_after_explicit_authorization" in artifact["collection_path_options"]


def test_option_a_recommended(artifact):
    opt = artifact["collection_path_options"]["option_a_manual_draw_result_file_artifact"]
    assert opt["recommended"] is True
    assert opt["risk_level"] == "LOW"
    assert opt["requires_db_write"] is False
    assert opt["requires_live_api"] is False


def test_option_b_recommended(artifact):
    opt = artifact["collection_path_options"]["option_b_local_verified_draw_source_file_artifact"]
    assert opt["recommended"] is True
    assert opt["risk_level"] == "LOW"


def test_option_c_not_recommended(artifact):
    opt = artifact["collection_path_options"]["option_c_live_api_after_explicit_authorization"]
    assert opt["recommended"] is False
    assert opt["requires_live_api"] is True


def test_option_d_not_recommended(artifact):
    opt = artifact["collection_path_options"]["option_d_scheduled_monitoring_after_explicit_authorization"]
    assert opt["recommended"] is False
    assert opt["requires_scheduler"] is True
    assert opt["risk_level"] == "HIGH"


# ---------------------------------------------------------------------------
# Non-actions
# ---------------------------------------------------------------------------


def test_non_actions_db_write_false(artifact):
    assert artifact["non_actions"]["db_write_in_p148"] is False


def test_non_actions_live_monitoring_verified_record_created_false(artifact):
    assert artifact["non_actions"]["live_monitoring_verified_record_created_in_p148"] is False


def test_non_actions_live_api_called_false(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


def test_non_actions_scheduler_installed_false(artifact):
    assert artifact["non_actions"]["scheduler_installed"] is False


def test_non_actions_champion_promotion_false(artifact):
    assert artifact["non_actions"]["champion_promotion_executed_in_p148"] is False


def test_non_actions_registry_update_false(artifact):
    assert artifact["non_actions"]["registry_update_executed_in_p148"] is False


# ---------------------------------------------------------------------------
# Dirty file hygiene
# ---------------------------------------------------------------------------


def test_dirty_file_hygiene_backups_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


def test_dirty_file_hygiene_forbidden_files_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["forbidden_files_staged"] is False


# ---------------------------------------------------------------------------
# Candidate strategy inventory
# ---------------------------------------------------------------------------


def test_candidate_strategy_inventory_count(artifact):
    assert len(artifact["candidate_strategy_inventory"]) == 6


def test_candidate_strategies_all_present(artifact):
    found = {s["strategy_id"] for s in artifact["candidate_strategy_inventory"]}
    assert found == EXPECTED_STRATEGIES, (
        f"Missing/extra strategies: {found ^ EXPECTED_STRATEGIES}"
    )


def test_all_strategies_have_zero_live_verified(artifact):
    for entry in artifact["candidate_strategy_inventory"]:
        assert entry["live_verified_records"] == 0, (
            f"{entry['strategy_id']} has live_verified_records="
            f"{entry['live_verified_records']}, expected 0"
        )


def test_all_strategies_not_collection_ready(artifact):
    for entry in artifact["candidate_strategy_inventory"]:
        assert entry["collection_ready"] is False, (
            f"{entry['strategy_id']} has collection_ready=True unexpectedly"
        )


# ---------------------------------------------------------------------------
# Markdown artifact
# ---------------------------------------------------------------------------


def test_markdown_exists(md_content):
    assert len(md_content) > 0, "Markdown file is empty"


def test_markdown_contains_evidence_source_readiness(md_content):
    assert "evidence source readiness" in md_content.lower(), (
        "Markdown missing 'evidence source readiness' section"
    )


def test_markdown_contains_non_actions(md_content):
    assert (
        "non-actions" in md_content.lower() or "non_actions" in md_content.lower()
    ), "Markdown missing 'non-actions' / 'non_actions' section"


def test_markdown_contains_final_classification(md_content):
    assert "P148_LIVE_MONITORING_VERIFIED_EVIDENCE_COLLECTION_GATE_READY" in md_content


def test_markdown_contains_collection_path_options(md_content):
    assert "collection path options" in md_content.lower(), (
        "Markdown missing 'Collection Path Options' section"
    )


def test_markdown_contains_executive_summary(md_content):
    assert "executive summary" in md_content.lower(), (
        "Markdown missing 'Executive Summary' section"
    )


def test_markdown_contains_next_execution_gate(md_content):
    assert "P148B_MANUAL_LIVE_VERIFIED_EVIDENCE_FILE_ARTIFACT_RUN" in md_content


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
