"""
wbc_backend/recommendation/p29_density_diagnosis_analyzer.py

Analyzes why current active entry density is low by inspecting P25 true-date
slices and P27 date results. Answers: what is blocking entries from becoming
active recommendations?

Research only. paper_only=True. production_ready=False.
No look-ahead leakage.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from wbc_backend.recommendation.p29_density_expansion_contract import (
    P29DensityDiagnosis,
    TARGET_ACTIVE_ENTRIES_DEFAULT,
)

# ---------------------------------------------------------------------------
# Gate reason classification
# ---------------------------------------------------------------------------

_GATE_REASON_EDGE = "P16_6_BLOCKED_EDGE_BELOW_P18_THRESHOLD"
_GATE_REASON_ODDS = "P16_6_BLOCKED_ODDS_ABOVE_POLICY_MAX"
_GATE_REASON_ELIGIBLE = "P16_6_ELIGIBLE_PAPER_RECOMMENDATION"

_SLICE_FILENAME = "p15_true_date_input.csv"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_p27_date_results(path: Path) -> pd.DataFrame:
    """Load P27 date_results.csv."""
    df = pd.read_csv(path)
    for col in ("n_active_paper_entries", "total_pnl_units", "total_stake_units", "roi_units"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def load_p25_true_date_slices(p25_dir: Path) -> pd.DataFrame:
    """
    Load all per-date true-date slices from the P25 true_date_slices/ sub-directory.
    Returns a concatenated DataFrame of all slice rows.
    Raises FileNotFoundError if the slices directory is absent.
    """
    slices_dir = p25_dir / "true_date_slices"
    if not slices_dir.exists():
        raise FileNotFoundError(f"P25 slices directory not found: {slices_dir}")

    frames: List[pd.DataFrame] = []
    for date_dir in sorted(slices_dir.iterdir()):
        if not date_dir.is_dir():
            continue
        csv_file = date_dir / _SLICE_FILENAME
        if csv_file.exists():
            df = pd.read_csv(csv_file)
            df["slice_date"] = date_dir.name
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    full = pd.concat(frames, ignore_index=True)
    for col in ("paper_stake_units", "edge", "odds_decimal", "pnl_units"):
        if col in full.columns:
            full[col] = pd.to_numeric(full[col], errors="coerce").fillna(0.0)
    return full


# ---------------------------------------------------------------------------
# Density computations
# ---------------------------------------------------------------------------


def compute_current_density(date_results_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Compute daily active entry density stats from P27 date_results.csv.
    Returns a dict with per-day min/max/mean/std and total.
    """
    if date_results_df.empty:
        return {
            "total_active_entries": 0,
            "n_days": 0,
            "active_per_day_min": 0.0,
            "active_per_day_max": 0.0,
            "active_per_day_mean": 0.0,
            "active_per_day_std": 0.0,
        }
    n_active = date_results_df["n_active_paper_entries"]
    return {
        "total_active_entries": int(n_active.sum()),
        "n_days": len(date_results_df),
        "active_per_day_min": float(n_active.min()),
        "active_per_day_max": float(n_active.max()),
        "active_per_day_mean": float(n_active.mean()),
        "active_per_day_std": float(n_active.std(ddof=0)),
    }


def compute_available_row_coverage(p25_dir: Path) -> Dict[str, Any]:
    """
    Compute total available rows across all P25 slices and their gate reason breakdown.
    Returns row counts by gate_reason plus odds/edge stats.
    """
    slices_dir = p25_dir / "true_date_slices"
    if not slices_dir.exists():
        return {
            "total_source_rows": 0,
            "n_active_eligible": 0,
            "n_blocked_edge": 0,
            "n_blocked_odds": 0,
            "n_blocked_unknown": 0,
            "odds_min": None,
            "odds_max": None,
            "edge_min": None,
            "edge_max": None,
        }

    frames: List[pd.DataFrame] = []
    for date_dir in sorted(slices_dir.iterdir()):
        if not date_dir.is_dir():
            continue
        csv_file = date_dir / _SLICE_FILENAME
        if csv_file.exists():
            frames.append(pd.read_csv(csv_file))

    if not frames:
        return {"total_source_rows": 0, "n_active_eligible": 0,
                "n_blocked_edge": 0, "n_blocked_odds": 0, "n_blocked_unknown": 0,
                "odds_min": None, "odds_max": None, "edge_min": None, "edge_max": None}

    full = pd.concat(frames, ignore_index=True)
    for col in ("odds_decimal", "edge"):
        if col in full.columns:
            full[col] = pd.to_numeric(full[col], errors="coerce")

    gr = full.get("gate_reason", pd.Series(dtype=str))
    return {
        "total_source_rows": len(full),
        "n_active_eligible": int((gr == _GATE_REASON_ELIGIBLE).sum()),
        "n_blocked_edge": int((gr == _GATE_REASON_EDGE).sum()),
        "n_blocked_odds": int((gr == _GATE_REASON_ODDS).sum()),
        "n_blocked_unknown": int(~gr.isin(
            {_GATE_REASON_ELIGIBLE, _GATE_REASON_EDGE, _GATE_REASON_ODDS}
        ).sum()),
        "odds_min": float(full["odds_decimal"].min()) if "odds_decimal" in full.columns else None,
        "odds_max": float(full["odds_decimal"].max()) if "odds_decimal" in full.columns else None,
        "edge_min": float(full["edge"].min()) if "edge" in full.columns else None,
        "edge_max": float(full["edge"].max()) if "edge" in full.columns else None,
    }


