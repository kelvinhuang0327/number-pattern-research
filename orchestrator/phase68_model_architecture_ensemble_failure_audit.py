"""Phase 68 — Model Architecture and Ensemble Failure Audit

DIAGNOSTIC ONLY.  CANDIDATE_PATCH_CREATED = False.  PRODUCTION_MODIFIED = False.
ALPHA_MODIFIED = False.  ALPHA = 0.40 (FROZEN).

Audits the model/ensemble architecture for sources of systematic prediction
failure, focusing on:
  - Calibration residual patterns (overconfidence / underconfidence by band)
  - Model vs market vs blend Brier comparison across confidence segments
  - Blend dilution effect (market outperforms blend at heavy-fav bands)
  - Model-market disagreement analysis
  - Architecture instability (5 walk-forward windows with different ensemble weights)
  - Expected Calibration Error (ECE) by source
  - Negative controls to verify signal authenticity

KEY ARCHITECTURAL FINDINGS (diagnostic):
  1. 5 different model_version strings across walk-forward windows:
       marl_w_elo=0.543_w_market=0.243  | marl_w_elo=0.494_w_market=0.400
       marl_w_elo=0.400_w_market=0.350  | marl_w_elo=0.636_w_market=0.371
       marl_w_elo=0.413_w_market=0.384
     The w_market here is the INTERNAL stacking weight — NOT ALPHA (which is 0.40 and frozen).
  2. stacking_model.py applies `away_wp * 0.9` when away_wp < 0.3  →  artificial fav sharpening.
  3. stacking_model.py applies logit rescaling `logit / 0.85`  →  overconfidence injection.
  4. stacking_model.py applies `away_wp += steam * 0.25`  →  double market incorporation.
  5. model_fav_prob is the MARL-blended output; individual sub-model probs not in JSONL.

PIT Safety: All inputs are pre-game predictions. No look-ahead leakage possible.
  This audit is purely retrospective over realised 2025 MLB game outcomes.
"""
from __future__ import annotations

import json
import math
import random
from collections import Counter
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ═══════════════════════════════════════════════════════════════════
# SAFETY CONSTANTS — FROZEN, DO NOT MODIFY
# ═══════════════════════════════════════════════════════════════════
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
ALPHA_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
ALPHA: float = 0.40

# ═══════════════════════════════════════════════════════════════════
# PHASE IDENTITY
# ═══════════════════════════════════════════════════════════════════
PHASE_VERSION: str = "phase68_model_architecture_ensemble_failure_audit_v1"
COMPLETION_MARKER: str = "PHASE_68_MODEL_ARCHITECTURE_ENSEMBLE_FAILURE_AUDIT_VERIFIED"

# ═══════════════════════════════════════════════════════════════════
# GATE CONSTANTS
# ═══════════════════════════════════════════════════════════════════
MODEL_ARCHITECTURE_REPAIR_PROMISING: str = "MODEL_ARCHITECTURE_REPAIR_PROMISING"
ENSEMBLE_WEIGHTING_REPAIR_PROMISING: str = "ENSEMBLE_WEIGHTING_REPAIR_PROMISING"
CALIBRATION_OBJECTIVE_REDESIGN_PROMISING: str = "CALIBRATION_OBJECTIVE_REDESIGN_PROMISING"
ABSTENTION_GUARD_PROMISING: str = "ABSTENTION_GUARD_PROMISING"
OVERFIT_RISK: str = "OVERFIT_RISK"
MODEL_ARCHITECTURE_NOT_PROMISING: str = "MODEL_ARCHITECTURE_NOT_PROMISING"

_VALID_GATES: frozenset[str] = frozenset({
    MODEL_ARCHITECTURE_REPAIR_PROMISING,
    ENSEMBLE_WEIGHTING_REPAIR_PROMISING,
    CALIBRATION_OBJECTIVE_REDESIGN_PROMISING,
    ABSTENTION_GUARD_PROMISING,
    OVERFIT_RISK,
    MODEL_ARCHITECTURE_NOT_PROMISING,
})

# ═══════════════════════════════════════════════════════════════════
# PREVIOUS PHASE GATE ANCHORS (FROZEN)
# ═══════════════════════════════════════════════════════════════════
PHASE67_GATE_ANCHOR: str = "OVERFIT_RISK"
PHASE67_VERSION: str = "phase67_context_failure_attribution_v1"
PHASE66_GATE_ANCHOR: str = "MARKET_MICROSTRUCTURE_NOT_PROMISING"
PHASE66_VERSION: str = "phase66_market_microstructure_failure_attribution_v1"
PHASE65_GATE_ANCHOR: str = "OVERFIT_RISK"
PHASE65_VERSION: str = "phase65_sp_fatigue_attribution_v1"
PHASE64B_GATE_ANCHOR: str = "BULLPEN_GRANULAR_FEATURE_NOT_PROMISING"
PHASE64B_VERSION: str = "phase64b_bullpen_granular_feature_attribution_v1"

# ═══════════════════════════════════════════════════════════════════
# ANALYSIS THRESHOLDS
# ═══════════════════════════════════════════════════════════════════
_MIN_SEGMENT_N: int = 20
_MIN_BUCKET_N: int = 15
_BOOTSTRAP_N: int = 1000

# Confidence-segment blend-fav-prob thresholds
_HEAVY_FAV_THRESHOLD: float = 0.70
_HIGH_CONF_THRESHOLD: float = 0.75
_EXTREME_FAV_THRESHOLD: float = 0.80
_PHASE45_FAIL_MIN_FAV: float = 0.60

# Calibration residual thresholds (absolute value)
_OVERCONF_RESIDUAL_THRESHOLD: float = 0.04   # residual > +4pp → overconfident band
_UNDERCONF_RESIDUAL_THRESHOLD: float = 0.04  # residual < -4pp → underconfident band

# Disagreement threshold: |model_home_prob - market_home_prob_no_vig| > this → "large"
_LARGE_DISAGREE_THRESHOLD: float = 0.05

