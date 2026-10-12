"""
WBC Rule Engine — applies WBC-specific adjustments to predictions.

Covers:
  • Empirical Bayes strength shrinkage for small international samples
  • Pitch-count limit impact
  • Star player impact multiplier
"""
from __future__ import annotations

import logging
from dataclasses import replace

from wbc_backend.domain.schemas import Matchup, PredictionResult, TeamSnapshot

logger = logging.getLogger(__name__)


def _empirical_bayes_strength(team: TeamSnapshot, alpha: float = 120.0) -> float:
    """Shrinks volatile international samples toward league prior strength."""
    n = max(1.0, float(team.sample_size))
    weight_data = n / (n + alpha)
    observed = (team.batting_woba - 0.320) * 1.8 + (team.batting_ops_plus - 100.0) / 200.0
    posterior = weight_data * observed + (1.0 - weight_data) * team.league_prior_strength
    return posterior


def _pitch_count_adjustment(team: TeamSnapshot) -> tuple[float, float]:
    """Returns (win_delta_component, run_delta_component)."""
    deficit = max(0, 75 - team.pitch_limit)
    starter_penalty = 0.0014 * deficit
    bullpen_support = 0.0012 * max(0.0, team.bullpen_depth - 7.0)
    if team.ace_pitch_count_limited:
        starter_penalty += 0.010
    return bullpen_support - starter_penalty, -0.015 * starter_penalty


def apply_wbc_rules(
    matchup: Matchup,
    pred: PredictionResult,
) -> tuple[PredictionResult, list[str], dict[str, float]]:
    """Apply WBC-specific adjustments to the prediction."""
    notes: list[str] = []

    home_eb = _empirical_bayes_strength(matchup.home)
    away_eb = _empirical_bayes_strength(matchup.away)
    eb_delta = (home_eb - away_eb) * 0.035

    home_pitch_delta, home_run_delta = _pitch_count_adjustment(matchup.home)
    away_pitch_delta, away_run_delta = _pitch_count_adjustment(matchup.away)
    pitch_delta = home_pitch_delta - away_pitch_delta

    star_delta = (matchup.home.top50_stars - matchup.away.top50_stars) * 0.012

    home_wp = pred.home_win_prob + eb_delta + pitch_delta + star_delta
    home_wp = max(0.03, min(0.97, home_wp))

    expected_home_runs = max(1.5, pred.expected_home_runs + home_run_delta + 0.08 * matchup.home.top50_stars)
    expected_away_runs = max(1.5, pred.expected_away_runs + away_run_delta + 0.08 * matchup.away.top50_stars)

    if matchup.home.pitch_limit < 70 or matchup.away.pitch_limit < 70:
        notes.append("WBC pitch-count rule applied: starter weight reduced, bullpen weight increased")
    if matchup.home.top50_stars or matchup.away.top50_stars:
        notes.append("Roster impact applied: MLB Top-50 star multiplier active")
    if matchup.home.sample_size < 100 or matchup.away.sample_size < 100:
        notes.append("Small-sample correction applied via Empirical Bayes prior")

    updated = replace(
        pred,
        home_win_prob=home_wp,
        away_win_prob=1.0 - home_wp,
        expected_home_runs=expected_home_runs,
        expected_away_runs=expected_away_runs,
        x_factors=pred.x_factors + notes,
        diagnostics={
            **pred.diagnostics,
            "wbc_eb_delta": eb_delta,
            "wbc_pitch_delta": pitch_delta,
            "wbc_star_delta": star_delta,
        },
    )
    return updated, notes, {"eb_delta": eb_delta, "pitch_delta": pitch_delta, "star_delta": star_delta}
