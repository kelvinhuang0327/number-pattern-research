"""
Game Context Adapters — WBC vs MLB (§ P2).

Provides `WBCAdapter` and `MLBAdapter` that encapsulate
scenario-specific configuration and adjustments.

Usage:
    from models.adapters import get_adapter
    adapter = get_adapter(match)  # auto-selects WBC or MLB
    config = adapter.get_config()
    adjusted_lam = adapter.adjust_run_expectancy(base_lam, inning, context)
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class AdapterConfig:
    """Shared configuration output from adapters."""
    # Monte Carlo
    mc_simulations: int = 10_000
    # Elo
    home_field_advantage: float = 0.035
    elo_k_factor: float = 20.0
    # Bayesian prior shrinkage
    prior_sigma: float = 1.2
    # Kelly
    kelly_fraction: float = 0.25
    max_single_bet_pct: float = 0.015
    # Bullpen
    bullpen_weight: float = 0.30
    sp_expected_innings: float = 6.0
    # Roster
    cohesion_discount: float = 0.0  # team chemistry penalty
    # Market
    market_efficiency: float = 0.95  # 0=inefficient, 1=fully efficient


class BaseAdapter(ABC):
    """Base adapter interface."""

    @abstractmethod
    def get_config(self) -> AdapterConfig:
        ...

    @abstractmethod
    def adjust_run_expectancy(
        self, base_lam: float, inning: int, context: Dict,
    ) -> float:
        ...

    @abstractmethod
    def adjust_elo(
        self, raw_elo: float, team_code: str, context: Dict,
    ) -> float:
        ...

    @abstractmethod
    def bullpen_transition_inning(self, pitch_count_limit: int) -> float:
        """Expected inning when SP exits."""
        ...


class WBCAdapter(BaseAdapter):
    """
    WBC-specific adjustments:
    - Pitch count limits → early SP exit
    - Neutral site → zero HFA
    - Stronger Bayesian shrinkage (small sample)
    - Cohesion discount for national teams
    - Lower market efficiency → bigger edges
    """

    WBC_PITCH_LIMITS = {"Pool": 65, "2ndRound": 80, "Semi": 95, "Final": 95}

    def __init__(self, round_name: str = "Pool"):
        self.round_name = round_name
        self._pitch_limit = self.WBC_PITCH_LIMITS.get(round_name, 65)

    def get_config(self) -> AdapterConfig:
        sp_innings = self.bullpen_transition_inning(self._pitch_limit)
        return AdapterConfig(
            mc_simulations=10_000,
            home_field_advantage=0.0,  # neutral site
            elo_k_factor=32.0,  # faster learning, small sample
            prior_sigma=0.8,   # tighter prior (shrink to mean)
            kelly_fraction=0.15,
            max_single_bet_pct=0.015,
            bullpen_weight=0.60,  # bullpen dominates WBC
            sp_expected_innings=sp_innings,
            cohesion_discount=0.05,  # national team chemistry penalty
            market_efficiency=0.80,  # WBC markets are thin
        )

    def adjust_run_expectancy(
        self, base_lam: float, inning: int, context: Dict,
    ) -> float:
        sp_limit = self.bullpen_transition_inning(self._pitch_limit)
        per_inning = base_lam / 9.0

        if inning > sp_limit:
            # Bullpen phase — use bullpen ERA ratio
            bp_era = context.get("bullpen_era", 4.5)
            per_inning *= (bp_era / 4.5) * 1.05
        else:
            # SP phase with fatigue curve
            fatigue = context.get("sp_fatigue", 0.0)
            per_inning *= 1.0 + fatigue * max(0, inning - 2) * 0.04

        return max(0.05, per_inning)

    def adjust_elo(
        self, raw_elo: float, team_code: str, context: Dict,
    ) -> float:
        # No home field advantage in WBC
        # Apply roster strength modifier
        rsi = context.get("roster_strength_index", 100)
        rsi_adj = (rsi - 75) * 2.0  # RSI 75→0, RSI 100→+50 Elo
        return raw_elo + rsi_adj

    def bullpen_transition_inning(self, pitch_limit: int) -> float:
        # Approx 16 pitches/inning
        return min(6.0, pitch_limit / 16.0)


class MLBAdapter(BaseAdapter):
    """
    MLB regular season adjustments:
    - No pitch count limits
    - Standard HFA
    - Larger sample → wider priors OK
    - Efficient market
    """

    def get_config(self) -> AdapterConfig:
        return AdapterConfig(
            mc_simulations=50_000,
            home_field_advantage=0.035,
            elo_k_factor=20.0,
            prior_sigma=1.2,
            kelly_fraction=0.25,
            max_single_bet_pct=0.04,
            bullpen_weight=0.30,
            sp_expected_innings=6.0,
            cohesion_discount=0.0,
            market_efficiency=0.95,
        )

    def adjust_run_expectancy(
        self, base_lam: float, inning: int, context: Dict,
    ) -> float:
        per_inning = base_lam / 9.0
        if inning > 6:
            bp_era = context.get("bullpen_era", 4.0)
            per_inning *= bp_era / 4.0
        else:
            fatigue = context.get("sp_fatigue", 0.0)
            per_inning *= 1.0 + fatigue * max(0, inning - 4) * 0.02
        return max(0.05, per_inning)

    def adjust_elo(
        self, raw_elo: float, team_code: str, context: Dict,
    ) -> float:
        is_home = context.get("is_home", False)
        hfa = 24.0 if is_home else 0.0  # ~24 Elo points = 3.5% WP
        return raw_elo + hfa

    def bullpen_transition_inning(self, pitch_limit: int = 100) -> float:
        return 6.0


def get_adapter(match) -> BaseAdapter:
    """Auto-select adapter based on match game_type."""
    game_type = getattr(match, "game_type", "INTERNATIONAL")
    if game_type == "PROFESSIONAL":
        return MLBAdapter()
    round_name = getattr(match, "round_name", "Pool")
    return WBCAdapter(round_name=round_name)
