"""Tests for P156 DB_ONLY lifecycle governance audit."""

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT     = Path(__file__).parent.parent
ARTIFACT_PATH = REPO_ROOT / "outputs/replay/p156_db_only_lifecycle_governance_audit_20260529.json"

CANONICAL_REPO   = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

VALID_CLASSIFICATIONS = {
    "P156_DB_ONLY_LIFECYCLE_GOVERNANCE_AUDIT_READY",
    "P156_SCOPE_REALIGNED_DB_ONLY_COUNT_CHANGED",
    "P156_DB_ONLY_LIFECYCLE_UPDATE_REQUIRES_AUTHORIZATION_GATE",
    "P156_STOP_SCOPE_REALIGNMENT_REQUIRED",
}

EXPECTED_DB_ONLY_IDS = {
    "539_3bet_orthogonal","acb_single_539","bet2_fourier_expansion_biglotto",
    "biglotto_echo_aware_3bet","biglotto_ts3_markov_4bet_w30","cold_complement_2bet",
    "cold_complement_biglotto","coldpool15_biglotto","daily539_f4cold_3bet",
    "daily539_f4cold_5bet","fourier30_markov30_2bet","fourier30_markov30_biglotto",
    "markov_1bet_539","markov_2bet_biglotto","markov_single_biglotto",
    "midfreq_fourier_mk_3bet","p0b_539_3bet_f_cold_fmid","p0c_539_3bet_f_cold_x2",
    "power_fourier_rhythm_2bet","pp3_freqort_4bet","zonal_entropy_2bet","zone_gap_3bet_539"
}


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_PATH.exists(), f"P156 artifact missing: {ARTIFACT_PATH}"
    return json.loads(ARTIFACT_PATH.read_text())


@pytest.fixture(scope="module")
def matrix(artifact):
    return {m["strategy_id"]: m for m in artifact["lifecycle_recommendation_matrix"]}


# ── Artifact basics ───────────────────────────────────────────────────────────

def test_artifact_exists():
    assert ARTIFACT_PATH.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P156"


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


def test_p154_ok(artifact):
    assert artifact["p154_source_summary"]["ok"] is True


# ── DB_ONLY inventory ─────────────────────────────────────────────────────────

def test_expected_count(artifact):
    assert artifact["db_only_lifecycle_inventory"]["expected_db_only_count_from_p154"] == 22


def test_actual_count(artifact):
    assert artifact["db_only_lifecycle_inventory"]["actual_db_only_count"] == 22


def test_all_22_strategy_ids(artifact):
    actual = set(artifact["db_only_lifecycle_inventory"]["strategy_ids"])
    assert actual == EXPECTED_DB_ONLY_IDS


def test_no_discrepancy(artifact):
    assert artifact["db_only_lifecycle_inventory"]["discrepancy_if_any"] is None


# ── Recommendation matrix ─────────────────────────────────────────────────────

def test_matrix_has_22_entries(artifact):
    assert len(artifact["lifecycle_recommendation_matrix"]) == 22


def test_all_have_recommended_lifecycle(matrix):
    for sid, m in matrix.items():
        assert m["recommended_lifecycle"] in {"ONLINE", "RETIRED", "REJECTED", "OFFLINE", "OBSERVATION", "CANDIDATE", "UNKNOWN_NEEDS_REVIEW"}, f"{sid}: invalid lifecycle"


def test_all_have_confidence(matrix):
    for sid, m in matrix.items():
        assert m["confidence"] in {"HIGH", "MEDIUM", "LOW"}, f"{sid}: invalid confidence"


def test_all_have_reason(matrix):
    for _, m in matrix.items():
        assert m["reason"] and len(m["reason"]) > 10


def test_all_have_current_lifecycle(matrix):
    for _, m in matrix.items():
        assert m["current_lifecycle"] == "DB_ONLY_MISSING_LIFECYCLE"


def test_all_have_replay_rows(matrix):
    for sid, m in matrix.items():
        assert m["replay_rows_count"] > 0, f"{sid}: expected rows > 0"


# ── Group A: ONLINE active multi-bet ─────────────────────────────────────────

def test_group_a_biglotto_echo_aware(matrix):
    m = matrix["biglotto_echo_aware_3bet"]
    assert m["recommended_lifecycle"] == "ONLINE"
    assert m["confidence"] == "HIGH"
    assert m["replay_rows_count"] > 0


def test_group_a_daily539_f4cold_5bet(matrix):
    m = matrix["daily539_f4cold_5bet"]
    assert m["recommended_lifecycle"] == "ONLINE"
    assert m["max_bet_index"] == 5


