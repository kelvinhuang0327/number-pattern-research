#!/usr/bin/env python3
"""
P2 研究：連號注入機制

032期教訓：2組連號 (26,27) + (45,46)，歷史 50% 出現至少1組連號

研究設計：
A. 現行: 無連號約束
B. 連號加分: 在現有模型上加分 (候選號碼的 ±1 鄰號若也在候選中，加分)
C. 連號保證: 至少1注包含至少1組連號對
D. 連號注入: 額外注入1組基於頻率的連號對到最弱注
"""
import sys
import os
import json
import random
import numpy as np
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from tools.quick_predict import (
    enforce_tail_diversity,
    biglotto_p1_deviation_5bet,
    _bl_fourier_scores,
    _bl_markov_scores,
    _bl_cold_sum_fixed,
    _bl_dev_complement_2bet,
    _bl_bet5_sum_conditional,
)

BASELINES = {
    'BIG_LOTTO': {1: 1.86, 2: 3.69, 3: 5.49, 4: 7.25, 5: 8.96},
}


def consecutive_histogram(all_draws, test_periods=1500):
    """分析歷史連號出現頻率"""
    consec_counts = Counter()  # 連號對數量 → 出現次數

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 0:
            continue
        nums = sorted(all_draws[target_idx]['numbers'])
        n_consec = sum(1 for j in range(len(nums) - 1) if nums[j + 1] - nums[j] == 1)
        consec_counts[n_consec] += 1

    total = sum(consec_counts.values())
    print(f"\n  連號對分布 ({total}期):")
    print(f"  {'連號對數':>8} | {'期數':>5} | {'比例':>7}")
    print(f"  {'-'*30}")
    has_consec = 0
    for nc in sorted(consec_counts.keys()):
        cnt = consec_counts[nc]
        rate = cnt / total * 100
        print(f"  {nc:>8} | {cnt:>5} | {rate:>6.1f}%")
        if nc > 0:
            has_consec += cnt
    print(f"  {'≥1':>8} | {has_consec:>5} | {has_consec/total*100:>6.1f}%")


def find_best_consecutive_pair(history, exclude=None, max_num=49, window=100):
    """找到最佳連號對（基於 Fourier+Markov 分數）"""
    exclude = exclude or set()
    f_scores = _bl_fourier_scores(history, window=500)
    mk_scores = _bl_markov_scores(history, window=30)
    f_max = max(f_scores.values()) or 1
    mk_max = max(mk_scores.values()) or 1

    pair_scores = []
    for n in range(1, max_num):
        n2 = n + 1
        if n in exclude or n2 in exclude or n2 > max_num:
            continue
        s1 = f_scores.get(n, 0) / f_max + 0.5 * mk_scores.get(n, 0) / mk_max
        s2 = f_scores.get(n2, 0) / f_max + 0.5 * mk_scores.get(n2, 0) / mk_max
        pair_scores.append(((n, n2), s1 + s2))

    if not pair_scores:
        return None

    pair_scores.sort(key=lambda x: -x[1])
    return pair_scores[0][0]


def inject_consecutive_to_bet(bet_nums, pair, max_num=49, history=None, window=100):
    """在一注中注入連號對，替換最弱的2個號碼"""
    if pair is None:
        return bet_nums

    nums = list(bet_nums)
    pair_set = set(pair)

    # 如果已經包含連號對，不需要注入
    for i in range(len(nums) - 1):
        if nums[i + 1] - nums[i] == 1:
            return nums

    # 找最弱的號碼替換
    freq = Counter()
    if history:
        recent = history[-window:] if len(history) >= window else history
        for d in recent:
            for n in d['numbers']:
                freq[n] += 1

    # 移除2個最弱的（頻率最低），加入連號對
    nums_with_scores = [(n, freq.get(n, 0)) for n in nums if n not in pair_set]
    nums_with_scores.sort(key=lambda x: x[1])

    # 移除最弱的2個（或足夠讓連號對裝入）
    n_to_remove = 2 - sum(1 for p in pair if p in nums)
    remaining = [n for n, _ in nums_with_scores[n_to_remove:]]

    result = sorted(set(remaining) | pair_set)
    return result[:6]  # 確保只有6個


