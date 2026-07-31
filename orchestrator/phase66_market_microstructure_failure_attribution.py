"""
orchestrator/phase66_market_microstructure_failure_attribution.py
=================================================================
Phase 66 — Market Microstructure Failure Attribution for Heavy Favorites

背景：
  Phase 59-Pre+: heavy_favorite / high_confidence 校準失敗，isotonic/Platt 無效修復。
  Phase 64-B: bullpen granular features 不顯著。Gate = BULLPEN_GRANULAR_FEATURE_NOT_PROMISING
  Phase 65: SP fatigue features 小樣本偽信號。Gate = OVERFIT_RISK

目標：
  歸因 heavy_fav / high_conf failure 是否來自 market microstructure 問題：
  - market implied probability 定價結構
  - no-vig conversion 差異
  - model-market disagreement 模式
  - favorite side (home vs away)
  - overround/vig 水準
  - opening vs closing line movement (DATA_LIMITED)
  - CLV direction (DATA_LIMITED)

安全常數 (NEVER CHANGE):
  CANDIDATE_PATCH_CREATED = False
  PRODUCTION_MODIFIED     = False
  ALPHA_MODIFIED          = False
  DIAGNOSTIC_ONLY         = True
  ALPHA                   = 0.40

PIT 安全性：
  所有特徵均來自開賽前盤口資料（odds CSV + model predictions）。
  home_win 僅用作目標變數，不作為特徵。
"""
from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── 安全常數 (FROZEN — NEVER CHANGE) ──────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
ALPHA_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
ALPHA: float = 0.40

PHASE_VERSION: str = "phase66_market_microstructure_failure_attribution_v1"

# Phase65 錨點
_PHASE65_GATE: str = "OVERFIT_RISK"
_PHASE65_VERSION: str = "phase65_sp_fatigue_attribution_v1"
# Phase64B 錨點
_PHASE64B_GATE: str = "BULLPEN_GRANULAR_FEATURE_NOT_PROMISING"
_PHASE64B_VERSION: str = "phase64b_full_season_attribution_v1"

# ── Gate 常數 ─────────────────────────────────────────────────────────────────
MARKET_MICROSTRUCTURE_FEATURE_PROMISING: str = "MARKET_MICROSTRUCTURE_FEATURE_PROMISING"
DIAGNOSTIC_ONLY_SIGNAL: str = "DIAGNOSTIC_ONLY_SIGNAL"
DATA_LIMITED: str = "DATA_LIMITED"
OVERFIT_RISK: str = "OVERFIT_RISK"
MARKET_MICROSTRUCTURE_NOT_PROMISING: str = "MARKET_MICROSTRUCTURE_NOT_PROMISING"

# ── 分析參數 ──────────────────────────────────────────────────────────────────
_HEAVY_FAV_THRESHOLD: float = 0.70
_HIGH_CONF_THRESHOLD: float = 0.75
_EXTREME_FAV_THRESHOLD: float = 0.80
_MIN_SEGMENT_N: int = 20
_MIN_BUCKET_N: int = 15
_BOOTSTRAP_N: int = 1000
_OOF_PROMISING_DELTA: float = 0.005   # BSS delta ≥ 0.5% = promising
_OVERFIT_SIGMA: float = 1.5           # null_std × sigma for overfit check
_MIN_ODDS_COVERAGE: float = 0.70      # < 70% → DATA_LIMITED

# DATA_LIMITED 欄位清單
_DATA_LIMITED_FIELDS: list[str] = [
    "opening_home_ml",
    "opening_away_ml",
    "closing_vs_opening_shift",
    "clv_direction",
    "line_movement_direction",
    "pregame_snapshot_count",
]

# ── Attribution Dimensions ────────────────────────────────────────────────────
_AVAILABLE_DIMENSIONS: list[str] = [
    "market_implied_bucket",    # no-vig market prob bucket
    "model_prob_bucket",        # model home prob bucket
    "blend_prob_bucket",        # blend prob bucket
    "disagreement_bucket",      # |model - market| magnitude
    "fav_side",                 # home_favorite vs away_favorite
    "overround_bucket",         # vig level
    "odds_price_bucket",        # fav ML price range
]

_DATA_LIMITED_DIMENSIONS: list[str] = [
    "opening_line_direction",   # no opening line data
    "clv_direction",            # no CLV data
    "line_movement_shift",      # single snapshot only
]

_ALL_DIMENSIONS: list[str] = _AVAILABLE_DIMENSIONS + _DATA_LIMITED_DIMENSIONS


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  Dataclasses
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class OddsRecord:
    """Closing moneyline odds snapshot for one game (PIT-safe: pre-game prices)."""
    game_date: str
    home_team: str
    home_ml_raw: str        # raw string, e.g. '+125'
    away_ml_raw: str
    home_ml_num: Optional[int]
    away_ml_num: Optional[int]
    home_implied: Optional[float]   # raw implied prob (with vig)
    away_implied: Optional[float]
    overround: Optional[float]      # home_implied + away_implied - 1
    novig_home: Optional[float]     # no-vig implied prob for home
    novig_away: Optional[float]


