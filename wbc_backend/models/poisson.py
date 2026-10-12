"""
Poisson Scoring Model

Uses expected runs per game (Poisson-distributed) to estimate
win probabilities and score distributions.
"""
from __future__ import annotations


import numpy as np
from scipy.stats import poisson

from wbc_backend.domain.schemas import Matchup, SubModelResult


def expected_runs(
    off_woba: float,
    off_ops_plus: float,
    opp_fip: float,
    opp_whip: float,
    opp_der: float,
    rpg: float = 4.5,
) -> float:
    """Estimate runs/game from offensive and pitching metrics."""
    offense = (off_woba - 0.310) * 12.0 + (off_ops_plus - 100) / 25.0
    defense = (opp_fip - 3.8) * 0.7 + (opp_whip - 1.25) * 1.4 - (opp_der - 0.700) * 4.0
    return max(1.5, rpg + offense - defense)


def poisson_win_prob(lambda_home: float, lambda_away: float, max_runs: int = 15) -> float:
    """Home win probability via Poisson distribution convolution."""
    r = np.arange(max_runs + 1)
    ph = poisson.pmf(r, lambda_home)
    pa = poisson.pmf(r, lambda_away)

    home_win = 0.0
    draw = 0.0
    for h in range(max_runs + 1):
        for a in range(max_runs + 1):
            prob = ph[h] * pa[a]
            if h > a:
                home_win += prob
            elif h == a:
                draw += prob

    # Split draws equally (baseball has no ties normally, but for model comparison)
    return home_win + draw * 0.5


def score_distribution(lambda_home: float, lambda_away: float, max_runs: int = 12) -> dict:
    """Return most likely score outcomes."""
    r = np.arange(max_runs + 1)
    ph = poisson.pmf(r, lambda_home)
    pa = poisson.pmf(r, lambda_away)

    scores = {}
    for h in range(max_runs + 1):
        for a in range(max_runs + 1):
            prob = ph[h] * pa[a]
            if prob > 0.005:
                scores[f"{h}-{a}"] = round(float(prob), 4)

    return dict(sorted(scores.items(), key=lambda x: -x[1])[:10])


def predict(matchup: Matchup) -> SubModelResult:
    lam_home = expected_runs(
        matchup.home.batting_woba, matchup.home.batting_ops_plus,
        matchup.away.pitching_fip, matchup.away.pitching_whip, matchup.away.der,
        matchup.home.runs_per_game,
    )
    lam_away = expected_runs(
        matchup.away.batting_woba, matchup.away.batting_ops_plus,
        matchup.home.pitching_fip, matchup.home.pitching_whip, matchup.home.der,
        matchup.away.runs_per_game,
    )

    home_wp = poisson_win_prob(lam_home, lam_away)
    home_wp = max(0.05, min(0.95, home_wp))

    return SubModelResult(
        model_name="poisson",
        home_win_prob=round(home_wp, 4),
        away_win_prob=round(1.0 - home_wp, 4),
        expected_home_runs=round(lam_home, 2),
        expected_away_runs=round(lam_away, 2),
        confidence=0.65,
        diagnostics={
            "lambda_home": round(lam_home, 3),
            "lambda_away": round(lam_away, 3),
        },
    )
