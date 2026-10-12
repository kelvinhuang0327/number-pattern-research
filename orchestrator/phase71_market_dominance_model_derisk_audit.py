"""Phase 71 — Market Dominance and Model De-risk Audit for 0.65–0.70 Strong Favorite Band

DIAGNOSTIC ONLY.  CANDIDATE_PATCH_CREATED = False.  PRODUCTION_MODIFIED = False.
ALPHA_MODIFIED = False.  PREDICTION_JSONL_OVERWRITTEN = False.  ALPHA = 0.40 (FROZEN).

Phase 70 found: gate = MARKET_ONLY_SUPERIOR
  model Brier (0.65–0.70) = 0.1865, market Brier = 0.1725, gap = +0.014
  Both model and market underestimate true win rate (0.767)
  Market distribution is wider / better-spread → lower Brier
  split residual std is high → direction inconsistent across windows
  sp_fip_delta extreme_delta = +0.314 → possible pitcher/market correlation
  5/5 negative controls passed

Phase 71 paper-only audit investigates:
  A. Market dominance: per-segment model vs market Brier, residual, ECE
  B. Market distribution shape: std, min/max, IQR, rank correlation, compression
  C. sp_fip_delta × market signal: correlation, bucket analysis, independence
  D. Split / date / sample concentration: per-split market Brier comparison
  E. Team / pitcher / feature concentration: top teams, feature availability matrix

NEGATIVE CONTROLS (6):
  1. shuffled_market_assignment     — scramble market_home_prob within band
  2. shuffled_model_assignment      — scramble model_home_prob within band
  3. random_model_minus_market      — shuffle model-minus-market differences
  4. random_sp_fip_bucket           — random sp_fip_delta high/low bucket
  5. random_split_assignment        — shuffle split_id labels
  6. irrelevant_date_bucket_split   — odd/even day-of-month Brier gap

GATE (one of 7):
  MARKET_DE_RISK_GUARD_PROMISING
  MARKET_AWARE_ENSEMBLE_PROMISING
  SP_FIP_FEATURE_REPAIR_PROMISING
  MARKET_DOMINANCE_DATA_LIMITED
  SPLIT_INSTABILITY_RISK
  OVERFIT_RISK
  MARKET_DOMINANCE_NOT_PROMISING

PHASE CHAIN:
  Phase 70 gate: MARKET_ONLY_SUPERIOR  (carried from Phase 70)
  Phase 71 gate: one of 7 listed above

SAFETY CONSTANTS (FROZEN, DO NOT MODIFY):
  CANDIDATE_PATCH_CREATED        = False
  PRODUCTION_MODIFIED            = False
  ALPHA_MODIFIED                 = False
  DIAGNOSTIC_ONLY                = True
  PREDICTION_JSONL_OVERWRITTEN   = False
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

# ═══════════════════════════════════════════════════════════════════
# SAFETY CONSTANTS — FROZEN, DO NOT MODIFY
# ═══════════════════════════════════════════════════════════════════
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
ALPHA_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
PREDICTION_JSONL_OVERWRITTEN: bool = False
PIT_SAFE_VALIDATION: bool = True
ALPHA: float = 0.40

# ═══════════════════════════════════════════════════════════════════
# PHASE IDENTITY
# ═══════════════════════════════════════════════════════════════════
PHASE_VERSION: str = "phase71_market_dominance_model_derisk_audit_v1"
COMPLETION_MARKER: str = "PHASE_71_MARKET_DOMINANCE_MODEL_DERISK_AUDIT_VERIFIED"

# ═══════════════════════════════════════════════════════════════════
# GATE CONSTANTS (7)
# ═══════════════════════════════════════════════════════════════════
MARKET_DE_RISK_GUARD_PROMISING: str = "MARKET_DE_RISK_GUARD_PROMISING"
MARKET_AWARE_ENSEMBLE_PROMISING: str = "MARKET_AWARE_ENSEMBLE_PROMISING"
SP_FIP_FEATURE_REPAIR_PROMISING: str = "SP_FIP_FEATURE_REPAIR_PROMISING"
MARKET_DOMINANCE_DATA_LIMITED: str = "MARKET_DOMINANCE_DATA_LIMITED"
SPLIT_INSTABILITY_RISK: str = "SPLIT_INSTABILITY_RISK"
OVERFIT_RISK: str = "OVERFIT_RISK"
MARKET_DOMINANCE_NOT_PROMISING: str = "MARKET_DOMINANCE_NOT_PROMISING"

_VALID_GATES: frozenset[str] = frozenset({
    MARKET_DE_RISK_GUARD_PROMISING,
    MARKET_AWARE_ENSEMBLE_PROMISING,
    SP_FIP_FEATURE_REPAIR_PROMISING,
    MARKET_DOMINANCE_DATA_LIMITED,
    SPLIT_INSTABILITY_RISK,
    OVERFIT_RISK,
    MARKET_DOMINANCE_NOT_PROMISING,
})

# ═══════════════════════════════════════════════════════════════════
# PREVIOUS PHASE GATE ANCHORS (FROZEN — READ ONLY)
# ═══════════════════════════════════════════════════════════════════
PHASE70_GATE_ANCHOR: str = "MARKET_ONLY_SUPERIOR"
PHASE70_VERSION: str = "phase70_strong_home_favorite_underconfidence_audit_v1"

# ═══════════════════════════════════════════════════════════════════
# ANALYSIS THRESHOLDS
# ═══════════════════════════════════════════════════════════════════
_MIN_SEGMENT_N: int = 20          # minimum rows for a segment to be non-data_limited
_MIN_BUCKET_N: int = 10           # minimum rows for bucket-level stats
_BOOTSTRAP_N: int = 1000          # default bootstrap iterations

# Target band (Phase 70 finding)
_TARGET_BAND_LO: float = 0.65
_TARGET_BAND_HI: float = 0.70

# Gate decision thresholds
_MARKET_SUPERIORITY_BRIER_GAP: float = 0.005    # model_brier - market_brier >= this
_MARKET_SUPERIORITY_CI_STABLE: bool = True       # CI must be stable for GUARD gate
_RESIDUAL_SPLIT_STD_THRESHOLD: float = 0.08      # std of residuals across splits >= this
_NC_SIGNAL_THRESHOLD: float = 0.04               # |signal_gap| < this → overfit_risk
_NC_OVERFIT_RISK_COUNT_THRESHOLD: int = 4        # >= 4/6 NCs with overfit_risk → OVERFIT_RISK
_CI_STABLE_WIDTH: float = 0.10                   # CI width > this → unstable
_SP_FIP_CORRELATION_THRESHOLD: float = 0.10      # |corr| >= this → meaningful sp_fip signal
_SP_FIP_RESIDUAL_BUCKET_GAP: float = 0.05        # |residual_gap| >= this in sp_fip buckets
_DISTRIBUTION_COMPRESSION_RATIO: float = 0.90   # model_std / market_std <= this → compressed
_RANK_CORR_THRESHOLD: float = 0.80              # rank corr >= this → model/market agree on rank
_DISAGREEMENT_GAP: float = 0.05                  # |model_minus_market| >= this → disagreement
_MARKET_INDEPENDENT_BRIER_GAP: float = 0.010    # gap when sp_fip is "independent" of market

# ═══════════════════════════════════════════════════════════════════
# SEGMENT DEFINITIONS  (same as Phase 70 for comparability)
# ═══════════════════════════════════════════════════════════════════
_SEGMENT_DEFS: list[tuple[str, float, float, str | None]] = [
    ("all_games",              0.00, 1.01, None),
    ("home_favorite_only",     0.50, 1.01, None),
    ("away_favorite_only",     0.00, 0.50, None),
    ("model_prob_0.60_0.65",   0.60, 0.65, None),
    ("model_prob_0.65_0.70",   0.65, 0.70, None),   # KEY: target band
    ("model_prob_0.70_0.75",   0.70, 0.75, None),
    ("heavy_favorite",         0.70, 1.01, None),
    ("high_confidence",        0.75, 1.01, None),
    ("extreme_favorite",       0.80, 1.01, None),
    ("phase45_failure",        0.60, 1.01, "home_win_0"),
    ("phase68_failure",        0.65, 1.01, "home_win_0"),
    ("phase70_target",         0.65, 0.70, None),   # alias for target band
]

# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SegmentMetrics:
    """Full market + model side-by-side metrics for one segment (Phase 71 variant)."""
    segment: str
    n: int
    # Model metrics
    model_brier: float
    model_ece: float
    model_residual_mean: float      # model_home_prob - home_win
    model_residual_std: float
    observed_win_rate: float
    model_mean_prob: float
    # Market metrics
    market_brier: float
    market_ece: float
    market_residual_mean: float     # market_home_prob - home_win
    market_mean_prob: float
    # Comparison
    brier_delta: float              # model_brier - market_brier (positive = market better)
    model_minus_market_mean: float  # model_home_prob - market_home_prob_no_vig
    bss_vs_market: float            # BSS = 1 - model_brier / market_brier
    market_superiority: bool        # brier_delta >= _MARKET_SUPERIORITY_BRIER_GAP
    # Flags
    data_limited: bool


@dataclass
class DistributionShapeResult:
    """Distribution shape comparison for model vs market in a segment."""
    segment: str
    n: int
    # Model shape
    model_std: float
    model_min: float
    model_max: float
    model_q25: float
    model_q75: float
    model_iqr: float
    # Market shape
    market_std: float
    market_min: float
    market_max: float
    market_q25: float
    market_q75: float
    market_iqr: float
    # Comparison
    compression_ratio: float        # model_std / market_std (< 1 means model narrower)
    rank_correlation: float         # Spearman rank correlation of model vs market prob
    mean_disagreement: float        # mean |model_home_prob - market_home_prob_no_vig|
    n_disagreement_rows: int        # rows with |diff| >= _DISAGREEMENT_GAP
    disagreement_rate: float        # n_disagreement_rows / n
    model_compressed: bool          # compression_ratio <= _DISTRIBUTION_COMPRESSION_RATIO
    data_limited: bool


@dataclass
class SpFipAttributionResult:
    """sp_fip_delta × market signal attribution in target band."""
    # Availability
    n_target_available: int
    n_target_total: int
    n_all_available: int
    n_all_total: int
    availability_rate_target: float
    availability_rate_all: float
    # Distribution
    mean_sp_fip_target: float | None
    mean_sp_fip_all: float | None
    std_sp_fip_target: float | None
    std_sp_fip_all: float | None
    # Correlations (available rows only)
    sp_fip_vs_model_minus_market_corr: float    # sp_fip corr with model-market diff
    sp_fip_vs_market_prob_corr: float           # sp_fip corr with market_home_prob
    sp_fip_vs_outcome_residual_corr: float      # sp_fip corr with model residual
    # Bucket analysis (sp_fip_delta high vs low in target band)
    n_sp_fip_high_bucket: int                   # sp_fip_delta > median
    n_sp_fip_low_bucket: int                    # sp_fip_delta <= median
    model_brier_sp_fip_high: float
    model_brier_sp_fip_low: float
    market_brier_sp_fip_high: float
    market_brier_sp_fip_low: float
    residual_mean_sp_fip_high: float
    residual_mean_sp_fip_low: float
    residual_bucket_gap: float                  # high - low residual
    # Key finding
    sp_fip_absorbed_by_market: bool             # market corr > model corr with sp_fip
    sp_fip_independent_signal: bool             # residual_bucket_gap >= _SP_FIP_RESIDUAL_BUCKET_GAP
    data_limited: bool


@dataclass
class SplitMarketResult:
    """Per-split model vs market comparison for the target band."""
    split_id: str
    n: int
    model_brier: float
    market_brier: float
    brier_delta: float              # model_brier - market_brier
    model_residual_mean: float
    market_residual_mean: float
    observed_win_rate: float
    model_mean_prob: float
    market_mean_prob: float
    market_superior: bool
    data_limited: bool


@dataclass
class TeamConcentrationResult:
    """Concentration metrics in the target band (per home team)."""
    team: str
    n_in_target_band: int
    share_of_target_band: float
    model_brier: float
    market_brier: float
    brier_delta: float
    model_residual_mean: float
    observed_win_rate: float
    model_mean_prob: float
    market_mean_prob: float
    data_limited: bool


@dataclass
class FeatureAvailabilityRow:
    """Feature availability and concentration check for one feature."""
    feature_name: str
    source_dict: str
    n_available_target: int
    n_available_all: int
    availability_rate_target: float
    availability_rate_all: float
    mean_value_target: float | None
    mean_value_all: float | None
    extreme_delta: float
    data_limited: bool


@dataclass
class NegativeControlResult:
    """One of the 6 negative controls."""
    control_name: str
    description: str
    n_permutations: int
    observed_gap: float
    permuted_gap_mean: float
    permuted_gap_std: float
    signal_gap: float
    overfit_risk: bool
    interpretation: str


@dataclass
class BootstrapCI:
    """Bootstrap CI for a key metric in a segment."""
    metric: str
    segment: str
    n: int
    n_boot: int
    observed: float
    ci_lower: float
    ci_upper: float
    ci_excludes_zero: bool
    ci_stable: bool         # CI width < _CI_STABLE_WIDTH
    data_limited: bool


@dataclass
class Phase71Report:
    """Full Phase 71 report: market dominance and model de-risk audit."""
    phase_version: str
    completion_marker: str
    generated_at: str
    data_path: str

    # Safety flags (all FROZEN)
    candidate_patch_created: bool
    production_modified: bool
    alpha_modified: bool
    diagnostic_only: bool
    prediction_jsonl_overwritten: bool
    pit_safe_validation: bool
    alpha: float

    # Phase anchor
    phase70_gate_anchor: str

    # Data summary
    n_total: int
    feature_version: str
    n_target_band: int

    # Dimension A: per-segment market vs model metrics
    segment_metrics: list[SegmentMetrics]

    # Dimension B: distribution shape comparison
    distribution_shape: list[DistributionShapeResult]

    # Dimension C: sp_fip_delta × market signal
    sp_fip_attribution: SpFipAttributionResult | None

    # Dimension D: per-split market comparison
    split_market_results: list[SplitMarketResult]

    # Dimension E: team concentration + feature availability matrix
    team_concentration: list[TeamConcentrationResult]
    feature_availability: list[FeatureAvailabilityRow]

    # Negative controls (6)
    negative_controls: list[NegativeControlResult]

    # Bootstrap CIs
    bootstrap_cis: list[BootstrapCI]

    # Gate
    gate: str
    gate_rationale: str
    phase72_recommendation: str
    risk_notes: list[str]

    # Summary flags
    market_dominance_stable: bool
    split_instability_detected: bool
    sp_fip_independent_signal: bool
    overfit_risk_detected: bool
    model_compressed: bool
    worth_phase72: bool


# ═══════════════════════════════════════════════════════════════════
# CORE MATH
# ═══════════════════════════════════════════════════════════════════

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
    if not vals:
        return 0.0
    sv = sorted(vals)
    n = len(sv)
    idx = (q / 100.0) * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sv[lo] * (1.0 - frac) + sv[hi] * frac


def _pearson_corr(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation coefficient. Returns 0.0 if <2 pairs or zero variance."""
    n = len(xs)
    if n < 2 or len(ys) != n:
        return 0.0
    mx, my = _mean(xs), _mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x < 1e-12 or den_y < 1e-12:
        return 0.0
    return round(num / (den_x * den_y), 6)


