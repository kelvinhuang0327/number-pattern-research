"""Phase 69 — Calibration Objective Redesign Counterfactual with OOF / PIT-safe Validation

DIAGNOSTIC ONLY.  CANDIDATE_PATCH_CREATED = False.  PRODUCTION_MODIFIED = False.
ALPHA_MODIFIED = False.  PREDICTION_JSONL_OVERWRITTEN = False.  ALPHA = 0.40 (FROZEN).

Evaluates whether calibration objective redesign / probability shaping removal is
worth advancing to Phase 70 by running paper-only counterfactuals with strict
Out-of-Fold (OOF) / PIT-safe validation.

COUNTERFACTUALS (all paper-only, no production code modified):
  1. original_baseline       — existing model_home_prob unchanged
  2. remove_logit_sharpening — reverse logit/0.85 sharpening from stacking_model.py
  3. remove_away_damping     — approximate reverse of away_wp*0.9 damping
  4. remove_both             — reverse both sharpening and damping
  5. oof_isotonic            — OOF isotonic calibration (train: windows 1-3, eval: 4-5)
  6. oof_platt               — OOF Platt scaling (train: windows 1-3, eval: 4-5)
  7. confidence_band_abstention — diagnostic: which bands drag down Brier/ECE/BSS

OOF SPLIT (PIT-SAFE):
  calib_train: split_id in {window_1, window_2, window_3}  (n≈1215, Apr–Jul 2025)
  calib_eval:  split_id in {window_4, window_5}            (n≈810,  Jul–Sep 2025)
  Train windows are strictly earlier in time than eval windows.

PHASE CHAIN:
  Phase 68 gate: CALIBRATION_OBJECTIVE_REDESIGN_PROMISING
  Phase 69 gate: one of 7 allowed values (see GATE constants)

SAFETY CONSTANTS (FROZEN, DO NOT MODIFY):
  CANDIDATE_PATCH_CREATED        = False
  PRODUCTION_MODIFIED            = False
  ALPHA_MODIFIED                 = False
  DIAGNOSTIC_ONLY                = True
  PREDICTION_JSONL_OVERWRITTEN   = False
  IN_SAMPLE_FIT_AND_EVALUATE     = False
  PIT_SAFE_VALIDATION            = True
  ALPHA                          = 0.40
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# sklearn for OOF calibration (isotonic + Platt)
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

# ═══════════════════════════════════════════════════════════════════
# SAFETY CONSTANTS — FROZEN, DO NOT MODIFY
# ═══════════════════════════════════════════════════════════════════
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
ALPHA_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
PREDICTION_JSONL_OVERWRITTEN: bool = False
IN_SAMPLE_FIT_AND_EVALUATE: bool = False
PIT_SAFE_VALIDATION: bool = True
ALPHA: float = 0.40

# ═══════════════════════════════════════════════════════════════════
# PHASE IDENTITY
# ═══════════════════════════════════════════════════════════════════
PHASE_VERSION: str = "phase69_calibration_objective_redesign_counterfactual_v1"
COMPLETION_MARKER: str = "PHASE_69_CALIBRATION_OBJECTIVE_REDESIGN_COUNTERFACTUAL_VERIFIED"

# ═══════════════════════════════════════════════════════════════════
# GATE CONSTANTS
# ═══════════════════════════════════════════════════════════════════
CALIBRATION_OBJECTIVE_PATCH_PROMISING: str = "CALIBRATION_OBJECTIVE_PATCH_PROMISING"
PROBABILITY_SHAPING_REMOVAL_PROMISING: str = "PROBABILITY_SHAPING_REMOVAL_PROMISING"
ENSEMBLE_WEIGHTING_REPAIR_PROMISING: str = "ENSEMBLE_WEIGHTING_REPAIR_PROMISING"
ABSTENTION_GUARD_PROMISING: str = "ABSTENTION_GUARD_PROMISING"
OVERFIT_RISK: str = "OVERFIT_RISK"
DATA_LIMITED: str = "DATA_LIMITED"
CALIBRATION_OBJECTIVE_NOT_PROMISING: str = "CALIBRATION_OBJECTIVE_NOT_PROMISING"

_VALID_GATES: frozenset[str] = frozenset({
    CALIBRATION_OBJECTIVE_PATCH_PROMISING,
    PROBABILITY_SHAPING_REMOVAL_PROMISING,
    ENSEMBLE_WEIGHTING_REPAIR_PROMISING,
    ABSTENTION_GUARD_PROMISING,
    OVERFIT_RISK,
    DATA_LIMITED,
    CALIBRATION_OBJECTIVE_NOT_PROMISING,
})

# ═══════════════════════════════════════════════════════════════════
# PREVIOUS PHASE GATE ANCHORS (FROZEN)
# ═══════════════════════════════════════════════════════════════════
PHASE68_GATE_ANCHOR: str = "CALIBRATION_OBJECTIVE_REDESIGN_PROMISING"
PHASE68_VERSION: str = "phase68_model_architecture_ensemble_failure_audit_v1"
PHASE67_GATE_ANCHOR: str = "OVERFIT_RISK"
PHASE67_VERSION: str = "phase67_context_failure_attribution_v1"

# ═══════════════════════════════════════════════════════════════════
# STACKING MODEL SHAPING CONSTANTS (from stacking_model.py — DO NOT EDIT THERE)
# These are read-only copies for paper-only reversal.
# ═══════════════════════════════════════════════════════════════════
_LOGIT_SHARPENING_FACTOR: float = 0.85   # stacking_model.py: logit / 0.85
_AWAY_DAMPING_FACTOR: float = 0.90       # stacking_model.py: away_wp * 0.9
_AWAY_DAMPING_THRESHOLD: float = 0.30    # stacking_model.py: if away_wp < 0.3

# ═══════════════════════════════════════════════════════════════════
# OOF SPLIT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════
_OOF_TRAIN_WINDOWS: frozenset[str] = frozenset({"window_1", "window_2", "window_3"})
_OOF_EVAL_WINDOWS: frozenset[str] = frozenset({"window_4", "window_5"})
_MIN_CALIB_TRAIN_N: int = 100   # minimum calibration training rows
_MIN_CALIB_EVAL_N: int = 100    # minimum calibration eval rows

# ═══════════════════════════════════════════════════════════════════
# ANALYSIS THRESHOLDS
# ═══════════════════════════════════════════════════════════════════
_MIN_SEGMENT_N: int = 20
_MIN_BUCKET_N: int = 15
_BOOTSTRAP_N: int = 1000

_HEAVY_FAV_THRESHOLD: float = 0.70
_HIGH_CONF_THRESHOLD: float = 0.75
_EXTREME_FAV_THRESHOLD: float = 0.80
_PHASE45_FAIL_MIN_FAV: float = 0.60

# Meaningful improvement thresholds
_MIN_ECE_IMPROVEMENT: float = 0.002    # ECE must improve by >= 0.2pp to be meaningful
_MIN_BSS_IMPROVEMENT: float = 0.001    # BSS must improve by >= 0.1pp to be meaningful
_MIN_BRIER_IMPROVEMENT: float = 0.001  # Brier must improve by >= 0.1pp

# Negative control overfit threshold
_OVERFIT_GAP_THRESHOLD: float = 0.02

# Calibration residual thresholds
_OVERCONF_RESIDUAL_THRESHOLD: float = 0.04
_UNDERCONF_RESIDUAL_THRESHOLD: float = 0.04

# Bootstrap CI stability check: 95% CI must not clearly cross zero
# (If CI lower bound < 0 and improvement is claimed, flag as unstable)
_CI_STABILITY_THRESHOLD: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CounterfactualMetrics:
    """Metrics for one counterfactual method on one segment."""
    method: str
    segment: str
    n: int
    brier: float
    bss_vs_market: float       # BSS(method, market)
    bss_vs_original: float     # BSS(method, original_baseline)
    ece: float
    brier_delta_vs_original: float  # method.brier - original.brier (negative = better)
    ece_delta_vs_original: float    # method.ece - original.ece (negative = better)
    data_limited: bool


@dataclass
class CalibrationBandResult:
    """Calibration residual for one probability band under one method."""
    method: str
    band_label: str
    lo: float
    hi: float
    n: int
    pred: float               # mean predicted fav_prob for this method
    actual_win_rate: float
    residual: float           # pred - actual_win_rate
    is_overconfident: bool
    is_underconfident: bool
    data_limited: bool


@dataclass
class BootstrapCI:
    """Bootstrap confidence interval for a delta metric."""
    metric: str           # e.g. "brier_delta", "bss_delta", "ece_delta"
    method: str           # counterfactual method name
    segment: str
    n: int
    n_boot: int
    observed: float       # observed delta (method - original)
    ci_lower: float       # 2.5th percentile
    ci_upper: float       # 97.5th percentile
    ci_excludes_zero: bool  # True if CI fully < 0 (improvement) or fully > 0 (degradation)
    ci_stable: bool         # False if CI is wide or crosses zero unexpectedly
    data_limited: bool


@dataclass
class NegativeControlResult:
    """Negative control result for a specific test."""
    control_name: str
    description: str
    real_improvement: float    # observed improvement (lower brier = positive improvement)
    null_improvement_mean: float
    null_improvement_std: float
    signal_gap: float          # real - null_mean
    overfit_risk: bool         # signal_gap < threshold
    n_permutations: int


@dataclass
class AbstentionDiagnostic:
    """Confidence band abstention diagnostic — which bands drag down metrics."""
    band_label: str
    lo: float
    hi: float
    n: int
    brier: float
    bss_vs_market: float
    ece: float
    market_brier: float
    model_beats_market: bool      # model brier < market brier
    blend_beats_market: bool      # blend brier < market brier
    abstention_recommended: bool  # model significantly underperforms market
    data_limited: bool


@dataclass
class OofSplitInfo:
    """OOF calibration split metadata."""
    train_windows: list[str]
    eval_windows: list[str]
    n_train: int
    n_eval: int
    train_date_start: str
    train_date_end: str
    eval_date_start: str
    eval_date_end: str
    pit_safe: bool          # always True: eval strictly after train


@dataclass
class Phase69Report:
    """Full Phase 69 calibration objective redesign counterfactual report."""
    phase_version: str
    completion_marker: str
    generated_at: str
    data_path: str

    # Safety constants (all verified at runtime)
    candidate_patch_created: bool
    production_modified: bool
    alpha_modified: bool
    diagnostic_only: bool
    prediction_jsonl_overwritten: bool
    in_sample_fit_and_evaluate: bool
    pit_safe_validation: bool
    alpha: float

    # Phase anchors
    phase68_gate_anchor: str
    phase67_gate_anchor: str

    # Data summary
    n_total: int
    n_train: int
    n_eval: int
    feature_version: str

    # OOF split metadata
    oof_split: OofSplitInfo

    # Counterfactual metrics — list of (method × segment) results
    counterfactual_metrics: list[CounterfactualMetrics]

    # Calibration band results per method (eval set only)
    calibration_bands: list[CalibrationBandResult]

    # Bootstrap CIs
    bootstrap_cis: list[BootstrapCI]

    # Negative controls
    negative_controls: list[NegativeControlResult]

    # Abstention diagnostic
    abstention_diagnostics: list[AbstentionDiagnostic]

    # Gate decision
    gate: str
    gate_rationale: str
    phase70_recommendation: str
    risk_notes: list[str]

    # Summary flags
    oof_calibration_improves_ece: bool
    oof_calibration_improves_bss: bool
    shaping_removal_improves_heavy_fav: bool
    negative_controls_clear: bool
    bootstrap_ci_stable: bool
    worth_phase70: bool


# ═══════════════════════════════════════════════════════════════════
# CORE MATH
# ═══════════════════════════════════════════════════════════════════

def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def _logit_fn(p: float) -> float:
    """Logit function with clipping."""
    p = max(1e-9, min(1.0 - 1e-9, p))
    return math.log(p / (1.0 - p))


def _brier(probs: list[float], labels: list[float]) -> float:
    if not probs:
        return 0.0
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(probs)


def _bss_direct(model_brier: float, ref_brier: float) -> float:
    """BSS = 1 - model_brier / ref_brier.  Positive = model beats reference."""
    if ref_brier <= 0.0:
        return 0.0
    return 1.0 - model_brier / ref_brier


def _ece(probs: list[float], labels: list[float], n_bins: int = 10) -> float:
    if not probs:
        return 0.0
    bins: list[list[tuple[float, float]]] = [[] for _ in range(n_bins)]
    for p, y in zip(probs, labels):
        idx = min(int(p * n_bins), n_bins - 1)
        bins[idx].append((p, y))
    total = len(probs)
    ece_val = 0.0
    for b in bins:
        if b:
            mp = sum(x for x, _ in b) / len(b)
            my = sum(y for _, y in b) / len(b)
            ece_val += (len(b) / total) * abs(mp - my)
    return ece_val


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _std(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))


def _percentile(vals: list[float], q: float) -> float:
    """Compute q-th percentile (0-100) of sorted vals."""
    if not vals:
        return 0.0
    sv = sorted(vals)
    n = len(sv)
    idx = (q / 100.0) * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sv[lo] * (1.0 - frac) + sv[hi] * frac


# ═══════════════════════════════════════════════════════════════════
# ROW ENRICHMENT (same as Phase 68, no production changes)
# ═══════════════════════════════════════════════════════════════════

def _enrich(rows: list[dict]) -> list[dict]:
    """Add derived blend / fav-side fields to each prediction row (in-place)."""
    for r in rows:
        blend = (1.0 - ALPHA) * r["model_home_prob"] + ALPHA * r["market_home_prob_no_vig"]
        r["_blend"] = blend
        r["_fav_is_home"] = blend >= 0.5
        r["_fav_prob"] = max(blend, 1.0 - blend)
        r["_fav_win"] = float(r["home_win"]) if r["_fav_is_home"] else 1.0 - float(r["home_win"])
        r["_model_fav_prob"] = max(r["model_home_prob"], 1.0 - r["model_home_prob"])
        r["_mkt_fav_prob"] = max(
            r["market_home_prob_no_vig"], 1.0 - r["market_home_prob_no_vig"]
        )
    return rows


# ═══════════════════════════════════════════════════════════════════
# PAPER-ONLY PROBABILITY SHAPING REVERSALS
# ═══════════════════════════════════════════════════════════════════

def _reverse_logit_sharpening(model_home_prob: float) -> float:
    """Paper-only reversal of logit/0.85 sharpening from stacking_model.py.

    stacking_model.py applies:
        logit = log(away_wp / (1 - away_wp))
        away_wp_calibrated = sigmoid(logit / 0.85)

    To reverse: given away_wp_calibrated, recover away_wp by:
        logit_sharpened = logit(away_wp_calibrated)  [= logit / 0.85]
        logit_original  = logit_sharpened * 0.85
        away_desharpened = sigmoid(logit_original)

    Returns: home_prob after removing the /0.85 sharpening.
    This is a paper-only approximation — does not modify production code.
    """
    away_calibrated = max(1e-9, min(1.0 - 1e-9, 1.0 - model_home_prob))
    # away_calibrated = sigmoid(logit / 0.85), so logit(away_calibrated) = logit/0.85
    logit_sharpened = _logit_fn(away_calibrated)
    # Reverse: original logit = logit_sharpened * 0.85
    logit_original = logit_sharpened * _LOGIT_SHARPENING_FACTOR
    away_desharpened = _sigmoid(logit_original)
    return 1.0 - away_desharpened


def _reverse_away_damping_only(model_home_prob: float) -> float:
    """Paper-only approximate reversal of away_wp*0.9 damping, keeping sharpening.

    stacking_model.py applies (before logit):
        if away_wp < 0.30:  away_wp = away_wp * 0.90

    Strategy:
      1. Reverse sharpening to get pre-sharpening away_wp.
      2. If pre_sharp_away_wp < damping_threshold * damping_factor (≈0.27),
         the damping was likely applied → divide by 0.9 to recover original.
      3. Re-apply logit sharpening to the un-damped value.

    This is an approximation because we don't have the exact pre-steam away_wp.
    Returns: home_prob after removing the away_wp*0.9 artifact only.
    """
    away_calibrated = max(1e-9, min(1.0 - 1e-9, 1.0 - model_home_prob))
    logit_sharpened = _logit_fn(away_calibrated)
    logit_original = logit_sharpened * _LOGIT_SHARPENING_FACTOR
    pre_sharp_away_wp = _sigmoid(logit_original)

    # Approximate reversal of damping: threshold is 0.3*0.9 = 0.27
    damping_applied_threshold = _AWAY_DAMPING_THRESHOLD * _AWAY_DAMPING_FACTOR
    if pre_sharp_away_wp < damping_applied_threshold:
        undamped_away_wp = pre_sharp_away_wp / _AWAY_DAMPING_FACTOR
    else:
        undamped_away_wp = pre_sharp_away_wp

    # Re-apply sharpening to the undamped value
    logit_undamped = _logit_fn(undamped_away_wp)
    away_resharpened = _sigmoid(logit_undamped / _LOGIT_SHARPENING_FACTOR)
    return 1.0 - away_resharpened


def _reverse_both(model_home_prob: float) -> float:
    """Paper-only reversal of both logit/0.85 sharpening and away_wp*0.9 damping.

    1. Reverse sharpening to get pre-sharpening away_wp.
    2. If damping was likely applied, reverse it.
    3. Do NOT re-apply sharpening.

    Returns: home_prob after removing both artifacts.
    """
    away_calibrated = max(1e-9, min(1.0 - 1e-9, 1.0 - model_home_prob))
    logit_sharpened = _logit_fn(away_calibrated)
    logit_original = logit_sharpened * _LOGIT_SHARPENING_FACTOR
    pre_sharp_away_wp = _sigmoid(logit_original)

    damping_applied_threshold = _AWAY_DAMPING_THRESHOLD * _AWAY_DAMPING_FACTOR
    if pre_sharp_away_wp < damping_applied_threshold:
        undamped_away_wp = pre_sharp_away_wp / _AWAY_DAMPING_FACTOR
    else:
        undamped_away_wp = pre_sharp_away_wp

    return 1.0 - undamped_away_wp


def _apply_counterfactual(row: dict, method: str) -> float:
    """Apply a counterfactual transform to model_home_prob. Returns modified home_prob."""
    p = row["model_home_prob"]
    if method == "original_baseline":
        return p
    elif method == "remove_logit_sharpening":
        return _reverse_logit_sharpening(p)
    elif method == "remove_away_damping":
        return _reverse_away_damping_only(p)
    elif method == "remove_both":
        return _reverse_both(p)
    else:
        raise ValueError(f"Unknown method for _apply_counterfactual: {method!r}")


def _counterfactual_fav_prob(row: dict, method: str) -> float:
    """Get the fav-side probability for a given counterfactual method."""
    if method in ("original_baseline", "remove_logit_sharpening",
                  "remove_away_damping", "remove_both"):
        home_prob = _apply_counterfactual(row, method)
        # Rebuild blend with counterfactual model_home_prob
        cf_blend = (1.0 - ALPHA) * home_prob + ALPHA * row["market_home_prob_no_vig"]
        return max(cf_blend, 1.0 - cf_blend)
    elif method in ("oof_isotonic", "oof_platt"):
        # Calibrated prob stored in row during OOF application
        return max(row[f"_{method}_fav_prob"], 1.0 - row[f"_{method}_fav_prob"])
    else:
        raise ValueError(f"Unknown method for _counterfactual_fav_prob: {method!r}")


# ═══════════════════════════════════════════════════════════════════
# OOF CALIBRATION (ISOTONIC + PLATT)
# ═══════════════════════════════════════════════════════════════════

def _fit_and_apply_oof_calibration(
    train_rows: list[dict],
    eval_rows: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Fit OOF calibration (isotonic + Platt) on train_rows, apply to eval_rows.

    PIT-safe: train_rows must be strictly earlier in time than eval_rows.
    Does NOT modify train_rows.

    Returns: (train_rows_unchanged, eval_rows_with_cf_probs)
    Each eval row gets two new keys:
      _oof_isotonic_home_prob  — isotonic calibrated home_prob
      _oof_platt_home_prob     — Platt-scaled home_prob
      _oof_isotonic_fav_prob   — isotonic calibrated fav_prob (on blend side)
      _oof_platt_fav_prob      — Platt-scaled fav_prob (on blend side)
    """
    # Training data: raw model_home_prob → actual home_win
    X_train = [[r["model_home_prob"]] for r in train_rows]
    y_train = [float(r["home_win"]) for r in train_rows]
    model_probs_train = [r["model_home_prob"] for r in train_rows]
    labels_train = y_train

    # Fit isotonic regression on model_home_prob
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(model_probs_train, labels_train)

    # Fit Platt scaling (logistic regression) on model_home_prob
    platt = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
    platt.fit(X_train, y_train)

    # Apply to eval rows (paper-only, no production modification)
    eval_rows_out = []
    for r in eval_rows:
        r = dict(r)  # shallow copy to avoid mutating originals
        p = r["model_home_prob"]
        mkt = r["market_home_prob_no_vig"]

        # Isotonic calibrated home_prob
        iso_home = float(iso.predict([p])[0])
        iso_home = max(1e-6, min(1.0 - 1e-6, iso_home))
        iso_blend = (1.0 - ALPHA) * iso_home + ALPHA * mkt
        r["_oof_isotonic_home_prob"] = iso_home
        r["_oof_isotonic_fav_prob"] = max(iso_blend, 1.0 - iso_blend)

        # Platt calibrated home_prob
        platt_home = float(platt.predict_proba([[p]])[0, 1])
        platt_home = max(1e-6, min(1.0 - 1e-6, platt_home))
        platt_blend = (1.0 - ALPHA) * platt_home + ALPHA * mkt
        r["_oof_platt_home_prob"] = platt_home
        r["_oof_platt_fav_prob"] = max(platt_blend, 1.0 - platt_blend)

        eval_rows_out.append(r)

    return train_rows, eval_rows_out


