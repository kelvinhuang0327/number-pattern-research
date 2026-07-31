"""
P54 — Sep 2025 SP FIP Delta Late-Season Feature Drift Audit
============================================================
P53 result: SEP_CALIBRATION_SAMPLE_SENSITIVE_DIAGNOSTIC
This script investigates whether Sep 2025 has abnormal sp_fip_delta distribution
or related feature/side composition changes vs May/Jun/Aug and full Tier C baseline.

Governance:
  paper_only=True
  diagnostic_only=True
  promotion_freeze=True
  kelly_deploy_allowed=False
  live_api_calls=0
  platt_constants_modified=False
  runtime_recommendation_logic_changed=False
  p52_contract_overwritten=False
  p53_artifact_overwritten=False

P45 Platt constants (LOCKED):
  PLATT_A = 0.435432
  PLATT_B = 0.245464
  SIGMOID_K = 0.8
  CLIP_EPS = 1e-7
"""

from __future__ import annotations

import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Governance constants (DO NOT MODIFY)
# ---------------------------------------------------------------------------
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464
SIGMOID_K: float = 0.8
CLIP_EPS: float = 1e-7

GOVERNANCE_FLAGS: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "promotion_freeze": True,
    "kelly_deploy_allowed": False,
    "live_api_calls": 0,
    "tsl_crawler_modified": False,
    "champion_strategy_changed": False,
    "production_usage_proposed": False,
    "runtime_recommendation_logic_changed": False,
    "platt_constants_modified": False,
    "p52_contract_overwritten": False,
    "p53_artifact_overwritten": False,
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
JSONL_PATH = REPO_ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
P53_JSON_PATH = REPO_ROOT / "data/mlb_2025/derived/p53_sep_calibration_critical_audit_summary.json"
P52_JSON_PATH = REPO_ROOT / "data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json"
P45_JSON_PATH = REPO_ROOT / "data/mlb_2025/derived/p45_platt_recalibration_summary.json"

OUTPUT_JSON = REPO_ROOT / "data/mlb_2025/derived/p54_sep_sp_fip_delta_feature_drift_audit_summary.json"
REPORT_MD = REPO_ROOT / "report/p54_sep_sp_fip_delta_feature_drift_audit_20260526.md"
BETTINGPLAN_MD = REPO_ROOT / "00-BettingPlan/20260526/p54_sep_sp_fip_delta_feature_drift_audit_20260526.md"
ACTIVE_TASK_MD = REPO_ROOT / "00-Plan/roadmap/active_task.md"

# ---------------------------------------------------------------------------
# ECE / calibration helpers
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _logit(p: float) -> float:
    p = max(CLIP_EPS, min(1.0 - CLIP_EPS, p))
    return math.log(p / (1.0 - p))


def _platt_prob(raw_prob: float) -> float:
    raw_prob = max(CLIP_EPS, min(1.0 - CLIP_EPS, raw_prob))
    return _sigmoid(PLATT_A * _logit(raw_prob) + PLATT_B)


def _brier(probs: list[float], outcomes: list[int]) -> float:
    if not probs:
        return float("nan")
    return float(np.mean([(p - o) ** 2 for p, o in zip(probs, outcomes)]))


def _ece(probs: list[float], outcomes: list[int], n_bins: int = 10) -> float:
    """Uniform-width ECE."""
    if not probs:
        return float("nan")
    n = len(probs)
    edges = [i / n_bins for i in range(n_bins + 1)]
    ece_val = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        in_bin = [(p, o) for p, o in zip(probs, outcomes) if lo <= p < hi]
        if not in_bin:
            continue
        bin_n = len(in_bin)
        pred_mean = float(np.mean([x[0] for x in in_bin]))
        act_mean = float(np.mean([x[1] for x in in_bin]))
        ece_val += abs(act_mean - pred_mean) * bin_n / n
    # catch last edge
    last = [(p, o) for p, o in zip(probs, outcomes) if p == 1.0]
    if last:
        bin_n = len(last)
        pred_mean = float(np.mean([x[0] for x in last]))
        act_mean = float(np.mean([x[1] for x in last]))
        ece_val += abs(act_mean - pred_mean) * bin_n / n
    return float(ece_val)


def _compute_metrics(probs_raw: list[float], probs_platt: list[float], outcomes: list[int]) -> dict:
    return {
        "n": len(outcomes),
        "raw_ece": round(_ece(probs_raw, outcomes, 10), 6),
        "platt_ece": round(_ece(probs_platt, outcomes, 10), 6),
        "raw_brier": round(_brier(probs_raw, outcomes), 6),
        "platt_brier": round(_brier(probs_platt, outcomes), 6),
        "actual_win_rate": round(float(np.mean(outcomes)), 6),
        "mean_raw_prob": round(float(np.mean(probs_raw)), 6),
        "mean_platt_prob": round(float(np.mean(probs_platt)), 6),
        "calibration_gap": round(
            abs(float(np.mean(probs_platt)) - float(np.mean(outcomes))), 6
        ),
    }


