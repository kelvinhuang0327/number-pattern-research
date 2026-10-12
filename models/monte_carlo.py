"""
Monte Carlo game simulator (10 000 iterations).

Simulates full 9-inning games using Poisson run distributions per inning,
with adjustments for:
  • Starting pitcher fatigue (innings 1-5 vs 6+)
  • Bullpen transition
  • WBC pitch-count limits
  • Score-dependent strategy shifts
"""
from __future__ import annotations
from typing import Dict, List, Tuple
import random
import math
from data.wbc_data import TeamStats, PitcherStats, MatchData
from config.settings import MC_SIMULATIONS
from models.advanced_features import aggregate_lineup_strength, calculate_bullpen_fatigue_penalty


def _inning_lambda(
    base_lambda: float,
    inning: int,
    sp_fatigue: float,
    is_bullpen: bool,
    bullpen_era: float,
    league_avg: float = 4.5,
) -> float:
    """
    Per-inning expected runs.
    base_lambda is per-game; convert to per-inning then adjust.
    """
    per_inning = base_lambda / 9.0

    if is_bullpen:
        bp_factor = bullpen_era / league_avg
        per_inning *= bp_factor * 1.05   # slight increase for transition
    else:
        # SP fatigue curve: effectiveness drops in later innings
        fatigue = 1.0 + sp_fatigue * max(0, inning - 3) * 0.03
        per_inning *= fatigue

    return max(0.05, per_inning)


def _poisson_sample(lam: float) -> int:
    """Sample from Poisson using inverse-CDF method."""
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= random.random()
        if p < L:
            return k - 1


def simulate_game(
    away_lam: float,
    home_lam: float,
    match: MatchData,
) -> Tuple[int, int]:
    """
    Simulate a single 9-inning game (with extra innings if tied).
    Returns (away_score, home_score).
    """
    # WBC Rules: SP expected innings based on round limits
    if match.game_type == "PROFESSIONAL":
        away_sp_limit_innings = 6.0  # Pro SPs go longer
        home_sp_limit_innings = 6.0
        away_pb_innings = 0
        home_pb_innings = 0
    else:
        away_sp_limit_innings = match.pitch_count_rule.expected_sp_innings
        home_sp_limit_innings = match.pitch_count_rule.expected_sp_innings
        # Piggyback (Second Starter) logic
        away_pb_innings = 3.5 if match.away_piggyback else 0
        home_pb_innings = 3.5 if match.home_piggyback else 0

    away_sp_fatigue = match.away_sp.whip
    home_sp_fatigue = match.home_sp.whip

    a_score = 0
    h_score = 0

    for inn in range(1, 10):
        # --- Away batting (vs home pitching) ---
        is_bullpen_h = False
        active_era_h = 0.0
        active_fatigue_h = home_sp_fatigue
        
        if inn > home_sp_limit_innings + home_pb_innings:
            is_bullpen_h = True
            active_era_h = match.home.bullpen_era
        elif inn > home_sp_limit_innings:
            # Piggyback is active
            active_era_h = match.home_piggyback.era if match.home_piggyback else match.home.bullpen_era
            active_fatigue_h = match.home_piggyback.whip if match.home_piggyback else 1.2
        else:
            # SP is active
            active_era_h = match.home_sp.era
            
        lam_a = _inning_lambda(away_lam, inn, active_fatigue_h, is_bullpen_h, active_era_h)
        a_score += _poisson_sample(lam_a)

        # --- Home batting (vs away pitching) ---
        is_bullpen_a = False
        active_era_a = 0.0
        active_fatigue_a = away_sp_fatigue
        
        if inn > away_sp_limit_innings + away_pb_innings:
            is_bullpen_a = True
            active_era_a = match.away.bullpen_era
        elif inn > away_sp_limit_innings:
            # Piggyback is active
            active_era_a = match.away_piggyback.era if match.away_piggyback else match.away.bullpen_era
            active_fatigue_a = match.away_piggyback.whip if match.away_piggyback else 1.2
        else:
            # SP is active
            active_era_a = match.away_sp.era
            
        lam_h = _inning_lambda(home_lam, inn, active_fatigue_a, is_bullpen_a, active_era_a)
        h_score += _poisson_sample(lam_h)

    # Extra innings (WBC tiebreaker: runner on 2B from 10th)
    extra = 0
    while a_score == h_score and extra < 5:
        extra += 1
        bonus = 0.35  # expected value of runner on 2B
        a_score += _poisson_sample(away_lam / 9.0 + bonus)
        h_score += _poisson_sample(home_lam / 9.0 + bonus)

    return a_score, h_score


