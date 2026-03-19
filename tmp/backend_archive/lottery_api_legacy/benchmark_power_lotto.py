#!/usr/bin/env python3
"""
Benchmark Prediction Accuracy vs. Data Volume for POWER_LOTTO
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

def calculate_match(predicted, target, pred_special=None, target_special=None):
    """Calculate match count and special number match"""
    pred_set = set(predicted)
    target_set = set(target)
    matches = pred_set.intersection(target_set)
    count = len(matches)
    special_match = (pred_special == target_special) if pred_special is not None and target_special is not None else False
    return count, special_match

def run_benchmark(lottery_type):
    lottery_rules = get_lottery_rules(lottery_type)
    
    # Fix database path
    import os
    db_path = os.path.join(os.getcwd(), 'lottery_api', 'data', 'lottery_v2.db')
    if os.path.exists(db_path):
        db_manager.db_path = db_path
        print(f"DEBUG: Updated DB path to {db_path}")

    all_draws_full = db_manager.get_all_draws(lottery_type)
    
    if not all_draws_full:
        print("❌ No data found.")
        return

    # Filter 2025 draws
    draws_2025 = [d for d in all_draws_full if '2025' in str(d.get('date', ''))]
    draws_2025 = sorted(draws_2025, key=lambda x: x['draw'])
    
    if not draws_2025:
        print("❌ No 2025 data found.")
        return

    print("=" * 115)
    print(f"📊 2025 ROLLING BACKTEST: {lottery_type}")
    print(f"📅 Total Draws: {len(draws_2025)} (From {draws_2025[0]['date']} to {draws_2025[-1]['date']})")
    print("=" * 115)

    available_methods = [
        ('Frequency', prediction_engine.frequency_predict),
        ('Trend', prediction_engine.trend_predict),
        ('Bayesian', prediction_engine.bayesian_predict),
        ('Monte Carlo', prediction_engine.monte_carlo_predict),
        ('Deviation', prediction_engine.deviation_predict),
        ('Statistical', prediction_engine.statistical_predict),
        ('Entropy', prediction_engine.entropy_predict),
        # ('Hot-Cold', prediction_engine.hot_cold_mix_predict) # Skip for speed if needed
    ]

    # Initialize stats
    stats = defaultdict(lambda: {'match_counts': defaultdict(int), 'special_hits': 0, 'total': 0})
    
    # Try to init ensemble once
    try:
        ensemble = create_optimized_ensemble_predictor(prediction_engine)
        has_ensemble = True
    except:
        has_ensemble = False

    # Perform rolling backtest
    total_draws = len(draws_2025)
    
    for idx, target_draw in enumerate(draws_2025):
        draw_id = target_draw['draw']
        actual_numbers = target_draw['numbers']
        actual_special = target_draw.get('special')
        
        # Find index in full history
        full_idx = -1
        for i, d in enumerate(all_draws_full):
            if d['draw'] == draw_id:
                full_idx = i
                break
        
        if full_idx == -1 or full_idx + 1 >= len(all_draws_full):
            continue
            
        # History is everything AFTER the target draw (since draws are sorted desc in DB usually, but we need to check)
        # DB returns sorted by date DESC usually.
        # Let's double check. If all_draws_full[0] is latest, then history is all_draws_full[full_idx+1:]
        history = all_draws_full[full_idx+1:]
        
        # Limit history to 200 for speed if needed, or use full
        # history = history[:200]
        
        print(f"Processing {idx+1}/{total_draws}: {draw_id}...", end='\r')

        # Test Standard Methods
        for name, method in available_methods:
            try:
                pred = method(history, lottery_rules)
                count, s_hit = calculate_match(pred['numbers'], actual_numbers, pred.get('special'), actual_special)
                stats[name]['match_counts'][count] += 1
                if s_hit: stats[name]['special_hits'] += 1
                stats[name]['total'] += 1
            except:
                pass
        
        # Test Ensemble
        if has_ensemble:
            try:
                # Disable backtest_periods for speed (use default 0 or small)
                # Ensure ensemble uses cached weights if possible to speed up
                ens_res = ensemble.predict(history, lottery_rules, backtest_periods=5) 
                
                # Bet 1
                c1, s1 = calculate_match(ens_res['bet1']['numbers'], actual_numbers, ens_res['bet1'].get('special'), actual_special)
                stats['Ensemble (Bet1)']['match_counts'][c1] += 1
                if s1: stats['Ensemble (Bet1)']['special_hits'] += 1
                stats['Ensemble (Bet1)']['total'] += 1
                
                # Bet 2
                c2, s2 = calculate_match(ens_res['bet2']['numbers'], actual_numbers, ens_res['bet2'].get('special'), actual_special)
                stats['Ensemble (Bet2)']['match_counts'][c2] += 1
                if s2: stats['Ensemble (Bet2)']['special_hits'] += 1
                stats['Ensemble (Bet2)']['total'] += 1
            except:
                pass

    print("\n" + "=" * 100)
    print(f"{'Method':<20} | {'Win Rate (3+)':<15} | {'Avg Match':<10} | {'Special Accuracy':<18}")
    print("-" * 100)
    
    # Sort by Win Rate (3+)
    results = []
    for name, data in stats.items():
        total = data['total']
        if total == 0: continue
        
        # Calculate Win Rate (Match 3 or more)
        wins_3plus = sum(data['match_counts'][k] for k in data['match_counts'] if k >= 3)
        win_rate = (wins_3plus / total) * 100
        
        # Avg Match
        total_matches = sum(k * v for k, v in data['match_counts'].items())
        avg_match = total_matches / total
        
        # Special Acc
        special_acc = (data['special_hits'] / total) * 100
        
        results.append((name, win_rate, avg_match, special_acc))
        
    results.sort(key=lambda x: x[1], reverse=True)
    
    for res in results:
        print(f"{res[0]:<20} | {res[1]:6.2f}%         | {res[2]:5.2f}      | {res[3]:6.2f}%")
        
    print("=" * 100)

if __name__ == '__main__':
    run_benchmark('POWER_LOTTO')
