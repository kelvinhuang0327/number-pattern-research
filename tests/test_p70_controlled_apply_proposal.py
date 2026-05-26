"""
tests/test_p70_controlled_apply_proposal.py

Governance tests for P70 Controlled Apply Proposal.
Asserts all required invariants for the proposal artifact.

PROJECT_CONTEXT_LOCK = LotteryNew
"""
import json
import os
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(ROOT, "outputs", "replay", "p70_controlled_apply_proposal_20260526.json")
DOC_PATH = os.path.join(ROOT, "docs", "replay", "p70_controlled_apply_proposal_20260526.md")


@pytest.fixture(scope="module")
def proposal():
    with open(JSON_PATH, "r") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def doc_content():
    with open(DOC_PATH, "r") as f:
        return f.read()


# --- File existence ---

def test_json_exists():
    assert os.path.exists(JSON_PATH), f"P70 JSON not found: {JSON_PATH}"


def test_doc_exists():
    assert os.path.exists(DOC_PATH), f"P70 doc not found: {DOC_PATH}"


# --- project_context_lock ---

def test_project_context_lock(proposal):
    assert proposal["project_context_lock"] == "LotteryNew"


def test_doc_project_context_lock(doc_content):
    assert "PROJECT_CONTEXT_LOCK" in doc_content
    assert "LotteryNew" in doc_content


# --- Production rows ---

def test_production_rows_before(proposal):
    assert proposal["production_rows_before"] == 46960


def test_production_rows_after(proposal):
    assert proposal["production_rows_after"] == 46960


def test_doc_production_rows_before(doc_content):
    assert "46960" in doc_content


# --- Candidate count ---

def test_authorized_candidate_count(proposal):
    assert proposal["authorized_candidate_count"] == 8


def test_authorized_candidates_list_length(proposal):
    assert len(proposal["authorized_candidates"]) == 8


# --- POWER_LOTTO candidates ---

def test_power_lotto_fourier_rhythm_3bet(proposal):
    ids = [c["strategy_id"] for c in proposal["authorized_candidates"] if c["lottery_type"] == "POWER_LOTTO"]
    assert "fourier_rhythm_3bet" in ids


def test_power_lotto_fourier30_markov30_2bet(proposal):
    ids = [c["strategy_id"] for c in proposal["authorized_candidates"] if c["lottery_type"] == "POWER_LOTTO"]
    assert "fourier30_markov30_2bet" in ids


# --- DAILY_539 candidates ---

def test_daily_539_acb_1bet(proposal):
    ids = [c["strategy_id"] for c in proposal["authorized_candidates"] if c["lottery_type"] == "DAILY_539"]
    assert "acb_1bet" in ids


def test_daily_539_acb_markov_midfreq_3bet(proposal):
    ids = [c["strategy_id"] for c in proposal["authorized_candidates"] if c["lottery_type"] == "DAILY_539"]
    assert "acb_markov_midfreq_3bet" in ids


def test_daily_539_midfreq_acb_2bet(proposal):
    ids = [c["strategy_id"] for c in proposal["authorized_candidates"] if c["lottery_type"] == "DAILY_539"]
    assert "midfreq_acb_2bet" in ids


def test_daily_539_midfreq_fourier_2bet(proposal):
    ids = [c["strategy_id"] for c in proposal["authorized_candidates"] if c["lottery_type"] == "DAILY_539"]
    assert "midfreq_fourier_2bet" in ids


def test_daily_539_539_3bet_orthogonal(proposal):
    ids = [c["strategy_id"] for c in proposal["authorized_candidates"] if c["lottery_type"] == "DAILY_539"]
    assert "539_3bet_orthogonal" in ids


def test_daily_539_acb_single_539(proposal):
    ids = [c["strategy_id"] for c in proposal["authorized_candidates"] if c["lottery_type"] == "DAILY_539"]
    assert "acb_single_539" in ids


def test_exactly_2_power_lotto_candidates(proposal):
    pl = [c for c in proposal["authorized_candidates"] if c["lottery_type"] == "POWER_LOTTO"]
    assert len(pl) == 2


def test_exactly_6_daily_539_candidates(proposal):
    d539 = [c for c in proposal["authorized_candidates"] if c["lottery_type"] == "DAILY_539"]
    assert len(d539) == 6


# --- Exclusions ---

def test_big_lotto_excluded(proposal):
    excluded = proposal["excluded_candidates"]
    assert "BIG_LOTTO_excluded_reason" in excluded


def test_cold_complement_2bet_excluded_as_sub_baseline(proposal):
    excluded = proposal["excluded_candidates"]
    assert "cold_complement_2bet" in excluded
    assert excluded["cold_complement_2bet"]["reason"] == "sub-baseline"


def test_zonal_entropy_2bet_excluded_as_fallback_equivalent(proposal):
    excluded = proposal["excluded_candidates"]
    assert "zonal_entropy_2bet" in excluded
    assert excluded["zonal_entropy_2bet"]["reason"] == "fallback-equivalent"


def test_midfreq_fourier_mk_3bet_deferred_pending_oos(proposal):
    excluded = proposal["excluded_candidates"]
    assert "midfreq_fourier_mk_3bet" in excluded
    assert "deferred" in excluded["midfreq_fourier_mk_3bet"]["reason"].lower() or \
           "OOS" in excluded["midfreq_fourier_mk_3bet"]["reason"]


# --- Governance flags ---

def test_no_db_write(proposal):
    assert proposal["no_db_write"] is True


def test_no_force_push(proposal):
    assert proposal["no_force_push"] is True