def biglotto_5bet_consec_boost(history):
    """變體B: 在注1的Fourier+Markov分數中加入連號加分"""
    MAX_NUM = 49

    prev_nums = history[-1]['numbers']
    neighbor_pool = set()
    for n in prev_nums:
        for d in [-1, 0, 1]:
            nn = n + d
            if 1 <= nn <= MAX_NUM:
                neighbor_pool.add(nn)

    f_scores = _bl_fourier_scores(history, window=500)
    mk_scores = _bl_markov_scores(history, window=30)
    f_max = max(f_scores.values()) or 1
    mk_max = max(mk_scores.values()) or 1

    scored = {}
    for n in neighbor_pool:
        base = f_scores.get(n, 0) / f_max + 0.5 * (mk_scores.get(n, 0) / mk_max)
        # 連號加分：如果 n±1 也在 neighbor_pool 中且得分也不錯
        consec_bonus = 0
        for adj in [n - 1, n + 1]:
            if adj in neighbor_pool and 1 <= adj <= MAX_NUM:
                adj_score = f_scores.get(adj, 0) / f_max + 0.5 * (mk_scores.get(adj, 0) / mk_max)
                if adj_score > 0.3:  # 鄰號得分要有一定水準
                    consec_bonus += 0.2
        scored[n] = base + consec_bonus

    ranked = sorted(neighbor_pool, key=lambda n: scored[n], reverse=True)
    bet1 = sorted(ranked[:6])
    used = set(bet1)

    bet2 = _bl_cold_sum_fixed(history, exclude=used)
    used.update(bet2)
    bet3, bet4 = _bl_dev_complement_2bet(history, exclude=used)
    used.update(bet3)
    used.update(bet4)
    pool = [n for n in range(1, MAX_NUM + 1) if n not in used]
    bet5 = _bl_bet5_sum_conditional(history, pool)

    return [
        {'numbers': bet1}, {'numbers': bet2}, {'numbers': bet3},
        {'numbers': bet4}, {'numbers': bet5},
    ]


def biglotto_5bet_consec_guarantee(history):
    """變體C: 保證至少1注包含連號對（在注5中注入）"""
    bets = biglotto_p1_deviation_5bet(history)

    # 檢查是否已有連號
    has_consec = False
    for bet in bets:
        nums = sorted(bet['numbers'])
        for i in range(len(nums) - 1):
            if nums[i + 1] - nums[i] == 1:
                has_consec = True
                break
        if has_consec:
            break

    if has_consec:
        return bets

    # 在注5中注入連號對
    all_used = set()
    for bet in bets[:4]:
        all_used.update(bet['numbers'])

    pair = find_best_consecutive_pair(history, exclude=all_used)
    if pair:
        new_bet5 = inject_consecutive_to_bet(bets[4]['numbers'], pair, history=history)
        bets[4] = {'numbers': sorted(new_bet5)}

    return bets


def biglotto_5bet_consec_inject(history):
    """變體D: 在最弱注中強制注入連號對"""
    bets = biglotto_p1_deviation_5bet(history)

    # 找全域最佳連號對
    all_used = set()
    for bet in bets:
        all_used.update(bet['numbers'])

    # 迭代：嘗試在不同注中注入
    # 選注5（殘差注）作為注入位置
    pair = find_best_consecutive_pair(history, exclude=set())
    if pair:
        # 注入到注5
        bet5_nums = list(bets[4]['numbers'])
        used_others = set()
        for b in bets[:4]:
            used_others.update(b['numbers'])

        # 如果連號對的號碼已在其他注中，尋找不衝突的連號對
        if any(p in used_others for p in pair):
            pair = find_best_consecutive_pair(history, exclude=used_others)

        if pair:
            new_bet5 = inject_consecutive_to_bet(bet5_nums, pair, history=history)
            bets[4] = {'numbers': sorted(new_bet5)}

    return bets


def backtest_variant(predict_func, all_draws, test_periods, n_bets=5):
    """回測"""
    m3_plus = 0
    total = 0
    consec_rate_in_actual = 0
    consec_rate_in_bets = 0
    pairs = []

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 100:
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'])

        # 實際開獎的連號統計
        actual_sorted = sorted(actual)
        actual_has_consec = any(actual_sorted[j + 1] - actual_sorted[j] == 1
                                for j in range(len(actual_sorted) - 1))
        if actual_has_consec:
            consec_rate_in_actual += 1

        try:
            bets = predict_func(hist)
            bets = enforce_tail_diversity(bets, 2, 49, hist)

            # 預測注中的連號統計
            bet_has_consec = False
            for bet in bets:
                nums = sorted(bet.get('numbers', []))
                if any(nums[j + 1] - nums[j] == 1 for j in range(len(nums) - 1)):
                    bet_has_consec = True
                    break
            if bet_has_consec:
                consec_rate_in_bets += 1

            hit = any(len(set(b.get('numbers', [])) & actual) >= 3 for b in bets)
            if hit:
                m3_plus += 1

            pred_sets = [set(b.get('numbers', [])) for b in bets]
            pairs.append((pred_sets, actual))
            total += 1
        except Exception:
            continue

    baseline = BASELINES['BIG_LOTTO'][n_bets]
    rate = m3_plus / total * 100 if total else 0
    edge = rate - baseline

    return {
        'total': total,
        'm3_plus': m3_plus,
        'rate': round(rate, 2),
        'edge': round(edge, 2),
        'consec_in_actual': round(consec_rate_in_actual / total * 100, 1) if total else 0,
        'consec_in_bets': round(consec_rate_in_bets / total * 100, 1) if total else 0,
        'pairs': pairs,
    }


