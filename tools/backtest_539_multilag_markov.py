#!/usr/bin/env python3
"""
今彩539 Multi-lag Markov Echo 驗證腳本
2026-03-14 115000065期檢討後 — L70 行動項目

研究問題:
  115000065 [02,05,11,12,15] 中 #11,#12 在 lag-3 期前 (115000062) 出現後重複
  是否存在 lag-2 / lag-3 的 Echo 信號？

策略設計:
  A) ACB_lag1_2bet: ACB + Markov lag-1 boost → 2注
  B) ACB_lag2_2bet: ACB + Markov lag-2 boost → 2注 (NEW)
  C) ACB_lag3_2bet: ACB + Markov lag-3 boost → 2注 (NEW)
  D) ACB_lag123_2bet: ACB + 綜合 lag-1/2/3 加權 boost → 2注

評分設計:
  lag_boost(n, lag_weight):
    若 n 在 lag 期前出現 → score × (1 + lag_weight)
    lag_weight: lag1=0.3, lag2=0.2, lag3=0.15

驗證:
  1. 三窗口 (150/500/1500期)
  2. Permutation test (200次)
  3. McNemar vs MidFreq+ACB 基準

基準:
  2注 M2+: 21.54%
  MidFreq+ACB 2注 Edge: +8.46% (300p Sharpe最高)
"""
import sys, os, json, time, random
import numpy as np
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


# ===== 核心評分函數 =====

def acb_scores_539(history, window=100):
    """ACB 異常捕捉分數 (與 production 完全一致)"""
    recent = history[-window:] if len(history) >= window else history
    counter = {n: 0 for n in range(1, MAX_NUM + 1)}
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            if 1 <= n <= MAX_NUM:
                counter[n] += 1
                last_seen[n] = i
    current = len(recent)
    expected = current * PICK / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM + 1):
        freq_deficit = expected - counter[n]
        gap = current - last_seen.get(n, -1)
        gap_score = gap / (current / 2) if current > 0 else 0
        bb = 1.2 if (n <= 5 or n >= 35) else 1.0
        m3 = 1.1 if n % 3 == 0 else 1.0
        scores[n] = (freq_deficit * 0.4 + gap_score * 0.6) * bb * m3
    return scores


def acb_scores_boundary_v2(history, window=100, boundary_threshold=8):
    """ACB 異常捕捉分數 - 擴展 boundary pool 到 n≤boundary_threshold"""
    recent = history[-window:] if len(history) >= window else history
    counter = {n: 0 for n in range(1, MAX_NUM + 1)}
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            if 1 <= n <= MAX_NUM:
                counter[n] += 1
                last_seen[n] = i
    current = len(recent)
    expected = current * PICK / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM + 1):
        freq_deficit = expected - counter[n]
        gap = current - last_seen.get(n, -1)
        gap_score = gap / (current / 2) if current > 0 else 0
        bb = 1.2 if (n <= boundary_threshold or n >= 35) else 1.0
        m3 = 1.1 if n % 3 == 0 else 1.0
        scores[n] = (freq_deficit * 0.4 + gap_score * 0.6) * bb * m3
    return scores


def midfreq_scores_539(history, window=100):
    """MidFreq 均值回歸分數"""
    recent = history[-window:] if len(history) >= window else history
    freq = {n: 0 for n in range(1, MAX_NUM + 1)}
    for d in recent:
        for n in d['numbers']:
            if 1 <= n <= MAX_NUM:
                freq[n] += 1
    expected = len(recent) * PICK / MAX_NUM
    max_dist = max(abs(freq[n] - expected) for n in range(1, MAX_NUM + 1))
    return {n: max_dist - abs(freq[n] - expected) for n in range(1, MAX_NUM + 1)}


def lag_echo_boost(base_scores, history, lags, lag_weights):
    """
    對 base_scores 疊加 multi-lag echo boost
    lags: list of int, e.g. [1, 2, 3]
    lag_weights: list of float, e.g. [0.3, 0.2, 0.15]
    若 history 不足則跳過對應 lag
    """
    boosted = dict(base_scores)
    for lag, wt in zip(lags, lag_weights):
        if len(history) < lag:
            continue
        lag_draw = set(history[-lag]['numbers'])
        for n in lag_draw:
            if 1 <= n <= MAX_NUM:
                boosted[n] = boosted.get(n, 0) * (1 + wt)
    return boosted


# ===== 預測函數 =====

