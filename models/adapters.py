"""
Legacy game-context adapters.

This module is kept for backward compatibility and now delegates to the
new `league_adapters` package so WBC behavior is preserved while MLB can
join the same architecture without duplication.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from league_adapters.base import LeagueAdapter as BaseAdapter
from league_adapters.base import LeagueContext
from league_adapters.mlb_adapter import MLBLeagueAdapter
from league_adapters.registry import get_league_adapter
from league_adapters.wbc_adapter import WBCLeagueAdapter


@dataclass(frozen=True)
class AdapterConfig:
    mc_simulations: int
    home_field_advantage: float
    elo_k_factor: float
    prior_sigma: float
    kelly_fraction: float
    max_single_bet_pct: float
    bullpen_weight: float
    sp_expected_innings: float
    cohesion_discount: float
    market_efficiency: float


WBCAdapter = WBCLeagueAdapter
MLBAdapter = MLBLeagueAdapter


def get_adapter(match) -> BaseAdapter:
    game_type = getattr(match, "game_type", "INTERNATIONAL")
    league = "MLB" if game_type == "PROFESSIONAL" else "WBC"
    round_name = getattr(match, "round_name", "Pool")
    return get_league_adapter(league if league == "MLB" else "WBC")
