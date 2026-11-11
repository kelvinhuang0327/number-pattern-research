"""
tests/test_p18_strategy_policy_contract.py

Unit tests for wbc_backend/simulation/p18_strategy_policy_contract.py
"""
from __future__ import annotations

import pytest

from wbc_backend.simulation.p18_strategy_policy_grid import (
    GridSearchReport,
    PolicyCandidate,
)
from wbc_backend.simulation.p18_strategy_policy_contract import (
    GATE_BLOCKED,
    GATE_CONTRACT_VIOLATION,
    GATE_INPUT_MISSING,
    GATE_NON_DETERMINISTIC,
    GATE_REPAIRED,
    StrategyPolicyRecommendation,
    build_recommendation,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_passing_candidate() -> PolicyCandidate:
    return PolicyCandidate(
        policy_id="edge_0.05_stake_0.005_kelly_0.25_odds_3.00",
        edge_threshold=0.05,
        max_stake_cap=0.005,
        kelly_fraction=0.25,
        odds_decimal_max=3.0,
        n_bets=120,
        roi_mean=5.0,
        roi_ci_low_95=-0.5,
        roi_ci_high_95=10.5,
        max_drawdown_pct=18.0,
        sharpe_ratio=0.35,
        hit_rate=0.54,
        max_consecutive_loss=4,
        avg_edge=0.07,
        avg_stake_fraction=0.004,
        total_turnover=0.48,
        policy_pass=True,
        fail_reasons=(),
    )


def _make_grid_report_with_best(best: PolicyCandidate) -> GridSearchReport:
    return GridSearchReport(
        candidates=[best],
        best_candidate=best,
        gate_decision=GATE_REPAIRED,
        selection_reason="Lowest max_drawdown_pct among passing candidates.",
        n_candidates_evaluated=400,
        n_candidates_passing=1,
    )


def _make_grid_report_no_best() -> GridSearchReport:
    return GridSearchReport(
        candidates=[],
        best_candidate=None,
        gate_decision=GATE_BLOCKED,
        selection_reason="No candidate passed all risk criteria.",
        n_candidates_evaluated=400,
        n_candidates_passing=0,
    )


# ── build_recommendation ───────────────────────────────────────────────────────

def test_build_recommendation_repaired():
    candidate = _make_passing_candidate()
    report = _make_grid_report_with_best(candidate)
    rec = build_recommendation(report)
    assert rec.gate_decision == GATE_REPAIRED
    assert rec.selected_policy_id == candidate.policy_id
    assert rec.edge_threshold == candidate.edge_threshold
    assert rec.max_stake_cap == candidate.max_stake_cap
    assert rec.kelly_fraction == candidate.kelly_fraction
    assert rec.odds_decimal_max == candidate.odds_decimal_max
    assert rec.n_bets == candidate.n_bets
    assert rec.roi_mean == candidate.roi_mean
    assert rec.max_drawdown_pct == candidate.max_drawdown_pct
    assert rec.sharpe_ratio == candidate.sharpe_ratio
    assert rec.hit_rate == candidate.hit_rate


def test_build_recommendation_blocked():
    report = _make_grid_report_no_best()
    rec = build_recommendation(report)
    assert rec.gate_decision == GATE_BLOCKED
    assert rec.selected_policy_id is None
    assert rec.edge_threshold is None
    assert rec.max_stake_cap is None
    assert rec.sharpe_ratio is None


def test_build_recommendation_paper_only_enforced():
    report = _make_grid_report_with_best(_make_passing_candidate())
    rec = build_recommendation(report)
    assert rec.paper_only is True
    assert rec.production_ready is False


def test_build_recommendation_blocked_paper_only_enforced():
    report = _make_grid_report_no_best()
    rec = build_recommendation(report)
    assert rec.paper_only is True
    assert rec.production_ready is False


# ── as_dict ────────────────────────────────────────────────────────────────────

def test_as_dict_has_all_keys():
    report = _make_grid_report_with_best(_make_passing_candidate())
    rec = build_recommendation(report)
    d = rec.as_dict()
    required_keys = {
        "selected_policy_id", "edge_threshold", "max_stake_cap",
        "kelly_fraction", "odds_decimal_max", "n_bets",
        "roi_mean", "roi_ci_low_95", "roi_ci_high_95",
        "max_drawdown_pct", "sharpe_ratio", "hit_rate",
        "selection_reason", "gate_decision",
        "paper_only", "production_ready",
    }
    for key in required_keys:
        assert key in d, f"Missing key: {key}"


def test_as_dict_values_match():
    report = _make_grid_report_with_best(_make_passing_candidate())
    rec = build_recommendation(report)
    d = rec.as_dict()
    assert d["paper_only"] is True
    assert d["production_ready"] is False
    assert d["gate_decision"] == GATE_REPAIRED


# ── StrategyPolicyRecommendation invariants ────────────────────────────────────

def test_paper_only_false_raises():
    with pytest.raises(ValueError, match="paper_only"):
        StrategyPolicyRecommendation(
            selected_policy_id="test",
            edge_threshold=0.05,
            max_stake_cap=0.005,
            kelly_fraction=0.25,
            odds_decimal_max=3.0,
            n_bets=100,
            roi_mean=5.0,
            roi_ci_low_95=-0.5,
            roi_ci_high_95=10.0,
            max_drawdown_pct=15.0,
            sharpe_ratio=0.3,
            hit_rate=0.55,
            selection_reason="test",
            gate_decision=GATE_REPAIRED,
            paper_only=False,     # <-- invalid
            production_ready=False,
        )


def test_production_ready_true_raises():
    with pytest.raises(ValueError, match="production_ready"):
        StrategyPolicyRecommendation(
            selected_policy_id="test",
            edge_threshold=0.05,
            max_stake_cap=0.005,
            kelly_fraction=0.25,
            odds_decimal_max=3.0,
            n_bets=100,
            roi_mean=5.0,
            roi_ci_low_95=-0.5,
            roi_ci_high_95=10.0,
            max_drawdown_pct=15.0,
            sharpe_ratio=0.3,
            hit_rate=0.55,
            selection_reason="test",
            gate_decision=GATE_REPAIRED,
            paper_only=True,
            production_ready=True,    # <-- invalid
        )


def test_invalid_gate_raises():
    with pytest.raises(ValueError, match="Unknown gate_decision"):
        StrategyPolicyRecommendation(
            selected_policy_id=None,
            edge_threshold=None,
            max_stake_cap=None,
            kelly_fraction=None,
            odds_decimal_max=None,
            n_bets=None,
            roi_mean=None,
            roi_ci_low_95=None,
            roi_ci_high_95=None,
            max_drawdown_pct=None,
            sharpe_ratio=None,
            hit_rate=None,
            selection_reason="test",
            gate_decision="INVALID_GATE",    # <-- invalid
            paper_only=True,
            production_ready=False,
        )


def test_all_valid_gate_decisions_accepted():
    valid_gates = [
        GATE_REPAIRED, GATE_BLOCKED,
        GATE_INPUT_MISSING, GATE_CONTRACT_VIOLATION, GATE_NON_DETERMINISTIC,
    ]
    for gate in valid_gates:
        rec = StrategyPolicyRecommendation(
            selected_policy_id=None,
            edge_threshold=None,
            max_stake_cap=None,
            kelly_fraction=None,
            odds_decimal_max=None,
            n_bets=None,
            roi_mean=None,
            roi_ci_low_95=None,
            roi_ci_high_95=None,
            max_drawdown_pct=None,
            sharpe_ratio=None,
            hit_rate=None,
            selection_reason="test",
            gate_decision=gate,
            paper_only=True,
            production_ready=False,
        )
        assert rec.gate_decision == gate