# ═══════════════════════════════════════════════════════════════════
# SEGMENT COMPUTATIONS
# ═══════════════════════════════════════════════════════════════════

_METHODS: list[str] = [
    "original_baseline",
    "remove_logit_sharpening",
    "remove_away_damping",
    "remove_both",
    "oof_isotonic",
    "oof_platt",
]

_SEGMENT_DEFS: list[tuple[str, str, float, float]] = [
    # (name, key, lo, hi)
    ("all_games",          "_fav_prob",       0.50, 1.01),
    ("heavy_favorite",     "_fav_prob",       0.70, 1.01),
    ("high_confidence",    "_fav_prob",       0.75, 1.01),
    ("extreme_favorite",   "_fav_prob",       0.80, 1.01),
    ("phase45_failure",    "_fav_prob",       0.60, 1.01),   # fav_prob>=0.60 AND fav_win==0
    ("model_band_50_60",   "_model_fav_prob", 0.50, 0.60),
    ("model_band_60_70",   "_model_fav_prob", 0.60, 0.70),
    ("model_band_70_80",   "_model_fav_prob", 0.70, 0.80),
    ("model_band_80_90",   "_model_fav_prob", 0.80, 0.90),
    ("model_band_90_100",  "_model_fav_prob", 0.90, 1.01),
]


