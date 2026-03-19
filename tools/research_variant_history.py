#!/usr/bin/env python3
"""
大樂透變體研究：不同歷史區間的效能分析
目的：尋找能維持高勝率的不同參數配置 (Windows)，以構建多樣化的 7 注組合。
"""
import sys
import os
import io
from collections import Counter
import random
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.unified_predictor import UnifiedPredictionEngine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def analyze_variants():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()
    
    test_periods = 120 # 测试更多期数以稳定数据
    print(f"🔬 變體效能分析 (最近 {test_periods} 期)")
    print("=" * 100)
    print(f"{'策略變體':<25} {'Match-3+':<10} {'Diff (vs Baseline)'}")
    print("-" * 100)
    
    # Define variants to test
    # (Method Name, Window Size)
    variants = [
        ('deviation_predict', 50),
        ('deviation_predict', 100),
        ('deviation_predict', 200),
        ('statistical_predict', 50),
        ('statistical_predict', 100),
        ('statistical_predict', 200),
        ('markov_predict', 50),
        ('markov_predict', 100),
        ('markov_predict', 200),
        ('frequency_predict', 50), # 測試一下頻率
        ('zone_balance_predict', 100) # 測試一下區域
    ]
    
    results = {v: {'wins': 0, 'draws': 0, 'matches': []} for v in variants}
    
    # Baseline: Random single bet
    random_wins = 0
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        
        target_draw = all_draws[target_idx]
        actual = set(target_draw['numbers'])
        
        # Test strategies
        for method_name, windowit in variants:
            # 獲取對應窗口的歷史
            # 如果 window=100, 取 target_idx 前 100 期
            start_hist = max(0, target_idx - windowit)
            hist_variant = all_draws[start_hist:target_idx]
            
            if len(hist_variant) < 20: continue # 數據太少不測
            
            try:
                method = getattr(engine, method_name)
                res = method(hist_variant, rules)
                predicted = set(res['numbers'][:6])
                match_count = len(predicted & actual)
                
                results[(method_name, windowit)]['matches'].append(match_count)
                if match_count >= 3:
                    results[(method_name, windowit)]['wins'] += 1
                
                results[(method_name, windowit)]['draws'] += 1
            except Exception as e:
                pass
                
        # Random Control
        rand_pred = set(random.sample(range(1, 50), 6))
        if len(rand_pred & actual) >= 3:
            random_wins += 1
            
    # Report
    random_rate = random_wins / test_periods * 100
    print(f"隨機基準 (1注): {random_rate:.2f}%")
    print("-" * 100)
    
    successful_variants = []
    
    for v in variants:
        data = results[v]
        total = data['draws']
        if total == 0: continue
        
        rate = data['wins'] / total * 100
        diff = rate - random_rate
        
        name = f"{v[0].replace('_predict', '')} (W{v[1]})"
        print(f"{name:<25} {rate:>6.2f}%    {diff:>+5.2f}%")
        
        if diff > 0.5: # 至少優於隨機 0.5%
            successful_variants.append(v)
            
    print("-" * 100)
    print(f"篩選出的優秀變體 ({len(successful_variants)} 個):")
    for s in successful_variants:
        print(f"  - {s[0]} (W{s[1]})")

if __name__ == '__main__':
    analyze_variants()
