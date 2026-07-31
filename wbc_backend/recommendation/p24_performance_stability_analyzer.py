"""
wbc_backend/recommendation/p24_performance_stability_analyzer.py

P24 — Performance Stability Analyzer.

Loads P23 date_replay_results.csv and computes per-date performance profiles
plus variance metrics to detect duplicate-source replay via uniform performance.

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from wbc_backend.recommendation.p24_backfill_stability_contract import (
    STABILITY_ACCEPTABLE,
    STABILITY_DUPLICATE_SOURCE_SUSPECTED,
    STABILITY_INSUFFICIENT_VARIANCE,
    P24DatePerformanceProfile,
)

# Tolerance for "all identical" check
_FLOAT_EQ_TOL = 1e-12


def load_p23_date_results(path: str) -> pd.DataFrame:
    """Load date_replay_results.csv produced by P23 aggregator.

    Raises FileNotFoundError if path does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"P23 date results not found: {path}")
    df = pd.read_csv(p)
    return df


def compute_per_date_performance_profiles(
    date_results_df: pd.DataFrame,
    source_hash_map: Optional[Dict[str, str]] = None,
    game_id_set_hash_map: Optional[Dict[str, str]] = None,
    game_date_range_map: Optional[Dict[str, str]] = None,
    run_date_matches_game_date_map: Optional[Dict[str, bool]] = None,
) -> List[P24DatePerformanceProfile]:
    """Build per-date performance profiles from P23 results DataFrame.

    source_hash_map: {run_date: content_hash_excl_run_date}
    game_id_set_hash_map: {run_date: game_id_set_hash}
    game_date_range_map: {run_date: "min_date:max_date"}
    run_date_matches_game_date_map: {run_date: bool}
    """
    if source_hash_map is None:
        source_hash_map = {}
    if game_id_set_hash_map is None:
        game_id_set_hash_map = {}
    if game_date_range_map is None:
        game_date_range_map = {}
    if run_date_matches_game_date_map is None:
        run_date_matches_game_date_map = {}

    profiles = []
    for _, row in date_results_df.iterrows():
        run_date = str(row.get("run_date", ""))
        profiles.append(
            P24DatePerformanceProfile(
                run_date=run_date,
                n_active_entries=int(row.get("n_active_paper_entries", 0)),
                n_settled_win=int(row.get("n_settled_win", 0)),
                n_settled_loss=int(row.get("n_settled_loss", 0)),
                n_unsettled=int(row.get("n_unsettled", 0)),
                total_stake_units=float(row.get("total_stake_units", 0.0)),
                total_pnl_units=float(row.get("total_pnl_units", 0.0)),
                roi_units=float(row.get("roi_units", 0.0)),
                hit_rate=float(row.get("hit_rate", 0.0)),
                game_id_coverage=float(row.get("game_id_coverage", 0.0)),
                source_hash_content=source_hash_map.get(run_date, ""),
                game_id_set_hash=game_id_set_hash_map.get(run_date, ""),
                game_date_range_str=game_date_range_map.get(run_date, "UNKNOWN"),
                run_date_matches_game_date=run_date_matches_game_date_map.get(
                    run_date, False
                ),
            )
        )
    return profiles


def compute_weighted_aggregate_metrics(
    profiles: List[P24DatePerformanceProfile],
) -> Dict:
    """Compute aggregate ROI and hit rate using weighted totals."""
    total_stake = sum(p.total_stake_units for p in profiles)
    total_pnl = sum(p.total_pnl_units for p in profiles)
    total_win = sum(p.n_settled_win for p in profiles)
    total_loss = sum(p.n_settled_loss for p in profiles)

    agg_roi = total_pnl / total_stake if total_stake > 0 else 0.0
    agg_hit_rate = (
        total_win / (total_win + total_loss)
        if (total_win + total_loss) > 0
        else 0.0
    )
    return {
        "total_stake_units": total_stake,
        "total_pnl_units": total_pnl,
        "aggregate_roi_units": agg_roi,
        "aggregate_hit_rate": agg_hit_rate,
    }


def _std(values: List[float]) -> float:
    """Population std dev."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    return math.sqrt(variance)


def compute_variance_metrics(
    profiles: List[P24DatePerformanceProfile],
) -> Dict:
    """Compute std/min/max for ROI, hit_rate, and active entries."""
    if not profiles:
        return {
            "roi_std_by_date": 0.0,
            "roi_min_by_date": 0.0,
            "roi_max_by_date": 0.0,
            "hit_rate_std_by_date": 0.0,
            "hit_rate_min_by_date": 0.0,
            "hit_rate_max_by_date": 0.0,
            "active_entry_std_by_date": 0.0,
            "active_entry_min_by_date": 0,
            "active_entry_max_by_date": 0,
        }

    rois = [p.roi_units for p in profiles]
    hit_rates = [p.hit_rate for p in profiles]
    active = [float(p.n_active_entries) for p in profiles]

    return {
        "roi_std_by_date": _std(rois),
        "roi_min_by_date": min(rois),
        "roi_max_by_date": max(rois),
        "hit_rate_std_by_date": _std(hit_rates),
        "hit_rate_min_by_date": min(hit_rates),
        "hit_rate_max_by_date": max(hit_rates),
        "active_entry_std_by_date": _std(active),
        "active_entry_min_by_date": int(min(active)),
        "active_entry_max_by_date": int(max(active)),
    }


def detect_too_uniform_performance(
    profiles: List[P24DatePerformanceProfile],
) -> Tuple[bool, str]:
    """Return (is_suspicious, reason) if performance metrics are too uniform.

    Suspicious indicators:
    - All dates have identical ROI
    - All dates have identical hit_rate
    - All dates have identical active entry count
    - All dates share same content hash
    - game_date does not match run_date for any date
    """
    if len(profiles) < 2:
        return False, ""

    reasons = []

    rois = [p.roi_units for p in profiles]
    if max(rois) - min(rois) < _FLOAT_EQ_TOL:
        reasons.append("all dates have identical ROI")

    hit_rates = [p.hit_rate for p in profiles]
    if max(hit_rates) - min(hit_rates) < _FLOAT_EQ_TOL:
        reasons.append("all dates have identical hit_rate")

    active = [p.n_active_entries for p in profiles]
    if max(active) == min(active):
        reasons.append("all dates have identical active entry count")

    hashes = [p.source_hash_content for p in profiles if p.source_hash_content]
    if hashes and len(set(hashes)) == 1:
        reasons.append("all dates share identical source content hash")

    mismatches = [p for p in profiles if not p.run_date_matches_game_date]
    if mismatches:
        reasons.append(
            f"{len(mismatches)}/{len(profiles)} dates have game_date != run_date"
        )

    is_suspicious = len(reasons) > 0
    return is_suspicious, "; ".join(reasons)


def summarize_performance_stability(
    profiles: List[P24DatePerformanceProfile],
) -> Dict:
    """Return dict with aggregate + variance + uniformity detection."""
    aggregate = compute_weighted_aggregate_metrics(profiles)
    variance = compute_variance_metrics(profiles)
    is_suspicious, reason = detect_too_uniform_performance(profiles)

    if is_suspicious:
        stability_flag = STABILITY_INSUFFICIENT_VARIANCE
    else:
        stability_flag = STABILITY_ACCEPTABLE

    return {
        **aggregate,
        **variance,
        "n_profiles": len(profiles),
        "is_performance_suspicious": is_suspicious,
        "suspicion_reason": reason,
        "performance_stability_flag": stability_flag,
    }