def _spearman_corr(xs: list[float], ys: list[float]) -> float:
    """Spearman rank correlation. Returns 0.0 if <2 pairs."""
    n = len(xs)
    if n < 2 or len(ys) != n:
        return 0.0
    def _ranks(vals: list[float]) -> list[float]:
        indexed = sorted(enumerate(vals), key=lambda x: x[1])
        ranks = [0.0] * n
        for rank, (i, _) in enumerate(indexed):
            ranks[i] = float(rank + 1)
        return ranks
    rx = _ranks(xs)
    ry = _ranks(ys)
    return _pearson_corr(rx, ry)


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    return bool(val) if val is not None else False


# ═══════════════════════════════════════════════════════════════════
# ROW ENRICHMENT
# ═══════════════════════════════════════════════════════════════════

def _enrich(rows: list[dict]) -> list[dict]:
    """Add derived Phase 71 analysis fields in-place.

    Prefixed keys added:
      _model_home_prob        copy of model_home_prob
      _market_home_prob       copy of market_home_prob_no_vig
      _home_win               float copy of home_win
      _model_residual         model_home_prob - home_win
      _market_residual        market_home_prob_no_vig - home_win
      _model_minus_market     model_home_prob - market_home_prob_no_vig
      _month_bucket           YYYY-MM
      _game_day_odd           1 if day-of-month is odd, else 0
      _sp_fip_delta           from p0_features (None if unavailable)
      _sp_fip_available       bool
      _park_run_factor        from p0_features
      _park_factor_available  bool
      _season_game_index      from p0_features
      _season_game_index_available bool
      _bullpen_fatigue_delta  from bullpen_features
      _home_bullpen_fatigue   from bullpen_features
      _away_bullpen_fatigue   from bullpen_features
      _bullpen_available      bool
      _sp_home_pitcher        from p0_features
      _sp_away_pitcher        from p0_features
    """
    for r in rows:
        mhp = float(r["model_home_prob"])
        mktp = float(r["market_home_prob_no_vig"])
        hw = float(r["home_win"])

        r["_model_home_prob"] = mhp
        r["_market_home_prob"] = mktp
        r["_home_win"] = hw
        r["_model_residual"] = mhp - hw
        r["_market_residual"] = mktp - hw
        r["_model_minus_market"] = mhp - mktp

        gd = str(r.get("game_date", ""))
        r["_month_bucket"] = gd[:7] if len(gd) >= 7 else "unknown"
        try:
            day_num = int(gd[8:10]) if len(gd) >= 10 else 0
        except ValueError:
            day_num = 0
        r["_game_day_odd"] = day_num % 2

        p0 = r.get("p0_features") or {}
        r["_sp_fip_delta"] = p0.get("sp_fip_delta")
        r["_sp_fip_available"] = _safe_bool(p0.get("sp_fip_delta_available", False))
        r["_park_run_factor"] = p0.get("park_run_factor")
        r["_park_factor_available"] = _safe_bool(p0.get("park_factor_available", False))
        r["_season_game_index"] = p0.get("season_game_index")
        r["_season_game_index_available"] = _safe_bool(
            p0.get("season_game_index_available", False)
        )
        r["_sp_home_pitcher"] = p0.get("sp_home_pitcher")
        r["_sp_away_pitcher"] = p0.get("sp_away_pitcher")

        bp = r.get("bullpen_features") or {}
        r["_bullpen_fatigue_delta"] = bp.get("bullpen_fatigue_delta_3d")
        r["_home_bullpen_fatigue"] = bp.get("home_bullpen_fatigue_3d")
        r["_away_bullpen_fatigue"] = bp.get("away_bullpen_fatigue_3d")
        r["_bullpen_available"] = _safe_bool(bp.get("bullpen_feature_available", False))

    return rows


