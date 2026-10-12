"""
Phase 45: Model Value Attribution & Failure Diagnosis
======================================================
Identifies which specific conditions the α=0.4 market_blend model adds value
under, and diagnoses failure patterns compared to the raw market baseline.

Background (Phase 44 conclusions):
  - gate_state = PAPER_ONLY
  - bootstrap = NOT_SIGNIFICANT (CI crosses 0)
  - fold stability = STABLE (4/5 folds positive)
  - segment_value = CONDITIONAL_VALUE (month + odds_bucket)
  - NOT cleared for production

Goal: Find concrete conditions where model value is real, and explain why.

Hard Rules (never violate):
  - Do NOT modify production model.
  - Do NOT create CANDIDATE_PATCH.
  - Do NOT call external API / LLM.
  - Do NOT bypass BSS Safety Gate.
  - gate NEVER == "PATCH" (only valid values: COLLECT_MORE_DATA |
    FEATURE_REPAIR_INVESTIGATION | MARKET_BLEND_PAPER_ONLY)
  - candidate_patch_created ALWAYS = False
  - All metrics delegate to wbc_backend.evaluation.metrics (SSOT).
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from wbc_backend.evaluation.metrics import (
    brier_score,
    brier_skill_score,
    expected_calibration_error,
)
from wbc_backend.evaluation.prediction_persistence import PredictionRow

logger = logging.getLogger(__name__)

# ─── Hard Constants ───────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False   # NEVER change
ALPHA: float = 0.4                       # Fixed from Phase 42A/43/44
_MIN_SEGMENT_N: int = 30                 # Minimum observations for labelling
_FAILURE_BSS_THRESHOLD: float = -0.01   # BSS < -1% → failure segment
_ECE_DETERIORATION_MARGIN: float = 0.01 # blend_ece > market_ece + margin → ECE failure
_VALID_GATES: frozenset[str] = frozenset({
    "COLLECT_MORE_DATA",
    "FEATURE_REPAIR_INVESTIGATION",
    "MARKET_BLEND_PAPER_ONLY",
})

# ─── Segment Labels ───────────────────────────────────────────────────────────
VALUE_POSITIVE: str = "VALUE_POSITIVE"   # BSS >= +0.5% and n >= _MIN_SEGMENT_N
VALUE_NEGATIVE: str = "VALUE_NEGATIVE"  # BSS < -1% and n >= _MIN_SEGMENT_N
NO_SIGNAL: str = "NO_SIGNAL"            # Weak/uncertain or n < _MIN_SEGMENT_N

# ─── Global Conclusion Labels ─────────────────────────────────────────────────
# Returned in AttributionResult.global_conclusion
NO_VALUE: str = "NO_VALUE"
CONDITIONAL_VALUE: str = "CONDITIONAL_VALUE"
STRUCTURAL_BIAS: str = "STRUCTURAL_BIAS"
NOISY_SIGNAL: str = "NOISY_SIGNAL"


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  Data Structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SegmentResult:
    """
    Per-segment value attribution metrics.

    Covers one (dimension, bucket) pair, e.g. ("odds_bucket", "heavy_favorite").
    """
    segment_type: str            # "odds_bucket" | "disagreement" | "confidence" | "month"
    segment_label: str           # human-readable bucket name
    n: int                       # sample size
    model_brier: float
    market_brier: float
    bss: float                   # model BSS vs market (raw model, not blend)
    blend_bss: float             # blend BSS vs market (alpha=0.4)
    model_ece: float
    market_ece: float
    win_rate: float              # empirical home-win rate
    value_label: str             # VALUE_POSITIVE | VALUE_NEGATIVE | NO_SIGNAL


@dataclass
class FailureSegment:
    """A segment where the model clearly underperforms the market."""
    segment_type: str
    segment_label: str
    n: int
    bss: float
    blend_bss: float
    failure_reason: str          # human-readable heuristic explanation
    failure_type: str            # "BSS_NEGATIVE" | "ECE_DETERIORATION" | "BOTH"


@dataclass
class AttributionResult:
    """
    Full Phase 45 attribution snapshot.

    gate is always one of: COLLECT_MORE_DATA | FEATURE_REPAIR_INVESTIGATION |
    MARKET_BLEND_PAPER_ONLY. Never "PATCH".
    """
    run_id: str
    generated_at: str
    input_prediction_path: str
    sample_size: int
    date_start: str
    date_end: str
    alpha: float = ALPHA
    # Per-segment results across all four dimensions
    segment_results: list[SegmentResult] = field(default_factory=list)
    # Failure diagnosis
    failure_segments: list[FailureSegment] = field(default_factory=list)
    # Top performers
    top_positive_segments: list[SegmentResult] = field(default_factory=list)
    top_negative_segments: list[SegmentResult] = field(default_factory=list)
    # High-level conclusions
    global_conclusion: str = NO_VALUE
    global_conclusion_detail: str = ""
    gate: str = "MARKET_BLEND_PAPER_ONLY"
    gate_rationale: str = ""
    # Hard-rule flags
    candidate_patch_created: bool = False
    # Audit
    audit_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Ensure hard rules are preserved in serialised form
        d["candidate_patch_created"] = False
        assert d["gate"] in _VALID_GATES, f"INVARIANT VIOLATION: gate={d['gate']!r}"
        return d


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  Bucketing helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _odds_bucket(market_prob: float) -> str:
    """
    Classify a game by market-implied home-win probability.

    heavy_favorite : market_prob >= 0.65
    mid            : 0.45 <= market_prob < 0.65
    underdog       : market_prob < 0.45
    """
    if market_prob >= 0.65:
        return "heavy_favorite"
    if market_prob >= 0.45:
        return "mid"
    return "underdog"


def _disagreement_bucket(model_prob: float, market_prob: float) -> str:
    """
    Classify the magnitude of model–market disagreement.

    low    : |model - market| < 0.05
    medium : 0.05 <= |model - market| < 0.10
    high   : |model - market| >= 0.10
    """
    gap = abs(model_prob - market_prob)
    if gap < 0.05:
        return "low"
    if gap < 0.10:
        return "medium"
    return "high"


def _confidence_bucket(model_prob: float) -> str:
    """
    Classify model confidence as distance from 0.5.

    high_confidence : |model - 0.5| >= 0.10
    mid_confidence  : 0.05 <= |model - 0.5| < 0.10
    low_confidence  : |model - 0.5| < 0.05
    """
    dist = abs(model_prob - 0.5)
    if dist >= 0.10:
        return "high_confidence"
    if dist >= 0.05:
        return "mid_confidence"
    return "low_confidence"


def _month_bucket(game_date: str) -> str:
    """
    Extract YYYY-MM from game_date string.  Returns 'unknown' if parsing fails.
    """
    try:
        if not game_date or len(game_date) < 7:
            return "unknown"
        return game_date[:7]   # "YYYY-MM"
    except (IndexError, TypeError):
        return "unknown"


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  Segment metric computation
# ═══════════════════════════════════════════════════════════════════════════════

def _value_label(bss: float, blend_bss: float, n: int) -> str:
    """
    Assign a value label to a segment based on BSS thresholds.

    VALUE_POSITIVE : blend_bss >= 0.005 and n >= _MIN_SEGMENT_N
    VALUE_NEGATIVE : blend_bss <= _FAILURE_BSS_THRESHOLD and n >= _MIN_SEGMENT_N
    NO_SIGNAL      : otherwise (weak signal or too few samples)
    """
    if n < _MIN_SEGMENT_N:
        return NO_SIGNAL
    if blend_bss >= 0.005:
        return VALUE_POSITIVE
    if blend_bss <= _FAILURE_BSS_THRESHOLD:
        return VALUE_NEGATIVE
    return NO_SIGNAL


def _blend_probs(
    model_probs: list[float],
    market_probs: list[float],
    alpha: float = ALPHA,
) -> list[float]:
    return [alpha * m + (1.0 - alpha) * k for m, k in zip(model_probs, market_probs)]


def _compute_segment_result(
    rows: list[PredictionRow],
    seg_type: str,
    seg_label: str,
    alpha: float = ALPHA,
) -> SegmentResult:
    """Compute all metrics for a single segment slice."""
    model_p = [r.model_home_prob for r in rows]
    market_p = [r.market_home_prob_no_vig for r in rows]
    labels = [r.home_win for r in rows]
    blend_p = _blend_probs(model_p, market_p, alpha)

    model_b = brier_score(model_p, labels)
    market_b = brier_score(market_p, labels)
    blend_b = brier_score(blend_p, labels)

    model_bss_v = brier_skill_score(model_b, market_b) or 0.0
    blend_bss_v = brier_skill_score(blend_b, market_b) or 0.0

    # ECE only meaningful with enough samples
    if len(rows) >= _MIN_SEGMENT_N:
        model_ece_v = expected_calibration_error(model_p, labels)["ece"]
        market_ece_v = expected_calibration_error(market_p, labels)["ece"]
    else:
        model_ece_v = float("nan")
        market_ece_v = float("nan")

    win_rate_v = sum(labels) / len(labels) if labels else float("nan")

    return SegmentResult(
        segment_type=seg_type,
        segment_label=seg_label,
        n=len(rows),
        model_brier=round(model_b, 6),
        market_brier=round(market_b, 6),
        bss=round(model_bss_v, 6),
        blend_bss=round(blend_bss_v, 6),
        model_ece=round(model_ece_v, 6) if not _is_nan(model_ece_v) else float("nan"),
        market_ece=round(market_ece_v, 6) if not _is_nan(market_ece_v) else float("nan"),
        win_rate=round(win_rate_v, 4) if not _is_nan(win_rate_v) else float("nan"),
        value_label=_value_label(model_bss_v, blend_bss_v, len(rows)),
    )


def _is_nan(v: float) -> bool:
    import math
    return math.isnan(v)


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  Segment grouping across all four dimensions
# ═══════════════════════════════════════════════════════════════════════════════

def _group_by(
    rows: list[PredictionRow],
    key_fn: Any,
) -> dict[str, list[PredictionRow]]:
    """Group rows by the string key returned by key_fn(row)."""
    groups: dict[str, list[PredictionRow]] = {}
    for row in rows:
        k = key_fn(row)
        groups.setdefault(k, []).append(row)
    return groups


def compute_all_segments(
    rows: list[PredictionRow],
    alpha: float = ALPHA,
) -> list[SegmentResult]:
    """
    Compute segment metrics across all four analysis dimensions.

    Returns a flat list of SegmentResult objects, one per (dim, bucket) pair.
    Buckets with zero rows are omitted.
    """
    results: list[SegmentResult] = []

    # (1) odds_bucket — based on market_home_prob_no_vig
    groups = _group_by(rows, lambda r: _odds_bucket(r.market_home_prob_no_vig))
    for label, grp in sorted(groups.items()):
        results.append(_compute_segment_result(grp, "odds_bucket", label, alpha))

    # (2) disagreement — |model - market|
    groups = _group_by(
        rows,
        lambda r: _disagreement_bucket(r.model_home_prob, r.market_home_prob_no_vig),
    )
    for label, grp in sorted(groups.items()):
        results.append(_compute_segment_result(grp, "disagreement", label, alpha))

    # (3) confidence — |model - 0.5|
    groups = _group_by(rows, lambda r: _confidence_bucket(r.model_home_prob))
    for label, grp in sorted(groups.items()):
        results.append(_compute_segment_result(grp, "confidence", label, alpha))

    # (4) month — YYYY-MM from game_date
    groups = _group_by(rows, lambda r: _month_bucket(r.game_date))
    for label, grp in sorted(groups.items()):
        results.append(_compute_segment_result(grp, "month", label, alpha))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# § 5  Failure pattern detection
# ═══════════════════════════════════════════════════════════════════════════════

def _failure_reason(seg: SegmentResult) -> str:
    """
    Heuristic explanation for why a segment is failing.
    Based only on observable patterns — no guessing.
    """
    parts: list[str] = []
    if seg.blend_bss < _FAILURE_BSS_THRESHOLD:
        parts.append(
            f"blend_bss={seg.blend_bss:+.4f} is below -1% threshold "
            f"(model adds negative value in this bucket)"
        )
    if (
        not _is_nan(seg.model_ece)
        and not _is_nan(seg.market_ece)
        and seg.model_ece > seg.market_ece + _ECE_DETERIORATION_MARGIN
    ):
        parts.append(
            f"model_ece={seg.model_ece:.4f} exceeds market_ece={seg.market_ece:.4f} "
            f"by >{_ECE_DETERIORATION_MARGIN:.2f} (calibration worse than market)"
        )
    return "; ".join(parts) if parts else "segment underperforms market consistently"


def _failure_type(seg: SegmentResult) -> str:
    bss_fail = seg.blend_bss < _FAILURE_BSS_THRESHOLD
    ece_fail = (
        not _is_nan(seg.model_ece)
        and not _is_nan(seg.market_ece)
        and seg.model_ece > seg.market_ece + _ECE_DETERIORATION_MARGIN
    )
    if bss_fail and ece_fail:
        return "BOTH"
    if ece_fail:
        return "ECE_DETERIORATION"
    return "BSS_NEGATIVE"


def detect_failure_segments(
    segment_results: list[SegmentResult],
) -> list[FailureSegment]:
    """
    Find segments where model clearly underperforms market.

    Criteria:
      - BSS < -1% threshold, or
      - ECE clearly deteriorated (model_ece > market_ece + 0.01)
    Both require n >= _MIN_SEGMENT_N to avoid noise.
    """
    failures: list[FailureSegment] = []
    for seg in segment_results:
        if seg.n < _MIN_SEGMENT_N:
            continue
        bss_fail = seg.blend_bss < _FAILURE_BSS_THRESHOLD
        ece_fail = (
            not _is_nan(seg.model_ece)
            and not _is_nan(seg.market_ece)
            and seg.model_ece > seg.market_ece + _ECE_DETERIORATION_MARGIN
        )
        if bss_fail or ece_fail:
            failures.append(FailureSegment(
                segment_type=seg.segment_type,
                segment_label=seg.segment_label,
                n=seg.n,
                bss=seg.bss,
                blend_bss=seg.blend_bss,
                failure_reason=_failure_reason(seg),
                failure_type=_failure_type(seg),
            ))
    return failures


# ═══════════════════════════════════════════════════════════════════════════════
# § 6  Value attribution summary
# ═══════════════════════════════════════════════════════════════════════════════

def _top_k_segments(
    segments: list[SegmentResult],
    k: int = 3,
    *,
    highest: bool = True,
) -> list[SegmentResult]:
    """Return top-k segments by blend_bss (only n >= _MIN_SEGMENT_N)."""
    eligible = [s for s in segments if s.n >= _MIN_SEGMENT_N]
    eligible.sort(key=lambda s: s.blend_bss, reverse=highest)
    return eligible[:k]


def _global_conclusion(
    segments: list[SegmentResult],
    failure_segments: list[FailureSegment],
) -> tuple[str, str]:
    """
    Derive global conclusion label and detail string.

    Returns (conclusion_label, detail_string).

    Labels:
      STRUCTURAL_BIAS      : majority of segments show ECE deterioration
      NO_VALUE             : model BSS <= 0 across all eligible segments
      CONDITIONAL_VALUE    : some segments positive, some negative/no-signal
      NOISY_SIGNAL         : mixed without enough positive evidence
    """
    eligible = [s for s in segments if s.n >= _MIN_SEGMENT_N]
    if not eligible:
        return NO_VALUE, "Insufficient sample size in all segments."

    # Count ECE failures
    ece_fails = sum(
        1 for s in eligible
        if not _is_nan(s.model_ece)
        and not _is_nan(s.market_ece)
        and s.model_ece > s.market_ece + _ECE_DETERIORATION_MARGIN
    )
    if ece_fails >= len(eligible) * 0.5:
        detail = (
            f"{ece_fails}/{len(eligible)} eligible segments show ECE deterioration "
            f"> {_ECE_DETERIORATION_MARGIN:.2f}. Model calibration structurally worse than market."
        )
        return STRUCTURAL_BIAS, detail

    n_positive = sum(1 for s in eligible if s.value_label == VALUE_POSITIVE)
    n_negative = sum(1 for s in eligible if s.value_label == VALUE_NEGATIVE)

    if n_positive == 0 and n_negative == 0:
        # All NO_SIGNAL
        avg_bss = sum(s.blend_bss for s in eligible) / len(eligible)
        if avg_bss <= 0:
            return NO_VALUE, (
                f"All {len(eligible)} eligible segments are NO_SIGNAL; "
                f"average blend_bss={avg_bss:+.4f} <= 0. No model value detected."
            )
        return NOISY_SIGNAL, (
            f"All {len(eligible)} eligible segments are NO_SIGNAL; "
            f"average blend_bss={avg_bss:+.4f} > 0 but below VALUE_POSITIVE threshold. "
            "Signal too weak to act on."
        )

    if n_positive > 0 and n_negative == 0:
        pos_labels = [s.segment_label for s in eligible if s.value_label == VALUE_POSITIVE]
        return CONDITIONAL_VALUE, (
            f"{n_positive} segments show VALUE_POSITIVE: {pos_labels}. "
            "No clearly negative segments. Conditional value present."
        )

    if n_positive > 0 and n_negative > 0:
        pos_labels = [s.segment_label for s in eligible if s.value_label == VALUE_POSITIVE]
        neg_labels = [s.segment_label for s in eligible if s.value_label == VALUE_NEGATIVE]
        return CONDITIONAL_VALUE, (
            f"{n_positive} positive segments ({pos_labels}); "
            f"{n_negative} negative segments ({neg_labels}). "
            "Model value is conditional on bucket."
        )

    # Only negative, no positive
    return NO_VALUE, (
        f"0 VALUE_POSITIVE, {n_negative} VALUE_NEGATIVE segments. "
        "Model consistently underperforms market."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 7  Gate recommendation
# ═══════════════════════════════════════════════════════════════════════════════

def _gate_recommendation(
    global_conclusion: str,
    top_positive: list[SegmentResult],
    failure_segments: list[FailureSegment],
    sample_size: int,
) -> tuple[str, str]:
    """
    Determine gate recommendation (never "PATCH").

    Returns (gate_label, gate_rationale).

    Rules:
      FEATURE_REPAIR_INVESTIGATION : value concentrated in ≤2 specific buckets
                                     AND ≥1 failure segment detected
      COLLECT_MORE_DATA            : weak but positive direction overall,
                                     or sample too small for conclusion
      MARKET_BLEND_PAPER_ONLY      : fallback — no stable positive pattern
    """
    n_top_positive = len(top_positive)
    n_failures = len(failure_segments)

    # Concentrated value with failure patterns → investigate features
    if n_top_positive >= 1 and n_failures >= 1 and global_conclusion == CONDITIONAL_VALUE:
        positive_labels = [f"{s.segment_type}:{s.segment_label}" for s in top_positive]
        failure_labels = [f"{f.segment_type}:{f.segment_label}" for f in failure_segments]
        gate = "FEATURE_REPAIR_INVESTIGATION"
        rationale = (
            f"Value concentrated in {positive_labels}; "
            f"clear failures in {failure_labels}. "
            "Investigate feature quality in failure segments before re-evaluating blend."
        )
        return gate, rationale

    # Weak but directionally positive with small sample
    if global_conclusion in (CONDITIONAL_VALUE, NOISY_SIGNAL) and sample_size < 3_000:
        gate = "COLLECT_MORE_DATA"
        rationale = (
            f"sample_size={sample_size} < 3000; signal direction is "
            f"{global_conclusion}. Accumulate more data before gate re-evaluation."
        )
        return gate, rationale

    # Default: stay in paper-only tracking
    gate = "MARKET_BLEND_PAPER_ONLY"
    rationale = (
        f"global_conclusion={global_conclusion}; no evidence sufficient to "
        "change gate from PAPER_ONLY. Continue paper tracking per Phase 44."
    )
    return gate, rationale


# ═══════════════════════════════════════════════════════════════════════════════
# § 8  Audit hash
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_audit_hash(result: AttributionResult) -> str:
    """
    Stable sha256 over key result fields (exclude audit_hash itself).
    """
    payload = json.dumps({
        "run_id": result.run_id,
        "sample_size": result.sample_size,
        "date_start": result.date_start,
        "date_end": result.date_end,
        "alpha": result.alpha,
        "global_conclusion": result.global_conclusion,
        "gate": result.gate,
        "candidate_patch_created": result.candidate_patch_created,
        "n_segments": len(result.segment_results),
        "n_failures": len(result.failure_segments),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
# § 9  Main entrypoint
# ═══════════════════════════════════════════════════════════════════════════════

def run_phase45_attribution(
    rows: list[PredictionRow],
    input_path: str = "",
    alpha: float = ALPHA,
) -> AttributionResult:
    """
    Full Phase 45 model value attribution pipeline.

    Parameters
    ----------
    rows :
        Validated PredictionRow list (from persisted JSONL).
    input_path :
        Source path string for provenance.
    alpha :
        Blend alpha — must be 0.4.  Any other value raises ValueError.

    Returns
    -------
    AttributionResult with all segments, failures, top lists, and gate.
    """
    if len(rows) == 0:
        raise ValueError("rows must be non-empty")
    if abs(alpha - ALPHA) > 1e-9:
        raise ValueError(f"alpha must be {ALPHA} (got {alpha}); Phase 45 is paper-only.")

    rows_sorted = sorted(rows, key=lambda r: (r.game_date, r.prediction_time_utc or ""))
    date_start = rows_sorted[0].game_date
    date_end = rows_sorted[-1].game_date

    # Compute segment metrics
    segment_results = compute_all_segments(rows_sorted, alpha=alpha)

    # Detect failures
    failure_segments = detect_failure_segments(segment_results)

    # Top 3 positive / negative
    top_positive = _top_k_segments(segment_results, k=3, highest=True)
    top_negative = _top_k_segments(segment_results, k=3, highest=False)

    # Global conclusion
    conclusion, conclusion_detail = _global_conclusion(segment_results, failure_segments)

    # Gate recommendation
    gate, gate_rationale = _gate_recommendation(
        conclusion, top_positive, failure_segments, len(rows)
    )

    # Gate safety guard
    assert gate in _VALID_GATES, f"INVARIANT VIOLATION: gate={gate!r} not in valid set"

    result = AttributionResult(
        run_id=str(uuid.uuid4()),
        generated_at=datetime.now(timezone.utc).isoformat(),
        input_prediction_path=input_path,
        sample_size=len(rows),
        date_start=date_start,
        date_end=date_end,
        alpha=alpha,
        segment_results=segment_results,
        failure_segments=failure_segments,
        top_positive_segments=top_positive,
        top_negative_segments=top_negative,
        global_conclusion=conclusion,
        global_conclusion_detail=conclusion_detail,
        gate=gate,
        gate_rationale=gate_rationale,
        candidate_patch_created=False,
        audit_hash="",
    )
    result.audit_hash = _compute_audit_hash(result)
    return result
