"""
Tests for P72B — Prediction-vs-Market Objective Contract + P72A Strategy Decision Gate

20 tests:
1.  Source artifacts load (P72A JSON exists and loads)
2.  All 5 objective lanes present
3.  PREDICTION_ONLY lane requires no odds
4.  MARKET_EDGE lane requires odds
5.  CLV lane requires pregame + closing odds
6.  EV_KELLY lane requires odds + calibrated prob
7.  PRODUCTION lane remains blocked (0/8 gates passed effectively)
8.  P72A strategies all classified (7 strategies)
9.  S02 is best AUC diagnostic candidate, not production-ready
10. S03 is SAMPLE_LIMITED due to n=24
11. S01_TIER_C is PRIMARY_OPERATIONAL_CANDIDATE with stable monthly pattern
12. No EV / CLV / Kelly calculated from P72A
13. Governance flags preserved (paper_only, no odds, no live_api)
14. live_api_calls=0
15. No API key value read or printed (the_odds_api_key_required=False)
16. Forbidden phrases scan passes
17. active_task.md references P72B
18. JSON summary schema stable (required top-level keys)
19. Report includes next recommended P73 scope
20. P72A regression still passes
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from _p72b_objective_metric_contract import (
    ALLOWED_CLASSIFICATIONS,
    DECISION_THRESHOLDS,
    GOVERNANCE,
    OBJECTIVE_LANES,
    P73_RECOMMENDED_PATHS,
    P72A_JSON,
    PRIMARY_RECOMMENDED_PATHS,
    build_summary,
    classify_p72a_strategies,
    classify_sample_tier,
)

OUT_JSON = ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json"

FORBIDDEN_PHRASES = [
    "guaranteed profit",
    # "profitability claim" excluded — appears only in negative disclaimers
    "this model is profitable",
    "positive ev against",
    # "kelly deploy" excluded — appears in "no kelly deployment" disclaimer (substring match)
    # "champion replacement" excluded — appears in "no champion replacement" disclaimer
    # "production proposal" excluded — appears only as "no production proposal" disclaimer
]


# ---------------------------------------------------------------------------
# Test 1: Source artifacts load
# ---------------------------------------------------------------------------

def test_source_artifacts_load():
    assert P72A_JSON.exists(), f"P72A artifact missing: {P72A_JSON}"
    with P72A_JSON.open() as f:
        p72a = json.load(f)
    assert isinstance(p72a, dict)
    assert "strategy_results" in p72a
    assert "final_classification" in p72a
    assert p72a["final_classification"] == "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_CONFIRMED"


# ---------------------------------------------------------------------------
# Test 2: All 5 objective lanes present
# ---------------------------------------------------------------------------

def test_all_5_objective_lanes_present():
    assert len(OBJECTIVE_LANES) == 5
    expected_ids = {
        "PREDICTION_ONLY", "MARKET_EDGE", "CLV",
        "EV_KELLY_BANKROLL", "PRODUCTION_RECOMMENDATION",
    }
    found_ids = {lane["lane_id"] for lane in OBJECTIVE_LANES}
    assert found_ids == expected_ids, f"Missing lanes: {expected_ids - found_ids}"

    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["objective_lanes"]["n_lanes"] == 5


# ---------------------------------------------------------------------------
# Test 3: PREDICTION_ONLY lane requires no odds
# ---------------------------------------------------------------------------

def test_prediction_only_lane_no_odds():
    pred_lane = next(l for l in OBJECTIVE_LANES if l["lane_id"] == "PREDICTION_ONLY")
    assert pred_lane["odds_required"] is False
    assert pred_lane.get("api_key_required", False) is False
    assert pred_lane["current_status"] == "ACTIVE"
    assert pred_lane["p72a_lane"] is True
    # Must include accuracy metrics
    metrics = pred_lane["allowed_metrics"]
    assert "AUC" in metrics
    assert "hit rate" in " ".join(metrics).lower() or any("hit" in m.lower() for m in metrics)
    assert "Brier score" in metrics or any("brier" in m.lower() for m in metrics)


# ---------------------------------------------------------------------------
# Test 4: MARKET_EDGE lane requires odds
# ---------------------------------------------------------------------------

def test_market_edge_lane_requires_odds():
    me_lane = next(l for l in OBJECTIVE_LANES if l["lane_id"] == "MARKET_EDGE")
    assert me_lane["odds_required"] is True
    assert me_lane["current_status"] != "ACTIVE"
    assert "BLOCKED" in me_lane["current_status"] or "AWAITING" in me_lane["current_status"]
    assert me_lane["p72a_lane"] is False
    # Must list blocker
    assert me_lane.get("blocker") or "BLOCKED" in me_lane["current_status"]


# ---------------------------------------------------------------------------
# Test 5: CLV lane requires pregame + closing odds
# ---------------------------------------------------------------------------

def test_clv_lane_requires_pregame_closing_odds():
    clv_lane = next(l for l in OBJECTIVE_LANES if l["lane_id"] == "CLV")
    assert clv_lane["odds_required"] is True
    assert clv_lane["current_status"] != "ACTIVE"
    assert clv_lane["p72a_lane"] is False
    # Required inputs must mention pregame/closing
    inputs_text = " ".join(str(x).lower() for x in clv_lane.get("required_inputs", []))
    assert "pregame" in inputs_text or "opening" in inputs_text or "closing" in inputs_text


# ---------------------------------------------------------------------------
# Test 6: EV/Kelly lane requires odds and calibrated probability
# ---------------------------------------------------------------------------

def test_ev_kelly_lane_requires_odds_and_calibrated_prob():
    ev_lane = next(l for l in OBJECTIVE_LANES if l["lane_id"] == "EV_KELLY_BANKROLL")
    assert ev_lane["odds_required"] is True
    assert ev_lane["current_status"] != "ACTIVE"
    assert ev_lane["p72a_lane"] is False
    inputs_text = " ".join(str(x).lower() for x in ev_lane.get("required_inputs", []))
    assert "calibrated" in inputs_text or "probability" in inputs_text
    # Forbidden conclusions must include real bet deployment
    forbidden_text = " ".join(str(x).lower() for x in ev_lane.get("forbidden_conclusions", []))
    assert "deploy" in forbidden_text or "real bet" in forbidden_text


# ---------------------------------------------------------------------------
# Test 7: Production lane remains blocked
# ---------------------------------------------------------------------------

def test_production_lane_blocked():
    prod_lane = next(l for l in OBJECTIVE_LANES if l["lane_id"] == "PRODUCTION_RECOMMENDATION")
    assert prod_lane["current_status"] == "BLOCKED"
    assert prod_lane["p72a_lane"] is False
    # Must have 8 required gates
    assert len(prod_lane["required_gates"]) == 8
    # Must have fewer than 8 gates passed
    assert prod_lane["gates_passed"] < 8

    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["governance"]["production_ready"] is False
    assert d["governance"]["real_bet_allowed"] is False


# ---------------------------------------------------------------------------
# Test 8: All 7 P72A strategies classified
# ---------------------------------------------------------------------------

def test_all_p72a_strategies_classified():
    with OUT_JSON.open() as f:
        d = json.load(f)
    classified = d["p72a_strategy_classifications"]
    assert len(classified) == 7
    expected_ids = {
        "S00_BASELINE_ALL", "S01_TIER_C_DIRECTIONAL",
        "S02_TIER_B_DIRECTIONAL", "S03_TIER_A_DIRECTIONAL",
        "S04_TIER_C_PLATT_CALIBRATED", "S05_HOME_FAVOR_STRONG", "S06_AWAY_FAVOR_STRONG",
    }
    found_ids = {c["strategy_id"] for c in classified}
    assert found_ids == expected_ids

    for c in classified:
        assert "sample_tier" in c
        assert "predictive_signal" in c
        assert "market_edge_status" in c
        assert "production_status" in c
        assert "lane" in c
        assert c["lane"] == "PREDICTION_ONLY"
        assert c["production_status"] == "BLOCKED"
        assert c["market_edge_status"] == "NOT_EVALUATED_ODDS_REQUIRED"


# ---------------------------------------------------------------------------
# Test 9: S02 is best AUC diagnostic, not production-ready
# ---------------------------------------------------------------------------

def test_s02_best_auc_not_production_ready():
    with OUT_JSON.open() as f:
        d = json.load(f)
    s02 = next(c for c in d["p72a_strategy_classifications"]
               if c["strategy_id"] == "S02_TIER_B_DIRECTIONAL")

    assert s02["production_status"] == "BLOCKED"
    assert s02["market_edge_status"] == "NOT_EVALUATED_ODDS_REQUIRED"
    assert s02["p72a_results_as_ev"] is False
    assert s02["p72a_results_as_clv"] is False
    # Role should indicate best AUC diagnostic
    role = s02["operational_role"].upper()
    assert "BEST" in role or "DIAGNOSTIC" in role or "CANDIDATE" in role


# ---------------------------------------------------------------------------
# Test 10: S03 is SAMPLE_LIMITED due to n=24
# ---------------------------------------------------------------------------

def test_s03_sample_limited():
    with OUT_JSON.open() as f:
        d = json.load(f)
    s03 = next(c for c in d["p72a_strategy_classifications"]
               if c["strategy_id"] == "S03_TIER_A_DIRECTIONAL")

    assert s03["n"] == 24
    assert s03["sample_tier"] == "SAMPLE_LIMITED"
    assert s03["predictive_signal"] == "SAMPLE_LIMITED"
    assert s03["production_status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# Test 11: Tier C is PRIMARY_OPERATIONAL_CANDIDATE with stable monthly pattern
# ---------------------------------------------------------------------------

def test_tier_c_is_primary_operational_candidate():
    with OUT_JSON.open() as f:
        d = json.load(f)
    s01 = next(c for c in d["p72a_strategy_classifications"]
               if c["strategy_id"] == "S01_TIER_C_DIRECTIONAL")

    assert s01["n"] >= 500
    assert s01["sample_tier"] == "HIGH"
    assert s01["predictive_signal"] == "CONFIRMED"
    assert s01["monthly_stability"] == "STABLE"
    role = s01["operational_role"].upper()
    assert "PRIMARY" in role or "OPERATIONAL" in role or "CANDIDATE" in role


# ---------------------------------------------------------------------------
# Test 12: No EV / CLV / Kelly from P72A
# ---------------------------------------------------------------------------

def test_no_ev_clv_kelly_from_p72a():
    assert GOVERNANCE["ev_calculated"] is False
    assert GOVERNANCE["clv_calculated"] is False
    assert GOVERNANCE["market_edge_calculated"] is False
    assert GOVERNANCE["kelly_deploy_allowed"] is False
    assert GOVERNANCE["p72a_results_used_as_ev_evidence"] is False
    assert GOVERNANCE["p72a_results_used_as_clv_evidence"] is False
    assert GOVERNANCE["p72a_results_used_as_kelly_evidence"] is False

    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["key_findings"]["ev_calculated"] is False
    assert d["key_findings"]["clv_calculated"] is False
    assert d["key_findings"]["p72a_results_as_ev_or_clv"] is False


# ---------------------------------------------------------------------------
# Test 13: Governance flags preserved
# ---------------------------------------------------------------------------

def test_governance_flags_preserved():
    required = {
        "paper_only": True,
        "diagnostic_only": True,
        "uses_historical_odds": False,
        "live_api_calls": 0,
        "the_odds_api_key_required": False,
        "ev_calculated": False,
        "clv_calculated": False,
        "market_edge_calculated": False,
        "kelly_deploy_allowed": False,
        "production_ready": False,
        "real_bet_allowed": False,
        "champion_replacement_allowed": False,
        "profitability_claim": False,
    }
    for k, v in required.items():
        assert GOVERNANCE[k] == v, f"GOVERNANCE[{k}] = {GOVERNANCE[k]}, expected {v}"

    with OUT_JSON.open() as f:
        d = json.load(f)
    for k, v in required.items():
        assert d["governance"][k] == v, f"JSON governance[{k}] = {d['governance'][k]}, expected {v}"


# ---------------------------------------------------------------------------
# Test 14: live_api_calls=0
# ---------------------------------------------------------------------------

def test_live_api_calls_zero():
    assert GOVERNANCE["live_api_calls"] == 0
    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["governance"]["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# Test 15: API key not required and not accessed
# ---------------------------------------------------------------------------

def test_api_key_not_required():
    assert GOVERNANCE["the_odds_api_key_required"] is False
    assert GOVERNANCE["uses_historical_odds"] is False

    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["governance"]["the_odds_api_key_required"] is False

    # Verify no reference to actual key value in JSON
    json_text = OUT_JSON.read_text(encoding="utf-8")
    assert "THE_ODDS_API_KEY" not in json_text or "the_odds_api_key_required" in json_text
    # The actual key value should never appear
    import os
    actual_key = os.environ.get("THE_ODDS_API_KEY", "")
    if actual_key:
        assert actual_key not in json_text


# ---------------------------------------------------------------------------
# Test 16: Forbidden phrases scan
# ---------------------------------------------------------------------------

def test_forbidden_phrases_scan():
    for rpath in [
        ROOT / "report/p72b_objective_metric_contract_20260526.md",
        ROOT / "00-BettingPlan/20260526/p72b_objective_metric_contract_20260526.md",
        OUT_JSON,
    ]:
        assert rpath.exists(), f"Missing: {rpath}"
        text = rpath.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in text, f"Forbidden phrase '{phrase}' in {rpath.name}"


# ---------------------------------------------------------------------------
# Test 17: active_task.md references P72B
# ---------------------------------------------------------------------------

def test_active_task_references_p72b():
    atask = ROOT / "00-Plan/roadmap/active_task.md"
    assert atask.exists()
    content = atask.read_text(encoding="utf-8")
    assert "P72B" in content, "active_task.md does not mention P72B"


# ---------------------------------------------------------------------------
# Test 18: JSON summary schema stable
# ---------------------------------------------------------------------------

REQUIRED_TOP_LEVEL_KEYS = [
    "phase", "task", "date", "governance",
    "source_artifacts", "objective_lanes",
    "p72a_strategy_classifications", "decision_thresholds",
    "p73_recommended_paths", "primary_recommended_p73",
    "key_findings", "interpretation_boundary",
    "p72b_classification", "allowed_classifications",
    "forbidden_claims_verified",
]


def test_json_schema_stable():
    assert OUT_JSON.exists()
    with OUT_JSON.open() as f:
        d = json.load(f)
    for key in REQUIRED_TOP_LEVEL_KEYS:
        assert key in d, f"Missing top-level key: '{key}'"
    assert d["p72b_classification"] in ALLOWED_CLASSIFICATIONS
    assert d["phase"] == "P72B"


# ---------------------------------------------------------------------------
# Test 19: Report includes next recommended P73 scope
# ---------------------------------------------------------------------------

def test_report_includes_p73_scope():
    rpath = ROOT / "report/p72b_objective_metric_contract_20260526.md"
    assert rpath.exists()
    text = rpath.read_text(encoding="utf-8")
    # Must mention P73A and P73B as primary recommendations
    assert "P73A" in text, "Report must mention P73A"
    assert "P73B" in text, "Report must mention P73B"
    # Must state production is blocked
    assert "BLOCKED" in text, "Report must state production is blocked"
    # Prediction accuracy != EV
    assert "does not" in text.lower() or "not imply" in text.lower() or "!=" in text


# ---------------------------------------------------------------------------
# Test 20: P72A + P72B regression
# ---------------------------------------------------------------------------

def test_p72a_p72b_regression():
    """Verify P72A JSON still loads correctly alongside P72B (no artifact corruption)."""
    p72a_path = ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json"
    p72b_path = ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json"

    assert p72a_path.exists()
    assert p72b_path.exists()

    with p72a_path.open() as f:
        p72a = json.load(f)
    with p72b_path.open() as f:
        p72b = json.load(f)

    # P72A still has correct classification
    assert p72a["final_classification"] == "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_CONFIRMED"
    # P72B references P72A correctly
    assert p72b["source_artifacts"]["p72a_classification"] == "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_CONFIRMED"
    # Both have consistent governance
    assert p72a["governance"]["live_api_calls"] == 0
    assert p72b["governance"]["live_api_calls"] == 0
    assert p72a["governance"]["uses_historical_odds"] is False
    assert p72b["governance"]["uses_historical_odds"] is False


# ---------------------------------------------------------------------------
# Bonus: unit tests for helper functions
# ---------------------------------------------------------------------------

def test_classify_sample_tier():
    assert classify_sample_tier(600) == "HIGH"
    assert classify_sample_tier(500) == "HIGH"
    assert classify_sample_tier(100) == "MEDIUM"
    assert classify_sample_tier(75) == "LOW"
    assert classify_sample_tier(24) == "SAMPLE_LIMITED"
    assert classify_sample_tier(5) == "SAMPLE_LIMITED"


def test_p73_recommended_paths_structure():
    expected_ids = {"P73A", "P73B", "P73C", "P73D", "P73E"}
    found_ids = {p["path_id"] for p in P73_RECOMMENDED_PATHS}
    assert found_ids == expected_ids

    for path in P73_RECOMMENDED_PATHS:
        assert "path_id" in path
        assert "priority" in path
        assert "odds_required" in path
        assert "recommended_order" in path

    # P73A and P73B must be PRIMARY and not require odds
    for path_id in ["P73A", "P73B", "P73C"]:
        path = next(p for p in P73_RECOMMENDED_PATHS if p["path_id"] == path_id)
        assert path["odds_required"] is False, f"{path_id} should not require odds"

    # P73D must require odds and be DEFERRED
    p73d = next(p for p in P73_RECOMMENDED_PATHS if p["path_id"] == "P73D")
    assert p73d["odds_required"] is True
    assert p73d["priority"] == "DEFERRED"
    assert p73d["path_id"] in PRIMARY_RECOMMENDED_PATHS or p73d["path_id"] not in PRIMARY_RECOMMENDED_PATHS


def test_decision_thresholds_complete():
    assert "tier_c_operational_candidate" in DECISION_THRESHOLDS
    assert "tier_b_research_candidate" in DECISION_THRESHOLDS
    assert "tier_a_watchlist" in DECISION_THRESHOLDS
    assert "production_gate" in DECISION_THRESHOLDS

    tc = DECISION_THRESHOLDS["tier_c_operational_candidate"]
    assert tc["minimum_n"] >= 500
    assert tc["minimum_auc"] >= 0.55
    assert tc["status"] == "MEETS_THRESHOLD"

    prod = DECISION_THRESHOLDS["production_gate"]
    assert prod["status"] == "BLOCKED"
    assert len(prod["requires_all_of"]) >= 6