def _inning_runs(lam: float, volatility: float, rng=random) -> int:
    """Sample runs for an inning with Gamma-Poisson (Negative Binomial) dispersion."""
    # Gamma-Poisson mixture: lam = mean, volatility = dispersion
    # For a team that's hot, volatility should increase
    if lam <= 0: return 0
    shape = lam / volatility
    scale = volatility
    # random.gammavariate(alpha, beta) where alpha=shape, beta=scale
    # But here lam is mean of the Poisson.
    # In rng terms: mean = alpha * beta.
    # We want mean = lam, so alpha = lam/volatility, beta = volatility.
    try:
        actual_lam = rng.gammavariate(max(0.1, lam/volatility), volatility)
        # Poisson sample
        L = math.exp(-actual_lam)
        k = 0
        p = 1.0
        while True:
            k += 1
            p *= rng.random()
            if p < L:
                return k - 1
    except:
        return 0

def simulate_game(
    away_lam: float,
    home_lam: float,
    match: MatchData,
    mercy_rule: bool = True,
) -> Tuple[int, int, int]:
    """
    Simulate a single game with WBC Mercy Rule and Inning Entropy.
    Returns (away_score, home_score, final_inning).
    """
    # WBC Rules: SP expected innings
    away_sp_limit = match.pitch_count_rule.expected_sp_innings if match.pitch_count_rule else 3.5
    home_sp_limit = match.pitch_count_rule.expected_sp_innings if match.pitch_count_rule else 3.5
    
    away_pb_innings = 3.5 if match.away_piggyback else 0
    home_pb_innings = 3.5 if match.home_piggyback else 0

    a_score = 0
    h_score = 0
    final_inn = 9

    # Volatility factor (Inning Entropy)
    # Higher variance = more scoring chains
    vol_a = 0.22 if "Pool" in match.round_name else 0.18
    vol_h = 0.22 if "Pool" in match.round_name else 0.18

    for inn in range(1, 13):
        # 1. Pitching Gradient Adjustments
        is_bp_h = inn > (home_sp_limit + home_pb_innings)
        is_pb_h = not is_bp_h and inn > home_sp_limit
        
        is_bp_a = inn > (away_sp_limit + away_pb_innings)
        is_pb_a = not is_bp_a and inn > away_sp_limit

        active_fatigue_h = match.home_sp.whip if not is_bp_h else (match.home_piggyback.whip if is_pb_h else 1.3)
        active_fatigue_a = match.away_sp.whip if not is_bp_a else (match.away_piggyback.whip if is_pb_a else 1.3)

        # 2. Inning Scoring
        l_a = _inning_lambda(away_lam, inn, active_fatigue_h, is_bp_h or is_pb_h, 4.5)
        l_h = _inning_lambda(home_lam, inn, active_fatigue_a, is_bp_a or is_pb_a, 4.5)

        # Zero-Inflation (Lockout logic)
        # If lambda is low, increase chance of 0
        a_r = _inning_runs(l_a, vol_a)
        if l_a < 0.2 and random.random() < 0.1: a_r = 0
        a_score += a_r

        # Bottom of inning check
        if not (inn >= 9 and h_score > a_score):
            h_r = _inning_runs(l_h, vol_h)
            if l_h < 0.2 and random.random() < 0.1: h_r = 0
            h_score += h_r

        # 3. WBC Mercy Rule
        if mercy_rule:
            lead = abs(h_score - a_score)
            if inn == 5 and lead >= 15:
                final_inn = 5
                break
            if inn >= 7 and lead >= 10:
                final_inn = inn
                break

        # 4. End Condition
        if inn >= 9 and h_score != a_score:
            final_inn = inn
            break
        
        final_inn = inn

    return a_score, h_score, final_inn


