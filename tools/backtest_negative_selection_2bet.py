#!/usr/bin/env python3
import os
import sys
from collections import Counter

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from ai_lab.scripts.negative_selection_predictor import NegativeSelectionPredictor

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    predictor = NegativeSelectionPredictor()
    
    print("=" * 80)
    print("🔬 Phase 34a: Negative Selection 2-Bet Benchmark (Kill-10)")
    print("=" * 80)
    
    periods = 150
    total = 0
    wins = 0
    match_dist = Counter()
    kill_success = 0  # How often kill numbers were NOT in actual draw
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            res = predictor.predict_2bets(history, rules)
            bets = res['bets']
            kill_nums = set(res.get('kill_numbers', []))
            
            # Check if kill was successful (no actual number was killed)
            killed_actual = kill_nums & actual
            if len(killed_actual) == 0:
                kill_success += 1
            
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
                print(f"Processed {i+1}/{periods}... Win Rate: {wins/total*100:.2f}%, Kill Success: {kill_success/total*100:.1f}%")
                
        except Exception as e:
            print(f"Error: {e}")
            continue

    rate = wins / total * 100 if total > 0 else 0
    kill_rate = kill_success / total * 100 if total > 0 else 0
    
    print("-" * 80)
    print(f"✅ Final Negative Selection 2-Bet Rate (150期): {rate:.2f}%")
    print(f"📊 Match Distribution: M3:{match_dist[3]} M4:{match_dist[4]} M5:{match_dist[5]} M6:{match_dist[6]}")
    print(f"🗑️ Kill Success Rate: {kill_rate:.1f}% (no actual numbers killed)")
    print("=" * 80)
    
    print("\n📊 Comparison:")
    print(f"   Negative Selection 2-Bet: {rate:.2f}%")
    print(f"   Orthogonal 2-Bet:         6.00%")
    print(f"   Improvement:              {rate - 6.0:+.2f}%")

if __name__ == "__main__":
    main()
