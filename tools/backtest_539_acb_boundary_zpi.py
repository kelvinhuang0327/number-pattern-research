#!/usr/bin/env python3
"""
今彩539 ACB Boundary Pool 擴大驗證
2026-03-14 115000065期檢討後 — 評審 P2 行動項目

研究問題:
  115000065 [02,05,11,12,15] 中 #02,#05 靠近下邊界，#15 在 Z1 中上段
  現有 ACB boundary_bonus n≤5 已 boost #02,#05
  問題：擴大到 n≤8 是否讓 #06,#07,#08 也受益？是否提升整體 Edge？

策略矩陣:
  A) ACB_b5_1bet:  boundary n≤5 (現有 ADOPTED)
  B) ACB_b8_1bet:  boundary n≤8 (NEW)
  C) ACB_b10_1bet: boundary n≤10 (NEW, 較寬鬆)
  D) ACB_b5_2bet:  boundary n≤5 + MidFreq (現有2注基準)
  E) ACB_b8_2bet:  boundary n≤8 + MidFreq (NEW)

Zone Pressure Index (ZPI) 研究:
  額外輸出每期的 ZPI 歷史，供後續 Zone補充注研究
  ZPI_z1(t) = Σ(Z1_count in last-100p) - 100 × E[Z1]
  E[Z1] = 13/39 × 5 = 1.667

通過條件:
  三窗口全正 + perm p<0.05 + perm_z>1.64
"""
import sys, os, json, random
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

# Zone 定義 (與 production 一致)
ZONES = {
    'Z1': (1, 13),    # 低號
    'Z2': (14, 26),   # 中號
    'Z3': (27, 39),   # 高號
}
E_Z1 = (13 / 39) * 5  # = 5/3 ≈ 1.667


# ===== 評分函數 =====

def acb_scores_with_boundary(history, window=100, boundary_threshold=5):
    """
    ACB 分數，支援可調 boundary_threshold
    boundary_bonus = 1.2 for n <= boundary_threshold or n >= 35
    """
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


# ===== 預測函數 =====

def make_acb_1bet(boundary):
    """工廠函數: 建立指定 boundary 的 1注 ACB 預測函數"""
    def pred(history):
        scores = acb_scores_with_boundary(history, boundary_threshold=boundary)
        ranked = sorted(scores, key=lambda x: -scores[x])
        return [sorted(ranked[:PICK])]
    pred.__name__ = f'ACB_b{boundary}_1bet'
    return pred


def make_acb_midfreq_2bet(boundary):
    """工廠函數: 建立指定 boundary 的 MidFreq+ACB 2注 預測函數"""
    def pred(history):
        midfreq = midfreq_scores_539(history)
        acb = acb_scores_with_boundary(history, boundary_threshold=boundary)
        mf_ranked = sorted(midfreq, key=lambda x: -midfreq[x])
        acb_ranked = sorted(acb, key=lambda x: -acb[x])
        bet1 = sorted(mf_ranked[:PICK])
        excl = set(bet1)
        bet2 = sorted([n for n in acb_ranked if n not in excl][:PICK])
        return [bet1, bet2]
    pred.__name__ = f'ACB_b{boundary}+MidFreq_2bet'
    return pred


# ===== ZPI 計算 (Zone Pressure Index) =====

def compute_zpi_history(all_draws, window=100):
    """
    對每期計算回溯 window 期的 ZPI
    ZPI_Z1(t) = 實際Z1出現次數 - E[Z1]×window
    返回: list of {'period': ..., 'zpi_z1': ..., 'zpi_z2': ..., 'zpi_z3': ...}
    """
    e_z1 = (13 / 39) * PICK * window
    e_z2 = (13 / 39) * PICK * window
    e_z3 = (13 / 39) * PICK * window

    zpi_records = []
    for t in range(window, len(all_draws)):
        recent = all_draws[t - window:t]
        cnt_z1 = sum(1 for d in recent for n in d['numbers'] if 1 <= n <= 13)
        cnt_z2 = sum(1 for d in recent for n in d['numbers'] if 14 <= n <= 26)
        cnt_z3 = sum(1 for d in recent for n in d['numbers'] if 27 <= n <= 39)
        zpi_records.append({
            'period': all_draws[t].get('draw', t),
            'zpi_z1': cnt_z1 - e_z1,
            'zpi_z2': cnt_z2 - e_z2,
            'zpi_z3': cnt_z3 - e_z3,
            'actual_z1': cnt_z1 / window,
            'next_z1': sum(1 for n in all_draws[t]['numbers'] if 1 <= n <= 13),
        })
    return zpi_records