# ═══════════════════════════════════════════════════════════════════
# SEGMENT FILTERING
# ═══════════════════════════════════════════════════════════════════

def _filter_segment(
    rows: list[dict],
    lo: float,
    hi: float,
    extra_filter: str | None,
) -> list[dict]:
    """Return rows where model_home_prob in [lo, hi) with optional extra filter."""
    out = [r for r in rows if lo <= r["_model_home_prob"] < hi]
    if extra_filter == "home_win_0":
        out = [r for r in out if r["_home_win"] == 0.0]
    elif extra_filter == "home_win_1":
        out = [r for r in out if r["_home_win"] == 1.0]
    return out


# ═══════════════════════════════════════════════════════════════════
# DIMENSION A: SEGMENT METRICS (market + model side-by-side)
# ═══════════════════════════════════════════════════════════════════

def _compute_segment_metrics(
    rows: list[dict],
    seg_name: str,
    lo: float,
    hi: float,
    extra_filter: str | None,
) -> SegmentMetrics:
    seg = _filter_segment(rows, lo, hi, extra_filter)
    n = len(seg)
    dl = n < _MIN_SEGMENT_N

    if n == 0:
        return SegmentMetrics(
            segment=seg_name, n=0,
            model_brier=0.0, model_ece=0.0,
            model_residual_mean=0.0, model_residual_std=0.0,
            observed_win_rate=0.0, model_mean_prob=0.0,
            market_brier=0.0, market_ece=0.0,
            market_residual_mean=0.0, market_mean_prob=0.0,
            brier_delta=0.0, model_minus_market_mean=0.0,
            bss_vs_market=0.0, market_superiority=False, data_limited=True,
        )

    model_probs = [r["_model_home_prob"] for r in seg]
    market_probs = [r["_market_home_prob"] for r in seg]
    outcomes = [r["_home_win"] for r in seg]
    model_residuals = [r["_model_residual"] for r in seg]
    market_residuals = [r["_market_residual"] for r in seg]
    mmm = [r["_model_minus_market"] for r in seg]

    mb = _brier(model_probs, outcomes)
    mkb = _brier(market_probs, outcomes)
    bd = round(mb - mkb, 6)
    bss = _bss_direct(mb, mkb)

    return SegmentMetrics(
        segment=seg_name,
        n=n,
        model_brier=round(mb, 6),
        model_ece=round(_ece(model_probs, outcomes), 6),
        model_residual_mean=round(_mean(model_residuals), 6),
        model_residual_std=round(_std(model_residuals), 6),
        observed_win_rate=round(_mean(outcomes), 6),
        model_mean_prob=round(_mean(model_probs), 6),
        market_brier=round(mkb, 6),
        market_ece=round(_ece(market_probs, outcomes), 6),
        market_residual_mean=round(_mean(market_residuals), 6),
        market_mean_prob=round(_mean(market_probs), 6),
        brier_delta=bd,
        model_minus_market_mean=round(_mean(mmm), 6),
        bss_vs_market=round(bss, 6),
        market_superiority=(bd >= _MARKET_SUPERIORITY_BRIER_GAP and not dl),
        data_limited=dl,
    )


def _compute_all_segment_metrics(rows: list[dict]) -> list[SegmentMetrics]:
    return [
        _compute_segment_metrics(rows, name, lo, hi, filt)
        for name, lo, hi, filt in _SEGMENT_DEFS
    ]


# ═══════════════════════════════════════════════════════════════════
# DIMENSION B: DISTRIBUTION SHAPE
# ═══════════════════════════════════════════════════════════════════

def _compute_distribution_shape(
    rows: list[dict],
    seg_name: str,
    lo: float,
    hi: float,
    extra_filter: str | None = None,
) -> DistributionShapeResult:
    """Compare model vs market probability distribution shape in a segment."""
    seg = _filter_segment(rows, lo, hi, extra_filter)
    n = len(seg)
    dl = n < _MIN_SEGMENT_N

    if n == 0:
        return DistributionShapeResult(
            segment=seg_name, n=0,
            model_std=0.0, model_min=0.0, model_max=0.0,
            model_q25=0.0, model_q75=0.0, model_iqr=0.0,
            market_std=0.0, market_min=0.0, market_max=0.0,
            market_q25=0.0, market_q75=0.0, market_iqr=0.0,
            compression_ratio=1.0, rank_correlation=0.0,
            mean_disagreement=0.0, n_disagreement_rows=0, disagreement_rate=0.0,
            model_compressed=False, data_limited=True,
        )

    mp = [r["_model_home_prob"] for r in seg]
    mkp = [r["_market_home_prob"] for r in seg]
    diffs = [abs(r["_model_minus_market"]) for r in seg]

    m_std = _std(mp)
    mk_std = _std(mkp)
    compression = round(m_std / mk_std, 6) if mk_std > 1e-9 else 1.0
    rank_corr = _spearman_corr(mp, mkp)

    n_disagree = sum(1 for d in diffs if d >= _DISAGREEMENT_GAP)

    return DistributionShapeResult(
        segment=seg_name,
        n=n,
        model_std=round(m_std, 6),
        model_min=round(min(mp), 6),
        model_max=round(max(mp), 6),
        model_q25=round(_percentile(mp, 25), 6),
        model_q75=round(_percentile(mp, 75), 6),
        model_iqr=round(_percentile(mp, 75) - _percentile(mp, 25), 6),
        market_std=round(mk_std, 6),
        market_min=round(min(mkp), 6),
        market_max=round(max(mkp), 6),
        market_q25=round(_percentile(mkp, 25), 6),
        market_q75=round(_percentile(mkp, 75), 6),
        market_iqr=round(_percentile(mkp, 75) - _percentile(mkp, 25), 6),
        compression_ratio=compression,
        rank_correlation=round(rank_corr, 6),
        mean_disagreement=round(_mean(diffs), 6),
        n_disagreement_rows=n_disagree,
        disagreement_rate=round(n_disagree / n, 4) if n > 0 else 0.0,
        model_compressed=(compression <= _DISTRIBUTION_COMPRESSION_RATIO),
        data_limited=dl,
    )


def _compute_all_distribution_shapes(rows: list[dict]) -> list[DistributionShapeResult]:
    """Distribution shape for key segments."""
    targets = [
        ("all_games",             0.00, 1.01, None),
        ("home_favorite_only",    0.50, 1.01, None),
        ("model_prob_0.60_0.65",  0.60, 0.65, None),
        ("model_prob_0.65_0.70",  0.65, 0.70, None),
        ("model_prob_0.70_0.75",  0.70, 0.75, None),
        ("heavy_favorite",        0.70, 1.01, None),
    ]
    return [_compute_distribution_shape(rows, name, lo, hi, filt)
            for name, lo, hi, filt in targets]


# ═══════════════════════════════════════════════════════════════════
# DIMENSION C: sp_fip_delta × market signal
# ═══════════════════════════════════════════════════════════════════

