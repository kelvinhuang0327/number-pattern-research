"""
wbc_backend/features/mlb_bullpen_feature_injection.py
=====================================================
Phase 56 — Bullpen Feature Injection Adapter

功能：
  apply_bullpen_adjustment(base_model_prob, bullpen_features) -> BullpenAdjustmentResult

調整邏輯（保守 deterministic，不重新訓練模型）：

1. bullpen_fatigue_delta_3d
   若 bullpen_feature_available 且 |delta_3d| > FATIGUE_MIN_THRESHOLD：
     delta_3d > 0 (away 更疲憊)：小幅提升 home win prob
     delta_3d < 0 (home 更疲憊)：小幅降低 home win prob
     adjustment = delta_3d * FATIGUE_SCALE

2. bullpen_recent_era_proxy delta
   若 away_era_available 且 home_era_available：
     away_era > home_era (away bullpen 表現差)：小幅提升 home win prob
     away_era < home_era (home bullpen 表現差)：小幅降低 home win prob

3. late_game_leverage_usage_proxy
   若 home_late_game_leverage_usage_proxy > HIGH_LEVERAGE_THRESHOLD：
     home 過度使用高槓桿 relievers → 輕微往 0.5 收縮

Hard Rules (NEVER violate):
  - CANDIDATE_PATCH_CREATED = False
  - PRODUCTION_MODIFIED = False
  - DIAGNOSTIC_ONLY = True
  - 單場最大 ±0.015 total adjustment
  - adjusted_prob clamp [0.01, 0.99]
  - bullpen_feature_available = False → no adjustment (neutral)
  - 不讀取 home_win / final_score / post_game_stats
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

# ─── Hard Constants ───────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
FEATURE_VERSION: str = "phase56_bullpen_injected_v1"

# ─── Adjustment bounds ────────────────────────────────────────────────────────
_MAX_TOTAL_ADJUSTMENT: float = 0.015         # cap per game (per spec)
_PROB_CLAMP_LO: float = 0.01
_PROB_CLAMP_HI: float = 0.99

# ─── Feature scaling constants ────────────────────────────────────────────────
_FATIGUE_MIN_THRESHOLD: float = 0.05         # ignore tiny fatigue differences
_FATIGUE_SCALE: float = 0.008                # per 1 unit of fatigue delta
_ERA_DELTA_SCALE: float = 0.0015             # per 1 ERA point difference
_ERA_LEAGUE_AVG: float = 4.10                # fallback if ERA unavailable
_HIGH_LEVERAGE_THRESHOLD: float = 0.60      # home leverage ratio > 0.60 → shrink
_LEVERAGE_SHRINK_RATE: float = 0.003         # shrink toward 0.5

# ─── Forbidden fields ─────────────────────────────────────────────────────────
_FORBIDDEN_FIELDS: frozenset[str] = frozenset({
    "home_win", "final_score", "home_score", "away_score",
    "result", "closing_odds_after_game", "post_game_stats",
})


@dataclass
class BullpenAdjustmentResult:
    """Result of a single bullpen adjustment operation."""
    original_model_home_prob: float
    adjusted_model_home_prob: float
    bullpen_adjustment: float              # total signed adjustment
    adjustment_components: dict[str, float] = field(default_factory=dict)
    bullpen_feature_available: bool = False
    feature_effect_mode: str = "REPORT_ONLY"   # REPORT_ONLY | MODEL_AFFECTING
    adjustment_capped: bool = False
    fallback_applied: bool = True
    audit_hash: str = ""
    feature_version: str = FEATURE_VERSION
    # Hard rules (always embedded)
    candidate_patch_created: bool = False
    production_modified: bool = False
    diagnostic_only: bool = True


def apply_bullpen_adjustment(
    base_model_prob: float,
    bullpen_features: dict,
) -> BullpenAdjustmentResult:
    """
    Apply bullpen features as an additive adjustment to base model probability.

    Args:
        base_model_prob: Raw model home-win probability [0.01, 0.99].
        bullpen_features: Output of build_bullpen_features().
                          Forbidden post-game fields silently ignored.

    Returns:
        BullpenAdjustmentResult

    Hard rules:
        - candidate_patch_created = False (always)
        - production_modified = False (always)
        - diagnostic_only = True (always)
        - total adjustment capped at ±0.015
        - adjusted_prob clamped to [0.01, 0.99]
        - bullpen_feature_available = False → neutral (0 adjustment)
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED
    assert DIAGNOSTIC_ONLY

    # Sanitize forbidden fields
    safe_features = {
        k: v for k, v in bullpen_features.items()
        if k not in _FORBIDDEN_FIELDS
    }

    feature_available = bool(safe_features.get("bullpen_feature_available", False))

    # Early exit: no data → neutral
    if not feature_available:
        audit_hash = _compute_audit_hash(base_model_prob, 0.0, "no_data")
        return BullpenAdjustmentResult(
            original_model_home_prob=base_model_prob,
            adjusted_model_home_prob=base_model_prob,
            bullpen_adjustment=0.0,
            adjustment_components={},
            bullpen_feature_available=False,
            feature_effect_mode="REPORT_ONLY",
            adjustment_capped=False,
            fallback_applied=True,
            audit_hash=audit_hash,
            candidate_patch_created=False,
            production_modified=False,
            diagnostic_only=True,
        )

    components: dict[str, float] = {}

    # ── Component 1: Fatigue delta ─────────────────────────────────────────
    fatigue_delta_3d = float(safe_features.get("bullpen_fatigue_delta_3d", 0.0))
    if abs(fatigue_delta_3d) > _FATIGUE_MIN_THRESHOLD:
        adj_fatigue = fatigue_delta_3d * _FATIGUE_SCALE
        components["bullpen_fatigue_3d"] = round(adj_fatigue, 5)

    # ── Component 2: ERA proxy delta ───────────────────────────────────────
    home_era = float(safe_features.get("home_bullpen_recent_era_proxy", _ERA_LEAGUE_AVG))
    away_era = float(safe_features.get("away_bullpen_recent_era_proxy", _ERA_LEAGUE_AVG))
    home_era_avail = bool(safe_features.get("home_bullpen_era_available", False))
    away_era_avail = bool(safe_features.get("away_bullpen_era_available", False))

    if home_era_avail and away_era_avail:
        era_delta = away_era - home_era   # positive = away bullpen worse = home advantage
        adj_era = era_delta * _ERA_DELTA_SCALE
        components["bullpen_era_delta"] = round(adj_era, 5)

    # ── Component 3: High-leverage shrinkage ──────────────────────────────
    home_leverage = float(safe_features.get("home_late_game_leverage_usage_proxy", 0.0))
    home_lev_avail = bool(safe_features.get("home_lev_avail", False))  # optional field
    if home_leverage > _HIGH_LEVERAGE_THRESHOLD and base_model_prob > 0.60:
        adj_lev = -(base_model_prob - 0.5) * _LEVERAGE_SHRINK_RATE
        components["high_leverage_shrink"] = round(adj_lev, 5)

    # ── Aggregate ──────────────────────────────────────────────────────────
    total_adj = sum(components.values())
    adjustment_capped = abs(total_adj) > _MAX_TOTAL_ADJUSTMENT
    if adjustment_capped:
        # Scale down to cap
        sign = 1.0 if total_adj >= 0 else -1.0
        total_adj = sign * _MAX_TOTAL_ADJUSTMENT

    adjusted_prob = base_model_prob + total_adj
    adjusted_prob = max(_PROB_CLAMP_LO, min(_PROB_CLAMP_HI, adjusted_prob))
    adjusted_prob = round(adjusted_prob, 6)

    effect_mode = "MODEL_AFFECTING" if abs(total_adj) > 1e-9 else "REPORT_ONLY"

    audit_hash = _compute_audit_hash(base_model_prob, total_adj, "bullpen_adj")

    return BullpenAdjustmentResult(
        original_model_home_prob=base_model_prob,
        adjusted_model_home_prob=adjusted_prob,
        bullpen_adjustment=round(total_adj, 6),
        adjustment_components=components,
        bullpen_feature_available=True,
        feature_effect_mode=effect_mode,
        adjustment_capped=adjustment_capped,
        fallback_applied=False,
        audit_hash=audit_hash,
        candidate_patch_created=False,
        production_modified=False,
        diagnostic_only=True,
    )


def _compute_audit_hash(base_prob: float, total_adj: float, mode: str) -> str:
    parts = f"{base_prob:.6f}|{total_adj:.6f}|{mode}"
    return "sha256:" + hashlib.sha256(parts.encode()).hexdigest()[:16]
