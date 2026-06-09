"""P258I — D3 read-only contract-validation integration skeleton tests.

Tests validate the JSON artifact, the integration_skeleton.py module
(structure, metadata, stubs), and confirm no forbidden executable modules
were created and no forbidden imports are present.

No executable gate evaluation, no null generation, no p-values, no real
candidate methods, no DB access — skeleton/planning only.
"""

import inspect
import json
import pathlib
import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_PATH = (
    REPO_ROOT
    / "outputs"
    / "research"
    / "p258i_d3_readonly_contract_validation_integration_skeleton_20260609.json"
)
D3_GATE_DIR = REPO_ROOT / "lottery_api" / "research" / "d3_gate"
SKELETON_PATH = D3_GATE_DIR / "integration_skeleton.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def artifact() -> dict:
    with ARTIFACT_PATH.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def skeleton_module():
    import sys
    # Ensure repo root is on sys.path so the package import resolves.
    repo_root_str = str(REPO_ROOT)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    import importlib
    return importlib.import_module("lottery_api.research.d3_gate.integration_skeleton")


# ---------------------------------------------------------------------------
# Artifact: basic structure
# ---------------------------------------------------------------------------

def test_artifact_parses(artifact):
    assert isinstance(artifact, dict)


def test_final_classification(artifact):
    assert artifact["final_classification"] == (
        "P258I_D3_READ_ONLY_CONTRACT_VALIDATION_INTEGRATION_SKELETON_READY"
    )


def test_artifact_is_skeleton_only(artifact):
    assert artifact["skeleton_only_declaration"]["is_skeleton_only"] is True


def test_no_implementation_beyond_skeleton(artifact):
    proof = artifact["proof_of_non_implementation"]
    assert proof["executable_integration_not_implemented"] is True
    assert proof["run_contract_validation_flow_raises_NotImplementedError"] is True
    assert proof["build_contract_validation_plan_returns_static_dict_only"] is True


# ---------------------------------------------------------------------------
# Artifact: validator invocation order matches P258H plan
# ---------------------------------------------------------------------------

EXPECTED_VALIDATOR_ORDER = [
    "validate_no_approval_status_contract",
    "validate_candidate_provenance_contract",
    "validate_timestamp_cutoff_contract",
    "validate_p257a_baseline_contract",
    "validate_matched_null_family_contract",
    "validate_correction_family_contract",
]


def test_artifact_defines_validator_invocation_order(artifact):
    order = artifact["validator_invocation_order"]
    assert len(order) == 6


@pytest.mark.parametrize("i, expected_name", enumerate(EXPECTED_VALIDATOR_ORDER))
def test_validator_order_step_name(artifact, i, expected_name):
    order = artifact["validator_invocation_order"]
    assert order[i]["name"] == expected_name
    assert order[i]["step"] == i + 1


def test_all_validators_have_fail_behavior(artifact):
    for entry in artifact["validator_invocation_order"]:
        assert "fail_behavior" in entry
        assert "ContractValidationError" in entry["fail_behavior"]


# ---------------------------------------------------------------------------
# Artifact: fail-closed behavior documented
# ---------------------------------------------------------------------------

def test_artifact_documents_fail_closed_behavior(artifact):
    fb = artifact["fail_closed_semantics"]
    assert fb["any_contract_validation_error_blocks_further_validation"] is True
    assert fb["failure_cannot_be_converted_to_warning_only"] is True
    assert fb["not_yet_rejected_remains_not_approval"] is True


def test_forbidden_patterns_include_exception_swallow(artifact):
    patterns = artifact["fail_closed_semantics"]["forbidden_patterns"]
    assert any("ContractValidationError: pass" in p for p in patterns)


def test_forbidden_patterns_include_warning_downgrade(artifact):
    patterns = artifact["fail_closed_semantics"]["forbidden_patterns"]
    assert any("warnings.warn" in p for p in patterns)


# ---------------------------------------------------------------------------
# Artifact: safety semantics
# ---------------------------------------------------------------------------

