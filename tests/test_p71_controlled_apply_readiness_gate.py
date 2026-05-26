"""
P71 Controlled Apply Readiness Gate — Governance Test Suite.

Verifies all invariants for the P71 readiness gate artifacts:
- JSON and markdown exist
- Authorization mode is READINESS_ONLY
- 8 candidates confirmed
- Exclusions confirmed
- No DB write, no force push, no lifecycle promotion, no registry mutation
- Real apply is gated behind explicit authorization + temp rehearsal + duplicate check + rollback
"""

import json
import os
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(REPO_ROOT, "outputs", "replay", "p71_controlled_apply_readiness_gate_20260526.json")
DOC_PATH = os.path.join(REPO_ROOT, "docs", "replay", "p71_controlled_apply_readiness_gate_20260526.md")


@pytest.fixture(scope="module")
def p71_json():
    with open(JSON_PATH, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Existence
# ---------------------------------------------------------------------------

def test_json_exists():
    assert os.path.isfile(JSON_PATH), f"P71 JSON not found: {JSON_PATH}"


def test_doc_exists():
    assert os.path.isfile(DOC_PATH), f"P71 markdown not found: {DOC_PATH}"


# ---------------------------------------------------------------------------
# Project lock
# ---------------------------------------------------------------------------

def test_project_context_lock(p71_json):
    assert p71_json["project_context_lock"] == "LotteryNew"


def test_task_field(p71_json):
    assert p71_json["task"] == "P71_CONTROLLED_APPLY_READINESS_GATE"


# ---------------------------------------------------------------------------
# Authorization mode
# ---------------------------------------------------------------------------

def test_authorization_mode_is_readiness_only(p71_json):
    assert p71_json["authorization_mode"] == "READINESS_ONLY"


def test_no_production_apply(p71_json):
    assert p71_json["no_production_apply"] is True


def test_no_db_write(p71_json):
    assert p71_json["no_db_write"] is True


def test_proposed_row_impact_no_db_write(p71_json):
    assert p71_json["proposed_row_impact"]["no_db_write_in_p71"] is True
    assert p71_json["proposed_row_impact"]["readiness_only"] is True


# ---------------------------------------------------------------------------
# Production rows
# ---------------------------------------------------------------------------

def test_production_rows_before(p71_json):
    assert p71_json["production_rows_before"] == 46960


def test_production_rows_after(p71_json):
    assert p71_json["production_rows_after"] == 46960


def test_proposed_row_impact_before(p71_json):
    assert p71_json["proposed_row_impact"]["production_rows_before"] == 46960


def test_proposed_row_impact_after_readiness(p71_json):
    assert p71_json["proposed_row_impact"]["production_rows_after_p71_readiness"] == 46960


# ---------------------------------------------------------------------------
# Candidate count
# ---------------------------------------------------------------------------

def test_authorized_candidate_count(p71_json):
    assert p71_json["authorized_candidate_count"] == 8


def test_authorized_candidates_length(p71_json):
    assert len(p71_json["authorized_candidates"]) == 8


# ---------------------------------------------------------------------------
# POWER_LOTTO candidates
# ---------------------------------------------------------------------------

def _candidate_ids(p71_json):
    return {c["strategy_id"] for c in p71_json["authorized_candidates"]}


def test_fourier_rhythm_3bet_present(p71_json):
    ids = _candidate_ids(p71_json)
    assert "fourier_rhythm_3bet" in ids


def test_fourier30_markov30_2bet_present(p71_json):
    ids = _candidate_ids(p71_json)
    assert "fourier30_markov30_2bet" in ids


def test_fourier_rhythm_3bet_lottery_type(p71_json):
    c = next(c for c in p71_json["authorized_candidates"] if c["strategy_id"] == "fourier_rhythm_3bet")
    assert c["lottery_type"] == "POWER_LOTTO"


def test_fourier30_markov30_2bet_lottery_type(p71_json):
    c = next(c for c in p71_json["authorized_candidates"] if c["strategy_id"] == "fourier30_markov30_2bet")
    assert c["lottery_type"] == "POWER_LOTTO"


# ---------------------------------------------------------------------------
# DAILY_539 candidates
# ---------------------------------------------------------------------------

def test_acb_1bet_present(p71_json):
    ids = _candidate_ids(p71_json)
    assert "acb_1bet" in ids


def test_acb_markov_midfreq_3bet_present(p71_json):
    ids = _candidate_ids(p71_json)
    assert "acb_markov_midfreq_3bet" in ids


def test_midfreq_acb_2bet_present(p71_json):
    ids = _candidate_ids(p71_json)
    assert "midfreq_acb_2bet" in ids


def test_midfreq_fourier_2bet_present(p71_json):
    ids = _candidate_ids(p71_json)
    assert "midfreq_fourier_2bet" in ids


def test_539_3bet_orthogonal_present(p71_json):
    ids = _candidate_ids(p71_json)
    assert "539_3bet_orthogonal" in ids


def test_acb_single_539_present(p71_json):
    ids = _candidate_ids(p71_json)
    assert "acb_single_539" in ids


def test_daily_539_candidates_have_correct_lottery_type(p71_json):
    daily_ids = {"acb_1bet", "acb_markov_midfreq_3bet", "midfreq_acb_2bet",
                 "midfreq_fourier_2bet", "539_3bet_orthogonal", "acb_single_539"}
    for c in p71_json["authorized_candidates"]:
        if c["strategy_id"] in daily_ids:
            assert c["lottery_type"] == "DAILY_539", (
                f"{c['strategy_id']} expected DAILY_539 got {c['lottery_type']}"
            )


# ---------------------------------------------------------------------------
# Exclusions
# ---------------------------------------------------------------------------

def _excluded_ids(p71_json):
    return [e["strategy_id"] for e in p71_json["excluded_candidates"]]


def test_big_lotto_excluded(p71_json):
    excluded = _excluded_ids(p71_json)
    assert any("BIG_LOTTO" in e for e in excluded), "BIG_LOTTO must be excluded"


def test_cold_complement_2bet_excluded_sub_baseline(p71_json):
    cold = next(
        (e for e in p71_json["excluded_candidates"] if e["strategy_id"] == "cold_complement_2bet"),
        None,
    )
    assert cold is not None, "cold_complement_2bet must be in excluded_candidates"
    assert cold["reason"] == "sub_baseline"
    assert cold["classification"] == "EXCLUDED_SUB_BASELINE"


def test_zonal_entropy_2bet_excluded_fallback_equivalent(p71_json):
    zonal = next(
        (e for e in p71_json["excluded_candidates"] if e["strategy_id"] == "zonal_entropy_2bet"),
        None,
    )
    assert zonal is not None, "zonal_entropy_2bet must be in excluded_candidates"
    assert zonal["reason"] == "fallback_equivalent"
    assert zonal["classification"] == "EXCLUDED_FALLBACK_EQUIVALENT"


def test_midfreq_fourier_mk_3bet_deferred(p71_json):
    mk = next(
        (e for e in p71_json["excluded_candidates"] if e["strategy_id"] == "midfreq_fourier_mk_3bet"),
        None,
    )
    assert mk is not None, "midfreq_fourier_mk_3bet must be in excluded_candidates"
    assert mk["reason"] == "deferred_pending_oos_gates"
    assert mk["classification"] == "EXCLUDED_DEFERRED_OOS"


# ---------------------------------------------------------------------------
# Governance flags
# ---------------------------------------------------------------------------

def test_no_force_push(p71_json):
    assert p71_json["no_force_push"] is True


def test_no_lifecycle_promotion(p71_json):
    assert p71_json["no_lifecycle_promotion"] is True


def test_no_champion_replacement(p71_json):
    assert p71_json["no_champion_replacement"] is True


def test_no_registry_mutation(p71_json):
    assert p71_json["no_registry_mutation"] is True


def test_requires_future_explicit_apply_authorization(p71_json):
    assert p71_json["requires_future_explicit_apply_authorization"] is True


# ---------------------------------------------------------------------------
# Readiness statuses
# ---------------------------------------------------------------------------

def test_fourier_rhythm_3bet_readiness(p71_json):
    assert p71_json["readiness_by_strategy"]["fourier_rhythm_3bet"] == "READY_FOR_CONTROLLED_APPLY"


def test_fourier30_markov30_2bet_readiness(p71_json):
    assert p71_json["readiness_by_strategy"]["fourier30_markov30_2bet"] == "READY_FOR_CONTROLLED_APPLY"


def test_539_3bet_orthogonal_readiness(p71_json):
    assert p71_json["readiness_by_strategy"]["539_3bet_orthogonal"] == "READY_FOR_CONTROLLED_APPLY"


def test_acb_single_539_readiness(p71_json):
    assert p71_json["readiness_by_strategy"]["acb_single_539"] == "READY_FOR_CONTROLLED_APPLY"


def test_midfreq_acb_2bet_readiness(p71_json):
    assert p71_json["readiness_by_strategy"]["midfreq_acb_2bet"] == "READY_AFTER_TEMP_REHEARSAL"


def test_midfreq_fourier_2bet_readiness(p71_json):
    assert p71_json["readiness_by_strategy"]["midfreq_fourier_2bet"] == "READY_AFTER_TEMP_REHEARSAL"


def test_acb_1bet_readiness(p71_json):
    assert p71_json["readiness_by_strategy"]["acb_1bet"] == "READY_AFTER_TEMP_REHEARSAL"


def test_acb_markov_midfreq_3bet_readiness(p71_json):
    assert p71_json["readiness_by_strategy"]["acb_markov_midfreq_3bet"] == "READY_AFTER_TEMP_REHEARSAL"


# ---------------------------------------------------------------------------
# midfreq_fourier_2bet dual strategy_id risk
# ---------------------------------------------------------------------------

def test_midfreq_fourier_2bet_dual_id_risk_flagged(p71_json):
    c = next(
        c for c in p71_json["authorized_candidates"]
        if c["strategy_id"] == "midfreq_fourier_2bet" and c["lottery_type"] == "DAILY_539"
    )
    assert c["dual_strategy_id_risk"] is True


def test_midfreq_fourier_2bet_power_lotto_rows_documented(p71_json):
    c = next(
        c for c in p71_json["authorized_candidates"]
        if c["strategy_id"] == "midfreq_fourier_2bet" and c["lottery_type"] == "DAILY_539"
    )
    assert c["power_lotto_rows_current"] == 1500


def test_midfreq_fourier_2bet_lottery_type_filter_gate(p71_json):
    gates = p71_json["required_apply_gates"]["midfreq_fourier_2bet_additional"]
    assert "lottery_type_filter_confirmed_DAILY_539" in gates


def test_midfreq_fourier_2bet_power_lotto_unaffected_gate(p71_json):
    gates = p71_json["required_apply_gates"]["midfreq_fourier_2bet_additional"]
    assert "post_apply_power_lotto_rows_still_1500" in gates


# ---------------------------------------------------------------------------
# Batch readiness
# ---------------------------------------------------------------------------

def test_batch_a_readiness(p71_json):
    assert p71_json["batch_readiness_summary"]["batch_A"]["readiness"] == "READY_FOR_CONTROLLED_APPLY"


def test_batch_b1_readiness(p71_json):
    assert p71_json["batch_readiness_summary"]["batch_B1"]["readiness"] == "READY_FOR_CONTROLLED_APPLY"


def test_batch_b2_readiness(p71_json):
    assert p71_json["batch_readiness_summary"]["batch_B2"]["readiness"] == "READY_AFTER_TEMP_REHEARSAL"


def test_batch_b3_readiness(p71_json):
    assert p71_json["batch_readiness_summary"]["batch_B3"]["readiness"] == "READY_AFTER_TEMP_REHEARSAL"


def test_batch_a_sequence(p71_json):
    assert p71_json["batch_readiness_summary"]["batch_A"]["sequence"] == 1


def test_batch_b1_sequence(p71_json):
    assert p71_json["batch_readiness_summary"]["batch_B1"]["sequence"] == 2


def test_batch_b2_sequence(p71_json):
    assert p71_json["batch_readiness_summary"]["batch_B2"]["sequence"] == 3


def test_batch_b3_sequence(p71_json):
    assert p71_json["batch_readiness_summary"]["batch_B3"]["sequence"] == 4


def test_batch_b2_temp_rehearsal_required(p71_json):
    assert p71_json["batch_readiness_summary"]["batch_B2"]["temp_rehearsal_required"] is True


def test_batch_b3_temp_rehearsal_required(p71_json):
    assert p71_json["batch_readiness_summary"]["batch_B3"]["temp_rehearsal_required"] is True


def test_batch_a_no_temp_rehearsal(p71_json):
    assert p71_json["batch_readiness_summary"]["batch_A"]["temp_rehearsal_required"] is False


def test_batch_b1_no_temp_rehearsal(p71_json):
    assert p71_json["batch_readiness_summary"]["batch_B1"]["temp_rehearsal_required"] is False


# ---------------------------------------------------------------------------
# Row impact
# ---------------------------------------------------------------------------

def test_all_8_applied_new_rows(p71_json):
    assert p71_json["proposed_row_impact"]["if_all_8_applied_at_1500"]["total_new_rows"] == 12000


def test_all_8_applied_rows_after(p71_json):
    assert p71_json["proposed_row_impact"]["if_all_8_applied_at_1500"]["production_rows_after"] == 58960


def test_active_only_new_rows(p71_json):
    assert p71_json["proposed_row_impact"]["if_only_active_lifecycle_4_applied"]["total_new_rows"] == 6000


def test_active_only_rows_after(p71_json):
    assert p71_json["proposed_row_impact"]["if_only_active_lifecycle_4_applied"]["production_rows_after"] == 52960


# ---------------------------------------------------------------------------
# Required gates: explicit authorization gate present
# ---------------------------------------------------------------------------

def test_all_batches_require_explicit_apply_authorization(p71_json):
    gates = p71_json["required_apply_gates"]["all_batches"]
    assert "explicit_apply_authorization_phrase_in_future_task" in gates


def test_all_batches_require_temp_rehearsal_gate(p71_json):
    gates = p71_json["required_apply_gates"]["all_batches"]
    assert "temp_db_rehearsal_pass" in gates


def test_all_batches_require_duplicate_check(p71_json):
    gates = p71_json["required_apply_gates"]["all_batches"]
    assert "duplicate_check_pass" in gates


def test_all_batches_require_rollback_plan(p71_json):
    gates = p71_json["required_apply_gates"]["all_batches"]
    assert "rollback_plan_confirmed" in gates


def test_retired_batches_require_lifecycle_promotion(p71_json):
    gates = p71_json["required_apply_gates"]["retired_lifecycle_batches_additional"]
    assert "lifecycle_promotion_gate" in gates


def test_retired_batches_require_temp_rehearsal_evidence(p71_json):
    gates = p71_json["required_apply_gates"]["retired_lifecycle_batches_additional"]
    assert "temp_rehearsal_evidence_committed" in gates


# ---------------------------------------------------------------------------
# Naming scheme
# ---------------------------------------------------------------------------

def test_controlled_apply_id_naming_scheme_present(p71_json):
    scheme = p71_json["controlled_apply_id_naming_scheme"]
    assert "pattern" in scheme
    assert "examples" in scheme
    assert "batch_A" in scheme["examples"]
    assert "batch_B1" in scheme["examples"]
    assert "batch_B2" in scheme["examples"]
    assert "batch_B3" in scheme["examples"]


# ---------------------------------------------------------------------------
# Guard results
# ---------------------------------------------------------------------------

def test_guard_drift_pass(p71_json):
    assert p71_json["guard_results"]["drift_guard"] == "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS"


def test_guard_branch_governance_pass(p71_json):
    assert p71_json["guard_results"]["branch_governance"] == "BRANCH_GOVERNANCE_PASS"


def test_guard_contamination_clean(p71_json):
    assert p71_json["guard_results"]["cross_project_contamination"] == "CLEAN"


# ---------------------------------------------------------------------------
# Final classification
# ---------------------------------------------------------------------------

def test_final_classification(p71_json):
    assert p71_json["final_classification"] == "P71_CONTROLLED_APPLY_READINESS_GATE_READY"


# ---------------------------------------------------------------------------
# Existing rows confirmed in DB (snapshot assertions from pre-flight)
# ---------------------------------------------------------------------------

def test_fourier_rhythm_3bet_existing_rows(p71_json):
    c = next(c for c in p71_json["authorized_candidates"] if c["strategy_id"] == "fourier_rhythm_3bet")
    assert c["existing_rows"] == 1500


def test_midfreq_fourier_2bet_existing_rows(p71_json):
    c = next(
        c for c in p71_json["authorized_candidates"]
        if c["strategy_id"] == "midfreq_fourier_2bet" and c["lottery_type"] == "DAILY_539"
    )
    assert c["existing_rows"] == 1500


def test_doc_contains_project_context_lock():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "PROJECT_CONTEXT_LOCK" in content


def test_doc_contains_readiness_only_mode():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "READINESS_ONLY" in content


def test_doc_contains_final_classification():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "P71_CONTROLLED_APPLY_READINESS_GATE_READY" in content


def test_doc_contains_governance_confirmations():
    with open(DOC_PATH, "r") as f:
        content = f.read()
    assert "No DB write in P71" in content
    assert "No force push" in content
