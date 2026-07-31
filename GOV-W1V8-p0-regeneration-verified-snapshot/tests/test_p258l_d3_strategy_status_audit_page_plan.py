"""P258L — D3 strategy status audit page plan tests.

Validates the plan artifact properties, page contract, row field definitions,
D3 contract status enum boundaries, safety semantics, and absent forbidden
modules. No executable gate, no DB, no real candidate methods.
"""

import json
import pathlib
import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_PATH = (
    REPO_ROOT
    / "outputs"
    / "research"
    / "p258l_d3_strategy_status_audit_page_plan_20260609.json"
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
        "P258L_D3_STRATEGY_STATUS_AUDIT_PAGE_PLAN_READY"
    )


def test_artifact_is_plan_only(artifact):
    assert artifact["plan_only_declaration"]["is_plan_only"] is True


def test_no_ui_implementation(artifact):
    assert artifact["plan_only_declaration"]["no_ui_implementation"] is True


def test_no_api_route_implementation(artifact):
    assert artifact["plan_only_declaration"]["no_api_route_implementation"] is True


def test_no_real_candidate_methods(artifact):
    assert artifact["plan_only_declaration"]["no_real_candidate_methods_used"] is True


def test_no_executable_gate_evaluation(artifact):
    assert artifact["plan_only_declaration"]["no_executable_gate_evaluation"] is True


def test_no_null_generation(artifact):
    assert artifact["plan_only_declaration"]["no_null_generation"] is True


def test_no_p_values(artifact):
    assert artifact["plan_only_declaration"]["no_p_values_computed"] is True


def test_no_backtests(artifact):
    assert artifact["plan_only_declaration"]["no_backtests"] is True


def test_no_db_write(artifact):
    assert artifact["plan_only_declaration"]["no_db_write"] is True


# ---------------------------------------------------------------------------
# Artifact: page purpose
# ---------------------------------------------------------------------------

def test_artifact_defines_page_purpose(artifact):
    purposes = artifact["page_contract"]["page_purpose"]
    assert isinstance(purposes, list)
    assert len(purposes) >= 3


def test_page_purpose_includes_lifecycle_status(artifact):
    purposes = artifact["page_contract"]["page_purpose"]
    assert any("lifecycle" in p.lower() or "evidence" in p.lower() for p in purposes)


def test_page_purpose_includes_d3_contract_status(artifact):
    purposes = artifact["page_contract"]["page_purpose"]
    assert any("d3" in p.lower() or "contract" in p.lower() for p in purposes)


def test_page_purpose_prevents_approval_misinterpretation(artifact):
    purposes = artifact["page_contract"]["page_purpose"]
    assert any("approval" in p.lower() or "not approval" in p.lower() for p in purposes)


def test_page_is_not_betting_advice(artifact):
    assert artifact["page_contract"]["page_is_not_betting_advice"] is True


def test_page_is_historical_evidence_only(artifact):
    assert artifact["page_contract"]["page_is_historical_evidence_only"] is True


# ---------------------------------------------------------------------------
# Artifact: required row fields
# ---------------------------------------------------------------------------

REQUIRED_FIELD_NAMES = [
    "lottery_type",
    "strategy_id",
    "lifecycle_status",
    "evidence_status",
    "d3_contract_status",
    "d3_contract_reason",
    "d3_not_approval_warning",
    "no_prediction_claim",
    "no_betting_advice",
]

OPTIONAL_FIELD_NAMES = [
    "strategy_name",
    "replay_row_count",
    "draw_coverage",
    "best_n_bet_status",
    "latest_evidence_artifact",
]


def test_artifact_defines_all_required_row_fields(artifact):
    defined = {f["field"] for f in artifact["required_row_fields"]}
    for name in REQUIRED_FIELD_NAMES:
        assert name in defined, f"Required field missing: {name}"


