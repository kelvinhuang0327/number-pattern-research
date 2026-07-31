"""Phase 70 — Strong Home Favorite Underconfidence Feature Root-Cause Audit

DIAGNOSTIC ONLY.  CANDIDATE_PATCH_CREATED = False.  PRODUCTION_MODIFIED = False.
ALPHA_MODIFIED = False.  PREDICTION_JSONL_OVERWRITTEN = False.  ALPHA = 0.40 (FROZEN).

Phase 69 found: model_home_prob 0.65–0.70 band has severe underconfidence
(predicted ~0.67, actual ~0.84, residual ≈ -0.17). Calibration / probability
shaping counterfactuals (Phase 69) could NOT fix this. Phase 70 traces the root
cause via paper-only attribution across five dimensions:

  A. Market vs Model comparison per segment
  B. Favorite direction split (home_only vs away_only)
  C. Split / time stability (per split_id, month bucket)
  D. Team / pitcher / context concentration in 0.65–0.70 band
  E. Feature family proxy attribution (sp_fip_delta, bullpen, park)

NEGATIVE CONTROLS (5):
  1. shuffled_probability_band    — scramble band membership
  2. random_favorite_direction    — random home/away assignment
  3. irrelevant_date_bucket_split — odd/even game_day split
  4. random_team_bucket_split     — random team assignment to buckets
  5. random_confidence_assignment — shuffle model_home_prob across rows

GATE (one of 7):
  FEATURE_ROOT_CAUSE_PROMISING
  MARKET_ONLY_SUPERIOR
  ENSEMBLE_ATTRIBUTION_PROMISING
  TEAM_OR_SPLIT_CONCENTRATION_PROMISING
  DATA_LIMITED
  OVERFIT_RISK
  FEATURE_ROOT_CAUSE_NOT_PROMISING

PHASE CHAIN:
  Phase 69 gate: CALIBRATION_OBJECTIVE_NOT_PROMISING  (carried from Phase 69)
  Phase 70 gate: one of 7 listed above

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
PHASE_VERSION: str = "phase70_strong_home_favorite_underconfidence_audit_v1"
COMPLETION_MARKER: str = "PHASE_70_STRONG_HOME_FAVORITE_UNDERCONFIDENCE_AUDIT_VERIFIED"

# ═══════════════════════════════════════════════════════════════════
# GATE CONSTANTS (7)
# ═══════════════════════════════════════════════════════════════════
FEATURE_ROOT_CAUSE_PROMISING: str = "FEATURE_ROOT_CAUSE_PROMISING"
MARKET_ONLY_SUPERIOR: str = "MARKET_ONLY_SUPERIOR"
ENSEMBLE_ATTRIBUTION_PROMISING: str = "ENSEMBLE_ATTRIBUTION_PROMISING"
TEAM_OR_SPLIT_CONCENTRATION_PROMISING: str = "TEAM_OR_SPLIT_CONCENTRATION_PROMISING"
DATA_LIMITED: str = "DATA_LIMITED"
OVERFIT_RISK: str = "OVERFIT_RISK"
FEATURE_ROOT_CAUSE_NOT_PROMISING: str = "FEATURE_ROOT_CAUSE_NOT_PROMISING"

_VALID_GATES: frozenset[str] = frozenset({
    FEATURE_ROOT_CAUSE_PROMISING,
    MARKET_ONLY_SUPERIOR,
    ENSEMBLE_ATTRIBUTION_PROMISING,
    TEAM_OR_SPLIT_CONCENTRATION_PROMISING,
    DATA_LIMITED,
    OVERFIT_RISK,
    FEATURE_ROOT_CAUSE_NOT_PROMISING,
})

# ═══════════════════════════════════════════════════════════════════
# PREVIOUS PHASE GATE ANCHORS (FROZEN — READ ONLY)
# ═══════════════════════════════════════════════════════════════════
PHASE69_GATE_ANCHOR: str = "CALIBRATION_OBJECTIVE_NOT_PROMISING"
PHASE69_VERSION: str = "phase69_calibration_objective_redesign_counterfactual_v1"

# ═══════════════════════════════════════════════════════════════════
# ANALYSIS THRESHOLDS
# ═══════════════════════════════════════════════════════════════════
_MIN_SEGMENT_N: int = 20          # minimum rows for a segment to be non-data_limited
_MIN_BUCKET_N: int = 10           # minimum rows for bucket-level stats
_BOOTSTRAP_N: int = 1000          # default bootstrap iterations

# Target band (Phase 69 finding)
_TARGET_BAND_LO: float = 0.65
_TARGET_BAND_HI: float = 0.70

# Gate decision thresholds
_MARKET_SUPERIORITY_BRIER_GAP: float = 0.005   # model_brier - market_brier >= this
_TEAM_CONCENTRATION_SHARE: float = 0.30         # single team >= 30% of target band
_RESIDUAL_SPLIT_STD_THRESHOLD: float = 0.08     # std of residuals across splits >= this
_FEATURE_EXTREME_DELTA: float = 0.10            # feature mean diff target vs all >= this
_NC_SIGNAL_THRESHOLD: float = 0.04              # |signal_gap| < this → overfit_risk
_NC_OVERFIT_RISK_COUNT_THRESHOLD: int = 4       # >= 4/5 NCs with overfit_risk → OVERFIT_RISK gate
_CI_STABLE_WIDTH: float = 0.10                  # CI width > this → unstable (for residual CI)

# Underconfidence severity threshold for target band
_SEVERE_UNDERCONF_THRESHOLD: float = 0.10       # |residual| >= this in target band

# ═══════════════════════════════════════════════════════════════════
# SEGMENT DEFINITIONS
# (name, lo, hi, extra_filter)  — key = model_home_prob
# extra_filter: None | "home_win_0" | "home_win_1"
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
]

# ═══════════════════════════════════════════════════════════════════
# FEATURE FIELDS TO PROBE (from p0_features / bullpen_features)
# ═══════════════════════════════════════════════════════════════════
_FEATURE_PROBES: list[tuple[str, str, str]] = [
    # (feature_name, source_dict, available_flag)
    ("sp_fip_delta",             "p0_features",      "sp_fip_delta_available"),
    ("park_run_factor",          "p0_features",      "park_factor_available"),
    ("season_game_index",        "p0_features",      "season_game_index_available"),
    ("bullpen_fatigue_delta_3d", "bullpen_features",  "bullpen_feature_available"),
    ("home_bullpen_fatigue_3d",  "bullpen_features",  "bullpen_feature_available"),
    ("away_bullpen_fatigue_3d",  "bullpen_features",  "bullpen_feature_available"),
]

# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SegmentMetrics:
    """Full metrics for one segment (market + model side-by-side)."""
    segment: str
    n: int
    # Model metrics
    brier: float
    bss_vs_market: float
    ece: float
    residual_mean: float          # model_home_prob - home_win  (negative = underconfident)
    residual_std: float
    observed_win_rate: float
    predicted_mean_prob: float
    # Market metrics
    market_brier: float
    market_residual_mean: float   # market_home_prob - home_win
    market_mean_prob: float
    # Comparison
    model_minus_market_mean: float  # model_home_prob - market_home_prob_no_vig
    market_beats_model_brier: bool
    # Flags
    severe_underconfidence: bool    # |residual_mean| >= _SEVERE_UNDERCONF_THRESHOLD
    data_limited: bool


@dataclass
class SplitStabilityResult:
    """Per-split-id metrics for the target band (0.65–0.70)."""
    split_id: str
    n: int
    brier: float
    residual_mean: float
    observed_win_rate: float
    predicted_mean_prob: float
    market_mean_prob: float
    data_limited: bool


@dataclass
class TeamConcentrationResult:
    """Concentration metrics: teams appearing most in the target band."""
    team: str
    team_role: str   # "home" | "away"
    n_in_target_band: int
    share_of_target_band: float
    brier: float
    residual_mean: float
    observed_win_rate: float
    predicted_mean_prob: float
    data_limited: bool


@dataclass
class FeatureAttributionResult:
    """Proxy attribution for one feature in target vs all segments."""
    feature_name: str
    n_target_available: int
    n_target_total: int
    n_all_available: int
    n_all_total: int
    availability_rate_target: float
    availability_rate_all: float
    mean_value_target: float | None     # None if 0 available
    mean_value_all: float | None
    mean_residual_avail_target: float   # residual when feature available in target
    mean_residual_unavail_target: float # residual when feature unavailable in target
    residual_delta_proxy: float         # avail - unavail residual (proxy for feature impact)
    extreme_value_delta: float          # mean_value_target - mean_value_all (is it unusual?)
    data_limited: bool                  # n_target_available < _MIN_BUCKET_N


@dataclass
class NegativeControlResult:
    """Result for one of the 5 negative controls."""
    control_name: str
    description: str
    n_permutations: int
    observed_gap: float
    permuted_gap_mean: float
    permuted_gap_std: float
    signal_gap: float       # observed_gap - permuted_gap_mean
    overfit_risk: bool      # |signal_gap| < _NC_SIGNAL_THRESHOLD
    interpretation: str


@dataclass
class BootstrapCI:
    """Bootstrap CI for residual_mean or brier_delta in a segment."""
    metric: str       # "residual_mean" | "brier_delta_vs_market"
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
class Phase70Report:
    """Full Phase 70 report: strong home favorite underconfidence root-cause audit."""
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
    phase69_gate_anchor: str

    # Data summary
    n_total: int
    feature_version: str
    n_target_band: int       # games in model_home_prob 0.65–0.70

    # Dimension A + B: segment metrics (all_games + 10 segments)
    segment_metrics: list[SegmentMetrics]

    # Dimension C: split stability (for target band)
    split_stability: list[SplitStabilityResult]

    # Dimension D: team concentration (top N in target band)
    team_concentration: list[TeamConcentrationResult]

    # Dimension E: feature attribution proxy
    feature_attribution: list[FeatureAttributionResult]

    # Negative controls (5)
    negative_controls: list[NegativeControlResult]

    # Bootstrap CIs (key segments)
    bootstrap_cis: list[BootstrapCI]

    # Gate
    gate: str
    gate_rationale: str
    phase71_recommendation: str
    risk_notes: list[str]

    # Summary flags
    market_better_in_target_band: bool
    feature_gap_detected: bool
    team_concentration_detected: bool
    split_instability_detected: bool
    negative_controls_clear: bool
    bootstrap_ci_stable: bool
    worth_phase71: bool


# ═══════════════════════════════════════════════════════════════════
# CORE MATH (identical convention to Phase 69)
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


# ═══════════════════════════════════════════════════════════════════
# ROW ENRICHMENT — adds Phase70 analysis fields (in-place)
# ═══════════════════════════════════════════════════════════════════

def _safe_float(val: Any, default: float = 0.0) -> float:
    """Convert to float, returning default if None or non-numeric."""
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


def _enrich(rows: list[dict]) -> list[dict]:
    """Add derived analysis fields to each prediction row (in-place).

    Added keys (all prefixed _70_):
      _model_home_prob        copy of model_home_prob
      _market_home_prob       copy of market_home_prob_no_vig
      _home_win               float copy of home_win
      _model_residual         model_home_prob - home_win  (neg = underconfident)
      _market_residual        market_home_prob_no_vig - home_win
      _model_minus_market     model_home_prob - market_home_prob_no_vig
      _month_bucket           YYYY-MM string from game_date
      _game_day_odd           1 if day-of-month is odd, else 0
      _sp_fip_delta           from p0_features (None if unavailable)
      _sp_fip_available       bool
      _park_run_factor        from p0_features (None if unavailable)
      _park_factor_available  bool
      _season_game_index      from p0_features (None if unavailable)
      _season_game_index_available bool
      _bullpen_fatigue_delta  from bullpen_features (None if unavailable)
      _home_bullpen_fatigue   from bullpen_features
      _away_bullpen_fatigue   from bullpen_features
      _bullpen_available      bool
      _sp_home_pitcher        home pitcher name (None if missing)
      _sp_away_pitcher        away pitcher name
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

        # Time buckets
        gd = str(r.get("game_date", ""))
        r["_month_bucket"] = gd[:7] if len(gd) >= 7 else "unknown"
        try:
            day_num = int(gd[8:10]) if len(gd) >= 10 else 0
        except ValueError:
            day_num = 0
        r["_game_day_odd"] = day_num % 2

        # p0_features
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

        # bullpen_features
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
# DIMENSION A+B: SEGMENT METRICS
# ═══════════════════════════════════════════════════════════════════

