#!/usr/bin/env python3
"""
Benchmark Prediction Accuracy vs. Data Volume
Tests various window sizes for BIG_LOTTO to find the best match for target numbers.
"""
import sys
import os
import logging
import json
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

def calculate_match(predicted, target):
    """Calculate match count and content"""
    pred_set = set(predicted)
    target_set = set(target)
    matches = pred_set.intersection(target_set)
    return len(matches), sorted(list(matches))

def run_benchmark(target_numbers):
    lottery_type = 'BIG_LOTTO'
    lottery_rules = get_lottery_rules(lottery_type)
    all_draws = db_manager.get_all_draws(lottery_type)
    
    if not all_draws:
        print("❌ No data found.")
        return

    window_sizes = [50, 100, 200, 500, 1000, 2000, len(all_draws)]
    
    # Define Predictors
    available_methods = [
        ('Frequency Analysis', prediction_engine.frequency_predict),
        ('Trend Analysis', prediction_engine.trend_predict),
        ('Bayesian Probability', prediction_engine.bayesian_predict),
        ('Monte Carlo Simulation', prediction_engine.monte_carlo_predict),
        ('Deviation Tracking', prediction_engine.deviation_predict),
        ('Statistical Model', prediction_engine.statistical_predict),
    ]
    
    try:
        if hasattr(prediction_engine, 'entropy_predict'):
            available_methods.append(('Entropy Analysis', prediction_engine.entropy_predict))
        if hasattr(prediction_engine, 'hot_cold_mix_predict'):
            available_methods.append(('Hot-Cold Mixed', prediction_engine.hot_cold_mix_predict))
        if hasattr(prediction_engine, 'zone_balance_predict'):
            available_methods.append(('Zone Balance', prediction_engine.zone_balance_predict))
    except:
        pass

    print("=" * 100)
    print(f"📊 DATA VOLUME BENCHMARK: {lottery_type}")
    print(f"🎯 TARGET NUMBERS: {target_numbers}")
    print("=" * 100)
    print(f"{'Method':25s} | " + " | ".join([f"W={w:4d}" for w in window_sizes]))
    print("-" * 100)

    method_results = defaultdict(dict)

    for w in window_sizes:
        history = all_draws[:w]
        
        # Standard Methods
        for name, method in available_methods:
            try:
                # Some models like Statistical might be stochastic, so we keep it simple for benchmark
                prediction = method(history, lottery_rules)
                match_count, _ = calculate_match(prediction['numbers'], target_numbers)
                method_results[name][w] = match_count
            except:
                method_results[name][w] = "ERR"

        # Ensemble
        try:
            ensemble = create_optimized_ensemble_predictor(prediction_engine)
            ens_result = ensemble.predict(history, lottery_rules)
            
            m1, _ = calculate_match(ens_result['bet1']['numbers'], target_numbers)
            m2, _ = calculate_match(ens_result['bet2']['numbers'], target_numbers)
            method_results['Ensemble (Bet 1)'][w] = m1
            method_results['Ensemble (Bet 2)'][w] = m2
        except:
            method_results['Ensemble (Bet 1)'][w] = "ERR"
            method_results['Ensemble (Bet 2)'][w] = "ERR"

    # Print Report
    for name in sorted(method_results.keys()):
        row = f"{name:25s} | "
        cols = []
        for w in window_sizes:
            val = method_results[name][w]
            cell = str(val).center(6)
            # Simple highlight for better visibility in terminal
            if isinstance(val, int) and val >= 2:
                cell = f"*{val}*".center(6)
            cols.append(cell)
        print(row + " | ".join(cols))

    print("-" * 100)
    print("*N* = 2 or more matches")
    print("=" * 100)

if __name__ == '__main__':
    targets = [6, 7, 15, 19, 24, 33, 46]
    run_benchmark(targets)
