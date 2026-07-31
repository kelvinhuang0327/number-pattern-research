"""P258A — Prediction Accuracy Improvement Research Intake Protocol tests.

Verifies the read-only intake-protocol artifact: objective scoping, retained
validation gates, external-agent prompt, scoring rubric, hard rejection rules,
baseline references, and governance no-action flags.

Read-only: no DB write, no registry mutation, no strategy promotion.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
P258A_JSON = (
    REPO_ROOT / "outputs" / "research"
    / "p258a_prediction_accuracy_research_intake_protocol_20260608.json"
)
P258A_MD = (
    REPO_ROOT / "outputs" / "research"
    / "p258a_prediction_accuracy_research_intake_protocol_20260608.md"
)

EXPECTED_FINAL_DECISION = "P258A_PREDICTION_ACCURACY_RESEARCH_INTAKE_PROTOCOL_READY"


@pytest.fixture(scope="module")
def artifact() -> dict:
    assert P258A_JSON.exists(), f"missing artifact: {P258A_JSON}"
    with P258A_JSON.open(encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Structural / identity
# ---------------------------------------------------------------------------

def test_json_parses(artifact):
    assert isinstance(artifact, dict)


def test_task_id(artifact):
    assert artifact["task_id"] == "P258A"


def test_classification_exists(artifact):
    assert artifact.get("classification")


def test_final_decision(artifact):
    assert artifact["final_decision"] == EXPECTED_FINAL_DECISION


def test_markdown_exists():
    assert P258A_MD.exists()


# ---------------------------------------------------------------------------
# Objective scoping
# ---------------------------------------------------------------------------

def test_objective_is_accuracy_only(artifact):
    assert artifact["objective"] == "prediction_accuracy_only"


def test_excluded_objectives_cover_money_metrics(artifact):
    excluded = " ".join(str(x).lower() for x in artifact["excluded_objectives"])
    for token in ("cp_value", "ev", "payout", "cost", "roi"):
        assert token in excluded, f"excluded_objectives missing {token}"


# ---------------------------------------------------------------------------
# Retained validation gates (must NOT be weakened)
# ---------------------------------------------------------------------------

def test_required_validation_gates_present(artifact):
    gates = " ".join(str(g).lower() for g in artifact["required_validation_gates"])
    assert "oos" in gates
    assert ("mcnemar" in gates) or ("paired" in gates)
    assert "multiple-testing" in gates or "multiple testing" in gates
    assert "short/mid/long" in gates or ("short" in gates and "long" in gates)
    assert "drift" in gates


# ---------------------------------------------------------------------------
# External-agent prompt
# ---------------------------------------------------------------------------

def test_external_agent_prompt_exists(artifact):
    prompt = artifact["external_agent_prompt"]
    assert isinstance(prompt, str) and len(prompt) > 200


def test_prompt_requests_exactly_three_directions(artifact):
    prompt = artifact["external_agent_prompt"].lower()
    assert "exactly 3" in prompt or "exactly three" in prompt


def test_prompt_ignores_money_metrics(artifact):
    prompt = artifact["external_agent_prompt"].lower()
    assert "ignore" in prompt
    assert "ev" in prompt and "payout" in prompt


# ---------------------------------------------------------------------------
# Rubric + rejection rules
# ---------------------------------------------------------------------------

def test_scoring_rubric_exists(artifact):
    rubric = artifact["scoring_rubric"]
    assert isinstance(rubric, dict) and rubric.get("criteria")


def test_implementation_cost_not_dominant(artifact):
    # cost criterion must be explicitly optional / weight-capped
    blob = json.dumps(artifact["scoring_rubric"]).lower()
    assert "implementation_cost" in blob
    assert "optional" in blob or "not dominate" in blob or "capped" in blob


def test_hard_rejection_rules_exist(artifact):
    rules = artifact["hard_rejection_rules"]
    assert isinstance(rules, list) and len(rules) >= 5
    joined = " ".join(rules).lower()
    assert "single_window" in joined or "single-window" in joined
    assert "no_oos" in joined or "oos" in joined
    assert "p257a" in joined or "best_nbet" in joined


# ---------------------------------------------------------------------------
# Baseline references
# ---------------------------------------------------------------------------

def test_baseline_references_include_p256a_and_p257a(artifact):
    refs = artifact["baseline_references"]
    assert "P256A" in refs
    assert "P257A" in refs


# ---------------------------------------------------------------------------
# Governance no-action flags
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "flag",
    [
        "no_db_write_confirmed",
        "no_strategy_implementation_confirmed",
        "no_registry_mutation_confirmed",
        "no_recommendation_logic_change_confirmed",
        "no_production_write_confirmed",
        "no_betting_advice_confirmed",
    ],
)
def test_no_action_flags_true(artifact, flag):
    assert artifact[flag] is True


def test_artifact_does_not_authorize_mutations(artifact):
    """The artifact must explicitly NOT authorize any mutating action."""
    assert artifact["no_db_write_confirmed"] is True
    assert artifact["no_strategy_implementation_confirmed"] is True
    assert artifact["no_registry_mutation_confirmed"] is True
    assert artifact["no_recommendation_logic_change_confirmed"] is True
