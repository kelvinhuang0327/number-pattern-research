"""
P258M — D3 Strategy Status Audit: Artifact-Backed API Contract Tests

Validates the P258M contract artifact. This test file itself:
- contains no imports of random, numpy, scipy
- contains no p-value, paired-test, backtest, or null-generation functions
- does not create executable D3 modules
- does not touch DB, recommendation, production, registry, controlled_apply, or deployment paths
"""

import json
import os
import pytest

ARTIFACT_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "outputs",
    "research",
    "p258m_d3_strategy_status_audit_api_contract_20260609.json",
)

FORBIDDEN_MODULES = [
    "candidate_ingest.py",
    "baseline_ingest.py",
    "null_factory.py",
    "gate_statistics.py",
    "gate_orchestrator.py",
    "gate_audit.py",
    "integration_runner.py",
]

FORBIDDEN_D3_STATUSES = [
    "APPROVED",
    "PROMOTED",
    "PRODUCTION_READY",
    "RECOMMENDED",
    "PREDICTIVE_EDGE_CONFIRMED",
]

ALLOWED_D3_STATUSES = [
    "NOT_EVALUATED_BY_D3",
    "CONTRACT_READY",
    "CONTRACT_BLOCKED",
    "NOT_APPLICABLE_HISTORICAL_ARTIFACT",
    "NOT_APPLICABLE_NO_REPLAY",
]

REQUIRED_TOP_LEVEL_FIELDS = [
    "schema_version",
    "generated_at",
    "source_artifacts",
    "route_path",
    "page_title",
    "summary",
    "filters",
    "rows",
    "safety_disclaimers",
    "forbidden_actions_confirmed",
    "next_allowed_task",
]

REQUIRED_ROW_FIELDS = [
    "lottery_type",
    "strategy_id",
    "strategy_name",
    "lifecycle_status",
    "evidence_status",
    "replay_row_count",
    "draw_coverage",
    "best_n_bet_status",
    "latest_evidence_artifact",
    "d3_contract_status",
    "d3_contract_reason",
    "d3_not_approval_warning",
    "no_prediction_claim",
    "no_betting_advice",
]

REQUIRED_FILTERS = [
    "lottery_type",
    "lifecycle_status",
    "evidence_status",
    "d3_contract_status",
    "has_replay",
    "has_artifact",
]

REQUIRED_SAFETY_DISCLAIMERS_SUBSTRINGS = [
    "D3 is not a prediction model",
    "Contract validation is not strategy evaluation",
    "NOT_YET_REJECTED is not approval",
    "does not imply improved prediction accuracy",
    "not betting advice",
]


@pytest.fixture(scope="module")
def artifact():
    with open(ARTIFACT_PATH, "r") as f:
        return json.load(f)


# --- Basic parse ---

def test_artifact_parses(artifact):
    assert isinstance(artifact, dict)


def test_final_classification(artifact):
    assert artifact["final_classification"] == "P258M_D3_STRATEGY_STATUS_AUDIT_API_CONTRACT_READY"


# --- Scope declarations ---

def test_is_api_contract_only(artifact):
    assert artifact["plan_only_declaration"]["is_api_contract_only"] is True


def test_no_api_route_implemented(artifact):
    assert artifact["plan_only_declaration"]["no_api_route_implemented"] is True


def test_no_ui_implemented(artifact):
    assert artifact["plan_only_declaration"]["no_ui_implemented"] is True


def test_no_db_query(artifact):
    assert artifact["plan_only_declaration"]["no_db_query"] is True


def test_no_db_write(artifact):
    assert artifact["plan_only_declaration"]["no_db_write"] is True


def test_no_real_candidate_methods_used(artifact):
    assert artifact["plan_only_declaration"]["no_real_candidate_methods_used"] is True


def test_no_executable_gate_evaluation(artifact):
    assert artifact["plan_only_declaration"]["no_executable_gate_evaluation"] is True


def test_no_null_generation(artifact):
    assert artifact["plan_only_declaration"]["no_null_generation"] is True


def test_no_p_values_computed(artifact):
    assert artifact["plan_only_declaration"]["no_p_values_computed"] is True


def test_no_paired_tests(artifact):
    assert artifact["plan_only_declaration"]["no_paired_tests"] is True


def test_no_backtest_run(artifact):
    assert artifact["plan_only_declaration"]["no_backtest_run"] is True