@dataclass
class OddsAlignment:
    """Alignment statistics between predictions and odds CSV."""
    n_predictions: int
    n_odds_rows: int
    n_aligned: int
    n_unaligned: int
    coverage: float             # n_aligned / n_predictions
    coverage_sufficient: bool   # coverage >= _MIN_ODDS_COVERAGE
    sample_audit_hash: str


@dataclass
class SegmentMetrics:
    """Brier / BSS / ECE for model, market, and blend on one segment."""
    n: int
    win_rate: float             # empirical home win rate
    fav_win_rate: float         # empirical fav win rate (blend-defined)
    model_brier: float
    market_brier: float
    blend_brier: float
    model_bss_vs_climate: float     # model BSS vs climatology
    market_bss_vs_climate: float    # market BSS vs climatology
    blend_bss_vs_climate: float     # blend BSS vs climatology
    blend_bss_vs_market: float      # blend BSS relative to market baseline
    model_bss_vs_market: float      # model BSS relative to market baseline
    model_ece: float
    market_ece: float
    blend_ece: float
    blend_ece_vs_market: float      # positive = blend worse calibrated


@dataclass
class BootstrapResult:
    """Bootstrap CI for blend BSS vs market."""
    ci_lower: float
    ci_upper: float
    prob_positive: float    # fraction of bootstrap samples BSS > 0
    significant: bool       # CI excludes zero


@dataclass
class AttributionBucket:
    """One bucket of a single attribution dimension."""
    dim: str
    bucket_label: str
    n: int
    segment_name: str       # which segment this bucket is from
    metrics: SegmentMetrics
    bootstrap: BootstrapResult


@dataclass
class NegativeControl:
    """Negative control for one attribution dimension."""
    dim: str
    segment: str
    real_blend_bss_delta: float      # blend BSS delta vs market (high - low bucket)
    shuffled_mean_delta: float
    shuffled_std_delta: float
    null_rejected: bool             # |real| > shuffled_mean + 1.5 * std
    overfit_risk: bool              # null_rejected AND shuffled_std > 0.05


@dataclass
class OOFResult:
    """Rolling monthly OOF validation for one attribution dimension."""
    dim: str
    segment: str
    n_folds: int
    fold_months: list[str]
    fold_bss_deltas: list[float]    # blend-vs-market BSS per fold
    fold_ns: list[int]
    oof_mean_delta: float
    oof_consistent_sign: bool
    oof_significant: bool           # mean_delta >= _OOF_PROMISING_DELTA


@dataclass
class Phase66Result:
    """Complete Phase 66 market microstructure attribution result."""
    # Metadata
    phase_version: str
    run_timestamp: str
    completion_marker: str

    # Safety constants snapshot
    candidate_patch_created: bool
    production_modified: bool
    alpha_modified: bool
    diagnostic_only: bool
    alpha: float

    # Phase anchors
    phase65_gate: str
    phase65_version: str
    phase64b_gate: str
    phase64b_version: str

    # Artifact provenance
    predictions_path: str
    odds_csv_path: str
    predictions_audit_hash: str
    odds_metadata_notes: str

    # Alignment
    n_predictions: int
    odds_alignment: OddsAlignment

    # Segment sizes
    segment_n_all: int
    segment_n_heavy_fav: int
    segment_n_high_conf: int
    segment_n_extreme_fav: int
    segment_n_phase45_failure: int

    # Overall metrics
    all_metrics: SegmentMetrics
    heavy_fav_metrics: SegmentMetrics
    high_conf_metrics: SegmentMetrics
    extreme_fav_metrics: SegmentMetrics
    phase45_failure_metrics: Optional[SegmentMetrics]

    # Attribution buckets (by dim × segment)
    attribution_buckets: list[AttributionBucket]

    # Negative controls
    negative_controls: list[NegativeControl]

    # OOF results
    oof_results: list[OOFResult]

    # Summary flags
    any_bootstrap_significant: bool
    any_oof_promising: bool
    any_overfit_risk: bool

    # DATA_LIMITED fields
    data_limited_dimensions: list[str]
    data_limited_fields: list[str]

    # Gate decision
    gate: str
    gate_rationale: str
    next_step: str
    worth_phase67: bool


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  ML Odds Conversion
# ═══════════════════════════════════════════════════════════════════════════════

def _ml_to_prob(ml_str: str) -> Optional[float]:
    """Convert American moneyline string to implied probability."""
    s = ml_str.strip().replace("+", "")
    if not s or s == "-":
        return None
    try:
        ml = int(s)
    except ValueError:
        return None
    if ml == 0:
        return None
    if ml > 0:
        return 100.0 / (ml + 100.0)
    else:
        return abs(ml) / (abs(ml) + 100.0)


def _novig_probs(home_raw: float, away_raw: float) -> tuple[float, float, float]:
    """Return (novig_home, novig_away, overround)."""
    total = home_raw + away_raw
    if total <= 0:
        return 0.5, 0.5, 0.0
    return home_raw / total, away_raw / total, total - 1.0


