"""Tests for P158 replay product governance chain closure."""

import importlib
import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT     = Path(__file__).parent.parent
ARTIFACT_PATH = REPO_ROOT / "outputs/replay/p158_replay_product_governance_chain_closure_20260529.json"

CANONICAL_REPO   = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

VALID_CLASSIFICATIONS = {
    "P158_REPLAY_PRODUCT_GOVERNANCE_CHAIN_CLOSED",
    "P158_REPLAY_PRODUCT_GOVERNANCE_CHAIN_BLOCKED_BY_GAPS",
    "P158_STOP_SCOPE_REALIGNMENT_REQUIRED",
}


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_PATH.exists()
    return json.loads(ARTIFACT_PATH.read_text())


@pytest.fixture(scope="module")
def registry():
    import sys
    sys.path.insert(0, str(REPO_ROOT))
    import lottery_api.models.replay_strategy_registry as reg_mod
    importlib.reload(reg_mod)
    return {s["strategy_id"]: s["lifecycle_status"]
            for s in reg_mod.list_strategy_lifecycle_metadata()}


# ── Artifact basics ───────────────────────────────────────────────────────────

def test_artifact_exists():
    assert ARTIFACT_PATH.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P158"


def test_classification(artifact):
    assert artifact["classification"] == "P158_REPLAY_PRODUCT_GOVERNANCE_CHAIN_CLOSED"


def test_classification_valid(artifact):
    assert artifact["classification"] in VALID_CLASSIFICATIONS


