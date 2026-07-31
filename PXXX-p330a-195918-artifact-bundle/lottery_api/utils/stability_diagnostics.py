"""P253B — Signal Stability Diagnostics SSOT.

Pure-Python module for signal stability diagnostics used in lottery prediction
research. Consolidates M7 gap from P252B. Standardises block/year/era/robustness
vocabulary, thresholds, and output previously scattered across P211R, P224,
P230, P231, and research scripts.

Design constraints:
- No DB connection
- No strategy registry dependency
- No production recommendation dependency
- No numpy / scipy — pure stdlib only (math, statistics, typing)
- Deterministic output for identical inputs
- No claim of predictive edge
- No betting advice

Vocabulary alignment (P252B M7 gap):
    block  = era  = year   — all refer to a non-overlapping time partition
    robustness             — subset-exclusion check: remove one block, recompute
    rolling_window         — sliding window from rolling_window.py (P252F)

Note on drift_detector.py (production):
    DriftDetector uses STABLE/WARNING/CRITICAL for PSI-based drift detection.
    This module uses STABLE/MIXED/UNSTABLE to avoid confusion with production
    labels — these are research-layer stability assessments, not production alerts.

Usage::

    from lottery_api.utils.stability_diagnostics import (
        STABILITY_DIMENSIONS,
        STABILITY_STATUS,
        DEFAULT_STABILITY_THRESHOLDS,
        classify_stability,
        block_stability,
        subset_exclusion_stability,
        stability_summary,
    )

    # Classify a list of per-block hit rates
    status, score = classify_stability([0.18, 0.19, 0.17, 0.20], higher_is_better=True)

    # Full block stability report
    report = block_stability(
        block_results=[{"hits": 5, "n": 30}, {"hits": 6, "n": 30}, {"hits": 4, "n": 30}],
        metric_key="hit_rate",
        family_label="DAILY_539_midfreq_3blocks",
    )
    assert report["no_edge_claim"] is True
"""
from __future__ import annotations

import math
import statistics
from typing import Optional, Sequence

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

MODULE_VERSION = "1.0"
SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Vocabulary constants
# ---------------------------------------------------------------------------

# Canonical stability dimension labels (P252B M7 gap: block=era=year synonyms)
STABILITY_DIMENSIONS = {
    "block":           "Non-overlapping temporal partition (synonym: era, year)",
    "era":             "Non-overlapping temporal partition (synonym: block, year)",
    "year":            "Non-overlapping temporal partition (synonym: block, era)",
    "subset_exclusion": (
        "Robustness check: remove one block and recompute; "
        "measures sensitivity to individual sub-populations"
    ),
    "rolling_window":  (
        "Sliding window (use with rolling_window.py P252F); "
        "overlapping windows — distinct from non-overlapping blocks"
    ),
}

# Research-layer stability status labels (NOT to be confused with DriftDetector production labels)
STABILITY_STATUS = {
    "STABLE":       "Values across blocks are consistent within threshold",
    "MIXED":        "Values vary moderately — some blocks deviate beyond threshold",
    "UNSTABLE":     "Values vary substantially — stability not demonstrated",
    "UNDERPOWERED": "Too few blocks or too few samples per block for reliable assessment",
    "UNKNOWN":      "Cannot determine stability — missing or invalid inputs",
}

# Default thresholds for classify_stability
# Stability score = 1 - (value_range / (|value_mean| + ε))
# STABLE if score >= 0.7, MIXED if >= 0.4, UNSTABLE if < 0.4
DEFAULT_STABILITY_THRESHOLDS = {
    "stable_min_score": 0.70,   # score >= 0.70 → STABLE
    "mixed_min_score":  0.40,   # 0.40 <= score < 0.70 → MIXED
    # score < 0.40 → UNSTABLE
    "min_windows":      2,      # need at least 2 blocks/windows for assessment
    "min_count_per_block": 10,  # warn if fewer than 10 samples per block
}

