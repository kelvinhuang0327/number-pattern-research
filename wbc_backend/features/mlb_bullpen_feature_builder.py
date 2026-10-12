"""
wbc_backend/features/mlb_bullpen_feature_builder.py
====================================================
Phase 56 — Bullpen Feature Builder

功能：
  build_bullpen_features(game_record, context=None) -> dict

輸出五種牛棚特徵：
  - bullpen_fatigue_3d              過去 3 天牛棚使用負荷 proxy
  - bullpen_fatigue_7d              過去 7 天牛棚使用負荷 proxy
  - reliever_back_to_back_count     連續出賽 reliever 數量 proxy
  - bullpen_recent_era_proxy        最近牛棚表現 (ERA proxy)
  - late_game_leverage_usage_proxy  高槓桿牛棚使用量 proxy

Hard Rules (NEVER violate):
  - CANDIDATE_PATCH_CREATED = False
  - PRODUCTION_MODIFIED = False
  - DIAGNOSTIC_ONLY = True
  - 所有特徵必須 point-in-time safe
  - 不可使用 game_date 當天賽後資料
  - 不可使用 home_win / final_score / post_game_stats

Context 格式 (若提供)：
  context = {
    "home_schedule": [{"game_date": ..., "bullpen_outs": ..., "leverage_idx": ...}, ...],
    "away_schedule": [...],
  }
  schedule 中只能包含 game_date < 本場 game_date 的記錄。
"""
from __future__ import annotations

import hashlib
import logging
import math
from datetime import date
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Hard Constants ───────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
FEATURE_VERSION: str = "phase56_bullpen_v1"

# ─── Leakage Guard ────────────────────────────────────────────────────────────
_FORBIDDEN_FIELDS: frozenset[str] = frozenset({
    "home_win",
    "final_score",
    "home_score",
    "away_score",
    "result",
    "box_score",
    "post_game_stats",
    "closing_odds_after_game",
    "innings_pitched_today",
    "era_after_game",
    "game_score",
    "actual_starter_ip_today",
})

# ─── League average defaults (MLB 2024 reference) ─────────────────────────────
_LEAGUE_AVG_ERA: float = 4.10          # MLB 2024 bullpen ERA baseline
_NEUTRAL_FATIGUE: float = 0.0          # Neutral fatigue proxy (0 = unknown)
_NEUTRAL_B2B: int = 0                  # Neutral back-to-back count
_NEUTRAL_LEVERAGE: float = 0.0         # Neutral high-leverage usage (0 = unknown)

# ─── Fatigue computation parameters ──────────────────────────────────────────
_LOOKBACK_3D_DAYS: int = 3
_LOOKBACK_7D_DAYS: int = 7
_FATIGUE_PER_OUT: float = 0.1          # Fatigue unit per bullpen out recorded
_FATIGUE_CAP: float = 1.0              # Maximum fatigue proxy value
_LEVERAGE_HIGH_THRESHOLD: float = 1.5  # High-leverage index threshold


def _check_leakage(record: dict) -> list[str]:
    """Identify forbidden post-game fields in a record."""
    violations: list[str] = []
    for field in _FORBIDDEN_FIELDS:
        if field in record and record[field] is not None:
            violations.append(field)
    return violations


def _compute_fatigue_from_schedule(
    schedule: list[dict],
    game_date_str: str,
    lookback_days: int,
) -> tuple[float, bool]:
    """
    Compute bullpen fatigue proxy from historical game schedule.

    Args:
        schedule: List of past game records for a team.
                  Each must have "game_date" (YYYY-MM-DD) and "bullpen_outs".
        game_date_str: The current game date (YYYY-MM-DD).
        lookback_days: Number of days to look back.

    Returns:
        (fatigue_value, data_available)

    point-in-time safety: only games BEFORE game_date are included.
    """
    try:
        game_d = date.fromisoformat(game_date_str)
    except ValueError:
        return _NEUTRAL_FATIGUE, False

    total_outs = 0.0
    games_found = 0

    for g in schedule:
        gd_str = g.get("game_date", "")
        if not gd_str:
            continue
        try:
            gd = date.fromisoformat(gd_str)
        except ValueError:
            continue

        # Strict point-in-time: only use games BEFORE game_date
        if gd >= game_d:
            continue
        days_ago = (game_d - gd).days
        if days_ago <= lookback_days:
            outs = float(g.get("bullpen_outs", 0))
            total_outs += outs
            games_found += 1

    if games_found == 0:
        return _NEUTRAL_FATIGUE, False

    raw_fatigue = total_outs * _FATIGUE_PER_OUT
    fatigue = min(_FATIGUE_CAP, raw_fatigue)
    return round(fatigue, 4), True


