"""
League Configuration — Unified Threshold Management
======================================================
Central registry for league-specific and round-specific threshold
overrides. The Decision Engine and all intelligence modules read
from this configuration instead of hardcoding thresholds.

Why needed:
  WBC 2023 backtest revealed that MLB-calibrated thresholds (65 for
  edge/realism gates) are too strict for WBC's thinner markets and
  fewer sub-models. This module provides a clean, single source of
  truth for all configurable parameters across different contexts.

Usage:
  from wbc_backend.intelligence.league_config import get_league_config

  config = get_league_config("WBC", round_name="Pool A")
  threshold = config.edge_threshold      # 45 for WBC Pool
  realism   = config.realism_threshold   # 45 for WBC
"""
from __future__ import annotations

from dataclasses import dataclass


# ─── Configuration Dataclass ───────────────────────────────────────────────

@dataclass
class LeagueConfig:
    """All tunable parameters for a specific league/round context."""

    # ── Identity ───────────────────────────────────────────────
    league: str = "MLB"
    round_name: str = ""
    description: str = ""

    # ── Phase 1: Edge Validator ────────────────────────────────
    edge_threshold: int = 65          # min edge_score for is_valid
    edge_strong: int = 80
    edge_elite: int = 90

    # ── Phase 1b: Edge Realism Filter ─────────────────────────
    realism_threshold: int = 65       # min real_edge_score

    # ── Phase 4: Bet Selector gates ───────────────────────────
    bet_edge_score_min: int = 70      # gate 1 in bet_selector
    bet_min_viable_edge: float = 0.02 # gate 6: min adjusted edge
    bet_min_odds: float = 1.40
    bet_max_odds: float = 4.50
    bet_min_odds_band_roi: float = 0.0

    # ── Position Sizing ───────────────────────────────────────
    max_single_bet_pct: float = 0.025  # max 2.5% of bankroll
    max_daily_exposure_pct: float = 0.12
    kelly_fraction: float = 0.25

    # ── Risk ──────────────────────────────────────────────────
    max_daily_bets: int = 5
    daily_loss_stop_pct: float = 0.08

    # ── Market ────────────────────────────────────────────────
    default_liquidity: float = 0.50
    default_hours_to_game: float = 12.0
    default_avg_limit: float = 5000.0
    default_vig: float = 0.08

    # ── Band ROI (override for leagues without MLB data) ──────
    band_roi_override: dict[str, float] | None = None


# ─── Predefined Configurations ─────────────────────────────────────────────

# MLB Regular Season (default — most calibrated)
MLB_CONFIG = LeagueConfig(
    league="MLB",
    description="MLB Regular Season — efficient market, many sub-models",
    edge_threshold=65,
    realism_threshold=65,
    bet_edge_score_min=70,
    bet_min_viable_edge=0.02,
    bet_min_odds=1.40,
    bet_max_odds=4.50,
    max_single_bet_pct=0.025,
    max_daily_exposure_pct=0.10,
    max_daily_bets=5,
    default_liquidity=0.70,
    default_avg_limit=8000.0,
)

# WBC Pool Stage
WBC_POOL_CONFIG = LeagueConfig(
    league="WBC",
    round_name="Pool",
    description="WBC Pool rounds — thin market, fewer sub-models",
    edge_threshold=45,
    realism_threshold=45,
    bet_edge_score_min=45,
    bet_min_viable_edge=0.01,
    bet_min_odds=1.20,
    bet_max_odds=6.00,
    bet_min_odds_band_roi=-0.10,
    max_single_bet_pct=0.020,
    max_daily_exposure_pct=0.06,
    max_daily_bets=3,
    kelly_fraction=0.20,
    default_liquidity=0.35,
    default_avg_limit=2500.0,
    default_vig=0.10,
    band_roi_override={
        "1.01-1.50": 0.02, "1.51-1.80": 0.02,
        "1.81-2.10": 0.02, "2.11-2.60": 0.02,
        "2.61-3.50": 0.02, "3.51+": 0.02,
    },
)

# WBC Knockout (QF/SF/Final)
WBC_KO_CONFIG = LeagueConfig(
    league="WBC",
    round_name="KO",
    description="WBC Knockout rounds — better liquidity, higher stakes",
    edge_threshold=42,
    realism_threshold=42,
    bet_edge_score_min=42,
    bet_min_viable_edge=0.01,
    bet_min_odds=1.20,
    bet_max_odds=6.00,
    bet_min_odds_band_roi=-0.10,
    max_single_bet_pct=0.030,
    max_daily_exposure_pct=0.08,
    max_daily_bets=4,
    kelly_fraction=0.25,
    default_liquidity=0.65,
    default_avg_limit=8000.0,
    default_vig=0.08,
    band_roi_override={
        "1.01-1.50": 0.02, "1.51-1.80": 0.02,
        "1.81-2.10": 0.02, "2.11-2.60": 0.02,
        "2.61-3.50": 0.02, "3.51+": 0.02,
    },
)

