#!/usr/bin/env python3
"""
Power-Pivot V3 Backtest (Phase 3 Optimization: Resilience)
🛡 波動權重 (Volatility) + 反轉保護 (Reversal) + 總和偏差 (Sum-Bias)
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
from models.unified_predictor import UnifiedPredictionEngine
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

def run_v3_backtest():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    optimizer = MultiBetOptimizer()
    engine = UnifiedPredictionEngine()
    
    # 回測參數 (2025 全年)
    test_periods = 118
    num_bets = 4
    lookback = 15 # 中間平衡點
    
    wins = 0
    special_hits = 0
    match_counts = Counter()
    
    print(f"🚀 開始 Power-Pivot V3 回測 (最近 {test_periods} 期)...")
    print(f"🛡 核心優化：波動權重 (Volatility) + 反轉保護 (Reversal) + 五倍特別號涵蓋 (V2 Sum-Bias)")
    print("-" * 60)

    strategy_history = defaultdict(list)
    strategies = {
        'frequency': engine.frequency_predict,
        'bayesian': engine.bayesian_predict,
        'markov': engine.markov_predict,
        'trend': engine.trend_predict,
        'hot_cold': engine.hot_cold_mix_predict,
    }

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        actual_special = target_draw['special']
        
        # 🟢 1. 動態剪枝
        if i >= lookback:
            perf = {name: sum(strategy_history[name][-lookback:]) for name in strategies.keys()}
            whitelist = sorted(perf, key=perf.get, reverse=True)[:3]
        else:
            whitelist = list(strategies.keys())
        
        # 🟢 2. 獲取當前預測與命中紀錄
        for name, func in strategies.items():
            res = func(history, rules)
            hits = len(set(res['numbers']) & actual)
            strategy_history[name].append(hits)
            
        # 🟢 3. 關聯地圖
        c_map, t_map = get_deep_correlation_maps(history[-1000:])
        
        # 🟢 4. 生成 V3 投注 (Resilience=True)
        meta_config = {
            'method': 'cluster_pivot',
            'resilience': True, # 啟用 V3 穩定性邏輯
            'anchor_count': 2,
            'correlation_map': c_map,
            'trio_correlation_map': t_map,
            'strategy_whitelist': whitelist
        }
        
        res = optimizer.generate_diversified_bets(history, rules, num_bets=num_bets, meta_config=meta_config)
        bets = res['bets']
        
        # 🟢 5. 判斷命中
        period_best_match = 0
        hit_this_period = False
        special_hit_this_period = False
        
        for bet_data in bets:
            bet_nums = set(bet_data['numbers'])
            m_count = len(bet_nums & actual)
            s_match = (bet_data['special'] == actual_special)
            
            period_best_match = max(period_best_match, m_count)
            if s_match: special_hit_this_period = True
            
            if (m_count >= 1 and s_match) or (m_count >= 3):
                hit_this_period = True
                
        if hit_this_period:
            wins += 1
        if special_hit_this_period:
            special_hits += 1
        match_counts[period_best_match] += 1
        
        if (i+1) % 20 == 0:
            print(f"已完成 {i+1:3d} 期 | 目前勝率: {wins/(i+1)*100:.2f}%")

    print("-" * 60)
    print(f"🏆 Power-Pivot V3 最終結果 (2025年 {test_periods} 期):")
    print(f"  總中獎期數: {wins}")
    print(f"  總勝率 (Win Rate): {wins/test_periods*100:.2f}% 🔥")
    print(f"  第二區命中率: {special_hits/test_periods*100:.1f}%")
    print(f"  平均最高命中: {sum(k*v for k,v in match_counts.items())/test_periods:.2f}")

if __name__ == '__main__':
    run_v3_backtest()