def _filter_segment(rows: list[dict], seg_name: str, seg_key: str,
                    lo: float, hi: float) -> list[dict]:
    """Filter rows for a segment definition, with special Phase45 logic."""
    filtered = [r for r in rows if lo <= r[seg_key] < hi]
    if seg_name == "phase45_failure":
        # Phase 45 failure: games where we favoured a team but it lost
        filtered = [r for r in filtered if r["_fav_win"] == 0.0]
    return filtered


def _get_cf_fav_probs(rows: list[dict], method: str) -> list[float]:
    """Get counterfactual fav_prob list for a given method."""
    result = []
    for r in rows:
        if method in ("oof_isotonic", "oof_platt"):
            key = f"_oof_{method.split('oof_')[1]}_fav_prob"
            prob = r.get(key)
            if prob is None:
                # Not in eval set (train rows don't have OOF keys) — skip
                result.append(r["_fav_prob"])  # fallback to original
                continue
            result.append(max(prob, 1.0 - prob))
        else:
            home_p = _apply_counterfactual(r, method)
            cf_blend = (1.0 - ALPHA) * home_p + ALPHA * r["market_home_prob_no_vig"]
            result.append(max(cf_blend, 1.0 - cf_blend))
    return result


def _compute_counterfactual_metrics(
    eval_rows: list[dict],
    original_brier_by_segment: dict[str, float],
) -> list[CounterfactualMetrics]:
    """Compute metrics for every (method × segment) combination."""
    results: list[CounterfactualMetrics] = []

    for method in _METHODS:
        for seg_name, seg_key, lo, hi in _SEGMENT_DEFS:
            seg_rows = _filter_segment(eval_rows, seg_name, seg_key, lo, hi)
            n = len(seg_rows)
            data_limited = n < _MIN_SEGMENT_N

            if n == 0:
                results.append(CounterfactualMetrics(
                    method=method, segment=seg_name, n=0,
                    brier=0.0, bss_vs_market=0.0, bss_vs_original=0.0,
                    ece=0.0, brier_delta_vs_original=0.0, ece_delta_vs_original=0.0,
                    data_limited=True,
                ))
                continue

            cf_fps = _get_cf_fav_probs(seg_rows, method)
            fav_wins = [r["_fav_win"] for r in seg_rows]
            mkt_fps = [r["_mkt_fav_prob"] for r in seg_rows]

            b = _brier(cf_fps, fav_wins)
            mkt_b = _brier(mkt_fps, fav_wins)
            bss_mkt = _bss_direct(b, mkt_b)
            e = _ece(cf_fps, fav_wins)

            orig_b = original_brier_by_segment.get(seg_name, b)
            orig_e_key = f"{seg_name}_ece"
            orig_e = original_brier_by_segment.get(orig_e_key, e)
            bss_orig = _bss_direct(b, orig_b) if orig_b > 0 else 0.0

            results.append(CounterfactualMetrics(
                method=method,
                segment=seg_name,
                n=n,
                brier=round(b, 6),
                bss_vs_market=round(bss_mkt, 6),
                bss_vs_original=round(bss_orig, 6),
                ece=round(e, 6),
                brier_delta_vs_original=round(b - orig_b, 6),
                ece_delta_vs_original=round(e - orig_e, 6),
                data_limited=data_limited,
            ))

    return results


