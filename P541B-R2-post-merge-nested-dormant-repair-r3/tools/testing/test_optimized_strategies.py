#!/usr/bin/env python3
"""
策略優化測試腳本
測試優化後的策略配置是否正常工作
"""

import sys
import os

# 添加項目路徑
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/Lottery/lottery_api')

from database import DatabaseManager
from models.unified_predictor import UnifiedPredictionEngine
from models.optimized_ensemble import OptimizedEnsemblePredictor

# 初始化數據庫管理器 - 使用絕對路徑
db_manager = DatabaseManager('/Users/kelvin/Kelvin-WorkSpace/Lottery/lottery_api/data/lottery.db')

# 彩票規則
LOTTERY_RULES = {
    'id': 'BIG_LOTTO',
    'name': '大樂透',
    'pickCount': 6,
    'minNumber': 1,
    'maxNumber': 49,
    'hasSpecialNumber': True
}


def test_optimized_strategies():
    """測試優化後的策略"""
    print("="*60)
    print("📊 策略優化測試")
    print("="*60)
    
    # 1. 獲取歷史數據
    print("\n1️⃣ 獲取歷史數據...")
    history = db_manager.get_all_draws('BIG_LOTTO')
    print(f"   ✅ 獲取 {len(history)} 筆歷史數據")
    
    if len(history) < 50:
        print("   ❌ 數據量不足，無法測試")
        return
    
    # 2. 初始化引擎
    print("\n2️⃣ 初始化預測引擎...")
    unified_engine = UnifiedPredictionEngine()
    ensemble_predictor = OptimizedEnsemblePredictor(unified_engine)
    
    # 顯示策略配置
    print("   📌 策略列表:")
    for name in ensemble_predictor.strategy_methods:
        weight = ensemble_predictor.RECOMMENDED_WEIGHTS.get(name, 0)
        print(f"      - {name}: {weight:.0%}")
    
    # 3. 計算策略權重
    print("\n3️⃣ 計算策略權重 (回測50期)...")
    weights = ensemble_predictor.calculate_strategy_weights(
        history, 
        LOTTERY_RULES,
        backtest_periods=50,
        training_window=100
    )
    
    print("\n   📊 最終權重分配:")
    for name, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(weight * 40)
        print(f"      {name:15s}: {weight:6.1%} {bar}")
    
    # 4. 執行預測
    print("\n4️⃣ 執行優化集成預測...")
    result = ensemble_predictor.predict(history, LOTTERY_RULES)
    
    print("\n   🎯 預測結果:")
    print(f"      第一注: {result['bet1']['numbers']} (信心度: {result['bet1']['confidence']:.1%})")
    print(f"      第二注: {result['bet2']['numbers']} (信心度: {result['bet2']['confidence']:.1%})")
    print(f"      整體信心度: {result['overall_confidence']:.1%}")
    
    # 5. 回測驗證 (最近10期)
    print("\n5️⃣ 回測驗證 (最近10期)...")
    
    hits_summary = []
    for i in range(10):
        test_draw = history[i]
        train_data = history[i+1:]  # 排除測試期
        
        # 預測
        pred_result = ensemble_predictor.predict(train_data, LOTTERY_RULES)
        predicted = set(pred_result['bet1']['numbers'])
        
        # 實際開獎
        actual = set(test_draw['numbers'])
        special = test_draw.get('special')
        if special is not None:
            actual.add(int(special))  # 加入特別號
        
        # 計算命中
        hits = len(predicted & actual)
        hits_summary.append(hits)
        
        hit_nums = predicted & actual
        print(f"      期號 {test_draw.get('draw', i)}: 命中 {hits} 個 {list(hit_nums) if hit_nums else ''}")
    
    avg_hits = sum(hits_summary) / len(hits_summary)
    success_count = sum(1 for h in hits_summary if h >= 3)
    
    print(f"\n   📈 回測統計:")
    print(f"      平均命中: {avg_hits:.2f} 個")
    print(f"      成功次數 (≥3命中): {success_count}/10 ({success_count*10}%)")
    
    # 對比理論機率
    theory_prob = 1.76  # 大樂透命中3個以上的理論機率
    actual_rate = success_count * 10
    improvement = (actual_rate - theory_prob) / theory_prob * 100 if theory_prob > 0 else 0
    
    print(f"      理論機率: {theory_prob}%")
    print(f"      實際機率: {actual_rate}%")
    if improvement > 0:
        print(f"      ✅ 比理論高 {improvement:.0f}%")
    else:
        print(f"      ⚠️ 比理論低 {abs(improvement):.0f}%")
    
    print("\n" + "="*60)
    print("✅ 測試完成!")
    print("="*60)


if __name__ == "__main__":
    test_optimized_strategies()
