"""
P258B — External Response Evaluation artifact validation tests.

Validates the P258B evaluation artifact (JSON + MD) against governance requirements:
- Exactly 3 directions recorded
- Correct per-direction classification
- D2 hard-rejected with correct rationale
- D3 selected with mandatory methodology-not-predictor caveat
- All forbidden actions blocked
- Next task (P258C) requires strong model
"""

import json
import os
import pytest

ARTIFACT_JSON = os.path.join(
    os.path.dirname(__file__),
    "..",
    "outputs",
    "research",
    "p258b_external_response_evaluation_20260608.json",
)
ARTIFACT_MD = os.path.join(
    os.path.dirname(__file__),
    "..",
    "outputs",
    "research",
    "p258b_external_response_evaluation_20260608.md",
)


@pytest.fixture(scope="module")
def artifact():
    with open(ARTIFACT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Structural / parse tests
# ---------------------------------------------------------------------------


def test_json_artifact_parses(artifact):
    assert isinstance(artifact, dict)


def test_json_has_required_top_level_keys(artifact):
    required = [
        "task_id",
        "classification",
        "generated_date",
        "task_type",
        "phase0_summary",
        "structure_check",
        "evaluation_results",
        "selected_candidate",
        "recommended_next_task",
        "final_decision",
    ]
    for key in required:
        assert key in artifact, f"Missing top-level key: {key}"


def test_task_id_is_p258b(artifact):
    assert artifact["task_id"] == "P258B"


def test_md_artifact_exists():
    assert os.path.isfile(ARTIFACT_MD), "P258B MD artifact is missing"


# ---------------------------------------------------------------------------
# Structure check
# ---------------------------------------------------------------------------


def test_structure_check_exactly_3_directions(artifact):
    assert artifact["structure_check"]["exactly_3_directions"] is True


def test_structure_check_direction_names(artifact):
    names = artifact["structure_check"]["direction_names"]
    assert len(names) == 3
    assert "CrossLotteryLaggedEntropyRegime" in names
    assert "DrawSetGeometryResidualConformal" in names
    assert "AdversarialNullSurvivorGate" in names


def test_structure_check_all_9_fields(artifact):
    sc = artifact["structure_check"]
    assert sc["all_9_fields_present_d1"] is True
    assert sc["all_9_fields_present_d2"] is True
    assert sc["all_9_fields_present_d3"] is True


def test_structure_check_result_pass(artifact):
    assert artifact["structure_check"]["result"] == "PASS"


# ---------------------------------------------------------------------------
# Per-direction classification
# ---------------------------------------------------------------------------


def _get_direction(artifact, method_name):
    for d in artifact["evaluation_results"]:
        if d["method_name"] == method_name:
            return d
    return None


def test_d1_classification_is_reject_insufficient_evidence(artifact):
    d1 = _get_direction(artifact, "CrossLotteryLaggedEntropyRegime")
    assert d1 is not None
    assert d1["classification"] == "REJECT_INSUFFICIENT_EVIDENCE"


def test_d1_is_not_hard_rejected(artifact):
    d1 = _get_direction(artifact, "CrossLotteryLaggedEntropyRegime")
    assert d1["hard_rejected"] is False


def test_d1_has_rejection_reasons(artifact):
    d1 = _get_direction(artifact, "CrossLotteryLaggedEntropyRegime")
    assert len(d1["rejection_reasons"]) >= 1


def test_d2_classification_is_hard_reject(artifact):
    d2 = _get_direction(artifact, "DrawSetGeometryResidualConformal")
    assert d2 is not None
    assert d2["classification"] == "HARD_REJECT"


def test_d2_is_hard_rejected(artifact):
    d2 = _get_direction(artifact, "DrawSetGeometryResidualConformal")
    assert d2["hard_rejected"] is True


def test_d2_has_hard_rejection_reasons(artifact):
    d2 = _get_direction(artifact, "DrawSetGeometryResidualConformal")
    assert len(d2["hard_rejection_reasons"]) >= 1


def test_d2_hard_rejection_cites_prior_evidence(artifact):
    d2 = _get_direction(artifact, "DrawSetGeometryResidualConformal")
    combined = " ".join(d2["hard_rejection_reasons"]).lower()
    # Must cite at least one of the prior closed lines
    assert any(
        ref in combined
        for ref in ["l82", "l91", "l73", "l104", "l105", "prior negative evidence"]
    )


def test_d2_rubric_scores_are_null(artifact):
    d2 = _get_direction(artifact, "DrawSetGeometryResidualConformal")
    assert d2["rubric_scores"] is None


def test_d3_classification_is_accept(artifact):
    d3 = _get_direction(artifact, "AdversarialNullSurvivorGate")
    assert d3 is not None
    assert d3["classification"] == "ACCEPT_FOR_READ_ONLY_PREREGISTRATION"


def test_d3_is_not_hard_rejected(artifact):
    d3 = _get_direction(artifact, "AdversarialNullSurvivorGate")
    assert d3["hard_rejected"] is False


def test_d3_eligibility_criteria_all_pass(artifact):
    d3 = _get_direction(artifact, "AdversarialNullSurvivorGate")
    ec = d3["eligibility_check"]
    assert ec["no_hard_rejection"] is True
    assert ec["explicit_p257a_baseline_comparison"] is True
    assert ec["explicit_p256a_null_risk_boundary"] is True
    assert ec["feasible_oos_and_paired_comparison_plan"] is True
    assert ec["no_production_recommendation_mutation"] is True


def test_d3_has_rubric_scores(artifact):
    d3 = _get_direction(artifact, "AdversarialNullSurvivorGate")
    scores = d3["rubric_scores"]
    assert scores is not None
    expected_keys = [
        "novelty_of_signal",
        "leakage_safety",
        "oos_feasibility",
        "mcnemar_paired_test_feasibility",
        "short_mid_long_stability",
        "multiple_testing_discipline",
        "drift_detectability",
    ]
    for key in expected_keys:
        assert key in scores, f"Missing rubric key: {key}"
        assert 0 <= scores[key] <= 5, f"Score out of range for {key}"


# ---------------------------------------------------------------------------
# Final classification
# ---------------------------------------------------------------------------


def test_final_classification(artifact):
    assert artifact["final_decision"] == "P258B_READ_ONLY_PREREGISTRATION_CANDIDATE_SELECTED"
    assert artifact["classification"] == "P258B_READ_ONLY_PREREGISTRATION_CANDIDATE_SELECTED"


# ---------------------------------------------------------------------------
# Selected candidate — D3 caveat
# ---------------------------------------------------------------------------


def test_selected_candidate_is_d3(artifact):
    assert artifact["selected_candidate"]["method_name"] == "AdversarialNullSurvivorGate"
    assert artifact["selected_candidate"]["direction_number"] == 3


def test_d3_methodology_not_predictor_caveat_present(artifact):
    # Must be present in the selected_candidate block
    caveat = artifact["selected_candidate"]["methodology_not_predictor_caveat"].lower()
    assert "validation" in caveat or "gate" in caveat
    assert "not a" in caveat or "not a number" in caveat or "not a predictive" in caveat


def test_d3_caveat_in_direction_entry(artifact):
    d3 = _get_direction(artifact, "AdversarialNullSurvivorGate")
    caveat = d3["methodology_not_predictor_caveat"].upper()
    assert "VALIDATION" in caveat or "GATE" in caveat


# ---------------------------------------------------------------------------
# Forbidden-action booleans
# ---------------------------------------------------------------------------


def test_no_db_write_confirmed(artifact):
    assert artifact["no_db_write_confirmed"] is True


def test_no_prototype_code_confirmed(artifact):
    assert artifact["no_prototype_code_confirmed"] is True


def test_no_strategy_implementation_confirmed(artifact):
    assert artifact["no_strategy_implementation_confirmed"] is True


def test_no_registry_mutation_confirmed(artifact):
    assert artifact["no_registry_mutation_confirmed"] is True


def test_no_recommendation_logic_change_confirmed(artifact):
    assert artifact["no_recommendation_logic_change_confirmed"] is True


def test_no_production_write_confirmed(artifact):
    assert artifact["no_production_write_confirmed"] is True


def test_no_betting_advice_confirmed(artifact):
    assert artifact["no_betting_advice_confirmed"] is True


# ---------------------------------------------------------------------------
# Next task requires strong model
# ---------------------------------------------------------------------------


def test_next_task_is_p258c(artifact):
    assert artifact["recommended_next_task"]["task_id"] == "P258C"


def test_next_task_requires_strong_model(artifact):
    assert artifact["recommended_next_task"]["strong_model_required"] is True


def test_next_task_is_read_only(artifact):
    task_type = artifact["recommended_next_task"]["type"].lower()
    assert "read-only" in task_type or "type b" in task_type


# ---------------------------------------------------------------------------
# MD artifact content spot-checks
# ---------------------------------------------------------------------------


def test_md_contains_hard_reject_label():
    with open(ARTIFACT_MD, "r", encoding="utf-8") as f:
        content = f.read()
    assert "HARD_REJECT" in content


def test_md_contains_accept_label():
    with open(ARTIFACT_MD, "r", encoding="utf-8") as f:
        content = f.read()
    assert "ACCEPT_FOR_READ_ONLY_PREREGISTRATION" in content


def test_md_contains_methodology_caveat():
    with open(ARTIFACT_MD, "r", encoding="utf-8") as f:
        content = f.read()
    assert "VALIDATION / ADVERSARIAL-NULL SURVIVOR GATE" in content


def test_md_contains_no_db_write_statement():
    with open(ARTIFACT_MD, "r", encoding="utf-8") as f:
        content = f.read()
    assert "No DB write" in content


def test_md_contains_no_recommendation_mutation_statement():
    with open(ARTIFACT_MD, "r", encoding="utf-8") as f:
        content = f.read()
    assert "recommendation" in content.lower()


def test_md_contains_strong_model_requirement():
    with open(ARTIFACT_MD, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Strong model required" in content or "strong model" in content.lower()
