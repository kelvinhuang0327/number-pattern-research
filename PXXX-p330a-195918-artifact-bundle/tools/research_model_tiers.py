#!/usr/bin/env python3
"""
大樂透分層效能研究 (Tier Performance Research)
目的：驗證 "核心模型" 的第 2 層 (Rank 7-12) 預測是否優於隨機，
      以決定是否用它們來填補 7 注策略的空缺。
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

def analyze_tiers():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()
    
    test_periods = 100
    print(f"🔬 模型分層效能分析 (最近 {test_periods} 期)")
    print("=" * 80)
    
    # Trackers
    results = {
        'dev_t1': 0, 'dev_t2': 0, 'dev_t3': 0,
        'stat_t1': 0, 'stat_t2': 0, 'stat_t3': 0,
        'mar_t1': 0, 'mar_t2': 0, 'mar_t3': 0,
    }
    
    total = 0
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        
        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        def check_hit(numbers):
            return 1 if len(set(numbers) & actual) >= 3 else 0
            
        # 1. Deviation
        try:
            res = engine.deviation_predict(hist, rules)
            results['dev_t1'] += check_hit(res['numbers'][0:6])
            results['dev_t2'] += check_hit(res['numbers'][6:12])
            results['dev_t3'] += check_hit(res['numbers'][12:18])
        except: pass
        
        # 2. Statistical
        try:
            res = engine.statistical_predict(hist, rules)
            results['stat_t1'] += check_hit(res['numbers'][0:6])
            results['stat_t2'] += check_hit(res['numbers'][6:12])
            results['stat_t3'] += check_hit(res['numbers'][12:18])
        except: pass

        # 3. Markov
        try:
            res = engine.markov_predict(hist, rules)
            results['mar_t1'] += check_hit(res['numbers'][0:6])
            results['mar_t2'] += check_hit(res['numbers'][6:12])
            results['mar_t3'] += check_hit(res['numbers'][12:18])
        except: pass
        
        total += 1
        
    # Report
    print(f"基準 (隨機單注 Match-3+): ~1.76%")
    print("-" * 60)
    print(f"模型 | Tier 1 (1-6) | Tier 2 (7-12) | Tier 3 (13-18)")
    print("-" * 60)
    
    def p(k): return f"{results[k]/total*100:.2f}%"
    
    print(f"Dev  | {p('dev_t1'):<12} | {p('dev_t2'):<13} | {p('dev_t3')}")
    print(f"Stat | {p('stat_t1'):<12} | {p('stat_t2'):<13} | {p('stat_t3')}")
    print(f"Mar  | {p('mar_t1'):<12} | {p('mar_t2'):<13} | {p('mar_t3')}")
    
    print("-" * 60)
    # Check if Tier 2 is viable
    avg_t2 = (results['dev_t2'] + results['stat_t2'] + results['mar_t2']) / 3 / total * 100
    print(f"Tier 2 平均勝率: {avg_t2:.2f}%")
    
    if avg_t2 > 2.0:
        print("✅ Tier 2 具備優於隨機的潛力，可以用於填補 7 注")
    else:
        print("❌ Tier 2 表現不佳，不應直接使用")

if __name__ == '__main__':
    analyze_tiers()
