"""
tests/test_p16_recommendation_gate.py

Unit tests for wbc_backend/recommendation/p16_recommendation_gate.py

Test cases:
- invalid probability / invalid odds / zero BSS blocked
- edge below selected threshold blocked
- paper_only=False / production_ready=True ALWAYS blocked
- drawdown > limit → P16_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT
- sharpe < floor → P16_BLOCKED_SHARPE_BELOW_FLOOR
- sweep INSUFFICIENT → P16_BLOCKED_SWEEP_INSUFFICIENT_SAMPLES
- passed rows carry correct gate_decision
- failed rows have stake 0
- passed rows have stake > 0
"""
from __future__ import annotations

import pytest

from wbc_backend.recommendation.p16_recommendation_gate import (
    BLOCKED_DRAWDOWN,
    BLOCKED_EDGE_BELOW,
    BLOCKED_INVALID_ODDS,
    BLOCKED_INVALID_PROB,
    BLOCKED_NEGATIVE_BSS,
    BLOCKED_NOT_PAPER_ONLY,
    BLOCKED_ODDS_NOT_JOINED,
    BLOCKED_PRODUCTION,
    BLOCKED_SHARPE,
    BLOCKED_SWEEP_INSUFFICIENT,
    ELIGIBLE,
    GateResult,
    apply_gate,
    compute_paper_stake,
)
from wbc_backend.recommendation.p16_recommendation_input_adapter import P16InputRow
from wbc_backend.simulation.strategy_risk_metrics import StrategyRiskProfile


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _good_profile(
    max_drawdown_pct: float = 5.0,
    sharpe_ratio: float = 0.5,
) -> StrategyRiskProfile:
    return StrategyRiskProfile(
        roi_mean=5.0,
        roi_ci_low_95=-1.0,
        roi_ci_high_95=11.0,
        max_drawdown_pct=max_drawdown_pct,
        sharpe_ratio=sharpe_ratio,
        max_consecutive_loss=3,
        n_bets=200,
        n_winning_bets=110,
        hit_rate=0.55,
    )


def _good_row(
    paper_only: bool = True,
    production_ready: bool = False,
    odds_join_status: str = "JOINED",
    p_model: float = 0.62,
    p_market: float = 0.55,
    edge: float = 0.07,
    odds_decimal: float = 1.82,
    source_bss_oof: float = 0.008253,
) -> P16InputRow:
    return P16InputRow(
        game_id="test_game",
        date="2025-05-08",
        p_model=p_model,
        p_market=p_market,
        edge=edge,
        odds_decimal=odds_decimal,
        odds_join_status=odds_join_status,
        y_true=1,
        source_model="p13_walk_forward_logistic",
        source_bss_oof=source_bss_oof,
        odds_join_coverage=0.9987,
        paper_only=paper_only,
        production_ready=production_ready,
        eligible=True,
        ineligibility_reason=None,
    )


# ── Sweep insufficient ────────────────────────────────────────────────────────

def test_sweep_insufficient_blocks_all():
    row = _good_row()
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.03,
        risk_profile=_good_profile(),
        sweep_status="SWEEP_INSUFFICIENT_SAMPLES",
    )
    assert result.passed is False
    assert result.reason_code == BLOCKED_SWEEP_INSUFFICIENT


# ── Production / paper invariants ─────────────────────────────────────────────

def test_production_ready_true_always_blocked():
    row = _good_row(production_ready=True)
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.03,
        risk_profile=_good_profile(),
        sweep_status="SWEEP_OK",
    )
    assert result.passed is False
    assert result.reason_code == BLOCKED_PRODUCTION


def test_paper_only_false_always_blocked():
    row = _good_row(paper_only=False)
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.03,
        risk_profile=_good_profile(),
        sweep_status="SWEEP_OK",
    )
    assert result.passed is False
    assert result.reason_code == BLOCKED_NOT_PAPER_ONLY


# ── BSS check ─────────────────────────────────────────────────────────────────

def test_zero_bss_blocked():
    row = _good_row(source_bss_oof=0.0)
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.03,
        risk_profile=_good_profile(),
        sweep_status="SWEEP_OK",
    )
    assert result.passed is False
    assert result.reason_code == BLOCKED_NEGATIVE_BSS


def test_negative_bss_blocked():
    row = _good_row(source_bss_oof=-0.01)
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.03,
        risk_profile=_good_profile(),
        sweep_status="SWEEP_OK",
    )
    assert result.passed is False
    assert result.reason_code == BLOCKED_NEGATIVE_BSS


# ── Odds join status ──────────────────────────────────────────────────────────

def test_missing_join_status_blocked():
    row = _good_row(odds_join_status="MISSING")
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.03,
        risk_profile=_good_profile(),
        sweep_status="SWEEP_OK",
    )
    assert result.passed is False
    assert result.reason_code == BLOCKED_ODDS_NOT_JOINED


