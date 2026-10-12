"""
Elo Rating Model

Uses Elo difference to compute win probabilities.
Includes WBC-specific adjustments for neutral site and roster strength.
"""
from __future__ import annotations

from wbc_backend.domain.schemas import Matchup, SubModelResult


def elo_win_prob(home_elo: float, away_elo: float, home_advantage: float = 30.0) -> float:
    diff = home_elo - away_elo + home_advantage
    return 1.0 / (1.0 + 10 ** (-diff / 400.0))


def predict(matchup: Matchup, home_advantage: float = 30.0) -> SubModelResult:
    ha = 0.0 if matchup.neutral_site else home_advantage
    home_wp = elo_win_prob(matchup.home.elo, matchup.away.elo, ha)
    home_wp = max(0.05, min(0.95, home_wp))

    return SubModelResult(
        model_name="elo",
        home_win_prob=round(home_wp, 4),
        away_win_prob=round(1.0 - home_wp, 4),
        confidence=0.6,
        diagnostics={
            "elo_diff": matchup.home.elo - matchup.away.elo,
            "home_advantage_applied": ha,
        },
    )
