"""
Stacking Meta-Learner for Ensemble.
Combines sub-model outputs (Elo, Bayesian, Poisson, GBM, MC)
using a context-aware weighting scheme with EMA Brier dynamic weights.
"""
from typing import Dict, List, Tuple
import math

from learning.self_learning import get_current_weights, get_ema_brier


def meta_predict(sub_model_results: Dict[str, Tuple[float, float]], context: Dict) -> Tuple[float, float, float]:
    """
    Apply a Meta-Learner to sub-model outputs.
    Returns (away_wp, home_wp, confidence_score)
    """
    
    # 1. Dynamic base weights from EMA Brier learning
    learned = get_current_weights()
    base_weights = {
        "elo":          learned.get("elo", 0.05),
        "bayesian":     learned.get("bayesian", 0.15),
        "poisson":      learned.get("poisson", 0.20),
        "gbm":          learned.get("gbm", 0.25),
        "monte_carlo":  learned.get("monte_carlo", 0.25),
        "baseline":     0.10,
    }
    
    # 2. Dynamic Weighting (EWMA-style emulation based on context)
    # If roster volatility is high, we discount the historical models (Elo/Bayesian)
    roster_strength = context.get("roster_strength_index", 100)
    vol_factor = (100 - roster_strength) / 100.0 # 0.0 to 1.0
    
    # Aggressively shift weights based on volatility (V3 Enhancement)
    base_weights["elo"] *= max(0.01, (1.0 - vol_factor * 1.5))
    base_weights["bayesian"] *= max(0.05, (1.0 - vol_factor * 0.8))
    base_weights["monte_carlo"] *= (1.0 + vol_factor * 1.2)
    base_weights["gbm"] *= (1.0 + vol_factor * 1.0)
    base_weights["baseline"] *= max(0.01, (1.0 - vol_factor * 2.0))
    
    # 3. Upset Detection logic
    # If MC shows a team is much stronger than Elo suggests, we have an "Upset Signal"
    # This captures the "Chinese Taipei 2024" factor where current form > history
    elo_res = sub_model_results.get("elo", (0.5, 0.5))
    mc_res = sub_model_results.get("monte_carlo", (0.5, 0.5))
    
    # Check if MC favors the underdog (the one Elo dislikes)
    upset_signal = False
    if (elo_res[0] < 0.45 and mc_res[0] > elo_res[0] + 0.15) or \
       (elo_res[1] < 0.45 and mc_res[1] > elo_res[1] + 0.15):
        upset_signal = True
        
    if upset_signal:
        base_weights["monte_carlo"] *= 2.0 # Trust the simulation data
        base_weights["elo"] *= 0.2          # Discount historical rank
        base_weights["gbm"] *= 1.5          # Trust ML features

    # 4. Aggregate
    total_w = sum(base_weights.values())
    away_wp = 0.0
    for name, (a, h) in sub_model_results.items():
        weight = base_weights.get(name, 0.1)
        away_wp += a * (weight / total_w)
        
    # 5. Market Sentiment Adjustment
    steam = context.get("steam_move", 0.0)
    # steam > 0: Away support, steam < 0: Home support
    away_wp += steam * 0.25 # Sharp money influence (capped)
    
    # Apply calibration
    # If JPN (Home) is heavy favorite, ensure we aren't too conservative
    if away_wp < 0.3:
        away_wp = away_wp * 0.9 # enhance favorite edge
    
    # Softmax-like smoothing
    logit = math.log(max(1e-6, away_wp) / (1.0 - away_wp + 1e-6))
    away_wp_calibrated = 1.0 / (1.0 + math.exp(-logit / 0.85))
    
    # Calculate Confidence Score (Model Agreement)
    # We look at how many models agree on the favorite
    agreement = calculate_model_agreement(sub_model_results)
    
    return away_wp_calibrated, 1.0 - away_wp_calibrated, agreement

def calculate_model_agreement(sub_model_results: Dict[str, Tuple[float, float]]) -> float:
    """
    Measures how consistent sub-models are. 
    Returns a score 0.0 to 1.0 (1.0 = perfect consensus)
    """
    if not sub_model_results: return 0.0
    
    fav_counts = {"AWAY": 0, "HOME": 0}
    for name, (a, h) in sub_model_results.items():
        if a > h: fav_counts["AWAY"] += 1
        elif h > a: fav_counts["HOME"] += 1
        
    total_models = len(sub_model_results)
    max_agreement = max(fav_counts.values())
    
    # Simple ratio: if 5/6 models agree, score is 0.83
    agreement_score = max_agreement / total_models
    return agreement_score

def calculate_kelly_bet(win_prob: float, odds: float, fraction: float = 0.25) -> float:
    """
    Calculate the Kelly Criterion bet size.
    fraction=0.25 is "Quarter-Kelly" to account for variance and estimation error.
    odds is decimal odds.
    """
    if odds <= 1.0: return 0.0
    
    # Kelly Formula: f = (bp - q) / b
    # b = decimal_odds - 1
    # p = win probability
    # q = 1 - p
    b = odds - 1.0
    p = win_prob
    q = 1.0 - p
    
    kelly_f = (b * p - q) / b
    
    # Apply fractional Kelly and ensure it's positive
    suggested_bet = max(0.0, kelly_f * fraction)
    return suggested_bet
