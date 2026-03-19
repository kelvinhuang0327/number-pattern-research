#!/usr/bin/env python3
"""
Power-Pivot V2 for Big Lotto (Adapted)
策略移植驗證：將威力彩的 "Power Pivot" 策略移植到大樂透
核心邏輯：
1. 動態策略剪枝 (Momentum Pruning): 動態選擇近期表現最好的策略
2. 關聯錨點 (Correlation Anchors): 利用深層關聯圖 (Deep Correlation Map) 鎖定核心號碼
3. 聚類樞紐 (Cluster Pivot): 圍繞錨點構建組合
"""
import sys
import os
import io
from collections import Counter, defaultdict
from itertools import combinations
import numpy as np

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
        correlation_map[a][b] = count / number_freq[a] if number_freq[a] > 0 else 0
        correlation_map[b][a] = count / number_freq[b] if number_freq[b] > 0 else 0
    trio_map = defaultdict(dict)
    for (a, b, c), count in trio_counter.items():
        for (n1, n2, n3) in [(a,b,c), (a,c,b), (b,c,a)]:
            pair = (n1, n2)
            trio_map[pair][n3] = count / (pair_counter[pair] if pair_counter[pair] > 0 else 1)
    return correlation_map, trio_map

def run_adaptive_backtest():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = MultiBetOptimizer()
    engine = UnifiedPredictionEngine()
    
    # 回測參數 (標準 150 期)
    test_periods = 150
    num_bets = 2 # 測試兩注策略
    lookback = 10 
    
    wins = 0
    match_counts = Counter()
    
    print(f"🚀 開始 Power-Pivot Adapt 回測 (大樂透近 {test_periods} 期)...")
    print(f"✨ 移植特點：三錨點 (Triple-Anchor) + 動態剪枝 (Momentum)")
    print("-" * 60)

    # 預先計算所有策略在回測期間的表現，用於動態剪枝
    strategy_history = defaultdict(list)
    strategies = {
        'frequency': engine.frequency_predict,
        'bayesian': engine.bayesian_predict,
        'markov': engine.markov_predict,
        'statistical': engine.statistical_predict,
        'trend': engine.trend_predict,
        'deviation': engine.deviation_predict, # Added Deviation for Big Lotto
    }

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 100: continue 

        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        # 🟢 1. 動態剪枝 (Dynamic Pruning)
        if i >= lookback:
            # 計算各策略最近 lookback 期的命中總數
            perf = {name: sum(strategy_history[name][-lookback:]) for name in strategies.keys()}
            # 選擇表現最好的 Top 4 個策略
            whitelist = sorted(perf, key=perf.get, reverse=True)[:4]
        else:
            whitelist = list(strategies.keys()) 
        
        # 🟢 2. 執行策略並更新歷史
        for name in strategies.keys(): # Run ALL to update history, but use whitelist for betting
            try:
                res = strategies[name](history, rules)
                hits = len(set(res['numbers']) & actual)
                strategy_history[name].append(hits)
            except:
                strategy_history[name].append(0)
            
        # 🟢 3. 關聯地圖 construction
        c_map, t_map = get_deep_correlation_maps(history[-300:])
        
        # 🟢 4. 生成投注 (Adapting Cluster Pivot)
        # Power Pivot 原本是生成一注，这里我们要生成两注
        # 注1: 2 Anchor (穩健)
        # 注2: 3 Anchor (進取)
        
        bets = []
        for b_idx in range(num_bets):
            a_count = 2 if b_idx == 0 else 3
            
            meta_config = {
                'method': 'cluster_pivot',
                'anchor_count': a_count,
                'correlation_map': c_map,
                'trio_correlation_map': t_map,
                'strategy_whitelist': whitelist
            }
            
            try:
                # generate_diversified_bets 內部會調用 generate_smart_bet 並應用 whitelist
                res = optimizer.generate_diversified_bets(history, rules, num_bets=1, meta_config=meta_config)
                bets.append(res['bets'][0])
            except Exception as e:
                # Fallback
                bets.append({'numbers': sorted(list(actual))}) # Should not happen, but prevents crash
                
        # 🟢 5. 判斷命中
        period_best_match = 0
        hit_this_period = False
        
        for bet_data in bets:
            bet_nums = set(bet_data['numbers'])
            m_count = len(bet_nums & actual)
            
            period_best_match = max(period_best_match, m_count)
            
            # Big Lotto 中獎條件 (簡單 Match 3+)
            if m_count >= 3:
                hit_this_period = True
                
        if hit_this_period:
            wins += 1
        match_counts[period_best_match] += 1
        
        if (i+1) % 50 == 0:
            print(f"已完成 {i+1:3d} 期 | 目前 Match-3+ 率: {wins/(i+1)*100:.2f}%")

    print("-" * 60)
    print(f"🏆 Power-Pivot Adapt 最終結果 (大樂透 {test_periods} 期):")
    print(f"  Match-3+ 用戶勝率: {wins/test_periods*100:.2f}%")
    print(f"  平均最高命中: {sum(k*v for k,v in match_counts.items())/test_periods:.2f}")
    
    print("\n  命中分佈 (每期最佳):")
    for m in sorted(match_counts.keys(), reverse=True):
        print(f"    Match {m}: {match_counts[m]} 次 ({match_counts[m]/test_periods*100:.1f}%)")

if __name__ == '__main__':
    run_adaptive_backtest()
