#!/usr/bin/env python3
"""
方案 A 優化測試腳本 (Python 版)

測試優化後的 4 個策略：
1. Bayesian - 動態權重調整
2. Frequency - 自適應衰減係數
3. Odd_Even - 位置分佈增強
4. Hot_Cold - 動態窗口選擇
"""

import sys
import os

# 添加 lottery-api 目錄到路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lottery-api'))

from models.unified_predictor import prediction_engine
import random
from datetime import datetime, timedelta

def generate_test_data(count=100):
    """生成測試數據（大樂透格式）"""
    data = []
    start_date = datetime(2023, 1, 1)

    for i in range(count):
        date = start_date + timedelta(days=i * 3)

        # 隨機生成 6 個號碼（1-49）
        numbers = sorted(random.sample(range(1, 50), 6))

        data.append({
            'draw': f"2023{str(i+1).zfill(3)}",
            'date': date.strftime('%Y-%m-%d'),
            'numbers': numbers,
            'lotteryType': 'BIG_LOTTO',
            'year': 2023 + i // 100
        })

    return data

def test_strategy(strategy_name, display_name, history, lottery_rules):
    """測試單個策略"""
    print(f"\n🔍 測試: {display_name}")
    print("-" * 80)

    try:
        # 執行預測
        if strategy_name == 'bayesian':
            result = prediction_engine.bayesian_predict(history, lottery_rules)
        elif strategy_name == 'frequency':
            result = prediction_engine.frequency_predict(history, lottery_rules)
        elif strategy_name == 'odd_even':
            result = prediction_engine.odd_even_balance_predict(history, lottery_rules)
        elif strategy_name == 'hot_cold':
            result = prediction_engine.hot_cold_mix_predict(history, lottery_rules)
        else:
            print(f"❌ 未知策略: {strategy_name}")
            return False

        # 顯示結果
        print(f"✅ 預測成功")
        print(f"   號碼: {', '.join(map(str, result['numbers']))}")
        print(f"   信心度: {result['confidence'] * 100:.1f}%")
        print(f"   方法: {result['method']}")

        if result.get('probabilities'):
            probs = result['probabilities']
            if probs and len(probs) > 0:
                avg_prob = sum(probs) / len(probs)
                print(f"   平均概率: {avg_prob * 100:.2f}%")

        return True

    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主測試函數"""
    print("🚀 開始方案 A 優化測試\n")
    print("=" * 80)

    # 生成測試數據
    print("\n📊 生成測試數據...")
    test_data = generate_test_data(100)
    print(f"✅ 生成 {len(test_data)} 期測試數據\n")

    lottery_rules = {
        'pickCount': 6,
        'minNumber': 1,
        'maxNumber': 49,
        'lotteryType': 'BIG_LOTTO'
    }

    # 測試策略列表
    strategies = [
        ('bayesian', 'Bayesian (動態權重)'),
        ('frequency', 'Frequency (自適應衰減)'),
        ('odd_even', 'Odd_Even (位置分佈)'),
        ('hot_cold', 'Hot_Cold (動態窗口)')
    ]

    print("🧪 測試優化後的策略...")
    print("=" * 80)

    # 測試每個策略
    success_count = 0
    for strategy_name, display_name in strategies:
        if test_strategy(strategy_name, display_name, test_data, lottery_rules):
            success_count += 1

    print("\n" + "=" * 80)
    print(f"✅ 測試完成！成功: {success_count}/{len(strategies)}")
    print("\n💡 觀察要點：")
    print("   1. Bayesian 信心度是否提升（目標: 0.68 → 0.74-0.82）")
    print("   2. Frequency 信心度是否提升（目標: 動態 → 0.70-0.90）")
    print("   3. Odd_Even 信心度是否提升（目標: 0.55 → 0.63-0.70）")
    print("   4. Hot_Cold 信心度是否提升（目標: 0.62 → 0.68-0.74）")
    print("\n📈 預期整體提升: +8-15%")

if __name__ == '__main__':
    print("🎯 方案 A 優化測試腳本 (Python 版)")
    print("=" * 80)
    main()
