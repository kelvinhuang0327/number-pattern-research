"""Metrics SSOT — Single Source of Truth for Phase67–72+ Audit Reports.

Provides a unified, PIT-safe set of calculation functions, dataclasses, and
schema validators for use by future phases.  Existing Phase67–72 modules are
NOT modified; they keep their private implementations.  This module is the
canonical reference that new phases should import.

Safety constants (all read-only / diagnostic only):
  PRODUCTION_MODIFIED        = False
  CANDIDATE_PATCH_CREATED    = False
  ALPHA_MODIFIED             = False
  NO_EDGE_CLAIM              = True
  NO_PROFIT_CLAIM            = True

Design principles:
  1. Math matches Phase70/71 (most mature implementations).
  2. Dataclass schemas are the canonical "best" across Phase67–72.
  3. All public functions are pure / stateless — no I/O, no model import.
  4. No betting edge, no EV / Kelly / ROI calculation.
  5. Inventory-compatible: each dataclass can be serialised to dict via
     `ssot_to_dict()`.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

# ─── Safety constants ────────────────────────────────────────────────────────

PRODUCTION_MODIFIED: bool = False
CANDIDATE_PATCH_CREATED: bool = False
ALPHA_MODIFIED: bool = False
PREDICTION_JSONL_OVERWRITTEN: bool = False
NO_EDGE_CLAIM: bool = True
NO_PROFIT_CLAIM: bool = True
DIAGNOSTIC_ONLY: bool = True

MODULE_VERSION: str = "metrics_ssot_v1"
COMPLETION_MARKER: str = "METRICS_SSOT_PHASE67_72_INVENTORY_VERIFIED"

# ─── Valid gate constants ─────────────────────────────────────────────────────

METRICS_SSOT_FOUNDATION_READY: str = "METRICS_SSOT_FOUNDATION_READY"
METRICS_SSOT_INVENTORY_READY: str = "METRICS_SSOT_INVENTORY_READY"
METRICS_SSOT_NEEDS_PHASE_REFACTOR: str = "METRICS_SSOT_NEEDS_PHASE_REFACTOR"
METRICS_SSOT_DATA_LIMITED: str = "METRICS_SSOT_DATA_LIMITED"
METRICS_SSOT_SCHEMA_CONFLICT: str = "METRICS_SSOT_SCHEMA_CONFLICT"
METRICS_SSOT_REGRESSION_RISK: str = "METRICS_SSOT_REGRESSION_RISK"
METRICS_SSOT_NOT_READY: str = "METRICS_SSOT_NOT_READY"

VALID_GATES: frozenset[str] = frozenset({
    METRICS_SSOT_FOUNDATION_READY,
    METRICS_SSOT_INVENTORY_READY,
    METRICS_SSOT_NEEDS_PHASE_REFACTOR,
    METRICS_SSOT_DATA_LIMITED,
    METRICS_SSOT_SCHEMA_CONFLICT,
    METRICS_SSOT_REGRESSION_RISK,
    METRICS_SSOT_NOT_READY,
})

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION A — Canonical Dataclasses
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class BrierResult:
    """Result of a Brier score calculation."""
    n: int
    brier: float
    baseline_brier: float            # e.g. climatology (mean(y))
    bss_vs_baseline: float           # 1 - brier / baseline_brier


@dataclass
class ECEBucket:
    """Per-bucket ECE decomposition."""
    bin_index: int
    bin_lo: float                    # lower edge of probability bin
    bin_hi: float                    # upper edge of probability bin
    n: int
    mean_predicted: float
    mean_observed: float
    abs_calibration_error: float     # |mean_predicted - mean_observed|
    weight: float                    # n / total_n


@dataclass
class ECEResult:
    """Result of ECE calculation with bucket decomposition."""
    n: int
    ece: float
    n_bins: int
    buckets: list[ECEBucket]


@dataclass
class ResidualSummary:
    """Residual statistics for a prediction source."""
    n: int
    residual_mean: float             # pred - actual  (pos = overconfident)
    residual_std: float
    residual_min: float
    residual_max: float
    overconfident_bands: int         # bins where residual > overconf_threshold
    underconfident_bands: int        # bins where residual < -underconf_threshold


@dataclass
class SegmentMetricsSSO:
    """Canonical segment metrics schema (SSOT version).

    Supersedes all Phase67–71 local SegmentMetrics dataclasses for new phases.
    Field names follow Phase71 convention (most complete).
    """
    segment_name: str
    segment_definition: str
    n: int
    # Model metrics
    model_brier: float
    model_ece: float
    model_residual_mean: float
    model_residual_std: float
    model_mean_prob: float
    # Market metrics
    market_brier: float
    market_ece: float
    market_residual_mean: float
    market_mean_prob: float
    # Delta
    brier_delta: float               # model_brier - market_brier (pos = model worse)
    bss_vs_market: float             # 1 - model_brier / market_brier
    model_minus_market_mean: float
    # Targets
    observed_win_rate: float
    # Flags
    market_superiority: bool
    data_limited: bool
    notes: str = ""


@dataclass
class BootstrapCISSO:
    """Canonical bootstrap CI schema (SSOT version).

    Compatible with Phase70/71 BootstrapCI; adds optional `method` field
    for Phase69 compatibility without breaking Phase70/71 tests.
    """
    metric: str
    segment: str
    n: int
    n_boot: int
    seed: int
    observed: float
    ci_lower: float
    ci_upper: float
    ci_excludes_zero: bool
    ci_stable: bool
    ci_width: float
    data_limited: bool
    method: str = ""                 # Phase69 compatibility (optional)


@dataclass
class NegativeControlSSO:
    """Canonical negative control schema (SSOT version).

    Supersedes Phase67–71 local NegativeControl / NegativeControlResult.
    Follows Phase70/71 structure (most complete).
    """
    control_name: str
    control_type: str                # "shuffle_labels" | "shuffle_segment" | "random_split" etc.
    description: str
    n_permutations: int
    seed: int
    observed_gap: float              # real signal gap
    permuted_gap_mean: float
    permuted_gap_std: float
    signal_gap: float                # observed_gap - permuted_gap_mean
    overfit_risk: bool
    interpretation: str


@dataclass
class GateSummarySSO:
    """Canonical gate summary schema (SSOT version)."""
    phase_id: str
    gate: str
    gate_candidates: list[str]
    gate_rationale: str
    worth_next_phase: bool
    next_phase_recommendation: str
    # Safety flags
    candidate_patch_created: bool
    production_modified: bool
    alpha_modified: bool
    no_edge_claim: bool
    # Report metadata
    report_paths: list[str]
    completion_marker: str


@dataclass
class MetricsPayload:
    """Container for a full metrics payload to be validated."""
    phase_id: str
    n_samples: int
    brier: float | None = None
    ece: float | None = None
    residual_mean: float | None = None
    bootstrap_ci: BootstrapCISSO | None = None
    segments: list[SegmentMetricsSSO] = field(default_factory=list)
    negative_controls: list[NegativeControlSSO] = field(default_factory=list)
    gate_summary: GateSummarySSO | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION B — Core Math (pure functions, zero I/O)
# ═══════════════════════════════════════════════════════════════════════════════

def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _std(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))


def _percentile(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    sv = sorted(vals)
    n = len(sv)
    idx = (q / 100.0) * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sv[lo] * (1.0 - frac) + sv[hi] * frac


# ─── Public API ───────────────────────────────────────────────────────────────

def calculate_brier_score(
    probs: list[float],
    labels: list[float],
    baseline_probs: list[float] | None = None,
) -> BrierResult:
    """Calculate Brier score and BSS vs baseline.

    Args:
        probs: predicted probabilities [0, 1]
        labels: binary outcomes {0, 1}
        baseline_probs: if provided, compute BSS = 1 - brier / brier(baseline)
                        if None, baseline is climatology (mean(labels))

    Returns:
        BrierResult with brier, baseline_brier, bss_vs_baseline
    """
    if not probs:
        return BrierResult(n=0, brier=0.0, baseline_brier=0.0, bss_vs_baseline=0.0)
    n = len(probs)
    brier = sum((p - y) ** 2 for p, y in zip(probs, labels)) / n

    if baseline_probs is not None:
        baseline_brier = sum((p - y) ** 2 for p, y in zip(baseline_probs, labels)) / n
    else:
        # Climatology baseline
        clim = _mean(list(labels))
        baseline_brier = sum((clim - y) ** 2 for y in labels) / n

    bss = (1.0 - brier / baseline_brier) if baseline_brier > 0.0 else 0.0
    return BrierResult(n=n, brier=round(brier, 6), baseline_brier=round(baseline_brier, 6),
                       bss_vs_baseline=round(bss, 6))


def calculate_bss(model_brier: float, ref_brier: float) -> float:
    """BSS = 1 - model_brier / ref_brier.  Positive = model beats reference.

    Returns 0.0 if ref_brier ≤ 0.
    """
    if ref_brier <= 0.0:
        return 0.0
    return round(1.0 - model_brier / ref_brier, 6)


def calculate_ece(
    probs: list[float],
    labels: list[float],
    n_bins: int = 10,
) -> ECEResult:
    """Calculate Expected Calibration Error with bucket decomposition.

    Args:
        probs: predicted probabilities
        labels: binary outcomes
        n_bins: number of equal-width bins

    Returns:
        ECEResult with scalar ECE and per-bucket breakdown
    """
    if not probs:
        return ECEResult(n=0, ece=0.0, n_bins=n_bins, buckets=[])

    n = len(probs)
    bins: list[list[tuple[float, float]]] = [[] for _ in range(n_bins)]
    for p, y in zip(probs, labels):
        idx = min(int(p * n_bins), n_bins - 1)
        bins[idx].append((p, y))

    ece_val = 0.0
    buckets: list[ECEBucket] = []
    for i, b in enumerate(bins):
        if b:
            mp = sum(x for x, _ in b) / len(b)
            my = sum(y for _, y in b) / len(b)
            w = len(b) / n
            ace = abs(mp - my)
            ece_val += w * ace
            buckets.append(ECEBucket(
                bin_index=i,
                bin_lo=round(i / n_bins, 4),
                bin_hi=round((i + 1) / n_bins, 4),
                n=len(b),
                mean_predicted=round(mp, 6),
                mean_observed=round(my, 6),
                abs_calibration_error=round(ace, 6),
                weight=round(w, 6),
            ))

    return ECEResult(n=n, ece=round(ece_val, 6), n_bins=n_bins, buckets=buckets)


def calculate_bucket_ece(
    probs: list[float],
    labels: list[float],
    n_bins: int = 10,
) -> list[ECEBucket]:
    """Return only the per-bucket ECE breakdown (shorthand for ECEResult.buckets)."""
    return calculate_ece(probs, labels, n_bins=n_bins).buckets


def calculate_residual_summary(
    probs: list[float],
    labels: list[float],
    overconf_threshold: float = 0.04,
    underconf_threshold: float = 0.04,
) -> ResidualSummary:
    """Calculate residual statistics (pred − actual).

    Args:
        probs: predicted probabilities
        labels: binary outcomes
        overconf_threshold:  residual > +threshold → overconfident band
        underconf_threshold: residual < −threshold → underconfident band

    Returns:
        ResidualSummary
    """
    if not probs:
        return ResidualSummary(n=0, residual_mean=0.0, residual_std=0.0,
                               residual_min=0.0, residual_max=0.0,
                               overconfident_bands=0, underconfident_bands=0)

    residuals = [p - y for p, y in zip(probs, labels)]
    rm = _mean(residuals)
    rs = _std(residuals)
    over = sum(1 for r in residuals if r > overconf_threshold)
    under = sum(1 for r in residuals if r < -underconf_threshold)

    return ResidualSummary(
        n=len(probs),
        residual_mean=round(rm, 6),
        residual_std=round(rs, 6),
        residual_min=round(min(residuals), 6),
        residual_max=round(max(residuals), 6),
        overconfident_bands=over,
        underconfident_bands=under,
    )


def calculate_segment_metrics(
    model_probs: list[float],
    market_probs: list[float],
    labels: list[float],
    segment_name: str,
    segment_definition: str = "",
    n_bins_ece: int = 10,
    min_n: int = 20,
) -> SegmentMetricsSSO:
    """Compute the canonical SegmentMetricsSSO for a filtered list of rows.

    Args:
        model_probs: model home win probabilities
        market_probs: no-vig market home win probabilities
        labels: binary outcomes
        segment_name: e.g. "model_prob_0.65_0.70"
        segment_definition: human-readable filter description
        n_bins_ece: ECE bin count
        min_n: minimum rows to be non-data_limited

    Returns:
        SegmentMetricsSSO
    """
    n = len(model_probs)
    if n == 0:
        return SegmentMetricsSSO(
            segment_name=segment_name,
            segment_definition=segment_definition,
            n=0,
            model_brier=0.0, model_ece=0.0, model_residual_mean=0.0,
            model_residual_std=0.0, model_mean_prob=0.0,
            market_brier=0.0, market_ece=0.0, market_residual_mean=0.0,
            market_mean_prob=0.0,
            brier_delta=0.0, bss_vs_market=0.0, model_minus_market_mean=0.0,
            observed_win_rate=0.0,
            market_superiority=False, data_limited=True,
        )

    mb = sum((p - y) ** 2 for p, y in zip(model_probs, labels)) / n
    mkb = sum((p - y) ** 2 for p, y in zip(market_probs, labels)) / n
    mece = calculate_ece(model_probs, labels, n_bins=n_bins_ece).ece
    mkece = calculate_ece(market_probs, labels, n_bins=n_bins_ece).ece
    m_res = _mean([p - y for p, y in zip(model_probs, labels)])
    mk_res = _mean([p - y for p, y in zip(market_probs, labels)])
    m_std = _std([p - y for p, y in zip(model_probs, labels)])
    brier_delta = mb - mkb
    bss = calculate_bss(mb, mkb)
    owr = _mean(list(labels))

    return SegmentMetricsSSO(
        segment_name=segment_name,
        segment_definition=segment_definition,
        n=n,
        model_brier=round(mb, 6),
        model_ece=round(mece, 6),
        model_residual_mean=round(m_res, 6),
        model_residual_std=round(m_std, 6),
        model_mean_prob=round(_mean(model_probs), 6),
        market_brier=round(mkb, 6),
        market_ece=round(mkece, 6),
        market_residual_mean=round(mk_res, 6),
        market_mean_prob=round(_mean(market_probs), 6),
        brier_delta=round(brier_delta, 6),
        bss_vs_market=round(bss, 6),
        model_minus_market_mean=round(_mean(model_probs) - _mean(market_probs), 6),
        observed_win_rate=round(owr, 6),
        market_superiority=(mkb < mb),
        data_limited=(n < min_n),
    )


def calculate_model_market_delta(
    model_probs: list[float],
    market_probs: list[float],
    labels: list[float],
) -> dict[str, float]:
    """Summarise model-market probability and Brier delta.

    Returns a plain dict suitable for JSON serialisation.
    """
    n = len(model_probs)
    if n == 0:
        return {
            "n": 0,
            "model_brier": 0.0,
            "market_brier": 0.0,
            "brier_delta": 0.0,
            "bss_vs_market": 0.0,
            "model_prob_mean": 0.0,
            "market_prob_mean": 0.0,
            "prob_mean_delta": 0.0,
        }
    mb = sum((p - y) ** 2 for p, y in zip(model_probs, labels)) / n
    mkb = sum((p - y) ** 2 for p, y in zip(market_probs, labels)) / n
    return {
        "n": n,
        "model_brier": round(mb, 6),
        "market_brier": round(mkb, 6),
        "brier_delta": round(mb - mkb, 6),
        "bss_vs_market": round(calculate_bss(mb, mkb), 6),
        "model_prob_mean": round(_mean(model_probs), 6),
        "market_prob_mean": round(_mean(market_probs), 6),
        "prob_mean_delta": round(_mean(model_probs) - _mean(market_probs), 6),
    }


# ─── Bootstrap CI ─────────────────────────────────────────────────────────────

def bootstrap_ci(
    values: list[float],
    stat_fn: Any,  # Callable[[list[float]], float]
    n_boot: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
    ci_stable_width: float = 0.10,
    metric: str = "",
    segment: str = "",
    method: str = "",
) -> BootstrapCISSO:
    """Generic bootstrap CI for any scalar statistic.

    Args:
        values: raw sample values
        stat_fn: function (list[float]) → float
        n_boot: number of bootstrap resamples
        seed: random seed for reproducibility
        alpha: two-sided alpha (default 0.05 → 95% CI)
        ci_stable_width: width threshold for ci_stable flag
        metric: label for the metric
        segment: label for the segment
        method: optional method label (Phase69 compatibility)

    Returns:
        BootstrapCISSO
    """
    n = len(values)
    if n < 2:
        return BootstrapCISSO(
            metric=metric, segment=segment, n=n, n_boot=n_boot, seed=seed,
            observed=stat_fn(values) if n > 0 else 0.0,
            ci_lower=0.0, ci_upper=0.0,
            ci_excludes_zero=False, ci_stable=False, ci_width=0.0,
            data_limited=True, method=method,
        )

    rng = random.Random(seed)
    observed = stat_fn(values)
    boot_stats = [stat_fn(rng.choices(values, k=n)) for _ in range(n_boot)]

    lo_pct = (alpha / 2.0) * 100.0
    hi_pct = (1.0 - alpha / 2.0) * 100.0
    ci_lo = round(_percentile(boot_stats, lo_pct), 6)
    ci_hi = round(_percentile(boot_stats, hi_pct), 6)
    width = ci_hi - ci_lo

    return BootstrapCISSO(
        metric=metric,
        segment=segment,
        n=n,
        n_boot=n_boot,
        seed=seed,
        observed=round(observed, 6),
        ci_lower=ci_lo,
        ci_upper=ci_hi,
        ci_excludes_zero=(ci_hi < 0.0 or ci_lo > 0.0),
        ci_stable=(width < ci_stable_width),
        ci_width=round(width, 6),
        data_limited=False,
        method=method,
    )


def bootstrap_brier_delta_ci(
    model_probs: list[float],
    market_probs: list[float],
    labels: list[float],
    n_boot: int = 1000,
    seed: int = 42,
    ci_stable_width: float = 0.10,
    segment: str = "",
) -> BootstrapCISSO:
    """Bootstrap CI for model_brier - market_brier.

    Convenience wrapper for the most common use-case in Phase70/71.
    """
    n = len(model_probs)
    if n < 2:
        return BootstrapCISSO(
            metric="brier_delta_vs_market", segment=segment, n=n,
            n_boot=n_boot, seed=seed,
            observed=0.0, ci_lower=0.0, ci_upper=0.0,
            ci_excludes_zero=False, ci_stable=False, ci_width=0.0,
            data_limited=True,
        )

    rows = list(zip(model_probs, market_probs, labels))
    rng = random.Random(seed)

    def _brier_delta(sample: list[tuple[float, float, float]]) -> float:
        k = len(sample)
        mb = sum((mp - y) ** 2 for mp, _, y in sample) / k
        mkb = sum((mkp - y) ** 2 for _, mkp, y in sample) / k
        return mb - mkb

    observed = _brier_delta(rows)
    boot_stats = [_brier_delta(rng.choices(rows, k=n)) for _ in range(n_boot)]
    ci_lo = round(_percentile(boot_stats, 2.5), 6)
    ci_hi = round(_percentile(boot_stats, 97.5), 6)
    width = ci_hi - ci_lo

    return BootstrapCISSO(
        metric="brier_delta_vs_market",
        segment=segment,
        n=n,
        n_boot=n_boot,
        seed=seed,
        observed=round(observed, 6),
        ci_lower=ci_lo,
        ci_upper=ci_hi,
        ci_excludes_zero=(ci_hi < 0.0 or ci_lo > 0.0),
        ci_stable=(width < ci_stable_width),
        ci_width=round(width, 6),
        data_limited=(n < 20),
    )


# ─── Negative Control ─────────────────────────────────────────────────────────

def build_negative_control_summary(
    control_name: str,
    control_type: str,
    description: str,
    observed_gap: float,
    permuted_gaps: list[float],
    seed: int = 42,
    n_permutations: int | None = None,
) -> NegativeControlSSO:
    """Build a NegativeControlSSO from pre-computed permutation gaps.

    Args:
        control_name: identifier
        control_type: e.g. "shuffle_labels", "random_split"
        description: human-readable description
        observed_gap: the real signal gap
        permuted_gaps: list of gaps from permuted/null distributions
        seed: seed used in permutation
        n_permutations: if None, inferred from len(permuted_gaps)

    Returns:
        NegativeControlSSO
    """
    if not permuted_gaps:
        return NegativeControlSSO(
            control_name=control_name,
            control_type=control_type,
            description=description,
            n_permutations=0,
            seed=seed,
            observed_gap=round(observed_gap, 6),
            permuted_gap_mean=0.0,
            permuted_gap_std=0.0,
            signal_gap=round(observed_gap, 6),
            overfit_risk=False,
            interpretation="insufficient_permutations",
        )

    pm = _mean(permuted_gaps)
    ps = _std(permuted_gaps)
    signal_gap = observed_gap - pm
    # Overfit risk: signal is not stronger than 1 std above null
    overfit_risk = signal_gap <= ps

    interp = (
        "real_signal_detected" if (signal_gap > ps * 1.5)
        else "marginal_signal" if signal_gap > 0
        else "overfit_risk_null_not_rejected"
    )

    return NegativeControlSSO(
        control_name=control_name,
        control_type=control_type,
        description=description,
        n_permutations=n_permutations if n_permutations is not None else len(permuted_gaps),
        seed=seed,
        observed_gap=round(observed_gap, 6),
        permuted_gap_mean=round(pm, 6),
        permuted_gap_std=round(ps, 6),
        signal_gap=round(signal_gap, 6),
        overfit_risk=overfit_risk,
        interpretation=interp,
    )


# ─── Gate Summary ─────────────────────────────────────────────────────────────

def build_gate_summary(
    phase_id: str,
    gate: str,
    gate_candidates: list[str],
    gate_rationale: str,
    completion_marker: str,
    worth_next_phase: bool = False,
    next_phase_recommendation: str = "",
    candidate_patch_created: bool = False,
    production_modified: bool = False,
    alpha_modified: bool = False,
    no_edge_claim: bool = True,
    report_paths: list[str] | None = None,
) -> GateSummarySSO:
    """Build a canonical GateSummarySSO."""
    if gate not in VALID_GATES:
        raise ValueError(f"gate '{gate}' is not in VALID_GATES: {sorted(VALID_GATES)}")
    return GateSummarySSO(
        phase_id=phase_id,
        gate=gate,
        gate_candidates=list(gate_candidates),
        gate_rationale=gate_rationale,
        worth_next_phase=worth_next_phase,
        next_phase_recommendation=next_phase_recommendation,
        candidate_patch_created=candidate_patch_created,
        production_modified=production_modified,
        alpha_modified=alpha_modified,
        no_edge_claim=no_edge_claim,
        report_paths=report_paths or [],
        completion_marker=completion_marker,
    )


# ─── Validation ───────────────────────────────────────────────────────────────

class MetricsValidationError(Exception):
    """Raised when a metrics payload fails schema validation."""
    pass


_REQUIRED_FIELDS_SEGMENT: frozenset[str] = frozenset({
    "segment_name", "segment_definition", "n",
    "model_brier", "model_ece", "model_residual_mean",
    "market_brier", "market_ece", "market_residual_mean",
    "brier_delta", "bss_vs_market", "observed_win_rate",
    "market_superiority", "data_limited",
})

_REQUIRED_FIELDS_BOOTSTRAP: frozenset[str] = frozenset({
    "metric", "segment", "n", "n_boot", "seed",
    "observed", "ci_lower", "ci_upper",
    "ci_excludes_zero", "ci_stable", "ci_width", "data_limited",
})

_REQUIRED_FIELDS_NEGATIVE_CONTROL: frozenset[str] = frozenset({
    "control_name", "control_type", "description",
    "n_permutations", "seed",
    "observed_gap", "permuted_gap_mean", "permuted_gap_std",
    "signal_gap", "overfit_risk", "interpretation",
})

_REQUIRED_FIELDS_GATE: frozenset[str] = frozenset({
    "phase_id", "gate", "gate_candidates", "gate_rationale",
    "worth_next_phase", "next_phase_recommendation",
    "candidate_patch_created", "production_modified", "alpha_modified",
    "no_edge_claim", "report_paths", "completion_marker",
})


def validate_metrics_payload(payload: dict[str, Any]) -> list[str]:
    """Validate a metrics payload dict against the SSOT schema.

    Returns a list of validation error strings (empty = valid).
    Does NOT raise; caller decides whether to fail.
    """
    errors: list[str] = []

    # Check top-level required keys
    for key in ("phase_id", "n_samples"):
        if key not in payload:
            errors.append(f"Missing top-level key: '{key}'")

    # Validate segments if present
    for i, seg in enumerate(payload.get("segments", [])):
        missing = _REQUIRED_FIELDS_SEGMENT - set(seg.keys())
        if missing:
            errors.append(f"Segment[{i}] missing fields: {sorted(missing)}")
        if seg.get("n", -1) < 0:
            errors.append(f"Segment[{i}] has negative n")

    # Validate bootstrap_ci if present
    bci = payload.get("bootstrap_ci")
    if bci is not None:
        missing = _REQUIRED_FIELDS_BOOTSTRAP - set(bci.keys())
        if missing:
            errors.append(f"bootstrap_ci missing fields: {sorted(missing)}")

    # Validate negative controls if present
    for i, nc in enumerate(payload.get("negative_controls", [])):
        missing = _REQUIRED_FIELDS_NEGATIVE_CONTROL - set(nc.keys())
        if missing:
            errors.append(f"NegativeControl[{i}] missing fields: {sorted(missing)}")

    # Validate gate_summary if present
    gs = payload.get("gate_summary")
    if gs is not None:
        missing = _REQUIRED_FIELDS_GATE - set(gs.keys())
        if missing:
            errors.append(f"gate_summary missing fields: {sorted(missing)}")
        gate = gs.get("gate", "")
        if gate and gate not in VALID_GATES:
            errors.append(f"gate_summary.gate '{gate}' not in VALID_GATES")

    # Safety flags
    if payload.get("candidate_patch_created", False) is not False:
        errors.append("Safety violation: candidate_patch_created must be False")
    if payload.get("production_modified", False) is not False:
        errors.append("Safety violation: production_modified must be False")
    if payload.get("alpha_modified", False) is not False:
        errors.append("Safety violation: alpha_modified must be False")

    return errors


# ─── Serialisation helper ─────────────────────────────────────────────────────

def ssot_to_dict(obj: Any) -> Any:
    """Recursively convert SSOT dataclass instances to JSON-serialisable dicts."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: ssot_to_dict(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, (list, tuple)):
        return [ssot_to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: ssot_to_dict(v) for k, v in obj.items()}
    return obj