def test_d3_is_not_a_prediction_model(artifact):
    assert artifact["mandatory_safety_semantics"]["d3_is_not_a_prediction_model"] is True


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
# Artifact: next allowed task
# ---------------------------------------------------------------------------

def test_next_allowed_task_is_p258j(artifact):
    next_task = artifact["next_allowed_task"]
    assert "P258J" in next_task


def test_executable_gate_evaluation_is_forbidden_next_task(artifact):
    forbidden = artifact["forbidden_next_tasks"]
    assert any("executable gate" in t.lower() for t in forbidden)


def test_null_generation_is_forbidden_next_task(artifact):
    forbidden = artifact["forbidden_next_tasks"]
    assert any("null generation" in t.lower() for t in forbidden)


def test_not_yet_rejected_as_approved_is_forbidden_next_task(artifact):
    forbidden = artifact["forbidden_next_tasks"]
    assert any("NOT_YET_REJECTED" in t for t in forbidden)


# ---------------------------------------------------------------------------
# Artifact: no real candidates / no executable modules
# ---------------------------------------------------------------------------

def test_no_real_candidate_methods_in_artifact(artifact):
    assert artifact["skeleton_only_declaration"]["no_real_candidate_methods_used"] is True


def test_no_null_generation_in_artifact(artifact):
    assert artifact["skeleton_only_declaration"]["no_null_generation"] is True


def test_no_p_values_in_artifact(artifact):
    assert artifact["skeleton_only_declaration"]["no_p_values_computed"] is True


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
def test_forbidden_executable_module_not_created(module_name):
    path = D3_GATE_DIR / module_name
    assert not path.exists(), f"Forbidden module {module_name} exists in d3_gate/"


@pytest.mark.parametrize("module_name", FORBIDDEN_MODULES)
def test_forbidden_module_confirmed_in_artifact(artifact, module_name):
    confirmed = artifact["forbidden_executable_modules_not_created"]
    assert module_name in confirmed


# ---------------------------------------------------------------------------
# Skeleton module: exists and loads
# ---------------------------------------------------------------------------

def test_skeleton_file_exists():
    assert SKELETON_PATH.exists(), "integration_skeleton.py must exist"


def test_skeleton_module_loads(skeleton_module):
    assert skeleton_module is not None


# ---------------------------------------------------------------------------
# Skeleton module: metadata objects are present
# ---------------------------------------------------------------------------

def test_validator_invocation_order_metadata_exists(skeleton_module):
    order = skeleton_module.VALIDATOR_INVOCATION_ORDER
    assert isinstance(order, tuple)
    assert len(order) == 6


@pytest.mark.parametrize("i, expected_name", enumerate(EXPECTED_VALIDATOR_ORDER))
def test_skeleton_validator_order_names(skeleton_module, i, expected_name):
    order = skeleton_module.VALIDATOR_INVOCATION_ORDER
    assert order[i]["name"] == expected_name
    assert order[i]["step"] == i + 1


def test_skeleton_validator_order_has_callables(skeleton_module):
    for entry in skeleton_module.VALIDATOR_INVOCATION_ORDER:
        assert callable(entry["callable"]), (
            f"Step {entry['step']} 'callable' must be a real callable"
        )


def test_allowed_input_contract_boundaries_metadata_exists(skeleton_module):
    boundaries = skeleton_module.ALLOWED_INPUT_CONTRACT_BOUNDARIES
    assert isinstance(boundaries, tuple)
    assert len(boundaries) == 5


def test_fail_closed_policy_metadata_exists(skeleton_module):
    policy = skeleton_module.FAIL_CLOSED_POLICY
    assert policy["any_contract_validation_error_blocks_further_validation"] is True
    assert policy["failure_cannot_be_converted_to_warning_only"] is True
    assert policy["not_yet_rejected_remains_not_approval"] is True


