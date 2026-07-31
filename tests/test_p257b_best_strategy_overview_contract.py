"""P257B — Contract tests for governance artifact.

Validates the P257B governance JSON, warning copy semantics,
no-flag compliance, and absence of forbidden claims.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_JSON = REPO_ROOT / "outputs" / "research" / "p257b_best_strategy_overview_readonly_ui_20260608.json"
ARTIFACT_MD   = REPO_ROOT / "outputs" / "research" / "p257b_best_strategy_overview_readonly_ui_20260608.md"
P257A_JSON    = REPO_ROOT / "outputs" / "research" / "p257a_best_nbet_strategy_overview_historical_replay_20260608.json"

VALID_FINAL_DECISIONS = {
    "BEST_STRATEGY_OVERVIEW_READONLY_UI_IMPLEMENTED",
    "API_IMPLEMENTED_UI_BLOCKED_NEEDS_SCOPE",
    "UI_IMPLEMENTED_API_NOT_REQUIRED",
    "HOLD_NEEDS_FRONTEND_STRUCTURE_CLARIFICATION",
}

FORBIDDEN_POSITIVE_CLAIMS = [
    "保證", "必中", "推薦下注", "提高中獎率",
    "deployable edge confirmed",
    "betting recommendation",
    "guaranteed win",
]


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_JSON.exists(), f"P257B artifact missing: {ARTIFACT_JSON}"
    with ARTIFACT_JSON.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_text():
    assert ARTIFACT_MD.exists(), f"P257B markdown missing: {ARTIFACT_MD}"
    return ARTIFACT_MD.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Basic structure
# ---------------------------------------------------------------------------

def test_json_parses(artifact):
    assert isinstance(artifact, dict)


def test_task_id(artifact):
    assert artifact["task_id"] == "P257B"


def test_classification_exists(artifact):
    assert "classification" in artifact
    assert artifact["classification"]


def test_final_decision_valid(artifact):
    assert artifact["final_decision"] in VALID_FINAL_DECISIONS


# ---------------------------------------------------------------------------
# 2. Governance flags all True
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("flag", [
    "no_db_write_confirmed",
    "no_replay_generation_confirmed",
    "no_registry_mutation_confirmed",
    "no_strategy_promotion_confirmed",
    "no_recommendation_logic_change_confirmed",
    "no_betting_advice_confirmed",
])
def test_governance_flags_true(artifact, flag):
    assert artifact.get(flag) is True, f"Flag {flag!r} must be True"


# ---------------------------------------------------------------------------
# 3. Warning copy includes required disclaimers
# ---------------------------------------------------------------------------

def test_warning_copy_historical_only(artifact):
    wc = artifact.get("warning_copy", {})
    all_text = " ".join(wc.get("zh", []) + wc.get("en", []))
    assert any(w in all_text for w in ("歷史", "historical", "回測")), \
        "Warning copy must mention historical nature"


def test_warning_copy_no_betting_advice(artifact):
    wc = artifact.get("warning_copy", {})
    all_text = " ".join(wc.get("zh", []) + wc.get("en", []))
    assert any(w in all_text for w in ("不提供投注", "no betting", "not betting advice")), \
        "Warning copy must disclaim betting advice"


def test_warning_copy_no_future_guarantee(artifact):
    wc = artifact.get("warning_copy", {})
    all_text = " ".join(wc.get("zh", []) + wc.get("en", []))
    assert any(w in all_text for w in ("不代表未來", "no future", "future win", "future guarantee")), \
        "Warning copy must disclaim future win guarantee"


# ---------------------------------------------------------------------------
# 4. No forbidden positive claims in artifact or markdown
# ---------------------------------------------------------------------------

def test_no_forbidden_claims_in_artifact(artifact):
    artifact_str = json.dumps(artifact, ensure_ascii=False)
    for phrase in FORBIDDEN_POSITIVE_CLAIMS:
        assert phrase not in artifact_str, \
            f"Forbidden claim {phrase!r} found in P257B artifact"


def test_no_forbidden_claims_in_markdown(md_text):
    for phrase in FORBIDDEN_POSITIVE_CLAIMS:
        assert phrase not in md_text, \
            f"Forbidden claim {phrase!r} found in P257B markdown"


# ---------------------------------------------------------------------------
# 5. API and UI sections documented
# ---------------------------------------------------------------------------

def test_implemented_api_endpoint_present(artifact):
    ep = artifact.get("implemented_api_endpoint", "")
    assert "best-strategy-overview" in ep or ep == "N/A", \
        f"implemented_api_endpoint should reference the endpoint, got: {ep!r}"


def test_source_artifact_references_p257a(artifact):
    src = artifact.get("source_artifact", "")
    assert "p257a" in src.lower(), \
        f"source_artifact must reference P257A, got: {src!r}"


# ---------------------------------------------------------------------------
# 6. P257A regression — source artifact still valid
# ---------------------------------------------------------------------------

def test_p257a_artifact_still_parses():
    assert P257A_JSON.exists()
    with P257A_JSON.open() as f:
        data = json.load(f)
    assert data["task_id"] == "P257A"
    assert data["final_decision"] == "BEST_NBET_STRATEGY_OVERVIEW_DATA_READY_FOR_UI_DESIGN"
    assert data["no_db_write_confirmed"] is True
