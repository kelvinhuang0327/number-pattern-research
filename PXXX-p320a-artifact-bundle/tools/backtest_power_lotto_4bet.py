#!/usr/bin/env python3
import os
import sys
from collections import Counter

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    
    engine = UnifiedPredictionEngine()
    
    print("=" * 80)
    print("🔬 Power Lotto 4-Bet Benchmark (Top 4 Methods)")
    print("   Methods: Statistical, Frequency, Deviation, Markov")
    print("=" * 80)
    
    periods = 150
    total = 0
    wins = 0
    match_dist = Counter()
    method_wins = {'Statistical': 0, 'Frequency': 0, 'Deviation': 0, 'Markov': 0}
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        
        actual = set(target_draw.get('numbers', target_draw.get('first_zone', [])))
        
        try:
            # 4 bets from top methods
            bets = []
            bets.append(('Statistical', engine.statistical_predict(history, rules)['numbers'][:6]))
            bets.append(('Frequency', engine.frequency_predict(history, rules)['numbers'][:6]))
            bets.append(('Deviation', engine.deviation_predict(history, rules)['numbers'][:6]))
            bets.append(('Markov', engine.markov_predict(history, rules)['numbers'][:6]))
            
            round_best = 0
            hit = False
            for name, bet in bets:
                m = len(set(bet) & actual)
                if m > round_best: round_best = m
                if m >= 3: 
                    hit = True
                    method_wins[name] += 1
            
            if hit: wins += 1
            match_dist[round_best] += 1
            total += 1
            
            if (i+1) % 50 == 0:
                print(f"Processed {i+1}/{periods}... Win Rate: {wins/total*100:.2f}%")
                
        except Exception as e:
            continue

    rate = wins / total * 100 if total > 0 else 0
    
    print("-" * 80)
    print(f"✅ Final 4-Bet Rate (150期): {rate:.2f}%")
    print(f"📊 Match Distribution: M3:{match_dist[3]} M4:{match_dist[4]} M5:{match_dist[5]} M6:{match_dist[6]}")
    print(f"🏆 Method Contribution:")
    for k, v in method_wins.items():
        print(f"  {k}: {v} wins")
    print("=" * 80)

if __name__ == "__main__":
    main()