def test_group_a_pp3_freqort_4bet(matrix):
    m = matrix["pp3_freqort_4bet"]
    assert m["recommended_lifecycle"] == "ONLINE"
    assert m["max_bet_index"] >= 4


# ── Group D: RETIRED BIG_LOTTO wave3 ─────────────────────────────────────────

def test_group_d_fourier30_biglotto_retired(matrix):
    m = matrix["fourier30_markov30_biglotto"]
    assert m["recommended_lifecycle"] == "RETIRED"
    assert m["requires_human_review"] is True


def test_group_d_markov_single_biglotto(matrix):
    m = matrix["markov_single_biglotto"]
    assert m["recommended_lifecycle"] == "RETIRED"


def test_group_d_all_biglotto_wave3_retired(matrix):
    group_d = ["bet2_fourier_expansion_biglotto", "cold_complement_biglotto", "coldpool15_biglotto",
               "fourier30_markov30_biglotto", "markov_2bet_biglotto", "markov_single_biglotto"]
    for sid in group_d:
        assert matrix[sid]["recommended_lifecycle"] == "RETIRED", f"{sid} not RETIRED"


# ── Group C: RETIRED DAILY_539 wave2 ─────────────────────────────────────────

def test_group_c_all_539_wave2_retired(matrix):
    group_c = ["539_3bet_orthogonal", "acb_single_539", "markov_1bet_539",
               "p0b_539_3bet_f_cold_fmid", "p0c_539_3bet_f_cold_x2", "zone_gap_3bet_539"]
    for sid in group_c:
        assert matrix[sid]["recommended_lifecycle"] == "RETIRED", f"{sid} not RETIRED"


# ── Decision groups ───────────────────────────────────────────────────────────

def test_decision_groups_total_is_22(artifact):
    dg = artifact["recommended_decision_groups"]
    total = (dg["recommended_online_count"] +
             dg["recommended_retiired_or_retired_count"] +
             dg["recommended_rejected_count"] +
             dg["recommended_offline_count"] +
             dg["recommended_observation_count"] +
             dg["recommended_candidate_count"] +
             dg["unknown_needs_review_count"])
    assert total == 22


def test_online_count(artifact):
    assert artifact["recommended_decision_groups"]["recommended_online_count"] == 10


def test_retired_count(artifact):
    assert artifact["recommended_decision_groups"]["recommended_retiired_or_retired_count"] == 12


def test_human_review_count(artifact):
    assert artifact["recommended_decision_groups"]["human_review_required_count"] == 4


# ── Registry storage assessment ──────────────────────────────────────────────

def test_registry_is_source_controlled(artifact):
    assert artifact["registry_storage_assessment"]["registry_is_source_controlled"] is True


def test_no_db_mutation_required(artifact):
    assert artifact["registry_storage_assessment"]["db_mutation_required_for_lifecycle_update"] is False


def test_safe_to_update_false(artifact):
    assert artifact["registry_storage_assessment"]["safe_to_update_in_p156"] is False


# ── Authorization gate ────────────────────────────────────────────────────────

def test_p156b_required(artifact):
    assert artifact["authorization_gate_requirement"]["p156b_required"] is True


def test_p156b_has_phrase_template(artifact):
    template = artifact["authorization_gate_requirement"]["exact_authorization_phrase_template"]
    assert "{strategy_id}" in template and "{recommended_lifecycle}" in template


# ── Non-actions ───────────────────────────────────────────────────────────────

def test_no_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p156"] is False


def test_no_lifecycle_update(artifact):
    assert artifact["non_actions"]["lifecycle_update_executed_in_p156"] is False


def test_no_replay_rows(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p156"] == 0
    assert artifact["non_actions"]["replay_rows_updated_in_p156"] == 0
    assert artifact["non_actions"]["replay_rows_deleted_in_p156"] == 0


def test_no_live_api(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


def test_no_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p156"] is False


# ── Hygiene ───────────────────────────────────────────────────────────────────

def test_backups_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


def test_no_forbidden_staged(artifact):
    assert artifact["dirty_file_hygiene"]["forbidden_files_staged"] is False


def test_no_db_files_in_staged():
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=CANONICAL_REPO,
    )
    staged = r.stdout.strip().splitlines()
    forbidden = [
        f for f in staged
        if "lottery_v2.db" in f or "replay_lifecycle_drift_guard.py" in f
        or f.startswith("backups/") or f.endswith(".pyc")
        or "replay_strategy_registry.py" in f
    ]
    assert forbidden == [], f"Forbidden staged: {forbidden}"
