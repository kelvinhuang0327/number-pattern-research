"""P258K — D3 integration contract documentation closeout tests.

Validates the closeout artifact, confirms no new executable D3 modules
were created, and verifies the arc's final read-only state.

No executable gate evaluation, no null generation, no p-values,
no real candidate methods, no DB access.
"""

import json
import pathlib
import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_PATH = (
    REPO_ROOT
    / "outputs"
    / "research"
    / "p258k_d3_integration_contract_documentation_closeout_20260609.json"
)
D3_GATE_DIR = REPO_ROOT / "lottery_api" / "research" / "d3_gate"
SKELETON_PATH = D3_GATE_DIR / "integration_skeleton.py"


@pytest.fixture(scope="module")
def artifact():
    with ARTIFACT_PATH.open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Artifact: basic structure and classification
# ---------------------------------------------------------------------------

def test_artifact_parses(artifact):
    assert isinstance(artifact, dict)


def test_final_classification(artifact):
    assert artifact["final_classification"] == (
        "P258K_D3_INTEGRATION_CONTRACT_DOCUMENTATION_CLOSEOUT_READY"
    )


def test_artifact_is_documentation_closeout_only(artifact):
    assert artifact["documentation_closeout_only_declaration"]["is_documentation_closeout_only"] is True


def test_no_implementation_code_created(artifact):
    assert artifact["documentation_closeout_only_declaration"]["no_implementation_code_created"] is True


# ---------------------------------------------------------------------------
# Artifact: P258A through P258J milestone chain
# ---------------------------------------------------------------------------

def test_artifact_summarizes_p258a_through_p258j(artifact):
    chain = artifact["p258_arc_milestone_chain"]
    task_ids = [entry["task"] for entry in chain]
    expected = ["P258A", "P258B", "P258C", "P258D", "P258E",
                "P258F", "P258G", "P258H", "P258I", "P258J"]
    assert task_ids == expected


def test_p258a_in_chain(artifact):
    chain = artifact["p258_arc_milestone_chain"]
    tasks = {e["task"]: e for e in chain}
    assert "P258A" in tasks
    assert "P258A_PREDICTION_ACCURACY_RESEARCH_INTAKE_PROTOCOL_READY" in tasks["P258A"]["classification"]


def test_p258f_in_chain(artifact):
    chain = artifact["p258_arc_milestone_chain"]
    tasks = {e["task"]: e for e in chain}
    assert "P258F" in tasks
    assert "CONTRACT_VALIDATORS" in tasks["P258F"]["classification"]


def test_p258i_in_chain(artifact):
    chain = artifact["p258_arc_milestone_chain"]
    tasks = {e["task"]: e for e in chain}
    assert "P258I" in tasks
    assert "SKELETON" in tasks["P258I"]["classification"]


def test_p258j_in_chain(artifact):
    chain = artifact["p258_arc_milestone_chain"]
    tasks = {e["task"]: e for e in chain}
    assert "P258J" in tasks
    assert "SYNTHETIC" in tasks["P258J"]["classification"]


# ---------------------------------------------------------------------------
# Artifact: no implementation code
# ---------------------------------------------------------------------------

def test_no_real_candidate_methods_used(artifact):
    assert artifact["documentation_closeout_only_declaration"]["no_real_candidate_methods_used"] is True


def test_no_executable_gate_evaluation(artifact):
    assert artifact["documentation_closeout_only_declaration"]["no_executable_gate_evaluation"] is True


def test_no_null_generation(artifact):
    assert artifact["documentation_closeout_only_declaration"]["no_null_generation"] is True


def test_no_p_values_computed(artifact):
    assert artifact["documentation_closeout_only_declaration"]["no_p_values_computed"] is True


def test_no_paired_tests(artifact):
    assert artifact["documentation_closeout_only_declaration"]["no_paired_tests"] is True


def test_no_backtests(artifact):
    assert artifact["documentation_closeout_only_declaration"]["no_backtests"] is True


