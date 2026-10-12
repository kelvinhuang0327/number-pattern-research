#!/usr/bin/env python3
"""
Power Lotto Prediction Analysis Script
Compare all existing prediction models against a user-provided target set.
"""
import sys
import os
import logging
from collections import defaultdict

# Add current directory to path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from models.optimized_ensemble import create_optimized_ensemble_predictor
from common import get_lottery_rules, normalize_lottery_type

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)

def calculate_score(predicted_nums, special_num, target_nums, target_special):
    """
    Calculate similarity score
    """
    pred_set = set(predicted_nums)
    target_set = set(target_nums)
    
    matches_zone1 = pred_set.intersection(target_set)
    match_count1 = len(matches_zone1)
    
    match_special = (special_num == target_special)
    
    # Priority: Zone 1 Matches > Zone 2 Match
    score = (match_count1 * 10) + (1 if match_special else 0)
    
    return {
        'score': score,
        'matches_zone1': sorted(list(matches_zone1)),
        'match_count1': match_count1,
        'special_match': match_special
    }

def run_analysis(target_nums, target_special):
    lottery_type = 'POWER_LOTTO'
    rules = get_lottery_rules(lottery_type)
    all_draws = db_manager.get_all_draws(lottery_type)
    
    if not all_draws:
        print("❌ No historical data found for POWER_LOTTO.")
        return

    print("=" * 80)
    print(f"🎯 Target Numbers: {target_nums} (Zone 2: {target_special})")
    print(f"📊 Based on {len(all_draws)} historical draws.")
    print("=" * 80)
    
    # Define models
    models = [
        ('Frequency Analysis', prediction_engine.frequency_predict),
        ('Trend Analysis', prediction_engine.trend_predict),
        ('Bayesian Probability', prediction_engine.bayesian_predict),
        ('Monte Carlo Simulation', prediction_engine.monte_carlo_predict),
        ('Deviation Tracking', prediction_engine.deviation_predict),
        ('Markov Chain', prediction_engine.markov_predict),
    ]
    
    # Optional models
    extensions = [
        ('Entropy Analysis', 'entropy_predict'),
        ('Hot-Cold Mixed', 'hot_cold_mix_predict'),
        ('Statistical Model', 'statistical_predict'),
    ]
    
    for name, attr in extensions:
        if hasattr(prediction_engine, attr):
            models.append((name, getattr(prediction_engine, attr)))

    results = []

    # 1. Run standard models
    for name, method in models:
        try:
            pred = method(all_draws, rules)
            info = calculate_score(pred['numbers'], pred.get('special'), target_nums, target_special)
            results.append({
                'method': name,
                'nums': sorted(pred['numbers']),
                'special': pred.get('special'),
                **info
            })
        except Exception as e:
            print(f"❌ {name} failed: {e}")

    # 2. Run Ensemble
    try:
        ensemble = create_optimized_ensemble_predictor(prediction_engine)
        ens_pred = ensemble.predict(all_draws, rules)
        
        for bet_key in ['bet1', 'bet2']:
            if bet_key in ens_pred:
                bet = ens_pred[bet_key]
                info = calculate_score(bet['numbers'], bet.get('special'), target_nums, target_special)
                results.append({
                    'method': f'Ensemble ({bet_key})',
                    'nums': sorted(bet['numbers']),
                    'special': bet.get('special'),
                    **info
                })
    except Exception as e:
        print(f"❌ Ensemble failed: {e}")

    # Sort results
    sorted_results = sorted(results, key=lambda x: x['score'], reverse=True)
    
    print("\n" + "🏆 RANKING RESULTS" + "\n" + "-" * 80)
    for i, res in enumerate(sorted_results, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
        match_str = ", ".join(f"{n:02d}" for n in res['matches_zone1']) if res['matches_zone1'] else "None"
        special_match_text = "MATCH!" if res['special_match'] else "No match"
        special_val_text = f"{res['special']:02d}" if res['special'] is not None else "N/A"
        
        print(f"{medal} [{res['method']}] Score: {res['score']}")
        print(f"   Matches Zone 1: {res['match_count1']} ({match_str})")
        print(f"   Matches Zone 2: {special_match_text} ({special_val_text})")
        print(f"   Full Prediction: {res['nums']} + {special_val_text}")
        print("-" * 40)

if __name__ == "__main__":
    # Zone 1: 08, 15, 16, 21, 29, 37
    # Zone 2: 05
    target_nums = [8, 15, 16, 21, 29, 37]
    target_special = 5
    run_analysis(target_nums, target_special)
