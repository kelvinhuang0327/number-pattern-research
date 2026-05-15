#!/usr/bin/env python3
"""
今彩539 Neighbor-ACB 2注 完整驗證腳本
2026-03-04 115000056期檢討後 — P1 行動項目

策略設計:
  Bet1: 上期號碼 ±1 鄰號池 → ACB評分 Top-5
  Bet2: 排除Bet1後 → 全池ACB評分 Top-5

驗證項目:
  1. 三窗口驗證 (150/500/1500期)
  2. Permutation test (200次)
  3. McNemar vs MidFreq+ACB (現有2注冠軍, Edge +5.06%)
  4. McNemar vs ACB 1注 (確認Neighbor注有附加價值)
  5. 版本對比: Top-5 vs Top-3 鄰號選取

基準:
  2注 M2+: 21.54%
"""
import sys, os, json, time, random
import numpy as np
from numpy.fft import fft, fftfreq
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

MAX_NUM = 39
PICK = 5
BASELINES_M2 = {1: 11.40, 2: 21.54, 3: 30.50}
SEED = 42

random.seed(SEED)
np.random.seed(SEED)


# ===== 評分函數 =====

def acb_scores_539(history, window=100):
    """ACB 異常捕捉分數 (與主腳本完全一致)"""
    recent = history[-window:] if len(history) >= window else history
    counter = Counter()
    for n in range(1, MAX_NUM + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM:
                counter[n] += 1
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            if n <= MAX_NUM:
                last_seen[n] = i
    current = len(recent)
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, MAX_NUM + 1)}
    expected = len(recent) * PICK / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM + 1):
        freq_deficit = expected - counter[n]
        gap_score = gaps[n] / (len(recent) / 2)
        bb = 1.2 if (n <= 5 or n >= 35) else 1.0
        m3 = 1.1 if n % 3 == 0 else 1.0
        scores[n] = (freq_deficit * 0.4 + gap_score * 0.6) * bb * m3
    return scores


