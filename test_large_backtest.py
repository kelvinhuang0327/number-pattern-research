#!/usr/bin/env python3
"""
大規模策略回測腳本
測試優化後的策略在更大樣本上的表現
"""

import sys
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/Lottery/lottery-api')

from database import DatabaseManager
from models.unified_predictor import UnifiedPredictionEngine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from collections import Counter

# 初始化
db_manager = DatabaseManager('/Users/kelvin/Kelvin-WorkSpace/Lottery/lottery-api/data/lottery.db')

LOTTERY_RULES = {
    'id': 'BIG_LOTTO',
    'name': '大樂透',
    'pickCount': 6,
    'minNumber': 1,
    'maxNumber': 49,
    'hasSpecialNumber': True
}


def run_large_backtest():
    """執行大規模回測"""
    print("="*70)
    print("📊 大規模策略回測測試 (100期回測)")
    print("="*70)
    
    # 獲取數據
    print("\n1️⃣ 獲取歷史數據...")
    history = db_manager.get_all_draws('BIG_LOTTO')
    print(f"   ✅ 獲取 {len(history)} 筆歷史數據")
    
    if len(history) < 200:
        print("   ❌ 數據量不足，無法進行大規模回測")
        return
    
    # 初始化
    unified_engine = UnifiedPredictionEngine()
    ensemble_predictor = OptimizedEnsemblePredictor(unified_engine)
    
    print("\n2️⃣ 策略配置:")
    for name, weight in ensemble_predictor.RECOMMENDED_WEIGHTS.items():
        print(f"      {name}: {weight:.0%}")
    
    # 回測參數
    test_periods = 100  # 測試100期
    training_window = 150  # 訓練窗口150期
    
    print(f"\n3️⃣ 開始回測 ({test_periods}期測試, {training_window}期訓練窗口)...")
    print("-"*70)
    
    hits_distribution = Counter()
    success_count = 0
    total_hits = 0
    
    for i in range(test_periods):
        test_draw = history[i]
        train_start = i + 1
        train_end = train_start + training_window
        
        if train_end > len(history):
            print(f"   ⚠️ 訓練數據不足，停止於第 {i} 期")
            break
        
        train_data = history[train_start:train_end]
        
        # 使用單注預測（更快）
        try:
            result = ensemble_predictor.predict_single(train_data, LOTTERY_RULES)
            predicted = set(result['numbers'])
        except Exception as e:
            print(f"   ❌ 預測失敗: {e}")
            continue
        
        # 實際開獎 (6個主號 + 1個特別號 = 7個目標)
        actual = set(test_draw['numbers'])
        special = test_draw.get('special')
        if special is not None:
            actual.add(int(special))
        
        # 計算命中
        hits = len(predicted & actual)
        hits_distribution[hits] += 1
        total_hits += hits
        
        if hits >= 3:
            success_count += 1
        
        # 進度顯示
        if (i + 1) % 20 == 0:
            print(f"   進度: {i+1}/{test_periods} ({(i+1)/test_periods*100:.0f}%)")
    
    # 統計結果
    actual_tests = sum(hits_distribution.values())
    avg_hits = total_hits / actual_tests if actual_tests > 0 else 0
    success_rate = success_count / actual_tests * 100 if actual_tests > 0 else 0
    
    print("\n" + "="*70)
    print("📈 回測結果統計")
    print("="*70)
    
    print(f"\n   測試總期數: {actual_tests}")
    print(f"   平均命中數: {avg_hits:.2f} 個/期")
    print(f"   成功次數 (≥3命中): {success_count} 次")
    print(f"   成功率: {success_rate:.2f}%")
    
    # 命中分布
    print("\n   命中分佈:")
    for hits in sorted(hits_distribution.keys()):
        count = hits_distribution[hits]
        pct = count / actual_tests * 100
        bar = "█" * int(pct)
        print(f"      {hits}個命中: {count:3d} 次 ({pct:5.1f}%) {bar}")
    
    # 對比理論機率
    theory_prob = 1.76  # 大樂透理論機率
    improvement = (success_rate - theory_prob) / theory_prob * 100 if theory_prob > 0 else 0
    
    print(f"\n   📊 vs 理論機率 ({theory_prob}%):")
    if improvement > 0:
        print(f"      ✅ 實際 {success_rate:.2f}%, 比理論高 {improvement:.0f}%")
    else:
        print(f"      ⚠️ 實際 {success_rate:.2f}%, 比理論低 {abs(improvement):.0f}%")
    
    # 策略權重摘要
    print("\n   📌 使用的策略權重:")
    weights = ensemble_predictor._cached_weights or ensemble_predictor.RECOMMENDED_WEIGHTS
    for name, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        print(f"      {name}: {weight:.1%}")
    
    print("\n" + "="*70)
    print("✅ 大規模回測完成!")
    print("="*70)


if __name__ == "__main__":
    run_large_backtest()