def _compute_b2b_from_schedule(
    schedule: list[dict],
    game_date_str: str,
) -> tuple[int, bool]:
    """
    Compute reliever back-to-back count proxy.

    A reliever is counted as back-to-back if they appeared in consecutive games.
    Since we lack individual reliever records, proxy = number of consecutive
    game days within last 2 days with bullpen usage > 2 outs.

    point-in-time safety: only games BEFORE game_date are included.
    """
    try:
        game_d = date.fromisoformat(game_date_str)
    except ValueError:
        return _NEUTRAL_B2B, False

    # Collect game dates (before game_date) within 2 days
    recent_dates: set[date] = set()
    games_found = 0
    for g in schedule:
        gd_str = g.get("game_date", "")
        if not gd_str:
            continue
        try:
            gd = date.fromisoformat(gd_str)
        except ValueError:
            continue
        if gd >= game_d:
            continue
        days_ago = (game_d - gd).days
        if days_ago <= 2 and float(g.get("bullpen_outs", 0)) > 2:
            recent_dates.add(gd)
            games_found += 1

    if games_found == 0:
        return _NEUTRAL_B2B, False

    b2b_count = len(recent_dates)
    return b2b_count, True


def _compute_era_from_schedule(
    schedule: list[dict],
    game_date_str: str,
    lookback_days: int = 14,
) -> tuple[float, bool]:
    """
    Compute bullpen recent ERA proxy.

    Uses earned_runs / innings_pitched ratio from past {lookback_days} days.
    Annualizes to ERA format (× 9).

    point-in-time safety: only games BEFORE game_date are included.
    """
    try:
        game_d = date.fromisoformat(game_date_str)
    except ValueError:
        return _LEAGUE_AVG_ERA, False

    total_er = 0.0
    total_outs = 0.0
    games_found = 0

    for g in schedule:
        gd_str = g.get("game_date", "")
        if not gd_str:
            continue
        try:
            gd = date.fromisoformat(gd_str)
        except ValueError:
            continue
        if gd >= game_d:
            continue
        days_ago = (game_d - gd).days
        if days_ago <= lookback_days:
            er = float(g.get("bullpen_earned_runs", 0))
            outs = float(g.get("bullpen_outs", 0))
            total_er += er
            total_outs += outs
            games_found += 1

    if games_found == 0 or total_outs == 0:
        return _LEAGUE_AVG_ERA, False

    # ERA = (ER / (outs/3)) × 9
    ip = total_outs / 3.0
    era = (total_er / ip) * 9.0
    # Clamp to reasonable range [0, 15]
    era = max(0.0, min(15.0, era))
    return round(era, 3), True


def _compute_leverage_from_schedule(
    schedule: list[dict],
    game_date_str: str,
    lookback_days: int = 7,
) -> tuple[float, bool]:
    """
    Compute high-leverage usage proxy.

    Counts bullpen appearances in high-leverage situations
    (leverage_idx >= _LEVERAGE_HIGH_THRESHOLD) over last {lookback_days} days.
    Normalizes by total appearances.

    point-in-time safety: only games BEFORE game_date are included.
    """
    try:
        game_d = date.fromisoformat(game_date_str)
    except ValueError:
        return _NEUTRAL_LEVERAGE, False

    total_appearances = 0
    high_lev_appearances = 0
    games_found = 0

    for g in schedule:
        gd_str = g.get("game_date", "")
        if not gd_str:
            continue
        try:
            gd = date.fromisoformat(gd_str)
        except ValueError:
            continue
        if gd >= game_d:
            continue
        days_ago = (game_d - gd).days
        if days_ago <= lookback_days:
            apps = int(g.get("bullpen_appearances", 0))
            high_lev = int(g.get("high_leverage_appearances", 0))
            total_appearances += apps
            high_lev_appearances += high_lev
            games_found += 1

    if games_found == 0 or total_appearances == 0:
        return _NEUTRAL_LEVERAGE, False

    ratio = high_lev_appearances / total_appearances
    return round(ratio, 4), True


def _compute_audit_hash(
    game_id: str,
    home_f3d: float,
    away_f3d: float,
    available: bool,
) -> str:
    parts = f"{game_id}|{home_f3d:.4f}|{away_f3d:.4f}|{available}"
    return "sha256:" + hashlib.sha256(parts.encode()).hexdigest()[:32]