def test_no_lifecycle_promotion(proposal):
    assert proposal["no_lifecycle_promotion"] is True


def test_no_champion_replacement(proposal):
    assert proposal["no_champion_replacement"] is True


def test_no_registry_mutation(proposal):
    assert proposal["no_registry_mutation"] is True


def test_no_production_apply(proposal):
    assert proposal["no_production_apply"] is True


def test_requires_future_explicit_apply_authorization(proposal):
    assert proposal["requires_future_explicit_apply_authorization"] is True


# --- Real apply gating ---

def test_real_apply_gated_behind_explicit_authorization(proposal):
    gates = proposal["required_apply_gates"]["all_batches"]
    assert "explicit_apply_authorization_phrase_in_future_task" in gates


def test_real_apply_gated_behind_temp_rehearsal(proposal):
    gates = proposal["required_apply_gates"]["all_batches"]
    assert "temp_db_rehearsal_pass" in gates


def test_real_apply_gated_behind_duplicate_check(proposal):
    gates = proposal["required_apply_gates"]["all_batches"]
    assert "duplicate_check_pass" in gates


def test_real_apply_gated_behind_rollback_plan(proposal):
    gates = proposal["required_apply_gates"]["all_batches"]
    assert "rollback_plan_confirmed" in gates


def test_real_apply_gated_behind_branch_governance(proposal):
    gates = proposal["required_apply_gates"]["all_batches"]
    assert "branch_governance_guard_pass" in gates


def test_real_apply_gated_behind_drift_guard(proposal):
    gates = proposal["required_apply_gates"]["all_batches"]
    assert "replay_lifecycle_drift_guard_pass" in gates


def test_real_apply_gated_behind_api_verification(proposal):
    gates = proposal["required_apply_gates"]["all_batches"]
    assert "api_verification_pass" in gates


# --- RETIRED lifecycle gating ---

def test_retired_lifecycle_batches_require_promotion_gate(proposal):
    retired_gates = proposal["required_apply_gates"]["retired_lifecycle_batches_additional"]
    assert "lifecycle_promotion_gate" in retired_gates


def test_midfreq_fourier_2bet_lottery_type_filter_gate(proposal):
    midfreq = [c for c in proposal["authorized_candidates"] if c["strategy_id"] == "midfreq_fourier_2bet"][0]
    assert "lottery_type_filter_confirmed_DAILY_539" in midfreq["dependencies"]


def test_midfreq_fourier_2bet_daily_539_only(proposal):
    midfreq_candidates = [c for c in proposal["authorized_candidates"]
                          if c["strategy_id"] == "midfreq_fourier_2bet"]
    assert len(midfreq_candidates) == 1
    assert midfreq_candidates[0]["lottery_type"] == "DAILY_539"


# --- Row impact consistency ---

def test_row_impact_all_8_before(proposal):
    assert proposal["proposed_row_impact"]["if_all_8_applied_at_1500"]["production_rows_before"] == 46960


def test_row_impact_all_8_after(proposal):
    assert proposal["proposed_row_impact"]["if_all_8_applied_at_1500"]["production_rows_after"] == 58960


def test_row_impact_all_8_total_new_rows(proposal):
    assert proposal["proposed_row_impact"]["if_all_8_applied_at_1500"]["total_new_rows"] == 12000


def test_no_db_write_in_p70_flag(proposal):
    assert proposal["proposed_row_impact"]["no_db_write_in_p70"] is True


# --- Batch plan structure ---

def test_batch_A_contains_power_lotto_strategies(proposal):
    batch_a = proposal["apply_proposal_batches"]["batch_A"]
    assert "fourier_rhythm_3bet" in batch_a["strategies"]
    assert "fourier30_markov30_2bet" in batch_a["strategies"]
    assert batch_a["game_type"] == "POWER_LOTTO"


def test_batch_B1_contains_active_daily_539(proposal):
    batch_b1 = proposal["apply_proposal_batches"]["batch_B1"]
    assert "539_3bet_orthogonal" in batch_b1["strategies"]
    assert "acb_single_539" in batch_b1["strategies"]
    assert batch_b1["game_type"] == "DAILY_539"


def test_batch_B2_requires_temp_rehearsal(proposal):
    batch_b2 = proposal["apply_proposal_batches"]["batch_B2"]
    assert batch_b2["temp_rehearsal_required"] is True


def test_batch_B3_requires_temp_rehearsal(proposal):
    batch_b3 = proposal["apply_proposal_batches"]["batch_B3"]
    assert batch_b3["temp_rehearsal_required"] is True


def test_batch_A_does_not_require_temp_rehearsal(proposal):
    batch_a = proposal["apply_proposal_batches"]["batch_A"]
    assert batch_a["temp_rehearsal_required"] is False


def test_batch_B1_does_not_require_temp_rehearsal(proposal):
    batch_b1 = proposal["apply_proposal_batches"]["batch_B1"]
    assert batch_b1["temp_rehearsal_required"] is False


def test_batch_sequencing_order(proposal):
    batches = proposal["apply_proposal_batches"]
    assert batches["batch_A"]["sequence"] == 1
    assert batches["batch_B1"]["sequence"] == 2
    assert batches["batch_B2"]["sequence"] == 3
    assert batches["batch_B3"]["sequence"] == 4


# --- Final classification ---

def test_final_classification(proposal):
    assert proposal["final_classification"] == "P70_CONTROLLED_APPLY_PROPOSAL_READY"


def test_doc_final_classification(doc_content):
    assert "P70_CONTROLLED_APPLY_PROPOSAL_READY" in doc_content
