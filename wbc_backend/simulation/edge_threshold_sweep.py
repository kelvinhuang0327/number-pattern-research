"""
wbc_backend/simulation/edge_threshold_sweep.py

CEO-mandated P16 edge threshold sweep module.

Sweeps a grid of edge thresholds over the simulation ledger and selects the
threshold that maximises Sharpe ratio subject to n_bets >= min_bets_floor.

Key entry point:
    sweep_edge_thresholds(ledger_df, thresholds, min_bets_floor) -> SweepReport

PAPER_ONLY: Paper simulation only. No production bets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import pandas as pd

from wbc_backend.simulation.strategy_risk_metrics import (
    StrategyRiskProfile,
    summarize_strategy_risk,
)

# ── Data contracts ────────────────────────────────────────────────────────────

SWEEP_INSUFFICIENT_SAMPLES = "SWEEP_INSUFFICIENT_SAMPLES"
SWEEP_OK = "SWEEP_OK"


@dataclass
class ThresholdResult:
    threshold: float
    n_eligible_rows: int
    risk_profile: StrategyRiskProfile


@dataclass
class SweepReport:
    per_threshold_rows: list[ThresholdResult]
    recommended_threshold: float | None
    recommended_reason: str
    fallback_threshold: float | None
    sweep_status: str  # SWEEP_OK | SWEEP_INSUFFICIENT_SAMPLES


# ── Sweep logic ───────────────────────────────────────────────────────────────

def _filter_ledger_by_edge(
    ledger_df: pd.DataFrame,
    threshold: float,
) -> pd.DataFrame:
    """
    Return ledger rows for capped_kelly policy where edge >= threshold.

    The ledger stores per-policy rows. For the sweep we use capped_kelly.
    Edge is computed as (p_model - p_market) for JOINED rows; the ledger
    does not carry 'edge' directly, so we compute it from p_model / p_market.

    If 'edge' column is present in the ledger, we use it directly.
    Otherwise we derive: edge = p_model - p_market.
    """
    df = ledger_df.copy()

    # Filter to capped_kelly policy only (the one used for recommendations)
    if "policy" in df.columns:
        df = df[df["policy"] == "capped_kelly"].copy()

    # Compute edge if not present
    if "edge" not in df.columns:
        if "p_model" in df.columns and "p_market" in df.columns:
            df = df.copy()
            df["edge"] = df["p_model"] - df["p_market"]
        else:
            # Cannot compute edge; return empty
            return df.iloc[0:0]

    # Apply threshold filter: must have should_bet=True OR have positive edge
    # We filter rows where the model has sufficient edge; then evaluate risk
    # on those rows treating them as bets (should_bet based on stake_fraction > 0
    # AND edge >= threshold)
    eligible = df[df["edge"] >= threshold].copy()
    # Mark eligible rows as should_bet for risk computation
    eligible = eligible.copy()
    if "should_bet" not in eligible.columns:
        eligible["should_bet"] = True
    else:
        eligible["should_bet"] = eligible["should_bet"] | (eligible["stake_fraction"] > 0)
    # For sweep: treat any row with edge >= threshold as a bet
    eligible["should_bet"] = True

    return eligible


def sweep_edge_thresholds(
    ledger_df: pd.DataFrame,
    thresholds: Sequence[float] = (0.01, 0.02, 0.03, 0.05, 0.08),
    min_bets_floor: int = 50,
    n_bootstrap: int = 2000,
    bootstrap_seed: int = 42,
) -> SweepReport:
    """
    Sweep edge thresholds and select the one maximising Sharpe
    subject to n_bets >= min_bets_floor.

    Parameters
    ----------
    ledger_df : pd.DataFrame
        Full simulation ledger (all policies, all rows).
    thresholds : Sequence[float]
        Edge thresholds to evaluate.
    min_bets_floor : int
        Minimum number of bets required for a threshold to be eligible.
    n_bootstrap : int
        Bootstrap iterations for CI. Default 2000.
    bootstrap_seed : int
        Fixed seed. Default 42.

    Returns
    -------
    SweepReport
    """
    sorted_thresholds = sorted(thresholds)
    per_threshold_rows: list[ThresholdResult] = []

    for thresh in sorted_thresholds:
        filtered = _filter_ledger_by_edge(ledger_df, thresh)
        n_eligible = len(filtered)
        profile = summarize_strategy_risk(
            filtered,
            n_bootstrap=n_bootstrap,
            bootstrap_seed=bootstrap_seed,
        )
        per_threshold_rows.append(ThresholdResult(
            threshold=thresh,
            n_eligible_rows=n_eligible,
            risk_profile=profile,
        ))

    # Select recommended: max Sharpe subject to n_bets >= min_bets_floor
    eligible_results = [
        r for r in per_threshold_rows
        if r.risk_profile.n_bets >= min_bets_floor
    ]

    if not eligible_results:
        # Fallback: use lowest threshold regardless of floor
        fallback = per_threshold_rows[0] if per_threshold_rows else None
        return SweepReport(
            per_threshold_rows=per_threshold_rows,
            recommended_threshold=None,
            recommended_reason=SWEEP_INSUFFICIENT_SAMPLES,
            fallback_threshold=fallback.threshold if fallback else None,
            sweep_status=SWEEP_INSUFFICIENT_SAMPLES,
        )

    # Sort by Sharpe descending, then by threshold ascending (tiebreak)
    eligible_results.sort(key=lambda r: (-r.risk_profile.sharpe_ratio, r.threshold))
    best = eligible_results[0]

    # Fallback: second-best or lowest threshold with enough bets
    fallback_candidates = [r for r in eligible_results if r.threshold != best.threshold]
    fallback = fallback_candidates[0] if fallback_candidates else per_threshold_rows[0]

    reason = (
        f"threshold={best.threshold:.4f} maximises Sharpe={best.risk_profile.sharpe_ratio:.4f} "
        f"with n_bets={best.risk_profile.n_bets} >= floor={min_bets_floor}"
    )

    return SweepReport(
        per_threshold_rows=per_threshold_rows,
        recommended_threshold=best.threshold,
        recommended_reason=reason,
        fallback_threshold=fallback.threshold,
        sweep_status=SWEEP_OK,
    )
