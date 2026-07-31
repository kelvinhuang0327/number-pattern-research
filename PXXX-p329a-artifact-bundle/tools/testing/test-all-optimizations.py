#!/usr/bin/env python3
"""
完整優化測試腳本 (方案 A + B)

測試所有 7 個優化策略：
方案 A (4個):
1. Bayesian - 動態權重調整
2. Frequency - 自適應衰減係數
3. Odd_Even - 位置分佈增強
4. Hot_Cold - 動態窗口選擇

方案 B (3個):
5. Markov - 多階轉移矩陣
6. Zone_Balance - 動態區域劃分
7. Sum_Range - 多特徵增強
"""

import sys
import os

# 添加 lottery_api 目錄到路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lottery_api'))

from models.unified_predictor import prediction_engine
import random
from datetime import datetime, timedelta

def generate_test_data(count=150):
    """生成測試數據"""
    data = []
    start_date = datetime(2023, 1, 1)

    for i in range(count):
        date = start_date + timedelta(days=i * 3)
        numbers = sorted(random.sample(range(1, 50), 6))

        data.append({
            'draw': f"2023{str(i+1).zfill(3)}",
            'date': date.strftime('%Y-%m-%d'),
            'numbers': numbers,
            'lotteryType': 'BIG_LOTTO',
            'year': 2023 + i // 100
        })

    return data

def test_strategy(strategy_name, display_name, history, lottery_rules, baseline, target_range):
    """測試單個策略"""
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
        elif strategy_name == 'markov':
            result = prediction_engine.markov_predict(history, lottery_rules)
        elif strategy_name == 'zone_balance':
            result = prediction_engine.zone_balance_predict(history, lottery_rules)
        elif strategy_name == 'sum_range':
            result = prediction_engine.sum_range_predict(history, lottery_rules)
        else:
            return None

        confidence = result['confidence']

        # 計算提升
        improvement = (confidence - baseline) / baseline * 100

        # 檢查是否在目標範圍
        target_min, target_max = target_range
        in_range = target_min <= confidence <= target_max

        return {
            'name': display_name,
            'numbers': result['numbers'],
            'confidence': confidence,
            'method': result['method'],
            'baseline': baseline,
            'improvement': improvement,
            'target': f"{target_min:.2f}-{target_max:.2f}",
            'in_range': in_range
        }

    except Exception as e:
        print(f"❌ {display_name} 測試失敗: {str(e)}")
        return None

def main():
    """主測試函數"""
    print("=" * 90)
    print("🚀 完整優化測試 - 方案 A + B (7 個策略)")
    print("=" * 90)

    # 生成測試數據
    print("\n📊 生成測試數據...")
    test_data = generate_test_data(150)
    print(f"✅ 生成 {len(test_data)} 期測試數據\n")

    lottery_rules = {
        'pickCount': 6,
        'minNumber': 1,
        'maxNumber': 49,
        'lotteryType': 'BIG_LOTTO'
    }

    # 定義所有策略
    strategies = [
        # 方案 A
        ('bayesian', 'Bayesian (動態權重)', 0.68, (0.74, 0.82)),
        ('frequency', 'Frequency (自適應衰減)', 0.61, (0.70, 0.90)),
        ('odd_even', 'Odd_Even (位置分佈)', 0.55, (0.63, 0.70)),
        ('hot_cold', 'Hot_Cold (動態窗口)', 0.62, (0.68, 0.74)),
        # 方案 B
        ('markov', 'Markov (多階轉移)', 0.65, (0.73, 0.77)),
        ('zone_balance', 'Zone_Balance (動態區域)', 0.58, (0.64, 0.70)),
        ('sum_range', 'Sum_Range (多特徵)', 0.70, (0.76, 0.80)),
    ]

    print("🧪 測試所有優化策略...")
    print("=" * 90)
    print(f"{'策略':<25} {'基線':<8} {'現值':<8} {'目標範圍':<14} {'提升':<10} {'狀態'}")
    print("-" * 90)

    results = []
    for name, display, baseline, target in strategies:
        result = test_strategy(name, display, test_data, lottery_rules, baseline, target)
        if result:
            results.append(result)
            status = "✅ 達標" if result['in_range'] else "⚠️  超標" if result['confidence'] > target[1] else "❌ 未達"
            print(f"{result['name']:<25} {result['baseline']:<8.2f} {result['confidence']:<8.2f} "
                  f"{result['target']:<14} {result['improvement']:>7.1f}%  {status}")

    # 統計總結
    print("\n" + "=" * 90)
    print("📊 優化總結")
    print("=" * 90)

    total_strategies = len(results)
    achieved = sum(1 for r in results if r['in_range'])
    over_target = sum(1 for r in results if r['confidence'] > r['baseline'] and not r['in_range'])
    avg_improvement = sum(r['improvement'] for r in results) / len(results)

    print(f"✅ 測試策略數: {total_strategies}")
    print(f"✅ 達標策略數: {achieved} ({achieved/total_strategies*100:.1f}%)")
    print(f"📈 平均提升: +{avg_improvement:.1f}%")
    print(f"🎯 最高提升: +{max(r['improvement'] for r in results):.1f}% ({max(results, key=lambda x: x['improvement'])['name']})")
    print(f"📉 最低提升: +{min(r['improvement'] for r in results):.1f}% ({min(results, key=lambda x: x['improvement'])['name']})")

    # 顯示實施細節
    print("\n" + "=" * 90)
    print("🔧 實施細節")
    print("=" * 90)

    print("\n方案 A (保守優化)：")
    print("  1. Bayesian: 動態權重調整 (數據量 + 穩定性)")
    print("  2. Frequency: 自適應衰減係數 (高/低頻號碼差異化)")
    print("  3. Odd_Even: 位置分佈增強 (分析每位奇偶偏好)")
    print("  4. Hot_Cold: 動態窗口選擇 (測試多窗口選最穩)")

    print("\n方案 B (進階優化)：")
    print("  5. Markov: 多階轉移矩陣 (1-3階自適應)")
    print("  6. Zone_Balance: 動態區域劃分 (K-means聚類)")
    print("  7. Sum_Range: 多特徵增強 (和值+AC+奇偶+跨度)")

    print("\n" + "=" * 90)

if __name__ == '__main__':
    main()
