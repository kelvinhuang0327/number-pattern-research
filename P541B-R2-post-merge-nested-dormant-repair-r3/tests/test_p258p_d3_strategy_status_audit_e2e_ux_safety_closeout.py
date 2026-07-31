"""
P258P — D3 Strategy Status Audit: E2E / UX / Safety Closeout Tests

Validates the full P258L–P258O arc:
- P258N API route returns correct payload
- P258O UI section has all required safety elements
- P258P closeout artifact validates
- No forbidden vocabulary anywhere
- No DB query, D3 execution, random/numpy/scipy imports

This test file itself contains no DB queries, no D3 execution,
no random/numpy/scipy imports.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LOTTERY_API_DIR = str(REPO_ROOT / "lottery_api")
if LOTTERY_API_DIR not in sys.path:
    sys.path.insert(0, LOTTERY_API_DIR)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

INDEX_HTML = REPO_ROOT / "index.html"
P258P_ARTIFACT = REPO_ROOT / "outputs" / "research" / "p258p_d3_strategy_status_audit_e2e_ux_safety_closeout_20260609.json"
P258O_ARTIFACT = REPO_ROOT / "outputs" / "research" / "p258o_d3_strategy_status_audit_readonly_ui_display_20260609.json"

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

REQUIRED_SAFETY_SUBSTRINGS = [
    "NOT_YET_REJECTED",
    "預測模型",
    "下注建議",
    "預測準確性",
    "合約驗證不是策略評估",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def html() -> str:
    assert INDEX_HTML.exists(), f"index.html not found: {INDEX_HTML}"
    return INDEX_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def p258_html_section(html) -> str:
    m = re.search(
        r"<!-- ===== P258O D3 Strategy Status.*?<!-- ===== END P258O =====",
        html, re.DOTALL,
    )
    assert m, "P258O section not found in index.html"
    return m.group(0)


@pytest.fixture(scope="module")
def p258_js_block(html) -> str:
    m = re.search(
        r"// ===== P258O D3 STRATEGY STATUS.*?p258Init\(\);",
        html, re.DOTALL,
    )
    return m.group(0) if m else ""


@pytest.fixture(scope="module")
def api_client():
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
        pytest.skip("TestClient version incompatibility")


@pytest.fixture(scope="module")
def api_payload(api_client) -> dict:
    r = api_client.get("/api/replay/d3-strategy-status-audit")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    return r.json()


@pytest.fixture(scope="module")
def p258p_artifact() -> dict:
    assert P258P_ARTIFACT.exists(), f"P258P artifact missing: {P258P_ARTIFACT}"
    with P258P_ARTIFACT.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. P258P artifact validation
# ---------------------------------------------------------------------------

def test_p258p_artifact_parses(p258p_artifact):
    assert isinstance(p258p_artifact, dict)


def test_p258p_final_classification(p258p_artifact):
    assert p258p_artifact["final_classification"] == "P258P_D3_STRATEGY_STATUS_AUDIT_E2E_UX_SAFETY_CLOSEOUT_READY"


def test_p258p_arc_closed(p258p_artifact):
    assert p258p_artifact["arc_closed"] is not None
    assert "P258L" in p258p_artifact["arc_closed"]
    assert "P258P" in p258p_artifact["arc_closed"]


def test_p258p_recommended_next_state_is_hold(p258p_artifact):
    state = p258p_artifact["recommended_next_state"]
    assert "HOLD" in state or "WAITING" in state


def test_p258p_d3_not_prediction_model(p258p_artifact):
    assert p258p_artifact["governance"]["d3_is_not_prediction_model"] is True


def test_p258p_d3_not_approval_gate(p258p_artifact):
    assert p258p_artifact["governance"]["d3_is_not_approval_gate"] is True


def test_p258p_not_yet_rejected_not_approval(p258p_artifact):
    assert p258p_artifact["governance"]["not_yet_rejected_is_not_approval"] is True


def test_p258p_arc_final_status_all_merged(p258p_artifact):
    arc = p258p_artifact["p258_arc_final_status"]
    for task in ["P258L", "P258M", "P258N", "P258O"]:
        assert "MERGED" in arc[task], f"{task} not marked MERGED"


def test_p258p_forbidden_next_tasks_declared(p258p_artifact):
    ft = p258p_artifact["future_task_split"]
    assert "FORBIDDEN" in ft["running_d3_on_real_candidate_methods"]
    assert "FORBIDDEN" in ft["executable_gate_evaluation"]
    assert "FORBIDDEN" in ft["null_generation"]
    assert "FORBIDDEN" in ft["db_write"]
    assert "FORBIDDEN" in ft["treating_not_yet_rejected_as_approved"]


# ---------------------------------------------------------------------------
# 2. API E2E validation
# ---------------------------------------------------------------------------

def test_api_returns_200(api_client):
    r = api_client.get("/api/replay/d3-strategy-status-audit")
    assert r.status_code == 200


def test_api_payload_parses(api_payload):
    assert isinstance(api_payload, dict)


def test_api_route_path_field(api_payload):
    assert api_payload.get("route_path") == "/api/replay/d3-strategy-status-audit"


def test_api_row_count_14(api_payload):
    rows = api_payload.get("rows", [])
    assert len(rows) == 14, f"Expected 14 rows, got {len(rows)}"


def test_api_all_required_top_level_fields(api_payload):
    required = [
        "schema_version", "generated_at", "source_artifacts", "route_path",
        "page_title", "summary", "filters", "rows",
        "safety_disclaimers", "forbidden_actions_confirmed", "next_allowed_task",
    ]
    for f in required:
        assert f in api_payload, f"Missing top-level field: {f}"


def test_api_every_row_has_required_fields(api_payload):
    required = [
        "lottery_type", "strategy_id", "lifecycle_status", "evidence_status",
        "d3_contract_status", "d3_contract_reason",
        "d3_not_approval_warning", "no_prediction_claim", "no_betting_advice",
    ]
    for row in api_payload["rows"]:
        for f in required:
            assert f in row, f"Row {row.get('strategy_id','?')} missing field: {f}"


def test_api_only_allowed_d3_statuses(api_payload):
    for row in api_payload["rows"]:
        assert row["d3_contract_status"] in ALLOWED_D3_STATUSES, (
            f"Forbidden status: {row['d3_contract_status']}"
        )


def test_api_no_forbidden_d3_statuses(api_payload):
    statuses = {row["d3_contract_status"] for row in api_payload["rows"]}
    for forbidden in FORBIDDEN_D3_STATUSES:
        assert forbidden not in statuses


def test_api_safety_disclaimers_count(api_payload):
    assert len(api_payload.get("safety_disclaimers", [])) >= 5


def test_api_forbidden_actions_confirmed(api_payload):
    fac = api_payload.get("forbidden_actions_confirmed", {})
    assert fac.get("no_db_write") is True
    assert fac.get("no_db_query") is True
    assert fac.get("no_prediction_claim") is True
    assert fac.get("no_betting_advice") is True


def test_api_rows_cover_all_three_lottery_types(api_payload):
    types = {row["lottery_type"] for row in api_payload["rows"]}
    assert "DAILY_539" in types
    assert "BIG_LOTTO" in types
    assert "POWER_LOTTO" in types


def test_api_every_row_d3_not_approval_warning_present(api_payload):
    for row in api_payload["rows"]:
        w = row.get("d3_not_approval_warning", "")
        assert "NOT approval" in w or "not approval" in w.lower()


def test_api_every_row_no_prediction_claim(api_payload):
    for row in api_payload["rows"]:
        c = row.get("no_prediction_claim", "")
        assert "prediction" in c.lower()


def test_api_every_row_no_betting_advice(api_payload):
    for row in api_payload["rows"]:
        a = row.get("no_betting_advice", "")
        assert "betting" in a.lower() or "evidence" in a.lower()


# ---------------------------------------------------------------------------
# 3. UI section safety validation
# ---------------------------------------------------------------------------

def test_ui_nav_button_exists(html):
    assert 'data-section="p258-d3-audit"' in html


def test_ui_section_exists(html):
    assert 'id="p258-d3-audit-section"' in html


def test_ui_disclaimer_banner_exists(p258_html_section):
    assert "p258-disclaimer-banner" in p258_html_section


def test_ui_all_safety_disclaimers_present(p258_html_section):
    for substr in REQUIRED_SAFETY_SUBSTRINGS:
        assert substr in p258_html_section, f"Missing safety copy: {substr}"


def test_ui_not_yet_rejected_is_not_approval(p258_html_section):
    assert "NOT_YET_REJECTED" in p258_html_section
    assert "核准" in p258_html_section or "approval" in p258_html_section.lower()


def test_ui_lifecycle_evidence_group_present(p258_html_section):
    assert "生命週期" in p258_html_section or "lifecycle" in p258_html_section.lower()


def test_ui_d3_contract_group_present(p258_html_section):
    assert "D3 合約狀態" in p258_html_section


def test_ui_d3_labeled_non_approval(p258_html_section):
    assert "非核准" in p258_html_section or "not approval" in p258_html_section.lower()


def test_ui_filters_all_present(p258_html_section):
    assert "p258-filter-lottery" in p258_html_section
    assert "p258-filter-lifecycle" in p258_html_section
    assert "p258-filter-d3" in p258_html_section


def test_ui_filters_no_forbidden_d3_options(p258_html_section):
    for status in FORBIDDEN_D3_STATUSES:
        assert f"value='{status}'" not in p258_html_section
        assert f'value="{status}"' not in p258_html_section


def test_ui_rows_table_exists(p258_html_section):
    assert "p258-rows-table" in p258_html_section
    assert "p258-rows-tbody" in p258_html_section


def test_ui_summary_bar_exists(p258_html_section):
    assert "p258-summary-bar" in p258_html_section


def test_ui_status_element_exists(p258_html_section):
    assert "p258-status" in p258_html_section


# ---------------------------------------------------------------------------
# 4. JS safety validation
# ---------------------------------------------------------------------------

def test_js_fetches_correct_route(p258_js_block):
    assert "/api/replay/d3-strategy-status-audit" in p258_js_block


def test_js_only_allowed_d3_statuses(p258_js_block):
    for status in ALLOWED_D3_STATUSES:
        assert status in p258_js_block


def test_js_no_forbidden_d3_statuses(p258_js_block):
    for status in FORBIDDEN_D3_STATUSES:
        assert status not in p258_js_block


def test_js_no_db_query(p258_js_block):
    assert "sqlite3" not in p258_js_block
    assert "DatabaseManager" not in p258_js_block


def test_js_no_d3_execution(p258_js_block):
    assert "run_contract_validation_flow" not in p258_js_block
    assert "gate_orchestrator" not in p258_js_block
    assert "null_factory" not in p258_js_block


def test_js_no_numpy(p258_js_block):
    assert "numpy" not in p258_js_block


def test_js_no_scipy(p258_js_block):
    assert "scipy" not in p258_js_block


def test_js_empty_state_handled(p258_js_block):
    assert "無符合條件" in p258_js_block or "no result" in p258_js_block.lower()


def test_js_loading_state_handled(p258_js_block):
    assert "載入中" in p258_js_block or "loading" in p258_js_block.lower()


def test_js_error_state_handled(p258_js_block):
    assert "載入失敗" in p258_js_block or "error" in p258_js_block.lower()


# ---------------------------------------------------------------------------
# 5. No forbidden vocabulary anywhere in P258O section + JS
# ---------------------------------------------------------------------------

def test_no_forbidden_vocabulary_in_section_or_js(p258_html_section, p258_js_block):
    combined = p258_html_section + p258_js_block
    for status in FORBIDDEN_D3_STATUSES:
        assert status not in combined, f"Forbidden vocabulary found: {status}"


def test_no_betting_advice_in_section(p258_html_section):
    lower = p258_html_section.lower()
    assert "betting advice" not in lower


def test_no_improved_accuracy_claim_in_section(p258_html_section):
    lower = p258_html_section.lower()
    assert "improved prediction accuracy" not in lower
    assert "improve your winning" not in lower


# ---------------------------------------------------------------------------
# 6. No branch changes to API/D3 gate files
# ---------------------------------------------------------------------------

def test_no_api_route_files_modified():
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    changed = result.stdout.strip().splitlines()
    api_files = [f for f in changed if f.startswith("lottery_api/routes/")]
    assert api_files == [], f"API route files must not be modified in P258P: {api_files}"


def test_no_d3_gate_files_modified():
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    changed = result.stdout.strip().splitlines()
    gate_files = [f for f in changed if "d3_gate" in f]
    assert gate_files == [], f"D3 gate files must not be modified in P258P: {gate_files}"


def test_no_index_html_modified_unexpectedly():
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    changed = result.stdout.strip().splitlines()
    # index.html may only be present for minimal safety fixes; if it is,
    # verify it is not adding forbidden vocabulary
    if "index.html" in changed:
        diff_result = subprocess.run(
            ["git", "diff", "origin/main...HEAD", "--", "index.html"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        diff_text = diff_result.stdout
        for status in FORBIDDEN_D3_STATUSES:
            assert "+" + status not in diff_text, f"Forbidden status added to index.html: {status}"