def _compute_segment_metrics(
    rows: list[dict],
    seg_name: str,
    lo: float,
    hi: float,
    extra_filter: str | None,
) -> SegmentMetrics:
    """Compute full model + market metrics for one segment."""
    seg = _filter_segment(rows, lo, hi, extra_filter)
    n = len(seg)
    data_limited = n < _MIN_SEGMENT_N

    if n == 0:
        return SegmentMetrics(
            segment=seg_name, n=0,
            brier=0.0, bss_vs_market=0.0, ece=0.0,
            residual_mean=0.0, residual_std=0.0,
            observed_win_rate=0.0, predicted_mean_prob=0.0,
            market_brier=0.0, market_residual_mean=0.0, market_mean_prob=0.0,
            model_minus_market_mean=0.0, market_beats_model_brier=False,
            severe_underconfidence=False, data_limited=True,
        )

    model_probs = [r["_model_home_prob"] for r in seg]
    market_probs = [r["_market_home_prob"] for r in seg]
    outcomes = [r["_home_win"] for r in seg]
    model_residuals = [r["_model_residual"] for r in seg]
    market_residuals = [r["_market_residual"] for r in seg]
    mmm = [r["_model_minus_market"] for r in seg]

    model_b = _brier(model_probs, outcomes)
    market_b = _brier(market_probs, outcomes)
    bss = _bss_direct(model_b, market_b)
    ece_val = _ece(model_probs, outcomes)
    res_mean = round(_mean(model_residuals), 6)
    res_std = round(_std(model_residuals), 6)

    return SegmentMetrics(
        segment=seg_name,
        n=n,
        brier=round(model_b, 6),
        bss_vs_market=round(bss, 6),
        ece=round(ece_val, 6),
        residual_mean=res_mean,
        residual_std=res_std,
        observed_win_rate=round(_mean(outcomes), 6),
        predicted_mean_prob=round(_mean(model_probs), 6),
        market_brier=round(market_b, 6),
        market_residual_mean=round(_mean(market_residuals), 6),
        market_mean_prob=round(_mean(market_probs), 6),
        model_minus_market_mean=round(_mean(mmm), 6),
        market_beats_model_brier=(market_b < model_b),
        severe_underconfidence=(abs(res_mean) >= _SEVERE_UNDERCONF_THRESHOLD and not data_limited),
        data_limited=data_limited,
    )