# Negative control: real BSS must exceed shuffled mean by this much
_OVERFIT_GAP_THRESHOLD: float = 0.02

# Architecture instability: coefficient of variation threshold for w_market
_INSTABILITY_CV_THRESHOLD: float = 0.10

# Abstention: heavy-fav ECE trigger for ABSTENTION_GUARD_PROMISING
_ABSTENTION_ECE_THRESHOLD: float = 0.06


# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SegmentMetrics:
    """Per-segment prediction accuracy and calibration summary."""
    n: int
    model_brier: float
    market_brier: float
    blend_brier: float
    blend_bss_vs_market: float    # _bss_direct(blend_brier, market_brier)
    model_bss_vs_market: float    # _bss_direct(model_brier, market_brier)
    fav_win_rate: float           # fraction the blended-favourite wins
    ece_blend: float
    ece_model: float
    ece_market: float
    mean_blend_fav_prob: float    # mean predicted fav-probability (blend)
    mean_model_fav_prob: float    # mean predicted fav-probability (model only)
    mean_mkt_fav_prob: float      # mean predicted fav-probability (market only)
    data_limited: bool            # True when n < _MIN_SEGMENT_N


@dataclass
class CalibrationBand:
    """Calibration residual for one probability band."""
    band_label: str
    lo: float
    hi: float
    n: int
    blend_pred: float
    model_pred: float
    mkt_pred: float
    actual_win_rate: float
    residual: float            # blend_pred − actual_win_rate
    model_residual: float      # model_pred − actual_win_rate
    mkt_residual: float        # mkt_pred − actual_win_rate
    is_overconfident: bool     # residual > +_OVERCONF_RESIDUAL_THRESHOLD
    is_underconfident: bool    # residual < −_UNDERCONF_RESIDUAL_THRESHOLD
    data_limited: bool         # True when n < _MIN_BUCKET_N


@dataclass
class DisagreementBucket:
    """Model-vs-market disagreement bucket metrics."""
    bucket_label: str           # model_large_fav | mkt_large_fav | agree
    threshold: float            # _LARGE_DISAGREE_THRESHOLD used
    n: int
    model_brier: float
    market_brier: float
    blend_brier: float
    market_beats_model: bool    # market_brier < model_brier
    blend_beats_model: bool     # blend_brier < model_brier
    market_beats_blend: bool    # market_brier < blend_brier


@dataclass
class ModelVersionProfile:
    """Per-model-version accuracy profile."""
    model_version: str
    n: int
    w_elo: float              # extracted from model_version string
    w_market_internal: float  # extracted from model_version string (NOT ALPHA!)
    model_brier: float
    market_brier: float
    blend_brier: float
    blend_bss_vs_market: float


@dataclass
class ArchitectureInstability:
    """Ensemble weight instability across walk-forward windows."""
    n_model_versions: int
    model_versions: list[str]
    w_market_values: list[float]
    w_elo_values: list[float]
    w_market_mean: float
    w_market_std: float
    w_market_cv: float           # coefficient of variation
    w_elo_mean: float
    w_elo_std: float
    w_elo_cv: float
    instability_detected: bool   # cv > _INSTABILITY_CV_THRESHOLD


@dataclass
class EnsembleSharpness:
    """Sharpness (mean fav_prob) comparison across sources."""
    model_mean_fav_prob: float
    model_std_fav_prob: float
    market_mean_fav_prob: float
    market_std_fav_prob: float
    blend_mean_fav_prob: float
    blend_std_fav_prob: float
    model_less_sharp_than_market: bool   # model sharpness < market sharpness


@dataclass
class BlendDilutionCheck:
    """Check whether market alone outperforms blend (dilution effect)."""
    segment: str
    n: int
    market_brier: float
    blend_brier: float
    dilution_detected: bool      # blend_brier > market_brier
    dilution_magnitude: float    # blend_brier − market_brier  (positive = market better)


@dataclass
class NegativeControl:
    """Negative control result for overfit/noise detection."""
    control_name: str
    description: str
    real_bss: float              # BSS of real fav_prob vs naive 0.5 reference
    null_bss_mean: float         # mean BSS of shuffled/null labels
    null_bss_std: float
    signal_gap: float            # real_bss − null_bss_mean
    overfit_threshold: float     # _OVERFIT_GAP_THRESHOLD
    overfit_risk: bool           # signal_gap < overfit_threshold


@dataclass
class Phase68Report:
    """Full Phase 68 model architecture and ensemble failure audit report."""
    phase_version: str
    completion_marker: str
    generated_at: str
    data_path: str

    # Safety constants (all verified at runtime)
    candidate_patch_created: bool
    production_modified: bool
    alpha_modified: bool
    diagnostic_only: bool
    alpha: float

    # Phase anchors
    phase67_gate_anchor: str
    phase66_gate_anchor: str
    phase65_gate_anchor: str
    phase64b_gate_anchor: str

    # Core statistics
    n_predictions: int
    feature_version: str

    # All-games metrics
    all_metrics: SegmentMetrics

    # Confidence-based segments (blend fav_prob)
    heavy_fav_metrics: SegmentMetrics        # fav_prob >= 0.70
    high_conf_metrics: SegmentMetrics        # fav_prob >= 0.75  (may be DATA_LIMITED)
    extreme_fav_metrics: SegmentMetrics      # fav_prob >= 0.80  (likely DATA_LIMITED)
    phase45_failure_metrics: SegmentMetrics  # fav_prob >= 0.60 AND fav_win == 0

    # Model confidence band segments (model_fav_prob-based)
    model_band_60_65: SegmentMetrics
    model_band_65_70: SegmentMetrics
    model_band_70_75: SegmentMetrics
    model_band_75_plus: SegmentMetrics

    # Calibration residual analysis
    calibration_bands_blend: list[CalibrationBand]   # defined by blend_fav_prob
    calibration_bands_model: list[CalibrationBand]   # defined by model_fav_prob

    # Disagreement analysis
    disagreement_buckets: list[DisagreementBucket]

    # Model version profiles
    model_version_profiles: list[ModelVersionProfile]
    architecture_instability: ArchitectureInstability

    # Sharpness
    ensemble_sharpness: EnsembleSharpness

    # Blend dilution checks
    blend_dilution_checks: list[BlendDilutionCheck]

    # Negative controls
    negative_controls: list[NegativeControl]

    # Gate decision
    gate: str
    gate_rationale: str
    next_step: str

    # Summary flags
    calibration_overconfidence_detected: bool
    calibration_underconfidence_detected: bool
    blend_dilution_heavy_fav: bool
    architecture_instability_detected: bool
    overfit_risk_detected: bool
    worth_phase69: bool


