"""Tests for P156B DB_ONLY lifecycle decision gate."""

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT     = Path(__file__).parent.parent
ARTIFACT_PATH = REPO_ROOT / "outputs/replay/p156b_db_only_lifecycle_decision_gate_20260529.json"
REGISTRY_PATH = REPO_ROOT / "lottery_api/models/replay_strategy_registry.py"

CANONICAL_REPO   = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

VALID_CLASSIFICATIONS = {
    "P156B_DB_ONLY_LIFECYCLE_DECISION_GATE_READY_WAITING_FOR_AUTHORIZATION",
    "P156B_AUTHORIZATION_VALIDATED_READY_FOR_P156C",
    "P156B_SCOPE_REALIGNMENT_REQUIRED",
    "P156B_STOP_PREFLIGHT_MISMATCH",
}

HUMAN_REVIEW_IDS = {
    "cold_complement_2bet", "zonal_entropy_2bet",
    "fourier30_markov30_2bet", "fourier30_markov30_biglotto",
}


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_PATH.exists(), f"P156B artifact missing: {ARTIFACT_PATH}"
    return json.loads(ARTIFACT_PATH.read_text())


@pytest.fixture(scope="module")
def matrix(artifact):
    return {m["strategy_id"]: m for m in artifact["decision_gate_matrix"]}


# ── Artifact basics ───────────────────────────────────────────────────────────

def test_artifact_exists():
    assert ARTIFACT_PATH.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P156B"


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


def test_p156_ok(artifact):
    assert artifact["p156_source_summary"]["ok"] is True


def test_p154_ok(artifact):
    assert artifact["p154_source_summary"]["ok"] is True


# ── Decision gate matrix ──────────────────────────────────────────────────────

def test_matrix_has_22_rows(artifact):
    assert len(artifact["decision_gate_matrix"]) == 22


def test_all_update_allowed_false(matrix):
    for sid, m in matrix.items():
        assert m["update_allowed_in_p156b"] is False, f"{sid}: update_allowed_in_p156b must be False"


def test_all_current_lifecycle(matrix):
    for _, m in matrix.items():
        assert m["current_lifecycle"] == "DB_ONLY_MISSING_LIFECYCLE"


def test_all_have_authorization_phrase(matrix):
    for sid, m in matrix.items():
        phrase = m["exact_authorization_phrase"]
        assert sid in phrase, f"{sid}: phrase must contain strategy_id"
        assert m["recommended_lifecycle"] in phrase, f"{sid}: phrase must contain lifecycle"


def test_human_review_flagged(matrix):
    for sid in HUMAN_REVIEW_IDS:
        assert matrix[sid]["requires_human_review"] is True


def test_group_a_recommended_online(matrix):
    group_a = [
        "biglotto_echo_aware_3bet", "biglotto_ts3_markov_4bet_w30",
        "daily539_f4cold_3bet", "daily539_f4cold_5bet",
        "power_fourier_rhythm_2bet", "midfreq_fourier_mk_3bet", "pp3_freqort_4bet",
    ]
    for sid in group_a:
        assert matrix[sid]["recommended_lifecycle"] == "ONLINE"
        assert matrix[sid]["group"] == "A"


def test_group_c_recommended_retired(matrix):
    group_c = [
        "539_3bet_orthogonal", "acb_single_539", "markov_1bet_539",
        "p0b_539_3bet_f_cold_fmid", "p0c_539_3bet_f_cold_x2", "zone_gap_3bet_539",
    ]
    for sid in group_c:
        assert matrix[sid]["recommended_lifecycle"] == "RETIRED"
        assert matrix[sid]["group"] == "C"


def test_group_d_recommended_retired(matrix):
    group_d = [
        "bet2_fourier_expansion_biglotto", "cold_complement_biglotto",
        "coldpool15_biglotto", "fourier30_markov30_biglotto",
        "markov_2bet_biglotto", "markov_single_biglotto",
    ]
    for sid in group_d:
        assert matrix[sid]["recommended_lifecycle"] == "RETIRED"
        assert matrix[sid]["group"] == "D"


def test_online_count_10(artifact):
    online = [m for m in artifact["decision_gate_matrix"] if m["recommended_lifecycle"] == "ONLINE"]
    assert len(online) == 10


def test_retired_count_12(artifact):
    retired = [m for m in artifact["decision_gate_matrix"] if m["recommended_lifecycle"] == "RETIRED"]
    assert len(retired) == 12


# ── Group authorization options ───────────────────────────────────────────────

def test_group_a_allows_group_update(artifact):
    assert artifact["group_authorization_options"]["group_a_online_high_confidence"]["group_update_allowed"] is True


