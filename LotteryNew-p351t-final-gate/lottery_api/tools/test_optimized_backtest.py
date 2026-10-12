"""
測試優化後的預測器回測效果
比較：無優化 vs 溫和優化
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import json
import numpy as np
from collections import Counter

# 導入模型
from models.unified_predictor import UnifiedPredictionEngine
from models.prediction_optimizer import PowerLottoPredictionOptimizer


def get_power_lotto_data():
    """獲取威力彩數據"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'lottery.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT draw, numbers, special
        FROM draws
        WHERE lottery_type = 'POWER_LOTTO'
        ORDER BY draw DESC
    ''')

    results = []
    for row in cursor.fetchall():
        # numbers 存儲為 JSON 字符串 "[1, 2, 3, ...]"
        numbers = json.loads(row[1])
        results.append({
            'draw_id': row[0],
            'numbers': numbers,
            'special': row[2]
        })

    conn.close()
    return results


def run_backtest(history, start_idx=0, num_periods=50, use_optimizer=False):
    """
    執行滾動回測

    Args:
        history: 歷史數據（按時間倒序）
        start_idx: 開始位置
        num_periods: 回測期數
        use_optimizer: 是否使用優化器
    """
    predictor = UnifiedPredictionEngine()
    optimizer = PowerLottoPredictionOptimizer() if use_optimizer else None

    rules = {
        'minNumber': 1,
        'maxNumber': 38,
        'pickCount': 6,
        'hasSpecialNumber': True,
        'specialMinNumber': 1,
        'specialMaxNumber': 8
    }

    results = []
    consecutive_count = 0
    special_hits = 0

    for i in range(start_idx, start_idx + num_periods):
        if i + 200 >= len(history):
            break

        # 目標期（要預測的期）
        target = history[i]
        actual_numbers = set(target['numbers'][:6])
        actual_special = target.get('special')

        # 用於預測的歷史（不包含目標期）
        pred_history = history[i+1:i+201]

        # 使用 bayesian 預測（表現較好的方法）
        pred = predictor.bayesian_predict(pred_history, rules)
        predicted_numbers = pred['numbers'][:6]
        predicted_special = pred.get('special')

        # 應用優化器
        if use_optimizer and optimizer:
            predicted_numbers, predicted_special = optimizer.optimize_prediction(
                predicted_numbers, predicted_special, pred_history, rules
            )

        # 計算命中
        pred_set = set(predicted_numbers)
        hits = len(pred_set & actual_numbers)
        special_hit = predicted_special == actual_special

        # 檢查是否有連號
        sorted_pred = sorted(predicted_numbers)
        has_consecutive = any(
            sorted_pred[j+1] - sorted_pred[j] == 1
            for j in range(len(sorted_pred) - 1)
        )
        if has_consecutive:
            consecutive_count += 1
        if special_hit:
            special_hits += 1

        results.append({
            'draw_id': target['draw_id'],
            'actual': sorted(actual_numbers),
            'predicted': sorted(predicted_numbers),
            'hits': hits,
            'special_hit': special_hit,
            'has_consecutive': has_consecutive
        })

    return {
        'results': results,
        'avg_hits': np.mean([r['hits'] for r in results]),
        'consecutive_rate': consecutive_count / len(results) * 100 if results else 0,
        'special_hit_rate': special_hits / len(results) * 100 if results else 0,
        'hit_distribution': Counter([r['hits'] for r in results])
    }


def main():
    print("=" * 60)
    print("威力彩預測優化器 - 效果對比測試")
    print("=" * 60)

    # 獲取數據
    history = get_power_lotto_data()
    print(f"\n數據總量: {len(history)} 期")

    # 只測試 2025 年數據
    history_2025 = [h for h in history if h['draw_id'].startswith('114')]
    print(f"2025 年數據: {len(history_2025)} 期")

    # 找出 2025 年數據在全數據中的位置
    start_idx = 0
    for i, h in enumerate(history):
        if h['draw_id'].startswith('114'):
            start_idx = i
            break

    num_periods = min(90, len(history_2025))  # 測試更多期數
    print(f"回測期數: {num_periods}")

    # 隨機基準線
    random_baseline = 6 * 6 / 38  # 約 0.95
    print(f"\n隨機基準線: {random_baseline:.4f} 命中/期")

    # === 無優化回測 ===
    print("\n" + "-" * 40)
    print("測試 1: 無優化 (原始 Bayesian)")
    print("-" * 40)

    result_no_opt = run_backtest(history, start_idx, num_periods, use_optimizer=False)

    print(f"平均命中: {result_no_opt['avg_hits']:.2f}")
    print(f"vs 隨機: {((result_no_opt['avg_hits'] / random_baseline) - 1) * 100:+.1f}%")
    print(f"連號率: {result_no_opt['consecutive_rate']:.1f}%")
    print(f"特別號命中率: {result_no_opt['special_hit_rate']:.1f}%")
    print(f"命中分布: {dict(result_no_opt['hit_distribution'])}")

    # === 有優化回測 ===
    print("\n" + "-" * 40)
    print("測試 2: 溫和優化")
    print("-" * 40)

    # 重設隨機種子以確保可比較性
    np.random.seed(42)
    result_with_opt = run_backtest(history, start_idx, num_periods, use_optimizer=True)

    print(f"平均命中: {result_with_opt['avg_hits']:.2f}")
    print(f"vs 隨機: {((result_with_opt['avg_hits'] / random_baseline) - 1) * 100:+.1f}%")
    print(f"連號率: {result_with_opt['consecutive_rate']:.1f}%")
    print(f"特別號命中率: {result_with_opt['special_hit_rate']:.1f}%")
    print(f"命中分布: {dict(result_with_opt['hit_distribution'])}")

    # === 對比總結 ===
    print("\n" + "=" * 60)
    print("優化效果對比")
    print("=" * 60)

    avg_diff = result_with_opt['avg_hits'] - result_no_opt['avg_hits']
    consec_diff = result_with_opt['consecutive_rate'] - result_no_opt['consecutive_rate']
    special_diff = result_with_opt['special_hit_rate'] - result_no_opt['special_hit_rate']

    print(f"主號命中: {result_no_opt['avg_hits']:.2f} → {result_with_opt['avg_hits']:.2f} ({avg_diff:+.2f})")
    print(f"連號率:  {result_no_opt['consecutive_rate']:.1f}% → {result_with_opt['consecutive_rate']:.1f}% ({consec_diff:+.1f}%)")
    print(f"特別號:  {result_no_opt['special_hit_rate']:.1f}% → {result_with_opt['special_hit_rate']:.1f}% ({special_diff:+.1f}%)")

    if avg_diff >= 0 and special_diff >= 0:
        print("\n✅ 優化成功：主號和特別號都有改善或持平")
    elif avg_diff >= -0.05:
        print("\n⚠️ 優化效果：主號略降，但在可接受範圍內")
    else:
        print("\n❌ 優化需調整：主號命中率下降過多")


if __name__ == '__main__':
    main()
