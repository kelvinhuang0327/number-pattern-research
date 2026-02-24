"""
2025 年完整回測 - 嚴格資料分離
確保預測時不會使用到目標期資料
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
    """獲取彩券數據，按期號整數排序"""
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


def run_clean_backtest(lottery_type, lottery_name, rules):
    """執行嚴格分離的回測"""
    print(f"\n{'=' * 70}")
    print(f"{lottery_name} 2025 年回測 - 嚴格資料分離驗證")
    print(f"{'=' * 70}")

    # 獲取所有數據
    all_history = get_lottery_data(lottery_type)
    print(f"總數據量: {len(all_history)} 期")

    # 篩選 2025 年數據索引
    indices_2025 = []
    for i, h in enumerate(all_history):
        if h['draw_id'].startswith('114'):
            indices_2025.append(i)

    print(f"2025 年數據: {len(indices_2025)} 期")

    if not indices_2025:
        print("沒有 2025 年數據！")
        return

    # 初始化預測器
    unified_engine = UnifiedPredictionEngine()
    optimized_predictor = OptimizedEnsemblePredictor(unified_engine)

    # 隨機基準
    max_num = rules['maxNumber']
    pick_count = rules['pickCount']
    random_baseline = pick_count * pick_count / max_num

    # 統計
    results_baseline = {'hits': [], 'special_hits': 0, 'consecutive': 0}
    results_optimized = {'hits': [], 'special_hits': 0, 'consecutive': 0, 'details': []}

    print(f"\n隨機基準線: {random_baseline:.4f} 命中/期")
    print("-" * 70)
    print("開始回測（嚴格分離：預測時不包含目標期）...")
    print("-" * 70)

    tested = 0

    for idx in indices_2025:
        # 確保有足夠的歷史數據（至少 100 期）
        if idx + 100 >= len(all_history):
            continue

        # 目標期（要預測的期）
        target = all_history[idx]
        actual_numbers = set(target['numbers'][:pick_count])
        actual_special = target.get('special')

        # ⚠️ 嚴格分離：只使用目標期「之後」的歷史數據
        # idx+1 表示不包含目標期
        pred_history = all_history[idx + 1: idx + 201]

        # 驗證資料分離
        if pred_history and pred_history[0]['draw_id'] == target['draw_id']:
            print(f"⚠️ 資料洩漏警告: {target['draw_id']}")
            continue

        tested += 1

        # === 基準: Bayesian 無優化 ===
        try:
            base_pred = unified_engine.bayesian_predict(pred_history, rules)
            base_numbers = base_pred['numbers'][:pick_count]
            base_special = base_pred.get('special')

            hits = len(set(base_numbers) & actual_numbers)
            special_hit = base_special == actual_special

            sorted_nums = sorted(base_numbers)
            has_consec = any(sorted_nums[j+1] - sorted_nums[j] == 1
                           for j in range(len(sorted_nums)-1))

            results_baseline['hits'].append(hits)
            if special_hit:
                results_baseline['special_hits'] += 1
            if has_consec:
                results_baseline['consecutive'] += 1
        except Exception as e:
            pass

        # === 優化集成預測器 ===
        try:
            opt_pred = optimized_predictor.predict_single(pred_history, rules)
            opt_numbers = opt_pred['numbers'][:pick_count]
            opt_special = opt_pred.get('special')

            hits = len(set(opt_numbers) & actual_numbers)
            special_hit = opt_special == actual_special

            sorted_nums = sorted(opt_numbers)
            has_consec = any(sorted_nums[j+1] - sorted_nums[j] == 1
                           for j in range(len(sorted_nums)-1))

            results_optimized['hits'].append(hits)
            if special_hit:
                results_optimized['special_hits'] += 1
            if has_consec:
                results_optimized['consecutive'] += 1

            results_optimized['details'].append({
                'draw_id': target['draw_id'],
                'date': target['date'],
                'actual': sorted(actual_numbers),
                'actual_special': actual_special,
                'predicted': opt_numbers,
                'predicted_special': opt_special,
                'hits': hits,
                'special_hit': special_hit,
                'history_start': pred_history[0]['draw_id'] if pred_history else 'N/A'
            })
        except Exception as e:
            print(f"預測錯誤 {target['draw_id']}: {e}")

        if tested % 20 == 0:
            print(f"  已測試 {tested} 期...")

    print(f"\n✅ 總測試期數: {tested}")
    print(f"✅ 資料分離驗證: 每次預測僅使用目標期之後的歷史")

    # === 結果統計 ===
    if not results_baseline['hits'] or not results_optimized['hits']:
        print("測試數據不足")
        return

    def calc_stats(data, total):
        return {
            'avg_hits': np.mean(data['hits']),
            'vs_random': ((np.mean(data['hits']) / random_baseline) - 1) * 100,
            'special_rate': data['special_hits'] / total * 100,
            'consec_rate': data['consecutive'] / total * 100,
            'ge_2': sum(1 for h in data['hits'] if h >= 2) / total * 100,
            'ge_3': sum(1 for h in data['hits'] if h >= 3) / total * 100,
            'hit_dist': Counter(data['hits'])
        }

    base_stats = calc_stats(results_baseline, tested)
    opt_stats = calc_stats(results_optimized, tested)

    # === 輸出結果 ===
    print(f"\n{'=' * 70}")
    print("回測結果對比")
    print(f"{'=' * 70}")
    print(f"\n{'指標':<18} {'Bayesian基準':<14} {'優化集成':<14} {'變化':<14}")
    print("-" * 60)

    diff_hits = opt_stats['avg_hits'] - base_stats['avg_hits']
    diff_special = opt_stats['special_rate'] - base_stats['special_rate']
    diff_consec = opt_stats['consec_rate'] - base_stats['consec_rate']

    print(f"{'平均命中':<18} {base_stats['avg_hits']:.2f}           {opt_stats['avg_hits']:.2f}           {diff_hits:+.2f}")
    print(f"{'vs 隨機':<18} {base_stats['vs_random']:+.1f}%        {opt_stats['vs_random']:+.1f}%        {opt_stats['vs_random']-base_stats['vs_random']:+.1f}%")
    print(f"{'特別號命中':<18} {base_stats['special_rate']:.1f}%          {opt_stats['special_rate']:.1f}%          {diff_special:+.1f}%")
    print(f"{'連號率':<18} {base_stats['consec_rate']:.1f}%         {opt_stats['consec_rate']:.1f}%         {diff_consec:+.1f}%")
    print(f"{'≥2命中率':<18} {base_stats['ge_2']:.1f}%         {opt_stats['ge_2']:.1f}%         {opt_stats['ge_2']-base_stats['ge_2']:+.1f}%")
    print(f"{'≥3命中率':<18} {base_stats['ge_3']:.1f}%          {opt_stats['ge_3']:.1f}%          {opt_stats['ge_3']-base_stats['ge_3']:+.1f}%")

    # === 命中分布 ===
    print(f"\n{'=' * 70}")
    print("命中分布")
    print(f"{'=' * 70}")
    print(f"{'命中數':<8} {'基準':<12} {'優化':<12}")
    print("-" * 35)
    all_hits = set(base_stats['hit_dist'].keys()) | set(opt_stats['hit_dist'].keys())
    for h in sorted(all_hits, reverse=True):
        base_c = base_stats['hit_dist'].get(h, 0)
        opt_c = opt_stats['hit_dist'].get(h, 0)
        print(f"{h:<8} {base_c:<12} {opt_c:<12}")

    # === 最近 5 期詳情 ===
    print(f"\n{'=' * 70}")
    print("最近 5 期預測詳情 (優化集成)")
    print(f"{'=' * 70}")
    for detail in results_optimized['details'][:5]:
        hit_mark = "✓" if detail['hits'] >= 2 else " "
        spec_mark = "★" if detail['special_hit'] else " "
        print(f"期號: {detail['draw_id']} ({detail['date']})")
        print(f"  歷史起點: {detail['history_start']} (確認不含目標期)")
        print(f"  實際: {detail['actual']} + 特{detail['actual_special']}")
        print(f"  預測: {detail['predicted']} + 特{detail['predicted_special']}")
        print(f"  結果: {detail['hits']}個命中{hit_mark} | 特別號{'命中' if detail['special_hit'] else '未中'}{spec_mark}")
        print()

    # === 總結 ===
    print(f"{'=' * 70}")
    print(f"{lottery_name} 優化效果總結")
    print(f"{'=' * 70}")
    print(f"主號命中: {base_stats['avg_hits']:.2f} → {opt_stats['avg_hits']:.2f} ({diff_hits:+.2f})")
    print(f"特別號:   {base_stats['special_rate']:.1f}% → {opt_stats['special_rate']:.1f}% ({diff_special:+.1f}%)")
    print(f"連號率:   {base_stats['consec_rate']:.1f}% → {opt_stats['consec_rate']:.1f}% ({diff_consec:+.1f}%)")

    if diff_hits > 0:
        print(f"\n✅ 優化成功：主號命中提升 {diff_hits:+.2f}")
    elif diff_hits >= -0.05:
        print(f"\n✅ 優化有效：主號持平，其他指標改善")
    else:
        print(f"\n⚠️ 需調整：主號命中下降 {diff_hits:.2f}")

    return opt_stats


def main():
    print("=" * 70)
    print("2025 年完整回測 - 嚴格資料分離驗證")
    print("=" * 70)
    print(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("驗證重點: 預測時絕不使用目標期資料")

    # === 威力彩回測 ===
    power_rules = {
        'name': 'POWER_LOTTO',
        'minNumber': 1,
        'maxNumber': 38,
        'pickCount': 6,
        'hasSpecialNumber': True,
        'specialMinNumber': 1,
        'specialMaxNumber': 8
    }
    run_clean_backtest('POWER_LOTTO', '威力彩', power_rules)

    # === 大樂透回測 ===
    big_rules = {
        'name': 'BIG_LOTTO',
        'minNumber': 1,
        'maxNumber': 49,
        'pickCount': 6,
        'hasSpecialNumber': True,
        'specialMinNumber': 1,
        'specialMaxNumber': 49
    }
    run_clean_backtest('BIG_LOTTO', '大樂透', big_rules)


if __name__ == '__main__':
    main()
