#!/usr/bin/env python3
"""
Evaluate which prediction method and window size best matches a target set of numbers.
Target: [08, 15, 16, 21, 29, 37] Special: 05
Lottery: POWER_LOTTO
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
from common import get_lottery_rules

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)

def calculate_match(predicted, target_nums, pred_special=None, target_special=None):
    """Calculate match count for main numbers and special number"""
    pred_set = set(predicted)
    target_set = set(target_nums)
    matches = pred_set.intersection(target_set)
    count = len(matches)
    special_hit = (pred_special == target_special) if pred_special is not None and target_special is not None else False
    return count, special_hit, sorted(list(matches))

def run_matching_analysis():
    lottery_type = 'POWER_LOTTO'
    target_numbers = [8, 15, 16, 21, 29, 37]
    target_special = 5
    
    lottery_rules = get_lottery_rules(lottery_type)
    all_draws = db_manager.get_all_draws(lottery_type)
    
    # We assume the target is the LATEST draw (e.g. 114000101) which might not be in DB yet.
    # So we use the latest DB record as the start of history.
    history_pool = all_draws
    
    window_sizes = [50, 100, 200, 500, 1000]
    
    available_methods = [
        ('Frequency Analysis', prediction_engine.frequency_predict),
        ('Trend Analysis', prediction_engine.trend_predict),
        ('Bayesian Probability', prediction_engine.bayesian_predict),
        ('Monte Carlo Simulation', prediction_engine.monte_carlo_predict),
        ('Deviation Tracking', prediction_engine.deviation_predict),
        ('Statistical Model', prediction_engine.statistical_predict),
        ('Markov Chain', prediction_engine.markov_predict),
        ('Entropy Analysis', prediction_engine.entropy_predict),
        ('Hot-Cold Mixed', prediction_engine.hot_cold_mix_predict),
    ]

    print("=" * 120)
    print(f"🎯 TARGET MATCHING ANALYSIS: {lottery_type}")
    print(f"🎯 Target Numbers: {target_numbers} | Special: {target_special}")
    print(f"📊 Training on historical data up to Draw {all_draws[0]['draw']} ({all_draws[0]['date']})")
    print("=" * 120)
    print(f"{'Method/Strategy':25s} | " + " | ".join([f"W={str(w).rjust(5)}" for w in window_sizes]))
    print("-" * 120)

    method_results = defaultdict(dict)

    for w in window_sizes:
        history = history_pool[:w]
        
        # Standard Methods
        for name, method in available_methods:
            try:
                prediction = method(history, lottery_rules)
                count, special_hit, matches = calculate_match(
                    prediction['numbers'], 
                    target_numbers, 
                    prediction.get('special'), 
                    target_special
                )
                res_str = f"{count}" + ("+S" if special_hit else "")
                method_results[name][w] = res_str
            except Exception as e:
                method_results[name][w] = "ERR"

        # Ensemble
        try:
            ensemble = create_optimized_ensemble_predictor(prediction_engine)
            ens_result = ensemble.predict(history, lottery_rules)
            
            for bet_name in ['bet1', 'bet2']:
                res = ens_result[bet_name]
                count, special_hit, matches = calculate_match(
                    res['numbers'], 
                    target_numbers, 
                    res.get('special'), 
                    target_special
                )
                res_str = f"{count}" + ("+S" if special_hit else "")
                display_name = f"Ensemble ({bet_name.capitalize()})"
                method_results[display_name][w] = res_str
        except:
            pass

    # Print Report
    sorted_methods = sorted(method_results.keys())
    for name in sorted_methods:
        row = f"{name:25s} | "
        cols = []
        for w in window_sizes:
            val = method_results[name].get(w, "N/A")
            cell = str(val).center(7)
            
            # Highlight high matches
            count_val = 0
            has_s = False
            if "+S" in str(val):
                has_s = True
                count_val = int(str(val).replace("+S", ""))
            elif str(val).isdigit():
                count_val = int(val)
                
            if count_val >= 2 or has_s:
                cell = f"*{val}*".center(7)
            if count_val >= 3:
                cell = f"[{val}]".center(7)
                
            cols.append(cell)
        print(row + " | ".join(cols))

    print("-" * 120)
    print("Legend: *N* = 2+ matches or Special hit (+S) | [N] = 3+ matches")
    print("=" * 120)

if __name__ == '__main__':
    run_matching_analysis()