def _compute_all_segment_metrics(rows: list[dict]) -> list[SegmentMetrics]:
    return [
        _compute_segment_metrics(rows, name, lo, hi, filt)
        for name, lo, hi, filt in _SEGMENT_DEFS
    ]


# ═══════════════════════════════════════════════════════════════════
# DIMENSION C: SPLIT / TIME STABILITY
# ═══════════════════════════════════════════════════════════════════

def _compute_split_stability(rows: list[dict]) -> list[SplitStabilityResult]:
    """Per split_id metrics for the target band (0.65–0.70)."""
    target = _filter_segment(rows, _TARGET_BAND_LO, _TARGET_BAND_HI, None)

    # Group by split_id
    by_split: dict[str, list[dict]] = {}
    for r in target:
        sid = str(r.get("split_id", "unknown"))
        by_split.setdefault(sid, []).append(r)

    results: list[SplitStabilityResult] = []
    for sid in sorted(by_split.keys()):
        grp = by_split[sid]
        n = len(grp)
        dl = n < _MIN_BUCKET_N
        model_probs = [r["_model_home_prob"] for r in grp]
        market_probs = [r["_market_home_prob"] for r in grp]
        outcomes = [r["_home_win"] for r in grp]
        residuals = [r["_model_residual"] for r in grp]
        results.append(SplitStabilityResult(
            split_id=sid,
            n=n,
            brier=round(_brier(model_probs, outcomes), 6) if not dl else 0.0,
            residual_mean=round(_mean(residuals), 6),
            observed_win_rate=round(_mean(outcomes), 6),
            predicted_mean_prob=round(_mean(model_probs), 6),
            market_mean_prob=round(_mean(market_probs), 6),
            data_limited=dl,
        ))
    return results


# ═══════════════════════════════════════════════════════════════════
# DIMENSION D: TEAM CONCENTRATION
# ═══════════════════════════════════════════════════════════════════

def _compute_team_concentration(
    rows: list[dict],
    top_n: int = 10,
) -> list[TeamConcentrationResult]:
    """Find teams most frequently appearing in the target band (as home or away)."""
    target = _filter_segment(rows, _TARGET_BAND_LO, _TARGET_BAND_HI, None)
    n_total = len(target)

    if n_total == 0:
        return []

    # Count home team appearances
    home_counts: dict[str, list[dict]] = {}
    for r in target:
        ht = str(r.get("home_team", "unknown"))
        home_counts.setdefault(ht, []).append(r)

    # Sort by count descending
    sorted_teams = sorted(home_counts.items(), key=lambda x: len(x[1]), reverse=True)
    results: list[TeamConcentrationResult] = []

    for team, grp in sorted_teams[:top_n]:
        n = len(grp)
        if n < 2:
            continue
        dl = n < _MIN_BUCKET_N
        model_probs = [r["_model_home_prob"] for r in grp]
        outcomes = [r["_home_win"] for r in grp]
        residuals = [r["_model_residual"] for r in grp]
        results.append(TeamConcentrationResult(
            team=team,
            team_role="home",
            n_in_target_band=n,
            share_of_target_band=round(n / n_total, 4),
            brier=round(_brier(model_probs, outcomes), 6) if not dl else 0.0,
            residual_mean=round(_mean(residuals), 6),
            observed_win_rate=round(_mean(outcomes), 6),
            predicted_mean_prob=round(_mean(model_probs), 6),
            data_limited=dl,
        ))

    return results


