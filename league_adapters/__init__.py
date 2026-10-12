"""
League adapters for shared baseball core.

This package provides a thin, explicit league boundary so the shared
core engine can remain league-agnostic while WBC and MLB keep their own
rules, data requirements, and simulation defaults.
"""
from .base import LeagueAdapter, LeagueContext, LeagueRuleSet, LeagueSimulationConfig
from .registry import get_league_adapter, normalize_league_name, register_league_adapter
from .wbc_adapter import WBCLeagueAdapter
from .mlb_adapter import MLBLeagueAdapter

__all__ = [
    "LeagueAdapter",
    "LeagueContext",
    "LeagueRuleSet",
    "LeagueSimulationConfig",
    "WBCLeagueAdapter",
    "MLBLeagueAdapter",
    "get_league_adapter",
    "normalize_league_name",
    "register_league_adapter",
]