def test_artifact_defines_optional_row_fields(artifact):
    defined = {f["field"] for f in artifact["required_row_fields"]}
    for name in OPTIONAL_FIELD_NAMES:
        assert name in defined, f"Optional field missing: {name}"


def test_required_fields_are_marked_required(artifact):
    field_map = {f["field"]: f for f in artifact["required_row_fields"]}
    for name in REQUIRED_FIELD_NAMES:
        assert field_map[name].get("required") is True, (
            f"Field {name} should be marked required"
        )


def test_d3_contract_status_field_has_allowed_values(artifact):
    field_map = {f["field"]: f for f in artifact["required_row_fields"]}
    d3_field = field_map["d3_contract_status"]
    assert "allowed_values" in d3_field
    assert "NOT_EVALUATED_BY_D3" in d3_field["allowed_values"]
    assert "CONTRACT_READY" in d3_field["allowed_values"]


def test_d3_contract_status_field_has_forbidden_values(artifact):
    field_map = {f["field"]: f for f in artifact["required_row_fields"]}
    d3_field = field_map["d3_contract_status"]
    assert "forbidden_values" in d3_field
    forbidden = d3_field["forbidden_values"]
    assert "APPROVED" in forbidden
    assert "PROMOTED" in forbidden
    assert "PRODUCTION_READY" in forbidden
    assert "RECOMMENDED" in forbidden
    assert "PREDICTIVE_EDGE_CONFIRMED" in forbidden


def test_d3_not_approval_warning_field_present(artifact):
    field_map = {f["field"]: f for f in artifact["required_row_fields"]}
    assert "d3_not_approval_warning" in field_map


def test_no_prediction_claim_field_present(artifact):
    field_map = {f["field"]: f for f in artifact["required_row_fields"]}
    assert "no_prediction_claim" in field_map


def test_no_betting_advice_field_present(artifact):
    field_map = {f["field"]: f for f in artifact["required_row_fields"]}
    assert "no_betting_advice" in field_map


# ---------------------------------------------------------------------------
# Artifact: data sources
# ---------------------------------------------------------------------------

def test_artifact_defines_data_sources(artifact):
    sources = artifact["data_sources"]
    assert "strategy_registry_lifecycle_status" in sources
    assert "p251_evidence_dashboard_payload" in sources
    assert "p257_best_strategy_overview_payload" in sources
    assert "p258_d3_contract_validation_artifact_chain" in sources


def test_all_data_sources_are_read_only(artifact):
    for key, source in artifact["data_sources"].items():
        assert source.get("db_write") is False, (
            f"Data source {key} must not write DB"
        )


# ---------------------------------------------------------------------------
# Artifact: allowed D3 contract statuses
# ---------------------------------------------------------------------------

EXPECTED_ALLOWED_STATUSES = [
    "NOT_EVALUATED_BY_D3",
    "CONTRACT_READY",
    "CONTRACT_BLOCKED",
    "NOT_APPLICABLE_HISTORICAL_ARTIFACT",
    "NOT_APPLICABLE_NO_REPLAY",
]


def test_artifact_defines_allowed_d3_contract_statuses(artifact):
    statuses = [s["status"] for s in artifact["allowed_d3_contract_statuses"]]
    for expected in EXPECTED_ALLOWED_STATUSES:
        assert expected in statuses, f"Allowed D3 status missing: {expected}"


def test_no_allowed_status_implies_approval(artifact):
    for entry in artifact["allowed_d3_contract_statuses"]:
        assert entry.get("implies_approval") is False, (
            f"D3 status {entry['status']} must not imply approval"
        )


def test_artifact_bans_approved_status(artifact):
    assert "APPROVED" in artifact["forbidden_d3_contract_statuses"]


def test_artifact_bans_promoted_status(artifact):
    assert "PROMOTED" in artifact["forbidden_d3_contract_statuses"]


def test_artifact_bans_production_ready_status(artifact):
    assert "PRODUCTION_READY" in artifact["forbidden_d3_contract_statuses"]


