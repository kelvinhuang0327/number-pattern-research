#!/usr/bin/env python3
"""
Find Closest Prediction Method
Legacy script to compare generated predictions against a target set of numbers.
"""
import sys
import os
import logging
from collections import defaultdict
import argparse

# Add current directory to path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from models.optimized_ensemble import create_optimized_ensemble_predictor
from common import get_lottery_rules, normalize_lottery_type

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)

def calculate_match(predicted, target):
    """
    Calculate match count and content
    """
    pred_set = set(predicted)
    target_set = set(target)
    
    matches = pred_set.intersection(target_set)
    return len(matches), sorted(list(matches))

def run_comparison(target_numbers, lottery_type_arg='DAILY_539'):
    # Normalize input
    lottery_type = normalize_lottery_type(lottery_type_arg)
    
    print("=" * 80)
    print(f"🚀 Prediction Method Matcher: {lottery_type}")
    print(f"🎯 Target Numbers: {target_numbers}")
    print("=" * 80)
    
    # 1. Load Rules
    lottery_rules = get_lottery_rules(lottery_type)
    
    # 2. Fetch History
    all_draws = db_manager.get_all_draws(lottery_type)
    
    if not all_draws or len(all_draws) < 50:
        print(f"❌ Insufficient data. Found {len(all_draws) if all_draws else 0} draws.")
        return

    print(f"📊 Based on {len(all_draws)} historical draws...")
    print(f"   Latest Draw in DB: {all_draws[0]['date']} (Draw {all_draws[0]['draw']})")
    print("-" * 80)
    
    # 3. Define Predictors
    available_methods = [
        ('Frequency Analysis', prediction_engine.frequency_predict),
        ('Trend Analysis', prediction_engine.trend_predict),
        ('Bayesian Probability', prediction_engine.bayesian_predict),
        ('Monte Carlo Simulation', prediction_engine.monte_carlo_predict),
        ('Deviation Tracking', prediction_engine.deviation_predict),
        ('Markov Chain', prediction_engine.markov_predict),
    ]
    
    try:
        if hasattr(prediction_engine, 'entropy_predict'):
            available_methods.append(('Entropy Analysis', prediction_engine.entropy_predict))
        if hasattr(prediction_engine, 'hot_cold_mix_predict'):
            available_methods.append(('Hot-Cold Mixed', prediction_engine.hot_cold_mix_predict))
        if hasattr(prediction_engine, 'statistical_predict'):
            available_methods.append(('Statistical Model', prediction_engine.statistical_predict))
    except:
        pass

    results = []

    # 4. Run Standard Predictors
    print("🔍 Comparing standard models...")
    for name, method in available_methods:
        try:
            prediction = method(all_draws, lottery_rules)
            nums = sorted(prediction['numbers'])
            
            match_count, match_nums = calculate_match(nums, target_numbers)
            
            results.append({
                'method': name,
                'predicted': nums,
                'matches': match_count,
                'matched_numbers': match_nums
            })
            # print(f"   ✓ {name:20s}: {nums} (Matches: {match_count})")
        except Exception as e:
            print(f"   ❌ {name:20s}: Failed")

    # 5. Run Ensemble
    try:
        ensemble = create_optimized_ensemble_predictor(prediction_engine)
        ens_result = ensemble.predict(all_draws, lottery_rules)
        
        # Bet 1
        nums1 = sorted(ens_result['bet1']['numbers'])
        match_count1, match_nums1 = calculate_match(nums1, target_numbers)
        results.append({
            'method': 'Ensemble (Bet 1)',
            'predicted': nums1,
            'matches': match_count1,
            'matched_numbers': match_nums1
        })
        
        # Bet 2
        nums2 = sorted(ens_result['bet2']['numbers'])
        match_count2, match_nums2 = calculate_match(nums2, target_numbers)
        results.append({
            'method': 'Ensemble (Bet 2)',
            'predicted': nums2,
            'matches': match_count2,
            'matched_numbers': match_nums2
        })
        # print(f"   ✓ {'Ensemble Analysis':20s}: Checked 2 bets")
        
    except Exception as e:
         import traceback
         print(f"   ❌ Ensemble Analysis   : Failed ({str(e)})")
         traceback.print_exc()

    # 6. Sort and Report
    # Sort by matches (desc), then by method name
    sorted_results = sorted(results, key=lambda x: x['matches'], reverse=True)
    
    print("\n" + "=" * 80)
    print("🏆 MATCH ANALYSIS RESULTS")
    print("=" * 80)
    
    for rank, res in enumerate(sorted_results, 1):
        match_str = ", ".join(f"{n:02d}" for n in res['matched_numbers']) if res['matched_numbers'] else "None"
        pred_str = ", ".join(f"{n:02d}" for n in res['predicted'])
        
        # Highlight top performers
        prefix = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
        
        print(f"{prefix} [{res['method']}]")
        print(f"   Matches: {res['matches']} ({match_str})")
        print(f"   Predict: {pred_str}")
        print("-" * 40)

if __name__ == '__main__':
    # Default input
    l_type = 'DAILY_539'
    
    # Allow command line calc
    if len(sys.argv) > 1:
        # Check if first arg is lottery type or number
        try:
            int(sys.argv[1])
            # If number, assume all are numbers
            targets = [int(x) for x in sys.argv[1:]]
        except:
            l_type = sys.argv[1]
            if len(sys.argv) > 2:
                targets = [int(x) for x in sys.argv[2:]]
            
    run_comparison(targets, l_type)
