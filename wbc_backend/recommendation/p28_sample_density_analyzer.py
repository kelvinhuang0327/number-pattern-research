"""
wbc_backend/recommendation/p28_sample_density_analyzer.py

P28 Sample Density Analyzer.

Analyzes the distribution of active PAPER entries across dates and segments
in the P27 backfill output to assess whether sufficient data exists for
meaningful statistical analysis.

Rules:
  - A date with 0 active entries is sparse.
  - A segment with fewer than 50 active entries is sparse.
  - The full backfill fails sample-size advisory if total_active_entries < min_sample_size.
  - Sample-size blocking is a RESEARCH READINESS signal, not an engineering failure.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from wbc_backend.recommendation.p28_true_date_stability_contract import (
    P28SampleDensityProfile,
)

# Thresholds
_SPARSE_ACTIVE_PER_DAY: int = 1          # < 1 active entry → sparse date
_SPARSE_ACTIVE_PER_SEGMENT: int = 50     # < 50 active entries → sparse segment


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_p27_date_results(path: Path) -> pd.DataFrame:
    """
    Load the P27 date_results.csv into a DataFrame.

    Expected columns include: run_date, n_active_paper_entries, n_settled_win,
    n_settled_loss, roi_units, hit_rate, total_stake_units, total_pnl_units.
    """
    df = pd.read_csv(path, dtype=str)
    # Coerce numeric columns
    numeric_cols = [
        "n_active_paper_entries", "n_settled_win", "n_settled_loss",
        "n_unsettled", "total_stake_units", "total_pnl_units", "roi_units",
        "hit_rate", "segment_index",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    # Ensure run_date is string
    if "run_date" in df.columns:
        df["run_date"] = df["run_date"].astype(str)
    return df


def load_p27_segment_results(path: Path) -> pd.DataFrame:
    """
    Load the P27 segment_results.csv into a DataFrame.

    Expected columns: segment_index, date_start, date_end, p26_gate, blocked,
    returncode, total_active_entries, total_settled_win, total_settled_loss,
    total_unsettled, total_stake_units, total_pnl_units.
    """
    df = pd.read_csv(path, dtype=str)
    numeric_cols = [
        "segment_index", "total_active_entries", "total_settled_win",
        "total_settled_loss", "total_unsettled", "total_stake_units", "total_pnl_units",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "blocked" in df.columns:
        df["blocked"] = df["blocked"].astype(str).str.lower().isin(["true", "1"])
    return df


# ---------------------------------------------------------------------------
# Core density functions
# ---------------------------------------------------------------------------


def compute_daily_sample_density(date_results_df: pd.DataFrame) -> Dict:
    """
    Compute per-day active entry statistics.

    Returns a dict with: min, max, mean, std, and the sorted list of per-day counts.
    """
    col = "n_active_paper_entries"
    if col not in date_results_df.columns or date_results_df.empty:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0, "per_day": []}

    counts = date_results_df[col].astype(float).tolist()
    s = pd.Series(counts)
    return {
        "min": float(s.min()),
        "max": float(s.max()),
        "mean": float(s.mean()),
        "std": float(s.std(ddof=1)) if len(s) > 1 else 0.0,
        "per_day": counts,
    }


def compute_segment_sample_density(segment_results_df: pd.DataFrame) -> Dict:
    """
    Compute per-segment active entry statistics.

    Returns a dict with: min, max, mean, std, and the sorted list of per-segment counts.
    """
    col = "total_active_entries"
    if col not in segment_results_df.columns or segment_results_df.empty:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0, "per_segment": []}

    counts = segment_results_df[col].astype(float).tolist()
    s = pd.Series(counts)
    return {
        "min": float(s.min()),
        "max": float(s.max()),
        "mean": float(s.mean()),
        "std": float(s.std(ddof=1)) if len(s) > 1 else 0.0,
        "per_segment": counts,
    }


def identify_sparse_dates(
    date_results_df: pd.DataFrame,
    min_active_per_day: int = _SPARSE_ACTIVE_PER_DAY,
) -> List[str]:
    """
    Return sorted list of run_date strings where n_active_paper_entries < min_active_per_day.

    A date with 0 active entries is considered sparse.
    """
    col = "n_active_paper_entries"
    date_col = "run_date"
    if col not in date_results_df.columns or date_col not in date_results_df.columns:
        return []

    mask = date_results_df[col].astype(float) < min_active_per_day
    sparse = date_results_df.loc[mask, date_col].astype(str).tolist()
    return sorted(sparse)


def identify_sparse_segments(
    segment_results_df: pd.DataFrame,
    min_active_per_segment: int = _SPARSE_ACTIVE_PER_SEGMENT,
) -> List[str]:
    """
    Return sorted list of 'seg{index}_{start}_{end}' labels where
    total_active_entries < min_active_per_segment.
    """
    col = "total_active_entries"
    if col not in segment_results_df.columns or segment_results_df.empty:
        return []

    mask = segment_results_df[col].astype(float) < min_active_per_segment
    sparse_rows = segment_results_df[mask]

    labels = []
    for _, row in sparse_rows.iterrows():
        idx = int(row.get("segment_index", 0))
        start = str(row.get("date_start", ""))
        end = str(row.get("date_end", ""))
        labels.append(f"seg{idx}_{start}_{end}")
    return sorted(labels)


def summarize_sample_density(
    date_results_df: pd.DataFrame,
    segment_results_df: pd.DataFrame,
    n_dates_total: int,
    n_dates_ready: int,
    n_dates_blocked: int,
    min_sample_size: int = 1500,
) -> P28SampleDensityProfile:
    """
    Build a P28SampleDensityProfile from the loaded DataFrames.
    """
    daily = compute_daily_sample_density(date_results_df)
    sparse_dates = identify_sparse_dates(date_results_df)
    sparse_segments = identify_sparse_segments(segment_results_df)

    total_active = int(
        date_results_df["n_active_paper_entries"].astype(float).sum()
        if "n_active_paper_entries" in date_results_df.columns and not date_results_df.empty
        else 0
    )

    return P28SampleDensityProfile(
        n_dates_total=n_dates_total,
        n_dates_ready=n_dates_ready,
        n_dates_blocked=n_dates_blocked,
        n_dates_sparse=len(sparse_dates),
        n_segments=len(segment_results_df) if not segment_results_df.empty else 0,
        n_segments_sparse=len(sparse_segments),
        total_active_entries=total_active,
        min_sample_size_advisory=min_sample_size,
        sample_size_pass=(total_active >= min_sample_size),
        daily_active_min=daily["min"],
        daily_active_max=daily["max"],
        daily_active_mean=daily["mean"],
        daily_active_std=daily["std"],
        sparse_date_list=tuple(sparse_dates),
        sparse_segment_list=tuple(sparse_segments),
        paper_only=True,
        production_ready=False,
    )