def test_no_recommendation_logic_modified(artifact):
    assert artifact["plan_only_declaration"]["no_recommendation_logic_modified"] is True


def test_no_production_code_modified(artifact):
    assert artifact["plan_only_declaration"]["no_production_code_modified"] is True


def test_no_registry_modified(artifact):
    assert artifact["plan_only_declaration"]["no_registry_modified"] is True


def test_no_controlled_apply_modified(artifact):
    assert artifact["plan_only_declaration"]["no_controlled_apply_modified"] is True


def test_no_deployment_modified(artifact):
    assert artifact["plan_only_declaration"]["no_deployment_modified"] is True


# --- Route contract ---

def test_proposed_route_path(artifact):
    assert artifact["api_contract"]["proposed_route_path"] == "GET /api/replay/d3-strategy-status-audit"


# --- Top-level payload fields ---

def test_top_level_payload_fields_defined(artifact):
    defined = {f["field"] for f in artifact["top_level_payload_fields"]}
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        assert field in defined, f"Missing top-level field: {field}"


# --- Row fields ---

def test_row_fields_defined(artifact):
    defined = {f["field"] for f in artifact["required_row_fields"]}
    for field in REQUIRED_ROW_FIELDS:
        assert field in defined, f"Missing row field: {field}"


def test_d3_contract_status_row_field_has_allowed_values(artifact):
    row_fields = {f["field"]: f for f in artifact["required_row_fields"]}
    d3_field = row_fields["d3_contract_status"]
    for status in ALLOWED_D3_STATUSES:
        assert status in d3_field["allowed_values"], f"Missing allowed status: {status}"


def test_d3_contract_status_row_field_has_forbidden_values(artifact):
    row_fields = {f["field"]: f for f in artifact["required_row_fields"]}
    d3_field = row_fields["d3_contract_status"]
    for status in FORBIDDEN_D3_STATUSES:
        assert status in d3_field["forbidden_values"], f"Missing forbidden status: {status}"


# --- Data source policy ---

def test_data_source_policy_is_artifact_backed_only(artifact):
    assert artifact["data_source_policy"]["first_implementation"] == "artifact-backed only"


def test_first_implementation_must_not_query_db(artifact):
    assert artifact["data_source_policy"]["first_implementation_must_not_query_db"] is True


def test_first_implementation_must_not_write_db(artifact):
    assert artifact["data_source_policy"]["first_implementation_must_not_write_db"] is True


def test_first_implementation_must_not_mutate_registry(artifact):
    assert artifact["data_source_policy"]["first_implementation_must_not_mutate_registry"] is True


def test_first_implementation_must_not_mutate_production_state(artifact):
    assert artifact["data_source_policy"]["first_implementation_must_not_mutate_production_state"] is True


# --- Allowed D3 statuses ---

def test_allowed_d3_statuses_defined(artifact):
    defined = {s["status"] for s in artifact["allowed_d3_contract_statuses"]}
    for status in ALLOWED_D3_STATUSES:
        assert status in defined, f"Missing allowed D3 status: {status}"


# --- Forbidden D3 statuses ---

def test_forbidden_d3_statuses_defined(artifact):
    defined = {s["status"] for s in artifact["forbidden_d3_contract_statuses"]}
    for status in FORBIDDEN_D3_STATUSES:
        assert status in defined, f"Missing forbidden D3 status: {status}"


def test_approved_is_forbidden(artifact):
    forbidden = {s["status"] for s in artifact["forbidden_d3_contract_statuses"]}
    assert "APPROVED" in forbidden


def test_promoted_is_forbidden(artifact):
    forbidden = {s["status"] for s in artifact["forbidden_d3_contract_statuses"]}
    assert "PROMOTED" in forbidden


def test_production_ready_is_forbidden(artifact):
    forbidden = {s["status"] for s in artifact["forbidden_d3_contract_statuses"]}
    assert "PRODUCTION_READY" in forbidden


def test_recommended_is_forbidden(artifact):
    forbidden = {s["status"] for s in artifact["forbidden_d3_contract_statuses"]}
    assert "RECOMMENDED" in forbidden


def test_predictive_edge_confirmed_is_forbidden(artifact):
    forbidden = {s["status"] for s in artifact["forbidden_d3_contract_statuses"]}
    assert "PREDICTIVE_EDGE_CONFIRMED" in forbidden


# --- Safety governance ---

