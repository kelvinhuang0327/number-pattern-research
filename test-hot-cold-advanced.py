#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 Hot_Cold 進階優化效果

目標：將信心度從 0.65 提升到 0.68-0.74
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'lottery-api'))

from models.unified_predictor import UnifiedPredictionEngine
import random
import numpy as np

def generate_test_data(periods=100):
    """生成測試數據"""
    history = []

    # 模擬冷熱號碼轉換的真實場景
    hot_pool = list(range(1, 20))  # 初始熱門池

    for i in range(periods):
        # 每 15 期調整一次熱門池（模擬趨勢變化）
        if i % 15 == 0 and i > 0:
            # 部分號碼從熱轉冷
            old_hot = random.sample(hot_pool, k=min(5, len(hot_pool)))
            hot_pool = [n for n in hot_pool if n not in old_hot]

            # 新號碼從冷轉熱
            cold_pool = [n for n in range(1, 50) if n not in hot_pool]
            new_hot = random.sample(cold_pool, k=5)
            hot_pool.extend(new_hot)

        # 70% 從熱門池選，30% 從全部選（模擬真實混合）
        numbers = []
        hot_count = random.randint(3, 5)
        cold_count = 6 - hot_count

        # 從熱門池選
        if len(hot_pool) >= hot_count:
            numbers.extend(random.sample(hot_pool, hot_count))
        else:
            numbers.extend(hot_pool)
            hot_count = len(hot_pool)
            cold_count = 6 - hot_count

        # 從冷門池選
        cold_pool = [n for n in range(1, 50) if n not in numbers]
        if len(cold_pool) >= cold_count:
            numbers.extend(random.sample(cold_pool, cold_count))

        # 確保有 6 個號碼
        while len(numbers) < 6:
            remaining = [n for n in range(1, 50) if n not in numbers]
            if remaining:
                numbers.append(random.choice(remaining))

        history.append({
            'period': f'TEST{i+1:03d}',
            'numbers': sorted(numbers[:6])
        })

    return history

def test_hot_cold_strategy():
    """測試 Hot_Cold 策略"""
    print("=" * 60)
    print("🔥 測試 Hot_Cold 進階優化")
    print("=" * 60)

    predictor = UnifiedPredictionEngine()
    lottery_rules = {
        'pickCount': 6,
        'minNumber': 1,
        'maxNumber': 49
    }

    # 生成測試數據
    print("\n📊 生成測試數據 (100 期，含冷熱轉換)...")
    history = generate_test_data(100)

    # 測試預測
    print("\n🎯 執行預測...")
    total_matches = 0
    total_tests = 20
    confidence_scores = []

    for test_idx in range(total_tests):
        # 使用前 80+test_idx 期預測下一期
        train_data = history[:80 + test_idx]
        actual = history[80 + test_idx]['numbers']

        result = predictor.hot_cold_mix_predict(train_data, lottery_rules)
        predicted = result['numbers']
        confidence = result['confidence']

        # 計算命中數
        matches = len(set(predicted) & set(actual))
        total_matches += matches
        confidence_scores.append(confidence)

        if test_idx < 5:  # 顯示前 5 次詳細結果
            print(f"\n測試 {test_idx + 1}:")
            print(f"  預測: {predicted}")
            print(f"  實際: {actual}")
            print(f"  命中: {matches}/6")
            print(f"  信心度: {confidence:.3f}")
            print(f"  方法: {result['method']}")

    # 計算平均信心度
    avg_confidence = np.mean(confidence_scores)
    std_confidence = np.std(confidence_scores)
    avg_match_rate = total_matches / (total_tests * 6)

    print("\n" + "=" * 60)
    print("📈 測試結果")
    print("=" * 60)
    print(f"總測試次數: {total_tests}")
    print(f"總命中數: {total_matches}/{total_tests * 6}")
    print(f"平均命中率: {avg_match_rate:.3f} ({avg_match_rate * 100:.1f}%)")
    print(f"平均信心度: {avg_confidence:.3f} ± {std_confidence:.3f}")
    print(f"信心度範圍: [{min(confidence_scores):.3f}, {max(confidence_scores):.3f}]")

    # 評估是否達標
    target_min = 0.68
    target_max = 0.74

    print("\n" + "=" * 60)
    print("🎯 目標達成評估")
    print("=" * 60)
    print(f"目標範圍: {target_min:.2f} - {target_max:.2f}")
    print(f"實際信心度: {avg_confidence:.3f}")

    if target_min <= avg_confidence <= target_max:
        print("✅ 達標！Hot_Cold 策略優化成功")
        improvement = ((avg_confidence - 0.65) / 0.65) * 100
        print(f"📊 提升幅度: +{improvement:.1f}%")
    elif avg_confidence > target_max:
        print(f"✅ 超出目標！信心度達到 {avg_confidence:.3f}")
        improvement = ((avg_confidence - 0.65) / 0.65) * 100
        print(f"📊 提升幅度: +{improvement:.1f}%")
    else:
        gap = target_min - avg_confidence
        print(f"⚠️  未達標，差距 {gap:.3f}")
        improvement = ((avg_confidence - 0.65) / 0.65) * 100
        if improvement > 0:
            print(f"📊 已提升: +{improvement:.1f}%")

    return avg_confidence

