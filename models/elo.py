"""
Elo Rating model for WBC team strength estimation.
"""
from __future__ import annotations
from typing import Tuple
from data.wbc_data import TeamStats


# Standard Elo parameters tuned for international baseball
K_FACTOR = 32
HOME_ADVANTAGE = 24        # reduced for neutral-site WBC games
NEUTRAL_SITE_ADJ = 0.0    # no home-field edge at neutral site


def expected_score(rating_a: float, rating_b: float) -> float:
    """Return expected win probability for team A."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def predict(
    away: TeamStats,
    home: TeamStats,
    neutral: bool = True,
) -> Tuple[float, float]:
    """
    Return (away_win_prob, home_win_prob) based on Elo ratings.
    """
    adj = 0.0 if neutral else HOME_ADVANTAGE
    home_elo = home.elo + adj
    away_elo = away.elo

    home_wp = expected_score(home_elo, away_elo)
    away_wp = 1.0 - home_wp

    return away_wp, home_wp


def update_elo(
    winner_elo: float,
    loser_elo: float,
    margin: int = 1,
) -> Tuple[float, float]:
    """Return updated (winner_elo, loser_elo) after a game."""
    # Margin-of-victory multiplier
    mov_mult = max(1.0, ((margin + 1) ** 0.8) / (1 + 0.006 * abs(winner_elo - loser_elo)))
    exp_w = expected_score(winner_elo, loser_elo)
    delta = K_FACTOR * mov_mult * (1.0 - exp_w)
    return winner_elo + delta, loser_elo - delta