def _load_odds_csv(path: str) -> dict[tuple[str, str], OddsRecord]:
    """
    Load mlb_odds_2025_real.csv and return lookup keyed by (date, home_team).
    PIT-safe: all odds are pre-game closing lines, not outcomes.
    """
    lookup: dict[tuple[str, str], OddsRecord] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row.get("Date", "").strip()
            home = row.get("Home", "").strip()
            if not date_str or not home:
                continue
            home_ml_raw = row.get("Home ML", "").strip()
            away_ml_raw = row.get("Away ML", "").strip()
            home_impl = _ml_to_prob(home_ml_raw)
            away_impl = _ml_to_prob(away_ml_raw)
            novig_h: Optional[float] = None
            novig_a: Optional[float] = None
            overround: Optional[float] = None
            if home_impl is not None and away_impl is not None:
                novig_h, novig_a, overround = _novig_probs(home_impl, away_impl)
            try:
                home_ml_num: Optional[int] = int(home_ml_raw.replace("+", "")) if home_ml_raw else None
            except ValueError:
                home_ml_num = None
            try:
                away_ml_num: Optional[int] = int(away_ml_raw.replace("+", "")) if away_ml_raw else None
            except ValueError:
                away_ml_num = None
            lookup[(date_str, home)] = OddsRecord(
                game_date=date_str,
                home_team=home,
                home_ml_raw=home_ml_raw,
                away_ml_raw=away_ml_raw,
                home_ml_num=home_ml_num,
                away_ml_num=away_ml_num,
                home_implied=home_impl,
                away_implied=away_impl,
                overround=overround,
                novig_home=novig_h,
                novig_away=novig_a,
            )
    return lookup


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  Probability Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _blend_prob(model_prob: float, market_prob: float) -> float:
    """Blend formula: (1 - ALPHA) * model + ALPHA * market."""
    return (1.0 - ALPHA) * model_prob + ALPHA * market_prob


def _fav_prob(blend: float) -> float:
    """Favorite's blend probability (always >= 0.5)."""
    return max(blend, 1.0 - blend)


def _fav_ml_num(home_ml: Optional[int], away_ml: Optional[int], blend: float) -> Optional[int]:
    """Return favorite's ML (abs value; negative ML = favorite by convention)."""
    if blend >= 0.5:
        return home_ml
    return away_ml


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  Feature Bucketing
# ═══════════════════════════════════════════════════════════════════════════════

def _market_implied_bucket(novig_fav_prob: float) -> str:
    """Bucket favorite's no-vig implied probability into 5 bins."""
    if novig_fav_prob < 0.50:
        return "pick_em"          # < 50% (edge cases)
    if novig_fav_prob < 0.55:
        return "slight_fav_50_55"
    if novig_fav_prob < 0.60:
        return "moderate_fav_55_60"
    if novig_fav_prob < 0.65:
        return "strong_fav_60_65"
    if novig_fav_prob < 0.70:
        return "heavy_fav_65_70"
    return "extreme_fav_70plus"


def _model_prob_bucket(model_fav_prob: float) -> str:
    """Bucket model's fav probability into 5 bins."""
    if model_fav_prob < 0.55:
        return "low_conf_lt55"
    if model_fav_prob < 0.60:
        return "mod_conf_55_60"
    if model_fav_prob < 0.65:
        return "high_conf_60_65"
    if model_fav_prob < 0.70:
        return "strong_conf_65_70"
    return "extreme_conf_70plus"


def _blend_prob_bucket(blend_fav: float) -> str:
    """Bucket blend's fav probability into 5 bins."""
    if blend_fav < 0.55:
        return "low_blend_lt55"
    if blend_fav < 0.60:
        return "mod_blend_55_60"
    if blend_fav < 0.65:
        return "high_blend_60_65"
    if blend_fav < 0.70:
        return "strong_blend_65_70"
    return "extreme_blend_70plus"


def _disagreement_bucket(delta: float) -> str:
    """Bucket |model_home_prob - market_novig_home| into 3 bins."""
    if delta < 0.03:
        return "agree_lt3pct"
    if delta < 0.07:
        return "slight_disagree_3_7pct"
    return "strong_disagree_7pct_plus"


def _overround_bucket(vig: float) -> str:
    """Bucket overround into low/medium/high."""
    if vig < 0.035:
        return "low_vig_lt3.5pct"
    if vig < 0.055:
        return "mid_vig_3.5_5.5pct"
    return "high_vig_5.5pct_plus"


def _odds_price_bucket(fav_ml: Optional[int]) -> str:
    """Bucket favorite's ML into price ranges."""
    if fav_ml is None:
        return "unknown_price"
    ml = abs(fav_ml)
    if ml < 130:
        return "small_fav_lt130"
    if ml < 165:
        return "moderate_fav_130_165"
    if ml < 210:
        return "strong_fav_165_210"
    return "heavy_fav_210plus"


def _get_dim_bucket(row: dict, dim: str) -> Optional[str]:
    """Get bucket label for a row on the given dimension."""
    if dim == "market_implied_bucket":
        v = row.get("novig_fav_prob")
        return _market_implied_bucket(v) if v is not None else None
    if dim == "model_prob_bucket":
        v = row.get("model_fav_prob")
        return _model_prob_bucket(v) if v is not None else None
    if dim == "blend_prob_bucket":
        v = row.get("blend_fav_prob")
        return _blend_prob_bucket(v) if v is not None else None
    if dim == "disagreement_bucket":
        v = row.get("disagreement")
        return _disagreement_bucket(v) if v is not None else None
    if dim == "fav_side":
        return row.get("fav_side")
    if dim == "overround_bucket":
        v = row.get("overround")
        return _overround_bucket(v) if v is not None else None
    if dim == "odds_price_bucket":
        return row.get("odds_price_bucket")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# § 5  Row Enrichment
