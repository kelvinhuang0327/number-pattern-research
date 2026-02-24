#!/usr/bin/env python3
"""
Power Lotto Zonal Entropy Predictor (Scientific Version)
========================================================
Logic:
1. Divide 1-38 range into 6 zones.
2. Calculate the Entropy (Information Density) of recent draws.
3. If Entropy is LOW (Predictable): Focus on Cluster Reinforcement.
4. If Entropy is HIGH (Chaotic): Focus on Gap Reversion (Cold numbers).
"""
import os
import sys
import math
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules

def calculate_entropy(draws, num_zones=6):
    max_num = 38
    zone_size = max_num / num_zones
    counts = [0] * num_zones
    
    total_nums = 0
    for d in draws:
        for n in d['numbers']:
            z_idx = min(int((n-1) / zone_size), num_zones - 1)
            counts[z_idx] += 1
            total_nums += 1
            
    if total_nums == 0: return 0
    
    probs = [c/total_nums for c in counts if c > 0]
    entropy = -sum(p * math.log2(p) for p in probs)
    return entropy

def entropy_predict(history, n_bets=2):
    rules = get_lottery_rules('POWER_LOTTO')
    recent_30 = history[:30]
    entropy = calculate_entropy(recent_30)
    
    # Max entropy for 6 zones is log2(6) approx 2.58
    is_chaotic = entropy > 2.2
    
    print(f"📊 Current Zonal Entropy (30 periods): {entropy:.4f} ({'CHAOTIC' if is_chaotic else 'STABLE'})")
    
    # Selection Logic
    all_recent_nums = [n for d in history[:100] for n in d['numbers']]
    freq = Counter(all_recent_nums)
    
    if is_chaotic:
        # Chaotic: Pick numbers from zones that are OVERDUE (Cold/Gap)
        # Sort by frequency ASC (Coldest first)
        candidates = sorted(range(1, 39), key=lambda x: freq.get(x, 0))
    else:
        # Stable: Pick numbers from zones that are TRENDING (Hot)
        # Sort by frequency DESC (Hottest first)
        candidates = sorted(range(1, 39), key=lambda x: freq.get(x, 0), reverse=True)
        
    bets = []
    for i in range(n_bets):
        # Add some randomness/offset for diversity
        start = i * 6
        bets.append(sorted(candidates[start:start+6]))
        
    return bets

def main():
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws('POWER_LOTTO')
    
    print("\n" + "╔" + "═"*68 + "╗")
    print("║" + " "*18 + "✨ POWER LOTTO ZONAL ENTROPY ENGINE ✨" + " " * 18 + "║")
    print("╚" + "═"*68 + "╝")
    
    bets = entropy_predict(history)
    
    for i, bet in enumerate(bets):
        print(f"注 {i+1}: {bet} | 策略: {'趨勢追蹤' if not (calculate_entropy(history[:30]) > 2.2) else '均值回歸'}")

if __name__ == "__main__":
    main()
