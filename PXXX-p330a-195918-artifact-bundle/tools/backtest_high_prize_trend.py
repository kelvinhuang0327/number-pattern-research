#!/usr/bin/env python3
import os
import sys
import numpy as np
from collections import Counter, defaultdict

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules

class HighPrizeTrend:
    def __init__(self, lambda_val=0.15):
        self.lambda_val = lambda_val
        
    def predict(self, history, rules):
        pick_count = rules.get('pickCount', 6)
        max_num = rules.get('maxNumber', 38)
        min_num = rules.get('minNumber', 1)
        
        weighted_freq = defaultdict(float)
        
        for i, draw in enumerate(reversed(history)):
            weight = np.exp(-self.lambda_val * i)
            nums = draw.get('numbers', draw.get('first_zone', []))
            for num in nums:
                weighted_freq[num] += weight
                
        total = sum(weighted_freq.values())
        probs = {n: weighted_freq.get(n, 0) / total for n in range(min_num, max_num + 1)}
        
        sorted_nums = sorted(probs.items(), key=lambda x: x[1], reverse=True)
        return sorted([n for n, _ in sorted_nums[:pick_count]])

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    
    print("=" * 80)
    print("🔬 High Prize Trend 2-Bet Benchmark (λ=0.15 + λ=0.05)")
    print("=" * 80)
    
    t1 = HighPrizeTrend(lambda_val=0.15)  # Optimized for Match-4+
    t2 = HighPrizeTrend(lambda_val=0.05)  # Standard (hit Match-5)
    
    periods = 150
    total = 0
    wins = 0
    match_dist = Counter()
    bet_wins = {'λ=0.15': 0, 'λ=0.05': 0}
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw.get('numbers', target_draw.get('first_zone', [])))
        
        bet1 = t1.predict(history, rules)
        bet2 = t2.predict(history, rules)
        
        round_best = 0
        hit = False
        
        m1 = len(set(bet1) & actual)
        m2 = len(set(bet2) & actual)
        
        if m1 > round_best: round_best = m1
        if m2 > round_best: round_best = m2
        
        if m1 >= 3: 
            hit = True
            bet_wins['λ=0.15'] += 1
        if m2 >= 3: 
            hit = True
            bet_wins['λ=0.05'] += 1
            
        if hit: wins += 1
        match_dist[round_best] += 1
        total += 1
        
        if (i+1) % 50 == 0:
            print(f"Processed {i+1}/{periods}... Win Rate: {wins/total*100:.2f}%")
    
    rate = wins / total * 100 if total > 0 else 0
    
    print("-" * 80)
    print(f"✅ Final High Prize Trend 2-Bet Rate (150期): {rate:.2f}%")
    print(f"📊 Match Distribution: M3:{match_dist[3]} M4:{match_dist[4]} M5:{match_dist[5]} M6:{match_dist[6]}")
    print(f"🏆 Bet Contribution: λ=0.15: {bet_wins['λ=0.15']}, λ=0.05: {bet_wins['λ=0.05']}")
    print("=" * 80)
    print(f"\n📊 Comparison:")
    print(f"   High Prize Trend 2-Bet: {rate:.2f}%")
    print(f"   Statistical + Frequency: 10.67% (previous best)")

if __name__ == "__main__":
    main()