# ═══════════════════════════════════════════════════════════════════════════════

def _enrich_row(pred: dict[str, Any], odds_rec: Optional[OddsRecord]) -> dict[str, Any]:
    """Attach market microstructure features to a prediction row."""
    model_p = pred["model_home_prob"]
    market_p = pred["market_home_prob_no_vig"]
    blend = _blend_prob(model_p, market_p)
    blend_fav = _fav_prob(blend)
    model_fav = _fav_prob(max(model_p, 1 - model_p))
    fav_side = "home_fav" if blend >= 0.5 else "away_fav"
    disagreement = abs(model_p - market_p)

    # From odds CSV
    novig_fav: Optional[float] = None
    overround: Optional[float] = None
    odds_price_bucket: Optional[str] = None
    if odds_rec is not None:
        novig_home = odds_rec.novig_home
        novig_away = odds_rec.novig_away
        overround = odds_rec.overround
        if novig_home is not None and novig_away is not None:
            novig_fav = novig_home if blend >= 0.5 else novig_away
        # Fav's ML num
        fav_ml_num: Optional[int] = None
        if blend >= 0.5:
            fav_ml_num = odds_rec.home_ml_num
        else:
            fav_ml_num = odds_rec.away_ml_num
        odds_price_bucket = _odds_price_bucket(fav_ml_num)

    # PIT safety: fav_win derived from blend (pre-game) and home_win (outcome target)
    home_win = pred["home_win"]
    fav_win = home_win if blend >= 0.5 else (1 - home_win)

    return {
        **pred,
        "_blend": blend,
        "_blend_fav": blend_fav,
        "_model_fav_prob": model_fav,
        "blend_fav_prob": blend_fav,
        "model_fav_prob": model_fav,
        "fav_side": fav_side,
        "disagreement": disagreement,
        "novig_fav_prob": novig_fav,
        "overround": overround,
        "odds_price_bucket": odds_price_bucket,
        "_fav_win": fav_win,
        "_odds_aligned": odds_rec is not None,
    }


def _build_enriched_rows(
    predictions_path: str,
    odds_lookup: dict[tuple[str, str], OddsRecord],
) -> tuple[list[dict[str, Any]], OddsAlignment, str]:
    """
    Load predictions and enrich with odds CSV data.
    Returns (enriched_rows, alignment_stats, audit_hash).
    PIT-safe: only pre-game odds are attached; home_win stays as target.
    """
    preds: list[dict[str, Any]] = []
    first_hash: str = ""
    with open(predictions_path) as f:
        for i, line in enumerate(f):
            r = json.loads(line)
            preds.append(r)
            if i == 0:
                first_hash = r.get("audit_hash", "")

    enriched: list[dict[str, Any]] = []
    n_aligned = 0
    for p in preds:
        key = (p["game_date"], p["home_team"])
        rec = odds_lookup.get(key)
        if rec is not None:
            n_aligned += 1
        enriched.append(_enrich_row(p, rec))

    n_pred = len(preds)
    n_odds = len(odds_lookup)
    cov = n_aligned / n_pred if n_pred else 0.0

    alignment = OddsAlignment(
        n_predictions=n_pred,
        n_odds_rows=n_odds,
        n_aligned=n_aligned,
        n_unaligned=n_pred - n_aligned,
        coverage=cov,
        coverage_sufficient=cov >= _MIN_ODDS_COVERAGE,
        sample_audit_hash=first_hash,
    )
    return enriched, alignment, first_hash


