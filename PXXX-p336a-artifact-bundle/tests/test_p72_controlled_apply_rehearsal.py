"""
P72 Controlled Apply Rehearsal Gate — Governance Test Suite.

Verifies all invariants for the P72 rehearsal gate artifacts:
- JSON and markdown exist
- Authorization mode is REHEARSAL_ONLY
- 8 candidates confirmed across 4 batches
- Exclusions confirmed
- No DB write, no force push, no lifecycle promotion, no registry mutation
- Batch B2 dual strategy_id mitigation documented
- B2/B3 lifecycle gate (RETIRED) documented
- Future apply gated behind explicit authorization
"""

import json
import os
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(REPO_ROOT, "outputs", "replay", "p72_controlled_apply_rehearsal_20260526.json")
DOC_PATH = os.path.join(REPO_ROOT, "docs", "replay", "p72_controlled_apply_rehearsal_20260526.md")


@pytest.fixture(scope="module")
def p72_json():
    with open(JSON_PATH, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Existence
# ---------------------------------------------------------------------------

def test_json_exists():
    assert os.path.isfile(JSON_PATH), f"P72 JSON not found: {JSON_PATH}"


def test_doc_exists():
    assert os.path.isfile(DOC_PATH), f"P72 markdown not found: {DOC_PATH}"


# ---------------------------------------------------------------------------
# Project lock
# ---------------------------------------------------------------------------

def test_project_context_lock(p72_json):
    assert p72_json["project_context_lock"] == "LotteryNew"


def test_task_field(p72_json):
    assert p72_json["task"] == "P72_CONTROLLED_APPLY_REHEARSAL"


# ---------------------------------------------------------------------------
# Authorization mode
# ---------------------------------------------------------------------------

def test_authorization_mode_is_rehearsal_only(p72_json):
    assert p72_json["authorization_mode"] == "REHEARSAL_ONLY"


def test_no_production_apply(p72_json):
    assert p72_json["no_production_apply"] is True


def test_no_db_write(p72_json):
    assert p72_json["no_db_write"] is True


def test_proposed_row_impact_no_db_write(p72_json):
    assert p72_json["proposed_row_impact"]["no_db_write_in_p72"] is True
    assert p72_json["proposed_row_impact"]["rehearsal_only"] is True


# ---------------------------------------------------------------------------
# Production rows
# ---------------------------------------------------------------------------

def test_production_rows_before(p72_json):
    assert p72_json["production_rows_before"] == 46960


def test_production_rows_after(p72_json):
    assert p72_json["production_rows_after"] == 46960


def test_proposed_row_impact_before(p72_json):
    assert p72_json["proposed_row_impact"]["production_rows_before"] == 46960


def test_proposed_row_impact_after_rehearsal(p72_json):
    assert p72_json["proposed_row_impact"]["production_rows_after_p72_rehearsal"] == 46960


# ---------------------------------------------------------------------------
# Candidate count
# ---------------------------------------------------------------------------

def test_candidate_count(p72_json):
    assert p72_json["candidate_count"] == 8


# ---------------------------------------------------------------------------
# Batch A — POWER_LOTTO
# ---------------------------------------------------------------------------

def test_batch_a_strategies(p72_json):
    batch = p72_json["batches"]["batch_A"]
    assert "fourier_rhythm_3bet" in batch["strategies"]
    assert "fourier30_markov30_2bet" in batch["strategies"]


def test_batch_a_lottery_type(p72_json):
    assert p72_json["batches"]["batch_A"]["lottery_type"] == "POWER_LOTTO"


def test_batch_a_sequence(p72_json):
    assert p72_json["batches"]["batch_A"]["sequence"] == 1


def test_batch_a_no_temp_rehearsal(p72_json):
    assert p72_json["batches"]["batch_A"]["temp_rehearsal_required"] is False


def test_batch_a_p71_readiness(p72_json):
    assert p72_json["batches"]["batch_A"]["p71_readiness"] == "READY_FOR_CONTROLLED_APPLY"


def test_batch_a_gate_result(p72_json):
    assert p72_json["rehearsal_results_by_batch"]["batch_A"]["gate_result"] == "REHEARSAL_READY"


# ---------------------------------------------------------------------------
# Batch B1 — DAILY_539
# ---------------------------------------------------------------------------

def test_batch_b1_strategies(p72_json):
    batch = p72_json["batches"]["batch_B1"]
    assert "539_3bet_orthogonal" in batch["strategies"]
    assert "acb_single_539" in batch["strategies"]


def test_batch_b1_lottery_type(p72_json):
    assert p72_json["batches"]["batch_B1"]["lottery_type"] == "DAILY_539"


def test_batch_b1_sequence(p72_json):
    assert p72_json["batches"]["batch_B1"]["sequence"] == 2


def test_batch_b1_no_temp_rehearsal(p72_json):
    assert p72_json["batches"]["batch_B1"]["temp_rehearsal_required"] is False


def test_batch_b1_p71_readiness(p72_json):
    assert p72_json["batches"]["batch_B1"]["p71_readiness"] == "READY_FOR_CONTROLLED_APPLY"


def test_batch_b1_gate_result(p72_json):
    assert p72_json["rehearsal_results_by_batch"]["batch_B1"]["gate_result"] == "REHEARSAL_READY"


# ---------------------------------------------------------------------------
# Batch B2 — DAILY_539 (RETIRED + dual ID risk)
# ---------------------------------------------------------------------------

def test_batch_b2_strategies(p72_json):
    batch = p72_json["batches"]["batch_B2"]
    assert "midfreq_acb_2bet" in batch["strategies"]
    assert "midfreq_fourier_2bet" in batch["strategies"]


def test_batch_b2_lottery_type(p72_json):
    assert p72_json["batches"]["batch_B2"]["lottery_type"] == "DAILY_539"


def test_batch_b2_sequence(p72_json):
    assert p72_json["batches"]["batch_B2"]["sequence"] == 3


def test_batch_b2_temp_rehearsal_required(p72_json):
    assert p72_json["batches"]["batch_B2"]["temp_rehearsal_required"] is True


def test_batch_b2_p71_readiness(p72_json):
    assert p72_json["batches"]["batch_B2"]["p71_readiness"] == "READY_AFTER_TEMP_REHEARSAL"


def test_batch_b2_gate_result(p72_json):
    assert p72_json["rehearsal_results_by_batch"]["batch_B2"]["gate_result"] == "REHEARSAL_READY"


def test_batch_b2_lifecycle_gate(p72_json):
    assert p72_json["rehearsal_results_by_batch"]["batch_B2"]["lifecycle_gate"] == "RETIRED_PROMOTION_REQUIRED_BEFORE_PRODUCTION"


def test_batch_b2_dual_id_mitigation_documented(p72_json):
    mitigation = p72_json["rehearsal_results_by_batch"]["batch_B2"]["dual_id_mitigation"]
    assert "DAILY_539" in mitigation
    assert "POWER_LOTTO" in mitigation


# ---------------------------------------------------------------------------
# Batch B3 — DAILY_539 (RETIRED)
# ---------------------------------------------------------------------------

def test_batch_b3_strategies(p72_json):
    batch = p72_json["batches"]["batch_B3"]
    assert "acb_1bet" in batch["strategies"]
    assert "acb_markov_midfreq_3bet" in batch["strategies"]


def test_batch_b3_lottery_type(p72_json):
    assert p72_json["batches"]["batch_B3"]["lottery_type"] == "DAILY_539"


def test_batch_b3_sequence(p72_json):
    assert p72_json["batches"]["batch_B3"]["sequence"] == 4


def test_batch_b3_temp_rehearsal_required(p72_json):
    assert p72_json["batches"]["batch_B3"]["temp_rehearsal_required"] is True


def test_batch_b3_p71_readiness(p72_json):
    assert p72_json["batches"]["batch_B3"]["p71_readiness"] == "READY_AFTER_TEMP_REHEARSAL"


def test_batch_b3_gate_result(p72_json):
    assert p72_json["rehearsal_results_by_batch"]["batch_B3"]["gate_result"] == "REHEARSAL_READY"


def test_batch_b3_lifecycle_gate(p72_json):
    assert p72_json["rehearsal_results_by_batch"]["batch_B3"]["lifecycle_gate"] == "RETIRED_PROMOTION_REQUIRED_BEFORE_PRODUCTION"


# ---------------------------------------------------------------------------
# Per-strategy: Batch B2 midfreq_fourier_2bet dual ID
# ---------------------------------------------------------------------------

def test_midfreq_fourier_2bet_dual_id_risk(p72_json):
    s = p72_json["rehearsal_results_by_strategy"]["midfreq_fourier_2bet"]
    assert s["dual_strategy_id_risk"] is True


def test_midfreq_fourier_2bet_power_lotto_rows(p72_json):
    s = p72_json["rehearsal_results_by_strategy"]["midfreq_fourier_2bet"]
    assert s["power_lotto_rows_current"] == 1500


def test_midfreq_fourier_2bet_lottery_type_filter(p72_json):
    s = p72_json["rehearsal_results_by_strategy"]["midfreq_fourier_2bet"]
    assert s["lottery_type_filter_enforced"] == "DAILY_539"


def test_midfreq_fourier_2bet_lottery_type(p72_json):
    s = p72_json["rehearsal_results_by_strategy"]["midfreq_fourier_2bet"]
    assert s["lottery_type"] == "DAILY_539"


# ---------------------------------------------------------------------------
# Per-strategy: existing_rows = 1500
# ---------------------------------------------------------------------------

def test_fourier_rhythm_3bet_existing_rows(p72_json):
    assert p72_json["rehearsal_results_by_strategy"]["fourier_rhythm_3bet"]["existing_rows"] == 1500


def test_fourier30_markov30_2bet_existing_rows(p72_json):
    assert p72_json["rehearsal_results_by_strategy"]["fourier30_markov30_2bet"]["existing_rows"] == 1500


def test_539_3bet_orthogonal_existing_rows(p72_json):
    assert p72_json["rehearsal_results_by_strategy"]["539_3bet_orthogonal"]["existing_rows"] == 1500


def test_acb_single_539_existing_rows(p72_json):
    assert p72_json["rehearsal_results_by_strategy"]["acb_single_539"]["existing_rows"] == 1500


def test_midfreq_acb_2bet_existing_rows(p72_json):
    assert p72_json["rehearsal_results_by_strategy"]["midfreq_acb_2bet"]["existing_rows"] == 1500


def test_midfreq_fourier_2bet_existing_rows(p72_json):
    assert p72_json["rehearsal_results_by_strategy"]["midfreq_fourier_2bet"]["existing_rows"] == 1500


def test_acb_1bet_existing_rows(p72_json):
    assert p72_json["rehearsal_results_by_strategy"]["acb_1bet"]["existing_rows"] == 1500


def test_acb_markov_midfreq_3bet_existing_rows(p72_json):
    assert p72_json["rehearsal_results_by_strategy"]["acb_markov_midfreq_3bet"]["existing_rows"] == 1500


# ---------------------------------------------------------------------------
# Exclusions
# ---------------------------------------------------------------------------

def _excluded_ids(p72_json):
    return [e["strategy_id"] for e in p72_json["excluded_strategies"]]


def test_big_lotto_excluded(p72_json):
    excluded = _excluded_ids(p72_json)
    assert any("BIG_LOTTO" in e for e in excluded)


def test_cold_complement_2bet_excluded(p72_json):
    cold = next((e for e in p72_json["excluded_strategies"] if e["strategy_id"] == "cold_complement_2bet"), None)
    assert cold is not None
    assert cold["classification"] == "EXCLUDED_SUB_BASELINE"


def test_zonal_entropy_2bet_excluded(p72_json):
    zonal = next((e for e in p72_json["excluded_strategies"] if e["strategy_id"] == "zonal_entropy_2bet"), None)
    assert zonal is not None
    assert zonal["classification"] == "EXCLUDED_FALLBACK_EQUIVALENT"


def test_midfreq_fourier_mk_3bet_excluded(p72_json):
    mk = next((e for e in p72_json["excluded_strategies"] if e["strategy_id"] == "midfreq_fourier_mk_3bet"), None)
    assert mk is not None
    assert mk["classification"] == "EXCLUDED_DEFERRED_OOS"


# ---------------------------------------------------------------------------
# Governance flags
# ---------------------------------------------------------------------------

def test_no_force_push(p72_json):
    assert p72_json["no_force_push"] is True


def test_no_lifecycle_promotion(p72_json):
    assert p72_json["no_lifecycle_promotion"] is True


def test_no_champion_replacement(p72_json):
    assert p72_json["no_champion_replacement"] is True


def test_no_registry_mutation(p72_json):
    assert p72_json["no_registry_mutation"] is True


def test_requires_future_explicit_apply_authorization(p72_json):
    assert p72_json["requires_future_explicit_apply_authorization"] is True


# ---------------------------------------------------------------------------
# Row impact
# ---------------------------------------------------------------------------

def test_if_all_8_applied_new_rows(p72_json):
    assert p72_json["proposed_row_impact"]["if_all_8_applied_at_1500"]["total_new_rows"] == 12000


def test_if_all_8_applied_rows_after(p72_json):
    assert p72_json["proposed_row_impact"]["if_all_8_applied_at_1500"]["production_rows_after"] == 58960


def test_if_active_only_new_rows(p72_json):
    assert p72_json["proposed_row_impact"]["if_only_active_lifecycle_4_applied"]["total_new_rows"] == 6000


def test_if_active_only_rows_after(p72_json):
    assert p72_json["proposed_row_impact"]["if_only_active_lifecycle_4_applied"]["production_rows_after"] == 52960


# ---------------------------------------------------------------------------
# Required future apply gates
# ---------------------------------------------------------------------------

def test_all_batches_require_explicit_apply_authorization(p72_json):
    gates = p72_json["required_future_apply_gates"]["all_batches"]
    assert "explicit_apply_authorization_phrase_YES_apply_P71_controlled_replay_rows" in gates


def test_all_batches_require_temp_rehearsal_gate(p72_json):
    gates = p72_json["required_future_apply_gates"]["all_batches"]
    assert "temp_db_rehearsal_pass" in gates


def test_all_batches_require_duplicate_check(p72_json):
    gates = p72_json["required_future_apply_gates"]["all_batches"]
    assert "duplicate_check_pass" in gates


def test_b2_b3_require_lifecycle_promotion_gate(p72_json):
    gates = p72_json["required_future_apply_gates"]["batch_B2_B3_additional"]
    assert "lifecycle_promotion_gate" in gates


def test_b2_requires_lottery_type_filter_gate(p72_json):
    gates = p72_json["required_future_apply_gates"]["batch_B2_midfreq_fourier_2bet_additional"]
    assert "lottery_type_filter_confirmed_DAILY_539" in gates


def test_b2_requires_power_lotto_row_check_gate(p72_json):
    gates = p72_json["required_future_apply_gates"]["batch_B2_midfreq_fourier_2bet_additional"]
    assert "post_apply_power_lotto_rows_still_1500" in gates


# ---------------------------------------------------------------------------
# Guard results
# ---------------------------------------------------------------------------

def test_guard_drift_pass(p72_json):
    assert p72_json["guard_results"]["drift_guard"] == "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS"


def test_guard_branch_governance_pass(p72_json):
    assert p72_json["guard_results"]["branch_governance"] == "BRANCH_GOVERNANCE_PASS"


def test_guard_contamination_clean(p72_json):
    assert p72_json["guard_results"]["cross_project_contamination"] == "CLEAN"


# ---------------------------------------------------------------------------
# Naming scheme
# ---------------------------------------------------------------------------

def test_naming_scheme_rehearsal_pattern(p72_json):
    scheme = p72_json["controlled_apply_id_naming_scheme"]
    assert "rehearsal_pattern" in scheme
    assert "REHEARSAL" in scheme["rehearsal_pattern"]


def test_naming_scheme_examples(p72_json):
    examples = p72_json["controlled_apply_id_naming_scheme"]["examples"]
    assert "batch_A_rehearsal_1" in examples
    assert "batch_B1_rehearsal_1" in examples
    assert "batch_B2_rehearsal_1" in examples
    assert "batch_B3_rehearsal_1" in examples


# ---------------------------------------------------------------------------
# Final classification
# ---------------------------------------------------------------------------

def test_final_classification(p72_json):
    assert p72_json["final_classification"] == "P72_CONTROLLED_APPLY_REHEARSAL_MERGED_TO_MAIN"


# ---------------------------------------------------------------------------
# Doc content checks
# ---------------------------------------------------------------------------

def test_doc_contains_project_context_lock():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "PROJECT_CONTEXT_LOCK" in content


def test_doc_contains_rehearsal_only():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "REHEARSAL_ONLY" in content


def test_doc_contains_final_classification():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "P72_CONTROLLED_APPLY_REHEARSAL_MERGED_TO_MAIN" in content


def test_doc_contains_no_db_write_confirmation():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "No DB write in P72" in content


def test_doc_contains_no_force_push():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "No force push" in content


def test_doc_contains_dual_id_risk():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "midfreq_fourier_2bet" in content
    assert "POWER_LOTTO" in content


def test_doc_contains_retired_lifecycle_note():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "RETIRED" in content