# ═══════════════════════════════════════════════════════════════════
# CORE MATH FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def _brier(probs: list[float], labels: list[float]) -> float:
    """Mean Brier score.  Returns 0.0 for empty input."""
    if not probs:
        return 0.0
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(probs)


def _bss_direct(model_brier: float, ref_brier: float) -> float:
    """Brier Skill Score via direct ratio.

    BSS = 1 − model_brier / ref_brier.
    Positive = model beats reference.  Negative = reference beats model.
    Returns 0.0 when ref_brier == 0.
    """
    if ref_brier == 0.0:
        return 0.0
    return 1.0 - model_brier / ref_brier


def _ece(probs: list[float], labels: list[float], n_bins: int = 10) -> float:
    """Expected Calibration Error.  Uses equal-width bins over [0, 1].

    ECE = Σ_b |B_b| / |N| · |mean_pred_b − mean_actual_b|
    """
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
            mean_p = sum(p for p, _ in b) / len(b)
            mean_y = sum(y for _, y in b) / len(b)
            ece_val += (len(b) / total) * abs(mean_p - mean_y)
    return ece_val


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _std(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))


def _cv(vals: list[float]) -> float:
    """Coefficient of variation (std / mean).  Returns 0.0 if mean ≈ 0."""
    m = _mean(vals)
    if abs(m) < 1e-12:
        return 0.0
    return _std(vals) / m


# ═══════════════════════════════════════════════════════════════════
# ROW ENRICHMENT
# ═══════════════════════════════════════════════════════════════════

def _enrich(rows: list[dict]) -> list[dict]:
    """Add derived blend / fav-side fields to each prediction row (in-place)."""
    for r in rows:
        blend = (1 - ALPHA) * r["model_home_prob"] + ALPHA * r["market_home_prob_no_vig"]
        r["_blend"] = blend
        r["_fav_is_home"] = blend >= 0.5
        r["_fav_prob"] = max(blend, 1.0 - blend)
        r["_fav_win"] = float(r["home_win"]) if r["_fav_is_home"] else 1.0 - float(r["home_win"])
        r["_model_fav_prob"] = max(r["model_home_prob"], 1.0 - r["model_home_prob"])
        r["_mkt_fav_prob"] = max(
            r["market_home_prob_no_vig"], 1.0 - r["market_home_prob_no_vig"]
        )
        r["_disagree"] = r["model_home_prob"] - r["market_home_prob_no_vig"]
    return rows


# ═══════════════════════════════════════════════════════════════════
# SEGMENT METRICS
# ═══════════════════════════════════════════════════════════════════

def _compute_segment_metrics(rows: list[dict]) -> SegmentMetrics:
    """Compute all accuracy/calibration metrics for a list of enriched rows.

    All probability comparisons use the fav-side: _fav_prob vs _fav_win.
    """
    n = len(rows)
    if n == 0:
        zero = SegmentMetrics(
            n=0, model_brier=0.0, market_brier=0.0, blend_brier=0.0,
            blend_bss_vs_market=0.0, model_bss_vs_market=0.0,
            fav_win_rate=0.0, ece_blend=0.0, ece_model=0.0, ece_market=0.0,
            mean_blend_fav_prob=0.0, mean_model_fav_prob=0.0,
            mean_mkt_fav_prob=0.0, data_limited=True,
        )
        return zero

    fav_wins = [r["_fav_win"] for r in rows]
    blend_fps = [r["_fav_prob"] for r in rows]
    model_fps = [r["_model_fav_prob"] for r in rows]
    mkt_fps = [r["_mkt_fav_prob"] for r in rows]

    model_b = _brier(model_fps, fav_wins)
    mkt_b = _brier(mkt_fps, fav_wins)
    blend_b = _brier(blend_fps, fav_wins)

    return SegmentMetrics(
        n=n,
        model_brier=round(model_b, 6),
        market_brier=round(mkt_b, 6),
        blend_brier=round(blend_b, 6),
        blend_bss_vs_market=round(_bss_direct(blend_b, mkt_b), 6),
        model_bss_vs_market=round(_bss_direct(model_b, mkt_b), 6),
        fav_win_rate=round(_mean(fav_wins), 6),
        ece_blend=round(_ece(blend_fps, fav_wins), 6),
        ece_model=round(_ece(model_fps, fav_wins), 6),
        ece_market=round(_ece(mkt_fps, fav_wins), 6),
        mean_blend_fav_prob=round(_mean(blend_fps), 6),
        mean_model_fav_prob=round(_mean(model_fps), 6),
        mean_mkt_fav_prob=round(_mean(mkt_fps), 6),
        data_limited=n < _MIN_SEGMENT_N,
    )


# ═══════════════════════════════════════════════════════════════════
# CALIBRATION RESIDUAL
# ═══════════════════════════════════════════════════════════════════

_BLEND_CALIB_BANDS: list[tuple[str, float, float]] = [
    ("0.50-0.55", 0.50, 0.55),
    ("0.55-0.60", 0.55, 0.60),
    ("0.60-0.65", 0.60, 0.65),
    ("0.65-0.70", 0.65, 0.70),
    ("0.70-0.75", 0.70, 0.75),
    ("0.75+",     0.75, 1.01),
]

_MODEL_CALIB_BANDS: list[tuple[str, float, float]] = [
    ("0.50-0.55", 0.50, 0.55),
    ("0.55-0.60", 0.55, 0.60),
    ("0.60-0.65", 0.60, 0.65),
    ("0.65-0.70", 0.65, 0.70),
    ("0.70-0.75", 0.70, 0.75),
    ("0.75+",     0.75, 1.01),
]