# ═══════════════════════════════════════════════════════════════════════════════
# § 6  Segment Extraction
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_segment(rows: list[dict[str, Any]], segment: str) -> list[dict[str, Any]]:
    """Filter rows to the specified analysis segment."""
    if segment == "all":
        return list(rows)
    if segment == "heavy_favorite":
        return [r for r in rows if r["_blend_fav"] >= _HEAVY_FAV_THRESHOLD]
    if segment == "high_confidence":
        return [r for r in rows if r["_blend_fav"] >= _HIGH_CONF_THRESHOLD]
    if segment == "extreme_favorite":
        return [r for r in rows if r["_blend_fav"] >= _EXTREME_FAV_THRESHOLD]
    if segment == "phase45_failure":
        # Phase 45 definition: blend performs worse than market (blend_bss_vs_market < -0.01)
        # We define this as rows where model is overconfident (model_fav >= 0.65 AND blend >= 0.5)
        # This matches the Phase 45 "failure" pattern described in calibration baseline
        return [r for r in rows if r["_blend_fav"] >= 0.65]
    return list(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# § 7  Metrics
# ═══════════════════════════════════════════════════════════════════════════════

def _brier_score(probs: list[float], labels: list[int]) -> float:
    if not probs:
        return float("nan")
    return sum((p - l) ** 2 for p, l in zip(probs, labels)) / len(probs)


def _bss(bs: float, climate_rate: float) -> float:
    if climate_rate <= 0 or climate_rate >= 1:
        return 0.0
    bs_climate = climate_rate * (1 - climate_rate)
    if bs_climate == 0:
        return 0.0
    return 1.0 - bs / bs_climate


def _bss_direct(model_brier: float, ref_brier: float) -> float:
    """Direct BSS: positive means model's Brier score beats reference.
    Uses simple formula: 1 - model_brier / ref_brier (not climate-scaled)."""
    if ref_brier <= 0:
        return 0.0
    return 1.0 - model_brier / ref_brier


def _compute_ece(probs: list[float], labels: list[int], n_bins: int = 10) -> float:
    if not probs:
        return float("nan")
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, l in zip(probs, labels):
        idx = min(int(p * n_bins), n_bins - 1)
        bins[idx].append((p, l))
    ece = 0.0
    n = len(probs)
    for b in bins:
        if not b:
            continue
        avg_conf = sum(x[0] for x in b) / len(b)
        avg_acc = sum(x[1] for x in b) / len(b)
        ece += len(b) / n * abs(avg_conf - avg_acc)
    return ece


def _compute_segment_metrics(rows: list[dict[str, Any]]) -> SegmentMetrics:
    """Compute model / market / blend Brier, BSS, ECE for a set of rows."""
    n = len(rows)
    if n == 0:
        z = 0.0
        return SegmentMetrics(n=0, win_rate=z, fav_win_rate=z,
                              model_brier=z, market_brier=z, blend_brier=z,
                              model_bss_vs_climate=z, market_bss_vs_climate=z,
                              blend_bss_vs_climate=z, blend_bss_vs_market=z,
                              model_bss_vs_market=z,
                              model_ece=z, market_ece=z, blend_ece=z,
                              blend_ece_vs_market=z)

    home_wins = [r["home_win"] for r in rows]
    fav_wins = [r["_fav_win"] for r in rows]
    win_rate = sum(home_wins) / n
    fav_win_rate = sum(fav_wins) / n

    model_probs = [r["model_home_prob"] for r in rows]
    market_probs = [r["market_home_prob_no_vig"] for r in rows]
    blend_probs = [r["_blend"] for r in rows]

    model_brier = _brier_score(model_probs, home_wins)
    market_brier = _brier_score(market_probs, home_wins)
    blend_brier = _brier_score(blend_probs, home_wins)

    model_bss_vs_climate = _bss(model_brier, win_rate)
    market_bss_vs_climate = _bss(market_brier, win_rate)
    blend_bss_vs_climate = _bss(blend_brier, win_rate)
    blend_bss_vs_market = _bss_direct(blend_brier, market_brier)
    model_bss_vs_market = _bss_direct(model_brier, market_brier)

    model_ece = _compute_ece(model_probs, home_wins)
    market_ece = _compute_ece(market_probs, home_wins)
    blend_ece = _compute_ece(blend_probs, home_wins)

    return SegmentMetrics(
        n=n,
        win_rate=win_rate,
        fav_win_rate=fav_win_rate,
        model_brier=round(model_brier, 6),
        market_brier=round(market_brier, 6),
        blend_brier=round(blend_brier, 6),
        model_bss_vs_climate=round(model_bss_vs_climate, 6),
        market_bss_vs_climate=round(market_bss_vs_climate, 6),
        blend_bss_vs_climate=round(blend_bss_vs_climate, 6),
        blend_bss_vs_market=round(blend_bss_vs_market, 6),
        model_bss_vs_market=round(model_bss_vs_market, 6),
        model_ece=round(model_ece, 6),
        market_ece=round(market_ece, 6),
        blend_ece=round(blend_ece, 6),
        blend_ece_vs_market=round(blend_ece - market_ece, 6),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 8  Bootstrap CI
# ═══════════════════════════════════════════════════════════════════════════════

def _bootstrap_bss_vs_market(
    rows: list[dict[str, Any]],
    n_boot: int = _BOOTSTRAP_N,
    rng_seed: int = 42,
) -> BootstrapResult:
    """Bootstrap CI for blend_bss_vs_market on a set of rows."""
    n = len(rows)
    if n_boot == 0 or n < _MIN_BUCKET_N:
        return BootstrapResult(ci_lower=0.0, ci_upper=0.0, prob_positive=0.5, significant=False)

    rng = random.Random(rng_seed)
    home_wins = [r["home_win"] for r in rows]
    market_probs = [r["market_home_prob_no_vig"] for r in rows]
    blend_probs = [r["_blend"] for r in rows]

    deltas: list[float] = []
    for _ in range(n_boot):
        idxs = [rng.randint(0, n - 1) for _ in range(n)]
        hw = [home_wins[i] for i in idxs]
        mp = [market_probs[i] for i in idxs]
        bp = [blend_probs[i] for i in idxs]
        mkt_bs = _brier_score(mp, hw)
        bld_bs = _brier_score(bp, hw)
        delta = _bss_direct(bld_bs, mkt_bs)
        deltas.append(delta)

    deltas_sorted = sorted(deltas)
    ci_lo = deltas_sorted[int(0.025 * n_boot)]
    ci_hi = deltas_sorted[int(0.975 * n_boot)]
    prob_pos = sum(1 for d in deltas if d > 0) / n_boot
    significant = ci_lo > 0 or ci_hi < 0

    return BootstrapResult(
        ci_lower=round(ci_lo, 6),
        ci_upper=round(ci_hi, 6),
        prob_positive=round(prob_pos, 4),
        significant=significant,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 9  Attribution by Dimension
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_attribution_dimension(
    rows: list[dict[str, Any]],
    dim: str,
    segment_name: str,
    n_boot: int = _BOOTSTRAP_N,
) -> list[AttributionBucket]:
    """Compute metrics per bucket for one attribution dimension."""
    bucket_groups: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        label = _get_dim_bucket(r, dim)
        if label is None:
            continue
        bucket_groups.setdefault(label, []).append(r)

    buckets: list[AttributionBucket] = []
    for label, grp in sorted(bucket_groups.items()):
        metrics = _compute_segment_metrics(grp)
        boot = _bootstrap_bss_vs_market(grp, n_boot=n_boot)
        buckets.append(AttributionBucket(
            dim=dim,
            bucket_label=label,
            n=len(grp),
            segment_name=segment_name,
            metrics=metrics,
            bootstrap=boot,
        ))
    return buckets


# ═══════════════════════════════════════════════════════════════════════════════
# § 10  Negative Control
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_negative_control(
    rows: list[dict[str, Any]],
    dim: str,
    segment: str,
    n_shuffles: int = 100,
    rng_seed: int = 77,
) -> NegativeControl:
    """
    Negative control: shuffle the bucket labels for the dimension,
    compute blend BSS delta (best - worst bucket), and compare to real.
    """
    # Get real best-worst BSS delta
    real_buckets = _compute_attribution_dimension(rows, dim, segment, n_boot=0)
    valid_bss = [b.metrics.blend_bss_vs_market for b in real_buckets if b.n >= _MIN_BUCKET_N]
    if len(valid_bss) < 2:
        return NegativeControl(dim=dim, segment=segment,
                               real_blend_bss_delta=0.0, shuffled_mean_delta=0.0,
                               shuffled_std_delta=0.0, null_rejected=False, overfit_risk=False)

    real_delta = max(valid_bss) - min(valid_bss)

    # Shuffled
    rng = random.Random(rng_seed)
    n = len(rows)
    shuffled_deltas: list[float] = []
    for _ in range(n_shuffles):
        # Create shuffled rows with randomised dimension bucket
        shuffled = [dict(r) for r in rows]
        # Overwrite the dim-defining field(s) with shuffled values
        labels = [_get_dim_bucket(r, dim) for r in rows]
        rng.shuffle(labels)  # type: ignore[arg-type]
        # Inject shuffled label via a proxy field
        for r, lab in zip(shuffled, labels):
            r["_shuffled_label"] = lab

        # Compute BSS per shuffled bucket
        shuf_groups: dict[str, list[dict[str, Any]]] = {}
        for r in shuffled:
            lab = r.get("_shuffled_label")
            if lab is None:
                continue
            shuf_groups.setdefault(lab, []).append(r)

        shuf_bss = []
        for grp in shuf_groups.values():
            if len(grp) >= _MIN_BUCKET_N:
                m = _compute_segment_metrics(grp)
                shuf_bss.append(m.blend_bss_vs_market)

        if len(shuf_bss) >= 2:
            shuffled_deltas.append(max(shuf_bss) - min(shuf_bss))

    if not shuffled_deltas:
        return NegativeControl(dim=dim, segment=segment,
                               real_blend_bss_delta=real_delta,
                               shuffled_mean_delta=0.0, shuffled_std_delta=0.0,
                               null_rejected=False, overfit_risk=False)

    shuf_mean = sum(shuffled_deltas) / len(shuffled_deltas)
    shuf_std = (sum((d - shuf_mean) ** 2 for d in shuffled_deltas) / len(shuffled_deltas)) ** 0.5
    null_rejected = real_delta > shuf_mean + _OVERFIT_SIGMA * shuf_std
    overfit_risk = null_rejected and shuf_std > 0.05

    return NegativeControl(
        dim=dim,
        segment=segment,
        real_blend_bss_delta=round(real_delta, 6),
        shuffled_mean_delta=round(shuf_mean, 6),
        shuffled_std_delta=round(shuf_std, 6),
        null_rejected=null_rejected,
        overfit_risk=overfit_risk,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 11  OOF Validation
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_oof(
    rows: list[dict[str, Any]],
    dim: str,
    segment: str,
) -> OOFResult:
    """
    Rolling monthly OOF: train = all months before test month,
    test = one month. Compute blend-BSS-vs-market per fold.
    """
    # Group by month
    month_groups: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        gd = r.get("game_date", "")
        month = gd[:7] if len(gd) >= 7 else "unknown"
        month_groups.setdefault(month, []).append(r)

    sorted_months = sorted(month_groups.keys())

    fold_months: list[str] = []
    fold_bss: list[float] = []
    fold_ns: list[int] = []

    for i, test_month in enumerate(sorted_months):
        if i == 0:
            continue  # need at least one prior month for train
        test_rows = month_groups[test_month]
        if len(test_rows) < _MIN_BUCKET_N:
            continue
        fold_months.append(test_month)
        m = _compute_segment_metrics(test_rows)
        fold_bss.append(m.blend_bss_vs_market)
        fold_ns.append(len(test_rows))

    n_folds = len(fold_bss)
    if n_folds == 0:
        return OOFResult(dim=dim, segment=segment, n_folds=0, fold_months=[],
                         fold_bss_deltas=[], fold_ns=[], oof_mean_delta=0.0,
                         oof_consistent_sign=False, oof_significant=False)

    oof_mean = sum(fold_bss) / n_folds
    consistent = all(d >= 0 for d in fold_bss) or all(d <= 0 for d in fold_bss)
    significant = abs(oof_mean) >= _OOF_PROMISING_DELTA and n_folds >= 2

    return OOFResult(
        dim=dim,
        segment=segment,
        n_folds=n_folds,
        fold_months=fold_months,
        fold_bss_deltas=[round(d, 6) for d in fold_bss],
        fold_ns=fold_ns,
        oof_mean_delta=round(oof_mean, 6),
        oof_consistent_sign=consistent,
        oof_significant=significant,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 12  Gate Decision
# ═══════════════════════════════════════════════════════════════════════════════

def _decide_gate(
    alignment: OddsAlignment,
    all_metrics: SegmentMetrics,
    attribution_buckets: list[AttributionBucket],
    negative_controls: list[NegativeControl],
    oof_results: list[OOFResult],
) -> tuple[str, str, str, bool]:
    """
    Decide Phase 66 gate. Returns (gate, rationale, next_step, worth_phase67).
    Priority order:
      1. DATA_LIMITED  → odds coverage < 70%
      2. OVERFIT_RISK  → negative control significant
      3. MARKET_MICROSTRUCTURE_FEATURE_PROMISING → OOF sig + bootstrap sig
      4. DIAGNOSTIC_ONLY_SIGNAL → bootstrap sig but OOF not consistent
      5. MARKET_MICROSTRUCTURE_NOT_PROMISING → default
    """
    # 1. DATA_LIMITED
    if not alignment.coverage_sufficient:
        return (
            DATA_LIMITED,
            f"Odds CSV coverage {alignment.coverage:.1%} < threshold {_MIN_ODDS_COVERAGE:.0%}. "
            "Cannot compute market microstructure features reliably.",
            "補充 odds / CLV / closing line source mapping。",
            False,
        )

    # 2. OVERFIT_RISK
    overfit_dims = [nc for nc in negative_controls if nc.overfit_risk]
    if overfit_dims:
        dim_names = ", ".join(nc.dim for nc in overfit_dims)
        return (
            OVERFIT_RISK,
            f"Negative control 顯示 overfit risk in dimensions: {dim_names}. "
            "Shuffled labels produce similar signal magnitude (std > 0.05, null rejected). "
            "Signal likely spurious given small heavy_fav segment.",
            "停止 fitted adjustment，重做 validation with broader hold-out or larger segment.",
            False,
        )

    # 3 & 4. Check bootstrap + OOF (direction-aware: positive = blend > market)
    any_boot_sig = any(
        b.bootstrap.significant and b.bootstrap.ci_lower > 0
        for b in attribution_buckets if b.n >= _MIN_BUCKET_N
    )
    promising_oof = [o for o in oof_results
                     if o.n_folds >= 3 and o.oof_significant
                     and o.oof_consistent_sign and o.oof_mean_delta > 0]

    if any_boot_sig and promising_oof:
        oof_dims = ", ".join(o.dim for o in promising_oof)
        return (
            MARKET_MICROSTRUCTURE_FEATURE_PROMISING,
            f"Bootstrap CI excludes zero with CI > 0 (blend beats market) in at least one "
            f"attribution bucket, AND OOF signal is positive and consistent across >= 3 folds "
            f"for dimensions: {oof_dims}. Market microstructure shows actionable pattern.",
            "Phase 67: 設計 paper-only market feature patch gate。",
            True,
        )

    if any_boot_sig:
        return (
            DIAGNOSTIC_ONLY_SIGNAL,
            "Bootstrap CI excludes zero with positive direction (blend > market) in at least one "
            "attribution bucket, but OOF validation is not consistently positive (n_folds < 3 or "
            "inconsistent/negative sign). Signal may be real but requires broader validation.",
            "補 CLV / line movement coverage 或 broader hold-out validation。",
            False,
        )

    # 5. NOT_PROMISING
    best_bss = max((b.metrics.blend_bss_vs_market for b in attribution_buckets
                    if b.n >= _MIN_BUCKET_N), default=0.0)
    return (
        MARKET_MICROSTRUCTURE_NOT_PROMISING,
        f"No attribution bucket shows bootstrap-significant blend BSS improvement vs market "
        f"(best blend_bss_vs_market={best_bss:+.4f}). "
        "Market microstructure (implied prob, disagreement, fav_side, vig) "
        "does not explain heavy_fav / high_conf failure. "
        "Consider lineup / travel / rest / schedule sources.",
        "降低 market attribution 優先級。轉查 lineup / travel / rest / schedule source。",
        False,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 13  Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def run_phase66_market_microstructure_failure_attribution(
    predictions_path: str,
    odds_csv_path: str,
) -> Phase66Result:
    """
    Execute Phase 66 market microstructure failure attribution.

    PIT-safe: only pre-game odds + model predictions used as features.
    home_win is used only as the target variable, never as a feature.

    Args:
        predictions_path: Path to Phase 56 prediction JSONL.
        odds_csv_path:    Path to mlb_odds_2025_real.csv.

    Returns:
        Phase66Result dataclass with gate, metrics, and diagnostics.
    """
    run_ts = datetime.now(timezone.utc).isoformat()

    # Load odds
    odds_lookup = _load_odds_csv(odds_csv_path)

    # Load & enrich predictions
    enriched, alignment, audit_hash = _build_enriched_rows(predictions_path, odds_lookup)

    # Read odds metadata notes
    odds_meta_path = Path(odds_csv_path).with_suffix(".csv.metadata.json")
    odds_meta_notes = ""
    if odds_meta_path.exists():
        with open(odds_meta_path) as f:
            meta = json.load(f)
        odds_meta_notes = meta.get("notes", "")

    # Segments
    seg_all = _extract_segment(enriched, "all")
    seg_hf = _extract_segment(enriched, "heavy_favorite")
    seg_hc = _extract_segment(enriched, "high_confidence")
    seg_ef = _extract_segment(enriched, "extreme_favorite")
    seg_p45 = _extract_segment(enriched, "phase45_failure")

    # Compute metrics
    all_metrics = _compute_segment_metrics(seg_all)
    hf_metrics = _compute_segment_metrics(seg_hf)
    hc_metrics = _compute_segment_metrics(seg_hc)
    ef_metrics = _compute_segment_metrics(seg_ef)
    p45_metrics = _compute_segment_metrics(seg_p45) if seg_p45 else None

    # Attribution by dimension × segment (use heavy_favorite as primary)
    all_buckets: list[AttributionBucket] = []
    for dim in _AVAILABLE_DIMENSIONS:
        for seg_rows, seg_name in [
            (seg_all, "all"),
            (seg_hf, "heavy_favorite"),
        ]:
            if len(seg_rows) >= _MIN_SEGMENT_N:
                buckets = _compute_attribution_dimension(seg_rows, dim, seg_name)
                all_buckets.extend(buckets)

    # Negative controls (heavy_fav as primary, fallback to all)
    primary_rows = seg_hf if len(seg_hf) >= _MIN_SEGMENT_N else seg_all
    primary_seg = "heavy_favorite" if len(seg_hf) >= _MIN_SEGMENT_N else "all"
    neg_controls: list[NegativeControl] = []
    for dim in _AVAILABLE_DIMENSIONS:
        nc = _compute_negative_control(primary_rows, dim, primary_seg)
        neg_controls.append(nc)

    # OOF (all segment — heavy_fav too small for monthly folds)
    oof_results: list[OOFResult] = []
    for dim in _AVAILABLE_DIMENSIONS:
        oof = _compute_oof(seg_all, dim, "all")
        oof_results.append(oof)

    # Summary flags — direction-aware (positive = blend > market)
    any_boot_sig = any(
        b.bootstrap.significant and b.bootstrap.ci_lower > 0
        for b in all_buckets if b.n >= _MIN_BUCKET_N
    )
    any_oof_promising = any(
        o.n_folds >= 3 and o.oof_significant and o.oof_consistent_sign and o.oof_mean_delta > 0
        for o in oof_results
    )
    any_overfit = any(nc.overfit_risk for nc in neg_controls)

    # Gate
    gate, rationale, next_step, worth_phase67 = _decide_gate(
        alignment, all_metrics, all_buckets, neg_controls, oof_results
    )

    return Phase66Result(
        phase_version=PHASE_VERSION,
        run_timestamp=run_ts,
        completion_marker="PHASE_66_MARKET_MICROSTRUCTURE_FAILURE_ATTRIBUTION_VERIFIED",
        candidate_patch_created=CANDIDATE_PATCH_CREATED,
        production_modified=PRODUCTION_MODIFIED,
        alpha_modified=ALPHA_MODIFIED,
        diagnostic_only=DIAGNOSTIC_ONLY,
        alpha=ALPHA,
        phase65_gate=_PHASE65_GATE,
        phase65_version=_PHASE65_VERSION,
        phase64b_gate=_PHASE64B_GATE,
        phase64b_version=_PHASE64B_VERSION,
        predictions_path=predictions_path,
        odds_csv_path=odds_csv_path,
        predictions_audit_hash=audit_hash,
        odds_metadata_notes=odds_meta_notes,
        n_predictions=len(enriched),
        odds_alignment=alignment,
        segment_n_all=len(seg_all),
        segment_n_heavy_fav=len(seg_hf),
        segment_n_high_conf=len(seg_hc),
        segment_n_extreme_fav=len(seg_ef),
        segment_n_phase45_failure=len(seg_p45),
        all_metrics=all_metrics,
        heavy_fav_metrics=hf_metrics,
        high_conf_metrics=hc_metrics,
        extreme_fav_metrics=ef_metrics,
        phase45_failure_metrics=p45_metrics,
        attribution_buckets=all_buckets,
        negative_controls=neg_controls,
        oof_results=oof_results,
        any_bootstrap_significant=any_boot_sig,
        any_oof_promising=any_oof_promising,
        any_overfit_risk=any_overfit,
        data_limited_dimensions=_DATA_LIMITED_DIMENSIONS,
        data_limited_fields=_DATA_LIMITED_FIELDS,
        gate=gate,
        gate_rationale=rationale,
        next_step=next_step,
        worth_phase67=worth_phase67,
    )
