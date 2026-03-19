#!/usr/bin/env python3
"""
539 P2c/P3a 正式驗證 — McNemar + 高樣本 Permutation Test
2026-03-01 修正版: 解決 p-value floor 問題 (≥500 permutations)

測試:
  1. P2c (MidFreq+ACB 2注) — McNemar vs 隨機 2注, permutation ≥500次
  2. P3a (Markov+MidFreq+ACB 3注) — McNemar vs F4Cold 前3注, permutation ≥500次
  3. F4Cold 3注 基準回測 (作為 McNemar 對照)
"""
import sys, os, json, time, random
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from tools.quick_predict import (
    _539_acb_bet, _539_markov_bet, _539_midfreq_bet, _539_fourier_scores
)

MAX_NUM = 39
PICK = 5
MATCH_THRESHOLD = 2
N_PERMS = 500  # 500次 shuffle — 最小 p = 1/501 ≈ 0.002


def backtest_paired(history, predict_fn_a, predict_fn_b, test_periods):
    """配對回測 — 同時記錄 A 和 B 在每期的命中/未命中"""
    start_idx = len(history) - test_periods
    if start_idx < 500:
        start_idx = 500

    a_hits = []
    b_hits = []

    for i in range(start_idx, len(history)):
        train = history[:i]
        actual = set(history[i]['numbers'])

        try:
            bets_a = predict_fn_a(train)
            best_a = max(len(set(b) & actual) for b in bets_a)
        except Exception:
            best_a = 0

        try:
            bets_b = predict_fn_b(train)
            best_b = max(len(set(b) & actual) for b in bets_b)
        except Exception:
            best_b = 0

        a_hits.append(1 if best_a >= MATCH_THRESHOLD else 0)
        b_hits.append(1 if best_b >= MATCH_THRESHOLD else 0)

    return np.array(a_hits), np.array(b_hits)


def mcnemar_test(hits_a, hits_b):
    """McNemar test: 比較兩策略配對勝率"""
    n = len(hits_a)
    # b: A命中 B未命中; c: A未命中 B命中
    b = np.sum((hits_a == 1) & (hits_b == 0))
    c = np.sum((hits_a == 0) & (hits_b == 1))

    # 含 Yates 校正
    if b + c == 0:
        return 0, 1.0, int(b), int(c)

    chi2 = (abs(b - c) - 1) ** 2 / (b + c)
    from scipy.stats import chi2 as chi2_dist
    p_value = 1 - chi2_dist.cdf(chi2, df=1)

    return chi2, p_value, int(b), int(c)


def backtest_strategy(history, predict_fn, test_periods):
    """標準回測"""
    start_idx = len(history) - test_periods
    if start_idx < 500:
        start_idx = 500

    wins = 0
    total = 0

    for i in range(start_idx, len(history)):
        train = history[:i]
        actual = set(history[i]['numbers'])

        try:
            bets = predict_fn(train)
        except Exception:
            continue

        total += 1
        best_match = max(len(set(b) & actual) for b in bets)
        if best_match >= MATCH_THRESHOLD:
            wins += 1

    return wins, total, wins / total * 100 if total > 0 else 0