def _compute_calibration_bands(
    rows: list[dict],
    prob_key: str,
    bands: list[tuple[str, float, float]],
) -> list[CalibrationBand]:
    """Compute calibration residual for each probability band.

    Args:
        rows:     enriched prediction rows.
        prob_key: key in row dict giving the probability to use for banding
                  (either '_fav_prob' or '_model_fav_prob').
        bands:    list of (label, lo, hi) tuples.
    """
    result: list[CalibrationBand] = []
    for label, lo, hi in bands:
        seg = [r for r in rows if lo <= r[prob_key] < hi]
        n = len(seg)
        if n == 0:
            continue
        blend_pred = _mean([r["_fav_prob"] for r in seg])
        model_pred = _mean([r["_model_fav_prob"] for r in seg])
        mkt_pred = _mean([r["_mkt_fav_prob"] for r in seg])
        actual = _mean([r["_fav_win"] for r in seg])
        residual = blend_pred - actual
        model_residual = model_pred - actual
        mkt_residual = mkt_pred - actual
        result.append(CalibrationBand(
            band_label=label,
            lo=lo,
            hi=hi,
            n=n,
            blend_pred=round(blend_pred, 6),
            model_pred=round(model_pred, 6),
            mkt_pred=round(mkt_pred, 6),
            actual_win_rate=round(actual, 6),
            residual=round(residual, 6),
            model_residual=round(model_residual, 6),
            mkt_residual=round(mkt_residual, 6),
            is_overconfident=(
                n >= _MIN_BUCKET_N and residual > _OVERCONF_RESIDUAL_THRESHOLD
            ),
            is_underconfident=(
                n >= _MIN_BUCKET_N and residual < -_UNDERCONF_RESIDUAL_THRESHOLD
            ),
            data_limited=n < _MIN_BUCKET_N,
        ))
    return result


# ═══════════════════════════════════════════════════════════════════
# DISAGREEMENT ANALYSIS
# ═══════════════════════════════════════════════════════════════════

def _compute_disagreement_buckets(rows: list[dict]) -> list[DisagreementBucket]:
    """Split rows into model_large_fav / mkt_large_fav / agree and compare Brier."""
    buckets: list[DisagreementBucket] = []
    band_defs = [
        ("model_large_fav",  _LARGE_DISAGREE_THRESHOLD, 1.0),
        ("mkt_large_fav",   -1.0, -_LARGE_DISAGREE_THRESHOLD),
        ("agree",           -_LARGE_DISAGREE_THRESHOLD, _LARGE_DISAGREE_THRESHOLD),
    ]
    for label, lo, hi in band_defs:
        seg = [r for r in rows if lo <= r["_disagree"] < hi]
        if not seg:
            continue
        # Use home-win-side brier for raw comparison (directional)
        model_b = _brier([r["model_home_prob"] for r in seg], [float(r["home_win"]) for r in seg])
        mkt_b = _brier([r["market_home_prob_no_vig"] for r in seg], [float(r["home_win"]) for r in seg])
        blend_b = _brier([r["_blend"] for r in seg], [float(r["home_win"]) for r in seg])
        buckets.append(DisagreementBucket(
            bucket_label=label,
            threshold=_LARGE_DISAGREE_THRESHOLD,
            n=len(seg),
            model_brier=round(model_b, 6),
            market_brier=round(mkt_b, 6),
            blend_brier=round(blend_b, 6),
            market_beats_model=mkt_b < model_b,
            blend_beats_model=blend_b < model_b,
            market_beats_blend=mkt_b < blend_b,
        ))
    return buckets


# ═══════════════════════════════════════════════════════════════════
# MODEL VERSION PROFILES
# ═══════════════════════════════════════════════════════════════════

_W_ELO_RE = re.compile(r"w_elo=([0-9]+\.[0-9]+)")
_W_MARKET_RE = re.compile(r"w_market=([0-9]+\.[0-9]+)")


def _parse_model_version(model_version: str) -> tuple[float, float]:
    """Extract (w_elo, w_market_internal) from 'marl_w_elo=X_w_market=Y'."""
    m_elo = _W_ELO_RE.search(model_version)
    m_mkt = _W_MARKET_RE.search(model_version)
    if m_elo is None or m_mkt is None:
        return 0.0, 0.0
    try:
        return float(m_elo.group(1)), float(m_mkt.group(1))
    except ValueError:
        return 0.0, 0.0


def _compute_model_version_profiles(rows: list[dict]) -> list[ModelVersionProfile]:
    """Compute accuracy profile for each walk-forward window / model version."""
    from collections import defaultdict
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r.get("model_version", "unknown")].append(r)

    profiles: list[ModelVersionProfile] = []
    for mv, seg in sorted(groups.items()):
        w_elo, w_mkt = _parse_model_version(mv)
        fav_wins = [r["_fav_win"] for r in seg]
        blend_fps = [r["_fav_prob"] for r in seg]
        model_fps = [r["_model_fav_prob"] for r in seg]
        mkt_fps = [r["_mkt_fav_prob"] for r in seg]
        model_b = _brier(model_fps, fav_wins)
        mkt_b = _brier(mkt_fps, fav_wins)
        blend_b = _brier(blend_fps, fav_wins)
        profiles.append(ModelVersionProfile(
            model_version=mv,
            n=len(seg),
            w_elo=w_elo,
            w_market_internal=w_mkt,
            model_brier=round(model_b, 6),
            market_brier=round(mkt_b, 6),
            blend_brier=round(blend_b, 6),
            blend_bss_vs_market=round(_bss_direct(blend_b, mkt_b), 6),
        ))
    return profiles