def test_group_a_not_human_review(artifact):
    assert artifact["group_authorization_options"]["group_a_online_high_confidence"]["human_review_required"] is False


def test_group_retired_high_allows_group(artifact):
    assert artifact["group_authorization_options"]["group_retired_high_confidence"]["group_update_allowed"] is True


def test_group_retired_medium_allows_group(artifact):
    assert artifact["group_authorization_options"]["group_retired_medium_confidence"]["group_update_allowed"] is True


def test_human_review_group_disallowed(artifact):
    assert artifact["group_authorization_options"]["human_review_group_disallowed"]["group_update_allowed"] is False


def test_group_phrase_templates_present(artifact):
    templates = artifact["group_authorization_options"]["exact_group_authorization_phrase_templates"]
    assert "group_a_template" in templates
    assert "individual_template" in templates


# ── Human review strategies ───────────────────────────────────────────────────

def test_human_review_has_4_entries(artifact):
    assert len(artifact["human_review_required_strategies"]) == 4


def test_human_review_strategy_ids(artifact):
    ids = {s["strategy_id"] for s in artifact["human_review_required_strategies"]}
    assert ids == HUMAN_REVIEW_IDS


def test_human_review_have_individual_phrases(artifact):
    for s in artifact["human_review_required_strategies"]:
        assert s["strategy_id"] in s["individual_phrase"]
        assert s["recommended_lifecycle"] in s["individual_phrase"]


# ── Authorization status ──────────────────────────────────────────────────────

def test_authorization_required(artifact):
    assert artifact["authorization_status"]["authorization_required_before_registry_update"] is True


def test_waiting_for_auth_has_zero_authorized(artifact):
    cls = artifact["classification"]
    if cls == "P156B_DB_ONLY_LIFECYCLE_DECISION_GATE_READY_WAITING_FOR_AUTHORIZATION":
        assert artifact["authorization_status"]["valid_authorization_count"] == 0
        assert artifact["authorization_status"]["authorization_present"] is False


# ── P156C execution plan ──────────────────────────────────────────────────────

def test_p156c_required(artifact):
    assert artifact["p156c_execution_plan"]["p156c_required"] is True


def test_p156c_registry_path(artifact):
    assert artifact["p156c_execution_plan"]["registry_file_path"] == "lottery_api/models/replay_strategy_registry.py"


def test_p156c_no_db_write(artifact):
    assert artifact["p156c_execution_plan"]["db_write_required"] is False


def test_p156c_must_reverify(artifact):
    assert artifact["p156c_execution_plan"]["p156c_must_reverify_phase0"] is True


# ── Registry safety assessment ────────────────────────────────────────────────

def test_registry_source_controlled(artifact):
    assert artifact["registry_update_safety_assessment"]["registry_is_source_controlled"] is True


def test_registry_not_db_table(artifact):
    assert artifact["registry_update_safety_assessment"]["registry_is_db_table"] is False


def test_no_db_mutation(artifact):
    assert artifact["registry_update_safety_assessment"]["db_mutation_required"] is False


def test_not_executed_in_p156b(artifact):
    assert artifact["registry_update_safety_assessment"]["update_executed_in_p156b"] is False


def test_registry_file_not_staged(artifact):
    assert artifact["registry_update_safety_assessment"]["registry_file_not_staged_in_p156b"] is True


# ── Non-actions ───────────────────────────────────────────────────────────────

def test_no_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p156b"] is False


def test_no_lifecycle_update(artifact):
    assert artifact["non_actions"]["lifecycle_update_executed_in_p156b"] is False


def test_no_registry_modified(artifact):
    assert artifact["non_actions"]["registry_file_modified_in_p156b"] is False


def test_no_replay_rows(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p156b"] == 0
    assert artifact["non_actions"]["replay_rows_updated_in_p156b"] == 0
    assert artifact["non_actions"]["replay_rows_deleted_in_p156b"] == 0


def test_no_live_api(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


# ── Hygiene ───────────────────────────────────────────────────────────────────

def test_backups_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


def test_registry_not_staged_in_git(artifact):
    assert artifact["dirty_file_hygiene"]["registry_file_staged"] is False


def test_no_forbidden_files_staged():
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


def test_registry_file_unchanged():
    """Registry Python file must NOT be modified."""
    r = subprocess.run(
        ["git", "diff", "--name-only", "lottery_api/models/replay_strategy_registry.py"],
        capture_output=True, text=True, cwd=CANONICAL_REPO,
    )
    assert r.stdout.strip() == "", "replay_strategy_registry.py must not be modified in P156B"
