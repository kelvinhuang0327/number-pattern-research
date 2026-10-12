"""
orchestrator/phase59_pre_heavy_favorite_local_calibration.py
=============================================================
Phase 59-Pre+ — Heavy-Favorite Local Calibration Counterfactual
with OOF / PIT-safe Validation

Purpose:
  Before investing in Phase59 real bullpen boxscore acquisition,
  determine whether heavy_favorite / high_confidence ECE failures
  can be fixed by local isotonic / Platt calibration — using strictly
  OOF / time-split validation to avoid in-sample overfit.

Hard Rules (never violate):
  - CANDIDATE_PATCH_CREATED = False
  - PRODUCTION_MODIFIED = False
  - ALPHA_MODIFIED = False
  - All calibration training data must have game_date < evaluation game_date
  - No game result from date D may be used to calibrate a prediction from date D

Gate Outcomes:
  LOCAL_CALIBRATION_SUFFICIENT   — heavy_fav ECE improved, bootstrap CI > 0
  BULLPEN_HYPOTHESIS_RETAINED    — calibration fails to fix heavy_fav ECE
  MIXED                          — partial improvement, inconclusive
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# ─── Third-party (venv only) ──────────────────────────────────────────────────
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

# ─── Internal ────────────────────────────────────────────────────────────────
from wbc_backend.evaluation.metrics import (
    brier_score,
    brier_skill_score,
    expected_calibration_error,
)

# ═══════════════════════════════════════════════════════════════════════════════
# § 0  Hard-coded safety constants
# ═══════════════════════════════════════════════════════════════════════════════

CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
ALPHA_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True

PHASE_VERSION: str = "phase59_pre_heavy_favorite_local_calibration_v1"
ALPHA: float = 0.4                    # market blend weight — MUST NOT be changed

# Calibration gate labels
LOCAL_CALIBRATION_SUFFICIENT: str = "LOCAL_CALIBRATION_SUFFICIENT"
BULLPEN_HYPOTHESIS_RETAINED: str = "BULLPEN_HYPOTHESIS_RETAINED"
MIXED: str = "MIXED"
BLOCKED_INSUFFICIENT_DATA: str = "BLOCKED_INSUFFICIENT_DATA"

_VALID_GATES = frozenset({
    LOCAL_CALIBRATION_SUFFICIENT,
    BULLPEN_HYPOTHESIS_RETAINED,
    MIXED,
    BLOCKED_INSUFFICIENT_DATA,
})

# Probability bucket boundaries — applied to max(p, 1-p) of blend prob
PROB_BUCKETS: list[tuple[float, float, str]] = [
    (0.50, 0.60, "0.50-0.60"),
    (0.60, 0.70, "0.60-0.70"),
    (0.70, 0.80, "0.70-0.80"),
    (0.80, 0.90, "0.80-0.90"),
    (0.90, 1.01, "0.90+"),
]

# Minimum rows needed in evaluation split to report calibration metrics
MIN_EVAL_ROWS: int = 50
MIN_HEAVY_FAV_EVAL: int = 10

# Bootstrap parameters
BOOTSTRAP_N: int = 1000
BOOTSTRAP_SEED: int = 42

# ═══════════════════════════════════════════════════════════════════════════════
# § 1  Dataclasses
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BucketMetrics:
    bucket: str
    n: int
    baseline_ece: float
    isotonic_ece: float
    platt_ece: float
    baseline_bss: float
    isotonic_bss: float
    platt_bss: float


@dataclass
class CalibrationVariantResult:
    """Metrics for one calibration variant (baseline / isotonic / Platt)."""
    name: str
    overall_bss: float
    overall_ece: float
    heavy_fav_ece: float
    heavy_fav_n: int
    high_conf_bss: float
    high_conf_n: int
    phase45_failure_segment_count: int
    bootstrap_ci_lower: float
    bootstrap_ci_upper: float
    bootstrap_prob_improvement: float
    bootstrap_significant: bool
    buckets: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class NegativeControlResult:
    """Shuffled-label sanity check — should show no improvement."""
    shuffled_isotonic_heavy_fav_ece: float
    shuffled_platt_heavy_fav_ece: float
    baseline_heavy_fav_ece: float
    sanity_ok: bool           # True if shuffled is NOT better than baseline


@dataclass
class Phase59PreResult:
    """Top-level result container."""
    phase_version: str
    run_timestamp: str
    audit_hash: str

    # Input artifact metadata
    input_jsonl_path: str
    input_audit_hash: str
    sample_size: int
    date_range_start: str
    date_range_end: str

    # Calibration validation strategy used
    validation_strategy: str       # "rolling_monthly_oof"
    train_months: list[str]
    eval_months: list[str]
    n_train: int
    n_eval: int

    # Per-variant results
    baseline: CalibrationVariantResult
    isotonic: CalibrationVariantResult
    platt: CalibrationVariantResult

    # Bucket-level metrics table
    bucket_metrics: list[BucketMetrics]

    # Negative control
    negative_control: NegativeControlResult

    # Gate conclusion
    gate: str
    gate_rationale: str
    next_step_recommendation: str

    # Safety flags
    candidate_patch_created: bool = CANDIDATE_PATCH_CREATED
    production_modified: bool = PRODUCTION_MODIFIED
    alpha_modified: bool = ALPHA_MODIFIED
    diagnostic_only: bool = DIAGNOSTIC_ONLY


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  PIT / leakage guard
# ═══════════════════════════════════════════════════════════════════════════════

def assert_no_lookahead(
    train_dates: list[str],
    eval_dates: list[str],
) -> None:
    """
    Raise ValueError if any eval_date <= max(train_date).

    This is the primary PIT safety gate: calibrator must be trained only
    on data strictly older than every row in the evaluation set.
    """
    if not train_dates or not eval_dates:
        return
    max_train = max(train_dates)
    min_eval = min(eval_dates)
    if min_eval <= max_train:
        raise ValueError(
            f"PIT VIOLATION: eval min_date={min_eval} <= train max_date={max_train}. "
            "Calibration training data must be strictly older than evaluation data."
        )


def assert_no_result_feature(row: dict[str, Any]) -> None:
    """
    Raise ValueError if a row uses post-game result as a calibration input.

    The fields home_win / final_score / game_result must never be used as
    inputs when computing calibrated probability for that same game.
    This function is invoked on each training row to ensure the calibrator
    only trains on (prob → label) pairs — not on forbidden feature columns.
    """
    forbidden = {"final_score", "game_result"}
    for key in forbidden:
        if key in row and row[key] is not None:
            raise ValueError(
                f"PIT VIOLATION: forbidden result feature '{key}' found in row. "
                "Only home_win (as label) is permitted; not as a calibration feature."
            )


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  Data loading and preprocessing
# ═══════════════════════════════════════════════════════════════════════════════

def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _blend_prob(model_p: float, market_p: float, alpha: float = ALPHA) -> float:
    """Compute market-blended probability: (1-alpha)*model + alpha*market."""
    return (1.0 - alpha) * model_p + alpha * market_p


def _validate_row(row: dict[str, Any]) -> bool:
    """Return True if a row has all required fields with valid values."""
    try:
        model_p = float(row.get("model_home_prob", -1))
        market_p = float(row.get("market_home_prob_no_vig", -1))
        home_win = row.get("home_win")
        game_date = row.get("game_date", "")
        if model_p < 0 or model_p > 1:
            return False
        if market_p < 0 or market_p > 1:
            return False
        if home_win not in (0, 1):
            return False
        if not game_date or len(game_date) < 10:
            return False
        return True
    except (TypeError, ValueError):
        return False


def _favorite_prob(blend_p: float) -> float:
    """Return the 'favorite-side' probability: max(blend_p, 1-blend_p)."""
    return max(blend_p, 1.0 - blend_p)


def _odds_bucket(fav_p: float) -> str:
    for lo, hi, label in PROB_BUCKETS:
        if lo <= fav_p < hi:
            return label
    return "0.90+"


def _prepare_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Filter and enrich rows with computed fields.
    Raises ValueError if any row contains forbidden result features.
    """
    out = []
    for row in rows:
        assert_no_result_feature(row)
        if not _validate_row(row):
            continue
        model_p = float(row["model_home_prob"])
        market_p = float(row["market_home_prob_no_vig"])
        blend_p = _blend_prob(model_p, market_p)
        fav_p = _favorite_prob(blend_p)
        out.append({
            **row,
            "_blend_prob": blend_p,
            "_fav_prob": fav_p,
            "_bucket": _odds_bucket(fav_p),
            "_label": int(row["home_win"]),
            "_month": row["game_date"][:7],   # "YYYY-MM"
        })
    return sorted(out, key=lambda r: r["game_date"])


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  OOF Rolling Monthly Calibration
# ═══════════════════════════════════════════════════════════════════════════════

