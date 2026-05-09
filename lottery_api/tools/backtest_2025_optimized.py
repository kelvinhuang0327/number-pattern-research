"""
2025 年威力彩完整回測 - 使用優化集成預測器
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
from models.optimized_ensemble import OptimizedEnsemblePredictor


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


def run_backtest():
    """執行回測"""
    print("=" * 70)
    print("威力彩 2025 年回測 - 優化集成預測器")
    print("=" * 70)
    print(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 獲取數據
    all_history = get_power_lotto_data()
    print(f"\n總數據量: {len(all_history)} 期")

    # 篩選 2025 年數據
    history_2025 = [h for h in all_history if h['draw_id'].startswith('114')]
    print(f"2025 年數據: {len(history_2025)} 期")

    # 初始化預測器
    unified_engine = UnifiedPredictionEngine()
    optimized_predictor = OptimizedEnsemblePredictor(unified_engine)

    # 威力彩規則
    rules = {
        'name': 'POWER_LOTTO',
        'minNumber': 1,
        'maxNumber': 38,
        'pickCount': 6,
        'hasSpecialNumber': True,
        'specialMinNumber': 1,
        'specialMaxNumber': 8
    }

    # 統計
    results_baseline = {'hits': [], 'special_hits': 0, 'consecutive': 0, 'details': []}
    results_optimized = {'hits': [], 'special_hits': 0, 'consecutive': 0, 'details': []}

    random_baseline = 6 * 6 / 38  # 0.9474

    print("\n" + "-" * 70)
    print("開始回測...")
    print("-" * 70)

    # 找出 2025 年起始位置
    start_idx = 0
    for i, h in enumerate(all_history):
        if h['draw_id'].startswith('114'):
            start_idx = i
            break

    tested = 0

    for i in range(start_idx, len(all_history)):
        target = all_history[i]

        if not target['draw_id'].startswith('114'):
            break

        if i + 100 >= len(all_history):
            break

        tested += 1
        actual_numbers = set(target['numbers'][:6])
        actual_special = target.get('special')

        # 歷史數據（不含目標期）
        pred_history = all_history[i+1:i+201]

        # === 基準: Bayesian 無優化 ===
        try:
            base_pred = unified_engine.bayesian_predict(pred_history, rules)
            base_numbers = base_pred['numbers'][:6]
            base_special = base_pred.get('special')

            hits = len(set(base_numbers) & actual_numbers)
            special_hit = base_special == actual_special

            sorted_nums = sorted(base_numbers)
            has_consec = any(sorted_nums[j+1] - sorted_nums[j] == 1 for j in range(len(sorted_nums)-1))

            results_baseline['hits'].append(hits)
            if special_hit:
                results_baseline['special_hits'] += 1
            if has_consec:
                results_baseline['consecutive'] += 1
        except Exception as e:
            print(f"基準預測錯誤: {e}")

        # === 優化集成預測器 ===
        try:
            opt_pred = optimized_predictor.predict_single(pred_history, rules)
            opt_numbers = opt_pred['numbers'][:6]
            opt_special = opt_pred.get('special')

            hits = len(set(opt_numbers) & actual_numbers)
            special_hit = opt_special == actual_special

            sorted_nums = sorted(opt_numbers)
            has_consec = any(sorted_nums[j+1] - sorted_nums[j] == 1 for j in range(len(sorted_nums)-1))

            results_optimized['hits'].append(hits)
            if special_hit:
                results_optimized['special_hits'] += 1
            if has_consec:
                results_optimized['consecutive'] += 1

            results_optimized['details'].append({
                'draw_id': target['draw_id'],
                'actual': sorted(actual_numbers),
                'actual_special': actual_special,
                'predicted': opt_numbers,
                'predicted_special': opt_special,
                'hits': hits,
                'special_hit': special_hit,
                'method': opt_pred.get('method', 'unknown')
            })
        except Exception as e:
            print(f"優化預測錯誤 {target['draw_id']}: {e}")

        if tested % 20 == 0:
            print(f"已測試 {tested} 期...")

    print(f"\n總測試期數: {tested}")

    # === 結果比較 ===
    print("\n" + "=" * 70)
    print("回測結果對比")
    print("=" * 70)

    def calc_stats(data):
        if not data['hits']:
            return None
        total = len(data['hits'])
        return {
            'avg_hits': np.mean(data['hits']),
            'vs_random': ((np.mean(data['hits']) / random_baseline) - 1) * 100,
            'special_rate': data['special_hits'] / total * 100,
            'consec_rate': data['consecutive'] / total * 100,
            'ge_2': sum(1 for h in data['hits'] if h >= 2) / total * 100,
            'ge_3': sum(1 for h in data['hits'] if h >= 3) / total * 100,
            'ge_4': sum(1 for h in data['hits'] if h >= 4) / total * 100,
            'hit_dist': Counter(data['hits'])
        }

    base_stats = calc_stats(results_baseline)
    opt_stats = calc_stats(results_optimized)

    print(f"\n{'指標':<20} {'Bayesian基準':<15} {'優化集成':<15} {'變化':<15}")
    print("-" * 70)

    if base_stats and opt_stats:
        diff_hits = opt_stats['avg_hits'] - base_stats['avg_hits']
        diff_special = opt_stats['special_rate'] - base_stats['special_rate']
        diff_consec = opt_stats['consec_rate'] - base_stats['consec_rate']

        print(f"{'平均命中':<20} {base_stats['avg_hits']:.2f}            {opt_stats['avg_hits']:.2f}            {diff_hits:+.2f}")
        print(f"{'vs 隨機':<20} {base_stats['vs_random']:+.1f}%          {opt_stats['vs_random']:+.1f}%          {opt_stats['vs_random']-base_stats['vs_random']:+.1f}%")
        print(f"{'特別號命中率':<20} {base_stats['special_rate']:.1f}%           {opt_stats['special_rate']:.1f}%           {diff_special:+.1f}%")
        print(f"{'連號率':<20} {base_stats['consec_rate']:.1f}%           {opt_stats['consec_rate']:.1f}%           {diff_consec:+.1f}%")
        print(f"{'≥2命中率':<20} {base_stats['ge_2']:.1f}%           {opt_stats['ge_2']:.1f}%           {opt_stats['ge_2']-base_stats['ge_2']:+.1f}%")
        print(f"{'≥3命中率':<20} {base_stats['ge_3']:.1f}%           {opt_stats['ge_3']:.1f}%           {opt_stats['ge_3']-base_stats['ge_3']:+.1f}%")

    # === 命中分布 ===
    print("\n" + "=" * 70)
    print("優化集成預測 - 命中分布")
    print("=" * 70)
    if opt_stats:
        print(f"{'命中數':<10} {'次數':<10} {'比例':<10}")
        print("-" * 30)
        for hits in sorted(opt_stats['hit_dist'].keys(), reverse=True):
            count = opt_stats['hit_dist'][hits]
            pct = count / len(results_optimized['hits']) * 100
            print(f"{hits:<10} {count:<10} {pct:.1f}%")

    # === 最近 10 期 ===
    print("\n" + "=" * 70)
    print("最近 10 期預測詳情")
    print("=" * 70)
    for detail in results_optimized['details'][:10]:
        hit_mark = "✓" if detail['hits'] >= 2 else " "
        spec_mark = "★" if detail['special_hit'] else " "
        print(f"期號: {detail['draw_id']} | 方法: {detail['method']}")
        print(f"  實際: {detail['actual']} + 特{detail['actual_special']}")
        print(f"  預測: {detail['predicted']} + 特{detail['predicted_special']}")
        print(f"  結果: {detail['hits']}個命中{hit_mark} | 特別號{'命中' if detail['special_hit'] else '未中'}{spec_mark}")
        print()

    # === 總結 ===
    print("=" * 70)
    print("優化效果總結")
    print("=" * 70)
    if base_stats and opt_stats:
        print(f"主號命中: {base_stats['avg_hits']:.2f} → {opt_stats['avg_hits']:.2f} ({diff_hits:+.2f})")
        print(f"特別號:   {base_stats['special_rate']:.1f}% → {opt_stats['special_rate']:.1f}% ({diff_special:+.1f}%)")
        print(f"連號率:   {base_stats['consec_rate']:.1f}% → {opt_stats['consec_rate']:.1f}% ({diff_consec:+.1f}%)")

        # 判斷優化是否成功
        if diff_hits >= 0 and diff_special >= 0:
            print("\n✅ 優化成功：所有指標均有提升")
        elif diff_hits >= -0.05 and diff_special > 0:
            print("\n✅ 優化有效：特別號顯著提升，主號基本持平")
        elif diff_hits < -0.1:
            print("\n⚠️ 需調整：主號命中下降過多")
        else:
            print("\n⚠️ 效果有限：部分指標有改善")


if __name__ == '__main__':
    run_backtest()
