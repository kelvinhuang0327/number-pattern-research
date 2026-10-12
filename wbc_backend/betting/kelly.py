"""
Kelly Criterion Calculator — § 五 投注策略引擎

Provides:
  calculate_kelly_bet(prob, odds)     → optimal Kelly stake
  half_kelly(prob, odds)              → conservative half-Kelly
  fractional_kelly(prob, odds, frac)  → configurable fraction
"""
from __future__ import annotations

import math


def calculate_kelly_bet(prob: float, odds: float) -> float:
    """
    Full Kelly criterion for a single bet.

    f* = (bp - q) / b

    where:
      b = decimal_odds - 1 (net payout)
      p = probability of winning
      q = 1 - p

    Returns
    -------
    float : Optimal fraction of bankroll to wager (0 if negative edge)
    """
    if odds <= 1.0 or prob <= 0 or prob >= 1:
        return 0.0

    b = odds - 1.0
    q = 1.0 - prob

    kelly = (b * prob - q) / b

    return max(0.0, kelly)


def half_kelly(prob: float, odds: float) -> float:
    """Half-Kelly for reduced variance."""
    return calculate_kelly_bet(prob, odds) * 0.5


def fractional_kelly(prob: float, odds: float, fraction: float = 0.25) -> float:
    """
    Fractional Kelly (default 1/4 Kelly for conservative play).

    The fraction parameter controls risk/reward:
      0.25 = Quarter Kelly (conservative)
      0.50 = Half Kelly (moderate)
      1.00 = Full Kelly (aggressive)
    """
    return calculate_kelly_bet(prob, odds) * fraction


def bayesian_kelly(
    prob: float,
    odds: float,
    confidence: float = 0.5,
    base_fraction: float = 0.25
) -> float:
    """
    P2.6 Upgrade: Bayesian Kelly with confidence interval adjustment.

    Adjusts the fractional Kelly stake based on the statistical confidence
    of the prediction. Lower confidence -> sharper stake reduction.
    """
    f_star = calculate_kelly_bet(prob, odds)

    # Square the confidence to penalize low-confidence signals more heavily
    # Confidence 1.0 -> 100% of base_fraction
    # Confidence 0.5 -> 25% of base_fraction
    dynamic_fraction = base_fraction * (confidence ** 2)

    return f_star * dynamic_fraction


def expected_value(prob: float, odds: float) -> float:
    """
    Calculate Expected Value of a bet.

    EV = p * (odds - 1) - q
    """
    if odds <= 1.0:
        return -1.0
    return prob * (odds - 1.0) - (1.0 - prob)


def edge(model_prob: float, implied_prob: float) -> float:
    """Calculate edge over the market."""
    return model_prob - implied_prob


def implied_probability(odds: float) -> float:
    """Convert decimal odds to implied probability."""
    return 1.0 / max(odds, 1.001)


def kelly_growth_rate(prob: float, odds: float, fraction: float = 0.25) -> float:
    """
    Expected log-growth rate of bankroll.

    G = p * log(1 + f*b) + q * log(1 - f)

    where f = fractional Kelly stake
    """
    f = fractional_kelly(prob, odds, fraction)
    if f <= 0 or f >= 1:
        return 0.0

    b = odds - 1.0
    q = 1.0 - prob
    growth = prob * math.log(1 + f * b) + q * math.log(1 - f)
    return growth