def test_forbidden_imports_metadata_exists(skeleton_module):
    forbidden = skeleton_module.FORBIDDEN_IMPORTS_AND_PATHS
    assert isinstance(forbidden, tuple)
    assert any("numpy" in f for f in forbidden)
    assert any("scipy" in f for f in forbidden)
    assert any("random" in f for f in forbidden)
    assert any("DB" in f or "database" in f.lower() for f in forbidden)


def test_safety_semantic_constants(skeleton_module):
    assert skeleton_module.D3_IS_NOT_A_PREDICTION_MODEL is True
    assert skeleton_module.CONTRACT_VALIDATION_IS_NOT_STRATEGY_EVALUATION is True
    assert skeleton_module.NOT_YET_REJECTED_IS_NOT_APPROVAL is True
    assert skeleton_module.PASSING_VALIDATORS_DOES_NOT_ALLOW_PRODUCTION_USE is True
    assert skeleton_module.PASSING_VALIDATORS_DOES_NOT_IMPLY_IMPROVED_PREDICTION_ACCURACY is True
    assert skeleton_module.NO_LOTTERY_EDGE_CLAIMED is True


# ---------------------------------------------------------------------------
# Skeleton module: stub functions
# ---------------------------------------------------------------------------

def test_build_contract_validation_plan_exists(skeleton_module):
    assert hasattr(skeleton_module, "build_contract_validation_plan")
    assert callable(skeleton_module.build_contract_validation_plan)


def test_build_contract_validation_plan_returns_static_dict(skeleton_module):
    result = skeleton_module.build_contract_validation_plan()
    assert isinstance(result, dict)


def test_build_contract_validation_plan_includes_validator_order(skeleton_module):
    result = skeleton_module.build_contract_validation_plan()
    order = result["validator_invocation_order"]
    assert len(order) == 6
    assert order[0]["name"] == "validate_no_approval_status_contract"


def test_build_contract_validation_plan_includes_safety_semantics(skeleton_module):
    result = skeleton_module.build_contract_validation_plan()
    sem = result["safety_semantics"]
    assert sem["d3_is_not_a_prediction_model"] is True
    assert sem["not_yet_rejected_is_not_approval"] is True


def test_build_contract_validation_plan_includes_not_implemented_status(skeleton_module):
    result = skeleton_module.build_contract_validation_plan()
    assert "NOT_IMPLEMENTED" in result["executable_flow_status"]


def test_build_contract_validation_plan_includes_next_task(skeleton_module):
    result = skeleton_module.build_contract_validation_plan()
    assert "P258J" in result["next_authorized_task"]


def test_run_contract_validation_flow_raises_not_implemented(skeleton_module):
    with pytest.raises(NotImplementedError) as exc_info:
        skeleton_module.run_contract_validation_flow()
    assert "NOT" in str(exc_info.value).upper() or "not" in str(exc_info.value)


def test_run_contract_validation_flow_mentions_p258i_in_error(skeleton_module):
    with pytest.raises(NotImplementedError) as exc_info:
        skeleton_module.run_contract_validation_flow()
    assert "P258I" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Skeleton module: no forbidden imports
# ---------------------------------------------------------------------------

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
def test_skeleton_does_not_contain_forbidden_import(import_line):
    source = SKELETON_PATH.read_text()
    assert import_line not in source, (
        f"integration_skeleton.py contains forbidden import: {import_line!r}"
    )


# ---------------------------------------------------------------------------
# Skeleton module: no p-value / backtest / null generation functions
# ---------------------------------------------------------------------------

FORBIDDEN_FUNCTION_PATTERNS = [
    "def compute_p_value",
    "def generate_null",
    "def run_backtest",
    "def evaluate_gate",
    "def run_gate",
    "def compute_statistic",
    "def paired_test",
]


@pytest.mark.parametrize("pattern", FORBIDDEN_FUNCTION_PATTERNS)
def test_skeleton_has_no_forbidden_function_definition(pattern):
    source = SKELETON_PATH.read_text()
    assert pattern not in source, (
        f"integration_skeleton.py contains forbidden function definition: {pattern!r}"
    )
