"""
wbc_backend/recommendation/p29_policy_sensitivity_simulator.py

Simulates what active entry counts would result from loosening policy thresholds.
This is sensitivity analysis ONLY — NOT deployment planning.

All candidates are labeled exploratory_only=True, is_deployment_ready=False.
No P18/P16.6 policy is replaced. No production DB written. paper_only=True.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from wbc_backend.recommendation.p29_density_expansion_contract import (
    P29PolicySensitivityCandidate,
    TARGET_ACTIVE_ENTRIES_DEFAULT,
)

# ---------------------------------------------------------------------------
# Policy grid definition
# ---------------------------------------------------------------------------

DEFAULT_POLICY_GRID: Dict[str, List[Any]] = {
    "edge_threshold": [0.02, 0.03, 0.04, 0.05],
    "odds_decimal_max": [2.50, 3.00, 4.00, 999.0],
    "max_stake_cap": [0.001, 0.0025],
    "kelly_fraction": [0.05, 0.10],
}

_SLICE_FILENAME = "p15_true_date_input.csv"

_GATE_REASON_ELIGIBLE = "P16_6_ELIGIBLE_PAPER_RECOMMENDATION"

# Risk flag thresholds
_HIGH_RISK_ODDS_THRESHOLD = 4.00
_HIGH_RISK_EDGE_THRESHOLD = 0.02
_HIGH_DRAWDOWN_PCT = 50.0


# ---------------------------------------------------------------------------
# Policy ID builder
# ---------------------------------------------------------------------------


def _build_policy_id(
    edge: float,
    odds_max: float,
    stake_cap: float,
    kelly: float,
) -> str:
    def _fmt(v: float) -> str:
        return f"{v:.4f}".replace(".", "p").rstrip("0").rstrip("p") or "0"

    odds_str = "inf" if odds_max >= 999 else _fmt(odds_max)
    return f"e{_fmt(edge)}_s{_fmt(stake_cap)}_k{_fmt(kelly)}_o{odds_str}"


# ---------------------------------------------------------------------------
# Simulate single policy on all slices
# ---------------------------------------------------------------------------


def _simulate_single_policy(
    all_slices_df: pd.DataFrame,
    edge_threshold: float,
    odds_decimal_max: float,
    max_stake_cap: float,
    kelly_fraction: float,
) -> Dict[str, Any]:
    """
    Apply a policy grid configuration to the pre-loaded full slices DataFrame
    and compute resulting active entries, ROI, hit rate, drawdown.

    Rules:
    - A row becomes "active" if edge >= edge_threshold AND odds_decimal <= odds_decimal_max
    - Stake = kelly_fraction * edge, capped at max_stake_cap (paper units)
    - ROI = pnl / stake (only for active rows with stake > 0)
    - Drawdown computed as cumulative PnL drawdown over time
    """
    if all_slices_df.empty:
        return _empty_candidate_result()

    df = all_slices_df.copy()
    df["edge"] = pd.to_numeric(df.get("edge", 0), errors="coerce").fillna(0.0)
    df["odds_decimal"] = pd.to_numeric(df.get("odds_decimal", 0), errors="coerce").fillna(0.0)
    df["y_true"] = pd.to_numeric(df.get("y_true", 0), errors="coerce").fillna(0.0)

    # Apply policy filter
    active_mask = (df["edge"] >= edge_threshold) & (df["odds_decimal"] <= odds_decimal_max)
    active_df = df[active_mask].copy()

    n_active = len(active_df)
    if n_active == 0:
        return _empty_candidate_result()

    # Stake calculation: kelly * edge capped at max_stake_cap
    active_df["sim_stake"] = (kelly_fraction * active_df["edge"]).clip(0, max_stake_cap)
    total_stake = float(active_df["sim_stake"].sum())

    # PnL: win = stake * (odds - 1), loss = -stake
    # Use y_true as outcome: 1 = win, 0 = loss
    active_df["sim_pnl"] = active_df.apply(
        lambda r: r["sim_stake"] * (r["odds_decimal"] - 1.0) if r["y_true"] == 1.0
        else -r["sim_stake"],
        axis=1,
    )

    total_pnl = float(active_df["sim_pnl"].sum())
    roi = (total_pnl / total_stake) if total_stake > 0 else 0.0

    # Hit rate
    n_wins = int((active_df["y_true"] == 1.0).sum())
    hit_rate = n_wins / n_active if n_active > 0 else 0.0

    # Max drawdown on cumulative PnL (sort by slice_date if available)
    if "slice_date" in active_df.columns:
        active_df = active_df.sort_values("slice_date")
    cum_pnl = active_df["sim_pnl"].cumsum()
    rolling_max = cum_pnl.cummax()
    drawdown = rolling_max - cum_pnl
    max_dd = float(drawdown.max())
    peak = float(rolling_max.max())
    max_dd_pct = (max_dd / abs(peak) * 100.0) if peak != 0 else 0.0

    # Gate reason counts for active subset
    gate_counts: Dict[str, int] = {}
    if "gate_reason" in active_df.columns:
        gate_counts = {str(k): int(v) for k, v in active_df["gate_reason"].value_counts().items()}

    return {
        "n_active_entries": n_active,
        "total_stake": total_stake,
        "total_pnl": total_pnl,
        "roi_units": round(roi, 6),
        "hit_rate": round(hit_rate, 6),
        "max_drawdown_pct": round(max_dd_pct, 4),
        "gate_reason_counts": gate_counts,
    }


def _empty_candidate_result() -> Dict[str, Any]:
    return {
        "n_active_entries": 0,
        "total_stake": 0.0,
        "total_pnl": 0.0,
        "roi_units": 0.0,
        "hit_rate": 0.0,
        "max_drawdown_pct": 0.0,
        "gate_reason_counts": {},
    }


def _compute_risk_flags(
    edge_threshold: float,
    odds_decimal_max: float,
    max_drawdown_pct: float,
    n_active: int,
    target: int,
) -> List[str]:
    """Return list of risk flag strings for a candidate."""
    flags: List[str] = []
    if edge_threshold <= _HIGH_RISK_EDGE_THRESHOLD:
        flags.append("LOW_EDGE_THRESHOLD")
    if odds_decimal_max >= _HIGH_RISK_ODDS_THRESHOLD:
        flags.append("HIGH_ODDS_CAP")
    if max_drawdown_pct > _HIGH_DRAWDOWN_PCT:
        flags.append("HIGH_DRAWDOWN")
    if n_active < target:
        flags.append("STILL_BELOW_TARGET")
    return flags


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def simulate_policy_density_on_true_date_slices(
    p25_dir: Path,
    policy_grid: Optional[Dict[str, List[Any]]] = None,
) -> List[P29PolicySensitivityCandidate]:
    """
    Load all P25 true-date slices and simulate each policy combination.
    Returns a list of P29PolicySensitivityCandidate (sorted by n_active_entries desc).
    """
    if policy_grid is None:
        policy_grid = DEFAULT_POLICY_GRID

    slices_dir = p25_dir / "true_date_slices"
    if not slices_dir.exists():
        return []

    # Load all slices once
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
        return []
    all_df = pd.concat(frames, ignore_index=True)

    # Current baseline active count
    current_active = int((all_df.get("gate_reason", pd.Series()) == _GATE_REASON_ELIGIBLE).sum())

    candidates: List[P29PolicySensitivityCandidate] = []

    for edge in policy_grid["edge_threshold"]:
        for odds_max in policy_grid["odds_decimal_max"]:
            for stake_cap in policy_grid["max_stake_cap"]:
                for kelly in policy_grid["kelly_fraction"]:
                    result = _simulate_single_policy(
                        all_df, edge, odds_max, stake_cap, kelly
                    )
                    n_active = result["n_active_entries"]
                    lift = n_active - current_active
                    risk_flags = _compute_risk_flags(
                        edge, odds_max, result["max_drawdown_pct"],
                        n_active, TARGET_ACTIVE_ENTRIES_DEFAULT,
                    )
                    policy_id = _build_policy_id(edge, odds_max, stake_cap, kelly)
                    candidate = P29PolicySensitivityCandidate(
                        policy_id=policy_id,
                        edge_threshold=edge,
                        odds_decimal_max=odds_max,
                        max_stake_cap=stake_cap,
                        kelly_fraction=kelly,
                        n_active_entries=n_active,
                        active_entry_lift_vs_current=lift,
                        estimated_total_stake_units=round(result["total_stake"], 6),
                        hit_rate=result["hit_rate"],
                        roi_units=result["roi_units"],
                        max_drawdown_pct=result["max_drawdown_pct"],
                        gate_reason_counts=json.dumps(result["gate_reason_counts"], sort_keys=True),
                        risk_flags=",".join(risk_flags) if risk_flags else "",
                        is_deployment_ready=False,
                        exploratory_only=True,
                        paper_only=True,
                        production_ready=False,
                    )
                    candidates.append(candidate)

    return sorted(candidates, key=lambda c: c.n_active_entries, reverse=True)


def compute_gate_reason_distribution(
    slice_df: pd.DataFrame,
    policy: Dict[str, Any],
) -> Dict[str, int]:
    """
    Given a slice DataFrame and a policy dict, apply the policy and return
    gate_reason distribution of the resulting active rows.
    """
    if slice_df.empty or "gate_reason" not in slice_df.columns:
        return {}
    edge = float(policy.get("edge_threshold", 0.05))
    odds_max = float(policy.get("odds_decimal_max", 2.50))
    df = slice_df.copy()
    df["edge"] = pd.to_numeric(df.get("edge", 0), errors="coerce").fillna(0.0)
    df["odds_decimal"] = pd.to_numeric(df.get("odds_decimal", 0), errors="coerce").fillna(0.0)
    mask = (df["edge"] >= edge) & (df["odds_decimal"] <= odds_max)
    filtered = df[mask]
    if filtered.empty:
        return {}
    return {str(k): int(v) for k, v in filtered["gate_reason"].value_counts().items()}


def summarize_policy_candidate(
    candidates: List[P29PolicySensitivityCandidate],
) -> Dict[str, Any]:
    """
    Summarize the policy sensitivity results:
    - best candidate by n_active_entries
    - count that reach target
    - baseline vs best lift
    """
    if not candidates:
        return {
            "n_candidates_tested": 0,
            "n_candidates_reach_target": 0,
            "best_candidate_policy_id": None,
            "best_candidate_n_active": 0,
            "best_candidate_risk_flags": "",
        }

    best = candidates[0]  # already sorted desc by n_active_entries
    reach_target = sum(
        1 for c in candidates
        if c.n_active_entries >= TARGET_ACTIVE_ENTRIES_DEFAULT
    )
    return {
        "n_candidates_tested": len(candidates),
        "n_candidates_reach_target": reach_target,
        "best_candidate_policy_id": best.policy_id,
        "best_candidate_n_active": best.n_active_entries,
        "best_candidate_lift_vs_current": best.active_entry_lift_vs_current,
        "best_candidate_risk_flags": best.risk_flags,
        "best_candidate_hit_rate": best.hit_rate,
        "best_candidate_roi_units": best.roi_units,
        "best_candidate_max_drawdown_pct": best.max_drawdown_pct,
    }


def rank_policy_candidates(
    candidates: List[P29PolicySensitivityCandidate],
) -> List[P29PolicySensitivityCandidate]:
    """Return candidates sorted: (reach target, no high-risk flags, most active)."""
    def _sort_key(c: P29PolicySensitivityCandidate):
        reaches_target = c.n_active_entries >= TARGET_ACTIVE_ENTRIES_DEFAULT
        has_high_risk = bool(c.risk_flags)
        return (not reaches_target, has_high_risk, -c.n_active_entries)

    return sorted(candidates, key=_sort_key)