def build_bullpen_features(
    game_record: dict,
    context: Optional[dict] = None,
) -> dict:
    """
    Build bullpen features for a single game.

    Args:
        game_record: Raw game record (must contain game_id, game_date,
                     home_team, away_team). Forbidden post-game fields
                     are silently ignored.
        context: Optional dict with keys "home_schedule" and "away_schedule".
                 Each schedule is a list of prior-game dicts with:
                   - game_date (YYYY-MM-DD, must be < game_date)
                   - bullpen_outs (float)
                   - bullpen_earned_runs (float)
                   - bullpen_appearances (int)
                   - high_leverage_appearances (int)
                 If None or empty, all features use neutral fallback.

    Returns:
        dict with all Phase56 bullpen feature fields.

    Hard rules enforced:
        - candidate_patch_created = False
        - production_modified = False
        - point_in_time_safe = True (validated internally)
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    game_id = str(game_record.get("game_id", ""))
    game_date = str(game_record.get("game_date", ""))

    # Leakage check — log but don't raise
    leakage_violations = _check_leakage(game_record)
    if leakage_violations:
        logger.warning(
            "game_id=%s: forbidden post-game fields detected (ignored): %s",
            game_id,
            leakage_violations,
        )

    # Extract schedules
    home_schedule: list[dict] = []
    away_schedule: list[dict] = []
    if context is not None:
        home_schedule = context.get("home_schedule", [])
        away_schedule = context.get("away_schedule", [])

        # Validate point-in-time safety of schedule data
        for entry in home_schedule + away_schedule:
            violations = _check_leakage(entry)
            if violations:
                logger.warning(
                    "Schedule entry for game_id=%s has forbidden fields (ignored): %s",
                    game_id, violations
                )

    # ── Feature 1 & 2: Bullpen fatigue (3d / 7d) ──────────────────────────
    home_f3d, home_f3d_avail = _compute_fatigue_from_schedule(home_schedule, game_date, _LOOKBACK_3D_DAYS)
    away_f3d, away_f3d_avail = _compute_fatigue_from_schedule(away_schedule, game_date, _LOOKBACK_3D_DAYS)
    home_f7d, home_f7d_avail = _compute_fatigue_from_schedule(home_schedule, game_date, _LOOKBACK_7D_DAYS)
    away_f7d, away_f7d_avail = _compute_fatigue_from_schedule(away_schedule, game_date, _LOOKBACK_7D_DAYS)

    # ── Feature 3: Reliever back-to-back count ─────────────────────────────
    home_b2b, home_b2b_avail = _compute_b2b_from_schedule(home_schedule, game_date)
    away_b2b, away_b2b_avail = _compute_b2b_from_schedule(away_schedule, game_date)

    # ── Feature 4: Bullpen recent ERA proxy ────────────────────────────────
    home_era, home_era_avail = _compute_era_from_schedule(home_schedule, game_date)
    away_era, away_era_avail = _compute_era_from_schedule(away_schedule, game_date)

    # ── Feature 5: Late-game leverage usage proxy ──────────────────────────
    home_lev, home_lev_avail = _compute_leverage_from_schedule(home_schedule, game_date)
    away_lev, away_lev_avail = _compute_leverage_from_schedule(away_schedule, game_date)

    # Overall feature availability: require at least fatigue_3d for both teams
    bullpen_feature_available = home_f3d_avail and away_f3d_avail

    # Fallback reason
    if not bullpen_feature_available:
        fallback_reason = "no_relief_pitcher_usage_data"
        source = "neutral_fallback"
    else:
        fallback_reason = "partial_data_available"
        source = "historical_schedule_proxy"

    # Delta features
    fatigue_delta_3d = round(away_f3d - home_f3d, 4)   # + = away more fatigued = home advantage
    fatigue_delta_7d = round(away_f7d - home_f7d, 4)

    audit_hash = _compute_audit_hash(game_id, home_f3d, away_f3d, bullpen_feature_available)

    return {
        "feature_version": FEATURE_VERSION,
        # Home bullpen
        "home_bullpen_fatigue_3d": home_f3d,
        "home_bullpen_fatigue_7d": home_f7d,
        "home_reliever_b2b_count": home_b2b,
        "home_bullpen_recent_era_proxy": home_era,
        "home_late_game_leverage_usage_proxy": home_lev,
        # Away bullpen
        "away_bullpen_fatigue_3d": away_f3d,
        "away_bullpen_fatigue_7d": away_f7d,
        "away_reliever_b2b_count": away_b2b,
        "away_bullpen_recent_era_proxy": away_era,
        "away_late_game_leverage_usage_proxy": away_lev,
        # Delta (positive = away team more fatigued = home advantage)
        "bullpen_fatigue_delta_3d": fatigue_delta_3d,
        "bullpen_fatigue_delta_7d": fatigue_delta_7d,
        # Availability flags
        "bullpen_feature_available": bullpen_feature_available,
        "home_bullpen_fatigue_3d_available": home_f3d_avail,
        "away_bullpen_fatigue_3d_available": away_f3d_avail,
        "home_bullpen_era_available": home_era_avail,
        "away_bullpen_era_available": away_era_avail,
        # Metadata
        "bullpen_feature_source": source,
        "fallback_reason": fallback_reason,
        "estimated": not bullpen_feature_available,
        "point_in_time_safe": True,
        "audit_hash": audit_hash,
        # Hard rules (always embedded for traceability)
        "candidate_patch_created": False,
        "production_modified": False,
        "diagnostic_only": True,
    }
