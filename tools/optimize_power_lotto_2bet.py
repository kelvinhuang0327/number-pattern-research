#!/usr/bin/env python3
"""
Power Lotto 2-Bet Combination Optimizer
Tests all pairs of prediction methods to find the best 2-bet combination.
"""
import os
import sys
from collections import Counter
from itertools import combinations

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine

def get_prediction(engine, method_name: str, history, rules):
    """Get prediction from a specific method."""
    methods = {
        'markov': engine.markov_predict,
        'deviation': engine.deviation_predict,
        'statistical': engine.statistical_predict,
        'trend': engine.trend_predict,
        'frequency': engine.frequency_predict,
        'bayesian': engine.bayesian_predict,
        'hot_cold_mix': engine.hot_cold_mix_predict,
    }
    
    if method_name in methods:
        result = methods[method_name](history, rules)
        return result.get('numbers', [])[:6]
    return list(range(1, 7))

def test_combination(engine, method1: str, method2: str, all_draws, rules, periods: int = 150):
    """Test a specific 2-bet combination."""
    wins = 0
    total = 0
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        
        actual = set(target_draw.get('numbers', target_draw.get('first_zone', [])))
        
        try:
            bet1 = get_prediction(engine, method1, history, rules)
            bet2 = get_prediction(engine, method2, history, rules)
            
            m1 = len(set(bet1) & actual)
            m2 = len(set(bet2) & actual)
            
            if m1 >= 3 or m2 >= 3:
                wins += 1
            total += 1
        except:
            continue
            
    return wins / total * 100 if total > 0 else 0

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    
    engine = UnifiedPredictionEngine()
    
    print("=" * 80)
    print("🔬 Power Lotto 2-Bet Combination Optimizer")
    print(f"   Testing all method pairs over 150 periods")
    print("=" * 80)
    
    methods = ['markov', 'deviation', 'statistical', 'trend', 'frequency', 'bayesian', 'hot_cold_mix']
    
    results = []
    
    for m1, m2 in combinations(methods, 2):
        print(f"Testing {m1} + {m2}...", end=" ", flush=True)
        rate = test_combination(engine, m1, m2, all_draws, rules)
        results.append((m1, m2, rate))
        print(f"{rate:.2f}%")
        
    # Sort by rate
    results.sort(key=lambda x: x[2], reverse=True)
    
    print("\n" + "=" * 80)
    print("📊 RESULTS RANKING")
    print("=" * 80)
    print(f"{'Rank':<6} {'Combination':<30} {'Match-3+ Rate':<15}")
    print("-" * 55)
    
    for i, (m1, m2, rate) in enumerate(results[:10], 1):
        marker = "⭐" if i == 1 else ""
        print(f"{i:<6} {m1} + {m2:<20} {rate:.2f}% {marker}")
        
    print("=" * 80)
    
    # Best combination
    best = results[0]
    print(f"\n🏆 Best 2-Bet Combination: {best[0]} + {best[1]} ({best[2]:.2f}%)")

if __name__ == "__main__":
    main()