# ═══════════════════════════════════════════════════════════════════
# CALIBRATION BANDS (PER METHOD)
# ═══════════════════════════════════════════════════════════════════

_CALIB_BAND_DEFS: list[tuple[str, float, float]] = [
    ("0.50-0.55", 0.50, 0.55),
    ("0.55-0.60", 0.55, 0.60),
    ("0.60-0.65", 0.60, 0.65),
    ("0.65-0.70", 0.65, 0.70),
    ("0.70-0.75", 0.70, 0.75),
    ("0.75+",     0.75, 1.01),
]


def _compute_calibration_bands_for_method(
    eval_rows: list[dict], method: str
) -> list[CalibrationBandResult]:
    """Compute calibration residual per band for a given counterfactual method."""
    results: list[CalibrationBandResult] = []
    for label, lo, hi in _CALIB_BAND_DEFS:
        # Band rows defined by blend_fav_prob (original, for consistent banding)
        seg = [r for r in eval_rows if lo <= r["_fav_prob"] < hi]
        n = len(seg)
        if n == 0:
            continue
        cf_fps = _get_cf_fav_probs(seg, method)
        fav_wins = [r["_fav_win"] for r in seg]
        pred = _mean(cf_fps)
        actual = _mean(fav_wins)
        residual = pred - actual
        results.append(CalibrationBandResult(
            method=method,
            band_label=label,
            lo=lo, hi=hi, n=n,
            pred=round(pred, 6),
            actual_win_rate=round(actual, 6),
            residual=round(residual, 6),
            is_overconfident=(n >= _MIN_BUCKET_N and residual > _OVERCONF_RESIDUAL_THRESHOLD),
            is_underconfident=(n >= _MIN_BUCKET_N and residual < -_UNDERCONF_RESIDUAL_THRESHOLD),
            data_limited=n < _MIN_BUCKET_N,
        ))
    return results


