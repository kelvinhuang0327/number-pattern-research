#!/usr/bin/env python3
"""
Retrospective Analysis - Draw 115000001
驗證 ClusterPivot 模型在 115000001 期的表現。
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
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from models.multi_bet_optimizer import MultiBetOptimizer
from database import DatabaseManager
from common import get_lottery_rules

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def get_deep_correlation_maps(history):
    pair_counter = Counter()
    trio_counter = Counter()
    number_freq = Counter()
    for draw in history:
        numbers = sorted(draw['numbers'])
        for n in numbers:
            number_freq[n] += 1
        for pair in combinations(numbers, 2):
            pair_counter[pair] += 1
        for trio in combinations(numbers, 3):
            trio_counter[trio] += 1
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

def analyze_115000001():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws(lottery_type='BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = MultiBetOptimizer()
    
    # 實際中獎號碼 (用戶提供)
    actual = {7, 14, 22, 23, 31, 35}
    special = 1
    
    # 找到 115000001 的位置並取其之前的數據
    target_idx = -1
    for i, d in enumerate(history):
        if d['draw'] == '115000001':
            target_idx = i
            break
            
    if target_idx == -1:
        print("未在資料庫中找到 115000001 期")
        return
        
    # 用於預測的歷史 (115000001 之前的數據)
    prediction_history = history[target_idx + 1:]
    
    # 策略精簡版
    strategy_whitelist = ['frequency', 'bayesian', 'markov', 'statistical', 'deviation', 'trend', 'hot_cold', 'monte_carlo']
    
    # 關聯分析
    pairing_history = prediction_history[:1000]
    c_map, t_map = get_deep_correlation_maps(pairing_history)
    
    print(f"📊 正在回顧預測 115000001 期...")
    print(f"歷史基準點: {prediction_history[0]['draw']} ({prediction_history[0]['date']})")
    print("-" * 60)

    # 4 注回測
    meta_config = {
        'method': 'cluster_pivot',
        'anchor_count': 2,
        'correlation_map': c_map,
        'trio_correlation_map': t_map,
        'strategy_whitelist': strategy_whitelist
    }
    
    res = optimizer.generate_diversified_bets(prediction_history, rules, num_bets=4, meta_config=meta_config)
    bets = res['bets']
    
    for i, bet_data in enumerate(bets):
        bet = set(bet_data['numbers'])
        matches = bet & actual
        s_match = (bet_data.get('special') == special or special in bet) # 大樂透特別號可能在主號內
        
        match_str = ",".join([f"{n:02d}" for n in sorted(list(matches))]) if matches else "無"
        print(f"注 {i+1}: {sorted(list(bet))} | 命中: {match_str} (Match {len(matches)}){' [特別號中!]' if s_match else ''}")

if __name__ == '__main__':
    analyze_115000001()