def test_no_db_write(artifact):
    assert artifact["documentation_closeout_only_declaration"]["no_db_write"] is True


# ---------------------------------------------------------------------------
# Artifact: final arc status
# ---------------------------------------------------------------------------

def test_no_executable_gate_evaluation_exists(artifact):
    assert artifact["final_d3_arc_status"]["no_executable_gate_evaluation_exists"] is True


def test_no_real_candidate_method_execution_exists(artifact):
    assert artifact["final_d3_arc_status"]["no_real_candidate_method_execution_exists"] is True


def test_no_null_generation_exists(artifact):
    assert artifact["final_d3_arc_status"]["no_null_generation_exists"] is True


def test_no_p_values_or_statistical_tests_or_backtests_exist(artifact):
    assert artifact["final_d3_arc_status"]["no_p_values_or_statistical_tests_or_backtests_exist"] is True


def test_no_db_write_exists(artifact):
    assert artifact["final_d3_arc_status"]["no_db_write_exists"] is True


def test_no_recommendation_production_paths_exist(artifact):
    assert artifact["final_d3_arc_status"][
        "no_recommendation_production_registry_controlled_apply_deployment_path_exists"
    ] is True


# ---------------------------------------------------------------------------
# Artifact: safety semantics
# ---------------------------------------------------------------------------

def test_d3_is_not_a_prediction_model(artifact):
    assert artifact["mandatory_safety_semantics"]["d3_is_not_a_prediction_model"] is True


def test_contract_validation_is_not_strategy_evaluation(artifact):
    assert artifact["mandatory_safety_semantics"]["contract_validation_is_not_strategy_evaluation"] is True


def test_not_yet_rejected_is_not_approval(artifact):
    assert artifact["mandatory_safety_semantics"]["not_yet_rejected_is_not_approval"] is True


def test_no_improved_accuracy_claimed(artifact):
    assert artifact["mandatory_safety_semantics"][
        "passing_contract_validation_does_not_imply_improved_prediction_accuracy"
    ] is True


def test_no_production_use_authorized(artifact):
    assert artifact["mandatory_safety_semantics"]["passing_validators_does_not_allow_production_use"] is True


def test_no_recommendation_use_authorized(artifact):
    assert artifact["mandatory_safety_semantics"]["passing_validators_does_not_allow_recommendation_use"] is True


def test_no_lottery_edge_claimed(artifact):
    assert artifact["mandatory_safety_semantics"]["no_lottery_edge_claimed"] is True


def test_executable_gate_evaluation_remains_forbidden(artifact):
    assert artifact["mandatory_safety_semantics"]["executable_gate_evaluation_remains_forbidden"] is True


# ---------------------------------------------------------------------------
# Artifact: module inventory
# ---------------------------------------------------------------------------

def test_module_inventory_includes_schemas_py(artifact):
    inventory = artifact["module_inventory"]
    assert "schemas_py" in inventory
    assert "lottery_api/research/d3_gate/schemas.py" in inventory["schemas_py"]["path"]


def test_module_inventory_includes_gate_validation_py(artifact):
    inventory = artifact["module_inventory"]
    assert "gate_validation_py" in inventory
    assert "gate_validation.py" in inventory["gate_validation_py"]["path"]


def test_module_inventory_includes_integration_skeleton_py(artifact):
    inventory = artifact["module_inventory"]
    assert "integration_skeleton_py" in inventory
    assert "integration_skeleton.py" in inventory["integration_skeleton_py"]["path"]


def test_module_inventory_schemas_not_executable(artifact):
    assert artifact["module_inventory"]["schemas_py"]["executable_code"] is False


def test_module_inventory_gate_validation_not_executable(artifact):
    assert artifact["module_inventory"]["gate_validation_py"]["executable_code"] is False


def test_module_inventory_skeleton_not_executable(artifact):
    assert artifact["module_inventory"]["integration_skeleton_py"]["executable_code"] is False


