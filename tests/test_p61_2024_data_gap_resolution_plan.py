"""
Tests for P61 — 2024 Closing-Line Data Gap Resolution Plan

12 tests:
1.  P43 and P60 source artifacts exist and load
2.  P61 JSON exists with required top-level sections
3.  P61 classification is one of allowed values
4.  Source evaluations include >= 5 sources
5.  At least one source provides moneyline odds
6.  At least one source has FULL resolution contribution
7.  Resolution paths include PATH_A and PATH_B
8.  Impact analysis contains current_state and if_gap_resolved
9.  Governance flags correct (paper_only, live_api_calls=0, etc.)
10. No live API calls attempted (data_download_attempted=False)
11. Reports contain no forbidden affirmative claims
12. active_task.md references P61
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from _p61_2024_data_gap_resolution_plan import (
    ALLOWED_CLASSIFICATIONS,
    GOVERNANCE,
    P43_JSON,
    P60_JSON,
    build_resolution_paths,
    build_source_evaluations,
    classify_resolution_feasibility,
)

OUT_JSON = ROOT / "data/mlb_2025/derived/p61_2024_data_gap_resolution_plan_summary.json"

FORBIDDEN_PHRASES = [
    "guaranteed profit",
    "profitability claim",
    "ready_for_production",
    "promote_to_live",
    "deployment_ready",
    "recommend production",
    "escalate to live",
]
# Note: "production proposal" and "champion replacement" are used in negative
# governance disclaimers ("No production proposal", "No champion replacement")
# and are intentionally excluded from the forbidden scan to avoid false positives.


# ---------------------------------------------------------------------------
# Test 1: Source artifacts exist
# ---------------------------------------------------------------------------

def test_source_artifacts_exist():
    assert P43_JSON.exists(), f"P43 artifact missing: {P43_JSON}"
    assert P60_JSON.exists(), f"P60 artifact missing: {P60_JSON}"
    with P43_JSON.open() as f:
        p43 = json.load(f)
    with P60_JSON.open() as f:
        p60 = json.load(f)
    assert isinstance(p43, dict)
    assert isinstance(p60, dict)


# ---------------------------------------------------------------------------
# Test 2: P61 JSON has required sections
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = [
    "governance",
    "p43_context",
    "p60_context",
    "required_target_schema",
    "source_evaluations",
    "resolution_paths",
    "impact_analysis",
    "p61_classification",
    "allowed_classifications",
]


def test_p61_json_required_sections():
    assert OUT_JSON.exists(), f"Missing: {OUT_JSON}"
    with OUT_JSON.open() as f:
        d = json.load(f)
    for section in REQUIRED_SECTIONS:
        assert section in d, f"Missing section: '{section}'"


# ---------------------------------------------------------------------------
# Test 3: Classification is allowed
# ---------------------------------------------------------------------------

def test_p61_classification_allowed():
    with OUT_JSON.open() as f:
        d = json.load(f)
    cls = d["p61_classification"]
    assert cls in ALLOWED_CLASSIFICATIONS, f"'{cls}' not in allowed set"

    # Verify classify function always returns allowed value
    sources = build_source_evaluations()
    result = classify_resolution_feasibility(sources)
    assert result in ALLOWED_CLASSIFICATIONS


# ---------------------------------------------------------------------------
# Test 4: Source evaluations >= 5
# ---------------------------------------------------------------------------

def test_source_evaluation_count():
    sources = build_source_evaluations()
    assert len(sources) >= 5, f"Expected >= 5 sources, got {len(sources)}"

    # Each source must have required fields
    required_fields = [
        "source_name", "provides_moneyline_odds",
        "effort_estimate", "resolution_contribution", "priority",
    ]
    for s in sources:
        for field in required_fields:
            assert field in s, f"Source '{s.get('source_name','?')}' missing field '{field}'"


# ---------------------------------------------------------------------------
# Test 5: At least one source provides moneyline odds
# ---------------------------------------------------------------------------

def test_at_least_one_moneyline_source():
    sources = build_source_evaluations()
    ml_sources = [s for s in sources if s.get("provides_moneyline_odds") is True]
    assert len(ml_sources) >= 1, "No source confirmed to provide moneyline odds"


# ---------------------------------------------------------------------------
# Test 6: At least one FULL resolution source
# ---------------------------------------------------------------------------

def test_at_least_one_full_resolution_source():
    sources = build_source_evaluations()
    full_sources = [
        s for s in sources
        if str(s.get("resolution_contribution", "")).startswith("FULL")
    ]
    assert len(full_sources) >= 1, "No source with FULL resolution contribution found"


# ---------------------------------------------------------------------------
# Test 7: Resolution paths include PATH_A and PATH_B
# ---------------------------------------------------------------------------

def test_resolution_paths_have_a_and_b():
    paths = build_resolution_paths()
    path_ids = {p["path_id"] for p in paths}
    assert "PATH_A" in path_ids, "PATH_A missing from resolution paths"
    assert "PATH_B" in path_ids, "PATH_B missing from resolution paths"

    # PATH_A must be The Odds API (paid, but no live betting)
    path_a = next(p for p in paths if p["path_id"] == "PATH_A")
    assert "odds api" in path_a["name"].lower() or "odds" in path_a["name"].lower()

    # PATH_B must be free
    path_b = next(p for p in paths if p["path_id"] == "PATH_B")
    assert "$0" in path_b["cost"] or "free" in path_b["cost"].lower()


# ---------------------------------------------------------------------------
# Test 8: Impact analysis is complete
# ---------------------------------------------------------------------------

def test_impact_analysis_complete():
    with OUT_JSON.open() as f:
        d = json.load(f)
    impact = d["impact_analysis"]
    assert "current_state" in impact
    assert "if_gap_resolved" in impact
    assert "recommendation" in impact

    current = impact["current_state"]
    assert "p43_classification" in current
    assert "blocked_by_gap" in current

    resolved = impact["if_gap_resolved"]
    assert "p43_potential_upgrade" in resolved
    assert "risk_if_2024_differs" in resolved
    assert "downstream_unlock" in resolved
    assert len(resolved["downstream_unlock"]) >= 2


# ---------------------------------------------------------------------------
# Test 9: Governance flags correct
# ---------------------------------------------------------------------------

def test_governance_flags():
    required = {
        "paper_only": True,
        "diagnostic_only": True,
        "promotion_freeze": True,
        "kelly_deploy_allowed": False,
        "live_api_calls": 0,
        "tsl_crawler_modified": False,
        "champion_strategy_changed": False,
        "production_usage_proposed": False,
        "runtime_recommendation_logic_changed": False,
        "data_download_attempted": False,
        "paid_api_called": False,
    }
    for k, v in required.items():
        assert GOVERNANCE[k] == v, f"GOVERNANCE[{k}]={GOVERNANCE[k]}, expected {v}"

    with OUT_JSON.open() as f:
        d = json.load(f)
    gov = d["governance"]
    for k, v in required.items():
        assert gov[k] == v, f"JSON governance[{k}]={gov[k]}, expected {v}"


# ---------------------------------------------------------------------------
# Test 10: No live API calls or data downloads
# ---------------------------------------------------------------------------

def test_no_live_api_calls():
    assert GOVERNANCE["live_api_calls"] == 0
    assert GOVERNANCE["data_download_attempted"] is False
    assert GOVERNANCE["paid_api_called"] is False

    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["governance"]["live_api_calls"] == 0
    assert d["governance"]["data_download_attempted"] is False


# ---------------------------------------------------------------------------
# Test 11: Reports no forbidden claims
# ---------------------------------------------------------------------------

def test_reports_no_forbidden_claims():
    for rpath in [
        ROOT / "report/p61_2024_data_gap_resolution_plan_20260526.md",
        ROOT / "00-BettingPlan/20260526/p61_2024_data_gap_resolution_plan_20260526.md",
    ]:
        assert rpath.exists(), f"Missing: {rpath}"
        text = rpath.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in text, f"Forbidden phrase '{phrase}' in {rpath.name}"


# ---------------------------------------------------------------------------
# Test 12: active_task.md references P61
# ---------------------------------------------------------------------------

def test_active_task_references_p61():
    atask = ROOT / "00-Plan/roadmap/active_task.md"
    assert atask.exists()
    content = atask.read_text(encoding="utf-8")
    assert "P61" in content, "active_task.md does not mention P61"


# ---------------------------------------------------------------------------
# Bonus: structural integrity tests
# ---------------------------------------------------------------------------

def test_required_target_schema_columns():
    with OUT_JSON.open() as f:
        d = json.load(f)
    schema = d["required_target_schema"]
    required_cols = schema["required_columns"]
    for col in ["Away ML", "Home ML", "Away Score", "Home Score", "Date"]:
        assert col in required_cols, f"Required column '{col}' not in target schema"


def test_p43_data_gap_confirmed():
    """P43 must confirm data gap — this drives the entire P61 raison d'être."""
    with OUT_JSON.open() as f:
        d = json.load(f)
    ctx = d["p43_context"]
    assert ctx["data_gap_2024_confirmed"] is True
    assert ctx["rows_2024_missing_market"] > 0
    assert "BLOCKED" in ctx["p43_final_classification"]


def test_no_source_has_retrosheet_odds():
    """Retrosheet never provides moneyline odds — verify correctly categorized."""
    sources = build_source_evaluations()
    retro = next((s for s in sources if "retrosheet" in s["source_name"].lower()), None)
    assert retro is not None, "Retrosheet should be in source list"
    assert retro["provides_moneyline_odds"] is False
    assert retro["resolution_contribution"] == "SCORES_ONLY"
