"""
TSL Market Taxonomy + Schema Pack.

Defines all Taiwan Sports Lottery (TSL) market types supported by this system.
v1: only MONEYLINE_HOME_AWAY is paper-implemented.

PAPER_ONLY=True
production_ready=False
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

PAPER_ONLY: bool = True
PRODUCTION_READY: bool = False


class TSLMarketType(str, Enum):
    MONEYLINE_HOME_AWAY = "moneyline_home_away"
    RUN_LINE_HANDICAP = "run_line_handicap"          # 讓分
    TOTALS_OVER_UNDER = "totals_over_under"           # 大小分
    FIRST_FIVE_INNINGS_MONEYLINE = "first_five_innings_moneyline"
    FIRST_FIVE_INNINGS_TOTALS = "first_five_innings_totals"
    ODD_EVEN_TOTAL_RUNS = "odd_even_total_runs"
    TEAM_TOTAL_HOME = "team_total_home"
    TEAM_TOTAL_AWAY = "team_total_away"


@dataclass(frozen=True)
class MarketContract:
    market_type: TSLMarketType
    label_fields: tuple[str, ...]       # y_true columns needed for settlement
    odds_fields: tuple[str, ...]        # odds columns needed for CLV / EV
    settlement_semantics: str           # human-readable win/loss rule
    supports_push_tie: bool
    is_paper_implemented: bool          # v1: only MONEYLINE_HOME_AWAY = True
    paper_only: bool = True             # always True in this phase
    production_ready: bool = False      # always False in this phase


_REGISTRY: dict[TSLMarketType, MarketContract] = {
    TSLMarketType.MONEYLINE_HOME_AWAY: MarketContract(
        market_type=TSLMarketType.MONEYLINE_HOME_AWAY,
        label_fields=("y_true_home_win",),
        odds_fields=("odds_home_ml", "odds_away_ml"),
        settlement_semantics=(
            "Win if selected team wins after 9 innings (or regulation). "
            "No push — extra innings count."
        ),
        supports_push_tie=False,
        is_paper_implemented=True,
        paper_only=True,
        production_ready=False,
    ),
    TSLMarketType.RUN_LINE_HANDICAP: MarketContract(
        market_type=TSLMarketType.RUN_LINE_HANDICAP,
        label_fields=("y_true_home_win", "run_diff", "handicap_value"),
        odds_fields=("odds_rl_home", "odds_rl_away", "handicap_value"),
        settlement_semantics=(
            "Home team must win by more than handicap_value runs (typically 1.5). "
            "If home wins by exactly handicap_value and it is a whole number, push applies."
        ),
        supports_push_tie=True,
        is_paper_implemented=False,
        paper_only=True,
        production_ready=False,
    ),
    TSLMarketType.TOTALS_OVER_UNDER: MarketContract(
        market_type=TSLMarketType.TOTALS_OVER_UNDER,
        label_fields=("total_runs", "line_value"),
        odds_fields=("odds_over", "odds_under", "line_value"),
        settlement_semantics=(
            "Over wins if total runs scored exceeds line_value. "
            "Under wins if total runs < line_value. "
            "Push if total == line_value and line_value is a whole number."
        ),
        supports_push_tie=True,
        is_paper_implemented=False,
        paper_only=True,
        production_ready=False,
    ),
    TSLMarketType.FIRST_FIVE_INNINGS_MONEYLINE: MarketContract(
        market_type=TSLMarketType.FIRST_FIVE_INNINGS_MONEYLINE,
        label_fields=("y_true_home_win_f5", "home_score_f5", "away_score_f5"),
        odds_fields=("odds_f5_home_ml", "odds_f5_away_ml"),
        settlement_semantics=(
            "Win if selected team leads after exactly 5 innings. "
            "Push if scores are tied after 5 innings."
        ),
        supports_push_tie=True,
        is_paper_implemented=False,
        paper_only=True,
        production_ready=False,
    ),
    TSLMarketType.FIRST_FIVE_INNINGS_TOTALS: MarketContract(
        market_type=TSLMarketType.FIRST_FIVE_INNINGS_TOTALS,
        label_fields=("total_runs_f5", "line_value_f5"),
        odds_fields=("odds_f5_over", "odds_f5_under", "line_value_f5"),
        settlement_semantics=(
            "Over wins if combined runs after 5 innings exceeds line_value_f5. "
            "Push if equal to line_value_f5 and it is a whole number."
        ),
        supports_push_tie=True,
        is_paper_implemented=False,
        paper_only=True,
        production_ready=False,
    ),
    TSLMarketType.ODD_EVEN_TOTAL_RUNS: MarketContract(
        market_type=TSLMarketType.ODD_EVEN_TOTAL_RUNS,
        label_fields=("total_runs",),
        odds_fields=("odds_odd", "odds_even"),
        settlement_semantics=(
            "Odd wins if total runs for the game is an odd number. "
            "Even wins if total runs is an even number. No push possible."
        ),
        supports_push_tie=False,
        is_paper_implemented=False,
        paper_only=True,
        production_ready=False,
    ),
    TSLMarketType.TEAM_TOTAL_HOME: MarketContract(
        market_type=TSLMarketType.TEAM_TOTAL_HOME,
        label_fields=("home_score", "team_total_line_home"),
        odds_fields=("odds_tt_home_over", "odds_tt_home_under", "team_total_line_home"),
        settlement_semantics=(
            "Over wins if home team's runs scored exceed team_total_line_home. "
            "Push if equal and line is a whole number."
        ),
        supports_push_tie=True,
        is_paper_implemented=False,
        paper_only=True,
        production_ready=False,
    ),
    TSLMarketType.TEAM_TOTAL_AWAY: MarketContract(
        market_type=TSLMarketType.TEAM_TOTAL_AWAY,
        label_fields=("away_score", "team_total_line_away"),
        odds_fields=("odds_tt_away_over", "odds_tt_away_under", "team_total_line_away"),
        settlement_semantics=(
            "Over wins if away team's runs scored exceed team_total_line_away. "
            "Push if equal and line is a whole number."
        ),
        supports_push_tie=True,
        is_paper_implemented=False,
        paper_only=True,
        production_ready=False,
    ),
}


def get_market_contract(market_type: TSLMarketType) -> MarketContract:
    """Return the frozen MarketContract for a given market type."""
    try:
        return _REGISTRY[market_type]
    except KeyError:
        raise KeyError(f"No contract registered for market type: {market_type!r}")


def list_implemented_markets() -> list[TSLMarketType]:
    """Return list of markets where is_paper_implemented=True (v1: moneyline only)."""
    return [mt for mt, contract in _REGISTRY.items() if contract.is_paper_implemented]


def describe_market_for_audit(market_type: TSLMarketType) -> dict[str, Any]:
    """Return a JSON-serializable dict for inclusion in recommendation row metadata."""
    contract = get_market_contract(market_type)
    return {
        "market_type": contract.market_type.value,
        "label_fields": list(contract.label_fields),
        "odds_fields": list(contract.odds_fields),
        "settlement_semantics": contract.settlement_semantics,
        "supports_push_tie": contract.supports_push_tie,
        "is_paper_implemented": contract.is_paper_implemented,
        "paper_only": contract.paper_only,
        "production_ready": contract.production_ready,
    }
