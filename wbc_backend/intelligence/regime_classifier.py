"""
Regime Classifier — market-structure regime detection.

Provides the legacy API expected by decision_engine/bet_selector:
  - MarketRegime
  - RegimeSignals
  - RegimeReport
  - build_signals_from_microstructure(...)
  - classify_market_regime(...)

Also keeps TournamentRegime/RegimeClassifier for older callers.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class MarketRegime(Enum):
    LIQUID_MARKET = "LIQUID_MARKET"
    ILLIQUID_MARKET = "ILLIQUID_MARKET"
    PUBLIC_BIAS = "PUBLIC_BIAS"
    SHARP_DOMINATED = "SHARP_DOMINATED"
    BOOKMAKER_TRAP = "BOOKMAKER_TRAP"


@dataclass
class RegimeSignals:
    liquidity_score: float = 0.50          # 0-1, higher = deeper market
    public_pct: float = 0.50               # 0-1 public money share
    sharp_signal_count: int = 0            # count of sharp/steam confirmations
    hours_to_game: float = 24.0
    trap_warning: bool = False


@dataclass
class RegimeReport:
    regime: MarketRegime = MarketRegime.LIQUID_MARKET
    confidence: float = 0.50
    should_bet: bool = True
    recommended_action: str = "NORMAL_EXECUTION"
    edge_multiplier: float = 1.00


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def build_signals_from_microstructure(
    micro_report: Any,
    public_pct: float,
    hours_to_game: float,
) -> RegimeSignals:
    """
    Build regime signals from a microstructure report object.
    This function is intentionally tolerant to different report shapes.
    """
    liq = getattr(micro_report, "liquidity_score", None)
    if liq is None:
        liq = getattr(micro_report, "overall_liquidity", 0.50)
    trap = bool(getattr(micro_report, "trap_warning", False))
    return RegimeSignals(
        liquidity_score=_clamp01(liq),
        public_pct=_clamp01(public_pct),
        sharp_signal_count=int(getattr(micro_report, "sharp_signal_count", 0)),
        hours_to_game=max(0.0, float(hours_to_game)),
        trap_warning=trap,
    )


def classify_market_regime(signals: RegimeSignals) -> RegimeReport:
    """
    Map market signals to a trading regime.
    """
    # Hard block: trap-like behavior.
    if signals.trap_warning:
        return RegimeReport(
            regime=MarketRegime.BOOKMAKER_TRAP,
            confidence=0.85,
            should_bet=False,
            recommended_action="SKIP_MARKET_TRAP",
            edge_multiplier=0.0,
        )

    # Sharp consensus with low liquidity is dangerous for retail execution.
    if signals.sharp_signal_count >= 2 and signals.liquidity_score < 0.45:
        return RegimeReport(
            regime=MarketRegime.SHARP_DOMINATED,
            confidence=0.78,
            should_bet=False,
            recommended_action="AVOID_SHARP_SIDE",
            edge_multiplier=0.0,
        )

    # Thin market: keep betting enabled but haircut edge.
    if signals.liquidity_score < 0.35:
        return RegimeReport(
            regime=MarketRegime.ILLIQUID_MARKET,
            confidence=0.68,
            should_bet=True,
            recommended_action="REDUCE_SIZE_AND_WAIT_BETTER_PRICE",
            edge_multiplier=0.75,
        )

    # Public-bias window: late market and one-sided public flow.
    if signals.public_pct >= 0.68 and signals.sharp_signal_count == 0:
        return RegimeReport(
            regime=MarketRegime.PUBLIC_BIAS,
            confidence=0.70,
            should_bet=True,
            recommended_action="FADE_PUBLIC_WHEN_EDGE_CONFIRMS",
            edge_multiplier=1.10,
        )

    return RegimeReport(
        regime=MarketRegime.LIQUID_MARKET,
        confidence=0.60,
        should_bet=True,
        recommended_action="NORMAL_EXECUTION",
        edge_multiplier=1.00,
    )


# Backward-compatible tournament classifier API
class TournamentRegime(Enum):
    POOL_PLAY = "pool"
    KNOCKOUT = "knockout"
    EXHIBITION = "exhibition"


class RegimeClassifier:
    @staticmethod
    def classify(round_name: str) -> TournamentRegime:
        round_map = {
            "Pool": TournamentRegime.POOL_PLAY,
            "Quarterfinal": TournamentRegime.KNOCKOUT,
            "Semifinal": TournamentRegime.KNOCKOUT,
            "Final": TournamentRegime.KNOCKOUT,
            "Warmup": TournamentRegime.EXHIBITION,
        }
        return round_map.get(round_name, TournamentRegime.POOL_PLAY)

    @staticmethod
    def get_variance_multiplier(regime: TournamentRegime) -> float:
        if regime == TournamentRegime.KNOCKOUT:
            return 0.85
        return 1.0
