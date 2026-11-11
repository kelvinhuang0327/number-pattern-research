"""
P76 — Tests for Corrected Tier C Final Rule Selection + 2026 Accumulation Plan
31 tests covering: artifact loading, scorecard mechanics, decision logic,
accumulation plan, roadmap, governance, forbidden phrases, and regression chain.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCRIPT = ROOT / "scripts/_p76_corrected_tier_c_final_rule_selection.py"
JSON_OUT = ROOT / "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json"
REPORT_OUT = ROOT / "report/p76_corrected_tier_c_final_rule_selection_20260526.md"

P75B_JSON = ROOT / "data/mlb_2025/derived/p75b_calibration_diagnostics_corrected_tier_c_summary.json"
P75A_JSON = ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json"
P74_JSON  = ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json"
P73_JSON  = ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json"
P72B_JSON = ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json"
P72A_JSON = ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json"

R125 = "TIER_C_HOME_PLUS_AWAY_125"
R100 = "TIER_C_HOME_PLUS_AWAY_100"

ALLOWED_CLASSIFICATIONS = [
    "P76_HOME_PLUS_AWAY_125_SELECTED_FOR_2026_SHADOW_TRACKING",
    "P76_HOME_PLUS_AWAY_100_SELECTED_FOR_2026_SHADOW_TRACKING",
    "P76_DUAL_FINALISTS_RETAINED_UNTIL_2026_DATA",
    "P76_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
    "P76_FAILED_VALIDATION",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def p76_module():
    spec = importlib.util.spec_from_file_location("_p76", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def p76_result(p76_module):
    return p76_module.run_p76()


@pytest.fixture(scope="module")
def p76_json() -> dict:
    assert JSON_OUT.exists(), f"Output JSON not found: {JSON_OUT}"
    with open(JSON_OUT) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p75b_json() -> dict:
    assert P75B_JSON.exists()
    with open(P75B_JSON) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Source artifact loading
# ---------------------------------------------------------------------------
def test_p76_source_artifact_p75b_exists():
    assert P75B_JSON.exists(), "P75B JSON is required for P76"


def test_p76_source_artifact_p75a_exists():
    assert P75A_JSON.exists(), "P75A JSON is required for P76"


# ---------------------------------------------------------------------------
# 2. Finalist extraction
# ---------------------------------------------------------------------------
def test_p76_both_finalists_extracted(p76_result):
    finalists = p76_result.get("step1_finalists", {})
    assert R125 in finalists, "HOME_PLUS_AWAY_125 must be a finalist"
    assert R100 in finalists, "HOME_PLUS_AWAY_100 must be a finalist"


def test_p76_finalist_125_metrics_match_p75b(p76_result):
    m = p76_result["step1_finalists"][R125]
    assert m["n"] == 316
    assert abs(m["hit_rate"] - 0.6392) < 1e-3
    assert abs(m["auc"] - 0.5787) < 1e-3
    assert abs(m["cal_brier"] - 0.2274) < 1e-3
    assert abs(m["cal_ece"] - 0.0877) < 1e-3


def test_p76_finalist_100_metrics_match_p75b(p76_result):
    m = p76_result["step1_finalists"][R100]
    assert m["n"] == 373
    assert abs(m["hit_rate"] - 0.6327) < 1e-3
    assert abs(m["auc"] - 0.5603) < 1e-3
    assert abs(m["cal_brier"] - 0.2254) < 1e-3
    assert abs(m["cal_ece"] - 0.0712) < 1e-3


# ---------------------------------------------------------------------------
# 3. Scorecard axis weights
# ---------------------------------------------------------------------------
def test_p76_axis_weights_sum_to_1(p76_module):
    total = sum(p76_module.AXIS_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9, f"Axis weights must sum to 1.0, got {total}"


def test_p76_axis_weights_values(p76_module):
    aw = p76_module.AXIS_WEIGHTS
    assert aw["directional"] == pytest.approx(0.30)
    assert aw["calibration"] == pytest.approx(0.25)
    assert aw["coverage"] == pytest.approx(0.20)
    assert aw["stability_risk"] == pytest.approx(0.15)
    assert aw["future_readiness"] == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# 4. Scorecard computation
# ---------------------------------------------------------------------------
def test_p76_scorecard_computed_for_both_finalists(p76_result):
    sc = p76_result.get("step2_scorecard", {})
    assert R125 in sc
    assert R100 in sc


def test_p76_scorecard_125_total_in_range(p76_result):
    total = p76_result["step2_scorecard"][R125]["weighted_total"]
    assert 0.0 <= total <= 1.0, f"Scorecard total must be in [0,1], got {total}"


def test_p76_scorecard_100_total_in_range(p76_result):
    total = p76_result["step2_scorecard"][R100]["weighted_total"]
    assert 0.0 <= total <= 1.0, f"Scorecard total must be in [0,1], got {total}"


def test_p76_all_five_axes_present_in_scorecard(p76_result, p76_module):
    sc125 = p76_result["step2_scorecard"][R125]["axes"]
    for axis in p76_module.AXIS_WEIGHTS:
        assert axis in sc125, f"Axis '{axis}' missing from scorecard"


def test_p76_directional_axis_125_wins(p76_result):
    """HOME_PLUS_AWAY_125 has better AUC (0.579 > 0.560) and hit_delta (0.034 > 0.027)."""
    axis_wins = p76_result["step3_decision"]["axis_wins"]
    assert axis_wins["directional"] == R125, (
        "Directional axis must favor HOME_PLUS_AWAY_125 (better AUC + hit_delta)"
    )


def test_p76_calibration_axis_100_wins(p76_result):
    """HOME_PLUS_AWAY_100 has better cal_brier (0.2254 < 0.2274) and cal_ece (0.071 < 0.088)."""
    axis_wins = p76_result["step3_decision"]["axis_wins"]
    assert axis_wins["calibration"] == R100, (
        "Calibration axis must favor HOME_PLUS_AWAY_100 (better Brier + ECE)"
    )


def test_p76_coverage_axis_100_wins(p76_result):
    """HOME_PLUS_AWAY_100 has larger n (373 > 316) and coverage fraction (0.70 > 0.59)."""
    axis_wins = p76_result["step3_decision"]["axis_wins"]
    assert axis_wins["coverage"] == R100, (
        "Coverage axis must favor HOME_PLUS_AWAY_100 (larger n + coverage)"
    )


def test_p76_stability_risk_axis_tie(p76_result):
    """Both rules are MODERATE stability with no severe caveats → TIE."""
    axis_wins = p76_result["step3_decision"]["axis_wins"]
    assert axis_wins["stability_risk"] == "TIE", (
        "Stability/risk axis must be TIE (both MODERATE, no caveats)"
    )


def test_p76_future_readiness_axis_125_wins(p76_result):
    """HOME_PLUS_AWAY_125 has better AUC and temperature calibration method (more robust)."""
    axis_wins = p76_result["step3_decision"]["axis_wins"]
    assert axis_wins["future_readiness"] == R125, (
        "Future readiness axis must favor HOME_PLUS_AWAY_125 (AUC + temperature method)"
    )


# ---------------------------------------------------------------------------
# 5. Decision logic
# ---------------------------------------------------------------------------
def test_p76_classification_in_allowed_list(p76_result):
    cls = p76_result.get("p76_classification", "")
    assert cls in ALLOWED_CLASSIFICATIONS, f"Classification '{cls}' not in allowed list"


def test_p76_classification_is_dual_finalists(p76_result):
    """Score delta is extremely small (<0.02) → dual finalists retained."""
    cls = p76_result.get("p76_classification", "")
    assert cls == "P76_DUAL_FINALISTS_RETAINED_UNTIL_2026_DATA", (
        f"Expected dual-finalist classification, got '{cls}'"
    )


def test_p76_score_delta_below_min_threshold(p76_result):
    delta = p76_result["step3_decision"]["score_delta"]
    assert delta < 0.02, (
        f"Score delta {delta:.4f} >= 0.02 — should trigger dual retention not selection"
    )


def test_p76_dual_finalists_flag_set(p76_result):
    assert p76_result["step3_decision"]["dual_finalists"] is True


def test_p76_winner_is_none_when_dual_retained(p76_result):
    assert p76_result["step3_decision"]["winner"] is None


# ---------------------------------------------------------------------------
# 6. Accumulation plan
# ---------------------------------------------------------------------------
def test_p76_accumulation_plan_primary_rule(p76_result):
    plan = p76_result["step4_accumulation_plan"]
    assert plan["primary_rule"] == R125, (
        "Primary rule must be HOME_PLUS_AWAY_125 (higher AUC / directional priority)"
    )


def test_p76_accumulation_plan_shadow_includes_100(p76_result):
    plan = p76_result["step4_accumulation_plan"]
    assert R100 in plan["shadow_rules"], "HOME_PLUS_AWAY_100 must be tracked as shadow rule"


def test_p76_accumulation_plan_monthly_cadence_count(p76_result):
    cadence = p76_result["step4_accumulation_plan"]["monthly_cadence"]
    assert len(cadence) >= 5, "Monthly cadence must have at least 5 entries (Apr–Nov 2026)"


def test_p76_accumulation_start_date(p76_result):
    plan = p76_result["step4_accumulation_plan"]
    assert plan["accumulation_start"] == "2026-04-01"


def test_p76_stop_criteria_rolling_window(p76_result):
    stop = p76_result["step4_accumulation_plan"]["stop_criteria"]
    assert stop["rolling_window_games"] == 100
    assert stop["hit_rate_floor"] == pytest.approx(0.55)


def test_p76_tier_b_threshold_min_n(p76_result):
    tier_b = p76_result["step4_accumulation_plan"]["tier_b_threshold"]
    assert tier_b["min_n"] == 200, "Tier B analysis requires n>=200 (per P73B spec)"


def test_p76_market_edge_status_deferred(p76_result):
    me = p76_result["step4_accumulation_plan"]["market_edge_resume"]
    assert me["status"] == "DEFERRED", "Market-edge must remain DEFERRED (no odds API key)"


# ---------------------------------------------------------------------------
# 7. Roadmap
# ---------------------------------------------------------------------------
def test_p76_roadmap_phase_count(p76_result):
    roadmap = p76_result["step5_roadmap"]
    assert len(roadmap) == 6, f"Roadmap must have 6 phases (P76–P81), got {len(roadmap)}"


def test_p76_roadmap_contains_all_phases(p76_result):
    phases = {p["phase"] for p in p76_result["step5_roadmap"]}
    for expected in ["P76", "P77", "P78", "P79", "P80", "P81"]:
        assert expected in phases, f"Phase {expected} missing from roadmap"


def test_p76_roadmap_p80_deferred(p76_result):
    p80 = next((p for p in p76_result["step5_roadmap"] if p["phase"] == "P80"), None)
    assert p80 is not None
    assert p80["status"] == "DEFERRED", "P80 market-edge must be DEFERRED until odds available"


# ---------------------------------------------------------------------------
# 8. Governance
# ---------------------------------------------------------------------------
def test_p76_governance_no_ev_no_clv_no_kelly(p76_result):
    gov = p76_result.get("governance", {})
    assert gov.get("ev_calculated") is False
    assert gov.get("clv_calculated") is False
    assert gov.get("kelly_deploy_allowed") is False


def test_p76_governance_live_api_calls_zero(p76_result):
    gov = p76_result.get("governance", {})
    assert gov.get("live_api_calls") == 0


def test_p76_governance_paper_only_true(p76_result):
    gov = p76_result.get("governance", {})
    assert gov.get("paper_only") is True
    assert gov.get("production_ready") is False
    assert gov.get("real_bet_allowed") is False


# ---------------------------------------------------------------------------
# 9. Forbidden phrase scan
# ---------------------------------------------------------------------------
FORBIDDEN_PHRASES = [
    "expected_value",
    "closing_line_value",
    '"clv_calculated": true',
    "kelly fraction",
    '"kelly_deploy_allowed": true',
    '"production_ready": true',
    "profitability confirmed",
    '"real_bet_allowed": true',
]


def test_p76_forbidden_phrase_scan_clean(p76_json):
    text = json.dumps(p76_json).lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase.lower() not in text, f"Forbidden phrase found: '{phrase}'"


# ---------------------------------------------------------------------------
# 10. Regression — prior phase classifications unchanged
# ---------------------------------------------------------------------------
def test_p76_regression_prior_phases_intact():
    """All prior phase JSON summaries must still carry their expected classifications."""
    chain = [
        (P72A_JSON, ["p72a_classification", "final_classification"], "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_CONFIRMED"),
        (P72B_JSON, ["p72b_classification"], "P72B_OBJECTIVE_CONTRACT_READY"),
        (P73_JSON,  ["p73_classification"], "P73_TIER_C_OPERATIONAL_STABLE_TIER_B_RESEARCH_CONFIRMED"),
        (P74_JSON,  ["p74_classification"], "P74_TIER_C_HOME_AWAY_CORRECTION_CONFIRMED"),
        (P75A_JSON, ["p75a_classification"], "P75A_MULTI_CANDIDATE_REQUIRES_CALIBRATION"),
        (P75B_JSON, ["p75b_classification"], "P75B_MULTI_CANDIDATE_KEEP_FOR_NEXT_PHASE"),
    ]
    for path, keys, expected in chain:
        assert path.exists(), f"Missing prior artifact: {path}"
        with open(path) as f:
            data = json.load(f)
        value = ""
        for k in keys:
            v = data.get(k)
            if v:
                value = str(v)
                break
        assert value == expected, (
            f"{path.name}: expected classification '{expected}', got '{value}'"
        )
