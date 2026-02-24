#!/usr/bin/env python3
import os
import sys
from collections import Counter

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from ai_lab.scripts.conditional_probability_predictor import ConditionalProbabilityPredictor

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    predictor = ConditionalProbabilityPredictor()
    
    print("=" * 80)
    print("🔬 Phase 34b: Conditional Probability 2-Bet Benchmark")
    print("=" * 80)
    
    periods = 150
    total = 0
    wins = 0
    match_dist = Counter()
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            res = predictor.predict_2bets(history, rules)
            bets = res['bets']
            
            round_best = 0
            hit = False
            for bet in bets:
                m = len(set(bet) & actual)
                if m > round_best: round_best = m
                if m >= 3: hit = True
            
            if hit: wins += 1
            match_dist[round_best] += 1
            total += 1
            
            if (i+1) % 50 == 0:
                print(f"Processed {i+1}/{periods}... Win Rate: {wins/total*100:.2f}%")
                
        except Exception as e:
            print(f"Error: {e}")
            continue

    rate = wins / total * 100 if total > 0 else 0
    
    print("-" * 80)
    print(f"✅ Final Conditional Probability 2-Bet Rate (150期): {rate:.2f}%")
    print(f"📊 Match Distribution: M3:{match_dist[3]} M4:{match_dist[4]} M5:{match_dist[5]} M6:{match_dist[6]}")
    print("=" * 80)
    
    print("\n📊 Comparison:")
    print(f"   Conditional Prob 2-Bet: {rate:.2f}%")
    print(f"   Orthogonal 2-Bet:       6.00%")
    print(f"   Negative Selection:     5.33%")

if __name__ == "__main__":
    main()
