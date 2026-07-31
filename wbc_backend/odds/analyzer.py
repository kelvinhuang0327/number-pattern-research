"""
Odds Analyzer — standardizes odds from multiple sources.
"""
from __future__ import annotations


from wbc_backend.domain.schemas import OddsLine, SimulationSummary


def decimal_to_implied_prob(decimal_odds: float) -> float:
    return 1.0 / max(decimal_odds, 1.001)


def standardize_odds() -> list[OddsLine]:
    """
    Return standardized odds lines from all sources.

    In production: fetches from odds APIs and TSL crawler.
    Here: provides seed data for the pipeline.
    """
    return [
        # ── Money Line ──
        OddsLine("Pinnacle", "ML", "TPE", None, 2.08, "international"),
        OddsLine("Pinnacle", "ML", "AUS", None, 1.80, "international"),
        OddsLine("TSL", "ML", "TPE", None, 2.00, "tsl"),
        OddsLine("TSL", "ML", "AUS", None, 1.76, "tsl"),
        # ── Run Line ──
        OddsLine("Pinnacle", "RL", "TPE", +1.5, 1.72, "international"),
        OddsLine("Pinnacle", "RL", "AUS", -1.5, 2.15, "international"),
        OddsLine("TSL", "RL", "TPE", +1.5, 1.68, "tsl"),
        OddsLine("TSL", "RL", "AUS", -1.5, 2.10, "tsl"),
        # ── Over/Under ──
        OddsLine("Pinnacle", "OU", "Over", 7.5, 1.95, "international"),
        OddsLine("Pinnacle", "OU", "Under", 7.5, 1.90, "international"),
        OddsLine("TSL", "OU", "Over", 7.5, 1.90, "tsl"),
        OddsLine("TSL", "OU", "Under", 7.5, 1.87, "tsl"),
        # ── Odd/Even ──
        OddsLine("TSL", "OE", "Odd", None, 1.90, "tsl"),
        OddsLine("TSL", "OE", "Even", None, 1.90, "tsl"),
        # ── First 5 ──
        OddsLine("Pinnacle", "F5", "TPE", None, 2.50, "international"),
        OddsLine("Pinnacle", "F5", "AUS", None, 1.58, "international"),
        OddsLine("TSL", "F5", "TPE", None, 2.40, "tsl"),
        OddsLine("TSL", "F5", "AUS", None, 1.55, "tsl"),
    ]


def market_probabilities_from_sim(
    home_code: str,
    away_code: str,
    sim_summary: SimulationSummary,
) -> dict[str, float]:
    return {
        f"ML_{home_code}": sim_summary.home_win_prob,
        f"ML_{away_code}": sim_summary.away_win_prob,
        f"RL_{home_code}": sim_summary.home_cover_prob,
        f"RL_{away_code}": sim_summary.away_cover_prob,
        "OU_Over": sim_summary.over_prob,
        "OU_Under": sim_summary.under_prob,
    }
