"""
orchestrator/phase64b_full_season_attribution.py
=================================================
Phase 64-B — Full-Season StatsAPI Historical Bullpen Ingestion & Attribution

目標：
  Phase 64 使用 Phase63 SSOT（4 teams，coverage=0.1%）→ DATA_LIMITED。
  Phase 64-B 使用 bullpen_usage_3d.jsonl 全季資料（2430 筆）構建全季 SSOT，
  使 3d 特徵 coverage ≈ 96.7%，解鎖 meaningful attribution。

特徵集（15 個任務指定特徵）：
  [AVAILABLE 96.7%] bullpen_usage_last_3d_fav, _dog, rest_imbalance_3d,
                    bullpen_fatigue_favorite_side, bullpen_fatigue_underdog_side
  [DATA_LIMITED]    bullpen_usage_last_1d_fav/dog, _5d_fav/dog,
                    reliever_b2b_count_fav/dog, reliever_3in4_count_fav/dog,
                    closer_used_1d_fav, closer_used_2d_fav

安全常數（絕不修改）：
  CANDIDATE_PATCH_CREATED = False
  PRODUCTION_MODIFIED     = False
  ALPHA_MODIFIED          = False
  DIAGNOSTIC_ONLY         = True
  ALPHA                   = 0.40

Gate 決策標準（與 Phase64 一致）：
  DATA_LIMITED                       ← coverage < 10% threshold
  OVERFIT_RISK                       ← null_rejected AND shuffled_std large
  BULLPEN_GRANULAR_FEATURE_PROMISING ← OOF significant + bootstrap CI excludes 0
  DIAGNOSTIC_ONLY_SIGNAL             ← bootstrap CI excludes 0, OOF not consistent
  BULLPEN_GRANULAR_FEATURE_NOT_PROMISING ← no significant attribution

Phase 64-B 完成標記：PHASE_64B_FULL_SEASON_BULLPEN_INGESTION_ATTRIBUTION_VERIFIED
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Safety Constants — FROZEN
# ---------------------------------------------------------------------------
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
ALPHA_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
ALPHA: float = 0.40
PHASE_VERSION: str = "phase64b_full_season_attribution_v1"

# Phase 64 anchor (for backward-compatibility assertions)
_PHASE64_GATE = "DATA_LIMITED"
_PHASE64_AUDIT_HASH = "4923b662e37f0ca1"

# ---------------------------------------------------------------------------
# Gate Constants (same 5 as Phase 64)
# ---------------------------------------------------------------------------
BULLPEN_GRANULAR_FEATURE_PROMISING: str = "BULLPEN_GRANULAR_FEATURE_PROMISING"
DIAGNOSTIC_ONLY_SIGNAL: str = "DIAGNOSTIC_ONLY_SIGNAL"
DATA_LIMITED: str = "DATA_LIMITED"
OVERFIT_RISK: str = "OVERFIT_RISK"
BULLPEN_GRANULAR_FEATURE_NOT_PROMISING: str = "BULLPEN_GRANULAR_FEATURE_NOT_PROMISING"

# ---------------------------------------------------------------------------
# Thresholds (consistent with Phase 60/64)
# ---------------------------------------------------------------------------
_HEAVY_FAV_THRESHOLD: float = 0.70
_HIGH_CONF_THRESHOLD: float = 0.75
_MIN_SEGMENT_N: int = 20
_BOOTSTRAP_N: int = 1000
_OOF_PROMISING_DELTA: float = 0.02
_MIN_COVERAGE_RATE: float = 0.10
_OVERFIT_SIGMA: float = 1.5
_B_ALIGNMENT_GATE: float = 0.80  # Phase 64-B requires >= 80% 3d coverage

# ---------------------------------------------------------------------------
# Phase 64-B Feature Registry
# 15 task-specified features + 2 fatigue aliases
# (name, window_days, data_limited_initially, description)
# ---------------------------------------------------------------------------
_B_FEATURE_REGISTRY: list[tuple[str, int, bool, str]] = [
    # AVAILABLE — derived from bullpen_usage_3d.jsonl (96.7% coverage)
    ("bullpen_usage_last_3d_fav",       3, False, "Fav team bullpen IP last 3d"),
    ("bullpen_usage_last_3d_dog",       3, False, "Dog team bullpen IP last 3d"),
    ("bullpen_rest_imbalance_3d",       3, False, "Abs diff home/away 3d bullpen usage"),
    ("bullpen_fatigue_favorite_side",   3, False, "Fav 3d fatigue proxy (=3d_fav)"),
    ("bullpen_fatigue_underdog_side",   3, False, "Dog 3d fatigue proxy (=3d_dog)"),
    # DATA_LIMITED — require StatsAPI boxscore cache (empty in dry-run)
    ("bullpen_usage_last_1d_fav",       1, True, "Fav 1d [DATA_LIMITED: no 1d source]"),
    ("bullpen_usage_last_1d_dog",       1, True, "Dog 1d [DATA_LIMITED: no 1d source]"),
    ("bullpen_usage_last_5d_fav",       5, True, "Fav 5d [DATA_LIMITED: no 5d source]"),
    ("bullpen_usage_last_5d_dog",       5, True, "Dog 5d [DATA_LIMITED: no 5d source]"),
    ("reliever_b2b_count_fav",          2, True, "Fav b2b count [DATA_LIMITED]"),
    ("reliever_b2b_count_dog",          2, True, "Dog b2b count [DATA_LIMITED]"),
    ("reliever_3in4_count_fav",         4, True, "Fav 3in4 count [DATA_LIMITED]"),
    ("reliever_3in4_count_dog",         4, True, "Dog 3in4 count [DATA_LIMITED]"),
    ("closer_used_1d_fav",              1, True, "Fav closer yesterday [DATA_LIMITED]"),
    ("closer_used_2d_fav",              2, True, "Fav closer last 2d [DATA_LIMITED]"),
]

_B_AVAILABLE_FEATURES = frozenset(
    name for name, _, limited, _ in _B_FEATURE_REGISTRY if not limited
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FullSeasonAlignment:
    """Alignment stats between full-season SSOT and prediction dataset."""
    n_ssot_artifacts: int
    n_predictions: int
    n_aligned_3d: int          # Predictions matched to bull_3d (3d data available)
    n_unmatched: int
    alignment_rate: float      # n_aligned_3d / n_predictions
    coverage_sufficient: bool  # alignment_rate >= _B_ALIGNMENT_GATE


@dataclass
class BFeatureCoverage:
    """Coverage for a single Phase 64-B feature."""
    feature_name: str
    n_available: int
    n_total: int
    coverage_pct: float
    data_limited: bool
    data_limited_reason: str | None


@dataclass
class BBucketAttribution:
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
class BSegmentAttribution:
    """Attribution for one feature × one segment."""
    feature_name: str
    segment: str
    n: int
    coverage_pct: float
    brier: float | None
    bss: float | None
    calibration_residual: float
    ece: float | None
    bucket_attribution: BBucketAttribution | None
    oof_win_rate_delta: float | None
    oof_n: int | None
    oof_replicated: bool | None
    data_limited: bool
    data_limited_reason: str | None


@dataclass
class BNegativeControl:
    """Negative control: shuffled vs real feature delta."""
    feature_name: str
    segment: str
    real_win_rate_delta: float
    shuffled_mean_delta: float
    shuffled_std_delta: float
    null_rejected: bool
    overfit_risk: bool


@dataclass
class BOOFResult:
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
class Phase64BResult:
    """Full Phase 64-B attribution result."""
    phase_version: str
    run_timestamp: str

    # Safety constants snapshot
    candidate_patch_created: bool
    production_modified: bool
    alpha_modified: bool
    diagnostic_only: bool
    alpha: float

    # Phase 64 anchor
    phase64_gate: str
    phase64_audit_hash: str

    # Ingestion summary
    n_bull_3d_rows: int
    n_ssot_artifacts: int
    n_predictions: int

    # Alignment
    alignment: FullSeasonAlignment

    # Feature coverage (15 features)
    feature_coverage: list[BFeatureCoverage]
    n_available_features: int
    n_data_limited_features: int

    # Segment sizes
    segment_n_all: int
    segment_n_heavy_fav: int
    segment_n_high_conf: int

    # Phase 60 baseline replication (3d)
    phase60_baseline_replication: dict[str, Any]

    # Attribution results
    attributions: list[BSegmentAttribution]

    # Negative controls
    negative_controls: list[BNegativeControl]

    # OOF validation
    oof_results: list[BOOFResult]

    # Summary
    any_bootstrap_significant: bool

    # Gate
    gate: str
    gate_rationale: str
    next_step: str

    # Completion marker
    completion_marker: str


# ---------------------------------------------------------------------------
# Utility: JSONL
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


# ---------------------------------------------------------------------------
# Team normalisation (consistent with Phase 64)
# ---------------------------------------------------------------------------

def _norm_team(name: str) -> str:
    return re.sub(r"[^A-Z0-9_]", "_", name.upper().replace(" ", "_"))


def _blend_prob(model_prob: float, market_prob: float) -> float:
    """FROZEN blend: blend = (1-α)*model + α*market."""
    return (1.0 - ALPHA) * model_prob + ALPHA * market_prob


def _fav_prob(blend: float) -> float:
    return max(blend, 1.0 - blend)


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------

def _brier_score(probs: list[float], labels: list[int]) -> float:
    if not probs:
        return float("nan")
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(probs)


def _bss(bs: float, climate_rate: float) -> float:
    base = climate_rate * (1 - climate_rate)
    if base == 0:
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
    deltas = []
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
) -> BBucketAttribution | None:
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
    return BBucketAttribution(
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
# bull_3d game_id parsing
# ---------------------------------------------------------------------------

def _parse_bull3d_game_id(game_id: str) -> tuple[str, str, str] | None:
    """Parse bull_3d game_id → (date_str, norm_away, norm_home)."""
    try:
        rest = game_id.replace("MLB-", "", 1)
        date_str = rest[:10].replace("_", "-")
        datetime.strptime(date_str, "%Y-%m-%d")  # validate
        after_date = rest[10:]
        at_idx = after_date.rfind("-AT-")
        if at_idx == -1:
            return None
        home_raw = after_date[at_idx + 4:]
        before_at = after_date[:at_idx].lstrip("-")
        time_end = before_at.find("-")
        if time_end == -1:
            return None
        away_raw = before_at[time_end + 1:]
        if not home_raw or not away_raw:
            return None
        return date_str, _norm_team(away_raw), _norm_team(home_raw)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Build full-season bull_3d index (date, norm_team) → (home_3d, away_3d)
# ---------------------------------------------------------------------------

def _build_bull3d_index(
    bull_3d_path: str,
) -> dict[tuple[str, str], tuple[float | None, float | None]]:
    """
    Build index: (date, norm_home_team) → (home_3d, away_3d).
    Also creates (date, norm_away_team) → (home_3d, away_3d).
    Used for per-team lookups.
    Returns unified dict: (date, norm_team) → {"home_3d": v, "away_3d": v, "side": side}
    """
    bull_rows = _load_jsonl(bull_3d_path)
    # Game-level index: (date, norm_home) → row
    game_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in bull_rows:
        gid = row.get("game_id", "")
        parsed = _parse_bull3d_game_id(gid)
        if parsed:
            date, away, home = parsed
            game_index[(date, away, home)] = row
    return game_index


def _build_team_index(
    bull_3d_path: str,
) -> dict[tuple[str, str], dict[str, Any]]:
    """
    Build per-team index: (date, norm_team) → {3d_val, side, game_id, ...}.
    For each game, both home and away get their own entry.
    """
    bull_rows = _load_jsonl(bull_3d_path)
    team_index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in bull_rows:
        gid = row.get("game_id", "")
        parsed = _parse_bull3d_game_id(gid)
        if parsed is None:
            continue
        date, norm_away, norm_home = parsed
        home_3d = row.get("bullpen_usage_last_3d_home")
        away_3d = row.get("bullpen_usage_last_3d_away")
        if home_3d is not None:
            team_index[(date, norm_home)] = {
                "game_date": date,
                "team_norm": norm_home,
                "side": "home",
                "bullpen_usage_last_3d": float(home_3d),
                "bullpen_usage_last_1d": None,
                "bullpen_usage_last_5d": None,
                "reliever_back_to_back_count": None,
                "reliever_three_in_four_days_count": None,
                "closer_used_last_1d": None,
                "closer_used_last_2d": None,
                "game_id": gid,
            }
        if away_3d is not None:
            team_index[(date, norm_away)] = {
                "game_date": date,
                "team_norm": norm_away,
                "side": "away",
                "bullpen_usage_last_3d": float(away_3d),
                "bullpen_usage_last_1d": None,
                "bullpen_usage_last_5d": None,
                "reliever_back_to_back_count": None,
                "reliever_three_in_four_days_count": None,
                "closer_used_last_1d": None,
                "closer_used_last_2d": None,
                "game_id": gid,
            }
    return team_index


# ---------------------------------------------------------------------------
# Derive Phase 64-B features for a game row
# ---------------------------------------------------------------------------

def _derive_b_features(
    row: dict[str, Any],
    team_index: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    """
    Derive all Phase 64-B granular features for one prediction row.
    Uses team_index (date, norm_team) → ssot artifact.

    PIT-safe: only uses game_date (prediction date); no outcome data.
    """
    game_date = str(row.get("game_date", ""))
    home_team = str(row.get("home_team", ""))
    away_team = str(row.get("away_team", ""))

    blend = _blend_prob(
        float(row.get("model_home_prob", 0.5)),
        float(row.get("market_home_prob_no_vig", 0.5)),
    )
    home_is_fav = blend >= 0.50
    fav_team = home_team if home_is_fav else away_team
    dog_team = away_team if home_is_fav else home_team

    home_art = team_index.get((game_date, _norm_team(home_team)))
    away_art = team_index.get((game_date, _norm_team(away_team)))
    fav_art = team_index.get((game_date, _norm_team(fav_team)))
    dog_art = team_index.get((game_date, _norm_team(dog_team)))

    def _get(art: dict | None, key: str) -> Any | None:
        return art.get(key) if art else None

    home_3d = _get(home_art, "bullpen_usage_last_3d")
    away_3d = _get(away_art, "bullpen_usage_last_3d")
    fav_3d = _get(fav_art, "bullpen_usage_last_3d")
    dog_3d = _get(dog_art, "bullpen_usage_last_3d")

    rest_imbalance = (
        abs(home_3d - away_3d)
        if (home_3d is not None and away_3d is not None)
        else None
    )

    return {
        # AVAILABLE (96.7%)
        "bullpen_usage_last_3d_fav":       fav_3d,
        "bullpen_usage_last_3d_dog":       dog_3d,
        "bullpen_rest_imbalance_3d":       rest_imbalance,
        "bullpen_fatigue_favorite_side":   fav_3d,   # alias for 3d_fav
        "bullpen_fatigue_underdog_side":   dog_3d,   # alias for 3d_dog
        # DATA_LIMITED (always None in dry-run / no cache)
        "bullpen_usage_last_1d_fav":       None,
        "bullpen_usage_last_1d_dog":       None,
        "bullpen_usage_last_5d_fav":       None,
        "bullpen_usage_last_5d_dog":       None,
        "reliever_b2b_count_fav":          None,
        "reliever_b2b_count_dog":          None,
        "reliever_3in4_count_fav":         None,
        "reliever_3in4_count_dog":         None,
        "closer_used_1d_fav":              None,
        "closer_used_2d_fav":              None,
    }


# ---------------------------------------------------------------------------
# Alignment: align predictions with full-season SSOT
# ---------------------------------------------------------------------------

def _align_predictions_with_bull3d(
    predictions_path: str,
    bull_3d_path: str,
) -> tuple[list[dict[str, Any]], FullSeasonAlignment, int]:
    """
    Load predictions, build team_index from bull_3d, derive Phase 64-B features.
    Returns (enriched_rows, alignment, n_ssot_artifacts).
    """
    pred_rows = _load_jsonl(predictions_path)
    team_index = _build_team_index(bull_3d_path)

    n_aligned = 0
    enriched: list[dict[str, Any]] = []
    for row in pred_rows:
        features = _derive_b_features(row, team_index)
        combined = dict(row)
        combined.update(features)
        # Tag alignment: True if home 3d or away 3d is available
        aligned = features["bullpen_usage_last_3d_fav"] is not None
        combined["_b_aligned"] = aligned
        if aligned:
            n_aligned += 1
        enriched.append(combined)

    n_pred = len(pred_rows)
    n_ssot = len(team_index)
    alignment_rate = n_aligned / max(n_pred, 1)

    return enriched, FullSeasonAlignment(
        n_ssot_artifacts=n_ssot,
        n_predictions=n_pred,
        n_aligned_3d=n_aligned,
        n_unmatched=n_pred - n_aligned,
        alignment_rate=round(alignment_rate, 4),
        coverage_sufficient=alignment_rate >= _B_ALIGNMENT_GATE,
    ), n_ssot


# ---------------------------------------------------------------------------
# Feature coverage
# ---------------------------------------------------------------------------

def _compute_b_coverage(
    enriched_rows: list[dict[str, Any]],
) -> list[BFeatureCoverage]:
    n_total = len(enriched_rows)
    coverage: list[BFeatureCoverage] = []
    for fname, window, inherently_limited, desc in _B_FEATURE_REGISTRY:
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
        coverage.append(BFeatureCoverage(
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

def _extract_segment(rows: list[dict[str, Any]], segment: str) -> list[dict[str, Any]]:
    if segment == "all":
        return rows
    result = []
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
# Attribution for one feature × segment
# ---------------------------------------------------------------------------

def _compute_b_attribution(
    feature_name: str,
    segment_name: str,
    rows: list[dict[str, Any]],
    data_limited: bool,
    data_limited_reason: str | None,
    n_boot: int = _BOOTSTRAP_N,
) -> BSegmentAttribution:
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

    return BSegmentAttribution(
        feature_name=feature_name,
        segment=segment_name,
        n=n_valid,
        coverage_pct=round(cov, 4),
        brier=round(bs, 4) if not math.isnan(bs) else None,
        bss=round(bss_val, 4) if not math.isnan(bss_val) else None,
        calibration_residual=round(resid, 4),
        ece=round(ece, 4) if not math.isnan(ece) else None,
        bucket_attribution=bucket_attr,
        oof_win_rate_delta=None,
        oof_n=None,
        oof_replicated=None,
        data_limited=data_limited,
        data_limited_reason=data_limited_reason,
    )


# ---------------------------------------------------------------------------
# Negative Control
# ---------------------------------------------------------------------------

def _compute_b_negative_control(
    rows: list[dict[str, Any]],
    feature_name: str,
    segment: str = "heavy_favorite",
    n_shuffles: int = 100,
    rng_seed: int = 99,
) -> BNegativeControl:
    seg_rows = _extract_segment(rows, segment)
    fv = [r.get(feature_name) for r in seg_rows]
    wl = [int(r.get("home_win", 0)) for r in seg_rows]

    paired = [(f, w) for f, w in zip(fv, wl) if f is not None]
    if len(paired) < _MIN_SEGMENT_N:
        return BNegativeControl(
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

    rng = random.Random(rng_seed)
    shuffled_deltas: list[float] = []
    all_fv = [f for f, _ in paired]
    all_wl = [w for _, w in paired]
    for _ in range(n_shuffles):
        sfv = rng.sample(all_fv, len(all_fv))
        s_med = sorted(sfv)[len(sfv) // 2]
        s_high = [all_wl[i] for i, f in enumerate(sfv) if f > s_med]
        s_low = [all_wl[i] for i, f in enumerate(sfv) if f <= s_med]
        if s_high and s_low:
            shuffled_deltas.append(
                sum(s_high) / len(s_high) - sum(s_low) / len(s_low)
            )

    if not shuffled_deltas:
        sm, ss = 0.0, 0.0
        null_rejected = False
    else:
        sm = sum(shuffled_deltas) / len(shuffled_deltas)
        ss = (sum((d - sm) ** 2 for d in shuffled_deltas) / len(shuffled_deltas)) ** 0.5
        null_rejected = abs(real_delta) > abs(sm) + _OVERFIT_SIGMA * ss

    overfit_risk = null_rejected and ss > 0.10

    return BNegativeControl(
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

def _compute_b_oof(
    rows: list[dict[str, Any]],
    feature_name: str,
    segment: str = "heavy_favorite",
) -> BOOFResult:
    seg_rows = _extract_segment(rows, segment)

    def _ym(row: dict) -> str:
        return str(row.get("game_date", ""))[:7]

    months = sorted(set(_ym(r) for r in seg_rows))
    if len(months) < 2:
        return BOOFResult(
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
        return BOOFResult(
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

    return BOOFResult(
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
# Phase 60 Baseline Replication (same as Phase 64, using bull_3d directly)
# ---------------------------------------------------------------------------

def _replicate_phase60_baseline(
    enriched_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Replicate Phase 60 3d attribution using enriched prediction rows."""
    hf_rows = _extract_segment(enriched_rows, "heavy_favorite")
    hf_valid = [
        (r["bullpen_usage_last_3d_fav"], int(r.get("home_win", 0)))
        for r in hf_rows
        if r.get("bullpen_usage_last_3d_fav") is not None
    ]
    if not hf_valid:
        return {"status": "NO_DATA", "n": 0}

    fav_3d_vals = [v[0] for v in hf_valid]
    labels = [v[1] for v in hf_valid]
    bucket = _bucket_attribution(fav_3d_vals, labels, n_boot=_BOOTSTRAP_N)

    all_valid = [
        r for r in enriched_rows if r.get("bullpen_usage_last_3d_fav") is not None
    ]
    bp_all = [
        _blend_prob(
            float(r.get("model_home_prob", 0.5)),
            float(r.get("market_home_prob_no_vig", 0.5)),
        )
        for r in all_valid
    ]
    wl_all = [int(r.get("home_win", 0)) for r in all_valid]

    bs = _brier_score(bp_all, wl_all)
    climate = sum(wl_all) / max(len(wl_all), 1)

    return {
        "status": "REPLICATED",
        "n_all_aligned": len(all_valid),
        "n_heavy_fav": len(hf_valid),
        "brier": round(bs, 4),
        "bss": round(_bss(bs, climate), 4),
        "heavy_fav_win_rate": round(sum(labels) / max(len(labels), 1), 4),
        "heavy_fav_bucket_attribution": asdict(bucket) if bucket else None,
        "phase60_signal": "DIAGNOSTIC_ONLY_SIGNAL",
    }


