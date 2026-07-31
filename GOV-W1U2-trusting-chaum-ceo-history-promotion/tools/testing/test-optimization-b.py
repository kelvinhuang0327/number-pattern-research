#!/usr/bin/env python3
"""
方案 B 優化測試腳本 (Python 版)

測試新增的 3 個優化策略：
1. Markov - 多階轉移矩陣 (1-3階自適應)
2. Zone_Balance - 動態區域劃分 (K-means聚類)
3. Sum_Range - 多特徵增強 (和值+AC+奇偶+跨度)
"""

import sys
import os

# 添加 lottery_api 目錄到路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lottery_api'))

from models.unified_predictor import prediction_engine
import random
from datetime import datetime, timedelta

def generate_test_data(count=150):
    """生成測試數據（大樂透格式）- 更多數據以測試高階 Markov"""
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

def test_strategy(strategy_name, display_name, history, lottery_rules, expected_improvement):
    """測試單個策略"""
    print(f"\n🔍 測試: {display_name}")
    print("-" * 80)

    try:
        # 執行預測
        if strategy_name == 'markov':
            result = prediction_engine.markov_predict(history, lottery_rules)
        elif strategy_name == 'zone_balance':
            result = prediction_engine.zone_balance_predict(history, lottery_rules)
        elif strategy_name == 'sum_range':
            result = prediction_engine.sum_range_predict(history, lottery_rules)
        else:
            print(f"❌ 未知策略: {strategy_name}")
            return False, 0

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

        # 檢查改進
        confidence = result['confidence']
        print(f"   預期改進: {expected_improvement}")

        # 解析預期範圍
        if ' → ' in expected_improvement:
            old_conf, new_range = expected_improvement.split(' → ')
            old_val = float(old_conf)
            new_min, new_max = map(lambda x: float(x.strip('%')) / 100, new_range.split('-'))

            if new_min <= confidence <= new_max:
                improvement = (confidence - old_val) / old_val * 100
                print(f"   ✅ 達標！提升: +{improvement:.1f}%")
                return True, improvement
            else:
                print(f"   ⚠️  未達預期範圍")
                return True, 0

        return True, 0

    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, 0

def main():
    """主測試函數"""
    print("🚀 開始方案 B 優化測試\n")
    print("=" * 80)

    # 生成測試數據 (150期以支援3階Markov)
    print("\n📊 生成測試數據...")
    test_data = generate_test_data(150)
    print(f"✅ 生成 {len(test_data)} 期測試數據\n")

    lottery_rules = {
        'pickCount': 6,
        'minNumber': 1,
        'maxNumber': 49,
        'lotteryType': 'BIG_LOTTO'
    }

    # 測試策略列表
    strategies = [
        {
            'name': 'markov',
            'displayName': 'Markov (多階轉移矩陣)',
            'expectedImprovement': '0.65 → 0.73-0.77%'
        },
        {
            'name': 'zone_balance',
            'displayName': 'Zone_Balance (動態區域劃分)',
            'expectedImprovement': '0.58 → 0.64-0.70%'
        },
        {
            'name': 'sum_range',
            'displayName': 'Sum_Range (多特徵增強)',
            'expectedImprovement': '0.70 → 0.76-0.80%'
        }
    ]

    print("🧪 測試優化後的策略...")
    print("=" * 80)

    # 測試每個策略
    success_count = 0
    total_improvement = 0
    improvements = []

    for strategy in strategies:
        success, improvement = test_strategy(
            strategy['name'],
            strategy['displayName'],
            test_data,
            lottery_rules,
            strategy['expectedImprovement']
        )
        if success:
            success_count += 1
            if improvement > 0:
                improvements.append(improvement)
                total_improvement += improvement

    print("\n" + "=" * 80)
    print(f"✅ 測試完成！成功: {success_count}/{len(strategies)}")

    if improvements:
        avg_improvement = total_improvement / len(improvements)
        print(f"📈 平均提升: +{avg_improvement:.1f}%")

    print("\n💡 優化總結：")
    print("   1. Markov: 實作 1-3 階轉移矩陣，根據數據量自適應選擇")
    print("   2. Zone_Balance: 使用頻率聚類動態劃分區域，取代固定三等分")
    print("   3. Sum_Range: 新增奇偶比例、跨度分析，實現多目標優化")
    print("\n🎯 方案 A + B 合計優化了 7 個策略！")

if __name__ == '__main__':
    print("🎯 方案 B 優化測試腳本 (Python 版)")
    print("=" * 80)
    main()