# ═══════════════════════════════════════════════════════════════════
# DIMENSION E: FEATURE ATTRIBUTION PROXY
# ═══════════════════════════════════════════════════════════════════

def _compute_feature_attribution(rows: list[dict]) -> list[FeatureAttributionResult]:
    """Proxy attribution: compare feature distributions in target vs all segments."""
    target = _filter_segment(rows, _TARGET_BAND_LO, _TARGET_BAND_HI, None)
    all_rows = rows

    results: list[FeatureAttributionResult] = []

    for feat_name, source_dict, avail_flag in _FEATURE_PROBES:
        # Map feature names to enriched row keys
        key_map = {
            "sp_fip_delta": "_sp_fip_delta",
            "park_run_factor": "_park_run_factor",
            "season_game_index": "_season_game_index",
            "bullpen_fatigue_delta_3d": "_bullpen_fatigue_delta",
            "home_bullpen_fatigue_3d": "_home_bullpen_fatigue",
            "away_bullpen_fatigue_3d": "_away_bullpen_fatigue",
        }
        avail_key_map = {
            "sp_fip_delta_available": "_sp_fip_available",
            "park_factor_available": "_park_factor_available",
            "season_game_index_available": "_season_game_index_available",
            "bullpen_feature_available": "_bullpen_available",
        }

        row_key = key_map.get(feat_name, f"_{feat_name}")
        avail_row_key = avail_key_map.get(avail_flag, f"_{avail_flag}")

        def _get_avail(r: dict) -> bool:
            v = r.get(avail_row_key)
            if v is None:
                return False
            return bool(v)

        def _get_val(r: dict) -> float | None:
            v = r.get(row_key)
            if v is None:
                return None
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        # Target band
        target_avail = [r for r in target if _get_avail(r)]
        target_unavail = [r for r in target if not _get_avail(r)]
        n_ta = len(target_avail)
        n_tt = len(target)

        # All rows
        all_avail = [r for r in all_rows if _get_avail(r)]
        n_aa = len(all_avail)
        n_at = len(all_rows)

        # Mean feature values
        def _mean_vals(rlist: list[dict]) -> float | None:
            vs = [_get_val(r) for r in rlist]
            vs_f = [v for v in vs if v is not None]
            return round(_mean(vs_f), 6) if vs_f else None

        mv_target = _mean_vals(target_avail)
        mv_all = _mean_vals(all_avail)

        extreme_delta = 0.0
        if mv_target is not None and mv_all is not None:
            extreme_delta = round(mv_target - mv_all, 6)

        # Residual proxy: mean residual when feature available vs unavailable in target
        res_avail = _mean([r["_model_residual"] for r in target_avail]) if target_avail else 0.0
        res_unavail = _mean([r["_model_residual"] for r in target_unavail]) if target_unavail else 0.0
        res_delta = round(res_avail - res_unavail, 6)

        dl = n_ta < _MIN_BUCKET_N

        results.append(FeatureAttributionResult(
            feature_name=feat_name,
            n_target_available=n_ta,
            n_target_total=n_tt,
            n_all_available=n_aa,
            n_all_total=n_at,
            availability_rate_target=round(n_ta / n_tt, 4) if n_tt > 0 else 0.0,
            availability_rate_all=round(n_aa / n_at, 4) if n_at > 0 else 0.0,
            mean_value_target=mv_target,
            mean_value_all=mv_all,
            mean_residual_avail_target=round(res_avail, 6),
            mean_residual_unavail_target=round(res_unavail, 6),
            residual_delta_proxy=res_delta,
            extreme_value_delta=extreme_delta,
            data_limited=dl,
        ))

    return results


# ═══════════════════════════════════════════════════════════════════
# BOOTSTRAP CI
# ═══════════════════════════════════════════════════════════════════

def _bootstrap_residual_ci(
    rows: list[dict],
    lo: float,
    hi: float,
    seg_name: str,
    metric: str,
    n_boot: int,
    rng: random.Random,
) -> BootstrapCI:
    """Bootstrap CI for residual_mean in [lo, hi) band."""
    seg = _filter_segment(rows, lo, hi, None)
    n = len(seg)
    dl = n < _MIN_SEGMENT_N

    if n < 2:
        return BootstrapCI(
            metric=metric, segment=seg_name, n=n, n_boot=n_boot,
            observed=0.0, ci_lower=0.0, ci_upper=0.0,
            ci_excludes_zero=False, ci_stable=False, data_limited=True,
        )

    if metric == "residual_mean":
        vals = [r["_model_residual"] for r in seg]
        observed = round(_mean(vals), 6)
    else:  # brier_delta_vs_market
        model_probs = [r["_model_home_prob"] for r in seg]
        market_probs = [r["_market_home_prob"] for r in seg]
        outcomes = [r["_home_win"] for r in seg]
        observed = round(_brier(model_probs, outcomes) - _brier(market_probs, outcomes), 6)
        vals = [r["_model_residual"] for r in seg]  # used for resampling proxy

    boot_stats: list[float] = []
    for _ in range(n_boot):
        sample = rng.choices(seg, k=n)
        if metric == "residual_mean":
            boot_stats.append(_mean([r["_model_residual"] for r in sample]))
        else:
            mp = [r["_model_home_prob"] for r in sample]
            mkp = [r["_market_home_prob"] for r in sample]
            oc = [r["_home_win"] for r in sample]
            boot_stats.append(_brier(mp, oc) - _brier(mkp, oc))

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
        ci_stable=ci_width < _CI_STABLE_WIDTH,
        data_limited=dl,
    )