# ---------------------------------------------------------------------------
# Artifact: forbidden executable modules confirmed absent
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
def test_forbidden_module_not_created_on_disk(module_name):
    path = D3_GATE_DIR / module_name
    assert not path.exists(), f"Forbidden module {module_name} exists in d3_gate/"


@pytest.mark.parametrize("module_name", FORBIDDEN_MODULES)
def test_forbidden_module_confirmed_absent_in_artifact(artifact, module_name):
    confirmed = artifact["module_inventory"]["forbidden_executable_modules_confirmed_absent"]
    assert module_name in confirmed


# ---------------------------------------------------------------------------
# Artifact: test inventory
# ---------------------------------------------------------------------------

def test_test_inventory_lists_p258e_through_p258j(artifact):
    inventory = artifact["test_inventory"]
    expected_keys = [
        "p258e_skeleton_tests",
        "p258f_validator_tests",
        "p258g_synthetic_fixture_tests",
        "p258h_integration_plan_tests",
        "p258i_skeleton_tests",
        "p258j_dry_contract_fixture_tests",
    ]
    for key in expected_keys:
        assert key in inventory, f"test_inventory missing key: {key}"


def test_test_files_listed_in_inventory_exist_on_disk(artifact):
    inventory = artifact["test_inventory"]
    for key, path_str in inventory.items():
        if key == "total_tests_across_arc":
            continue
        path = REPO_ROOT / path_str
        assert path.exists(), f"Test file listed in inventory does not exist: {path_str}"


# ---------------------------------------------------------------------------
# Artifact: governance final recommendation
# ---------------------------------------------------------------------------

def test_governance_recommends_hold(artifact):
    rec = artifact["governance_final_recommendation"]["recommended_next_state"]
    assert "HOLD" in rec or "WAITING" in rec


def test_governance_says_do_not_proceed_automatically(artifact):
    assert artifact["governance_final_recommendation"][
        "do_not_proceed_automatically_to_executable_d3_evaluation"
    ] is True


def test_governance_arc_is_closed(artifact):
    assert "CLOSED" in artifact["governance_final_recommendation"]["arc_status"]


# ---------------------------------------------------------------------------
# Artifact: forbidden next tasks
# ---------------------------------------------------------------------------

def test_forbidden_next_tasks_include_executable_gate(artifact):
    forbidden = artifact["forbidden_next_tasks"]
    assert any("executable gate" in t.lower() for t in forbidden)


def test_forbidden_next_tasks_include_not_yet_rejected_as_approved(artifact):
    forbidden = artifact["forbidden_next_tasks"]
    assert any("NOT_YET_REJECTED" in t for t in forbidden)


def test_forbidden_next_tasks_include_null_generation(artifact):
    forbidden = artifact["forbidden_next_tasks"]
    assert any("null generation" in t.lower() for t in forbidden)


def test_forbidden_next_tasks_include_db_write(artifact):
    forbidden = artifact["forbidden_next_tasks"]
    assert any("DB write" in t or "db write" in t.lower() for t in forbidden)


# ---------------------------------------------------------------------------
# No new forbidden imports introduced in skeleton
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
def test_skeleton_still_has_no_forbidden_import(import_line):
    source = SKELETON_PATH.read_text()
    assert import_line not in source, (
        f"integration_skeleton.py contains forbidden import: {import_line!r}"
    )


# ---------------------------------------------------------------------------
# No forbidden function definitions
# ---------------------------------------------------------------------------

FORBIDDEN_FUNCTION_PATTERNS = [
    "def compute_p_value",
    "def generate_null",
    "def run_backtest",
    "def evaluate_gate",
    "def run_gate",
    "def compute_statistic",
    "def paired_test",
    "def load_db",
    "def write_db",
]


@pytest.mark.parametrize("pattern", FORBIDDEN_FUNCTION_PATTERNS)
def test_skeleton_still_has_no_forbidden_function(pattern):
    source = SKELETON_PATH.read_text()
    assert pattern not in source, (
        f"integration_skeleton.py defines forbidden function: {pattern!r}"
    )
