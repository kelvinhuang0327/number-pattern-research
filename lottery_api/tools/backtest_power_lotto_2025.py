#!/usr/bin/env python3
"""
威力彩 2025年完整滾動回測
目標：找出達成33%中獎率所需的最少注數

回測邏輯：
- 預測第N期時，只使用第N-1期及之前的歷史數據
- 中獎門檻：中3個號碼以上（符合威力彩官方最低獎項）
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import Counter, defaultdict
from itertools import combinations
from database import db_manager
from common import get_lottery_rules
from models.unified_predictor import prediction_engine

# 載入規則
rules = get_lottery_rules('POWER_LOTTO')
WIN_THRESHOLD = 3  # 中3個以上算中獎


def get_all_prediction_methods():
    """獲取所有可用的預測方法"""
    return [
        ('frequency', lambda h, r: prediction_engine.frequency_predict(h, r), 100),
        ('hot_cold_mix', lambda h, r: prediction_engine.hot_cold_mix_predict(h, r), 100),
        ('bayesian', lambda h, r: prediction_engine.bayesian_predict(h, r), 300),
        ('trend', lambda h, r: prediction_engine.trend_predict(h, r), 100),
        ('monte_carlo', lambda h, r: prediction_engine.monte_carlo_predict(h, r), 100),
        ('ensemble', lambda h, r: prediction_engine.ensemble_predict(h, r), 100),
        ('zone_balance', lambda h, r: prediction_engine.zone_balance_predict(h, r), 500),
        ('sum_range', lambda h, r: prediction_engine.sum_range_predict(h, r), 300),
        ('gap_analysis', lambda h, r: prediction_engine.gap_analysis_predict(h, r), 200),
        ('anti_consensus', lambda h, r: prediction_engine.anti_consensus_predict(h, r), 200),
    ]


def run_single_method_backtest(all_history, test_draws, method_name, predict_func, window):
    """執行單一方法的滾動回測"""
    results = []

    for orig_idx, target_draw in test_draws:
        # 訓練數據：只使用目標期之前的歷史數據
        train_data = all_history[orig_idx + 1:]

        if len(train_data) < window:
            continue

        try:
            prediction = predict_func(train_data[:window], rules)
            predicted = set(prediction['numbers'])
            actual = set(target_draw['numbers'])
            matches = len(predicted & actual)
            results.append({
                'draw': target_draw['draw'],
                'matches': matches,
                'predicted': sorted(predicted),
                'actual': sorted(actual),
                'is_win': matches >= WIN_THRESHOLD
            })
        except Exception as e:
            continue

    return results


def run_comprehensive_backtest():
    """執行完整的2025年滾動回測"""

    print("=" * 90)
    print("威力彩 2025年完整滾動回測")
    print("=" * 90)

    # 載入所有數據
    all_history = db_manager.get_all_draws('POWER_LOTTO')
    print(f"總數據量: {len(all_history)} 期")

    # 找出2025年數據 (民國114年)
    test_draws = []
    for i, d in enumerate(all_history):
        draw_id = str(d.get('draw', ''))
        if draw_id.startswith('114'):
            test_draws.append((i, d))

    # 按時間順序排列 (從早到晚)
    test_draws = list(reversed(test_draws))

    print(f"2025年測試期數: {len(test_draws)} 期")
    print(f"測試範圍: {test_draws[0][1]['draw']} ~ {test_draws[-1][1]['draw']}")
    print(f"中獎門檻: 中 {WIN_THRESHOLD} 個號碼以上")
    print("=" * 90)

    # ============================================================
    # Phase 1: 單注回測 - 所有方法
    # ============================================================
    print("\n📊 Phase 1: 單注方法回測")
    print("-" * 90)

    methods = get_all_prediction_methods()
    single_results = {}

    for method_name, predict_func, window in methods:
        results = run_single_method_backtest(all_history, test_draws, method_name, predict_func, window)

        if results:
            wins = sum(1 for r in results if r['is_win'])
            total = len(results)
            win_rate = wins / total if total > 0 else 0

            # 統計命中分布
            match_dist = Counter(r['matches'] for r in results)

            single_results[method_name] = {
                'wins': wins,
                'total': total,
                'win_rate': win_rate,
                'match_dist': match_dist,
                'results': results,
                'window': window
            }

            print(f"  {method_name:<20} ({window}期): {win_rate*100:>6.2f}% ({wins}/{total}) | "
                  f"中3={match_dist[3]}, 中4={match_dist[4]}, 中5={match_dist[5]}, 中6={match_dist[6]}")

    # 排序並顯示最佳方法
    ranked = sorted(single_results.items(), key=lambda x: x[1]['win_rate'], reverse=True)

    print("\n📌 單注方法排名 (Top 5):")
    for i, (name, stats) in enumerate(ranked[:5], 1):
        print(f"  {i}. {name}: {stats['win_rate']*100:.2f}%")

    # ============================================================
    # Phase 2: 2注組合回測
    # ============================================================
    print("\n" + "=" * 90)
    print("📊 Phase 2: 2注組合回測")
    print("-" * 90)

    top_methods = [name for name, _ in ranked[:6]]  # 取前6個方法做組合
    combo_results_2 = {}

    for m1, m2 in combinations(top_methods, 2):
        combo_name = f"{m1}+{m2}"
        wins = 0
        total = 0

        r1_list = single_results[m1]['results']
        r2_list = single_results[m2]['results']

        # 對齊兩個方法的結果
        r1_dict = {r['draw']: r for r in r1_list}
        r2_dict = {r['draw']: r for r in r2_list}

        common_draws = set(r1_dict.keys()) & set(r2_dict.keys())

        for draw in common_draws:
            best_match = max(r1_dict[draw]['matches'], r2_dict[draw]['matches'])
            if best_match >= WIN_THRESHOLD:
                wins += 1
            total += 1

        if total > 0:
            win_rate = wins / total
            combo_results_2[combo_name] = {
                'wins': wins,
                'total': total,
                'win_rate': win_rate
            }

    # 排序2注組合
    ranked_2 = sorted(combo_results_2.items(), key=lambda x: x[1]['win_rate'], reverse=True)

    print("📌 2注組合排名 (Top 10):")
    for i, (name, stats) in enumerate(ranked_2[:10], 1):
        print(f"  {i}. {name}: {stats['win_rate']*100:.2f}% ({stats['wins']}/{stats['total']})")

    best_2_rate = ranked_2[0][1]['win_rate'] if ranked_2 else 0

    # ============================================================
    # Phase 3: 3注組合回測
    # ============================================================
    print("\n" + "=" * 90)
    print("📊 Phase 3: 3注組合回測")
    print("-" * 90)

    combo_results_3 = {}

    for m1, m2, m3 in combinations(top_methods, 3):
        combo_name = f"{m1}+{m2}+{m3}"
        wins = 0
        total = 0

        r1_dict = {r['draw']: r for r in single_results[m1]['results']}
        r2_dict = {r['draw']: r for r in single_results[m2]['results']}
        r3_dict = {r['draw']: r for r in single_results[m3]['results']}

        common_draws = set(r1_dict.keys()) & set(r2_dict.keys()) & set(r3_dict.keys())

        for draw in common_draws:
            best_match = max(
                r1_dict[draw]['matches'],
                r2_dict[draw]['matches'],
                r3_dict[draw]['matches']
            )
            if best_match >= WIN_THRESHOLD:
                wins += 1
            total += 1

        if total > 0:
            win_rate = wins / total
            combo_results_3[combo_name] = {
                'wins': wins,
                'total': total,
                'win_rate': win_rate
            }

    ranked_3 = sorted(combo_results_3.items(), key=lambda x: x[1]['win_rate'], reverse=True)

    print("📌 3注組合排名 (Top 10):")
    for i, (name, stats) in enumerate(ranked_3[:10], 1):
        target_met = "✅" if stats['win_rate'] >= 0.33 else ""
        print(f"  {i}. {name}: {stats['win_rate']*100:.2f}% ({stats['wins']}/{stats['total']}) {target_met}")

    best_3_rate = ranked_3[0][1]['win_rate'] if ranked_3 else 0

    # ============================================================
    # Phase 4: 4注組合回測
    # ============================================================
    print("\n" + "=" * 90)
    print("📊 Phase 4: 4注組合回測")
    print("-" * 90)

    combo_results_4 = {}

    for methods_combo in combinations(top_methods, 4):
        combo_name = "+".join(methods_combo)
        wins = 0
        total = 0

        result_dicts = [{r['draw']: r for r in single_results[m]['results']} for m in methods_combo]
        common_draws = set.intersection(*[set(d.keys()) for d in result_dicts])

        for draw in common_draws:
            best_match = max(d[draw]['matches'] for d in result_dicts)
            if best_match >= WIN_THRESHOLD:
                wins += 1
            total += 1

        if total > 0:
            win_rate = wins / total
            combo_results_4[combo_name] = {
                'wins': wins,
                'total': total,
                'win_rate': win_rate
            }

    ranked_4 = sorted(combo_results_4.items(), key=lambda x: x[1]['win_rate'], reverse=True)

    print("📌 4注組合排名 (Top 5):")
    for i, (name, stats) in enumerate(ranked_4[:5], 1):
        target_met = "✅" if stats['win_rate'] >= 0.33 else ""
        print(f"  {i}. {name}: {stats['win_rate']*100:.2f}% ({stats['wins']}/{stats['total']}) {target_met}")

    best_4_rate = ranked_4[0][1]['win_rate'] if ranked_4 else 0

    # ============================================================
    # Phase 5: 5注、6注組合
    # ============================================================
    print("\n" + "=" * 90)
    print("📊 Phase 5: 5注、6注組合回測")
    print("-" * 90)

    # 5注
    combo_results_5 = {}
    for methods_combo in combinations(top_methods, 5):
        combo_name = "+".join(methods_combo)
        wins = 0
        total = 0

        result_dicts = [{r['draw']: r for r in single_results[m]['results']} for m in methods_combo]
        common_draws = set.intersection(*[set(d.keys()) for d in result_dicts])

        for draw in common_draws:
            best_match = max(d[draw]['matches'] for d in result_dicts)
            if best_match >= WIN_THRESHOLD:
                wins += 1
            total += 1

        if total > 0:
            combo_results_5[combo_name] = {'wins': wins, 'total': total, 'win_rate': wins/total}

    ranked_5 = sorted(combo_results_5.items(), key=lambda x: x[1]['win_rate'], reverse=True)
    best_5_rate = ranked_5[0][1]['win_rate'] if ranked_5 else 0

    print(f"📌 5注最佳組合: {ranked_5[0][0] if ranked_5 else 'N/A'}")
    print(f"   中獎率: {best_5_rate*100:.2f}%")

    # 6注
    combo_results_6 = {}
    for methods_combo in combinations(top_methods, 6):
        combo_name = "+".join(methods_combo)
        wins = 0
        total = 0

        result_dicts = [{r['draw']: r for r in single_results[m]['results']} for m in methods_combo]
        common_draws = set.intersection(*[set(d.keys()) for d in result_dicts])

        for draw in common_draws:
            best_match = max(d[draw]['matches'] for d in result_dicts)
            if best_match >= WIN_THRESHOLD:
                wins += 1
            total += 1

        if total > 0:
            combo_results_6[combo_name] = {'wins': wins, 'total': total, 'win_rate': wins/total}

    ranked_6 = sorted(combo_results_6.items(), key=lambda x: x[1]['win_rate'], reverse=True)
    best_6_rate = ranked_6[0][1]['win_rate'] if ranked_6 else 0

    print(f"📌 6注最佳組合: {ranked_6[0][0] if ranked_6 else 'N/A'}")
    print(f"   中獎率: {best_6_rate*100:.2f}%")

    # ============================================================
    # 最終結論
    # ============================================================
    print("\n" + "=" * 90)
    print("📋 最終結論")
    print("=" * 90)

    best_single = ranked[0] if ranked else None
    best_single_rate = best_single[1]['win_rate'] if best_single else 0

    print(f"\n{'注數':<8} {'最佳中獎率':>12} {'達成33%':>10}")
    print("-" * 35)
    print(f"{'1注':<8} {best_single_rate*100:>11.2f}% {'❌':>10}")
    print(f"{'2注':<8} {best_2_rate*100:>11.2f}% {'✅' if best_2_rate >= 0.33 else '❌':>10}")
    print(f"{'3注':<8} {best_3_rate*100:>11.2f}% {'✅' if best_3_rate >= 0.33 else '❌':>10}")
    print(f"{'4注':<8} {best_4_rate*100:>11.2f}% {'✅' if best_4_rate >= 0.33 else '❌':>10}")
    print(f"{'5注':<8} {best_5_rate*100:>11.2f}% {'✅' if best_5_rate >= 0.33 else '❌':>10}")
    print(f"{'6注':<8} {best_6_rate*100:>11.2f}% {'✅' if best_6_rate >= 0.33 else '❌':>10}")

    # 找出達成33%的最少注數
    rates = [(1, best_single_rate), (2, best_2_rate), (3, best_3_rate),
             (4, best_4_rate), (5, best_5_rate), (6, best_6_rate)]

    min_bets_for_33 = None
    for num_bets, rate in rates:
        if rate >= 0.33:
            min_bets_for_33 = num_bets
            break

    print("\n" + "=" * 90)
    if min_bets_for_33:
        print(f"🎯 達成33%中獎率所需最少注數: {min_bets_for_33} 注")
    else:
        print("❌ 6注仍無法達成33%目標")
        print(f"   6注最佳中獎率: {best_6_rate*100:.2f}%")
        # 估算需要多少注
        if best_single_rate > 0:
            estimated_bets = int(0.33 / best_single_rate) + 1
            print(f"   估計需要約 {estimated_bets} 注才能接近33%")
    print("=" * 90)

    return {
        'single': single_results,
        'combo_2': combo_results_2,
        'combo_3': combo_results_3,
        'combo_4': combo_results_4,
        'combo_5': combo_results_5,
        'combo_6': combo_results_6,
        'min_bets_for_33': min_bets_for_33
    }


if __name__ == '__main__':
    results = run_comprehensive_backtest()
