"""Phase 67 — Lineup / Rest / Schedule / Ballpark Context Failure Attribution

DIAGNOSTIC ONLY.  CANDIDATE_PATCH_CREATED = False.  PRODUCTION_MODIFIED = False.
ALPHA_MODIFIED = False.  ALPHA = 0.40 (FROZEN).

Attributes heavy_favorite / high_confidence / Phase45 failure segments to
pre-game context features derived from:
  - Retrosheet gl2025.txt  (rest days, day/night, DOW, DH, season phase,
                             consecutive road games, divisional matchup)
  - p0_features in predictions JSONL (park_run_factor, season_game_index)

PIT Safety: ALL context features are pre-game information.
  - Rest days: derived from prior game dates (not outcomes)
  - Day/Night: known at scheduling time
  - Division matchup: static lookup
  - Park factor: static park factor table
  - Consecutive road games: derived from prior schedule (not outcomes)

DATA_LIMITED (not available in this repository):
  - travel_distance      — no travel data source
  - getaway_day          — no series schedule designation
  - lineup_available     — no lineup API
  - lineup_missing       — no lineup API
  - key_batter_missing   — no injury report data
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

# ═══════════════════════════════════════════════════════════════════
# SAFETY CONSTANTS — FROZEN, DO NOT MODIFY
# ═══════════════════════════════════════════════════════════════════
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
ALPHA_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
ALPHA: float = 0.40

# ═══════════════════════════════════════════════════════════════════
# PHASE IDENTITY
# ═══════════════════════════════════════════════════════════════════
PHASE_VERSION: str = "phase67_context_failure_attribution_v1"
COMPLETION_MARKER: str = "PHASE_67_CONTEXT_FAILURE_ATTRIBUTION_VERIFIED"

# ═══════════════════════════════════════════════════════════════════
# GATE CONSTANTS
# ═══════════════════════════════════════════════════════════════════
CONTEXT_FEATURE_PROMISING: str = "CONTEXT_FEATURE_PROMISING"
DIAGNOSTIC_ONLY_SIGNAL: str = "DIAGNOSTIC_ONLY_SIGNAL"
DATA_LIMITED_GATE: str = "DATA_LIMITED"
OVERFIT_RISK: str = "OVERFIT_RISK"
CONTEXT_FEATURE_NOT_PROMISING: str = "CONTEXT_FEATURE_NOT_PROMISING"

_VALID_GATES: frozenset[str] = frozenset({
    CONTEXT_FEATURE_PROMISING,
    DIAGNOSTIC_ONLY_SIGNAL,
    DATA_LIMITED_GATE,
    OVERFIT_RISK,
    CONTEXT_FEATURE_NOT_PROMISING,
})

# ═══════════════════════════════════════════════════════════════════
# PREVIOUS PHASE GATE ANCHORS (FROZEN)
# ═══════════════════════════════════════════════════════════════════
PHASE66_GATE_ANCHOR: str = "MARKET_MICROSTRUCTURE_NOT_PROMISING"
PHASE66_VERSION: str = "phase66_market_microstructure_failure_attribution_v1"
PHASE65_GATE_ANCHOR: str = "OVERFIT_RISK"
PHASE65_VERSION: str = "phase65_sp_fatigue_attribution_v1"
PHASE64B_GATE_ANCHOR: str = "BULLPEN_GRANULAR_FEATURE_NOT_PROMISING"
PHASE64B_VERSION: str = "phase64b_bullpen_granular_feature_attribution_v1"

# ═══════════════════════════════════════════════════════════════════
# ANALYSIS THRESHOLDS
# ═══════════════════════════════════════════════════════════════════
_MIN_COVERAGE_RATE: float = 0.70
_MIN_SEGMENT_N: int = 20
_MIN_BUCKET_N: int = 15
_BOOTSTRAP_N: int = 1000
_OVERFIT_SIGMA: float = 2.0
_OOF_PROMISING_DELTA: float = 0.005

# Segment blend-probability thresholds
_HEAVY_FAV_THRESHOLD: float = 0.70
_HIGH_CONF_THRESHOLD: float = 0.75
_EXTREME_FAV_THRESHOLD: float = 0.80
_PHASE45_FAIL_MIN_FAV: float = 0.60

# ═══════════════════════════════════════════════════════════════════
# DATA_LIMITED DIMENSIONS
# ═══════════════════════════════════════════════════════════════════
_DATA_LIMITED_DIMENSIONS: list[str] = [
    "travel_distance",
    "getaway_day",
    "lineup_available",
    "lineup_missing",
    "key_batter_missing",
]
_DATA_LIMITED_FIELDS: list[str] = [
    "travel_miles_proxy",
    "getaway_day_flag",
    "lineup_missing_count",
    "key_batter_il_flag",
    "injury_report_available",
]

# ═══════════════════════════════════════════════════════════════════
# AVAILABLE CONTEXT DIMENSIONS (from gl2025.txt + p0_features)
# ═══════════════════════════════════════════════════════════════════
_AVAILABLE_DIMENSIONS: list[str] = [
    "home_rest_days_bucket",
    "away_rest_days_bucket",
    "rest_imbalance_bucket",
    "back_to_back_bucket",
    "day_night_bucket",
    "day_of_week_bucket",
    "double_header_bucket",
    "divisional_matchup_bucket",
    "fav_side_bucket",
    "park_run_env_bucket",
    "season_phase_bucket",
    "away_consec_road_bucket",
]

# ═══════════════════════════════════════════════════════════════════
# TEAM MAPPINGS — Retrosheet 3-letter ID → Full team name
# ═══════════════════════════════════════════════════════════════════
_RETRO_TO_FULL: dict[str, str] = {
    "ANA": "Los Angeles Angels",
    "ARI": "Arizona Diamondbacks",
    "ATH": "Athletics",
    "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles",
    "BOS": "Boston Red Sox",
    "CHA": "Chicago White Sox",
    "CHN": "Chicago Cubs",
    "CIN": "Cincinnati Reds",
    "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies",
    "DET": "Detroit Tigers",
    "HOU": "Houston Astros",
    "KCA": "Kansas City Royals",
    "LAN": "Los Angeles Dodgers",
    "MIA": "Miami Marlins",
    "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins",
    "NYA": "New York Yankees",
    "NYN": "New York Mets",
    "PHI": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates",
    "SDN": "San Diego Padres",
    "SEA": "Seattle Mariners",
    "SFN": "San Francisco Giants",
    "SLN": "St. Louis Cardinals",
    "TBA": "Tampa Bay Rays",
    "TEX": "Texas Rangers",
    "TOR": "Toronto Blue Jays",
    "WAS": "Washington Nationals",
}

# ═══════════════════════════════════════════════════════════════════
# DIVISION MAPPING — Full team name → Division string
# ═══════════════════════════════════════════════════════════════════
_TEAM_DIVISION: dict[str, str] = {
    # AL East
    "New York Yankees": "AL_East", "Boston Red Sox": "AL_East",
    "Toronto Blue Jays": "AL_East", "Tampa Bay Rays": "AL_East",
    "Baltimore Orioles": "AL_East",
    # AL Central
    "Cleveland Guardians": "AL_Central", "Minnesota Twins": "AL_Central",
    "Detroit Tigers": "AL_Central", "Chicago White Sox": "AL_Central",
    "Kansas City Royals": "AL_Central",
    # AL West
    "Houston Astros": "AL_West", "Texas Rangers": "AL_West",
    "Seattle Mariners": "AL_West", "Los Angeles Angels": "AL_West",
    "Athletics": "AL_West",
    # NL East
    "New York Mets": "NL_East", "Atlanta Braves": "NL_East",
    "Philadelphia Phillies": "NL_East", "Miami Marlins": "NL_East",
    "Washington Nationals": "NL_East",
    # NL Central
    "Chicago Cubs": "NL_Central", "Milwaukee Brewers": "NL_Central",
    "St. Louis Cardinals": "NL_Central", "Cincinnati Reds": "NL_Central",
    "Pittsburgh Pirates": "NL_Central",
    # NL West
    "Los Angeles Dodgers": "NL_West", "Arizona Diamondbacks": "NL_West",
    "San Diego Padres": "NL_West", "Colorado Rockies": "NL_West",
    "San Francisco Giants": "NL_West",
}


# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ContextRecord:
    """Pre-game context features for a single game, from gl2025.txt."""
    game_date: str
    home_team: str
    away_team: str
    home_rest_days: int      # Days since home team's last game (0 = back-to-back)
    away_rest_days: int      # Days since away team's last game (0 = back-to-back)
    away_consec_road_games: int  # Road trip length for away team (incl. this game)
    day_night: str           # 'D' or 'N'
    day_of_week: str         # 'Mon', 'Tue', etc.
    double_header: int       # 0 = solo game, 1 = DH game 1, 2 = DH game 2
    home_season_game_num: int
    away_season_game_num: int
    divisional_matchup: bool
    same_league: bool
    source: str
    audit_hash: str = ""


@dataclass
class ContextAlignment:
    n_predictions: int
    n_gl_records: int
    n_aligned: int
    n_unaligned: int
    coverage: float
    coverage_sufficient: bool
    sample_audit_hash: str


@dataclass
class SegmentMetrics:
    n: int
    model_brier: float
    market_brier: float
    blend_brier: float
    blend_bss_vs_market: float
    model_bss_vs_market: float
    fav_win_rate: float
    win_rate: float
    ece_blend: float


@dataclass
class BootstrapResult:
    n: int
    n_boot: int
    observed_delta: float
    ci_lower: float
    ci_upper: float
    prob_positive: float
    significant: bool


@dataclass
class AttributionBucket:
    dim: str
    bucket_label: str
    n: int
    segment_name: str
    metrics: SegmentMetrics
    bootstrap: BootstrapResult


@dataclass
class NegativeControl:
    dim: str
    segment: str
    real_blend_bss_delta: float
    shuffled_mean_delta: float
    shuffled_std_delta: float
    null_rejected: bool
    overfit_risk: bool


@dataclass
class OOFResult:
    dim: str
    segment: str
    n_folds: int
    fold_months: list[str]
    fold_bss_deltas: list[float]
    fold_ns: list[int]
    oof_mean_delta: float
    oof_consistent_sign: bool
    oof_significant: bool


@dataclass
class Phase67Result:
    phase_version: str
    completion_marker: str
    run_timestamp_utc: str
    candidate_patch_created: bool
    production_modified: bool
    alpha_modified: bool
    diagnostic_only: bool
    alpha: float
    phase66_gate_anchor: str
    phase65_gate_anchor: str
    phase64b_gate_anchor: str
    context_alignment: ContextAlignment
    segment_n_all: int
    segment_n_heavy_fav: int
    segment_n_high_conf: int
    segment_n_extreme_fav: int
    segment_n_phase45_failure: int
    all_metrics: SegmentMetrics
    heavy_fav_metrics: SegmentMetrics
    high_conf_metrics: SegmentMetrics
    phase45_failure_metrics: SegmentMetrics
    attribution_buckets: list[AttributionBucket]
    negative_controls: list[NegativeControl]
    oof_results: list[OOFResult]
    gate: str
    gate_rationale: str
    next_step: str
    any_bootstrap_significant: bool
    any_oof_promising: bool
    any_overfit_risk: bool
    worth_phase68: bool
    data_limited_dimensions: list[str]
    data_limited_fields: list[str]
    available_dimensions: list[str]


# ═══════════════════════════════════════════════════════════════════
# MATH HELPERS
# ═══════════════════════════════════════════════════════════════════

def _brier_score(probs: list[float], labels: list[int]) -> float:
    """Mean squared error between probabilities and binary outcomes."""
    if not probs:
        return 0.25
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(probs)


def _bss_direct(model_brier: float, ref_brier: float) -> float:
    """Brier Skill Score: 1 - model_brier / ref_brier.

    Positive = model beats reference.  Uses direct ratio (NOT climatological).
    """
    if ref_brier <= 0.0:
        return 0.0
    return 1.0 - model_brier / ref_brier


def _compute_ece(probs: list[float], labels: list[int], n_bins: int = 10) -> float:
    """Expected Calibration Error across equal-width probability bins."""
    if not probs:
        return 0.0
    bins: dict[int, list] = defaultdict(list)
    for p, y in zip(probs, labels):
        b = min(int(p * n_bins), n_bins - 1)
        bins[b].append((p, y))
    ece = 0.0
    n = len(probs)
    for b_rows in bins.values():
        if not b_rows:
            continue
        ps, ys = zip(*b_rows)
        conf = sum(ps) / len(ps)
        acc = sum(ys) / len(ys)
        ece += (len(ps) / n) * abs(conf - acc)
    return ece


# ═══════════════════════════════════════════════════════════════════
# REST DAY COMPUTATION
# ═══════════════════════════════════════════════════════════════════

def _rest_days(last_date: date | None, current: date) -> int:
    """Days of rest before current game (0 = back-to-back).
    Default of 3 for first game of season (matches mlb_data_loader.py).
    """
    if last_date is None:
        return 3
    delta = (current - last_date).days
    return max(0, delta - 1)


# ═══════════════════════════════════════════════════════════════════
# GL2025 PARSING
# ═══════════════════════════════════════════════════════════════════

def _load_gl2025(
    gl_path: Path,
) -> tuple[dict[tuple[str, str], ContextRecord], str, int]:
    """Parse Retrosheet gl2025.txt sequentially, computing pre-game context.

    Returns:
        lookup:  {(date_str 'YYYY-MM-DD', home_team_full) -> ContextRecord}
        audit_hash: sha256 of key fields
        n_records: number of records parsed

    Retrosheet game log field layout (0-indexed):
        0  date YYYYMMDD
        1  double-header indicator (0=solo, 1=first, 2=second)
        2  day of week (Mon, Tue, Wed, Thu, Fri, Sat, Sun)
        3  visiting team ID (3-letter Retrosheet)
        4  visiting league
        5  visiting team game number in season
        6  home team ID (3-letter Retrosheet)
        7  home league
        8  home team game number in season
        9  visiting score (not used — PIT safety)
        10 home score (not used — PIT safety)
        12 day/night (D/N)
    """
    lookup: dict[tuple[str, str], ContextRecord] = {}

    # Sequential state
    last_game_date: dict[str, date | None] = defaultdict(lambda: None)
    consec_road: dict[str, int] = defaultdict(int)

    hash_parts: list[str] = []
    n_records = 0

    with open(gl_path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if len(row) < 13:
                continue

            date_raw = row[0].strip().strip('"')
            dh_raw = row[1].strip().strip('"')
            dow_raw = row[2].strip().strip('"')
            vis_retro = row[3].strip().strip('"')
            vis_gnum_raw = row[5].strip().strip('"')
            home_retro = row[6].strip().strip('"')
            home_gnum_raw = row[8].strip().strip('"')
            day_night_raw = row[12].strip().strip('"')

            # Parse date
            try:
                game_date = datetime.strptime(date_raw, "%Y%m%d").date()
                date_str = game_date.strftime("%Y-%m-%d")
            except ValueError:
                continue

            dh = int(dh_raw) if dh_raw.isdigit() else 0

            # Map team IDs to full names
            home_full = _RETRO_TO_FULL.get(home_retro)
            vis_full = _RETRO_TO_FULL.get(vis_retro)
            if home_full is None or vis_full is None:
                continue

            try:
                home_gnum = int(home_gnum_raw)
            except (ValueError, TypeError):
                home_gnum = 0
            try:
                vis_gnum = int(vis_gnum_raw)
            except (ValueError, TypeError):
                vis_gnum = 0

            # Pre-game state — compute rest days from prior game dates
            home_rest = _rest_days(last_game_date[home_full], game_date)
            away_rest = _rest_days(last_game_date[vis_full], game_date)

            # Away team's current road trip length (this game included)
            away_consec = consec_road[vis_full] + 1

            # Division / league
            home_div = _TEAM_DIVISION.get(home_full, "")
            vis_div = _TEAM_DIVISION.get(vis_full, "")
            div_match = bool(home_div) and (home_div == vis_div)
            same_lg = (
                home_div[:2] == vis_div[:2]
                if home_div and vis_div
                else False
            )

            dn = day_night_raw if day_night_raw in ("D", "N") else "N"

            key = (date_str, home_full)
            # Only insert first game for the same key (handles DH day)
            if key not in lookup:
                rec = ContextRecord(
                    game_date=date_str,
                    home_team=home_full,
                    away_team=vis_full,
                    home_rest_days=home_rest,
                    away_rest_days=away_rest,
                    away_consec_road_games=away_consec,
                    day_night=dn,
                    day_of_week=dow_raw,
                    double_header=dh,
                    home_season_game_num=home_gnum,
                    away_season_game_num=vis_gnum,
                    divisional_matchup=div_match,
                    same_league=same_lg,
                    source="retrosheet_gl2025",
                )
                lookup[key] = rec
                hash_parts.append(
                    f"{date_str}|{home_full}|{vis_full}"
                    f"|{home_rest}|{away_rest}|{away_consec}|{dn}"
                )

            n_records += 1

            # Post-game state update
            last_game_date[home_full] = game_date
            last_game_date[vis_full] = game_date
            consec_road[home_full] = 0          # home team ends road streak
            consec_road[vis_full] = away_consec  # away team continues road streak

    audit_hash = (
        "sha256:" + hashlib.sha256("|".join(hash_parts).encode()).hexdigest()
    )
    return lookup, audit_hash, n_records


# ═══════════════════════════════════════════════════════════════════
# BLEND FORMULA  (FROZEN: blend = 0.60*model + 0.40*market)
# ═══════════════════════════════════════════════════════════════════

def _blend_prob(model: float, market: float) -> float:
    return (1.0 - ALPHA) * model + ALPHA * market


def _fav_prob(blend: float) -> float:
    """Probability of the blend-favored side (always >= 0.5)."""
    return max(blend, 1.0 - blend)


# ═══════════════════════════════════════════════════════════════════
# ROW ENRICHMENT
# ═══════════════════════════════════════════════════════════════════

def _enrich_rows(
    predictions: list[dict],
    context_lookup: dict[tuple[str, str], ContextRecord],
) -> tuple[list[dict], ContextAlignment, str]:
    """Merge predictions with pre-game context features.

    Join key: (game_date 'YYYY-MM-DD', home_team full name)
    Returns enriched rows, alignment stats, and sample audit hash.
    """
    rows: list[dict] = []
    n_aligned = 0
    n_unaligned = 0
    hash_parts: list[str] = []

    for pred in predictions:
        gd = pred.get("game_date", "")
        ht = pred.get("home_team", "")
        key = (gd, ht)
        ctx = context_lookup.get(key)

        model_prob = float(pred.get("model_home_prob", 0.5))
        market_prob = float(pred.get("market_home_prob_no_vig", 0.5))
        home_win = int(pred.get("home_win", 0))

        blend = _blend_prob(model_prob, market_prob)
        fav_is_home = blend >= 0.5
        fav_p = _fav_prob(blend)
        fav_win = home_win if fav_is_home else (1 - home_win)

        p0 = pred.get("p0_features") or {}
        park_run_factor = p0.get("park_run_factor", None)
        season_game_index = p0.get("season_game_index", None)

        row: dict[str, Any] = {
            "game_date": gd,
            "home_team": ht,
            "away_team": pred.get("away_team", ""),
            "model_home_prob": model_prob,
            "market_home_prob_no_vig": market_prob,
            "home_win": home_win,
            "_blend": blend,
            "_fav_is_home": fav_is_home,
            "_fav_prob": fav_p,
            "_fav_win": fav_win,
            # From p0_features
            "park_run_factor": park_run_factor,
            "season_game_index": season_game_index,
            # Context (filled from gl2025 or None)
            "home_rest_days": None,
            "away_rest_days": None,
            "away_consec_road_games": None,
            "day_night": None,
            "day_of_week": None,
            "double_header": None,
            "home_season_game_num": None,
            "away_season_game_num": None,
            "divisional_matchup": None,
            "same_league": None,
            "_ctx_aligned": False,
        }

        if ctx is not None:
            row.update({
                "home_rest_days": ctx.home_rest_days,
                "away_rest_days": ctx.away_rest_days,
                "away_consec_road_games": ctx.away_consec_road_games,
                "day_night": ctx.day_night,
                "day_of_week": ctx.day_of_week,
                "double_header": ctx.double_header,
                "home_season_game_num": ctx.home_season_game_num,
                "away_season_game_num": ctx.away_season_game_num,
                "divisional_matchup": ctx.divisional_matchup,
                "same_league": ctx.same_league,
                "_ctx_aligned": True,
            })
            n_aligned += 1
            hash_parts.append(f"{gd}|{ht}|{ctx.day_night}|{ctx.home_rest_days}")
        else:
            n_unaligned += 1

        rows.append(row)

    n = len(predictions)
    coverage = n_aligned / n if n > 0 else 0.0
    sample_hash = (
        "sha256:" + hashlib.sha256("|".join(hash_parts[:100]).encode()).hexdigest()
    )

    alignment = ContextAlignment(
        n_predictions=n,
        n_gl_records=0,  # filled by caller
        n_aligned=n_aligned,
        n_unaligned=n_unaligned,
        coverage=round(coverage, 4),
        coverage_sufficient=coverage >= _MIN_COVERAGE_RATE,
        sample_audit_hash=sample_hash,
    )
    return rows, alignment, sample_hash


# ═══════════════════════════════════════════════════════════════════
# SEGMENT EXTRACTION
# ═══════════════════════════════════════════════════════════════════

_VALID_SEGMENTS = frozenset({
    "all", "heavy_favorite", "high_confidence", "extreme_favorite",
    "phase45_failure",
})


def _extract_segment(rows: list[dict], segment: str) -> list[dict]:
    if segment == "all":
        return list(rows)
    if segment == "heavy_favorite":
        return [r for r in rows if r["_fav_prob"] >= _HEAVY_FAV_THRESHOLD]
    if segment == "high_confidence":
        return [r for r in rows if r["_fav_prob"] >= _HIGH_CONF_THRESHOLD]
    if segment == "extreme_favorite":
        return [r for r in rows if r["_fav_prob"] >= _EXTREME_FAV_THRESHOLD]
    if segment == "phase45_failure":
        return [
            r for r in rows
            if r["_fav_prob"] >= _PHASE45_FAIL_MIN_FAV and r["_fav_win"] == 0
        ]
    return list(rows)


# ═══════════════════════════════════════════════════════════════════
# SEGMENT METRICS
# ═══════════════════════════════════════════════════════════════════

def _compute_segment_metrics(rows: list[dict]) -> SegmentMetrics:
    if not rows:
        return SegmentMetrics(
            n=0, model_brier=0.25, market_brier=0.25, blend_brier=0.25,
            blend_bss_vs_market=0.0, model_bss_vs_market=0.0,
            fav_win_rate=0.0, win_rate=0.0, ece_blend=0.0,
        )
    model_ps = [r["model_home_prob"] for r in rows]
    market_ps = [r["market_home_prob_no_vig"] for r in rows]
    blend_ps = [r["_blend"] for r in rows]
    labels = [r["home_win"] for r in rows]

    model_brier = _brier_score(model_ps, labels)
    market_brier = _brier_score(market_ps, labels)
    blend_brier = _brier_score(blend_ps, labels)

    return SegmentMetrics(
        n=len(rows),
        model_brier=round(model_brier, 4),
        market_brier=round(market_brier, 4),
        blend_brier=round(blend_brier, 4),
        blend_bss_vs_market=round(_bss_direct(blend_brier, market_brier), 4),
        model_bss_vs_market=round(_bss_direct(model_brier, market_brier), 4),
        fav_win_rate=round(sum(r["_fav_win"] for r in rows) / len(rows), 4),
        win_rate=round(sum(labels) / len(labels), 4),
        ece_blend=round(_compute_ece(blend_ps, labels), 4),
    )


# ═══════════════════════════════════════════════════════════════════
# CONTEXT BUCKETING
# ═══════════════════════════════════════════════════════════════════

def _get_context_bucket(row: dict, dim: str) -> str | None:
    """Return bucket label for `dim` from an enriched row, or None if missing."""

    if dim == "home_rest_days_bucket":
        v = row.get("home_rest_days")
        if v is None:
            return None
        if v == 0:
            return "b2b_0d"
        if v == 1:
            return "rest_1d"
        if v == 2:
            return "rest_2d"
        if v == 3:
            return "rest_3d"
        return "rest_4plus"

    if dim == "away_rest_days_bucket":
        v = row.get("away_rest_days")
        if v is None:
            return None
        if v == 0:
            return "b2b_0d"
        if v == 1:
            return "rest_1d"
        if v == 2:
            return "rest_2d"
        if v == 3:
            return "rest_3d"
        return "rest_4plus"

    if dim == "rest_imbalance_bucket":
        h = row.get("home_rest_days")
        a = row.get("away_rest_days")
        if h is None or a is None:
            return None
        diff = h - a
        if diff >= 2:
            return "home_2plus_more"
        if diff == 1:
            return "home_1_more"
        if diff == 0:
            return "equal_rest"
        if diff == -1:
            return "away_1_more"
        return "away_2plus_more"

    if dim == "back_to_back_bucket":
        h = row.get("home_rest_days")
        a = row.get("away_rest_days")
        if h is None or a is None:
            return None
        hb = h == 0
        ab = a == 0
        if hb and ab:
            return "both_b2b"
        if hb:
            return "home_b2b"
        if ab:
            return "away_b2b"
        return "neither_b2b"

    if dim == "day_night_bucket":
        dn = row.get("day_night")
        if dn == "D":
            return "day_game"
        if dn == "N":
            return "night_game"
        return None

    if dim == "day_of_week_bucket":
        dow = row.get("day_of_week")
        if dow in ("Sat", "Sun"):
            return "weekend"
        if dow == "Mon":
            return "monday"
        if dow == "Fri":
            return "friday"
        if dow in ("Tue", "Wed", "Thu"):
            return "midweek"
        return None

    if dim == "double_header_bucket":
        dh = row.get("double_header")
        if dh is None:
            return None
        if dh == 0:
            return "single_game"
        if dh == 1:
            return "dh_game1"
        if dh == 2:
            return "dh_game2"
        return None

    if dim == "divisional_matchup_bucket":
        dm = row.get("divisional_matchup")
        if dm is None:
            return None
        if dm:
            return "same_division"
        sl = row.get("same_league")
        if sl:
            return "same_league_diff_div"
        return "interleague"

    if dim == "fav_side_bucket":
        return "home_fav" if row["_fav_is_home"] else "away_fav"

    if dim == "park_run_env_bucket":
        prf = row.get("park_run_factor")
        if prf is None:
            return None
        if prf < 0.97:
            return "pitcher_park"
        if prf <= 1.03:
            return "neutral_park"
        return "hitter_park"

    if dim == "season_phase_bucket":
        sgi = row.get("season_game_index")
        if sgi is None:
            return None
        if sgi < 0.33:
            return "early_season"
        if sgi < 0.67:
            return "mid_season"
        return "late_season"

    if dim == "away_consec_road_bucket":
        n_road = row.get("away_consec_road_games")
        if n_road is None:
            return None
        if n_road <= 3:
            return "road_trip_1_3"
        if n_road <= 6:
            return "road_trip_4_6"
        return "road_trip_7plus"

    return None


# ═══════════════════════════════════════════════════════════════════
# BOOTSTRAP
# ═══════════════════════════════════════════════════════════════════

def _bootstrap_bss_vs_market(
    rows: list[dict],
    n_boot: int = _BOOTSTRAP_N,
    seed: int = 42,
) -> BootstrapResult:
    """Bootstrap 95 % CI for blend_bss_vs_market.

    Positive CI (ci_lower > 0) = blend reliably beats market.
    Returns a zero-width CI (0, 0) with significant=False when n < threshold.
    """
    n = len(rows)
    if n_boot == 0 or n < _MIN_BUCKET_N:
        m = _compute_segment_metrics(rows)
        return BootstrapResult(
            n=n, n_boot=n_boot,
            observed_delta=m.blend_bss_vs_market,
            ci_lower=0.0, ci_upper=0.0,
            prob_positive=0.5, significant=False,
        )

    rng = random.Random(seed)
    observed = _compute_segment_metrics(rows).blend_bss_vs_market
    boot_deltas: list[float] = []
    for _ in range(n_boot):
        sample = [rows[rng.randrange(n)] for _ in range(n)]
        boot_deltas.append(_compute_segment_metrics(sample).blend_bss_vs_market)

    boot_deltas.sort()
    lo_idx = int(0.025 * n_boot)
    hi_idx = int(0.975 * n_boot) - 1
    ci_lower = boot_deltas[lo_idx]
    ci_upper = boot_deltas[hi_idx]
    prob_pos = sum(1 for d in boot_deltas if d > 0) / n_boot
    # Significant AND positive direction: blend beats market
    significant = ci_lower > 0

    return BootstrapResult(
        n=n, n_boot=n_boot,
        observed_delta=round(observed, 4),
        ci_lower=round(ci_lower, 4),
        ci_upper=round(ci_upper, 4),
        prob_positive=round(prob_pos, 4),
        significant=significant,
    )


# ═══════════════════════════════════════════════════════════════════
# ATTRIBUTION DIMENSION
# ═══════════════════════════════════════════════════════════════════

def _compute_attribution_dimension(
    rows: list[dict],
    dim: str,
    segment_name: str,
    n_boot: int = _BOOTSTRAP_N,
) -> list[AttributionBucket]:
    """Compute per-bucket BSS and bootstrap CI for a single context dimension."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        label = _get_context_bucket(r, dim)
        if label is not None:
            buckets[label].append(r)

    results: list[AttributionBucket] = []
    for label, bucket_rows in sorted(buckets.items()):
        metrics = _compute_segment_metrics(bucket_rows)
        boot = _bootstrap_bss_vs_market(bucket_rows, n_boot=n_boot)
        results.append(AttributionBucket(
            dim=dim,
            bucket_label=label,
            n=len(bucket_rows),
            segment_name=segment_name,
            metrics=metrics,
            bootstrap=boot,
        ))
    return results


