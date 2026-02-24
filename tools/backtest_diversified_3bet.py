#!/usr/bin/env python3
"""
Corrected Backtest for Diversified 3-Bet Strategy
================================================
Fixes data leakage and adds Random Baseline.
"""
import os
import sys
import numpy as np
import json
from collections import Counter
from tqdm import tqdm
import random

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from tools.biglotto_diversified_ensemble import DiversifiedEnsemble

def calculate_prize(matched_main, matched_special):
    """
    Taiwan Big Lotto (大樂透) Prize Table
    Rules: 6 main drawn + 1 special.
    """
    if matched_main == 6:           return 100000000  # 1st: 6 main
    if matched_main == 5 and matched_special: return 1500000   # 2nd: 5 main + special
    if matched_main == 5:           return 40000    # 3rd: 5 main
    if matched_main == 4 and matched_special: return 10000    # 4th: 4 main + special
    if matched_main == 4:           return 2000     # 5th: 4 main
    if matched_main == 3 and matched_special: return 1000     # 6th: 3 main + special
    if matched_main == 2 and matched_special: return 400      # 7th: 2 main + special
    if matched_main == 3:           return 400      # 8th: 3 main (General)
    return 0

def predict_random_3bets():
    bets = []
    for _ in range(3):
        # Big Lotto: Just pick 6 numbers from 1-49
        nums = random.sample(range(1, 50), 6)
        bets.append({'numbers': nums})
    return bets

def run_backtest(n_periods=50, strategy='DIVERSIFIED', seed=123):
    random.seed(seed)
    np.random.seed(seed)
    
    db = DatabaseManager(os.path.join(project_root, 'lottery_api/data/lottery_v2.db'))
    # Pass seed to ensemble too
    ensemble = DiversifiedEnsemble(seed=seed)
    
    # Get all draws and sort by date ASC (Normalize date format for stable sorting)
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    all_draws = sorted(all_draws, key=lambda x: str(x.get('date', '')).replace('/', '-'))
    
    # We want the LAST n_periods of the dataset
    start_idx = len(all_draws) - n_periods
    
    results = {
        'total_cost': 0,
        'total_prize': 0,
        'total_wins': 0,
        'win_periods': 0,
        'prize_counts': Counter(),
        'prize_dist': Counter(),
        'periods': 0
    }
    
    print(f"🎬 Starting {strategy} Backtest (N={n_periods})...")
    
    for i in tqdm(range(start_idx, len(all_draws))):
        current_draw = all_draws[i]
        # History is everything BEFORE this index (Keep as ASC)
        history_before = all_draws[:i]
        
        if strategy == 'DIVERSIFIED':
            bets = ensemble.predict_3bets(history=history_before)
        else: # RANDOM
            bets = predict_random_3bets()
            
        actual_nums = json.loads(current_draw['numbers']) if isinstance(current_draw['numbers'], str) else current_draw['numbers']
        actual_special = current_draw['special']
        
        results['total_cost'] += 3 * 50
        results['periods'] += 1
        
        period_won_prize = False
        for bet_raw in bets:
            # Handle both dict and list return formats
            bet_nums = bet_raw['numbers'] if isinstance(bet_raw, dict) else bet_raw
            
            # Match calculation: actual_nums is the 6 main, actual_special is the 7th
            matched_main = len(set(bet_nums) & set(actual_nums))
            # Big Lotto Special: Is the 7th number in my pick of 6?
            matched_special = (actual_special > 0 and actual_special in bet_nums)
            
            prize = calculate_prize(matched_main, matched_special)
            results['total_prize'] += prize # Accumulate prize for the period
            
            if prize > 0:
                results['total_wins'] += 1
                period_won_prize = True

                # Categorize for prize_dist and prize_counts
                label = f"M{matched_main}{'+S' if matched_special else ''}"
                results['prize_dist'][label] += 1
                results['prize_counts'][matched_main] += 1 # Still track main matches
        
        if period_won_prize:
            results['win_periods'] += 1
                 
    results['roi'] = (results['total_prize'] - results['total_cost']) / results['total_cost']
    results['detail_prizes'] = results['prize_counts'] # Use prize_counts which tracks matched_main
    return results

def run_comprehensive_audit():
    horizons = [150, 500]
    all_audit_results = []

    print("\n" + "="*80)
    print("🚀 TARGETED SUCCESS RATE AUDIT (150 / 500 / 1500 Periods)")
    print("="*80)
    print(f"{'Horizon':<12} | {'Win Rate (3+)':<15} | {'Strategy ROI':<15} | {'Random ROI':<12} | {'Alpha'}")
    print("-" * 80)

    for h in horizons:
        # Run Strategy
        res_strat = run_backtest(h, strategy='DIVERSIFIED')
        # Run Random
        res_rand = run_backtest(h, strategy='RANDOM')
        
        win_rate_strat = (res_strat['win_periods'] / h) * 100
        win_rate_rand = (res_rand['win_periods'] / h) * 100
        
        diff = res_strat['roi'] - res_rand['roi']
        
        print(f"{h:<12} | {win_rate_strat:>12.2f}% | {res_strat['roi']:>13.2%} | {res_rand['roi']:>10.2%} | {diff:>+7.2%}")
        
        all_audit_results.append({
            'horizon': h,
            'strat': res_strat,
            'rand': res_rand
        })

    print("-" * 80)
    print("\n🏆 Detailed Success Breakdown:")
    for r in all_audit_results:
        h = r['horizon']
        s = r['strat']
        rand_res = r['rand']
        print(f"\n[ Horizon {h} ]")
        print(f"  Strategy - Total Wins: {s['total_wins']} (M3: {s['prize_dist'].get('M3', 0)}, M3+S: {s['prize_dist'].get('M3+S', 0)}, M4: {s['prize_dist'].get('M4', 0)}, M4+S: {s['prize_dist'].get('M4+S', 0)}, M2+S: {s['prize_dist'].get('M2+S', 0)})")
        print(f"  Random   - Total Wins: {rand_res['total_wins']} (M3: {rand_res['prize_dist'].get('M3', 0)}, M3+S: {rand_res['prize_dist'].get('M3+S', 0)}, M4: {rand_res['prize_dist'].get('M4', 0)}, M4+S: {rand_res['prize_dist'].get('M4+S', 0)}, M2+S: {rand_res['prize_dist'].get('M2+S', 0)})")

if __name__ == '__main__':
    run_comprehensive_audit()