def diagnose_density_gap(
    current_active_entries: int,
    target_active_entries: int = TARGET_ACTIVE_ENTRIES_DEFAULT,
) -> Dict[str, Any]:
    """
    Compute density gap and required lift.
    Returns dict with gap, required_lift_pct, feasibility_note.
    """
    gap = max(0, target_active_entries - current_active_entries)
    lift_pct = (gap / current_active_entries * 100.0) if current_active_entries > 0 else float("inf")
    return {
        "density_gap": gap,
        "required_lift_pct": round(lift_pct, 1),
        "feasibility_note": (
            "FEASIBLE: minor loosening may suffice" if lift_pct < 100
            else "REQUIRES_SIGNIFICANT_EXPANSION: policy loosening or additional sources needed"
        ),
    }


def identify_zero_active_dates(date_results_df: pd.DataFrame) -> List[str]:
    """Return sorted list of dates with zero active entries."""
    if date_results_df.empty or "n_active_paper_entries" not in date_results_df.columns:
        return []
    mask = date_results_df["n_active_paper_entries"] == 0
    col = "run_date" if "run_date" in date_results_df.columns else date_results_df.columns[0]
    return sorted(date_results_df.loc[mask, col].astype(str).tolist())


def compute_gate_reason_distribution(slice_df: pd.DataFrame) -> Dict[str, int]:
    """Return a dict of gate_reason → count from a slice DataFrame."""
    if slice_df.empty or "gate_reason" not in slice_df.columns:
        return {}
    return {str(k): int(v) for k, v in slice_df["gate_reason"].value_counts().items()}


def _determine_primary_blocker(
    n_blocked_edge: int,
    n_blocked_odds: int,
    total_source_rows: int,
) -> str:
    if total_source_rows == 0:
        return "no_source_rows"
    if n_blocked_edge >= n_blocked_odds and n_blocked_edge > 0:
        return "edge_threshold"
    if n_blocked_odds > n_blocked_edge and n_blocked_odds > 0:
        return "odds_cap"
    return "unknown"


def summarize_density_diagnosis(
    date_results_df: pd.DataFrame,
    p25_dir: Path,
    target_active_entries: int = TARGET_ACTIVE_ENTRIES_DEFAULT,
) -> P29DensityDiagnosis:
    """
    Combine density metrics and row coverage into a P29DensityDiagnosis.
    """
    density = compute_current_density(date_results_df)
    coverage = compute_available_row_coverage(p25_dir)
    gap_info = diagnose_density_gap(density["total_active_entries"], target_active_entries)
    zero_dates = identify_zero_active_dates(date_results_df)

    # Sparse dates = dates with 1 or 2 active entries
    if not date_results_df.empty and "n_active_paper_entries" in date_results_df.columns:
        sparse_count = int(
            ((date_results_df["n_active_paper_entries"] > 0)
             & (date_results_df["n_active_paper_entries"] <= 2)).sum()
        )
    else:
        sparse_count = 0

    n_active = density["total_active_entries"]
    total_rows = coverage["total_source_rows"]
    conversion_rate = (n_active / total_rows) if total_rows > 0 else 0.0

    n_days = density["n_days"] or 1
    target_per_day = round(target_active_entries / n_days, 2)

    primary_blocker = _determine_primary_blocker(
        coverage["n_blocked_edge"],
        coverage["n_blocked_odds"],
        total_rows,
    )

    note = (
        f"Of {total_rows} total source rows, {n_active} are active ({conversion_rate:.1%}). "
        f"Primary blocker: {primary_blocker}. "
        f"Edge-blocked: {coverage['n_blocked_edge']}, "
        f"Odds-blocked: {coverage['n_blocked_odds']}. "
        f"Gap of {gap_info['density_gap']} entries needed to reach target {target_active_entries}."
    )

    return P29DensityDiagnosis(
        current_active_entries=n_active,
        target_active_entries=target_active_entries,
        density_gap=gap_info["density_gap"],
        current_active_per_day=round(density["active_per_day_mean"], 4),
        target_active_per_day=target_per_day,
        total_source_rows=total_rows,
        active_conversion_rate=round(conversion_rate, 4),
        n_blocked_edge=coverage["n_blocked_edge"],
        n_blocked_odds=coverage["n_blocked_odds"],
        n_blocked_unknown=coverage["n_blocked_unknown"],
        n_dates_zero_active=len(zero_dates),
        n_dates_sparse_active=sparse_count,
        primary_blocker=primary_blocker,
        diagnosis_note=note,
        paper_only=True,
        production_ready=False,
    )
