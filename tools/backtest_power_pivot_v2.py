#!/usr/bin/env python3
"""
Power-Pivot V2 Backtest (Phase 2 Optimization)
✨ 三錨點 (Triple-Anchor) + 總和驅動特別號 (Sum-Bias) + 動態策略剪枝 (Momentum Pruning)
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

def run_v2_backtest():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    optimizer = MultiBetOptimizer()
    engine = UnifiedPredictionEngine()
    
    # 回測參數
    test_periods = 118 # 全 2025 數據
    num_bets = 4
    lookback = 10 # 更加敏感的反應 (Reactive Momentum)
    
    wins = 0
    special_hits = 0
    match_counts = Counter()
    
    print(f"🚀 開始 Power-Pivot V2 回測 (最近 {test_periods} 期)...")
    print(f"✨ 核心優化：三錨點 (Triple-Anchor) + 總和偏差 (Sum-Bias) + 動態剪枝 (Momentum)")
    print("-" * 60)

    # 預先計算所有策略在回測期間的表現，用於動態剪枝
    strategy_history = defaultdict(list)
    strategies = {
        'frequency': engine.frequency_predict,
        'bayesian': engine.bayesian_predict,
        'markov': engine.markov_predict,
        'statistical': engine.statistical_predict,
        'trend': engine.trend_predict,
        'hot_cold': engine.hot_cold_mix_predict,
    }

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        actual_special = target_draw['special']
        
        # 🟢 1. 動態剪枝 (Dynamic Pruning)
        # 分析過去 'lookback' 期的策略表現
        if i >= lookback:
            perf = {name: sum(strategy_history[name][-lookback:]) for name in strategies.keys()}
            # 選擇表現最好的 Top 3-4 個策略
            whitelist = sorted(perf, key=perf.get, reverse=True)[:4]
        else:
            whitelist = list(strategies.keys()) # 初始階段使用全部
        
        # 🟢 2. 獲取當前預測
        all_predictions = {}
        for name in whitelist:
            res = strategies[name](history, rules)
            all_predictions[name] = res
            # 更新命中歷史 (用於下一輪剪枝)
            hits = len(set(res['numbers']) & actual)
            strategy_history[name].append(hits)
            
        # 🟢 3. 關聯地圖 (V2 使用較深的地圖)
        c_map, t_map = get_deep_correlation_maps(history[-1000:])
        
        # 🟢 4. 生成 V2 投注 (Hybrid Anchor Approach)
        bets = []
        for b_idx in range(num_bets):
            # 前兩注穩健 (2 錨點)，後兩注進取 (3 錨點)
            a_count = 2 if b_idx < 2 else 3
            
            meta_config = {
                'method': 'cluster_pivot',
                'anchor_count': a_count,
                'correlation_map': c_map,
                'trio_correlation_map': t_map,
                'strategy_whitelist': whitelist
            }
            
            # 使用單注生成循環構建組合
            res = optimizer.generate_diversified_bets(history, rules, num_bets=1, meta_config=meta_config)
            # 因為 generate_diversified_bets 的 round-robin 是基於它的 num_bets 參數，
            # 我們需要手動調整它生成的多樣性，或者直接修正其內部的特別號索引。
            # 這裡簡化：我們直接傳遞 b_idx 給 meta_config 作為偏移量 (如果 optimizer 支援，或在此手動修正)。
            
            bet_data = res['bets'][0]
            # 手動修正特別號為輪詢 (確保覆蓋)
            # 從 optimizer 的 _get_sum_biased_specials 等邏輯構建的順序中取第 b_idx 個
            pred_sum = sum(bet_data['numbers'])
            all_specials = optimizer._get_sum_biased_specials(pred_sum)
            # 補充剩餘投票與範圍
            special_scores = defaultdict(float)
            for name, data in all_predictions.items():
                if 'special' in data:
                    special_scores[data['special']] += data.get('confidence', 0.5)
            vote_specials = [s for s, _ in sorted(special_scores.items(), key=lambda x: x[1], reverse=True)]
            for s in vote_specials:
                if s not in all_specials: all_specials.append(s)
            for s in range(1, 9):
                if s not in all_specials: all_specials.append(s)
                
            bet_data['special'] = all_specials[b_idx % len(all_specials)]
            bets.append(bet_data)

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
            
            # 威力彩中獎條件 (Match 1 + Special 或 Match 3)
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
    print(f"🏆 Power-Pivot V2 最終結果 (2025年 {test_periods} 期):")
    print(f"  總中獎期數: {wins}")
    print(f"  總勝率 (Win Rate): {wins/test_periods*100:.2f}% 🔥")
    print(f"  第二區命中率: {special_hits/test_periods*100:.1f}%")
    print(f"  平均最高命中: {sum(k*v for k,v in match_counts.items())/test_periods:.2f}")
    
    print("\n  命中分佈 (Best Match per Draw):")
    for m in sorted(match_counts.keys(), reverse=True):
        print(f"    Match {m}: {match_counts[m]} 次 ({match_counts[m]/test_periods*100:.1f}%)")

if __name__ == '__main__':
    run_v2_backtest()