def test_repo_ok(artifact):
    assert artifact["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(artifact):
    assert artifact["repo_branch_check"]["branch_ok"] is True


def test_db_rows(artifact):
    assert artifact["db_snapshot"]["rows"] == EXPECTED_DB_ROWS


def test_db_match(artifact):
    assert artifact["db_snapshot"]["match"] is True


def test_drift_guard_pass(artifact):
    assert artifact["drift_guard_status"] == "PASS"


def test_p157_ok(artifact):
    assert artifact["p157_source_summary"]["ok"] is True


def test_p156c_ok(artifact):
    assert artifact["p156c_source_summary"]["ok"] is True


def test_p154_ok(artifact):
    assert artifact["p154_source_summary"]["ok"] is True


# ── Governance chain closure ──────────────────────────────────────────────────

def test_rc_closed(artifact):
    assert artifact["governance_chain_closure_status"]["replay_product_rc_closed"] is True


def test_governance_chain_closed(artifact):
    assert artifact["governance_chain_closure_status"]["replay_product_governance_chain_closed"] is True


def test_blocking_gaps_zero(artifact):
    assert artifact["governance_chain_closure_status"]["blocking_gaps_count"] == 0


def test_total_strategies_40(artifact):
    assert artifact["governance_chain_closure_status"]["total_strategies_visible"] == 40


def test_db_only_remaining_zero(artifact):
    assert artifact["governance_chain_closure_status"]["db_only_missing_lifecycle_remaining"] == 0


def test_h6_gate_visible_zero_rows(artifact):
    assert artifact["governance_chain_closure_status"]["h6_gate_visible_zero_rows"] is True


def test_champion_chain_separate(artifact):
    assert artifact["governance_chain_closure_status"]["champion_chain_separate"] is True


def test_p149_to_p157_all_confirmed(artifact):
    assert artifact["governance_chain_closure_status"]["p149_to_p157_all_confirmed"] is True


# ── P149-P157 completion matrix ───────────────────────────────────────────────

def test_completion_matrix_count(artifact):
    assert len(artifact["p149_to_p157_completion_matrix"]) == 11


def test_all_completed_confirmed(artifact):
    for entry in artifact["p149_to_p157_completion_matrix"]:
        assert entry["confirmed"] is True, f"{entry['task']} not confirmed"


# ── Replay visibility final invariant ────────────────────────────────────────

def test_invariant_all_visible(artifact):
    inv = artifact["replay_visibility_final_invariant"]
    assert inv["all_lifecycle_strategies_visible_in_replay"] is True


def test_invariant_retired(artifact):
    assert artifact["replay_visibility_final_invariant"]["retired_strategies_visible"] is True


def test_invariant_rejected(artifact):
    assert artifact["replay_visibility_final_invariant"]["rejected_strategies_visible"] is True


def test_invariant_observation(artifact):
    assert artifact["replay_visibility_final_invariant"]["observation_strategies_visible"] is True


def test_invariant_no_data(artifact):
    assert artifact["replay_visibility_final_invariant"]["no_data_strategies_visible"] is True


def test_invariant_lifecycle_label(artifact):
    assert artifact["replay_visibility_final_invariant"]["lifecycle_is_label_not_visibility_gate"] is True


def test_invariant_catalog_includes_all(artifact):
    assert artifact["replay_visibility_final_invariant"]["lifecycle_filter_may_filter_but_default_catalog_includes_all"] is True


# ── Acceptance proof ──────────────────────────────────────────────────────────

def test_acceptance_catalog(artifact):
    assert artifact["replay_product_acceptance_proof"]["catalog_acceptance_passed"] is True


def test_acceptance_api(artifact):
    assert artifact["replay_product_acceptance_proof"]["api_acceptance_passed"] is True


def test_acceptance_ui(artifact):
    assert artifact["replay_product_acceptance_proof"]["ui_acceptance_passed"] is True


def test_acceptance_multi_bet(artifact):
    assert artifact["replay_product_acceptance_proof"]["multi_bet_acceptance_passed"] is True


def test_acceptance_no_data(artifact):
    assert artifact["replay_product_acceptance_proof"]["no_data_acceptance_passed"] is True


def test_acceptance_provenance(artifact):
    assert artifact["replay_product_acceptance_proof"]["provenance_metadata_acceptance_passed"] is True


def test_acceptance_operator_guide(artifact):
    assert artifact["replay_product_acceptance_proof"]["operator_guide_created"] is True


def test_acceptance_drift(artifact):
    assert artifact["replay_product_acceptance_proof"]["drift_guard_passed"] is True


def test_acceptance_total_40(artifact):
    assert artifact["replay_product_acceptance_proof"]["total_strategies"] == 40


def test_acceptance_db_rows(artifact):
    assert artifact["replay_product_acceptance_proof"]["total_replay_rows"] == EXPECTED_DB_ROWS


def test_acceptance_multi_bet_max_5(artifact):
    assert artifact["replay_product_acceptance_proof"]["multi_bet_max_bet_index"] == 5


# ── Lifecycle governance closure ──────────────────────────────────────────────

def test_lifecycle_p156c_completed(artifact):
    assert artifact["lifecycle_governance_closure"]["p156c_completed"] is True


def test_lifecycle_db_only_before_22(artifact):
    assert artifact["lifecycle_governance_closure"]["db_only_missing_lifecycle_before"] == 22


def test_lifecycle_db_only_after_0(artifact):
    assert artifact["lifecycle_governance_closure"]["db_only_missing_lifecycle_after"] == 0


def test_lifecycle_no_db_write(artifact):
    assert artifact["lifecycle_governance_closure"]["db_write_required"] is False


def test_lifecycle_r001_closed(artifact):
    assert artifact["lifecycle_governance_closure"]["r001_post_rc_risk_closed"] is True


# ── H6 gate ───────────────────────────────────────────────────────────────────

def test_h6_visible(artifact):
    assert artifact["h6_gate_final_decision"]["visible_in_catalog"] is True


def test_h6_zero_rows(artifact):
    assert artifact["h6_gate_final_decision"]["replay_rows_count"] == 0


def test_h6_observation(artifact):
    assert artifact["h6_gate_final_decision"]["lifecycle_current"] == "OBSERVATION"


def test_h6_no_data_reason(artifact):
    assert artifact["h6_gate_final_decision"]["no_data_reason_current"] == "ONLINE_ZERO_REPLAY_ROWS"


def test_h6_no_apply(artifact):
    assert artifact["h6_gate_final_decision"]["no_apply_executed"] is True


def test_h6_recommended_keep(artifact):
    assert artifact["h6_gate_final_decision"]["recommended_decision"] == "keep_observation_zero_rows"


# ── Champion boundary ─────────────────────────────────────────────────────────

def test_champion_blocked(artifact):
    assert artifact["champion_governance_boundary"]["champion_evaluation_blocked"] is True


def test_champion_not_blocking_replay(artifact):
    assert artifact["champion_governance_boundary"]["replay_product_blocked_by_champion"] is False


# ── Non-blocking backlog ──────────────────────────────────────────────────────

def test_backlog_has_4_items(artifact):
    assert len(artifact["final_non_blocking_backlog"]) == 4


def test_backlog_none_blocking(artifact):
    for k, v in artifact["final_non_blocking_backlog"].items():
        assert v["blocks_replay_product"] is False, f"{k} blocks replay product"


# ── Non-actions ───────────────────────────────────────────────────────────────

def test_no_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p158"] is False


def test_no_lifecycle_update(artifact):
    assert artifact["non_actions"]["lifecycle_update_executed_in_p158"] is False


def test_no_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p158"] is False


def test_no_replay_rows(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p158"] == 0
    assert artifact["non_actions"]["replay_rows_updated_in_p158"] == 0
    assert artifact["non_actions"]["replay_rows_deleted_in_p158"] == 0


def test_no_live_api(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


# ── Registry state ────────────────────────────────────────────────────────────

def test_registry_total_40(registry):
    assert len(registry) == 40


def test_registry_no_db_only(registry):
    assert "DB_ONLY_MISSING_LIFECYCLE" not in registry.values()


def test_registry_online_18(registry):
    assert sum(1 for v in registry.values() if v == "ONLINE") == 18


def test_registry_retired_17(registry):
    assert sum(1 for v in registry.values() if v == "RETIRED") == 17


def test_registry_rejected_4(registry):
    assert sum(1 for v in registry.values() if v == "REJECTED") == 4


def test_registry_h6_observation(registry):
    assert registry.get("h6_gate_mk20_ew85") == "OBSERVATION"


# ── Hygiene ───────────────────────────────────────────────────────────────────

def test_backups_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


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
        or f.startswith("backups/")
        or f.endswith(".pyc")
    ]
    assert forbidden == [], f"Forbidden staged: {forbidden}"
