#!/usr/bin/env python3
"""
Backtest Power Lotto Grand Slam Strategy (150 Periods)
======================================================
Evaluates the "Grand Slam" 3-Bet strategy over the last 150 draws.

Strategy:
1. Bet 1: Alpha (True Freq) Top 1-6
2. Bet 2: Alpha (True Freq) Top 7-12
3. Bet 3: Beta (Deviation) Top 1-6
Special: Best Single Prediction (Markov/Freq Mix)

Metrics:
- Jackpot Capture Rate (Combined Pool of ~18 numbers containing 6 winning numbers)
- Win Rate per Bet (Match 3+, Match 4+, etc.)
- Special Number Accuracy
"""
import sys
import os
import json
import logging
import numpy as np
from tqdm import tqdm
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.unified_predictor import UnifiedPredictionEngine, predict_pool_numbers

def calculate_prize(hits, special_hit):
    # Simplified Power Lotto Prize Structure
    # Ref: https://www.taiwanlottery.com.tw/SuperLotto638/index.asp
    if hits == 6 and special_hit: return "Jackpot" # 頭獎
    if hits == 6: return "2nd Prize" # 貳獎
    if hits == 5 and special_hit: return "3rd Prize" # 參獎
    if hits == 5: return "4th Prize" # 肆獎
    if hits == 4 and special_hit: return "5th Prize" # 伍獎
    if hits == 4: return "6th Prize" # 陸獎
    if hits == 3 and special_hit: return "7th Prize" # 柒獎
    if hits == 2 and special_hit: return "8th Prize" # 捌獎 (2+1)
    if hits == 3: return "9th Prize" # 玖獎 (3+0)
    if hits == 1 and special_hit: return "10th Prize" # 普獎 (1+1)
    return "Loss"

def main():
    print("=" * 60)
    print("📉 Backtesting Grand Slam Strategy (Last 150 Draws)")
    print("=" * 60)
    
    # 1. Load Data
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    if len(all_history) < 200:
        print("❌ Not enough history.")
        return
        
    # Ensure sorted Old -> New for slicing, then we iterate
    # But get_all_draws returns New -> Old (date DESC)
    # Let's keep it New -> Old so history[0] is latest
    # The "Test Set" is history[0:150]
    # For each i in 0..149:
    #   Target: history[i]
    #   Training Data: history[i+1:] (All older draws)
    
    test_count = 150
    test_set = all_history[:test_count]
    
    engine = UnifiedPredictionEngine()
    rules = get_lottery_rules('POWER_LOTTO')
    
    results = {
        'combined_6_hits': 0,
        'combined_5_hits': 0,
        'combined_4_hits': 0,
        'bet_wins': {'Bet1': 0, 'Bet2': 0, 'Bet3': 0},
        'special_hits': 0,
        'prizes': Counter()
    }
    
    full_capture_draws = []
    
    print(f"Running backtest on {test_count} periods...")
    
    for i in tqdm(range(test_count)):
        target_draw = all_history[i]
        train_history = all_history[i+1:] # Future looking back
        
        # Ground Truth
        actual_nums = set(target_draw['numbers'])
        actual_special = target_draw['special']
        
        # --- PREDICTION LOGIC ---
        
        # 1. Alpha (True Freq)
        rules['pickCount'] = 12
        rules['frequency_window'] = 50
        pred_alpha = engine.true_frequency_predict(train_history, rules)
        alpha_list = pred_alpha['ranked_list'] 
        if len(alpha_list) < 12: alpha_list = alpha_list + [0]*(12-len(alpha_list))
        
        bet1 = sorted(alpha_list[:6])    # Top 1-6
        bet2 = sorted(alpha_list[6:12])  # Top 7-12
        
        # 2. Beta (Deviation)
        rules['pickCount'] = 6
        pred_beta = engine.deviation_predict(train_history, rules)
        bet3 = sorted(pred_beta['numbers'])
        
        # 3. Special
        # Simple strategy: Mix Markov and Freq
        # Since we want speed, let's just use Freq(50) Top 1 for this backtest
        # As checking Markov 150 times is slower and Freq caught 06 anyway
        special_hist = [{'numbers': [d['special']]} for d in train_history if d.get('special')]
        tf_special = engine.true_frequency_predict(special_hist, {'pickCount': 1, 'frequency_window': 50})
        pred_special = tf_special['ranked_list'][0] if tf_special['ranked_list'] else 1
        
        # --- EVALUATION ---
        
        bets = [('Bet1', bet1), ('Bet2', bet2), ('Bet3', bet3)]
        special_hit = (pred_special == actual_special)
        if special_hit: results['special_hits'] += 1
        
        # 1. Combined Coverage
        combined_pool = set(bet1) | set(bet2) | set(bet3)
        combined_hits = len(combined_pool & actual_nums)
        
        if combined_hits == 6: results['combined_6_hits'] += 1
        if combined_hits >= 5: results['combined_5_hits'] += 1
        if combined_hits >= 4: results['combined_4_hits'] += 1
        
        if combined_hits == 6 and special_hit:
            full_capture_draws.append(target_draw['draw'])
            
        # 2. Individual Bet Performance
        for b_name, b_nums in bets:
            hits = len(set(b_nums) & actual_nums)
            prize = calculate_prize(hits, special_hit)
            
            if prize != "Loss":
                results['bet_wins'][b_name] += 1
                results['prizes'][prize] += 1
                
    # --- REPORTING ---
    print("\n" + "=" * 60)
    print("📊 Backtest Results (150 Periods)")
    print("=" * 60)
    
    print(f"Jackpot Capture Rate (Pool Covers 6+1): {len(full_capture_draws)} / {test_count} ({len(full_capture_draws)/test_count:.2%})")
    print(f"Pool Covers 6 Main Numbers:             {results['combined_6_hits']} / {test_count} ({results['combined_6_hits']/test_count:.2%})")
    print(f"Pool Covers 5+ Main Numbers:            {results['combined_5_hits']} / {test_count} ({results['combined_5_hits']/test_count:.2%})")
    print(f"Special Number Accuracy:                {results['special_hits']} / {test_count} ({results['special_hits']/test_count:.2%})")
    
    if full_capture_draws:
        print(f"🔥 Full Capture Draws: {full_capture_draws}")
    
    print("\n💰 Prize Distribution (Total Per Bet)")
    for prize, count in results['prizes'].most_common():
        print(f"   {prize:<10}: {count}")
        
    print("\n🏆 Win Rate Per Bet (Any Prize)")
    for b_name, wins in results['bet_wins'].items():
        print(f"   {b_name}: {wins} wins ({wins/test_count:.2%})")

if __name__ == '__main__':
    main()
