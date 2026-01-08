#!/usr/bin/env python3
"""
大樂透雙注覆蓋優化回測
驗證短期方案是否能達成 Match-3+ 率提升 5% 的目標
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
from models.biglotto_2bet_optimizer import BigLotto2BetOptimizer
from models.unified_predictor import UnifiedPredictionEngine

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def backtest_2bet_optimizer():
    """回測雙注優化器"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    # 測試最近 150 期
    test_periods = min(150, len(all_draws) - 50)  # 確保有足夠的訓練數據
    
    optimizer = BigLotto2BetOptimizer()
    engine = UnifiedPredictionEngine()
    
    # 統計數據
    wins_2bet = 0
    match_3_plus_2bet = 0
    
    wins_1bet_deviation = 0
    match_3_plus_1bet_deviation = 0
    
    wins_1bet_markov = 0
    match_3_plus_1bet_markov = 0
    
    total = 0
    
    match_dist_2bet = Counter()
    match_dist_1bet_dev = Counter()
    match_dist_1bet_mar = Counter()
    
    print("=" * 80)
    print(f"🔬 大樂透雙注覆蓋優化回測 (最近 {test_periods} 期)")
    print("=" * 80)
    print(f"測試期數: {test_periods} 期")
    print(f"比較方案:")
    print(f"  1. 雙注覆蓋優化（新方案）")
    print(f"  2. 單注偏差分析（當前最佳）")
    print(f"  3. 單注馬可夫鏈（威力彩最佳）")
    print("-" * 80)
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0:
            continue
        
        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        
        if len(hist) < 10:
            continue
        
        actual = set(target_draw['numbers'])
        
        try:
            # 測試雙注優化
            result_2bet = optimizer.predict_2bets(hist, rules)
            
            # 檢查雙注中是否有中獎
            period_win_2bet = False
            period_match3_2bet = False
            max_match_2bet = 0
            
            for bet in result_2bet['bets']:
                predicted = set(bet['numbers'])
                match_count = len(predicted & actual)
                max_match_2bet = max(max_match_2bet, match_count)
                
                if match_count >= 3:
                    period_match3_2bet = True
                    period_win_2bet = True
                elif match_count >= 1:
                    period_win_2bet = True
            
            match_dist_2bet[max_match_2bet] += 1
            
            if period_match3_2bet:
                match_3_plus_2bet += 1
            if period_win_2bet:
                wins_2bet += 1
            
        except Exception as e:
            continue
        
        try:
            # 測試單注偏差分析
            result_dev = engine.deviation_predict(hist, rules)
            predicted_dev = set(result_dev['numbers'])
            match_dev = len(predicted_dev & actual)
            
            match_dist_1bet_dev[match_dev] += 1
            
            if match_dev >= 3:
                match_3_plus_1bet_deviation += 1
                wins_1bet_deviation += 1
            elif match_dev >= 1:
                wins_1bet_deviation += 1
        
        except Exception as e:
            pass
        
        try:
            # 測試單注馬可夫鏈
            result_mar = engine.markov_predict(hist, rules)
            predicted_mar = set(result_mar['numbers'])
            match_mar = len(predicted_mar & actual)
            
            match_dist_1bet_mar[match_mar] += 1
            
            if match_mar >= 3:
                match_3_plus_1bet_markov += 1
                wins_1bet_markov += 1
            elif match_mar >= 1:
                wins_1bet_markov += 1
        
        except Exception as e:
            pass
        
        total += 1
    
    if total == 0:
        print("❌ 測試失敗：無有效數據")
        return
    
    # 顯示結果
    print("\n" + "=" * 80)
    print("📊 回測結果")
    print("=" * 80)
    
    # 雙注優化
    win_rate_2bet = wins_2bet / total * 100
    match3_rate_2bet = match_3_plus_2bet / total * 100
    
    # 單注偏差
    win_rate_1bet_dev = wins_1bet_deviation / total * 100
    match3_rate_1bet_dev = match_3_plus_1bet_deviation / total * 100
    
    # 單注馬可夫
    win_rate_1bet_mar = wins_1bet_markov / total * 100
    match3_rate_1bet_mar = match_3_plus_1bet_markov / total * 100
    
    print(f"\n{'方案':<30} {'Match-3+ 率':<15} {'提升幅度':<15} {'總勝率':<15}")
    print("-" * 80)
    
    baseline = match3_rate_1bet_dev
    
    print(f"{'單注偏差分析 (基準)':<30} {match3_rate_1bet_dev:>13.2f}% {'-':>15} {win_rate_1bet_dev:>13.2f}%")
    print(f"{'單注馬可夫鏈':<30} {match3_rate_1bet_mar:>13.2f}% {match3_rate_1bet_mar - baseline:>13.2f}% {win_rate_1bet_mar:>13.2f}%")
    
    improvement = match3_rate_2bet - baseline
    print(f"{'🎯 雙注覆蓋優化 (新方案)':<30} {match3_rate_2bet:>13.2f}% {improvement:>13.2f}% {win_rate_2bet:>13.2f}%")
    
    # 判定結果
    print("\n" + "=" * 80)
    print("🎯 目標達成度評估")
    print("=" * 80)
    print(f"目標: Match-3+ 率提升 5%")
    print(f"實際提升: {improvement:.2f}%")
    
    if improvement >= 5.0:
        print(f"✅ 目標達成！提升 {improvement:.2f}% >= 5%")
    elif improvement >= 3.0:
        print(f"📈 接近目標！提升 {improvement:.2f}%，需要進一步優化")
    else:
        print(f"⚠️ 未達目標。提升 {improvement:.2f}% < 5%，需要調整策略")
    
    # 詳細分佈
    print("\n" + "=" * 80)
    print("📊 命中分佈詳情")
    print("=" * 80)
    
    print(f"\n雙注優化:")
    for match_count in sorted(match_dist_2bet.keys(), reverse=True):
        count = match_dist_2bet[match_count]
        pct = count / total * 100
        bar = "█" * int(pct / 2)
        print(f"  Match-{match_count}: {count:3d} 次 ({pct:5.1f}%) {bar}")
    
    print(f"\n單注偏差分析:")
    for match_count in sorted(match_dist_1bet_dev.keys(), reverse=True):
        count = match_dist_1bet_dev[match_count]
        pct = count / total * 100
        bar = "█" * int(pct / 2)
        print(f"  Match-{match_count}: {count:3d} 次 ({pct:5.1f}%) {bar}")
    
    # 成本效益分析
    print("\n" + "=" * 80)
    print("💰 成本效益分析")
    print("=" * 80)
    print(f"單注成本: 1 單位")
    print(f"雙注成本: 2 單位")
    print(f"\n單注偏差分析 Match-3+ 率: {match3_rate_1bet_dev:.2f}%")
    print(f"雙注優化 Match-3+ 率: {match3_rate_2bet:.2f}%")
    print(f"\n成本效益比 (雙注): {match3_rate_2bet / 2:.2f}% per 單位")
    print(f"成本效益比 (單注): {match3_rate_1bet_dev:.2f}% per 單位")
    
    if match3_rate_2bet / 2 > match3_rate_1bet_dev:
        print(f"✅ 雙注方案性價比更高")
    else:
        print(f"⚠️ 單注方案性價比更高，建議調整策略")

if __name__ == '__main__':
    backtest_2bet_optimizer()
