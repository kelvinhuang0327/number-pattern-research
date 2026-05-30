"""
P148B Manual Live Verified Evidence File Artifact Run — pytest test suite.

Tests verify:
- JSON artifact exists with correct structure and values
- task_id, classification values
- repo/branch checks
- DB snapshot matches expected state (live query)
- bet_index column exists (live query)
- P148 source summary classification
- All non-actions are false
- Evidence contract is complete with 14 required fields
- Champion evaluation unlock status is blocked (when no source found)
- Dirty file hygiene fields
- Markdown artifact contains required sections
- Per-strategy evidence results has 6 entries with all expected strategy IDs
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
    "outputs/replay/p148b_manual_live_verified_evidence_file_artifact_run_20260529.json",
)
MD_PATH = os.path.join(
    REPO_ROOT,
    "docs/replay/p148b_manual_live_verified_evidence_file_artifact_run_20260529.md",
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

VALID_CLASSIFICATIONS = {
    "P148B_LIVE_MONITORING_VERIFIED_FILE_ARTIFACT_CREATED",
    "P148B_BLOCKED_PENDING_MANUAL_DRAW_RESULT_INPUT",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def artifact():
    assert os.path.exists(JSON_PATH), f"P148B JSON not found: {JSON_PATH}"
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_content():
    assert os.path.exists(MD_PATH), f"P148B Markdown not found: {MD_PATH}"
    with open(MD_PATH) as f:
        return f.read()


@pytest.fixture(scope="module")
def db_conn():
    con = sqlite3.connect(DB_PATH)
    yield con
    con.close()


# ---------------------------------------------------------------------------
# JSON artifact existence
# ---------------------------------------------------------------------------


def test_json_exists():
    assert os.path.exists(JSON_PATH), f"P148B JSON artifact missing: {JSON_PATH}"


# ---------------------------------------------------------------------------
# task_id
# ---------------------------------------------------------------------------


def test_task_id(artifact):
    assert artifact["task_id"] == "P148B"


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------


def test_classification_valid(artifact):
    assert artifact["classification"] in VALID_CLASSIFICATIONS, (
        f"Unexpected classification: {artifact['classification']}"
    )


# ---------------------------------------------------------------------------
# Repo / branch checks
# ---------------------------------------------------------------------------


def test_repo_ok(artifact):
    assert artifact["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(artifact):
    assert artifact["repo_branch_check"]["branch_ok"] is True


# ---------------------------------------------------------------------------
# DB snapshot — live queries
# ---------------------------------------------------------------------------


def test_db_total_rows_live(db_conn):
    """Query live DB to confirm 94924 rows."""
    cur = db_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    count = cur.fetchone()[0]
    assert count == 94924, f"DB row count is {count}, expected 94924"


def test_db_total_rows_artifact(artifact):
    assert artifact["db_snapshot"]["total_rows"] == 94924


def test_bet_index_column_exists(db_conn):
    """Confirm bet_index column exists in live DB."""
    cur = db_conn.cursor()
    cur.execute("PRAGMA table_info(strategy_prediction_replays)")
    cols = [row[1] for row in cur.fetchall()]
    assert "bet_index" in cols, "bet_index column missing from strategy_prediction_replays"


# ---------------------------------------------------------------------------
# P148 source summary
# ---------------------------------------------------------------------------


def test_p148_source_classification(artifact):
    assert (
        artifact["p148_source_summary"]["classification"]
        == "P148_LIVE_MONITORING_VERIFIED_EVIDENCE_COLLECTION_GATE_READY"
    )


# ---------------------------------------------------------------------------
# Non-actions
# ---------------------------------------------------------------------------


def test_non_actions_db_write_false(artifact):
    assert artifact["non_actions"]["db_write_in_p148b"] is False


def test_non_actions_live_api_called_false(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


def test_non_actions_scheduler_installed_false(artifact):
    assert artifact["non_actions"]["scheduler_installed"] is False


def test_non_actions_registry_update_false(artifact):
    assert artifact["non_actions"]["registry_update_executed_in_p148b"] is False


def test_non_actions_champion_promotion_false(artifact):
    assert artifact["non_actions"]["champion_promotion_executed_in_p148b"] is False


# ---------------------------------------------------------------------------
# Evidence contract validation
# ---------------------------------------------------------------------------


def test_evidence_contract_complete(artifact):
    assert artifact["live_verified_evidence_contract_validation"]["contract_complete"] is True


def test_evidence_contract_required_fields_count(artifact):
    assert artifact["live_verified_evidence_contract_validation"]["required_fields_count"] == 14


# ---------------------------------------------------------------------------
# Champion evaluation unlock status (when usable_source_found == false)
# ---------------------------------------------------------------------------


def test_champion_evaluation_unlocked_false_when_no_source(artifact):
    audit = artifact["manual_input_source_audit"]
    if not audit["usable_source_found"]:
        assert (
            artifact["champion_evaluation_unlock_status"]["champion_evaluation_unlocked"]
            is False
        ), "Expected champion_evaluation_unlocked=False when no source found"


def test_live_verified_records_zero_when_no_source(artifact):
    audit = artifact["manual_input_source_audit"]
    if not audit["usable_source_found"]:
        assert (
            artifact["champion_evaluation_unlock_status"]["live_monitoring_verified_records_created"]
            == 0
        ), "Expected live_monitoring_verified_records_created=0 when no source found"


# ---------------------------------------------------------------------------
# Dirty file hygiene
# ---------------------------------------------------------------------------


def test_dirty_file_hygiene_backups_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


def test_dirty_file_hygiene_forbidden_files_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["forbidden_files_staged"] is False


# ---------------------------------------------------------------------------
# Markdown artifact
# ---------------------------------------------------------------------------


def test_markdown_exists():
    assert os.path.exists(MD_PATH), f"P148B Markdown artifact missing: {MD_PATH}"


def test_markdown_contains_evidence_source(md_content):
    assert "evidence source" in md_content.lower(), (
        "Markdown missing 'evidence source' section"
    )


def test_markdown_contains_non_actions(md_content):
    assert (
        "non-action" in md_content.lower() or "non_action" in md_content.lower()
    ), "Markdown missing 'Non-Actions' / 'non_actions' section"


# ---------------------------------------------------------------------------
# Per-strategy evidence results
# ---------------------------------------------------------------------------


def test_per_strategy_evidence_results_count(artifact):
    assert len(artifact["per_strategy_evidence_results"]) == 6, (
        f"Expected 6 strategy entries, got {len(artifact['per_strategy_evidence_results'])}"
    )


def test_per_strategy_all_strategy_ids_present(artifact):
    found = {r["strategy_id"] for r in artifact["per_strategy_evidence_results"]}
    assert found == EXPECTED_STRATEGIES, (
        f"Missing/extra strategies: {found ^ EXPECTED_STRATEGIES}"
    )


def test_per_strategy_acb_markov_midfreq_3bet(artifact):
    ids = [r["strategy_id"] for r in artifact["per_strategy_evidence_results"]]
    assert "acb_markov_midfreq_3bet" in ids


def test_per_strategy_midfreq_fourier_mk_3bet(artifact):
    ids = [r["strategy_id"] for r in artifact["per_strategy_evidence_results"]]
    assert "midfreq_fourier_mk_3bet" in ids


def test_per_strategy_fourier_rhythm_3bet(artifact):
    ids = [r["strategy_id"] for r in artifact["per_strategy_evidence_results"]]
    assert "fourier_rhythm_3bet" in ids


def test_per_strategy_pp3_freqort_4bet(artifact):
    ids = [r["strategy_id"] for r in artifact["per_strategy_evidence_results"]]
    assert "pp3_freqort_4bet" in ids


def test_per_strategy_power_precision_3bet(artifact):
    ids = [r["strategy_id"] for r in artifact["per_strategy_evidence_results"]]
    assert "power_precision_3bet" in ids


def test_per_strategy_power_orthogonal_5bet(artifact):
    ids = [r["strategy_id"] for r in artifact["per_strategy_evidence_results"]]
    assert "power_orthogonal_5bet" in ids


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
