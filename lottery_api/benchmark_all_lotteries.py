#!/usr/bin/env python3
"""
Benchmark Script for Lottery Prediction Methods
"""
import sys
import os
import json
import logging
from collections import defaultdict
from typing import Dict, List, Set

# Add current directory to path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from common import get_lottery_rules

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def evaluate_prediction(predicted: List[int], actual: List[int], special_predicted: int = None, special_actual: int = None) -> Dict:
    """
    Evaluate a single prediction against actual results.
    """
    pred_set = set(predicted)
    actual_set = set(actual)
    
    matches = len(pred_set & actual_set)
    special_match = False
    
    if special_predicted is not None and special_actual is not None:
        special_match = (special_predicted == special_actual)
        
    return {
        'matches': matches,
        'special_match': special_match,
        'predicted_len': len(predicted),
        'actual_len': len(actual)
    }

def run_benchmark():
    print("=" * 80)
    print("🚀 Lottery Prediction Benchmark System")
    print("=" * 80)

    # 1. Load Lottery Types
    try:
        with open('data/lottery_types.json', 'r', encoding='utf-8') as f:
            lottery_types = json.load(f)
    except FileNotFoundError:
        print("❌ Error: data/lottery_types.json not found.")
        return

    # Prediction Methods to Test
    # Using methods available in unified_predictor.py
    prediction_methods = [
        ('Frequency', lambda h, r: prediction_engine.frequency_predict(h, r)),
        ('Trend', lambda h, r: prediction_engine.trend_predict(h, r)),
        ('Bayesian', lambda h, r: prediction_engine.bayesian_predict(h, r)),
        ('Markov', lambda h, r: prediction_engine.markov_predict(h, r)),
        ('Deviation', lambda h, r: prediction_engine.deviation_predict(h, r)),
    ]
    
    # Store aggregated results
    # { lottery_type: { method_name: { total_matches: 0, count: 0, avg_match: 0.0 } } }
    benchmark_results = defaultdict(lambda: defaultdict(lambda: {'total_matches': 0, 'total_special_matches': 0, 'count': 0}))

    for type_key, type_info in lottery_types.items():
        type_name = type_info.get('name', type_key)
        print(f"\n📊 Processing {type_name} ({type_key})...")
        
        # 2. Fetch History
        all_draws = db_manager.get_all_draws(type_key)
        total_records = len(all_draws)
        
        if total_records < 50:
            print(f"   ⚠️  Insufficient data ({total_records} records). Skipping.")
            continue
            
        # Test Set: Last 20 draws (or less if not enough data, though we checked < 50)
        test_count = 20
        test_data = all_draws[:test_count] # all_draws seems to be sorted DESC based on other files (index 0 is latest)
        
        # We need to simulate 'past' history for each test item.
        # If all_draws[0] is latest, then for test item i (0..19), 
        # training data is all_draws[i+1:]
        
        print(f"   🧪 Running backtest on latest {test_count} draws...")
        
        lottery_rules = get_lottery_rules(type_key)
        
        for i in range(test_count):
            target_draw = all_draws[i]
            target_numbers = target_draw['numbers']
            target_special = target_draw.get('special')
            
            # Training history: all draws strictly AFTER this draw index (meaning older in time)
            training_history = all_draws[i+1:]
            
            # We need a reasonable amount of history to predict
            if len(training_history) < 30:
                continue
                
            for method_name, method_func in prediction_methods:
                try:
                    # Run Prediction
                    result = method_func(training_history, lottery_rules)
                    predicted_numbers = result.get('numbers', [])
                    predicted_special = result.get('special')
                    
                    # Evaluate
                    eval_res = evaluate_prediction(
                        predicted_numbers, 
                        target_numbers, 
                        predicted_special, 
                        int(target_special) if target_special else None
                    )
                    
                    # Aggregate
                    stats = benchmark_results[type_key][method_name]
                    stats['total_matches'] += eval_res['matches']
                    if eval_res['special_match']:
                        stats['total_special_matches'] += 1
                    stats['count'] += 1
                    
                except Exception as e:
                    # logger.error(f"Error in {method_name} for {type_key}: {e}")
                    pass
        
        # Calculate Averages for this Type
        print(f"   🏁 Results for {type_name}:")
        type_summary = []
        for method_name, stats in benchmark_results[type_key].items():
            if stats['count'] > 0:
                avg_match = stats['total_matches'] / stats['count']
                special_rate = (stats['total_special_matches'] / stats['count']) * 100
                type_summary.append((method_name, avg_match, special_rate))
        
        # Sort by average match
        type_summary.sort(key=lambda x: x[1], reverse=True)
        
        for m_name, avg, sp_rate in type_summary:
            print(f"      - {m_name:12s}: Avg Matches {avg:.2f} | Special Hit Rate {sp_rate:.1f}%")

    # 3. Final Summary Report
    print("\n" + "=" * 80)
    print("🏆 FINAL RECOMMENDATIONS (Best Method by Type)")
    print("=" * 80)
    
    for type_key, methods in benchmark_results.items():
        if not methods:
            continue
            
        type_name = lottery_types[type_key].get('name', type_key)
        
        # Find best method based on Avg Matches
        best_method = None
        best_avg = -1
        best_sp = -1
        
        for m_name, stats in methods.items():
            if stats['count'] == 0: continue
            avg = stats['total_matches'] / stats['count']
            if avg > best_avg:
                best_avg = avg
                best_method = m_name
                best_sp = (stats['total_special_matches'] / stats['count']) * 100
        
        if best_method:
            print(f"🌟 {type_name:15s} [{type_key}]")
            print(f"   Best Strategy: {best_method}")
            print(f"   Performance  : Avg {best_avg:.2f} matches per draw")
            print(f"   Special Num  : {best_sp:.1f}% accuracy")
            print("-" * 40)

if __name__ == "__main__":
    run_benchmark()