def test_artifact_bans_recommended_status(artifact):
    assert "RECOMMENDED" in artifact["forbidden_d3_contract_statuses"]


def test_artifact_bans_predictive_edge_confirmed_status(artifact):
    assert "PREDICTIVE_EDGE_CONFIRMED" in artifact["forbidden_d3_contract_statuses"]


# ---------------------------------------------------------------------------
# Artifact: safety semantics
# ---------------------------------------------------------------------------

def test_d3_is_not_a_prediction_model(artifact):
    assert artifact["mandatory_safety_semantics"]["d3_is_not_a_prediction_model"] is True


def test_contract_validation_is_not_strategy_evaluation(artifact):
    assert artifact["mandatory_safety_semantics"][
        "contract_validation_is_not_strategy_evaluation"
    ] is True


def test_not_yet_rejected_is_not_approval(artifact):
    assert artifact["mandatory_safety_semantics"]["not_yet_rejected_is_not_approval"] is True


def test_no_improved_accuracy_claimed(artifact):
    assert artifact["mandatory_safety_semantics"][
        "passing_contract_validation_does_not_imply_improved_prediction_accuracy"
    ] is True


def test_no_production_use_authorized(artifact):
    assert artifact["mandatory_safety_semantics"][
        "passing_validators_does_not_allow_production_use"
    ] is True


def test_no_recommendation_use_authorized(artifact):
    assert artifact["mandatory_safety_semantics"][
        "passing_validators_does_not_allow_recommendation_use"
    ] is True


def test_no_betting_advice_in_semantics(artifact):
    assert artifact["mandatory_safety_semantics"]["no_betting_advice"] is True


def test_no_lottery_edge_claimed(artifact):
    assert artifact["mandatory_safety_semantics"]["no_lottery_edge_claimed"] is True


def test_executable_gate_evaluation_remains_forbidden(artifact):
    assert artifact["mandatory_safety_semantics"][
        "executable_gate_evaluation_remains_forbidden"
    ] is True


# ---------------------------------------------------------------------------
# Artifact: required safety copy
# ---------------------------------------------------------------------------

def test_safety_copy_includes_d3_not_prediction_model(artifact):
    copy = artifact["required_safety_copy"]
    assert any("D3 is not a prediction model" in v for v in copy.values())


def test_safety_copy_includes_not_yet_rejected_not_approval(artifact):
    copy = artifact["required_safety_copy"]
    assert any("NOT_YET_REJECTED is not approval" in v for v in copy.values())


def test_safety_copy_includes_no_betting_advice(artifact):
    copy = artifact["required_safety_copy"]
    assert any("not betting advice" in v.lower() for v in copy.values())


def test_safety_copy_includes_no_accuracy_implication(artifact):
    copy = artifact["required_safety_copy"]
    assert any("accuracy" in v.lower() for v in copy.values())


# ---------------------------------------------------------------------------
# Artifact: next allowed task
# ---------------------------------------------------------------------------

def test_artifact_says_next_allowed_task_is_p258m(artifact):
    future = artifact["future_task_split"]
    assert "P258M" in future["p258m_authorized_scope"]


def test_artifact_says_running_d3_on_real_candidates_is_forbidden(artifact):
    future = artifact["future_task_split"]
    assert "FORBIDDEN" in future["running_d3_on_real_candidates"]


def test_each_future_task_requires_separate_authorization(artifact):
    assert artifact["future_task_split"]["each_task_requires_separate_explicit_authorization"] is True


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
    confirmed = artifact["forbidden_executable_modules_confirmed_absent"]
    assert module_name in confirmed


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
]


@pytest.mark.parametrize("import_line", FORBIDDEN_IMPORT_LINES)
def test_skeleton_still_has_no_forbidden_import(import_line):
    source = SKELETON_PATH.read_text()
    assert import_line not in source, (
        f"integration_skeleton.py contains forbidden import: {import_line!r}"
    )


# ---------------------------------------------------------------------------
# No forbidden function definitions in skeleton
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
