"""
wbc_backend/recommendation/p28_performance_variance_analyzer.py

P28 Performance Variance Analyzer.

Computes ROI and hit-rate variance across segments and daily date windows,
and provides a bootstrap 95% confidence interval for aggregate ROI.

Important:
  - ROI CI is NOT proof of edge. It is a research-only stability measure.
  - Bootstrap must be deterministic with a fixed seed.
  - ROI = total_pnl / total_stake (stake-weighted per date/segment).
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from wbc_backend.recommendation.p28_true_date_stability_contract import (
    P28PerformanceVarianceProfile,
)


# ---------------------------------------------------------------------------
# Daily ROI profile
# ---------------------------------------------------------------------------


def compute_daily_roi_profiles(date_results_df: pd.DataFrame) -> List[Dict]:
    """
    Compute per-date ROI and hit_rate metrics.

    Returns a list of dicts with: run_date, roi_units, hit_rate, n_active,
    total_stake_units, total_pnl_units.
    """
    if date_results_df.empty:
        return []

    profiles = []
    for _, row in date_results_df.iterrows():
        stake = float(row.get("total_stake_units", 0) or 0)
        pnl = float(row.get("total_pnl_units", 0) or 0)
        roi = pnl / stake if stake > 0 else 0.0
        profiles.append({
            "run_date": str(row.get("run_date", "")),
            "roi_units": roi,
            "hit_rate": float(row.get("hit_rate", 0) or 0),
            "n_active": int(float(row.get("n_active_paper_entries", 0) or 0)),
            "total_stake_units": stake,
            "total_pnl_units": pnl,
        })
    return profiles


# ---------------------------------------------------------------------------
# Segment ROI profile
# ---------------------------------------------------------------------------


def compute_segment_roi_profiles(segment_results_df: pd.DataFrame) -> List[Dict]:
    """
    Compute per-segment ROI and hit_rate metrics.

    Returns a list of dicts with: segment_index, date_start, date_end,
    roi_units, hit_rate, n_active, total_stake_units, total_pnl_units.
    """
    if segment_results_df.empty:
        return []

    profiles = []
    for _, row in segment_results_df.iterrows():
        stake = float(row.get("total_stake_units", 0) or 0)
        pnl = float(row.get("total_pnl_units", 0) or 0)
        wins = float(row.get("total_settled_win", 0) or 0)
        losses = float(row.get("total_settled_loss", 0) or 0)
        total_decided = wins + losses
        hit_rate = wins / total_decided if total_decided > 0 else 0.0
        roi = pnl / stake if stake > 0 else 0.0
        profiles.append({
            "segment_index": int(float(row.get("segment_index", 0) or 0)),
            "date_start": str(row.get("date_start", "")),
            "date_end": str(row.get("date_end", "")),
            "roi_units": roi,
            "hit_rate": hit_rate,
            "n_active": int(float(row.get("total_active_entries", 0) or 0)),
            "total_stake_units": stake,
            "total_pnl_units": pnl,
        })
    return profiles


# ---------------------------------------------------------------------------
# Variance metrics
# ---------------------------------------------------------------------------


def compute_roi_variance_metrics(profiles: List[Dict]) -> Dict:
    """
    Compute min/max/mean/std of roi_units across profiles.
    Returns dict with keys: min, max, mean, std.
    """
    if not profiles:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0}

    rois = [p["roi_units"] for p in profiles]
    s = pd.Series(rois)
    return {
        "min": float(s.min()),
        "max": float(s.max()),
        "mean": float(s.mean()),
        "std": float(s.std(ddof=1)) if len(s) > 1 else 0.0,
    }


def compute_hit_rate_variance_metrics(profiles: List[Dict]) -> Dict:
    """
    Compute min/max/mean/std of hit_rate across profiles.
    Returns dict with keys: min, max, mean, std.
    """
    if not profiles:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0}

    rates = [p["hit_rate"] for p in profiles]
    s = pd.Series(rates)
    return {
        "min": float(s.min()),
        "max": float(s.max()),
        "mean": float(s.mean()),
        "std": float(s.std(ddof=1)) if len(s) > 1 else 0.0,
    }


# ---------------------------------------------------------------------------
# Bootstrap CI
# ---------------------------------------------------------------------------


def bootstrap_roi_confidence_interval(
    date_results_df: pd.DataFrame,
    n_iter: int = 2000,
    seed: int = 42,
) -> Dict:
    """
    Compute bootstrap 95% confidence interval for aggregate ROI.

    Method: resample daily (pnl, stake) pairs with replacement n_iter times;
    compute aggregate ROI = sum(pnl) / sum(stake) for each resample.
    Returns dict with: ci_low_95, ci_high_95, mean_roi, n_iter, seed.

    Deterministic with fixed seed.
    This CI is for research stability assessment ONLY — not a proof of edge.
    """
    if date_results_df.empty:
        return {
            "ci_low_95": 0.0, "ci_high_95": 0.0,
            "mean_roi": 0.0, "n_iter": n_iter, "seed": seed,
        }

    stakes = date_results_df["total_stake_units"].astype(float).values
    pnls = date_results_df["total_pnl_units"].astype(float).values
    total_stake = stakes.sum()
    if total_stake <= 0:
        return {
            "ci_low_95": 0.0, "ci_high_95": 0.0,
            "mean_roi": 0.0, "n_iter": n_iter, "seed": seed,
        }

    rng = np.random.RandomState(seed)
    n = len(stakes)
    bootstrap_rois = np.empty(n_iter)
    for i in range(n_iter):
        idx = rng.randint(0, n, size=n)
        s = stakes[idx].sum()
        p = pnls[idx].sum()
        bootstrap_rois[i] = p / s if s > 0 else 0.0

    ci_low = float(np.percentile(bootstrap_rois, 2.5))
    ci_high = float(np.percentile(bootstrap_rois, 97.5))
    mean_roi = float(bootstrap_rois.mean())

    return {
        "ci_low_95": ci_low,
        "ci_high_95": ci_high,
        "mean_roi": mean_roi,
        "n_iter": n_iter,
        "seed": seed,
    }


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------


def summarize_performance_variance(
    date_results_df: pd.DataFrame,
    segment_results_df: pd.DataFrame,
    bootstrap_n_iter: int = 2000,
    bootstrap_seed: int = 42,
) -> P28PerformanceVarianceProfile:
    """
    Compute and return a complete P28PerformanceVarianceProfile.
    """
    daily_profiles = compute_daily_roi_profiles(date_results_df)
    segment_profiles = compute_segment_roi_profiles(segment_results_df)

    daily_roi_var = compute_roi_variance_metrics(daily_profiles)
    daily_hr_var = compute_hit_rate_variance_metrics(daily_profiles)
    seg_roi_var = compute_roi_variance_metrics(segment_profiles)
    seg_hr_var = compute_hit_rate_variance_metrics(segment_profiles)

    bootstrap_ci = bootstrap_roi_confidence_interval(
        date_results_df, n_iter=bootstrap_n_iter, seed=bootstrap_seed
    )

    n_pos = sum(1 for p in segment_profiles if p["roi_units"] > 0)
    n_neg = sum(1 for p in segment_profiles if p["roi_units"] <= 0)

    return P28PerformanceVarianceProfile(
        segment_roi_min=seg_roi_var["min"],
        segment_roi_max=seg_roi_var["max"],
        segment_roi_mean=seg_roi_var["mean"],
        segment_roi_std=seg_roi_var["std"],
        segment_hit_rate_min=seg_hr_var["min"],
        segment_hit_rate_max=seg_hr_var["max"],
        segment_hit_rate_std=seg_hr_var["std"],
        daily_roi_min=daily_roi_var["min"],
        daily_roi_max=daily_roi_var["max"],
        daily_roi_mean=daily_roi_var["mean"],
        daily_roi_std=daily_roi_var["std"],
        daily_hit_rate_min=daily_hr_var["min"],
        daily_hit_rate_max=daily_hr_var["max"],
        daily_hit_rate_std=daily_hr_var["std"],
        n_positive_roi_segments=n_pos,
        n_negative_roi_segments=n_neg,
        bootstrap_roi_ci_low_95=bootstrap_ci["ci_low_95"],
        bootstrap_roi_ci_high_95=bootstrap_ci["ci_high_95"],
        paper_only=True,
        production_ready=False,
    )
