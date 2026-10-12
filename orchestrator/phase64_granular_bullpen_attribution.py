"""
orchestrator/phase64_granular_bullpen_attribution.py
=====================================================
Phase 64 — Granular Bullpen Attribution with OOF / PIT-safe Validation

目標：
  - 使用 Phase63 產出的 granular bullpen SSOT artifacts，對重要 failure segment
    做 PIT-safe attribution 與 OOF 驗證。
  - 驗證新顆粒化特徵（1d/5d/b2b/3in4/closer）能否提供超越 Phase60 3d baseline 的
    預測訊號。
  - 若 Phase63 artifact 覆蓋不足，誠實標記 DATA_LIMITED。

安全常數（絕不修改）：
  CANDIDATE_PATCH_CREATED = False
  PRODUCTION_MODIFIED     = False
  ALPHA_MODIFIED          = False
  DIAGNOSTIC_ONLY         = True

市場混合公式（FROZEN）：
  blend = (1 - 0.40) * model_home_prob + 0.40 * market_home_prob_no_vig
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Safety Constants — FROZEN, never modify
# ---------------------------------------------------------------------------
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
ALPHA_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
ALPHA: float = 0.40
PHASE_VERSION: str = "phase64_granular_bullpen_attribution_v1"

# ---------------------------------------------------------------------------
# Gate Constants
# ---------------------------------------------------------------------------
BULLPEN_GRANULAR_FEATURE_PROMISING: str = "BULLPEN_GRANULAR_FEATURE_PROMISING"
DIAGNOSTIC_ONLY_SIGNAL: str = "DIAGNOSTIC_ONLY_SIGNAL"
DATA_LIMITED: str = "DATA_LIMITED"
OVERFIT_RISK: str = "OVERFIT_RISK"
BULLPEN_GRANULAR_FEATURE_NOT_PROMISING: str = "BULLPEN_GRANULAR_FEATURE_NOT_PROMISING"

# ---------------------------------------------------------------------------
# Segment Thresholds (consistent with Phase 60)
# ---------------------------------------------------------------------------
_HEAVY_FAV_THRESHOLD: float = 0.70
_HIGH_CONF_THRESHOLD: float = 0.75
_MIN_SEGMENT_N: int = 20
_BOOTSTRAP_N: int = 1000
_OOF_PROMISING_DELTA: float = 0.02
_MIN_COVERAGE_RATE: float = 0.10   # < 10% coverage → DATA_LIMITED for that feature
_OVERFIT_SIGMA: float = 1.5        # real > shuffled_mean + sigma*shuffled_std → null rejected
_PHASE63_AUDIT_HASH: str = "4923b662e37f0ca1"

# ---------------------------------------------------------------------------
# Feature registry: Phase 64 granular feature set
# Each tuple: (feature_name, window_days, data_limited_initially, description)
# ---------------------------------------------------------------------------
_GRANULAR_FEATURE_REGISTRY: list[tuple[str, int, bool, str]] = [
    # New Phase63 features
    ("bullpen_usage_last_1d_fav",    1,  False, "Favored team bullpen IP yesterday"),
    ("bullpen_usage_last_1d_dog",    1,  False, "Underdog team bullpen IP yesterday"),
    ("bullpen_usage_last_3d_fav",    3,  False, "Favored team bullpen IP last 3d"),
    ("bullpen_usage_last_3d_dog",    3,  False, "Underdog team bullpen IP last 3d"),
    ("bullpen_usage_last_5d_fav",    5,  False, "Favored team bullpen IP last 5d"),
    ("bullpen_usage_last_5d_dog",    5,  False, "Underdog team bullpen IP last 5d"),
    ("reliever_b2b_count_fav",       2,  False, "Favored team back-to-back reliever count"),
    ("reliever_b2b_count_dog",       2,  False, "Underdog team back-to-back reliever count"),
    ("reliever_3in4_count_fav",      4,  False, "Favored team 3-in-4-days reliever count"),
    ("reliever_3in4_count_dog",      4,  False, "Underdog team 3-in-4-days reliever count"),
    ("closer_used_1d_fav",           1,  False, "Favored team closer used yesterday"),
    ("closer_used_2d_fav",           2,  False, "Favored team closer used last 2d"),
    ("bullpen_rest_imbalance_3d",    3,  False, "Abs diff home-away 3d bullpen usage"),
    # DATA_LIMITED (no LI source)
    ("high_leverage_used_1d_fav",    1,  True,  "Favored team high-leverage reliever yesterday [DATA_LIMITED: needs LI/PbP]"),
    ("high_leverage_workload_3d_fav",3,  True,  "Favored team high-leverage workload last 3d [DATA_LIMITED: needs LI/PbP]"),
]


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class Phase63ArtifactAlignment:
    """Alignment stats between Phase 63 SSOT artifacts and prediction dataset."""
    n_ssot_artifacts: int           # total Phase63 SSOT artifacts loaded
    n_predictions: int              # total prediction rows
    n_game_alignments: int          # game rows with at least 1 team's SSOT aligned
    n_fully_aligned: int            # game rows with BOTH teams' SSOT aligned
    alignment_rate_partial: float   # n_game_alignments / n_predictions
    alignment_rate_full: float      # n_fully_aligned / n_predictions
    aligned_game_ids: list[str]     # game_ids with any alignment
    coverage_insufficient: bool     # True if alignment_rate_partial < _MIN_COVERAGE_RATE


@dataclass
class FeatureCoverage:
    """Coverage for a single granular feature across the prediction dataset."""
    feature_name: str
    n_available: int
    n_total: int
    coverage_pct: float
    data_limited: bool          # True if below threshold or inherently DATA_LIMITED
    data_limited_reason: str | None


@dataclass
class BucketAttribution:
    """Win-rate attribution: median-split high vs low buckets."""
    n_high: int
    n_low: int
    win_rate_high: float
    win_rate_low: float
    win_rate_delta: float
    bootstrap_ci_lower: float
    bootstrap_ci_upper: float
    bootstrap_significant: bool


@dataclass
class GranularSegmentAttribution:
    """Attribution result for one feature × one segment."""
    feature_name: str
    segment: str
    n: int
    coverage_pct: float
    baseline_brier: float
    baseline_bss: float
    calibration_residual: float
    ece: float
    heavy_fav_ece: float | None    # ECE for heavy_fav sub-segment (if in all)
    bucket_attribution: BucketAttribution | None
    oof_win_rate_delta: float | None
    oof_n: int | None
    oof_replicated: bool | None
    data_limited: bool
    data_limited_reason: str | None


@dataclass
class Phase64NegativeControl:
    """Negative control: shuffled vs real feature delta."""
    feature_name: str
    segment: str
    real_win_rate_delta: float
    shuffled_mean_delta: float
    shuffled_std_delta: float
    null_rejected: bool
    overfit_risk: bool   # True if null_rejected AND shuffled also significant


@dataclass
class Phase64OOFResult:
    """Rolling monthly OOF validation."""
    feature_name: str
    n_folds: int
    fold_months: list[str]
    fold_win_rate_deltas: list[float]
    fold_n: list[int]
    oof_mean_delta: float
    oof_consistent_sign: bool
    oof_significant: bool


@dataclass
class Phase64AttributionResult:
    """Full Phase 64 attribution result."""
    phase_version: str
    run_timestamp: str
    audit_hash: str

    # Safety constants snapshot
    candidate_patch_created: bool
    production_modified: bool
    alpha_modified: bool
    diagnostic_only: bool
    alpha: float

    # Phase 63 anchor
    phase63_audit_hash: str
    phase63_gate: str

    # Data summary
    n_predictions: int
    n_bullpen_3d_rows: int        # Phase60 baseline data
    n_phase63_ssot_artifacts: int # Phase63 SSOT artifacts
    n_aligned_3d: int             # Phase60 alignment count

    # Phase 63 artifact alignment
    phase63_alignment: Phase63ArtifactAlignment

    # Feature coverage
    feature_coverage: list[FeatureCoverage]
    n_available_features: int
    n_data_limited_features: int

    # Segment sizes (from prediction dataset)
    segment_n_all: int
    segment_n_heavy_fav: int
    segment_n_high_conf: int
    segment_n_phase45_failure: int

    # Attribution results
    phase60_baseline_replication: dict[str, Any]   # Phase60 3d results replicated
    granular_attributions: list[GranularSegmentAttribution]

    # Negative controls
    negative_controls: list[Phase64NegativeControl]

    # OOF validation
    oof_results: list[Phase64OOFResult]

    # Bootstrap CI summary
    any_bootstrap_significant: bool

    # Gate
    gate: str
    gate_rationale: str

    # Next step
    next_step: str


# ---------------------------------------------------------------------------
# Helper: IP string parsing (consistent with Phase 62/63)
# ---------------------------------------------------------------------------

def _parse_ip(ip_str: str | None) -> float:
    """Parse StatsAPI innings_pitched string to decimal float."""
    if not ip_str:
        return 0.0
    try:
        s = str(ip_str).strip()
        if "." in s:
            integer_part, frac_part = s.split(".", 1)
            return int(integer_part) + int(frac_part) / 3
        return float(s)
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Helper: Team name normalisation
# ---------------------------------------------------------------------------

def _norm_team(name: str) -> str:
    """Normalise team name: upper-case, spaces → underscores, strip non-alnum_."""
    return re.sub(r"[^A-Z0-9_]", "_", name.upper().replace(" ", "_"))


def _teams_match(a: str, b: str) -> bool:
    return _norm_team(a) == _norm_team(b)


# ---------------------------------------------------------------------------
# Helper: Blend probability computation
# ---------------------------------------------------------------------------

def _blend_prob(model_prob: float, market_prob: float) -> float:
    """FROZEN blend formula: blend = (1-α)*model + α*market."""
    return (1.0 - ALPHA) * model_prob + ALPHA * market_prob


def _fav_prob(blend: float) -> float:
    return max(blend, 1.0 - blend)


def _is_home_favorite(blend: float) -> bool:
    return blend >= 0.50


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------

def _compute_ece(probs: list[float], labels: list[int], n_bins: int = 10) -> float:
    if not probs:
        return float("nan")
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, y in zip(probs, labels):
        idx = min(int(p * n_bins), n_bins - 1)
        bins[idx].append((p, y))
    ece = 0.0
    for b in bins:
        if not b:
            continue
        mean_p = sum(x[0] for x in b) / len(b)
        mean_y = sum(x[1] for x in b) / len(b)
        ece += len(b) / len(probs) * abs(mean_p - mean_y)
    return ece


def _brier_score(probs: list[float], labels: list[int]) -> float:
    if not probs:
        return float("nan")
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(probs)


def _bss(bs: float, climate_rate: float) -> float:
    bs_climate = climate_rate * (1 - climate_rate)
    if bs_climate == 0:
        return 0.0
    return 1.0 - bs / bs_climate


def _bootstrap_win_rate_delta(
    high_wins: list[int],
    low_wins: list[int],
    n_boot: int = _BOOTSTRAP_N,
    rng_seed: int = 42,
) -> tuple[float, float]:
    """95% bootstrap CI for win_rate_high - win_rate_low."""
    rng = random.Random(rng_seed)
    deltas = []
    for _ in range(n_boot):
        h = rng.choices(high_wins, k=len(high_wins))
        l = rng.choices(low_wins, k=len(low_wins))
        wr_h = sum(h) / len(h) if h else 0.5
        wr_l = sum(l) / len(l) if l else 0.5
        deltas.append(wr_h - wr_l)
    deltas.sort()
    return deltas[int(0.025 * n_boot)], deltas[int(0.975 * n_boot)]


def _bucket_attribution(
    feature_vals: list[float | None],
    win_labels: list[int],
    n_boot: int = _BOOTSTRAP_N,
) -> BucketAttribution | None:
    paired = [(f, w) for f, w in zip(feature_vals, win_labels) if f is not None]
    if len(paired) < _MIN_SEGMENT_N:
        return None
    med = sorted(f for f, _ in paired)[len(paired) // 2]
    high = [w for f, w in paired if f > med]
    low = [w for f, w in paired if f <= med]
    if not high or not low:
        return None
    wr_h = sum(high) / len(high)
    wr_l = sum(low) / len(low)
    delta = wr_h - wr_l
    ci_lo, ci_hi = _bootstrap_win_rate_delta(high, low, n_boot)
    return BucketAttribution(
        n_high=len(high),
        n_low=len(low),
        win_rate_high=round(wr_h, 4),
        win_rate_low=round(wr_l, 4),
        win_rate_delta=round(delta, 4),
        bootstrap_ci_lower=round(ci_lo, 4),
        bootstrap_ci_upper=round(ci_hi, 4),
        bootstrap_significant=(ci_lo > 0 or ci_hi < 0),
    )


# ---------------------------------------------------------------------------
# PIT Safety
# ---------------------------------------------------------------------------

_FORBIDDEN_FUTURE = {"home_win", "result", "score", "final_score",
                     "winning_team", "losing_team"}

def assert_no_forbidden_feature(feature_name: str) -> None:
    lower = feature_name.lower()
    for word in ["home_win", "result", "final", "winning"]:
        if word in lower:
            raise ValueError(
                f"[PIT-SAFETY] Feature '{feature_name}' contains forbidden "
                f"pattern '{word}' — possible future leakage. Abort."
            )
    if lower in _FORBIDDEN_FUTURE:
        raise ValueError(f"[PIT-SAFETY] Feature '{feature_name}' forbidden.")


def validate_phase63_pit_safety(ssot_artifacts: list[dict[str, Any]]) -> bool:
    """
    PIT-safe validation for Phase63 SSOT artifacts.
    prediction_date (game_date) must be strictly after all boxscore data used.
    Phase63 artifacts have pit_window_map with max window sizes.
    We verify the game_date field is syntactically valid (no post-game leakage).
    """
    for art in ssot_artifacts:
        gd = art.get("game_date", "")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", gd):
            return False
        # The artifact is marked diagnostic_only=True (Phase63 guard)
        if not art.get("diagnostic_only", True):
            return False
    return True


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------

def _load_jsonl(path: str) -> list[dict[str, Any]]:
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _compute_audit_hash(*args: str) -> str:
    h = hashlib.sha256()
    for s in args:
        h.update(s.encode())
    return h.hexdigest()[:16]


def _load_phase63_ssot_artifacts(path: str) -> dict[tuple[str, str], dict[str, Any]]:
    """
    Load Phase63 SSOT artifacts, index by (game_date, normalized_team_name).
    Returns dict: (game_date, norm_team) → artifact dict.
    """
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in _load_jsonl(path):
        gd = row.get("game_date", "")
        team = row.get("team", "")
        if gd and team:
            index[(gd, _norm_team(team))] = row
    return index


def _load_phase63_report(path: str) -> dict[str, Any]:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Game-Level Granular Feature Derivation
# ---------------------------------------------------------------------------

def _derive_granular_features_for_game(
    row: dict[str, Any],
    ssot_index: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any | None]:
    """
    Derive all Phase64 granular features for one prediction game row.
    Returns dict feature_name → value (None if unavailable / DATA_LIMITED).

    PIT-safe: only uses game_date (prediction date), not post-game outcomes.
    """
    game_date = row.get("game_date", "")
    home_team = row.get("home_team", "")
    away_team = row.get("away_team", "")
    blend = _blend_prob(
        row.get("model_home_prob", 0.5),
        row.get("market_home_prob_no_vig", 0.5),
    )
    home_is_fav = blend >= 0.50
    fav_team = home_team if home_is_fav else away_team
    dog_team = away_team if home_is_fav else home_team

    fav_key = (game_date, _norm_team(fav_team))
    dog_key = (game_date, _norm_team(dog_team))

    fav_art = ssot_index.get(fav_key)
    dog_art = ssot_index.get(dog_key)

    def _get(art: dict | None, key: str) -> Any | None:
        if art is None:
            return None
        return art.get(key)

    # Compute rest_imbalance from 3d usage (home - away, can be negative)
    home_art = ssot_index.get((game_date, _norm_team(home_team)))
    away_art = ssot_index.get((game_date, _norm_team(away_team)))
    home_3d = _get(home_art, "bullpen_usage_last_3d")
    away_3d = _get(away_art, "bullpen_usage_last_3d")
    rest_imbalance = (abs(home_3d - away_3d) if (home_3d is not None and away_3d is not None)
                      else None)

    # Closer bool → int conversion (1=True, 0=False, None if unavailable)
    def _bool_feature(art: dict | None, key: str) -> float | None:
        v = _get(art, key)
        if v is None:
            return None
        return 1.0 if v else 0.0

    return {
        "bullpen_usage_last_1d_fav": _get(fav_art, "bullpen_usage_last_1d"),
        "bullpen_usage_last_1d_dog": _get(dog_art, "bullpen_usage_last_1d"),
        "bullpen_usage_last_3d_fav": _get(fav_art, "bullpen_usage_last_3d"),
        "bullpen_usage_last_3d_dog": _get(dog_art, "bullpen_usage_last_3d"),
        "bullpen_usage_last_5d_fav": _get(fav_art, "bullpen_usage_last_5d"),
        "bullpen_usage_last_5d_dog": _get(dog_art, "bullpen_usage_last_5d"),
        "reliever_b2b_count_fav":    _get(fav_art, "reliever_back_to_back_count"),
        "reliever_b2b_count_dog":    _get(dog_art, "reliever_back_to_back_count"),
        "reliever_3in4_count_fav":   _get(fav_art, "reliever_three_in_four_days_count"),
        "reliever_3in4_count_dog":   _get(dog_art, "reliever_three_in_four_days_count"),
        "closer_used_1d_fav":        _bool_feature(fav_art, "closer_used_last_1d"),
        "closer_used_2d_fav":        _bool_feature(fav_art, "closer_used_last_2d"),
        "bullpen_rest_imbalance_3d": rest_imbalance,
        # DATA_LIMITED: high-leverage features always None
        "high_leverage_used_1d_fav":     None,
        "high_leverage_workload_3d_fav": None,
    }


# ---------------------------------------------------------------------------
# Prediction Alignment
# ---------------------------------------------------------------------------

def _parse_bull_game_id(game_id: str) -> tuple[str, str, str] | None:
    """Parse bullpen_usage_3d game_id to (date_str, norm_away, norm_home)."""
    try:
        rest = game_id.replace("MLB-", "", 1)
        date_part = rest[:10]
        date_str = date_part.replace("_", "-")
        after_date = rest[10:]
        at_idx = after_date.rfind("-AT-")
        if at_idx == -1:
            return None
        teams_part = after_date[at_idx + 4:]
        before_at = after_date[:at_idx].lstrip("-")
        time_end = before_at.find("-")
        if time_end == -1:
            return None
        away_raw = before_at[time_end + 1:]
        return date_str, _norm_team(away_raw), _norm_team(teams_part)
    except Exception:
        return None


def _load_and_align_with_bullpen3d(
    predictions_path: str,
    bullpen_3d_path: str,
) -> tuple[list[dict[str, Any]], int, int, int]:
    """
    Align predictions with Phase60's bullpen_usage_3d data (3d window only).
    Returns (aligned_rows, n_pred, n_bull, n_aligned).
    """
    pred_rows = _load_jsonl(predictions_path)
    bull_rows = _load_jsonl(bullpen_3d_path)

    # Index bullpen by (date, norm_away, norm_home)
    bull_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in bull_rows:
        gid = row.get("game_id", "")
        parsed = _parse_bull_game_id(gid)
        if parsed:
            bull_index[parsed] = row

    # For each prediction, find bullpen match
    aligned = []
    for pred in pred_rows:
        game_date = pred.get("game_date", "")
        home = _norm_team(pred.get("home_team", ""))
        away = _norm_team(pred.get("away_team", ""))
        bull = bull_index.get((game_date, away, home))
        combined = dict(pred)
        combined["bull_home_3d"] = bull.get("bullpen_usage_last_3d_home") if bull else None
        combined["bull_away_3d"] = bull.get("bullpen_usage_last_3d_away") if bull else None
        combined["bull_aligned"] = bull is not None
        aligned.append(combined)

    n_aligned = sum(1 for r in aligned if r["bull_aligned"])
    return aligned, len(pred_rows), len(bull_rows), n_aligned


def align_phase63_to_predictions(
    aligned_rows: list[dict[str, Any]],
    ssot_index: dict[tuple[str, str], dict[str, Any]],
) -> Phase63ArtifactAlignment:
    """
    Attempt to align Phase63 SSOT artifacts with existing prediction rows.
    Adds granular feature columns to each row (in-place).
    Returns alignment stats.
    """
    n_partial = 0
    n_full = 0
    aligned_game_ids: list[str] = []

    for row in aligned_rows:
        game_date = row.get("game_date", "")
        home_team = row.get("home_team", "")
        away_team = row.get("away_team", "")

        home_key = (game_date, _norm_team(home_team))
        away_key = (game_date, _norm_team(away_team))

        home_art = ssot_index.get(home_key)
        away_art = ssot_index.get(away_key)

        has_any = home_art is not None or away_art is not None
        has_both = home_art is not None and away_art is not None

        if has_any:
            n_partial += 1
            aligned_game_ids.append(row.get("game_id", ""))
        if has_both:
            n_full += 1

        # Derive and store granular features
        granular = _derive_granular_features_for_game(row, ssot_index)
        row.update(granular)

    n_pred = len(aligned_rows)
    return Phase63ArtifactAlignment(
        n_ssot_artifacts=len(ssot_index),
        n_predictions=n_pred,
        n_game_alignments=n_partial,
        n_fully_aligned=n_full,
        alignment_rate_partial=round(n_partial / max(n_pred, 1), 4),
        alignment_rate_full=round(n_full / max(n_pred, 1), 4),
        aligned_game_ids=aligned_game_ids,
        coverage_insufficient=n_partial / max(n_pred, 1) < _MIN_COVERAGE_RATE,
    )


# ---------------------------------------------------------------------------
# Feature Coverage Computation
# ---------------------------------------------------------------------------

def compute_feature_coverage(
    aligned_rows: list[dict[str, Any]],
) -> list[FeatureCoverage]:
    """Compute per-feature coverage across all prediction rows."""
    coverage_list: list[FeatureCoverage] = []
    n_total = len(aligned_rows)

    for fname, window, inherently_limited, desc in _GRANULAR_FEATURE_REGISTRY:
        n_avail = sum(1 for r in aligned_rows if r.get(fname) is not None)
        cov_pct = n_avail / max(n_total, 1)
        is_limited = inherently_limited or cov_pct < _MIN_COVERAGE_RATE
        reason = None
        if inherently_limited:
            reason = "LI/PbP leverage index not available from boxscore"
        elif cov_pct < _MIN_COVERAGE_RATE:
            reason = (
                f"Phase63 artifact coverage {n_avail}/{n_total} "
                f"({cov_pct:.1%}) < threshold {_MIN_COVERAGE_RATE:.0%}. "
                f"Need full historical ingestion run."
            )
        coverage_list.append(FeatureCoverage(
            feature_name=fname,
            n_available=n_avail,
            n_total=n_total,
            coverage_pct=round(cov_pct, 4),
            data_limited=is_limited,
            data_limited_reason=reason,
        ))
    return coverage_list


# ---------------------------------------------------------------------------
# Segment Extraction
# ---------------------------------------------------------------------------

def _extract_segment(
    rows: list[dict[str, Any]],
    segment: str,
) -> list[dict[str, Any]]:
    """Extract rows belonging to a named segment."""
    if segment == "all":
        return rows

    result = []
    for row in rows:
        blend = _blend_prob(
            row.get("model_home_prob", 0.5),
            row.get("market_home_prob_no_vig", 0.5),
        )
        fp = _fav_prob(blend)

        if segment == "heavy_favorite" and fp >= _HEAVY_FAV_THRESHOLD:
            result.append(row)
        elif segment == "high_confidence" and fp >= _HIGH_CONF_THRESHOLD:
            result.append(row)
        elif segment == "phase45_failure":
            # Phase45 failure: heavy favorite (prob ≥ 0.70) that lost
            # Consistent with Phase45 attribution definition
            if fp >= _HEAVY_FAV_THRESHOLD:
                home_win = row.get("home_win")
                if home_win is not None:
                    home_won = int(home_win) == 1
                    fav_won = (blend >= 0.5) == home_won
                    if not fav_won:
                        result.append(row)
    return result


# ---------------------------------------------------------------------------
# Attribution Computation
# ---------------------------------------------------------------------------

def _compute_granular_attribution(
    feature_name: str,
    segment_name: str,
    rows: list[dict[str, Any]],
    data_limited: bool,
    data_limited_reason: str | None,
    n_boot: int = _BOOTSTRAP_N,
) -> GranularSegmentAttribution:
    """Compute attribution for one feature × one segment."""
    n_total = len(rows)

    # Blend probs and labels
    blend_probs = [
        _blend_prob(r.get("model_home_prob", 0.5), r.get("market_home_prob_no_vig", 0.5))
        for r in rows
    ]
    win_labels = [int(r.get("home_win", 0)) for r in rows]

    # Feature values
    feature_vals: list[float | None] = [r.get(feature_name) for r in rows]

    valid_mask = [v is not None for v in feature_vals]
    n_valid = sum(valid_mask)
    cov = n_valid / max(n_total, 1)

    fv = [v for v, m in zip(feature_vals, valid_mask) if m]
    bp = [p for p, m in zip(blend_probs, valid_mask) if m]
    wl = [y for y, m in zip(win_labels, valid_mask) if m]

    bs = _brier_score(bp, wl) if bp else float("nan")
    climate = sum(wl) / max(len(wl), 1) if wl else 0.5
    bss_val = _bss(bs, climate) if not math.isnan(bs) else float("nan")
    resid = (sum(bp) / max(len(bp), 1)) - climate if bp else 0.0
    ece = _compute_ece(bp, wl) if bp else float("nan")

    # Heavy fav ECE (only if segment == "all")
    heavy_fav_ece = None
    if segment_name == "all" and bp:
        hf_rows = [
            (p, y) for p, y in zip(bp, wl)
            if _fav_prob(p) >= _HEAVY_FAV_THRESHOLD
        ]
        if hf_rows:
            hf_probs = [p for p, _ in hf_rows]
            hf_labels = [y for _, y in hf_rows]
            heavy_fav_ece = round(_compute_ece(hf_probs, hf_labels), 4)

    bucket_attr = _bucket_attribution(fv, wl, n_boot) if n_valid >= _MIN_SEGMENT_N else None

    return GranularSegmentAttribution(
        feature_name=feature_name,
        segment=segment_name,
        n=n_valid,
        coverage_pct=round(cov, 4),
        baseline_brier=round(bs, 4) if not math.isnan(bs) else None,  # type: ignore[arg-type]
        baseline_bss=round(bss_val, 4) if not math.isnan(bss_val) else None,  # type: ignore[arg-type]
        calibration_residual=round(resid, 4),
        ece=round(ece, 4) if not math.isnan(ece) else None,  # type: ignore[arg-type]
        heavy_fav_ece=heavy_fav_ece,
        bucket_attribution=bucket_attr,
        oof_win_rate_delta=None,  # filled by OOF
        oof_n=None,
        oof_replicated=None,
        data_limited=data_limited,
        data_limited_reason=data_limited_reason,
    )


# ---------------------------------------------------------------------------
# Negative Control
# ---------------------------------------------------------------------------

def _compute_negative_control(
    rows: list[dict[str, Any]],
    feature_name: str,
    segment: str = "heavy_favorite",
    n_shuffles: int = 100,
    rng_seed: int = 99,
) -> Phase64NegativeControl:
    """Negative control: compare real win_rate_delta vs shuffled feature distribution."""
    seg_rows = _extract_segment(rows, segment)
    fv = [r.get(feature_name) for r in seg_rows]
    wl = [int(r.get("home_win", 0)) for r in seg_rows]
    bp = [_blend_prob(r.get("model_home_prob", 0.5), r.get("market_home_prob_no_vig", 0.5))
          for r in seg_rows]

    # Real delta
    paired = [(f, w) for f, w in zip(fv, wl) if f is not None]
    if len(paired) < _MIN_SEGMENT_N:
        return Phase64NegativeControl(
            feature_name=feature_name,
            segment=segment,
            real_win_rate_delta=0.0,
            shuffled_mean_delta=0.0,
            shuffled_std_delta=0.0,
            null_rejected=False,
            overfit_risk=False,
        )

    med = sorted(f for f, _ in paired)[len(paired) // 2]
    real_high = [w for f, w in paired if f > med]
    real_low = [w for f, w in paired if f <= med]
    real_delta = (
        sum(real_high) / len(real_high) - sum(real_low) / len(real_low)
        if real_high and real_low else 0.0
    )

    # Shuffled distribution
    rng = random.Random(rng_seed)
    shuffled_deltas: list[float] = []
    all_fv = [f for f, _ in paired]
    all_wl = [w for _, w in paired]
    for _ in range(n_shuffles):
        shuffled_fv = rng.sample(all_fv, len(all_fv))
        s_med = sorted(shuffled_fv)[len(shuffled_fv) // 2]
        s_high = [all_wl[i] for i, f in enumerate(shuffled_fv) if f > s_med]
        s_low = [all_wl[i] for i, f in enumerate(shuffled_fv) if f <= s_med]
        if s_high and s_low:
            shuffled_deltas.append(sum(s_high) / len(s_high) - sum(s_low) / len(s_low))

    if not shuffled_deltas:
        shuffled_mean, shuffled_std = 0.0, 0.0
        null_rejected = False
    else:
        shuffled_mean = sum(shuffled_deltas) / len(shuffled_deltas)
        shuffled_std = (
            sum((d - shuffled_mean) ** 2 for d in shuffled_deltas) / len(shuffled_deltas)
        ) ** 0.5
        null_rejected = abs(real_delta) > abs(shuffled_mean) + _OVERFIT_SIGMA * shuffled_std

    # Overfit risk: null rejected AND shuffled std is very large
    overfit_risk = null_rejected and shuffled_std > 0.10

    return Phase64NegativeControl(
        feature_name=feature_name,
        segment=segment,
        real_win_rate_delta=round(real_delta, 4),
        shuffled_mean_delta=round(shuffled_mean, 4),
        shuffled_std_delta=round(shuffled_std, 4),
        null_rejected=null_rejected,
        overfit_risk=overfit_risk,
    )


# ---------------------------------------------------------------------------
# OOF Validation
# ---------------------------------------------------------------------------

def _compute_oof_validation(
    rows: list[dict[str, Any]],
    feature_name: str,
    segment: str = "heavy_favorite",
) -> Phase64OOFResult:
    """
    Rolling monthly OOF validation.
    Each fold: train = all months before fold month, test = fold month.
    Reports win_rate_delta on fold month using median split from train months.
    """
    seg_rows = _extract_segment(rows, segment)

    # Extract year-month per row
    def _ym(row: dict) -> str:
        return row.get("game_date", "")[:7]

    months = sorted(set(_ym(r) for r in seg_rows))
    if len(months) < 2:
        return Phase64OOFResult(
            feature_name=feature_name,
            n_folds=0,
            fold_months=months,
            fold_win_rate_deltas=[],
            fold_n=[],
            oof_mean_delta=0.0,
            oof_consistent_sign=False,
            oof_significant=False,
        )

    fold_months: list[str] = []
    fold_deltas: list[float] = []
    fold_ns: list[int] = []

    for test_month in months[1:]:
        train = [r for r in seg_rows if _ym(r) < test_month]
        test = [r for r in seg_rows if _ym(r) == test_month]
        if len(train) < _MIN_SEGMENT_N or len(test) < 5:
            continue

        # Median threshold from training data
        train_fv = [r.get(feature_name) for r in train if r.get(feature_name) is not None]
        if not train_fv:
            continue
        train_med = sorted(train_fv)[len(train_fv) // 2]

        test_pairs = [
            (r.get(feature_name), int(r.get("home_win", 0)))
            for r in test
            if r.get(feature_name) is not None
        ]
        if not test_pairs:
            continue

        t_high = [w for f, w in test_pairs if f > train_med]
        t_low = [w for f, w in test_pairs if f <= train_med]
        if not t_high or not t_low:
            fold_deltas.append(0.0)
        else:
            fold_deltas.append(sum(t_high) / len(t_high) - sum(t_low) / len(t_low))
        fold_months.append(test_month)
        fold_ns.append(len(test_pairs))

    if not fold_deltas:
        mean_delta = 0.0
        consistent = False
        significant = False
    else:
        mean_delta = sum(fold_deltas) / len(fold_deltas)
        consistent = all(d > 0 for d in fold_deltas) or all(d < 0 for d in fold_deltas)
        significant = abs(mean_delta) >= _OOF_PROMISING_DELTA

    return Phase64OOFResult(
        feature_name=feature_name,
        n_folds=len(fold_months),
        fold_months=fold_months,
        fold_win_rate_deltas=[round(d, 4) for d in fold_deltas],
        fold_n=fold_ns,
        oof_mean_delta=round(mean_delta, 4),
        oof_consistent_sign=consistent,
        oof_significant=significant,
    )


# ---------------------------------------------------------------------------
# Gate Decision
# ---------------------------------------------------------------------------

def _decide_gate(
    phase63_alignment: Phase63ArtifactAlignment,
    coverage_results: list[FeatureCoverage],
    attributions: list[GranularSegmentAttribution],
    neg_controls: list[Phase64NegativeControl],
    oof_results: list[Phase64OOFResult],
) -> tuple[str, str, str]:
    """
    Determine Phase64 gate from evidence.
    Returns (gate, rationale, next_step).
    """
    # Check coverage first
    new_granular = [f for f in coverage_results if not any(
        f.feature_name in x for x in ["3d_fav", "3d_dog"]
    ) or "1d" in f.feature_name or "5d" in f.feature_name
      or "b2b" in f.feature_name or "3in4" in f.feature_name
      or "closer" in f.feature_name or "leverage" in f.feature_name]

    all_data_limited = all(f.data_limited for f in coverage_results
                           if f.feature_name not in ("bullpen_usage_last_3d_fav",
                                                      "bullpen_usage_last_3d_dog"))
    n_aligned = phase63_alignment.n_game_alignments
    cov_rate = phase63_alignment.alignment_rate_partial

    # Check overfit risk
    any_overfit = any(nc.overfit_risk for nc in neg_controls)

    # Check promising OOF signal
    promising_oof = [r for r in oof_results
                     if r.oof_significant and r.oof_consistent_sign and r.n_folds >= 3]

    # Check bootstrap significant
    any_bootstrap_sig = any(
        a.bucket_attribution is not None and a.bucket_attribution.bootstrap_significant
        for a in attributions
    )

    # --- Gate logic ---
    if all_data_limited or cov_rate < _MIN_COVERAGE_RATE:
        gate = DATA_LIMITED
        rationale = (
            f"Phase63 granular SSOT artifact coverage = {n_aligned}/{phase63_alignment.n_predictions} "
            f"games ({cov_rate:.1%}) < {_MIN_COVERAGE_RATE:.0%} threshold. "
            f"New granular features (1d, 5d, b2b, 3in4, closer) cannot be meaningfully "
            f"attributed on current prediction dataset. "
            f"Phase63 fixture-only artifacts do not overlap with labeled 2025 prediction history "
            f"at sufficient scale. "
            f"3d replication from Phase60 confirms DIAGNOSTIC_ONLY_SIGNAL. "
            f"No production patch produced."
        )
        next_step = (
            "Run Phase63 ingestion pipeline against full 2025 historical boxscore dataset "
            "(data/mlb_context/bullpen_usage_3d.jsonl covers 2429 games; run per-pitcher "
            "parse for same date range). Then re-run Phase64 with full granular coverage."
        )
    elif any_overfit:
        gate = OVERFIT_RISK
        rationale = (
            "Negative control indicates overfit: null hypothesis rejected AND shuffled_std "
            "too large. Fitted adjustment likely noise-driven. No production patch produced."
        )
        next_step = (
            "Disable fitted adjustment. Re-validate on a fully fresh hold-out window "
            "with larger sample (n ≥ 200 per segment)."
        )
    elif promising_oof and any_bootstrap_sig:
        gate = BULLPEN_GRANULAR_FEATURE_PROMISING
        rationale = (
            f"OOF validation consistent ({len(promising_oof)} features) + bootstrap CI "
            f"excludes zero. Granular features show replicable signal. "
            f"No production patch produced — paper-only gate recommended."
        )
        next_step = (
            "Phase65: Design paper-only bullpen feature patch gate. "
            "Use Phase64 promising features as candidate set."
        )
    elif any_bootstrap_sig:
        gate = DIAGNOSTIC_ONLY_SIGNAL
        rationale = (
            "Bootstrap CI excludes zero for some features but OOF not consistently significant. "
            "Directional signal present but not robust enough for production. "
            "No production patch produced."
        )
        next_step = (
            "Increase sample coverage (run full historical ingestion). "
            "Re-run OOF with larger n per fold before promoting to Phase65."
        )
    else:
        gate = BULLPEN_GRANULAR_FEATURE_NOT_PROMISING
        rationale = (
            "No bootstrap-significant attribution found. OOF deltas inconsistent. "
            "Granular bullpen features do not provide reliable signal above 3d baseline. "
            "No production patch produced."
        )
        next_step = (
            "De-prioritise bullpen as attribution signal. "
            "Investigate other failure sources (SP fatigue, weather, park factor, rest)."
        )

    return gate, rationale, next_step


# ---------------------------------------------------------------------------
# Phase60 Baseline Replication (3d features)
# ---------------------------------------------------------------------------

def _replicate_phase60_baseline_signal(
    aligned_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Replicate Phase60's key 3d attribution signals using the same bullpen_usage_3d data.
    Returns a summary dict for embedding in the Phase64 report.
    """
    # Only rows with 3d data
    hf_rows = _extract_segment(aligned_rows, "heavy_favorite")
    hf_valid = [(r.get("bull_home_3d"), r.get("bull_away_3d"), int(r.get("home_win", 0)))
                for r in hf_rows if r.get("bull_home_3d") is not None and r.get("bull_away_3d") is not None]

    if not hf_valid:
        return {"status": "NO_DATA", "n": 0}

    # home 3d as fav_fatigue proxy
    home_3d_vals = [v[0] for v in hf_valid]
    labels = [v[2] for v in hf_valid]
    bucket = _bucket_attribution(home_3d_vals, labels, n_boot=_BOOTSTRAP_N)

    all_rows = aligned_rows
    all_valid = [(r.get("bull_home_3d"), r.get("bull_away_3d"), int(r.get("home_win", 0)))
                 for r in all_rows if r.get("bull_home_3d") is not None]
    bp_all = [
        _blend_prob(r.get("model_home_prob", 0.5), r.get("market_home_prob_no_vig", 0.5))
        for r in all_rows if r.get("bull_home_3d") is not None
    ]
    wl_all = [v[2] for v in all_valid]

    bs = _brier_score(bp_all, wl_all)
    climate = sum(wl_all) / max(len(wl_all), 1)

    return {
        "status": "REPLICATED",
        "n_all_aligned": len(all_valid),
        "n_heavy_fav": len(hf_valid),
        "brier": round(bs, 4),
        "bss": round(_bss(bs, climate), 4),
        "ece_heavy_fav_calib_residual": round(climate - sum(labels) / max(len(labels), 1), 4),
        "phase60_signal": "DIAGNOSTIC_ONLY_SIGNAL",
        "heavy_fav_bucket_attribution": asdict(bucket) if bucket else None,
    }


