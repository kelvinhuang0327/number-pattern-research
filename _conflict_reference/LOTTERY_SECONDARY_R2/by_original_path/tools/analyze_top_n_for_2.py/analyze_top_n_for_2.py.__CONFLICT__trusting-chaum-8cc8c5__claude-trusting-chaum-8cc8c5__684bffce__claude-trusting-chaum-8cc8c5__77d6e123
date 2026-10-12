
#!/usr/bin/env python3
"""
Top-N Hit-2 Analyzer
目標：分析選取前 N 個號碼 (Top N) 時，命中 2 碼 (Match >= 2) 的機率。
回答使用者：到底要選幾個號碼才能「必中兩碼」？
"""
import sys
import os
import argparse
import pandas as pd
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.unified_predictor import UnifiedPredictionEngine

def analyze_top_n_hit_2(year=2025):
    print("=" * 80)
    print(f"📊 Top-N for 'Hit 2' Analysis - {year}")
    print("=" * 80)
    
    # 準備數據
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    all_draws = sorted(all_draws, key=lambda x: x['date'])
    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()

    test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
    if not test_draws:
        print(f"❌ No data for {year}")
        return

    # 我們主要分析表現最好的方法：Bayesian (2025 King) 和 Deviation (Long-term King)
    methods = ['bayesian_predict', 'deviation_predict']
    
    # 測試 N 的範圍: 2 到 8
    n_range = range(2, 9)

    for method in methods:
        print(f"\n🔍 Method: {method}")
        print(f"{'Top N':<10} | {'Hit >= 2 Probability':<25}")
        print("-" * 40)
        
        for n in n_range:
            hits_2_plus = 0
            total = 0
            
            for target_draw in test_draws:
                target_idx = all_draws.index(target_draw)
                history = all_draws[:target_idx]
                actual = set(target_draw['numbers'])
                
                try:
                    func = getattr(engine, method)
                    result = func(history, rules)
                    # 取前 n 個
                    top_n = set(result['numbers'][:n])
                    
                    if len(top_n & actual) >= 2:
                        hits_2_plus += 1
                    
                    total += 1
                except:
                    pass
            
            rate = (hits_2_plus / total) * 100 if total > 0 else 0
            print(f"Top {n:<6} | {rate:.2f}%")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, default=2025)
    args = parser.parse_args()
    
    analyze_top_n_hit_2(args.year)
