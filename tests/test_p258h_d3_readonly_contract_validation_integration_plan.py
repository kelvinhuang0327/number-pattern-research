"""P258H — D3 read-only contract-validation integration plan tests.

Tests validate the JSON artifact (plan properties, safety semantics, forbidden
patterns) and confirm that no forbidden executable D3 modules were created.
No executable gate evaluation, no null generation, no p-values, no real
candidate methods, no DB access.
"""

import json
import os
import pathlib
import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_PATH = (
    REPO_ROOT
    / "outputs"
    / "research"
    / "p258h_d3_readonly_contract_validation_integration_plan_20260609.json"
)
D3_GATE_DIR = REPO_ROOT / "lottery_api" / "research" / "d3_gate"


@pytest.fixture(scope="module")
def artifact() -> dict:
    with ARTIFACT_PATH.open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Artifact parses and basic structure
# ---------------------------------------------------------------------------

def test_artifact_parses(artifact):
    assert isinstance(artifact, dict)


def test_final_classification(artifact):
    assert artifact["final_classification"] == (
        "P258H_D3_READ_ONLY_CONTRACT_VALIDATION_INTEGRATION_PLAN_READY"
    )


def test_artifact_is_plan_only(artifact):
    decl = artifact["plan_only_declaration"]
    assert decl["is_plan_only"] is True


def test_no_implementation_code_created(artifact):
    decl = artifact["plan_only_declaration"]
    assert decl["no_implementation_code_created"] is True


# ---------------------------------------------------------------------------
# Validator invocation order
# ---------------------------------------------------------------------------

def test_artifact_defines_validator_invocation_order(artifact):
    order = artifact["validator_invocation_order"]["ordered_validators"]
    assert isinstance(order, list)
    assert len(order) == 6


def test_validator_order_starts_with_no_approval_status(artifact):
    order = artifact["validator_invocation_order"]["ordered_validators"]
    assert order[0]["validator"] == "validate_no_approval_status_contract"
    assert order[0]["step"] == 1


def test_validator_order_step_2_is_candidate_provenance(artifact):
    order = artifact["validator_invocation_order"]["ordered_validators"]
    assert order[1]["validator"] == "validate_candidate_provenance_contract"
    assert order[1]["step"] == 2


def test_validator_order_step_3_is_timestamp_cutoff(artifact):
    order = artifact["validator_invocation_order"]["ordered_validators"]
    assert order[2]["validator"] == "validate_timestamp_cutoff_contract"
    assert order[2]["step"] == 3


def test_validator_order_step_4_is_p257a_baseline(artifact):
    order = artifact["validator_invocation_order"]["ordered_validators"]
    assert order[3]["validator"] == "validate_p257a_baseline_contract"
    assert order[3]["step"] == 4


def test_validator_order_step_5_is_matched_null(artifact):
    order = artifact["validator_invocation_order"]["ordered_validators"]
    assert order[4]["validator"] == "validate_matched_null_family_contract"
    assert order[4]["step"] == 5


def test_validator_order_step_6_is_correction_family(artifact):
    order = artifact["validator_invocation_order"]["ordered_validators"]
    assert order[5]["validator"] == "validate_correction_family_contract"
    assert order[5]["step"] == 6


def test_all_validators_have_fail_behavior(artifact):
    order = artifact["validator_invocation_order"]["ordered_validators"]
    for entry in order:
        assert "fail_behavior" in entry
        assert "ContractValidationError" in entry["fail_behavior"]


# ---------------------------------------------------------------------------
# Fail-closed behavior
# ---------------------------------------------------------------------------

def test_artifact_defines_fail_closed_behavior(artifact):
    fb = artifact["fail_closed_behavior"]
    assert fb["any_contract_validation_error_blocks_further_validation"] is True


def test_failure_cannot_be_converted_to_warning_only(artifact):
    fb = artifact["fail_closed_behavior"]
    assert fb["failure_cannot_be_converted_to_warning_only"] is True


def test_not_yet_rejected_remains_not_approval_in_fail_closed(artifact):
    fb = artifact["fail_closed_behavior"]
    assert fb["not_yet_rejected_remains_not_approval"] is True


def test_forbidden_patterns_include_exception_swallow(artifact):
    forbidden = artifact["fail_closed_behavior"]["forbidden_patterns"]
    assert any("except ContractValidationError: pass" in p for p in forbidden)


def test_forbidden_patterns_include_warning_conversion(artifact):
    forbidden = artifact["fail_closed_behavior"]["forbidden_patterns"]
    assert any("warnings.warn" in p for p in forbidden)


# ---------------------------------------------------------------------------
# Allowed input contract boundaries
# ---------------------------------------------------------------------------