# ═══════════════════════════════════════════════════════════════════
# BOOTSTRAP CI
# ═══════════════════════════════════════════════════════════════════

def _bootstrap_brier_delta(
    eval_rows: list[dict],
    cf_method: str,
    seg_name: str,
    seg_key: str,
    lo: float,
    hi: float,
    n_boot: int,
    rng: random.Random,
) -> BootstrapCI:
    """Bootstrap CI for Brier delta (cf_method - original_baseline) on a segment."""
    seg_rows = _filter_segment(eval_rows, seg_name, seg_key, lo, hi)
    n = len(seg_rows)
    data_limited = n < _MIN_SEGMENT_N

    if n < 10:
        return BootstrapCI(
            metric="brier_delta", method=cf_method, segment=seg_name,
            n=n, n_boot=0, observed=0.0, ci_lower=0.0, ci_upper=0.0,
            ci_excludes_zero=False, ci_stable=False, data_limited=True,
        )

    orig_fps = _get_cf_fav_probs(seg_rows, "original_baseline")
    cf_fps = _get_cf_fav_probs(seg_rows, cf_method)
    fav_wins = [r["_fav_win"] for r in seg_rows]

    observed_delta = _brier(cf_fps, fav_wins) - _brier(orig_fps, fav_wins)

    # Bootstrap
    boot_deltas: list[float] = []
    pairs = list(zip(orig_fps, cf_fps, fav_wins))
    for _ in range(n_boot):
        sample = [pairs[rng.randint(0, n - 1)] for _ in range(n)]
        o_fps_s = [x[0] for x in sample]
        c_fps_s = [x[1] for x in sample]
        w_s = [x[2] for x in sample]
        boot_deltas.append(_brier(c_fps_s, w_s) - _brier(o_fps_s, w_s))

    ci_lower = _percentile(boot_deltas, 2.5)
    ci_upper = _percentile(boot_deltas, 97.5)
    ci_excludes_zero = ci_upper < 0.0 or ci_lower > 0.0
    ci_stable = not data_limited and (ci_upper - ci_lower) < 0.05

    return BootstrapCI(
        metric="brier_delta",
        method=cf_method,
        segment=seg_name,
        n=n,
        n_boot=n_boot,
        observed=round(observed_delta, 6),
        ci_lower=round(ci_lower, 6),
        ci_upper=round(ci_upper, 6),
        ci_excludes_zero=ci_excludes_zero,
        ci_stable=ci_stable,
        data_limited=data_limited,
    )


# ═══════════════════════════════════════════════════════════════════
# NEGATIVE CONTROLS
# ═══════════════════════════════════════════════════════════════════

def _run_negative_controls(
    eval_rows: list[dict],
    best_method: str,
    n_boot: int,
    rng: random.Random,
) -> list[NegativeControlResult]:
    """Three negative controls to verify signal authenticity."""
    controls: list[NegativeControlResult] = []
    fav_wins = [r["_fav_win"] for r in eval_rows]
    orig_fps = [r["_fav_prob"] for r in eval_rows]
    cf_fps = _get_cf_fav_probs(eval_rows, best_method)
    orig_b = _brier(orig_fps, fav_wins)
    cf_b = _brier(cf_fps, fav_wins)
    real_improvement = orig_b - cf_b  # positive = method improves over baseline

    # ── Control 1: shuffled_probability_band ─────────────────────────
    # Shuffle fav_prob across all rows; if improvement survives shuffling → overfit
    shuffled_improvements: list[float] = []
    fps_copy = cf_fps[:]
    orig_copy = orig_fps[:]
    for _ in range(n_boot):
        rng.shuffle(fps_copy)
        rng.shuffle(orig_copy)
        b_null = _brier(fps_copy, fav_wins)
        b_orig_null = _brier(orig_copy, fav_wins)
        shuffled_improvements.append(b_orig_null - b_null)
    null_mean_1 = _mean(shuffled_improvements)
    null_std_1 = _std(shuffled_improvements)
    gap_1 = real_improvement - null_mean_1
    controls.append(NegativeControlResult(
        control_name="shuffled_probability_band",
        description=(
            "Shuffle fav_prob labels. Improvement should collapse to noise "
            "if real improvement reflects genuine calibration signal."
        ),
        real_improvement=round(real_improvement, 6),
        null_improvement_mean=round(null_mean_1, 6),
        null_improvement_std=round(null_std_1, 6),
        signal_gap=round(gap_1, 6),
        overfit_risk=gap_1 < _OVERFIT_GAP_THRESHOLD,
        n_permutations=n_boot,
    ))

    # ── Control 2: random_confidence_assignment ───────────────────────
    # Assign random confidence values; check if "improvement" survives
    random_improvements: list[float] = []
    for _ in range(n_boot):
        rand_fps = [rng.uniform(0.5, 1.0) for _ in range(len(eval_rows))]
        rand_orig = [rng.uniform(0.5, 1.0) for _ in range(len(eval_rows))]
        b_rand = _brier(rand_fps, fav_wins)
        b_rand_orig = _brier(rand_orig, fav_wins)
        random_improvements.append(b_rand_orig - b_rand)
    null_mean_2 = _mean(random_improvements)
    null_std_2 = _std(random_improvements)
    gap_2 = real_improvement - null_mean_2
    controls.append(NegativeControlResult(
        control_name="random_confidence_assignment",
        description=(
            "Assign random confidence values. Method improvement should not match "
            "random assignment improvement."
        ),
        real_improvement=round(real_improvement, 6),
        null_improvement_mean=round(null_mean_2, 6),
        null_improvement_std=round(null_std_2, 6),
        signal_gap=round(gap_2, 6),
        overfit_risk=gap_2 < _OVERFIT_GAP_THRESHOLD,
        n_permutations=n_boot,
    ))

    # ── Control 3: irrelevant_bucket_split ────────────────────────────
    # Odd/even game index split — irrelevant dimension, should show no improvement
    even_rows = [r for i, r in enumerate(eval_rows) if i % 2 == 0]
    odd_rows = [r for i, r in enumerate(eval_rows) if i % 2 == 1]
    if even_rows and odd_rows:
        even_cf = _get_cf_fav_probs(even_rows, best_method)
        even_orig = _get_cf_fav_probs(even_rows, "original_baseline")
        even_wins = [r["_fav_win"] for r in even_rows]
        odd_cf = _get_cf_fav_probs(odd_rows, best_method)
        odd_orig = _get_cf_fav_probs(odd_rows, "original_baseline")
        odd_wins = [r["_fav_win"] for r in odd_rows]
        even_imp = _brier(even_orig, even_wins) - _brier(even_cf, even_wins)
        odd_imp = _brier(odd_orig, odd_wins) - _brier(odd_cf, odd_wins)
        real_parity_delta = abs(even_imp - odd_imp)

        parity_deltas: list[float] = []
        all_rows_copy = eval_rows[:]
        for _ in range(n_boot):
            rng.shuffle(all_rows_copy)
            half = len(all_rows_copy) // 2
            a_rows = all_rows_copy[:half]
            b_rows = all_rows_copy[half:]
            a_cf = _get_cf_fav_probs(a_rows, best_method)
            a_orig = _get_cf_fav_probs(a_rows, "original_baseline")
            a_wins = [r["_fav_win"] for r in a_rows]
            b_cf = _get_cf_fav_probs(b_rows, best_method)
            b_orig = _get_cf_fav_probs(b_rows, "original_baseline")
            b_wins = [r["_fav_win"] for r in b_rows]
            a_imp = _brier(a_orig, a_wins) - _brier(a_cf, a_wins)
            b_imp = _brier(b_orig, b_wins) - _brier(b_cf, b_wins)
            parity_deltas.append(abs(a_imp - b_imp))

        null_mean_3 = _mean(parity_deltas)
        null_std_3 = _std(parity_deltas)
        gap_3 = real_parity_delta - null_mean_3
        overfit_3 = gap_3 > _OVERFIT_GAP_THRESHOLD * 3
        controls.append(NegativeControlResult(
            control_name="irrelevant_bucket_split",
            description=(
                "Odd/even game index split — irrelevant dimension. "
                "Improvement parity between splits should be consistent with null."
            ),
            real_improvement=round(real_parity_delta, 6),
            null_improvement_mean=round(null_mean_3, 6),
            null_improvement_std=round(null_std_3, 6),
            signal_gap=round(gap_3, 6),
            overfit_risk=overfit_3,
            n_permutations=n_boot,
        ))
    else:
        controls.append(NegativeControlResult(
            control_name="irrelevant_bucket_split",
            description="Skipped — insufficient rows for odd/even split.",
            real_improvement=0.0, null_improvement_mean=0.0, null_improvement_std=0.0,
            signal_gap=1.0, overfit_risk=False, n_permutations=0,
        ))

    return controls


