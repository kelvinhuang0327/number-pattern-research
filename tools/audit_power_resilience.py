#!/usr/bin/env python3
"""
🛡 Power Lotto Leak-Free Audit Script
目標：排除所有數據洩漏，重新評估真實勝率 (僅計算 Match-3+)。
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

def get_rolling_correlation(history):
    """
    動態計算關聯，不依賴全局寫死的表格。
    """
    sum_to_special = defaultdict(Counter)
    for draw in history:
        s = sum(draw['numbers'])
        # 將總和分區
        bin_size = 10
        s_bin = (s // bin_size) * bin_size
        sum_to_special[s_bin][draw['special']] += 1
    
    # 返回每個區間最強的特別號
    bias_map = {}
    for s_bin, counters in sum_to_special.items():
        bias_map[s_bin] = [s for s, _ in counters.most_common(5)]
    return bias_map

def run_leak_free_audit():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    optimizer = MultiBetOptimizer()
    
    test_periods = 118 # 2025 全年
    num_bets = 4
    
    real_wins_match3 = 0 # 僅計算 Match-3+
    real_wins_match2s = 0 # Match-2 + Special (捌獎)
    total_any_win = 0
    
    print(f"🕵️ 正在執行「無洩漏」誠信審計 (最近 {test_periods} 期)...")
    print(f"🔍 排除所有全局寫死的 Sum-Bias 數據，改用滾動計算 (Rolling Context)。")
    print("-" * 60)

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        actual_special = target_draw['special']
        
        # 🟢 1. 滾動計算跨區關聯 (無洩漏！)
        # 我們只看當前日期之前的 history 來建立偏差地圖
        rolling_bias = get_rolling_correlation(history[-1000:])
        
        # 🟢 2. 注入滾動地圖到備選配置
        meta_config = {
            'method': 'cluster_pivot',
            'anchor_count': 2,
            # 手動模擬 V2/V3 邏輯，但使用滾動計算的 rolling_bias
            'rolling_bias': rolling_bias
        }
        
        # 由於 optimizer 內部目前寫死了 bias 表，我們在這裡手動干預生成
        res = optimizer.generate_diversified_bets(history, rules, num_bets=num_bets, meta_config=meta_config)
        bets = res['bets']
        
        # 手動套用滾動偏差覆蓋 (模擬實戰優化)
        for b_idx, bet in enumerate(bets):
            pred_sum = sum(bet['numbers'])
            s_bin = (pred_sum // 10) * 10
            bias_specials = rolling_bias.get(s_bin, [2, 5, 8])
            # 輪詢覆蓋
            bet['special'] = bias_specials[b_idx % len(bias_specials)]
        
        # 🟢 3. 嚴格判定
        period_match3 = False
        period_match2s = False
        period_any = False
        
        for bet in bets:
            m_count = len(set(bet['numbers']) & actual)
            s_match = (bet['special'] == actual_special)
            
            # Match 3+
            if m_count >= 3: period_match3 = True
            # Match 2 + S (捌獎)
            if m_count >= 2 and s_match: period_match2s = True
            # Any (包括 Match 1 + S)
            if (m_count >= 1 and s_match) or (m_count >= 3): period_any = True
            
        if period_match3: real_wins_match3 += 1
        if period_match2s: real_wins_match2s += 1
        if period_any: total_any_win += 1
        
    print("-" * 60)
    print(f"📊 審計結果 (2025 全年 {test_periods} 期):")
    print(f"  [嚴格] Match-3+ 勝率: {real_wins_match3/test_periods*100:.2f}% (目標 ~15%)")
    print(f"  [中低] Match-2+S 勝率: {real_wins_match2s/test_periods*100:.2f}%")
    print(f"  [寬鬆] 普獎+ (Any Win): {total_any_win/test_periods*100:.2f}%")
    print(f"  (註：當前 4 注配置下，15% 的 Match-3+ 才是真實的技術標竿)")

if __name__ == '__main__':
    run_leak_free_audit()
