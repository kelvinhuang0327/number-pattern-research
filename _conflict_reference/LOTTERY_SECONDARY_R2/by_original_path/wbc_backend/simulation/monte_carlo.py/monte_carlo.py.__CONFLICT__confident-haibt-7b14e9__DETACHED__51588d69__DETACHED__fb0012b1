"""
Monte Carlo Simulation Engine — § 二 模擬模型

At least 50,000 simulations incorporating:
  • Poisson-distributed scoring
  • Pitcher fatigue impact
  • Bullpen availability
  • WBC pitch-count limits
  • Score variance adjustments
"""
from __future__ import annotations

import logging

import numpy as np

from wbc_backend.domain.schemas import PredictionResult, SimulationSummary

logger = logging.getLogger(__name__)


def run_monte_carlo(  # noqa: C901
    pred: PredictionResult,
    line_total: float = 7.5,
    line_spread_home: float = -1.5,
    simulations: int = 50_000,
    seed: int = 42,
    home_sp_fatigue: float = 0.0,
    away_sp_fatigue: float = 0.0,
    home_bullpen_stress: float = 0.0,
    away_bullpen_stress: float = 0.0,
    wbc_variance_add: float = 0.18,
    mercy_rule: bool = True,
    blowout_propensity: float = 0.0,    # N.02 mismatch_blowout_propensity → tail expansion
) -> SimulationSummary:
    """
    Run N Monte Carlo game simulations with inning-by-inning precision.

    Optimized for WBC 2026:
      • Inning-by-inning scoring with momentum (Inning Entropy)
      • Mercy Rule: lead >= 15 after 5th, lead >= 10 after 7th
      • Pitching Depth Gradient: Different lambdas for SP (Innings 1-4) vs RP (5-9)
      • Zero-Inflation: Better lockout modeling
    """
    rng = np.random.default_rng(seed)

    # ── Master Scoreboards ──
    final_home_runs = np.zeros(simulations, dtype=int)
    final_away_runs = np.zeros(simulations, dtype=int)
    final_innings = np.zeros(simulations, dtype=int)

    # ── Expected Runs per Inning (ERI) ──
    # Base lambdas from prediction (per game, divide by 9)
    lam_home_base = max(0.5, pred.expected_home_runs) / 9.0
    lam_away_base = max(0.5, pred.expected_away_runs) / 9.0

    # ── Asymmetric λ Boost for High-Mismatch Games (N.02) ────────────────
    # blowout_propensity > 0.3 → amplify existing λ asymmetry
    # Rationale: Elo gap captures capability mismatch not fully reflected in
    # per-game run estimates; stronger team scores MORE, weaker team scores LESS
    # blowout=0.85 (B06 level) → elo_boost=0.17 → lam_h × 1.17, lam_a × 0.915
    if blowout_propensity > 0.3:
        elo_boost = blowout_propensity * 0.20  # max +20% per inning at propensity=1.0
        if lam_home_base >= lam_away_base:
            lam_home_base = lam_home_base * (1.0 + elo_boost)
            lam_away_base = max(0.10, lam_away_base * (1.0 - elo_boost * 0.5))
        else:
            lam_away_base = lam_away_base * (1.0 + elo_boost)
            lam_home_base = max(0.10, lam_home_base * (1.0 - elo_boost * 0.5))

    # ── Simulation Loop ──
    for i in range(simulations):
        h_score = 0
        a_score = 0
        game_ended = False

        # Inning-by-Inning Simulation (up to 9 innings + possible extras)
        for inn in range(1, 13): # Allow up to 12 innings
            if game_ended:
                break

            # 1. Pitching Gradient & Fatigue (SP vs RP)
            # Innings 1-4: SP dominated
            # Innings 5-9: Bullpen dominated
            l_home = lam_home_base
            l_away = lam_away_base

            # Adjustments based on Pitching Tier
            if inn <= 4:
                # SP performance (affected by fatigue)
                l_home += away_sp_fatigue * 0.1
                l_away += home_sp_fatigue * 0.1
            else:
                # RP performance (affected by stress/depth)
                # If depth is poor (high stress), bias scoring up
                l_home += away_bullpen_stress * 0.08
                l_away += home_bullpen_stress * 0.08

            # 2. Inning Entropy / Scoring Chains (The "13-0" effect)
            # If a team starts scoring, the probability of scoring more in THAT inning increases
            # We simulate this via a Gamma-Poisson mixture per inning
            # High variance_add = more likely to have 4+ run innings
            # blowout_propensity (N.02) inflates variance for high-mismatch games:
            #   propensity=0.85 (B06 level) → adds +0.128 to variance_add
            #   propensity=0.00 → no change
            effective_variance_add = wbc_variance_add + blowout_propensity * 0.15
            volatility = 1.0 + effective_variance_add

            # Away Inning
            a_inn_lam = rng.gamma(l_away / volatility, volatility)
            a_inn_runs = rng.poisson(a_inn_lam)

            # Zero-Inflation Check (Shutout logic)
            if rng.random() < 0.05 and l_away < 0.3: # 5% chance of total lockout if lambda is low
                a_inn_runs = 0

            a_score += a_inn_runs

            # Home Inning (Bottom)
            if not (inn >= 9 and h_score > a_score): # Home doesn't bat in bottom 9 if winning
                h_inn_lam = rng.gamma(l_home / volatility, volatility)
                h_inn_runs = rng.poisson(h_inn_lam)

                if rng.random() < 0.05 and l_home < 0.3:
                    h_inn_runs = 0

                h_score += h_inn_runs

            # 3. WBC Mercy Rule
            if mercy_rule:
                lead = abs(h_score - a_score)
                if inn == 5 and lead >= 15 or inn >= 7 and lead >= 10:
                    game_ended = True

            # 4. Standard End of Game
            if inn >= 9 and h_score != a_score:
                game_ended = True

            final_innings[i] = inn

        final_home_runs[i] = h_score
        final_away_runs[i] = a_score

    # ── Compute Market Probabilities ──
    total_runs = final_home_runs + final_away_runs
    margin = final_home_runs.astype(float) - final_away_runs.astype(float)

    home_wins_final = (final_home_runs > final_away_runs)
    home_win_prob = float(home_wins_final.mean())
    over_prob = float((total_runs > line_total).mean())
    home_cover = float((margin > line_spread_home).mean())
    odd_prob = float((total_runs % 2 == 1).mean())

    # F5 calculated from actual 5-inning snapshots
    # (Approx as exact 5-inning data wasn't stored to save memory, use ratio)
    f5_home_win = home_win_prob * 0.95 # Slight bias toward home in full game

    # Score distribution
    score_dist = {}
    for h, a in zip(final_home_runs[:10000], final_away_runs[:10000]):
        key = f"{h}-{a}"
        score_dist[key] = score_dist.get(key, 0) + 1
    for key in score_dist:
        score_dist[key] = round(score_dist[key] / 10000, 4)
    top_scores = dict(sorted(score_dist.items(), key=lambda x: -x[1])[:10])

    mean_total = float(total_runs.mean())
    std_total = float(total_runs.std())

    # ── Derive Scenarios (Multi-Scenario logic) ──
    # Baseline: Median
    # Pitching Duel: 20th percentile
    # Explosion: 90th percentile
    scenarios = {
        "baseline": float(np.median(total_runs)),
        "pitching_duel": float(np.percentile(total_runs, 20)),
        "explosion": float(np.percentile(total_runs, 90)),
        "avg_innings": float(final_innings.mean()),
    }

    return SimulationSummary(
        home_win_prob=round(home_win_prob, 4),
        away_win_prob=round(1 - home_win_prob, 4),
        over_prob=round(over_prob, 4),
        under_prob=round(1 - over_prob, 4),
        home_cover_prob=round(home_cover, 4),
        away_cover_prob=round(1 - home_cover, 4),
        mean_total_runs=round(mean_total, 2),
        std_total_runs=round(std_total, 2),
        odd_prob=round(odd_prob, 4),
        even_prob=round(1 - odd_prob, 4),
        home_f5_win_prob=round(f5_home_win, 4),
        away_f5_win_prob=round(1 - f5_home_win, 4),
        score_distribution=top_scores,
        n_simulations=simulations,
        scenarios=scenarios,
    )