def midfreq_scores_539(history, window=100):
    """MidFreq 均值回歸分數"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter()
    for n in range(1, MAX_NUM + 1):
        freq[n] = 0
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM:
                freq[n] += 1
    expected = len(recent) * PICK / MAX_NUM
    max_dist = max(abs(freq[n] - expected) for n in range(1, MAX_NUM + 1))
    scores = {}
    for n in range(1, MAX_NUM + 1):
        scores[n] = max_dist - abs(freq[n] - expected)
    return scores


def get_neighbor_pool(history):
    """
    建構鄰號池: 上期號碼每個 ±1，限制在 [1,39]，排除上期號碼本身
    返回: sorted list of neighbor numbers
    """
    if not history:
        return []
    prev = set(history[-1]['numbers'])
    neighbors = set()
    for n in prev:
        if n - 1 >= 1:
            neighbors.add(n - 1)
        if n + 1 <= MAX_NUM:
            neighbors.add(n + 1)
    # 排除上期號碼本身（鄰號僅包含未開出的相鄰號碼）
    neighbors -= prev
    return sorted(neighbors)


# ===== 預測函數 =====

def pred_neighbor_acb_v1(history):
    """
    Neighbor-ACB 2注 V1 (Top-5鄰號)
    Bet1: 鄰號池(~9碼) → ACB Top-5
    Bet2: 全池排除Bet1 → ACB Top-5
    """
    neighbor_pool = get_neighbor_pool(history)
    acb = acb_scores_539(history)
    acb_ranked = sorted(acb, key=lambda x: -acb[x])

    # Bet1: 在鄰號池中按ACB排名取Top-5
    bet1_cands = [n for n in acb_ranked if n in set(neighbor_pool)]
    bet1 = sorted(bet1_cands[:PICK])

    # 若鄰號池不足5個，補全
    if len(bet1) < PICK:
        for n in acb_ranked:
            if n not in set(bet1):
                bet1.append(n)
                if len(bet1) >= PICK:
                    break
        bet1 = sorted(bet1[:PICK])

    # Bet2: 排除Bet1，全池ACB Top-5
    excl = set(bet1)
    bet2_cands = [n for n in acb_ranked if n not in excl]
    bet2 = sorted(bet2_cands[:PICK])

    return [bet1, bet2]


def pred_neighbor_acb_v2(history):
    """
    Neighbor-ACB 2注 V2 (Top-3鄰號，更嚴格篩選)
    Bet1: 鄰號池(~9碼) → ACB Top-3，再補充全池ACB Top-2（非鄰號）
    Bet2: 全池排除Bet1 → ACB Top-5
    """
    neighbor_pool = get_neighbor_pool(history)
    acb = acb_scores_539(history)
    acb_ranked = sorted(acb, key=lambda x: -acb[x])

    # Bet1 核心: 鄰號中ACB Top-3
    neighbor_set = set(neighbor_pool)
    bet1_neighbor = [n for n in acb_ranked if n in neighbor_set][:3]

    # Bet1 補充: 非鄰號但ACB最高的2個
    excl_neighbor = set(bet1_neighbor)
    bet1_supplement = [n for n in acb_ranked if n not in neighbor_set and n not in excl_neighbor][:2]

    bet1 = sorted(bet1_neighbor + bet1_supplement)

    # 補足到5個（邊界保護）
    if len(bet1) < PICK:
        used = set(bet1)
        for n in acb_ranked:
            if n not in used:
                bet1.append(n)
                if len(bet1) >= PICK:
                    break
        bet1 = sorted(bet1[:PICK])

    # Bet2: 排除Bet1，全池ACB Top-5
    excl = set(bet1)
    bet2_cands = [n for n in acb_ranked if n not in excl]
    bet2 = sorted(bet2_cands[:PICK])

    return [bet1, bet2]


def pred_neighbor_acb_v3(history):
    """
    Neighbor-ACB 2注 V3 (純鄰號Bet1，不補充)
    Bet1: 鄰號池 → ACB Top-5（若不足則擴展到全ACB）
    Bet2: 全池排除Bet1 → ACB Top-5

    與V1相同邏輯，用於驗證V1=V3確認
    """
    return pred_neighbor_acb_v1(history)


def pred_midfreq_acb_2bet(history):
    """MidFreq+ACB 2注 (現有 ADOPTED 2注冠軍, Edge +5.06%)"""
    midfreq = midfreq_scores_539(history)
    acb = acb_scores_539(history)
    mf_ranked = sorted(midfreq, key=lambda x: -midfreq[x])
    acb_ranked = sorted(acb, key=lambda x: -acb[x])

    bet1 = sorted(mf_ranked[:PICK])
    excl = set(bet1)
    bet2_cands = [n for n in acb_ranked if n not in excl]
    bet2 = sorted(bet2_cands[:PICK])
    return [bet1, bet2]


def pred_acb_1bet(history):
    """ACB 1注 (現有 ADOPTED)"""
    acb = acb_scores_539(history)
    acb_ranked = sorted(acb, key=lambda x: -acb[x])
    return [sorted(acb_ranked[:PICK])]


# ===== 回測引擎 =====

def backtest_539(predict_func, all_draws, test_periods=1500, n_bets=2,
                 match_threshold=2):
    """539 通用回測 (M2+ 基準)"""
    hits = 0
    total = 0
    hit_details = []

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 100:
            hit_details.append(0)
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'][:PICK])

        try:
            bets = predict_func(hist)
            hit = any(len(set(bet) & actual) >= match_threshold for bet in bets)
            if hit:
                hits += 1
                hit_details.append(1)
            else:
                hit_details.append(0)
            total += 1
        except Exception as e:
            hit_details.append(0)
            total += 1

    rate = hits / total * 100 if total > 0 else 0
    baseline = BASELINES_M2.get(n_bets, BASELINES_M2[2])
    edge = rate - baseline

    p0 = baseline / 100
    if total > 0 and p0 > 0:
        se = np.sqrt(p0 * (1 - p0) / total)
        z = (hits / total - p0) / se if se > 0 else 0
    else:
        z = 0

    return {
        'hits': hits,
        'total': total,
        'rate': rate,
        'baseline': baseline,
        'edge': edge,
        'z': z,
        'hit_details': hit_details,
    }


def permutation_test_539(predict_func, all_draws, test_periods=1500, n_bets=2,
                          match_threshold=2, n_perm=200):
    """539 Permutation test (200次)"""
    real = backtest_539(predict_func, all_draws, test_periods, n_bets, match_threshold)
    real_rate = real['rate']

    target_indices = []
    for i in range(test_periods):
        idx = len(all_draws) - test_periods + i
        if idx >= 100:
            target_indices.append(idx)

    all_actuals = [set(all_draws[idx]['numbers'][:PICK]) for idx in target_indices]

    perm_rates = []
    for p in range(n_perm):
        shuffled = list(all_actuals)
        rng = random.Random(p * 7919 + 42)
        rng.shuffle(shuffled)

        hits = 0
        total = 0
        for i, idx in enumerate(target_indices):
            hist = all_draws[:idx]
            actual = shuffled[i]
            try:
                bets = predict_func(hist)
                hit = any(len(set(bet) & actual) >= match_threshold for bet in bets)
                if hit:
                    hits += 1
                total += 1
            except:
                total += 1

        if total > 0:
            perm_rates.append(hits / total * 100)

    count_exceed = sum(1 for pr in perm_rates if pr >= real_rate)
    p_value = (count_exceed + 1) / (n_perm + 1)
    perm_mean = np.mean(perm_rates)
    perm_std = np.std(perm_rates) if len(perm_rates) > 1 else 1
    signal_edge = real_rate - perm_mean
    perm_z = signal_edge / perm_std if perm_std > 0 else 0

    return {
        'real_rate': real_rate,
        'real': real,
        'perm_mean': perm_mean,
        'perm_std': perm_std,
        'signal_edge': signal_edge,
        'perm_z': perm_z,
        'p_value': p_value,
        'n_perm': n_perm,
        'count_exceed': count_exceed,
    }


def mcnemar_test(details_a, details_b, label_a='A', label_b='B'):
    """McNemar 配對檢定"""
    from scipy.stats import chi2 as chi2_dist
    n = min(len(details_a), len(details_b))
    da, db = details_a[-n:], details_b[-n:]

    both_hit = sum(1 for a, b in zip(da, db) if a and b)
    a_only = sum(1 for a, b in zip(da, db) if a and not b)
    b_only = sum(1 for a, b in zip(da, db) if not a and b)
    both_miss = sum(1 for a, b in zip(da, db) if not a and not b)

    n_disc = a_only + b_only
    if n_disc == 0:
        chi2_val, p = 0, 1.0
    else:
        chi2_val = (abs(a_only - b_only) - 1) ** 2 / n_disc  # Yates校正
        if chi2_val < 0:
            chi2_val = 0
        p = 1 - chi2_dist.cdf(chi2_val, df=1)

    return {
        'both_hit': both_hit,
        'a_only': a_only,
        'b_only': b_only,
        'both_miss': both_miss,
        'n_disc': n_disc,
        'chi2': chi2_val,
        'p_value': p,
        'net': a_only - b_only,
        'winner': label_a if a_only > b_only else (label_b if b_only > a_only else 'TIE'),
    }


def stability_label(edges):
    """三窗口穩定性分類"""
    e150, e500, e1500 = edges
    if all(x > 0 for x in edges):
        return "✅ STABLE (三窗口全正)"
    elif e1500 < 0:
        return "❌ SHORT_MOMENTUM" if (e150 > 0 or e500 > 0) else "❌ INEFFECTIVE"
    elif e150 < 0 and e1500 > 0:
        return "⚠️ LATE_BLOOMER"
    elif e150 > 0 and e500 < 0 < e1500:
        return "⚠️ MODERATE_DECAY"
    else:
        return "⚠️ MIXED"


def analyze_neighbor_pool_stats(all_draws, test_periods=1500):
    """分析鄰號池統計特性"""
    pool_sizes = []
    hit_in_pool = []

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 100:
            continue
        hist = all_draws[:target_idx]
        actual = set(all_draws[target_idx]['numbers'][:PICK])

        pool = set(get_neighbor_pool(hist))
        pool_sizes.append(len(pool))
        hit_count = len(pool & actual)
        hit_in_pool.append(hit_count)

    return {
        'avg_pool_size': np.mean(pool_sizes),
        'min_pool': min(pool_sizes),
        'max_pool': max(pool_sizes),
        'avg_hit_in_pool': np.mean(hit_in_pool),
        'pct_ge1': sum(1 for h in hit_in_pool if h >= 1) / len(hit_in_pool) * 100,
        'pct_ge2': sum(1 for h in hit_in_pool if h >= 2) / len(hit_in_pool) * 100,
        'pct_ge3': sum(1 for h in hit_in_pool if h >= 3) / len(hit_in_pool) * 100,
        'n': len(pool_sizes),
    }


# ===== 主程式 =====

def main():
    t0 = time.time()

    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='DAILY_539')
    all_draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))
    print(f"✅ 載入 {len(all_draws)} 期 539 資料")
    print(f"   最新期: {all_draws[-1]['draw']} ({all_draws[-1]['date']})")

    # ===================================================================
    # 0. 鄰號池統計分析
    # ===================================================================
    print("\n" + "=" * 70)
    print("  §0: 鄰號池統計特性分析 (1500期)")
    print("=" * 70)
    stats = analyze_neighbor_pool_stats(all_draws, 1500)
    print(f"  平均鄰號池大小: {stats['avg_pool_size']:.1f} 碼")
    print(f"  池大小範圍: [{stats['min_pool']}, {stats['max_pool']}]")
    print(f"  平均命中: {stats['avg_hit_in_pool']:.2f} 碼/期")
    print(f"  命中≥1碼: {stats['pct_ge1']:.1f}%")
    print(f"  命中≥2碼: {stats['pct_ge2']:.1f}%")
    print(f"  命中≥3碼: {stats['pct_ge3']:.1f}%")
    print(f"  期望(若隨機): {5*stats['avg_pool_size']/39:.2f} 碼/期")

    # ===================================================================
    # 1. 三窗口驗證 — Neighbor-ACB V1 (Top-5鄰號)
    # ===================================================================
    print("\n" + "=" * 70)
    print("  §1: Neighbor-ACB V1 三窗口驗證 (Bet1=鄰號Top-5)")
    print("=" * 70)

    results_v1 = {}
    for periods in [150, 500, 1500]:
        r = backtest_539(pred_neighbor_acb_v1, all_draws, periods, n_bets=2)
        results_v1[periods] = r
        marker = '★' if r['edge'] > 0 else '  '
        print(f"  {periods:4d}p: M2+={r['hits']}/{r['total']} "
              f"({r['rate']:.2f}%) base={r['baseline']:.2f}% "
              f"Edge={r['edge']:+.2f}% z={r['z']:.2f} {marker}")

    edges_v1 = [results_v1[p]['edge'] for p in [150, 500, 1500]]
    print(f"  穩定性: {stability_label(edges_v1)}")

    # ===================================================================
    # 2. 三窗口驗證 — Neighbor-ACB V2 (Top-3鄰號+補充)
    # ===================================================================
    print("\n" + "=" * 70)
    print("  §2: Neighbor-ACB V2 三窗口驗證 (Bet1=鄰號Top-3+全池Top-2)")
    print("=" * 70)

    results_v2 = {}
    for periods in [150, 500, 1500]:
        r = backtest_539(pred_neighbor_acb_v2, all_draws, periods, n_bets=2)
        results_v2[periods] = r
        marker = '★' if r['edge'] > 0 else '  '
        print(f"  {periods:4d}p: M2+={r['hits']}/{r['total']} "
              f"({r['rate']:.2f}%) base={r['baseline']:.2f}% "
              f"Edge={r['edge']:+.2f}% z={r['z']:.2f} {marker}")

    edges_v2 = [results_v2[p]['edge'] for p in [150, 500, 1500]]
    print(f"  穩定性: {stability_label(edges_v2)}")

    # ===================================================================
    # 3. 基準比較 — MidFreq+ACB (現有冠軍)
    # ===================================================================
    print("\n" + "=" * 70)
    print("  §3: MidFreq+ACB 2注 基準確認 (現有ADOPTED, Edge +5.06%)")
    print("=" * 70)

    results_mf = {}
    for periods in [150, 500, 1500]:
        r = backtest_539(pred_midfreq_acb_2bet, all_draws, periods, n_bets=2)
        results_mf[periods] = r
        marker = '★' if r['edge'] > 0 else '  '
        print(f"  {periods:4d}p: M2+={r['hits']}/{r['total']} "
              f"({r['rate']:.2f}%) base={r['baseline']:.2f}% "
              f"Edge={r['edge']:+.2f}% z={r['z']:.2f} {marker}")

    edges_mf = [results_mf[p]['edge'] for p in [150, 500, 1500]]
    print(f"  穩定性: {stability_label(edges_mf)}")

    # ===================================================================
    # 4. 選定最佳版本進行 Permutation Test
    # ===================================================================
    best_version = 'V1' if edges_v1[2] >= edges_v2[2] else 'V2'
    best_func = pred_neighbor_acb_v1 if best_version == 'V1' else pred_neighbor_acb_v2
    best_results = results_v1 if best_version == 'V1' else results_v2
    print(f"\n  → 選定最佳版本: {best_version} (1500p Edge 較高) 進行Permutation Test")

    print("\n" + "=" * 70)
    print(f"  §4: Permutation Test — Neighbor-ACB {best_version} (200次, 1500期)")
    print("=" * 70)
    print("  執行中...")

    perm_result = permutation_test_539(best_func, all_draws, test_periods=1500,
                                        n_bets=2, n_perm=200)
    pr = perm_result
    print(f"  真實 M2+ 率: {pr['real_rate']:.2f}%")
    print(f"  Perm 平均:   {pr['perm_mean']:.2f}% ± {pr['perm_std']:.2f}%")
    print(f"  Signal Edge: {pr['signal_edge']:+.2f}%")
    print(f"  Perm z-score:{pr['perm_z']:.2f}")
    print(f"  p-value:     {pr['p_value']:.4f} ({pr['count_exceed']}/{pr['n_perm']}超越)")

    if pr['p_value'] <= 0.01:
        perm_judge = "SIGNAL_DETECTED ✅✅"
    elif pr['p_value'] <= 0.05:
        perm_judge = "SIGNAL_DETECTED ✅"
    elif pr['p_value'] <= 0.10:
        perm_judge = "MARGINAL ⚠️"
    else:
        perm_judge = "NO_SIGNAL ❌"
    print(f"  判定: {perm_judge}")

    # ===================================================================
    # 5. McNemar — Neighbor-ACB vs MidFreq+ACB
    # ===================================================================
    print("\n" + "=" * 70)
    print(f"  §5: McNemar — Neighbor-ACB {best_version} vs MidFreq+ACB (1500期)")
    print("=" * 70)

    mn1 = mcnemar_test(
        best_results[1500]['hit_details'],
        results_mf[1500]['hit_details'],
        label_a=f'Neighbor-ACB_{best_version}',
        label_b='MidFreq+ACB'
    )
    print(f"  兩者均命中: {mn1['both_hit']}")
    print(f"  Neighbor only: {mn1['a_only']}")
    print(f"  MidFreq only:  {mn1['b_only']}")
    print(f"  兩者均未中: {mn1['both_miss']}")
    print(f"  Net (A-B): {mn1['net']:+d}")
    print(f"  chi2={mn1['chi2']:.3f}, p={mn1['p_value']:.4f}")
    print(f"  勝出: {mn1['winner']}")

    if mn1['p_value'] < 0.05:
        mcnemar_judge1 = "顯著差異 — 兩策略不可互換"
    else:
        mcnemar_judge1 = "無顯著差異 — 可作為互補候選"
    print(f"  判定: {mcnemar_judge1}")

    # ===================================================================
    # 6. McNemar — Neighbor-ACB vs ACB 1注 (確認Neighbor注的附加價值)
    # ===================================================================
    print("\n" + "=" * 70)
    print(f"  §6: McNemar — Neighbor-ACB {best_version} vs ACB 1注 (確認Neighbor附加價值)")
    print("=" * 70)

    r_acb1 = backtest_539(pred_acb_1bet, all_draws, 1500, n_bets=1)
    mn2 = mcnemar_test(
        best_results[1500]['hit_details'],
        r_acb1['hit_details'],
        label_a=f'Neighbor-ACB_{best_version}(2注)',
        label_b='ACB_1注'
    )
    print(f"  ACB 1注 1500p Edge: {r_acb1['edge']:+.2f}% (基準 {r_acb1['baseline']:.2f}%)")
    print(f"  Neighbor-ACB只中: {mn2['a_only']}")
    print(f"  ACB-1注只中:      {mn2['b_only']}")
    print(f"  Net: {mn2['net']:+d}")
    print(f"  p={mn2['p_value']:.4f}")
    print(f"  判定: {'Neighbor注有附加價值' if mn2['net'] > 0 else '無顯著附加價值'}")

    # ===================================================================
    # 7. 結論摘要
    # ===================================================================
    print("\n" + "=" * 70)
    print("  §7: 綜合結論")
    print("=" * 70)

    best_e = best_results[1500]['edge']
    mf_e = results_mf[1500]['edge']

    print(f"\n  Neighbor-ACB {best_version} (1500p Edge {best_e:+.2f}%):")
    print(f"    150p: {edges_v1[0]:+.2f}% | 500p: {edges_v1[1]:+.2f}% | 1500p: {edges_v1[2]:+.2f}%"
          if best_version == 'V1' else
          f"    150p: {edges_v2[0]:+.2f}% | 500p: {edges_v2[1]:+.2f}% | 1500p: {edges_v2[2]:+.2f}%")
    print(f"    Perm p={perm_result['p_value']:.4f} ({perm_judge})")
    print(f"    vs MidFreq+ACB: net={mn1['net']:+d}, McNemar p={mn1['p_value']:.4f}")
    print(f"\n  MidFreq+ACB (1500p Edge {mf_e:+.2f}%, 現有ADOPTED):")
    print(f"    150p: {edges_mf[0]:+.2f}% | 500p: {edges_mf[1]:+.2f}% | 1500p: {edges_mf[2]:+.2f}%")

    # 採納決策
    print("\n  --- 採納決策 ---")
    if (pr['p_value'] <= 0.05 and
        all(x > 0 for x in (edges_v1 if best_version == 'V1' else edges_v2))):
        if mn1['net'] > 0:
            print("  ✅ PROVISIONAL — 三窗口全正 + Perm通過 + vs MidFreq+ACB正向")
            print("     建議: 評估4注組合(MidFreq+ACB 2注 + Neighbor-ACB 2注)")
        else:
            print("  ⚠️ CONDITIONAL — 三窗口全正 + Perm通過，但 McNemar劣於MidFreq+ACB")
            print("     建議: 不替換MidFreq+ACB，評估正交互補性(Bet3/Bet4)")
    elif pr['p_value'] > 0.10:
        print("  ❌ REJECT — Perm p值未達MARGINAL門檻")
        print("     建議: 歸檔，記錄失敗原因")
    else:
        print("  ⚠️ MONITOR — Perm MARGINAL，需更多資料確認")
        print("     建議: 觀察100期RSM，不採納為主策略")

    # ===================================================================
    # 8. 儲存結果
    # ===================================================================
    output = {
        'meta': {
            'script': 'backtest_539_neighbor_acb.py',
            'date': '2026-03-04',
            'data_periods': len(all_draws),
            'latest_draw': all_draws[-1]['draw'],
        },
        'neighbor_pool_stats': stats,
        'v1_results': {
            '150p': {'edge': results_v1[150]['edge'], 'rate': results_v1[150]['rate'],
                     'z': results_v1[150]['z']},
            '500p': {'edge': results_v1[500]['edge'], 'rate': results_v1[500]['rate'],
                     'z': results_v1[500]['z']},
            '1500p': {'edge': results_v1[1500]['edge'], 'rate': results_v1[1500]['rate'],
                      'z': results_v1[1500]['z']},
            'stability': stability_label(edges_v1),
        },
        'v2_results': {
            '150p': {'edge': results_v2[150]['edge'], 'rate': results_v2[150]['rate'],
                     'z': results_v2[150]['z']},
            '500p': {'edge': results_v2[500]['edge'], 'rate': results_v2[500]['rate'],
                     'z': results_v2[500]['z']},
            '1500p': {'edge': results_v2[1500]['edge'], 'rate': results_v2[1500]['rate'],
                      'z': results_v2[1500]['z']},
            'stability': stability_label(edges_v2),
        },
        'midfreq_acb_baseline': {
            '150p': results_mf[150]['edge'],
            '500p': results_mf[500]['edge'],
            '1500p': results_mf[1500]['edge'],
        },
        'permutation': {
            'version': best_version,
            'real_rate': pr['real_rate'],
            'perm_mean': pr['perm_mean'],
            'signal_edge': pr['signal_edge'],
            'p_value': pr['p_value'],
            'perm_z': pr['perm_z'],
            'judge': perm_judge,
        },
        'mcnemar_vs_midfreq': {
            'net': mn1['net'],
            'a_only': mn1['a_only'],
            'b_only': mn1['b_only'],
            'p_value': mn1['p_value'],
        },
        'elapsed_sec': round(time.time() - t0, 1),
    }

    out_path = os.path.join(project_root, 'backtest_539_neighbor_acb_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n  結果已儲存: {out_path}")
    print(f"  總耗時: {time.time() - t0:.1f}s")


if __name__ == '__main__':
    main()
