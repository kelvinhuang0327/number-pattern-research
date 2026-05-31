"""Tests for P157 replay visibility invariant and h6 zero rows gate."""

import importlib
import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT     = Path(__file__).parent.parent
ARTIFACT_PATH = REPO_ROOT / "outputs/replay/p157_replay_visibility_invariant_and_h6_zero_rows_decision_gate_20260529.json"

CANONICAL_REPO   = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

VALID_CLASSIFICATIONS = {
    "P157_REPLAY_VISIBILITY_INVARIANT_CONFIRMED_H6_DECISION_GATE_READY",
    "P157_STOP_PREFLIGHT_MISMATCH",
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
    assert artifact["task_id"] == "P157"


def test_classification_valid(artifact):
    assert artifact["classification"] in VALID_CLASSIFICATIONS


def test_repo_ok(artifact):
    assert artifact["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(artifact):
    assert artifact["repo_branch_check"]["branch_ok"] is True


def test_db_rows(artifact):
    assert artifact["db_snapshot"]["rows"] == EXPECTED_DB_ROWS


def test_drift_guard_pass(artifact):
    assert artifact["drift_guard_status"] == "PASS"


def test_p156c_ok(artifact):
    assert artifact["p156c_source_summary"]["ok"] is True


# ── Replay visibility invariant ───────────────────────────────────────────────

def test_invariant_all_visible(artifact):
    inv = artifact["replay_visibility_invariant"]
    assert inv["all_lifecycle_strategies_visible_in_replay"] is True


def test_invariant_retired_visible(artifact):
    assert artifact["replay_visibility_invariant"]["retired_strategies_visible"] is True


def test_invariant_rejected_visible(artifact):
    assert artifact["replay_visibility_invariant"]["rejected_strategies_visible"] is True


def test_invariant_observation_visible(artifact):
    assert artifact["replay_visibility_invariant"]["observation_strategies_visible"] is True


def test_invariant_no_data_visible(artifact):
    assert artifact["replay_visibility_invariant"]["no_data_strategies_visible"] is True


def test_invariant_lifecycle_is_label(artifact):
    assert artifact["replay_visibility_invariant"]["lifecycle_is_label_not_visibility_gate"] is True


def test_invariant_filter_not_exclude(artifact):
    assert artifact["replay_visibility_invariant"]["lifecycle_filter_does_not_exclude_by_default"] is True


def test_p156c_did_not_reduce_visibility(artifact):
    assert artifact["replay_visibility_invariant"]["p156c_lifecycle_update_reduced_visibility"] is False


# ── Post-P156C catalog visibility audit ──────────────────────────────────────

def test_catalog_total_40(artifact):
    assert artifact["post_p156c_catalog_visibility_audit"]["total_strategies_visible"] == 40


def test_catalog_complete(artifact):
    assert artifact["post_p156c_catalog_visibility_audit"]["catalog_complete"] is True


def test_db_only_remaining_zero(artifact):
    assert artifact["post_p156c_catalog_visibility_audit"]["db_only_missing_lifecycle_remaining"] == 0


def test_online_count_18(artifact):
    assert artifact["post_p156c_catalog_visibility_audit"]["online_visible_count"] == 18


def test_retired_count_17(artifact):
    assert artifact["post_p156c_catalog_visibility_audit"]["retired_visible_count"] == 17


def test_rejected_count_4(artifact):
    assert artifact["post_p156c_catalog_visibility_audit"]["rejected_visible_count"] == 4


def test_observation_count_1(artifact):
    assert artifact["post_p156c_catalog_visibility_audit"]["observation_visible_count"] == 1


def test_all_strategies_visible_flag(artifact):
    assert artifact["post_p156c_catalog_visibility_audit"]["all_strategies_visible"] is True


def test_retired_with_rows_all_visible(artifact):
    """All 17 RETIRED strategies should have replay rows (from historical backfill)."""
    # P156C-updated strategies all had DB rows before they were RETIRED
    assert artifact["post_p156c_catalog_visibility_audit"]["retired_with_rows_count"] == 17


# ── Lifecycle visibility matrix ───────────────────────────────────────────────

def test_visibility_matrix_has_40(artifact):
    assert len(artifact["lifecycle_visibility_matrix"]) == 40


def test_all_matrix_visible_in_catalog(artifact):
    for m in artifact["lifecycle_visibility_matrix"]:
        assert m["visible_in_catalog"] is True, f"{m['strategy_id']} not visible"


# ── H6 gate zero rows audit ───────────────────────────────────────────────────

def test_h6_visible_in_catalog(artifact):
    h6 = artifact["h6_gate_zero_rows_audit"]
    assert h6["visible_in_catalog"] is True


def test_h6_zero_rows(artifact):
    h6 = artifact["h6_gate_zero_rows_audit"]
    assert h6["replay_rows_count"] == 0


def test_h6_observation_lifecycle(artifact):
    h6 = artifact["h6_gate_zero_rows_audit"]
    assert h6["lifecycle_current"] == "OBSERVATION"


def test_h6_no_data_reason(artifact):
    h6 = artifact["h6_gate_zero_rows_audit"]
    assert h6["no_data_reason_current"] == "ONLINE_ZERO_REPLAY_ROWS"


def test_h6_should_remain_visible_if_retired(artifact):
    h6 = artifact["h6_gate_zero_rows_audit"]
    assert h6["should_remain_visible_even_if_retired"] is True


# ── H6 decision options ───────────────────────────────────────────────────────

def test_option_a_recommended(artifact):
    assert artifact["h6_gate_decision_options"]["option_a"]["recommended"] is True


def test_option_a_no_auth_required(artifact):
    assert artifact["h6_gate_decision_options"]["option_a"]["requires_authorization"] is False


def test_option_c_not_reduce_visibility(artifact):
    """Option C (RETIRE) must not reduce visibility."""
    opt_c = artifact["h6_gate_decision_options"]["option_c"]
    assert "visible" in opt_c["impact"].lower() or "catalog" in opt_c["impact"].lower()


# ── Non-actions ───────────────────────────────────────────────────────────────

def test_no_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p157"] is False


def test_no_lifecycle_update(artifact):
    assert artifact["non_actions"]["lifecycle_update_executed_in_p157"] is False


def test_no_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p157"] is False


def test_no_replay_rows(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p157"] == 0
    assert artifact["non_actions"]["replay_rows_updated_in_p157"] == 0
    assert artifact["non_actions"]["replay_rows_deleted_in_p157"] == 0


def test_no_live_api(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


# ── Registry state invariant ──────────────────────────────────────────────────

def test_registry_total_40(registry):
    assert len(registry) == 40


def test_registry_no_db_only(registry):
    db_only = [sid for sid, lc in registry.items() if lc == "DB_ONLY_MISSING_LIFECYCLE"]
    assert db_only == []


def test_registry_h6_observation(registry):
    assert registry.get("h6_gate_mk20_ew85") == "OBSERVATION"


def test_registry_online_18(registry):
    assert sum(1 for lc in registry.values() if lc == "ONLINE") == 18


def test_registry_retired_17(registry):
    assert sum(1 for lc in registry.values() if lc == "RETIRED") == 17


def test_registry_rejected_4(registry):
    assert sum(1 for lc in registry.values() if lc == "REJECTED") == 4


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