def _compute_architecture_instability(
    profiles: list[ModelVersionProfile],
) -> ArchitectureInstability:
    w_mkt_vals = [p.w_market_internal for p in profiles]
    w_elo_vals = [p.w_elo for p in profiles]
    w_mkt_cv = _cv(w_mkt_vals)
    w_elo_cv = _cv(w_elo_vals)
    return ArchitectureInstability(
        n_model_versions=len(profiles),
        model_versions=[p.model_version for p in profiles],
        w_market_values=w_mkt_vals,
        w_elo_values=w_elo_vals,
        w_market_mean=round(_mean(w_mkt_vals), 6),
        w_market_std=round(_std(w_mkt_vals), 6),
        w_market_cv=round(w_mkt_cv, 6),
        w_elo_mean=round(_mean(w_elo_vals), 6),
        w_elo_std=round(_std(w_elo_vals), 6),
        w_elo_cv=round(w_elo_cv, 6),
        instability_detected=(
            w_mkt_cv > _INSTABILITY_CV_THRESHOLD
            or w_elo_cv > _INSTABILITY_CV_THRESHOLD
        ),
    )


# ═══════════════════════════════════════════════════════════════════
# SHARPNESS AND BLEND DILUTION
# ═══════════════════════════════════════════════════════════════════

def _compute_ensemble_sharpness(rows: list[dict]) -> EnsembleSharpness:
    model_fps = [r["_model_fav_prob"] for r in rows]
    mkt_fps = [r["_mkt_fav_prob"] for r in rows]
    blend_fps = [r["_fav_prob"] for r in rows]
    return EnsembleSharpness(
        model_mean_fav_prob=round(_mean(model_fps), 6),
        model_std_fav_prob=round(_std(model_fps), 6),
        market_mean_fav_prob=round(_mean(mkt_fps), 6),
        market_std_fav_prob=round(_std(mkt_fps), 6),
        blend_mean_fav_prob=round(_mean(blend_fps), 6),
        blend_std_fav_prob=round(_std(blend_fps), 6),
        model_less_sharp_than_market=_mean(model_fps) < _mean(mkt_fps),
    )


def _compute_blend_dilution_checks(rows: list[dict]) -> list[BlendDilutionCheck]:
    """Check blend-dilution effect at multiple confidence thresholds."""
    checks: list[BlendDilutionCheck] = []
    thresholds = [
        ("all_games",        0.50),
        ("heavy_fav_0.70",   0.70),
        ("high_conf_0.75",   0.75),
        ("extreme_fav_0.80", 0.80),
        ("fav_0.60",         0.60),
        ("fav_0.65",         0.65),
    ]
    for label, lo in thresholds:
        seg = [r for r in rows if r["_fav_prob"] >= lo]
        if len(seg) < _MIN_BUCKET_N:
            checks.append(BlendDilutionCheck(
                segment=label, n=len(seg),
                market_brier=0.0, blend_brier=0.0,
                dilution_detected=False, dilution_magnitude=0.0,
            ))
            continue
        fav_wins = [r["_fav_win"] for r in seg]
        blend_fps = [r["_fav_prob"] for r in seg]
        mkt_fps = [r["_mkt_fav_prob"] for r in seg]
        mkt_b = _brier(mkt_fps, fav_wins)
        blend_b = _brier(blend_fps, fav_wins)
        magnitude = blend_b - mkt_b   # positive = market is better (dilution)
        checks.append(BlendDilutionCheck(
            segment=label,
            n=len(seg),
            market_brier=round(mkt_b, 6),
            blend_brier=round(blend_b, 6),
            dilution_detected=magnitude > 0,
            dilution_magnitude=round(magnitude, 6),
        ))
    return checks


# ═══════════════════════════════════════════════════════════════════
# NEGATIVE CONTROLS
# ═══════════════════════════════════════════════════════════════════

