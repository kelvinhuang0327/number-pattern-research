"""
2025 年完整回測 - 修正版
威力彩：預測特別號（獨立池 1-8）
大樂透：檢查預測號碼是否包含特別號（同池 1-49）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import json
import numpy as np
from collections import Counter
from datetime import datetime

from models.unified_predictor import UnifiedPredictionEngine
from models.optimized_ensemble import OptimizedEnsemblePredictor


def get_lottery_data(lottery_type):
    """獲取彩券數據"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'lottery.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT draw, numbers, special, date
        FROM draws
        WHERE lottery_type = ?
        ORDER BY CAST(draw AS INTEGER) DESC
    ''', (lottery_type,))

    results = []
    for row in cursor.fetchall():
        numbers = json.loads(row[1])
        results.append({
            'draw_id': row[0],
            'numbers': numbers,
            'special': row[2],
            'date': row[3]
        })

    conn.close()
    return results


def run_power_lotto_backtest():
    """威力彩回測 - 特別號需要獨立預測"""
    print(f"\n{'=' * 70}")
    print("威力彩 2025 年回測")
    print("規則：主號 1-38 選 6，特別號 1-8 獨立池（需預測）")
    print(f"{'=' * 70}")

    all_history = get_lottery_data('POWER_LOTTO')
    indices_2025 = [i for i, h in enumerate(all_history) if h['draw_id'].startswith('114')]

    print(f"總數據: {len(all_history)} 期 | 2025年: {len(indices_2025)} 期")

    unified_engine = UnifiedPredictionEngine()
    optimized_predictor = OptimizedEnsemblePredictor(unified_engine)

    rules = {
        'name': 'POWER_LOTTO',
        'minNumber': 1, 'maxNumber': 38, 'pickCount': 6,
        'hasSpecialNumber': True,
        'specialMinNumber': 1, 'specialMaxNumber': 8
    }

    random_baseline = 6 * 6 / 38  # 0.9474

    results = {'hits': [], 'special_hits': 0, 'consecutive': 0, 'details': []}
    tested = 0

    print("\n開始回測...")

    for idx in indices_2025:
        if idx + 100 >= len(all_history):
            continue

        target = all_history[idx]
        actual_numbers = set(target['numbers'][:6])
        actual_special = target.get('special')

        pred_history = all_history[idx + 1: idx + 201]
        tested += 1

        try:
            pred = optimized_predictor.predict_single(pred_history, rules)
            pred_numbers = set(pred['numbers'][:6])
            pred_special = pred.get('special')

            # 主號命中
            hits = len(pred_numbers & actual_numbers)

            # 特別號命中（威力彩需要預測特別號）
            special_hit = pred_special == actual_special

            # 連號檢查
            sorted_nums = sorted(pred['numbers'][:6])
            has_consec = any(sorted_nums[j+1] - sorted_nums[j] == 1
                           for j in range(len(sorted_nums)-1))

            results['hits'].append(hits)
            if special_hit:
                results['special_hits'] += 1
            if has_consec:
                results['consecutive'] += 1

            results['details'].append({
                'draw_id': target['draw_id'],
                'actual': sorted(actual_numbers),
                'actual_special': actual_special,
                'predicted': pred['numbers'][:6],
                'predicted_special': pred_special,
                'hits': hits,
                'special_hit': special_hit
            })

        except Exception as e:
            print(f"錯誤 {target['draw_id']}: {e}")

    # 輸出結果
    print(f"\n測試期數: {tested}")
    avg_hits = np.mean(results['hits'])
    print(f"\n主號命中: {avg_hits:.2f} (隨機基準: {random_baseline:.2f}, +{((avg_hits/random_baseline)-1)*100:.1f}%)")
    print(f"特別號命中: {results['special_hits']}/{tested} ({results['special_hits']/tested*100:.1f}%) - 隨機基準 12.5%")
    print(f"連號率: {results['consecutive']/tested*100:.1f}%")
    print(f"≥2命中: {sum(1 for h in results['hits'] if h >= 2)/tested*100:.1f}%")
    print(f"≥3命中: {sum(1 for h in results['hits'] if h >= 3)/tested*100:.1f}%")

    print("\n命中分布:")
    for hits, count in sorted(Counter(results['hits']).items(), reverse=True):
        print(f"  {hits}個: {count}期 ({count/tested*100:.1f}%)")

    return results


def run_big_lotto_backtest():
    """大樂透回測 - 特別號不需預測，只檢查是否包含"""
    print(f"\n{'=' * 70}")
    print("大樂透 2025 年回測")
    print("規則：主號 1-49 選 6，特別號是第7球（不需預測，只需比對）")
    print(f"{'=' * 70}")

    all_history = get_lottery_data('BIG_LOTTO')
    indices_2025 = [i for i, h in enumerate(all_history) if h['draw_id'].startswith('114')]

    print(f"總數據: {len(all_history)} 期 | 2025年: {len(indices_2025)} 期")

    unified_engine = UnifiedPredictionEngine()
    optimized_predictor = OptimizedEnsemblePredictor(unified_engine)

    rules = {
        'name': 'BIG_LOTTO',
        'minNumber': 1, 'maxNumber': 49, 'pickCount': 6,
        'hasSpecialNumber': False  # 大樂透不需要預測特別號
    }

    random_baseline = 6 * 6 / 49  # 0.7347
    # 預測 6 個號碼包含特別號的機率 = 6/49 ≈ 12.2%
    special_random_baseline = 6 / 49

    results = {'hits': [], 'special_hits': 0, 'consecutive': 0, 'details': []}
    tested = 0

    print("\n開始回測...")

    for idx in indices_2025:
        if idx + 100 >= len(all_history):
            continue

        target = all_history[idx]
        actual_numbers = set(target['numbers'][:6])
        actual_special = target.get('special')

        pred_history = all_history[idx + 1: idx + 201]
        tested += 1

        try:
            pred = optimized_predictor.predict_single(pred_history, rules)
            pred_numbers = set(pred['numbers'][:6])

            # 主號命中
            hits = len(pred_numbers & actual_numbers)

            # 特別號命中（大樂透：檢查預測的6個號碼是否包含特別號）
            special_hit = actual_special in pred_numbers

            # 連號檢查
            sorted_nums = sorted(pred['numbers'][:6])
            has_consec = any(sorted_nums[j+1] - sorted_nums[j] == 1
                           for j in range(len(sorted_nums)-1))

            results['hits'].append(hits)
            if special_hit:
                results['special_hits'] += 1
            if has_consec:
                results['consecutive'] += 1

            results['details'].append({
                'draw_id': target['draw_id'],
                'actual': sorted(actual_numbers),
                'actual_special': actual_special,
                'predicted': pred['numbers'][:6],
                'hits': hits,
                'special_hit': special_hit,
                'special_note': f"預測號碼{'包含' if special_hit else '不包含'}特別號 {actual_special}"
            })

        except Exception as e:
            print(f"錯誤 {target['draw_id']}: {e}")

    # 輸出結果
    print(f"\n測試期數: {tested}")
    avg_hits = np.mean(results['hits'])
    print(f"\n主號命中: {avg_hits:.2f} (隨機基準: {random_baseline:.2f}, +{((avg_hits/random_baseline)-1)*100:.1f}%)")
    print(f"預測包含特別號: {results['special_hits']}/{tested} ({results['special_hits']/tested*100:.1f}%) - 隨機基準 {special_random_baseline*100:.1f}%")
    print(f"連號率: {results['consecutive']/tested*100:.1f}%")
    print(f"≥2命中: {sum(1 for h in results['hits'] if h >= 2)/tested*100:.1f}%")
    print(f"≥3命中: {sum(1 for h in results['hits'] if h >= 3)/tested*100:.1f}%")

    print("\n命中分布:")
    for hits, count in sorted(Counter(results['hits']).items(), reverse=True):
        print(f"  {hits}個: {count}期 ({count/tested*100:.1f}%)")

    # 最近 5 期詳情
    print(f"\n最近 5 期詳情:")
    print("-" * 60)
    for detail in results['details'][:5]:
        mark = "✓" if detail['hits'] >= 2 else " "
        spec_mark = "★" if detail['special_hit'] else " "
        print(f"期號: {detail['draw_id']}")
        print(f"  實際: {detail['actual']} + 特{detail['actual_special']}")
        print(f"  預測: {detail['predicted']}")
        print(f"  結果: {detail['hits']}個命中{mark} | {detail['special_note']}{spec_mark}")
        print()

    return results


def main():
    print("=" * 70)
    print("2025 年回測 - 修正特別號邏輯")
    print("=" * 70)
    print(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    run_power_lotto_backtest()
    run_big_lotto_backtest()

    print("\n" + "=" * 70)
    print("邏輯說明")
    print("=" * 70)
    print("威力彩：特別號從獨立池(1-8)開出 → 需要預測")
    print("大樂透：特別號是第7球(1-49同池) → 不預測，只檢查預測號碼是否包含")


if __name__ == '__main__':
    main()