def permutation_test_proper(history, predict_fn, test_periods, n_perms=500):
    """正式 Permutation Test — 500+ shuffles"""
    print(f"    正式 permutation test ({n_perms} shuffles, {test_periods} 期)...")

    # 真實回測
    real_wins, real_total, real_rate = backtest_strategy(
        history, predict_fn, test_periods)

    if real_total == 0:
        return real_rate, 0, 1.0, 0

    # Permutation: 打亂號碼時序
    perm_rates = []
    numbers_pool = [d['numbers'] for d in history]

    for p in range(n_perms):
        if (p + 1) % 100 == 0:
            print(f"      shuffle {p+1}/{n_perms}...")

        shuffled_numbers = numbers_pool.copy()
        random.shuffle(shuffled_numbers)
        shuffled_hist = []
        for j, d in enumerate(history):
            sd = d.copy()
            sd['numbers'] = shuffled_numbers[j]
            shuffled_hist.append(sd)

        _, _, perm_rate = backtest_strategy(
            shuffled_hist, predict_fn, min(test_periods, 500))
        perm_rates.append(perm_rate)

    perm_mean = np.mean(perm_rates)
    perm_std = np.std(perm_rates) if len(perm_rates) > 1 else 1
    edge = real_rate - perm_mean
    z = edge / perm_std if perm_std > 0 else 0

    # 經驗 p-value (有多少 shuffle >= real)
    p_empirical = (np.sum([pr >= real_rate for pr in perm_rates]) + 1) / (n_perms + 1)

    # 從 z-score 計算的 p-value (更精確)
    from scipy.stats import norm
    p_from_z = 1 - norm.cdf(z)

    return {
        'real_rate': real_rate,
        'perm_mean': perm_mean,
        'perm_std': perm_std,
        'edge': edge,
        'z_score': z,
        'p_empirical': p_empirical,
        'p_from_z': p_from_z,
        'n_perms': n_perms,
        'real_wins': real_wins,
        'real_total': real_total,
    }


# ==================== Strategy functions ====================

def make_p2c_2bet(history):
    """P2c: MidFreq + ACB 正交2注"""
    bet1 = _539_midfreq_bet(history)
    bet2 = _539_acb_bet(history, exclude=set(bet1))
    return [bet1, bet2]


def make_p3a_3bet(history):
    """P3a: Markov + MidFreq + ACB 正交3注"""
    bet1 = _539_markov_bet(history)
    excl = set(bet1)
    bet2 = _539_midfreq_bet(history, exclude=excl)
    excl.update(bet2)
    bet3 = _539_acb_bet(history, exclude=excl)
    return [bet1, bet2, bet3]


def make_f4cold_3bet(history):
    """F4Cold 前3注: Fourier rank 1-5, 6-10, 11-15"""
    sc = _539_fourier_scores(history, window=500)
    ranked = [n for n in sorted(sc, key=lambda x: -sc[x]) if sc[n] > 0]
    bets = []
    for i in range(3):
        chunk = ranked[i * 5:(i + 1) * 5]
        if len(chunk) >= 5:
            bets.append(sorted(chunk))
        else:
            excl = set(n for b in bets for n in b)
            remaining = [n for n in ranked if n not in excl]
            bets.append(sorted(remaining[:5]))
    return bets


def make_f4cold_5bet(history):
    """F4Cold 全5注"""
    sc = _539_fourier_scores(history, window=500)
    ranked = [n for n in sorted(sc, key=lambda x: -sc[x]) if sc[n] > 0]
    bets = [sorted(ranked[i * 5:(i + 1) * 5]) for i in range(4)]
    excl = set(n for b in bets for n in b)
    freq = Counter(n for d in history[-100:] for n in d['numbers'])
    cold = sorted([n for n in range(1, 40) if n not in excl],
                  key=lambda n: freq.get(n, 0))
    bets.append(sorted(cold[:5]))
    return bets


# ==================== Main ====================