def _compute_sp_fip_attribution(rows: list[dict]) -> SpFipAttributionResult | None:
    """Analyse sp_fip_delta relationship with market signal in target band.

    Returns None only if no rows exist at all.
    """
    target = _filter_segment(rows, _TARGET_BAND_LO, _TARGET_BAND_HI, None)
    n_total_target = len(target)

    # All available rows
    target_avail = [r for r in target if r.get("_sp_fip_available", False)]
    all_avail = [r for r in rows if r.get("_sp_fip_available", False)]
    n_ta = len(target_avail)
    n_aa = len(all_avail)

    dl = n_ta < _MIN_BUCKET_N

    # Availability rates
    avail_rate_target = round(n_ta / n_total_target, 4) if n_total_target > 0 else 0.0
    avail_rate_all = round(n_aa / len(rows), 4) if rows else 0.0

    # Mean / std sp_fip_delta
    def _fip_vals(rlist: list[dict]) -> list[float]:
        out = []
        for r in rlist:
            v = r.get("_sp_fip_delta")
            if v is not None:
                try:
                    out.append(float(v))
                except (ValueError, TypeError):
                    pass
        return out

    fips_target = _fip_vals(target_avail)
    fips_all = _fip_vals(all_avail)

    mean_fip_target = round(_mean(fips_target), 6) if fips_target else None
    mean_fip_all = round(_mean(fips_all), 6) if fips_all else None
    std_fip_target = round(_std(fips_target), 6) if len(fips_target) >= 2 else None
    std_fip_all = round(_std(fips_all), 6) if len(fips_all) >= 2 else None

    # Correlations (only where both fields exist in target band)
    sp_vs_mmm = 0.0
    sp_vs_mkt = 0.0
    sp_vs_res = 0.0
    if not dl and fips_target:
        mmm_vals = [r["_model_minus_market"] for r in target_avail]
        mkt_vals = [r["_market_home_prob"] for r in target_avail]
        res_vals = [r["_model_residual"] for r in target_avail]
        sp_vs_mmm = _pearson_corr(fips_target, mmm_vals)
        sp_vs_mkt = _pearson_corr(fips_target, mkt_vals)
        sp_vs_res = _pearson_corr(fips_target, res_vals)

    # Bucket analysis: high vs low sp_fip_delta within target band
    n_high = 0
    n_low = 0
    mb_high = 0.0
    mb_low = 0.0
    mkb_high = 0.0
    mkb_low = 0.0
    rm_high = 0.0
    rm_low = 0.0
    res_bucket_gap = 0.0
    sp_absorbed = False
    sp_independent = False

    if not dl and fips_target:
        median_fip = _percentile(fips_target, 50)
        high_rows = [r for r, f in zip(target_avail, fips_target) if f > median_fip]
        low_rows = [r for r, f in zip(target_avail, fips_target) if f <= median_fip]
        n_high = len(high_rows)
        n_low = len(low_rows)

        if n_high >= 3 and n_low >= 3:
            h_mp = [r["_model_home_prob"] for r in high_rows]
            h_mkp = [r["_market_home_prob"] for r in high_rows]
            h_oc = [r["_home_win"] for r in high_rows]
            h_res = [r["_model_residual"] for r in high_rows]

            l_mp = [r["_model_home_prob"] for r in low_rows]
            l_mkp = [r["_market_home_prob"] for r in low_rows]
            l_oc = [r["_home_win"] for r in low_rows]
            l_res = [r["_model_residual"] for r in low_rows]

            mb_high = round(_brier(h_mp, h_oc), 6)
            mb_low = round(_brier(l_mp, l_oc), 6)
            mkb_high = round(_brier(h_mkp, h_oc), 6)
            mkb_low = round(_brier(l_mkp, l_oc), 6)
            rm_high = round(_mean(h_res), 6)
            rm_low = round(_mean(l_res), 6)
            res_bucket_gap = round(rm_high - rm_low, 6)

            # sp_fip absorbed: |sp_vs_mkt| > |sp_vs_res| (market tracks sp_fip more)
            sp_absorbed = abs(sp_vs_mkt) > abs(sp_vs_res) + 0.05

            # sp independent: residual bucket gap is large
            sp_independent = abs(res_bucket_gap) >= _SP_FIP_RESIDUAL_BUCKET_GAP

    return SpFipAttributionResult(
        n_target_available=n_ta,
        n_target_total=n_total_target,
        n_all_available=n_aa,
        n_all_total=len(rows),
        availability_rate_target=avail_rate_target,
        availability_rate_all=avail_rate_all,
        mean_sp_fip_target=mean_fip_target,
        mean_sp_fip_all=mean_fip_all,
        std_sp_fip_target=std_fip_target,
        std_sp_fip_all=std_fip_all,
        sp_fip_vs_model_minus_market_corr=sp_vs_mmm,
        sp_fip_vs_market_prob_corr=sp_vs_mkt,
        sp_fip_vs_outcome_residual_corr=sp_vs_res,
        n_sp_fip_high_bucket=n_high,
        n_sp_fip_low_bucket=n_low,
        model_brier_sp_fip_high=mb_high,
        model_brier_sp_fip_low=mb_low,
        market_brier_sp_fip_high=mkb_high,
        market_brier_sp_fip_low=mkb_low,
        residual_mean_sp_fip_high=rm_high,
        residual_mean_sp_fip_low=rm_low,
        residual_bucket_gap=res_bucket_gap,
        sp_fip_absorbed_by_market=sp_absorbed,
        sp_fip_independent_signal=sp_independent,
        data_limited=dl,
    )


# ═══════════════════════════════════════════════════════════════════
# DIMENSION D: SPLIT / DATE / SAMPLE CONCENTRATION (market comparison)
# ═══════════════════════════════════════════════════════════════════

def _compute_split_market_results(rows: list[dict]) -> list[SplitMarketResult]:
    """Per-split model vs market Brier comparison in the target band."""
    target = _filter_segment(rows, _TARGET_BAND_LO, _TARGET_BAND_HI, None)

    by_split: dict[str, list[dict]] = {}
    for r in target:
        sid = str(r.get("split_id", "unknown"))
        by_split.setdefault(sid, []).append(r)

    results: list[SplitMarketResult] = []
    for sid in sorted(by_split.keys()):
        grp = by_split[sid]
        n = len(grp)
        dl = n < _MIN_BUCKET_N
        mp = [r["_model_home_prob"] for r in grp]
        mkp = [r["_market_home_prob"] for r in grp]
        oc = [r["_home_win"] for r in grp]
        mr = [r["_model_residual"] for r in grp]
        mkr = [r["_market_residual"] for r in grp]

        mb = round(_brier(mp, oc), 6) if not dl else 0.0
        mkb = round(_brier(mkp, oc), 6) if not dl else 0.0
        bd = round(mb - mkb, 6) if not dl else 0.0

        results.append(SplitMarketResult(
            split_id=sid,
            n=n,
            model_brier=mb,
            market_brier=mkb,
            brier_delta=bd,
            model_residual_mean=round(_mean(mr), 6),
            market_residual_mean=round(_mean(mkr), 6),
            observed_win_rate=round(_mean(oc), 6),
            model_mean_prob=round(_mean(mp), 6),
            market_mean_prob=round(_mean(mkp), 6),
            market_superior=(bd >= _MARKET_SUPERIORITY_BRIER_GAP and not dl),
            data_limited=dl,
        ))
    return results


# ═══════════════════════════════════════════════════════════════════
# DIMENSION E: TEAM CONCENTRATION + FEATURE AVAILABILITY MATRIX
# ═══════════════════════════════════════════════════════════════════

def _compute_team_concentration(
    rows: list[dict],
    top_n: int = 10,
) -> list[TeamConcentrationResult]:
    """Team concentration analysis in the target band."""
    target = _filter_segment(rows, _TARGET_BAND_LO, _TARGET_BAND_HI, None)
    n_total = len(target)
    if n_total == 0:
        return []

    home_counts: dict[str, list[dict]] = {}
    for r in target:
        ht = str(r.get("home_team", "unknown"))
        home_counts.setdefault(ht, []).append(r)

    sorted_teams = sorted(home_counts.items(), key=lambda x: len(x[1]), reverse=True)
    results: list[TeamConcentrationResult] = []
    for team, grp in sorted_teams[:top_n]:
        n = len(grp)
        if n < 2:
            continue
        dl = n < _MIN_BUCKET_N
        mp = [r["_model_home_prob"] for r in grp]
        mkp = [r["_market_home_prob"] for r in grp]
        oc = [r["_home_win"] for r in grp]
        res = [r["_model_residual"] for r in grp]

        mb = round(_brier(mp, oc), 6) if not dl else 0.0
        mkb = round(_brier(mkp, oc), 6) if not dl else 0.0

        results.append(TeamConcentrationResult(
            team=team,
            n_in_target_band=n,
            share_of_target_band=round(n / n_total, 4),
            model_brier=mb,
            market_brier=mkb,
            brier_delta=round(mb - mkb, 6) if not dl else 0.0,
            model_residual_mean=round(_mean(res), 6),
            observed_win_rate=round(_mean(oc), 6),
            model_mean_prob=round(_mean(mp), 6),
            market_mean_prob=round(_mean(mkp), 6),
            data_limited=dl,
        ))
    return results


_FEATURE_PROBES: list[tuple[str, str, str]] = [
    ("sp_fip_delta",             "p0_features",      "_sp_fip_available"),
    ("park_run_factor",          "p0_features",      "_park_factor_available"),
    ("season_game_index",        "p0_features",      "_season_game_index_available"),
    ("bullpen_fatigue_delta_3d", "bullpen_features",  "_bullpen_available"),
    ("home_bullpen_fatigue_3d",  "bullpen_features",  "_bullpen_available"),
    ("away_bullpen_fatigue_3d",  "bullpen_features",  "_bullpen_available"),
]

_FEATURE_VALUE_KEYS: dict[str, str] = {
    "sp_fip_delta":             "_sp_fip_delta",
    "park_run_factor":          "_park_run_factor",
    "season_game_index":        "_season_game_index",
    "bullpen_fatigue_delta_3d": "_bullpen_fatigue_delta",
    "home_bullpen_fatigue_3d":  "_home_bullpen_fatigue",
    "away_bullpen_fatigue_3d":  "_away_bullpen_fatigue",
}


