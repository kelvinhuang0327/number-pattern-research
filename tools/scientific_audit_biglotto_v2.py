#!/usr/bin/env python3
"""
Phase 70: Rigorous Big Lotto Strategy Audit v2
Benchmarking existing advanced strategies against random baseline.
"""

import sys
import os
import json
import sqlite3
import numpy as np
from collections import Counter
from scipy.stats import binomtest
import logging
from typing import List, Dict

# Ensure project root is in path
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer
from lottery_api.common import get_lottery_rules
from tools.backtest_cluster_pivot_biglotto import cluster_pivot_3bet
from tools.biglotto_triple_strike import fourier_rhythm_bet, cold_numbers_bet, tail_balance_bet

logging.basicConfig(level=logging.ERROR) # Lower log level for clean output

def load_history(max_records: int = 1500) -> List[Dict]:
    db_path = os.path.join(project_root, 'lottery_api/data/lottery_v2.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, numbers, date FROM draws 
        WHERE lottery_type = 'BIG_LOTTO' 
        ORDER BY draw DESC LIMIT ?
    """, (max_records,))
    rows = cursor.fetchall()
    conn.close()
    history = []
    for r in rows:
        nums = json.loads(r[1]) if isinstance(r[1], str) else []
        if len(nums) == 6:
            history.append({'draw': r[0], 'numbers': nums, 'date': r[2]})
    return history

def triple_strike_logic(history):
    # Reverse history for the functions which expect newest at the end (or as specified)
    # Most existing tools expect history in date order ASC
    h_asc = sorted(history, key=lambda x: x['draw'])
    b1 = fourier_rhythm_bet(h_asc)
    b2 = cold_numbers_bet(h_asc, exclude=set(b1))
    b3 = tail_balance_bet(h_asc, exclude=set(b1)|set(b2))
    return [b1, b2, b3]

def run_audit(periods: int = 500):
    print("=" * 80)
    print(f"🔬 BIG LOTTO RIGOROUS AUDIT (v2) - {periods} PERIODS")
    print("=" * 80)
    
    all_history = load_history(periods + 500)
    print(f"Loaded {len(all_history)} draws.")
    
    baseline_1bet = 0.018638
    baseline_3bet = 1 - (1 - baseline_1bet)**3 # ~5.48%
    
    strategies = {
        'Cluster Pivot (3-bet)': cluster_pivot_3bet,
        'Triple Strike (3-bet)': triple_strike_logic,
        'Tri-Core Ortho (3-bet)': None # Will implement using MultiBetOptimizer
    }
    
    optimizer = MultiBetOptimizer()
    rules = get_lottery_rules('BIG_LOTTO')
    
    results = {name: {'hits': 0, 'sessions': 0} for name in strategies}
    
    # Run audit
    for i in range(periods):
        # We need newest at end for history passed to some tools, 
        # but history in desc order for others. 
        # Standardizing: all_history[i+1:] is the context (desc order, newest at start)
        context = all_history[i+1:]
        target = set(all_history[i]['numbers'])
        
        for name in strategies:
            if name == 'Tri-Core Ortho (3-bet)':
                # Tri-Core needs history as List[Dict] newest-first
                try:
                    res = optimizer.generate_tri_core_3bets(context, rules, {}, num_bets=3)
                    bets = [b['numbers'] for b in res['bets']]
                except:
                    continue
            else:
                try:
                    # These tools expect newest-first or handle it internally
                    bets = strategies[name](context)
                except:
                    continue
            
            if not bets: continue
            
            results[name]['sessions'] += 1
            is_win = False
            for bet in bets:
                if len(set(bet) & target) >= 3:
                    is_win = True
                    break
            if is_win:
                results[name]['hits'] += 1
                
        if (i+1) % 100 == 0:
            print(f"Progress: {i+1}/{periods}...")

    print("\n" + "=" * 80)
    print(f"{'Strategy':<25} {'Hits':<8} {'Rate':<10} {'Edge':<10} {'p-value':<10}")
    print("-" * 80)
    
    for name, data in results.items():
        hits = data['hits']
        total = data['sessions']
        if total == 0: continue
        rate = hits / total
        edge = (rate - baseline_3bet) * 100
        p = binomtest(hits, total, baseline_3bet, alternative='greater').pvalue
        
        status = "✅" if p < 0.05 and edge > 2.0 else ("⚠️" if p < 0.05 else "❌")
        print(f"{status} {name:<23} {hits:<8} {rate*100:6.2f}% {edge:+6.2f}% {p:8.4f}")

    print("=" * 80)
    print("Baseline (3-bet M3+): 5.48%")
    print("=" * 80)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--periods', type=int, default=500)
    args = parser.parse_args()
    run_audit(args.periods)