def analyze_zpi_predictive(all_draws, window=100):
    """
    分析 ZPI 的預測力:
    當 ZPI_Z1 < threshold (Z1被壓抑) 時，下期 Z1≥3 的概率是否顯著升高？
    """
    zpi_records = compute_zpi_history(all_draws, window)

    results = {}
    for threshold in [-5, -8, -10, -12]:
        triggered = [r for r in zpi_records if r['zpi_z1'] < threshold]
        if not triggered:
            continue
        not_triggered = [r for r in zpi_records if r['zpi_z1'] >= threshold]
        p_z1ge3_triggered = np.mean([1 if r['next_z1'] >= 3 else 0 for r in triggered])
        p_z1ge3_base = np.mean([1 if r['next_z1'] >= 3 else 0 for r in not_triggered])
        lift = p_z1ge3_triggered - p_z1ge3_base
        n = len(triggered)
        p_b = p_z1ge3_base
        se = np.sqrt(p_b * (1 - p_b) / n) if n > 0 and 0 < p_b < 1 else 1
        z = lift / se if se > 0 else 0
        results[threshold] = {
            'threshold': threshold,
            'n_triggered': n,
            'p_z1ge3_when_triggered': p_z1ge3_triggered,
            'p_z1ge3_baseline': p_z1ge3_base,
            'lift': lift,
            'z': z,
            'sig': abs(z) > 1.96,
        }
    return results


# ===== 回測引擎 (與 multilag 相同) =====

def backtest_539(predict_func, all_draws, test_periods=1500, n_bets=2, min_hist=100):
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


def three_window_test(predict_func, all_draws, n_bets):
    results = {}
    for w in [150, 500, 1500]:
        if len(all_draws) < w + 100:
            results[w] = None
            continue
        results[w] = backtest_539(predict_func, all_draws, w, n_bets)
    return results


def permutation_test_539(predict_func, all_draws, test_periods=1500, n_bets=2, n_perm=200):
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
            try:
                bets = predict_func(hist)
                if any(len(set(b) & shuffled[i]) >= 2 for b in bets):
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
    n01 = sum(1 for a, b in zip(hits_a, hits_b) if a == 0 and b == 1)
    n10 = sum(1 for a, b in zip(hits_a, hits_b) if a == 1 and b == 0)
    if n01 + n10 == 0:
        return {'n01': 0, 'n10': 0, 'p': 1.0, 'sig': False}
    from scipy.stats import binomtest
    try:
        p = binomtest(n10, n01 + n10, 0.5).pvalue
    except Exception:
        p = 1.0
    return {'n01': n01, 'n10': n10, 'p': p, 'sig': p < 0.05}


# ===== 主程式 =====