# ═══════════════════════════════════════════════════════════════════
# ABSTENTION DIAGNOSTIC
# ═══════════════════════════════════════════════════════════════════

def _compute_abstention_diagnostics(eval_rows: list[dict]) -> list[AbstentionDiagnostic]:
    """Identify which confidence bands drag down metrics (diagnostic only, no patch)."""
    diagnostics: list[AbstentionDiagnostic] = []
    for label, lo, hi in _CALIB_BAND_DEFS:
        seg = [r for r in eval_rows if lo <= r["_fav_prob"] < hi]
        n = len(seg)
        if n == 0:
            continue
        fav_wins = [r["_fav_win"] for r in seg]
        blend_fps = [r["_fav_prob"] for r in seg]
        model_fps = [r["_model_fav_prob"] for r in seg]
        mkt_fps = [r["_mkt_fav_prob"] for r in seg]

        model_b = _brier(model_fps, fav_wins)
        blend_b = _brier(blend_fps, fav_wins)
        mkt_b = _brier(mkt_fps, fav_wins)
        bss_mkt = _bss_direct(blend_b, mkt_b)
        ece_b = _ece(blend_fps, fav_wins)
        data_limited = n < _MIN_BUCKET_N

        diagnostics.append(AbstentionDiagnostic(
            band_label=label,
            lo=lo, hi=hi, n=n,
            brier=round(blend_b, 6),
            bss_vs_market=round(bss_mkt, 6),
            ece=round(ece_b, 6),
            market_brier=round(mkt_b, 6),
            model_beats_market=model_b < mkt_b,
            blend_beats_market=blend_b < mkt_b,
            abstention_recommended=(
                not data_limited and mkt_b < blend_b and bss_mkt < -0.01
            ),
            data_limited=data_limited,
        ))
    return diagnostics


# ═══════════════════════════════════════════════════════════════════
# GATE DETERMINATION
# ═══════════════════════════════════════════════════════════════════

