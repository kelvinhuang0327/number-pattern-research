#!/usr/bin/env python3
"""
Final Prediction Generator - peak-optimized ClusterPivot
為下期大樂透與威力彩生成 4 注預測組合。
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
    """計算關聯地圖"""
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

def generate_predictions():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    optimizer = MultiBetOptimizer()
    
    lotteries = ['BIG_LOTTO', 'POWER_LOTTO']
    
    # 動態載入最佳策略（如果有熱度分析結果）
    heat_map_file = os.path.join(project_root, 'data', 'strategy_heat_map.json')
    if os.path.exists(heat_map_file):
        with open(heat_map_file, 'r', encoding='utf-8') as f:
            heat_data = json.load(f)
            strategy_whitelist = heat_data.get('recommended_whitelist', [
                'frequency', 'bayesian', 'markov', 'statistical', 
                'deviation', 'trend', 'hot_cold', 'monte_carlo'
            ])
            print(f"📊 使用動態策略白名單: {strategy_whitelist}")
    else:
        strategy_whitelist = [
            'frequency', 'bayesian', 'markov', 'statistical', 
            'deviation', 'trend', 'hot_cold', 'monte_carlo'
        ]

    print("=" * 60)
    print("💎 FINAL OPTIMIZED PREDICTIONS (4-BET CLUSTERPivot) 💎")
    print("=" * 60)

    for l_type in lotteries:
        history = db.get_all_draws(lottery_type=l_type)
        if not history:
            print(f"\n⚠️ {l_type} | 無歷史數據，跳過預測。")
            continue
            
        rules = get_lottery_rules(l_type)
        
        latest_draw = history[0]
        print(f"\n📍 {l_type} | 最後更新期數: {latest_draw['draw']} ({latest_draw['date']})")
        
        # 關聯分析
        pairing_history = history[-1000:]
        c_map, t_map = get_deep_correlation_maps(pairing_history)
        
        # 配置 (V6/V7 Hybrid Peak)
        meta_config = {
            'method': 'cluster_pivot',
            'anchor_count': 2,
            'correlation_map': c_map,
            'trio_correlation_map': t_map,
            'strategy_whitelist': strategy_whitelist
        }
        
        # Power Lotto 特化配置 (V3 Resilience)
        if l_type == 'POWER_LOTTO':
            meta_config['anchor_count'] = 2 # 威力彩鎖定 2 個主碼錨點效果最佳
            meta_config['resilience'] = True # 啟用波動權重與反轉保護
        
        res = optimizer.generate_diversified_bets(history, rules, num_bets=4, meta_config=meta_config)
        bets = res['bets']
        summary = res.get('summary', {})
        
        print(f"🔗 核心鎖定錨點: {summary.get('anchors', [])}")
        if 'specials' in summary:
             print(f"🎯 第二區分佈: {summary.get('specials', [])}")
        
        print("-" * 40)
        for i, bet_data in enumerate(bets):
            nums = ",".join([f"{n:02d}" for n in bet_data['numbers']])
            special = f" | 特別號/第二區: {bet_data['special']:02d}" if 'special' in bet_data else ""
            print(f"注 {i+1}: {nums}{special}")
        print("-" * 40)

    print("\n✅ 預測生成完畢。祝您幸運！")
    print("=" * 60)

if __name__ == '__main__':
    generate_predictions()
