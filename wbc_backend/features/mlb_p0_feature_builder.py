"""
Phase 48 — P0 Feature Builder
==============================
Implements three P0 features from Phase 46 Feature Repair Blueprint:

  F-001  sp_fip_delta         Starting pitcher FIP quality delta
  F-002  park_run_factor      Ball-park run environment factor
  F-004  season_game_index    Season-progress dampener (0.0–1.0)

Hard Rules (inherited from Phase 46 Blueprint):
  - CANDIDATE_PATCH_CREATED = False (never create a candidate patch)
  - PRODUCTION_MODIFIED     = False (never touch the production model)
  - alpha                   = 0.4   (not adjustable here)
  - NO external API / LLM calls
  - ALL features must be point-in-time safe (no look-ahead leakage)

Leakage guard:
  Any of the following fields present in game_record/context are silently
  ignored and logged to audit_notes; they NEVER influence feature values:
    home_win, final_score, home_score, away_score, result,
    closing_odds_after_game, post_game_stats
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Safety invariants ────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
FEATURE_VERSION: str = "phase48_p0_v1"

# Fields that must NEVER influence feature values (leakage guard)
_FORBIDDEN_FIELDS: frozenset[str] = frozenset({
    "home_win",
    "final_score",
    "home_score",
    "away_score",
    "result",
    "closing_odds_after_game",
    "post_game_stats",
})

# ─── Season boundaries for F-004 ─────────────────────────────────────────────
_SEASON_START: date = date(2025, 3, 1)   # before this → index 0.0
_SEASON_END: date   = date(2025, 10, 1)  # on/after this → index 1.0
_SEASON_DAYS: int   = (_SEASON_END - _SEASON_START).days  # 214

# ─── Park run factor lookup table (F-002) ─────────────────────────────────────
# Values relative to 1.00 = league average.
# Source: Baseball Reference Park Factors (2022-2024 rolling average).
# Point-in-time safe: uses prior-season data, no current game outcome.
_PARK_RUN_FACTOR: dict[str, float] = {
    # High-run environments (>= 1.03)
    "Colorado Rockies":         1.15,   # Coors Field
    "Boston Red Sox":           1.08,   # Fenway Park
    "Chicago Cubs":             1.03,   # Wrigley Field
    "New York Yankees":         1.04,   # Yankee Stadium
    "Cincinnati Reds":          1.05,   # Great American Ball Park
    "Texas Rangers":            1.04,   # Globe Life Field
    "Philadelphia Phillies":    1.03,   # Citizens Bank Park
    "Atlanta Braves":           1.02,   # Truist Park
    "Houston Astros":           1.02,   # Minute Maid Park
    "Minnesota Twins":          1.01,   # Target Field
    # Neutral
    "Cleveland Guardians":      1.00,
    "Detroit Tigers":           1.00,
    "Kansas City Royals":       1.00,
    "Toronto Blue Jays":        1.00,
    "Baltimore Orioles":        1.00,
    "Pittsburgh Pirates":       1.00,
    "Milwaukee Brewers":        1.00,
    "Arizona Diamondbacks":     1.00,
    "Chicago White Sox":        0.99,
    "Los Angeles Angels":       0.99,
    "St. Louis Cardinals":      0.99,
    "New York Mets":            0.98,
    "Washington Nationals":     0.98,
    "Miami Marlins":            0.97,
    "Tampa Bay Rays":           0.97,
    # Low-run environments (<= 0.96)
    "Los Angeles Dodgers":      0.96,   # Dodger Stadium
    "Athletics":                0.96,   # (Sutter Health Park 2025)
    "San Francisco Giants":     0.96,   # Oracle Park
    "San Diego Padres":         0.94,   # Petco Park
    "Seattle Mariners":         0.95,   # T-Mobile Park
}


# ═══════════════════════════════════════════════════════════════════════════════
# § Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _strip_forbidden(
    mapping: dict[str, Any],
    label: str,
) -> tuple[dict[str, Any], list[str]]:
    """
    Return a copy of *mapping* with forbidden fields removed.
    Also returns a sorted list of field names that were stripped.
    """
    stripped: list[str] = []
    clean: dict[str, Any] = {}
    for k, v in mapping.items():
        if k in _FORBIDDEN_FIELDS:
            stripped.append(k)
        else:
            clean[k] = v
    if stripped:
        logger.warning(
            "[phase48][leakage_guard][%s] Ignoring forbidden fields: %s",
            label,
            stripped,
        )
    return clean, sorted(stripped)


def _compute_feature_audit_hash(
    game_id: str,
    sp_fip_delta: float,
    park_run_factor: float,
    season_game_index: float,
    feature_version: str,
) -> str:
    """Deterministic SHA-256 over the three feature values + identifiers."""
    payload = "|".join([
        game_id,
        feature_version,
        f"{sp_fip_delta:.8f}",
        f"{park_run_factor:.8f}",
        f"{season_game_index:.8f}",
    ])
    return hashlib.sha256(payload.encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
# § F-001  sp_fip_delta
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_sp_fip_delta(
    context: dict[str, Any],
) -> tuple[float, bool]:
    """
    Compute F-001: starting pitcher FIP delta.

    sp_fip_delta = away_sp_fip - home_sp_fip
    Positive value ⇒ home starter is superior (lower FIP is better).

    Context keys expected (both required for non-fallback):
      - home_sp_fip  float   Home team probable starter season FIP
      - away_sp_fip  float   Away team probable starter season FIP

    Returns:
      (sp_fip_delta, available)
      available=False → neutral fallback (0.0)
    """
    home_fip = context.get("home_sp_fip")
    away_fip = context.get("away_sp_fip")

    if home_fip is None or away_fip is None:
        return 0.0, False

    try:
        home_fip = float(home_fip)
        away_fip = float(away_fip)
    except (TypeError, ValueError):
        return 0.0, False

    if not (0.0 <= home_fip <= 15.0 and 0.0 <= away_fip <= 15.0):
        logger.warning(
            "[phase48][sp_fip_delta] FIP values out of plausible range "
            "(home=%.2f, away=%.2f) — using fallback",
            home_fip, away_fip,
        )
        return 0.0, False

    delta = away_fip - home_fip
    return round(delta, 6), True


# ═══════════════════════════════════════════════════════════════════════════════
# § F-002  park_run_factor
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_park_run_factor(
    home_team: str,
) -> tuple[float, bool]:
    """
    Compute F-002: park run factor for the home team's ballpark.

    Returns:
      (park_run_factor, available)
      available=False → unknown park, returns neutral fallback 1.00
    """
    factor = _PARK_RUN_FACTOR.get(home_team)
    if factor is None:
        return 1.00, False
    return factor, True


# ═══════════════════════════════════════════════════════════════════════════════
# § F-004  season_game_index
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_season_game_index(game_date_str: str) -> tuple[float, bool]:
    """
    Compute F-004: season progress index in [0.0, 1.0].

    Linearly interpolated between _SEASON_START (0.0) and _SEASON_END (1.0).
    Dates before _SEASON_START return 0.0; on/after _SEASON_END return 1.0.

    Returns:
      (season_game_index, available)
      available=False if game_date_str cannot be parsed.
    """
    if not game_date_str:
        return 0.0, False
    try:
        gd = date.fromisoformat(game_date_str)
    except ValueError:
        return 0.0, False

    if gd <= _SEASON_START:
        return 0.0, True
    if gd >= _SEASON_END:
        return 1.0, True

    elapsed = (gd - _SEASON_START).days
    index = elapsed / _SEASON_DAYS
    return round(min(1.0, max(0.0, index)), 6), True


# ═══════════════════════════════════════════════════════════════════════════════
# § Public API
# ═══════════════════════════════════════════════════════════════════════════════

def build_mlb_p0_features(
    game_record: dict[str, Any],
    context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Build all P0 features for a single game record.

    Parameters
    ----------
    game_record : dict
        A dict representing one game (e.g. a PredictionRow deserialized to dict).
        Required keys: ``game_date``, ``home_team``, ``game_id`` (optional fallback).
        Forbidden keys (home_win, final_score, …) are silently ignored.

    context : dict | None
        Optional per-game enrichment dict.  May include:
          - ``home_sp_fip``   float  home starter FIP (prior to game)
          - ``away_sp_fip``   float  away starter FIP (prior to game)
        Forbidden keys present here are also silently ignored.

    Returns
    -------
    dict with keys:
      feature_version            str
      candidate_patch_created    bool  (always False)
      production_modified        bool  (always False)
      sp_fip_delta               float
      sp_fip_delta_available     bool
      park_run_factor            float
      park_factor_available      bool
      season_game_index          float
      season_game_index_available bool
      feature_audit_hash         str   (SHA-256, 64 hex chars)
      audit_notes                dict  (metadata, ignored_forbidden_fields, etc.)
    """
    if context is None:
        context = {}

    # ── Leakage guard: strip forbidden fields from both inputs ────────────────
    clean_record, forbidden_from_record = _strip_forbidden(game_record, "game_record")
    clean_context, forbidden_from_context = _strip_forbidden(context, "context")
    ignored_forbidden_fields: list[str] = sorted(
        set(forbidden_from_record) | set(forbidden_from_context)
    )

    # ── Extract safe identifiers ──────────────────────────────────────────────
    game_id: str    = str(clean_record.get("game_id", ""))
    home_team: str  = str(clean_record.get("home_team", ""))
    game_date: str  = str(clean_record.get("game_date", ""))

    # ── F-001 sp_fip_delta ────────────────────────────────────────────────────
    sp_fip_delta, sp_fip_delta_available = _compute_sp_fip_delta(clean_context)

    # ── F-002 park_run_factor ─────────────────────────────────────────────────
    park_run_factor, park_factor_available = _compute_park_run_factor(home_team)

    # ── F-004 season_game_index ───────────────────────────────────────────────
    season_game_index, season_game_index_available = _compute_season_game_index(
        game_date
    )

    # ── Audit hash ────────────────────────────────────────────────────────────
    feature_audit_hash = _compute_feature_audit_hash(
        game_id=game_id,
        sp_fip_delta=sp_fip_delta,
        park_run_factor=park_run_factor,
        season_game_index=season_game_index,
        feature_version=FEATURE_VERSION,
    )

    return {
        "feature_version":              FEATURE_VERSION,
        "candidate_patch_created":      CANDIDATE_PATCH_CREATED,
        "production_modified":          PRODUCTION_MODIFIED,
        # F-001
        "sp_fip_delta":                 sp_fip_delta,
        "sp_fip_delta_available":       sp_fip_delta_available,
        # F-002
        "park_run_factor":              park_run_factor,
        "park_factor_available":        park_factor_available,
        # F-004
        "season_game_index":            season_game_index,
        "season_game_index_available":  season_game_index_available,
        # Integrity
        "feature_audit_hash":           feature_audit_hash,
        "audit_notes": {
            "ignored_forbidden_fields": ignored_forbidden_fields,
            "sp_fip_source":            "context" if sp_fip_delta_available else "neutral_fallback",
            "park_factor_source":       "lookup_table" if park_factor_available else "neutral_fallback",
            "season_index_source":      "computed" if season_game_index_available else "neutral_fallback",
        },
    }