def _compute_feature_availability(rows: list[dict]) -> list[FeatureAvailabilityRow]:
    """Feature availability matrix for target band vs all."""
    target = _filter_segment(rows, _TARGET_BAND_LO, _TARGET_BAND_HI, None)
    results: list[FeatureAvailabilityRow] = []

    for feat_name, source_dict, avail_key in _FEATURE_PROBES:
        val_key = _FEATURE_VALUE_KEYS.get(feat_name, f"_{feat_name}")

        def _avail(r: dict) -> bool:
            v = r.get(avail_key)
            return bool(v) if v is not None else False

        def _val(r: dict) -> float | None:
            v = r.get(val_key)
            if v is None:
                return None
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        ta = [r for r in target if _avail(r)]
        aa = [r for r in rows if _avail(r)]
        n_ta, n_tt = len(ta), len(target)
        n_aa, n_at = len(aa), len(rows)

        vals_t = [_val(r) for r in ta]
        vals_t_f = [v for v in vals_t if v is not None]
        vals_a = [_val(r) for r in aa]
        vals_a_f = [v for v in vals_a if v is not None]

        mv_t = round(_mean(vals_t_f), 6) if vals_t_f else None
        mv_a = round(_mean(vals_a_f), 6) if vals_a_f else None
        ext_delta = round((mv_t - mv_a), 6) if (mv_t is not None and mv_a is not None) else 0.0

        results.append(FeatureAvailabilityRow(
            feature_name=feat_name,
            source_dict=source_dict,
            n_available_target=n_ta,
            n_available_all=n_aa,
            availability_rate_target=round(n_ta / n_tt, 4) if n_tt > 0 else 0.0,
            availability_rate_all=round(n_aa / n_at, 4) if n_at > 0 else 0.0,
            mean_value_target=mv_t,
            mean_value_all=mv_a,
            extreme_delta=ext_delta,
            data_limited=(n_ta < _MIN_BUCKET_N),
        ))
    return results


# ═══════════════════════════════════════════════════════════════════
# BOOTSTRAP CI
# ═══════════════════════════════════════════════════════════════════

def _bootstrap_ci(
    rows: list[dict],
    lo: float,
    hi: float,
    seg_name: str,
    metric: str,
    n_boot: int,
    rng: random.Random,
) -> BootstrapCI:
    """Bootstrap CI for a metric in segment [lo, hi).

    metric options:
      'residual_mean'          — model residual mean
      'brier_delta_vs_market'  — model_brier - market_brier
      'market_residual_mean'   — market residual mean
      'sp_fip_residual_bucket_gap' — uses all rows with _sp_fip_available in [lo,hi)
    """
    seg = _filter_segment(rows, lo, hi, None)
    n = len(seg)
    dl = n < _MIN_SEGMENT_N

    if n < 2:
        return BootstrapCI(
            metric=metric, segment=seg_name, n=n, n_boot=n_boot,
            observed=0.0, ci_lower=0.0, ci_upper=0.0,
            ci_excludes_zero=False, ci_stable=False, data_limited=True,
        )

    def _compute(sample: list[dict]) -> float:
        if metric == "residual_mean":
            return _mean([r["_model_residual"] for r in sample])
        elif metric == "brier_delta_vs_market":
            mp = [r["_model_home_prob"] for r in sample]
            mkp = [r["_market_home_prob"] for r in sample]
            oc = [r["_home_win"] for r in sample]
            return _brier(mp, oc) - _brier(mkp, oc)
        elif metric == "market_residual_mean":
            return _mean([r["_market_residual"] for r in sample])
        else:  # sp_fip_residual_bucket_gap
            avail = [r for r in sample if r.get("_sp_fip_available", False)]
            if len(avail) < 4:
                return 0.0
            fips = []
            for r in avail:
                v = r.get("_sp_fip_delta")
                try:
                    fips.append(float(v))
                except (ValueError, TypeError):
                    fips.append(0.0)
            med = _percentile(fips, 50)
            high_res = [r["_model_residual"] for r, f in zip(avail, fips) if f > med]
            low_res = [r["_model_residual"] for r, f in zip(avail, fips) if f <= med]
            return _mean(high_res) - _mean(low_res) if (high_res and low_res) else 0.0

    observed = round(_compute(seg), 6)
    boot_stats = [_compute(rng.choices(seg, k=n)) for _ in range(n_boot)]
    ci_lo = round(_percentile(boot_stats, 2.5), 6)
    ci_hi = round(_percentile(boot_stats, 97.5), 6)
    ci_width = ci_hi - ci_lo

    return BootstrapCI(
        metric=metric,
        segment=seg_name,
        n=n,
        n_boot=n_boot,
        observed=observed,
        ci_lower=ci_lo,
        ci_upper=ci_hi,
        ci_excludes_zero=(ci_hi < 0.0 or ci_lo > 0.0),
        ci_stable=(ci_width < _CI_STABLE_WIDTH),
        data_limited=dl,
    )


def _compute_bootstrap_cis(
    rows: list[dict], n_boot: int, rng: random.Random
) -> list[BootstrapCI]:
    """Compute bootstrap CIs for key metrics."""
    targets = [
        (_TARGET_BAND_LO, _TARGET_BAND_HI, "model_prob_0.65_0.70", "brier_delta_vs_market"),
        (_TARGET_BAND_LO, _TARGET_BAND_HI, "model_prob_0.65_0.70", "residual_mean"),
        (_TARGET_BAND_LO, _TARGET_BAND_HI, "model_prob_0.65_0.70", "market_residual_mean"),
        (0.70, 1.01,  "heavy_favorite",      "brier_delta_vs_market"),
        (0.00, 1.01,  "all_games",            "brier_delta_vs_market"),
        (_TARGET_BAND_LO, _TARGET_BAND_HI, "model_prob_0.65_0.70", "sp_fip_residual_bucket_gap"),
    ]
    return [
        _bootstrap_ci(rows, lo, hi, seg, met, n_boot, rng)
        for lo, hi, seg, met in targets
    ]


# ═══════════════════════════════════════════════════════════════════
# NEGATIVE CONTROLS (6)
# ═══════════════════════════════════════════════════════════════════

def _observed_market_brier_gap(rows: list[dict]) -> float:
    """Observed: target band (model_brier - market_brier)."""
    seg = _filter_segment(rows, _TARGET_BAND_LO, _TARGET_BAND_HI, None)
    if len(seg) < 2:
        return 0.0
    mp = [r["_model_home_prob"] for r in seg]
    mkp = [r["_market_home_prob"] for r in seg]
    oc = [r["_home_win"] for r in seg]
    return round(_brier(mp, oc) - _brier(mkp, oc), 6)