EPSILON = 1e-9  # division guard


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_stability_inputs(
    window_results: Sequence,
    min_windows: int = 2,
    min_count: int = 1,
) -> dict:
    """Validate inputs for stability assessment.

    Args:
        window_results: Sequence of numeric values or dicts with a metric field.
        min_windows: Minimum number of windows/blocks required.
        min_count: Minimum count per window (when window_results are dicts with 'n').

    Returns:
        dict with keys: valid (bool), errors (list), warnings (list),
        n_windows (int), underpowered (bool).
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not hasattr(window_results, "__iter__") or isinstance(window_results, (str, bytes)):
        errors.append(f"window_results must be a sequence, got {type(window_results).__name__!r}")
        return {"valid": False, "errors": errors, "warnings": warnings,
                "n_windows": 0, "underpowered": True}

    lst = list(window_results)
    n = len(lst)

    if n == 0:
        errors.append("window_results must not be empty")
        return {"valid": False, "errors": errors, "warnings": warnings,
                "n_windows": 0, "underpowered": True}

    if not isinstance(min_windows, int) or min_windows < 1:
        errors.append(f"min_windows must be a positive integer, got {min_windows!r}")
    if not isinstance(min_count, int) or min_count < 1:
        errors.append(f"min_count must be a positive integer, got {min_count!r}")

    underpowered = n < min_windows
    if underpowered:
        warnings.append(
            f"Only {n} window(s) — fewer than min_windows={min_windows}. "
            "Result is UNDERPOWERED."
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "n_windows": n,
        "underpowered": underpowered,
    }


# ---------------------------------------------------------------------------
# Core classification
# ---------------------------------------------------------------------------


def classify_stability(
    values: Sequence[float],
    threshold: Optional[float] = None,
    higher_is_better: bool = True,
    min_windows: int = 2,
) -> tuple[str, float]:
    """Classify stability of a sequence of numeric metric values.

    Stability score = 1 - (value_range / (|value_mean| + ε))

    Args:
        values: Sequence of per-block/window metric values (e.g., hit rates).
        threshold: Override the stable_min_score threshold. If None, uses
                   DEFAULT_STABILITY_THRESHOLDS["stable_min_score"].
        higher_is_better: True if higher metric values are preferred
                          (currently informational only — does not change score).
        min_windows: Minimum blocks needed for a reliable assessment.

    Returns:
        tuple: (status_str, stability_score_float)
               status_str is one of STABILITY_STATUS keys.
               stability_score is in [0, 1] where 1.0 = perfectly stable.

    Raises:
        ValueError: If values are invalid or non-numeric.
    """
    lst = [float(v) for v in values]
    n = len(lst)

    if n == 0:
        raise ValueError("values must not be empty")
    for i, v in enumerate(lst):
        if math.isnan(v) or math.isinf(v):
            raise ValueError(f"values[{i}] is non-finite: {v!r}")

    if n < min_windows:
        return (STABILITY_STATUS.keys().__class__.__new__(str) if False else "UNDERPOWERED",
                0.0)

    val_min  = min(lst)
    val_max  = max(lst)
    val_mean = sum(lst) / n
    val_range = val_max - val_min

    score = 1.0 - val_range / (abs(val_mean) + EPSILON)
    score = max(0.0, min(1.0, score))

    stable_threshold = threshold if threshold is not None else DEFAULT_STABILITY_THRESHOLDS["stable_min_score"]
    mixed_threshold  = DEFAULT_STABILITY_THRESHOLDS["mixed_min_score"]

    if score >= stable_threshold:
        status = "STABLE"
    elif score >= mixed_threshold:
        status = "MIXED"
    else:
        status = "UNSTABLE"

    return status, round(score, 6)


# ---------------------------------------------------------------------------
# Block (era / year) stability
# ---------------------------------------------------------------------------


def block_stability(
    block_results: Sequence[dict],
    metric_key: str,
    threshold: Optional[float] = None,
    family_label: Optional[str] = None,
    min_windows: int = 2,
    min_count_key: str = "n",
) -> dict:
    """Assess stability across non-overlapping blocks (era / year / block synonyms).

    Args:
        block_results: Sequence of dicts, each representing one block.
                       Must contain metric_key. May contain min_count_key ('n').
        metric_key: Dict key for the numeric metric (e.g. "hit_rate", "edge").
        threshold: Override stable score threshold.
        family_label: Optional audit label.
        min_windows: Minimum blocks required.
        min_count_key: Key for per-block sample count (default "n").

    Returns:
        dict: Structured stability result with schema_version and no_edge_claim=True.

    Raises:
        ValueError: If block_results is empty, metric_key missing, or values invalid.
    """
    lst = list(block_results)
    if not lst:
        raise ValueError("block_results must not be empty")
    for i, b in enumerate(lst):
        if metric_key not in b:
            raise ValueError(f"block_results[{i}] missing key {metric_key!r}")

    values = [float(b[metric_key]) for b in lst]
    counts = [b.get(min_count_key) for b in lst]

    validation = validate_stability_inputs(values, min_windows=min_windows)
    underpowered = validation["underpowered"]

    if underpowered:
        status, score = "UNDERPOWERED", 0.0
    else:
        status, score = classify_stability(values, threshold=threshold, min_windows=min_windows)

    n = len(values)
    val_mean = sum(values) / n if n > 0 else 0.0
    val_min  = min(values) if n > 0 else 0.0
    val_max  = max(values) if n > 0 else 0.0
    val_range = val_max - val_min
    val_std  = statistics.pstdev(values) if n > 1 else 0.0

    return {
        "schema_version": SCHEMA_VERSION,
        "diagnostic_type": "signal_stability_diagnostics",
        "dimension": "block",
        "dimension_note": "block = era = year (synonyms per P252B M7 vocabulary)",
        "family_label": family_label or "UNLABELED",
        "metric_key": metric_key,
        "status": status,
        "threshold": threshold if threshold is not None else DEFAULT_STABILITY_THRESHOLDS["stable_min_score"],
        "min_windows": min_windows,
        "window_count": n,
        "underpowered": underpowered,
        "values": values,
        "value_min": val_min,
        "value_max": val_max,
        "value_range": round(val_range, 8),
        "value_mean": round(val_mean, 8),
        "value_std": round(val_std, 8),
        "stability_score": score,
        "block_counts": [c for c in counts if c is not None],
        "validation_warnings": validation["warnings"],
        "no_edge_claim": True,
        "no_betting_advice": True,
        "assumptions": [
            "Blocks are non-overlapping temporal partitions (block = era = year)",
            "Values are assumed to be drawn from the same distribution if signal is stable",
            "UNDERPOWERED does not mean unstable — only that sample is insufficient",
        ],
        "limitations": [
            "Stability score is heuristic; a significant p-value from permutation test "
            "provides stronger evidence (use permutation_test.py for that)",
            "A stable signal does not imply a deployable prediction edge",
            "GREEN randomness does not imply any exploitable signal",
        ],
    }


# ---------------------------------------------------------------------------
# Subset exclusion (robustness check)
# ---------------------------------------------------------------------------


def subset_exclusion_stability(
    full_result: float,
    subset_results: Sequence[float],
    metric_key: str = "metric",
    tolerance: Optional[float] = None,
    family_label: Optional[str] = None,
) -> dict:
    """Robustness check: assess sensitivity to subset exclusion.

    Computes whether excluding individual blocks one at a time changes
    the aggregate result materially ('leave-one-out' robustness).

    Args:
        full_result: Full-dataset metric value.
        subset_results: Sequence of leave-one-out metric values (one per block).
        metric_key: Label for the metric (audit trail only).
        tolerance: Absolute tolerance within which subset ≈ full is "robust".
                   Default: 5% of |full_result| or 0.005, whichever is larger.
        family_label: Optional label.

    Returns:
        dict: Robustness summary with no_edge_claim=True.
    """
    subset_list = [float(v) for v in subset_results]
    if not subset_list:
        raise ValueError("subset_results must not be empty")

    full = float(full_result)
    eff_tol = tolerance if tolerance is not None else max(0.005, abs(full) * 0.05)

    deviations = [abs(s - full) for s in subset_list]
    n_robust   = sum(1 for d in deviations if d <= eff_tol)
    n_total    = len(subset_list)
    robust_fraction = n_robust / n_total

    if robust_fraction >= 0.8:
        status = "STABLE"
    elif robust_fraction >= 0.5:
        status = "MIXED"
    else:
        status = "UNSTABLE"

    if n_total < 2:
        status = "UNDERPOWERED"

    return {
        "schema_version": SCHEMA_VERSION,
        "diagnostic_type": "signal_stability_diagnostics",
        "dimension": "subset_exclusion",
        "dimension_note": "robustness = subset-exclusion stability (leave-one-out)",
        "family_label": family_label or "UNLABELED",
        "metric_key": metric_key,
        "full_result": full,
        "tolerance": round(eff_tol, 8),
        "subset_count": n_total,
        "n_robust": n_robust,
        "n_non_robust": n_total - n_robust,
        "robust_fraction": round(robust_fraction, 6),
        "subset_results": subset_list,
        "deviations": [round(d, 8) for d in deviations],
        "max_deviation": round(max(deviations), 8),
        "status": status,
        "underpowered": n_total < 2,
        "no_edge_claim": True,
        "no_betting_advice": True,
        "assumptions": [
            "Each subset_result is computed by excluding one block from the full dataset",
            "Tolerance is relative to the full_result magnitude (default: max(0.5%, 5% of |full|))",
        ],
        "limitations": [
            "Robustness to subset exclusion does not imply a deployable prediction edge",
            "A subset-stable signal may still fail out-of-sample validation",
        ],
    }


# ---------------------------------------------------------------------------
# Unified stability summary (canonical SSOT output)
# ---------------------------------------------------------------------------


def stability_summary(
    results: Sequence,
    dimension: str,
    metric_key: str,
    family_label: Optional[str] = None,
    threshold: Optional[float] = None,
    min_windows: int = 2,
    value_getter: Optional[object] = None,
) -> dict:
    """Canonical SSOT stability summary output.

    Accepts either a list of numeric values or a list of dicts with metric_key.
    Always includes no_edge_claim=True.

    Args:
        results: Sequence of numeric values OR dicts containing metric_key.
        dimension: One of STABILITY_DIMENSIONS keys or any string label.
        metric_key: Name of the metric (audit trail and dict extraction).
        family_label: Optional audit label.
        threshold: Override stable score threshold.
        min_windows: Minimum blocks/windows required.
        value_getter: Optional callable(item) -> float for custom extraction.

    Returns:
        dict: Canonical stability summary.

    Raises:
        ValueError: If results are invalid or metric_key missing.
    """
    lst = list(results)
    if not lst:
        raise ValueError("results must not be empty")

    if value_getter is not None:
        values = [float(value_getter(r)) for r in lst]
    elif isinstance(lst[0], dict):
        if metric_key not in lst[0]:
            raise ValueError(f"results[0] missing key {metric_key!r}")
        values = [float(r[metric_key]) for r in lst]
    else:
        values = [float(r) for r in lst]

    validation = validate_stability_inputs(values, min_windows=min_windows)
    underpowered = validation["underpowered"]

    if underpowered:
        status, score = "UNDERPOWERED", 0.0
    else:
        status, score = classify_stability(values, threshold=threshold,
                                           min_windows=min_windows)

    n = len(values)
    val_mean  = sum(values) / n if n > 0 else 0.0
    val_min   = min(values) if n > 0 else 0.0
    val_max   = max(values) if n > 0 else 0.0
    val_range = val_max - val_min

    return {
        "schema_version": SCHEMA_VERSION,
        "diagnostic_type": "signal_stability_diagnostics",
        "family_label": family_label or "UNLABELED",
        "dimension": dimension,
        "metric_key": metric_key,
        "status": status,
        "threshold": threshold if threshold is not None else DEFAULT_STABILITY_THRESHOLDS["stable_min_score"],
        "min_windows": min_windows,
        "window_count": n,
        "underpowered": underpowered,
        "values": values,
        "value_min": round(val_min, 8),
        "value_max": round(val_max, 8),
        "value_range": round(val_range, 8),
        "value_mean": round(val_mean, 8),
        "stability_score": score,
        "no_edge_claim": True,
        "no_betting_advice": True,
        "assumptions": [
            "Results are ordered chronologically (oldest first)",
            "Each result represents one non-overlapping partition or window",
            "block = era = year (synonyms per P252B M7 vocabulary)",
            "UNDERPOWERED status does not mean unstable",
        ],
        "limitations": [
            "Stability score is heuristic; permutation test (permutation_test.py) "
            "provides stronger statistical evidence",
            "A stable signal does not imply a deployable prediction edge",
            "GREEN randomness does not imply any exploitable signal",
        ],
    }
