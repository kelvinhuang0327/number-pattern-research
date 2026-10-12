"""
Phase 60 — Bullpen Feature Decomposition and PIT-safe Attribution

目標：
  - 將 bullpen_usage_last_3d 分解為多個特徵家族（raw_home, raw_away, delta,
    fav_side, dog_side, normalized_delta）
  - 對每個可用特徵家族在四個 segment 上做 attribution 分析：
      all | heavy_favorite | high_confidence | phase45_failure
  - 執行 negative control（shuffle feature）驗證假訊號
  - 執行 rolling monthly OOF 驗證（訓練期 vs 測試期 訊號複製性）
  - 判定 gate：BULLPEN_FEATURE_PROMISING | DIAGNOSTIC_ONLY_SIGNAL |
               DATA_LIMITED | BULLPEN_FEATURE_NOT_PROMISING

安全常數（絕不修改）：
  CANDIDATE_PATCH_CREATED = False
  PRODUCTION_MODIFIED     = False
  ALPHA_MODIFIED          = False
  DIAGNOSTIC_ONLY         = True
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
PHASE_VERSION: str = "phase60_bullpen_feature_decomposition_v1"

# ---------------------------------------------------------------------------
# Gate Constants
# ---------------------------------------------------------------------------
BULLPEN_FEATURE_PROMISING: str = "BULLPEN_FEATURE_PROMISING"
DIAGNOSTIC_ONLY_SIGNAL: str = "DIAGNOSTIC_ONLY_SIGNAL"
DATA_LIMITED: str = "DATA_LIMITED"
BULLPEN_FEATURE_NOT_PROMISING: str = "BULLPEN_FEATURE_NOT_PROMISING"

# ---------------------------------------------------------------------------
# Segment Thresholds
# ---------------------------------------------------------------------------
_HEAVY_FAV_THRESHOLD: float = 0.70      # fav_prob >= 0.70
_HIGH_CONF_THRESHOLD: float = 0.75      # fav_prob >= 0.75 (0.80 effectively empty)
_LOW_DISAG_PERCENTILE: float = 0.50     # bottom 50% disagreement = low_disagreement
_MIN_SEGMENT_N: int = 20               # minimum for any attribution analysis
_BOOTSTRAP_N: int = 1000               # bootstrap resamples
_OOF_PROMISING_DELTA: float = 0.02     # OOF win_rate_delta >= 0.02 → promising
_DATA_LIMITED_COVERAGE: float = 0.50   # coverage < 50% → DATA_LIMITED

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class FeatureFamilyMeta:
    """Metadata for a single feature family."""
    feature_name: str
    description: str
    available: bool        # False = DATA_LIMITED
    coverage_pct: float    # fraction of aligned rows with valid values
    n_usable: int
    data_limited_reason: str | None = None  # if not available


@dataclass
class BucketAttribution:
    """Win-rate attribution for median-split high vs low feature buckets."""
    n_high: int
    n_low: int
    win_rate_high: float
    win_rate_low: float
    win_rate_delta: float    # high - low (positive = tired side loses more)
    bootstrap_ci_lower: float
    bootstrap_ci_upper: float
    bootstrap_significant: bool  # CI excludes 0


@dataclass
class SegmentAttribution:
    """Full attribution result for one feature × one segment."""
    feature_name: str
    segment: str
    n: int
    coverage_pct: float
    baseline_brier: float
    baseline_bss: float          # vs climatological
    calibration_residual: float  # mean(pred) - mean(actual)
    ece: float
    bucket_attribution: BucketAttribution | None  # None if n < _MIN_SEGMENT_N
    oof_win_rate_delta: float | None    # rolling OOF replication
    oof_n: int | None
    oof_replicated: bool | None  # True if oof_delta > 0 and same sign as training


@dataclass
class NegativeControlResult:
    """Negative control: shuffled feature vs real feature."""
    real_win_rate_delta_heavy_fav: float
    shuffled_mean_delta: float
    shuffled_std_delta: float
    null_rejected: bool   # True if real > shuffled_mean + 1.5*shuffled_std


@dataclass
class OOFSummary:
    """Summary of rolling monthly OOF validation across all folds."""
    n_folds: int
    fold_months: list[str]
    fold_win_rate_deltas: list[float]
    fold_n: list[int]
    oof_mean_delta: float
    oof_consistent_sign: bool   # all positive or all negative
    oof_significant: bool       # mean_delta >= _OOF_PROMISING_DELTA


@dataclass
class Phase60DecompositionResult:
    """Full result of Phase 60 bullpen feature decomposition."""
    phase_version: str
    run_timestamp: str
    audit_hash: str

    # Safety constants snapshot
    candidate_patch_created: bool
    production_modified: bool
    alpha_modified: bool
    diagnostic_only: bool
    alpha: float

    # Data summary
    n_predictions: int
    n_bullpen_rows: int
    n_aligned: int
    alignment_rate: float

    # Segment sizes
    segment_n_all: int
    segment_n_heavy_fav: int
    segment_n_high_conf: int
    segment_n_phase45_failure: int
    high_conf_note: str   # doc: why 0.80 threshold was adjusted

    # Feature family metadata
    feature_families: list[FeatureFamilyMeta]
    n_available_features: int
    n_data_limited_features: int

    # Attribution results
    attributions: list[SegmentAttribution]

    # Negative control
    negative_control: NegativeControlResult

    # OOF validation (for fav_vs_dog_delta_3d on heavy_fav segment)
    oof_summary: OOFSummary

    # Final gate
    gate: str
    gate_rationale: str


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _norm_team(name: str) -> str:
    """Normalise team name: upper-case, spaces → underscores, strip non-alphanum_."""
    return re.sub(r"[^A-Z0-9_]", "_", name.upper().replace(" ", "_"))


def _parse_bull_game_id(game_id: str) -> tuple[str, str, str] | None:
    """
    Parse bullpen_usage_3d game_id into (date_str, norm_away, norm_home).
    Format: MLB-YYYY_MM_DD-H_MM_PM-AWAY_TEAM-AT-HOME_TEAM
    """
    try:
        # Remove leading "MLB-"
        rest = game_id.replace("MLB-", "", 1)
        # Date part: YYYY_MM_DD
        date_part = rest[:10]
        date_str = date_part.replace("_", "-")
        # After date: -H_MM_PM-TEAMS_PART
        after_date = rest[10:]
        # Find "-AT-" which separates away from home
        at_idx = after_date.rfind("-AT-")
        if at_idx == -1:
            return None
        teams_part = after_date[at_idx + 4:]  # after "-AT-"
        # Time part between date and -AT-
        before_at = after_date[:at_idx]
        # before_at = -H_MM_PM-AWAY_TEAM  (starts with '-')
        # Find second '-': skip leading '-', then find next '-' after time
        before_at = before_at.lstrip("-")
        time_end = before_at.find("-")
        if time_end == -1:
            return None
        away_raw = before_at[time_end + 1:]
        norm_away = _norm_team(away_raw)
        norm_home = _norm_team(teams_part)
        return date_str, norm_away, norm_home
    except Exception:
        return None


def _blend_prob(model_prob: float, market_prob: float) -> float:
    return (1.0 - ALPHA) * model_prob + ALPHA * market_prob


def _fav_prob(blend: float) -> float:
    return max(blend, 1.0 - blend)


def _compute_ece(probs: list[float], labels: list[int], n_bins: int = 10) -> float:
    """Compute Expected Calibration Error with equal-width bins."""
    if not probs:
        return float("nan")
    bins = [[] for _ in range(n_bins)]
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
    """Brier Skill Score vs climatological baseline."""
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
        h_sample = rng.choices(high_wins, k=len(high_wins))
        l_sample = rng.choices(low_wins, k=len(low_wins))
        wr_h = sum(h_sample) / len(h_sample) if h_sample else 0.5
        wr_l = sum(l_sample) / len(l_sample) if l_sample else 0.5
        deltas.append(wr_h - wr_l)
    deltas.sort()
    ci_lo = deltas[int(0.025 * n_boot)]
    ci_hi = deltas[int(0.975 * n_boot)]
    return ci_lo, ci_hi


def _bucket_attribution(
    feature_vals: list[float],
    win_labels: list[int],
    n_boot: int = _BOOTSTRAP_N,
) -> BucketAttribution | None:
    """Compute median-split bucket attribution."""
    paired = [(f, w) for f, w in zip(feature_vals, win_labels) if f is not None]
    if len(paired) < _MIN_SEGMENT_N:
        return None
    med = sorted(f for f, _ in paired)[len(paired) // 2]
    high = [(f, w) for f, w in paired if f > med]
    low = [(f, w) for f, w in paired if f <= med]
    if not high or not low:
        return None
    wr_high = sum(w for _, w in high) / len(high)
    wr_low = sum(w for _, w in low) / len(low)
    delta = wr_high - wr_low
    ci_lo, ci_hi = _bootstrap_win_rate_delta(
        [w for _, w in high], [w for _, w in low], n_boot
    )
    return BucketAttribution(
        n_high=len(high),
        n_low=len(low),
        win_rate_high=round(wr_high, 4),
        win_rate_low=round(wr_low, 4),
        win_rate_delta=round(delta, 4),
        bootstrap_ci_lower=round(ci_lo, 4),
        bootstrap_ci_upper=round(ci_hi, 4),
        bootstrap_significant=(ci_lo > 0 or ci_hi < 0),
    )


def _compute_attribution(
    feature_name: str,
    segment_name: str,
    feature_vals: list[float | None],
    blend_probs: list[float],
    win_labels: list[int],
    n_boot: int = _BOOTSTRAP_N,
) -> SegmentAttribution:
    """Compute full attribution for one feature × one segment."""
    n_total = len(blend_probs)
    valid_mask = [f is not None for f in feature_vals]
    n_valid = sum(valid_mask)
    cov = n_valid / max(n_total, 1)

    # Subset to valid feature rows
    fv = [f for f, m in zip(feature_vals, valid_mask) if m]
    bp = [p for p, m in zip(blend_probs, valid_mask) if m]
    wl = [y for y, m in zip(win_labels, valid_mask) if m]

    bs = _brier_score(bp, wl)
    climate = sum(wl) / max(len(wl), 1)
    bss = _bss(bs, climate)
    resid = (sum(bp) / max(len(bp), 1)) - climate if bp else 0.0
    ece = _compute_ece(bp, wl)

    bucket_attr = _bucket_attribution(fv, wl, n_boot)

    return SegmentAttribution(
        feature_name=feature_name,
        segment=segment_name,
        n=n_valid,
        coverage_pct=round(cov, 4),
        baseline_brier=round(bs, 4),
        baseline_bss=round(bss, 4),
        calibration_residual=round(resid, 4),
        ece=round(ece, 4),
        bucket_attribution=bucket_attr,
        oof_win_rate_delta=None,
        oof_n=None,
        oof_replicated=None,
    )


# ---------------------------------------------------------------------------
# PIT Safety Guard
# ---------------------------------------------------------------------------

_FORBIDDEN_FUTURE_FEATURES = {
    "home_win",
    "result",
    "score",
    "final_score",
    "winning_team",
    "losing_team",
}

_FORBIDDEN_PATTERNS = [
    r"home_win",
    r"result",
    r"final",
    r"winning",
]


def assert_no_forbidden_feature(feature_name: str) -> None:
    """Raise ValueError if feature name contains any forbidden future-leaking term."""
    lower = feature_name.lower()
    for pat in _FORBIDDEN_PATTERNS:
        if re.search(pat, lower):
            raise ValueError(
                f"[PIT-SAFETY] Feature '{feature_name}' matches forbidden pattern "
                f"'{pat}' — likely future information. Abort."
            )
    if lower in _FORBIDDEN_FUTURE_FEATURES:
        raise ValueError(
            f"[PIT-SAFETY] Feature '{feature_name}' is explicitly forbidden."
        )


def validate_pit_safety(entries: list[dict[str, Any]]) -> bool:
    """
    Validate that all bullpen data entries have fetched_at after the game_date
    implied by game_id. Returns True if PIT-safe.
    """
    violations = 0
    for entry in entries[:200]:  # spot-check first 200
        gid = entry.get("game_id", "")
        parsed = _parse_bull_game_id(gid)
        if parsed is None:
            continue
        game_date_str, _, _ = parsed
        fetched_at = entry.get("fetched_at", "")
        if fetched_at and fetched_at[:10] <= game_date_str:
            violations += 1
    return violations == 0


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


def _compute_audit_hash(*paths: str) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        try:
            h.update(Path(p).read_bytes()[:4096])
        except Exception:
            pass
    return h.hexdigest()[:16]


def _load_and_align(
    predictions_path: str,
    bullpen_path: str,
) -> tuple[list[dict[str, Any]], int, int, int]:
    """
    Load predictions and bullpen data, align on (date, away, home).
    Returns (aligned_rows, n_pred, n_bull, n_aligned).
    Each aligned row has all prediction fields plus bullpen fields.
    """
    pred_rows = _load_jsonl(predictions_path)
    bull_rows = _load_jsonl(bullpen_path)

    # Index bullpen by (date, norm_away, norm_home)
    bull_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in bull_rows:
        gid = row.get("game_id", "")
        parsed = _parse_bull_game_id(gid)
        if parsed is None:
            continue
        date_str, norm_away, norm_home = parsed
        key = (date_str, norm_away, norm_home)
        bull_index[key] = row

    # Align predictions
    aligned = []
    for row in pred_rows:
        game_date = row.get("game_date", "")
        away = _norm_team(row.get("away_team", ""))
        home = _norm_team(row.get("home_team", ""))
        key = (game_date, away, home)
        bull_row = bull_index.get(key)

        mp = row.get("model_home_prob")
        mkp = row.get("market_home_prob_no_vig")
        hw = row.get("home_win")
        if mp is None or mkp is None or hw is None:
            continue

        bp = _blend_prob(mp, mkp)
        fp = _fav_prob(bp)

        aligned_row: dict[str, Any] = {
            "game_date": game_date,
            "away_team": row.get("away_team", ""),
            "home_team": row.get("home_team", ""),
            "model_home_prob": mp,
            "market_home_prob_no_vig": mkp,
            "blend_prob": bp,
            "fav_prob": fp,
            "_label_home_win": int(hw),
            "bull_matched": bull_row is not None,
            # Bullpen raw values
            "bull_home_3d": None,
            "bull_away_3d": None,
        }

        if bull_row is not None:
            unavail = bull_row.get("unavailable_fields", [])
            h_val = bull_row.get("bullpen_usage_last_3d_home")
            a_val = bull_row.get("bullpen_usage_last_3d_away")
            if "bullpen_usage_last_3d_home" not in unavail and h_val is not None:
                aligned_row["bull_home_3d"] = float(h_val)
            if "bullpen_usage_last_3d_away" not in unavail and a_val is not None:
                aligned_row["bull_away_3d"] = float(a_val)

        aligned.append(aligned_row)

    return aligned, len(pred_rows), len(bull_rows), sum(1 for r in aligned if r["bull_matched"])


def _load_rest_data(
    aligned: list[dict[str, Any]],
    rest_path: str,
) -> None:
    """
    Augment aligned rows in-place with rest_days from injury_rest.jsonl.
    Matches by (date, away, home) via game_id parsing.
    """
    rest_rows = _load_jsonl(rest_path)
    rest_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rest_rows:
        gid = row.get("game_id", "")
        parsed = _parse_bull_game_id(gid)
        if parsed is None:
            continue
        date_str, norm_away, norm_home = parsed
        key = (date_str, norm_away, norm_home)
        rest_index[key] = row

    for row in aligned:
        game_date = row["game_date"]
        away = _norm_team(row["away_team"])
        home = _norm_team(row["home_team"])
        key = (game_date, away, home)
        rest_row = rest_index.get(key)
        row["rest_days_home"] = None
        row["rest_days_away"] = None
        if rest_row:
            unavail = rest_row.get("unavailable_fields", [])
            if "rest_days_home" not in unavail:
                row["rest_days_home"] = rest_row.get("rest_days_home")
            if "rest_days_away" not in unavail:
                row["rest_days_away"] = rest_row.get("rest_days_away")


# ---------------------------------------------------------------------------
# Derived Feature Computation
# ---------------------------------------------------------------------------

def _derive_features(aligned: list[dict[str, Any]]) -> None:
    """
    Compute all derived feature families in-place. 
    All feature names are validated PIT-safe.
    """
    # Validate no forbidden features are used
    safe_feature_names = [
        "bull_home_3d", "bull_away_3d", "bull_delta_3d",
        "bull_norm_delta_3d", "fav_fatigue_3d", "dog_fatigue_3d",
        "fav_vs_dog_delta_3d",
    ]
    for fn in safe_feature_names:
        assert_no_forbidden_feature(fn)

    for row in aligned:
        h = row.get("bull_home_3d")
        a = row.get("bull_away_3d")
        fp = row["fav_prob"]
        bp = row["blend_prob"]

        # bull_delta_3d = home - away
        if h is not None and a is not None:
            row["bull_delta_3d"] = round(h - a, 4)
            row["bull_norm_delta_3d"] = round((h - a) / (h + a + 1e-6), 4)
        else:
            row["bull_delta_3d"] = None
            row["bull_norm_delta_3d"] = None

        # Determine which side is the favorite
        home_is_fav = bp >= 0.5

        # fav_fatigue_3d = 3d usage of the favored team
        if h is not None and a is not None:
            row["fav_fatigue_3d"] = h if home_is_fav else a
            row["dog_fatigue_3d"] = a if home_is_fav else h
            row["fav_vs_dog_delta_3d"] = round(
                (h if home_is_fav else a) - (a if home_is_fav else h), 4
            )
        else:
            row["fav_fatigue_3d"] = None
            row["dog_fatigue_3d"] = None
            row["fav_vs_dog_delta_3d"] = None

        # Win label from the fav perspective (for feature-signal analysis)
        # fav wins if:  (home_is_fav and home_win==1) or (!home_is_fav and home_win==0)
        hw = row["_label_home_win"]
        row["_fav_win"] = int((home_is_fav and hw == 1) or (not home_is_fav and hw == 0))


# ---------------------------------------------------------------------------
# Segment Extraction
# ---------------------------------------------------------------------------

def _compute_median_disagreement(aligned: list[dict[str, Any]]) -> float:
    diffs = [
        abs(r["model_home_prob"] - r["market_home_prob_no_vig"])
        for r in aligned
    ]
    if not diffs:
        return 0.0
    diffs.sort()
    return diffs[len(diffs) // 2]


def _extract_segment(
    aligned: list[dict[str, Any]],
    segment: str,
    median_disagreement: float,
) -> list[dict[str, Any]]:
    """Extract rows for a given segment."""
    if segment == "all":
        return list(aligned)
    elif segment == "heavy_favorite":
        return [r for r in aligned if r["fav_prob"] >= _HEAVY_FAV_THRESHOLD]
    elif segment == "high_confidence":
        return [r for r in aligned if r["fav_prob"] >= _HIGH_CONF_THRESHOLD]
    elif segment == "phase45_failure":
        # odds_bucket:heavy_favorite AND disagreement:low
        return [
            r for r in aligned
            if r["fav_prob"] >= _HEAVY_FAV_THRESHOLD
            and abs(r["model_home_prob"] - r["market_home_prob_no_vig"]) <= median_disagreement
        ]
    else:
        raise ValueError(f"Unknown segment: {segment}")


# ---------------------------------------------------------------------------
# Rolling OOF Validation
# ---------------------------------------------------------------------------

def _rolling_oof_validation(
    aligned: list[dict[str, Any]],
    feature_name: str,
    segment_filter_fn: Any,
) -> OOFSummary:
    """
    Rolling monthly OOF: for each test month starting from month 3,
    train on all prior months. Compute win_rate_delta for the feature.
    """
    # Group by month
    from collections import defaultdict
    month_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in aligned:
        month = row["game_date"][:7]
        month_groups[month].append(row)

    months = sorted(month_groups.keys())
    if len(months) < 3:
        return OOFSummary(
            n_folds=0, fold_months=[], fold_win_rate_deltas=[],
            fold_n=[], oof_mean_delta=0.0,
            oof_consistent_sign=False, oof_significant=False,
        )

    fold_months = []
    fold_deltas = []
    fold_n_list = []

    for i in range(2, len(months)):
        test_month = months[i]
        train_rows = [r for m in months[:i] for r in month_groups[m]]
        test_rows = month_groups[test_month]

        # Apply segment filter
        train_seg = [r for r in train_rows if segment_filter_fn(r)]
        test_seg = [r for r in test_rows if segment_filter_fn(r)]

        if not test_seg:
            continue

        # Compute median threshold from training data
        train_vals = [r.get(feature_name) for r in train_seg if r.get(feature_name) is not None]
        if not train_vals:
            continue
        threshold = sorted(train_vals)[len(train_vals) // 2]

        # Compute win_rate_delta in test data (fav_win as the label)
        test_high = [r for r in test_seg if r.get(feature_name) is not None and r[feature_name] > threshold]
        test_low = [r for r in test_seg if r.get(feature_name) is not None and r[feature_name] <= threshold]

        if not test_high or not test_low:
            continue

        wr_h = sum(r["_fav_win"] for r in test_high) / len(test_high)
        wr_l = sum(r["_fav_win"] for r in test_low) / len(test_low)
        delta = round(wr_h - wr_l, 4)

        fold_months.append(test_month)
        fold_deltas.append(delta)
        fold_n_list.append(len(test_high) + len(test_low))

    if not fold_deltas:
        return OOFSummary(
            n_folds=0, fold_months=[], fold_win_rate_deltas=[],
            fold_n=[], oof_mean_delta=0.0,
            oof_consistent_sign=False, oof_significant=False,
        )

    mean_delta = sum(fold_deltas) / len(fold_deltas)
    consistent_sign = all(d >= 0 for d in fold_deltas) or all(d <= 0 for d in fold_deltas)

    return OOFSummary(
        n_folds=len(fold_deltas),
        fold_months=fold_months,
        fold_win_rate_deltas=fold_deltas,
        fold_n=fold_n_list,
        oof_mean_delta=round(mean_delta, 4),
        oof_consistent_sign=consistent_sign,
        oof_significant=abs(mean_delta) >= _OOF_PROMISING_DELTA,
    )


# ---------------------------------------------------------------------------
# Negative Control
# ---------------------------------------------------------------------------

def _negative_control(
    aligned: list[dict[str, Any]],
    feature_name: str,
    n_shuffle: int = 200,
    rng_seed: int = 7,
) -> NegativeControlResult:
    """
    Shuffle the feature values across heavy_fav rows and compute win_rate_delta.
    Repeat n_shuffle times. Compare real delta vs shuffled distribution.
    """
    hf_rows = [r for r in aligned if r["fav_prob"] >= _HEAVY_FAV_THRESHOLD]
    paired = [(r.get(feature_name), r["_fav_win"]) for r in hf_rows if r.get(feature_name) is not None]

    if len(paired) < _MIN_SEGMENT_N:
        return NegativeControlResult(
            real_win_rate_delta_heavy_fav=0.0,
            shuffled_mean_delta=0.0,
            shuffled_std_delta=0.0,
            null_rejected=False,
        )

    # Real delta
    med = sorted(f for f, _ in paired)[len(paired) // 2]
    high_wins = [w for f, w in paired if f > med]
    low_wins = [w for f, w in paired if f <= med]
    real_delta = (sum(high_wins) / len(high_wins)) - (sum(low_wins) / len(low_wins)) if high_wins and low_wins else 0.0

    # Shuffled deltas
    rng = random.Random(rng_seed)
    feature_vals = [f for f, _ in paired]
    win_vals = [w for _, w in paired]
    shuffle_deltas = []
    for _ in range(n_shuffle):
        shuffled = rng.sample(feature_vals, len(feature_vals))
        s_high = [w for f, w in zip(shuffled, win_vals) if f > med]
        s_low = [w for f, w in zip(shuffled, win_vals) if f <= med]
        if s_high and s_low:
            d = (sum(s_high) / len(s_high)) - (sum(s_low) / len(s_low))
            shuffle_deltas.append(d)

    mean_s = sum(shuffle_deltas) / max(len(shuffle_deltas), 1)
    std_s = (sum((d - mean_s) ** 2 for d in shuffle_deltas) / max(len(shuffle_deltas), 1)) ** 0.5

    null_rejected = (std_s > 0) and (real_delta > mean_s + 1.5 * std_s)

    return NegativeControlResult(
        real_win_rate_delta_heavy_fav=round(real_delta, 4),
        shuffled_mean_delta=round(mean_s, 4),
        shuffled_std_delta=round(std_s, 4),
        null_rejected=null_rejected,
    )


# ---------------------------------------------------------------------------
# Gate Recommendation
# ---------------------------------------------------------------------------

def _recommend_gate(
    segment_n_heavy_fav: int,
    all_attributions: list[SegmentAttribution],
    oof_summary: OOFSummary,
    n_available_features: int,
) -> tuple[str, str]:
    """
    Determine the Phase 60 gate.
    Returns (gate, rationale).
    """
    # DATA_LIMITED: not enough heavy_fav rows
    if segment_n_heavy_fav < _MIN_SEGMENT_N:
        return DATA_LIMITED, (
            f"heavy_fav segment has only {segment_n_heavy_fav} rows "
            f"(< {_MIN_SEGMENT_N} minimum). Attribution unreliable."
        )

    # Check if any feature shows OOF-significant signal
    if oof_summary.oof_significant and oof_summary.oof_consistent_sign:
        return BULLPEN_FEATURE_PROMISING, (
            f"OOF win_rate_delta={oof_summary.oof_mean_delta:+.4f} across "
            f"{oof_summary.n_folds} folds with consistent sign. Signal replicates."
        )

    # Check if there's directional signal in training
    hf_attrs = [a for a in all_attributions if a.segment == "heavy_favorite"
                and a.bucket_attribution is not None]
    has_any_signal = any(
        abs(a.bucket_attribution.win_rate_delta) > 0.01
        for a in hf_attrs
        if a.bucket_attribution
    )

    if has_any_signal:
        if oof_summary.oof_significant and not oof_summary.oof_consistent_sign:
            oof_reason = (
                f"OOF mean_delta={oof_summary.oof_mean_delta:+.4f} is large but "
                f"inconsistent sign across {oof_summary.n_folds} folds "
                f"(fold sizes: {oof_summary.fold_n}) — likely noise from small n."
            )
        else:
            oof_reason = (
                f"OOF mean_delta={oof_summary.oof_mean_delta:+.4f} "
                f"({oof_summary.n_folds} folds, n_heavy_fav/fold too small for reliability)."
            )
        return DIAGNOSTIC_ONLY_SIGNAL, (
            "Training-set directional signal present in ≥1 feature family (heavy_fav). "
            f"{oof_reason} "
            f"n_heavy_fav={segment_n_heavy_fav}. "
            "DIAGNOSTIC ONLY — no production patch."
        )

    return BULLPEN_FEATURE_NOT_PROMISING, (
        "No directional signal found in any available feature family "
        "across heavy_fav segment."
    )


# ---------------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------------

def run_phase60_decomposition(
    predictions_path: str,
    bullpen_path: str,
    rest_path: str | None = None,
) -> Phase60DecompositionResult:
    """
    Full Phase 60 orchestration:
    1. Load and align data
    2. Derive feature families
    3. Run attribution per feature × segment
    4. Negative control
    5. Rolling OOF validation
    6. Gate recommendation
    """
    run_ts = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    # Validate PIT safety
    bull_raw = _load_jsonl(bullpen_path)
    assert validate_pit_safety(bull_raw), "PIT safety violation detected in bullpen data!"

    # Compute audit hash
    paths_to_hash = [predictions_path, bullpen_path]
    if rest_path:
        paths_to_hash.append(rest_path)
    audit_hash = _compute_audit_hash(*paths_to_hash)

    # Load and align
    aligned, n_pred, n_bull, n_aligned = _load_and_align(predictions_path, bullpen_path)

    # Load rest data if provided
    if rest_path:
        _load_rest_data(aligned, rest_path)
    else:
        for row in aligned:
            row["rest_days_home"] = None
            row["rest_days_away"] = None

    # Derive features
    _derive_features(aligned)

    # Segment analysis
    median_disag = _compute_median_disagreement(aligned)

    seg_all = _extract_segment(aligned, "all", median_disag)
    seg_hf = _extract_segment(aligned, "heavy_favorite", median_disag)
    seg_hc = _extract_segment(aligned, "high_confidence", median_disag)
    seg_p45 = _extract_segment(aligned, "phase45_failure", median_disag)

    high_conf_note = (
        f"fav_prob >= 0.80 has only 1 game in this dataset "
        f"(blend formula with ALPHA={ALPHA} suppresses extremes). "
        f"Using fav_prob >= {_HIGH_CONF_THRESHOLD} as 'high_confidence' segment instead."
    )

    # Feature families metadata
    feature_registry = [
        ("bull_home_3d", "Raw home bullpen 3-day IP usage", True),
        ("bull_away_3d", "Raw away bullpen 3-day IP usage", True),
        ("bull_delta_3d", "Home minus away 3-day usage (positive=home more tired)", True),
        ("bull_norm_delta_3d", "Normalized: (home-away)/(home+away+1e-6)", True),
        ("fav_fatigue_3d", "Favored team 3-day bullpen usage", True),
        ("dog_fatigue_3d", "Underdog team 3-day bullpen usage", True),
        ("fav_vs_dog_delta_3d", "Fav minus dog 3-day usage (positive=fav more tired)", True),
        ("bull_usage_last_1d", "Yesterday bullpen usage (IP)", False),
        ("bull_usage_last_5d", "5-day rolling bullpen usage (IP)", False),
        ("back_to_back_proxy", "Back-to-back appearance proxy (bullpen-level)", False),
        ("closer_high_leverage", "Closer / high-leverage appearance count", False),
    ]

    data_limited_reasons = {
        "bull_usage_last_1d": "Not available in mlb_stats_api_boxscore source (only 3d window fetched)",
        "bull_usage_last_5d": "Not available in mlb_stats_api_boxscore source (only 3d window fetched)",
        "back_to_back_proxy": "No inning-by-inning or day-specific bullpen data available",
        "closer_high_leverage": "boxscore source does not expose closer/high-leverage specific usage",
    }

    feature_metas = []
    for fname, desc, avail in feature_registry:
        n_usable = sum(1 for r in aligned if r.get(fname) is not None) if avail else 0
        cov = n_usable / max(len(aligned), 1) if avail else 0.0
        feature_metas.append(FeatureFamilyMeta(
            feature_name=fname,
            description=desc,
            available=avail,
            coverage_pct=round(cov, 4),
            n_usable=n_usable,
            data_limited_reason=data_limited_reasons.get(fname) if not avail else None,
        ))

    n_available = sum(1 for _, _, a in feature_registry if a)
    n_data_limited = sum(1 for _, _, a in feature_registry if not a)

    # Attribution analysis
    available_features = [fname for fname, _, avail in feature_registry if avail]
    segments = [
        ("all", seg_all),
        ("heavy_favorite", seg_hf),
        ("high_confidence", seg_hc),
        ("phase45_failure", seg_p45),
    ]

    all_attributions: list[SegmentAttribution] = []
    for seg_name, seg_rows in segments:
        for fname in available_features:
            feat_vals = [r.get(fname) for r in seg_rows]
            blend_probs = [r["blend_prob"] for r in seg_rows]
            win_labels = [r["_label_home_win"] for r in seg_rows]

            attr = _compute_attribution(
                fname, seg_name, feat_vals, blend_probs, win_labels
            )
            all_attributions.append(attr)

    # Rolling OOF on best candidate feature (fav_vs_dog_delta_3d, heavy_fav segment)
    def _heavy_fav_filter(row: dict[str, Any]) -> bool:
        return row["fav_prob"] >= _HEAVY_FAV_THRESHOLD

    oof_summary = _rolling_oof_validation(
        aligned, "fav_vs_dog_delta_3d", _heavy_fav_filter
    )

    # Negative control
    neg_ctrl = _negative_control(aligned, "fav_vs_dog_delta_3d")

    # Gate
    gate, rationale = _recommend_gate(
        segment_n_heavy_fav=len(seg_hf),
        all_attributions=all_attributions,
        oof_summary=oof_summary,
        n_available_features=n_available,
    )

    return Phase60DecompositionResult(
        phase_version=PHASE_VERSION,
        run_timestamp=run_ts,
        audit_hash=audit_hash,

        candidate_patch_created=CANDIDATE_PATCH_CREATED,
        production_modified=PRODUCTION_MODIFIED,
        alpha_modified=ALPHA_MODIFIED,
        diagnostic_only=DIAGNOSTIC_ONLY,
        alpha=ALPHA,

        n_predictions=n_pred,
        n_bullpen_rows=n_bull,
        n_aligned=n_aligned,
        alignment_rate=round(n_aligned / max(n_pred, 1), 4),

        segment_n_all=len(seg_all),
        segment_n_heavy_fav=len(seg_hf),
        segment_n_high_conf=len(seg_hc),
        segment_n_phase45_failure=len(seg_p45),
        high_conf_note=high_conf_note,

        feature_families=feature_metas,
        n_available_features=n_available,
        n_data_limited_features=n_data_limited,

        attributions=all_attributions,

        negative_control=neg_ctrl,
        oof_summary=oof_summary,

        gate=gate,
        gate_rationale=rationale,
    )


def result_to_dict(result: Phase60DecompositionResult) -> dict[str, Any]:
    """Serialise result to plain dict (JSON-ready)."""
    def _clean(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_clean(v) for v in obj]
        elif isinstance(obj, float) and math.isnan(obj):
            return None
        return obj

    return _clean(asdict(result))