def _run_negative_controls(
    rows: list[dict], n_permutations: int, rng: random.Random
) -> list[NegativeControlResult]:
    results: list[NegativeControlResult] = []

    observed_gap = _observed_market_brier_gap(rows)
    seg_target = _filter_segment(rows, _TARGET_BAND_LO, _TARGET_BAND_HI, None)
    n_seg = len(seg_target)

    model_probs_all = [r["_model_home_prob"] for r in rows]
    market_probs_all = [r["_market_home_prob"] for r in rows]
    outcomes_all = [r["_home_win"] for r in rows]

    # ── NC1: shuffled_market_assignment ───────────────────────────
    # Shuffle market_home_prob across all rows; recompute target band Brier delta
    null1: list[float] = []
    for _ in range(n_permutations):
        shuffled_mkt = market_probs_all[:]
        rng.shuffle(shuffled_mkt)
        # Recompute Brier delta in target band with shuffled market
        seg_mp = [model_probs_all[i] for i, r in enumerate(rows)
                  if _TARGET_BAND_LO <= r["_model_home_prob"] < _TARGET_BAND_HI]
        seg_mkp = [shuffled_mkt[i] for i, r in enumerate(rows)
                   if _TARGET_BAND_LO <= r["_model_home_prob"] < _TARGET_BAND_HI]
        seg_oc = [outcomes_all[i] for i, r in enumerate(rows)
                  if _TARGET_BAND_LO <= r["_model_home_prob"] < _TARGET_BAND_HI]
        if seg_mp:
            null1.append(_brier(seg_mp, seg_oc) - _brier(seg_mkp, seg_oc))
        else:
            null1.append(0.0)

    n1_mean = _mean(null1)
    n1_std = _std(null1)
    sig1 = observed_gap - n1_mean
    results.append(NegativeControlResult(
        control_name="shuffled_market_assignment",
        description=(
            "Shuffle market_home_prob across all rows; recompute target-band Brier delta. "
            "Real market dominance signal should be distinct from random market assignment."
        ),
        n_permutations=n_permutations,
        observed_gap=round(observed_gap, 6),
        permuted_gap_mean=round(n1_mean, 6),
        permuted_gap_std=round(n1_std, 6),
        signal_gap=round(sig1, 6),
        overfit_risk=abs(sig1) < _NC_SIGNAL_THRESHOLD,
        interpretation=(
            "SIGNAL: market probability assignment is meaningfully structured."
            if abs(sig1) >= _NC_SIGNAL_THRESHOLD
            else "NO SIGNAL: market dominance gap not distinguishable from random market assignment."
        ),
    ))

    # ── NC2: shuffled_model_assignment ────────────────────────────
    # Shuffle model_home_prob; recompute target band Brier delta
    null2: list[float] = []
    for _ in range(n_permutations):
        shuffled_mod = model_probs_all[:]
        rng.shuffle(shuffled_mod)
        seg_mp2 = [shuffled_mod[i] for i, r in enumerate(rows)
                   if _TARGET_BAND_LO <= r["_model_home_prob"] < _TARGET_BAND_HI]
        seg_mkp2 = [market_probs_all[i] for i, r in enumerate(rows)
                    if _TARGET_BAND_LO <= r["_model_home_prob"] < _TARGET_BAND_HI]
        seg_oc2 = [outcomes_all[i] for i, r in enumerate(rows)
                   if _TARGET_BAND_LO <= r["_model_home_prob"] < _TARGET_BAND_HI]
        if seg_mp2:
            null2.append(_brier(seg_mp2, seg_oc2) - _brier(seg_mkp2, seg_oc2))
        else:
            null2.append(0.0)

    n2_mean = _mean(null2)
    n2_std = _std(null2)
    sig2 = observed_gap - n2_mean
    results.append(NegativeControlResult(
        control_name="shuffled_model_assignment",
        description=(
            "Shuffle model_home_prob across all rows; recompute target-band Brier delta. "
            "Should collapse the observed gap if model's band selection matters."
        ),
        n_permutations=n_permutations,
        observed_gap=round(observed_gap, 6),
        permuted_gap_mean=round(n2_mean, 6),
        permuted_gap_std=round(n2_std, 6),
        signal_gap=round(sig2, 6),
        overfit_risk=abs(sig2) < _NC_SIGNAL_THRESHOLD,
        interpretation=(
            "SIGNAL: model band selection is structurally meaningful."
            if abs(sig2) >= _NC_SIGNAL_THRESHOLD
            else "NO SIGNAL: Brier delta not distinguishable from random model assignment."
        ),
    ))

    # ── NC3: random_model_minus_market ────────────────────────────
    # Shuffle the model-minus-market differences; recompute mean |diff| in target band
    mmm_all = [r["_model_minus_market"] for r in rows]
    obs_mmm_mean = abs(_mean([r["_model_minus_market"] for r in seg_target]))

    null3: list[float] = []
    for _ in range(n_permutations):
        shuffled_mmm = mmm_all[:]
        rng.shuffle(shuffled_mmm)
        seg_mmm = [shuffled_mmm[i] for i, r in enumerate(rows)
                   if _TARGET_BAND_LO <= r["_model_home_prob"] < _TARGET_BAND_HI]
        null3.append(abs(_mean(seg_mmm)) if seg_mmm else 0.0)

    n3_mean = _mean(null3)
    n3_std = _std(null3)
    sig3 = obs_mmm_mean - n3_mean
    results.append(NegativeControlResult(
        control_name="random_model_minus_market",
        description=(
            "Shuffle model-minus-market differences; check if target-band mean disagreement "
            "is structurally distinct from random assignment of disagreements."
        ),
        n_permutations=n_permutations,
        observed_gap=round(obs_mmm_mean, 6),
        permuted_gap_mean=round(n3_mean, 6),
        permuted_gap_std=round(n3_std, 6),
        signal_gap=round(sig3, 6),
        overfit_risk=abs(sig3) < _NC_SIGNAL_THRESHOLD,
        interpretation=(
            "SIGNAL: model-market disagreement is band-specific, not random."
            if abs(sig3) >= _NC_SIGNAL_THRESHOLD
            else "NO SIGNAL: model-market disagreement not distinguishable from random."
        ),
    ))

    # ── NC4: random_sp_fip_bucket ─────────────────────────────────
    # Randomly reassign sp_fip high/low labels; compare resulting Brier gap
    sp_avail = [r for r in seg_target if r.get("_sp_fip_available", False)]
    if len(sp_avail) >= 4:
        fips = []
        for r in sp_avail:
            v = r.get("_sp_fip_delta")
            try:
                fips.append(float(v))
            except (ValueError, TypeError):
                fips.append(0.0)
        med_fip = _percentile(fips, 50)
        high_r = [r for r, f in zip(sp_avail, fips) if f > med_fip]
        low_r = [r for r, f in zip(sp_avail, fips) if f <= med_fip]
        obs_sp_gap = 0.0
        if high_r and low_r:
            obs_sp_gap = abs(
                _mean([r["_model_residual"] for r in high_r])
                - _mean([r["_model_residual"] for r in low_r])
            )
    else:
        obs_sp_gap = 0.0
        sp_avail = []

    null4: list[float] = []
    for _ in range(n_permutations):
        if len(sp_avail) >= 4:
            perm = sp_avail[:]
            rng.shuffle(perm)
            half = len(perm) // 2
            pa = perm[:half]
            pb = perm[half:]
            ra = [r["_model_residual"] for r in pa]
            rb = [r["_model_residual"] for r in pb]
            null4.append(abs(_mean(ra) - _mean(rb)) if (ra and rb) else 0.0)
        else:
            null4.append(0.0)

    n4_mean = _mean(null4)
    n4_std = _std(null4)
    sig4 = obs_sp_gap - n4_mean
    results.append(NegativeControlResult(
        control_name="random_sp_fip_bucket",
        description=(
            "Randomly reassign sp_fip high/low bucket labels; compare residual gap. "
            "Real sp_fip signal should produce larger gap than random bucket assignment."
        ),
        n_permutations=n_permutations,
        observed_gap=round(obs_sp_gap, 6),
        permuted_gap_mean=round(n4_mean, 6),
        permuted_gap_std=round(n4_std, 6),
        signal_gap=round(sig4, 6),
        overfit_risk=(len(sp_avail) < 4) or (abs(sig4) < _NC_SIGNAL_THRESHOLD),
        interpretation=(
            "SIGNAL: sp_fip bucket is meaningfully associated with residual."
            if (len(sp_avail) >= 4 and abs(sig4) >= _NC_SIGNAL_THRESHOLD)
            else (
                "DATA_LIMITED: insufficient sp_fip available rows for bucket analysis."
                if len(sp_avail) < 4
                else "NO SIGNAL: sp_fip bucket gap not distinguishable from random."
            )
        ),
    ))

    # ── NC5: random_split_assignment ──────────────────────────────
    # Shuffle split_id labels in target band; check if Brier delta consistency holds
    split_ids_target = [r.get("split_id", "unknown") for r in seg_target]
    if seg_target:
        # Observed: std of per-split Brier deltas
        by_split: dict[str, list[dict]] = {}
        for r in seg_target:
            sid = str(r.get("split_id", "unknown"))
            by_split.setdefault(sid, []).append(r)
        obs_split_bds: list[float] = []
        for grp in by_split.values():
            if len(grp) >= _MIN_BUCKET_N:
                mp_g = [r["_model_home_prob"] for r in grp]
                mkp_g = [r["_market_home_prob"] for r in grp]
                oc_g = [r["_home_win"] for r in grp]
                obs_split_bds.append(_brier(mp_g, oc_g) - _brier(mkp_g, oc_g))
        obs_split_std = _std(obs_split_bds) if len(obs_split_bds) >= 2 else 0.0
    else:
        obs_split_std = 0.0

    null5: list[float] = []
    for _ in range(n_permutations):
        if seg_target:
            shuffled_sids = split_ids_target[:]
            rng.shuffle(shuffled_sids)
            by_split_r: dict[str, list[dict]] = {}
            for r, sid in zip(seg_target, shuffled_sids):
                by_split_r.setdefault(str(sid), []).append(r)
            bds: list[float] = []
            for grp in by_split_r.values():
                if len(grp) >= _MIN_BUCKET_N:
                    mp_g = [r["_model_home_prob"] for r in grp]
                    mkp_g = [r["_market_home_prob"] for r in grp]
                    oc_g = [r["_home_win"] for r in grp]
                    bds.append(_brier(mp_g, oc_g) - _brier(mkp_g, oc_g))
            null5.append(_std(bds) if len(bds) >= 2 else 0.0)
        else:
            null5.append(0.0)

    n5_mean = _mean(null5)
    n5_std = _std(null5)
    sig5 = obs_split_std - n5_mean
    results.append(NegativeControlResult(
        control_name="random_split_assignment",
        description=(
            "Shuffle split_id labels in target band; check Brier delta std across splits. "
            "High std in observed vs random suggests real instability."
        ),
        n_permutations=n_permutations,
        observed_gap=round(obs_split_std, 6),
        permuted_gap_mean=round(n5_mean, 6),
        permuted_gap_std=round(n5_std, 6),
        signal_gap=round(sig5, 6),
        overfit_risk=abs(sig5) < _NC_SIGNAL_THRESHOLD,
        interpretation=(
            "SIGNAL: split-level Brier delta variation is real, not random."
            if abs(sig5) >= _NC_SIGNAL_THRESHOLD
            else "NO SIGNAL: Brier delta std across splits not distinguishable from random splits."
        ),
    ))

    # ── NC6: irrelevant_date_bucket_split ─────────────────────────
    # Odd vs even day-of-month Brier delta gap (should be near zero)
    odd_seg = [r for r in seg_target if r.get("_game_day_odd", 0) == 1]
    even_seg = [r for r in seg_target if r.get("_game_day_odd", 0) == 0]

    def _brier_delta(rlist: list[dict]) -> float:
        if len(rlist) < 2:
            return 0.0
        mp = [r["_model_home_prob"] for r in rlist]
        mkp = [r["_market_home_prob"] for r in rlist]
        oc = [r["_home_win"] for r in rlist]
        return _brier(mp, oc) - _brier(mkp, oc)

    obs_date_gap = abs(_brier_delta(odd_seg) - _brier_delta(even_seg))

    null6: list[float] = []
    seg_outcomes = [r["_home_win"] for r in seg_target]
    seg_model = [r["_model_home_prob"] for r in seg_target]
    seg_market = [r["_market_home_prob"] for r in seg_target]
    for _ in range(n_permutations):
        shuffled_oc = seg_outcomes[:]
        rng.shuffle(shuffled_oc)
        # Recompute with shuffled outcomes, same odd/even split
        odd_idx = [i for i, r in enumerate(seg_target) if r.get("_game_day_odd", 0) == 1]
        even_idx = [i for i, r in enumerate(seg_target) if r.get("_game_day_odd", 0) == 0]
        def _bd_idx(idx_list: list[int]) -> float:
            if len(idx_list) < 2:
                return 0.0
            return (_brier([seg_model[i] for i in idx_list], [shuffled_oc[i] for i in idx_list])
                    - _brier([seg_market[i] for i in idx_list], [shuffled_oc[i] for i in idx_list]))
        null6.append(abs(_bd_idx(odd_idx) - _bd_idx(even_idx)))

    n6_mean = _mean(null6)
    n6_std = _std(null6)
    sig6 = obs_date_gap - n6_mean
    # Inverted: large gap from irrelevant split IS the overfit signal
    results.append(NegativeControlResult(
        control_name="irrelevant_date_bucket_split",
        description=(
            "Split target-band by odd/even day-of-month; compute Brier delta difference. "
            "Should be near zero — large gap from irrelevant split suggests confounding."
        ),
        n_permutations=n_permutations,
        observed_gap=round(obs_date_gap, 6),
        permuted_gap_mean=round(n6_mean, 6),
        permuted_gap_std=round(n6_std, 6),
        signal_gap=round(sig6, 6),
        overfit_risk=abs(sig6) >= _NC_SIGNAL_THRESHOLD,  # INVERTED
        interpretation=(
            "NO SIGNAL: irrelevant date split does not produce spurious Brier delta gap."
            if abs(sig6) < _NC_SIGNAL_THRESHOLD
            else "WARNING: irrelevant date split produces Brier delta gap (possible confound)."
        ),
    ))

    return results


