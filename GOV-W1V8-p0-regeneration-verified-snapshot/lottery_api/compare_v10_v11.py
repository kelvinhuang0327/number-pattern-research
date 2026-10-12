#!/usr/bin/env python3
import sys
import os
import json
from tqdm import tqdm

# Setup path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.multi_bet_optimizer import MultiBetOptimizer
from models.unified_predictor import UnifiedPredictionEngine
from common import get_lottery_rules

def calculate_matches(predicted, actual):
    return len(set(predicted) & set(actual))

def run_comparison(test_periods=50):
    lottery_type = 'BIG_LOTTO'
    rules = get_lottery_rules(lottery_type)
    optimizer = MultiBetOptimizer()
    engine = UnifiedPredictionEngine()
    
    all_draws = db_manager.get_all_draws(lottery_type)
    test_draws = all_draws[:test_periods]
    
    stats = {
        'v10': {'wins': 0, 'avg_union': 0},
        'v11': {'wins': 0, 'avg_union': 0}
    }
    
    print(f"🚀 Comparing Strategy v10 vs v11 ({test_periods} draws)")
    
    for i in tqdm(range(test_periods)):
        target = test_draws[i]
        history = all_draws[i+1:]
        target_numbers = target['numbers']
        
        # Common scores for both
        all_preds = engine.ensemble_predict(history, rules)
        number_scores = optimizer._calculate_number_scores({'main': all_preds}, 1, 49, {}, history)
        
        # Test v10
        try:
            res_v10 = optimizer.generate_orthogonal_5bets(history, rules, number_scores)
            max_hit_v10 = max(calculate_matches(b['numbers'], target_numbers) for b in res_v10['bets'])
            union_hit_v10 = len(set().union(*[set(b['numbers']) for b in res_v10['bets']]) & set(target_numbers))
            if max_hit_v10 >= 3: stats['v10']['wins'] += 1
            stats['v10']['avg_union'] += union_hit_v10
        except: pass
        
        # Test v11
        try:
            res_v11 = optimizer.generate_optimized_5bets_v11(history, rules, number_scores)
            max_hit_v11 = max(calculate_matches(b['numbers'], target_numbers) for b in res_v11['bets'])
            union_hit_v11 = len(set().union(*[set(b['numbers']) for b in res_v11['bets']]) & set(target_numbers))
            if max_hit_v11 >= 3: stats['v11']['wins'] += 1
            stats['v11']['avg_union'] += union_hit_v11
        except: pass
        
    print("\n" + "="*50)
    print("📊 COMPARISON RESULTS")
    print("="*50)
    print(f"Metric          | v10 (Baseline) | v11 (Concentrated)")
    print("-" * 50)
    print(f"Win Rate (3+)   | {stats['v10']['wins']/test_periods:14.2%} | {stats['v11']['wins']/test_periods:18.2%}")
    print(f"Avg Union Hits  | {stats['v10']['avg_union']/test_periods:14.2f} | {stats['v11']['avg_union']/test_periods:18.2f}")
    print("=" * 50)

if __name__ == '__main__':
    run_comparison(20)
