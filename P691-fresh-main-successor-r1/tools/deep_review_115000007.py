#!/usr/bin/env python3
"""
Deep Review for Big Lotto Draw 115000007
Winning Numbers: 21, 23, 32, 36, 39, 43 + 12
"""
import sys
import os
import logging
from collections import Counter
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
# Import our strategies
from tools.predict_biglotto_6bets_cluster import BigLottoClusterPivotPredictor
from tools.predict_biglotto_apriori import BigLottoAprioriPredictor

def analyze_draw():
    # 1. Setup
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws('BIG_LOTTO')
    
    # Filter history strictly BEFORE 115000007
    # Assuming the DB might have it, or not. We want to train on T-1.
    # If 115000007 is in DB, remove it and everything after.
    # The user said date is 115/01/23 (2026/01/23).
    # Let's just take the list and find the cut-off.
    
    cutoff_date = "2026-01-23" # Approximate matching
    train_history = [d for d in all_draws if d['draw'] < '115000007']
    
    actual_numbers = {21, 23, 32, 36, 39, 43}
    actual_special = 12
    
    print(f"📊 Analyzing Draw 115000007")
    print(f"   Winning Numbers: {sorted(list(actual_numbers))} + {actual_special}")
    print(f"   Training History: {len(train_history)} draws (Last: {train_history[0]['draw']})")
    print("="*60)
    
    # 2. Characteristic Analysis
    print("🔍 Feature 1: Zone Analysis")
    zones = [0]*5 # 1-10, 11-20, 21-30, 31-40, 41-49
    for n in actual_numbers:
        if 1 <= n <= 10: zones[0] += 1
        elif 11 <= n <= 20: zones[1] += 1
        elif 21 <= n <= 30: zones[2] += 1
        elif 31 <= n <= 40: zones[3] += 1
        elif 41 <= n <= 49: zones[4] += 1
    
    print(f"   Zone Check (1-10): {zones[0]}")
    print(f"   Zone Check (11-20): {zones[1]}")
    print(f"   Zone Check (21-30): {zones[2]}")
    print(f"   Zone Check (31-40): {zones[3]}")
    print(f"   Zone Check (41-49): {zones[4]}")
    
    if zones[0] == 0 and zones[1] == 0:
        print("   ⚠️ ANOMALY: 'Small Numbers' (1-20) Completely Missing!")
        
    print("\n🔍 Feature 2: High/Low Ratio (Pivot 25)")
    high = len([n for n in actual_numbers if n > 25])
    low = 6 - high
    print(f"   High(>25): {high}, Low(<=25): {low} (Normal is 3:3 or 4:2)")
    
    # 3. Strategy Benchmark
    print("\n⚔️ Strategy Showdown")
    
    # 3.1 Cluster Pivot
    cp = BigLottoClusterPivotPredictor()
    # Mocking the get_draws to return our train_history
    cp.get_draws = lambda: train_history 
    cp_bets = cp.generate_bets(num_bets=7, window=150)
    
    best_cp = 0
    best_cp_bet = []
    print("\n   [Cluster Pivot Results]")
    for i, bet in enumerate(cp_bets):
        match = len(set(bet['numbers']) & actual_numbers)
        print(f"     Bet {i+1} (Anchor {bet['anchor']}): {match} Matches {set(bet['numbers']) & actual_numbers}")
        if match > best_cp:
            best_cp = match
            best_cp_bet = bet['numbers']
            
    # 3.2 Apriori
    ap = BigLottoAprioriPredictor()
    ap.get_draws = lambda: train_history
    ap_bets = ap.predict_next_draw(num_bets=7, window=150)
    
    best_ap = 0
    print("\n   [Apriori Results]")
    for i, bet in enumerate(ap_bets):
        match = len(set(bet['numbers']) & actual_numbers)
        print(f"     Bet {i+1} [Rules]: {match} Matches {set(bet['numbers']) & actual_numbers}")
        if match > best_ap:
            best_ap = match

    # 3.3 Frequency (Baseline)
    last_100 = train_history[:100]
    freq = Counter()
    for d in last_100:
        for n in d['numbers']: freq[n] += 1
    hot_10 = [n for n, _ in freq.most_common(10)]
    cold_10 = [n for n, _ in freq.most_common()[:-11:-1]]
    
    print("\n   [Baseline Stats]")
    match_hot = len(set(hot_10) & actual_numbers)
    match_cold = len(set(cold_10) & actual_numbers)
    print(f"     Hot Top 10 Match: {match_hot} {set(hot_10) & actual_numbers}")
    print(f"     Cold Top 10 Match: {match_cold} {set(cold_10) & actual_numbers}")
    
    # 4. Conclusion
    print("\n" + "="*60)
    print("📋 AUTO-DIAGNOSIS")
    if best_cp > best_ap:
        print(f"   🏆 Winner: Cluster Pivot (Max Match {best_cp})")
    elif best_ap > best_cp:
        print(f"   🏆 Winner: Apriori (Max Match {best_ap})")
    else:
        print(f"   🤝 Draw (Max Match {best_cp})")
        
    if zones[0]+zones[1] == 0:
        print("   ❌ Failure Cause: Strategy likely balanced zone distribution, but this draw had Zero small numbers.")

if __name__ == '__main__':
    analyze_draw()