def test_artifact_defines_allowed_input_contract_boundaries(artifact):
    boundaries = artifact["allowed_input_contract_boundaries"]
    required_keys = {
        "candidate_provenance_contract",
        "p257a_baseline_contract",
        "matched_null_metadata_contract",
        "correction_family_declaration_contract",
        "status_result_contract",
    }
    assert required_keys.issubset(boundaries.keys())


def test_candidate_contract_defines_required_fields(artifact):
    boundary = artifact["allowed_input_contract_boundaries"]["candidate_provenance_contract"]
    fields = boundary["required_fields"]
    assert "candidate_id" in fields
    assert "available_information_cutoff" in fields
    assert "provenance_digest" in fields


def test_status_contract_defines_forbidden_approval_values(artifact):
    boundary = artifact["allowed_input_contract_boundaries"]["status_result_contract"]
    forbidden = boundary["forbidden_gate_status_values"]
    assert "APPROVED" in forbidden
    assert "PROMOTED" in forbidden
    assert "PRODUCTION_READY" in forbidden
    assert "RECOMMENDED" in forbidden


# ---------------------------------------------------------------------------
# Future validation report schema
# ---------------------------------------------------------------------------

def test_artifact_defines_output_result_schema(artifact):
    schema = artifact["future_validation_report_schema"]
    assert "fields" in schema
    fields = schema["fields"]
    assert "validation_scope" in fields
    assert "validators_run" in fields
    assert "validation_results" in fields
    assert "failures" in fields
    assert "forbidden_actions_confirmed" in fields
    assert "final_contract_status" in fields
    assert "no_approval_semantics" in fields


def test_report_schema_has_invariants(artifact):
    schema = artifact["future_validation_report_schema"]
    invariants = schema["invariants"]
    assert any("approval" in inv.lower() for inv in invariants)
    assert any("no_approval_semantics" in inv for inv in invariants)


# ---------------------------------------------------------------------------
# Forbidden imports
# ---------------------------------------------------------------------------

def test_artifact_defines_forbidden_imports(artifact):
    boundary = artifact["allowed_import_boundary_plan"]
    forbidden = boundary["forbidden_imports_for_future_integration"]
    assert any("numpy" in i for i in forbidden)
    assert any("scipy" in i for i in forbidden)
    assert any("random" in i for i in forbidden)
    assert any("DB" in i or "database" in i.lower() for i in forbidden)
    assert any("backtest" in i.lower() for i in forbidden)


def test_artifact_defines_allowed_imports(artifact):
    boundary = artifact["allowed_import_boundary_plan"]
    allowed = boundary["allowed_imports_for_future_integration"]
    assert any("schemas" in i for i in allowed)
    assert any("gate_validation" in i for i in allowed)
    assert len(allowed) == 2, "Only schemas.py and gate_validation.py may be imported"


# ---------------------------------------------------------------------------
# STOP gates
# ---------------------------------------------------------------------------

def test_artifact_defines_stop_gates(artifact):
    gates = artifact["stop_gates_for_future_implementation"]["gates"]
    assert len(gates) >= 7


def test_stop_gates_cover_real_candidate_methods(artifact):
    gates = artifact["stop_gates_for_future_implementation"]["gates"]
    conditions = [g["condition"] for g in gates]
    assert any("real candidate methods" in c for c in conditions)


def test_stop_gates_cover_executable_gate_evaluation(artifact):
    gates = artifact["stop_gates_for_future_implementation"]["gates"]
    conditions = [g["condition"] for g in gates]
    assert any("executable gate evaluation" in c for c in conditions)


def test_stop_gates_cover_null_generation(artifact):
    gates = artifact["stop_gates_for_future_implementation"]["gates"]
    conditions = [g["condition"] for g in gates]
    assert any("null generation" in c for c in conditions)


def test_stop_gates_cover_p_values(artifact):
    gates = artifact["stop_gates_for_future_implementation"]["gates"]
    conditions = [g["condition"] for g in gates]
    assert any("p-value" in c or "statistical" in c for c in conditions)


def test_stop_gates_cover_db_production(artifact):
    gates = artifact["stop_gates_for_future_implementation"]["gates"]
    conditions = [g["condition"] for g in gates]
    assert any("DB" in c or "production" in c for c in conditions)


def test_stop_gates_cover_not_yet_rejected_as_approved(artifact):
    gates = artifact["stop_gates_for_future_implementation"]["gates"]
    conditions = [g["condition"] for g in gates]
    assert any("NOT_YET_REJECTED" in c and "APPROVED" in c for c in conditions)


# ---------------------------------------------------------------------------
# Safety semantics
# ---------------------------------------------------------------------------

