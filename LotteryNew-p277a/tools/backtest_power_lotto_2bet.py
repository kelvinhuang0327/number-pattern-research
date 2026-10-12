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
from ai_lab.scripts.power_lotto_best_2bet import PowerLottoBestOfBest2Bet

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    
    engine = UnifiedPredictionEngine()
    predictor = PowerLottoBestOfBest2Bet(engine)
    
    print("=" * 80)
    print("🔬 Power Lotto Best-of-Best 2-Bet Benchmark (Markov + Anomaly)")
    print(f"   Total draws available: {len(all_draws)}")
    print("=" * 80)
    
    periods = min(150, len(all_draws) - 50)  # Ensure enough history
    total = 0
    wins = 0
    match_dist = Counter()
    bet_wins = {'Markov': 0, 'Anomaly': 0}
    zone2_wins = 0
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        
        # Handle different data formats
        actual_nums = set(target_draw.get('numbers', target_draw.get('first_zone', [])))
        actual_z2 = target_draw.get('special', target_draw.get('second_zone'))
        
        try:
            res = predictor.predict(history, rules)
            bets = res['bets']
            names = ['Markov', 'Anomaly']
            
            round_best = 0
            hit = False
            for idx, bet_info in enumerate(bets):
                bet_nums = set(bet_info['numbers'])
                m = len(bet_nums & actual_nums)
                if m > round_best: round_best = m
                if m >= 3: 
                    hit = True
                    bet_wins[names[idx]] += 1
                    
                # Check zone 2
                if bet_info.get('special') == actual_z2:
                    zone2_wins += 1
            
            if hit: wins += 1
            match_dist[round_best] += 1
            total += 1
            
            if (i+1) % 50 == 0:
                print(f"Processed {i+1}/{periods}... Win Rate: {wins/total*100:.2f}%")
                
        except Exception as e:
            print(f"Error at {i}: {e}")
            continue

    rate = wins / total * 100 if total > 0 else 0
    z2_rate = zone2_wins / (total * 2) * 100 if total > 0 else 0  # 2 bets per round
    
    print("-" * 80)
    print(f"✅ Final Power Lotto 2-Bet Rate ({periods}期): {rate:.2f}%")
    print(f"📊 Match Distribution: M3:{match_dist[3]} M4:{match_dist[4]} M5:{match_dist[5]} M6:{match_dist[6]}")
    print(f"🎯 Zone 2 Accuracy: {z2_rate:.1f}%")
    print(f"🏆 Bet Contribution: Markov: {bet_wins['Markov']}, Anomaly: {bet_wins['Anomaly']}")
    print("=" * 80)

if __name__ == "__main__":
    main()
