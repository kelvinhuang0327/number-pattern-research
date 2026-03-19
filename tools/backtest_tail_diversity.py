#!/usr/bin/env python3
"""
P0 回測：尾數多樣性約束 (max_same_tail=2)
三窗口驗證 (150/500/1500 期) + Permutation test

目標：驗證 enforce_tail_diversity 後處理對 Edge 的影響
      Edge 不應下降（理想情況略上升）
"""
import sys
import os
import json
import random
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from tools.quick_predict import (
    enforce_tail_diversity,
    biglotto_p1_deviation_5bet,
    biglotto_p1_neighbor_cold_2bet,
    biglotto_triple_strike,
    power_fourier_rhythm_2bet,
    power_precision_3bet,
    predict_539,
)

BASELINES = {
    'BIG_LOTTO': {1: 1.86, 2: 3.69, 3: 5.49, 4: 7.25, 5: 8.96},
    'POWER_LOTTO': {1: 3.87, 2: 7.59, 3: 11.17, 4: 14.60},
    'DAILY_539': {1: 11.40, 2: 21.54, 3: 30.50, 4: 38.43, 5: 45.39},
}


def backtest_with_tail_filter(predict_func, lottery_type, test_periods, n_bets,
                               max_num, max_same_tail=2, use_filter=True):
    """回測帶/不帶尾數多樣性過濾"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type)
    all_draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))

    m3_plus = 0
    total = 0
    tail_violations_before = 0
    tail_violations_after = 0

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 100:
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'])

        try:
            bets = predict_func(hist)

            # 統計過濾前尾數違規
            for bet in bets:
                nums = bet.get('numbers', [])
                tails = Counter(n % 10 for n in nums)
                if any(c > max_same_tail for c in tails.values()):
                    tail_violations_before += 1

            # 尾數多樣性過濾
            if use_filter:
                bets = enforce_tail_diversity(bets, max_same_tail, max_num, hist)

            # 統計過濾後尾數違規
            for bet in bets:
                nums = bet.get('numbers', [])
                tails = Counter(n % 10 for n in nums)
                if any(c > max_same_tail for c in tails.values()):
                    tail_violations_after += 1

            hit = any(len(set(bet.get('numbers', [])) & actual) >= 3 for bet in bets)
            if hit:
                m3_plus += 1
            total += 1
        except Exception as e:
            continue

    rate = m3_plus / total * 100 if total > 0 else 0
    baseline = BASELINES[lottery_type][n_bets]
    edge = rate - baseline

    return {
        'total': total,
        'm3_plus': m3_plus,
        'rate': round(rate, 2),
        'baseline': baseline,
        'edge': round(edge, 2),
        'tail_violations_before': tail_violations_before,
        'tail_violations_after': tail_violations_after,
        'use_filter': use_filter,
    }


def permutation_test(predict_func, lottery_type, test_periods, n_bets,
                     max_num, max_same_tail=2, n_perms=200):
    """Permutation test：拱手 vs 隨機打亂"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type)
    all_draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))

    # 真實回測
    real_hits = []
    predictions_cache = []

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 100:
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'])

        try:
            bets = predict_func(hist)
            bets = enforce_tail_diversity(bets, max_same_tail, max_num, hist)
            all_nums_in_bets = []
            for bet in bets:
                all_nums_in_bets.append(set(bet.get('numbers', [])))
            predictions_cache.append(all_nums_in_bets)
            hit = any(len(s & actual) >= 3 for s in all_nums_in_bets)
            real_hits.append(1 if hit else 0)
        except Exception:
            continue

    real_rate = sum(real_hits) / len(real_hits) * 100 if real_hits else 0

    # Permutation: 打亂 actual 與 prediction 的對應
    perm_rates = []
    for _ in range(n_perms):
        shuffled = list(real_hits)
        random.shuffle(shuffled)
        perm_rates.append(sum(shuffled) / len(shuffled) * 100)

    p_value = sum(1 for r in perm_rates if r >= real_rate) / n_perms
    return {
        'real_rate': round(real_rate, 2),
        'perm_mean': round(np.mean(perm_rates), 2),
        'perm_std': round(np.std(perm_rates), 2),
        'p_value': round(p_value, 4),
    }


