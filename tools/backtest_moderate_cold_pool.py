#!/usr/bin/env python3
"""
P1 研究：中度冷號池 (gap 8-15) vs 現有極端冷號池 (pool_size=12, 最低頻率)

032期教訓：#05 (gap=13) 屬 pool=12 盲區（以 gap>15 為極端冷號門檻）
研究假設：gap 8-15 的「中度冷號」可能比極端冷號更有回歸預測力

實驗設計：
A. 現行版本: _bl_cold_sum_fixed(pool_size=12) — 按頻率最低取12顆
B. 中度冷號: gap 8-15 的號碼池 + Sum約束
C. 綜合池: gap 6-18 (更寬) + 頻率排序
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
    _bl_fourier_scores,
    _bl_markov_scores,
    _bl_cold_sum_fixed,
)

BASELINES = {
    'BIG_LOTTO': {1: 1.86, 2: 3.69, 3: 5.49, 4: 7.25, 5: 8.96},
}


def gap_profile(history, max_num=49):
    """計算每個號碼的 gap (距上次出現的期數)"""
    gaps = {}
    for n in range(1, max_num + 1):
        gaps[n] = len(history)  # default: 從未出現

    for i, d in enumerate(reversed(history)):
        idx = len(history) - 1 - i
        for n in d['numbers']:
            if n <= max_num and n not in gaps or gaps[n] == len(history):
                gaps[n] = i  # gap = distance from end

    # 重新計算：gap = 距離最後一次出現的期數
    gaps = {}
    for n in range(1, max_num + 1):
        gaps[n] = len(history)
    for i in range(len(history) - 1, -1, -1):
        for n in history[i]['numbers']:
            if n <= max_num and gaps[n] == len(history):
                gaps[n] = len(history) - 1 - i

    return gaps


def moderate_cold_bet(history, exclude=None, gap_lo=8, gap_hi=15, max_num=49, pick=6):
    """中度冷號注：選擇 gap 在 [gap_lo, gap_hi] 的號碼 + Sum 約束"""
    exclude = exclude or set()
    gaps = gap_profile(history, max_num)

    # 篩選中度冷號
    moderate_cold = sorted(
        [n for n in range(1, max_num + 1) if n not in exclude and gap_lo <= gaps[n] <= gap_hi],
        key=lambda x: gaps[x],  # 按 gap 從大到小
        reverse=True
    )

    if len(moderate_cold) < pick:
        # 候選不足，擴展搜索範圍
        extended = sorted(
            [n for n in range(1, max_num + 1) if n not in exclude and gaps[n] >= gap_lo - 2],
            key=lambda x: gaps[x], reverse=True
        )
        moderate_cold = extended

    # Sum 約束
    sums = [sum(d['numbers']) for d in history[-300:]]
    mu, sg = np.mean(sums), np.std(sums)
    tlo, thi = mu - 0.5 * sg, mu + 0.5 * sg
    tmid = mu

    pool = moderate_cold[:18] if len(moderate_cold) > 18 else moderate_cold
    if len(pool) < pick:
        # 最後備援：取剩餘號碼
        remaining = sorted([n for n in range(1, max_num + 1) if n not in exclude],
                           key=lambda x: gaps.get(x, 0), reverse=True)
        pool = remaining[:18]

    best, best_dist, best_in = None, float('inf'), False
    for combo in combinations(pool, pick):
        s = sum(combo)
        in_range = (tlo <= s <= thi)
        dist = abs(s - tmid)
        if in_range and (not best_in or dist < best_dist):
            best, best_dist, best_in = combo, dist, True
        elif not in_range and not best_in and dist < best_dist:
            best, best_dist = combo, dist

    return sorted(best if best else pool[:pick])


def wide_cold_bet(history, exclude=None, gap_lo=6, gap_hi=18, max_num=49, pick=6):
    """寬範圍冷號注：gap 6~18"""
    return moderate_cold_bet(history, exclude, gap_lo, gap_hi, max_num, pick)


def build_p1_5bet_variant(history, cold_func):
    """5注系統，替換 bet2 (冷號注) 為不同的冷號策略"""
    MAX_NUM = 49

    # 注1: 鄰域 + Fourier+Markov (與定案版完全相同)
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
    scored = {n: f_scores.get(n, 0) / f_max + 0.5 * (mk_scores.get(n, 0) / mk_max)
              for n in neighbor_pool}
    ranked = sorted(neighbor_pool, key=lambda n: scored[n], reverse=True)
    bet1 = sorted(ranked[:6])
    used = set(bet1)

    # 注2: 被測試的冷號策略
    bet2 = cold_func(history, exclude=used)
    used.update(bet2)

    # 注3+4: 偏差互補
    from tools.quick_predict import _bl_dev_complement_2bet
    bet3, bet4 = _bl_dev_complement_2bet(history, exclude=used)
    used.update(bet3)
    used.update(bet4)

    # 注5: 殘差 sum
    from tools.quick_predict import _bl_bet5_sum_conditional
    pool = [n for n in range(1, MAX_NUM + 1) if n not in used]
    bet5 = _bl_bet5_sum_conditional(history, pool)

    return [
        {'numbers': bet1},
        {'numbers': bet2},
        {'numbers': bet3},
        {'numbers': bet4},
        {'numbers': bet5},
    ]


def backtest_cold_variant(cold_func, all_draws, test_periods, n_bets=5):
    """回測冷號變體"""
    m3_plus = 0
    total = 0

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 100:
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'])

        try:
            bets = build_p1_5bet_variant(hist, cold_func)
            # 尾數多樣性過濾
            bets = enforce_tail_diversity(bets, 2, 49, hist)

            hit = any(len(set(b.get('numbers', [])) & actual) >= 3 for b in bets)
            if hit:
                m3_plus += 1
            total += 1
        except Exception as e:
            continue

    rate = m3_plus / total * 100 if total else 0
    baseline = BASELINES['BIG_LOTTO'][n_bets]
    edge = rate - baseline
    return {'total': total, 'm3_plus': m3_plus, 'rate': round(rate, 2), 'edge': round(edge, 2)}


def permutation_test(cold_func, all_draws, test_periods, n_perms=200):
    """Permutation test"""
    pairs = []
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 100:
            continue
        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'])
        try:
            bets = build_p1_5bet_variant(hist, cold_func)
            bets = enforce_tail_diversity(bets, 2, 49, hist)
            pred_sets = [set(b.get('numbers', [])) for b in bets]
            pairs.append((pred_sets, actual))
        except Exception:
            continue

    # 真實命中
    real_hits = sum(1 for ps, a in pairs if any(len(s & a) >= 3 for s in ps))
    n = len(pairs)
    real_rate = real_hits / n * 100 if n else 0

    # Permutation
    all_actuals = [a for _, a in pairs]
    perm_rates = []
    for _ in range(n_perms):
        shuffled = list(all_actuals)
        random.shuffle(shuffled)
        ph = sum(1 for (ps, _), a in zip(pairs, shuffled) if any(len(s & a) >= 3 for s in ps))
        perm_rates.append(ph / n * 100)

    p_value = sum(1 for r in perm_rates if r >= real_rate) / n_perms

    return {
        'real_rate': round(real_rate, 2),
        'perm_mean': round(np.mean(perm_rates), 2),
        'perm_std': round(np.std(perm_rates), 2),
        'p_value': round(p_value, 4),
    }


def gap_histogram(all_draws, test_periods=1500, max_num=49):
    """統計開獎號碼的 gap 分布，確認中度冷號的回歸率"""
    gap_hit_counts = Counter()  # gap值 → 出現次數
    gap_total_counts = Counter()  # gap值 → 可能出現次數

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 100:
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'])
        gaps = gap_profile(hist, max_num)

        for n in range(1, max_num + 1):
            g = min(gaps[n], 30)  # cap at 30
            gap_total_counts[g] += 1
            if n in actual:
                gap_hit_counts[g] += 1

    print("\n  Gap 回歸率分析 (1500期):")
    print(f"  {'Gap':>4} | {'出現':>5} | {'總候選':>7} | {'回歸率':>7} | {'期望':>7} | {'Lift':>5}")
    print(f"  {'-'*50}")
    expected_rate = 6.0 / max_num * 100  # ~12.24%
    for g in sorted(gap_total_counts.keys()):
        hits = gap_hit_counts[g]
        total = gap_total_counts[g]
        rate = hits / total * 100 if total else 0
        lift = rate / expected_rate if expected_rate > 0 else 0
        bar = "█" * int(lift * 10)
        marker = " ★" if 8 <= g <= 15 else ""
        print(f"  {g:>4} | {hits:>5} | {total:>7} | {rate:>6.1f}% | {expected_rate:>6.1f}% | {lift:>4.2f}x {bar}{marker}")


def main():
    random.seed(42)
    np.random.seed(42)

    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws('BIG_LOTTO')
    all_draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))
    print(f"資料量: {len(all_draws)} 期")

    # === Gap 分布分析 ===
    gap_histogram(all_draws, test_periods=1500)

    # === 冷號策略變體定義 ===
    variants = {
        'A: 現行 pool=12 (最低頻率)': lambda h, exclude=None: _bl_cold_sum_fixed(h, exclude=exclude),
        'B: 中度冷號 gap 8-15': lambda h, exclude=None: moderate_cold_bet(h, exclude=exclude, gap_lo=8, gap_hi=15),
        'C: 中度冷號 gap 6-12': lambda h, exclude=None: moderate_cold_bet(h, exclude=exclude, gap_lo=6, gap_hi=12),
        'D: 寬範圍 gap 6-18': lambda h, exclude=None: wide_cold_bet(h, exclude=exclude, gap_lo=6, gap_hi=18),
        'E: 小池 gap 10-20': lambda h, exclude=None: moderate_cold_bet(h, exclude=exclude, gap_lo=10, gap_hi=20),
    }

    # === 三窗口回測 ===
    print(f"\n{'='*70}")
    print(f"  大樂透 5注 — 冷號池變體比較")
    print(f"{'='*70}")

    results = {}
    for vname, cold_func in variants.items():
        print(f"\n  --- {vname} ---")
        r = {}
        for periods in [150, 500, 1500]:
            bt = backtest_cold_variant(cold_func, all_draws, periods)
            r[periods] = bt
            print(f"    {periods}期: M3+={bt['m3_plus']}/{bt['total']} ({bt['rate']:.2f}%) Edge={bt['edge']:+.2f}%")

        # 三窗口穩定性
        edges = [r[p]['edge'] for p in [150, 500, 1500]]
        if all(e > 0 for e in edges):
            stability = "STABLE ✅"
        elif edges[2] > 0:
            stability = "LATE_BLOOMER ⚠️"
        else:
            stability = "INEFFECTIVE ❌"
        print(f"    穩定性: {stability}")
        print(f"    三窗口: {edges[0]:+.2f}% / {edges[1]:+.2f}% / {edges[2]:+.2f}%")

        results[vname] = {'windows': r, 'stability': stability, 'edges': edges}

    # === 最佳變體: 1500期 permutation test ===
    # 找長期 Edge 最佳的變體
    best_name = max(results, key=lambda k: results[k]['edges'][2])
    best_func = variants[best_name]
    print(f"\n{'='*70}")
    print(f"  最佳變體: {best_name} — Permutation test")
    print(f"{'='*70}")

    perm = permutation_test(best_func, all_draws, 1500, n_perms=200)
    print(f"  real={perm['real_rate']:.2f}% | perm_mean={perm['perm_mean']:.2f}% ± {perm['perm_std']:.2f}%")
    sig = "✅ SIGNAL" if perm['p_value'] < 0.05 else "❌ NOT_SIG"
    print(f"  p={perm['p_value']:.4f} {sig}")

    # 同時測試現行版本的 perm
    perm_a = permutation_test(variants['A: 現行 pool=12 (最低頻率)'], all_draws, 1500, n_perms=200)
    print(f"\n  現行版本 perm: real={perm_a['real_rate']:.2f}% | p={perm_a['p_value']:.4f}")

    # === 總結 ===
    print(f"\n{'='*70}")
    print(f"  冷號池研究總結")
    print(f"{'='*70}")
    print(f"  {'變體':<35} {'150p':>8} {'500p':>8} {'1500p':>8} {'穩定性':>12}")
    print(f"  {'-'*75}")
    for vname, r in results.items():
        e = r['edges']
        print(f"  {vname:<35} {e[0]:+7.2f}% {e[1]:+7.2f}% {e[2]:+7.2f}% {r['stability']:>12}")

    # 保存結果
    output = {
        vname: {
            'edges': r['edges'],
            'stability': r['stability'],
            'details': {str(k): v for k, v in r['windows'].items()},
        } for vname, r in results.items()
    }
    output['best_variant'] = best_name
    output['best_perm_p'] = perm['p_value']
    output['baseline_perm_p'] = perm_a['p_value']

    output_path = os.path.join(project_root, 'backtest_moderate_cold_pool_results.json')
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  結果已存至 {output_path}")


if __name__ == '__main__':
    main()