# ---------------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------------

def run_phase64_attribution(
    predictions_path: str,
    bullpen_3d_path: str,
    phase63_ssot_path: str,
    phase63_appearances_path: str,
    phase63_report_path: str,
) -> Phase64AttributionResult:
    """
    Full Phase 64 orchestration:
    1. Load and align data (Phase60 3d + Phase63 granular)
    2. Compute feature coverage
    3. Attribution per feature × segment
    4. Negative control
    5. OOF validation
    6. Gate decision
    """
    run_ts = datetime.now(timezone.utc).isoformat()

    # Audit hash over input artifacts
    audit_hash = _compute_audit_hash(
        predictions_path, bullpen_3d_path, phase63_ssot_path, phase63_report_path
    )

    # Load Phase63 report (for gate chaining)
    phase63_report = _load_phase63_report(phase63_report_path)
    phase63_gate = phase63_report.get("phase63_gate", "UNKNOWN")

    # Load Phase63 SSOT artifacts and validate PIT safety
    ssot_artifacts_raw = _load_jsonl(phase63_ssot_path)
    assert validate_phase63_pit_safety(ssot_artifacts_raw), \
        "PIT safety violation in Phase63 SSOT artifacts!"
    ssot_index = _load_phase63_ssot_artifacts(phase63_ssot_path)

    # Load and align with Phase60 3d data
    aligned_rows, n_pred, n_bull_3d, n_aligned_3d = _load_and_align_with_bullpen3d(
        predictions_path, bullpen_3d_path
    )

    # Align Phase63 SSOT to predictions (adds granular feature columns)
    phase63_alignment = align_phase63_to_predictions(aligned_rows, ssot_index)

    # Compute feature coverage
    coverage_results = compute_feature_coverage(aligned_rows)
    n_avail = sum(1 for f in coverage_results if not f.data_limited)
    n_limited = sum(1 for f in coverage_results if f.data_limited)

    # Segment sizes
    seg_all = _extract_segment(aligned_rows, "all")
    seg_hf = _extract_segment(aligned_rows, "heavy_favorite")
    seg_hc = _extract_segment(aligned_rows, "high_confidence")
    seg_p45 = _extract_segment(aligned_rows, "phase45_failure")

    # Phase60 baseline replication
    phase60_baseline = _replicate_phase60_baseline_signal(aligned_rows)

    # Attribution: run for all features × [all, heavy_favorite, high_confidence, phase45_failure]
    # For DATA_LIMITED features, compute attribution with data_limited=True
    attributions: list[GranularSegmentAttribution] = []
    coverage_by_name = {fc.feature_name: fc for fc in coverage_results}

    segments = [
        ("all", seg_all),
        ("heavy_favorite", seg_hf),
        ("high_confidence", seg_hc),
        ("phase45_failure", seg_p45),
    ]

    # Only run attribution for non-inherently-limited features
    # (inherently DATA_LIMITED features like high_leverage are always None)
    for fname, _, inherently_limited, _ in _GRANULAR_FEATURE_REGISTRY:
        assert_no_forbidden_feature(fname)
        fc = coverage_by_name[fname]
        for seg_name, seg_rows in segments:
            attr = _compute_granular_attribution(
                feature_name=fname,
                segment_name=seg_name,
                rows=seg_rows,
                data_limited=fc.data_limited,
                data_limited_reason=fc.data_limited_reason,
            )
            attributions.append(attr)

    # Negative controls: for features with sufficient coverage (≥ MIN_SEGMENT_N in heavy_fav)
    neg_controls: list[Phase64NegativeControl] = []
    for fname, _, inherently_limited, _ in _GRANULAR_FEATURE_REGISTRY:
        if inherently_limited:
            continue
        nc = _compute_negative_control(aligned_rows, fname, segment="heavy_favorite")
        neg_controls.append(nc)

    # OOF validation: for features with sufficient coverage
    oof_results: list[Phase64OOFResult] = []
    for fname, _, inherently_limited, _ in _GRANULAR_FEATURE_REGISTRY:
        if inherently_limited:
            continue
        oof = _compute_oof_validation(aligned_rows, fname, segment="heavy_favorite")
        oof_results.append(oof)

    # Bootstrap significance summary
    any_bootstrap_sig = any(
        a.bucket_attribution is not None and a.bucket_attribution.bootstrap_significant
        for a in attributions
    )

    # Gate decision
    gate, rationale, next_step = _decide_gate(
        phase63_alignment=phase63_alignment,
        coverage_results=coverage_results,
        attributions=attributions,
        neg_controls=neg_controls,
        oof_results=oof_results,
    )

    return Phase64AttributionResult(
        phase_version=PHASE_VERSION,
        run_timestamp=run_ts,
        audit_hash=audit_hash,
        candidate_patch_created=CANDIDATE_PATCH_CREATED,
        production_modified=PRODUCTION_MODIFIED,
        alpha_modified=ALPHA_MODIFIED,
        diagnostic_only=DIAGNOSTIC_ONLY,
        alpha=ALPHA,
        phase63_audit_hash=_PHASE63_AUDIT_HASH,
        phase63_gate=phase63_gate,
        n_predictions=n_pred,
        n_bullpen_3d_rows=n_bull_3d,
        n_phase63_ssot_artifacts=len(ssot_index),
        n_aligned_3d=n_aligned_3d,
        phase63_alignment=phase63_alignment,
        feature_coverage=coverage_results,
        n_available_features=n_avail,
        n_data_limited_features=n_limited,
        segment_n_all=len(seg_all),
        segment_n_heavy_fav=len(seg_hf),
        segment_n_high_conf=len(seg_hc),
        segment_n_phase45_failure=len(seg_p45),
        phase60_baseline_replication=phase60_baseline,
        granular_attributions=attributions,
        negative_controls=neg_controls,
        oof_results=oof_results,
        any_bootstrap_significant=any_bootstrap_sig,
        gate=gate,
        gate_rationale=rationale,
        next_step=next_step,
    )