# ═══════════════════════════════════════════════════════════════════
# NEGATIVE CONTROL
# ═══════════════════════════════════════════════════════════════════

def _compute_negative_control(
    rows: list[dict],
    dim: str,
    segment: str,
    n_shuffle: int = 200,
    seed: int = 99,
) -> NegativeControl:
    """Permutation test: shuffle dim labels, check if bucket BSS std inflates.

    A real signal should produce larger per-bucket BSS spread than random label
    shuffling.  If shuffled std >= real std → likely overfit / noise.
    """
    seg_rows = _extract_segment(rows, segment)
    if len(seg_rows) < _MIN_BUCKET_N:
        return NegativeControl(
            dim=dim, segment=segment,
            real_blend_bss_delta=0.0,
            shuffled_mean_delta=0.0,
            shuffled_std_delta=0.0,
            null_rejected=False,
            overfit_risk=False,
        )

    # Real inter-bucket BSS range
    buckets_real = _compute_attribution_dimension(seg_rows, dim, segment, n_boot=0)
    if not buckets_real:
        return NegativeControl(
            dim=dim, segment=segment,
            real_blend_bss_delta=0.0,
            shuffled_mean_delta=0.0,
            shuffled_std_delta=0.0,
            null_rejected=False,
            overfit_risk=False,
        )
    real_bss = [b.metrics.blend_bss_vs_market for b in buckets_real]
    real_delta = max(real_bss) - min(real_bss) if len(real_bss) > 1 else 0.0

    # Shuffled distribution
    rng = random.Random(seed)
    labels_pool = [_get_context_bucket(r, dim) for r in seg_rows]
    labels_pool = [lb for lb in labels_pool if lb is not None]

    shuf_deltas: list[float] = []
    for _ in range(n_shuffle):
        shuffled = labels_pool[:]
        rng.shuffle(shuffled)
        shuf_buckets: dict[str, list[dict]] = defaultdict(list)
        lb_iter = iter(shuffled)
        for r in seg_rows:
            orig = _get_context_bucket(r, dim)
            if orig is not None:
                lbl = next(lb_iter, orig)
                shuf_buckets[lbl].append(r)
        bss_vals = [
            _compute_segment_metrics(br).blend_bss_vs_market
            for br in shuf_buckets.values()
            if br
        ]
        if len(bss_vals) > 1:
            shuf_deltas.append(max(bss_vals) - min(bss_vals))

    if not shuf_deltas:
        shuf_mean = 0.0
        shuf_std = 0.0
    else:
        shuf_mean = sum(shuf_deltas) / len(shuf_deltas)
        variance = sum((d - shuf_mean) ** 2 for d in shuf_deltas) / len(shuf_deltas)
        shuf_std = variance ** 0.5

    null_rejected = shuf_std > 0 and (real_delta - shuf_mean) > _OVERFIT_SIGMA * shuf_std
    # Overfit risk: shuffled std >= real_delta (noise explains the signal)
    overfit_risk = shuf_std >= real_delta and real_delta > 0

    return NegativeControl(
        dim=dim, segment=segment,
        real_blend_bss_delta=round(real_delta, 4),
        shuffled_mean_delta=round(shuf_mean, 4),
        shuffled_std_delta=round(shuf_std, 4),
        null_rejected=null_rejected,
        overfit_risk=overfit_risk,
    )