# ═══════════════════════════════════════════════════════════════════
# GATE DETERMINATION
# ═══════════════════════════════════════════════════════════════════

def _determine_gate(
    segment_metrics: list[SegmentMetrics],
    distribution_shape: list[DistributionShapeResult],
    sp_fip_attribution: SpFipAttributionResult | None,
    split_market_results: list[SplitMarketResult],
    negative_controls: list[NegativeControlResult],
    bootstrap_cis: list[BootstrapCI],
) -> tuple[str, str, str, list[str], bool]:
    """Returns (gate, rationale, phase72_rec, risk_notes, worth_phase72)."""

    risk_notes: list[str] = []

    seg_by_name: dict[str, SegmentMetrics] = {s.segment: s for s in segment_metrics}
    target_seg = seg_by_name.get("model_prob_0.65_0.70")
    n_target = target_seg.n if target_seg else 0

    # ── 1. MARKET_DOMINANCE_DATA_LIMITED ──────────────────────────
    if n_target < _MIN_SEGMENT_N:
        return (
            MARKET_DOMINANCE_DATA_LIMITED,
            f"Insufficient data in target band 0.65–0.70 (n={n_target} < {_MIN_SEGMENT_N}).",
            "停止 Phase72 patch path。回到本週 P1：LeagueAdapter / Budget Guard / Metrics SSOT / governance hardening。",
            risk_notes,
            False,
        )

    # ── 2. OVERFIT_RISK ────────────────────────────────────────────
    nc_overfit_count = sum(1 for nc in negative_controls if nc.overfit_risk)
    if nc_overfit_count >= _NC_OVERFIT_RISK_COUNT_THRESHOLD:
        risk_notes.append(
            f"⚠  {nc_overfit_count}/6 negative controls show overfit risk."
        )
        return (
            OVERFIT_RISK,
            (
                f"{nc_overfit_count}/6 negative controls show overfit risk. "
                "Market dominance signal may not be distinct from noise."
            ),
            "停止 Phase72 patch path。回到本週 P1：LeagueAdapter / Budget Guard / Metrics SSOT / governance hardening。",
            risk_notes,
            False,
        )

    # ── Collect flags ──────────────────────────────────────────────

    # Market superiority check in target band
    target_brier_delta = target_seg.brier_delta if target_seg else 0.0
    market_dominant = (
        target_seg is not None
        and not target_seg.data_limited
        and target_brier_delta >= _MARKET_SUPERIORITY_BRIER_GAP
    )

    # Bootstrap CI for Brier delta in target band
    brier_ci = next(
        (ci for ci in bootstrap_cis
         if ci.segment == "model_prob_0.65_0.70"
         and ci.metric == "brier_delta_vs_market"),
        None
    )
    brier_ci_excludes_zero = brier_ci.ci_excludes_zero if brier_ci else False
    brier_ci_stable = brier_ci.ci_stable if brier_ci else False

    # Split instability
    valid_split_bds = [s.brier_delta for s in split_market_results if not s.data_limited]
    split_bd_std = _std(valid_split_bds)
    split_instability = split_bd_std >= _RESIDUAL_SPLIT_STD_THRESHOLD

    # How many splits show market_superior?
    n_splits_market_superior = sum(1 for s in split_market_results if s.market_superior)
    n_splits_non_dl = sum(1 for s in split_market_results if not s.data_limited)

    # Distribution compression
    target_shape = next(
        (d for d in distribution_shape if d.segment == "model_prob_0.65_0.70"), None
    )
    model_compressed = target_shape.model_compressed if target_shape else False

    # sp_fip independent signal
    sp_independent = (
        sp_fip_attribution is not None
        and not sp_fip_attribution.data_limited
        and sp_fip_attribution.sp_fip_independent_signal
    )

    # sp_fip absorbed by market
    sp_absorbed = (
        sp_fip_attribution is not None
        and not sp_fip_attribution.data_limited
        and sp_fip_attribution.sp_fip_absorbed_by_market
    )

    # ── 3. SPLIT_INSTABILITY_RISK ──────────────────────────────────
    # If market dominance exists but is NOT consistent across splits
    if market_dominant and split_instability:
        # Check if most splits agree on market_superior
        market_dom_fraction = n_splits_market_superior / n_splits_non_dl if n_splits_non_dl > 0 else 0.0
        if market_dom_fraction < 0.6:  # less than 60% of splits agree
            risk_notes.append(
                f"⚠  Market dominant in target band (Brier delta={target_brier_delta:+.4f}) "
                f"but split Brier delta std={split_bd_std:.4f} is high."
            )
            risk_notes.append(
                f"⚠  Only {n_splits_market_superior}/{n_splits_non_dl} splits show market superiority."
            )
            return (
                SPLIT_INSTABILITY_RISK,
                (
                    f"Market is dominant in target band (Brier delta={target_brier_delta:+.4f}) "
                    f"but dominance is NOT consistent across splits (std={split_bd_std:.4f} >= "
                    f"{_RESIDUAL_SPLIT_STD_THRESHOLD}, {n_splits_market_superior}/{n_splits_non_dl} "
                    "splits agree). Cannot confirm stable market dominance."
                ),
                "停止 Phase72 patch path。回到本週 P1：LeagueAdapter / Budget Guard / Metrics SSOT / governance hardening。",
                risk_notes,
                False,
            )

    # ── 4. MARKET_DE_RISK_GUARD_PROMISING ─────────────────────────
    # Market is clearly dominant, CI stable and excludes zero, splits mostly agree
    if (market_dominant
            and brier_ci_excludes_zero
            and brier_ci_stable
            and not split_instability):
        risk_notes.append(
            f"Market Brier delta in target band = {target_brier_delta:+.4f}, "
            f"CI=[{brier_ci.ci_lower:+.4f}, {brier_ci.ci_upper:+.4f}] "
            f"(stable, excludes zero)."
        ) if brier_ci else None
        return (
            MARKET_DE_RISK_GUARD_PROMISING,
            (
                f"Market is clearly superior in 0.65–0.70 band "
                f"(Brier delta={target_brier_delta:+.4f}, CI stable and excludes zero, "
                f"splits consistent). A paper-only market de-risk guard is worth proposing."
            ),
            (
                "Phase72 可做 paper-only market de-risk guard proposal。"
                "調查在 0.65–0.70 band 以 market probability 替代 model probability 的 "
                "paper-only simulation，仍不得 production patch。"
            ),
            risk_notes,
            True,
        )

    # ── 5. MARKET_AWARE_ENSEMBLE_PROMISING ─────────────────────────
    # Market dominant but CI is wide/unstable — model/market disagreement has pattern
    if market_dominant and brier_ci_excludes_zero and model_compressed:
        risk_notes.append(
            f"⚠  Bootstrap CI for target band Brier delta is unstable (width > {_CI_STABLE_WIDTH})."
        ) if not brier_ci_stable else None
        return (
            MARKET_AWARE_ENSEMBLE_PROMISING,
            (
                f"Market is dominant in 0.65–0.70 band (Brier delta={target_brier_delta:+.4f}) "
                f"and model is compressed (compression_ratio="
                f"{target_shape.compression_ratio if target_shape else 'N/A':.4f}). "
                "Ensemble blending with market signal is worth investigating (paper-only)."
            ),
            (
                "Phase72 可做 paper-only market-aware ensemble proposal。"
                "調查 model compression 問題，及 market signal 作為 ensemble anchor 的 "
                "paper-only simulation，仍不得 production patch。"
            ),
            risk_notes,
            True,
        )

    # ── 6. SP_FIP_FEATURE_REPAIR_PROMISING ────────────────────────
    # sp_fip has independent signal not absorbed by market
    if sp_independent and not sp_absorbed:
        return (
            SP_FIP_FEATURE_REPAIR_PROMISING,
            (
                f"sp_fip_delta shows independent residual bucket gap "
                f"(gap={sp_fip_attribution.residual_bucket_gap:+.4f} if sp_fip_attribution else 0.0) "
                f"not absorbed by market signal. Feature repair is worth investigating (paper-only)."
            ),
            (
                "Phase72 可做 paper-only sp_fip_delta feature repair proposal。"
                "調查 sp_fip_delta 在 0.65–0.70 band 的 model weight 是否不足，"
                "仍不得 production patch。"
            ),
            risk_notes,
            True,
        )

    # ── 7. MARKET_DOMINANCE_NOT_PROMISING ─────────────────────────
    if not market_dominant:
        risk_notes.append("Market dominance in target band is below threshold or data limited.")

    if market_dominant:
        risk_notes.append(
            f"Market dominant (delta={target_brier_delta:+.4f}) but CI wide/unstable "
            "and no clear ensemble or feature pattern."
        )

    return (
        MARKET_DOMINANCE_NOT_PROMISING,
        (
            "Market dominance could not be confirmed as stable, structurally explained, "
            "or actionable for a paper-only repair proposal. "
            "Further Phase 72 investigation is not justified."
        ),
        "停止 Phase72 patch path。回到本週 P1：LeagueAdapter / Budget Guard / Metrics SSOT / governance hardening。",
        risk_notes,
        False,
    )


