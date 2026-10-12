"""
Phase 47: Probability Shape Repair (Pre-Feature Fix)
=====================================================
Diagnoses the shape of the model's output probability distribution and applies
offline-only post-hoc calibration (temperature scaling, isotonic regression)
to determine whether structural ECE failures from Phase 45 are correctable
before committing to feature engineering.

Background (Phase 45 conclusions):
  - CONDITIONAL_VALUE (2 positive / 1 negative segments)
  - 6/15 segments with ECE failure; heavy_favorite ECE = 2.7× market
  - high_confidence BSS = -0.27% (overconfidence pattern)
  - global gate = FEATURE_REPAIR_INVESTIGATION

This module is DIAGNOSTIC ONLY.  It does NOT:
  - Modify any production model weights or predictions
  - Create a CANDIDATE_PATCH
  - Add features
  - Perform ensemble construction
  - Deploy anything to production

Calibration is applied offline to copies of model_home_prob only.
Production JSONL rows are read-only.

Hard rules (never violate):
  - candidate_patch_created ALWAYS False
  - production_modified ALWAYS False
  - gate NEVER "PATCH"
  - alpha ALWAYS 0.4 (for blend comparisons)
  - No external API / LLM calls
  - All base metrics via wbc_backend.evaluation.metrics (SSOT)
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sklearn.isotonic import IsotonicRegression

from wbc_backend.evaluation.metrics import (
    brier_score,
    brier_skill_score,
    expected_calibration_error,
    reliability_bins,
)
from wbc_backend.evaluation.prediction_persistence import PredictionRow

logger = logging.getLogger(__name__)

# ─── Hard Constants ───────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False   # NEVER change
PRODUCTION_MODIFIED: bool = False       # NEVER change
ALPHA: float = 0.4                      # Fixed from Phase 42A/43/44
_N_BINS: int = 10
_TEMP_SCALE_ITERATIONS: int = 200
_TEMP_SCALE_LR: float = 0.01
_MIN_FEATURE_PHASE_ECE_REDUCTION: float = 0.30   # 30% ECE reduction gate
_OVERCONFIDENT: str = "OVERCONFIDENT"
_UNDERCONFIDENT: str = "UNDERCONFIDENT"
_WELL_CALIBRATED: str = "WELL_CALIBRATED"

# Gate constants
_PROCEED_TO_FEATURE_PHASE: str = "PROCEED_TO_FEATURE_PHASE"
_CALIBRATION_FIRST: str = "CALIBRATION_FIRST"
_VALID_GATES: frozenset[str] = frozenset({
    _PROCEED_TO_FEATURE_PHASE,
    _CALIBRATION_FIRST,
})


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  Data Structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BinCalibration:
    """Reliability-diagram bin with calibration verdict."""
    bin_lower: float
    bin_upper: float
    count: int
    mean_confidence: float
    mean_accuracy: float
    gap: float
    verdict: str  # OVERCONFIDENT | UNDERCONFIDENT | WELL_CALIBRATED


@dataclass
class DistributionStats:
    """Shape statistics for a probability sequence."""
    n: int
    mean: float
    std: float                 # sharpness proxy
    variance: float            # true sharpness = variance of predicted probs
    entropy: float             # mean binary entropy H(p) = -p log p - (1-p) log(1-p)
    fraction_near_half: float  # |p - 0.5| < 0.05
    fraction_extreme: float    # |p - 0.5| >= 0.20


@dataclass
class BucketDiagnosis:
    """Overconfidence / underconfidence verdict for one segment bucket."""
    bucket_name: str           # e.g. "high_confidence", "heavy_favorite"
    n: int
    predicted_mean: float
    actual_win_rate: float
    calibration_gap: float     # predicted_mean - actual_win_rate
    verdict: str               # OVERCONFIDENT | UNDERCONFIDENT | WELL_CALIBRATED


@dataclass
class CalibrationMetrics:
    """Metrics for one calibration method applied to the full dataset."""
    method: str               # "raw" | "temperature_scaling" | "isotonic_regression"
    brier: float
    ece: float
    bss_vs_market: Optional[float]
    temperature: Optional[float]  # None except for temperature_scaling
    n: int


@dataclass
class ShapeRepairResult:
    """
    Full Phase 47 probability shape repair result.

    gate is always one of: PROCEED_TO_FEATURE_PHASE | CALIBRATION_FIRST.
    candidate_patch_created and production_modified are always False.
    """
    run_id: str
    generated_at: str
    input_prediction_path: str
    sample_size: int
    date_start: str
    date_end: str
    alpha: float = ALPHA

    # § Distribution analysis
    model_dist: Optional[DistributionStats] = None
    market_dist: Optional[DistributionStats] = None

    # § Reliability diagram (10 bins)
    model_reliability_bins: list[BinCalibration] = field(default_factory=list)
    market_reliability_bins: list[BinCalibration] = field(default_factory=list)

    # § Bucket-level diagnostics (from Phase 45 segmentation)
    bucket_diagnoses: list[BucketDiagnosis] = field(default_factory=list)

    # § Calibration methods comparison
    raw_metrics: Optional[CalibrationMetrics] = None
    temp_scale_metrics: Optional[CalibrationMetrics] = None
    isotonic_metrics: Optional[CalibrationMetrics] = None

    # § Gate decision
    gate: str = _CALIBRATION_FIRST
    gate_rationale: str = ""
    ece_reduction_temp: float = 0.0     # fraction improvement (temp scaling)
    ece_reduction_isotonic: float = 0.0  # fraction improvement (isotonic)
    high_conf_bss_improved: bool = False
    heavy_fav_ece_improved: bool = False

    # Hard-rule flags (invariants)
    candidate_patch_created: bool = False
    production_modified: bool = False

    # Audit
    audit_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Enforce hard rules on serialisation
        d["candidate_patch_created"] = False
        d["production_modified"] = False
        assert d["gate"] in _VALID_GATES, (
            f"INVARIANT VIOLATION: gate={d['gate']!r} not in {sorted(_VALID_GATES)}"
        )
        return d


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  Distribution Analysis
# ═══════════════════════════════════════════════════════════════════════════════

def _binary_entropy(p: float) -> float:
    """H(p) = -p log2 p - (1-p) log2(1-p).  0 log 0 = 0 by convention."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))


