"""
wbc_backend/simulation/p18_strategy_policy_grid.py

P18 — Deterministic strategy policy grid search.

Grid over (edge_threshold × max_stake_cap × kelly_fraction × odds_decimal_max)
to find a policy that satisfies:
  - n_bets >= 50
  - max_drawdown_pct <= 25.0%
  - sharpe_ratio >= 0.0
  - roi_ci_low_95 >= -2.0% (i.e. -0.02 fractional)

PnL convention:
  - won bet: pnl = stake_fraction * (decimal_odds - 1)
  - lost bet: pnl = -stake_fraction

PAPER_ONLY: grid search only; no production bets.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

import pandas as pd


# ── Grid parameters ────────────────────────────────────────────────────────────

DEFAULT_EDGE_THRESHOLDS = (0.05, 0.08, 0.10, 0.12, 0.15)
DEFAULT_MAX_STAKE_CAPS = (0.0025, 0.005, 0.01, 0.015, 0.02)
DEFAULT_KELLY_FRACTIONS = (0.10, 0.25, 0.50, 1.00)
DEFAULT_ODDS_DECIMAL_MAXES = (2.50, 3.00, 4.00, 999.0)
DEFAULT_MIN_BETS_FLOOR = 50
BOOTSTRAP_N_ITER = 2000
BOOTSTRAP_SEED = 42


# ── Data contracts ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PolicyCandidate:
    policy_id: str
    edge_threshold: float
    max_stake_cap: float
    kelly_fraction: float
    odds_decimal_max: float
    n_bets: int
    roi_mean: float
    roi_ci_low_95: float
    roi_ci_high_95: float
    max_drawdown_pct: float
    sharpe_ratio: float
    hit_rate: float
    max_consecutive_loss: int
    avg_edge: float
    avg_stake_fraction: float
    total_turnover: float
    policy_pass: bool
    fail_reasons: tuple[str, ...]


@dataclass(frozen=True)
class GridSearchReport:
    candidates: list[PolicyCandidate]
    best_candidate: Optional[PolicyCandidate]
    gate_decision: str  # P18_STRATEGY_POLICY_RISK_REPAIRED | P18_BLOCKED_NO_RISK_ACCEPTABLE_POLICY
    selection_reason: str
    n_candidates_evaluated: int
    n_candidates_passing: int


# ── Internal helpers ───────────────────────────────────────────────────────────

def _make_policy_id(
    edge: float, stake_cap: float, kelly: float, odds_max: float
) -> str:
    return (
        f"e{edge:.4f}_s{stake_cap:.4f}_k{kelly:.2f}_o{odds_max:.2f}"
        .replace(".", "p")
    )


def _filter_and_compute_stakes(
    ledger_df: pd.DataFrame,
    edge_threshold: float,
    max_stake_cap: float,
    kelly_fraction: float,
    odds_decimal_max: float,
) -> pd.DataFrame:
    """
    Filter P15 ledger (capped_kelly rows) by edge >= threshold and
    odds <= max, then recompute stake as Kelly × kelly_fraction capped at max_stake_cap.
    Fully vectorized — no row-wise apply.
    """
    # Filter to capped_kelly policy rows
    if "policy" in ledger_df.columns:
        df = ledger_df[ledger_df["policy"] == "capped_kelly"].copy()
    else:
        df = ledger_df.copy()

    # Compute edge (vectorized)
    if "edge" not in df.columns:
        if "p_model" in df.columns and "p_market" in df.columns:
            df = df.assign(edge=df["p_model"] - df["p_market"])
        else:
            df = df.assign(edge=0.0)

    # Apply edge and odds filters
    df = df[df["edge"] >= edge_threshold]
    if odds_decimal_max < 999.0:
        df = df[df["decimal_odds"] <= odds_decimal_max]

    if df.empty:
        return df.copy()

    # Vectorized Kelly stake computation
    p = df["p_model"].clip(0.0, 1.0)
    b = (df["decimal_odds"] - 1.0).clip(lower=0.0)
    # full Kelly: (p*b - (1-p)) / b
    with_b = b > 0
    raw_kelly = pd.Series(0.0, index=df.index)
    raw_kelly[with_b] = ((p[with_b] * b[with_b] - (1.0 - p[with_b])) / b[with_b]).clip(lower=0.0)
    stake = (raw_kelly * kelly_fraction).clip(upper=max_stake_cap)

    df = df.copy()
    df["stake_fraction"] = stake.values
    df = df[df["stake_fraction"] > 0]

    if "row_idx" in df.columns:
        df = df.sort_values("row_idx").reset_index(drop=True)
    else:
        df = df.reset_index(drop=True)

    return df


def _compute_metrics(df: pd.DataFrame, bootstrap_n_iter: int = BOOTSTRAP_N_ITER) -> dict:
    """Compute risk metrics from a filtered and staked DataFrame."""
    if df.empty:
        return {
            "n_bets": 0,
            "roi_mean": 0.0,
            "roi_ci_low_95": 0.0,
            "roi_ci_high_95": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_ratio": 0.0,
            "hit_rate": 0.0,
            "max_consecutive_loss": 0,
            "avg_edge": 0.0,
            "avg_stake_fraction": 0.0,
            "total_turnover": 0.0,
        }

    # Vectorized PnL
    stake = df["stake_fraction"].to_numpy(dtype=float)
    odds = df["decimal_odds"].to_numpy(dtype=float)
    y = df["y_true"].to_numpy(dtype=int)
    pnl = stake * (odds - 1.0) * y - stake * (1 - y)  # win: stake*(odds-1), loss: -stake
    pnl_list = pnl.tolist()
    n = len(pnl_list)

    # ROI mean
    total_staked = float(stake.sum())
    total_pnl = float(pnl.sum())
    roi_mean = (total_pnl / total_staked * 100) if total_staked > 0 else 0.0

    # Bootstrap CI
    rng = random.Random(BOOTSTRAP_SEED)
    boot_rois: list[float] = []
    for _ in range(bootstrap_n_iter):
        sample = [rng.choice(pnl_list) for _ in range(n)]
        sample_staked = sum(abs(s) for s in sample)
        boot_rois.append(
            (sum(sample) / sample_staked * 100) if sample_staked > 0 else 0.0
        )
    boot_rois.sort()
    ci_low = boot_rois[int(bootstrap_n_iter * 0.025)]
    ci_high = boot_rois[int(bootstrap_n_iter * 0.975)]

    # Sharpe (on per-bet returns)
    mean_pnl = float(pnl.mean())
    std = float(pnl.std(ddof=1)) if n > 1 else 0.0
    sharpe = mean_pnl / std if std > 1e-12 else 0.0

    # Max drawdown (vectorized cumsum)
    equity = 1.0 + pnl.cumsum()
    equity_with_start = [1.0] + equity.tolist()
    max_dd = 0.0
    peak = equity_with_start[0]
    for eq in equity_with_start[1:]:
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
    max_dd_pct = float(max_dd * 100)

    # Hit rate and consecutive losses
    hits = (pnl > 0).sum()
    hit_rate = float(hits) / n if n > 0 else 0.0

    max_streak = 0
    streak = 0
    for p in pnl_list:
        if p < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    # Avg edge
    avg_edge = float(df["edge"].mean()) if "edge" in df.columns else 0.0

    return {
        "n_bets": n,
        "roi_mean": float(roi_mean),
        "roi_ci_low_95": float(ci_low),
        "roi_ci_high_95": float(ci_high),
        "max_drawdown_pct": max_dd_pct,
        "sharpe_ratio": float(sharpe),
        "hit_rate": hit_rate,
        "max_consecutive_loss": int(max_streak),
        "avg_edge": avg_edge,
        "avg_stake_fraction": float(stake.mean()),
        "total_turnover": float(total_staked),
    }


def _evaluate_pass(
    metrics: dict,
    min_bets_floor: int,
    max_drawdown_limit: float,
    sharpe_floor: float,
    ci_low_floor: float = -2.0,  # -2% ROI CI low floor
) -> tuple[bool, tuple[str, ...]]:
    fails: list[str] = []
    if metrics["n_bets"] < min_bets_floor:
        fails.append(f"n_bets={metrics['n_bets']} < floor={min_bets_floor}")
    if metrics["max_drawdown_pct"] > max_drawdown_limit * 100:
        fails.append(
            f"drawdown={metrics['max_drawdown_pct']:.2f}% > {max_drawdown_limit*100:.1f}%"
        )
    if metrics["sharpe_ratio"] < sharpe_floor:
        fails.append(
            f"sharpe={metrics['sharpe_ratio']:.4f} < {sharpe_floor}"
        )
    if metrics["roi_ci_low_95"] < ci_low_floor:
        fails.append(
            f"roi_ci_low_95={metrics['roi_ci_low_95']:.4f}% < {ci_low_floor}%"
        )
    return (len(fails) == 0), tuple(fails)


# ── Public API ─────────────────────────────────────────────────────────────────

def run_policy_grid_search(
    ledger_df: pd.DataFrame,
    edge_thresholds: tuple[float, ...] = DEFAULT_EDGE_THRESHOLDS,
    max_stake_caps: tuple[float, ...] = DEFAULT_MAX_STAKE_CAPS,
    kelly_fractions: tuple[float, ...] = DEFAULT_KELLY_FRACTIONS,
    odds_decimal_maxes: tuple[float, ...] = DEFAULT_ODDS_DECIMAL_MAXES,
    min_bets_floor: int = DEFAULT_MIN_BETS_FLOOR,
    max_drawdown_limit: float = 0.25,
    sharpe_floor: float = 0.0,
    bootstrap_n_iter: int = BOOTSTRAP_N_ITER,
) -> GridSearchReport:
    """
    Run deterministic grid search over all policy parameter combinations.

    Selection rule (among passing candidates):
      1. max_drawdown_pct ascending
      2. sharpe_ratio descending
      3. roi_mean descending
      4. n_bets descending

    Returns GridSearchReport with best_candidate and gate_decision.
    """
    candidates: list[PolicyCandidate] = []

    # Iterate in fixed order for determinism
    for edge in edge_thresholds:
        for stake_cap in max_stake_caps:
            for kelly in kelly_fractions:
                for odds_max in odds_decimal_maxes:
                    policy_id = _make_policy_id(edge, stake_cap, kelly, odds_max)
                    df = _filter_and_compute_stakes(
                        ledger_df, edge, stake_cap, kelly, odds_max
                    )
                    metrics = _compute_metrics(df, bootstrap_n_iter=bootstrap_n_iter)
                    passed, fails = _evaluate_pass(
                        metrics, min_bets_floor, max_drawdown_limit, sharpe_floor
                    )
                    candidates.append(
                        PolicyCandidate(
                            policy_id=policy_id,
                            edge_threshold=edge,
                            max_stake_cap=stake_cap,
                            kelly_fraction=kelly,
                            odds_decimal_max=odds_max,
                            n_bets=metrics["n_bets"],
                            roi_mean=metrics["roi_mean"],
                            roi_ci_low_95=metrics["roi_ci_low_95"],
                            roi_ci_high_95=metrics["roi_ci_high_95"],
                            max_drawdown_pct=metrics["max_drawdown_pct"],
                            sharpe_ratio=metrics["sharpe_ratio"],
                            hit_rate=metrics["hit_rate"],
                            max_consecutive_loss=metrics["max_consecutive_loss"],
                            avg_edge=metrics["avg_edge"],
                            avg_stake_fraction=metrics["avg_stake_fraction"],
                            total_turnover=metrics["total_turnover"],
                            policy_pass=passed,
                            fail_reasons=fails,
                        )
                    )

    # Select best passing candidate
    passing = [c for c in candidates if c.policy_pass]

    if passing:
        passing.sort(
            key=lambda c: (
                c.max_drawdown_pct,
                -c.sharpe_ratio,
                -c.roi_mean,
                -c.n_bets,
            )
        )
        best = passing[0]
        gate = "P18_STRATEGY_POLICY_RISK_REPAIRED"
        reason = (
            f"Selected policy {best.policy_id}: "
            f"drawdown={best.max_drawdown_pct:.2f}% <= 25%, "
            f"sharpe={best.sharpe_ratio:.4f} >= 0, "
            f"n_bets={best.n_bets} >= {min_bets_floor}, "
            f"roi_ci_low_95={best.roi_ci_low_95:.4f}%"
        )
    else:
        best = None
        gate = "P18_BLOCKED_NO_RISK_ACCEPTABLE_POLICY"
        reason = (
            f"No candidate among {len(candidates)} passed all criteria "
            f"(drawdown <= 25%, sharpe >= 0, n_bets >= {min_bets_floor}, "
            f"roi_ci_low_95 >= -2%)"
        )

    return GridSearchReport(
        candidates=candidates,
        best_candidate=best,
        gate_decision=gate,
        selection_reason=reason,
        n_candidates_evaluated=len(candidates),
        n_candidates_passing=len(passing),
    )
