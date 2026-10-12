"""
wbc_backend/recommendation/p28_risk_drawdown_analyzer.py

P28 Risk and Drawdown Analyzer.

Builds the daily equity curve from cumulative PnL, computes max drawdown
in units and percentage, and measures losing-streak characteristics.

Risk thresholds:
  - max_drawdown_pct > 25%  → P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT
  - max_consecutive_losing_days >= 7  → flag (high_losing_streak=True, not always blocked)
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from wbc_backend.recommendation.p28_true_date_stability_contract import (
    MAX_DRAWDOWN_PCT_LIMIT,
    HIGH_LOSING_STREAK_DAYS,
    P28RiskProfile,
)


# ---------------------------------------------------------------------------
# Equity curve
# ---------------------------------------------------------------------------


def build_daily_equity_curve(date_results_df: pd.DataFrame) -> pd.Series:
    """
    Build cumulative PnL equity curve sorted by run_date.

    Returns a pandas Series indexed by run_date (str) with cumulative
    total_pnl_units values.
    """
    if date_results_df.empty or "total_pnl_units" not in date_results_df.columns:
        return pd.Series(dtype=float)

    df = date_results_df.copy()
    df["run_date"] = df["run_date"].astype(str)
    df["total_pnl_units"] = df["total_pnl_units"].astype(float)
    df = df.sort_values("run_date").reset_index(drop=True)
    equity = df.set_index("run_date")["total_pnl_units"].cumsum()
    return equity


# ---------------------------------------------------------------------------
# Max drawdown
# ---------------------------------------------------------------------------


def compute_max_drawdown(equity_curve: pd.Series) -> Dict:
    """
    Compute max drawdown from peak as both units and percentage.

    Returns dict with: max_drawdown_units (float), max_drawdown_pct (float),
    drawdown_exceeds_limit (bool).

    max_drawdown_pct = (peak - trough) / abs(peak) if peak != 0 else 0.
    Drawdown is always expressed as a positive value.
    """
    if equity_curve.empty:
        return {
            "max_drawdown_units": 0.0,
            "max_drawdown_pct": 0.0,
            "drawdown_exceeds_limit": False,
        }

    values = equity_curve.values.astype(float)
    running_max = pd.Series(values).cummax().values
    drawdowns_units = running_max - values
    max_dd_units = float(drawdowns_units.max())

    # Compute percentage drawdown relative to running_max at the deepest point
    pct_drawdowns = []
    for dd, peak in zip(drawdowns_units, running_max):
        if peak != 0:
            pct_drawdowns.append(dd / abs(peak) * 100.0)
        else:
            pct_drawdowns.append(0.0)
    max_dd_pct = float(max(pct_drawdowns)) if pct_drawdowns else 0.0

    return {
        "max_drawdown_units": max_dd_units,
        "max_drawdown_pct": max_dd_pct,
        "drawdown_exceeds_limit": max_dd_pct > MAX_DRAWDOWN_PCT_LIMIT,
    }


# ---------------------------------------------------------------------------
# Losing streak
# ---------------------------------------------------------------------------


def compute_max_consecutive_losing_days(date_results_df: pd.DataFrame) -> int:
    """
    Compute the maximum number of consecutive calendar dates with total_pnl_units < 0.

    Zero-pnl days are treated as neutral (not winning, not losing).
    """
    if date_results_df.empty or "total_pnl_units" not in date_results_df.columns:
        return 0

    df = date_results_df.copy()
    df["run_date"] = df["run_date"].astype(str)
    df["total_pnl_units"] = df["total_pnl_units"].astype(float)
    df = df.sort_values("run_date").reset_index(drop=True)

    max_streak = 0
    current_streak = 0
    for pnl in df["total_pnl_units"]:
        if pnl < 0:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0
    return max_streak


# ---------------------------------------------------------------------------
# Loss cluster summary
# ---------------------------------------------------------------------------


def compute_loss_cluster_summary(date_results_df: pd.DataFrame) -> Dict:
    """
    Identify clusters of consecutive losing days.

    Returns dict with:
      - total_losing_days: int
      - total_winning_days: int
      - total_neutral_days: int
      - n_loss_clusters: int (sequences of >=2 consecutive losing days)
      - max_consecutive_losing_days: int
      - high_losing_streak: bool
      - loss_cluster_note: str
    """
    if date_results_df.empty or "total_pnl_units" not in date_results_df.columns:
        return {
            "total_losing_days": 0,
            "total_winning_days": 0,
            "total_neutral_days": 0,
            "n_loss_clusters": 0,
            "max_consecutive_losing_days": 0,
            "high_losing_streak": False,
            "loss_cluster_note": "no data",
        }

    df = date_results_df.copy()
    df["run_date"] = df["run_date"].astype(str)
    df["total_pnl_units"] = df["total_pnl_units"].astype(float)
    df = df.sort_values("run_date").reset_index(drop=True)

    pnls = df["total_pnl_units"].tolist()
    total_losing = sum(1 for p in pnls if p < 0)
    total_winning = sum(1 for p in pnls if p > 0)
    total_neutral = sum(1 for p in pnls if p == 0)

    # Count clusters of >=2 consecutive losing days
    n_clusters = 0
    max_streak = 0
    cur_streak = 0
    for pnl in pnls:
        if pnl < 0:
            cur_streak += 1
        else:
            if cur_streak >= 2:
                n_clusters += 1
            max_streak = max(max_streak, cur_streak)
            cur_streak = 0
    # Final sequence
    if cur_streak >= 2:
        n_clusters += 1
    max_streak = max(max_streak, cur_streak)

    high_streak = max_streak >= HIGH_LOSING_STREAK_DAYS

    note = (
        f"{total_losing} losing days total, {n_loss_clusters_note(n_clusters)} clusters "
        f"of ≥2 consecutive losing days, max streak={max_streak}"
    )

    return {
        "total_losing_days": total_losing,
        "total_winning_days": total_winning,
        "total_neutral_days": total_neutral,
        "n_loss_clusters": n_clusters,
        "max_consecutive_losing_days": max_streak,
        "high_losing_streak": high_streak,
        "loss_cluster_note": note,
    }


def n_loss_clusters_note(n: int) -> str:
    return str(n)


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------


def summarize_risk_profile(
    date_results_df: pd.DataFrame,
) -> P28RiskProfile:
    """
    Compute and return a P28RiskProfile.
    """
    equity = build_daily_equity_curve(date_results_df)
    dd = compute_max_drawdown(equity)
    cluster = compute_loss_cluster_summary(date_results_df)

    return P28RiskProfile(
        max_drawdown_units=dd["max_drawdown_units"],
        max_drawdown_pct=dd["max_drawdown_pct"],
        max_consecutive_losing_days=cluster["max_consecutive_losing_days"],
        total_losing_days=cluster["total_losing_days"],
        total_winning_days=cluster["total_winning_days"],
        total_neutral_days=cluster["total_neutral_days"],
        loss_cluster_summary=cluster["loss_cluster_note"],
        drawdown_exceeds_limit=dd["drawdown_exceeds_limit"],
        high_losing_streak=cluster["high_losing_streak"],
        paper_only=True,
        production_ready=False,
    )
