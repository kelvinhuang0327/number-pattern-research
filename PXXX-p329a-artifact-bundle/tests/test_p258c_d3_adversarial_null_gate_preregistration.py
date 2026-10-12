"""
P258C — D3 AdversarialNullSurvivorGate read-only pre-registration design tests.

Validates the P258C design artifact (JSON + MD) against governance requirements:
- JSON parses; final classification correct
- D3 framed as a validation gate, NOT a prediction model
- improved-accuracy claims banned
- matched adversarial null dimensions present
- P257A baseline comparison + candidate percentile vs matched null
- chronological OOS split, short/mid/long validation
- multiple-testing correction family
- leakage/provenance gates
- DB write / recommendation / production / registry / controlled_apply / deployment all banned
"""

import json
import os
import pytest

ARTIFACT_JSON = os.path.join(
    os.path.dirname(__file__),
    "..",
    "outputs",
    "research",
    "p258c_d3_adversarial_null_gate_preregistration_20260608.json",
)
ARTIFACT_MD = os.path.join(
    os.path.dirname(__file__),
    "..",
    "outputs",
    "research",
    "p258c_d3_adversarial_null_gate_preregistration_20260608.md",
)


@pytest.fixture(scope="module")
def artifact():
    with open(ARTIFACT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Parse / structure
# ---------------------------------------------------------------------------


def test_json_artifact_parses(artifact):
    assert isinstance(artifact, dict)


def test_task_id_is_p258c(artifact):
    assert artifact["task_id"] == "P258C"


def test_md_artifact_exists():
    assert os.path.isfile(ARTIFACT_MD)


def test_final_classification(artifact):
    assert artifact["final_decision"] == "P258C_D3_READ_ONLY_PREREGISTRATION_DESIGN_READY"


# ---------------------------------------------------------------------------
# D3 is a gate, not a predictor; no accuracy claims
# ---------------------------------------------------------------------------


def test_artifact_states_d3_is_not_a_prediction_model(artifact):
    caveat = artifact["d3_methodology_not_predictor_caveat"].lower()
    assert "not a number-prediction" in caveat or "not a prediction" in caveat
    assert "validation" in caveat or "falsification" in caveat


def test_artifact_bans_improved_accuracy_claims(artifact):
    assert artifact["no_improved_accuracy_claim_confirmed"] is True
    assert artifact["explicit_ban"]["no_improved_accuracy_claim"] is True


def test_non_goals_include_not_predictor_and_no_promotion(artifact):
    joined = " ".join(artifact["non_goals"]).lower()
    assert "not a number-prediction" in joined or "not a number" in joined
    assert "auto-approve" in joined or "auto-promote" in joined or "promote" in joined


def test_no_auto_approval_gate_ban(artifact):
    val = artifact["explicit_ban"]["no_auto_approval_gate"].lower()
    assert "auto-approval" in val or "falsification-only" in val or "never promote" in val


# ---------------------------------------------------------------------------
# Matched adversarial null
# ---------------------------------------------------------------------------


def test_matched_null_dimensions_present(artifact):
    dims = artifact["null_matching_dimensions"]
    required = [
        "lottery_type",
        "n_bet_count",
        "number_count_per_bet",
        "window_schedule",
        "candidate_feature_dimensionality",
        "regime_count_or_parameter_count_when_applicable",
        "prediction_cadence",
        "available_information_timestamp_cutoff",
    ]
    for dim in required:
        assert dim in dims, f"Missing null matching dimension: {dim}"


def test_matched_null_family_min_size(artifact):
    assert artifact["matched_adversarial_null_family"]["family_size_min"] >= 1000


def test_matched_null_uses_binomial_not_label_shuffle(artifact):
    methods = " ".join(
        artifact["matched_adversarial_null_family"]["construction_methods"]
    ).lower()
    assert "binomial" in methods


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def test_primary_endpoints_include_p257a_baseline(artifact):
    joined = " ".join(artifact["primary_endpoints"]).lower()
    assert "p257a" in joined
    assert "baseline" in joined


def test_primary_endpoints_include_candidate_percentile_vs_null(artifact):
    joined = " ".join(artifact["primary_endpoints"]).lower()
    assert "percentile" in joined
    assert "null" in joined


def test_secondary_endpoints_high_hit_corrected_only(artifact):
    joined = " ".join(artifact["secondary_endpoints"]).lower()
    assert "hit_count_ge_2" in joined or "ge_2" in joined
    assert "diagnostic_only" in joined


# ---------------------------------------------------------------------------
# OOS split / windows / correction family / leakage
# ---------------------------------------------------------------------------


def test_chronological_oos_split(artifact):
    assert artifact["oos_split_design"]["type"] == "chronological"
    segments = artifact["oos_split_design"]["segments"]
    assert "train" in segments
    assert "untouched_test" in segments


def test_short_mid_long_validation_present(artifact):
    sched = artifact["short_mid_long_validation_schedule"]
    assert sched["short_windows"] == [100, 125, 150]
    assert sched["mid_windows"] == [500, 750, 1000]
    assert "long_window" in sched


def test_multiple_testing_correction_family(artifact):
    fam = artifact["multiple_testing_correction_family"]
    required_members = [
        "candidate_methods",
        "null_variants",
        "lottery_types",
        "n_values",
        "metrics",
        "windows",
    ]
    for m in required_members:
        assert m in fam["members"], f"Missing correction family member: {m}"
    assert "BH_FDR" in fam["methods"]
    assert "Bonferroni" in fam["methods"]


def test_leakage_and_provenance_gates_present(artifact):
    assert len(artifact["leakage_prevention_tests"]) >= 3
    assert len(artifact["provenance_requirements"]) >= 3
    leak = " ".join(artifact["leakage_prevention_tests"]).lower()
    assert "source_time < target_draw_time" in leak or "source_time" in leak


def test_paired_test_plan_mcnemar(artifact):
    plan = artifact["paired_test_plan"]
    assert "mcnemar" in plan["binary_hit_count_ge_1"].lower()
    assert "bootstrap" in plan["average_hit_count"].lower() or "signed-rank" in plan["average_hit_count"].lower()


# ---------------------------------------------------------------------------
# Forbidden-action bans
# ---------------------------------------------------------------------------


def test_explicit_ban_block(artifact):
    ban = artifact["explicit_ban"]
    assert ban["no_db_write"] is True
    assert ban["no_production_change"] is True
    assert ban["no_registry_mutation"] is True
    assert ban["no_controlled_apply"] is True
    assert ban["no_deployment"] is True
    assert ban["no_recommendation_mutation"] is True
    assert ban["no_prototype_code"] is True
    assert ban["no_strategy_backtest"] is True
    assert ban["no_improved_accuracy_claim"] is True


def test_confirmation_booleans(artifact):
    assert artifact["no_db_write_confirmed"] is True
    assert artifact["no_prototype_code_confirmed"] is True
    assert artifact["no_strategy_implementation_confirmed"] is True
    assert artifact["no_registry_mutation_confirmed"] is True
    assert artifact["no_recommendation_logic_change_confirmed"] is True
    assert artifact["no_production_write_confirmed"] is True
    assert artifact["no_betting_advice_confirmed"] is True
    assert artifact["no_improved_accuracy_claim_confirmed"] is True


# ---------------------------------------------------------------------------
# Next task
# ---------------------------------------------------------------------------


def test_next_allowed_task_is_p258d_read_only_plan(artifact):
    nxt = artifact["next_allowed_task"]
    assert nxt["task_id"] == "P258D"
    typ = nxt["type"].lower()
    assert "implementation plan" in typ
    assert "not a prototype" in typ or "not prototype" in typ.replace("a ", "")


# ---------------------------------------------------------------------------
# Risk control triggers
# ---------------------------------------------------------------------------


def test_risk_control_triggers_complete(artifact):
    triggers = artifact["risk_control_triggers"]
    for key in [
        "observation_only",
        "auto_downgrade",
        "rollback",
        "stop",
        "re_pre_registration",
        "ban_from_recommendation",
    ]:
        assert key in triggers, f"Missing risk-control trigger: {key}"


# ---------------------------------------------------------------------------
# MD content spot-checks
# ---------------------------------------------------------------------------


def test_md_contains_methodology_caveat():
    with open(ARTIFACT_MD, "r", encoding="utf-8") as f:
        content = f.read()
    assert "VALIDATION / FALSIFICATION gate" in content
    assert "not a number-prediction model" in content


def test_md_contains_no_auto_approval():
    with open(ARTIFACT_MD, "r", encoding="utf-8") as f:
        content = f.read()
    assert "auto-approval gate" in content


def test_md_contains_p257a_and_null_percentile():
    with open(ARTIFACT_MD, "r", encoding="utf-8") as f:
        content = f.read()
    assert "P257A" in content
    assert "95th percentile" in content