# ═══════════════════════════════════════════════════════════════════
# SERIALIZATION
# ═══════════════════════════════════════════════════════════════════

def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses / lists to JSON-serializable dict."""
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float, str)):
        return obj
    if isinstance(obj, list):
        return [_to_dict(x) for x in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict(v) for k, v in asdict(obj).items()}
    return obj


# ═══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def run_phase71_market_dominance_model_derisk_audit(
    predictions_path: str | Path,
    n_boot: int = _BOOTSTRAP_N,
    rng_seed: int = 42,
    n_permutations: int = 200,
) -> Phase71Report:
    """Full Phase 71 market dominance / model de-risk audit.

    Reads prediction JSONL, computes all 5 analysis dimensions plus NCs and
    bootstrap CIs, determines gate, and returns a Phase71Report.

    This function does NOT modify the source JSONL file.
    """
    predictions_path = Path(predictions_path)
    rng = random.Random(rng_seed)

    # ── Load data ──────────────────────────────────────────────────
    rows: list[dict] = []
    with predictions_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    rows = _enrich(rows)
    n_total = len(rows)

    feature_version = rows[0].get("feature_version", "unknown") if rows else "unknown"

    target_rows = _filter_segment(rows, _TARGET_BAND_LO, _TARGET_BAND_HI, None)
    n_target_band = len(target_rows)

    # ── Dimension A: segment metrics ──────────────────────────────
    segment_metrics = _compute_all_segment_metrics(rows)

    # ── Dimension B: distribution shape ───────────────────────────
    distribution_shape = _compute_all_distribution_shapes(rows)

    # ── Dimension C: sp_fip attribution ───────────────────────────
    sp_fip_attribution = _compute_sp_fip_attribution(rows)

    # ── Dimension D: split market results ─────────────────────────
    split_market_results = _compute_split_market_results(rows)

    # ── Dimension E: team concentration + feature availability ────
    team_concentration = _compute_team_concentration(rows, top_n=10)
    feature_availability = _compute_feature_availability(rows)

    # ── Negative controls ─────────────────────────────────────────
    negative_controls = _run_negative_controls(rows, n_permutations, rng)

    # ── Bootstrap CIs ─────────────────────────────────────────────
    bootstrap_cis = _compute_bootstrap_cis(rows, n_boot, rng)

    # ── Gate determination ────────────────────────────────────────
    gate, rationale, phase72_rec, risk_notes, worth_phase72 = _determine_gate(
        segment_metrics=segment_metrics,
        distribution_shape=distribution_shape,
        sp_fip_attribution=sp_fip_attribution,
        split_market_results=split_market_results,
        negative_controls=negative_controls,
        bootstrap_cis=bootstrap_cis,
    )

    # ── Summary flags ─────────────────────────────────────────────
    target_seg = next((s for s in segment_metrics if s.segment == "model_prob_0.65_0.70"), None)
    market_dominance_stable = (
        target_seg is not None
        and not target_seg.data_limited
        and target_seg.brier_delta >= _MARKET_SUPERIORITY_BRIER_GAP
    )

    valid_splits = [s for s in split_market_results if not s.data_limited]
    split_bds = [s.brier_delta for s in valid_splits]
    split_instability_detected = _std(split_bds) >= _RESIDUAL_SPLIT_STD_THRESHOLD

    sp_independent_signal = (
        sp_fip_attribution is not None
        and not sp_fip_attribution.data_limited
        and sp_fip_attribution.sp_fip_independent_signal
    )

    overfit_risk_detected = sum(1 for nc in negative_controls if nc.overfit_risk) >= _NC_OVERFIT_RISK_COUNT_THRESHOLD

    target_shape = next(
        (d for d in distribution_shape if d.segment == "model_prob_0.65_0.70"), None
    )
    model_compressed = target_shape.model_compressed if target_shape else False

    # Validate safety constants (assert at end for fail-fast)
    assert not CANDIDATE_PATCH_CREATED, "CANDIDATE_PATCH_CREATED must remain False"
    assert not PRODUCTION_MODIFIED, "PRODUCTION_MODIFIED must remain False"
    assert not ALPHA_MODIFIED, "ALPHA_MODIFIED must remain False"
    assert DIAGNOSTIC_ONLY, "DIAGNOSTIC_ONLY must remain True"
    assert not PREDICTION_JSONL_OVERWRITTEN, "PREDICTION_JSONL_OVERWRITTEN must remain False"
    assert PIT_SAFE_VALIDATION, "PIT_SAFE_VALIDATION must remain True"
    assert ALPHA == 0.40, f"ALPHA must remain 0.40, got {ALPHA}"

    return Phase71Report(
        phase_version=PHASE_VERSION,
        completion_marker=COMPLETION_MARKER,
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_path=str(predictions_path),
        candidate_patch_created=CANDIDATE_PATCH_CREATED,
        production_modified=PRODUCTION_MODIFIED,
        alpha_modified=ALPHA_MODIFIED,
        diagnostic_only=DIAGNOSTIC_ONLY,
        prediction_jsonl_overwritten=PREDICTION_JSONL_OVERWRITTEN,
        pit_safe_validation=PIT_SAFE_VALIDATION,
        alpha=ALPHA,
        phase70_gate_anchor=PHASE70_GATE_ANCHOR,
        n_total=n_total,
        feature_version=feature_version,
        n_target_band=n_target_band,
        segment_metrics=segment_metrics,
        distribution_shape=distribution_shape,
        sp_fip_attribution=sp_fip_attribution,
        split_market_results=split_market_results,
        team_concentration=team_concentration,
        feature_availability=feature_availability,
        negative_controls=negative_controls,
        bootstrap_cis=bootstrap_cis,
        gate=gate,
        gate_rationale=rationale,
        phase72_recommendation=phase72_rec,
        risk_notes=risk_notes,
        market_dominance_stable=market_dominance_stable,
        split_instability_detected=split_instability_detected,
        sp_fip_independent_signal=sp_independent_signal,
        overfit_risk_detected=overfit_risk_detected,
        model_compressed=model_compressed,
        worth_phase72=worth_phase72,
    )
