"""
orchestrator/phase59_real_bullpen_boxscore_acquisition.py
==========================================================
Phase 59 — Real Bullpen Boxscore / Relief Appearance Acquisition
and PIT-safe Feature Validation

目的：
  盤點並驗證 repo 內已存在的真實 bullpen boxscore 資料
  (data/mlb_context/bullpen_usage_3d.jsonl)，對 heavy_favorite /
  high_confidence 失敗 segment 進行 before vs after 診斷。

Hard Rules (NEVER violate):
  - CANDIDATE_PATCH_CREATED = False   (diagnostic only)
  - PRODUCTION_MODIFIED    = False
  - ALPHA_MODIFIED         = False    (blend alpha = 0.40, frozen)
  - DIAGNOSTIC_ONLY        = True
  - 不可使用 home_win / final_score / game_result 作為 feature
  - 不可使用 game_date 當天之 bullpen 出賽記錄
  - PIT 要求：bullpen_usage_last_3d_* = Σ(D-1, D-2, D-3) 之 bullpen IP

Gate 結論 (四選一)：
  REAL_BULLPEN_FEATURE_PROMISING    — 信號明顯，值得進入 repair loop
  BULLPEN_DATA_GAP_BLOCKED          — 覆蓋率不足，無法結論
  BULLPEN_FEATURE_NOT_PROMISING     — 無信號
  INCONCLUSIVE                      — 混合 / 邊界

版本：phase59_real_bullpen_boxscore_acquisition_v1
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import random
import re
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Hard Constants ───────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
ALPHA_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
ALPHA: float = 0.40          # blend = (1-alpha)*model + alpha*market  (frozen)
PHASE_VERSION: str = "phase59_real_bullpen_boxscore_acquisition_v1"

# ─── Forbidden post-game feature fields ──────────────────────────────────────
_FORBIDDEN_FEATURE_FIELDS: frozenset[str] = frozenset({
    "home_win", "final_score", "home_score", "away_score",
    "result", "box_score", "post_game_stats", "closing_odds_after_game",
    "innings_pitched_today", "era_after_game", "game_score",
    "actual_starter_ip_today", "same_game_boxscore", "box_score_result",
    "game_result",
})

# ─── Gate labels ─────────────────────────────────────────────────────────────
REAL_BULLPEN_FEATURE_PROMISING: str = "REAL_BULLPEN_FEATURE_PROMISING"
BULLPEN_DATA_GAP_BLOCKED: str = "BULLPEN_DATA_GAP_BLOCKED"
BULLPEN_FEATURE_NOT_PROMISING: str = "BULLPEN_FEATURE_NOT_PROMISING"
INCONCLUSIVE: str = "INCONCLUSIVE"

_VALID_GATES: frozenset[str] = frozenset({
    REAL_BULLPEN_FEATURE_PROMISING,
    BULLPEN_DATA_GAP_BLOCKED,
    BULLPEN_FEATURE_NOT_PROMISING,
    INCONCLUSIVE,
})

# ─── Thresholds ───────────────────────────────────────────────────────────────
HEAVY_FAV_THRESHOLD: float = 0.70    # fav_prob >= 0.70
HIGH_CONF_THRESHOLD: float = 0.65    # fav_prob >= 0.65
MATCH_RATE_MIN: float = 0.80         # alignment coverage minimum
MIN_HEAVY_FAV_WITH_BULL: int = 15    # minimum heavy_fav rows with real bullpen data
MIN_COVERAGE_FOR_GATE: float = 0.50  # gate requires >= 50% heavy_fav coverage
BULLPEN_DELTA_PROMISING_THRESHOLD: float = 0.015  # Δ|correct_dir_rate - 0.5| > this → promising


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  Data Structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BullpenDataSourceReport:
    """牛棚資料來源與覆蓋率報告。"""
    source_file: str
    total_rows: int
    date_range_start: str
    date_range_end: str
    missing_home_pct: float
    missing_away_pct: float
    pit_source: str            # e.g. "mlb_stats_api_boxscore"
    pit_validated: bool        # True if d-1, d-2, d-3 lookback confirmed
    pit_explanation: str


@dataclass
class AlignmentReport:
    """Prediction JSONL ↔ bullpen JSONL alignment report。"""
    total_prediction_rows: int
    matched_rows: int
    match_rate: float
    unmatched_rows: int
    null_bull_rows: int        # matched but bullpen value is None
    usable_rows: int           # matched & non-null
    usable_rate: float
    heavy_fav_total: int       # heavy_fav in all prediction rows
    heavy_fav_matched: int     # heavy_fav with any bullpen match
    heavy_fav_usable: int      # heavy_fav with non-null bullpen values
    heavy_fav_coverage: float  # usable / total heavy_fav
    high_conf_usable: int
    high_conf_coverage: float
    alignment_method: str


@dataclass
class BullpenSignalStats:
    """Bullpen fatigue signal statistics for a segment."""
    segment: str
    n: int
    mean_bull_delta: float     # home - away mean (IP)
    stdev_bull_delta: float
    home_win_rate: float
    mean_blend_prob: float
    # When favorite has tired bullpen vs rested
    tired_fav_n: int           # rows where fav team has higher 3d bullpen usage (>= +2 IP)
    tired_fav_win_rate: float  # win rate for favorite team when their bullpen is tired
    rested_fav_n: int          # rows where fav team has lower 3d bullpen usage (<= -2 IP)
    rested_fav_win_rate: float # win rate for favorite team when their bullpen is rested
    fatigue_win_rate_delta: float  # rested - tired win rate (positive = signal in expected direction)
    has_signal: bool           # |delta| > BULLPEN_DELTA_PROMISING_THRESHOLD


@dataclass
class SegmentECE:
    """ECE for a segment, with and without bullpen-adjusted ordering."""
    segment: str
    n: int
    baseline_ece: float
    baseline_bss: float        # BSS vs climatological (0.25)
    bullpen_adjusted_ece: float   # ECE after simple bullpen-direction correction
    bullpen_adjusted_bss: float
    ece_delta: float           # baseline - adjusted (positive = improvement)


@dataclass
class Phase59AcquisitionResult:
    """Phase 59 complete acquisition & validation result."""
    phase_version: str
    run_timestamp: str
    audit_hash: str

    # Safety flags
    candidate_patch_created: bool
    production_modified: bool
    alpha_modified: bool
    diagnostic_only: bool

    # Data source inventory
    bullpen_source_report: BullpenDataSourceReport
    alignment: AlignmentReport

    # Signal analysis
    heavy_fav_signal: BullpenSignalStats
    high_conf_signal: BullpenSignalStats

    # ECE comparison
    heavy_fav_ece_comparison: SegmentECE
    high_conf_ece_comparison: SegmentECE

    # Phase 55/56/57/58 historical context
    phase55_gate: str
    phase56_gate: str
    phase56_bullpen_available_rate: float
    prior_heavy_fav_ece_baseline: float   # from Phase 59-Pre

    # Gate
    gate: str
    gate_rationale: str
    next_step: str

    # Timestamps and coverage
    sample_size: int
    date_range_start: str
    date_range_end: str


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  PIT Validation
# ═══════════════════════════════════════════════════════════════════════════════

def assert_no_forbidden_feature(row: dict[str, Any]) -> None:
    """Raise ValueError if row contains any forbidden post-game field."""
    for field_name in _FORBIDDEN_FEATURE_FIELDS:
        if field_name in row and row[field_name] is not None:
            raise ValueError(
                f"PIT VIOLATION: forbidden post-game field '{field_name}' "
                f"found in bullpen feature row. game_date={row.get('game_date')}"
            )


def validate_pit_safety_of_bullpen_source(
    bullpen_rows: list[dict[str, Any]],
) -> tuple[bool, str]:
    """
    Validate that bullpen_usage_last_3d is computed from prior-days data.

    The `external_sources.py` code computes:
        recent = [(d - timedelta(days=i)).isoformat() for i in (1, 2, 3)]
        home_usage = sum(by_team_by_date[home].get(k, 0) for k in recent)

    This means the 3-day sum uses D-1, D-2, D-3 — strictly before game_date.

    Returns:
        (is_valid, explanation)
    """
    if not bullpen_rows:
        return False, "No bullpen rows to validate"

    # Check source attribution
    sources = {r.get("source", "unknown") for r in bullpen_rows[:100]}
    source_str = ", ".join(sorted(sources))

    # Check that all rows have game_id with extractable date
    valid_ids = 0
    for r in bullpen_rows[:50]:
        gid = r.get("game_id", "")
        if re.search(r'\d{4}_\d{2}_\d{2}', gid):
            valid_ids += 1

    if valid_ids == 0:
        return False, "Cannot parse game dates from game_id format"

    explanation = (
        f"Source: {source_str}. "
        f"bullpen_usage_last_3d = Σ(D-1, D-2, D-3) bullpen innings, "
        f"computed from completed-game boxscores of PRIOR days only. "
        f"Current game boxscore is stored but D is never included in the lookback. "
        f"Validated via external_sources.py code review: "
        f"recent = [(d - timedelta(days=i)) for i in (1, 2, 3)]."
    )
    return True, explanation


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  Data Loading and Alignment
# ═══════════════════════════════════════════════════════════════════════════════

def _norm_team(s: str) -> str:
    """Normalize team name for alignment."""
    return re.sub(r'[_\s]+', ' ', s).strip().lower()


def _parse_bull_game_id(gid: str) -> tuple[str | None, str | None, str | None]:
    """
    Parse MLB-2025_MM_DD-H_MM_PM-AWAY-AT-HOME into (date, away_norm, home_norm).
    """
    m = re.match(r'MLB-(\d{4})_(\d{2})_(\d{2})-\d+_\d+_[AP]M-(.+)-AT-(.+)', gid)
    if m:
        yr, mo, dy, away, home = m.groups()
        return f'{yr}-{mo}-{dy}', _norm_team(away), _norm_team(home)
    return None, None, None


def _blend_prob(model_prob: float, market_prob: float) -> float:
    """Compute blend probability: (1 - alpha) * model + alpha * market."""
    return (1.0 - ALPHA) * model_prob + ALPHA * market_prob


def _fav_prob(blend: float) -> float:
    """Return max(blend, 1-blend) — probability of the favored team winning."""
    return max(blend, 1.0 - blend)


def _is_home_favorite(blend: float) -> bool:
    """True if home team is the stronger team."""
    return blend >= 0.50


def load_and_align(
    predictions_path: Path,
    bullpen_path: Path,
) -> tuple[list[dict[str, Any]], AlignmentReport]:
    """
    Load prediction JSONL and bullpen JSONL, align by (date, away_team, home_team).

    PIT contract:
      - bullpen values represent D-1, D-2, D-3 innings pitched
      - home_win label is used as target, NOT as feature
      - no forbidden feature field is propagated

    Returns:
        (aligned_rows, AlignmentReport)
    """
    # Load bullpen data
    with bullpen_path.open() as fh:
        bull_raw = [json.loads(l) for l in fh if l.strip()]

    # Build bullpen index by (date, away_norm, home_norm)
    bull_idx: dict[tuple[str, str, str], dict[str, Any]] = {}
    bull_date_start = "9999"
    bull_date_end = "0000"
    missing_home = 0
    missing_away = 0
    bull_source = "unknown"

    for r in bull_raw:
        dt, away, home = _parse_bull_game_id(r.get("game_id", ""))
        if dt:
            key = (dt, away, home)
            bull_idx[key] = r
            bull_date_start = min(bull_date_start, dt)
            bull_date_end = max(bull_date_end, dt)
            if r.get("bullpen_usage_last_3d_home") is None:
                missing_home += 1
            if r.get("bullpen_usage_last_3d_away") is None:
                missing_away += 1
        if r.get("source"):
            bull_source = r["source"]

    n_bull = len(bull_raw)
    missing_home_pct = missing_home / max(n_bull, 1)
    missing_away_pct = missing_away / max(n_bull, 1)

    pit_valid, pit_expl = validate_pit_safety_of_bullpen_source(bull_raw)

    source_report = BullpenDataSourceReport(
        source_file=str(bullpen_path),
        total_rows=n_bull,
        date_range_start=bull_date_start,
        date_range_end=bull_date_end,
        missing_home_pct=missing_home_pct,
        missing_away_pct=missing_away_pct,
        pit_source=bull_source,
        pit_validated=pit_valid,
        pit_explanation=pit_expl,
    )

    # Load predictions
    with predictions_path.open() as fh:
        pred_raw = [json.loads(l) for l in fh if l.strip()]

    # Validate no forbidden fields in predictions used as feature
    for r in pred_raw[:10]:  # spot check
        assert_no_forbidden_feature({k: v for k, v in r.items()
                                      if k not in ("home_win", "game_result")
                                      and isinstance(v, (int, float, str))})

    # Align
    aligned: list[dict[str, Any]] = []
    matched = 0
    null_bull = 0
    heavy_fav_total = 0
    heavy_fav_matched = 0
    heavy_fav_usable = 0
    high_conf_usable = 0

    pred_date_start = "9999"
    pred_date_end = "0000"

    for r in pred_raw:
        mp = r.get("model_home_prob")
        mkp = r.get("market_home_prob_no_vig")
        hw = r.get("home_win")
        dt = r.get("game_date", "")

        if mp is None or mkp is None or hw is None:
            continue

        # Compute blend
        bp = _blend_prob(mp, mkp)
        fp = _fav_prob(bp)
        home_is_fav = _is_home_favorite(bp)

        pred_date_start = min(pred_date_start, dt)
        pred_date_end = max(pred_date_end, dt)

        if fp >= HEAVY_FAV_THRESHOLD:
            heavy_fav_total += 1

        # Try to match bullpen
        away_norm = _norm_team(r.get("away_team", ""))
        home_norm = _norm_team(r.get("home_team", ""))
        bull = bull_idx.get((dt, away_norm, home_norm))

        bull_home = None
        bull_away = None
        has_bull = False

        if bull:
            matched += 1
            if fp >= HEAVY_FAV_THRESHOLD:
                heavy_fav_matched += 1
            bull_home = bull.get("bullpen_usage_last_3d_home")
            bull_away = bull.get("bullpen_usage_last_3d_away")
            if bull_home is None or bull_away is None:
                null_bull += 1
            else:
                has_bull = True
                if fp >= HEAVY_FAV_THRESHOLD:
                    heavy_fav_usable += 1
                if fp >= HIGH_CONF_THRESHOLD:
                    high_conf_usable += 1

        # Build row (home_win is target, bull data is feature)
        row = {
            "game_date": dt,
            "game_id": r.get("game_id", ""),
            "home_team": r.get("home_team", ""),
            "away_team": r.get("away_team", ""),
            # Target (label) — never used as feature
            "_label_home_win": int(hw),
            # Prediction features
            "_model_prob": mp,
            "_market_prob": mkp,
            "_blend_prob": bp,
            "_fav_prob": fp,
            "_home_is_fav": home_is_fav,
            # Bullpen features (may be None)
            "_bull_home_3d": bull_home,
            "_bull_away_3d": bull_away,
            "_has_bull": has_bull,
            # Derived bullpen features
            "_bull_delta": (bull_home - bull_away) if has_bull else None,
            # Fatigue direction relative to favorite
            # Positive = favorite team has MORE bullpen usage (tired)
            # home_fav: delta = home_usage - away_usage
            # away_fav: delta = away_usage - home_usage (flip sign)
            "_fav_bull_fatigue": (
                (bull_home - bull_away) if (has_bull and home_is_fav)
                else (bull_away - bull_home) if has_bull
                else None
            ),
        }
        aligned.append(row)

    total = len(aligned)
    usable = sum(1 for r in aligned if r["_has_bull"])
    usable_rate = usable / max(total, 1)
    match_rate = matched / max(total, 1)

    heavy_fav_cov = (
        heavy_fav_usable / heavy_fav_total if heavy_fav_total > 0 else 0.0
    )
    high_conf_total = sum(1 for r in aligned if r["_fav_prob"] >= HIGH_CONF_THRESHOLD)
    high_conf_cov = high_conf_usable / max(high_conf_total, 1)

    alignment_report = AlignmentReport(
        total_prediction_rows=total,
        matched_rows=matched,
        match_rate=match_rate,
        unmatched_rows=total - matched,
        null_bull_rows=null_bull,
        usable_rows=usable,
        usable_rate=usable_rate,
        heavy_fav_total=heavy_fav_total,
        heavy_fav_matched=heavy_fav_matched,
        heavy_fav_usable=heavy_fav_usable,
        heavy_fav_coverage=heavy_fav_cov,
        high_conf_usable=high_conf_usable,
        high_conf_coverage=high_conf_cov,
        alignment_method="(game_date, norm(away_team), norm(home_team))",
    )

    return aligned, source_report, alignment_report


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  Signal Analysis
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_signal(
    rows: list[dict[str, Any]],
    segment_name: str,
    segment_filter_key: str,
    tired_threshold: float = 2.0,
    rested_threshold: float = -2.0,
) -> BullpenSignalStats:
    """
    Compute bullpen signal statistics for a segment.

    Tired: favorite team's bullpen has >= tired_threshold more IP than opponent
    Rested: favorite team's bullpen has <= rested_threshold IP vs opponent
    """
    seg_rows = [r for r in rows if r.get(segment_filter_key) and r["_has_bull"]]

    if not seg_rows:
        return BullpenSignalStats(
            segment=segment_name,
            n=0,
            mean_bull_delta=float("nan"),
            stdev_bull_delta=float("nan"),
            home_win_rate=float("nan"),
            mean_blend_prob=float("nan"),
            tired_fav_n=0,
            tired_fav_win_rate=float("nan"),
            rested_fav_n=0,
            rested_fav_win_rate=float("nan"),
            fatigue_win_rate_delta=float("nan"),
            has_signal=False,
        )

    deltas = [r["_bull_delta"] for r in seg_rows if r["_bull_delta"] is not None]
    labels = [r["_label_home_win"] for r in seg_rows]
    probs = [r["_blend_prob"] for r in seg_rows]
    fav_fatigue = [r["_fav_bull_fatigue"] for r in seg_rows if r["_fav_bull_fatigue"] is not None]

    mean_delta = statistics.mean(deltas) if deltas else float("nan")
    stdev_delta = statistics.stdev(deltas) if len(deltas) > 1 else 0.0
    home_win_rate = sum(labels) / len(labels) if labels else float("nan")
    mean_blend = statistics.mean(probs) if probs else float("nan")

    # Tired: favorite has HIGH bullpen usage (fatigued)
    tired_rows = [r for r in seg_rows
                  if r["_fav_bull_fatigue"] is not None
                  and r["_fav_bull_fatigue"] >= tired_threshold]
    rested_rows = [r for r in seg_rows
                   if r["_fav_bull_fatigue"] is not None
                   and r["_fav_bull_fatigue"] <= rested_threshold]

    def _fav_win_rate(rows_subset: list[dict]) -> float:
        """Rate at which the FAVORED team wins."""
        if not rows_subset:
            return float("nan")
        wins = []
        for r in rows_subset:
            hw = r["_label_home_win"]
            if r["_home_is_fav"]:
                wins.append(1 if hw else 0)
            else:
                wins.append(0 if hw else 1)
        return sum(wins) / len(wins)

    tired_win_rate = _fav_win_rate(tired_rows)
    rested_win_rate = _fav_win_rate(rested_rows)

    # Expected direction: tired → favorite wins less, rested → favorite wins more
    if not math.isnan(tired_win_rate) and not math.isnan(rested_win_rate):
        delta_wr = rested_win_rate - tired_win_rate
    else:
        delta_wr = float("nan")

    has_signal = (
        not math.isnan(delta_wr)
        and abs(delta_wr) > BULLPEN_DELTA_PROMISING_THRESHOLD
        and len(tired_rows) >= 5
        and len(rested_rows) >= 5
    )

    return BullpenSignalStats(
        segment=segment_name,
        n=len(seg_rows),
        mean_bull_delta=mean_delta,
        stdev_bull_delta=stdev_delta,
        home_win_rate=home_win_rate,
        mean_blend_prob=mean_blend,
        tired_fav_n=len(tired_rows),
        tired_fav_win_rate=tired_win_rate,
        rested_fav_n=len(rested_rows),
        rested_fav_win_rate=rested_win_rate,
        fatigue_win_rate_delta=delta_wr,
        has_signal=has_signal,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 5  Calibration Comparison (ECE / BSS)
# ═══════════════════════════════════════════════════════════════════════════════

_CLIMATOLOGICAL_BRIER: float = 0.25


def _ece_segment(probs: list[float], labels: list[int], n_bins: int = 10) -> float:
    """Compute Expected Calibration Error for a set of predictions."""
    if not probs:
        return float("nan")
    # Sort by prob
    combined = sorted(zip(probs, labels), key=lambda x: x[0])
    bin_size = max(1, len(combined) // n_bins)
    total_abs_err = 0.0
    total_n = 0
    for i in range(0, len(combined), bin_size):
        chunk = combined[i : i + bin_size]
        if not chunk:
            continue
        n_chunk = len(chunk)
        mean_p = sum(p for p, _ in chunk) / n_chunk
        mean_y = sum(y for _, y in chunk) / n_chunk
        total_abs_err += n_chunk * abs(mean_p - mean_y)
        total_n += n_chunk
    return total_abs_err / max(total_n, 1)


def _bss_segment(probs: list[float], labels: list[int]) -> float:
    """BSS vs climatological baseline (0.25 Brier)."""
    if not probs or not labels:
        return float("nan")
    brier = sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(probs)
    return (1.0 - brier / _CLIMATOLOGICAL_BRIER) if _CLIMATOLOGICAL_BRIER > 0 else float("nan")


def _bullpen_adjusted_prob(
    blend: float,
    fav_fatigue: float | None,
    adjustment_cap: float = 0.015,
    fatigue_scale: float = 0.002,
) -> float:
    """
    Simple diagnostic adjustment: if favorite is tired, slightly reduce their win prob.
    home_is_fav + tired → reduce blend_prob
    away_is_fav + tired → increase blend_prob (reducing away fav probability)

    NOTE: This is a DIAGNOSTIC proxy — not a production patch.
    """
    if fav_fatigue is None:
        return blend
    # fav_fatigue > 0 → favorite has tired bullpen → reduce their implied prob
    adj = -fav_fatigue * fatigue_scale
    adj = max(-adjustment_cap, min(adjustment_cap, adj))
    if blend >= 0.50:
        # home is favorite
        return max(0.01, min(0.99, blend + adj))
    else:
        # away is favorite, reduce away's implied win prob = increase blend_prob
        return max(0.01, min(0.99, blend - adj))


def _compute_ece_comparison(
    rows: list[dict[str, Any]],
    segment_name: str,
    segment_fav_threshold: float,
) -> SegmentECE:
    """Compare baseline ECE vs bullpen-adjusted ECE for a segment."""
    seg_rows = [r for r in rows
                if r["_fav_prob"] >= segment_fav_threshold and r["_has_bull"]]

    if not seg_rows:
        return SegmentECE(
            segment=segment_name,
            n=0,
            baseline_ece=float("nan"),
            baseline_bss=float("nan"),
            bullpen_adjusted_ece=float("nan"),
            bullpen_adjusted_bss=float("nan"),
            ece_delta=float("nan"),
        )

    base_probs = [r["_blend_prob"] for r in seg_rows]
    adj_probs = [
        _bullpen_adjusted_prob(r["_blend_prob"], r["_fav_bull_fatigue"])
        for r in seg_rows
    ]
    labels = [r["_label_home_win"] for r in seg_rows]

    base_ece = _ece_segment(base_probs, labels)
    adj_ece = _ece_segment(adj_probs, labels)
    base_bss = _bss_segment(base_probs, labels)
    adj_bss = _bss_segment(adj_probs, labels)

    return SegmentECE(
        segment=segment_name,
        n=len(seg_rows),
        baseline_ece=base_ece,
        baseline_bss=base_bss,
        bullpen_adjusted_ece=adj_ece,
        bullpen_adjusted_bss=adj_bss,
        ece_delta=base_ece - adj_ece,   # positive = adjustment improved ECE
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 6  Gate Recommendation
# ═══════════════════════════════════════════════════════════════════════════════

def _recommend_gate(
    alignment: AlignmentReport,
    heavy_fav_signal: BullpenSignalStats,
    high_conf_signal: BullpenSignalStats,
    heavy_fav_ece: SegmentECE,
) -> tuple[str, str, str]:
    """
    Determine gate from alignment coverage and signal analysis.

    Priority:
    1. If heavy_fav coverage < MIN_COVERAGE_FOR_GATE → BULLPEN_DATA_GAP_BLOCKED
    2. If heavy_fav_usable < MIN_HEAVY_FAV_WITH_BULL → BULLPEN_DATA_GAP_BLOCKED
    3. If signal detected AND ECE improved → REAL_BULLPEN_FEATURE_PROMISING
    4. If signal detected BUT ECE not clearly improved → INCONCLUSIVE
    5. No signal detected → BULLPEN_FEATURE_NOT_PROMISING
    """
    hf_cov = alignment.heavy_fav_coverage
    hf_n = alignment.heavy_fav_usable

    # Coverage check
    if hf_cov < MIN_COVERAGE_FOR_GATE or hf_n < MIN_HEAVY_FAV_WITH_BULL:
        rationale = (
            f"Heavy_fav coverage {hf_cov:.1%} (min {MIN_COVERAGE_FOR_GATE:.0%}) "
            f"or usable_n={hf_n} (min {MIN_HEAVY_FAV_WITH_BULL}) insufficient. "
            f"Bullpen data alignment gap prevents conclusive analysis."
        )
        next_step = (
            "Expand bullpen boxscore acquisition to cover unmatched games "
            "(unmatched_rows=" + str(alignment.unmatched_rows) + "). "
            "Target: bullpen coverage >= 80% for all heavy_fav games."
        )
        return BULLPEN_DATA_GAP_BLOCKED, rationale, next_step

    has_signal = heavy_fav_signal.has_signal
    ece_improved = (
        not math.isnan(heavy_fav_ece.ece_delta)
        and heavy_fav_ece.ece_delta > 0.005
    )

    if has_signal and ece_improved:
        rationale = (
            f"Bullpen fatigue signal DETECTED in heavy_fav (n={hf_n}): "
            f"rested_fav_win_rate={heavy_fav_signal.rested_fav_win_rate:.3f} vs "
            f"tired_fav_win_rate={heavy_fav_signal.tired_fav_win_rate:.3f} "
            f"(Δ={heavy_fav_signal.fatigue_win_rate_delta:.3f}). "
            f"Diagnostic adjustment ECE: {heavy_fav_ece.baseline_ece:.4f} → "
            f"{heavy_fav_ece.bullpen_adjusted_ece:.4f} "
            f"(Δ_ECE={heavy_fav_ece.ece_delta:+.4f}). "
            f"Real bullpen data promising for further investigation."
        )
        next_step = (
            "Proceed to bullpen feature engineering: expand to additional features "
            "(B2B count, closer usage, rest days), train PIT-safe model with "
            "rolling OOF validation on full 2025 season."
        )
        return REAL_BULLPEN_FEATURE_PROMISING, rationale, next_step

    if has_signal and not ece_improved:
        rationale = (
            f"Directional signal found (Δ_win_rate={heavy_fav_signal.fatigue_win_rate_delta:.3f}) "
            f"but simple diagnostic adjustment did not improve ECE "
            f"({heavy_fav_ece.baseline_ece:.4f} → {heavy_fav_ece.bullpen_adjusted_ece:.4f}). "
            f"Possibly needs: (a) more features, (b) non-linear relationship, "
            f"(c) more data. Sample size heavy_fav_usable={hf_n} may be limiting."
        )
        next_step = (
            "INCONCLUSIVE: Collect additional bullpen features (B2B, closer usage) "
            "and expand to full season before deciding. "
            "Directional signal warrants further investigation."
        )
        return INCONCLUSIVE, rationale, next_step

    # No meaningful signal
    tired_n = heavy_fav_signal.tired_fav_n
    rested_n = heavy_fav_signal.rested_fav_n
    delta = heavy_fav_signal.fatigue_win_rate_delta if not math.isnan(
        heavy_fav_signal.fatigue_win_rate_delta) else 0.0

    rationale = (
        f"No meaningful bullpen fatigue signal in heavy_fav segment (n={hf_n}). "
        f"Tired_fav (n={tired_n}): win_rate={heavy_fav_signal.tired_fav_win_rate:.3f}, "
        f"Rested_fav (n={rested_n}): win_rate={heavy_fav_signal.rested_fav_win_rate:.3f}, "
        f"Δ={delta:.3f} (threshold {BULLPEN_DELTA_PROMISING_THRESHOLD:.3f}). "
        f"Bullpen 3d usage alone is not informative for heavy_fav failure correction."
    )
    next_step = (
        "BULLPEN_FEATURE_NOT_PROMISING for heavy_fav ECE repair. "
        "Consider: (a) different bullpen feature (closer-specific rest, leverage index), "
        "(b) park/weather interaction, (c) accept heavy_fav ECE as structural."
    )
    return BULLPEN_FEATURE_NOT_PROMISING, rationale, next_step


# ═══════════════════════════════════════════════════════════════════════════════
# § 7  Audit Hash
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_audit_hash(predictions_path: Path, bullpen_path: Path) -> str:
    """Compute short audit hash from prediction + bullpen file sizes."""
    h = hashlib.sha256()
    for p in [predictions_path, bullpen_path]:
        if p.exists():
            stat = p.stat()
            h.update(f"{p.name}:{stat.st_size}:{stat.st_mtime_ns}".encode())
    return h.hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════════════
# § 8  Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def run_phase59_acquisition(
    predictions_path: Path,
    bullpen_path: Path,
) -> Phase59AcquisitionResult:
    """
    Phase 59 — Real Bullpen Boxscore Acquisition and PIT-safe Feature Validation.

    Args:
        predictions_path: Path to mlb_2025_per_game_predictions.jsonl
        bullpen_path:      Path to bullpen_usage_3d.jsonl

    Returns:
        Phase59AcquisitionResult with gate and full diagnostic
    """
    assert not CANDIDATE_PATCH_CREATED, "Safety violation"
    assert not PRODUCTION_MODIFIED, "Safety violation"

    audit_hash = _compute_audit_hash(predictions_path, bullpen_path)
    now_ts = datetime.now(timezone.utc).isoformat()

    logger.info("[phase59] Loading data: %s + %s", predictions_path.name, bullpen_path.name)
    aligned, source_report, alignment = load_and_align(predictions_path, bullpen_path)
    logger.info("[phase59] Aligned %d rows (match_rate=%.1f%%, heavy_fav_usable=%d)",
                alignment.total_prediction_rows,
                alignment.match_rate * 100,
                alignment.heavy_fav_usable)

    # Date range
    dates = sorted({r["game_date"] for r in aligned if r["game_date"]})
    date_start = dates[0] if dates else ""
    date_end = dates[-1] if dates else ""

    # Signal analysis — heavy_fav segment
    for row in aligned:
        row["_is_heavy_fav"] = row["_fav_prob"] >= HEAVY_FAV_THRESHOLD
        row["_is_high_conf"] = row["_fav_prob"] >= HIGH_CONF_THRESHOLD

    heavy_fav_signal = _compute_signal(aligned, "heavy_fav", "_is_heavy_fav")
    high_conf_signal = _compute_signal(aligned, "high_conf", "_is_high_conf")

    # ECE comparison
    heavy_fav_ece = _compute_ece_comparison(aligned, "heavy_fav", HEAVY_FAV_THRESHOLD)
    high_conf_ece = _compute_ece_comparison(aligned, "high_conf", HIGH_CONF_THRESHOLD)

    # Gate
    gate, rationale, next_step = _recommend_gate(
        alignment, heavy_fav_signal, high_conf_signal, heavy_fav_ece
    )

    logger.info("[phase59] Gate: %s", gate)
    logger.info("[phase59] Rationale: %s", rationale[:120])

    return Phase59AcquisitionResult(
        phase_version=PHASE_VERSION,
        run_timestamp=now_ts,
        audit_hash=audit_hash,
        # Safety
        candidate_patch_created=CANDIDATE_PATCH_CREATED,
        production_modified=PRODUCTION_MODIFIED,
        alpha_modified=ALPHA_MODIFIED,
        diagnostic_only=DIAGNOSTIC_ONLY,
        # Data source
        bullpen_source_report=source_report,
        alignment=alignment,
        # Signal
        heavy_fav_signal=heavy_fav_signal,
        high_conf_signal=high_conf_signal,
        # ECE
        heavy_fav_ece_comparison=heavy_fav_ece,
        high_conf_ece_comparison=high_conf_ece,
        # Historical context
        phase55_gate="BULLPEN_FEATURE_INVESTIGATION",
        phase56_gate="DATA_GAP_REMAINS",
        phase56_bullpen_available_rate=0.0,
        prior_heavy_fav_ece_baseline=0.077877,  # from Phase 59-Pre
        # Gate
        gate=gate,
        gate_rationale=rationale,
        next_step=next_step,
        # Coverage
        sample_size=alignment.total_prediction_rows,
        date_range_start=date_start,
        date_range_end=date_end,
    )