def permutation_test_proper(pairs, n_perms=200):
    """Permutation test"""
    real_hits = sum(1 for ps, a in pairs if any(len(s & a) >= 3 for s in ps))
    n = len(pairs)
    real_rate = real_hits / n * 100 if n else 0

    all_actuals = [a for _, a in pairs]
    perm_rates = []
    for _ in range(n_perms):
        shuffled = list(all_actuals)
        random.shuffle(shuffled)
        ph = sum(1 for (ps, _), a in zip(pairs, shuffled) if any(len(s & a) >= 3 for s in ps))
        perm_rates.append(ph / n * 100)

    p = sum(1 for r in perm_rates if r >= real_rate) / n_perms
    return {
        'real_rate': round(real_rate, 2),
        'perm_mean': round(np.mean(perm_rates), 2),
        'perm_std': round(np.std(perm_rates), 2),
        'p_value': round(p, 4),
    }


def main():
    random.seed(42)
    np.random.seed(42)

    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws('BIG_LOTTO')
    all_draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))
    print(f"資料量: {len(all_draws)} 期")

    # === 連號分布分析 ===
    consecutive_histogram(all_draws, test_periods=1500)

    # === 變體定義 ===
    variants = {
        'A: 現行 (無連號約束)': lambda h: biglotto_p1_deviation_5bet(h),
        'B: 連號加分 (注1 Fourier+Markov)': lambda h: biglotto_5bet_consec_boost(h),
        'C: 連號保證 (注5注入)': lambda h: biglotto_5bet_consec_guarantee(h),
        'D: 連號注入 (注5最佳對)': lambda h: biglotto_5bet_consec_inject(h),
    }

    # === 三窗口回測 ===
    print(f"\n{'='*70}")
    print(f"  大樂透 5注 — 連號注入變體比較")
    print(f"{'='*70}")

    results = {}
    for vname, func in variants.items():
        print(f"\n  --- {vname} ---")
        r = {}
        for periods in [150, 500, 1500]:
            bt = backtest_variant(func, all_draws, periods)
            r[periods] = bt
            print(f"    {periods}期: M3+={bt['m3_plus']}/{bt['total']} ({bt['rate']:.2f}%) Edge={bt['edge']:+.2f}%"
                  f" | 連號覆蓋: actual={bt['consec_in_actual']:.1f}% bets={bt['consec_in_bets']:.1f}%")

        edges = [r[p]['edge'] for p in [150, 500, 1500]]
        if all(e > 0 for e in edges):
            stability = "STABLE ✅"
        elif edges[2] > 0:
            stability = "LATE_BLOOMER ⚠️"
        else:
            stability = "INEFFECTIVE ❌"
        print(f"    穩定性: {stability}")
        results[vname] = {'r': r, 'stability': stability, 'edges': edges}

    # === Permutation test for best variant vs baseline ===
    best_name = max(results, key=lambda k: results[k]['edges'][2])
    print(f"\n{'='*70}")
    print(f"  Perm tests (1500期)")
    print(f"{'='*70}")

    for vname in [list(variants.keys())[0], best_name]:
        if vname == best_name and vname == list(variants.keys())[0]:
            continue
        bt1500 = backtest_variant(variants[vname], all_draws, 1500)
        perm = permutation_test_proper(bt1500['pairs'], n_perms=200)
        sig = "✅" if perm['p_value'] < 0.05 else "❌"
        print(f"  {vname}: p={perm['p_value']:.4f} {sig} (real={perm['real_rate']:.2f}%)")

    # === 總結 ===
    print(f"\n{'='*70}")
    print(f"  連號注入研究總結")
    print(f"{'='*70}")
    print(f"  {'變體':<40} {'150p':>8} {'500p':>8} {'1500p':>8} {'穩定':>10}")
    print(f"  {'-'*75}")
    for vname, r in results.items():
        e = r['edges']
        print(f"  {vname:<40} {e[0]:+7.2f}% {e[1]:+7.2f}% {e[2]:+7.2f}% {r['stability']:>10}")

    # 保存結果
    output = {
        vname: {
            'edges': r['edges'],
            'stability': r['stability'],
        } for vname, r in results.items()
    }
    output_path = os.path.join(project_root, 'backtest_consecutive_injection_results.json')
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  結果已存至 {output_path}")


if __name__ == '__main__':
    main()