def _run_negative_controls(
    rows: list[dict],
    n_boot: int,
    rng: random.Random,
) -> list[NegativeControl]:
    """Three negative controls to verify signal authenticity."""
    controls: list[NegativeControl] = []
    fav_wins = [r["_fav_win"] for r in rows]
    blend_fps = [r["_fav_prob"] for r in rows]
    ref_brier = _brier([0.5] * len(rows), fav_wins)

    # ── Control 1: Shuffled confidence bucket ────────────────────
    real_blend_brier = _brier(blend_fps, fav_wins)
    real_bss = _bss_direct(real_blend_brier, ref_brier)

    shuffled_bss_vals: list[float] = []
    fps_copy = blend_fps[:]
    for _ in range(n_boot):
        rng.shuffle(fps_copy)
        b = _brier(fps_copy, fav_wins)
        shuffled_bss_vals.append(_bss_direct(b, ref_brier))

    null_mean = _mean(shuffled_bss_vals)
    null_std = _std(shuffled_bss_vals)
    gap = real_bss - null_mean
    controls.append(NegativeControl(
        control_name="shuffled_confidence_bucket",
        description=(
            "Shuffle blend fav_prob across all rows. "
            "BSS should collapse to near-zero if signal is real."
        ),
        real_bss=round(real_bss, 6),
        null_bss_mean=round(null_mean, 6),
        null_bss_std=round(null_std, 6),
        signal_gap=round(gap, 6),
        overfit_threshold=_OVERFIT_GAP_THRESHOLD,
        overfit_risk=gap < _OVERFIT_GAP_THRESHOLD,
    ))

    # ── Control 2: Random model-market disagreement assignment ────
    real_disagree_vals = [r["_disagree"] for r in rows]
    # Real: Brier difference between high-disagree and agree segments
    real_high = [r for r in rows if abs(r["_disagree"]) >= _LARGE_DISAGREE_THRESHOLD]
    real_agree = [r for r in rows if abs(r["_disagree"]) < _LARGE_DISAGREE_THRESHOLD]
    if real_high and real_agree:
        real_delta = _brier(
            [r["model_home_prob"] for r in real_high],
            [float(r["home_win"]) for r in real_high],
        ) - _brier(
            [r["model_home_prob"] for r in real_agree],
            [float(r["home_win"]) for r in real_agree],
        )
        perm_deltas: list[float] = []
        disagree_copy = real_disagree_vals[:]
        model_probs = [r["model_home_prob"] for r in rows]
        home_wins = [float(r["home_win"]) for r in rows]
        for _ in range(n_boot):
            rng.shuffle(disagree_copy)
            perm_high = [model_probs[i] for i, d in enumerate(disagree_copy)
                         if abs(d) >= _LARGE_DISAGREE_THRESHOLD]
            perm_agree = [model_probs[i] for i, d in enumerate(disagree_copy)
                          if abs(d) < _LARGE_DISAGREE_THRESHOLD]
            hw_high = [home_wins[i] for i, d in enumerate(disagree_copy)
                       if abs(d) >= _LARGE_DISAGREE_THRESHOLD]
            hw_agree = [home_wins[i] for i, d in enumerate(disagree_copy)
                        if abs(d) < _LARGE_DISAGREE_THRESHOLD]
            if perm_high and perm_agree:
                perm_deltas.append(
                    _brier(perm_high, hw_high) - _brier(perm_agree, hw_agree)
                )
        perm_mean = _mean(perm_deltas)
        perm_std = _std(perm_deltas)
        d_gap = abs(real_delta) - abs(perm_mean)
        controls.append(NegativeControl(
            control_name="random_disagreement_assignment",
            description=(
                "Shuffle model-market disagreement labels. "
                "Brier gap between high-disagree and agree should collapse."
            ),
            real_bss=round(real_delta, 6),
            null_bss_mean=round(perm_mean, 6),
            null_bss_std=round(perm_std, 6),
            signal_gap=round(d_gap, 6),
            overfit_threshold=_OVERFIT_GAP_THRESHOLD,
            overfit_risk=d_gap < _OVERFIT_GAP_THRESHOLD,
        ))
    else:
        # Insufficient data for this control; treat as non-overfit
        controls.append(NegativeControl(
            control_name="random_disagreement_assignment",
            description="Skipped — insufficient segment sizes.",
            real_bss=0.0, null_bss_mean=0.0, null_bss_std=0.0,
            signal_gap=1.0, overfit_threshold=_OVERFIT_GAP_THRESHOLD,
            overfit_risk=False,
        ))

    # ── Control 3: Odd/even game index split (irrelevant dimension) ──
    odd_rows = [r for i, r in enumerate(rows) if i % 2 == 1]
    even_rows = [r for i, r in enumerate(rows) if i % 2 == 0]
    if odd_rows and even_rows:
        odd_brier = _brier([r["_fav_prob"] for r in odd_rows], [r["_fav_win"] for r in odd_rows])
        even_brier = _brier([r["_fav_prob"] for r in even_rows], [r["_fav_win"] for r in even_rows])
        parity_delta = abs(odd_brier - even_brier)
        # Permute parity labels; the observed delta should be consistent with noise
        all_fps = [r["_fav_prob"] for r in rows]
        all_wins = [r["_fav_win"] for r in rows]
        parity_perm_deltas: list[float] = []
        indices = list(range(len(rows)))
        for _ in range(n_boot):
            rng.shuffle(indices)
            half = len(indices) // 2
            perm_odd_fps = [all_fps[i] for i in indices[:half]]
            perm_even_fps = [all_fps[i] for i in indices[half:]]
            perm_odd_wins = [all_wins[i] for i in indices[:half]]
            perm_even_wins = [all_wins[i] for i in indices[half:]]
            parity_perm_deltas.append(
                abs(_brier(perm_odd_fps, perm_odd_wins) - _brier(perm_even_fps, perm_even_wins))
            )
        parity_null_mean = _mean(parity_perm_deltas)
        parity_null_std = _std(parity_perm_deltas)
        # Parity should NOT be significant; overfit if real signal > null
        parity_gap = parity_delta - parity_null_mean
        controls.append(NegativeControl(
            control_name="irrelevant_odd_even_split",
            description=(
                "Odd/even game index split — irrelevant dimension. "
                "Should show no predictive Brier difference."
            ),
            real_bss=round(parity_delta, 6),
            null_bss_mean=round(parity_null_mean, 6),
            null_bss_std=round(parity_null_std, 6),
            signal_gap=round(parity_gap, 6),
            overfit_threshold=_OVERFIT_GAP_THRESHOLD,
            # Irrelevant split should be near null → overfit_risk if far from null
            overfit_risk=parity_gap > _OVERFIT_GAP_THRESHOLD * 3,
        ))
    return controls


# ═══════════════════════════════════════════════════════════════════
# GATE DETERMINATION
# ═══════════════════════════════════════════════════════════════════

