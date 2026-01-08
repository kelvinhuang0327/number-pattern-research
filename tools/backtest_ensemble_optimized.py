#!/usr/bin/env python3
"""
優化後 Ensemble Stacking 回測
驗證 Top 3 方法組合的效果
"""
import sys
import os
import io
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.ensemble_stacking import EnsembleStackingPredictor

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def backtest_optimized_ensemble():
    """回測優化後的 Ensemble"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    
    ensemble = EnsembleStackingPredictor()
    
    test_periods = 118
    wins = 0
    match_3_plus = 0
    match_2_special = 0
    special_hits = 0
    total = 0
    
    match_distribution = Counter()
    
    print("=" * 80)
    print("🔬 優化後 Ensemble Stacking 回測 (Top 3: Markov + Bayesian + Trend)")
    print("=" * 80)
    print(f"測試期數: {test_periods} 期 (2025 全年)")
    print(f"模型配置: Markov (1.5x) + Bayesian (1.2x) + Trend (1.0x)")
    print("-" * 80)
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0:
            continue
        
        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        
        if len(hist) < 10:
            continue
        
        try:
            # 使用優化後的 Ensemble
            result = ensemble.predict_with_features(hist, rules, use_lstm=False)
            
            if not result or 'numbers' not in result:
                continue
            
            predicted = set(result['numbers'])
            actual = set(target_draw['numbers'])
            
            match_count = len(predicted & actual)
            special_match = result.get('special') == target_draw.get('special')
            
            match_distribution[match_count] += 1
            
            if special_match:
                special_hits += 1
            
            # 判定中獎
            if match_count >= 3:
                match_3_plus += 1
                wins += 1
            elif match_count >= 2 and special_match:
                match_2_special += 1
                wins += 1
            elif match_count >= 1 and special_match:
                wins += 1
            
            total += 1
            
        except Exception as e:
            continue
    
    if total == 0:
        print("❌ 測試失敗：無有效數據")
        return
    
    # 顯示結果
    win_rate = wins / total * 100
    match_3_rate = match_3_plus / total * 100
    match_2s_rate = match_2_special / total * 100
    special_rate = special_hits / total * 100
    
    print("\n" + "=" * 80)
    print("📊 回測結果")
    print("=" * 80)
    print(f"總勝率: {win_rate:.2f}%")
    print(f"Match-3+ 率: {match_3_rate:.2f}%")
    print(f"Match-2+S 率: {match_2s_rate:.2f}%")
    print(f"特別號命中率: {special_rate:.2f}%")
    print(f"測試期數: {total}")
    
    print("\n命中分佈:")
    for match_count in sorted(match_distribution.keys(), reverse=True):
        count = match_distribution[match_count]
        pct = count / total * 100
        bar = "█" * int(pct / 2)
        print(f"  Match-{match_count}: {count:3d} 次 ({pct:5.1f}%) {bar}")
    
    # 比較分析
    print("\n" + "=" * 80)
    print("📈 與原始方法比較")
    print("=" * 80)
    print(f"{'方法':<30} {'總勝率':<12} {'Match-3+':<12} {'特別號':<12}")
    print("-" * 80)
    print(f"{'馬可夫鏈 (單一最佳)':<30} {'16.10%':<12} {'4.24%':<12} {'21.19%':<12}")
    print(f"{'原始 Ensemble (5 方法)':<30} {'11.02%':<12} {'1.69%':<12} {'13.56%':<12}")
    print(f"{'優化 Ensemble (Top 3)':<30} {f'{win_rate:.2f}%':<12} {f'{match_3_rate:.2f}%':<12} {f'{special_rate:.2f}%':<12}")
    
    # 判定
    print("\n" + "=" * 80)
    print("💡 結論")
    print("=" * 80)
    
    if win_rate > 16.10:
        print(f"✅ 優化成功！Ensemble 勝率 ({win_rate:.2f}%) 超越單一最佳方法 (16.10%)")
    elif win_rate > 11.02:
        print(f"📈 有所改善！從 11.02% 提升至 {win_rate:.2f}%")
    else:
        print(f"⚠️ 仍需優化。當前 {win_rate:.2f}%，目標 >16.10%")
    
    if special_rate > 21.19:
        print(f"✅ 特別號預測超越馬可夫鏈！({special_rate:.2f}% vs 21.19%)")
    elif special_rate > 13.56:
        print(f"📈 特別號有改善！從 13.56% 提升至 {special_rate:.2f}%")

if __name__ == '__main__':
    backtest_optimized_ensemble()
