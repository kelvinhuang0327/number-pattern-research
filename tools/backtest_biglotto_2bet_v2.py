#!/usr/bin/env python3
"""
V2 優化版回測
"""
import sys
import os
import io
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.biglotto_2bet_optimizer_v2 import BigLotto2BetOptimizerV2
from models.unified_predictor import UnifiedPredictionEngine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def backtest_v2():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    test_periods = min(150, len(all_draws) - 50)
    
    optimizer_v2 = BigLotto2BetOptimizerV2()
    engine = UnifiedPredictionEngine()
    
    wins_v2 = 0
    match_3_plus_v2 = 0
    
    wins_v1 = 0
    match_3_plus_v1 = 0
    
    total = 0
    
    print("=" * 80)
    print(f"🔬 雙注優化 V2 vs V1 對比回測 (最近 {test_periods} 期)")
    print("=" * 80)
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0:
            continue
        
        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        
        if len(hist) < 10:
            continue
        
        actual = set(target_draw['numbers'])
        
        # Test V2
        try:
            result_v2 = optimizer_v2.predict_2bets_optimized(hist, rules)
            
            period_win_v2 = False
            period_match3_v2 = False
            
            for bet in result_v2['bets']:
                predicted = set(bet['numbers'])
                match_count = len(predicted & actual)
                
                if match_count >= 3:
                    period_match3_v2 = True
                    period_win_v2 = True
                elif match_count >= 1:
                    period_win_v2 = True
            
            if period_match3_v2:
                match_3_plus_v2 += 1
            if period_win_v2:
                wins_v2 += 1
        except:
            pass
        
        # Test V1 baseline (單注偏差)
        try:
            result_v1 = engine.deviation_predict(hist, rules)
            predicted_v1 = set(result_v1['numbers'])
            match_v1 = len(predicted_v1 & actual)
            
            if match_v1 >= 3:
                match_3_plus_v1 += 1
                wins_v1 += 1
            elif match_v1 >= 1:
                wins_v1 += 1
        except:
            pass
        
        total += 1
    
    if total == 0:
        return
    
    match3_rate_v2 = match_3_plus_v2 / total * 100
    match3_rate_v1 = match_3_plus_v1 / total * 100
    improvement = match3_rate_v2 - match3_rate_v1
    
    print("\n" + "=" * 80)
    print("📊 V2 優化結果")
    print("=" * 80)
    print(f"{'方案':<30} {'Match-3+':<12} {'提升幅度':<12}")
    print("-" * 80)
    print(f"{'單注偏差分析 (基準)':<30} {match3_rate_v1:>10.2f}% {'-':>12}")
    print(f"{'雙注優化 V1':<30} {'4.00%':>12} {'+1.33%':>12}")
    print(f"{'🎯 雙注優化 V2 (新)':<30} {match3_rate_v2:>10.2f}% {improvement:>10.2f}%")
    
    print("\n" + "="*80)
    print("目標達成度:")
    if improvement >= 5.0:
        print(f"✅ 目標達成！提升 {improvement:.2f}% >= 5%")
    elif improvement >= 3.0:
        print(f"📈 顯著改善！提升 {improvement:.2f}%，接近目標")
    else:
        print(f"⚠️ 仍需優化。提升 {improvement:.2f}% < 5%")

if __name__ == '__main__':
    backtest_v2()