def test_d3_is_not_prediction_model_disclaimer(artifact):
    disclaimers = artifact["required_safety_disclaimers"]
    assert any("D3 is not a prediction model" in d for d in disclaimers)


def test_contract_validation_is_not_strategy_evaluation_disclaimer(artifact):
    disclaimers = artifact["required_safety_disclaimers"]
    assert any("Contract validation is not strategy evaluation" in d for d in disclaimers)


def test_not_yet_rejected_is_not_approval_disclaimer(artifact):
    disclaimers = artifact["required_safety_disclaimers"]
    assert any("NOT_YET_REJECTED is not approval" in d for d in disclaimers)


def test_no_improved_accuracy_claim_disclaimer(artifact):
    disclaimers = artifact["required_safety_disclaimers"]
    assert any("does not imply improved prediction accuracy" in d for d in disclaimers)


def test_no_betting_advice_disclaimer(artifact):
    disclaimers = artifact["required_safety_disclaimers"]
    assert any("not betting advice" in d for d in disclaimers)


def test_governance_d3_not_approval_gate(artifact):
    assert artifact["governance"]["d3_is_not_approval_gate"] is True


def test_governance_d3_not_prediction_model(artifact):
    assert artifact["governance"]["d3_is_not_prediction_model"] is True


def test_governance_contract_validation_not_strategy_evaluation(artifact):
    assert artifact["governance"]["contract_validation_is_not_strategy_evaluation"] is True


def test_governance_not_yet_rejected_not_approval(artifact):
    assert artifact["governance"]["not_yet_rejected_is_not_approval"] is True


# --- Forbidden actions confirmed ---

def test_forbidden_actions_no_api_route_in_p258m(artifact):
    assert artifact["forbidden_actions_confirmed"]["no_api_route_implemented_in_p258m"] is True


def test_forbidden_actions_no_ui_in_p258m(artifact):
    assert artifact["forbidden_actions_confirmed"]["no_ui_implemented_in_p258m"] is True


def test_forbidden_actions_no_db_write(artifact):
    assert artifact["forbidden_actions_confirmed"]["no_db_write"] is True


def test_forbidden_actions_no_db_query_first_impl(artifact):
    assert artifact["forbidden_actions_confirmed"]["no_db_query_in_first_implementation"] is True


def test_forbidden_actions_no_recommendation_logic(artifact):
    assert artifact["forbidden_actions_confirmed"]["no_recommendation_logic_modified"] is True


def test_forbidden_actions_no_registry(artifact):
    assert artifact["forbidden_actions_confirmed"]["no_registry_modified"] is True


def test_forbidden_actions_no_production_code(artifact):
    assert artifact["forbidden_actions_confirmed"]["no_production_code_modified"] is True


def test_forbidden_actions_no_null_generation(artifact):
    assert artifact["forbidden_actions_confirmed"]["no_null_generation"] is True


def test_forbidden_actions_no_backtest(artifact):
    assert artifact["forbidden_actions_confirmed"]["no_backtest_run"] is True


def test_forbidden_actions_no_real_candidates(artifact):
    assert artifact["forbidden_actions_confirmed"]["no_real_candidate_methods_used"] is True


def test_forbidden_actions_no_executable_gate(artifact):
    assert artifact["forbidden_actions_confirmed"]["no_executable_gate_evaluation"] is True


def test_forbidden_actions_no_improved_accuracy_claimed(artifact):
    assert artifact["forbidden_actions_confirmed"]["no_improved_accuracy_claimed"] is True


def test_forbidden_actions_no_betting_advice(artifact):
    assert artifact["forbidden_actions_confirmed"]["no_betting_advice"] is True


def test_forbidden_actions_no_prediction_claim(artifact):
    assert artifact["forbidden_actions_confirmed"]["no_prediction_claim"] is True


# --- Forbidden executable modules ---

def test_forbidden_executable_modules_listed(artifact):
    listed = artifact["forbidden_executable_modules_confirmed_absent"]
    for mod in FORBIDDEN_MODULES:
        assert mod in listed, f"Module not in forbidden list: {mod}"


def test_candidate_ingest_not_created():
    path = os.path.join(
        os.path.dirname(__file__), "..", "lottery_api", "research", "d3_gate", "candidate_ingest.py"
    )
    assert not os.path.exists(path), "candidate_ingest.py must not be created in P258M"


