"""
Hierarchical Bayesian Team Strength Model (§ P3).

Upgrades the conjugate Normal-Normal model to a hierarchical structure
where team strengths share a common distribution (partial pooling).

If PyMC is available, uses MCMC sampling for full posterior inference.
Otherwise, falls back to analytic conjugate approximation.

Hierarchy:
    μ_global ~ N(4.5, σ_global²)     # global mean run-scoring
    σ_team ~ HalfNormal(1.0)          # between-team variance
    θ_team ~ N(μ_global, σ_team²)     # per-team strength
    y_ij | θ_i ~ N(θ_i, σ_obs²)      # observed runs

This provides better small-sample estimates for WBC (5-7 games)
by borrowing strength across teams (shrinkage toward the global mean).
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from data.wbc_data import TeamStats

# Try importing PyMC; gracefully degrade if not available
try:
    import pymc as pm
    import numpy as np
    import arviz as az
    HAS_PYMC = True
except ImportError:
    HAS_PYMC = False

# Priors
PRIOR_MU = 4.5
PRIOR_SIGMA_GLOBAL = 1.0   # tighter global prior for WBC
OBS_SIGMA = 2.0
N_SAMPLES = 1000
N_TUNE = 500


class HierarchicalBayesian:
    """
    Hierarchical Bayesian model for team strength estimation.

    Maintains a cache of posterior estimates per team, updated
    as new game data arrives.
    """

    def __init__(self):
        self._posteriors: Dict[str, Tuple[float, float]] = {}
        self._observations: Dict[str, List[float]] = {}

    def observe(self, team_code: str, runs_scored: float) -> None:
        """Record an observed game for a team."""
        self._observations.setdefault(team_code, []).append(runs_scored)

    def fit(self, teams: Optional[List[str]] = None) -> Dict[str, Tuple[float, float]]:
        """
        Fit the hierarchical model on all observed data.

        Returns {team_code: (posterior_mu, posterior_sigma)}.
        """
        if not self._observations:
            return {}

        if teams is None:
            teams = list(self._observations.keys())

        if HAS_PYMC:
            return self._fit_pymc(teams)
        return self._fit_conjugate(teams)

    def _fit_pymc(self, teams: List[str]) -> Dict[str, Tuple[float, float]]:
        """Full MCMC hierarchical model via PyMC."""
        team_idx_map = {t: i for i, t in enumerate(teams)}
        n_teams = len(teams)

        # Flatten observations
        obs_list = []
        idx_list = []
        for team in teams:
            for r in self._observations.get(team, []):
                obs_list.append(r)
                idx_list.append(team_idx_map[team])

        if not obs_list:
            return {}

        obs_arr = np.array(obs_list, dtype=np.float64)
        idx_arr = np.array(idx_list, dtype=np.int32)

        with pm.Model():
            # Hyperpriors
            mu_global = pm.Normal("mu_global", mu=PRIOR_MU, sigma=PRIOR_SIGMA_GLOBAL)
            sigma_team = pm.HalfNormal("sigma_team", sigma=1.0)

            # Per-team strengths
            theta = pm.Normal("theta", mu=mu_global, sigma=sigma_team, shape=n_teams)

            # Likelihood
            pm.Normal("obs", mu=theta[idx_arr], sigma=OBS_SIGMA, observed=obs_arr)

            # Sample
            trace = pm.sample(
                N_SAMPLES, tune=N_TUNE,
                cores=1, return_inferencedata=True,
                progressbar=False,
            )

        # Extract posteriors
        theta_samples = trace.posterior["theta"].values.reshape(-1, n_teams)
        results = {}
        for team in teams:
            i = team_idx_map[team]
            mu = float(np.mean(theta_samples[:, i]))
            sigma = float(np.std(theta_samples[:, i]))
            results[team] = (round(mu, 4), round(sigma, 4))
            self._posteriors[team] = results[team]

        return results

    def _fit_conjugate(self, teams: List[str]) -> Dict[str, Tuple[float, float]]:
        """
        Analytic conjugate approximation with empirical Bayes shrinkage.

        Estimates σ_team from data, then computes per-team posteriors
        with appropriate shrinkage toward the global mean.
        """
        # Compute per-team means
        team_means = {}
        team_ns = {}
        for team in teams:
            obs = self._observations.get(team, [])
            if obs:
                team_means[team] = sum(obs) / len(obs)
                team_ns[team] = len(obs)
            else:
                team_means[team] = PRIOR_MU
                team_ns[team] = 0

        # Estimate between-team variance (empirical Bayes)
        if len(team_means) > 1:
            grand_mean = sum(team_means.values()) / len(team_means)
            var_between = sum(
                (m - grand_mean) ** 2 for m in team_means.values()
            ) / (len(team_means) - 1)
            sigma_team_est = max(0.3, math.sqrt(max(0, var_between - OBS_SIGMA**2 / 6)))
        else:
            sigma_team_est = PRIOR_SIGMA_GLOBAL

        results = {}
        for team in teams:
            n = team_ns[team]
            obs_mean = team_means[team]

            tau_prior = 1.0 / (sigma_team_est ** 2)
            tau_obs = 1.0 / (OBS_SIGMA ** 2)
            tau_post = tau_prior + n * tau_obs

            mu_post = (tau_prior * PRIOR_MU + n * tau_obs * obs_mean) / tau_post
            sigma_post = math.sqrt(1.0 / tau_post)

            results[team] = (round(mu_post, 4), round(sigma_post, 4))
            self._posteriors[team] = results[team]

        return results

    def predict(
        self,
        away: TeamStats,
        home: TeamStats,
    ) -> Tuple[float, float, Dict]:
        """
        Predict win probabilities using hierarchical posteriors.

        Falls back to single-team conjugate if no hierarchical fit available.
        """
        away_off = self._posteriors.get(
            away.code,
            self._single_team_posterior(away.runs_per_game),
        )
        home_off = self._posteriors.get(
            home.code,
            self._single_team_posterior(home.runs_per_game),
        )
        away_def = self._posteriors.get(
            f"{away.code}_def",
            self._single_team_posterior(away.runs_allowed_per_game),
        )
        home_def = self._posteriors.get(
            f"{home.code}_def",
            self._single_team_posterior(home.runs_allowed_per_game),
        )

        # Expected runs
        away_runs_mu = (away_off[0] + home_def[0]) / 2.0
        home_runs_mu = (home_off[0] + away_def[0]) / 2.0

        away_runs_sig = math.sqrt(away_off[1]**2 + home_def[1]**2)
        home_runs_sig = math.sqrt(home_off[1]**2 + away_def[1]**2)

        # Difference distribution
        diff_mu = away_runs_mu - home_runs_mu
        diff_sig = math.sqrt(away_runs_sig**2 + home_runs_sig**2)

        z = diff_mu / diff_sig if diff_sig > 0 else 0.0
        away_wp = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        home_wp = 1.0 - away_wp

        details = {
            "hierarchical": HAS_PYMC,
            "away_runs_mu": round(away_runs_mu, 3),
            "home_runs_mu": round(home_runs_mu, 3),
            "diff_mu": round(diff_mu, 3),
            "diff_sig": round(diff_sig, 3),
            "shrinkage_strength": "full" if HAS_PYMC else "conjugate",
        }

        return away_wp, home_wp, details

    @staticmethod
    def _single_team_posterior(observed_mean: float) -> Tuple[float, float]:
        """Fallback: single-team conjugate posterior."""
        tau_prior = 1.0 / (PRIOR_SIGMA_GLOBAL ** 2)
        tau_obs = 1.0 / (OBS_SIGMA ** 2)
        n = 6
        tau_post = tau_prior + n * tau_obs
        mu_post = (tau_prior * PRIOR_MU + n * tau_obs * observed_mean) / tau_post
        sigma_post = math.sqrt(1.0 / tau_post)
        return (round(mu_post, 4), round(sigma_post, 4))
