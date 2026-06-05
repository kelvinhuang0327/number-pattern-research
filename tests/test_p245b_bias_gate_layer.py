"""Tests for P245B corrected bias gate layer artifact.

Verifies: JSON parses, all gate states present, forbidden actions,
anomaly != predictor language, no P(win) claim, multiple-testing required,
data-contamination quarantine required, BIG_LOTTO GATE_RED example,
P245A not a dependency.
"""
import json
import os
import sys

import pytest

ARTIFACT_JSON = os.path.join(
    os.path.dirname(__file__),
    "..", "outputs", "research", "p245b_bias_gate_layer_20260605.json"
)
ARTIFACT_MD = os.path.join(
    os.path.dirname(__file__),
    "..", "outputs", "research", "p245b_bias_gate_layer_20260605.md"
)

REQUIRED_GATE_STATES = [
    "GATE_CLOSED_RANDOM_COMPATIBLE",
    "GATE_YELLOW_OBSERVATION_ONLY",
    "GATE_RED_DATA_CONTAMINATION",
    "GATE_OPEN_BIAS_RESEARCH_ALLOWED",
    "GATE_INVALID_INSUFFICIENT_DATA",
]

REQUIRED_FORBIDDEN_ACTIONS = [
    "DB write",
    "registry mutation",
    "production recommendation change",
    "controlled_apply",
    "strategy promotion",
    "betting advice",
]