def main():
    print("=" * 70)
    print(" 今彩539 ACB Boundary Pool 擴大 + ZPI 研究 (P2 行動項目)")
    print("=" * 70)

    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='DAILY_539')
    all_draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))
    all_draws = [d for d in all_draws if d.get('numbers')]
    print(f"\n資料筆數: {len(all_draws)} 期")
    if all_draws:
        print(f"最新期: {all_draws[-1]['draw']} ({all_draws[-1].get('date', 'N/A')})")

    # === Part 1: Boundary Pool 驗證 ===
    print(f"\n{'=' * 70}")
    print(" Part 1: Boundary Pool 比較 (n≤5 vs n≤8 vs n≤10)")
    print(f"{'=' * 70}")

    strategies_1bet = [
        ('ACB_b5_1bet (現有ADOPTED)', make_acb_1bet(5), 1),
        ('ACB_b8_1bet (NEW)', make_acb_1bet(8), 1),
        ('ACB_b10_1bet (NEW)', make_acb_1bet(10), 1),
    ]
    strategies_2bet = [
        ('ACB_b5+MidFreq_2bet (基準)', make_acb_midfreq_2bet(5), 2),
        ('ACB_b8+MidFreq_2bet (NEW)', make_acb_midfreq_2bet(8), 2),
    ]

    all_results = {}
    for name, func, n_bets in strategies_1bet + strategies_2bet:
        print(f"\n 策略: {name}")
        windows = three_window_test(func, all_draws, n_bets)
        for w, r in windows.items():
            if r:
                ok = '✓' if r['edge'] > 0 else '✗'
                print(f"  {w:4d}p: rate={r['rate']:.2f}% edge={r['edge']:+.2f}% {ok}")

        perm = permutation_test_539(func, all_draws, 1500, n_bets)
        sig = '✓' if perm['p_value'] < 0.05 else '✗'
        print(f"  perm: signal={perm['signal_edge']:+.2f}% z={perm['perm_z']:.2f} p={perm['p_value']:.3f} {sig}")

        all_results[name] = {
            'windows': {k: (v['edge'] if v else None) for k, v in windows.items()},
            'perm_p': perm['p_value'],
            'perm_z': perm['perm_z'],
            'signal_edge': perm['signal_edge'],
            'hit_details': windows.get(1500, {}).get('hit_details', []) if windows.get(1500) else [],
        }

    # McNemar: b8 vs b5
    print(f"\n{'─' * 60}")
    print(" McNemar: b8 vs b5 (1注)")
    b5_hits = all_results.get('ACB_b5_1bet (現有ADOPTED)', {}).get('hit_details', [])
    b8_hits = all_results.get('ACB_b8_1bet (NEW)', {}).get('hit_details', [])
    if b5_hits and b8_hits:
        mc = mcnemar_test(b5_hits, b8_hits)
        print(f"  n01={mc['n01']} n10={mc['n10']} p={mc['p']:.3f} {'SIG' if mc['sig'] else 'ns'}")

    # === Part 2: ZPI 研究 ===
    print(f"\n{'=' * 70}")
    print(" Part 2: Zone Pressure Index (ZPI) 預測力研究")
    print(f"{'=' * 70}")
    print(" 當 ZPI_Z1 < threshold 時 (Z1被壓抑)，下期 Z1≥3 的概率提升？")

    zpi_results = analyze_zpi_predictive(all_draws, window=100)
    for threshold, r in sorted(zpi_results.items()):
        sig = '★ SIG' if r['sig'] else '  ns'
        print(f"  ZPI<{threshold:3d}: n={r['n_triggered']:4d} "
              f"P(Z1≥3|triggered)={r['p_z1ge3_when_triggered']*100:.1f}% "
              f"base={r['p_z1ge3_baseline']*100:.1f}% "
              f"lift={r['lift']*100:+.1f}% z={r['z']:.2f} {sig}")

    # 計算目前 ZPI 值 (最新期)
    zpi_history = compute_zpi_history(all_draws, window=100)
    if zpi_history:
        current_zpi = zpi_history[-1]
        print(f"\n  當前 ZPI (基於最新100期):")
        print(f"    Z1={current_zpi['zpi_z1']:+.1f}  Z2={current_zpi['zpi_z2']:+.1f}  Z3={current_zpi['zpi_z3']:+.1f}")
        alert = ''
        if current_zpi['zpi_z1'] < -8:
            alert = ' ⚠ Z1壓力累積，下期可能出現Z1集中！'
        elif current_zpi['zpi_z3'] < -8:
            alert = ' ⚠ Z3壓力累積，下期可能出現Z3集中！'
        if alert:
            print(f"    {alert}")

    # === 摘要 ===
    print(f"\n{'=' * 70}")
    print(" 摘要")
    print(f"{'=' * 70}")
    for name, r in all_results.items():
        w150 = f"{r['windows'].get(150, 0):+.1f}%" if r['windows'].get(150) is not None else "N/A"
        w500 = f"{r['windows'].get(500, 0):+.1f}%" if r['windows'].get(500) is not None else "N/A"
        w1500 = f"{r['windows'].get(1500, 0):+.1f}%" if r['windows'].get(1500) is not None else "N/A"
        verdict = 'PASS' if r['perm_p'] < 0.05 and all(
            v > 0 for v in r['windows'].values() if v is not None) else 'FAIL'
        print(f" {name:<33} 150p={w150} 500p={w500} 1500p={w1500} p={r['perm_p']:.3f} → {verdict}")

    # 儲存
    out_path = os.path.join(project_root, 'backtest_539_acb_boundary_zpi_results.json')
    save_data = {k: {kk: vv for kk, vv in v.items() if kk != 'hit_details'}
                 for k, v in all_results.items()}
    save_data['zpi_analysis'] = zpi_results
    if zpi_history:
        save_data['current_zpi'] = zpi_history[-1]
        save_data['zpi_history_last10'] = zpi_history[-10:]
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2,
                  default=lambda o: bool(o) if isinstance(o, np.bool_) else float(o) if isinstance(o, (np.floating, np.integer)) else str(o))
    print(f"\n結果儲存至: {out_path}")

    print("\n注意事項:")
    print("  - ACB boundary 擴大須確認 McNemar 顯著 vs 現有 b5 才可採納")
    print("  - ZPI 若 z>1.96，可用於觸發 Zone補充注的警示（不直接修改策略）")
    print("  - ZPI 補充注策略需獨立 300期 Walk-Forward 驗證後才可納入生產")


if __name__ == '__main__':
    main()