def predict(
    match: MatchData,
    n_sims: int = MC_SIMULATIONS,
    seed: int = 42,
) -> Tuple[float, float, Dict]:
    """
    Run Monte Carlo simulation (C05 Optimized).
    Returns (away_wp, home_wp, details).
    """
    random.seed(seed)

    # Base lam calculation (Keep existing wOBA to Runs logic)
    # ... (skipping some logic for brevity, will replace whole block)
    
    # Use existing aggregate_lineup_strength logic
    away_vs_sp = aggregate_lineup_strength(match.away_lineup, match.home_sp, default_woba=match.away.team_woba)
    away_vs_bp = aggregate_lineup_strength(match.away_lineup, match.home_bullpen[0] if match.home_bullpen else match.home_sp, default_woba=match.away.team_woba)
    h_bp_penalty = calculate_bullpen_fatigue_penalty(match.home_bullpen)
    woba_to_runs = 4.5 / 0.320
    park_factor = 1.10 if match.venue == "Tokyo Dome" else 1.0
    away_lam = (away_vs_sp * 0.7 + away_vs_bp * h_bp_penalty * 0.3) * woba_to_runs * park_factor

    home_vs_sp = aggregate_lineup_strength(match.home_lineup, match.away_sp, default_woba=match.home.team_woba)
    home_vs_bp = aggregate_lineup_strength(match.home_lineup, match.away_bullpen[0] if match.away_bullpen else match.away_sp, default_woba=match.home.team_woba)
    a_bp_penalty = calculate_bullpen_fatigue_penalty(match.away_bullpen)
    home_lam = (home_vs_sp * 0.7 + home_vs_bp * a_bp_penalty * 0.3) * woba_to_runs * park_factor

    away_wins = 0
    home_wins = 0
    score_counts: Dict[str, int] = {}
    total_runs_list = []
    
    total_away_runs = 0
    total_home_runs = 0
    total_inns = 0

    for _ in range(n_sims):
        a, h, inn = simulate_game(away_lam, home_lam, match)
        if a > h:
            away_wins += 1
        else:
            home_wins += 1
        
        t = a + h
        total_runs_list.append(t)
        total_away_runs += a
        total_home_runs += h
        total_inns += inn
        
        key = f"{a}-{h}"
        score_counts[key] = score_counts.get(key, 0) + 1

    away_wp = away_wins / n_sims
    home_wp = home_wins / n_sims

    # Scenarios (Quantiles)
    import numpy as np
    runs_arr = np.array(total_runs_list)
    scenarios = {
        "baseline": float(np.median(runs_arr)),
        "pitching_duel": float(np.percentile(runs_arr, 20)),
        "explosion": float(np.percentile(runs_arr, 90)),
        "avg_innings": round(total_inns / n_sims, 1),
    }

    # Top 5 scores
    top5 = sorted(score_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top5 = [(s, c / n_sims) for s, c in top5]

    details = {
        "n_simulations": n_sims,
        "away_avg_runs": round(total_away_runs / n_sims, 2),
        "home_avg_runs": round(total_home_runs / n_sims, 2),
        "total_runs_avg": round(sum(total_runs_list) / n_sims, 2),
        "top5_scores": top5,
        "scenarios": scenarios,
        "total_runs_distribution": {
            str(k): round(v / n_sims, 4)
            for k, v in dict(sorted({t: total_runs_list.count(t) for t in set(total_runs_list[:1000])}.items())).items()
        }
    }

    return away_wp, home_wp, details
