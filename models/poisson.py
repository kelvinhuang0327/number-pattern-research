"""
Poisson Run Simulation model.

Each team's run production in a game is modelled as a Poisson process.
λ = f(team_offense, opponent_pitching, park_factor, WBC adjustments).
"""
from __future__ import annotations
from typing import Dict, List, Tuple
import math
from data.wbc_data import TeamStats, PitcherStats


LEAGUE_AVG_RPG = 4.50   # baseline runs per game


def _lambda(
    offense: TeamStats,
    opp_sp: PitcherStats,
    opp_bullpen_era: float,
    wbc_variance_adj: float = 0.18,
) -> float:
    """
    Compute expected runs (λ) for a team.
    Blends team offense strength with opposing pitching quality.
    """
    # Offense factor: how much better/worse than average
    off_factor = offense.runs_per_game / LEAGUE_AVG_RPG

    # Pitching suppression: how much the opposing SP suppresses runs
    sp_factor = opp_sp.era / LEAGUE_AVG_RPG  # >1 means bad pitching = more runs

    # Bullpen factor (opposing)
    bp_factor = opp_bullpen_era / LEAGUE_AVG_RPG

    # Weight: SP covers ~60% of game, bullpen 40%
    pitch_factor = 0.60 * sp_factor + 0.40 * bp_factor

    lam = LEAGUE_AVG_RPG * off_factor * pitch_factor

    # WBC variance adjustment: inflate slightly
    lam *= (1.0 + wbc_variance_adj * 0.5)

    return max(0.5, lam)


def _poisson_pmf(k: int, lam: float) -> float:
    """P(X=k) for Poisson(λ)."""
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _poisson_cdf(k: int, lam: float) -> float:
    """P(X ≤ k)."""
    return sum(_poisson_pmf(i, lam) for i in range(k + 1))


def score_distribution(lam: float, max_runs: int = 15) -> List[float]:
    """Return P(X=0), P(X=1), ..., P(X=max_runs)."""
    return [_poisson_pmf(k, lam) for k in range(max_runs + 1)]


def predict(
    away: TeamStats,
    home: TeamStats,
    away_sp: PitcherStats,
    home_sp: PitcherStats,
) -> Tuple[float, float, Dict]:
    """
    Return (away_wp, home_wp, details) using bivariate Poisson.
    """
    lam_away = _lambda(away, home_sp, home.bullpen_era)
    lam_home = _lambda(home, away_sp, away.bullpen_era)

    max_r = 15
    dist_a = score_distribution(lam_away, max_r)
    dist_h = score_distribution(lam_home, max_r)

    # Joint probability matrix (independence assumption)
    away_wp = 0.0
    home_wp = 0.0
    tie_p = 0.0
    for a in range(max_r + 1):
        for h in range(max_r + 1):
            p = dist_a[a] * dist_h[h]
            if a > h:
                away_wp += p
            elif h > a:
                home_wp += p
            else:
                tie_p += p

    # Distribute tie probability proportionally
    total_decisive = away_wp + home_wp
    if total_decisive > 0:
        away_wp += tie_p * (away_wp / total_decisive)
        home_wp += tie_p * (home_wp / total_decisive)
    else:
        away_wp = home_wp = 0.5

    # Top-5 most-likely exact scores
    score_probs: List[Tuple[str, float]] = []
    for a in range(max_r + 1):
        for h in range(max_r + 1):
            score_probs.append((f"{a}-{h}", dist_a[a] * dist_h[h]))
    score_probs.sort(key=lambda x: x[1], reverse=True)

    details = {
        "lambda_away": round(lam_away, 2),
        "lambda_home": round(lam_home, 2),
        "total_runs_mu": round(lam_away + lam_home, 2),
        "top5_scores": score_probs[:5],
        "dist_away": [round(p, 4) for p in dist_a],
        "dist_home": [round(p, 4) for p in dist_h],
    }

    return away_wp, home_wp, details