def _determine_gate(
    cf_metrics: list[CounterfactualMetrics],
    bootstrap_cis: list[BootstrapCI],
    negative_controls: list[NegativeControlResult],
    abstention_diagnostics: list[AbstentionDiagnostic],
    oof_split: OofSplitInfo,
    risk_notes: list[str],
) -> tuple[str, str, str, bool]:
    """Determine Phase 69 gate.

    Returns: (gate, rationale, phase70_recommendation, worth_phase70).

    Gate priority:
      1. DATA_LIMITED — if OOF eval set is too small
      2. OVERFIT_RISK — if negative controls also show improvement
      3. CALIBRATION_OBJECTIVE_PATCH_PROMISING — OOF calibration clearly helps
      4. PROBABILITY_SHAPING_REMOVAL_PROMISING — shaping removal clearly helps
      5. ENSEMBLE_WEIGHTING_REPAIR_PROMISING — ensemble issues dominate
      6. ABSTENTION_GUARD_PROMISING — band abstention diagnostic is clear
      7. CALIBRATION_OBJECTIVE_NOT_PROMISING — nothing works
    """
    # ── Data limited check ────────────────────────────────────────
    if oof_split.n_eval < _MIN_CALIB_EVAL_N:
        return (
            DATA_LIMITED,
            f"OOF eval set too small: n_eval={oof_split.n_eval} < {_MIN_CALIB_EVAL_N}. "
            "Cannot make reliable Phase 70 recommendations.",
            "Gather more evaluation data before proceeding to Phase 70.",
            False,
        )

    # Helper: get all-games metric for a method
    def _get_all(method: str, seg: str = "all_games") -> CounterfactualMetrics | None:
        for m in cf_metrics:
            if m.method == method and m.segment == seg:
                return m
        return None

    def _get_heavy(method: str) -> CounterfactualMetrics | None:
        return _get_all(method, "heavy_favorite")

    orig_all = _get_all("original_baseline")
    orig_heavy = _get_heavy("original_baseline")

    # ── Negative control check ────────────────────────────────────
    # Find best OOF method improvement
    best_oof_improvement = 0.0
    for method in ("oof_isotonic", "oof_platt"):
        m = _get_all(method)
        if m and m.n > 0:
            imp = -(m.brier_delta_vs_original)  # positive = improvement
            best_oof_improvement = max(best_oof_improvement, imp)

    any_nc_overfit = any(nc.overfit_risk for nc in negative_controls)
    if any_nc_overfit and best_oof_improvement > 0.0:
        bad_ncs = [nc.control_name for nc in negative_controls if nc.overfit_risk]
        risk_notes.append(
            f"Negative controls also showing improvement: {bad_ncs}. "
            "OOF improvement may be spurious."
        )
        return (
            OVERFIT_RISK,
            f"Negative control overfit risk: {bad_ncs}. "
            f"Best OOF improvement={best_oof_improvement:.4f} but controls also improve. "
            "Cannot confirm genuine calibration signal.",
            "標記 OVERFIT_RISK。深入調查 bootstrap CI 穩定性後再決定 Phase 70。",
            False,
        )

    # ── Check OOF calibration improvement ────────────────────────
    oof_all_games_ece_improves = False
    oof_heavy_fav_improves = False
    oof_all_games_bss_improves = False
    best_oof_method = ""
    best_oof_ece_delta = 0.0

    for method in ("oof_isotonic", "oof_platt"):
        m_all = _get_all(method)
        m_heavy = _get_heavy(method)
        if m_all and not m_all.data_limited:
            ece_delta = m_all.ece_delta_vs_original
            brier_delta = m_all.brier_delta_vs_original
            if ece_delta < -_MIN_ECE_IMPROVEMENT:
                oof_all_games_ece_improves = True
                if ece_delta < best_oof_ece_delta:
                    best_oof_ece_delta = ece_delta
                    best_oof_method = method
            if brier_delta < -_MIN_BSS_IMPROVEMENT:
                oof_all_games_bss_improves = True
        if m_heavy and not m_heavy.data_limited:
            if m_heavy.brier_delta_vs_original < -_MIN_BRIER_IMPROVEMENT:
                oof_heavy_fav_improves = True

    # Bootstrap CI check for best OOF method
    oof_ci_stable = True
    if best_oof_method:
        for ci in bootstrap_cis:
            if ci.method == best_oof_method and ci.segment == "all_games":
                if not ci.ci_stable:
                    oof_ci_stable = False
                    risk_notes.append(
                        f"Bootstrap CI for {best_oof_method} all_games is unstable "
                        f"(CI width: {ci.ci_upper - ci.ci_lower:.4f})"
                    )
                break

    if oof_all_games_ece_improves and not any_nc_overfit:
        heavy_note = " heavy_fav also improves." if oof_heavy_fav_improves else ""
        ci_note = " CI stable." if oof_ci_stable else " CI UNSTABLE — treat with caution."
        return (
            CALIBRATION_OBJECTIVE_PATCH_PROMISING,
            (
                f"OOF calibration ({best_oof_method or 'oof method'}) improves all-games ECE "
                f"by {abs(best_oof_ece_delta):.4f} on eval set (n={oof_split.n_eval})."
                f"{heavy_note}{ci_note} "
                f"PIT-safe validation: train=windows 1-3, eval=windows 4-5."
            ),
            (
                "Phase 70: implement OOF isotonic/Platt calibration layer as paper-only patch. "
                "Validate on hold-out season data. n_eval must be >= 1500 for production gate."
            ),
            True,
        )

    # ── Check shaping removal improvement ────────────────────────
    shaping_heavy_improves = False
    all_games_not_degraded = True
    best_shape_method = ""
    best_shape_heavy_delta = 0.0

    for method in ("remove_logit_sharpening", "remove_away_damping", "remove_both"):
        m_heavy = _get_heavy(method)
        m_all = _get_all(method)
        if m_heavy and not m_heavy.data_limited:
            delta = m_heavy.brier_delta_vs_original  # negative = better
            if delta < -_MIN_BRIER_IMPROVEMENT:
                shaping_heavy_improves = True
                if delta < best_shape_heavy_delta:
                    best_shape_heavy_delta = delta
                    best_shape_method = method
        if m_all and not m_all.data_limited:
            if m_all.brier_delta_vs_original > _MIN_BRIER_IMPROVEMENT * 3:
                all_games_not_degraded = False
                risk_notes.append(
                    f"Method {method!r} degrades all-games Brier: "
                    f"delta={m_all.brier_delta_vs_original:+.4f}"
                )

    if shaping_heavy_improves and all_games_not_degraded and not any_nc_overfit:
        return (
            PROBABILITY_SHAPING_REMOVAL_PROMISING,
            (
                f"Shaping removal ({best_shape_method or 'shaping method'}) improves heavy_fav Brier "
                f"by {abs(best_shape_heavy_delta):.4f} without degrading all-games metrics. "
                f"Root cause: logit/0.85 sharpening and/or away_wp*0.9 in stacking_model.py."
            ),
            (
                "Phase 70: implement paper-only removal of logit/0.85 and away_wp*0.9 "
                "in stacking_model.py. Validate on held-out data. Requires CANDIDATE_PATCH_CREATED gate."
            ),
            True,
        )

    # ── Abstention guard ──────────────────────────────────────────
    abstention_bands = [d for d in abstention_diagnostics if d.abstention_recommended]
    if abstention_bands and not any_nc_overfit:
        band_labels = [d.band_label for d in abstention_bands]
        return (
            ABSTENTION_GUARD_PROMISING,
            (
                f"Confidence bands {band_labels} consistently show blend worse than market "
                f"with bss_vs_market < -0.01. Diagnostic suggests no-bet in these bands."
            ),
            (
                "Phase 70: evaluate abstention guard for confidence bands "
                f"{band_labels}. Paper-only diagnostic only, no production patch."
            ),
            False,
        )

    # ── Default ───────────────────────────────────────────────────
    return (
        CALIBRATION_OBJECTIVE_NOT_PROMISING,
        (
            "No counterfactual produced meaningful improvement on eval set "
            f"(n={oof_split.n_eval}). All-games and heavy_fav improvements below "
            f"thresholds. Phase 70 calibration patch not warranted by evidence."
        ),
        "標記 CALIBRATION_OBJECTIVE_NOT_PROMISING。停止 Phase 70 calibration patch search。",
        False,
    )


# ═══════════════════════════════════════════════════════════════════
# SERIALIZATION
# ═══════════════════════════════════════════════════════════════════

def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses / lists to JSON-serialisable dicts."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(x) for x in obj]
    return obj