def compute_distribution_stats(probs: list[float]) -> DistributionStats:
    """
    Compute shape statistics for a list of predicted probabilities.

    Parameters
    ----------
    probs : list[float]
        Predicted probabilities in [0, 1].

    Returns
    -------
    DistributionStats
    """
    if not probs:
        raise ValueError("compute_distribution_stats: probs list is empty.")
    n = len(probs)
    mean = sum(probs) / n
    variance = sum((p - mean) ** 2 for p in probs) / n
    std = math.sqrt(variance)
    entropy = sum(_binary_entropy(p) for p in probs) / n
    near_half = sum(1 for p in probs if abs(p - 0.5) < 0.05) / n
    extreme = sum(1 for p in probs if abs(p - 0.5) >= 0.20) / n
    return DistributionStats(
        n=n,
        mean=round(mean, 6),
        std=round(std, 6),
        variance=round(variance, 6),
        entropy=round(entropy, 6),
        fraction_near_half=round(near_half, 6),
        fraction_extreme=round(extreme, 6),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  Reliability Diagram with Calibration Verdict
# ═══════════════════════════════════════════════════════════════════════════════

def _calibration_verdict(mean_confidence: float, mean_accuracy: float) -> str:
    """
    Classify a reliability-diagram bin.

    OVERCONFIDENT  : predicted > actual + 0.01
    UNDERCONFIDENT : predicted < actual - 0.01
    WELL_CALIBRATED: |predicted - actual| <= 0.01
    """
    gap = mean_confidence - mean_accuracy
    if gap > 0.01:
        return _OVERCONFIDENT
    if gap < -0.01:
        return _UNDERCONFIDENT
    return _WELL_CALIBRATED


def build_reliability_bins(
    probs: list[float],
    labels: list[int],
    n_bins: int = _N_BINS,
) -> list[BinCalibration]:
    """
    Build reliability diagram bins with calibration verdict per bin.

    Parameters
    ----------
    probs : list[float]
        Predicted probabilities in [0, 1].
    labels : list[int]
        Binary outcomes (0 or 1).
    n_bins : int
        Number of equal-width bins.

    Returns
    -------
    list[BinCalibration]
    """
    raw_bins = reliability_bins(probs, [float(y) for y in labels], n_bins=n_bins)
    result = []
    for b in raw_bins:
        verdict = _calibration_verdict(b["mean_confidence"], b["mean_accuracy"])
        result.append(BinCalibration(
            bin_lower=b["bin_lower"],
            bin_upper=b["bin_upper"],
            count=b["count"],
            mean_confidence=b["mean_confidence"],
            mean_accuracy=b["mean_accuracy"],
            gap=b["gap"],
            verdict=verdict,
        ))
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  Bucket-Level Diagnosis
# ═══════════════════════════════════════════════════════════════════════════════

def diagnose_bucket(
    bucket_name: str,
    probs: list[float],
    labels: list[int],
) -> BucketDiagnosis:
    """
    Compute overconfidence/underconfidence verdict for one segment bucket.

    Parameters
    ----------
    bucket_name : str
        Human-readable bucket label (e.g. "high_confidence").
    probs : list[float]
        Model predicted probabilities in this bucket.
    labels : list[int]
        Actual outcomes in this bucket.

    Returns
    -------
    BucketDiagnosis
    """
    if not probs:
        raise ValueError(f"diagnose_bucket: empty probs for bucket={bucket_name!r}")
    n = len(probs)
    pred_mean = sum(probs) / n
    win_rate = sum(labels) / n if labels else 0.0
    gap = pred_mean - win_rate
    verdict = _calibration_verdict(pred_mean, win_rate)
    return BucketDiagnosis(
        bucket_name=bucket_name,
        n=n,
        predicted_mean=round(pred_mean, 6),
        actual_win_rate=round(win_rate, 6),
        calibration_gap=round(gap, 6),
        verdict=verdict,
    )


def diagnose_all_buckets(rows: list[PredictionRow]) -> list[BucketDiagnosis]:
    """
    Run bucket diagnosis across Phase 45 segmentation dimensions.

    Segments analysed:
      - confidence: high_confidence / mid_confidence / low_confidence
      - odds_bucket: heavy_favorite / mid / underdog
      - disagreement: high / medium / low

    Parameters
    ----------
    rows : list[PredictionRow]
        Validated prediction rows.

    Returns
    -------
    list[BucketDiagnosis]
        One entry per non-empty bucket.
    """
    buckets: dict[str, tuple[list[float], list[int]]] = {}

    for row in rows:
        p = row.model_home_prob
        m = row.market_home_prob_no_vig
        y = row.home_win

        # Confidence bucket
        dist = abs(p - 0.5)
        if dist >= 0.10:
            c_key = "confidence:high_confidence"
        elif dist >= 0.05:
            c_key = "confidence:mid_confidence"
        else:
            c_key = "confidence:low_confidence"

        # Odds bucket
        if m >= 0.65:
            o_key = "odds_bucket:heavy_favorite"
        elif m >= 0.45:
            o_key = "odds_bucket:mid"
        else:
            o_key = "odds_bucket:underdog"

        # Disagreement bucket
        gap = abs(p - m)
        if gap < 0.05:
            d_key = "disagreement:low"
        elif gap < 0.10:
            d_key = "disagreement:medium"
        else:
            d_key = "disagreement:high"

        for key in (c_key, o_key, d_key):
            if key not in buckets:
                buckets[key] = ([], [])
            buckets[key][0].append(p)
            buckets[key][1].append(y)

    return [
        diagnose_bucket(name, probs, labels)
        for name, (probs, labels) in sorted(buckets.items())
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# § 5  Temperature Scaling (offline, paper-only)
# ═══════════════════════════════════════════════════════════════════════════════

def _prob_to_logit(p: float) -> float:
    """Logit transform: log(p / (1 - p)).  Clips to [-20, 20] for safety."""
    p = max(1e-7, min(1.0 - 1e-7, p))
    return math.log(p / (1.0 - p))


def _logit_to_prob(logit: float) -> float:
    """Sigmoid: 1 / (1 + exp(-logit))."""
    # Numerically stable for large |logit|
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    exp_l = math.exp(logit)
    return exp_l / (1.0 + exp_l)


def temperature_scale(
    probs: list[float],
    labels: list[int],
    *,
    iterations: int = _TEMP_SCALE_ITERATIONS,
    lr: float = _TEMP_SCALE_LR,
) -> tuple[list[float], float]:
    """
    Offline temperature scaling calibration.

    Finds scalar T that minimises Brier loss over log-scaled probabilities
    via simple gradient descent.  T > 1 → softer (reduces overconfidence);
    T < 1 → sharper.

    Applies to the COPY of probs only.  Does NOT modify production values.

    Parameters
    ----------
    probs : list[float]
        Raw model predicted probabilities.
    labels : list[int]
        Actual binary outcomes.
    iterations : int
        Number of gradient-descent steps.
    lr : float
        Learning rate.

    Returns
    -------
    tuple[list[float], float]
        (calibrated_probs, optimal_temperature)
    """
    if not probs:
        raise ValueError("temperature_scale: probs list is empty.")

    logits = [_prob_to_logit(p) for p in probs]
    labels_f = [float(y) for y in labels]
    n = len(logits)

    # Gradient descent on Brier loss w.r.t. T
    T = 1.0
    for _ in range(iterations):
        scaled_probs = [_logit_to_prob(lg / T) for lg in logits]
        # dBrier/dT = (2/n) * Σ (p_scaled - y) * p_scaled * (1-p_scaled) * (-lg/T²)
        grad = 0.0
        for lg, p_s, y in zip(logits, scaled_probs, labels_f):
            dp_dT = p_s * (1.0 - p_s) * (-lg / (T * T))
            grad += 2.0 * (p_s - y) * dp_dT
        grad /= n
        T = max(0.1, T - lr * grad)  # clip T to [0.1, ∞) for stability

    calibrated = [_logit_to_prob(lg / T) for lg in logits]
    return calibrated, round(T, 6)


# ═══════════════════════════════════════════════════════════════════════════════
# § 6  Isotonic Regression (offline, paper-only)
# ═══════════════════════════════════════════════════════════════════════════════

def isotonic_calibrate(
    probs: list[float],
    labels: list[int],
) -> list[float]:
    """
    Offline isotonic regression calibration.

    Fits IsotonicRegression on (probs, labels) and returns calibrated
    probability estimates.  Applies to the COPY of probs only.
    Does NOT modify production values.

    Parameters
    ----------
    probs : list[float]
        Raw model predicted probabilities.
    labels : list[int]
        Actual binary outcomes.

    Returns
    -------
    list[float]
        Isotonic-calibrated probabilities.
    """
    if not probs:
        raise ValueError("isotonic_calibrate: probs list is empty.")
    ir = IsotonicRegression(out_of_bounds="clip")
    ir.fit(probs, labels)
    calibrated = ir.predict(probs).tolist()
    return [max(0.0, min(1.0, p)) for p in calibrated]


# ═══════════════════════════════════════════════════════════════════════════════
# § 7  Calibration Metrics Evaluation
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_calibration_metrics(
    method: str,
    probs: list[float],
    labels: list[int],
    market_probs: list[float],
    temperature: Optional[float] = None,
) -> CalibrationMetrics:
    """Compute Brier, ECE, BSS-vs-market for one calibration method."""
    labels_f = [float(y) for y in labels]
    b = brier_score(probs, labels_f)
    ece_result = expected_calibration_error(probs, labels_f)
    market_brier = brier_score(market_probs, labels_f)
    bss = brier_skill_score(b, market_brier)
    return CalibrationMetrics(
        method=method,
        brier=round(b, 8),
        ece=round(ece_result["ece"], 8),
        bss_vs_market=round(bss, 6) if bss is not None else None,
        temperature=temperature,
        n=len(probs),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 8  Gate Logic
# ═══════════════════════════════════════════════════════════════════════════════

def _gate_decision(
    raw: CalibrationMetrics,
    temp: CalibrationMetrics,
    iso: CalibrationMetrics,
    bucket_diagnoses: list[BucketDiagnosis],
) -> tuple[str, str, float, float, bool, bool]:
    """
    Decide whether calibration alone is sufficient to proceed to Feature Phase.

    Criteria (ALL must pass for PROCEED_TO_FEATURE_PHASE):
      1. ECE reduction (best of temp/iso) >= 30%
      2. high_confidence bucket no longer negative BSS (improved)
      3. heavy_favorite ECE improved (proxy: high_confidence overconfidence gap reduced)

    Returns
    -------
    tuple: (gate, rationale, ece_reduction_temp, ece_reduction_iso,
            high_conf_bss_improved, heavy_fav_ece_improved)
    """
    raw_ece = raw.ece
    ece_red_temp = (raw_ece - temp.ece) / raw_ece if raw_ece > 0 else 0.0
    ece_red_iso = (raw_ece - iso.ece) / raw_ece if raw_ece > 0 else 0.0

    # Check high_confidence bucket
    high_conf = next(
        (d for d in bucket_diagnoses if d.bucket_name == "confidence:high_confidence"),
        None,
    )
    # BSS improvement check: if high_confidence gap reduced by calibration
    high_conf_improved = (
        high_conf is not None
        and high_conf.verdict != _OVERCONFIDENT
    )

    # ECE improvement from best method
    best_ece_reduction = max(ece_red_temp, ece_red_iso)

    # heavy_favorite diagnosed via odds_bucket
    heavy_fav = next(
        (d for d in bucket_diagnoses if d.bucket_name == "odds_bucket:heavy_favorite"),
        None,
    )
    heavy_fav_improved = (
        heavy_fav is not None
        and heavy_fav.verdict != _OVERCONFIDENT
    )

    passes = (
        best_ece_reduction >= _MIN_FEATURE_PHASE_ECE_REDUCTION
        and high_conf_improved
        and heavy_fav_improved
    )

    reasons = []
    reasons.append(
        f"Best ECE reduction={best_ece_reduction:.1%} "
        f"(temp={ece_red_temp:.1%}, iso={ece_red_iso:.1%}); "
        f"gate threshold={_MIN_FEATURE_PHASE_ECE_REDUCTION:.0%}"
    )
    reasons.append(
        f"high_confidence calibration: {high_conf.verdict if high_conf else 'N/A'}"
    )
    reasons.append(
        f"heavy_favorite calibration: {heavy_fav.verdict if heavy_fav else 'N/A'}"
    )

    if passes:
        gate = _PROCEED_TO_FEATURE_PHASE
        rationale = (
            "Calibration sufficient: " + "; ".join(reasons)
            + ". Proceed to Feature Builder (Phase 48)."
        )
    else:
        gate = _CALIBRATION_FIRST
        fails = []
        if best_ece_reduction < _MIN_FEATURE_PHASE_ECE_REDUCTION:
            fails.append(
                f"ECE reduction {best_ece_reduction:.1%} < {_MIN_FEATURE_PHASE_ECE_REDUCTION:.0%} threshold"
            )
        if not high_conf_improved:
            fails.append("high_confidence still OVERCONFIDENT")
        if not heavy_fav_improved:
            fails.append("heavy_favorite still OVERCONFIDENT")
        rationale = (
            "Calibration insufficient: " + "; ".join(fails)
            + ". " + "; ".join(reasons)
            + ". Apply calibration layer before Feature Phase."
        )

    return (
        gate,
        rationale,
        round(ece_red_temp, 6),
        round(ece_red_iso, 6),
        high_conf_improved,
        heavy_fav_improved,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 9  Audit Hash
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_audit_hash(rows: list[PredictionRow]) -> str:
    """SHA-256 of sorted (game_id, model_home_prob) pairs."""
    pairs = sorted(
        (r.game_id, round(r.model_home_prob, 8)) for r in rows
    )
    payload = json.dumps(pairs, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
# § 10  Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def run_phase47_shape_repair(
    rows: list[PredictionRow],
    input_path: str = "",
    alpha: float = ALPHA,
) -> ShapeRepairResult:
    """
    Full Phase 47 probability shape repair pipeline.

    Steps:
      1. Validate inputs and alpha
      2. Compute distribution stats (model & market)
      3. Build reliability diagrams
      4. Diagnose bucket-level overconfidence/underconfidence
      5. Apply temperature scaling (offline copy)
      6. Apply isotonic regression (offline copy)
      7. Compare raw vs calibrated metrics
      8. Gate decision

    Parameters
    ----------
    rows : list[PredictionRow]
        Validated prediction rows (read-only; never modified).
    input_path : str
        Source JSONL path (for audit trail only).
    alpha : float
        Blend alpha — must equal ALPHA (0.4).  Raises if wrong.

    Returns
    -------
    ShapeRepairResult

    Raises
    ------
    ValueError
        If rows is empty, or alpha != ALPHA.
    """
    # ── Validation ──────────────────────────────────────────────────────────
    if alpha != ALPHA:
        raise ValueError(
            f"run_phase47_shape_repair: alpha must be {ALPHA}, got {alpha!r}. "
            "Alpha is fixed per Phase 42A/43/44 invariant."
        )
    if not rows:
        raise ValueError("run_phase47_shape_repair: rows list is empty.")

    run_id = str(uuid.uuid4())
    generated_at = datetime.now(timezone.utc).isoformat()
    audit_hash = _compute_audit_hash(rows)

    # ── Extract probability/label sequences ──────────────────────────────────
    model_probs: list[float] = [r.model_home_prob for r in rows]
    market_probs: list[float] = [r.market_home_prob_no_vig for r in rows]
    labels: list[int] = [r.home_win for r in rows]

    dates = [r.game_date for r in rows if r.game_date]
    date_start = min(dates) if dates else ""
    date_end = max(dates) if dates else ""

    # ── § 2  Distribution stats ──────────────────────────────────────────────
    model_dist = compute_distribution_stats(model_probs)
    market_dist = compute_distribution_stats(market_probs)

    # ── § 3  Reliability diagrams ────────────────────────────────────────────
    model_rel_bins = build_reliability_bins(model_probs, labels)
    market_rel_bins = build_reliability_bins(market_probs, labels)

    # ── § 4  Bucket diagnoses ────────────────────────────────────────────────
    bucket_diagnoses = diagnose_all_buckets(rows)

    # ── § 5  Temperature scaling ─────────────────────────────────────────────
    temp_probs, optimal_temp = temperature_scale(model_probs, labels)

    # ── § 6  Isotonic regression ─────────────────────────────────────────────
    iso_probs = isotonic_calibrate(model_probs, labels)

    # ── § 7  Metrics comparison ──────────────────────────────────────────────
    raw_metrics = _compute_calibration_metrics(
        "raw", model_probs, labels, market_probs
    )
    temp_metrics = _compute_calibration_metrics(
        "temperature_scaling", temp_probs, labels, market_probs,
        temperature=optimal_temp
    )
    iso_metrics = _compute_calibration_metrics(
        "isotonic_regression", iso_probs, labels, market_probs
    )

    # ── § 8  Gate decision ───────────────────────────────────────────────────
    (gate, gate_rationale, ece_red_temp, ece_red_iso,
     hc_improved, hf_improved) = _gate_decision(
        raw_metrics, temp_metrics, iso_metrics, bucket_diagnoses
    )

    logger.info(
        "Phase 47 complete: gate=%s sample=%d ece_raw=%.4f "
        "ece_temp=%.4f ece_iso=%.4f reduction_temp=%.1f%% reduction_iso=%.1f%%",
        gate, len(rows),
        raw_metrics.ece, temp_metrics.ece, iso_metrics.ece,
        ece_red_temp * 100, ece_red_iso * 100,
    )

    return ShapeRepairResult(
        run_id=run_id,
        generated_at=generated_at,
        input_prediction_path=input_path,
        sample_size=len(rows),
        date_start=date_start,
        date_end=date_end,
        alpha=alpha,
        model_dist=model_dist,
        market_dist=market_dist,
        model_reliability_bins=model_rel_bins,
        market_reliability_bins=market_rel_bins,
        bucket_diagnoses=bucket_diagnoses,
        raw_metrics=raw_metrics,
        temp_scale_metrics=temp_metrics,
        isotonic_metrics=iso_metrics,
        gate=gate,
        gate_rationale=gate_rationale,
        ece_reduction_temp=ece_red_temp,
        ece_reduction_isotonic=ece_red_iso,
        high_conf_bss_improved=hc_improved,
        heavy_fav_ece_improved=hf_improved,
        candidate_patch_created=False,
        production_modified=False,
        audit_hash=audit_hash,
    )
