"""Bankroll and exposure control analysis for lottery portfolios."""

from __future__ import annotations

import math
from typing import Dict


def _fractional_kelly(win_prob: float, payout_multiple: float, fraction: float = 0.25) -> float:
    if payout_multiple <= 0:
        return 0.0
    raw = (win_prob * payout_multiple - (1.0 - win_prob)) / payout_multiple
    return max(0.0, raw) * fraction


def analyze_bankroll(
    strategy_name: str,
    expected_profit_per_draw: float,
    variance: float,
    payout_per_hit: float,
    total_ticket_cost: float,
    initial_bankroll: float = 100_000.0,
) -> Dict:
    vol = math.sqrt(max(variance, 1e-9))
    pseudo_win_prob = min(0.95, max(0.001, 0.5 + expected_profit_per_draw / max(2.0 * total_ticket_cost, 1.0)))
    payout_multiple = max(0.1, payout_per_hit / max(total_ticket_cost, 1.0))
    fractional_kelly = _fractional_kelly(pseudo_win_prob, payout_multiple)
    fixed_bet = min(total_ticket_cost, initial_bankroll * 0.01)
    capped_exposure = min(total_ticket_cost, initial_bankroll * 0.02)
    loss_streak_cap = min(total_ticket_cost, initial_bankroll * 0.005 if expected_profit_per_draw < 0 else initial_bankroll * 0.015)

    if expected_profit_per_draw <= 0:
        optimal_bet_size = min(fixed_bet, loss_streak_cap)
        recommendation = 'defensive_fixed'
    else:
        optimal_bet_size = min(
            max(fixed_bet, initial_bankroll * fractional_kelly),
            capped_exposure,
        )
        recommendation = 'fractional_kelly_capped'

    ruin_score = min(1.0, max(0.0, (vol - expected_profit_per_draw) / max(initial_bankroll * 0.02, 1.0)))
    survival = 1.0 - ruin_score

    return {
        'strategy': strategy_name,
        'initial_bankroll': initial_bankroll,
        'fixed_bet_size': round(fixed_bet, 2),
        'fractional_kelly_size': round(initial_bankroll * fractional_kelly, 2),
        'capped_exposure_size': round(capped_exposure, 2),
        'loss_streak_control_size': round(loss_streak_cap, 2),
        'optimal_bet_size': round(optimal_bet_size, 2),
        'risk_of_ruin': round(ruin_score, 4),
        'survival_probability': round(survival, 4),
        'adjusted_recommendation': recommendation,
    }