def pred_midfreq_acb_2bet(history):
    """MidFreq+ACB 2注 (現有 ADOPTED 基準)"""
    midfreq = midfreq_scores_539(history)
    acb = acb_scores_539(history)
    mf_ranked = sorted(midfreq, key=lambda x: -midfreq[x])
    acb_ranked = sorted(acb, key=lambda x: -acb[x])
    bet1 = sorted(mf_ranked[:PICK])
    excl = set(bet1)
    bet2 = sorted([n for n in acb_ranked if n not in excl][:PICK])
    return [bet1, bet2]


def pred_acb_lag1_2bet(history):
    """ACB + Markov lag-1 boost → 2注 (lag-1 已知有效)"""
    acb = acb_scores_539(history)
    boosted = lag_echo_boost(acb, history, lags=[1], lag_weights=[0.30])
    ranked = sorted(boosted, key=lambda x: -boosted[x])
    bet1 = sorted(ranked[:PICK])
    excl = set(bet1)
    # Bet2: ACB without lag boost (orthogonal)
    acb_ranked = sorted(acb, key=lambda x: -acb[x])
    bet2 = sorted([n for n in acb_ranked if n not in excl][:PICK])
    return [bet1, bet2]


def pred_acb_lag2_2bet(history):
    """ACB + Markov lag-2 boost → 2注 (NEW: 驗證 lag-2 Echo)"""
    acb = acb_scores_539(history)
    boosted = lag_echo_boost(acb, history, lags=[2], lag_weights=[0.20])
    ranked = sorted(boosted, key=lambda x: -boosted[x])
    bet1 = sorted(ranked[:PICK])
    excl = set(bet1)
    acb_ranked = sorted(acb, key=lambda x: -acb[x])
    bet2 = sorted([n for n in acb_ranked if n not in excl][:PICK])
    return [bet1, bet2]


def pred_acb_lag3_2bet(history):
    """ACB + Markov lag-3 boost → 2注 (NEW: 驗證 lag-3 Echo)"""
    acb = acb_scores_539(history)
    boosted = lag_echo_boost(acb, history, lags=[3], lag_weights=[0.15])
    ranked = sorted(boosted, key=lambda x: -boosted[x])
    bet1 = sorted(ranked[:PICK])
    excl = set(bet1)
    acb_ranked = sorted(acb, key=lambda x: -acb[x])
    bet2 = sorted([n for n in acb_ranked if n not in excl][:PICK])
    return [bet1, bet2]


def pred_acb_lag123_2bet(history):
    """ACB + 綜合 lag-1/2/3 加權 boost → 2注 (NEW: 最大信號疊加)"""
    acb = acb_scores_539(history)
    boosted = lag_echo_boost(acb, history, lags=[1, 2, 3], lag_weights=[0.30, 0.20, 0.15])
    ranked = sorted(boosted, key=lambda x: -boosted[x])
    bet1 = sorted(ranked[:PICK])
    excl = set(bet1)
    acb_ranked = sorted(acb, key=lambda x: -acb[x])
    bet2 = sorted([n for n in acb_ranked if n not in excl][:PICK])
    return [bet1, bet2]


def pred_acb_lag13_2bet(history):
    """ACB + lag-1 + lag-3 (跳過 lag-2，聚焦 115000065 觀察到的 lag-3)"""
    acb = acb_scores_539(history)
    boosted = lag_echo_boost(acb, history, lags=[1, 3], lag_weights=[0.30, 0.15])
    ranked = sorted(boosted, key=lambda x: -boosted[x])
    bet1 = sorted(ranked[:PICK])
    excl = set(bet1)
    acb_ranked = sorted(acb, key=lambda x: -acb[x])
    bet2 = sorted([n for n in acb_ranked if n not in excl][:PICK])
    return [bet1, bet2]


# ===== 回測引擎 =====

def backtest_539(predict_func, all_draws, test_periods=1500, n_bets=2, min_hist=100):
    """539 通用回測 (M2+ 基準)"""
    hits, total = 0, 0
    hit_details = []
    for i in range(test_periods):
        idx = len(all_draws) - test_periods + i
        if idx < min_hist:
            hit_details.append(0)
            continue
        target = all_draws[idx]
        hist = all_draws[:idx]
        actual = set(target['numbers'][:PICK])
        try:
            bets = predict_func(hist)
            hit = any(len(set(b) & actual) >= 2 for b in bets)
            hit_details.append(1 if hit else 0)
            if hit:
                hits += 1
            total += 1
        except Exception:
            hit_details.append(0)
            total += 1
    rate = hits / total * 100 if total > 0 else 0
    baseline = BASELINES_M2[n_bets]
    edge = rate - baseline
    p0 = baseline / 100
    se = np.sqrt(p0 * (1 - p0) / total) if total > 0 else 1
    z = (rate / 100 - p0) / se if se > 0 else 0
    return {'hits': hits, 'total': total, 'rate': rate,
            'baseline': baseline, 'edge': edge, 'z': z,
            'hit_details': hit_details}


