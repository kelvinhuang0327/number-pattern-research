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
from ai_lab.adapter import AIAdapter
from ai_lab.scripts.forced_orthogonal_2bet import ForcedOrthogonal2Bet

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    engine = UnifiedPredictionEngine()
    ai_adapter = AIAdapter()
    predictor = ForcedOrthogonal2Bet(engine, ai_adapter)
    
    print("=" * 80)
    print("🔬 Phase 33: Forced Orthogonal 2-Bet Benchmark")
    print("   Goal: Maximize 2-bet coverage, evaluate achievable success rate")
    print("=" * 80)
    
    periods = 150
    total = 0
    wins = 0
    match_dist = Counter()
    bet_wins = {'Bet1': 0, 'Bet2': 0}
    total_coverage = 0
    total_overlap = 0
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            res = predictor.predict(history, rules)
            bets = res['bets']
            
            total_coverage += res.get('coverage', 12)
            total_overlap += res.get('overlap', 0)
            
            round_best = 0
            hit = False
            for idx, bet in enumerate(bets):
                m = len(set(bet) & actual)
                if m > round_best: round_best = m
                if m >= 3: 
                    hit = True
                    bet_wins[f'Bet{idx+1}'] += 1
            
            if hit: wins += 1
            match_dist[round_best] += 1
            total += 1
            
            if (i+1) % 50 == 0:
                print(f"Processed {i+1}/{periods}... Current Win Rate: {wins/total*100:.2f}%")
                
        except Exception as e:
            print(f"Error: {e}")
            continue

    rate = wins / total * 100 if total > 0 else 0
    avg_coverage = total_coverage / total if total > 0 else 0
    avg_overlap = total_overlap / total if total > 0 else 0
    
    print("-" * 80)
    print(f"✅ Final Forced Orthogonal 2-Bet Rate (150期): {rate:.2f}%")
    print(f"📊 Match Distribution: M3:{match_dist[3]} M4:{match_dist[4]} M5:{match_dist[5]} M6:{match_dist[6]}")
    print(f"📈 Average Coverage: {avg_coverage:.1f} unique numbers (max 12)")
    print(f"🔗 Average Overlap: {avg_overlap:.1f} numbers")
    print("🏆 Bet Contribution:")
    for k, v in bet_wins.items():
        print(f"  {k}: {v} wins")
    print("=" * 80)
    
    # Compare theoretical
    print("\n📊 Comparison:")
    print(f"   2-Bet Orthogonal: {rate:.2f}%")
    print(f"   Single Bet Best:  3.50%")
    print(f"   Theoretical 2x:   7.00%")
    print(f"   Target 33%:       {'✅' if rate >= 33 else '❌'} ({rate/33*100:.0f}% of goal)")

if __name__ == "__main__":
    main()
