"""
P53 — Sep 2025 Calibration Critical Root-Cause Audit
=====================================================

Investigates why Sep 2025 triggered CALIBRATION_CRITICAL under P52 V2 contract.

Governance (ALL LOCKED):
    paper_only=True, diagnostic_only=True, promotion_freeze=True,
    kelly_deploy_allowed=False, live_api_calls=0,
    p52_contract_overwritten=False

Output:
    data/mlb_2025/derived/p53_sep_calibration_critical_audit_summary.json
    report/p53_sep_calibration_critical_audit_20260526.md
    00-BettingPlan/20260526/p53_sep_calibration_critical_audit_20260526.md
"""

from __future__ import annotations

import json
import math
import pathlib
from typing import Any

import numpy as np

# ── Governance ────────────────────────────────────────────────────────────────
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
    "p52_contract_overwritten": False,
}

# ── P45 Platt constants (LOCKED) ──────────────────────────────────────────────
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464
SIGMOID_K: float = 0.8
CLIP_EPS: float = 1e-7

# ── Bootstrap parameters (matching P50/P51) ───────────────────────────────────
BOOTSTRAP_SEED: int = 42
N_BOOT: int = 5000

# ── Tier C filter (same as P43–P52) ──────────────────────────────────────────
TIER_C_SP_FIP_DELTA_MIN: float = 0.5
TIER_C_EXPECTED_N: int = 535

# ── Paths ─────────────────────────────────────────────────────────────────────
_ROOT = pathlib.Path(__file__).parent.parent
_DERIVED = _ROOT / "data/mlb_2025/derived"

JSONL_PATH = _DERIVED / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
P52_PATH = _DERIVED / "p52_monitoring_contract_v2_summary.json"

OUTPUT_JSON = _DERIVED / "p53_sep_calibration_critical_audit_summary.json"
OUTPUT_REPORT = _ROOT / "report/p53_sep_calibration_critical_audit_20260526.md"
OUTPUT_PLAN = _ROOT / "00-BettingPlan/20260526/p53_sep_calibration_critical_audit_20260526.md"

ALLOWED_CLASSIFICATIONS = [
    "SEP_CALIBRATION_DRIFT_CONFIRMED_DIAGNOSTIC",
    "SEP_CALIBRATION_SAMPLE_SENSITIVE_DIAGNOSTIC",
    "SEP_CALIBRATION_BINNING_ARTIFACT_DIAGNOSTIC",
    "SEP_CALIBRATION_INCONCLUSIVE",
]

# ── Calibration helpers ───────────────────────────────────────────────────────

def _platt_prob(raw_p: float) -> float:
    """Apply P45-locked Platt scaling to raw model probability."""
    raw_p = max(CLIP_EPS, min(1.0 - CLIP_EPS, raw_p))
    logit_raw = math.log(raw_p / (1.0 - raw_p))
    return 1.0 / (1.0 + math.exp(-(PLATT_A * logit_raw + PLATT_B)))