def test_optimization_features():
    """測試新增的優化功能"""
    print("\n" + "=" * 60)
    print("🔬 測試新增優化功能")
    print("=" * 60)

    predictor = UnifiedPredictionEngine()
    history = generate_test_data(100)
    lottery_rules = {
        'pickCount': 6,
        'minNumber': 1,
        'maxNumber': 49
    }

    print("\n1️⃣ 測試多窗口融合分析...")
    scores = predictor._multi_window_temperature_analysis(
        history, 1, 49, 6
    )
    print(f"   ✓ 返回 {len(scores)} 個號碼的溫度得分")
    top_5 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
    print(f"   ✓ Top 5 熱號: {[num for num, _ in top_5]}")

    print("\n2️⃣ 測試冷熱轉移檢測...")
    transitions = predictor._detect_hot_cold_transitions(history, 1, 49)
    print(f"   ✓ 返回 {len(transitions)} 個號碼的轉移得分")
    # 找出上升趨勢最強的號碼
    rising = sorted(transitions.items(), key=lambda x: x[1], reverse=True)[:5]
    print(f"   ✓ 上升趨勢最強: {[num for num, _ in rising]}")

    print("\n3️⃣ 測試溫度分級系統...")
    temp_levels = predictor._classify_temperature_levels(scores, 6)
    level_counts = {}
    for level in temp_levels.values():
        level_counts[level] = level_counts.get(level, 0) + 1
    print(f"   ✓ 溫度分級統計:")
    for level in ['very_hot', 'hot', 'warm', 'cool', 'cold', 'very_cold']:
        count = level_counts.get(level, 0)
        print(f"      {level}: {count} 個號碼")

    print("\n4️⃣ 測試多窗口一致性計算...")
    predicted = [num for num, _ in top_5]
    consistency = predictor._calculate_multi_window_consistency(scores, predicted)
    print(f"   ✓ 一致性得分: {consistency:.3f}")

    print("\n5️⃣ 測試轉移穩定性計算...")
    stability = predictor._calculate_transition_stability(transitions, predicted)
    print(f"   ✓ 穩定性得分: {stability:.3f}")

    print("\n✅ 所有優化功能測試完成")

if __name__ == '__main__':
    print("🚀 Hot_Cold 進階優化測試")
    print("=" * 60)

    # 測試優化功能
    test_optimization_features()

    # 測試整體性能
    print("\n" * 2)
    final_confidence = test_hot_cold_strategy()

    print("\n" + "=" * 60)
    print("🎉 測試完成")
    print("=" * 60)