def _compute_bootstrap_cis(
    rows: list[dict], n_boot: int, rng: random.Random
) -> list[BootstrapCI]:
    """Compute bootstrap CIs for key segments."""
    targets = [
        # (lo, hi, seg_name, metric)
        (_TARGET_BAND_LO, _TARGET_BAND_HI, "model_prob_0.65_0.70", "residual_mean"),
        (_TARGET_BAND_LO, _TARGET_BAND_HI, "model_prob_0.65_0.70", "brier_delta_vs_market"),
        (0.70, 1.01, "heavy_favorite", "residual_mean"),
        (0.60, 0.65, "model_prob_0.60_0.65", "residual_mean"),
        (0.00, 1.01, "all_games", "residual_mean"),
    ]
    return [
        _bootstrap_residual_ci(rows, lo, hi, seg, met, n_boot, rng)
        for lo, hi, seg, met in targets
    ]


# ═══════════════════════════════════════════════════════════════════
# NEGATIVE CONTROLS (5)
# ═══════════════════════════════════════════════════════════════════

def _nc_observed_gap(rows: list[dict]) -> float:
    """Observed signal: mean residual in target band vs all_games residual."""
    target = _filter_segment(rows, _TARGET_BAND_LO, _TARGET_BAND_HI, None)
    all_r = [r["_model_residual"] for r in rows]
    tgt_r = [r["_model_residual"] for r in target]
    return _mean(tgt_r) - _mean(all_r)


