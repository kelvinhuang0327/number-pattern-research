#!/usr/bin/env python3
"""
Evaluate Custom Bets
Checks if user-provided bets align with system predictions.
"""
import sys
import os
import logging
from collections import defaultdict

sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from common import get_lottery_rules

# User provided bets (Updated for DAILY_539 Request)
USER_BETS = [
    [12, 33, 34, 37, 39],
    [12, 18, 19, 20, 36]
]

def evaluate_bets(lottery_type='DAILY_539'):
    # Normalize
    from common import normalize_lottery_type
    lottery_type = normalize_lottery_type(lottery_type)
    
    print("=" * 80)
    print(f"🔍 Evaluating User Bets against System Models - {lottery_type}")
    print("=" * 80)
    
    # 1. Load Data
    all_draws = db_manager.get_all_draws(lottery_type)
    all_draws.sort(key=lambda x: x['date'], reverse=True) # Latest first
    
    rules = get_lottery_rules(lottery_type)
    
    # 2. Run Models (Get Top Candidates for broad coverage)
    # For small pool (39 nums), Top 10-12 is enough overlap check.
    # Scaled based on pick count: pick_count * 2.5
    top_n = int(rules['pickCount'] * 2.5) 
    print(f"📊 Generating System Candidates (Top {top_n} per model)...")
    
    candidates = {}
    models = [
        ('Frequency', prediction_engine.frequency_predict),
        ('Trend', prediction_engine.trend_predict),
        ('Bayesian', prediction_engine.bayesian_predict),
        ('Deviation', prediction_engine.deviation_predict),
        ('Monte Carlo', prediction_engine.monte_carlo_predict),
        ('Hot-Cold', prediction_engine.hot_cold_mix_predict),
        ('Statistical', prediction_engine.statistical_predict),
        ('Entropy AI', prediction_engine.entropy_transformer_predict)
    ]
    
    temp_rules = rules.copy()
    temp_rules['pickCount'] = top_n
    
    for name, method in models:
        try:
            res = method(all_draws, temp_rules)
            candidates[name] = set(res['numbers'])
            # print(f"   {name}: {sorted(list(candidates[name]))}")
        except Exception as e:
            print(f"   Note: Model {name} failed or skipped: {e}")
            candidates[name] = set()
            
    print("-" * 80)
    
    # 3. Score Each Bet
    print(f"{'Bet':<35} | {'Score':<8} | {'Supporting Models'}")
    print("-" * 80)
    
    max_score = len(models) * rules['pickCount'] # Max possible points if all nums match all models (unlikely)
    
    for idx, bet in enumerate(USER_BETS, 1):
        bet_set = set(bet)
        
        total_matches = 0
        supporting_models = []
        
        for name, pool in candidates.items():
            overlap = len(bet_set.intersection(pool))
            total_matches += overlap
            
            # If significant overlap (>40% of bet size), list model as supporter
            threshold = max(2, int(len(bet) * 0.4))
            if overlap >= threshold:
                supporting_models.append(f"{name}({overlap})")
        
        raw_score = total_matches
        
        # Display
        bet_str = ", ".join(f"{n:02d}" for n in sorted(bet))
        models_str = ", ".join(supporting_models) if supporting_models else "None"
        
        print(f"#{idx} [{bet_str}] | {raw_score:<8} | {models_str}")
        
    print("-" * 80)
    print("💡 Analysis Legend:")
    print(f"   - Score: Total overlapping numbers with all models' top {top_n} candidates.")
    print("   - High Score: Strong consensus from multiple models.")
    print("   - Low Score: Runs counter to system trend predictions.")
    
if __name__ == '__main__':
    target = 'DAILY_539'
    if len(sys.argv) > 1:
        target = sys.argv[1]
    evaluate_bets(target)
