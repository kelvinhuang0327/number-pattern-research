"""
2025 年威力彩完整回測
測試所有預測方法的成功率
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import json
import numpy as np
from collections import Counter, defaultdict
from datetime import datetime

from models.unified_predictor import UnifiedPredictionEngine
from models.prediction_optimizer import PowerLottoPredictionOptimizer


def get_power_lotto_data():
    """獲取威力彩數據"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'lottery.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT draw, numbers, special, date
        FROM draws
        WHERE lottery_type = 'POWER_LOTTO'
        ORDER BY draw DESC
    ''')

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


def run_comprehensive_backtest():
    """執行完整回測"""
    print("=" * 70)
    print("威力彩 2025 年完整回測報告")
    print("=" * 70)
    print(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 獲取數據
    all_history = get_power_lotto_data()
    print(f"\n總數據量: {len(all_history)} 期")

    # 篩選 2025 年數據 (draw_id 以 114 開頭)
    history_2025 = [h for h in all_history if h['draw_id'].startswith('114')]
    print(f"2025 年數據: {len(history_2025)} 期")

    if not history_2025:
        print("錯誤: 沒有找到 2025 年數據")
        return

    # 初始化
    predictor = UnifiedPredictionEngine()
    optimizer = PowerLottoPredictionOptimizer()

    rules = {
        'minNumber': 1,
        'maxNumber': 38,
        'pickCount': 6,
        'hasSpecialNumber': True,
        'specialMinNumber': 1,
        'specialMaxNumber': 8
    }

    # 預測方法列表
    methods = [
        ('bayesian', predictor.bayesian_predict),
        ('trend', predictor.trend_predict),
        ('statistical', predictor.statistical_predict),
        ('markov', predictor.markov_predict),
        ('frequency', predictor.frequency_predict),
    ]

    # 統計結果
    results_by_method = defaultdict(lambda: {
        'hits': [],
        'special_hits': 0,
        'consecutive': 0,
        'details': []
    })

    results_optimized = {
        'hits': [],
        'special_hits': 0,
        'consecutive': 0,
        'details': []
    }

    # 隨機基準
    random_baseline = 6 * 6 / 38  # 0.9474

    print("\n" + "-" * 70)
    print("開始回測...")
    print("-" * 70)

    # 找出 2025 年數據在全數據中的起始位置
    start_idx = 0
    for i, h in enumerate(all_history):
        if h['draw_id'].startswith('114'):
            start_idx = i
            break

    tested_periods = 0

    # 遍歷每一期 2025 年數據
    for i in range(start_idx, len(all_history)):
        target = all_history[i]

        # 只測試 2025 年的數據
        if not target['draw_id'].startswith('114'):
            break

        # 需要至少 100 期歷史數據
        if i + 100 >= len(all_history):
            break

        tested_periods += 1
        actual_numbers = set(target['numbers'][:6])
        actual_special = target.get('special')

        # 用於預測的歷史（不包含目標期）
        pred_history = all_history[i+1:i+201]

        # 測試每個方法
        for method_name, method_func in methods:
            try:
                pred = method_func(pred_history, rules)
                predicted_numbers = pred['numbers'][:6]
                predicted_special = pred.get('special')

                # 計算命中
                hits = len(set(predicted_numbers) & actual_numbers)
                special_hit = predicted_special == actual_special

                # 檢查連號
                sorted_pred = sorted(predicted_numbers)
                has_consecutive = any(
                    sorted_pred[j+1] - sorted_pred[j] == 1
                    for j in range(len(sorted_pred) - 1)
                )

                results_by_method[method_name]['hits'].append(hits)
                if special_hit:
                    results_by_method[method_name]['special_hits'] += 1
                if has_consecutive:
                    results_by_method[method_name]['consecutive'] += 1

            except Exception as e:
                pass

        # 測試 Bayesian + 優化器
        try:
            pred = predictor.bayesian_predict(pred_history, rules)
            predicted_numbers = pred['numbers'][:6]
            predicted_special = pred.get('special')

            # 應用優化器
            opt_numbers, opt_special = optimizer.optimize_prediction(
                predicted_numbers, predicted_special, pred_history, rules
            )

            hits = len(set(opt_numbers) & actual_numbers)
            special_hit = opt_special == actual_special

            sorted_pred = sorted(opt_numbers)
            has_consecutive = any(
                sorted_pred[j+1] - sorted_pred[j] == 1
                for j in range(len(sorted_pred) - 1)
            )

            results_optimized['hits'].append(hits)
            if special_hit:
                results_optimized['special_hits'] += 1
            if has_consecutive:
                results_optimized['consecutive'] += 1

            results_optimized['details'].append({
                'draw_id': target['draw_id'],
                'actual': sorted(actual_numbers),
                'actual_special': actual_special,
                'predicted': opt_numbers,
                'predicted_special': opt_special,
                'hits': hits,
                'special_hit': special_hit
            })

        except Exception as e:
            pass

        # 進度顯示
        if tested_periods % 20 == 0:
            print(f"已測試 {tested_periods} 期...")

    print(f"\n總測試期數: {tested_periods}")

    # === 輸出結果 ===
    print("\n" + "=" * 70)
    print("各方法回測結果比較")
    print("=" * 70)
    print(f"{'方法':<20} {'平均命中':<12} {'vs隨機':<12} {'特別號%':<12} {'連號率%':<12}")
    print("-" * 70)

    # 排序方法（按平均命中率）
    method_results = []
    for method_name in results_by_method:
        data = results_by_method[method_name]
        if data['hits']:
            avg_hits = np.mean(data['hits'])
            vs_random = ((avg_hits / random_baseline) - 1) * 100
            special_rate = data['special_hits'] / len(data['hits']) * 100
            consec_rate = data['consecutive'] / len(data['hits']) * 100
            method_results.append((method_name, avg_hits, vs_random, special_rate, consec_rate, data['hits']))

    method_results.sort(key=lambda x: x[1], reverse=True)

    for name, avg, vs_rand, spec, consec, hits in method_results:
        print(f"{name:<20} {avg:.2f}         {vs_rand:+.1f}%        {spec:.1f}%         {consec:.1f}%")

    # 優化版本結果
    print("-" * 70)
    if results_optimized['hits']:
        avg_opt = np.mean(results_optimized['hits'])
        vs_random_opt = ((avg_opt / random_baseline) - 1) * 100
        special_opt = results_optimized['special_hits'] / len(results_optimized['hits']) * 100
        consec_opt = results_optimized['consecutive'] / len(results_optimized['hits']) * 100
        print(f"{'Bayesian+優化器':<20} {avg_opt:.2f}         {vs_random_opt:+.1f}%        {special_opt:.1f}%         {consec_opt:.1f}%")

    print("-" * 70)
    print(f"{'隨機基準':<20} {random_baseline:.2f}         {0:+.1f}%        {12.5:.1f}%         {50:.1f}%")

    # === 命中分布統計 ===
    print("\n" + "=" * 70)
    print("Bayesian+優化器 命中分布")
    print("=" * 70)
    if results_optimized['hits']:
        hit_dist = Counter(results_optimized['hits'])
        total = len(results_optimized['hits'])
        print(f"{'命中數':<10} {'次數':<10} {'比例':<10} {'累計>=':<10}")
        cumulative = 0
        for hits in sorted(hit_dist.keys(), reverse=True):
            count = hit_dist[hits]
            cumulative += count
            pct = count / total * 100
            cum_pct = cumulative / total * 100
            print(f"{hits:<10} {count:<10} {pct:.1f}%       {cum_pct:.1f}%")

    # === 最近 10 期詳細結果 ===
    print("\n" + "=" * 70)
    print("最近 10 期預測詳情 (Bayesian+優化器)")
    print("=" * 70)
    if results_optimized['details']:
        recent = results_optimized['details'][:10]
        for detail in recent:
            hit_symbol = "✓" if detail['hits'] >= 2 else " "
            spec_symbol = "★" if detail['special_hit'] else " "
            print(f"期號: {detail['draw_id']}")
            print(f"  實際: {detail['actual']} + 特{detail['actual_special']}")
            print(f"  預測: {detail['predicted']} + 特{detail['predicted_special']}")
            print(f"  結果: {detail['hits']}個命中 {hit_symbol}  特別號{'命中' if detail['special_hit'] else '未中'} {spec_symbol}")
            print()

    # === 總結 ===
    print("=" * 70)
    print("回測總結")
    print("=" * 70)
    if results_optimized['hits']:
        total = len(results_optimized['hits'])
        hits_ge_2 = sum(1 for h in results_optimized['hits'] if h >= 2)
        hits_ge_3 = sum(1 for h in results_optimized['hits'] if h >= 3)
        hits_ge_4 = sum(1 for h in results_optimized['hits'] if h >= 4)

        print(f"測試期數: {total}")
        print(f"平均命中: {avg_opt:.2f} (隨機基準: {random_baseline:.2f})")
        print(f"超越隨機: {vs_random_opt:+.1f}%")
        print(f"")
        print(f"≥2 命中: {hits_ge_2}/{total} ({hits_ge_2/total*100:.1f}%)")
        print(f"≥3 命中: {hits_ge_3}/{total} ({hits_ge_3/total*100:.1f}%)")
        print(f"≥4 命中: {hits_ge_4}/{total} ({hits_ge_4/total*100:.1f}%)")
        print(f"")
        print(f"特別號命中: {results_optimized['special_hits']}/{total} ({special_opt:.1f}%)")
        print(f"連號預測率: {consec_opt:.1f}%")


if __name__ == '__main__':
    run_comprehensive_backtest()
