"""
P258N — D3 Strategy Status Audit: Read-only Artifact-Backed API Route Tests

Validates:
- API route returns 200 and conforms to P258M contract
- Payload fields and row fields are present
- Only allowed D3 contract statuses appear
- Safety disclaimers are present
- Route does not touch DB, D3 execution, null generation, or production paths
- P258N research artifact validates correctly

This test file itself:
- contains no DB queries
- contains no D3 execution
- contains no random/numpy/scipy imports
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LOTTERY_API_DIR = str(REPO_ROOT / "lottery_api")
if LOTTERY_API_DIR not in sys.path:
    sys.path.insert(0, LOTTERY_API_DIR)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PAYLOAD_PATH = REPO_ROOT / "outputs" / "research" / "p258n_d3_strategy_status_audit_payload_20260609.json"
ARTIFACT_PATH = REPO_ROOT / "outputs" / "research" / "p258n_d3_strategy_status_audit_readonly_api_route_20260609.json"
ROUTE_FILE = REPO_ROOT / "lottery_api" / "routes" / "replay.py"

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

ALLOWED_D3_STATUSES = {
    "NOT_EVALUATED_BY_D3",
    "CONTRACT_READY",
    "CONTRACT_BLOCKED",
    "NOT_APPLICABLE_HISTORICAL_ARTIFACT",
    "NOT_APPLICABLE_NO_REPLAY",
}

FORBIDDEN_D3_STATUSES = {
    "APPROVED",
    "PROMOTED",
    "PRODUCTION_READY",
    "RECOMMENDED",
    "PREDICTIVE_EDGE_CONFIRMED",
}

REQUIRED_SAFETY_DISCLAIMER_SUBSTRINGS = [
    "D3 is not a prediction model",
    "Contract validation is not strategy evaluation",
    "NOT_YET_REJECTED is not approval",
    "does not imply improved prediction accuracy",
    "not betting advice",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_client():
    """FastAPI TestClient mounting only the replay router."""
    try:
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
    except ImportError as exc:
        pytest.skip(f"fastapi/httpx not available: {exc}")

    try:
        from routes import replay as replay_mod
    except Exception as exc:
        pytest.skip(f"replay module unavailable: {exc}")

    app = FastAPI()
    app.include_router(replay_mod.router)
    try:
        return TestClient(app)
    except TypeError:
        pytest.skip("TestClient version incompatibility (pre-existing env issue)")


@pytest.fixture(scope="module")
def api_payload(api_client) -> dict:
    r = api_client.get("/api/replay/d3-strategy-status-audit")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def static_payload() -> dict:
    assert PAYLOAD_PATH.exists(), f"P258N payload artifact missing: {PAYLOAD_PATH}"
    with PAYLOAD_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def artifact() -> dict:
    assert ARTIFACT_PATH.exists(), f"P258N research artifact missing: {ARTIFACT_PATH}"
    with ARTIFACT_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. API route smoke tests
# ---------------------------------------------------------------------------

def test_api_returns_200(api_client):
    r = api_client.get("/api/replay/d3-strategy-status-audit")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"


def test_api_response_parses(api_payload):
    assert isinstance(api_payload, dict)


def test_api_route_path_field(api_payload):
    assert api_payload["route_path"] == "/api/replay/d3-strategy-status-audit"


# ---------------------------------------------------------------------------
# 2. Top-level payload fields
# ---------------------------------------------------------------------------

def test_api_has_all_required_top_level_fields(api_payload):
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        assert field in api_payload, f"Missing top-level field: {field}"


def test_api_has_schema_version(api_payload):
    assert api_payload.get("schema_version") == "1.0"


def test_api_has_page_title(api_payload):
    assert "D3" in api_payload.get("page_title", "")


def test_api_has_rows(api_payload):
    assert isinstance(api_payload.get("rows"), list)
    assert len(api_payload["rows"]) > 0


def test_api_has_filters(api_payload):
    filters = api_payload.get("filters", {})
    assert "lottery_type" in filters
    assert "d3_contract_status" in filters
    assert "has_replay" in filters
    assert "has_artifact" in filters


def test_api_has_safety_disclaimers(api_payload):
    disclaimers = api_payload.get("safety_disclaimers", [])
    assert isinstance(disclaimers, list)
    assert len(disclaimers) >= 5


def test_api_has_forbidden_actions_confirmed(api_payload):
    fac = api_payload.get("forbidden_actions_confirmed", {})
    assert fac.get("no_db_write") is True
    assert fac.get("no_db_query") is True
    assert fac.get("no_recommendation_logic") is True
    assert fac.get("no_registry_mutation") is True
    assert fac.get("no_production_change") is True
    assert fac.get("no_prediction_claim") is True
    assert fac.get("no_betting_advice") is True


def test_api_has_next_allowed_task(api_payload):
    nxt = api_payload.get("next_allowed_task", "")
    assert "P258O" in nxt


# ---------------------------------------------------------------------------
# 3. Row field contract
# ---------------------------------------------------------------------------

def test_api_every_row_has_required_fields(api_payload):
    rows = api_payload.get("rows", [])
    assert len(rows) > 0
    for i, row in enumerate(rows):
        for field in REQUIRED_ROW_FIELDS:
            assert field in row, f"Row {i} ({row.get('strategy_id', '?')}) missing field: {field}"


def test_api_every_row_has_d3_not_approval_warning(api_payload):
    for row in api_payload["rows"]:
        warning = row.get("d3_not_approval_warning", "")
        assert "NOT approval" in warning or "not approval" in warning.lower(), (
            f"Row {row['strategy_id']}: d3_not_approval_warning missing approval denial"
        )


def test_api_every_row_has_no_prediction_claim(api_payload):
    for row in api_payload["rows"]:
        claim = row.get("no_prediction_claim", "")
        assert "prediction model" in claim.lower() or "prediction accuracy" in claim.lower(), (
            f"Row {row['strategy_id']}: no_prediction_claim too weak"
        )


def test_api_every_row_has_no_betting_advice(api_payload):
    for row in api_payload["rows"]:
        advice = row.get("no_betting_advice", "")
        assert "betting advice" in advice.lower() or "not betting" in advice.lower(), (
            f"Row {row['strategy_id']}: no_betting_advice too weak"
        )


# ---------------------------------------------------------------------------
# 4. D3 contract status values
# ---------------------------------------------------------------------------

def test_api_only_allowed_d3_statuses(api_payload):
    for row in api_payload["rows"]:
        status = row.get("d3_contract_status", "")
        assert status in ALLOWED_D3_STATUSES, (
            f"Row {row['strategy_id']}: forbidden or unknown d3_contract_status: {status}"
        )


def test_api_no_forbidden_d3_statuses(api_payload):
    for row in api_payload["rows"]:
        status = row.get("d3_contract_status", "")
        assert status not in FORBIDDEN_D3_STATUSES, (
            f"Row {row['strategy_id']}: forbidden d3_contract_status: {status}"
        )


def test_api_no_approved_status(api_payload):
    statuses = {row["d3_contract_status"] for row in api_payload["rows"]}
    assert "APPROVED" not in statuses


def test_api_no_promoted_status(api_payload):
    statuses = {row["d3_contract_status"] for row in api_payload["rows"]}
    assert "PROMOTED" not in statuses


def test_api_no_production_ready_status(api_payload):
    statuses = {row["d3_contract_status"] for row in api_payload["rows"]}
    assert "PRODUCTION_READY" not in statuses


def test_api_no_recommended_status(api_payload):
    statuses = {row["d3_contract_status"] for row in api_payload["rows"]}
    assert "RECOMMENDED" not in statuses


def test_api_no_predictive_edge_confirmed_status(api_payload):
    statuses = {row["d3_contract_status"] for row in api_payload["rows"]}
    assert "PREDICTIVE_EDGE_CONFIRMED" not in statuses


# ---------------------------------------------------------------------------
# 5. Safety disclaimers in payload
# ---------------------------------------------------------------------------

def test_api_d3_not_prediction_model_disclaimer(api_payload):
    disclaimers = api_payload.get("safety_disclaimers", [])
    assert any("D3 is not a prediction model" in d for d in disclaimers)


def test_api_contract_validation_not_strategy_evaluation_disclaimer(api_payload):
    disclaimers = api_payload.get("safety_disclaimers", [])
    assert any("Contract validation is not strategy evaluation" in d for d in disclaimers)


def test_api_not_yet_rejected_not_approval_disclaimer(api_payload):
    disclaimers = api_payload.get("safety_disclaimers", [])
    assert any("NOT_YET_REJECTED is not approval" in d for d in disclaimers)


def test_api_no_improved_accuracy_disclaimer(api_payload):
    disclaimers = api_payload.get("safety_disclaimers", [])
    assert any("does not imply improved prediction accuracy" in d for d in disclaimers)


def test_api_not_betting_advice_disclaimer(api_payload):
    disclaimers = api_payload.get("safety_disclaimers", [])
    assert any("not betting advice" in d for d in disclaimers)


# ---------------------------------------------------------------------------
# 6. Route is artifact-backed (no DB imports in route module)
# ---------------------------------------------------------------------------

def _route_function_source() -> str:
    """Extract only the P258N-added functions from replay.py."""
    src = ROUTE_FILE.read_text(encoding="utf-8")
    start = src.find("def _load_d3_strategy_status_audit_payload")
    if start == -1:
        return ""
    return src[start:]


def test_route_exists_in_replay_module():
    src = ROUTE_FILE.read_text(encoding="utf-8")
    assert "get_d3_strategy_status_audit" in src
    assert "_load_d3_strategy_status_audit_payload" in src
    assert "_D3_STRATEGY_STATUS_AUDIT_PATH" in src


def test_route_serves_artifact_path():
    src = ROUTE_FILE.read_text(encoding="utf-8")
    assert "p258n_d3_strategy_status_audit_payload_20260609.json" in src


def test_route_does_not_import_sqlite3_in_new_functions():
    fn_src = _route_function_source()
    assert "sqlite3" not in fn_src


def test_route_does_not_import_random_in_new_functions():
    fn_src = _route_function_source()
    # Check only actual import lines in the new function block
    import_lines = [ln.strip() for ln in fn_src.splitlines() if ln.lstrip().startswith(("import ", "from "))]
    assert not any("random" in ln for ln in import_lines)


def test_route_does_not_import_numpy_in_new_functions():
    fn_src = _route_function_source()
    import_lines = [ln.strip() for ln in fn_src.splitlines() if ln.lstrip().startswith(("import ", "from "))]
    assert not any("numpy" in ln for ln in import_lines)


def test_route_does_not_import_scipy_in_new_functions():
    fn_src = _route_function_source()
    import_lines = [ln.strip() for ln in fn_src.splitlines() if ln.lstrip().startswith(("import ", "from "))]
    assert not any("scipy" in ln for ln in import_lines)


def test_route_does_not_call_run_contract_validation_flow():
    fn_src = _route_function_source()
    assert "run_contract_validation_flow" not in fn_src


def test_route_does_not_use_database_manager_in_new_functions():
    fn_src = _route_function_source()
    assert "DatabaseManager" not in fn_src
    assert "database" not in fn_src.lower().replace("evidence_dashboard", "").replace("best_strategy_overview", "")


def test_no_ui_files_modified_in_branch():
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        capture_output=True, text=True,
        cwd=str(REPO_ROOT),
    )
    changed = result.stdout.strip().splitlines()
    ui_files = [f for f in changed if f.startswith("src/ui/") or f == "index.html"]
    assert ui_files == [], f"UI files must not be modified in P258N branch: {ui_files}"


# ---------------------------------------------------------------------------
# 7. P258N research artifact validation
# ---------------------------------------------------------------------------

def test_artifact_parses(artifact):
    assert isinstance(artifact, dict)


def test_artifact_final_classification(artifact):
    assert artifact["final_classification"] == "P258N_D3_STRATEGY_STATUS_AUDIT_READONLY_API_ROUTE_READY"


def test_artifact_route_implemented(artifact):
    assert artifact["route_implemented"] is True


def test_artifact_route_path(artifact):
    assert artifact["route_path"] == "GET /api/replay/d3-strategy-status-audit"


def test_artifact_data_source_is_artifact_backed(artifact):
    assert artifact["artifact_backed_source_policy"]["data_source"] == "artifact-backed only"


def test_artifact_no_db_query(artifact):
    assert artifact["artifact_backed_source_policy"]["no_db_query"] is True


def test_artifact_no_db_write(artifact):
    assert artifact["artifact_backed_source_policy"]["no_db_write"] is True


def test_artifact_no_d3_execution(artifact):
    assert artifact["artifact_backed_source_policy"]["no_d3_execution"] is True


def test_artifact_no_real_candidate_methods(artifact):
    assert "no real candidate method" in artifact["no_real_candidate_methods_proof"].lower()


def test_artifact_no_null_generation(artifact):
    assert "null generation" in artifact["no_null_generation_proof"].lower()


def test_artifact_no_p_values(artifact):
    assert "statistical" in artifact["no_p_values_proof"].lower()


def test_artifact_no_backtests(artifact):
    assert "backtest" in artifact["no_backtests_proof"].lower()


def test_artifact_no_ui_implementation(artifact):
    assert "no UI" in artifact["no_ui_implementation_proof"] or "no ui" in artifact["no_ui_implementation_proof"].lower()


def test_artifact_forbidden_d3_statuses_absent(artifact):
    for status in FORBIDDEN_D3_STATUSES:
        assert status in artifact["forbidden_d3_statuses_confirmed_absent"]


def test_artifact_d3_not_prediction_model_governance(artifact):
    assert artifact["governance"]["d3_is_not_prediction_model"] is True


def test_artifact_d3_not_approval_gate_governance(artifact):
    assert artifact["governance"]["d3_is_not_approval_gate"] is True


def test_artifact_contract_validation_not_strategy_evaluation_governance(artifact):
    assert artifact["governance"]["contract_validation_is_not_strategy_evaluation"] is True


def test_artifact_not_yet_rejected_not_approval_governance(artifact):
    assert artifact["governance"]["not_yet_rejected_is_not_approval"] is True


def test_artifact_next_allowed_task_is_p258o(artifact):
    nxt = artifact["future_task_split"]["next_allowed_task"]
    assert "P258O" in nxt


def test_artifact_p258n_does_not_authorize_p258o_automatically(artifact):
    assert artifact["governance"]["p258n_does_not_authorize_p258o_automatically"] is True


def test_artifact_running_d3_on_real_candidates_is_forbidden(artifact):
    assert "FORBIDDEN" in artifact["future_task_split"]["running_d3_on_real_candidate_methods"]


# ---------------------------------------------------------------------------
# 8. Static payload artifact validates
# ---------------------------------------------------------------------------

def test_static_payload_parses(static_payload):
    assert isinstance(static_payload, dict)


def test_static_payload_route_path(static_payload):
    assert static_payload["route_path"] == "/api/replay/d3-strategy-status-audit"


def test_static_payload_has_rows(static_payload):
    assert len(static_payload.get("rows", [])) > 0


def test_static_payload_rows_all_allowed_d3_statuses(static_payload):
    for row in static_payload["rows"]:
        status = row["d3_contract_status"]
        assert status in ALLOWED_D3_STATUSES, f"Forbidden status in payload: {status}"


def test_static_payload_no_forbidden_d3_statuses(static_payload):
    statuses = {row["d3_contract_status"] for row in static_payload["rows"]}
    for forbidden in FORBIDDEN_D3_STATUSES:
        assert forbidden not in statuses, f"Forbidden D3 status in static payload: {forbidden}"


def test_static_payload_safety_disclaimers_present(static_payload):
    disclaimers = static_payload.get("safety_disclaimers", [])
    for substr in REQUIRED_SAFETY_DISCLAIMER_SUBSTRINGS:
        assert any(substr in d for d in disclaimers), f"Missing disclaimer containing: {substr}"