@pytest.fixture(scope="module")
def data():
    with open(ARTIFACT_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def report_text():
    with open(ARTIFACT_MD) as f:
        return f.read()


# --- JSON integrity ----------------------------------------------------------

def test_json_parses(data):
    assert isinstance(data, dict), "P245B JSON must parse to a dict"


def test_schema_version_present(data):
    assert "schema_version" in data
    assert data["schema_version"] == "1.0"


def test_task_id(data):
    assert data.get("task_id") == "P245B"


def test_classification_present(data):
    assert "classification" in data
    assert "P245B" in data["classification"]


# --- Gate states -------------------------------------------------------------

def test_all_gate_states_present(data):
    states = data.get("gate_states", {})
    for gs in REQUIRED_GATE_STATES:
        assert gs in states, f"Gate state {gs!r} missing from P245B JSON"


def test_each_gate_state_has_allowed_and_forbidden(data):
    states = data["gate_states"]
    for name, body in states.items():
        assert "allowed_actions" in body, f"{name} missing allowed_actions"
        assert "forbidden_actions" in body, f"{name} missing forbidden_actions"


# --- Forbidden actions firewall ----------------------------------------------

def test_forbidden_actions_at_top_level(data):
    fa = data.get("forbidden_actions", [])
    fa_lower = " ".join(f.lower() for f in fa)
    for req in REQUIRED_FORBIDDEN_ACTIONS:
        assert req.lower() in fa_lower, \
            f"Required forbidden action {req!r} not found in top-level forbidden_actions"


def test_gate_open_does_not_allow_betting_advice(data):
    gate_open = data["gate_states"]["GATE_OPEN_BIAS_RESEARCH_ALLOWED"]
    fa = " ".join(gate_open["forbidden_actions"]).lower()
    assert "betting" in fa, "GATE_OPEN must forbid betting advice"
    assert "production" in fa or "recommendation" in fa, \
        "GATE_OPEN must forbid production recommendation"
    assert "registry" in fa or "mutation" in fa, \
        "GATE_OPEN must forbid registry mutation"


def test_gate_open_allows_only_research_task(data):
    gate_open = data["gate_states"]["GATE_OPEN_BIAS_RESEARCH_ALLOWED"]
    aa = gate_open["allowed_actions"]
    assert any("research" in a.lower() for a in aa), \
        "GATE_OPEN allowed_actions must mention research task"
    assert len(aa) <= 3, "GATE_OPEN should allow very few actions (narrow scope)"


# --- Anomaly != predictor ----------------------------------------------------

def test_anomaly_is_not_predictor_json(data):
    cp = data.get("bayesian_changepoint_layer", {})
    assert cp.get("anomaly_is_not_predictor") is True, \
        "bayesian_changepoint_layer must explicitly set anomaly_is_not_predictor=true"


def test_anomaly_is_not_predictor_report(report_text):
    assert "anomaly detection is not prediction" in report_text.lower() or \
           "anomaly is not prediction" in report_text.lower() or \
           "anomaly is NOT prediction" in report_text, \
        "Report must contain 'anomaly is not prediction' language"


# --- No P(win) improvement claim --------------------------------------------

def test_no_p_win_claim_json(data):
    assert data["fundamental_constraints"].get(
        "fair_random_lotteries_have_no_validated_external_method_that_raises_P_win"
    ) is True


def test_no_p_win_claim_report(report_text):
    text_lower = report_text.lower()
    # must NOT contain "raises p(win)" or "improve p(win)" or "improve win rate"
    assert "improve win rate" not in text_lower or "no validated external method" in text_lower, \
        "Report must not claim P(win) improvement"
    # must contain the denial
    assert "no validated external method that raises" in text_lower or \
           "no external method raises p(win)" in text_lower or \
           "no external method can raise p(win)" in text_lower, \
        "Report must explicitly state no external method raises P(win)"


# --- Multiple-testing correction required -----------------------------------

def test_multiple_testing_correction_required_json(data):
    mt = data.get("multiple_testing_policy", {})
    assert mt.get("mandatory") is True, "multiple_testing_policy.mandatory must be true"
    assert "Bonferroni" in mt.get("primary_correction", "") or \
           "bonferroni" in mt.get("primary_correction", "").lower(), \
        "Bonferroni must be primary correction"


def test_multiple_testing_correction_required_report(report_text):
    assert "bonferroni" in report_text.lower(), \
        "Report must mention Bonferroni correction"
    assert "mandatory" in report_text.lower() or "required" in report_text.lower(), \
        "Report must state multiple-testing correction is mandatory/required"


# --- Data-contamination quarantine required ---------------------------------

def test_data_integrity_policy_mandatory(data):
    di = data.get("data_integrity_policy", {})
    assert di.get("mandatory") is True, "data_integrity_policy.mandatory must be true"
    checks = di.get("checks_required_before_any_signal_review", [])
    assert len(checks) >= 5, "Must have at least 5 data-integrity checks"


def test_data_contamination_quarantine_report(report_text):
    assert "quarantine" in report_text.lower(), \
        "Report must mention data-contamination quarantine"
    assert "data-integrity" in report_text.lower() or \
           "data integrity" in report_text.lower(), \
        "Report must mention data-integrity checks"


# --- BIG_LOTTO GATE_RED prior example ---------------------------------------

def test_big_lotto_gate_red_json(data):
    prior = data.get("prior_findings", {}).get("P219", {})
    big = prior.get("big_lotto_contamination", {})
    assert big.get("gate_classification") == "GATE_RED_DATA_CONTAMINATION", \
        "BIG_LOTTO contamination must be classified as GATE_RED_DATA_CONTAMINATION"
    assert big.get("is_exploitable_edge") is False
    assert big.get("anomaly_is_not_predictor") is True


def test_big_lotto_gate_red_in_policy(data):
    di = data["data_integrity_policy"]
    ex = di.get("big_lotto_prior_example", {})
    assert ex.get("gate_state_assigned") == "GATE_RED_DATA_CONTAMINATION"
    assert "P219" in ex.get("finding", "")


# --- P245A not a dependency -------------------------------------------------

def test_p245a_not_in_verified_dependencies(data):
    verified = " ".join(data.get("dependency_artifacts_verified", []))
    assert "P245A" not in verified, "P245A must not appear in verified dependencies"


def test_p245a_listed_as_missing(data):
    missing = " ".join(data.get("dependency_artifacts_missing", []))
    assert "P245A" in missing, "P245A must be listed in dependency_artifacts_missing"


def test_p245a_not_required(report_text):
    assert "P245A does not exist" in report_text or \
           "P245A was not found" in report_text or \
           "P245A does not exist" in report_text or \
           "P245A: ABSENT" in report_text, \
        "Report must explicitly state P245A is absent/not a dependency"


# --- E-value layer present --------------------------------------------------

def test_e_value_layer_present(data):
    ev = data.get("e_value_layer", {})
    assert ev.get("evidence_accumulation_threshold", {}).get("K_for_strong_evidence") == 100
    assert "cooldown_and_reset" in ev
    assert ev.get("purpose"), "e_value_layer must have a purpose statement"


# --- Current gate status consistent -----------------------------------------

def test_current_status_no_conditions_met(data):
    unlock = data.get("future_research_unlock_conditions", {})
    status = unlock.get("current_status", "")
    assert "no condition" in status.lower() or "not met" in status.lower(), \
        "current_status must state no unlock conditions are currently met"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
