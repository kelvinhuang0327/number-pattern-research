#!/usr/bin/env python3
"""
Comprehensive Power Lotto 2-Bet Optimization
Tests all combinations including optimized Trend (λ=0.15).
"""
import os
import sys
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine

class OptimizedTrend:
    """Trend with λ=0.15 for high-prize focus."""
    def predict(self, history, rules):
        pick_count = rules.get('pickCount', 6)
        max_num = rules.get('maxNumber', 38)
        min_num = rules.get('minNumber', 1)
        
        weighted_freq = defaultdict(float)
        for i, draw in enumerate(reversed(history)):
            weight = np.exp(-0.15 * i)
            nums = draw.get('numbers', draw.get('first_zone', []))
            for num in nums:
                weighted_freq[num] += weight
        
        total = sum(weighted_freq.values())
        probs = {n: weighted_freq.get(n, 0) / total for n in range(min_num, max_num + 1)}
        sorted_nums = sorted(probs.items(), key=lambda x: x[1], reverse=True)
        return {'numbers': sorted([n for n, _ in sorted_nums[:pick_count]])}

def get_prediction(engine, method_name, history, rules, optimized_trend=None):
    if method_name == 'trend_optimized':
        return optimized_trend.predict(history, rules)['numbers']
    
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
        return methods[method_name](history, rules)['numbers'][:6]
    return list(range(1, 7))

def test_combination(engine, m1, m2, all_draws, rules, periods=150, optimized_trend=None):
    wins = 0
    m4_plus = 0
    total = 0
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw.get('numbers', target_draw.get('first_zone', [])))
        
        try:
            bet1 = get_prediction(engine, m1, history, rules, optimized_trend)
            bet2 = get_prediction(engine, m2, history, rules, optimized_trend)
            
            match1 = len(set(bet1) & actual)
            match2 = len(set(bet2) & actual)
            best = max(match1, match2)
            
            if best >= 3: wins += 1
            if best >= 4: m4_plus += 1
            total += 1
        except:
            continue
    
    win_rate = wins / total * 100 if total > 0 else 0
    m4_rate = m4_plus / total * 100 if total > 0 else 0
    return win_rate, m4_plus, m4_rate

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    
    engine = UnifiedPredictionEngine()
    optimized_trend = OptimizedTrend()
    
    print("=" * 80)
    print("🔬 Power Lotto Comprehensive 2-Bet Optimization")
    print("   Including optimized Trend (λ=0.15) for high prizes")
    print("=" * 80)
    
    methods = ['markov', 'deviation', 'statistical', 'trend', 'frequency', 
               'bayesian', 'hot_cold_mix', 'trend_optimized']
    
    results = []
    
    for m1, m2 in combinations(methods, 2):
        print(f"Testing {m1} + {m2}...", end=" ", flush=True)
        win_rate, m4_count, m4_rate = test_combination(
            engine, m1, m2, all_draws, rules, optimized_trend=optimized_trend
        )
        results.append((m1, m2, win_rate, m4_count, m4_rate))
        print(f"M3+: {win_rate:.2f}%, M4+: {m4_count}")
    
    # Sort by Match-3+ rate
    results.sort(key=lambda x: x[2], reverse=True)
    
    print("\n" + "=" * 80)
    print("📊 TOP 10 COMBINATIONS (Sorted by Match-3+ Rate)")
    print("=" * 80)
    print(f"{'Rank':<5} {'Combination':<35} {'M3+ Rate':<12} {'M4+ Count':<10}")
    print("-" * 65)
    
    for i, (m1, m2, rate, m4, m4_rate) in enumerate(results[:10], 1):
        marker = "⭐" if i == 1 else ""
        print(f"{i:<5} {m1} + {m2:<20} {rate:.2f}%{marker:<8} {m4}")
    
    # Also sort by Match-4+ for high prize ranking
    results_m4 = sorted(results, key=lambda x: x[3], reverse=True)
    
    print("\n" + "=" * 80)
    print("🏆 TOP 5 FOR HIGH PRIZES (Sorted by Match-4+ Count)")
    print("=" * 80)
    for i, (m1, m2, rate, m4, m4_rate) in enumerate(results_m4[:5], 1):
        marker = "⭐" if m4 > 0 else ""
        print(f"{i}. {m1} + {m2}: M4+={m4} {marker}, M3+={rate:.2f}%")
    
    print("\n" + "=" * 80)
    best = results[0]
    print(f"🏆 Best Overall: {best[0]} + {best[1]} ({best[2]:.2f}% M3+, {best[3]} M4+)")
    print("=" * 80)

if __name__ == "__main__":
    main()
