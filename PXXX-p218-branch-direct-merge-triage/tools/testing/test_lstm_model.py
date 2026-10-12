#!/usr/bin/env python3
"""
LSTM / 序列預測模型測試腳本
測試回退模式（不依賴 TensorFlow）
"""

import sys
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/Lottery/lottery_api')

import asyncio
from database import DatabaseManager

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


async def test_lstm():
    """測試序列預測模型"""
    print("="*70)
    print("🧠 序列預測模型測試")
    print("="*70)
    
    # 導入模型（在這裡導入避免初始化時崩潰）
    from models.lstm_model import LSTMPredictor, HAS_TF, HAS_SKLEARN
    
    print(f"\n1️⃣ 環境狀態:")
    print(f"   TensorFlow: {'✅ 可用' if HAS_TF else '❌ 不可用 (使用回退模式)'}")
    print(f"   Scikit-learn: {'✅ 可用' if HAS_SKLEARN else '❌ 不可用'}")
    
    # 獲取數據
    print("\n2️⃣ 獲取歷史數據...")
    history = db_manager.get_all_draws('BIG_LOTTO')
    print(f"   ✅ 獲取 {len(history)} 筆歷史數據")
    
    if len(history) < 100:
        print("   ❌ 數據量不足（至少需要100期）")
        return
    
    # 初始化預測器
    print("\n3️⃣ 初始化預測器...")
    lstm = LSTMPredictor()
    print(f"   使用模式: {'TensorFlow LSTM' if not lstm.use_fallback else '回退模式 (序列特徵)'}")
    
    # 執行預測
    print("\n4️⃣ 執行預測...")
    
    try:
        result = await lstm.predict(history, LOTTERY_RULES)
        
        print("\n   🎯 預測結果:")
        print(f"      號碼: {result['numbers']}")
        print(f"      信心度: {result['confidence']:.2%}")
        print(f"      方法: {result['method']}")
        if 'special' in result:
            print(f"      特別號: {result['special']}")
        
    except Exception as e:
        print(f"\n   ❌ 預測失敗: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 快速回測（5期）
    print("\n5️⃣ 快速回測驗證（5期）...")
    hits_list = []
    
    for i in range(5):
        test_draw = history[i]
        train_data = history[i+1:]
        
        try:
            pred = await lstm.predict(train_data, LOTTERY_RULES)
            predicted = set(pred['numbers'])
            
            actual = set(test_draw['numbers'])
            special = test_draw.get('special')
            if special is not None:
                actual.add(int(special))
            
            hits = len(predicted & actual)
            hits_list.append(hits)
            
            hit_nums = predicted & actual
            print(f"      期號 {test_draw.get('draw', i)}: 命中 {hits} 個 {list(hit_nums) if hit_nums else ''}")
            
        except Exception as e:
            print(f"      期號 {test_draw.get('draw', i)}: 失敗 - {e}")
    
    if hits_list:
        avg_hits = sum(hits_list) / len(hits_list)
        print(f"\n   📈 平均命中: {avg_hits:.2f} 個")
    
    print("\n" + "="*70)
    print("✅ 測試完成!")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(test_lstm())
