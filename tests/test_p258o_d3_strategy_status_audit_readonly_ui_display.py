"""
P258O — D3 Strategy Status Audit: Read-only UI Display Tests

Validates index.html P258O section and the P258O research artifact.
No DB queries, no D3 execution, no random/numpy/scipy imports.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
ARTIFACT_PATH = REPO_ROOT / "outputs" / "research" / "p258o_d3_strategy_status_audit_readonly_ui_display_20260609.json"

ALLOWED_D3_STATUSES = [
    "NOT_EVALUATED_BY_D3",
    "CONTRACT_READY",
    "CONTRACT_BLOCKED",
    "NOT_APPLICABLE_HISTORICAL_ARTIFACT",
    "NOT_APPLICABLE_NO_REPLAY",
]

FORBIDDEN_D3_STATUSES = [
    "APPROVED",
    "PROMOTED",
    "PRODUCTION_READY",
    "RECOMMENDED",
    "PREDICTIVE_EDGE_CONFIRMED",
]

REQUIRED_SAFETY_SUBSTRINGS = [
    "D3 是不是預測模型",
    "NOT_YET_REJECTED",
    "不作為下注建議",
    "不代表提升預測準確性",
    "合約驗證不是策略評估",
]

REQUIRED_SAFETY_SUBSTRINGS_EN = [
    "NOT_YET_REJECTED",
    "prediction model",
    "betting",
    "prediction accuracy",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def html() -> str:
    assert INDEX_HTML.exists(), f"index.html not found: {INDEX_HTML}"
    return INDEX_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def p258_section(html) -> str:
    """Extract the P258O section from index.html."""
    m = re.search(
        r"<!-- ===== P258O D3 Strategy Status.*?<!-- ===== END P258O =====",
        html, re.DOTALL,
    )
    assert m, "P258O section not found in index.html"
    return m.group(0)


@pytest.fixture(scope="module")
def p258_js(html) -> str:
    """Extract the P258O JS block from index.html."""
    m = re.search(
        r"// ===== P258O D3 STRATEGY STATUS.*?p258Init\(\);",
        html, re.DOTALL,
    )
    return m.group(0) if m else ""


@pytest.fixture(scope="module")
def artifact() -> dict:
    assert ARTIFACT_PATH.exists(), f"P258O artifact missing: {ARTIFACT_PATH}"
    with ARTIFACT_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Section existence and nav button
# ---------------------------------------------------------------------------

def test_p258_section_exists(p258_section):
    assert len(p258_section) > 100


def test_p258_nav_button_exists(html):
    assert 'data-section="p258-d3-audit"' in html


def test_p258_section_id_exists(html):
    assert 'id="p258-d3-audit-section"' in html


def test_p258_page_title_in_section(p258_section):
    assert "D3" in p258_section
    assert "Strategy Status" in p258_section or "策略狀態" in p258_section or "合約稽核" in p258_section


# ---------------------------------------------------------------------------
# 2. API route fetch target
# ---------------------------------------------------------------------------

def test_p258_fetches_correct_api_route(p258_js):
    assert "/api/replay/d3-strategy-status-audit" in p258_js


def test_p258_no_db_fetch_in_js(p258_js):
    assert "sqlite3" not in p258_js
    assert "DatabaseManager" not in p258_js


def test_p258_no_d3_execution_in_js(p258_js):
    assert "run_contract_validation_flow" not in p258_js
    assert "gate_statistics" not in p258_js
    assert "gate_orchestrator" not in p258_js
    assert "null_factory" not in p258_js


# ---------------------------------------------------------------------------
# 3. Safety disclaimers in HTML section
# ---------------------------------------------------------------------------

def test_p258_disclaimer_banner_exists(p258_section):
    assert "p258-disclaimer-banner" in p258_section or "p258-disclaimer" in p258_section


def test_p258_not_yet_rejected_disclaimer(p258_section):
    assert "NOT_YET_REJECTED" in p258_section


def test_p258_not_prediction_model_disclaimer(p258_section):
    assert "預測模型" in p258_section or "prediction model" in p258_section.lower()


def test_p258_not_betting_advice_disclaimer(p258_section):
    assert "下注建議" in p258_section or "betting" in p258_section.lower()


def test_p258_not_improved_accuracy_disclaimer(p258_section):
    assert "預測準確性" in p258_section or "prediction accuracy" in p258_section.lower()


def test_p258_contract_not_evaluation_disclaimer(p258_section):
    assert "合約驗證不是策略評估" in p258_section or "not strategy evaluation" in p258_section.lower()


# ---------------------------------------------------------------------------
# 4. D3 contract status vocabulary in JS
# ---------------------------------------------------------------------------

def test_p258_allowed_d3_statuses_in_js(p258_js):
    for status in ALLOWED_D3_STATUSES:
        assert status in p258_js, f"Allowed D3 status missing from JS: {status}"


def test_p258_forbidden_d3_statuses_absent_from_js(p258_js):
    for status in FORBIDDEN_D3_STATUSES:
        assert status not in p258_js, f"Forbidden D3 status found in JS: {status}"


def test_p258_no_approved_in_js(p258_js):
    assert "'APPROVED'" not in p258_js
    assert '"APPROVED"' not in p258_js


def test_p258_no_recommended_in_js(p258_js):
    assert "'RECOMMENDED'" not in p258_js
    assert '"RECOMMENDED"' not in p258_js


def test_p258_no_production_ready_in_js(p258_js):
    assert "PRODUCTION_READY" not in p258_js


def test_p258_no_predictive_edge_in_js(p258_js):
    assert "PREDICTIVE_EDGE_CONFIRMED" not in p258_js


# ---------------------------------------------------------------------------
# 5. Visual separation — two column groups
# ---------------------------------------------------------------------------

def test_p258_lifecycle_evidence_group_header(p258_section):
    assert "生命週期" in p258_section or "lifecycle" in p258_section.lower()


def test_p258_d3_contract_group_header_separate(p258_section):
    assert "D3 合約狀態" in p258_section or "D3 contract" in p258_section.lower()


def test_p258_d3_not_approval_label_in_ui(p258_section):
    assert "非核准" in p258_section or "not approval" in p258_section.lower()


# ---------------------------------------------------------------------------
# 6. Filters present
# ---------------------------------------------------------------------------

def test_p258_lottery_filter_exists(p258_section):
    assert "p258-filter-lottery" in p258_section


def test_p258_lifecycle_filter_exists(p258_section):
    assert "p258-filter-lifecycle" in p258_section


def test_p258_d3_filter_exists(p258_section):
    assert "p258-filter-d3" in p258_section


def test_p258_filter_d3_options_only_allowed(p258_section):
    for status in FORBIDDEN_D3_STATUSES:
        assert status not in p258_section, f"Forbidden D3 status in filter options: {status}"


# ---------------------------------------------------------------------------
# 7. No forbidden language in entire P258O section + JS
# ---------------------------------------------------------------------------

def test_p258_no_approval_language_anywhere(p258_section, p258_js):
    combined = p258_section + p258_js
    # These forbidden status tokens must not appear as option values
    for status in FORBIDDEN_D3_STATUSES:
        assert "value='" + status + "'" not in combined
        assert 'value="' + status + '"' not in combined


def test_p258_no_random_import_in_js(p258_js):
    import_lines = [ln.strip() for ln in p258_js.splitlines() if ln.lstrip().startswith(("import ", "from "))]
    assert not any("random" in ln for ln in import_lines)


def test_p258_no_numpy_in_js(p258_js):
    assert "numpy" not in p258_js


def test_p258_no_scipy_in_js(p258_js):
    assert "scipy" not in p258_js


# ---------------------------------------------------------------------------
# 8. P258O research artifact validation
# ---------------------------------------------------------------------------

def test_artifact_parses(artifact):
    assert isinstance(artifact, dict)


def test_artifact_final_classification(artifact):
    assert artifact["final_classification"] == "P258O_D3_STRATEGY_STATUS_AUDIT_READONLY_UI_DISPLAY_READY"


def test_artifact_ui_display_implemented(artifact):
    assert artifact["ui_display_implemented"] is True


def test_artifact_api_route_used(artifact):
    assert artifact["api_route_used"] == "GET /api/replay/d3-strategy-status-audit"


def test_artifact_safety_disclaimers_listed(artifact):
    disclaimers = artifact["safety_disclaimers_displayed"]
    assert len(disclaimers) >= 5
    assert any("prediction model" in d.lower() for d in disclaimers)
    assert any("NOT_YET_REJECTED" in d or "not approval" in d.lower() for d in disclaimers)
    assert any("betting" in d.lower() for d in disclaimers)
    assert any("prediction accuracy" in d.lower() for d in disclaimers)
    assert any("strategy evaluation" in d.lower() for d in disclaimers)


def test_artifact_no_db_query(artifact):
    assert "DB" in artifact["no_db_query_proof"] or "database" in artifact["no_db_query_proof"].lower()


def test_artifact_no_d3_execution(artifact):
    assert "D3" in artifact["no_d3_execution_proof"] or "d3" in artifact["no_d3_execution_proof"].lower()


def test_artifact_no_strategy_evaluation(artifact):
    assert "recommendation" in artifact["no_strategy_evaluation_proof"].lower() or "ranking" in artifact["no_strategy_evaluation_proof"].lower()


def test_artifact_forbidden_d3_statuses_listed(artifact):
    for status in FORBIDDEN_D3_STATUSES:
        assert status in artifact["forbidden_d3_statuses_confirmed_absent"]


def test_artifact_d3_not_prediction_model(artifact):
    assert artifact["governance"]["d3_is_not_prediction_model"] is True


def test_artifact_d3_not_approval_gate(artifact):
    assert artifact["governance"]["d3_is_not_approval_gate"] is True


def test_artifact_not_yet_rejected_not_approval(artifact):
    assert artifact["governance"]["not_yet_rejected_is_not_approval"] is True


def test_artifact_next_task_is_p258p(artifact):
    assert "P258P" in artifact["future_task_split"]["next_allowed_task"]


def test_artifact_p258o_does_not_authorize_p258p_automatically(artifact):
    assert artifact["governance"]["p258o_does_not_authorize_p258p_automatically"] is True


def test_artifact_running_d3_on_real_candidates_forbidden(artifact):
    assert "FORBIDDEN" in artifact["future_task_split"]["running_d3_on_real_candidate_methods"]


# ---------------------------------------------------------------------------
# 9. No changes to API route files
# ---------------------------------------------------------------------------

def test_no_api_route_files_modified_in_branch():
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        capture_output=True, text=True,
        cwd=str(REPO_ROOT),
    )
    changed = result.stdout.strip().splitlines()
    api_files = [f for f in changed if f.startswith("lottery_api/routes/")]
    assert api_files == [], f"API route files must not be modified in P258O: {api_files}"


def test_no_d3_gate_files_modified_in_branch():
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        capture_output=True, text=True,
        cwd=str(REPO_ROOT),
    )
    changed = result.stdout.strip().splitlines()
    gate_files = [f for f in changed if "d3_gate" in f]
    assert gate_files == [], f"D3 gate files must not be modified in P258O: {gate_files}"
