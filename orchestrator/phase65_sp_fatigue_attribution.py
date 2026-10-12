"""
orchestrator/phase65_sp_fatigue_attribution.py
===============================================
Phase 65 — Starting Pitcher Fatigue Attribution with PIT-safe Validation

目標：
  Phase 64-B gate = BULLPEN_GRANULAR_FEATURE_NOT_PROMISING。
  本 Phase 轉向先發投手 (SP) 疲勞指標，評估 SP rest_days / 短休 / 長休
  是否對 heavy_favorite 場次的投注預測有顯著貢獻。

資料來源：
  - mlb-2025-asplayed.csv (2430 rows, 100% starter name coverage)
    → 構建每位投手的先發紀錄，計算 rest_days (PIT-safe: entry_date < game_date)
  - mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl (2025 rows)
    → 主要預測集，含 blend probability 與 home_win 標籤

可用特徵 (AVAILABLE, from asplayed)：
  home_sp_rest_days       — 主場先發距上次先發的天數
  away_sp_rest_days       — 客場先發距上次先發的天數
  home_sp_short_rest      — home_sp_rest_days <= 4 (short rest flag)
  away_sp_short_rest      — away_sp_rest_days <= 4 (short rest flag)
  home_sp_long_rest       — home_sp_rest_days >= 10 (long rest / DL return flag)
  away_sp_long_rest       — away_sp_rest_days >= 10 (long rest flag)
  sp_rest_imbalance       — |home_rest - away_rest| (雙邊可用時)
  fav_sp_rest_days        — 讓分方先發的 rest_days
  dog_sp_rest_days        — 弱方先發的 rest_days
  fav_sp_short_rest       — 讓分方先發短休旗標
  sp_rest_advantage       — fav_rest - dog_rest (正=讓分方休息較多)

DATA_LIMITED 特徵 (無 IP 資料)：
  starter_previous_start_ip        — 前次先發局數 (asplayed 無 IP 欄位)
  starter_last_7d_ip               — 過去 7 天先發 IP 累計 (無資料)
  starter_last_14d_ip              — 過去 14 天先發 IP 累計 (無資料)
  starter_previous_start_pitch_count — 前次先發投球數 (無資料)
  opener_or_bulk_pitcher_flag      — 無法從姓名判斷 opener/bulk

安全常數（絕不修改）：
  CANDIDATE_PATCH_CREATED = False
  PRODUCTION_MODIFIED     = False
  ALPHA_MODIFIED          = False
  DIAGNOSTIC_ONLY         = True
  ALPHA                   = 0.40

Gate 決策標準：
  DATA_LIMITED                    ← SP 資料覆蓋率 < 10%
  OVERFIT_RISK                    ← 負控制顯著 AND shuffled_std 大
  SP_FATIGUE_FEATURE_PROMISING    ← OOF 一致 + bootstrap CI 排除零
  DIAGNOSTIC_ONLY_SIGNAL          ← bootstrap 顯著但 OOF 不一致
  SP_FATIGUE_FEATURE_NOT_PROMISING ← 無顯著歸因信號

Phase 65 完成標記：PHASE_65_SP_FATIGUE_ATTRIBUTION_VERIFIED
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Safety Constants — FROZEN
# ---------------------------------------------------------------------------
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
ALPHA_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
ALPHA: float = 0.40
PHASE_VERSION: str = "phase65_sp_fatigue_attribution_v1"

# Phase 64-B anchor
_PHASE64B_GATE = "BULLPEN_GRANULAR_FEATURE_NOT_PROMISING"
_PHASE64B_VERSION = "phase64b_full_season_attribution_v1"

# ---------------------------------------------------------------------------
# Gate Constants
# ---------------------------------------------------------------------------
SP_FATIGUE_FEATURE_PROMISING: str = "SP_FATIGUE_FEATURE_PROMISING"
DIAGNOSTIC_ONLY_SIGNAL: str = "DIAGNOSTIC_ONLY_SIGNAL"
DATA_LIMITED: str = "DATA_LIMITED"
OVERFIT_RISK: str = "OVERFIT_RISK"
SP_FATIGUE_FEATURE_NOT_PROMISING: str = "SP_FATIGUE_FEATURE_NOT_PROMISING"

# ---------------------------------------------------------------------------
# Thresholds (consistent with Phase 60/64/64-B)
# ---------------------------------------------------------------------------
_HEAVY_FAV_THRESHOLD: float = 0.70
_HIGH_CONF_THRESHOLD: float = 0.75
_MIN_SEGMENT_N: int = 20
_BOOTSTRAP_N: int = 1000
_OOF_PROMISING_DELTA: float = 0.02
_MIN_COVERAGE_RATE: float = 0.10
_OVERFIT_SIGMA: float = 1.5
_SHORT_REST_THRESHOLD: int = 4    # <= 4 days = short rest
_LONG_REST_THRESHOLD: int = 10    # >= 10 days = long rest / DL return

# ---------------------------------------------------------------------------
# Phase 65 Feature Registry
# (name, inherently_data_limited, description)
# ---------------------------------------------------------------------------
_SP_FEATURE_REGISTRY: list[tuple[str, bool, str]] = [
    # AVAILABLE — derived from asplayed.csv start history
    ("home_sp_rest_days",        False, "Home SP days since last start"),
    ("away_sp_rest_days",        False, "Away SP days since last start"),
    ("home_sp_short_rest",       False, "Home SP short rest flag (<=4d)"),
    ("away_sp_short_rest",       False, "Away SP short rest flag (<=4d)"),
    ("home_sp_long_rest",        False, "Home SP long rest flag (>=10d)"),
    ("away_sp_long_rest",        False, "Away SP long rest flag (>=10d)"),
    ("sp_rest_imbalance",        False, "Abs diff home/away SP rest days"),
    ("fav_sp_rest_days",         False, "Fav-side SP rest days"),
    ("dog_sp_rest_days",         False, "Dog-side SP rest days"),
    ("fav_sp_short_rest",        False, "Fav-side SP short rest flag"),
    ("sp_rest_advantage",        False, "Fav rest - dog rest (signed)"),
    # DATA_LIMITED — no IP / pitch count in asplayed.csv
    ("starter_previous_start_ip",        True, "SP prev-start IP [DATA_LIMITED: no IP in source]"),
    ("starter_last_7d_ip",               True, "SP rolling 7d IP [DATA_LIMITED: no IP in source]"),
    ("starter_last_14d_ip",              True, "SP rolling 14d IP [DATA_LIMITED: no IP in source]"),
    ("starter_previous_start_pitch_count", True, "SP prev-start pitches [DATA_LIMITED: no pitch count]"),
    ("opener_or_bulk_pitcher_flag",      True, "Opener/bulk flag [DATA_LIMITED: cannot infer from name]"),
]

_SP_AVAILABLE_FEATURES: frozenset[str] = frozenset(
    name for name, limited, _ in _SP_FEATURE_REGISTRY if not limited
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SPStartHistory:
    """Summary of SP start history build from asplayed.csv."""
    n_asplayed_rows: int
    n_unique_pitchers: int
    n_pitchers_with_multiple_starts: int
    date_range_start: str
    date_range_end: str
    build_timestamp: str


@dataclass
class SPFeatureCoverage:
    """Coverage for a single Phase 65 feature."""
    feature_name: str
    n_available: int
    n_total: int
    coverage_pct: float
    data_limited: bool
    data_limited_reason: str | None


@dataclass
class SPAlignment:
    """Alignment stats between asplayed SP history and prediction dataset."""
    n_predictions: int
    n_asplayed_rows: int
    n_aligned_home_rest: int
    n_aligned_away_rest: int
    n_both_aligned: int
    home_rest_coverage: float
    away_rest_coverage: float
    both_coverage: float
    coverage_sufficient: bool


@dataclass
class SPBucketAttribution:
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
class SPSegmentAttribution:
    """Attribution for one SP feature × one segment."""
    feature_name: str
    segment: str
    n: int
    coverage_pct: float
    brier: float | None
    bss: float | None
    calibration_residual: float
    ece: float | None
    bucket_attribution: SPBucketAttribution | None
    data_limited: bool
    data_limited_reason: str | None


@dataclass
class SPNegativeControl:
    """Negative control: shuffled vs real SP feature delta."""
    feature_name: str
    segment: str
    real_win_rate_delta: float
    shuffled_mean_delta: float
    shuffled_std_delta: float
    null_rejected: bool
    overfit_risk: bool


@dataclass
class SPOOFResult:
    """Rolling monthly OOF validation for SP fatigue features."""
    feature_name: str
    n_folds: int
    fold_months: list[str]
    fold_win_rate_deltas: list[float]
    fold_n: list[int]
    oof_mean_delta: float
    oof_consistent_sign: bool
    oof_significant: bool


@dataclass
class Phase65Result:
    """Full Phase 65 SP fatigue attribution result."""
    phase_version: str
    run_timestamp: str

    # Safety constants snapshot
    candidate_patch_created: bool
    production_modified: bool
    alpha_modified: bool
    diagnostic_only: bool
    alpha: float

    # Phase 64-B anchor
    phase64b_gate: str
    phase64b_version: str

    # Data source info
    sp_start_history: SPStartHistory
    n_predictions: int

    # Alignment
    alignment: SPAlignment

    # Feature coverage
    feature_coverage: list[SPFeatureCoverage]
    n_available_features: int
    n_data_limited_features: int

    # Segment sizes
    segment_n_all: int
    segment_n_heavy_fav: int
    segment_n_high_conf: int

    # Attribution results
    attributions: list[SPSegmentAttribution]

    # Negative controls
    negative_controls: list[SPNegativeControl]

    # OOF validation
    oof_results: list[SPOOFResult]

    # Summary
    any_bootstrap_significant: bool
    any_oof_promising: bool

    # Gate
    gate: str
    gate_rationale: str
    next_step: str
    worth_phase66: bool

    # Completion marker
    completion_marker: str


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _load_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_asplayed_csv(path: str) -> list[dict[str, str]]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _blend_prob(model_prob: float, market_prob: float) -> float:
    """FROZEN blend: (1 - ALPHA) * model + ALPHA * market."""
    return (1.0 - ALPHA) * model_prob + ALPHA * market_prob


def _fav_prob(blend: float) -> float:
    return max(blend, 1.0 - blend)


# ---------------------------------------------------------------------------
# SP Start History Builder (PIT-safe)
# ---------------------------------------------------------------------------

def _build_sp_start_history(asplayed_rows: list[dict[str, str]]) -> dict[str, list[str]]:
    """
    Build per-pitcher sorted start date list from asplayed rows.
    Returns dict: pitcher_name (str) → sorted list of game_date strings.

    PIT-safe: no outcome information used; only date + pitcher name.
    """
    from collections import defaultdict
    history: dict[str, list[str]] = defaultdict(list)
    for row in asplayed_rows:
        d = row.get("date", "").strip()
        if not d:
            continue
        home_sp = row.get("home_starter", "").strip()
        away_sp = row.get("away_starter", "").strip()
        if home_sp:
            history[home_sp].append(d)
        if away_sp:
            history[away_sp].append(d)
    # Sort each pitcher's list
    return {pitcher: sorted(dates) for pitcher, dates in history.items()}


def _compute_sp_rest_days(
    pitcher: str,
    game_date: str,
    history: dict[str, list[str]],
) -> int | None:
    """
    Compute rest_days for a pitcher on a given game_date.
    Uses only previous starts strictly before game_date (PIT-safe).
    Returns None if no previous start exists.
    """
    starts = history.get(pitcher, [])
    previous = [s for s in starts if s < game_date]
    if not previous:
        return None
    prev_date = datetime.strptime(previous[-1], "%Y-%m-%d").date()
    curr_date = datetime.strptime(game_date, "%Y-%m-%d").date()
    return (curr_date - prev_date).days


# ---------------------------------------------------------------------------
# SP Feature Derivation
# ---------------------------------------------------------------------------

def _derive_sp_features(
    game_date: str,
    home_sp: str,
    away_sp: str,
    blend_home: float,
    history: dict[str, list[str]],
) -> dict[str, Any]:
    """
    Derive all Phase 65 SP fatigue features for one game.

    Args:
        game_date: YYYY-MM-DD string
        home_sp: home starter name (from asplayed)
        away_sp: away starter name (from asplayed)
        blend_home: blended home win probability
        history: pitcher → sorted list of start dates (PIT-safe)

    Returns dict of feature values (None for DATA_LIMITED or unavailable).
    """
    home_rest = _compute_sp_rest_days(home_sp, game_date, history) if home_sp else None
    away_rest = _compute_sp_rest_days(away_sp, game_date, history) if away_sp else None

    home_short = (home_rest is not None and home_rest <= _SHORT_REST_THRESHOLD)
    away_short = (away_rest is not None and away_rest <= _SHORT_REST_THRESHOLD)
    home_long  = (home_rest is not None and home_rest >= _LONG_REST_THRESHOLD)
    away_long  = (away_rest is not None and away_rest >= _LONG_REST_THRESHOLD)

    rest_imbalance: float | None = None
    if home_rest is not None and away_rest is not None:
        rest_imbalance = float(abs(home_rest - away_rest))

    # Fav / dog assignment
    home_is_fav = blend_home >= 0.50
    fav_rest = home_rest if home_is_fav else away_rest
    dog_rest = away_rest if home_is_fav else home_rest
    fav_short = home_short if home_is_fav else away_short

    rest_advantage: float | None = None
    if fav_rest is not None and dog_rest is not None:
        rest_advantage = float(fav_rest - dog_rest)

    return {
        # AVAILABLE
        "home_sp_rest_days":   float(home_rest) if home_rest is not None else None,
        "away_sp_rest_days":   float(away_rest) if away_rest is not None else None,
        "home_sp_short_rest":  float(home_short) if home_rest is not None else None,
        "away_sp_short_rest":  float(away_short) if away_rest is not None else None,
        "home_sp_long_rest":   float(home_long)  if home_rest is not None else None,
        "away_sp_long_rest":   float(away_long)  if away_rest is not None else None,
        "sp_rest_imbalance":   rest_imbalance,
        "fav_sp_rest_days":    float(fav_rest) if fav_rest is not None else None,
        "dog_sp_rest_days":    float(dog_rest) if dog_rest is not None else None,
        "fav_sp_short_rest":   float(fav_short) if fav_rest is not None else None,
        "sp_rest_advantage":   rest_advantage,
        # DATA_LIMITED — always None
        "starter_previous_start_ip":          None,
        "starter_last_7d_ip":                 None,
        "starter_last_14d_ip":                None,
        "starter_previous_start_pitch_count": None,
        "opener_or_bulk_pitcher_flag":        None,
    }


# ---------------------------------------------------------------------------
# Align predictions with SP features
# ---------------------------------------------------------------------------

def _align_predictions_with_sp(
    predictions: list[dict[str, Any]],
    asplayed_rows: list[dict[str, str]],
    history: dict[str, list[str]],
) -> tuple[list[dict[str, Any]], SPAlignment]:
    """
    Join predictions to asplayed SP features via (game_date, home_team).
    Returns (enriched_rows, alignment).
    """
    asp_idx: dict[tuple[str, str], dict[str, str]] = {
        (r["date"].strip(), r["home_team"].strip()): r
        for r in asplayed_rows
    }

    n_home_rest = 0
    n_away_rest = 0
    n_both = 0
    enriched: list[dict[str, Any]] = []

    for row in predictions:
        gd = str(row.get("game_date", ""))
        ht = str(row.get("home_team", ""))
        blend = _blend_prob(
            float(row.get("model_home_prob", 0.5)),
            float(row.get("market_home_prob_no_vig", 0.5)),
        )

        asp_row = asp_idx.get((gd, ht))
        if asp_row:
            home_sp = asp_row.get("home_starter", "").strip()
            away_sp = asp_row.get("away_starter", "").strip()
        else:
            home_sp = ""
            away_sp = ""

        features = _derive_sp_features(gd, home_sp, away_sp, blend, history)

        combined = dict(row)
        combined.update(features)
        combined["_sp_home_starter"] = home_sp
        combined["_sp_away_starter"] = away_sp
        combined["_sp_aligned"] = asp_row is not None

        h_has = features["home_sp_rest_days"] is not None
        a_has = features["away_sp_rest_days"] is not None
        if h_has:
            n_home_rest += 1
        if a_has:
            n_away_rest += 1
        if h_has and a_has:
            n_both += 1

        enriched.append(combined)

    n_pred = len(predictions)
    alignment = SPAlignment(
        n_predictions=n_pred,
        n_asplayed_rows=len(asplayed_rows),
        n_aligned_home_rest=n_home_rest,
        n_aligned_away_rest=n_away_rest,
        n_both_aligned=n_both,
        home_rest_coverage=round(n_home_rest / max(n_pred, 1), 4),
        away_rest_coverage=round(n_away_rest / max(n_pred, 1), 4),
        both_coverage=round(n_both / max(n_pred, 1), 4),
        coverage_sufficient=(n_home_rest / max(n_pred, 1)) >= _MIN_COVERAGE_RATE,
    )
    return enriched, alignment


# ---------------------------------------------------------------------------
# Feature coverage
# ---------------------------------------------------------------------------

def _compute_sp_coverage(
    enriched_rows: list[dict[str, Any]],
) -> list[SPFeatureCoverage]:
    n_total = len(enriched_rows)
    coverage: list[SPFeatureCoverage] = []
    for fname, inherently_limited, desc in _SP_FEATURE_REGISTRY:
        n_avail = sum(1 for r in enriched_rows if r.get(fname) is not None)
        cov_pct = n_avail / max(n_total, 1)
        is_limited = inherently_limited or cov_pct < _MIN_COVERAGE_RATE
        reason: str | None = None
        if inherently_limited:
            reason = f"DATA_LIMITED: {desc}"
        elif cov_pct < _MIN_COVERAGE_RATE:
            reason = (
                f"Coverage {n_avail}/{n_total} ({cov_pct:.1%}) "
                f"< {_MIN_COVERAGE_RATE:.0%} threshold"
            )
        coverage.append(SPFeatureCoverage(
            feature_name=fname,
            n_available=n_avail,
            n_total=n_total,
            coverage_pct=round(cov_pct, 4),
            data_limited=is_limited,
            data_limited_reason=reason,
        ))
    return coverage


# ---------------------------------------------------------------------------
# Segment extraction
# ---------------------------------------------------------------------------

def _extract_segment(
    rows: list[dict[str, Any]],
    segment: str,
) -> list[dict[str, Any]]:
    if segment == "all":
        return rows
    result: list[dict[str, Any]] = []
    for row in rows:
        blend = _blend_prob(
            float(row.get("model_home_prob", 0.5)),
            float(row.get("market_home_prob_no_vig", 0.5)),
        )
        fp = _fav_prob(blend)
        if segment == "heavy_favorite" and fp >= _HEAVY_FAV_THRESHOLD:
            result.append(row)
        elif segment == "high_confidence" and fp >= _HIGH_CONF_THRESHOLD:
            result.append(row)
    return result


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------

def _brier_score(probs: list[float], labels: list[int]) -> float:
    if not probs:
        return float("nan")
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(probs)


def _bss(bs: float, climate_rate: float) -> float:
    base = climate_rate * (1.0 - climate_rate)
    if base == 0.0:
        return 0.0
    return 1.0 - bs / base


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
        mp = sum(x[0] for x in b) / len(b)
        my = sum(x[1] for x in b) / len(b)
        ece += len(b) / len(probs) * abs(mp - my)
    return ece


def _bootstrap_win_rate_delta(
    high_wins: list[int],
    low_wins: list[int],
    n_boot: int = _BOOTSTRAP_N,
    rng_seed: int = 42,
) -> tuple[float, float]:
    rng = random.Random(rng_seed)
    deltas: list[float] = []
    for _ in range(n_boot):
        h = rng.choices(high_wins, k=len(high_wins))
        lo = rng.choices(low_wins, k=len(low_wins))
        dh = sum(h) / len(h) if h else 0.5
        dl = sum(lo) / len(lo) if lo else 0.5
        deltas.append(dh - dl)
    deltas.sort()
    return deltas[int(0.025 * n_boot)], deltas[int(0.975 * n_boot)]


def _bucket_attribution(
    feature_vals: list[float | None],
    win_labels: list[int],
    n_boot: int = _BOOTSTRAP_N,
) -> SPBucketAttribution | None:
    paired = [(f, w) for f, w in zip(feature_vals, win_labels) if f is not None]
    if len(paired) < _MIN_SEGMENT_N:
        return None
    med = sorted(f for f, _ in paired)[len(paired) // 2]
    high = [w for f, w in paired if f > med]
    low  = [w for f, w in paired if f <= med]
    if not high or not low:
        return None
    wr_h = sum(high) / len(high)
    wr_l = sum(low) / len(low)
    delta = wr_h - wr_l
    ci_lo, ci_hi = _bootstrap_win_rate_delta(high, low, n_boot)
    return SPBucketAttribution(
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
# Attribution for one feature × segment
# ---------------------------------------------------------------------------

def _compute_sp_attribution(
    feature_name: str,
    segment_name: str,
    rows: list[dict[str, Any]],
    data_limited: bool,
    data_limited_reason: str | None,
    n_boot: int = _BOOTSTRAP_N,
) -> SPSegmentAttribution:
    blend_probs = [
        _blend_prob(
            float(r.get("model_home_prob", 0.5)),
            float(r.get("market_home_prob_no_vig", 0.5)),
        )
        for r in rows
    ]
    win_labels = [int(r.get("home_win", 0)) for r in rows]
    fvals: list[float | None] = [r.get(feature_name) for r in rows]

    valid_mask = [v is not None for v in fvals]
    n_valid = sum(valid_mask)
    cov = n_valid / max(len(rows), 1)

    fv = [v for v, m in zip(fvals, valid_mask) if m]
    bp = [p for p, m in zip(blend_probs, valid_mask) if m]
    wl = [y for y, m in zip(win_labels, valid_mask) if m]

    bs = _brier_score(bp, wl) if bp else float("nan")
    climate = sum(wl) / max(len(wl), 1) if wl else 0.5
    bss_val = _bss(bs, climate) if not math.isnan(bs) else float("nan")
    resid = (sum(bp) / max(len(bp), 1)) - climate if bp else 0.0
    ece = _compute_ece(bp, wl) if bp else float("nan")

    bucket_attr = _bucket_attribution(fv, wl, n_boot) if n_valid >= _MIN_SEGMENT_N else None

    return SPSegmentAttribution(
        feature_name=feature_name,
        segment=segment_name,
        n=n_valid,
        coverage_pct=round(cov, 4),
        brier=round(bs, 4) if not math.isnan(bs) else None,
        bss=round(bss_val, 4) if not math.isnan(bss_val) else None,
        calibration_residual=round(resid, 4),
        ece=round(ece, 4) if not math.isnan(ece) else None,
        bucket_attribution=bucket_attr,
        data_limited=data_limited,
        data_limited_reason=data_limited_reason,
    )


# ---------------------------------------------------------------------------
# Negative Control
# ---------------------------------------------------------------------------

def _compute_sp_negative_control(
    rows: list[dict[str, Any]],
    feature_name: str,
    segment: str = "heavy_favorite",
    n_shuffles: int = 100,
    rng_seed: int = 99,
) -> SPNegativeControl:
    seg_rows = _extract_segment(rows, segment)
    fv = [r.get(feature_name) for r in seg_rows]
    wl = [int(r.get("home_win", 0)) for r in seg_rows]

    paired = [(f, w) for f, w in zip(fv, wl) if f is not None]
    if len(paired) < _MIN_SEGMENT_N:
        return SPNegativeControl(
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
    real_low  = [w for f, w in paired if f <= med]
    real_delta = (
        sum(real_high) / len(real_high) - sum(real_low) / len(real_low)
        if real_high and real_low else 0.0
    )

    rng = random.Random(rng_seed)
    shuffled_deltas: list[float] = []
    all_fv = [f for f, _ in paired]
    all_wl = [w for _, w in paired]
    for _ in range(n_shuffles):
        sfv = rng.sample(all_fv, len(all_fv))
        s_med = sorted(sfv)[len(sfv) // 2]
        s_high = [all_wl[i] for i, f in enumerate(sfv) if f > s_med]
        s_low  = [all_wl[i] for i, f in enumerate(sfv) if f <= s_med]
        if s_high and s_low:
            shuffled_deltas.append(sum(s_high) / len(s_high) - sum(s_low) / len(s_low))

    if not shuffled_deltas:
        sm, ss = 0.0, 0.0
        null_rejected = False
    else:
        sm = sum(shuffled_deltas) / len(shuffled_deltas)
        ss = (sum((d - sm) ** 2 for d in shuffled_deltas) / len(shuffled_deltas)) ** 0.5
        null_rejected = abs(real_delta) > abs(sm) + _OVERFIT_SIGMA * ss

    overfit_risk = null_rejected and ss > 0.10

    return SPNegativeControl(
        feature_name=feature_name,
        segment=segment,
        real_win_rate_delta=round(real_delta, 4),
        shuffled_mean_delta=round(sm, 4),
        shuffled_std_delta=round(ss, 4),
        null_rejected=null_rejected,
        overfit_risk=overfit_risk,
    )


# ---------------------------------------------------------------------------
# OOF Rolling Monthly Validation
# ---------------------------------------------------------------------------

def _compute_sp_oof(
    rows: list[dict[str, Any]],
    feature_name: str,
    segment: str = "heavy_favorite",
) -> SPOOFResult:
    seg_rows = _extract_segment(rows, segment)

    def _ym(row: dict[str, Any]) -> str:
        return str(row.get("game_date", ""))[:7]

    months = sorted(set(_ym(r) for r in seg_rows))
    if len(months) < 2:
        return SPOOFResult(
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
        test  = [r for r in seg_rows if _ym(r) == test_month]
        if len(train) < _MIN_SEGMENT_N or len(test) < 5:
            continue
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
        t_low  = [w for f, w in test_pairs if f <= train_med]
        if not t_high or not t_low:
            fold_deltas.append(0.0)
        else:
            fold_deltas.append(sum(t_high) / len(t_high) - sum(t_low) / len(t_low))
        fold_months.append(test_month)
        fold_ns.append(len(test_pairs))

    if not fold_deltas:
        return SPOOFResult(
            feature_name=feature_name,
            n_folds=0,
            fold_months=[],
            fold_win_rate_deltas=[],
            fold_n=[],
            oof_mean_delta=0.0,
            oof_consistent_sign=False,
            oof_significant=False,
        )

    mean_delta = sum(fold_deltas) / len(fold_deltas)
    consistent = all(d > 0 for d in fold_deltas) or all(d < 0 for d in fold_deltas)
    significant = abs(mean_delta) >= _OOF_PROMISING_DELTA

    return SPOOFResult(
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

def _decide_sp_gate(
    alignment: SPAlignment,
    coverage_results: list[SPFeatureCoverage],
    attributions: list[SPSegmentAttribution],
    neg_controls: list[SPNegativeControl],
    oof_results: list[SPOOFResult],
) -> tuple[str, str, str, bool]:
    """
    Decide Phase 65 gate from evidence.
    Returns (gate, rationale, next_step, worth_phase66).
    """
    n_available = sum(1 for c in coverage_results if not c.data_limited)
    all_data_limited = n_available == 0
    cov_rate = alignment.home_rest_coverage

    any_overfit = any(nc.overfit_risk for nc in neg_controls)
    promising_oof = [
        r for r in oof_results
        if r.oof_significant and r.oof_consistent_sign and r.n_folds >= 3
    ]
    any_bootstrap_sig = any(
        a.bucket_attribution is not None and a.bucket_attribution.bootstrap_significant
        for a in attributions
    )

    if all_data_limited or cov_rate < _MIN_COVERAGE_RATE:
        gate = DATA_LIMITED
        rationale = (
            f"All Phase 65 SP features DATA_LIMITED or coverage < 10%. "
            f"home_rest_coverage={cov_rate:.1%}. Cannot run meaningful attribution."
        )
        next_step = (
            "Verify mlb-2025-asplayed.csv contains starter name columns. "
            "Re-run after validating data source."
        )
        worth_phase66 = False

    elif any_overfit:
        gate = OVERFIT_RISK
        rationale = (
            "Negative control indicates overfit risk: null rejected AND shuffled_std > 0.10. "
            "No production patch produced. SP fatigue signal may be spurious."
        )
        next_step = (
            "Disable fitted adjustment. Re-validate with fresh hold-out segment "
            "(n >= 200 heavy_fav games). Consider Bonferroni correction."
        )
        worth_phase66 = False

    elif promising_oof and any_bootstrap_sig:
        gate = SP_FATIGUE_FEATURE_PROMISING
        rationale = (
            f"OOF consistently significant for {len(promising_oof)} feature(s) (n_folds>=3) "
            f"AND bootstrap CI excludes zero. Replicable SP fatigue signal found. "
            f"No production patch produced — paper-only gate."
        )
        next_step = (
            "Phase 66: Design paper-only SP fatigue patch gate. "
            "Use promising rest_days features as candidate set. "
            "Validate on 2026 season data before any alpha modification."
        )
        worth_phase66 = True

    elif any_bootstrap_sig:
        gate = DIAGNOSTIC_ONLY_SIGNAL
        rationale = (
            "Bootstrap CI excludes zero for some SP fatigue features but OOF not consistently "
            "significant. Directional signal present but not robust enough for production. "
            "No production patch produced."
        )
        next_step = (
            "Broaden validation window. Add IP-based features if StatsAPI pitch data becomes "
            "available. Consider multi-feature composite SP fatigue index."
        )
        worth_phase66 = False

    else:
        gate = SP_FATIGUE_FEATURE_NOT_PROMISING
        rationale = (
            "No bootstrap-significant attribution found for any SP fatigue feature. "
            "OOF deltas inconsistent or weak. "
            "SP rest_days fatigue does not provide reliable signal above baseline. "
            "No production patch produced."
        )
        next_step = (
            "De-prioritise SP rest fatigue as primary signal. "
            "Consider: (a) weather/park interaction with SP quality, "
            "(b) pitcher-specific decay models, "
            "(c) pitch velocity / stuff metrics if available."
        )
        worth_phase66 = False

    return gate, rationale, next_step, worth_phase66


# ---------------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------------

def run_phase65_sp_fatigue_attribution(
    predictions_path: str,
    asplayed_path: str,
) -> Phase65Result:
    """
    Full Phase 65 orchestration:
    1. Load asplayed.csv → build SP start history
    2. Load predictions → derive SP fatigue features
    3. Align & compute coverage
    4. Attribution for available features × segments
    5. Negative control + OOF
    6. Gate decision

    Safety constants must remain:
        CANDIDATE_PATCH_CREATED = False
        PRODUCTION_MODIFIED     = False
        ALPHA_MODIFIED          = False
        DIAGNOSTIC_ONLY         = True
        ALPHA                   = 0.40
    """
    assert not CANDIDATE_PATCH_CREATED, "Safety violation: CANDIDATE_PATCH_CREATED must be False"
    assert not PRODUCTION_MODIFIED,     "Safety violation: PRODUCTION_MODIFIED must be False"
    assert not ALPHA_MODIFIED,          "Safety violation: ALPHA_MODIFIED must be False"
    assert DIAGNOSTIC_ONLY,             "Safety violation: DIAGNOSTIC_ONLY must be True"
    assert ALPHA == 0.40,               f"Safety violation: ALPHA must be 0.40, got {ALPHA}"

    run_ts = datetime.now(timezone.utc).isoformat()

    # Step 1: Build SP start history
    asplayed_rows = _load_asplayed_csv(asplayed_path)
    history = _build_sp_start_history(asplayed_rows)
    n_multi_start = sum(1 for v in history.values() if len(v) >= 2)
    dates_all = sorted(r.get("date", "") for r in asplayed_rows if r.get("date"))
    sp_start_history_meta = SPStartHistory(
        n_asplayed_rows=len(asplayed_rows),
        n_unique_pitchers=len(history),
        n_pitchers_with_multiple_starts=n_multi_start,
        date_range_start=dates_all[0] if dates_all else "",
        date_range_end=dates_all[-1] if dates_all else "",
        build_timestamp=run_ts,
    )

    # Step 2: Load predictions + align
    predictions = _load_jsonl(predictions_path)
    enriched_rows, alignment = _align_predictions_with_sp(predictions, asplayed_rows, history)

    # Step 3: Feature coverage
    feature_coverage = _compute_sp_coverage(enriched_rows)
    n_avail = sum(1 for c in feature_coverage if not c.data_limited)
    n_limited = sum(1 for c in feature_coverage if c.data_limited)

    # Segment sizes
    n_all = len(enriched_rows)
    hf_rows = _extract_segment(enriched_rows, "heavy_favorite")
    hc_rows = _extract_segment(enriched_rows, "high_confidence")

    # Step 4: Attribution for AVAILABLE features × segments
    attributions: list[SPSegmentAttribution] = []
    for fname, inherently_limited, desc in _SP_FEATURE_REGISTRY:
        cov = next(c for c in feature_coverage if c.feature_name == fname)
        for seg in ["all", "heavy_favorite"]:
            seg_rows = _extract_segment(enriched_rows, seg)
            attr = _compute_sp_attribution(
                feature_name=fname,
                segment_name=seg,
                rows=seg_rows,
                data_limited=cov.data_limited,
                data_limited_reason=cov.data_limited_reason,
                n_boot=_BOOTSTRAP_N,
            )
            attributions.append(attr)

    # Step 5: Negative control (available features only, heavy_fav segment)
    neg_controls: list[SPNegativeControl] = []
    for fname in _SP_AVAILABLE_FEATURES:
        nc = _compute_sp_negative_control(enriched_rows, fname, segment="heavy_favorite")
        neg_controls.append(nc)

    # Step 5b: OOF (available features only, heavy_fav segment)
    oof_results: list[SPOOFResult] = []
    for fname in _SP_AVAILABLE_FEATURES:
        oof = _compute_sp_oof(enriched_rows, fname, segment="heavy_favorite")
        oof_results.append(oof)

    # Step 6: Gate
    any_bootstrap_sig = any(
        a.bucket_attribution is not None and a.bucket_attribution.bootstrap_significant
        for a in attributions
    )
    any_oof_promising = any(
        r.oof_significant and r.oof_consistent_sign and r.n_folds >= 3
        for r in oof_results
    )
    gate, rationale, next_step, worth_phase66 = _decide_sp_gate(
        alignment, feature_coverage, attributions, neg_controls, oof_results
    )

    return Phase65Result(
        phase_version=PHASE_VERSION,
        run_timestamp=run_ts,
        candidate_patch_created=CANDIDATE_PATCH_CREATED,
        production_modified=PRODUCTION_MODIFIED,
        alpha_modified=ALPHA_MODIFIED,
        diagnostic_only=DIAGNOSTIC_ONLY,
        alpha=ALPHA,
        phase64b_gate=_PHASE64B_GATE,
        phase64b_version=_PHASE64B_VERSION,
        sp_start_history=sp_start_history_meta,
        n_predictions=len(predictions),
        alignment=alignment,
        feature_coverage=feature_coverage,
        n_available_features=n_avail,
        n_data_limited_features=n_limited,
        segment_n_all=n_all,
        segment_n_heavy_fav=len(hf_rows),
        segment_n_high_conf=len(hc_rows),
        attributions=attributions,
        negative_controls=neg_controls,
        oof_results=oof_results,
        any_bootstrap_significant=any_bootstrap_sig,
        any_oof_promising=any_oof_promising,
        gate=gate,
        gate_rationale=rationale,
        next_step=next_step,
        worth_phase66=worth_phase66,
        completion_marker="PHASE_65_SP_FATIGUE_ATTRIBUTION_VERIFIED",
    )