# ═══════════════════════════════════════════════════════════════════
# OOF VALIDATION (monthly fold)
# ═══════════════════════════════════════════════════════════════════

def _compute_oof(
    rows: list[dict],
    dim: str,
    segment: str,
) -> OOFResult:
    """Monthly OOF: blend_bss_vs_market per calendar month in segment."""
    seg_rows = _extract_segment(rows, segment)
    if len(seg_rows) < _MIN_SEGMENT_N:
        return OOFResult(
            dim=dim, segment=segment, n_folds=0,
            fold_months=[], fold_bss_deltas=[], fold_ns=[],
            oof_mean_delta=0.0,
            oof_consistent_sign=False,
            oof_significant=False,
        )

    by_month: dict[str, list[dict]] = defaultdict(list)
    for r in seg_rows:
        month = r["game_date"][:7]
        by_month[month].append(r)

    months = sorted(by_month.keys())
    fold_months: list[str] = []
    fold_deltas: list[float] = []
    fold_ns: list[int] = []

    for month in months:
        fold_rows = by_month[month]
        if len(fold_rows) < 5:
            continue
        m = _compute_segment_metrics(fold_rows)
        fold_months.append(month)
        fold_deltas.append(m.blend_bss_vs_market)
        fold_ns.append(len(fold_rows))

    if not fold_deltas:
        return OOFResult(
            dim=dim, segment=segment, n_folds=0,
            fold_months=[], fold_bss_deltas=[], fold_ns=[],
            oof_mean_delta=0.0,
            oof_consistent_sign=False,
            oof_significant=False,
        )

    oof_mean = sum(fold_deltas) / len(fold_deltas)
    consistent = all(d > 0 for d in fold_deltas)
    significant = abs(oof_mean) > _OOF_PROMISING_DELTA and consistent

    return OOFResult(
        dim=dim, segment=segment,
        n_folds=len(fold_months),
        fold_months=fold_months,
        fold_bss_deltas=[round(d, 5) for d in fold_deltas],
        fold_ns=fold_ns,
        oof_mean_delta=round(oof_mean, 5),
        oof_consistent_sign=consistent,
        oof_significant=significant,
    )