# NPB (Japanese Baseball)
NPB_CONFIG = LeagueConfig(
    league="NPB",
    description="NPB — limited data, model uncertainty higher",
    edge_threshold=55,
    realism_threshold=55,
    bet_edge_score_min=55,
    bet_min_viable_edge=0.015,
    bet_min_odds=1.50,
    bet_max_odds=3.50,
    max_single_bet_pct=0.015,
    max_daily_exposure_pct=0.04,
    max_daily_bets=3,
    kelly_fraction=0.15,
    default_liquidity=0.40,
    default_avg_limit=3000.0,
)

# KBO (Korean Baseball)
KBO_CONFIG = LeagueConfig(
    league="KBO",
    description="KBO — limited Western book availability",
    edge_threshold=55,
    realism_threshold=55,
    bet_edge_score_min=55,
    bet_min_viable_edge=0.015,
    max_single_bet_pct=0.015,
    max_daily_exposure_pct=0.04,
    default_liquidity=0.35,
    default_avg_limit=2000.0,
)


# ─── Registry ──────────────────────────────────────────────────────────────

_LEAGUE_CONFIGS: dict[str, LeagueConfig] = {
    "MLB": MLB_CONFIG,
    "WBC_POOL": WBC_POOL_CONFIG,
    "WBC_KO": WBC_KO_CONFIG,
    "NPB": NPB_CONFIG,
    "KBO": KBO_CONFIG,
}

# WBC round → config key mapping
_WBC_ROUND_MAP: dict[str, str] = {
    "Pool A": "WBC_POOL",
    "Pool B": "WBC_POOL",
    "Pool C": "WBC_POOL",
    "Pool D": "WBC_POOL",
    "QF": "WBC_KO",
    "SF": "WBC_KO",
    "Final": "WBC_KO",
}


# ─── Public API ─────────────────────────────────────────────────────────────

def get_league_config(
    league: str,
    round_name: str = "",
) -> LeagueConfig:
    """
    Get the configuration for a specific league and round.

    Args:
        league: League identifier ("MLB", "WBC", "NPB", "KBO")
        round_name: Optional round name for WBC ("Pool A", "QF", "Final", etc.)

    Returns:
        LeagueConfig with all tunable parameters.
    """
    # Direct lookup
    key = league.upper()
    if key in _LEAGUE_CONFIGS:
        return _LEAGUE_CONFIGS[key]

    # WBC with round
    if key == "WBC" and round_name:
        mapped = _WBC_ROUND_MAP.get(round_name, "WBC_POOL")
        return _LEAGUE_CONFIGS.get(mapped, WBC_POOL_CONFIG)

    # WBC without round → default to pool
    if key == "WBC":
        return WBC_POOL_CONFIG

    # Unknown league → use MLB defaults
    return MLB_CONFIG


def register_league_config(key: str, config: LeagueConfig) -> None:
    """Register a custom league configuration."""
    _LEAGUE_CONFIGS[key.upper()] = config


def list_leagues() -> list[str]:
    """List all registered league configs."""
    return list(_LEAGUE_CONFIGS.keys())


# ─── Smoke Tests ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from typing import List  # noqa

    print()
    print("=" * 60)
    print("⚙️ League Config — Smoke Tests")
    print("=" * 60)

    # Test 1: MLB defaults
    print("\n━━━ Test 1: MLB defaults ━━━")
    mlb = get_league_config("MLB")
    print(f"  Edge threshold: {mlb.edge_threshold}")
    print(f"  Realism threshold: {mlb.realism_threshold}")
    assert mlb.edge_threshold == 65
    print("  ✅ PASSED")

    # Test 2: WBC Pool
    print("\n━━━ Test 2: WBC Pool ━━━")
    wbc_pool = get_league_config("WBC", "Pool A")
    print(f"  Edge threshold: {wbc_pool.edge_threshold}")
    print(f"  Realism threshold: {wbc_pool.realism_threshold}")
    print(f"  Max bet: {wbc_pool.max_single_bet_pct:.1%}")
    assert wbc_pool.edge_threshold == 45
    assert wbc_pool.band_roi_override is not None
    print("  ✅ PASSED")

    # Test 3: WBC KO
    print("\n━━━ Test 3: WBC Knockout ━━━")
    wbc_ko = get_league_config("WBC", "Final")
    print(f"  Edge threshold: {wbc_ko.edge_threshold}")
    print(f"  Max bet: {wbc_ko.max_single_bet_pct:.1%}")
    assert wbc_ko.edge_threshold == 42
    assert wbc_ko.max_single_bet_pct == 0.030
    print("  ✅ PASSED")

    # Test 4: Unknown league falls back to MLB
    print("\n━━━ Test 4: Unknown league → MLB ━━━")
    unknown = get_league_config("CPBL")
    print(f"  Edge threshold: {unknown.edge_threshold}")
    assert unknown.edge_threshold == 65
    print("  ✅ PASSED")

    # Test 5: List leagues
    print("\n━━━ Test 5: List leagues ━━━")
    leagues = list_leagues()
    print(f"  Available: {leagues}")
    assert "MLB" in leagues
    assert "WBC_POOL" in leagues
    print("  ✅ PASSED")

    print(f"\n{'=' * 60}")
    print("✅ All 5 smoke tests passed")
    print(f"{'=' * 60}")