# ---------------------------------------------------------------------------
# Gate Decision
# ---------------------------------------------------------------------------

def _decide_b_gate(
    alignment: FullSeasonAlignment,
    coverage_results: list[BFeatureCoverage],
    attributions: list[BSegmentAttribution],
    neg_controls: list[BNegativeControl],
    oof_results: list[BOOFResult],
) -> tuple[str, str, str]:
    """Decide Phase 64-B gate from evidence."""
    # Check coverage
    n_available = sum(1 for c in coverage_results if not c.data_limited)
    all_data_limited = n_available == 0
    cov_rate = alignment.alignment_rate

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
            f"All Phase 64-B features DATA_LIMITED. Alignment={n_available} available. "
            f"Coverage rate={cov_rate:.1%}. Cannot run attribution."
        )
        next_step = (
            "Verify bullpen_usage_3d.jsonl accessibility and run ingestion with "
            "full bull_3d data."
        )
    elif any_overfit:
        gate = OVERFIT_RISK
        rationale = (
            "Negative control indicates overfit risk: null rejected AND shuffled_std large. "
            "No production patch produced."
        )
        next_step = (
            "Disable fitted adjustment. Re-validate with fresh hold-out data "
            "(n >= 200 per segment)."
        )
    elif promising_oof and any_bootstrap_sig:
        gate = BULLPEN_GRANULAR_FEATURE_PROMISING
        rationale = (
            f"OOF consistent ({len(promising_oof)} features with n_folds>=3) "
            f"AND bootstrap CI excludes zero. Replicable signal found. "
            f"No production patch produced — paper-only gate."
        )
        next_step = (
            "Phase 65: Design paper-only bullpen feature patch gate. "
            "Use promising 3d features as candidate set."
        )
    elif any_bootstrap_sig:
        gate = DIAGNOSTIC_ONLY_SIGNAL
        rationale = (
            "Bootstrap CI excludes zero for some features but OOF not consistently significant. "
            "Directional 3d signal present but not robust enough for production. "
            "No production patch produced."
        )
        next_step = (
            "Enrich with 1d/5d/b2b/3in4 features via StatsAPI cache "
            "(set dry_run=False, fill boxscores_cache/). "
            "Re-run Phase 64-B with full granular data."
        )
    else:
        gate = BULLPEN_GRANULAR_FEATURE_NOT_PROMISING
        rationale = (
            "No bootstrap-significant attribution found for any 3d feature. "
            "OOF deltas inconsistent or weak. "
            "Bullpen 3d fatigue does not provide reliable signal above baseline. "
            "No production patch produced."
        )
        next_step = (
            "De-prioritise 3d bullpen attribution as primary signal. "
            "Investigate 1d/b2b granular features (requires StatsAPI cache). "
            "Consider SP fatigue, weather, park factor, rest as alternative signals."
        )

    return gate, rationale, next_step


