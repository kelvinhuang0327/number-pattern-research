"""
P258D — D3 gate read-only implementation plan tests.

Validates the P258D plan artifact (JSON + MD):
- JSON parses; final classification correct
- D3 framed as validation gate, not a prediction model
- passing the gate is NOT approval
- DB write / recommendation / production / registry / controlled_apply / deployment banned
- module boundaries, data contracts, provenance contract, future schema + test plan present
- next allowed task is P258E read-only skeleton / contract tests only
- executable gate evaluation / backtest forbidden without later explicit authorization
"""

import json
import os
import pytest

ARTIFACT_JSON = os.path.join(
    os.path.dirname(__file__),
    "..",
    "outputs",
    "research",
    "p258d_d3_gate_readonly_implementation_plan_20260608.json",
)
ARTIFACT_MD = os.path.join(
    os.path.dirname(__file__),
    "..",
    "outputs",
    "research",
    "p258d_d3_gate_readonly_implementation_plan_20260608.md",
)


@pytest.fixture(scope="module")
def artifact():
    with open(ARTIFACT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Parse / classification
# ---------------------------------------------------------------------------


def test_json_artifact_parses(artifact):
    assert isinstance(artifact, dict)


def test_task_id_is_p258d(artifact):
    assert artifact["task_id"] == "P258D"


def test_md_artifact_exists():
    assert os.path.isfile(ARTIFACT_MD)


def test_final_classification(artifact):
    assert artifact["final_decision"] == "P258D_D3_READ_ONLY_IMPLEMENTATION_PLAN_READY"


# ---------------------------------------------------------------------------
# D3 mandatory interpretation
# ---------------------------------------------------------------------------


def test_artifact_states_d3_is_not_a_prediction_model(artifact):
    mi = artifact["d3_mandatory_interpretation"]
    assert mi["is_validation_gate_not_predictor"] is True
    assert mi["cannot_claim_accuracy_improvement"] is True


def test_passing_the_gate_is_not_approval(artifact):
    mi = artifact["d3_mandatory_interpretation"]
    assert mi["passing_means_only_not_yet_rejected_never_approved"] is True
    assert mi["cannot_approve_production"] is True
    assert artifact["passing_gate_is_not_approval_confirmed"] is True


# ---------------------------------------------------------------------------
# Forbidden-action bans
# ---------------------------------------------------------------------------


def test_artifact_bans_db_write(artifact):
    assert artifact["no_db_write_confirmed"] is True
    assert artifact["d3_mandatory_interpretation"]["cannot_write_db"] is True


def test_artifact_bans_recommendation_mutation(artifact):
    assert artifact["no_recommendation_logic_change_confirmed"] is True
    assert artifact["d3_mandatory_interpretation"]["cannot_touch_recommendation_logic"] is True


def test_artifact_bans_production_registry_controlled_apply_deployment(artifact):
    assert artifact["no_production_write_confirmed"] is True
    assert artifact["no_registry_mutation_confirmed"] is True
    assert artifact["no_controlled_apply_confirmed"] is True
    assert artifact["no_deployment_confirmed"] is True


def test_artifact_bans_executable_gate_and_backtest(artifact):
    assert artifact["no_executable_gate_code_confirmed"] is True
    assert artifact["no_strategy_backtest_confirmed"] is True


def test_artifact_bans_accuracy_claim(artifact):
    assert artifact["no_improved_accuracy_claim_confirmed"] is True


# ---------------------------------------------------------------------------
# Plan content presence
# ---------------------------------------------------------------------------


def test_module_boundaries_defined(artifact):
    mbp = artifact["module_boundary_proposal"]
    assert "layers" in mbp and len(mbp["layers"]) >= 4
    assert "import_ban" in mbp


def test_future_executable_gate_modules_still_not_created(artifact):
    names = artifact["proposed_future_module_names_P258E_ONLY_NOT_CREATED_NOW"]
    # P258E legitimately creates the read-only schema/stub skeleton proposed by
    # P258D. The permanent invariant is narrower: executable D3 gate modules
    # must still not exist.
    p258e_allowed_skeleton = {"schemas", "validation"}
    executable_module_keys = set(names) - {"note"} - p258e_allowed_skeleton

    for key in executable_module_keys:
        path = names[key]
        assert path.endswith(".py")
        assert not os.path.exists(
            os.path.join(os.path.dirname(__file__), "..", path)
        ), f"Executable D3 gate module must NOT exist: {path}"


def test_p258e_readonly_schema_stub_skeleton_may_exist(artifact):
    names = artifact["proposed_future_module_names_P258E_ONLY_NOT_CREATED_NOW"]
    allowed_skeleton_paths = [names["schemas"], names["validation"]]

    for path in allowed_skeleton_paths:
        assert path.endswith(".py")


def test_candidate_input_contract_defined(artifact):
    c = artifact["candidate_input_data_contract"]
    assert "required_fields" in c and len(c["required_fields"]) >= 8
    assert "per_draw_output_fields" in c
    assert "constraints" in c


def test_p257a_baseline_input_contract_defined(artifact):
    b = artifact["p257a_baseline_input_contract"]
    assert "required_fields" in b
    assert "alignment_rule" in b
    joined = " ".join(b["required_fields"]).lower()
    assert "lottery_type" in joined and "n_bet_count" in joined


def test_matched_null_contract_defined(artifact):
    m = artifact["matched_null_family_contract"]
    assert m["input"]["family_size_min"] >= 1000
    methods = " ".join(m["input"]["null_construction_methods"]).lower()
    assert "binomial" in methods
    assert "lesson_guard_L96" in m


def test_provenance_contract_defined(artifact):
    p = artifact["provenance_contract"]
    required = [
        "candidate_generation_timestamp",
        "available_information_cutoff",
        "lottery_type",
        "target_draw_id",
        "n_bet_count",
        "number_count_per_bet",
        "feature_dimensionality",
        "window_schedule",
        "random_seed",
        "null_generation_seed",
    ]
    for field in required:
        assert field in p["required_fields"], f"Missing provenance field: {field}"


def test_validation_contract_defined(artifact):
    v = artifact["validation_contract"]
    assert len(v) >= 6
    joined = " ".join(v).lower()
    assert "leakage" in joined
    assert "no_production_recommendation_mutation" in joined or "no production" in joined


def test_future_artifact_schema_defined(artifact):
    s = artifact["future_artifact_schema_proposal_P258E"]
    assert "inputs" in s and "outputs" in s
    assert "rejection_reasons" in s
    assert s["gate_decision_values"] == ["REJECTED", "NOT_YET_REJECTED"]
    assert "not_yet_rejected_semantics" in s
    assert "null_percentile" in s
    assert "corrected_p_values" in s


def test_future_test_plan_defined(artifact):
    t = artifact["future_test_plan_P258E"]
    joined = " ".join(t).lower()
    assert "schema_tests" in joined
    assert "leakage_guard_tests" in joined
    assert "no_auto_approval_tests" in joined
    assert "no_db_write_tests" in joined


def test_stop_gates_defined(artifact):
    g = artifact["stop_gates_for_future_implementation"]
    for expected in [
        "missing_p257a_baseline",
        "missing_candidate_provenance",
        "missing_timestamp_cutoff",
        "unmatched_null_family",
        "db_write_required",
    ]:
        assert expected in g, f"Missing STOP gate: {expected}"


# ---------------------------------------------------------------------------
# Next / forbidden tasks
# ---------------------------------------------------------------------------


def test_next_task_is_p258e_readonly_skeleton(artifact):
    nxt = artifact["next_allowed_task"]
    assert nxt["task_id"] == "P258E"
    typ = nxt["type"].lower()
    assert "skeleton" in typ
    assert "contract test" in typ
    assert "no executable gate" in typ or "no backtest" in typ


def test_forbidden_next_tasks_include_executable_backtest(artifact):
    forb = " ".join(artifact["forbidden_next_tasks"]).lower()
    assert "executable gate evaluation or backtest" in forb
    assert "production integration" in forb
    assert "db write" in forb


# ---------------------------------------------------------------------------
# MD spot-checks
# ---------------------------------------------------------------------------


def test_md_contains_not_approval_statement():
    with open(ARTIFACT_MD, "r", encoding="utf-8") as f:
        content = f.read()
    assert "not yet rejected" in content.lower()
    # MD states: Passing the gate means only "not yet rejected," never "approved."
    assert 'never "approved' in content or "never approved" in content.lower()


def test_md_contains_plan_only_statement():
    with open(ARTIFACT_MD, "r", encoding="utf-8") as f:
        content = f.read()
    assert "implementation plan only" in content.lower()


def test_md_contains_p258e_next():
    with open(ARTIFACT_MD, "r", encoding="utf-8") as f:
        content = f.read()
    assert "P258E" in content