def run_comparison(name, predict_func, lottery_type, n_bets, max_num):
    """三窗口比較：有/無尾數過濾"""
    print(f"\n{'='*60}")
    print(f"  {name} — 尾數多樣性約束回測")
    print(f"{'='*60}")

    for periods in [150, 500, 1500]:
        r_no = backtest_with_tail_filter(predict_func, lottery_type, periods, n_bets, max_num, use_filter=False)
        r_yes = backtest_with_tail_filter(predict_func, lottery_type, periods, n_bets, max_num, use_filter=True)

        delta = r_yes['edge'] - r_no['edge']
        print(f"\n  {periods}期:")
        print(f"    無過濾: M3+={r_no['m3_plus']}/{r_no['total']} ({r_no['rate']:.2f}%) Edge={r_no['edge']:+.2f}% | 違規={r_no['tail_violations_before']}")
        print(f"    有過濾: M3+={r_yes['m3_plus']}/{r_yes['total']} ({r_yes['rate']:.2f}%) Edge={r_yes['edge']:+.2f}% | 違規前={r_yes['tail_violations_before']} 後={r_yes['tail_violations_after']}")
        print(f"    ΔEdge: {delta:+.2f}%")

    # 1500期 Permutation test
    print(f"\n  Permutation test (1500期, 200 perms):")
    perm = permutation_test(predict_func, lottery_type, 1500, n_bets, max_num)
    print(f"    real={perm['real_rate']:.2f}% | perm_mean={perm['perm_mean']:.2f}% ± {perm['perm_std']:.2f}%")
    print(f"    p={perm['p_value']:.4f} {'✅ SIGNAL' if perm['p_value'] < 0.05 else '❌ NOT_SIG'}")

    return perm


def main():
    random.seed(42)
    np.random.seed(42)

    results = {}

    # === 大樂透 5注 ===
    def bl5(hist):
        return biglotto_p1_deviation_5bet(hist)
    perm1 = run_comparison("大樂透 5注 P1+偏差互補+Sum", bl5, 'BIG_LOTTO', 5, 49)
    results['biglotto_5bet'] = perm1

    # === 大樂透 2注 ===
    def bl2(hist):
        return biglotto_p1_neighbor_cold_2bet(hist)
    perm2 = run_comparison("大樂透 2注 P1鄰號+冷號", bl2, 'BIG_LOTTO', 2, 49)
    results['biglotto_2bet'] = perm2

    # === 威力彩 2注 ===
    def pw2(hist):
        return power_fourier_rhythm_2bet(hist)
    perm3 = run_comparison("威力彩 2注 Fourier Rhythm", pw2, 'POWER_LOTTO', 2, 38)
    results['power_2bet'] = perm3

    # === 今彩539 3注 ===
    def d539_3(hist):
        bet1_raw = _539_acb_bet_for_test(hist)
        bet2_raw = _539_markov_bet_for_test(hist, exclude=set(bet1_raw))
        excl = set(bet1_raw) | set(bet2_raw)
        sc = _539_fourier_for_test(hist)
        f_ranked = [n for n in sorted(sc, key=lambda x: -sc[x]) if sc[n] > 0 and n not in excl]
        bet3_raw = sorted(f_ranked[:5]) if len(f_ranked) >= 5 else sorted(f_ranked[:5])
        return [{'numbers': bet1_raw}, {'numbers': bet2_raw}, {'numbers': bet3_raw}]

    # 直接用 predict_539 返回值
    def d539_3_clean(hist):
        from tools.quick_predict import _539_acb_bet, _539_markov_bet, _539_fourier_scores
        bet1 = _539_acb_bet(hist)
        bet2 = _539_markov_bet(hist, exclude=set(bet1))
        excl = set(bet1) | set(bet2)
        sc = _539_fourier_scores(hist, window=500)
        f_ranked = [n for n in sorted(sc, key=lambda x: -sc[x]) if sc[n] > 0 and n not in excl]
        chunk = f_ranked[:5]
        if len(chunk) < 5:
            freq = Counter(n for d in hist[-100:] for n in d['numbers'])
            cold = sorted([n for n in range(1, 40) if n not in excl and n not in chunk],
                          key=lambda n: freq.get(n, 0))
            chunk.extend(cold[:5 - len(chunk)])
        return [{'numbers': bet1}, {'numbers': bet2}, {'numbers': sorted(chunk[:5])}]

    perm4 = run_comparison("今彩539 3注 ACB+Markov+Fourier", d539_3_clean, 'DAILY_539', 3, 39)
    results['daily539_3bet'] = perm4

    # 保存結果
    output_path = os.path.join(project_root, 'backtest_tail_diversity_results.json')
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n結果已存至 {output_path}")

    # === 總結 ===
    print(f"\n{'='*60}")
    print("  總結")
    print(f"{'='*60}")
    all_pass = True
    for name, r in results.items():
        sig = "✅" if r['p_value'] < 0.05 else "❌"
        print(f"  {name}: p={r['p_value']:.4f} {sig}")
        if r['p_value'] >= 0.05:
            all_pass = False

    if all_pass:
        print("\n  ✅ 所有策略加入尾數約束後仍維持統計顯著性")
    else:
        print("\n  ⚠️ 部分策略在加入尾數約束後顯著性有變化")


if __name__ == '__main__':
    main()