# ---------------------------------------------------------------------------
# Main Orchestration
# ---------------------------------------------------------------------------

def run_phase64b_attribution(
    predictions_path: str,
    bull_3d_path: str,
    ssot_output_path: str | None = None,
    ingestion_summary_path: str | None = None,
) -> Phase64BResult:
    """
    Full Phase 64-B orchestration:
    1. Build full-season SSOT from bull_3d (ingestion step)
    2. Align predictions with SSOT
    3. Compute feature coverage
    4. Run attribution for available features
    5. Negative control + OOF
    6. Gate decision

    Safety:
    - CANDIDATE_PATCH_CREATED = False
    - PRODUCTION_MODIFIED = False
    - ALPHA_MODIFIED = False
    - DIAGNOSTIC_ONLY = True
    """
    assert not CANDIDATE_PATCH_CREATED, "Safety violation: CANDIDATE_PATCH_CREATED must be False"
    assert not PRODUCTION_MODIFIED, "Safety violation: PRODUCTION_MODIFIED must be False"
    assert not ALPHA_MODIFIED, "Safety violation: ALPHA_MODIFIED must be False"
    assert DIAGNOSTIC_ONLY, "Safety violation: DIAGNOSTIC_ONLY must be True"
    assert ALPHA == 0.40, f"Safety violation: ALPHA must be 0.40, got {ALPHA}"

    run_ts = datetime.now(timezone.utc).isoformat()

    # Step 1+2: Align predictions with full-season SSOT
    bull_rows = _load_jsonl(bull_3d_path)
    enriched_rows, alignment, n_ssot = _align_predictions_with_bull3d(
        predictions_path, bull_3d_path
    )

    # Step 3: Feature coverage
    feature_coverage = _compute_b_coverage(enriched_rows)
    n_avail = sum(1 for c in feature_coverage if not c.data_limited)
    n_limited = sum(1 for c in feature_coverage if c.data_limited)

    # Segment sizes
    n_all = len(enriched_rows)
    hf_rows = _extract_segment(enriched_rows, "heavy_favorite")
    hc_rows = _extract_segment(enriched_rows, "high_confidence")

    # Phase 60 baseline replication
    phase60_rep = _replicate_phase60_baseline(enriched_rows)

    # Step 4: Attribution for AVAILABLE features × "all" and "heavy_favorite" segments
    attributions: list[BSegmentAttribution] = []
    available_names = [
        (fname, window, limited, desc)
        for fname, window, limited, desc in _B_FEATURE_REGISTRY
        if not limited
    ]
    for fname, window, limited, desc in _B_FEATURE_REGISTRY:
        cov = next(c for c in feature_coverage if c.feature_name == fname)
        for seg in ["all", "heavy_favorite"]:
            seg_rows = _extract_segment(enriched_rows, seg)
            attr = _compute_b_attribution(
                feature_name=fname,
                segment_name=seg,
                rows=seg_rows,
                data_limited=cov.data_limited,
                data_limited_reason=cov.data_limited_reason,
            )
            # Link OOF result (filled below)
            attributions.append(attr)

    # Step 5a: Negative controls for available features on heavy_favorite segment
    neg_controls: list[BNegativeControl] = []
    for fname, _, limited, _ in _B_FEATURE_REGISTRY:
        if not limited:
            nc = _compute_b_negative_control(enriched_rows, fname, "heavy_favorite")
            neg_controls.append(nc)

    # Step 5b: OOF for available features on heavy_favorite segment
    oof_results: list[BOOFResult] = []
    for fname, _, limited, _ in _B_FEATURE_REGISTRY:
        if not limited:
            oof = _compute_b_oof(enriched_rows, fname, "heavy_favorite")
            oof_results.append(oof)

    # Step 6: Gate decision
    any_bootstrap_sig = any(
        a.bucket_attribution is not None and a.bucket_attribution.bootstrap_significant
        for a in attributions
    )
    gate, rationale, next_step = _decide_b_gate(
        alignment, feature_coverage, attributions, neg_controls, oof_results
    )

    result = Phase64BResult(
        phase_version=PHASE_VERSION,
        run_timestamp=run_ts,
        candidate_patch_created=CANDIDATE_PATCH_CREATED,
        production_modified=PRODUCTION_MODIFIED,
        alpha_modified=ALPHA_MODIFIED,
        diagnostic_only=DIAGNOSTIC_ONLY,
        alpha=ALPHA,
        phase64_gate=_PHASE64_GATE,
        phase64_audit_hash=_PHASE64_AUDIT_HASH,
        n_bull_3d_rows=len(bull_rows),
        n_ssot_artifacts=n_ssot,
        n_predictions=n_all,
        alignment=alignment,
        feature_coverage=feature_coverage,
        n_available_features=n_avail,
        n_data_limited_features=n_limited,
        segment_n_all=n_all,
        segment_n_heavy_fav=len(hf_rows),
        segment_n_high_conf=len(hc_rows),
        phase60_baseline_replication=phase60_rep,
        attributions=attributions,
        negative_controls=neg_controls,
        oof_results=oof_results,
        any_bootstrap_significant=any_bootstrap_sig,
        gate=gate,
        gate_rationale=rationale,
        next_step=next_step,
        completion_marker="PHASE_64B_FULL_SEASON_BULLPEN_INGESTION_ATTRIBUTION_VERIFIED",
    )

    # Optionally write outputs
    if ssot_output_path:
        team_index = _build_team_index(bull_3d_path)
        ssot_rows = [
            {"game_date": k[0], "team_norm": k[1], **v}
            for k, v in sorted(team_index.items())
        ]
        Path(ssot_output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(ssot_output_path, "w") as f:
            for row in ssot_rows:
                f.write(json.dumps(row) + "\n")

    return result
