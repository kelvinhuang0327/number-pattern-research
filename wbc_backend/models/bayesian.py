"""
Bayesian Win Probability Model

Uses hierarchical empirical-Bayes priors to estimate win probability
with uncertainty quantification.
"""
from __future__ import annotations

import math
from wbc_backend.domain.schemas import Matchup, SubModelResult


ROUND_PRIOR_STRENGTH = {
    "POOL": 28.0,
    "QUARTER": 22.0,
    "SEMI": 18.0,
    "FINAL": 16.0,
}


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _round_prior_strength(round_name: str) -> float:
    round_key = (round_name or "POOL").upper()
    for token, weight in ROUND_PRIOR_STRENGTH.items():
        if token in round_key:
            return weight
    return ROUND_PRIOR_STRENGTH["POOL"]


def _team_observed_strength(team) -> float:
    offense = (
        (team.batting_woba - 0.320) * 420.0
        + (team.batting_ops_plus - 100.0) * 0.35
        + (team.runs_per_game - 4.5) * 11.0
    )
    prevention = (
        -(team.pitching_fip - 3.90) * 16.0
        -(team.pitching_whip - 1.25) * 55.0
        + (team.pitching_stuff_plus - 100.0) * 0.20
        + (team.der - 0.700) * 350.0
    )
    depth = (team.bullpen_depth - 8.0) * 1.8
    roster = (team.roster_strength_index - 80.0) * 0.12 + team.top50_stars * 0.9
    return offense + prevention + depth + roster


def _team_hierarchical_strength(team, round_name: str) -> tuple[float, float]:
    prior_strength = max(12.0, team.league_prior_strength + _round_prior_strength(round_name))
    sample = max(1.0, float(team.sample_size))
    shrink = sample / (sample + prior_strength)

    elo_component = (team.elo - 1500.0) / 18.0
    observed = _team_observed_strength(team)
    prior_mean = elo_component + team.league_prior_strength * 0.08
    posterior = prior_mean + shrink * (observed - prior_mean)
    return posterior, shrink


def hierarchical_bayesian_win_prob(matchup: Matchup) -> tuple[float, float, dict]:
    """
    Returns (home_win_prob, confidence, diagnostics).

    Hierarchical runtime:
    1. Build latent team strength from offense/prevention/depth
    2. Shrink toward round-aware prior using effective sample size
    3. Convert prior strength differential into a Beta prior
    4. Update with short-horizon observed evidence (form + run production)
    """
    home_strength, home_shrink = _team_hierarchical_strength(matchup.home, matchup.round_name)
    away_strength, away_shrink = _team_hierarchical_strength(matchup.away, matchup.round_name)

    home_field = 0.75 if not matchup.neutral_site else 0.0
    prior_logit = (home_strength - away_strength + home_field) / 9.5
    prior_prob = max(0.03, min(0.97, _sigmoid(prior_logit)))

    prior_strength = _round_prior_strength(matchup.round_name) + (
        matchup.home.league_prior_strength + matchup.away.league_prior_strength
    ) * 0.25
    alpha_prior = max(1.0, prior_prob * prior_strength)
    beta_prior = max(1.0, (1.0 - prior_prob) * prior_strength)

    form_signal = 0.5 + (matchup.home.win_pct_last_10 - matchup.away.win_pct_last_10) * 0.5
    run_signal = _sigmoid((matchup.home.runs_per_game - matchup.away.runs_per_game) * 0.75)
    woba_signal = _sigmoid((matchup.home.batting_woba - matchup.away.batting_woba) * 18.0)
    observed_home_rate = max(
        0.03,
        min(0.97, 0.45 * form_signal + 0.35 * run_signal + 0.20 * woba_signal),
    )

    evidence_n = max(8.0, min(float(matchup.home.sample_size), float(matchup.away.sample_size), 48.0))
    alpha_post = alpha_prior + observed_home_rate * evidence_n
    beta_post = beta_prior + (1.0 - observed_home_rate) * evidence_n
    posterior_mean = alpha_post / (alpha_post + beta_post)

    total_n = alpha_post + beta_post
    confidence = min(1.0, 0.30 + total_n / 110.0)
    diagnostics = {
        "prior_home": round(prior_prob, 4),
        "posterior_home": round(posterior_mean, 4),
        "home_shrink": round(home_shrink, 4),
        "away_shrink": round(away_shrink, 4),
        "prior_strength": round(prior_strength, 4),
        "evidence_n": round(evidence_n, 4),
    }

    return max(0.05, min(0.95, posterior_mean)), confidence, diagnostics


def predict(matchup: Matchup) -> SubModelResult:
    home_wp, conf, diagnostics = hierarchical_bayesian_win_prob(matchup)

    return SubModelResult(
        model_name="bayesian",
        home_win_prob=round(home_wp, 4),
        away_win_prob=round(1.0 - home_wp, 4),
        confidence=round(conf, 4),
        diagnostics={**diagnostics, "bayesian_confidence": round(conf, 4)},
    )
