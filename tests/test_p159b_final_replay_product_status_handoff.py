"""Tests for P159B final replay product status handoff."""

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT     = Path(__file__).parent.parent
ARTIFACT_PATH = REPO_ROOT / "outputs/replay/p159b_final_replay_product_status_handoff_20260529.json"

CANONICAL_REPO   = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_PATH.exists()
    return json.loads(ARTIFACT_PATH.read_text())


# ── Artifact basics ───────────────────────────────────────────────────────────

def test_artifact_exists():
    assert ARTIFACT_PATH.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P159B"


def test_classification(artifact):
    assert artifact["classification"] == "P159B_FINAL_REPLAY_PRODUCT_STATUS_HANDOFF_COMPLETE"


def test_repo_ok(artifact):
    assert artifact["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(artifact):
    assert artifact["repo_branch_check"]["branch_ok"] is True


def test_db_rows(artifact):
    assert artifact["db_snapshot"]["rows"] == EXPECTED_DB_ROWS


def test_drift_guard_pass(artifact):
    assert artifact["drift_guard_status"] == "PASS"


def test_p159_ok(artifact):
    assert artifact["p159_source_summary"]["ok"] is True


def test_p158b_ok(artifact):
    assert artifact["p158b_source_summary"]["ok"] is True


def test_p158_ok(artifact):
    assert artifact["p158_source_summary"]["ok"] is True


# ── Final replay product status ───────────────────────────────────────────────

def test_product_complete(artifact):
    assert artifact["final_replay_product_status"]["replay_product_complete"] is True


def test_governance_chain_closed(artifact):
    assert artifact["final_replay_product_status"]["governance_chain_closed"] is True


def test_smoke_ready(artifact):
    assert artifact["final_replay_product_status"]["smoke_evidence_ready"] is True


def test_provenance_polish_complete(artifact):
    assert artifact["final_replay_product_status"]["provenance_polish_complete"] is True


def test_blocking_tasks_zero(artifact):
    assert artifact["final_replay_product_status"]["blocking_tasks_remaining"] == 0


def test_total_strategies_40(artifact):
    assert artifact["final_replay_product_status"]["total_strategies_visible"] == 40


def test_replay_rows_94924(artifact):
    assert artifact["final_replay_product_status"]["replay_rows"] == EXPECTED_DB_ROWS


def test_db_only_zero(artifact):
    assert artifact["final_replay_product_status"]["db_only_missing_lifecycle_remaining"] == 0


# ── Completed chain ───────────────────────────────────────────────────────────

def test_chain_has_15_tasks(artifact):
    assert len(artifact["completed_chain_summary"]) == 15


def test_all_chain_complete(artifact):
    for entry in artifact["completed_chain_summary"]:
        assert entry["status"] == "COMPLETE", f"{entry['task']} not complete"


# ── Visibility invariant ──────────────────────────────────────────────────────

def test_invariant_all_visible(artifact):
    assert artifact["final_visibility_invariant"]["all_lifecycle_strategies_visible_in_replay"] is True


def test_invariant_retired(artifact):
    assert artifact["final_visibility_invariant"]["retired_strategies_visible"] is True


def test_invariant_lifecycle_label(artifact):
    assert artifact["final_visibility_invariant"]["lifecycle_is_label_not_visibility_gate"] is True


# ── Metadata display ──────────────────────────────────────────────────────────

def test_truth_level_visible(artifact):
    assert artifact["final_metadata_display_status"]["truth_level_visible"] is True


def test_source_visible(artifact):
    assert artifact["final_metadata_display_status"]["source_visible"] is True


def test_controlled_apply_id_visible(artifact):
    assert artifact["final_metadata_display_status"]["controlled_apply_id_visible"] is True


def test_provenance_hash_visible(artifact):
    assert artifact["final_metadata_display_status"]["provenance_hash_visible"] is True


def test_provenance_source_visible(artifact):
    assert artifact["final_metadata_display_status"]["provenance_source_visible"] is True


def test_bet_index_visible(artifact):
    assert artifact["final_metadata_display_status"]["bet_index_visible"] is True


def test_no_data_reason_visible(artifact):
    assert artifact["final_metadata_display_status"]["no_data_reason_visible"] is True


def test_all_fields_complete(artifact):
    assert artifact["final_metadata_display_status"]["all_fields_complete"] is True


# ── Non-blocking items ────────────────────────────────────────────────────────

def test_non_blocking_items_4(artifact):
    assert len(artifact["final_non_blocking_items"]) == 4


def test_all_non_blocking(artifact):
    for item in artifact["final_non_blocking_items"]:
        assert item["blocking"] is False


# ── Next step policy ──────────────────────────────────────────────────────────

def test_next_task_none_blocking(artifact):
    assert artifact["next_step_policy"]["next_recommended_task"] == "NONE_BLOCKING"


def test_product_line_complete(artifact):
    assert artifact["next_step_policy"]["replay_product_line_complete"] is True


def test_p160_requires_auth(artifact):
    assert artifact["next_step_policy"]["p160_requires_explicit_authorization"] is True


def test_champion_chain_separate(artifact):
    assert artifact["next_step_policy"]["champion_chain_is_separate"] is True


def test_four_star_chain_separate(artifact):
    assert artifact["next_step_policy"]["p108_p117_p118_four_star_chain_is_separate"] is True


# ── Non-actions ───────────────────────────────────────────────────────────────

def test_no_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p159b"] is False


def test_no_lifecycle_update(artifact):
    assert artifact["non_actions"]["lifecycle_update_executed_in_p159b"] is False


def test_no_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p159b"] is False


def test_no_replay_rows(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p159b"] == 0
    assert artifact["non_actions"]["replay_rows_updated_in_p159b"] == 0
    assert artifact["non_actions"]["replay_rows_deleted_in_p159b"] == 0


def test_no_live_api(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


# ── Forbidden staging ─────────────────────────────────────────────────────────

def test_no_forbidden_staged():
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=CANONICAL_REPO,
    )
    staged = r.stdout.strip().splitlines()
    forbidden = [
        f for f in staged
        if "lottery_v2.db" in f
        or "replay_lifecycle_drift_guard.py" in f
        or "replay_strategy_registry.py" in f
        or "routes/replay.py" in f
        or f.startswith("backups/")
        or f.endswith(".pyc")
    ]
    assert forbidden == [], f"Forbidden staged: {forbidden}"
