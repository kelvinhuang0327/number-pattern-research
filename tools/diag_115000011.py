#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
import random
import numpy as np
from collections import Counter
from typing import List, Dict

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

# Import methods from existing benchmark if possible, 
# but for speed and reliability I'll redefine them or import specifically.
from tools.exhaustive_nbet_benchmark import (
    method_frequency_hot, method_frequency_cold, method_gap_pressure,
    method_markov_transition, method_zone_balance, method_odd_even_balance,
    method_sum_optimal, method_clustering_centroid, method_entropy_max,
    method_anti_repeat, method_tail_pattern, method_hybrid_hot_cold
)
from tools.advanced_methods_benchmark import (
    ContextualBandit, CopulaAnalyzer, AnomalyDetector, 
    GraphCooccurrence, AttentionScorer
)

def load_history_up_to(lottery_type: str, target_draw: str) -> List[Dict]:
    db_path = os.path.join(project_root, 'lottery_api/data/lottery_v2.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, numbers, special, date FROM draws 
        WHERE lottery_type = ? AND CAST(draw AS INTEGER) < CAST(? AS INTEGER)
        ORDER BY draw DESC
    """, (lottery_type, target_draw))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for r in rows:
        nums = json.loads(r[1]) if isinstance(r[1], str) else []
        special = r[2]
        history.append({
            'draw': r[0], 
            'numbers': nums, 
            'special': int(special) if special else None,
            'date': r[3]
        })
    return history

def get_actual_draw(lottery_type: str, target_draw: str) -> Dict:
    db_path = os.path.join(project_root, 'lottery_api/data/lottery_v2.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT numbers, special FROM draws 
        WHERE lottery_type = ? AND draw = ?
    """, (lottery_type, target_draw))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {'numbers': json.loads(row[0]), 'special': row[1]}
    return None

def analyze_win_features(nums: List[int], special: int):
    print("\n--- Draw Features Analysis ---")
    print(f"Numbers: {nums} | Special: {special}")
    print(f"Sum: {sum(nums)}")
    print(f"Parity (Odd:Even): {sum(1 for n in nums if n%2==1)}:{sum(1 for n in nums if n%2==0)}")
    print(f"Zones (1-10, 11-20, 21-30, 31-38): "
          f"{sum(1 for n in nums if 1<=n<=10)}, "
          f"{sum(1 for n in nums if 11<=n<=20)}, "
          f"{sum(1 for n in nums if 21<=n<=30)}, "
          f"{sum(1 for n in nums if 31<=n<=38)}")
    
    # Calculate Mean and Max
    print(f"Min: {min(nums)} | Max: {max(nums)} | Mean: {sum(nums)/6:.2f}")
    
    # Gaps between numbers
    sorted_nums = sorted(nums)
    gaps = [sorted_nums[i+1] - sorted_nums[i] for i in range(len(sorted_nums)-1)]
    print(f"Internal Gaps: {gaps}")
    
    # Check for consecutive pairs
    consecutive = sum(1 for i in range(len(sorted_nums)-1) if sorted_nums[i+1] - sorted_nums[i] == 1)
    print(f"Consecutive Pairs: {consecutive}")

def run_diagnostic():
    target_draw = "115000011"
    lottery_type = "POWER_LOTTO"
    max_num = 38
    
    actual = get_actual_draw(lottery_type, target_draw)
    if not actual:
        print(f"Error: Draw {target_draw} not found.")
        return
    
    target_nums = set(actual['numbers'])
    target_special = actual['special']
    
    history = load_history_up_to(lottery_type, target_draw)
    print(f"Loaded {len(history)} historical draws up to {target_draw}.")
    
    analyze_win_features(actual['numbers'], target_special)
    
    # Methods to test
    methods = {
        'Frequency Hot': lambda h: method_frequency_hot(h, max_num),
        'Frequency Cold': lambda h: method_frequency_cold(h, max_num),
        'Gap Pressure': lambda h: method_gap_pressure(h, max_num),
        'Markov Transition': lambda h: method_markov_transition(h, max_num),
        'Zone Balance': lambda h: method_zone_balance(h, max_num),
        'Odd-Even Balance': lambda h: method_odd_even_balance(h, max_num),
        'Sum Optimal': lambda h: method_sum_optimal(h, max_num),
        'Clustering Centroid': lambda h: method_clustering_centroid(h, max_num),
        'Entropy Max': lambda h: method_entropy_max(h, max_num),
        'Anti-Repeat': lambda h: method_anti_repeat(h, max_num),
        'Tail Pattern': lambda h: method_tail_pattern(h, max_num),
        'Hybrid Hot-Cold': lambda h: method_hybrid_hot_cold(h, max_num),
    }
    
    # Advanced Methods
    print("\nTraining Advanced Methods...")
    adv_methods = {
         'Contextual Bandit': ContextualBandit(max_num),
         'Copula Analysis': CopulaAnalyzer(max_num),
         'Anomaly Detection': AnomalyDetector(max_num),
         'Graph PageRank': GraphCooccurrence(max_num),
         'Attention Scorer': AttentionScorer(max_num),
    }
    
    for name, method in adv_methods.items():
        if hasattr(method, 'train'):
            method.train(history)
            
    # Evaluation
    results = []
    
    print("\n--- Method Evaluation for Draw 115000011 ---")
    print(f"{'Method Name':<20} | {'Matches':<8} | {'Predicted Numbers'}")
    print("-" * 60)
    
    for name, func in methods.items():
        pred = func(history)
        matches = len(set(pred) & target_nums)
        results.append({'name': name, 'matches': matches, 'pred': pred})
        print(f"{name:<20} | {matches:<8} | {pred}")
        
    for name, method in adv_methods.items():
        pred = method.predict(history, 6)
        matches = len(set(pred) & target_nums)
        results.append({'name': name, 'matches': matches, 'pred': pred})
        print(f"{name:<20} | {matches:<8} | {pred}")
        
    # Find Best
    results.sort(key=lambda x: x['matches'], reverse=True)
    best = results[0]
    print(f"\nWinning Method: {best['name']} with {best['matches']} matches.")

    # Special Number Prediction
    print("\n--- Special Number (Zone 2) Analysis ---")
    special_freq = Counter()
    for d in history[:100]:
        special_freq[d['special']] += 1
    top_special = special_freq.most_common(3)
    print(f"Recent Hot Special Numbers: {top_special}")
    print(f"Actual Special Number: {target_special}")
    
    # ROI Feasibility for 2 or 3 bets
    print("\n--- Multi-Bet Feasibility ---")
    # Simulate an ensemble of top 3 methods
    top_3_preds = [r['pred'] for r in results[:3]]
    combined_matches = len(set().union(*[set(p) for p in top_3_preds]) & target_nums)
    print(f"Top 3 Methods Ensemble Coverage (18 numbers): {combined_matches}/6 matches.")

if __name__ == "__main__":
    run_diagnostic()
