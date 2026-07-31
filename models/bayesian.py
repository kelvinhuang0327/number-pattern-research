"""
Bayesian Team Strength model.

Uses conjugate-prior Normal–Normal model:
  θ_team ~ N(μ_prior, σ²_prior)
  observed_runs ~ N(θ_team, σ²_obs)

Posterior → analytic update.
"""
from __future__ import annotations
from typing import Tuple
import math
from data.wbc_data import TeamStats


# Priors (calibrated to WBC-level international baseball)
PRIOR_MU = 4.5         # average runs per game
PRIOR_SIGMA = 1.2      # prior uncertainty
OBS_SIGMA = 2.0        # game-to-game variance


def _team_strength(team: TeamStats) -> Tuple[float, float]:
    """
    Return posterior (mu, sigma) for a team's run-scoring ability.
    Uses runs_per_game as the observed mean, with a shrinkage prior.
    """
    tau_prior = 1.0 / (PRIOR_SIGMA ** 2)
    tau_obs = 1.0 / (OBS_SIGMA ** 2)
    # Assume ~6 observed "games" worth of data for the tournament so far
    n_games = 6
    tau_post = tau_prior + n_games * tau_obs
    mu_post = (tau_prior * PRIOR_MU + n_games * tau_obs * team.runs_per_game) / tau_post
    sigma_post = math.sqrt(1.0 / tau_post)
    return mu_post, sigma_post


def _team_defense(team: TeamStats) -> Tuple[float, float]:
    """Posterior for runs-allowed."""
    tau_prior = 1.0 / (PRIOR_SIGMA ** 2)
    tau_obs = 1.0 / (OBS_SIGMA ** 2)
    n_games = 6
    tau_post = tau_prior + n_games * tau_obs
    mu_post = (tau_prior * PRIOR_MU + n_games * tau_obs * team.runs_allowed_per_game) / tau_post
    sigma_post = math.sqrt(1.0 / tau_post)
    return mu_post, sigma_post


def predict(
    away: TeamStats,
    home: TeamStats,
) -> Tuple[float, float, dict]:
    """
    Return (away_wp, home_wp, details).
    Uses the difference of Normal distributions for run differential.
    """
    # Offense posteriors
    off_a_mu, off_a_sig = _team_strength(away)
    off_h_mu, off_h_sig = _team_strength(home)

    # Defense posteriors
    def_a_mu, def_a_sig = _team_defense(away)
    def_h_mu, def_h_sig = _team_defense(home)

    # Expected runs for each team:
    #   away scores ~ off_away vs def_home
    #   home scores ~ off_home vs def_away
    away_runs_mu = (off_a_mu + def_h_mu) / 2.0
    home_runs_mu = (off_h_mu + def_a_mu) / 2.0

    # Combined variance
    away_runs_sig = math.sqrt(off_a_sig**2 + def_h_sig**2)
    home_runs_sig = math.sqrt(off_h_sig**2 + def_a_sig**2)

    # Difference distribution (away − home)
    diff_mu = away_runs_mu - home_runs_mu
    diff_sig = math.sqrt(away_runs_sig**2 + home_runs_sig**2)

    # P(away wins) = P(diff > 0)
    z = diff_mu / diff_sig if diff_sig > 0 else 0.0
    away_wp = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    home_wp = 1.0 - away_wp

    details = {
        "away_runs_mu": round(away_runs_mu, 2),
        "home_runs_mu": round(home_runs_mu, 2),
        "diff_mu": round(diff_mu, 2),
        "diff_sig": round(diff_sig, 2),
    }

    return away_wp, home_wp, details