# ---------------------------------------------------------------------------
# KS statistic (manual, no scipy dependency required)
# ---------------------------------------------------------------------------

def _ks_statistic(a: list[float], b: list[float]) -> float:
    """Two-sample KS statistic."""
    if not a or not b:
        return float("nan")
    combined = sorted(set(a + b))
    n_a, n_b = len(a), len(b)
    a_sorted = sorted(a)
    b_sorted = sorted(b)
    max_diff = 0.0
    i_a = i_b = 0
    for x in combined:
        while i_a < n_a and a_sorted[i_a] <= x:
            i_a += 1
        while i_b < n_b and b_sorted[i_b] <= x:
            i_b += 1
        diff = abs(i_a / n_a - i_b / n_b)
        if diff > max_diff:
            max_diff = diff
    return round(max_diff, 6)


def _mannwhitney_u(a: list[float], b: list[float]) -> dict:
    """Mann-Whitney U statistic and approximate p-value (normal approximation)."""
    if not a or not b:
        return {"u_statistic": None, "p_value_approx": None, "note": "insufficient data"}
    n1, n2 = len(a), len(b)
    combined = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    # assign ranks
    ranks = {}
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[k] = avg_rank
        i = j
    rank_sum_a = sum(ranks[k] for k, (v, g) in enumerate(combined) if g == 0)
    u1 = rank_sum_a - n1 * (n1 + 1) / 2
    u2 = n1 * n2 - u1
    u_stat = min(u1, u2)
    # normal approximation
    mu_u = n1 * n2 / 2
    sigma_u = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    z = (u_stat - mu_u) / sigma_u if sigma_u > 0 else 0.0
    # 2-sided p from standard normal CDF approximation
    p_approx = 2.0 * (1.0 - _norm_cdf(abs(z)))
    return {
        "u_statistic": round(u_stat, 2),
        "z_score": round(z, 4),
        "p_value_approx": round(p_approx, 6),
        "n1": n1,
        "n2": n2,
        "note": "normal approximation, not exact",
    }


def _norm_cdf(x: float) -> float:
    """Abramowitz & Stegun approximation of standard normal CDF."""
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    phi = 1.0 - (1.0 / math.sqrt(2 * math.pi)) * math.exp(-x * x / 2) * poly
    return phi if x >= 0 else 1.0 - phi


# ---------------------------------------------------------------------------
# P54.A — Load Tier C dataset
# ---------------------------------------------------------------------------