# ─── Inventory helpers (used by the inventory script) ─────────────────────────

# Canonical field lists for inventory checks
CANONICAL_SEGMENT_FIELDS: list[str] = sorted(_REQUIRED_FIELDS_SEGMENT)
CANONICAL_BOOTSTRAP_FIELDS: list[str] = sorted(_REQUIRED_FIELDS_BOOTSTRAP)
CANONICAL_NC_FIELDS: list[str] = sorted(_REQUIRED_FIELDS_NEGATIVE_CONTROL)
CANONICAL_GATE_FIELDS: list[str] = sorted(_REQUIRED_FIELDS_GATE)

# Map of what each phase actually used (from manual audit) — read-only inventory
PHASE_SCHEMA_INVENTORY: dict[str, dict[str, Any]] = {
    "phase67": {
        "brier_fn": "_brier_score",
        "bss_fn": "_bss_direct",
        "ece_fn": "_compute_ece",
        "segment_class": "SegmentMetrics",
        "segment_fields_present": [
            "n", "model_brier", "market_brier", "blend_brier",
            "blend_bss_vs_market", "model_bss_vs_market",
            "fav_win_rate", "win_rate", "ece_blend",
        ],
        "bootstrap_class": "BootstrapResult",
        "bootstrap_fields_present": [
            "n", "n_boot", "observed_delta", "ci_lower", "ci_upper",
            "prob_positive", "significant",
        ],
        "nc_class": "NegativeControl",
        "nc_fields_present": [
            "dim", "segment", "real_blend_bss_delta",
            "shuffled_mean_delta", "shuffled_std_delta",
            "null_rejected", "overfit_risk",
        ],
        "safety_flags": ["CANDIDATE_PATCH_CREATED", "PRODUCTION_MODIFIED", "ALPHA_MODIFIED"],
        "gate": "OVERFIT_RISK",
        "naming_notes": [
            "BootstrapResult uses 'observed_delta' (SSOT: 'observed')",
            "BootstrapResult uses 'significant' (SSOT: 'ci_excludes_zero')",
            "NegativeControl uses 'dim'+'segment' (SSOT: 'control_name'+'control_type')",
            "NegativeControl missing 'control_type', 'n_permutations', 'seed', 'interpretation'",
            "SegmentMetrics uses 'ece_blend' (SSOT: 'model_ece')",
            "SegmentMetrics missing 'model_residual_mean', 'market_residual_mean', 'observed_win_rate'",
        ],
    },
    "phase68": {
        "brier_fn": "_brier",
        "bss_fn": "_bss_direct",
        "ece_fn": "_ece",
        "segment_class": "SegmentMetrics",
        "segment_fields_present": [
            "n", "model_brier", "market_brier", "blend_brier",
            "blend_bss_vs_market", "model_bss_vs_market",
            "fav_win_rate", "ece_blend", "ece_model", "ece_market",
            "mean_blend_fav_prob", "mean_model_fav_prob", "mean_mkt_fav_prob",
            "data_limited",
        ],
        "bootstrap_class": "None (no BootstrapCI class in phase68)",
        "bootstrap_fields_present": [],
        "nc_class": "NegativeControl",
        "nc_fields_present": [
            "control_name", "description", "real_bss",
            "null_bss_mean", "null_bss_std", "signal_gap",
            "overfit_threshold", "overfit_risk",
        ],
        "safety_flags": ["CANDIDATE_PATCH_CREATED", "PRODUCTION_MODIFIED", "ALPHA_MODIFIED"],
        "gate": "CALIBRATION_OBJECTIVE_REDESIGN_PROMISING",
        "naming_notes": [
            "NegativeControl uses 'real_bss' (SSOT: 'observed_gap')",
            "NegativeControl uses 'null_bss_mean'/'null_bss_std' (SSOT: 'permuted_gap_mean'/'permuted_gap_std')",
            "NegativeControl has 'overfit_threshold' (not in SSOT)",
            "NegativeControl missing 'control_type', 'n_permutations', 'seed', 'interpretation'",
            "SegmentMetrics uses 'ece_blend'/'ece_model'/'ece_market' (SSOT: 'model_ece'/'market_ece')",
            "SegmentMetrics missing 'model_residual_mean', 'market_residual_mean', 'brier_delta', 'observed_win_rate'",
        ],
    },
    "phase69": {
        "brier_fn": "_brier",
        "bss_fn": "_bss_direct",
        "ece_fn": "_ece",
        "segment_class": "None (phase69 uses CounterfactualMetrics, not SegmentMetrics)",
        "segment_fields_present": [
            "segment", "method", "brier", "bss_vs_market", "bss_vs_original",
            "ece", "brier_delta_vs_original", "ece_delta_vs_original",
        ],
        "bootstrap_class": "BootstrapCI",
        "bootstrap_fields_present": [
            "metric", "method", "segment", "n", "n_boot",
            "observed", "ci_lower", "ci_upper",
            "ci_excludes_zero", "ci_stable", "data_limited",
        ],
        "nc_class": "NegativeControlResult",
        "nc_fields_present": [
            "control_name", "description", "real_improvement",
            "null_improvement_mean", "null_improvement_std",
            "signal_gap", "overfit_risk", "n_permutations",
        ],
        "safety_flags": ["CANDIDATE_PATCH_CREATED", "PRODUCTION_MODIFIED", "ALPHA_MODIFIED"],
        "gate": "CALIBRATION_OBJECTIVE_NOT_PROMISING",
        "naming_notes": [
            "BootstrapCI adds 'method' (not in Phase70/71 SSOT canonical)",
            "BootstrapCI missing 'seed', 'ci_width'",
            "NegativeControlResult uses 'real_improvement' (SSOT: 'observed_gap')",
            "NegativeControlResult uses 'null_improvement_mean' (SSOT: 'permuted_gap_mean')",
            "NegativeControlResult missing 'control_type', 'seed', 'interpretation'",
            "Phase69 uses CounterfactualMetrics (not SegmentMetricsSSO) — structurally different",
        ],
    },
    "phase70": {
        "brier_fn": "_brier",
        "bss_fn": "_bss_direct",
        "ece_fn": "_ece",
        "segment_class": "SegmentMetrics",
        "segment_fields_present": [
            "segment", "n", "brier", "bss_vs_market", "ece",
            "residual_mean", "residual_std", "observed_win_rate",
            "predicted_mean_prob", "market_brier", "market_residual_mean",
            "market_mean_prob", "model_minus_market_mean",
            "market_beats_model_brier", "severe_underconfidence", "data_limited",
        ],
        "bootstrap_class": "BootstrapCI",
        "bootstrap_fields_present": [
            "metric", "segment", "n", "n_boot",
            "observed", "ci_lower", "ci_upper",
            "ci_excludes_zero", "ci_stable", "data_limited",
        ],
        "nc_class": "NegativeControlResult",
        "nc_fields_present": [
            "control_name", "description", "n_permutations",
            "observed_gap", "permuted_gap_mean", "permuted_gap_std",
            "signal_gap", "overfit_risk", "interpretation",
        ],
        "safety_flags": ["CANDIDATE_PATCH_CREATED", "PRODUCTION_MODIFIED", "ALPHA_MODIFIED"],
        "gate": "MARKET_ONLY_SUPERIOR",
        "naming_notes": [
            "SegmentMetrics uses 'brier' (SSOT: 'model_brier')",
            "SegmentMetrics uses 'predicted_mean_prob' (SSOT: 'model_mean_prob')",
            "SegmentMetrics uses 'bss_vs_market' (compatible with SSOT)",
            "SegmentMetrics has 'severe_underconfidence' (not in SSOT canonical)",
            "BootstrapCI missing 'seed', 'ci_width' (vs SSOT)",
        ],
    },
    "phase71": {
        "brier_fn": "_brier",
        "bss_fn": "_bss_direct",
        "ece_fn": "_ece",
        "segment_class": "SegmentMetrics",
        "segment_fields_present": [
            "segment", "n", "model_brier", "model_ece",
            "model_residual_mean", "model_residual_std",
            "observed_win_rate", "model_mean_prob",
            "market_brier", "market_ece", "market_residual_mean",
            "market_mean_prob", "brier_delta", "model_minus_market_mean",
            "bss_vs_market", "market_superiority", "data_limited",
        ],
        "bootstrap_class": "BootstrapCI",
        "bootstrap_fields_present": [
            "metric", "segment", "n", "n_boot",
            "observed", "ci_lower", "ci_upper",
            "ci_excludes_zero", "ci_stable", "data_limited",
        ],
        "nc_class": "NegativeControlResult",
        "nc_fields_present": [
            "control_name", "description", "n_permutations",
            "observed_gap", "permuted_gap_mean", "permuted_gap_std",
            "signal_gap", "overfit_risk", "interpretation",
        ],
        "safety_flags": ["CANDIDATE_PATCH_CREATED", "PRODUCTION_MODIFIED", "ALPHA_MODIFIED"],
        "gate": "MARKET_DE_RISK_GUARD_PROMISING",
        "naming_notes": [
            "Phase71 SegmentMetrics is closest to SSOT canonical",
            "BootstrapCI missing 'seed', 'ci_width' (vs SSOT)",
            "Phase71 is reference implementation for SSOT math",
        ],
    },
    "phase72": {
        "brier_fn": "N/A (no data load in Phase72)",
        "bss_fn": "N/A",
        "ece_fn": "N/A",
        "segment_class": "N/A (guard spec only, no segment calculation)",
        "segment_fields_present": [],
        "bootstrap_class": "N/A",
        "bootstrap_fields_present": [],
        "nc_class": "N/A",
        "nc_fields_present": [],
        "safety_flags": [
            "CANDIDATE_PATCH_CREATED", "PRODUCTION_MODIFIED", "ALPHA_MODIFIED",
            "DIAGNOSTIC_ONLY", "PREDICTION_JSONL_OVERWRITTEN", "PIT_SAFE_VALIDATION",
        ],
        "gate": "MARKET_DERISK_GUARD_SPEC_READY",
        "naming_notes": [
            "Phase72 is a paper-only guard proposal; no metrics calculation",
            "Phase72 references Phase71 evidence as read-only constants",
            "Phase72 safety flags are most complete (6 flags vs 3-4 in prior phases)",
        ],
    },
}
