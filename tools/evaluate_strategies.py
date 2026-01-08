#!/usr/bin/env python3
"""
Strategy Performance Pruner
分析各個子策略在 2025 年的「獨立表現」，找出哪些策略是「噪音」，並將其剔除出共識池。
"""
import sys
import os
import io
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from models.multi_bet_optimizer import MultiBetOptimizer
from database import DatabaseManager
from common import get_lottery_rules

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def evaluate_individual_strategies(lottery_type='BIG_LOTTO', year=2025):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type=lottery_type)))
    rules = get_lottery_rules(lottery_type)
    optimizer = MultiBetOptimizer()
    
    test_draws = [d for d in all_draws if d['date'].startswith(str(year))][:50] # 評估前 50 期
    start_idx = all_draws.index(test_draws[0])
    
    strategy_wins = Counter()
    total_periods = len(test_draws)
    
    print(f"🔍 評估各子策略獨立表現 (2025 前 {total_periods} 期)")
    print("-" * 60)
    
    for i, target_draw in enumerate(test_draws):
        current_history = all_draws[:start_idx + i]
        
        # 獲取所有策略的預測
        all_preds = {}
        for group_name, strategies in optimizer.strategy_groups.items():
            for name, func, weight in strategies:
                try:
                    res = func(current_history, rules)
                    all_preds[name] = res['numbers']
                except:
                    continue
        
        actual = target_draw['numbers']
        special = target_draw['special']
        
        for name, bet in all_preds.items():
            matches = len(set(bet) & set(actual))
            s_match = special in bet
            if matches >= 3 or (matches == 2 and s_match):
                strategy_wins[name] += 1
                
    results = []
    for name, wins in strategy_wins.items():
        results.append((name, wins / total_periods))
        
    results.sort(key=lambda x: x[1], reverse=True)
    
    print(f"{'策略名稱':<25} | {'勝率':<10}")
    print("-" * 40)
    for name, rate in results:
        print(f"{name:<25} | {rate:.2%}")
    print("-" * 60)
    print("💡 建議剔除 (勝率 < 2%):")
    for name, rate in results:
        if rate < 0.02:
            print(f"- {name}")

if __name__ == '__main__':
    evaluate_individual_strategies()
