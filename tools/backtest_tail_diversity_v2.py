#!/usr/bin/env python3
"""
P0 回測 v2：尾數多樣性約束 (max_same_tail=2)
三窗口驗證 (150/500/1500 期) + 正確 Permutation test

修正：
- Permutation test 打亂 actual draws 對應而非 hits 陣列
- 539 使用正確的 predict_539() 調用路徑
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
    power_fourier_rhythm_2bet,
    power_precision_3bet,
    _539_acb_bet,
    _539_markov_bet,
    _539_fourier_scores,
)

BASELINES = {
    'BIG_LOTTO': {1: 1.86, 2: 3.69, 3: 5.49, 4: 7.25, 5: 8.96},
    'POWER_LOTTO': {1: 3.87, 2: 7.59, 3: 11.17, 4: 14.60},
    'DAILY_539': {1: 11.40, 2: 21.54, 3: 30.50, 4: 38.43, 5: 45.39},
}


def load_draws(lottery_type):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type)
    return sorted(all_draws, key=lambda x: (x['date'], x['draw']))


def backtest_compare(predict_func, all_draws, lottery_type, test_periods, n_bets,
                     max_num, max_same_tail=2):
    """同時回測 有/無 尾數過濾，返回比較結果"""
    hits_no = 0
    hits_yes = 0
    total = 0
    violations_count = 0
    predictions_for_perm = []  # (prediction_numsets, actual_set)

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 100:
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'])

        try:
            bets_raw = predict_func(hist)
            bets_filtered = enforce_tail_diversity(
                [dict(b) for b in bets_raw],  # deep copy
                max_same_tail, max_num, hist
            )

            # 檢查違規數
            for bet in bets_raw:
                tails = Counter(n % 10 for n in bet.get('numbers', []))
                if any(c > max_same_tail for c in tails.values()):
                    violations_count += 1

            # 無過濾命中
            hit_no = any(len(set(b.get('numbers', [])) & actual) >= 3 for b in bets_raw)
            if hit_no:
                hits_no += 1

            # 有過濾命中
            hit_yes = any(len(set(b.get('numbers', [])) & actual) >= 3 for b in bets_filtered)
            if hit_yes:
                hits_yes += 1

            # 存儲用於 permutation test
            pred_sets = [set(b.get('numbers', [])) for b in bets_filtered]
            predictions_for_perm.append((pred_sets, actual))

            total += 1
        except Exception as e:
            continue

    baseline = BASELINES[lottery_type][n_bets]
    rate_no = hits_no / total * 100 if total else 0
    rate_yes = hits_yes / total * 100 if total else 0

    return {
        'total': total,
        'hits_no': hits_no,
        'hits_yes': hits_yes,
        'rate_no': round(rate_no, 2),
        'rate_yes': round(rate_yes, 2),
        'edge_no': round(rate_no - baseline, 2),
        'edge_yes': round(rate_yes - baseline, 2),
        'delta_edge': round((rate_yes - baseline) - (rate_no - baseline), 2),
        'violations': violations_count,
        'predictions_for_perm': predictions_for_perm,
    }


def permutation_test_proper(predictions_for_perm, n_perms=200):
    """正確的 Permutation test：打亂 actual draws 對應關係

    原理：若策略有信號，則真實的 prediction-actual 配對
          應比隨機配對產生更多命中。
    """
    # 真實命中率
    real_hits = sum(
        1 for pred_sets, actual in predictions_for_perm
        if any(len(s & actual) >= 3 for s in pred_sets)
    )
    n = len(predictions_for_perm)
    real_rate = real_hits / n * 100 if n else 0

    # 抽取所有 actual draws
    all_actuals = [actual for _, actual in predictions_for_perm]

    # Permutation：打亂 actual draws
    perm_rates = []
    for _ in range(n_perms):
        shuffled_actuals = list(all_actuals)
        random.shuffle(shuffled_actuals)
        perm_hits = sum(
            1 for (pred_sets, _), actual in zip(predictions_for_perm, shuffled_actuals)
            if any(len(s & actual) >= 3 for s in pred_sets)
        )
        perm_rates.append(perm_hits / n * 100)

    p_value = sum(1 for r in perm_rates if r >= real_rate) / n_perms

    return {
        'real_rate': round(real_rate, 2),
        'perm_mean': round(np.mean(perm_rates), 2),
        'perm_std': round(np.std(perm_rates), 2),
        'p_value': round(p_value, 4),
        'n_periods': n,
    }


def run_full_comparison(name, predict_func, lottery_type, n_bets, max_num):
    """三窗口比較 + permutation test"""
    print(f"\n{'='*60}")
    print(f"  {name} — 尾數多樣性約束回測")
    print(f"{'='*60}")

    all_draws = load_draws(lottery_type)
    print(f"  資料量: {len(all_draws)} 期")

    for periods in [150, 500, 1500]:
        r = backtest_compare(predict_func, all_draws, lottery_type, periods, n_bets, max_num)
        sign = '+' if r['delta_edge'] >= 0 else ''
        print(f"\n  {periods}期 ({r['total']}期有效):")
        print(f"    無過濾: M3+={r['hits_no']}/{r['total']} ({r['rate_no']:.2f}%) Edge={r['edge_no']:+.2f}%")
        print(f"    有過濾: M3+={r['hits_yes']}/{r['total']} ({r['rate_yes']:.2f}%) Edge={r['edge_yes']:+.2f}%")
        print(f"    ΔEdge: {sign}{r['delta_edge']:.2f}% | 違規注數(過濾前): {r['violations']}")

    # 1500期 permutation test (有過濾版本 vs 隨機)
    r1500 = backtest_compare(predict_func, all_draws, lottery_type, 1500, n_bets, max_num)
    perm = permutation_test_proper(r1500['predictions_for_perm'], n_perms=200)
    print(f"\n  Permutation test (有過濾, {perm['n_periods']}期, 200perms):")
    print(f"    real={perm['real_rate']:.2f}% | perm_mean={perm['perm_mean']:.2f}% ± {perm['perm_std']:.2f}%")
    sig = "✅ SIGNAL" if perm['p_value'] < 0.05 else "❌ NOT_SIG"
    print(f"    p={perm['p_value']:.4f} {sig}")

    return {
        'edge_no_1500': r1500['edge_no'],
        'edge_yes_1500': r1500['edge_yes'],
        'delta_edge_1500': r1500['delta_edge'],
        'violations_1500': r1500['violations'],
        'perm_p': perm['p_value'],
        'perm_real_rate': perm['real_rate'],
        'perm_mean': perm['perm_mean'],
    }


def main():
    random.seed(42)
    np.random.seed(42)

    results = {}

    # === 大樂透 5注 ===
    def bl5(hist):
        return biglotto_p1_deviation_5bet(hist)
    results['biglotto_5bet'] = run_full_comparison(
        "大樂透 5注 P1+偏差互補+Sum", bl5, 'BIG_LOTTO', 5, 49)

    # === 大樂透 2注 ===
    def bl2(hist):
        return biglotto_p1_neighbor_cold_2bet(hist)
    results['biglotto_2bet'] = run_full_comparison(
        "大樂透 2注 P1鄰號+冷號", bl2, 'BIG_LOTTO', 2, 49)

    # === 威力彩 2注 ===
    def pw2(hist):
        return power_fourier_rhythm_2bet(hist)
    results['power_2bet'] = run_full_comparison(
        "威力彩 2注 Fourier Rhythm", pw2, 'POWER_LOTTO', 2, 38)

    # === 威力彩 3注 ===
    def pw3(hist):
        return power_precision_3bet(hist)
    results['power_3bet'] = run_full_comparison(
        "威力彩 3注 Power Precision", pw3, 'POWER_LOTTO', 3, 38)

    # === 今彩539 3注 ===
    def d539_3(hist):
        bet1 = _539_acb_bet(hist)
        bet2 = _539_markov_bet(hist, exclude=set(bet1))
        excl = set(bet1) | set(bet2)
        sc = _539_fourier_scores(hist, window=500)
        f_ranked = [n for n in sorted(sc, key=lambda x: -sc[x]) if sc[n] > 0 and n not in excl]
        chunk = f_ranked[:5]
        if len(chunk) < 5:
            freq = Counter(n for d in hist[-100:] for n in d['numbers'])
            cold = sorted([n for n in range(1, 40) if n not in excl and n not in set(chunk)],
                          key=lambda n: freq.get(n, 0))
            chunk.extend(cold[:5 - len(chunk)])
        return [{'numbers': bet1}, {'numbers': bet2}, {'numbers': sorted(chunk[:5])}]

    results['daily539_3bet'] = run_full_comparison(
        "今彩539 3注 ACB+Markov+Fourier", d539_3, 'DAILY_539', 3, 39)

    # === 今彩539 2注 ===
    from tools.quick_predict import _539_midfreq_bet
    def d539_2(hist):
        bet1 = _539_midfreq_bet(hist)
        bet2 = _539_acb_bet(hist, exclude=set(bet1))
        return [{'numbers': bet1}, {'numbers': bet2}]

    results['daily539_2bet'] = run_full_comparison(
        "今彩539 2注 MidFreq+ACB", d539_2, 'DAILY_539', 2, 39)

    # === 保存 ===
    output_path = os.path.join(project_root, 'backtest_tail_diversity_v2_results.json')
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n結果已存至 {output_path}")

    # === 總結 ===
    print(f"\n{'='*60}")
    print("  P0 尾數多樣性約束 — 總結")
    print(f"{'='*60}")
    print(f"  {'策略':<30} {'ΔEdge':>8} {'1500p Edge':>12} {'Perm p':>8} {'結論':>8}")
    print(f"  {'-'*70}")
    for name, r in results.items():
        delta = r['delta_edge_1500']
        edge = r['edge_yes_1500']
        p = r['perm_p']
        verdict = "✅" if delta >= 0 and p < 0.05 else ("⚠️" if delta >= 0 else "❌")
        print(f"  {name:<30} {delta:+8.2f}% {edge:+12.2f}% {p:8.4f} {verdict:>8}")

    any_degraded = any(r['delta_edge_1500'] < -0.5 for r in results.values())
    if any_degraded:
        print("\n  ❌ 部分策略 Edge 明顯下降，建議檢查")
    else:
        print("\n  ✅ 尾數多樣性約束未造成 Edge 下降，可安全啟用")


if __name__ == '__main__':
    main()