def _run_negative_controls(
    rows: list[dict], n_permutations: int, rng: random.Random
) -> list[NegativeControlResult]:
    results: list[NegativeControlResult] = []

    observed_gap = _nc_observed_gap(rows)

    # ── NC1: shuffled_probability_band ─────────────────────────────
    null_gaps: list[float] = []
    model_probs = [r["_model_home_prob"] for r in rows]
    residuals = [r["_model_residual"] for r in rows]
    for _ in range(n_permutations):
        shuffled_probs = model_probs[:]
        rng.shuffle(shuffled_probs)
        # Compute residual_mean for rows whose shuffled_prob falls in target band
        tgt_res = [
            residuals[i] for i, p in enumerate(shuffled_probs)
            if _TARGET_BAND_LO <= p < _TARGET_BAND_HI
        ]
        all_res = residuals
        null_gaps.append(_mean(tgt_res) - _mean(all_res) if tgt_res else 0.0)

    ng_mean = _mean(null_gaps)
    ng_std = _std(null_gaps)
    sig_gap = observed_gap - ng_mean
    results.append(NegativeControlResult(
        control_name="shuffled_probability_band",
        description=(
            "Shuffle model_home_prob across rows and recompute target-band "
            "residual gap. Signal gap should be large if band membership is meaningful."
        ),
        n_permutations=n_permutations,
        observed_gap=round(observed_gap, 6),
        permuted_gap_mean=round(ng_mean, 6),
        permuted_gap_std=round(ng_std, 6),
        signal_gap=round(sig_gap, 6),
        overfit_risk=abs(sig_gap) < _NC_SIGNAL_THRESHOLD,
        interpretation=(
            "SIGNAL: band membership explains residual gap."
            if abs(sig_gap) >= _NC_SIGNAL_THRESHOLD
            else "NO SIGNAL: residual gap not distinguishable from random band assignment."
        ),
    ))

    # ── NC2: random_favorite_direction ─────────────────────────────
    null_gaps2: list[float] = []
    home_wins = [r["_home_win"] for r in rows]
    for _ in range(n_permutations):
        # Randomly flip which team is "home"
        flipped_probs = [
            1.0 - p if rng.random() < 0.5 else p for p in model_probs
        ]
        # Recompute residuals for flipped assignment
        flipped_res = [fp - hw for fp, hw in zip(flipped_probs, home_wins)]
        # Target band residual gap
        tgt_res2 = [
            flipped_res[i] for i, p in enumerate(flipped_probs)
            if _TARGET_BAND_LO <= p < _TARGET_BAND_HI
        ]
        null_gaps2.append(_mean(tgt_res2) - _mean(flipped_res) if tgt_res2 else 0.0)

    ng2_mean = _mean(null_gaps2)
    ng2_std = _std(null_gaps2)
    sig2 = observed_gap - ng2_mean
    results.append(NegativeControlResult(
        control_name="random_favorite_direction",
        description=(
            "Randomly flip home/away assignment for each game. "
            "If underconfidence is real, original direction should produce a "
            "stronger signal than random flipping."
        ),
        n_permutations=n_permutations,
        observed_gap=round(observed_gap, 6),
        permuted_gap_mean=round(ng2_mean, 6),
        permuted_gap_std=round(ng2_std, 6),
        signal_gap=round(sig2, 6),
        overfit_risk=abs(sig2) < _NC_SIGNAL_THRESHOLD,
        interpretation=(
            "SIGNAL: direction assignment is meaningful."
            if abs(sig2) >= _NC_SIGNAL_THRESHOLD
            else "NO SIGNAL: residual gap not distinguishable from random home/away flip."
        ),
    ))

    # ── NC3: irrelevant_date_bucket_split ──────────────────────────
    # Split into odd vs even day-of-month; compute Brier gap between the halves
    odd_rows = [r for r in rows if r.get("_game_day_odd", 0) == 1]
    even_rows = [r for r in rows if r.get("_game_day_odd", 0) == 0]
    odd_brier = _brier(
        [r["_model_home_prob"] for r in odd_rows],
        [r["_home_win"] for r in odd_rows]
    ) if odd_rows else 0.0
    even_brier = _brier(
        [r["_model_home_prob"] for r in even_rows],
        [r["_home_win"] for r in even_rows]
    ) if even_rows else 0.0
    obs_date_gap = abs(odd_brier - even_brier)

    null_date_gaps: list[float] = []
    all_outcomes = [r["_home_win"] for r in rows]
    for _ in range(n_permutations):
        shuffled_outcomes = all_outcomes[:]
        rng.shuffle(shuffled_outcomes)
        o_b = _brier(
            [r["_model_home_prob"] for r in odd_rows],
            [shuffled_outcomes[i] for i, r in enumerate(rows) if r.get("_game_day_odd", 0) == 1]
        ) if odd_rows else 0.0
        e_b = _brier(
            [r["_model_home_prob"] for r in even_rows],
            [shuffled_outcomes[i] for i, r in enumerate(rows) if r.get("_game_day_odd", 0) == 0]
        ) if even_rows else 0.0
        null_date_gaps.append(abs(o_b - e_b))

    nd3_mean = _mean(null_date_gaps)
    nd3_std = _std(null_date_gaps)
    sig3 = obs_date_gap - nd3_mean
    results.append(NegativeControlResult(
        control_name="irrelevant_date_bucket_split",
        description=(
            "Split by odd/even day-of-month; compute Brier gap between the two halves. "
            "Gap should be near zero (irrelevant partition)."
        ),
        n_permutations=n_permutations,
        observed_gap=round(obs_date_gap, 6),
        permuted_gap_mean=round(nd3_mean, 6),
        permuted_gap_std=round(nd3_std, 6),
        signal_gap=round(sig3, 6),
        overfit_risk=abs(sig3) >= _NC_SIGNAL_THRESHOLD,  # inverse: big gap means spurious
        interpretation=(
            "NO SIGNAL: date bucket produces no spurious Brier gap."
            if abs(sig3) < _NC_SIGNAL_THRESHOLD
            else "WARNING: irrelevant date split produces Brier gap (possible confound)."
        ),
    ))

    # ── NC4: random_team_bucket_split ──────────────────────────────
    # Randomly assign each home_team to bucket A or B; compute residual gap
    teams = list({str(r.get("home_team", "")) for r in rows})
    obs_team_gap = _nc_observed_gap(rows)  # reuse observed gap

    null_team_gaps: list[float] = []
    for _ in range(n_permutations):
        bucket_a = set(rng.sample(teams, k=max(1, len(teams) // 2)))
        a_rows = [r for r in rows if str(r.get("home_team", "")) in bucket_a]
        b_rows = [r for r in rows if str(r.get("home_team", "")) not in bucket_a]
        a_res = [r["_model_residual"] for r in a_rows]
        b_res = [r["_model_residual"] for r in b_rows]
        ng4 = abs(_mean(a_res) - _mean(b_res)) if (a_res and b_res) else 0.0
        null_team_gaps.append(ng4)

    nt4_mean = _mean(null_team_gaps)
    nt4_std = _std(null_team_gaps)
    sig4 = abs(obs_team_gap) - nt4_mean
    results.append(NegativeControlResult(
        control_name="random_team_bucket_split",
        description=(
            "Randomly assign teams to two buckets; compute residual gap. "
            "If real team concentration exists, the observed gap in target band "
            "should exceed random team splits."
        ),
        n_permutations=n_permutations,
        observed_gap=round(obs_team_gap, 6),
        permuted_gap_mean=round(nt4_mean, 6),
        permuted_gap_std=round(nt4_std, 6),
        signal_gap=round(sig4, 6),
        overfit_risk=abs(sig4) < _NC_SIGNAL_THRESHOLD,
        interpretation=(
            "SIGNAL: team structure explains part of residual gap."
            if abs(sig4) >= _NC_SIGNAL_THRESHOLD
            else "NO SIGNAL: residual gap not distinguishable from random team buckets."
        ),
    ))

    # ── NC5: random_confidence_assignment ─────────────────────────
    # Shuffle model_home_prob values across all rows; compute new target-band residual gap
    null_conf_gaps: list[float] = []
    for _ in range(n_permutations):
        shuffled_probs2 = model_probs[:]
        rng.shuffle(shuffled_probs2)
        new_res = [sp - hw for sp, hw in zip(shuffled_probs2, home_wins)]
        tgt_idx = [i for i, p in enumerate(shuffled_probs2)
                   if _TARGET_BAND_LO <= p < _TARGET_BAND_HI]
        tgt_new_res = [new_res[i] for i in tgt_idx]
        null_conf_gaps.append(_mean(tgt_new_res) - _mean(new_res) if tgt_new_res else 0.0)

    nc5_mean = _mean(null_conf_gaps)
    nc5_std = _std(null_conf_gaps)
    sig5 = observed_gap - nc5_mean
    results.append(NegativeControlResult(
        control_name="random_confidence_assignment",
        description=(
            "Shuffle model_home_prob values across all rows; compute residual gap in "
            "randomly-formed 0.65–0.70 'band'. Real signal should vanish under shuffling."
        ),
        n_permutations=n_permutations,
        observed_gap=round(observed_gap, 6),
        permuted_gap_mean=round(nc5_mean, 6),
        permuted_gap_std=round(nc5_std, 6),
        signal_gap=round(sig5, 6),
        overfit_risk=abs(sig5) < _NC_SIGNAL_THRESHOLD,
        interpretation=(
            "SIGNAL: original confidence assignment produces distinct residual gap."
            if abs(sig5) >= _NC_SIGNAL_THRESHOLD
            else "NO SIGNAL: residual gap not distinguishable from random confidence assignment."
        ),
    ))

    return results


# ═══════════════════════════════════════════════════════════════════
# GATE DETERMINATION
# ═══════════════════════════════════════════════════════════════════

def _determine_gate(
    segment_metrics: list[SegmentMetrics],
    split_stability: list[SplitStabilityResult],
    team_concentration: list[TeamConcentrationResult],
    feature_attribution: list[FeatureAttributionResult],
    negative_controls: list[NegativeControlResult],
    bootstrap_cis: list[BootstrapCI],
) -> tuple[str, str, str, list[str], bool]:
    """Returns (gate, rationale, phase71_rec, risk_notes, worth_phase71)."""

    risk_notes: list[str] = []

    # Look up key metrics
    seg_by_name: dict[str, SegmentMetrics] = {s.segment: s for s in segment_metrics}
    target_seg = seg_by_name.get("model_prob_0.65_0.70")
    all_seg = seg_by_name.get("all_games")

    n_target = target_seg.n if target_seg else 0

    # ── 1. DATA_LIMITED ────────────────────────────────────────────
    if n_target < _MIN_SEGMENT_N:
        return (
            DATA_LIMITED,
            f"Insufficient data in target band 0.65–0.70 (n={n_target} < {_MIN_SEGMENT_N}).",
            "停止 patch search。改回 governance / LeagueAdapter / Budget Guard / Metrics SSOT P1。",
            risk_notes,
            False,
        )

    # ── 2. OVERFIT_RISK ────────────────────────────────────────────
    nc_overfit_count = sum(1 for nc in negative_controls if nc.overfit_risk)
    if nc_overfit_count >= _NC_OVERFIT_RISK_COUNT_THRESHOLD:
        risk_notes.append(
            f"⚠  {nc_overfit_count}/5 negative controls show overfit risk. "
            "Target band signal may not be distinct from noise."
        )
        return (
            OVERFIT_RISK,
            (
                f"{nc_overfit_count}/5 negative controls show overfit risk. "
                "Cannot confirm target-band underconfidence is a systematic signal vs. noise."
            ),
            "停止 patch search。改回 governance / LeagueAdapter / Budget Guard / Metrics SSOT P1。",
            risk_notes,
            False,
        )

    # Collect summary flags
    # Market superiority in target band
    market_better = (
        target_seg is not None
        and not target_seg.data_limited
        and (target_seg.brier - target_seg.market_brier) >= _MARKET_SUPERIORITY_BRIER_GAP
    )

    # Team concentration in target band
    top_team_share = max(
        (t.share_of_target_band for t in team_concentration if not t.data_limited),
        default=0.0,
    )
    team_conc_detected = top_team_share >= _TEAM_CONCENTRATION_SHARE

    # Split instability in target band
    valid_split_residuals = [s.residual_mean for s in split_stability if not s.data_limited]
    split_instability = _std(valid_split_residuals) >= _RESIDUAL_SPLIT_STD_THRESHOLD

    # Feature extreme delta
    feat_extremes = [
        abs(f.extreme_value_delta)
        for f in feature_attribution
        if f.mean_value_target is not None and f.mean_value_all is not None
    ]
    feature_extreme_detected = any(d >= _FEATURE_EXTREME_DELTA for d in feat_extremes)

    # Feature residual delta proxy
    feat_res_deltas = [
        abs(f.residual_delta_proxy)
        for f in feature_attribution
        if not f.data_limited
    ]
    feature_residual_gap = any(d >= _FEATURE_EXTREME_DELTA for d in feat_res_deltas)

    # Bootstrap CI excludes zero in target band?
    target_ci = next(
        (ci for ci in bootstrap_cis
         if ci.segment == "model_prob_0.65_0.70" and ci.metric == "residual_mean"),
        None
    )
    ci_excludes_zero = target_ci.ci_excludes_zero if target_ci else False
    ci_stable = target_ci.ci_stable if target_ci else False

    if not ci_stable:
        risk_notes.append("⚠  Bootstrap CI for target band residual is wide or unstable.")

    # ── 3. MARKET_ONLY_SUPERIOR ────────────────────────────────────
    if market_better:
        market_gap = (target_seg.brier - target_seg.market_brier) if target_seg else 0.0
        return (
            MARKET_ONLY_SUPERIOR,
            (
                f"Market Brier is significantly lower than model Brier in 0.65–0.70 band "
                f"(gap={market_gap:+.4f} >= {_MARKET_SUPERIORITY_BRIER_GAP}). "
                "Market has information not captured by the model's feature set."
            ),
            (
                "Phase71 應轉向 market dominance / model de-risk audit。"
                "調查 market_home_prob 在 0.65–0.70 band 優於 model 的原因。"
            ),
            risk_notes,
            True,
        )

    # ── 4. TEAM_OR_SPLIT_CONCENTRATION_PROMISING ───────────────────
    if team_conc_detected or split_instability:
        reason_parts = []
        if team_conc_detected:
            reason_parts.append(
                f"Top home team share in target band = {top_team_share:.1%} "
                f">= {_TEAM_CONCENTRATION_SHARE:.0%} threshold."
            )
        if split_instability:
            reason_parts.append(
                f"Residual std across splits = {_std(valid_split_residuals):.4f} "
                f">= {_RESIDUAL_SPLIT_STD_THRESHOLD} threshold."
            )
        return (
            TEAM_OR_SPLIT_CONCENTRATION_PROMISING,
            " ".join(reason_parts),
            (
                "Phase71 應做 segment-specific robustness / sample concentration audit。"
                "調查哪些 team/split 造成 0.65–0.70 underconfidence。"
            ),
            risk_notes,
            True,
        )

    # ── 5. ENSEMBLE_ATTRIBUTION_PROMISING ─────────────────────────
    # Proxy: if bullpen or SP feature values are extreme in target band
    # AND feature is available for most target rows
    target_avail_rate = next(
        (f.availability_rate_target for f in feature_attribution
         if f.feature_name == "bullpen_fatigue_delta_3d"),
        0.0,
    )
    sp_extreme = next(
        (abs(f.extreme_value_delta) for f in feature_attribution
         if f.feature_name == "sp_fip_delta" and f.mean_value_target is not None),
        0.0,
    )
    bp_extreme = next(
        (abs(f.extreme_value_delta) for f in feature_attribution
         if f.feature_name == "bullpen_fatigue_delta_3d" and f.mean_value_target is not None),
        0.0,
    )

    if (target_avail_rate >= 0.50 and
            (sp_extreme >= _FEATURE_EXTREME_DELTA or bp_extreme >= _FEATURE_EXTREME_DELTA)):
        return (
            ENSEMBLE_ATTRIBUTION_PROMISING,
            (
                f"Feature values in target band are extreme relative to all_games "
                f"(sp_fip_delta_delta={sp_extreme:.4f}, "
                f"bullpen_delta_delta={bp_extreme:.4f}). "
                "Ensemble component (SP or bullpen) may explain underconfidence."
            ),
            (
                "Phase71 應做 ensemble weighting paper-only repair proposal。"
                "優先調查 sp_fip_delta 和 bullpen_fatigue_delta 的 ensemble weight。"
            ),
            risk_notes,
            True,
        )

    # ── 6. FEATURE_ROOT_CAUSE_PROMISING ───────────────────────────
    if (feature_extreme_detected or feature_residual_gap) and ci_excludes_zero:
        return (
            FEATURE_ROOT_CAUSE_PROMISING,
            (
                "Feature attribution proxy shows systematic patterns in 0.65–0.70 band "
                f"(feature_extreme={feature_extreme_detected}, "
                f"feature_residual_gap={feature_residual_gap}). "
                "Bootstrap CI excludes zero — underconfidence signal is real."
            ),
            (
                "Phase71 才能做 paper-only feature patch proposal。"
                "仍不得進行 production patch。"
            ),
            risk_notes,
            True,
        )

    # ── 7. FEATURE_ROOT_CAUSE_NOT_PROMISING (default) ─────────────
    target_res = target_seg.residual_mean if target_seg else 0.0
    return (
        FEATURE_ROOT_CAUSE_NOT_PROMISING,
        (
            f"Target band 0.65–0.70 underconfidence (residual={target_res:+.4f}) "
            "confirmed but no systematic feature, team, or split attribution found. "
            "Likely small-sample noise or structural issue beyond current feature set."
        ),
        (
            "停止 patch search。改回 governance / LeagueAdapter / Budget Guard / Metrics SSOT P1。"
        ),
        risk_notes,
        False,
    )


# ═══════════════════════════════════════════════════════════════════
# JSON SERIALIZATION
# ═══════════════════════════════════════════════════════════════════

def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclass / list / dict to JSON-serializable form."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(v) for v in obj]
    if isinstance(obj, (frozenset, set)):
        return sorted(str(v) for v in obj)
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


# ═══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def run_phase70_strong_home_favorite_underconfidence_audit(
    predictions_path: str | Path,
    n_boot: int = _BOOTSTRAP_N,
    rng_seed: int = 42,
) -> Phase70Report:
    """Run the full Phase 70 audit.

    Args:
        predictions_path: Path to phase56 JSONL predictions file.
        n_boot:           Number of bootstrap iterations.
        rng_seed:         RNG seed for reproducibility.

    Returns:
        Phase70Report with all attribution results and gate decision.

    SAFETY: Does NOT modify predictions_path or any production file.
    """
    rng = random.Random(rng_seed)
    path = Path(predictions_path)

    # Load all rows
    rows: list[dict] = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    # Enrich
    _enrich(rows)

    n_total = len(rows)
    feature_version = rows[0].get("feature_version", "unknown") if rows else "unknown"

    # Dimension A+B: segment metrics
    segment_metrics = _compute_all_segment_metrics(rows)
    n_target_band = next(
        (s.n for s in segment_metrics if s.segment == "model_prob_0.65_0.70"), 0
    )

    # Dimension C: split stability (target band)
    split_stability = _compute_split_stability(rows)

    # Dimension D: team concentration (target band)
    team_concentration = _compute_team_concentration(rows)

    # Dimension E: feature attribution proxy
    feature_attribution = _compute_feature_attribution(rows)

    # Bootstrap CIs
    bootstrap_cis = _compute_bootstrap_cis(rows, n_boot, rng)

    # Negative controls
    negative_controls = _run_negative_controls(rows, n_permutations=200, rng=rng)

    # Gate determination
    gate, rationale, phase71_rec, risk_notes, worth_phase71 = _determine_gate(
        segment_metrics, split_stability, team_concentration,
        feature_attribution, negative_controls, bootstrap_cis,
    )

    # Summary flags
    target_seg = next(
        (s for s in segment_metrics if s.segment == "model_prob_0.65_0.70"), None
    )
    market_better = (
        target_seg is not None
        and not target_seg.data_limited
        and (target_seg.brier - target_seg.market_brier) >= _MARKET_SUPERIORITY_BRIER_GAP
    )
    feat_extremes = [
        abs(f.extreme_value_delta)
        for f in feature_attribution
        if f.mean_value_target is not None and f.mean_value_all is not None
    ]
    feature_gap_detected = any(d >= _FEATURE_EXTREME_DELTA for d in feat_extremes)
    top_team_share = max(
        (t.share_of_target_band for t in team_concentration if not t.data_limited),
        default=0.0,
    )
    team_conc_detected = top_team_share >= _TEAM_CONCENTRATION_SHARE
    valid_split_res = [s.residual_mean for s in split_stability if not s.data_limited]
    split_instability = _std(valid_split_res) >= _RESIDUAL_SPLIT_STD_THRESHOLD
    nc_clear = sum(1 for nc in negative_controls if not nc.overfit_risk) >= 3
    target_ci = next(
        (ci for ci in bootstrap_cis
         if ci.segment == "model_prob_0.65_0.70" and ci.metric == "residual_mean"),
        None,
    )
    ci_stable = target_ci.ci_stable if target_ci else False

    return Phase70Report(
        phase_version=PHASE_VERSION,
        completion_marker=COMPLETION_MARKER,
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_path=str(path.resolve()),

        candidate_patch_created=CANDIDATE_PATCH_CREATED,
        production_modified=PRODUCTION_MODIFIED,
        alpha_modified=ALPHA_MODIFIED,
        diagnostic_only=DIAGNOSTIC_ONLY,
        prediction_jsonl_overwritten=PREDICTION_JSONL_OVERWRITTEN,
        pit_safe_validation=PIT_SAFE_VALIDATION,
        alpha=ALPHA,

        phase69_gate_anchor=PHASE69_GATE_ANCHOR,

        n_total=n_total,
        feature_version=feature_version,
        n_target_band=n_target_band,

        segment_metrics=segment_metrics,
        split_stability=split_stability,
        team_concentration=team_concentration,
        feature_attribution=feature_attribution,
        negative_controls=negative_controls,
        bootstrap_cis=bootstrap_cis,

        gate=gate,
        gate_rationale=rationale,
        phase71_recommendation=phase71_rec,
        risk_notes=risk_notes,

        market_better_in_target_band=market_better,
        feature_gap_detected=feature_gap_detected,
        team_concentration_detected=team_conc_detected,
        split_instability_detected=split_instability,
        negative_controls_clear=nc_clear,
        bootstrap_ci_stable=ci_stable,
        worth_phase71=worth_phase71,
    )
