#!/usr/bin/env python3
"""
模型比較腳本
比較不同預測模型的回測表現
"""

import sys
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/Lottery/lottery_api')

import asyncio
from database import DatabaseManager
from collections import Counter

# 初始化
db_manager = DatabaseManager('/Users/kelvin/Kelvin-WorkSpace/Lottery/lottery_api/data/lottery.db')

LOTTERY_RULES = {
    'id': 'BIG_LOTTO',
    'name': '大樂透',
    'pickCount': 6,
    'minNumber': 1,
    'maxNumber': 49,
    'hasSpecialNumber': True
}


async def backtest_model(model, history, test_periods=20, train_window=150):
    """對模型進行回測"""
    hits_list = []
    success_count = 0
    
    for i in range(test_periods):
        test_draw = history[i]
        train_data = history[i+1:i+1+train_window]
        
        if len(train_data) < 50:
            break
        
        try:
            result = await model.predict(train_data, LOTTERY_RULES)
            predicted = set(result['numbers'])
            
            actual = set(test_draw['numbers'])
            special = test_draw.get('special')
            if special is not None:
                actual.add(int(special))
            
            hits = len(predicted & actual)
            hits_list.append(hits)
            
            if hits >= 3:
                success_count += 1
                
        except Exception as e:
            print(f"   ⚠️ 預測失敗: {e}")
            hits_list.append(0)
    
    return {
        'avg_hits': sum(hits_list) / len(hits_list) if hits_list else 0,
        'success_rate': success_count / len(hits_list) * 100 if hits_list else 0,
        'hit_distribution': dict(Counter(hits_list)),
        'total_tests': len(hits_list)
    }


async def main():
    print("="*70)
    print("📊 模型比較測試")
    print("="*70)
    
    # 獲取數據
    print("\n1️⃣ 獲取歷史數據...")
    history = db_manager.get_all_draws('BIG_LOTTO')
    print(f"   ✅ 獲取 {len(history)} 筆歷史數據")
    
    if len(history) < 200:
        print("   ❌ 數據量不足")
        return
    
    # 要測試的模型
    models_to_test = {}
    
    # 1. LSTM (PyTorch)
    print("\n2️⃣ 初始化模型...")
    try:
        from models.lstm_model import LSTMPredictor, HAS_PYTORCH
        models_to_test['LSTM (PyTorch)' if HAS_PYTORCH else 'LSTM (Fallback)'] = LSTMPredictor()
        print(f"   ✅ LSTM: {'PyTorch' if HAS_PYTORCH else 'Fallback'} 模式")
    except Exception as e:
        print(f"   ❌ LSTM 載入失敗: {e}")
    
    # 2. 優化集成預測
    try:
        from models.unified_predictor import UnifiedPredictionEngine
        from models.optimized_ensemble import OptimizedEnsemblePredictor
        unified_engine = UnifiedPredictionEngine()
        ensemble = OptimizedEnsemblePredictor(unified_engine)
        
        # 包裝為 async
        class EnsembleWrapper:
            def __init__(self, predictor):
                self.predictor = predictor
            async def predict(self, history, rules):
                return self.predictor.predict_single(history, rules)
        
        models_to_test['Optimized Ensemble'] = EnsembleWrapper(ensemble)
        print("   ✅ Optimized Ensemble")
    except Exception as e:
        print(f"   ❌ Ensemble 載入失敗: {e}")
    
    # 3. 單一策略 - 頻率分析
    try:
        class FrequencyWrapper:
            def __init__(self, engine):
                self.engine = engine
            async def predict(self, history, rules):
                return self.engine.frequency_predict(history, rules)
        
        models_to_test['Frequency'] = FrequencyWrapper(unified_engine)
        print("   ✅ Frequency Analysis")
    except Exception as e:
        print(f"   ❌ Frequency 載入失敗: {e}")
    
    # 4. 區域平衡
    try:
        class ZoneWrapper:
            def __init__(self, engine):
                self.engine = engine
            async def predict(self, history, rules):
                return self.engine.zone_balance_predict(history, rules)
        
        models_to_test['Zone Balance'] = ZoneWrapper(unified_engine)
        print("   ✅ Zone Balance")
    except Exception as e:
        print(f"   ❌ Zone Balance 載入失敗: {e}")
    
    # 回測比較
    print("\n3️⃣ 開始回測比較 (每個模型測試 20 期)...")
    print("-"*70)
    
    results = {}
    for name, model in models_to_test.items():
        print(f"\n   🔄 測試 {name}...")
        try:
            result = await backtest_model(model, history, test_periods=20, train_window=150)
            results[name] = result
            print(f"      平均命中: {result['avg_hits']:.2f}, 成功率: {result['success_rate']:.1f}%")
        except Exception as e:
            print(f"      ❌ 測試失敗: {e}")
    
    # 結果比較
    print("\n" + "="*70)
    print("📈 模型比較結果")
    print("="*70)
    
    print(f"\n{'模型':<25} {'平均命中':<12} {'成功率':<12} {'命中分佈'}")
    print("-"*70)
    
    for name, result in sorted(results.items(), key=lambda x: x[1]['avg_hits'], reverse=True):
        dist = result['hit_distribution']
        dist_str = ', '.join([f"{k}:{v}" for k, v in sorted(dist.items())])
        print(f"{name:<25} {result['avg_hits']:<12.2f} {result['success_rate']:<12.1f}% {dist_str}")
    
    # 理論機率比較
    print("\n" + "-"*70)
    theory_prob = 1.76  # 大樂透命中≥3的理論機率
    print(f"📊 理論機率 (≥3命中): {theory_prob}%")
    
    best_model = max(results.items(), key=lambda x: x[1]['avg_hits']) if results else None
    if best_model:
        improvement = (best_model[1]['success_rate'] - theory_prob) / theory_prob * 100 if theory_prob > 0 else 0
        print(f"🏆 最佳模型: {best_model[0]}")
        if improvement > 0:
            print(f"   ✅ 比理論高 {improvement:.0f}%")
        else:
            print(f"   ⚠️ 比理論低 {abs(improvement):.0f}%")
    
    print("\n" + "="*70)
    print("✅ 模型比較完成!")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
