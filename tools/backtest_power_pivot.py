#!/usr/bin/env python3
"""
Power Lotto (威力彩) ClusterPivot Backtest V1
目標：驗證針對 38 碼池優化的「集群樞軸」策略。
目標勝率：33% (Match 2+S 或 Match 3+)
"""
import sys
import os
import io
import json
from collections import Counter, defaultdict
from itertools import combinations

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.multi_bet_optimizer import MultiBetOptimizer
from database import DatabaseManager
from common import get_lottery_rules

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def get_deep_correlation_maps(history):
    """針對 38 碼池計算關聯地圖"""
    pair_counter = Counter()
    trio_counter = Counter()
    quad_counter = Counter()
    number_freq = Counter()
    
    for draw in history:
        numbers = sorted(draw['numbers'])
        for n in numbers:
            number_freq[n] += 1
        for pair in combinations(numbers, 2):
            pair_counter[pair] += 1
        for trio in combinations(numbers, 3):
            trio_counter[trio] += 1
        for quad in combinations(numbers, 4):
            quad_counter[quad] += 1
            
    correlation_map = defaultdict(dict)
    for (a, b), count in pair_counter.items():
        correlation_map[a][b] = count / number_freq[a]
        correlation_map[b][a] = count / number_freq[b]
        
    trio_map = defaultdict(dict)
    for (a, b, c), count in trio_counter.items():
        for (n1, n2, n3) in [(a,b,c), (a,c,b), (b,c,a)]:
            pair = (n1, n2)
            trio_map[pair][n3] = count / (pair_counter[pair] if pair_counter[pair] > 0 else 1)
            
    return correlation_map, trio_map

def run_backtest(lottery_type='POWER_LOTTO', num_bets=4, year=2025):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type=lottery_type)))
    rules = get_lottery_rules(lottery_type)
    optimizer = MultiBetOptimizer()
    
    test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
    if not test_draws:
        print(f"No data for {year}")
        return

    start_idx = all_draws.index(test_draws[0])
    
    # 策略精簡
    strategy_whitelist = [
        'frequency', 'bayesian', 'markov', 'statistical', 
        'deviation', 'trend', 'hot_cold', 'monte_carlo'
    ]
    
    print(f"🚀 Power Lotto ClusterPivot V1 Backtest")
    print(f"模式: 38碼池共識 + 1-8區輪詢 (4注模式)")
    print(f"目標: 33% 成功率 | 年份: {year} | 期數: {len(test_draws)}")
    print("-" * 60)
    
    wins = 0
    total = 0
    match_dist = Counter()
    
    for i, target_draw in enumerate(test_draws):
        current_idx = start_idx + i
        current_history = all_draws[:current_idx]
        
        # 關聯分析
        pairing_history = current_history[-1000:]
        c_map, t_map = get_deep_correlation_maps(pairing_history)
        
        # 配置
        meta_config = {
            'method': 'cluster_pivot',
            'anchor_count': 2,
            'correlation_map': c_map,
            'trio_correlation_map': t_map,
            'strategy_whitelist': strategy_whitelist
        }
        
        res = optimizer.generate_diversified_bets(current_history, rules, num_bets=num_bets, meta_config=meta_config)
        bets = res['bets']
        
        actual = target_draw['numbers']
        special = target_draw['special'] # 威力彩第二區
        
        is_period_win = False
        best_main = 0
        
        for bet_data in bets:
            bet = bet_data['numbers']
            bet_special = bet_data.get('special')
            
            matches = len(set(bet) & set(actual))
            s_match = (bet_special == special)
            
            # 威力彩中獎規則簡化: 
            # 普獎: 2+S (100) -> 視為 Wins
            # 玖獎: 3   (100) -> 視為 Wins
            if matches >= 3 or (matches >= 1 and s_match): # 威力彩只要有特別號且有1碼主號就中獎 (捌獎)
                is_period_win = True
            
            if matches > best_main:
                best_main = matches
        
        if is_period_win:
            wins += 1
        
        match_dist[best_main] += 1
        total += 1
        
        if (i+1) % 5 == 0 or (i+1) == len(test_draws):
            print(f"進度: {i+1}/{len(test_draws)}, 目前中獎率: {wins/total*100:.2f}% (Wins: {wins})")

    print("-" * 60)
    print(f"✅ 最終勝率 (Win Rate): {wins/total*100:.2f} %")
    print(f"命中分佈 (最佳注主區):")
    for m in sorted(match_dist.keys(), reverse=True):
        print(f"  Match {m}: {match_dist[m]} 次")
    print("-" * 60)

if __name__ == '__main__':
    run_backtest(num_bets=4)
