"""
wbc_backend/simulation/strategy_risk_metrics.py

CEO-mandated P16 risk metrics module.

Provides deterministic, audit-ready strategy risk profiling:
  - Max drawdown from equity curve
  - Sharpe ratio from returns series
  - Max consecutive loss count
  - Bootstrap 95% CI on ROI (fixed seed, deterministic)
  - summarize_strategy_risk() → StrategyRiskProfile from ledger DataFrame

PnL convention (consistent with p13_strategy_simulator.py):
  - won bet: pnl = stake_fraction * (decimal_odds - 1)
  - lost bet: pnl = -stake_fraction
  - no-bet row: pnl = 0.0

PAPER_ONLY: This module is for paper simulation only.
No production bets are placed.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Sequence

import pandas as pd


# ── Data contract ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StrategyRiskProfile:
    roi_mean: float
    roi_ci_low_95: float
    roi_ci_high_95: float
    max_drawdown_pct: float
    sharpe_ratio: float
    max_consecutive_loss: int
    n_bets: int
    n_winning_bets: int
    hit_rate: float


# ── Core math functions ───────────────────────────────────────────────────────

def compute_max_drawdown(equity_curve: list[float]) -> float:
    """
    Compute peak-to-trough maximum drawdown from an equity curve.

    Parameters
    ----------
    equity_curve : list[float]
        Cumulative bankroll or equity values (e.g. [1.0, 1.02, 0.98, ...]).

    Returns
    -------
    float
        Maximum drawdown as a fraction (0.0 – 1.0).
        0.0 if no drawdown or fewer than 2 data points.
    """
    if len(equity_curve) < 2:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0
    for v in equity_curve[1:]:
        if v > peak:
            peak = v
        if peak > 0.0:
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
    return float(max_dd)


def compute_sharpe(returns: list[float], rf: float = 0.0) -> float:
    """
    Compute annualised Sharpe ratio from a returns series.

    Parameters
    ----------
    returns : list[float]
        Per-bet net returns (e.g. stake-normalised profits/losses).
    rf : float
        Risk-free rate per period (default 0.0).

    Returns
    -------
    float
        Sharpe ratio. Returns 0.0 if fewer than 2 data points or std == 0.
    """
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    excess = mean - rf
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(variance)
    if std < 1e-12:
        return 0.0
    return float(excess / std)


def compute_max_consecutive_loss(pnl_series: list[float]) -> int:
    """
    Compute the maximum number of consecutive losing bets.

    Parameters
    ----------
    pnl_series : list[float]
        Per-bet PnL values. Negative value = loss.

    Returns
    -------
    int
        Maximum consecutive loss streak.
    """
    max_streak = 0
    current = 0
    for pnl in pnl_series:
        if pnl < 0.0:
            current += 1
            if current > max_streak:
                max_streak = current
        else:
            current = 0
    return max_streak


def bootstrap_roi_ci(
    pnl_series: list[float],
    n_iter: int = 2000,
    seed: int = 42,
) -> tuple[float, float]:
    """
    Bootstrap 95% confidence interval for mean ROI.

    ROI is computed per bootstrap sample as:
        ROI = sum(pnl) / n_samples * 100   (mean pnl * 100)

    Uses fixed seed for determinism.

    Parameters
    ----------
    pnl_series : list[float]
        Per-bet PnL series (unit-stake normalised).
    n_iter : int
        Number of bootstrap iterations. Default 2000.
    seed : int
        Random seed for reproducibility. Default 42.

    Returns
    -------
    tuple[float, float]
        (ci_low_95, ci_high_95) as percentages.
        Returns (0.0, 0.0) if fewer than 2 samples.
    """
    n = len(pnl_series)
    if n < 2:
        return (0.0, 0.0)

    rng = random.Random(seed)
    boot_means: list[float] = []
    for _ in range(n_iter):
        sample = [rng.choice(pnl_series) for _ in range(n)]
        boot_means.append(sum(sample) / n * 100.0)

    boot_means.sort()
    lo_idx = int(math.floor(0.025 * n_iter))
    hi_idx = int(math.ceil(0.975 * n_iter)) - 1
    lo_idx = max(0, lo_idx)
    hi_idx = min(n_iter - 1, hi_idx)
    return (float(boot_means[lo_idx]), float(boot_means[hi_idx]))


# ── Primary summary function ──────────────────────────────────────────────────

def _compute_pnl_series(ledger_df: pd.DataFrame) -> list[float]:
    """
    Extract per-bet PnL from ledger rows where should_bet == True.

    PnL formula:
        win:  stake_fraction * (decimal_odds - 1)
        loss: -stake_fraction
    """
    pnl: list[float] = []
    for _, row in ledger_df.iterrows():
        if not row.get("should_bet", False):
            continue
        stake = float(row["stake_fraction"])
        if stake <= 0.0:
            continue
        dec_odds = float(row["decimal_odds"])
        y = int(row["y_true"])
        if y == 1:
            pnl.append(stake * (dec_odds - 1.0))
        else:
            pnl.append(-stake)
    return pnl


def summarize_strategy_risk(
    ledger_df: pd.DataFrame,
    n_bootstrap: int = 2000,
    bootstrap_seed: int = 42,
) -> StrategyRiskProfile:
    """
    Produce a StrategyRiskProfile from a simulation ledger DataFrame.

    The ledger must have columns:
        should_bet, stake_fraction, decimal_odds, y_true

    Parameters
    ----------
    ledger_df : pd.DataFrame
        Rows for a single policy (e.g., capped_kelly rows only).
    n_bootstrap : int
        Bootstrap iterations. Default 2000.
    bootstrap_seed : int
        Fixed seed. Default 42.

    Returns
    -------
    StrategyRiskProfile
    """
    pnl_series = _compute_pnl_series(ledger_df)
    n_bets = len(pnl_series)

    if n_bets == 0:
        return StrategyRiskProfile(
            roi_mean=0.0,
            roi_ci_low_95=0.0,
            roi_ci_high_95=0.0,
            max_drawdown_pct=0.0,
            sharpe_ratio=0.0,
            max_consecutive_loss=0,
            n_bets=0,
            n_winning_bets=0,
            hit_rate=0.0,
        )

    n_winning = sum(1 for p in pnl_series if p > 0.0)
    hit_rate = float(n_winning / n_bets)
    total_staked = sum(
        float(row["stake_fraction"])
        for _, row in ledger_df.iterrows()
        if row.get("should_bet", False) and float(row["stake_fraction"]) > 0.0
    )
    roi_mean = (sum(pnl_series) / total_staked * 100.0) if total_staked > 0.0 else 0.0

    # Equity curve: start at 1.0, cumsum of unit-bankroll pnl
    equity: list[float] = [1.0]
    running = 1.0
    for p in pnl_series:
        running += p
        equity.append(running)

    max_dd = compute_max_drawdown(equity)
    sharpe = compute_sharpe(pnl_series)
    max_cons_loss = compute_max_consecutive_loss(pnl_series)
    ci_low, ci_high = bootstrap_roi_ci(pnl_series, n_iter=n_bootstrap, seed=bootstrap_seed)

    return StrategyRiskProfile(
        roi_mean=roi_mean,
        roi_ci_low_95=ci_low,
        roi_ci_high_95=ci_high,
        max_drawdown_pct=float(max_dd * 100.0),
        sharpe_ratio=sharpe,
        max_consecutive_loss=max_cons_loss,
        n_bets=n_bets,
        n_winning_bets=n_winning,
        hit_rate=hit_rate,
    )