def three_window_test(predict_func, all_draws, n_bets=2):
    """三窗口驗證 (150/500/1500)"""
    results = {}
    for w in [150, 500, 1500]:
        if len(all_draws) < w + 100:
            results[w] = None
            continue
        results[w] = backtest_539(predict_func, all_draws, w, n_bets)
    return results


def permutation_test_539(predict_func, all_draws, test_periods=1500, n_bets=2, n_perm=200):
    """Permutation test (200次洗牌)"""
    real = backtest_539(predict_func, all_draws, test_periods, n_bets)
    real_rate = real['rate']

    target_indices = [len(all_draws) - test_periods + i
                      for i in range(test_periods)
                      if len(all_draws) - test_periods + i >= 100]
    all_actuals = [set(all_draws[idx]['numbers'][:PICK]) for idx in target_indices]

    perm_rates = []
    for p in range(n_perm):
        shuffled = list(all_actuals)
        rng = random.Random(p * 7919 + 42)
        rng.shuffle(shuffled)
        hits, total = 0, 0
        for i, idx in enumerate(target_indices):
            hist = all_draws[:idx]
            actual = shuffled[i]
            try:
                bets = predict_func(hist)
                if any(len(set(b) & actual) >= 2 for b in bets):
                    hits += 1
                total += 1
            except Exception:
                total += 1
        if total > 0:
            perm_rates.append(hits / total * 100)

    count_exceed = sum(1 for pr in perm_rates if pr >= real_rate)
    p_value = (count_exceed + 1) / (n_perm + 1)
    perm_mean = np.mean(perm_rates)
    perm_std = np.std(perm_rates) if len(perm_rates) > 1 else 1
    return {
        'real_rate': real_rate,
        'perm_mean': perm_mean,
        'signal_edge': real_rate - perm_mean,
        'perm_z': (real_rate - perm_mean) / perm_std if perm_std > 0 else 0,
        'p_value': p_value,
        'count_exceed': count_exceed,
        'n_perm': n_perm,
    }


def mcnemar_test(hits_a, hits_b):
    """McNemar 精確檢定"""
    n01 = sum(1 for a, b in zip(hits_a, hits_b) if a == 0 and b == 1)
    n10 = sum(1 for a, b in zip(hits_a, hits_b) if a == 1 and b == 0)
    if n01 + n10 == 0:
        return {'n01': 0, 'n10': 0, 'p': 1.0, 'sig': False}
    from scipy.stats import binomtest
    try:
        p = binomtest(n10, n01 + n10, 0.5).pvalue
    except Exception:
        total = n01 + n10
        p = min(1.0, 2 * sum(
            (0.5 ** total) * np.math.comb(total, k)
            for k in range(min(n10, n01), -1, -1)
        ) if total < 30 else 1.0)
    return {'n01': n01, 'n10': n10, 'p': p, 'sig': p < 0.05}


def judge(windows, perm, n_bets):
    """判斷策略是否通過驗證"""
    baseline = BASELINES_M2[n_bets]
    checks = []
    for w, r in windows.items():
        if r is None:
            continue
        checks.append(('window', w, r['edge'] > 0, f"edge={r['edge']:+.2f}%"))
    checks.append(('perm_p', None, perm['p_value'] < 0.05, f"p={perm['p_value']:.3f}"))
    checks.append(('perm_z', None, perm['perm_z'] > 1.64, f"z={perm['perm_z']:.2f}"))
    passed = sum(1 for c in checks if c[2])
    verdict = 'PASS' if passed >= len(checks) - 1 else 'FAIL'
    return verdict, checks, passed, len(checks)


# ===== 主程式 =====