def main():
    random.seed(42)
    np.random.seed(42)

    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(all_draws, key=lambda x: (x['date'], x['draw']))

    print(f"Total 539 draws: {len(history)}")
    print(f"Latest: {history[-1]['draw']} ({history[-1]['date']})")

    WINDOWS = [150, 500, 1500]

    # 隨機基準
    baselines = {1: 11.40, 2: 21.54, 3: 30.50}

    # ==================== Part 1: 三窗口回測 ====================
    print("\n" + "=" * 80)
    print("  Part 1: 三窗口回測")
    print("=" * 80)

    strategies = [
        ('P2c: MidFreq+ACB 2bet', make_p2c_2bet, 2),
        ('P3a: Markov+MidFreq+ACB 3bet', make_p3a_3bet, 3),
        ('F4Cold 3bet (baseline)', make_f4cold_3bet, 3),
        ('F4Cold 5bet (PROVISIONAL)', make_f4cold_5bet, 5),
    ]

    results = {}
    for label, fn, n_bets in strategies:
        print(f"\n  --- {label} ---")
        window_results = {}
        for w in WINDOWS:
            t0 = time.time()
            wins, total, rate = backtest_strategy(history, fn, w)
            elapsed = time.time() - t0
            bl = baselines.get(n_bets, 30.50)
            edge = rate - bl
            window_results[w] = {
                'wins': wins, 'total': total, 'rate': rate, 'edge': edge
            }
            print(f"    {w:4d}期: {wins:3d}/{total:3d} = {rate:5.2f}% | "
                  f"baseline={bl:.2f}% | Edge={edge:+.2f}% | {elapsed:.1f}s")

        edges = [window_results[w]['edge'] for w in WINDOWS]
        stability = "STABLE" if all(e > 0 for e in edges) else "UNSTABLE"

        # 檢查衰減模式
        if edges[0] > edges[2] * 2 and all(e > 0 for e in edges):
            stability = "MODERATE_DECAY"

        print(f"    三窗口: {stability} | Edges: {[f'{e:+.2f}%' for e in edges]}")
        results[label] = {'n_bets': n_bets, 'windows': window_results, 'stability': stability}

    # ==================== Part 2: McNemar P3a vs F4Cold ====================
    print("\n" + "=" * 80)
    print("  Part 2: McNemar Test — P3a vs F4Cold 3bet (1500期)")
    print("=" * 80)

    t0 = time.time()
    hits_p3a, hits_f4cold = backtest_paired(
        history, make_p3a_3bet, make_f4cold_3bet, test_periods=1500)
    elapsed = time.time() - t0

    p3a_rate = hits_p3a.sum() / len(hits_p3a) * 100
    f4cold_rate = hits_f4cold.sum() / len(hits_f4cold) * 100
    chi2, p_mcnemar, b, c = mcnemar_test(hits_p3a, hits_f4cold)

    print(f"    P3a 勝率: {p3a_rate:.2f}% ({hits_p3a.sum()}/{len(hits_p3a)})")
    print(f"    F4Cold 勝率: {f4cold_rate:.2f}% ({hits_f4cold.sum()}/{len(hits_f4cold)})")
    print(f"    P3a勝F4Cold敗: {b} 期 | P3a敗F4Cold勝: {c} 期 | net: {b-c:+d}")
    print(f"    McNemar chi2={chi2:.3f} | p={p_mcnemar:.6f}")
    print(f"    結論: {'P3a 顯著優於 F4Cold' if p_mcnemar < 0.05 else 'P3a 與 F4Cold 無顯著差異'}")
    print(f"    耗時: {elapsed:.1f}s")

    mcnemar_result = {
        'p3a_rate': p3a_rate, 'f4cold_rate': f4cold_rate,
        'chi2': chi2, 'p_value': p_mcnemar,
        'p3a_wins_f4cold_loses': b, 'p3a_loses_f4cold_wins': c,
        'net': b - c,
        'significant': p_mcnemar < 0.05,
    }

    # ==================== Part 3: Permutation Tests (500x) ====================
    print("\n" + "=" * 80)
    print(f"  Part 3: Permutation Tests ({N_PERMS} shuffles)")
    print("=" * 80)

    perm_results = {}

    # P2c
    print(f"\n  --- P2c: MidFreq+ACB 2bet ---")
    t0 = time.time()
    perm_p2c = permutation_test_proper(history, make_p2c_2bet, test_periods=1500, n_perms=N_PERMS)
    elapsed = time.time() - t0
    print(f"    Real={perm_p2c['real_rate']:.2f}% | Perm={perm_p2c['perm_mean']:.2f}% ± {perm_p2c['perm_std']:.2f}%")
    print(f"    Edge={perm_p2c['edge']:+.2f}% | z={perm_p2c['z_score']:.2f}")
    print(f"    p_empirical={perm_p2c['p_empirical']:.4f} | p_from_z={perm_p2c['p_from_z']:.6f}")
    verdict_p2c = "SIGNAL" if perm_p2c['p_from_z'] < 0.05 else "NO SIGNAL"
    print(f"    結論: {verdict_p2c} | {elapsed:.1f}s")
    perm_results['P2c'] = perm_p2c

    # P3a
    print(f"\n  --- P3a: Markov+MidFreq+ACB 3bet ---")
    t0 = time.time()
    perm_p3a = permutation_test_proper(history, make_p3a_3bet, test_periods=1500, n_perms=N_PERMS)
    elapsed = time.time() - t0
    print(f"    Real={perm_p3a['real_rate']:.2f}% | Perm={perm_p3a['perm_mean']:.2f}% ± {perm_p3a['perm_std']:.2f}%")
    print(f"    Edge={perm_p3a['edge']:+.2f}% | z={perm_p3a['z_score']:.2f}")
    print(f"    p_empirical={perm_p3a['p_empirical']:.4f} | p_from_z={perm_p3a['p_from_z']:.6f}")
    verdict_p3a = "SIGNAL" if perm_p3a['p_from_z'] < 0.05 else "NO SIGNAL"
    print(f"    結論: {verdict_p3a} | {elapsed:.1f}s")
    perm_results['P3a'] = perm_p3a

    # ==================== Final Summary ====================
    print("\n" + "=" * 80)
    print("  FINAL SUMMARY")
    print("=" * 80)

    p2c_key = 'P2c: MidFreq+ACB 2bet'
    p3a_key = 'P3a: Markov+MidFreq+ACB 3bet'
    f4c_key = 'F4Cold 3bet (baseline)'

    p2c_edges = [f"{results[p2c_key]['windows'][w]['edge']:+.2f}%" for w in WINDOWS]
    print(f"\n  P2c (MidFreq+ACB 2注):")
    print(f"    三窗口 Edge: {p2c_edges}")
    print(f"    Stability: {results[p2c_key]['stability']}")
    print(f"    Permutation: z={perm_p2c['z_score']:.2f}, p_z={perm_p2c['p_from_z']:.6f}, p_emp={perm_p2c['p_empirical']:.4f}")
    p2c_pass = perm_p2c['p_from_z'] < 0.05 and results[p2c_key]['stability'] in ['STABLE']
    print(f"    VERDICT: {'ADOPT' if p2c_pass else 'PENDING'}")

    p3a_edges = [f"{results[p3a_key]['windows'][w]['edge']:+.2f}%" for w in WINDOWS]
    print(f"\n  P3a (Markov+MidFreq+ACB 3注):")
    print(f"    三窗口 Edge: {p3a_edges}")
    print(f"    Stability: {results[p3a_key]['stability']}")
    print(f"    Permutation: z={perm_p3a['z_score']:.2f}, p_z={perm_p3a['p_from_z']:.6f}, p_emp={perm_p3a['p_empirical']:.4f}")
    print(f"    McNemar vs F4Cold: chi2={chi2:.3f}, p={p_mcnemar:.6f}, net={b-c:+d}")
    p3a_pass = perm_p3a['p_from_z'] < 0.05 and p_mcnemar < 0.05 and results[p3a_key]['stability'] in ['STABLE']
    print(f"    VERDICT: {'ADOPT (replace F4Cold)' if p3a_pass else 'PENDING'}")

    f4c_edges = [f"{results[f4c_key]['windows'][w]['edge']:+.2f}%" for w in WINDOWS]
    print(f"\n  F4Cold 3bet (current baseline):")
    print(f"    三窗口 Edge: {f4c_edges}")

    # Save results
    output = {
        'test_date': '2026-03-01',
        'trigger': '115000054期修正驗證',
        'total_draws': len(history),
        'baselines': baselines,
        'three_window': {k: {
            'n_bets': v['n_bets'],
            'stability': v['stability'],
            'windows': {str(w): v['windows'][w] for w in WINDOWS}
        } for k, v in results.items()},
        'mcnemar_p3a_vs_f4cold': mcnemar_result,
        'permutation': {k: v for k, v in perm_results.items()},
    }

    outpath = os.path.join(project_root, 'backtest_539_validation_results.json')
    with open(outpath, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=float)
    print(f"\n  結果已儲存: {outpath}")


if __name__ == '__main__':
    main()