# ── Probability validity ──────────────────────────────────────────────────────

def test_invalid_p_model_blocked():
    row = _good_row(p_model=1.5)
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.03,
        risk_profile=_good_profile(),
        sweep_status="SWEEP_OK",
    )
    assert result.passed is False
    assert result.reason_code == BLOCKED_INVALID_PROB


def test_none_p_market_blocked():
    row = _good_row(p_market=None)  # type: ignore[arg-type]
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.03,
        risk_profile=_good_profile(),
        sweep_status="SWEEP_OK",
    )
    assert result.passed is False
    assert result.reason_code == BLOCKED_INVALID_PROB


# ── Odds validity ─────────────────────────────────────────────────────────────

def test_invalid_odds_blocked():
    row = _good_row(odds_decimal=0.8)
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.03,
        risk_profile=_good_profile(),
        sweep_status="SWEEP_OK",
    )
    assert result.passed is False
    assert result.reason_code == BLOCKED_INVALID_ODDS


def test_none_odds_blocked():
    row = _good_row(odds_decimal=None)  # type: ignore[arg-type]
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.03,
        risk_profile=_good_profile(),
        sweep_status="SWEEP_OK",
    )
    assert result.passed is False
    assert result.reason_code == BLOCKED_INVALID_ODDS


# ── Edge threshold ────────────────────────────────────────────────────────────

def test_edge_below_threshold_blocked():
    row = _good_row(edge=0.02)
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.05,
        risk_profile=_good_profile(),
        sweep_status="SWEEP_OK",
    )
    assert result.passed is False
    assert result.reason_code == BLOCKED_EDGE_BELOW


def test_edge_exactly_at_threshold_passes():
    row = _good_row(edge=0.05)
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.05,
        risk_profile=_good_profile(),
        sweep_status="SWEEP_OK",
    )
    assert result.passed is True
    assert result.reason_code == ELIGIBLE


# ── Drawdown / Sharpe ─────────────────────────────────────────────────────────

def test_drawdown_exceeds_limit_blocked():
    profile = _good_profile(max_drawdown_pct=30.0)  # 30% > 25% limit
    row = _good_row(edge=0.07)
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.05,
        risk_profile=profile,
        sweep_status="SWEEP_OK",
        max_drawdown_limit=0.25,
    )
    assert result.passed is False
    assert result.reason_code == BLOCKED_DRAWDOWN


def test_drawdown_at_limit_passes():
    profile = _good_profile(max_drawdown_pct=25.0)  # exactly 25%
    row = _good_row(edge=0.07)
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.05,
        risk_profile=profile,
        sweep_status="SWEEP_OK",
        max_drawdown_limit=0.25,
    )
    assert result.passed is True


def test_sharpe_below_floor_blocked():
    profile = _good_profile(sharpe_ratio=-0.1)
    row = _good_row(edge=0.07)
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.05,
        risk_profile=profile,
        sweep_status="SWEEP_OK",
        sharpe_floor=0.0,
    )
    assert result.passed is False
    assert result.reason_code == BLOCKED_SHARPE


def test_sharpe_at_floor_passes():
    profile = _good_profile(sharpe_ratio=0.0)
    row = _good_row(edge=0.07)
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.05,
        risk_profile=profile,
        sweep_status="SWEEP_OK",
        sharpe_floor=0.0,
    )
    assert result.passed is True


# ── Eligible path ─────────────────────────────────────────────────────────────

def test_good_row_passes():
    row = _good_row()
    result = apply_gate(
        row=row,
        selected_edge_threshold=0.05,
        risk_profile=_good_profile(),
        sweep_status="SWEEP_OK",
    )
    assert result.passed is True
    assert result.reason_code == ELIGIBLE


# ── Stake rules ───────────────────────────────────────────────────────────────

def test_failed_gate_stake_zero():
    row = _good_row(edge=0.02)  # below threshold
    gate = apply_gate(
        row=row,
        selected_edge_threshold=0.05,
        risk_profile=_good_profile(),
        sweep_status="SWEEP_OK",
    )
    stake = compute_paper_stake(row, gate, _good_profile())
    assert stake == 0.0


def test_passed_gate_stake_positive():
    row = _good_row(edge=0.07)
    gate = apply_gate(
        row=row,
        selected_edge_threshold=0.05,
        risk_profile=_good_profile(),
        sweep_status="SWEEP_OK",
    )
    stake = compute_paper_stake(row, gate, _good_profile())
    assert stake > 0.0
    assert stake <= 0.02  # capped at 2%


def test_passed_gate_stake_capped_at_002():
    # Very high kelly → must be capped at 0.02
    row = _good_row(edge=0.40, p_model=0.9, odds_decimal=10.0)
    gate = GateResult(decision=ELIGIBLE, reason_code=ELIGIBLE, passed=True)
    stake = compute_paper_stake(row, gate, _good_profile(), max_stake_cap=0.02)
    assert stake <= 0.02