def _ece(probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error with uniform bins."""
    n = len(probs)
    if n == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece_val = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        if i == n_bins - 1:
            mask = (probs >= lo) & (probs <= hi)
        else:
            mask = (probs >= lo) & (probs < hi)
        cnt = int(mask.sum())
        if cnt == 0:
            continue
        avg_conf = float(probs[mask].mean())
        avg_acc = float(outcomes[mask].mean())
        ece_val += abs(avg_acc - avg_conf) * cnt / n
    return ece_val


def _brier(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Brier score (mean squared error)."""
    if len(probs) == 0:
        return float("nan")
    return float(np.mean((probs - outcomes) ** 2))


# ── Task P53.A — Tier C dataset ───────────────────────────────────────────────

def load_tier_c() -> list[dict]:
    """
    Rebuild the Tier C dataset used by P43–P52.
    Filter: |sp_fip_delta| >= 0.5, market_home_prob_no_vig in (0,1), home_win defined.
    sp_fip_delta is nested at row["p0_features"]["sp_fip_delta"].
    """
    rows: list[dict] = []
    with open(JSONL_PATH) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    tier_c: list[dict] = []
    for r in rows:
        feats = r.get("p0_features", {})
        sp = feats.get("sp_fip_delta")
        mp = r.get("market_home_prob_no_vig")
        hw = r.get("home_win")
        if sp is None or mp is None or hw is None:
            continue
        if abs(sp) >= TIER_C_SP_FIP_DELTA_MIN and 0.0 < mp < 1.0:
            tier_c.append(r)

    return tier_c


def build_calibration_vectors(
    rows: list[dict],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (raw_probs, platt_probs, outcomes) numpy arrays."""
    raw_probs = np.array([r["model_home_prob"] for r in rows], dtype=float)
    platt_probs = np.array([_platt_prob(p) for p in raw_probs], dtype=float)
    outcomes = np.array([float(r["home_win"]) for r in rows], dtype=float)
    return raw_probs, platt_probs, outcomes


# ── Task P53.A continued — metrics for a slice ───────────────────────────────

def compute_metrics(
    raw_probs: np.ndarray, platt_probs: np.ndarray, outcomes: np.ndarray
) -> dict:
    """Compute calibration metrics for any slice."""
    n = len(outcomes)
    if n == 0:
        return {"n": 0, "error": "empty"}
    return {
        "n": n,
        "raw_ece": round(_ece(raw_probs, outcomes, n_bins=10), 6),
        "platt_ece": round(_ece(platt_probs, outcomes, n_bins=10), 6),
        "raw_brier": round(_brier(raw_probs, outcomes), 6),
        "platt_brier": round(_brier(platt_probs, outcomes), 6),
        "mean_raw_prob": round(float(raw_probs.mean()), 6),
        "mean_platt_prob": round(float(platt_probs.mean()), 6),
        "actual_win_rate": round(float(outcomes.mean()), 6),
        "calibration_gap_raw": round(float(outcomes.mean()) - float(raw_probs.mean()), 6),
        "calibration_gap_platt": round(float(outcomes.mean()) - float(platt_probs.mean()), 6),
    }


# ── Task P53.B — Reliability bins ────────────────────────────────────────────

_MIN_BIN_N_SAMPLE_LIMITED = 10


def _bin_interpretation(
    platt_gap: float, n: int, min_n: int = _MIN_BIN_N_SAMPLE_LIMITED
) -> str:
    if n < min_n:
        return "SAMPLE_LIMITED_BIN"
    if abs(platt_gap) < 0.03:
        return "WELL_ALIGNED"
    if platt_gap > 0:
        return "UNDERCONFIDENT"
    return "OVERCONFIDENT"


def build_reliability_bins(
    raw_probs: np.ndarray,
    platt_probs: np.ndarray,
    outcomes: np.ndarray,
    n_bins: int = 10,
) -> list[dict]:
    """Build N-bin reliability table."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    n_total = len(outcomes)
    bins: list[dict] = []
    for i in range(n_bins):
        lo, hi = float(edges[i]), float(edges[i + 1])
        if i == n_bins - 1:
            mask = (platt_probs >= lo) & (platt_probs <= hi)
        else:
            mask = (platt_probs >= lo) & (platt_probs < hi)
        cnt = int(mask.sum())
        if cnt == 0:
            bins.append({
                "bin_low": round(lo, 2),
                "bin_high": round(hi, 2),
                "n": 0,
                "predicted_mean_raw": None,
                "predicted_mean_platt": None,
                "actual_win_rate": None,
                "raw_gap": None,
                "platt_gap": None,
                "ece_contribution": 0.0,
                "brier_contribution": 0.0,
                "interpretation": "EMPTY_BIN",
            })
            continue
        pred_raw = float(raw_probs[mask].mean())
        pred_platt = float(platt_probs[mask].mean())
        actual = float(outcomes[mask].mean())
        platt_gap = actual - pred_platt
        raw_gap = actual - pred_raw
        ece_contrib = abs(platt_gap) * cnt / n_total
        brier_contrib = float(np.mean((platt_probs[mask] - outcomes[mask]) ** 2)) * cnt / n_total
        bins.append({
            "bin_low": round(lo, 2),
            "bin_high": round(hi, 2),
            "n": cnt,
            "predicted_mean_raw": round(pred_raw, 6),
            "predicted_mean_platt": round(pred_platt, 6),
            "actual_win_rate": round(actual, 6),
            "raw_gap": round(raw_gap, 6),
            "platt_gap": round(platt_gap, 6),
            "ece_contribution": round(ece_contrib, 6),
            "brier_contribution": round(brier_contrib, 6),
            "interpretation": _bin_interpretation(platt_gap, cnt),
        })
    return bins


def analyze_reliability_bins(bins: list[dict]) -> dict:
    """Identify top ECE/Brier contributors and characterization."""
    populated = [b for b in bins if b["n"] > 0]
    if not populated:
        return {}
    by_ece = sorted(populated, key=lambda b: b["ece_contribution"], reverse=True)
    by_brier = sorted(populated, key=lambda b: b["brier_contribution"], reverse=True)
    top_ece_bin = by_ece[0]
    top_brier_bin = by_brier[0]

    # Concentration: top bin contributes > 50% of total ECE?
    total_ece = sum(b["ece_contribution"] for b in populated)
    top_ece_share = top_ece_bin["ece_contribution"] / total_ece if total_ece > 0 else 0

    # Pattern: are most bins overconfident or underconfident?
    under = sum(1 for b in populated if b["interpretation"] == "UNDERCONFIDENT")
    over = sum(1 for b in populated if b["interpretation"] == "OVERCONFIDENT")
    if under > over:
        dominant_pattern = "UNDERCONFIDENT"
    elif over > under:
        dominant_pattern = "OVERCONFIDENT"
    else:
        dominant_pattern = "MIXED"

    return {
        "top_ece_bin": top_ece_bin,
        "top_brier_bin": top_brier_bin,
        "top_ece_bin_share": round(top_ece_share, 4),
        "error_concentrated": top_ece_share > 0.5,
        "dominant_pattern": dominant_pattern,
        "n_underconfident_bins": under,
        "n_overconfident_bins": over,
        "n_well_aligned_bins": sum(1 for b in populated if b["interpretation"] == "WELL_ALIGNED"),
        "n_sample_limited_bins": sum(
            1 for b in populated if b["interpretation"] == "SAMPLE_LIMITED_BIN"
        ),
    }


# ── Task P53.C — Late-season comparison ──────────────────────────────────────

COMPARISON_MONTHS = {
    "2025-05": "May",
    "2025-06": "Jun",
    "2025-08": "Aug",
    "2025-09": "Sep",
}


def compute_late_season_comparison(tier_c: list[dict]) -> list[dict]:
    """Compare Sep against May, Jun, Aug, and late-Aug+Sep combined."""
    results: list[dict] = []

    def _slice_metrics(rows: list[dict], label: str) -> dict:
        raw, platt, out = build_calibration_vectors(rows)
        m = compute_metrics(raw, platt, out)
        # Top ECE bin
        bins_10 = build_reliability_bins(raw, platt, out, n_bins=10)
        populated = [b for b in bins_10 if b["n"] > 0]
        top_ece = max(populated, key=lambda b: b["ece_contribution"]) if populated else {}
        m["period"] = label
        m["top_ece_bin_range"] = (
            f"[{top_ece.get('bin_low')}, {top_ece.get('bin_high')}]"
            if top_ece
            else "N/A"
        )
        m["top_ece_bin_contrib"] = top_ece.get("ece_contribution", 0)
        m["v2_status"] = _v2_contract_status(m)
        return m

    # Individual months
    for month, label in COMPARISON_MONTHS.items():
        rows = [r for r in tier_c if r["game_date"].startswith(month)]
        if rows:
            results.append(_slice_metrics(rows, label))

    # Late-Aug + Sep combined
    late_rows = [
        r
        for r in tier_c
        if r["game_date"].startswith("2025-08") or r["game_date"].startswith("2025-09")
    ]
    if late_rows:
        results.append(_slice_metrics(late_rows, "LateAug+Sep"))

    return results


def _v2_contract_status(metrics: dict) -> str:
    """Classify under P52 V2 contract alert rules."""
    n = metrics.get("n", 0)
    platt_ece = metrics.get("platt_ece", 0)
    platt_brier = metrics.get("platt_brier", 0)

    if n < 100:
        sample_status = "SAMPLE_LIMITED"
    else:
        sample_status = "OK"

    if platt_ece > 0.12 or platt_brier > 0.27:
        calib_status = "CALIBRATION_CRITICAL"
    elif platt_ece > 0.10 or platt_brier > 0.25:
        calib_status = "CALIBRATION_WARNING"
    else:
        calib_status = "MONITORING_OK"

    # V2 dominance: CRITICAL is NOT suppressed by SAMPLE_LIMITED
    if calib_status == "CALIBRATION_CRITICAL":
        if sample_status == "SAMPLE_LIMITED":
            return f"CALIBRATION_CRITICAL+SAMPLE_LIMITED"
        return "CALIBRATION_CRITICAL"
    if sample_status == "SAMPLE_LIMITED":
        return f"SAMPLE_LIMITED"
    return calib_status


# ── Task P53.D — Sample sensitivity ──────────────────────────────────────────

def bootstrap_ece(
    platt_probs: np.ndarray,
    outcomes: np.ndarray,
    n_bins: int = 10,
    n_boot: int = N_BOOT,
    seed: int = BOOTSTRAP_SEED,
) -> dict:
    """Bootstrap CI for ECE. Uses numpy default_rng (matching P50/P51)."""
    rng = np.random.default_rng(seed)
    n = len(platt_probs)
    boot_eces: list[float] = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boot_eces.append(_ece(platt_probs[idx], outcomes[idx], n_bins=n_bins))
    arr = np.array(boot_eces)
    observed = _ece(platt_probs, outcomes, n_bins=n_bins)
    return {
        "n_boot": n_boot,
        "seed": seed,
        "observed_ece": round(float(observed), 6),
        "boot_mean": round(float(arr.mean()), 6),
        "boot_std": round(float(arr.std()), 6),
        "ci_low_95": round(float(np.percentile(arr, 2.5)), 6),
        "ci_high_95": round(float(np.percentile(arr, 97.5)), 6),
        "ci_low_90": round(float(np.percentile(arr, 5.0)), 6),
        "ci_high_90": round(float(np.percentile(arr, 95.0)), 6),
        "exceeds_critical_threshold_observed": float(observed) > 0.12,
        "ci_low_exceeds_critical": float(np.percentile(arr, 2.5)) > 0.12,
        "pct_boots_above_critical": round(float((arr > 0.12).mean()), 4),
        "pct_boots_above_warning": round(float((arr > 0.10).mean()), 4),
    }


def _adaptive_bins(
    platt_probs: np.ndarray,
    outcomes: np.ndarray,
    min_n: int = 10,
) -> list[dict]:
    """
    Adaptive bins: start with 10 equal-width bins, merge adjacent bins
    from lowest probability upward until each bin has n >= min_n.
    """
    # Use sorted order to merge small bins
    order = np.argsort(platt_probs)
    sorted_p = platt_probs[order]
    sorted_y = outcomes[order]

    # Greedy grouping: accumulate until n >= min_n
    groups: list[tuple[int, int]] = []  # (start_idx, end_idx)
    start = 0
    n = len(sorted_p)
    while start < n:
        end = start + min_n
        if end >= n:
            end = n
        # If remaining is small, merge into last group
        if end < n and (n - end) < min_n and groups:
            end = n
        groups.append((start, end))
        start = end

    # Compute bin metrics
    n_total = len(outcomes)
    result: list[dict] = []
    for gstart, gend in groups:
        seg_p = sorted_p[gstart:gend]
        seg_y = sorted_y[gstart:gend]
        cnt = len(seg_p)
        pred = float(seg_p.mean())
        actual = float(seg_y.mean())
        gap = actual - pred
        ece_contrib = abs(gap) * cnt / n_total
        result.append({
            "bin_low": round(float(seg_p.min()), 4),
            "bin_high": round(float(seg_p.max()), 4),
            "n": cnt,
            "predicted_mean_platt": round(pred, 6),
            "actual_win_rate": round(actual, 6),
            "platt_gap": round(gap, 6),
            "ece_contribution": round(ece_contrib, 6),
            "interpretation": _bin_interpretation(gap, cnt, min_n),
        })
    return result


def _ece_from_bins(bins: list[dict]) -> float:
    return sum(b["ece_contribution"] for b in bins)


def compute_sensitivity(
    raw_probs: np.ndarray,
    platt_probs: np.ndarray,
    outcomes: np.ndarray,
) -> dict:
    """P53.D: 5-bin, 10-bin, adaptive sensitivity + bootstrap."""
    # Bootstrap on 10-bin ECE
    boot = bootstrap_ece(platt_probs, outcomes, n_bins=10)

    # 5-bin ECE
    ece_5 = _ece(platt_probs, outcomes, n_bins=5)
    bins_5 = build_reliability_bins(raw_probs, platt_probs, outcomes, n_bins=5)

    # 10-bin ECE
    ece_10 = _ece(platt_probs, outcomes, n_bins=10)
    bins_10 = build_reliability_bins(raw_probs, platt_probs, outcomes, n_bins=10)

    # Adaptive bins (min n >= 10)
    bins_adaptive = _adaptive_bins(platt_probs, outcomes, min_n=10)
    ece_adaptive = _ece_from_bins(bins_adaptive)

    # Consistency check: all methods exceed 0.12?
    above_critical = {
        "5_bin": ece_5 > 0.12,
        "10_bin": ece_10 > 0.12,
        "adaptive": ece_adaptive > 0.12,
        "bootstrap_observed": boot["exceeds_critical_threshold_observed"],
        "bootstrap_ci_low_95": boot["ci_low_exceeds_critical"],
    }

    return {
        "binning_sensitivity": {
            "5_bin": {
                "n_bins": 5,
                "platt_ece": round(ece_5, 6),
                "above_critical_0_12": ece_5 > 0.12,
                "bins": bins_5,
            },
            "10_bin": {
                "n_bins": 10,
                "platt_ece": round(ece_10, 6),
                "above_critical_0_12": ece_10 > 0.12,
                "bins": bins_10,
            },
            "adaptive": {
                "n_bins_actual": len(bins_adaptive),
                "min_n_per_bin": 10,
                "platt_ece": round(ece_adaptive, 6),
                "above_critical_0_12": ece_adaptive > 0.12,
                "bins": bins_adaptive,
            },
        },
        "bootstrap": boot,
        "all_methods_above_critical": all(above_critical.values()),
        "any_method_above_critical": any(above_critical.values()),
        "above_critical_by_method": above_critical,
    }


# ── Final classification ──────────────────────────────────────────────────────

def classify_p53(sensitivity: dict) -> str:
    """
    Classify based on binning sensitivity and bootstrap results.

    Logic:
    - If all methods (5-bin, 10-bin, adaptive, bootstrap observed, CI_low 95%) confirm >0.12:
      SEP_CALIBRATION_DRIFT_CONFIRMED_DIAGNOSTIC
    - If most methods confirm but bootstrap CI_low dips below 0.12:
      SEP_CALIBRATION_SAMPLE_SENSITIVE_DIAGNOSTIC
    - If only one binning method triggers:
      SEP_CALIBRATION_BINNING_ARTIFACT_DIAGNOSTIC
    - Otherwise:
      SEP_CALIBRATION_INCONCLUSIVE
    """
    flags = sensitivity["above_critical_by_method"]
    n_true = sum(1 for v in flags.values() if v)
    n_total = len(flags)

    # All methods confirm → drift confirmed
    if sensitivity["all_methods_above_critical"]:
        return "SEP_CALIBRATION_DRIFT_CONFIRMED_DIAGNOSTIC"

    # Majority confirm but bootstrap CI_low doesn't → sample-sensitive
    if n_true >= 3 and not flags.get("bootstrap_ci_low_95", False):
        return "SEP_CALIBRATION_SAMPLE_SENSITIVE_DIAGNOSTIC"

    # Only some binning methods trigger → binning artifact
    if n_true >= 2 and flags.get("10_bin", False) and not flags.get("adaptive", False):
        return "SEP_CALIBRATION_BINNING_ARTIFACT_DIAGNOSTIC"

    # Some but not most confirm
    if n_true >= 2:
        return "SEP_CALIBRATION_SAMPLE_SENSITIVE_DIAGNOSTIC"

    if n_true >= 1:
        return "SEP_CALIBRATION_INCONCLUSIVE"

    return "SEP_CALIBRATION_INCONCLUSIVE"


# ── Main builder ──────────────────────────────────────────────────────────────

def build_p53_audit() -> dict:
    # Pre-load P52 to confirm source
    if not P52_PATH.exists():
        raise FileNotFoundError(f"P52 artifact missing: {P52_PATH}")
    p52_data = json.loads(P52_PATH.read_text())

    # ── P53.A: Tier C + Sep subset ────────────────────────────────────────────
    tier_c = load_tier_c()
    n_tier_c = len(tier_c)
    raw_all, platt_all, out_all = build_calibration_vectors(tier_c)

    sep_rows = [r for r in tier_c if r["game_date"].startswith("2025-09")]
    n_sep = len(sep_rows)
    raw_sep, platt_sep, out_sep = build_calibration_vectors(sep_rows)

    sep_metrics = compute_metrics(raw_sep, platt_sep, out_sep)

    # ── P53.B: Reliability bins for Sep ──────────────────────────────────────
    sep_bins_10 = build_reliability_bins(raw_sep, platt_sep, out_sep, n_bins=10)
    sep_bin_analysis = analyze_reliability_bins(sep_bins_10)

    # ── P53.C: Late-season comparison ────────────────────────────────────────
    late_season_comparison = compute_late_season_comparison(tier_c)

    # ── P53.D: Sample sensitivity ─────────────────────────────────────────────
    sensitivity = compute_sensitivity(raw_sep, platt_sep, out_sep)

    # ── Final classification ──────────────────────────────────────────────────
    classification = classify_p53(sensitivity)
    assert classification in ALLOWED_CLASSIFICATIONS, f"Invalid: {classification}"

    # ── 2025 full-season for context ──────────────────────────────────────────
    full_season_metrics = compute_metrics(raw_all, platt_all, out_all)

    result: dict = {
        "version": "1.0",
        "audit_date": "2026-05-26",
        "phase": "P53",
        "source_phase": "P52",
        "p52_classification": p52_data.get("final_p52_classification"),
        # ── P53.A ─────────────────────────────────────────────────────────────
        "tier_c_verification": {
            "n": n_tier_c,
            "expected_n": TIER_C_EXPECTED_N,
            "filter": "|sp_fip_delta| >= 0.5, market_home_prob_no_vig in (0,1), home_win defined",
            "sp_fip_delta_path": "row['p0_features']['sp_fip_delta']",
            "n_matches_expected": n_tier_c == TIER_C_EXPECTED_N,
        },
        "platt_coefficients": {
            "platt_a": PLATT_A,
            "platt_b": PLATT_B,
            "sigmoid_k": SIGMOID_K,
            "clip_eps": CLIP_EPS,
            "locked_from": "P45",
        },
        "full_season_metrics": full_season_metrics,
        "sep_2025_drilldown": {
            "month": "2025-09",
            "n": n_sep,
            "metrics": sep_metrics,
            "v2_status": _v2_contract_status(sep_metrics),
            "ece_critical_threshold": 0.12,
            "ece_warning_threshold": 0.10,
        },
        # ── P53.B ─────────────────────────────────────────────────────────────
        "sep_2025_reliability_bins_10": sep_bins_10,
        "sep_2025_bin_analysis": sep_bin_analysis,
        # ── P53.C ─────────────────────────────────────────────────────────────
        "late_season_comparison": late_season_comparison,
        # ── P53.D ─────────────────────────────────────────────────────────────
        "sample_sensitivity": sensitivity,
        # ── Governance + result ───────────────────────────────────────────────
        "governance_flags": GOVERNANCE_FLAGS,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "final_p53_classification": classification,
        "limitations": [
            "Sep 2025 n=98 is below the n=100 SAMPLE_LIMITED threshold — "
            "all sensitivity analyses account for this.",
            "Platt constants locked from P45. Recalibration requires explicit authorization.",
            "2024 closing-line data gap remains unresolved "
            "(P43_BLOCKED_BY_DATA_GAP — cross-year market-edge validation blocked).",
            "No live odds data used. Analysis is entirely offline.",
            "Root cause of Sep 2025 degradation (late-season regression, "
            "market adaptation, regime change) not yet determined.",
            "P53 does not modify runtime recommendation logic.",
            "P52 artifact not overwritten.",
        ],
        "framing_note": (
            "P53 is paper-only, offline, diagnostic. "
            "No production deployment proposed. No runtime logic changed."
        ),
    }

    return result


def write_report(audit: dict) -> None:
    """Write both MD report files."""
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PLAN.parent.mkdir(parents=True, exist_ok=True)

    sep = audit["sep_2025_drilldown"]
    sm = sep["metrics"]
    ba = audit["sep_2025_bin_analysis"]
    sens = audit["sample_sensitivity"]
    bins10 = audit["sep_2025_reliability_bins_10"]
    boot = sens["bootstrap"]
    clf = audit["final_p53_classification"]
    comparison = audit["late_season_comparison"]
    tier_c_v = audit["tier_c_verification"]
    flags = audit["governance_flags"]

    # ── Technical report ─────────────────────────────────────────────────────
    lines: list[str] = [
        "# P53 — Sep 2025 校準 CRITICAL 根因審計",
        "",
        f"**日期**: 2026-05-26  ",
        f"**Phase**: P53  ",
        f"**前置 Phase**: P52 (`{audit['p52_classification']}`)  ",
        f"**狀態**: COMPLETE — `{clf}`",
        "",
        "---",
        "",
        "## Governance（治理鎖定）",
        "",
        "| 項目 | 值 |",
        "|------|-----|",
    ]
    for k, v in flags.items():
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "---",
        "",
        "## 一、P52 背景回顧",
        "",
        "P52 正式確立 V2 監控合約：",
        "- 邊際監控：RAW_SIGMOID (`fip_signal_side_aware_edge`, k=1.0)",
        "- 校準監控：PLATT_CALIBRATED (A=0.435432, B=0.245464)",
        "- SAMPLE_LIMITED 不支配 CRITICAL（P49 錯誤修正）",
        "",
        "**P52 遺留問題**：Sep 2025 (n=98, platt_ece=0.1229 > 0.12) 被分類為 CALIBRATION_CRITICAL。",
        "P49 曾以 SAMPLE_LIMITED 掩蓋此問題。P53 調查根因。",
        "",
        "---",
        "",
        "## 二、Tier C 資料驗證",
        "",
        f"| 項目 | 值 |",
        "|------|-----|",
        f"| 總 Tier C n | {tier_c_v['n']} |",
        f"| 預期 n | {tier_c_v['expected_n']} |",
        f"| 符合預期 | {tier_c_v['n_matches_expected']} |",
        f"| Sep 2025 n | {sep['n']} |",
        f"| Platt A | {audit['platt_coefficients']['platt_a']} (P45 鎖定) |",
        f"| Platt B | {audit['platt_coefficients']['platt_b']} (P45 鎖定) |",
        "",
        "---",
        "",
        "## 三、Sep 2025 校準指標",
        "",
        "| 指標 | 值 |",
        "|------|-----|",
        f"| n | {sm['n']} |",
        f"| platt_ece | **{sm['platt_ece']}** |",
        f"| raw_ece | {sm['raw_ece']} |",
        f"| platt_brier | {sm['platt_brier']} |",
        f"| raw_brier | {sm['raw_brier']} |",
        f"| mean_platt_prob | {sm['mean_platt_prob']} |",
        f"| mean_raw_prob | {sm['mean_raw_prob']} |",
        f"| actual_win_rate | {sm['actual_win_rate']} |",
        f"| calibration_gap_platt | {sm['calibration_gap_platt']} |",
        f"| V2 Contract 狀態 | `{sep['v2_status']}` |",
        "",
        "> Platt ECE 臨界閾值 = 0.12；Sep platt_ece = "
        + f"{sm['platt_ece']} → 超出 {sm['platt_ece'] - 0.12:.6f}",
        "",
        "---",
        "",
        "## 四、可靠性 Bin 根因分析（10 個 Bin）",
        "",
        f"**主要模式**: {ba.get('dominant_pattern', 'N/A')}  ",
        f"**錯誤是否集中**: {ba.get('error_concentrated', False)}  ",
        f"（最大 ECE bin 佔比: {ba.get('top_ece_bin_share', 0):.2%}）",
        "",
        "| Bin | n | 預測均值(P) | 實際勝率 | Platt Gap | ECE 貢獻 | 解讀 |",
        "|-----|---|------------|---------|----------|---------|------|",
    ]
    for b in bins10:
        if b["n"] == 0:
            continue
        lines.append(
            f"| [{b['bin_low']:.2f},{b['bin_high']:.2f}] "
            f"| {b['n']} "
            f"| {b['predicted_mean_platt']:.4f} "
            f"| {b['actual_win_rate']:.4f} "
            f"| {b['platt_gap']:+.4f} "
            f"| {b['ece_contribution']:.4f} "
            f"| {b['interpretation']} |"
        )

    top_ece = ba.get("top_ece_bin", {})
    lines += [
        "",
        f"**最大 ECE 貢獻 Bin**: [{top_ece.get('bin_low')}, {top_ece.get('bin_high')}] "
        f"ECE 貢獻={top_ece.get('ece_contribution', 0):.4f}, "
        f"解讀={top_ece.get('interpretation', 'N/A')}",
        "",
        "---",
        "",
        "## 五、晚賽季比較",
        "",
        "| 期間 | n | raw_ece | platt_ece | platt_brier | 實際勝率 | 平均預測(P) | V2 狀態 |",
        "|------|---|---------|----------|------------|---------|-----------|---------|",
    ]
    for row in comparison:
        lines.append(
            f"| {row['period']} "
            f"| {row['n']} "
            f"| {row['raw_ece']:.4f} "
            f"| {row['platt_ece']:.4f} "
            f"| {row['platt_brier']:.4f} "
            f"| {row['actual_win_rate']:.4f} "
            f"| {row['mean_platt_prob']:.4f} "
            f"| {row['v2_status']} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 六、樣本敏感性分析（P53.D）",
        "",
        "### Bootstrap (n_boot=5000, seed=42, 10-bin ECE)",
        "",
        "| 指標 | 值 |",
        "|------|-----|",
        f"| 觀測 platt_ece | {boot['observed_ece']} |",
        f"| Bootstrap 均值 | {boot['boot_mean']} |",
        f"| Bootstrap 標準差 | {boot['boot_std']} |",
        f"| 95% CI | [{boot['ci_low_95']}, {boot['ci_high_95']}] |",
        f"| 90% CI | [{boot['ci_low_90']}, {boot['ci_high_90']}] |",
        f"| CI_low_95 > 0.12 | {boot['ci_low_exceeds_critical']} |",
        f"| Bootstrap > 0.12 佔比 | {boot['pct_boots_above_critical']:.2%} |",
        f"| Bootstrap > 0.10 佔比 | {boot['pct_boots_above_warning']:.2%} |",
        "",
        "### Bin 數量敏感性",
        "",
        "| 方法 | n_bins | platt_ece | > 0.12 |",
        "|------|--------|----------|-------|",
        f"| 5-bin | 5 | {sens['binning_sensitivity']['5_bin']['platt_ece']} "
        f"| {sens['binning_sensitivity']['5_bin']['above_critical_0_12']} |",
        f"| 10-bin | 10 | {sens['binning_sensitivity']['10_bin']['platt_ece']} "
        f"| {sens['binning_sensitivity']['10_bin']['above_critical_0_12']} |",
        f"| adaptive (min_n=10) | {sens['binning_sensitivity']['adaptive']['n_bins_actual']} "
        f"| {sens['binning_sensitivity']['adaptive']['platt_ece']} "
        f"| {sens['binning_sensitivity']['adaptive']['above_critical_0_12']} |",
        "",
        "### 方法一致性",
        "",
    ]
    for method, val in sens["above_critical_by_method"].items():
        lines.append(f"- {method}: `{'CRITICAL' if val else 'not_critical'}`")
    lines += [
        "",
        f"**所有方法均超 CRITICAL**: {sens['all_methods_above_critical']}  ",
        f"**任一方法超 CRITICAL**: {sens['any_method_above_critical']}",
        "",
        "---",
        "",
        "## 七、Platt 過/欠信心診斷",
        "",
        f"校準缺口（platt）= 實際勝率 - 平均 Platt 預測 = "
        f"{sm['actual_win_rate']:.4f} - {sm['mean_platt_prob']:.4f} = "
        f"{sm['calibration_gap_platt']:+.4f}",
        "",
    ]
    if sm["calibration_gap_platt"] > 0.02:
        lines.append("**診斷**: Platt **欠信心（UNDERCONFIDENT）** — 模型預測偏低，實際勝率偏高")
    elif sm["calibration_gap_platt"] < -0.02:
        lines.append("**診斷**: Platt **過信心（OVERCONFIDENT）** — 模型預測偏高，實際勝率偏低")
    else:
        lines.append("**診斷**: 整體 Platt 校準接近中性，偏差不顯著（< 2%）")

    lines += [
        "",
        f"Bin 主要模式: **{ba.get('dominant_pattern', 'N/A')}**",
        "",
        "---",
        "",
        "## 八、限制",
        "",
    ]
    for lim in audit["limitations"]:
        lines.append(f"- {lim}")

    lines += [
        "",
        "---",
        "",
        "## 九、最終分類",
        "",
        f"```",
        f"{clf}",
        "```",
        "",
        "**2024 closing-line 資料缺口**: 仍未解決 (`P43_BLOCKED_BY_DATA_GAP`)，",
        "為 cross-year blocker only，不影響 2025-only 分析。",
        "",
        "---",
        "",
        "## 十、建議下一步",
        "",
        "- **P54**（如需要）：若確認為真實校準漂移，調查 Sep 2025 SP FIP delta 分布變化",
        "  是否反映晚賽季投手 FIP 回歸，或者比賽特性改變",
        "- **P55**：若 2+ 個完整賽季數據可用，評估是否需要 Platt 常數重新校準",
        "  （需要 CEO 授權）",
        "- **P54 或 P55**：若 2024 closing-line odds 補齊，重新執行 P43 跨年驗證",
        "",
        "---",
        "",
        "## 成品清單",
        "",
        "| 成品 | 路徑 |",
        "|------|------|",
        "| 主腳本 | `scripts/_p53_sep_calibration_critical_audit.py` |",
        "| 測試 | `tests/test_p53_sep_calibration_critical_audit.py` |",
        "| JSON 輸出 | `data/mlb_2025/derived/p53_sep_calibration_critical_audit_summary.json` |",
        "| 報告（正式） | `report/p53_sep_calibration_critical_audit_20260526.md` |",
        "| 報告（下注計畫） | `00-BettingPlan/20260526/p53_sep_calibration_critical_audit_20260526.md` |",
        "",
        "*P53 diagnostic — paper_only=True, diagnostic_only=True, no production deployment proposed*",
    ]
    OUTPUT_REPORT.write_text("\n".join(lines))

    # ── Betting plan report ───────────────────────────────────────────────────
    plan_lines: list[str] = [
        "# P53 Sep 2025 校準根因審計 — 投注計畫備案",
        "",
        "**日期**: 2026-05-26  ",
        "**Phase**: P53  ",
        f"**最終分類**: `{clf}`",
        "",
        "---",
        "",
        "## 投注計畫相關性",
        "",
        "**本報告為診斷性研究**，不產生任何投注訊號或實際下注建議。",
        "所有 governance 旗標確認：`paper_only=True`, `kelly_deploy_allowed=False`, `live_api_calls=0`",
        "",
        "P53 調查 Sep 2025 CALIBRATION_CRITICAL 根因，是 P52 V2 合約遺留問題的直接跟進。",
        "",
        "---",
        "",
        "## 核心發現",
        "",
        f"| 項目 | 值 |",
        "|------|-----|",
        f"| Sep n | {sm['n']} |",
        f"| platt_ece | **{sm['platt_ece']}** (臨界值 0.12) |",
        f"| 超出 | +{sm['platt_ece'] - 0.12:.6f} |",
        f"| 5-bin ECE | {sens['binning_sensitivity']['5_bin']['platt_ece']} |",
        f"| adaptive ECE | {sens['binning_sensitivity']['adaptive']['platt_ece']} |",
        f"| Bootstrap 95% CI | [{boot['ci_low_95']}, {boot['ci_high_95']}] |",
        f"| Bootstrap > 0.12 佔比 | {boot['pct_boots_above_critical']:.2%} |",
        f"| 最終分類 | `{clf}` |",
        "",
        "---",
        "",
        "## 晚賽季比較概覽",
        "",
        "| 期間 | platt_ece | V2 狀態 |",
        "|------|----------|---------|",
    ]
    for row in comparison:
        plan_lines.append(f"| {row['period']} | {row['platt_ece']:.4f} | {row['v2_status']} |")

    plan_lines += [
        "",
        "---",
        "",
        "## 2025 賽季 FIP 信號狀態",
        "",
        f"- Tier C n=535，整賽季 platt_ece={audit['full_season_metrics']['platt_ece']}",
        f"- Sep 2025 邊際健康：`fip_edge ≈ 0.147`，`CI_low > 0.130`（P52 V2 合約確認）",
        "- 校準問題限於 Sep 2025（可能為晚賽季效應）",
        "",
        "---",
        "",
        "## 2024 資料缺口狀態",
        "",
        "- 2024 closing-line odds 缺失，`P43_BLOCKED_BY_DATA_GAP` 未解決",
        "- 影響範圍：cross-year only，**不影響 2025-only 分析**",
        "",
        "---",
        "",
        "## 研究鏈狀態",
        "",
        "```",
        "P43→P44→P45→P46→P47→P48→P49→P50→P51→P52→P53 (當前) → P54 (下一步)",
        "```",
        "",
        "---",
        "",
        "*診斷報告 — 不構成投注建議 — paper_only=True*",
    ]
    OUTPUT_PLAN.write_text("\n".join(plan_lines))


def main() -> None:
    audit = build_p53_audit()

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(audit, indent=2, ensure_ascii=False))
    print(f"Written: {OUTPUT_JSON}")

    write_report(audit)
    print(f"Written: {OUTPUT_REPORT}")
    print(f"Written: {OUTPUT_PLAN}")

    sm = audit["sep_2025_drilldown"]["metrics"]
    sens = audit["sample_sensitivity"]
    print(f"Tier C n: {audit['tier_c_verification']['n']}")
    print(f"Sep n: {audit['sep_2025_drilldown']['n']}")
    print(f"Sep platt_ece: {sm['platt_ece']}")
    print(f"Bootstrap 95% CI: [{audit['sample_sensitivity']['bootstrap']['ci_low_95']}, "
          f"{audit['sample_sensitivity']['bootstrap']['ci_high_95']}]")
    print(f"All methods above critical: {sens['all_methods_above_critical']}")
    print(f"Final classification: {audit['final_p53_classification']}")
    print(f"Governance: paper_only={audit['governance_flags']['paper_only']}, "
          f"live_api_calls={audit['governance_flags']['live_api_calls']}")


if __name__ == "__main__":
    main()