def _determine_gate(
    all_metrics: SegmentMetrics,
    heavy_fav_metrics: SegmentMetrics,
    calibration_bands_blend: list[CalibrationBand],
    disagreement_buckets: list[DisagreementBucket],
    negative_controls: list[NegativeControl],
    architecture_instability: ArchitectureInstability,
) -> tuple[str, str, str, bool]:
    """Determine Phase 68 gate.

    Returns: (gate, rationale, next_step, worth_phase69).
    Gate priority order:
      1. OVERFIT_RISK  — if shuffled_confidence_bucket control flags overfit
      2. CALIBRATION_OBJECTIVE_REDESIGN_PROMISING  — calibration residual > threshold
      3. ENSEMBLE_WEIGHTING_REPAIR_PROMISING  — model-only underperforms market
      4. ABSTENTION_GUARD_PROMISING  — heavy-fav ECE above threshold
      5. MODEL_ARCHITECTURE_NOT_PROMISING  — default

    Note: Only the shuffled_confidence_bucket control determines OVERFIT_RISK.
    Other controls (disagreement assignment, odd/even split) are informational only.
    """
    # Only the shuffled fav_prob control determines overfit gate
    shuffle_ctrl = next(
        (nc for nc in negative_controls if nc.control_name == "shuffled_confidence_bucket"),
        None,
    )
    any_overfit = shuffle_ctrl is not None and shuffle_ctrl.overfit_risk

    # Calibration band signals
    overconfident_bands = [
        b for b in calibration_bands_blend
        if b.is_overconfident and not b.data_limited
    ]
    underconfident_bands = [
        b for b in calibration_bands_blend
        if b.is_underconfident and not b.data_limited
    ]

    # ── Check 1: Overfit risk ─────────────────────────────────────
    if any_overfit:
        bad_controls = [nc.control_name for nc in negative_controls if nc.overfit_risk]
        return (
            OVERFIT_RISK,
            (
                f"Negative control overfit risk detected: {bad_controls}. "
                f"Signal gap below threshold ({_OVERFIT_GAP_THRESHOLD})."
            ),
            "標記 OVERFIT_RISK。調查 small-sample artifact。不可推進至架構修改。",
            False,
        )

    # ── Check 2: Calibration objective redesign ───────────────────
    if overconfident_bands or underconfident_bands:
        oc_labels = [(b.band_label, f"{b.residual:+.4f}", b.n) for b in overconfident_bands]
        uc_labels = [(b.band_label, f"{b.residual:+.4f}", b.n) for b in underconfident_bands]
        worst_oc = max(overconfident_bands, key=lambda b: b.residual, default=None)
        worst_uc = min(underconfident_bands, key=lambda b: b.residual, default=None)
        rationale_parts = []
        if worst_oc:
            rationale_parts.append(
                f"Overconfident band '{worst_oc.band_label}': "
                f"blend_pred={worst_oc.blend_pred:.4f} actual={worst_oc.actual_win_rate:.4f} "
                f"residual={worst_oc.residual:+.4f} (n={worst_oc.n})"
            )
        if worst_uc:
            rationale_parts.append(
                f"Underconfident band '{worst_uc.band_label}': "
                f"blend_pred={worst_uc.blend_pred:.4f} actual={worst_uc.actual_win_rate:.4f} "
                f"residual={worst_uc.residual:+.4f} (n={worst_uc.n})"
            )
        rationale_parts.append(
            f"All overconfident bands: {oc_labels}. "
            f"All underconfident bands: {uc_labels}. "
            "Probable causes: logit/0.85 sharpening + away_wp*0.9 artifact in stacking_model.py."
        )
        return (
            CALIBRATION_OBJECTIVE_REDESIGN_PROMISING,
            " | ".join(rationale_parts),
            (
                "標記 CALIBRATION_OBJECTIVE_REDESIGN_PROMISING。"
                "Phase 69 評估移除 logit/0.85 sharpening 與 away_wp*0.9 artifact 的 calibration 改進。"
                "需在 hold-out 窗口上驗證 ECE + BSS 提升，確保 n >= 1500 樣本。"
            ),
            True,
        )

    # ── Check 3: Ensemble weighting repair ────────────────────────
    if (
        not heavy_fav_metrics.data_limited
        and heavy_fav_metrics.model_bss_vs_market < 0.0
    ):
        return (
            ENSEMBLE_WEIGHTING_REPAIR_PROMISING,
            (
                f"Model-only underperforms market at heavy_fav segment "
                f"(model_bss_vs_market={heavy_fav_metrics.model_bss_vs_market:.4f}, "
                f"n={heavy_fav_metrics.n}). "
                f"Market alone is a better predictor than the ensemble in high-confidence cases."
            ),
            (
                "標記 ENSEMBLE_WEIGHTING_REPAIR_PROMISING。"
                "Phase 69 評估動態 ALPHA 調整：在 fav_prob >= 0.70 時增加市場權重至 0.6-0.7。"
            ),
            True,
        )

    # ── Check 4: Abstention guard ─────────────────────────────────
    if (
        not heavy_fav_metrics.data_limited
        and heavy_fav_metrics.ece_blend > _ABSTENTION_ECE_THRESHOLD
    ):
        return (
            ABSTENTION_GUARD_PROMISING,
            (
                f"Heavy-fav ECE(blend)={heavy_fav_metrics.ece_blend:.4f} "
                f"> threshold {_ABSTENTION_ECE_THRESHOLD}. "
                f"Large calibration error at confidence extremes suggests "
                f"abstention on heavy-fav bets would improve EV."
            ),
            (
                "標記 ABSTENTION_GUARD_PROMISING。"
                "Phase 69 評估在 fav_prob >= 0.70 的投注中建立 no-bet 閾值。"
            ),
            False,
        )

    # ── Default ───────────────────────────────────────────────────
    return (
        MODEL_ARCHITECTURE_NOT_PROMISING,
        (
            f"No significant calibration residuals (all bands within ±{_OVERCONF_RESIDUAL_THRESHOLD:.2f}). "
            f"No consistent model-vs-market advantage found. "
            f"all_metrics: blend_bss_vs_market={all_metrics.blend_bss_vs_market:.4f}, "
            f"n={all_metrics.n}. Architecture variations within tolerance."
        ),
        "標記 MODEL_ARCHITECTURE_NOT_PROMISING。考慮 Phase 69 轉向 external data 增強策略。",
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

def run_phase68_model_architecture_ensemble_failure_audit(
    predictions_path: Path,
    n_boot: int = _BOOTSTRAP_N,
    rng_seed: int = 42,
) -> Phase68Report:
    """Run full Phase 68 model architecture and ensemble failure audit.

    Args:
        predictions_path: Path to phase56 per-game predictions JSONL.
        n_boot:           Bootstrap iterations (default 1 000).
        rng_seed:         RNG seed for reproducibility.

    Returns:
        Phase68Report with gate, all audit evidence, and completion marker.
    """
    # ── Verify safety constants ──────────────────────────────────
    assert CANDIDATE_PATCH_CREATED is False, "SAFETY: candidate patch flag"
    assert PRODUCTION_MODIFIED is False,     "SAFETY: production modified flag"
    assert ALPHA_MODIFIED is False,          "SAFETY: alpha modified flag"
    assert DIAGNOSTIC_ONLY is True,          "SAFETY: diagnostic only flag"
    assert abs(ALPHA - 0.40) < 1e-9,        "SAFETY: alpha must be 0.40"

    rng = random.Random(rng_seed)

    # ── Load and enrich predictions ───────────────────────────────
    raw: list[dict] = []
    with open(predictions_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                raw.append(json.loads(line))
    rows = _enrich(raw)

    feature_versions = list({r.get("feature_version", "unknown") for r in rows})
    feature_version = feature_versions[0] if len(feature_versions) == 1 else str(feature_versions)

    # ── Segment rows ─────────────────────────────────────────────
    all_rows = rows
    heavy_fav_rows = [r for r in rows if r["_fav_prob"] >= _HEAVY_FAV_THRESHOLD]
    high_conf_rows  = [r for r in rows if r["_fav_prob"] >= _HIGH_CONF_THRESHOLD]
    extreme_fav_rows = [r for r in rows if r["_fav_prob"] >= _EXTREME_FAV_THRESHOLD]
    phase45_rows = [
        r for r in rows
        if r["_fav_prob"] >= _PHASE45_FAIL_MIN_FAV and r["_fav_win"] == 0.0
    ]
    model_band_60_65_rows = [r for r in rows if 0.60 <= r["_model_fav_prob"] < 0.65]
    model_band_65_70_rows = [r for r in rows if 0.65 <= r["_model_fav_prob"] < 0.70]
    model_band_70_75_rows = [r for r in rows if 0.70 <= r["_model_fav_prob"] < 0.75]
    model_band_75_plus_rows = [r for r in rows if r["_model_fav_prob"] >= 0.75]

    # ── Compute segment metrics ──────────────────────────────────
    all_metrics = _compute_segment_metrics(all_rows)
    heavy_fav_metrics = _compute_segment_metrics(heavy_fav_rows)
    high_conf_metrics = _compute_segment_metrics(high_conf_rows)
    extreme_fav_metrics = _compute_segment_metrics(extreme_fav_rows)
    phase45_failure_metrics = _compute_segment_metrics(phase45_rows)
    model_band_60_65 = _compute_segment_metrics(model_band_60_65_rows)
    model_band_65_70 = _compute_segment_metrics(model_band_65_70_rows)
    model_band_70_75 = _compute_segment_metrics(model_band_70_75_rows)
    model_band_75_plus = _compute_segment_metrics(model_band_75_plus_rows)

    # ── Calibration residuals ────────────────────────────────────
    calibration_bands_blend = _compute_calibration_bands(
        rows, "_fav_prob", _BLEND_CALIB_BANDS
    )
    calibration_bands_model = _compute_calibration_bands(
        rows, "_model_fav_prob", _MODEL_CALIB_BANDS
    )

    # ── Disagreement analysis ────────────────────────────────────
    disagreement_buckets = _compute_disagreement_buckets(rows)

    # ── Model version profiles + architecture instability ────────
    model_version_profiles = _compute_model_version_profiles(rows)
    architecture_instability = _compute_architecture_instability(model_version_profiles)

    # ── Sharpness + blend dilution ───────────────────────────────
    ensemble_sharpness = _compute_ensemble_sharpness(rows)
    blend_dilution_checks = _compute_blend_dilution_checks(rows)

    # ── Negative controls ────────────────────────────────────────
    negative_controls = _run_negative_controls(rows, n_boot, rng)

    # ── Gate decision ────────────────────────────────────────────
    gate, gate_rationale, next_step, worth_phase69 = _determine_gate(
        all_metrics=all_metrics,
        heavy_fav_metrics=heavy_fav_metrics,
        calibration_bands_blend=calibration_bands_blend,
        disagreement_buckets=disagreement_buckets,
        negative_controls=negative_controls,
        architecture_instability=architecture_instability,
    )

    assert gate in _VALID_GATES, f"Gate {gate!r} not in _VALID_GATES"

    # ── Summary flags ─────────────────────────────────────────────
    calib_oc = any(b.is_overconfident for b in calibration_bands_blend)
    calib_uc = any(b.is_underconfident for b in calibration_bands_blend)
    dilution_hf = any(
        c.dilution_detected for c in blend_dilution_checks
        if c.segment == "heavy_fav_0.70"
    )

    return Phase68Report(
        phase_version=PHASE_VERSION,
        completion_marker=COMPLETION_MARKER,
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_path=str(predictions_path),
        candidate_patch_created=CANDIDATE_PATCH_CREATED,
        production_modified=PRODUCTION_MODIFIED,
        alpha_modified=ALPHA_MODIFIED,
        diagnostic_only=DIAGNOSTIC_ONLY,
        alpha=ALPHA,
        phase67_gate_anchor=PHASE67_GATE_ANCHOR,
        phase66_gate_anchor=PHASE66_GATE_ANCHOR,
        phase65_gate_anchor=PHASE65_GATE_ANCHOR,
        phase64b_gate_anchor=PHASE64B_GATE_ANCHOR,
        n_predictions=len(rows),
        feature_version=feature_version,
        all_metrics=all_metrics,
        heavy_fav_metrics=heavy_fav_metrics,
        high_conf_metrics=high_conf_metrics,
        extreme_fav_metrics=extreme_fav_metrics,
        phase45_failure_metrics=phase45_failure_metrics,
        model_band_60_65=model_band_60_65,
        model_band_65_70=model_band_65_70,
        model_band_70_75=model_band_70_75,
        model_band_75_plus=model_band_75_plus,
        calibration_bands_blend=calibration_bands_blend,
        calibration_bands_model=calibration_bands_model,
        disagreement_buckets=disagreement_buckets,
        model_version_profiles=model_version_profiles,
        architecture_instability=architecture_instability,
        ensemble_sharpness=ensemble_sharpness,
        blend_dilution_checks=blend_dilution_checks,
        negative_controls=negative_controls,
        gate=gate,
        gate_rationale=gate_rationale,
        next_step=next_step,
        calibration_overconfidence_detected=calib_oc,
        calibration_underconfidence_detected=calib_uc,
        blend_dilution_heavy_fav=dilution_hf,
        architecture_instability_detected=architecture_instability.instability_detected,
        overfit_risk_detected=gate == OVERFIT_RISK,
        worth_phase69=worth_phase69,
    )