def test_d3_is_not_a_prediction_model(artifact):
    sem = artifact["mandatory_safety_semantics"]
    assert sem["d3_is_not_a_prediction_model"] is True


def test_contract_validation_is_not_strategy_evaluation(artifact):
    sem = artifact["mandatory_safety_semantics"]
    assert sem["contract_validation_is_not_strategy_evaluation"] is True


def test_not_yet_rejected_is_not_approval(artifact):
    sem = artifact["mandatory_safety_semantics"]
    assert sem["not_yet_rejected_is_not_approval"] is True


def test_no_improved_accuracy_claimed(artifact):
    sem = artifact["mandatory_safety_semantics"]
    assert sem["passing_contract_validation_does_not_imply_improved_prediction_accuracy"] is True


def test_no_production_use_authorized(artifact):
    sem = artifact["mandatory_safety_semantics"]
    assert sem["passing_validators_does_not_allow_production_use"] is True


def test_no_recommendation_use_authorized(artifact):
    sem = artifact["mandatory_safety_semantics"]
    assert sem["passing_validators_does_not_allow_recommendation_use"] is True


def test_no_lottery_edge_claimed(artifact):
    sem = artifact["mandatory_safety_semantics"]
    assert sem["no_lottery_edge_claimed"] is True


# ---------------------------------------------------------------------------
# No real candidate methods or statistical computation
# ---------------------------------------------------------------------------

def test_no_real_candidate_methods_used(artifact):
    assert artifact["plan_only_declaration"]["no_real_candidate_methods_used"] is True


def test_no_null_generation(artifact):
    assert artifact["plan_only_declaration"]["no_null_generation"] is True


def test_no_p_values_computed(artifact):
    assert artifact["plan_only_declaration"]["no_p_values_computed"] is True


def test_no_paired_tests(artifact):
    assert artifact["plan_only_declaration"]["no_paired_tests"] is True


def test_no_backtests(artifact):
    assert artifact["plan_only_declaration"]["no_backtests"] is True


# ---------------------------------------------------------------------------
# Next allowed task
# ---------------------------------------------------------------------------

def test_next_allowed_task_is_p258i_skeleton(artifact):
    future = artifact["future_task_split"]
    scope = future["p258i_authorized_scope"]
    assert "P258I" in scope or "skeleton" in scope.lower()


def test_executable_gate_evaluation_remains_forbidden(artifact):
    future = artifact["future_task_split"]
    assert "FORBIDDEN" in future["executable_gate_evaluation_status"]


def test_running_d3_on_real_candidates_remains_forbidden(artifact):
    future = artifact["future_task_split"]
    assert "FORBIDDEN" in future["running_d3_on_real_candidate_methods_status"]


# ---------------------------------------------------------------------------
# Forbidden executable modules not created
# ---------------------------------------------------------------------------

FORBIDDEN_MODULES = [
    "candidate_ingest.py",
    "baseline_ingest.py",
    "null_factory.py",
    "gate_statistics.py",
    "gate_orchestrator.py",
    "gate_audit.py",
    "integration_runner.py",
]


@pytest.mark.parametrize("module_name", FORBIDDEN_MODULES)
def test_forbidden_module_not_created_in_d3_gate(module_name):
    path = D3_GATE_DIR / module_name
    assert not path.exists(), f"Forbidden module {module_name} was created in d3_gate/"


@pytest.mark.parametrize("module_name", FORBIDDEN_MODULES)
def test_forbidden_module_confirmed_in_artifact(artifact, module_name):
    confirmed = artifact["forbidden_modules_not_created"]["confirmed_not_created"]
    assert module_name in confirmed


def test_artifact_confirms_no_executable_d3_runner_created(artifact):
    confirmed = artifact["forbidden_modules_not_created"]["confirmation"]
    assert "no executable" in confirmed.lower()


# ---------------------------------------------------------------------------
# No forbidden imports introduced in gate_validation.py
# ---------------------------------------------------------------------------

GATE_VALIDATION_PATH = D3_GATE_DIR / "gate_validation.py"
FORBIDDEN_IMPORT_LINES = [
    "import numpy",
    "import scipy",
    "from numpy",
    "from scipy",
    "import random",
    "import sqlalchemy",
    "import sqlite3",
    "import null_factory",
    "import gate_statistics",
    "import gate_orchestrator",
    "from null_factory",
    "from gate_statistics",
    "from gate_orchestrator",
]


@pytest.mark.parametrize("import_line", FORBIDDEN_IMPORT_LINES)
def test_gate_validation_does_not_import_forbidden_module(import_line):
    source = GATE_VALIDATION_PATH.read_text()
    assert import_line not in source, (
        f"gate_validation.py contains forbidden import: {import_line!r}"
    )
