#!/usr/bin/env python3
"""
大樂透變體覆蓋率分析 (Overlap Research)
目的：檢查候選變體之間的號碼重疊度，確保 7 注組合的多樣性。
"""
import sys
import os
import io
import itertools
from collections import Counter
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.unified_predictor import UnifiedPredictionEngine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def analyze_overlap():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()
    
    # 候選變體
    variants = [
        ('Mar_W50', 'markov_predict', 50),
        ('Mar_W100', 'markov_predict', 100),
        ('Dev_W100', 'deviation_predict', 100),
        ('Dev_W200', 'deviation_predict', 200),
        ('Stat_W100', 'statistical_predict', 100),
        ('Stat_W50', 'statistical_predict', 50),
    ]
    
    test_periods = 20
    print(f"🔬 變體重疊度分析 (最近 {test_periods} 期抽樣)")
    print("=" * 80)
    
    overlap_stats = {f"{v1[0]}_vs_{v2[0]}": [] for v1, v2 in itertools.combinations(variants, 2)}
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        
        # Collect predictions
        preds = {}
        for short_name, method_name, windowit in variants:
            start_hist = max(0, target_idx - windowit)
            hist = all_draws[start_hist:target_idx]
            try:
                res = getattr(engine, method_name)(hist, rules)
                preds[short_name] = set(res['numbers'][:6])
            except:
                preds[short_name] = set()
                
        # Calculate Overlap
        for key in overlap_stats:
            n1, n2 = key.split('_vs_')
            s1 = preds.get(n1, set())
            s2 = preds.get(n2, set())
            
            if not s1 or not s2: continue
            
            common = len(s1 & s2)
            overlap_stats[key].append(common)
            
    # Report
    print(f"{'Pair':<25} {'Avg Overlap (0-6)':<20} {'Similarity'}")
    print("-" * 60)
    
    for key, vals in overlap_stats.items():
        if not vals: continue
        avg = np.mean(vals)
        sim = avg / 6 * 100
        print(f"{key:<25} {avg:>5.2f} / 6             {sim:>5.1f}%")
        
    print("-" * 60)
    print("💡 解讀標準:")
    print("  - < 2.0 (33%): 非常多樣 (Excellent)")
    print("  - 2.0 ~ 4.0: 中度重疊 (Good)")
    print("  - > 4.5 (75%): 高度重複 (Bad - Waste of money)")

if __name__ == '__main__':
    analyze_overlap()