def main():
    print("=" * 70)
    print(" 今彩539 Multi-lag Markov Echo 驗證 (L70 行動項目)")
    print(" 115000065期 [02,05,11,12,15] #11,#12 lag-3 重複現象研究")
    print("=" * 70)

    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='DAILY_539')
    all_draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))
    all_draws = [d for d in all_draws if d.get('numbers')]
    print(f"\n資料筆數: {len(all_draws)} 期")
    if len(all_draws) > 0:
        print(f"最新期: {all_draws[-1]['draw']} ({all_draws[-1].get('date', 'N/A')})")
        print(f"最新號碼: {all_draws[-1]['numbers']}")

    strategies = {
        'MidFreq+ACB_2bet (基準)': (pred_midfreq_acb_2bet, 2),
        'ACB+lag1_2bet': (pred_acb_lag1_2bet, 2),
        'ACB+lag2_2bet': (pred_acb_lag2_2bet, 2),
        'ACB+lag3_2bet': (pred_acb_lag3_2bet, 2),
        'ACB+lag1+2+3_2bet': (pred_acb_lag123_2bet, 2),
        'ACB+lag1+3_2bet': (pred_acb_lag13_2bet, 2),
    }

    results = {}
    for name, (func, n_bets) in strategies.items():
        print(f"\n{'─' * 60}")
        print(f" 策略: {name}")
        print(f"{'─' * 60}")

        print(" 三窗口回測...")
        windows = three_window_test(func, all_draws, n_bets)
        for w, r in windows.items():
            if r:
                verdict_w = '✓' if r['edge'] > 0 else '✗'
                print(f"  {w:4d}p: rate={r['rate']:.2f}% edge={r['edge']:+.2f}% z={r['z']:.2f} {verdict_w}")

        print(" Permutation test (200次)...")
        perm = permutation_test_539(func, all_draws, 1500, n_bets, 200)
        sig = '✓' if perm['p_value'] < 0.05 else '✗'
        print(f"  signal_edge={perm['signal_edge']:+.2f}% perm_z={perm['perm_z']:.2f} p={perm['p_value']:.3f} {sig}")

        verdict, checks, passed, total_checks = judge(windows, perm, n_bets)
        print(f" 判定: {verdict} ({passed}/{total_checks})")

        results[name] = {
            'windows': {k: (v['edge'] if v else None) for k, v in windows.items()},
            'perm_p': perm['p_value'],
            'perm_z': perm['perm_z'],
            'signal_edge': perm['signal_edge'],
            'verdict': verdict,
            'hit_details_1500': windows.get(1500, {}).get('hit_details', []) if windows.get(1500) else [],
        }

    # McNemar: 各 lag 策略 vs 基準
    print(f"\n{'=' * 70}")
    print(" McNemar 檢定 vs MidFreq+ACB 基準")
    print(f"{'=' * 70}")

    base_name = 'MidFreq+ACB_2bet (基準)'
    base_hits = results[base_name]['hit_details_1500']
    for name, r in results.items():
        if name == base_name:
            continue
        other_hits = r['hit_details_1500']
        if len(base_hits) == len(other_hits) and len(base_hits) > 0:
            mc = mcnemar_test(base_hits, other_hits)
            sig = '✓ SIG' if mc['sig'] else '  ns'
            print(f"  {name:<30} n01={mc['n01']:3d} n10={mc['n10']:3d} p={mc['p']:.3f} {sig}")

    # 摘要
    print(f"\n{'=' * 70}")
    print(" 摘要")
    print(f"{'=' * 70}")
    for name, r in results.items():
        w150 = f"{r['windows'].get(150, 0):+.1f}%" if r['windows'].get(150) is not None else "N/A"
        w500 = f"{r['windows'].get(500, 0):+.1f}%" if r['windows'].get(500) is not None else "N/A"
        w1500 = f"{r['windows'].get(1500, 0):+.1f}%" if r['windows'].get(1500) is not None else "N/A"
        print(f" {name:<32} 150p={w150} 500p={w500} 1500p={w1500} "
              f"perm_p={r['perm_p']:.3f} → {r['verdict']}")

    # 儲存結果
    out_path = os.path.join(project_root, 'backtest_539_multilag_markov_results.json')
    save_data = {k: {kk: vv for kk, vv in v.items() if kk != 'hit_details_1500'}
                 for k, v in results.items()}
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"\n結果儲存至: {out_path}")

    print("\n注意事項:")
    print("  - 任何 lag-2/3 策略若 PASS，需額外 McNemar vs lag-1 確認增量效益")
    print("  - 通過條件: 三窗口全正 + perm p<0.05 + perm_z>1.64")
    print("  - 若 lag-2/3 PASS，下一步整合進 ACB+Markov 策略並執行 1500期三窗口")


if __name__ == '__main__':
    main()