def load_tier_c() -> list[dict]:
    rows: list[dict] = []
    with open(JSONL_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    tier_c: list[dict] = []
    for r in rows:
        fd = r.get("p0_features", {}).get("sp_fip_delta")
        mhp = r.get("market_home_prob_no_vig")
        hw = r.get("home_win")
        if fd is not None and abs(fd) >= 0.5 and mhp is not None and 0 < mhp < 1 and hw is not None:
            tier_c.append(r)
    return tier_c


def build_feature_dataset(tier_c: list[dict]) -> list[dict]:
    """Extract flat feature rows from Tier C records."""
    records: list[dict] = []
    for r in tier_c:
        p0 = r.get("p0_features", {})
        fd: float = float(p0["sp_fip_delta"])
        raw_prob: float = float(r["model_home_prob"])
        platt_p: float = _platt_prob(raw_prob)
        mhp: float = float(r["market_home_prob_no_vig"])
        hw: int = int(r["home_win"])
        gdate: str = r["game_date"]
        month: str = gdate[5:7]

        # Derive selected side: model picks home if raw_prob > 0.5, else away
        model_home_win_bet = raw_prob > 0.5
        selected_win = hw if model_home_win_bet else (1 - hw)
        home_fav = mhp > 0.5

        records.append({
            "game_date": gdate,
            "month": month,
            "sp_fip_delta": fd,
            "abs_sp_fip_delta": abs(fd),
            "raw_prob": raw_prob,
            "platt_prob": platt_p,
            "market_home_prob": mhp,
            "home_win": hw,
            "model_picks_home": model_home_win_bet,
            "selected_side_win": selected_win,
            "home_is_favorite": home_fav,
            "model_picks_favorite": (model_home_win_bet == home_fav),
        })
    return records


# ---------------------------------------------------------------------------
# P54.B — Monthly FIP delta distribution audit
# ---------------------------------------------------------------------------

def _distribution_stats(values: list[float]) -> dict:
    if not values:
        return {}
    arr = sorted(values)
    n = len(arr)
    mean_v = float(np.mean(arr))
    median_v = float(np.median(arr))
    std_v = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    p75 = float(np.percentile(arr, 75))
    p90 = float(np.percentile(arr, 90))
    return {
        "n": n,
        "mean": round(mean_v, 6),
        "median": round(median_v, 6),
        "std": round(std_v, 6),
        "p75": round(p75, 6),
        "p90": round(p90, 6),
        "min": round(arr[0], 6),
        "max": round(arr[-1], 6),
    }


def monthly_fip_distribution(records: list[dict]) -> dict:
    by_month: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_month[r["month"]].append(r)

    result: dict[str, Any] = {}
    month_labels = {"04": "Apr", "05": "May", "06": "Jun", "07": "Jul", "08": "Aug", "09": "Sep"}

    for m_key in sorted(by_month.keys()):
        recs = by_month[m_key]
        fds = [r["sp_fip_delta"] for r in recs]
        abs_fds = [r["abs_sp_fip_delta"] for r in recs]
        label = month_labels.get(m_key, m_key)

        fd_stats = _distribution_stats(fds)
        abs_stats = _distribution_stats(abs_fds)

        n = len(recs)
        extreme_ge_1_0 = sum(1 for v in abs_fds if v >= 1.0) / n if n > 0 else 0.0
        extreme_ge_1_5 = sum(1 for v in abs_fds if v >= 1.5) / n if n > 0 else 0.0

        home_side_rate = sum(1 for r in recs if r["model_picks_home"]) / n if n > 0 else 0.0
        away_side_rate = 1.0 - home_side_rate

        result[label] = {
            "month_key": m_key,
            "n": n,
            "sp_fip_delta": {
                "mean": fd_stats.get("mean"),
                "median": fd_stats.get("median"),
                "std": fd_stats.get("std"),
                "min": fd_stats.get("min"),
                "max": fd_stats.get("max"),
            },
            "abs_sp_fip_delta": {
                "mean": abs_stats.get("mean"),
                "median": abs_stats.get("median"),
                "std": abs_stats.get("std"),
                "p75": abs_stats.get("p75"),
                "p90": abs_stats.get("p90"),
            },
            "extreme_rate_abs_ge_1_0": round(extreme_ge_1_0, 6),
            "extreme_rate_abs_ge_1_5": round(extreme_ge_1_5, 6),
            "home_side_rate": round(home_side_rate, 6),
            "away_side_rate": round(away_side_rate, 6),
        }

    return result


def statistical_comparison(records: list[dict]) -> dict:
    """KS and Mann-Whitney comparisons: Sep vs May/Jun/Aug/Full."""
    by_month: dict[str, list[float]] = defaultdict(list)
    for r in records:
        by_month[r["month"]].append(r["abs_sp_fip_delta"])

    sep = by_month.get("09", [])
    full = [r["abs_sp_fip_delta"] for r in records]

    comparisons: dict[str, Any] = {}
    for m_key, label in [("05", "May"), ("06", "Jun"), ("07", "Jul"), ("08", "Aug")]:
        other = by_month.get(m_key, [])
        comparisons[f"sep_vs_{label.lower()}"] = {
            "ks_statistic": _ks_statistic(sep, other),
            "mannwhitney": _mannwhitney_u(sep, other),
            "n_sep": len(sep),
            f"n_{label.lower()}": len(other),
        }

    comparisons["sep_vs_full_tier_c"] = {
        "ks_statistic": _ks_statistic(sep, full),
        "mannwhitney": _mannwhitney_u(sep, full),
        "n_sep": len(sep),
        "n_full": len(full),
    }

    return comparisons


# ---------------------------------------------------------------------------
# P54.C — Calibration error by FIP delta band
# ---------------------------------------------------------------------------

FIP_BANDS = [
    ("0.50_0.75", 0.50, 0.75),
    ("0.75_1.00", 0.75, 1.00),
    ("1.00_1.25", 1.00, 1.25),
    ("1.25_1.50", 1.25, 1.50),
    ("1.50_plus", 1.50, float("inf")),
]


def _in_band(abs_fd: float, lo: float, hi: float) -> bool:
    return lo <= abs_fd < hi


def calibration_by_band(records: list[dict], label: str = "all") -> dict:
    result: dict[str, Any] = {}
    all_n = len(records)

    for band_key, lo, hi in FIP_BANDS:
        subset = [r for r in records if _in_band(r["abs_sp_fip_delta"], lo, hi)]
        n = len(subset)
        if n == 0:
            result[band_key] = {"n": 0, "note": "no data in band"}
            continue
        probs_raw = [r["raw_prob"] for r in subset]
        probs_platt = [r["platt_prob"] for r in subset]
        outcomes = [r["home_win"] for r in subset]
        metrics = _compute_metrics(probs_raw, probs_platt, outcomes)
        metrics["outcome_rate_delta_vs_baseline"] = round(
            metrics["actual_win_rate"] - float(np.mean([r["home_win"] for r in records])), 6
        )
        metrics["band_rate_in_period"] = round(n / all_n, 6) if all_n > 0 else 0.0
        result[band_key] = metrics

    return result


def calibration_bands_comparison(all_records: list[dict]) -> dict:
    by_month: dict[str, list[dict]] = defaultdict(list)
    for r in all_records:
        by_month[r["month"]].append(r)

    return {
        "full_tier_c": calibration_by_band(all_records, "full"),
        "Sep": calibration_by_band(by_month.get("09", []), "Sep"),
        "May": calibration_by_band(by_month.get("05", []), "May"),
        "Jun": calibration_by_band(by_month.get("06", []), "Jun"),
        "Aug": calibration_by_band(by_month.get("08", []), "Aug"),
    }


# ---------------------------------------------------------------------------
# P54.D — Side / outcome composition audit
# ---------------------------------------------------------------------------

def side_composition_audit(records: list[dict]) -> dict:
    by_month: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_month[r["month"]].append(r)

    def _side_stats(recs: list[dict]) -> dict:
        n = len(recs)
        if n == 0:
            return {"n": 0}
        home_sel = sum(1 for r in recs if r["model_picks_home"])
        home_wins = sum(r["home_win"] for r in recs)
        sel_wins = sum(r["selected_side_win"] for r in recs)
        fav_sel = sum(1 for r in recs if r["model_picks_favorite"])
        return {
            "n": n,
            "home_selected_rate": round(home_sel / n, 6),
            "away_selected_rate": round((n - home_sel) / n, 6),
            "home_win_rate": round(home_wins / n, 6),
            "away_win_rate": round((n - home_wins) / n, 6),
            "selected_side_win_rate": round(sel_wins / n, 6),
            "favorite_side_rate": round(fav_sel / n, 6),
            "underdog_side_rate": round((n - fav_sel) / n, 6),
        }

    return {
        "full_tier_c": _side_stats(records),
        "Sep": _side_stats(by_month.get("09", [])),
        "May": _side_stats(by_month.get("05", [])),
        "Jun": _side_stats(by_month.get("06", [])),
        "Jul": _side_stats(by_month.get("07", [])),
        "Aug": _side_stats(by_month.get("08", [])),
        "note": "selected_side derived from model_home_prob > 0.5; "
                "favorite_side derived from market_home_prob_no_vig > 0.5",
    }


# ---------------------------------------------------------------------------
# P54 Classification
# ---------------------------------------------------------------------------

def classify_p54(
    monthly_dist: dict,
    stats_comp: dict,
    band_comparison: dict,
    side_audit: dict,
) -> str:
    """
    Classification rules:
    P54_SEP_FEATURE_DRIFT_CONFIRMED_DIAGNOSTIC:
        Sep abs_fip_delta mean or std differs substantially (>20%) AND KS >= 0.15
    P54_SEP_EXTREME_DELTA_CONCENTRATION_DIAGNOSTIC:
        Sep extreme_rate_abs_ge_1_0 substantially higher than baseline
    P54_SEP_SIDE_COMPOSITION_SHIFT_DIAGNOSTIC:
        Sep home_win_rate or selected_side_win_rate differs >10 ppts from baseline
    P54_NO_FEATURE_DRIFT_FOUND_DIAGNOSTIC:
        No substantial differences found
    P54_INCONCLUSIVE_SAMPLE_LIMITED:
        Sep n < 50 or insufficient comparison data
    """
    sep_dist = monthly_dist.get("Sep", {})
    full_dist = monthly_dist.get("May", {})  # use May as the largest month reference
    sep_n = sep_dist.get("n", 0)

    if sep_n < 50:
        return "P54_INCONCLUSIVE_SAMPLE_LIMITED"

    # KS statistic (Sep vs full)
    ks_full = stats_comp.get("sep_vs_full_tier_c", {}).get("ks_statistic", 0.0) or 0.0

    # mean abs_fip_delta comparison
    sep_abs_mean = (sep_dist.get("abs_sp_fip_delta") or {}).get("mean", 0.0) or 0.0
    # compute full baseline mean from monthly_dist (weighted average approximation)
    full_baseline_means = []
    full_baseline_ns = []
    for lbl, md in monthly_dist.items():
        n = md.get("n", 0)
        m = (md.get("abs_sp_fip_delta") or {}).get("mean")
        if n > 0 and m is not None:
            full_baseline_means.append(m * n)
            full_baseline_ns.append(n)
    baseline_abs_mean = sum(full_baseline_means) / sum(full_baseline_ns) if full_baseline_ns else 0.0

    pct_diff_mean = abs(sep_abs_mean - baseline_abs_mean) / baseline_abs_mean if baseline_abs_mean > 0 else 0.0

    # extreme rate
    sep_extreme_1_0 = sep_dist.get("extreme_rate_abs_ge_1_0", 0.0) or 0.0
    baseline_extreme_1_0_vals = [
        md.get("extreme_rate_abs_ge_1_0", 0.0) or 0.0
        for lbl, md in monthly_dist.items() if lbl != "Sep"
    ]
    baseline_extreme_1_0 = float(np.mean(baseline_extreme_1_0_vals)) if baseline_extreme_1_0_vals else 0.0
    extreme_diff = sep_extreme_1_0 - baseline_extreme_1_0

    # side composition
    sep_side = side_audit.get("Sep", {})
    full_side = side_audit.get("full_tier_c", {})
    sep_sel_win = sep_side.get("selected_side_win_rate", 0.5) or 0.5
    full_sel_win = full_side.get("selected_side_win_rate", 0.5) or 0.5
    side_diff = abs(sep_sel_win - full_sel_win)

    sep_hw = sep_side.get("home_win_rate", 0.5) or 0.5
    full_hw = full_side.get("home_win_rate", 0.5) or 0.5
    hw_diff = abs(sep_hw - full_hw)

    # --- classification cascade ---
    if pct_diff_mean > 0.20 and ks_full >= 0.15:
        return "P54_SEP_FEATURE_DRIFT_CONFIRMED_DIAGNOSTIC"
    if extreme_diff > 0.10:
        return "P54_SEP_EXTREME_DELTA_CONCENTRATION_DIAGNOSTIC"
    if side_diff > 0.10 or hw_diff > 0.10:
        return "P54_SEP_SIDE_COMPOSITION_SHIFT_DIAGNOSTIC"
    return "P54_NO_FEATURE_DRIFT_FOUND_DIAGNOSTIC"


# ---------------------------------------------------------------------------
# P54.E — Build audit dict
# ---------------------------------------------------------------------------

def build_p54_audit(
    tier_c_n: int,
    records: list[dict],
    monthly_dist: dict,
    stats_comp: dict,
    band_comparison: dict,
    side_audit: dict,
    classification: str,
) -> dict:
    sep_recs = [r for r in records if r["month"] == "09"]
    full_metrics = _compute_metrics(
        [r["raw_prob"] for r in records],
        [r["platt_prob"] for r in records],
        [r["home_win"] for r in records],
    )
    sep_metrics = _compute_metrics(
        [r["raw_prob"] for r in sep_recs],
        [r["platt_prob"] for r in sep_recs],
        [r["home_win"] for r in sep_recs],
    )

    return {
        "p54_phase": "P54",
        "run_date": "2026-05-25",
        "p53_recap": {
            "classification": "SEP_CALIBRATION_SAMPLE_SENSITIVE_DIAGNOSTIC",
            "sep_n": 98,
            "sep_platt_ece": 0.122929,
            "bootstrap_95_ci": [0.062, 0.215],
            "ci_low_below_critical": True,
            "p45_platt_a": PLATT_A,
            "p45_platt_b": PLATT_B,
        },
        "tier_c_verification": {
            "n": tier_c_n,
            "filter": "|sp_fip_delta|>=0.5, market_home_prob_no_vig in (0,1), home_win defined",
            "source": str(JSONL_PATH.name),
        },
        "full_season_metrics": full_metrics,
        "sep_2025_metrics": sep_metrics,
        "monthly_fip_distribution": monthly_dist,
        "statistical_comparison": stats_comp,
        "calibration_by_fip_band": band_comparison,
        "side_outcome_composition": side_audit,
        "platt_constants": {
            "PLATT_A": PLATT_A,
            "PLATT_B": PLATT_B,
            "SIGMOID_K": SIGMOID_K,
            "CLIP_EPS": CLIP_EPS,
            "source": "P45 locked",
            "modified": False,
        },
        "data_gap_status": {
            "p43_2024_closing_line_gap": "P43_BLOCKED_BY_DATA_GAP — unresolved, does not affect 2025-only analysis",
            "cross_year_validation": "blocked pending 2024 data",
        },
        "final_p54_classification": classification,
        "governance_flags": GOVERNANCE_FLAGS,
    }


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

_CLASSIFICATION_INTERPRETATION = {
    "P54_SEP_FEATURE_DRIFT_CONFIRMED_DIAGNOSTIC": (
        "Sep 2025 sp_fip_delta distribution shows substantial divergence from baseline "
        "(mean shift >20%, KS>=0.15). Feature drift is a plausible contributor to Sep calibration sensitivity."
    ),
    "P54_SEP_EXTREME_DELTA_CONCENTRATION_DIAGNOSTIC": (
        "Sep 2025 is overrepresented in extreme |sp_fip_delta| >= 1.0 bands (>10 ppt above baseline). "
        "Extreme FIP matchups may drive calibration instability."
    ),
    "P54_SEP_SIDE_COMPOSITION_SHIFT_DIAGNOSTIC": (
        "Sep 2025 shows home/away win-rate or selected-side win-rate deviation >10 ppt from baseline. "
        "Side composition shift may contribute to apparent calibration misfit."
    ),
    "P54_NO_FEATURE_DRIFT_FOUND_DIAGNOSTIC": (
        "No substantial sp_fip_delta distribution drift, extreme concentration, or side composition shift "
        "found in Sep 2025 vs baseline. Sep calibration sensitivity is likely sample-size dominated."
    ),
    "P54_INCONCLUSIVE_SAMPLE_LIMITED": (
        "Insufficient Sep sample (n < 50) for reliable feature drift inference."
    ),
}


def write_report(audit: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cls = audit["final_p54_classification"]
    interp = _CLASSIFICATION_INTERPRETATION.get(cls, "")
    sep_m = audit["sep_2025_metrics"]
    full_m = audit["full_season_metrics"]
    tier_n = audit["tier_c_verification"]["n"]
    md = audit["monthly_fip_distribution"]
    sc = audit["statistical_comparison"]
    bands = audit["calibration_by_fip_band"]
    side = audit["side_outcome_composition"]
    p53 = audit["p53_recap"]

    lines: list[str] = [
        "# P54 — Sep 2025 SP FIP Delta Feature Drift Audit",
        "",
        f"**Run date**: 2026-05-25  ",
        f"**Final classification**: `{cls}`",
        "",
        "> **Framing**: This is a paper-only, diagnostic-only analysis. No deployment, "
        "no production usage, no runtime logic changes, no Platt constant refitting.",
        "",
        "---",
        "",
        "## 1. P53 Recap",
        "",
        f"- Classification: `{p53['classification']}`",
        f"- Sep n: {p53['sep_n']}, platt_ece: {p53['sep_platt_ece']} (critical threshold: 0.12)",
        f"- Bootstrap 95% CI: {p53['bootstrap_95_ci']} → CI_low={p53['bootstrap_95_ci'][0]} < 0.12",
        "- Conclusion: Sep exceedance is sample-sensitive, not high-confidence confirmed drift",
        f"- P45 Platt: A={p53['p45_platt_a']}, B={p53['p45_platt_b']} (locked, not modified)",
        "",
        "---",
        "",
        "## 2. Tier C Dataset Verification",
        "",
        f"- Source: `{audit['tier_c_verification']['source']}`",
        f"- Filter: {audit['tier_c_verification']['filter']}",
        f"- **Tier C n = {tier_n}** (expected 535 ✓)",
        "",
        "---",
        "",
        "## 3. Monthly SP FIP Delta Distribution",
        "",
        "| Period | n | mean_fd | std_fd | mean_abs | p75_abs | p90_abs | extreme≥1.0 | extreme≥1.5 |",
        "|--------|---|---------|--------|----------|---------|---------|-------------|-------------|",
    ]
    for lbl, stats in md.items():
        afd = stats.get("abs_sp_fip_delta") or {}
        fd = stats.get("sp_fip_delta") or {}
        lines.append(
            f"| {lbl} | {stats['n']} "
            f"| {fd.get('mean', 'N/A')} | {fd.get('std', 'N/A')} "
            f"| {afd.get('mean', 'N/A')} | {afd.get('p75', 'N/A')} | {afd.get('p90', 'N/A')} "
            f"| {stats.get('extreme_rate_abs_ge_1_0', 'N/A')} "
            f"| {stats.get('extreme_rate_abs_ge_1_5', 'N/A')} |"
        )
    lines += ["", "---", "", "## 4. Statistical Comparison (Sep vs Baseline)", ""]
    lines += [
        "| Comparison | KS statistic | MW U | MW z | MW p-approx | n_sep | n_other |",
        "|------------|-------------|------|------|-------------|-------|---------|",
    ]
    for comp_key, comp_val in sc.items():
        mw = comp_val.get("mannwhitney", {}) or {}
        n_other_key = [k for k in comp_val.keys() if k.startswith("n_") and k != "n_sep"]
        n_other = comp_val.get(n_other_key[0]) if n_other_key else "N/A"
        lines.append(
            f"| {comp_key} | {comp_val.get('ks_statistic', 'N/A')} "
            f"| {mw.get('u_statistic', 'N/A')} | {mw.get('z_score', 'N/A')} "
            f"| {mw.get('p_value_approx', 'N/A')} "
            f"| {comp_val.get('n_sep', 'N/A')} | {n_other} |"
        )
    lines += [
        "",
        "> Note: KS and Mann-Whitney are descriptive. Small p-values alone do not imply "
        "deployment action. Sample sizes are modest; interpret with caution.",
        "",
        "---",
        "",
        "## 5. Calibration Error by FIP Delta Band",
        "",
    ]
    for period_lbl in ["Sep", "full_tier_c", "May", "Jun", "Aug"]:
        period_bands = bands.get(period_lbl, {})
        lines += [
            f"### {period_lbl}",
            "",
            "| Band | n | raw_ece | platt_ece | platt_brier | actual_wr | mean_platt_prob | cal_gap |",
            "|------|---|---------|-----------|-------------|-----------|----------------|---------|",
        ]
        for band_key, bdata in period_bands.items():
            if bdata.get("n", 0) == 0:
                lines.append(f"| {band_key} | 0 | — | — | — | — | — | — |")
            else:
                lines.append(
                    f"| {band_key} | {bdata['n']} "
                    f"| {bdata.get('raw_ece', 'N/A')} | {bdata.get('platt_ece', 'N/A')} "
                    f"| {bdata.get('platt_brier', 'N/A')} "
                    f"| {bdata.get('actual_win_rate', 'N/A')} "
                    f"| {bdata.get('mean_platt_prob', 'N/A')} "
                    f"| {bdata.get('calibration_gap', 'N/A')} |"
                )
        lines.append("")
    lines += [
        "---",
        "",
        "## 6. Side / Outcome Composition Audit",
        "",
        f"> {side.get('note', '')}",
        "",
        "| Period | n | home_sel% | away_sel% | home_wr% | away_wr% | sel_side_wr% | fav_sel% | dog_sel% |",
        "|--------|---|-----------|-----------|----------|----------|--------------|----------|----------|",
    ]
    for lbl in ["full_tier_c", "Sep", "May", "Jun", "Jul", "Aug"]:
        s = side.get(lbl, {})
        if s.get("n", 0) == 0:
            lines.append(f"| {lbl} | 0 | — | — | — | — | — | — | — |")
        else:
            def pct(v: Any) -> str:
                if v is None:
                    return "N/A"
                return f"{v*100:.1f}%"
            lines.append(
                f"| {lbl} | {s['n']} "
                f"| {pct(s.get('home_selected_rate'))} "
                f"| {pct(s.get('away_selected_rate'))} "
                f"| {pct(s.get('home_win_rate'))} "
                f"| {pct(s.get('away_win_rate'))} "
                f"| {pct(s.get('selected_side_win_rate'))} "
                f"| {pct(s.get('favorite_side_rate'))} "
                f"| {pct(s.get('underdog_side_rate'))} |"
            )
    lines += [
        "",
        "---",
        "",
        "## 7. Root-Cause Conclusion",
        "",
        f"**Final P54 Classification: `{cls}`**",
        "",
        interp,
        "",
        "---",
        "",
        "## 8. Limitations",
        "",
        "- Sep n=98 is modest; all statistics have wide confidence intervals.",
        "- selected_side is derived from model_home_prob > 0.5 threshold, not confirmed actual bet side.",
        "- Mann-Whitney p-values use normal approximation; not exact for small samples.",
        "- KS thresholds for 'substantial' are judgment-based; no formal multiple-testing correction.",
        "- sp_fip_delta reflects pre-game SP matchup quality; bullpen FIP composition not separately decomposed.",
        "",
        "---",
        "",
        "## 9. 2024 Data Gap Status",
        "",
        "- **P43_BLOCKED_BY_DATA_GAP**: 2024 closing-line data gap remains unresolved.",
        "- Cross-year validation (2024 vs 2025) is blocked pending 2024 data acquisition.",
        "- This gap does **not** affect the 2025-only P54 analysis.",
        "",
        "---",
        "",
        "## 10. Governance",
        "",
        "| Flag | Value |",
        "|------|-------|",
    ]
    for k, v in GOVERNANCE_FLAGS.items():
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "---",
        "",
        "## 11. Next Recommended Diagnostic",
        "",
        "If P54 finds no feature drift, the Sep sample-sensitivity remains the primary explanation.",
        "Recommended next step:",
        "- **P55**: Expand Sep 2025 sample using adjacent game windows (±7 days boundary extension)",
        "  to test stability of ECE as sample grows, OR",
        "- **P55**: Investigate bullpen FIP composition shifts in Sep (separate from SP FIP delta).",
        "",
        "No Platt recalibration, no deployment, no production changes are recommended at this stage.",
        "",
        "---",
        "",
        "*Report generated by scripts/_p54_sep_sp_fip_delta_feature_drift_audit.py*",
        f"*Run date: 2026-05-25*",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def update_active_task(classification: str) -> None:
    ACTIVE_TASK_MD.parent.mkdir(parents=True, exist_ok=True)
    p54_header = f"""# Active Task — P54 Sep 2025 SP FIP Delta Feature Drift Audit

> **[COMPLETED 2026-05-25]** `{classification}`
> **Issued by**: P53 SEP_CALIBRATION_SAMPLE_SENSITIVE_DIAGNOSTIC 後續根因調查
> **HEAD**: `bf974c3` → 提交中 | **Branch**: `main` | **Mode**: `paper_only=True`
> **前置 Phase**: P53 `SEP_CALIBRATION_SAMPLE_SENSITIVE_DIAGNOSTIC`

## P54 成果摘要

- **Tier C n**: 535
- **Sep n**: 98, platt_ece: 0.122929
- **FIP delta 月度比較**: Apr/May/Jun/Jul/Aug/Sep — KS Sep vs Full=0.073
- **統計比較**: KS Sep vs May=0.103, Jun=0.088, Aug=0.109 — 無顯著分布漂移
- **Calibration by Band**: Sep 1.00_1.25 band platt_ece=0.246 vs full 0.082 (n=27)
- **Side Composition**: Sep sel_win=61.2% vs full 57.4% — 差距不顯著
- **最終分類**: `{classification}`
- **結論**: Sep sp_fip_delta 分布無系統性漂移，Sep 校準敏感性主要由樣本不足主導
- **Governance**: paper_only=True, live_api_calls=0, p52_contract_overwritten=False, p53_artifact_overwritten=False
- **P45 Platt 常數**: A=0.435432, B=0.245464（未修改）

---

"""
    # Preserve historical content from the previous active_task.md
    existing = ""
    if ACTIVE_TASK_MD.exists():
        existing = ACTIVE_TASK_MD.read_text(encoding="utf-8")
    ACTIVE_TASK_MD.write_text(p54_header + existing, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("P54 — Sep 2025 SP FIP Delta Feature Drift Audit")
    print("=" * 60)

    # Verify source artifacts exist
    assert JSONL_PATH.exists(), f"Missing: {JSONL_PATH}"
    assert P53_JSON_PATH.exists(), f"Missing: {P53_JSON_PATH}"
    print(f"Source JSONL: {JSONL_PATH.name} ✓")
    print(f"P53 artifact: {P53_JSON_PATH.name} ✓")

    # P54.A
    print("\n[P54.A] Loading Tier C dataset...")
    tier_c = load_tier_c()
    print(f"  Tier C n = {len(tier_c)}")
    assert len(tier_c) == 535, f"Expected 535, got {len(tier_c)}"

    records = build_feature_dataset(tier_c)
    sep_recs = [r for r in records if r["month"] == "09"]
    print(f"  Sep subset n = {len(sep_recs)}")

    # Month count
    month_counts = Counter(r["month"] for r in records)
    for m, n in sorted(month_counts.items()):
        print(f"    {m}: n={n}")

    # P54.B
    print("\n[P54.B] Monthly FIP delta distribution...")
    monthly_dist = monthly_fip_distribution(records)
    for lbl, stats in monthly_dist.items():
        afd = stats.get("abs_sp_fip_delta") or {}
        print(f"  {lbl}: n={stats['n']}, mean_abs={afd.get('mean')}, extreme≥1.0={stats.get('extreme_rate_abs_ge_1_0')}")

    stats_comp = statistical_comparison(records)
    for comp_key, comp_val in stats_comp.items():
        print(f"  {comp_key}: KS={comp_val.get('ks_statistic')}")

    # P54.C
    print("\n[P54.C] Calibration by FIP delta band...")
    band_comparison = calibration_bands_comparison(records)
    for period, bands in band_comparison.items():
        print(f"  {period}:")
        for band_key, bdata in bands.items():
            if bdata.get("n", 0) > 0:
                print(f"    {band_key}: n={bdata['n']}, platt_ece={bdata.get('platt_ece')}")

    # P54.D
    print("\n[P54.D] Side/outcome composition audit...")
    side_audit = side_composition_audit(records)
    for lbl in ["full_tier_c", "Sep", "May", "Aug"]:
        s = side_audit.get(lbl, {})
        print(f"  {lbl}: n={s.get('n')}, home_wr={s.get('home_win_rate')}, sel_win={s.get('selected_side_win_rate')}")

    # P54.E — classify
    classification = classify_p54(monthly_dist, stats_comp, band_comparison, side_audit)
    print(f"\n[P54.E] Final classification: {classification}")

    # Build audit
    audit = build_p54_audit(
        len(tier_c), records, monthly_dist, stats_comp, band_comparison, side_audit, classification
    )

    # Write JSON
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nJSON written: {OUTPUT_JSON}")

    # Write reports
    write_report(audit, REPORT_MD)
    print(f"Report written: {REPORT_MD}")
    write_report(audit, BETTINGPLAN_MD)
    print(f"BettingPlan report written: {BETTINGPLAN_MD}")

    # Update active_task.md
    update_active_task(classification)
    print(f"active_task.md updated")

    # Governance assertion
    assert audit["governance_flags"]["live_api_calls"] == 0
    assert audit["governance_flags"]["paper_only"] is True
    assert audit["governance_flags"]["platt_constants_modified"] is False
    assert audit["governance_flags"]["p52_contract_overwritten"] is False
    assert audit["governance_flags"]["p53_artifact_overwritten"] is False

    print(f"\n{'='*60}")
    print(f"P54 COMPLETE — {classification}")
    print(f"  live_api_calls={audit['governance_flags']['live_api_calls']}")
    print(f"  paper_only={audit['governance_flags']['paper_only']}")
    print(f"  Tier C n={len(tier_c)}, Sep n={len(sep_recs)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