def _rolling_monthly_oof(
    records: list[dict[str, Any]],
    *,
    min_train_months: int = 2,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """
    Build OOF calibration splits using rolling monthly scheme.

    For each month M (in chronological order), train calibrator on all
    data with game_date < first day of M, evaluate on data in month M.
    The result is a dataset where every row has an OOF-calibrated probability
    derived from a calibrator that never saw that row during training.

    Returns:
        eval_records  — rows in the evaluation set with OOF probs attached
        train_months  — list of months used only for training
        eval_months   — list of months that received OOF predictions
    """
    months = sorted(set(r["_month"] for r in records))
    if len(months) < min_train_months + 1:
        return [], [], []

    # Months before index min_train_months go to training-only
    # Remaining months get OOF evaluation
    train_only_months = months[:min_train_months]
    eval_month_list = months[min_train_months:]

    eval_records: list[dict[str, Any]] = []

    for eval_month in eval_month_list:
        # Training = all data strictly before this eval_month
        train_rows = [r for r in records if r["_month"] < eval_month]
        test_rows = [r for r in records if r["_month"] == eval_month]

        if len(train_rows) < 20 or len(test_rows) < 5:
            # Too few rows; include test rows without calibration
            for r in test_rows:
                eval_records.append({
                    **r,
                    "_iso_prob": r["_blend_prob"],
                    "_platt_prob": r["_blend_prob"],
                    "_calibrated": False,
                    "_calibration_train_n": len(train_rows),
                })
            continue

        # PIT guard — must pass before fitting any calibrator
        train_dates = [r["game_date"] for r in train_rows]
        eval_dates = [r["game_date"] for r in test_rows]
        assert_no_lookahead(train_dates, eval_dates)

        train_X = [[r["_blend_prob"]] for r in train_rows]
        train_y = [r["_label"] for r in train_rows]
        test_X = [[r["_blend_prob"]] for r in test_rows]

        # Isotonic regression (monotone)
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit([x[0] for x in train_X], train_y)
        iso_probs = [float(p) for p in iso.predict([x[0] for x in test_X])]

        # Platt / logistic scaling
        lr = LogisticRegression(max_iter=500, C=1.0, solver="lbfgs")
        lr.fit(train_X, train_y)
        platt_probs = [float(p) for p in lr.predict_proba(test_X)[:, 1]]

        for row, ip, pp in zip(test_rows, iso_probs, platt_probs):
            eval_records.append({
                **row,
                "_iso_prob": ip,
                "_platt_prob": pp,
                "_calibrated": True,
                "_calibration_train_n": len(train_rows),
            })

    return eval_records, train_only_months, eval_month_list


# ═══════════════════════════════════════════════════════════════════════════════
# § 5  Metrics computation
# ═══════════════════════════════════════════════════════════════════════════════

_CLIMATE_BRIER = 0.25   # baseline climate (50/50 guesser)


def _compute_bss(probs: list[float], labels: list[int]) -> float:
    """BSS vs climatological baseline (0.25)."""
    if not probs:
        return float("nan")
    b = brier_score(probs, labels)
    return brier_skill_score(b, _CLIMATE_BRIER)


def _compute_ece(probs: list[float], labels: list[int], n_bins: int = 10) -> float:
    if not probs:
        return float("nan")
    result = expected_calibration_error(probs, labels, n_bins=n_bins)
    return result["ece"]


def _phase45_failure_count(
    eval_records: list[dict[str, Any]],
    prob_key: str,
) -> int:
    """
    Count segments that still fail Phase45 criteria:
    - heavy_favorite: ECE > 0.05
    - high_confidence: BSS < -0.001
    These thresholds replicate Phase45's failure_segments logic.
    """
    count = 0
    heavy_rows = [r for r in eval_records if r["_fav_prob"] >= 0.70]
    if heavy_rows:
        probs = [r[prob_key] for r in heavy_rows]
        labels = [r["_label"] for r in heavy_rows]
        ece = _compute_ece(probs, labels)
        if ece > 0.05:
            count += 1

    high_conf_rows = [r for r in eval_records if r["_fav_prob"] >= 0.65]
    if high_conf_rows:
        probs = [r[prob_key] for r in high_conf_rows]
        labels = [r["_label"] for r in high_conf_rows]
        bss = _compute_bss(probs, labels)
        if not math.isnan(bss) and bss < -0.001:
            count += 1

    return count


def _bootstrap_ci(
    eval_records: list[dict[str, Any]],
    variant_key: str,
    *,
    n_bootstrap: int = BOOTSTRAP_N,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float, float]:
    """
    Bootstrap CI for BSS improvement of calibrated variant vs baseline.

    Returns: (ci_lower, ci_upper, prob_improvement)
    """
    rng = random.Random(seed)
    n = len(eval_records)
    if n < 30:
        return float("nan"), float("nan"), float("nan")

    deltas: list[float] = []
    for _ in range(n_bootstrap):
        sample = [rng.choice(eval_records) for _ in range(n)]
        base_probs = [r["_blend_prob"] for r in sample]
        var_probs = [r[variant_key] for r in sample]
        labels = [r["_label"] for r in sample]
        base_bss = _compute_bss(base_probs, labels)
        var_bss = _compute_bss(var_probs, labels)
        if not math.isnan(base_bss) and not math.isnan(var_bss):
            deltas.append(var_bss - base_bss)

    if not deltas:
        return float("nan"), float("nan"), float("nan")

    deltas.sort()
    lo = deltas[int(0.025 * len(deltas))]
    hi = deltas[int(0.975 * len(deltas))]
    prob = sum(1 for d in deltas if d > 0) / len(deltas)
    return lo, hi, prob


def _compute_variant_result(
    name: str,
    eval_records: list[dict[str, Any]],
    prob_key: str,
) -> CalibrationVariantResult:
    """Compute all metrics for one probability variant."""
    if not eval_records:
        return CalibrationVariantResult(
            name=name, overall_bss=float("nan"), overall_ece=float("nan"),
            heavy_fav_ece=float("nan"), heavy_fav_n=0,
            high_conf_bss=float("nan"), high_conf_n=0,
            phase45_failure_segment_count=0,
            bootstrap_ci_lower=float("nan"), bootstrap_ci_upper=float("nan"),
            bootstrap_prob_improvement=float("nan"),
            bootstrap_significant=False, buckets=[],
        )

    all_probs = [r[prob_key] for r in eval_records]
    all_labels = [r["_label"] for r in eval_records]

    overall_bss = _compute_bss(all_probs, all_labels)
    overall_ece = _compute_ece(all_probs, all_labels)

    heavy_rows = [r for r in eval_records if r["_fav_prob"] >= 0.70]
    heavy_fav_ece = (
        _compute_ece([r[prob_key] for r in heavy_rows], [r["_label"] for r in heavy_rows])
        if heavy_rows else float("nan")
    )

    high_conf_rows = [r for r in eval_records if r["_fav_prob"] >= 0.65]
    high_conf_bss = (
        _compute_bss([r[prob_key] for r in high_conf_rows], [r["_label"] for r in high_conf_rows])
        if high_conf_rows else float("nan")
    )

    failure_count = _phase45_failure_count(eval_records, prob_key)

    ci_lo, ci_hi, prob_imp = _bootstrap_ci(eval_records, prob_key)
    significant = (
        not math.isnan(ci_lo)
        and not math.isnan(ci_hi)
        and ci_lo > 0
    )

    # Bucket metrics
    bucket_dicts = []
    for _, _, bucket_label in PROB_BUCKETS:
        bucket_rows = [r for r in eval_records if r["_bucket"] == bucket_label]
        if bucket_rows:
            bp = [r[prob_key] for r in bucket_rows]
            bl = [r["_label"] for r in bucket_rows]
            bucket_dicts.append({
                "bucket": bucket_label,
                "n": len(bucket_rows),
                "ece": _compute_ece(bp, bl),
                "bss": _compute_bss(bp, bl),
            })

    return CalibrationVariantResult(
        name=name,
        overall_bss=overall_bss,
        overall_ece=overall_ece,
        heavy_fav_ece=heavy_fav_ece,
        heavy_fav_n=len(heavy_rows),
        high_conf_bss=high_conf_bss,
        high_conf_n=len(high_conf_rows),
        phase45_failure_segment_count=failure_count,
        bootstrap_ci_lower=ci_lo,
        bootstrap_ci_upper=ci_hi,
        bootstrap_prob_improvement=prob_imp,
        bootstrap_significant=significant,
        buckets=bucket_dicts,
    )


def _bucket_comparison(
    eval_records: list[dict[str, Any]],
) -> list[BucketMetrics]:
    """Build cross-variant bucket comparison table."""
    result = []
    for _, _, bucket_label in PROB_BUCKETS:
        rows = [r for r in eval_records if r["_bucket"] == bucket_label]
        if not rows:
            continue
        bm = BucketMetrics(
            bucket=bucket_label,
            n=len(rows),
            baseline_ece=_compute_ece([r["_blend_prob"] for r in rows], [r["_label"] for r in rows]),
            isotonic_ece=_compute_ece([r["_iso_prob"] for r in rows], [r["_label"] for r in rows]),
            platt_ece=_compute_ece([r["_platt_prob"] for r in rows], [r["_label"] for r in rows]),
            baseline_bss=_compute_bss([r["_blend_prob"] for r in rows], [r["_label"] for r in rows]),
            isotonic_bss=_compute_bss([r["_iso_prob"] for r in rows], [r["_label"] for r in rows]),
            platt_bss=_compute_bss([r["_platt_prob"] for r in rows], [r["_label"] for r in rows]),
        )
        result.append(bm)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# § 6  Negative control (shuffled labels)
# ═══════════════════════════════════════════════════════════════════════════════

def _run_negative_control(
    eval_records: list[dict[str, Any]],
    all_records: list[dict[str, Any]],
    *,
    seed: int = 9999,
) -> NegativeControlResult:
    """
    Shuffled-label negative control.

    Repeat the OOF calibration but with randomly shuffled labels in training data.
    The calibrated probabilities should NOT improve on heavy_fav ECE — if they do,
    it is a sign of overfitting or data leakage.
    """
    rng = random.Random(seed)

    # Shuffle labels in all records
    shuffled_records = []
    labels = [r["_label"] for r in all_records]
    rng.shuffle(labels)
    for rec, lbl in zip(all_records, labels):
        shuffled_records.append({**rec, "_label": lbl, "home_win": lbl})

    shuffled_eval, _, _ = _rolling_monthly_oof(shuffled_records)

    if not shuffled_eval:
        return NegativeControlResult(
            shuffled_isotonic_heavy_fav_ece=float("nan"),
            shuffled_platt_heavy_fav_ece=float("nan"),
            baseline_heavy_fav_ece=float("nan"),
            sanity_ok=True,
        )

    heavy_shuffled = [r for r in shuffled_eval if r["_fav_prob"] >= 0.70]
    sh_iso_ece = (
        _compute_ece([r["_iso_prob"] for r in heavy_shuffled], [r["_label"] for r in heavy_shuffled])
        if heavy_shuffled else float("nan")
    )
    sh_platt_ece = (
        _compute_ece([r["_platt_prob"] for r in heavy_shuffled], [r["_label"] for r in heavy_shuffled])
        if heavy_shuffled else float("nan")
    )

    heavy_base = [r for r in eval_records if r["_fav_prob"] >= 0.70]
    base_ece = (
        _compute_ece([r["_blend_prob"] for r in heavy_base], [r["_label"] for r in heavy_base])
        if heavy_base else float("nan")
    )

    # Sanity: shuffled calibrated ECE should NOT be clearly better than real baseline
    # We allow ±0.01 tolerance due to random variation
    sanity_ok = True
    for ece in [sh_iso_ece, sh_platt_ece]:
        if not math.isnan(ece) and not math.isnan(base_ece):
            if ece < base_ece - 0.01:
                sanity_ok = False

    return NegativeControlResult(
        shuffled_isotonic_heavy_fav_ece=sh_iso_ece,
        shuffled_platt_heavy_fav_ece=sh_platt_ece,
        baseline_heavy_fav_ece=base_ece,
        sanity_ok=sanity_ok,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 7  Gate recommendation
# ═══════════════════════════════════════════════════════════════════════════════

def _recommend_gate(
    baseline: CalibrationVariantResult,
    isotonic: CalibrationVariantResult,
    platt: CalibrationVariantResult,
    n_eval: int,
    n_heavy_fav: int,
) -> tuple[str, str, str]:
    """
    Determine gate outcome and next-step recommendation.

    Logic:
    1. If n_eval < MIN_EVAL_ROWS or n_heavy_fav < MIN_HEAVY_FAV_EVAL:
       → BLOCKED_INSUFFICIENT_DATA
    2. If both isotonic and Platt significantly improve heavy_fav ECE
       AND at least one bootstrap CI strictly > 0:
       → LOCAL_CALIBRATION_SUFFICIENT
    3. If neither variant improves heavy_fav ECE:
       → BULLPEN_HYPOTHESIS_RETAINED
    4. Otherwise: MIXED
    """
    if n_eval < MIN_EVAL_ROWS or n_heavy_fav < MIN_HEAVY_FAV_EVAL:
        return (
            BLOCKED_INSUFFICIENT_DATA,
            f"Insufficient evaluation data: n_eval={n_eval} (min={MIN_EVAL_ROWS}), "
            f"n_heavy_fav={n_heavy_fav} (min={MIN_HEAVY_FAV_EVAL}).",
            "Collect more data before re-running this experiment.",
        )

    base_hf_ece = baseline.heavy_fav_ece
    iso_hf_ece = isotonic.heavy_fav_ece
    platt_hf_ece = platt.heavy_fav_ece

    nan_ece = math.isnan(base_hf_ece) or math.isnan(iso_hf_ece) or math.isnan(platt_hf_ece)
    if nan_ece:
        return (
            BLOCKED_INSUFFICIENT_DATA,
            "Cannot compute heavy_fav ECE — NaN returned. Likely too few heavy_fav rows in eval split.",
            "Collect more heavy_favorite game data or widen eval split.",
        )

    # Improvement threshold: ECE must drop by >= 10% relative or 0.005 absolute
    iso_improves = (base_hf_ece - iso_hf_ece) > max(0.005, 0.10 * base_hf_ece)
    platt_improves = (base_hf_ece - platt_hf_ece) > max(0.005, 0.10 * base_hf_ece)
    any_sig_bootstrap = isotonic.bootstrap_significant or platt.bootstrap_significant

    if iso_improves and platt_improves and any_sig_bootstrap:
        rationale = (
            f"Both isotonic (ECE {iso_hf_ece:.4f}) and Platt (ECE {platt_hf_ece:.4f}) "
            f"substantially improve heavy_fav ECE vs baseline ({base_hf_ece:.4f}). "
            f"Bootstrap CI is statistically significant for at least one variant."
        )
        recommendation = (
            "Temporarily suspend Phase59 bullpen acquisition. "
            "Design a local calibration paper-only patch gate with OOF validation "
            "before committing to bullpen feature engineering."
        )
        return LOCAL_CALIBRATION_SUFFICIENT, rationale, recommendation

    elif not iso_improves and not platt_improves:
        rationale = (
            f"Neither isotonic (ECE {iso_hf_ece:.4f}) nor Platt (ECE {platt_hf_ece:.4f}) "
            f"substantially improves heavy_fav ECE vs baseline ({base_hf_ece:.4f}). "
            "Calibration layer is not the bottleneck."
        )
        recommendation = (
            "Proceed to Phase59: acquire real bullpen boxscore / relief appearance data. "
            "Bullpen feature hypothesis remains the primary candidate explanation "
            "for heavy_favorite / high_confidence ECE failures."
        )
        return BULLPEN_HYPOTHESIS_RETAINED, rationale, recommendation

    else:
        improved_names = []
        if iso_improves:
            improved_names.append(f"isotonic (ECE {iso_hf_ece:.4f})")
        if platt_improves:
            improved_names.append(f"Platt (ECE {platt_hf_ece:.4f})")
        rationale = (
            f"Mixed results: {', '.join(improved_names)} improve heavy_fav ECE vs baseline "
            f"({base_hf_ece:.4f}), but not both. Bootstrap not significant."
        )
        recommendation = (
            "Run Phase59 bullpen acquisition AND local calibration SSOT/guard in parallel. "
            "Calibration improvement is partial — do not treat as production-ready."
        )
        return MIXED, rationale, recommendation


# ═══════════════════════════════════════════════════════════════════════════════
# § 8  Audit hash
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_audit_hash(
    n_records: int,
    date_start: str,
    date_end: str,
    gate: str,
    baseline_heavy_fav_ece: float,
) -> str:
    payload = f"{PHASE_VERSION}|{n_records}|{date_start}|{date_end}|{gate}|{baseline_heavy_fav_ece:.6f}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════════════
# § 9  Main entry point
# ═══════════════════════════════════════════════════════════════════════════════

def run_phase59_pre(
    input_jsonl: Path,
    *,
    n_bootstrap: int = BOOTSTRAP_N,
    min_train_months: int = 2,
    verbose: bool = False,
) -> Phase59PreResult:
    """
    Run Phase 59-Pre heavy-favorite local calibration counterfactual.

    Steps:
      1. Load and validate baseline prediction JSONL
      2. Enrich with blend prob and bucket labels
      3. Build OOF rolling monthly calibration splits
      4. Fit isotonic + Platt calibrators (never in-sample)
      5. Compute metrics: BSS, ECE, bucket-level ECE, heavy_fav, high_conf
      6. Bootstrap CI for each variant
      7. Run shuffled-label negative control
      8. Determine gate conclusion
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    # ── Load input ─────────────────────────────────────────────────────────────
    raw_rows = _load_jsonl(input_jsonl)
    input_audit_hash = raw_rows[0].get("audit_hash", "unknown") if raw_rows else "unknown"

    records = _prepare_records(raw_rows)
    n_total = len(records)

    if n_total == 0:
        raise ValueError(f"No valid prediction rows found in {input_jsonl}")

    dates = sorted(r["game_date"] for r in records)
    date_start, date_end = dates[0], dates[-1]

    if verbose:
        print(f"[phase59_pre] Loaded {n_total} valid rows, {date_start} → {date_end}")

    # ── OOF rolling monthly calibration ───────────────────────────────────────
    eval_records, train_months, eval_months = _rolling_monthly_oof(
        records, min_train_months=min_train_months
    )

    n_eval = len(eval_records)
    n_train = n_total - n_eval
    n_heavy_fav = sum(1 for r in eval_records if r["_fav_prob"] >= 0.70)

    if verbose:
        print(f"[phase59_pre] Train months: {train_months}")
        print(f"[phase59_pre] Eval months:  {eval_months}")
        print(f"[phase59_pre] n_eval={n_eval}, n_heavy_fav={n_heavy_fav}")

    # ── Compute variant results ────────────────────────────────────────────────
    baseline_result = _compute_variant_result("baseline", eval_records, "_blend_prob")
    isotonic_result = _compute_variant_result("isotonic", eval_records, "_iso_prob")
    platt_result = _compute_variant_result("platt", eval_records, "_platt_prob")

    bucket_table = _bucket_comparison(eval_records)

    # ── Negative control ───────────────────────────────────────────────────────
    neg_control = _run_negative_control(eval_records, records)

    # ── Gate ──────────────────────────────────────────────────────────────────
    gate, rationale, recommendation = _recommend_gate(
        baseline_result, isotonic_result, platt_result,
        n_eval=n_eval, n_heavy_fav=n_heavy_fav,
    )

    audit_hash = _compute_audit_hash(
        n_total, date_start, date_end, gate,
        baseline_result.heavy_fav_ece if not math.isnan(baseline_result.heavy_fav_ece) else -1.0,
    )

    result = Phase59PreResult(
        phase_version=PHASE_VERSION,
        run_timestamp=now,
        audit_hash=audit_hash,
        input_jsonl_path=str(input_jsonl),
        input_audit_hash=input_audit_hash,
        sample_size=n_total,
        date_range_start=date_start,
        date_range_end=date_end,
        validation_strategy="rolling_monthly_oof",
        train_months=train_months,
        eval_months=eval_months,
        n_train=n_train,
        n_eval=n_eval,
        baseline=baseline_result,
        isotonic=isotonic_result,
        platt=platt_result,
        bucket_metrics=bucket_table,
        negative_control=neg_control,
        gate=gate,
        gate_rationale=rationale,
        next_step_recommendation=recommendation,
    )

    # Final safety assertions
    assert result.candidate_patch_created is False, "HARD RULE: candidate_patch_created must be False"
    assert result.production_modified is False, "HARD RULE: production_modified must be False"
    assert result.alpha_modified is False, "HARD RULE: alpha_modified must be False"
    assert result.gate in _VALID_GATES, f"Invalid gate value: {result.gate}"

    return result
