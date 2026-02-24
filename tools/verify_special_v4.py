#!/usr/bin/env python3
"""
V3 vs V4 特別號預測驗證腳本
驗證「聯合機率」邏輯是否真的有效
"""
import os
import sys
import random
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.special_predictor import PowerLottoSpecialPredictor

def run_backtest(periods=1000, seed=42):
    """執行 V3 vs V4 回測比較"""
    random.seed(seed)
    np.random.seed(seed)

    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    draws = db.get_all_draws('POWER_LOTTO')
    history = sorted(draws, key=lambda x: (x['date'], x['draw']))
    rules = get_lottery_rules('POWER_LOTTO')

    print(f"總期數: {len(history)}")
    print(f"測試期數: {periods}")
    print(f"隨機種子: {seed}")
    print("=" * 60)

    # 確保有足夠數據
    if len(history) < periods + 100:
        print(f"數據不足，需要至少 {periods + 100} 期")
        return

    # 統計變量
    v3_hits = 0  # V3: 不傳 main_numbers
    v4_hits = 0  # V4: 傳入 main_numbers (使用實際開獎主號模擬)
    v4_random_hits = 0  # V4: 傳入隨機主號
    random_hits = 0  # 純隨機基準

    start_idx = len(history) - periods

    for i in range(start_idx, len(history)):
        # 訓練數據: 只使用 i 之前的數據
        train_history = history[:i]

        # 實際開獎結果
        actual = history[i]
        actual_special = actual.get('special')
        actual_numbers = actual.get('numbers', [])
        if isinstance(actual_numbers, str):
            import json
            actual_numbers = json.loads(actual_numbers) if actual_numbers.startswith('[') else [int(n) for n in actual_numbers.split(',')]

        if not actual_special:
            continue

        sp = PowerLottoSpecialPredictor(rules)

        # V3: 不傳 main_numbers (原本的行為)
        v3_pred = sp.predict_top_n(train_history, n=1, main_numbers=None)[0]
        if v3_pred == actual_special:
            v3_hits += 1

        # V4: 傳入實際開獎主號 (這是作弊，用於測試關聯是否存在)
        v4_pred = sp.predict_top_n(train_history, n=1, main_numbers=actual_numbers)[0]
        if v4_pred == actual_special:
            v4_hits += 1

        # V4 with random: 傳入隨機主號 (公平測試)
        random_main = sorted(random.sample(range(1, 39), 6))
        v4_random_pred = sp.predict_top_n(train_history, n=1, main_numbers=random_main)[0]
        if v4_random_pred == actual_special:
            v4_random_hits += 1

        # 純隨機基準
        random_pred = random.randint(1, 8)
        if random_pred == actual_special:
            random_hits += 1

    # 計算勝率
    v3_rate = v3_hits / periods * 100
    v4_rate = v4_hits / periods * 100
    v4_random_rate = v4_random_hits / periods * 100
    random_rate = random_hits / periods * 100
    theoretical_random = 12.5  # 1/8

    print("\n📊 回測結果")
    print("=" * 60)
    print(f"{'策略':<30} {'命中':<8} {'勝率':<10} {'Edge':<10}")
    print("-" * 60)
    print(f"{'V3 (無 main_numbers)':<30} {v3_hits:<8} {v3_rate:.2f}%     {v3_rate - theoretical_random:+.2f}%")
    print(f"{'V4 (實際主號-作弊測試)':<30} {v4_hits:<8} {v4_rate:.2f}%     {v4_rate - theoretical_random:+.2f}%")
    print(f"{'V4 (隨機主號-公平測試)':<30} {v4_random_hits:<8} {v4_random_rate:.2f}%     {v4_random_rate - theoretical_random:+.2f}%")
    print(f"{'純隨機基準':<30} {random_hits:<8} {random_rate:.2f}%     {random_rate - theoretical_random:+.2f}%")
    print(f"{'理論隨機 (1/8)':<30} {'-':<8} {theoretical_random:.2f}%     {0:+.2f}%")
    print("=" * 60)

    # 分析
    print("\n🔍 分析")
    print("-" * 60)

    # V4 作弊測試 vs V3
    if v4_rate > v3_rate + 1:
        print(f"⚠️  V4 作弊測試 > V3: {v4_rate:.2f}% vs {v3_rate:.2f}%")
        print("   → 歷史數據中存在主號與特別號的統計關聯")
        print("   → 但這可能是過擬合，不代表未來有效")
    else:
        print(f"❌ V4 作弊測試 ≈ V3: {v4_rate:.2f}% vs {v3_rate:.2f}%")
        print("   → 即使知道實際主號，V4 也沒有明顯優勢")
        print("   → 「聯合機率」邏輯無效")

    # V4 公平測試 vs V3
    print()
    if v4_random_rate > v3_rate + 0.5:
        print(f"✅ V4 公平測試 > V3: {v4_random_rate:.2f}% vs {v3_rate:.2f}%")
        print("   → V4 在不知道實際主號的情況下仍有提升")
    elif v4_random_rate < v3_rate - 0.5:
        print(f"❌ V4 公平測試 < V3: {v4_random_rate:.2f}% vs {v3_rate:.2f}%")
        print("   → V4 傳入錯誤主號反而降低效果！")
    else:
        print(f"➖ V4 公平測試 ≈ V3: {v4_random_rate:.2f}% vs {v3_rate:.2f}%")
        print("   → V4 在公平條件下與 V3 相當")

    # 最終建議
    print("\n🏁 結論")
    print("-" * 60)
    best_rate = max(v3_rate, v4_random_rate)
    best_name = "V3" if v3_rate >= v4_random_rate else "V4 (隨機主號)"

    if best_rate > theoretical_random + 1.5:
        print(f"✅ 最佳策略: {best_name} ({best_rate:.2f}%, Edge +{best_rate - theoretical_random:.2f}%)")
    else:
        print(f"⚠️  所有策略與隨機相近，Edge 不顯著")

    # 返回結果供進一步分析
    return {
        'v3_rate': v3_rate,
        'v4_rate': v4_rate,
        'v4_random_rate': v4_random_rate,
        'random_rate': random_rate,
        'periods': periods
    }

if __name__ == "__main__":
    print("=" * 60)
    print("威力彩特別號 V3 vs V4 驗證")
    print("=" * 60)
    run_backtest(periods=1000, seed=42)