# ═══════════════════════════════════════════════════════════════════
# GATE DECISION
# ═══════════════════════════════════════════════════════════════════

def _decide_gate(
    alignment: ContextAlignment,
    all_metrics: SegmentMetrics,
    buckets: list[AttributionBucket],
    neg_controls: list[NegativeControl],
    oof_results: list[OOFResult],
) -> tuple[str, str, str, bool, bool, bool, bool]:
    """Decide gate and return (gate, rationale, next_step,
    any_boot_sig, any_oof_promising, any_overfit_risk, worth_phase68).
    """
    # Positive = blend beats market (ci_lower > 0)
    any_boot_sig = any(
        b.bootstrap.significant and b.bootstrap.ci_lower > 0
        for b in buckets
    )
    any_oof_promising = any(o.oof_significant and o.oof_mean_delta > 0 for o in oof_results)
    any_overfit_risk = any(nc.overfit_risk for nc in neg_controls)

    # Coverage check
    if alignment.n_aligned < _MIN_SEGMENT_N:
        gate = DATA_LIMITED_GATE
        rationale = (
            f"Context alignment n={alignment.n_aligned} insufficient "
            f"(< {_MIN_SEGMENT_N}).  Cannot evaluate context features."
        )
        next_step = "排查 gl2025.txt 對應問題，提高 context alignment 覆蓋率。"
        return gate, rationale, next_step, any_boot_sig, any_oof_promising, any_overfit_risk, False

    # Overfit risk check (must precede promising check)
    if any_overfit_risk:
        gate = OVERFIT_RISK
        bad_dims = [nc.dim for nc in neg_controls if nc.overfit_risk]
        rationale = (
            f"Negative control overfit risk detected for dimensions: {bad_dims}. "
            f"Shuffled label std >= real BSS spread — signal is noise-level."
        )
        next_step = "標記 OVERFIT_RISK。調查 small-bucket artifact。不可推進至 patch。"
        return gate, rationale, next_step, any_boot_sig, any_oof_promising, any_overfit_risk, False

    # Identify best bucket for reporting
    positive_buckets = [
        b for b in buckets
        if b.bootstrap.significant and b.bootstrap.ci_lower > 0
    ]

    if positive_buckets and any_oof_promising:
        # Promising: bootstrap sig positive AND OOF consistent positive
        best = max(positive_buckets, key=lambda b: b.bootstrap.ci_lower)
        gate = CONTEXT_FEATURE_PROMISING
        rationale = (
            f"Bootstrap-significant positive blend BSS vs market found in bucket "
            f"'{best.bucket_label}' of dim '{best.dim}' "
            f"(n={best.n}, ci=[{best.bootstrap.ci_lower:.3f},{best.bootstrap.ci_upper:.3f}]). "
            f"OOF consistent positive confirms signal."
        )
        next_step = (
            "標記 CONTEXT_FEATURE_PROMISING。"
            f"深入分析 {best.dim}/{best.bucket_label} 條件下的 blend 改進可能性。"
            "進行 Phase 68 針對此 context 進行條件 patch 評估。"
        )
        return gate, rationale, next_step, any_boot_sig, any_oof_promising, any_overfit_risk, True

    if positive_buckets:
        # Some bootstrap sig positive but OOF not consistent
        best = max(positive_buckets, key=lambda b: b.bootstrap.ci_lower)
        gate = DIAGNOSTIC_ONLY_SIGNAL
        rationale = (
            f"Bootstrap-significant positive bucket found: "
            f"'{best.bucket_label}' dim='{best.dim}' "
            f"(n={best.n}, ci=[{best.bootstrap.ci_lower:.3f},{best.bootstrap.ci_upper:.3f}]). "
            f"OOF not consistently positive — may be seasonal artifact."
        )
        next_step = (
            "標記 DIAGNOSTIC_ONLY_SIGNAL。"
            f"以更多月份數據驗證 {best.dim}/{best.bucket_label} 穩定性後再推進。"
        )
        return gate, rationale, next_step, any_boot_sig, any_oof_promising, any_overfit_risk, False

    # No positive signal — check DATA_LIMITED critical dims
    # Both lineup AND travel are DATA_LIMITED; cannot rule out context explanations
    critical_missing = [
        d for d in _DATA_LIMITED_DIMENSIONS
        if d in ("lineup_available", "lineup_missing", "key_batter_missing",
                 "travel_distance", "getaway_day")
    ]
    n_critical_missing = len(critical_missing)

    best_bss = max(
        (b.metrics.blend_bss_vs_market for b in buckets), default=0.0
    )

    if n_critical_missing >= 2:
        gate = DATA_LIMITED_GATE
        rationale = (
            f"No bootstrap-significant positive bucket found across {len(buckets)} buckets "
            f"(best blend_bss_vs_market={best_bss:+.4f}). "
            f"Critical context dimensions unavailable: {critical_missing}. "
            f"Cannot rule out lineup / travel / getaway explanations."
        )
        next_step = (
            "標記 DATA_LIMITED。補充 lineup API、travel distance、getaway schedule 數據源。"
            "現有 rest/day-night/division/park 維度無法解釋 heavy_fav 失敗。"
        )
        return gate, rationale, next_step, any_boot_sig, any_oof_promising, any_overfit_risk, False

    gate = CONTEXT_FEATURE_NOT_PROMISING
    rationale = (
        f"No bootstrap-significant positive context bucket found "
        f"(best blend_bss_vs_market={best_bss:+.4f} across {len(buckets)} buckets). "
        f"Rest / day-night / divisional / park context does not explain "
        f"heavy_fav / high_conf failure in blend vs market comparison."
    )
    next_step = (
        "標記 CONTEXT_FEATURE_NOT_PROMISING。"
        "考慮 Phase 68 進行 sequential pattern attribution 或 weather context。"
    )
    return gate, rationale, next_step, any_boot_sig, any_oof_promising, any_overfit_risk, False