# ═══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def run_phase69_calibration_objective_redesign_counterfactual(
    predictions_path: Path,
    n_boot: int = _BOOTSTRAP_N,
    rng_seed: int = 42,
) -> Phase69Report:
    """Run full Phase 69 calibration objective redesign counterfactual analysis.

    Args:
        predictions_path: Path to phase56 per-game predictions JSONL.
        n_boot:           Bootstrap iterations (default 1000).
        rng_seed:         RNG seed for reproducibility.

    Returns:
        Phase69Report with gate, all counterfactual evidence, and completion marker.
    """
    # ── Safety constant assertions ────────────────────────────────
    assert CANDIDATE_PATCH_CREATED is False,        "SAFETY: candidate_patch_created"
    assert PRODUCTION_MODIFIED is False,             "SAFETY: production_modified"
    assert ALPHA_MODIFIED is False,                  "SAFETY: alpha_modified"
    assert DIAGNOSTIC_ONLY is True,                  "SAFETY: diagnostic_only"
    assert PREDICTION_JSONL_OVERWRITTEN is False,    "SAFETY: prediction_jsonl_overwritten"
    assert IN_SAMPLE_FIT_AND_EVALUATE is False,      "SAFETY: in_sample_fit_and_evaluate"
    assert PIT_SAFE_VALIDATION is True,              "SAFETY: pit_safe_validation"
    assert abs(ALPHA - 0.40) < 1e-9,                "SAFETY: alpha must be 0.40"

    rng = random.Random(rng_seed)

    # ── Load and enrich predictions ───────────────────────────────
    raw: list[dict] = []
    with open(predictions_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                raw.append(json.loads(line))
    rows = _enrich(raw)

    # ── OOF split (PIT-safe by construction) ─────────────────────
    train_rows = [r for r in rows if r.get("split_id") in _OOF_TRAIN_WINDOWS]
    eval_rows_raw = [r for r in rows if r.get("split_id") in _OOF_EVAL_WINDOWS]

    # Sort by game_date for clean PIT ordering
    train_rows.sort(key=lambda r: r["game_date"])
    eval_rows_raw.sort(key=lambda r: r["game_date"])

    feature_versions = list({r.get("feature_version", "unknown") for r in rows})
    feature_version = feature_versions[0] if len(feature_versions) == 1 else str(feature_versions)

    train_dates = [r["game_date"] for r in train_rows]
    eval_dates = [r["game_date"] for r in eval_rows_raw]

    oof_split = OofSplitInfo(
        train_windows=sorted(_OOF_TRAIN_WINDOWS),
        eval_windows=sorted(_OOF_EVAL_WINDOWS),
        n_train=len(train_rows),
        n_eval=len(eval_rows_raw),
        train_date_start=min(train_dates) if train_dates else "",
        train_date_end=max(train_dates) if train_dates else "",
        eval_date_start=min(eval_dates) if eval_dates else "",
        eval_date_end=max(eval_dates) if eval_dates else "",
        pit_safe=True,  # eval windows are strictly later than train windows
    )

    # ── Fit OOF calibration and apply to eval rows ────────────────
    _, eval_rows = _fit_and_apply_oof_calibration(train_rows, eval_rows_raw)

    # ── Compute original baseline metrics per segment (for deltas) ─
    original_brier_by_segment: dict[str, float] = {}
    for seg_name, seg_key, lo, hi in _SEGMENT_DEFS:
        seg_rows = _filter_segment(eval_rows, seg_name, seg_key, lo, hi)
        if seg_rows:
            fps = [r["_fav_prob"] for r in seg_rows]
            wins = [r["_fav_win"] for r in seg_rows]
            original_brier_by_segment[seg_name] = _brier(fps, wins)
            original_brier_by_segment[f"{seg_name}_ece"] = _ece(fps, wins)
        else:
            original_brier_by_segment[seg_name] = 0.0
            original_brier_by_segment[f"{seg_name}_ece"] = 0.0

    # ── Counterfactual metrics ────────────────────────────────────
    cf_metrics = _compute_counterfactual_metrics(eval_rows, original_brier_by_segment)

    # ── Calibration bands per method ─────────────────────────────
    all_calib_bands: list[CalibrationBandResult] = []
    for method in _METHODS:
        all_calib_bands.extend(_compute_calibration_bands_for_method(eval_rows, method))

    # ── Bootstrap CIs ────────────────────────────────────────────
    bootstrap_cis: list[BootstrapCI] = []
    ci_methods = ["remove_logit_sharpening", "remove_both", "oof_isotonic", "oof_platt"]
    ci_segments = [
        ("all_games",      "_fav_prob",       0.50, 1.01),
        ("heavy_favorite", "_fav_prob",       0.70, 1.01),
    ]
    for method in ci_methods:
        for seg_name, seg_key, lo, hi in ci_segments:
            ci = _bootstrap_brier_delta(
                eval_rows, method, seg_name, seg_key, lo, hi, n_boot, rng
            )
            bootstrap_cis.append(ci)

    # ── Determine best method for negative controls ───────────────
    # Use the method with best all-games Brier improvement
    best_method = "oof_isotonic"
    best_improvement = 0.0
    for method in _METHODS[1:]:  # skip original_baseline
        for m in cf_metrics:
            if m.method == method and m.segment == "all_games" and m.n > 0:
                imp = -(m.brier_delta_vs_original)
                if imp > best_improvement:
                    best_improvement = imp
                    best_method = method
                break

    # ── Negative controls ─────────────────────────────────────────
    negative_controls = _run_negative_controls(eval_rows, best_method, n_boot, rng)

    # ── Abstention diagnostics ────────────────────────────────────
    abstention_diagnostics = _compute_abstention_diagnostics(eval_rows)

    # ── Gate decision ─────────────────────────────────────────────
    risk_notes: list[str] = []
    if oof_split.n_eval < 500:
        risk_notes.append(
            f"OOF eval set n={oof_split.n_eval} < 500. "
            "Bootstrap CIs may be unstable. CI_UNSTABLE risk."
        )
    if any(not ci.ci_stable for ci in bootstrap_cis):
        risk_notes.append("Some bootstrap CIs are wide or unstable.")

    gate, gate_rationale, phase70_rec, worth_phase70 = _determine_gate(
        cf_metrics=cf_metrics,
        bootstrap_cis=bootstrap_cis,
        negative_controls=negative_controls,
        abstention_diagnostics=abstention_diagnostics,
        oof_split=oof_split,
        risk_notes=risk_notes,
    )

    assert gate in _VALID_GATES, f"Gate {gate!r} not in _VALID_GATES"

    # ── Summary flags ─────────────────────────────────────────────
    oof_calib_ece = False
    oof_calib_bss = False
    for method in ("oof_isotonic", "oof_platt"):
        m = next((x for x in cf_metrics
                  if x.method == method and x.segment == "all_games"), None)
        if m and not m.data_limited:
            if m.ece_delta_vs_original < -_MIN_ECE_IMPROVEMENT:
                oof_calib_ece = True
            if m.brier_delta_vs_original < -_MIN_BSS_IMPROVEMENT:
                oof_calib_bss = True

    shaping_hf = False
    for method in ("remove_logit_sharpening", "remove_away_damping", "remove_both"):
        m = next((x for x in cf_metrics
                  if x.method == method and x.segment == "heavy_favorite"), None)
        if m and not m.data_limited and m.brier_delta_vs_original < -_MIN_BRIER_IMPROVEMENT:
            shaping_hf = True

    nc_clear = not any(nc.overfit_risk for nc in negative_controls)
    ci_stable = all(ci.ci_stable for ci in bootstrap_cis
                    if not ci.data_limited and ci.segment == "all_games")

    evidence_files = [str(predictions_path)]

    return Phase69Report(
        phase_version=PHASE_VERSION,
        completion_marker=COMPLETION_MARKER,
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_path=str(predictions_path),
        candidate_patch_created=CANDIDATE_PATCH_CREATED,
        production_modified=PRODUCTION_MODIFIED,
        alpha_modified=ALPHA_MODIFIED,
        diagnostic_only=DIAGNOSTIC_ONLY,
        prediction_jsonl_overwritten=PREDICTION_JSONL_OVERWRITTEN,
        in_sample_fit_and_evaluate=IN_SAMPLE_FIT_AND_EVALUATE,
        pit_safe_validation=PIT_SAFE_VALIDATION,
        alpha=ALPHA,
        phase68_gate_anchor=PHASE68_GATE_ANCHOR,
        phase67_gate_anchor=PHASE67_GATE_ANCHOR,
        n_total=len(rows),
        n_train=len(train_rows),
        n_eval=len(eval_rows),
        feature_version=feature_version,
        oof_split=oof_split,
        counterfactual_metrics=cf_metrics,
        calibration_bands=all_calib_bands,
        bootstrap_cis=bootstrap_cis,
        negative_controls=negative_controls,
        abstention_diagnostics=abstention_diagnostics,
        gate=gate,
        gate_rationale=gate_rationale,
        phase70_recommendation=phase70_rec,
        risk_notes=risk_notes,
        oof_calibration_improves_ece=oof_calib_ece,
        oof_calibration_improves_bss=oof_calib_bss,
        shaping_removal_improves_heavy_fav=shaping_hf,
        negative_controls_clear=nc_clear,
        bootstrap_ci_stable=ci_stable,
        worth_phase70=worth_phase70,
    )