def test_null_factory_not_created():
    path = os.path.join(
        os.path.dirname(__file__), "..", "lottery_api", "research", "d3_gate", "null_factory.py"
    )
    assert not os.path.exists(path), "null_factory.py must not be created in P258M"


def test_gate_statistics_not_created():
    path = os.path.join(
        os.path.dirname(__file__), "..", "lottery_api", "research", "d3_gate", "gate_statistics.py"
    )
    assert not os.path.exists(path), "gate_statistics.py must not be created in P258M"


def test_gate_orchestrator_not_created():
    path = os.path.join(
        os.path.dirname(__file__), "..", "lottery_api", "research", "d3_gate", "gate_orchestrator.py"
    )
    assert not os.path.exists(path), "gate_orchestrator.py must not be created in P258M"


def test_gate_audit_not_created():
    path = os.path.join(
        os.path.dirname(__file__), "..", "lottery_api", "research", "d3_gate", "gate_audit.py"
    )
    assert not os.path.exists(path), "gate_audit.py must not be created in P258M"


def test_integration_runner_not_created():
    path = os.path.join(
        os.path.dirname(__file__), "..", "lottery_api", "research", "d3_gate", "integration_runner.py"
    )
    assert not os.path.exists(path), "integration_runner.py must not be created in P258M"


# --- Filters ---

def test_required_filters_defined(artifact):
    defined = {f["filter"] for f in artifact["required_filters"]}
    for filt in REQUIRED_FILTERS:
        assert filt in defined, f"Missing filter: {filt}"


# --- Future task split ---

def test_next_allowed_task_is_p258n(artifact):
    nxt = artifact["future_task_split"]["next_allowed_task"]
    assert "P258N" in nxt


def test_p258m_does_not_authorize_p258n_automatically(artifact):
    assert artifact["governance"]["p258m_does_not_authorize_p258n_automatically"] is True


def test_p258n_requires_separate_explicit_authorization(artifact):
    assert artifact["future_task_split"]["each_task_requires_separate_explicit_authorization"] is True


def test_running_d3_on_real_candidates_is_forbidden(artifact):
    assert "FORBIDDEN" in artifact["future_task_split"]["running_d3_on_real_candidate_methods"]


# --- No forbidden imports in this test file itself ---
# Use token-based check to avoid false positives from string literals in assertions.

def _import_lines(path):
    """Return only lines that are actual import statements (start with 'import' or 'from')."""
    with open(path, "r") as f:
        return [ln.strip() for ln in f if ln.lstrip().startswith(("import ", "from "))]


def test_no_random_import_in_test_file():
    lines = _import_lines(__file__)
    forbidden = [ln for ln in lines if "random" in ln]
    assert forbidden == [], f"Forbidden random import in test file: {forbidden}"


def test_no_numpy_import_in_test_file():
    lines = _import_lines(__file__)
    forbidden = [ln for ln in lines if "numpy" in ln]
    assert forbidden == [], f"Forbidden numpy import in test file: {forbidden}"


def test_no_scipy_import_in_test_file():
    lines = _import_lines(__file__)
    forbidden = [ln for ln in lines if "scipy" in ln]
    assert forbidden == [], f"Forbidden scipy import in test file: {forbidden}"


# --- No UI/API implementation files modified ---

def _branch_changed_files():
    """Return files changed vs origin/main (the P258M branch delta only)."""
    import subprocess
    repo_root = os.path.join(os.path.dirname(__file__), "..")
    result = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        capture_output=True, text=True,
        cwd=repo_root,
    )
    return result.stdout.strip().splitlines()


def test_no_ui_files_modified():
    changed = _branch_changed_files()
    ui_files = [f for f in changed if f.startswith("src/ui/") or f == "index.html"]
    assert ui_files == [], f"UI files must not be modified in P258M branch: {ui_files}"


def test_no_api_route_files_modified():
    changed = _branch_changed_files()
    api_files = [f for f in changed if f.startswith("lottery_api/routes/")]
    assert api_files == [], f"API route files must not be modified in P258M branch: {api_files}"


def test_no_gate_validation_modified():
    changed = _branch_changed_files()
    gate_files = [
        f for f in changed
        if f in [
            "lottery_api/research/d3_gate/gate_validation.py",
            "lottery_api/research/d3_gate/schemas.py",
            "lottery_api/research/d3_gate/integration_skeleton.py",
        ]
    ]
    assert gate_files == [], f"D3 gate files must not be modified in P258M branch: {gate_files}"
