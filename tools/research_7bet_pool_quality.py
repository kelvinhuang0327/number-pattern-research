#!/usr/bin/env python3
"""
大樂透 7注優化研究：候選池品質分析 (Pool Quality Analysis)
目的：驗證 "核心模型 (Statistical/Deviation)" 生成的候選池是否具備達成 15% 勝率的潛力。
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

def analyze_pool_quality():
    # Initialize
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()
    
    test_periods = 100
    print(f"🔬 候選池品質分析 (最近 {test_periods} 期)")
    print("=" * 80)
    
    metrics = {
        'pool_size': [],
        'match_3_in_pool': 0,
        'match_4_in_pool': 0,
        'match_5_in_pool': 0,
        'match_6_in_pool': 0,
        'avg_matches_in_pool': 0
    }
    
    experiment_results = []
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        
        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        # --- 策略：聚合核心模型的 Top N ---
        pool_candidates = Counter()
        
        # 1. 統計綜合 (Statistical) - 權重 2.0
        try:
            res_stat = engine.statistical_predict(hist, rules)
            for n in res_stat['numbers'][:15]: # 取前 15
                pool_candidates[n] += 2.0
        except: pass
        
        # 2. 偏差分析 (Deviation) - 權重 2.0
        try:
            res_dev = engine.deviation_predict(hist, rules)
            for n in res_dev['numbers'][:15]: # 取前 15
                pool_candidates[n] += 2.0
        except: pass
        
        # 3. 馬可夫鏈 (Markov) - 權重 1.5
        try:
            res_mar = engine.markov_predict(hist, rules)
            for n in res_mar['numbers'][:12]: # 取前 12
                pool_candidates[n] += 1.5
        except: pass

        # 4. 區域平衡 (Zone) - 權重 1.0 (補充)
        try:
            res_zone = engine.zone_balance_predict(hist, rules)
            for n in res_zone['numbers'][:10]:
                pool_candidates[n] += 1.0
        except: pass
        
        # --- 生成候選池 ---
        # 我們目標是選出約 20-25 個號碼來做 7 注覆蓋
        # 如果池子裡的號碼能包含 3-4 個中獎號碼，我們就有機會
        
        top_24 = [n for n, _ in pool_candidates.most_common(24)]
        matches_in_pool = len(set(top_24) & actual)
        
        metrics['pool_size'].append(len(top_24))
        metrics['avg_matches_in_pool'] += matches_in_pool
        
        if matches_in_pool >= 3:
            metrics['match_3_in_pool'] += 1
        if matches_in_pool >= 4:
            metrics['match_4_in_pool'] += 1
        if matches_in_pool >= 5:
            metrics['match_5_in_pool'] += 1
        if matches_in_pool >= 6:
            metrics['match_6_in_pool'] += 1
            
    # Summary
    total = test_periods
    print(f"📊 分析結果 (Pool Size: 24, 來源: Stat/Dev/Mar/Zone)")
    print(f"  平均命中數: {metrics['avg_matches_in_pool']/total:.2f} 個號碼 (期望值: 6 * 24/49 ≈ 2.93)")
    print(f"  含 3+ 中獎號碼率: {metrics['match_3_in_pool']/total*100:.2f}%")
    print(f"  含 4+ 中獎號碼率: {metrics['match_4_in_pool']/total*100:.2f}%")
    print(f"  含 5+ 中獎號碼率: {metrics['match_5_in_pool']/total*100:.2f}%")
    print("-" * 60)
    
    # 判斷潛力
    # 如果池子包含 3+ 的機率很高 (例如 > 60%)，那麼用 7 注 (42個號碼次) 去覆蓋是很有機會的
    # 7注 x 6號 = 42個位置。如果池子只有24個號碼，每個號碼平均可以被選 1.75 次
    
    if metrics['match_3_in_pool']/total > 0.6:
        print("✅ 候選池品質極佳，適合進行覆蓋優化")
    elif metrics['match_3_in_pool']/total > 0.4:
        print("⚠️ 候選池品質尚可，需要精密的覆蓋算法")
    else:
        print("❌ 候選池品質不足，無法產生高勝率策略")

if __name__ == '__main__':
    analyze_pool_quality()
