"""
Tests for P72A — Odds-Free Strategy Accuracy Backtest

15 tests:
1.  Summary JSON exists
2.  Governance fields correct (no odds, no API key, no EV/CLV/Kelly)
3.  No odds API key required
4.  No live API calls (live_api_calls=0)
5.  No EV / CLV / Kelly fields present as results
6.  Strategy results exist for all defined strategies
7.  Every strategy has n (sample size)
8.  Every strategy has hit rate
9.  Every strategy has AUC or explicit unavailable flag
10. Every strategy has Brier or explicit unavailable flag
11. Monthly stability exists for all strategies
12. Final classification is an allowed value
13. Report contains no profitability claim
14. Report clearly states odds-free accuracy is not betting edge
15. active_task.md references P72A
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from _p72a_odds_free_strategy_accuracy_backtest import (
    ALLOWED_CLASSIFICATIONS,
    GOVERNANCE,
    STRATEGIES,
    build_summary,
    classify_strategy,
    compute_auc,
    compute_brier_score,
    compute_hit_rate,
    evaluate_strategy,
    load_records,
    platt_calibrate,
)

OUT_JSON = ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json"

FORBIDDEN_PHRASES = [
    "profitability claim",
    "this model is profitable",
    "guaranteed profit",
    # "positive ev" excluded — only appears in negative disclaimers ("does not imply positive ev")
    "kelly deploy",
    "real bet",
    "champion replacement",
    "production proposal",
]


# ---------------------------------------------------------------------------
# Test 1: Summary JSON exists
# ---------------------------------------------------------------------------

def test_summary_json_exists():
    assert OUT_JSON.exists(), f"Missing: {OUT_JSON}"
    with OUT_JSON.open() as f:
        d = json.load(f)
    assert isinstance(d, dict)
    assert "strategy_results" in d
    assert "final_classification" in d
    assert "governance" in d


# ---------------------------------------------------------------------------
# Test 2: Governance fields correct
# ---------------------------------------------------------------------------

def test_governance_fields_correct():
    required = {
        "paper_only": True,
        "diagnostic_only": True,
        "uses_historical_odds": False,
        "live_api_calls": 0,
        "paid_api_called": False,
        "the_odds_api_key_required": False,
        "market_edge_calculated": False,
        "ev_calculated": False,
        "clv_calculated": False,
        "kelly_deploy_allowed": False,
        "production_ready": False,
        "real_bet_allowed": False,
        "champion_replacement_allowed": False,
        "profitability_claim": False,
    }
    for k, v in required.items():
        assert GOVERNANCE[k] == v, f"GOVERNANCE[{k}]={GOVERNANCE[k]}, expected {v}"

    with OUT_JSON.open() as f:
        d = json.load(f)
    gov = d["governance"]
    for k, v in required.items():
        assert gov[k] == v, f"JSON governance[{k}]={gov[k]}, expected {v}"


# ---------------------------------------------------------------------------
# Test 3: No odds API key required
# ---------------------------------------------------------------------------

def test_no_odds_api_key_required():
    assert GOVERNANCE["the_odds_api_key_required"] is False
    assert GOVERNANCE["paid_api_called"] is False
    assert GOVERNANCE["uses_historical_odds"] is False

    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["governance"]["the_odds_api_key_required"] is False
    assert d["odds_used"] is False
    assert d["api_key_required"] is False


# ---------------------------------------------------------------------------
# Test 4: No live API calls
# ---------------------------------------------------------------------------

def test_no_live_api_calls():
    assert GOVERNANCE["live_api_calls"] == 0
    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["governance"]["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# Test 5: No EV / CLV / Kelly treated as results
# ---------------------------------------------------------------------------

def test_no_ev_clv_kelly_as_results():
    assert GOVERNANCE["ev_calculated"] is False
    assert GOVERNANCE["clv_calculated"] is False
    assert GOVERNANCE["market_edge_calculated"] is False
    assert GOVERNANCE["kelly_deploy_allowed"] is False

    with OUT_JSON.open() as f:
        d = json.load(f)
    assert d["ev_calculated"] is False
    assert d["clv_calculated"] is False
    assert d["market_edge_calculated"] is False

    # Verify none of the strategy results contain ev, clv, or kelly_deploy keys
    for strat in d["strategy_results"]:
        assert "ev" not in strat, "Strategy result should not contain EV"
        assert "clv" not in strat, "Strategy result should not contain CLV"
        assert "kelly_deploy" not in strat, "Strategy result should not contain kelly_deploy"


# ---------------------------------------------------------------------------
# Test 6: Strategy results exist for all defined strategies
# ---------------------------------------------------------------------------

def test_all_strategies_present():
    expected_ids = {s["strategy_id"] for s in STRATEGIES}
    with OUT_JSON.open() as f:
        d = json.load(f)
    found_ids = {r["strategy_id"] for r in d["strategy_results"]}
    assert found_ids == expected_ids, f"Missing strategies: {expected_ids - found_ids}"
    assert len(d["strategy_results"]) == len(STRATEGIES)


# ---------------------------------------------------------------------------
# Test 7: Every strategy has n (sample size)
# ---------------------------------------------------------------------------

def test_every_strategy_has_n():
    with OUT_JSON.open() as f:
        d = json.load(f)
    for strat in d["strategy_results"]:
        assert "n" in strat, f"Strategy {strat['strategy_id']} missing 'n'"
        assert isinstance(strat["n"], int), f"Strategy {strat['strategy_id']} n is not int"
        assert strat["n"] >= 0


# ---------------------------------------------------------------------------
# Test 8: Every strategy has hit rate
# ---------------------------------------------------------------------------

def test_every_strategy_has_hit_rate():
    with OUT_JSON.open() as f:
        d = json.load(f)
    for strat in d["strategy_results"]:
        assert "hit_rate" in strat, f"Strategy {strat['strategy_id']} missing 'hit_rate'"
        if strat["n"] >= 5:
            assert strat["hit_rate"] is not None, f"Strategy {strat['strategy_id']} hit_rate is None with n={strat['n']}"
            assert 0.0 <= strat["hit_rate"] <= 1.0


# ---------------------------------------------------------------------------
# Test 9: Every strategy has AUC or explicit unavailable
# ---------------------------------------------------------------------------

def test_every_strategy_has_auc_or_unavailable():
    with OUT_JSON.open() as f:
        d = json.load(f)
    for strat in d["strategy_results"]:
        assert "auc" in strat, f"Strategy {strat['strategy_id']} missing 'auc' field"
        if strat["n"] >= 20:
            # For reasonable sample size, AUC should be computed
            assert strat["auc"] is not None, (
                f"Strategy {strat['strategy_id']} has n={strat['n']} but auc=None"
            )
            assert 0.0 <= strat["auc"] <= 1.0


# ---------------------------------------------------------------------------
# Test 10: Every strategy has Brier score or explicit unavailable
# ---------------------------------------------------------------------------

def test_every_strategy_has_brier_or_unavailable():
    with OUT_JSON.open() as f:
        d = json.load(f)
    for strat in d["strategy_results"]:
        assert "brier_score" in strat, f"Strategy {strat['strategy_id']} missing 'brier_score'"
        if strat["n"] >= 5:
            assert strat["brier_score"] is not None, (
                f"Strategy {strat['strategy_id']} brier_score is None with n={strat['n']}"
            )
            assert 0.0 <= strat["brier_score"] <= 1.0


# ---------------------------------------------------------------------------
# Test 11: Monthly stability exists for all strategies
# ---------------------------------------------------------------------------

def test_monthly_stability_exists():
    with OUT_JSON.open() as f:
        d = json.load(f)
    for strat in d["strategy_results"]:
        assert "monthly_stability" in strat, f"Strategy {strat['strategy_id']} missing monthly_stability"
        ms = strat["monthly_stability"]
        assert "monthly_breakdown" in ms
        assert "stability_classification" in ms
        assert ms["stability_classification"] in (
            "STABLE", "MODERATE", "UNSTABLE", "INSUFFICIENT_MONTHS"
        )
        if strat["n"] >= 10:
            assert len(ms["monthly_breakdown"]) >= 1


# ---------------------------------------------------------------------------
# Test 12: Final classification is allowed
# ---------------------------------------------------------------------------

def test_final_classification_allowed():
    with OUT_JSON.open() as f:
        d = json.load(f)
    cls = d["final_classification"]
    assert cls in ALLOWED_CLASSIFICATIONS, f"'{cls}' not in allowed set"
    # For these data (2025 full season, 2025 games), we expect a confirmatory or weak result
    assert cls in (
        "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_CONFIRMED",
        "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_WEAK",
        "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_INCONCLUSIVE",
        "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_NEGATIVE",
    ), f"Blocked classification not expected for full 2025 data: {cls}"


# ---------------------------------------------------------------------------
# Test 13: Reports contain no profitability claims
# ---------------------------------------------------------------------------

def test_reports_no_forbidden_phrases():
    for rpath in [
        ROOT / "report/p72a_odds_free_strategy_accuracy_backtest_20260526.md",
        ROOT / "00-BettingPlan/20260526/p72a_odds_free_strategy_accuracy_backtest_20260526.md",
    ]:
        assert rpath.exists(), f"Missing report: {rpath}"
        text = rpath.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in text, f"Forbidden phrase '{phrase}' found in {rpath.name}"


# ---------------------------------------------------------------------------
# Test 14: Report clearly states accuracy is not betting edge
# ---------------------------------------------------------------------------

def test_report_states_accuracy_not_betting_edge():
    rpath = ROOT / "report/p72a_odds_free_strategy_accuracy_backtest_20260526.md"
    assert rpath.exists()
    text = rpath.read_text(encoding="utf-8").lower()
    # Report must contain one of these disclaimers
    assert any(phrase in text for phrase in [
        "does not imply positive ev",
        "not a betting recommendation",
        "accuracy != profitability",
        "accuracy-only",
        "does not constitute a betting",
    ]), "Report must explicitly state that accuracy is not the same as betting edge"


# ---------------------------------------------------------------------------
# Test 15: active_task.md references P72A
# ---------------------------------------------------------------------------

def test_active_task_references_p72a():
    atask = ROOT / "00-Plan/roadmap/active_task.md"
    assert atask.exists()
    content = atask.read_text(encoding="utf-8")
    assert "P72A" in content, "active_task.md does not mention P72A"


# ---------------------------------------------------------------------------
# Bonus: unit tests for metric functions
# ---------------------------------------------------------------------------

def test_compute_hit_rate_basic():
    rows = [
        {"actual_outcome": 1, "predicted_prob": 0.7},
        {"actual_outcome": 0, "predicted_prob": 0.4},
        {"actual_outcome": 1, "predicted_prob": 0.6},
        {"actual_outcome": 1, "predicted_prob": 0.8},
    ]
    hr = compute_hit_rate(rows)
    assert abs(hr - 0.75) < 1e-6


def test_compute_brier_score_basic():
    rows = [
        {"actual_outcome": 1, "predicted_prob": 1.0},
        {"actual_outcome": 0, "predicted_prob": 0.0},
    ]
    bs = compute_brier_score(rows)
    assert abs(bs) < 1e-6  # perfect prediction → 0 brier


def test_compute_auc_basic():
    rows_perfect = [
        {"actual_outcome": 1, "predicted_prob": 0.9},
        {"actual_outcome": 1, "predicted_prob": 0.8},
        {"actual_outcome": 0, "predicted_prob": 0.3},
        {"actual_outcome": 0, "predicted_prob": 0.2},
    ]
    auc = compute_auc(rows_perfect)
    assert abs(auc - 1.0) < 1e-6, f"Perfect separation should give AUC=1.0, got {auc}"

    rows_random = [
        {"actual_outcome": 1, "predicted_prob": 0.5},
        {"actual_outcome": 0, "predicted_prob": 0.5},
        {"actual_outcome": 1, "predicted_prob": 0.5},
        {"actual_outcome": 0, "predicted_prob": 0.5},
    ]
    auc_rand = compute_auc(rows_random)
    assert abs(auc_rand - 0.5) < 0.01, f"Random should give AUC≈0.5, got {auc_rand}"


def test_platt_calibrate_range():
    for prob in [0.3, 0.5, 0.65, 0.8]:
        cal = platt_calibrate(prob)
        assert 0 < cal < 1, f"Platt output out of range: {cal}"


def test_tier_b_hit_rate_elevated():
    """Tier B (n=98) should have hit rate noticeably above 0.50."""
    with OUT_JSON.open() as f:
        d = json.load(f)
    tier_b = next(r for r in d["strategy_results"] if r["strategy_id"] == "S02_TIER_B_DIRECTIONAL")
    assert tier_b["hit_rate"] > 0.55, (
        f"Tier B hit rate {tier_b['hit_rate']} expected > 0.55 for strong FIP delta games"
    )


def test_tier_c_has_good_coverage():
    """Tier C must cover >= 500 games (P43 confirmed 535)."""
    with OUT_JSON.open() as f:
        d = json.load(f)
    tier_c = next(r for r in d["strategy_results"] if r["strategy_id"] == "S01_TIER_C_DIRECTIONAL")
    assert tier_c["n"] >= 500, f"Tier C n={tier_c['n']}, expected >= 500"


def test_strategy_signal_labels_valid():
    """All signal labels must be from the allowed set."""
    valid_labels = {
        "PREDICTIVE_SIGNAL_CONFIRMED",
        "PREDICTIVE_SIGNAL_WEAK",
        "PREDICTIVE_SIGNAL_INCONCLUSIVE",
        "PREDICTIVE_SIGNAL_NEGATIVE",
    }
    with OUT_JSON.open() as f:
        d = json.load(f)
    for strat in d["strategy_results"]:
        assert strat["signal_label"] in valid_labels, (
            f"Invalid signal_label: {strat['signal_label']}"
        )
