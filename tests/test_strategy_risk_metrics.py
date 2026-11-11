"""
tests/test_strategy_risk_metrics.py

Unit tests for wbc_backend/simulation/strategy_risk_metrics.py

Test cases:
- drawdown math correct on synthetic equity curve
- Sharpe matches reference on synthetic returns
- bootstrap CI deterministic with fixed seed
- summarize_strategy_risk correct on synthetic ledger
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from wbc_backend.simulation.strategy_risk_metrics import (
    StrategyRiskProfile,
    bootstrap_roi_ci,
    compute_max_consecutive_loss,
    compute_max_drawdown,
    compute_sharpe,
    summarize_strategy_risk,
)


# ── compute_max_drawdown ──────────────────────────────────────────────────────

def test_drawdown_zero_on_flat_curve():
    curve = [1.0, 1.0, 1.0, 1.0]
    assert compute_max_drawdown(curve) == 0.0


def test_drawdown_zero_on_strictly_increasing():
    curve = [1.0, 1.1, 1.2, 1.3]
    assert compute_max_drawdown(curve) == 0.0


def test_drawdown_single_dip():
    # Peak 1.2, trough 0.9 → dd = (1.2 - 0.9) / 1.2 = 0.25
    curve = [1.0, 1.2, 0.9, 1.1]
    dd = compute_max_drawdown(curve)
    assert abs(dd - 0.25) < 1e-9


def test_drawdown_two_dips_max_is_larger():
    # First dip: 1.0 → 0.8, dd = 0.2
    # Second dip: 1.2 → 0.6, dd = 0.5
    curve = [1.0, 0.8, 1.2, 0.6]
    dd = compute_max_drawdown(curve)
    assert abs(dd - 0.5) < 1e-9


def test_drawdown_single_point_returns_zero():
    assert compute_max_drawdown([1.0]) == 0.0


def test_drawdown_empty_returns_zero():
    assert compute_max_drawdown([]) == 0.0


def test_drawdown_all_decline():
    # 1.0 → 0.8 → 0.6 → 0.4
    # Peak always 1.0, trough 0.4 → dd = 0.6
    curve = [1.0, 0.8, 0.6, 0.4]
    dd = compute_max_drawdown(curve)
    assert abs(dd - 0.6) < 1e-9


# ── compute_sharpe ────────────────────────────────────────────────────────────

def test_sharpe_zero_on_single_return():
    assert compute_sharpe([0.05]) == 0.0


def test_sharpe_zero_on_constant_returns():
    # mean = 0.05, std = 0 → sharpe = 0
    assert compute_sharpe([0.05, 0.05, 0.05]) == 0.0


def test_sharpe_reference_calculation():
    # returns = [0.1, -0.1, 0.2, 0.0]
    returns = [0.1, -0.1, 0.2, 0.0]
    n = len(returns)
    mean = sum(returns) / n  # 0.05
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(variance)
    expected = mean / std
    assert abs(compute_sharpe(returns) - expected) < 1e-9


def test_sharpe_positive_when_positive_mean():
    # all positive returns
    returns = [0.05, 0.03, 0.04, 0.06]
    assert compute_sharpe(returns) > 0.0


def test_sharpe_negative_when_negative_mean():
    returns = [-0.05, -0.03, -0.04, -0.06]
    assert compute_sharpe(returns) < 0.0


def test_sharpe_empty_returns_zero():
    assert compute_sharpe([]) == 0.0


# ── compute_max_consecutive_loss ──────────────────────────────────────────────

def test_consecutive_loss_no_losses():
    assert compute_max_consecutive_loss([1.0, 2.0, 0.5]) == 0


def test_consecutive_loss_all_losses():
    assert compute_max_consecutive_loss([-1.0, -2.0, -0.5]) == 3


def test_consecutive_loss_alternating():
    pnl = [-1.0, 1.0, -1.0, 1.0]
    assert compute_max_consecutive_loss(pnl) == 1


def test_consecutive_loss_streak_of_3():
    pnl = [1.0, -1.0, -1.0, -1.0, 1.0, -1.0]
    assert compute_max_consecutive_loss(pnl) == 3


def test_consecutive_loss_empty():
    assert compute_max_consecutive_loss([]) == 0


# ── bootstrap_roi_ci ──────────────────────────────────────────────────────────

def test_bootstrap_ci_deterministic():
    pnl = [0.01, -0.02, 0.03, -0.01, 0.02] * 10
    ci1 = bootstrap_roi_ci(pnl, n_iter=200, seed=42)
    ci2 = bootstrap_roi_ci(pnl, n_iter=200, seed=42)
    assert ci1 == ci2


def test_bootstrap_ci_different_seeds_differ():
    pnl = [0.01, -0.02, 0.03, -0.01, 0.02] * 10
    ci1 = bootstrap_roi_ci(pnl, n_iter=200, seed=42)
    ci2 = bootstrap_roi_ci(pnl, n_iter=200, seed=99)
    assert ci1 != ci2


def test_bootstrap_ci_low_less_than_high():
    pnl = [0.01, -0.02, 0.03, -0.01, 0.02] * 5
    lo, hi = bootstrap_roi_ci(pnl, n_iter=500, seed=42)
    assert lo <= hi


def test_bootstrap_ci_single_sample_returns_zeros():
    lo, hi = bootstrap_roi_ci([0.05])
    assert lo == 0.0 and hi == 0.0


def test_bootstrap_ci_empty_returns_zeros():
    lo, hi = bootstrap_roi_ci([])
    assert lo == 0.0 and hi == 0.0


# ── summarize_strategy_risk ───────────────────────────────────────────────────

def _make_ledger(
    n: int,
    y_true: list[int],
    stake: float = 0.02,
    decimal_odds: float = 2.0,
    policy: str = "capped_kelly",
) -> pd.DataFrame:
    return pd.DataFrame({
        "policy": [policy] * n,
        "should_bet": [True] * n,
        "stake_fraction": [stake] * n,
        "decimal_odds": [decimal_odds] * n,
        "y_true": y_true,
        "p_model": [0.6] * n,
        "p_market": [0.5] * n,
    })


def test_summarize_risk_all_wins():
    n = 100
    ledger = _make_ledger(n, [1] * n, stake=0.02, decimal_odds=2.0)
    profile = summarize_strategy_risk(ledger)
    assert profile.n_bets == n
    assert profile.n_winning_bets == n
    assert abs(profile.hit_rate - 1.0) < 1e-9
    assert profile.roi_mean > 0
    assert profile.max_consecutive_loss == 0
    assert isinstance(profile.roi_ci_low_95, float)
    assert profile.roi_ci_low_95 <= profile.roi_ci_high_95


def test_summarize_risk_all_losses():
    n = 100
    ledger = _make_ledger(n, [0] * n, stake=0.02, decimal_odds=2.0)
    profile = summarize_strategy_risk(ledger)
    assert profile.n_bets == n
    assert profile.n_winning_bets == 0
    assert profile.hit_rate == 0.0
    assert profile.roi_mean < 0
    assert profile.max_consecutive_loss == n


def test_summarize_risk_empty_ledger():
    ledger = pd.DataFrame(columns=["policy", "should_bet", "stake_fraction", "decimal_odds", "y_true"])
    profile = summarize_strategy_risk(ledger)
    assert profile.n_bets == 0
    assert profile.roi_mean == 0.0


def test_summarize_risk_returns_frozen_dataclass():
    n = 20
    ledger = _make_ledger(n, [1, 0] * (n // 2), stake=0.02, decimal_odds=2.0)
    profile = summarize_strategy_risk(ledger)
    assert isinstance(profile, StrategyRiskProfile)
    with pytest.raises((AttributeError, TypeError)):
        profile.roi_mean = 99.0  # type: ignore[misc]


def test_summarize_risk_deterministic():
    n = 50
    y = [1, 0, 1, 1, 0] * 10
    ledger = _make_ledger(n, y)
    p1 = summarize_strategy_risk(ledger)
    p2 = summarize_strategy_risk(ledger)
    assert p1.roi_mean == p2.roi_mean
    assert p1.roi_ci_low_95 == p2.roi_ci_low_95
    assert p1.sharpe_ratio == p2.sharpe_ratio