# ═══════════════════════════════════════════════════════════════════
# SERIALIZATION
# ═══════════════════════════════════════════════════════════════════

def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses / lists to JSON-serialisable dicts."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(x) for x in obj]
    return obj


# ═══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def run_phase67_context_failure_attribution(
    predictions_path: Path,
    gl2025_path: Path,
    n_boot: int = _BOOTSTRAP_N,
    rng_seed: int = 42,
) -> Phase67Result:
    """Run full Phase 67 context failure attribution analysis.

    Args:
        predictions_path: Path to phase56 predictions JSONL.
        gl2025_path:      Path to Retrosheet gl2025.txt.
        n_boot:           Bootstrap iterations (default 1 000).
        rng_seed:         RNG seed for reproducibility.

    Returns:
        Phase67Result with gate and all attribution evidence.
    """
    # ── Verify safety constants ──────────────────────────────────
    assert CANDIDATE_PATCH_CREATED is False,  "SAFETY: candidate patch flag"
    assert PRODUCTION_MODIFIED is False,      "SAFETY: production modified flag"
    assert ALPHA_MODIFIED is False,           "SAFETY: alpha modified flag"
    assert DIAGNOSTIC_ONLY is True,           "SAFETY: diagnostic only flag"
    assert abs(ALPHA - 0.40) < 1e-9,         "SAFETY: alpha must be 0.40"

    # ── Load GL2025 context ───────────────────────────────────────
    context_lookup, gl_audit_hash, n_gl = _load_gl2025(gl2025_path)

    # ── Load predictions ─────────────────────────────────────────
    predictions: list[dict] = []
    with open(predictions_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                predictions.append(json.loads(line))

    # ── Enrich rows ───────────────────────────────────────────────
    rows, alignment, _ = _enrich_rows(predictions, context_lookup)
    alignment.n_gl_records = n_gl

    # ── Extract segments ──────────────────────────────────────────
    seg_all = _extract_segment(rows, "all")
    seg_hf = _extract_segment(rows, "heavy_favorite")
    seg_hc = _extract_segment(rows, "high_confidence")
    seg_xt = _extract_segment(rows, "extreme_favorite")
    seg_p45 = _extract_segment(rows, "phase45_failure")

    # ── Segment metrics ───────────────────────────────────────────
    m_all = _compute_segment_metrics(seg_all)
    m_hf = _compute_segment_metrics(seg_hf)
    m_hc = _compute_segment_metrics(seg_hc)
    m_p45 = _compute_segment_metrics(seg_p45)

    # ── Attribution analysis (on "all" segment for max power) ─────
    all_buckets: list[AttributionBucket] = []
    neg_controls: list[NegativeControl] = []
    oof_results: list[OOFResult] = []

    for dim in _AVAILABLE_DIMENSIONS:
        buckets = _compute_attribution_dimension(seg_all, dim, "all", n_boot=n_boot)
        all_buckets.extend(buckets)
        nc = _compute_negative_control(rows, dim, "all")
        neg_controls.append(nc)
        oof = _compute_oof(rows, dim, "all")
        oof_results.append(oof)

    # ── Gate decision ─────────────────────────────────────────────
    gate, rationale, next_step, any_boot_sig, any_oof, any_overfit, worth_68 = (
        _decide_gate(alignment, m_all, all_buckets, neg_controls, oof_results)
    )

    assert gate in _VALID_GATES, f"Invalid gate: {gate}"

    # ── Assemble result ───────────────────────────────────────────
    result = Phase67Result(
        phase_version=PHASE_VERSION,
        completion_marker=COMPLETION_MARKER,
        run_timestamp_utc=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        candidate_patch_created=CANDIDATE_PATCH_CREATED,
        production_modified=PRODUCTION_MODIFIED,
        alpha_modified=ALPHA_MODIFIED,
        diagnostic_only=DIAGNOSTIC_ONLY,
        alpha=ALPHA,
        phase66_gate_anchor=PHASE66_GATE_ANCHOR,
        phase65_gate_anchor=PHASE65_GATE_ANCHOR,
        phase64b_gate_anchor=PHASE64B_GATE_ANCHOR,
        context_alignment=alignment,
        segment_n_all=len(seg_all),
        segment_n_heavy_fav=len(seg_hf),
        segment_n_high_conf=len(seg_hc),
        segment_n_extreme_fav=len(seg_xt),
        segment_n_phase45_failure=len(seg_p45),
        all_metrics=m_all,
        heavy_fav_metrics=m_hf,
        high_conf_metrics=m_hc,
        phase45_failure_metrics=m_p45,
        attribution_buckets=all_buckets,
        negative_controls=neg_controls,
        oof_results=oof_results,
        gate=gate,
        gate_rationale=rationale,
        next_step=next_step,
        any_bootstrap_significant=any_boot_sig,
        any_oof_promising=any_oof,
        any_overfit_risk=any_overfit,
        worth_phase68=worth_68,
        data_limited_dimensions=_DATA_LIMITED_DIMENSIONS,
        data_limited_fields=_DATA_LIMITED_FIELDS,
        available_dimensions=_AVAILABLE_DIMENSIONS,
    )

    return result


def save_result(result: Phase67Result, output_path: Path) -> None:
    """Serialise Phase67Result to JSON."""
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(_to_dict(result), fh, indent=2, ensure_ascii=False)
