#!/usr/bin/env python3
"""
=============================================================================
539 5bet_fourier4_cold 標準回測
=============================================================================
測試問題：Fourier 500p 正交分注(4注) + Cold(w=100) 補注(1注)
         的 5注結構，以 M3+ 為主指標，是否有統計顯著 Edge？

回測協議：
  - Walk-forward（嚴格無數據洩漏）
  - 三窗口穩定性：150 / 500 / 1500 期
  - Permutation test（200 次，Bonferroni α/2=0.025）
  - Z-test vs 理論基線
  - Random 5-bet baseline 對照
  - M3+ 為主指標（同 5bet_fourier4_cold 策略定義）

Output: 結構化 JSON + 報告摘要
=============================================================================
"""

import sys
import os
import json
import random
import math
import time
import warnings
from collections import Counter
from datetime import datetime

import numpy as np
from scipy import stats as scipy_stats
from scipy.fft import fft, fftfreq

warnings.filterwarnings('ignore')

# ─── Project Setup ───────────────────────────────────────────────
_base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_base, '..', 'lottery_api'))
sys.path.insert(0, os.path.join(_base, '..'))
from database import DatabaseManager

# ─── Constants ───────────────────────────────────────────────────
MAX_NUM = 39
PICK = 5
N_BETS = 5
TOTAL_NUMBERS = list(range(1, MAX_NUM + 1))

# Theoretical baselines (hypergeometric)
from math import comb
C39_5 = comb(39, 5)  # 575757

def _p_match_exactly(k):
    return comb(5, k) * comb(34, 5 - k) / C39_5

P_MATCH = {k: _p_match_exactly(k) for k in range(6)}
P_GE2_1 = sum(P_MATCH[k] for k in range(2, 6))
P_GE3_1 = sum(P_MATCH[k] for k in range(3, 6))

# N-bet baselines (independent bets, any-hit)
P_GE2_5 = 1 - (1 - P_GE2_1) ** N_BETS
P_GE3_5 = 1 - (1 - P_GE3_1) ** N_BETS

print(f"[BASELINE] 5-bet M2+ = {P_GE2_5*100:.2f}%")
print(f"[BASELINE] 5-bet M3+ = {P_GE3_5*100:.2f}%   ← 主指標")
print(f"[BASELINE] 1-bet M3+ = {P_GE3_1*100:.3f}%")


# ═══════════════════════════════════════════════════════════════════
#  DATA
# ═══════════════════════════════════════════════════════════════════
def load_data():
    db_path = os.path.join(_base, '..', 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    raw = db.get_all_draws('DAILY_539')
    draws = sorted(raw, key=lambda x: (x['date'], x['draw']))
    print(f"[DATA] {len(draws)} draws: {draws[0]['date']} → {draws[-1]['date']}")
    return draws


def get_numbers(draw):
    nums = draw.get('numbers', [])
    if isinstance(nums, str):
        nums = json.loads(nums)
    return list(nums)


# ═══════════════════════════════════════════════════════════════════
#  STRATEGY: 5bet_fourier4_cold (exact replica from predict_539_5bet_f4cold.py)
# ═══════════════════════════════════════════════════════════════════
def fourier_scores(hist, window=500):
    """Fourier rhythm scores — identical to predict_539_5bet_f4cold.py"""
    h = hist[-window:] if len(hist) >= window else hist
    w = len(h)
    scores = {}
    for n in range(1, MAX_NUM + 1):
        bh = np.zeros(w)
        for idx, d in enumerate(h):
            if n in get_numbers(d):
                bh[idx] = 1
        if sum(bh) < 2:
            scores[n] = 0.0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        ip = np.where(xf > 0)
        py = np.abs(yf[ip])
        px = xf[ip]
        pk = np.argmax(py)
        fv = px[pk]
        if fv == 0:
            scores[n] = 0.0
            continue
        period = 1 / fv
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return scores


def predict_5bet(hist):
    """
    5bet_fourier4_cold 策略:
    注1-4: Fourier 500p 排名 top-20 正交切片 (rank 1-5 / 6-10 / 11-15 / 16-20)
    注5:   Cold(w=100) 排除前4注後，前5冷號
    """
    sc = fourier_scores(hist, 500)
    ranked = [n for n in sorted(sc, key=lambda x: -sc[x]) if sc[n] > 0]

    # 注1-4: 正交 partition
    bets = []
    for i in range(4):
        start = i * 5
        end = (i + 1) * 5
        if end <= len(ranked):
            bets.append(sorted(ranked[start:end]))
        else:
            # Fallback: if not enough scored numbers
            remaining = [n for n in TOTAL_NUMBERS if n not in sum(bets, [])]
            bets.append(sorted(remaining[:5]))

    excl = set(sum(bets, []))

    # 注5: Cold(w=100) orthogonal
    freq = Counter()
    for d in hist[-100:]:
        for n in get_numbers(d):
            freq[n] += 1
    cold_sorted = sorted(range(1, MAX_NUM + 1), key=lambda n: freq.get(n, 0))
    bet5 = sorted([n for n in cold_sorted if n not in excl][:5])
    bets.append(bet5)

    return bets


def predict_random_5bet(seed_val):
    """Random 5-bet baseline factory — 5注隨機不重疊"""
    def _predict(hist):
        rng = random.Random(seed_val)
        pool = list(TOTAL_NUMBERS)
        rng.shuffle(pool)
        return [sorted(pool[i*5:(i+1)*5]) for i in range(5)]
    return _predict


# ═══════════════════════════════════════════════════════════════════
#  BACKTEST ENGINE (Walk-Forward, Leakage-Free)
# ═══════════════════════════════════════════════════════════════════
def backtest_structured(predict_func, all_draws, test_periods=1500, seed=42):
    """
    Walk-forward backtest for structured multi-bet strategy.
    predict_func(hist) → list of N bets (each bet = list of 5 numbers)
    
    Returns M2+ and M3+ rates across N bets (any-hit).
    """
    random.seed(seed)
    np.random.seed(seed)

    min_train = 500  # Fourier 需要 500期 window
    results = []

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < min_train:
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]  # 嚴格 walk-forward
        actual = set(get_numbers(target))

        try:
            bets = predict_func(hist)
        except Exception as e:
            continue

        any_ge2 = False
        any_ge3 = False
        max_match = 0
        bet_details = []

        for bet in bets:
            matches = len(set(bet) & actual)
            max_match = max(max_match, matches)
            if matches >= 2:
                any_ge2 = True
            if matches >= 3:
                any_ge3 = True
            bet_details.append(matches)

        # Coverage analysis
        all_nums = set(sum([list(b) for b in bets], []))
        coverage = len(all_nums & actual)
        overlap_count = sum(len(bets[i]) for i in range(len(bets))) - len(all_nums)

        results.append({
            'idx': target_idx,
            'ge2': any_ge2,
            'ge3': any_ge3,
            'max_match': max_match,
            'bet_details': bet_details,
            'coverage': coverage,
            'overlap': overlap_count,
            'unique_nums': len(all_nums),
        })

    total = len(results)
    if total == 0:
        return {'total': 0, 'ge2_rate': 0, 'ge3_rate': 0}

    ge2_hits = sum(1 for r in results if r['ge2'])
    ge3_hits = sum(1 for r in results if r['ge3'])

    return {
        'total': total,
        'n_bets': N_BETS,
        'ge2_hits': ge2_hits,
        'ge3_hits': ge3_hits,
        'ge2_rate': ge2_hits / total,
        'ge3_rate': ge3_hits / total,
        'ge2_edge': ge2_hits / total - P_GE2_5,
        'ge3_edge': ge3_hits / total - P_GE3_5,
        'avg_max_match': np.mean([r['max_match'] for r in results]),
        'avg_coverage': np.mean([r['coverage'] for r in results]),
        'avg_unique_nums': np.mean([r['unique_nums'] for r in results]),
        'avg_overlap': np.mean([r['overlap'] for r in results]),
        'results': results,
    }


# ═══════════════════════════════════════════════════════════════════
#  VALIDATION FRAMEWORK
# ═══════════════════════════════════════════════════════════════════

def z_test(hits, total, baseline):
    """One-sided Z-test: H1 = rate > baseline."""
    rate = hits / total
    se = math.sqrt(baseline * (1 - baseline) / total)
    if se == 0:
        return {'z': 0, 'p': 1}
    z = (rate - baseline) / se
    p = 1 - scipy_stats.norm.cdf(z)
    return {'z': z, 'p': p, 'rate': rate, 'se': se}


def three_window_test(predict_func, all_draws, seed=42):
    """三窗口穩定性：150 / 500 / 1500 期"""
    results = {}
    for period in [150, 500, 1500]:
        if len(all_draws) < period + 500:
            print(f"  [SKIP] {period}p: 不夠數據 (need {period+500}, have {len(all_draws)})")
            continue
        r = backtest_structured(predict_func, all_draws, period, seed)
        z_ge3 = z_test(r['ge3_hits'], r['total'], P_GE3_5)
        z_ge2 = z_test(r['ge2_hits'], r['total'], P_GE2_5)
        results[period] = {
            **r,
            'z_ge3': z_ge3,
            'z_ge2': z_ge2,
        }
        # 不存 results 裡的大量 per-draw data
        del results[period]['results']
    return results


def permutation_test(predict_func, all_draws, test_periods=500, n_perms=200, seed=42):
    """
    Permutation test vs random 5-bet baseline.
    
    測試問題：predict_func 生成的 5注結構，M3+ 率是否顯著高於
    隨機抽出的 5注不重疊結構？
    
    Random baseline: 每次隨機洗牌 39 個號碼，切成 5 注 × 5 號。
    這比獨立隨機更嚴格，因為它也是零重疊結構。
    """
    print(f"  [PERM] actual backtest ({test_periods}p)...", end='', flush=True)
    actual = backtest_structured(predict_func, all_draws, test_periods, seed)
    actual_rate = actual['ge3_rate']
    print(f" M3+={actual_rate*100:.2f}%")

    perm_rates = []
    print(f"  [PERM] {n_perms} random shuffles...", end='', flush=True)
    for i in range(n_perms):
        rand_func = predict_random_5bet(seed_val=seed * 1000 + i)
        r = backtest_structured(rand_func, all_draws, test_periods, seed + i + 10000)
        perm_rates.append(r['ge3_rate'])
        if (i + 1) % 50 == 0:
            print(f" {i+1}", end='', flush=True)

    print()

    perm_mean = np.mean(perm_rates)
    perm_std = np.std(perm_rates, ddof=1) if len(perm_rates) > 1 else 1e-10
    if perm_std < 1e-10:
        perm_std = 1e-10

    z = (actual_rate - perm_mean) / perm_std
    p = (np.sum(np.array(perm_rates) >= actual_rate) + 1) / (n_perms + 1)  # empirical p-value

    cohen_d = (actual_rate - perm_mean) / perm_std if perm_std > 1e-10 else 0

    return {
        'actual_rate': actual_rate,
        'actual_hits': actual['ge3_hits'],
        'actual_total': actual['total'],
        'perm_mean': perm_mean,
        'perm_std': perm_std,
        'perm_min': float(np.min(perm_rates)),
        'perm_max': float(np.max(perm_rates)),
        'z_score': z,
        'p_value_empirical': p,
        'p_value_normal': float(1 - scipy_stats.norm.cdf(z)),
        'cohen_d': cohen_d,
        'n_perms': n_perms,
        'shuffle_mean_edge': perm_mean - P_GE3_5,  # 分布偏好
        'signal_edge': actual_rate - perm_mean,       # 純時序信號
        'total_edge': actual_rate - P_GE3_5,          # 總 Edge
    }


def mcnemar_vs_random(predict_func, all_draws, test_periods=500, seed=42):
    """McNemar's test: strategy 5-bet vs random 5-bet, per-draw paired comparison."""
    random.seed(seed)
    np.random.seed(seed)

    rand_func = predict_random_5bet(seed_val=seed + 99999)
    min_train = 500

    a = 0  # both hit
    b = 0  # strategy hit, random miss
    c = 0  # strategy miss, random hit
    d = 0  # both miss
    total = 0

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < min_train:
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(get_numbers(target))

        try:
            strat_bets = predict_func(hist)
            rand_bets = rand_func(hist)
        except:
            continue

        strat_hit = any(len(set(b) & actual) >= 3 for b in strat_bets)
        rand_hit = any(len(set(b) & actual) >= 3 for b in rand_bets)

        if strat_hit and rand_hit:
            a += 1
        elif strat_hit and not rand_hit:
            b += 1
        elif not strat_hit and rand_hit:
            c += 1
        else:
            d += 1
        total += 1

    # McNemar's test
    if b + c > 0:
        chi2 = (abs(b - c) - 1) ** 2 / (b + c)  # continuity correction
        p = 1 - scipy_stats.chi2.cdf(chi2, 1)
    else:
        chi2 = 0
        p = 1.0

    return {
        'total': total,
        'both_hit': a,
        'strat_only': b,
        'rand_only': c,
        'both_miss': d,
        'net_improvement': b - c,
        'chi2': chi2,
        'p_value': p,
        'significant': p < 0.05,
    }


# ═══════════════════════════════════════════════════════════════════
#  ADDITIONAL STRATEGIES TO COMPARE
# ═══════════════════════════════════════════════════════════════════

def predict_fourier_only_5bet(hist):
    """Fourier-only 5bet: 全部用 Fourier 排名，無 Cold 補注"""
    sc = fourier_scores(hist, 500)
    ranked = [n for n in sorted(sc, key=lambda x: -sc[x]) if sc[n] > 0]
    bets = []
    for i in range(5):
        start = i * 5
        end = (i + 1) * 5
        if end <= len(ranked):
            bets.append(sorted(ranked[start:end]))
        else:
            remaining = [n for n in TOTAL_NUMBERS if n not in sum(bets, [])]
            bets.append(sorted(remaining[:5]))
    return bets


def predict_cold_dominant_5bet(hist):
    """Cold-dominant 5bet: 全部用 Cold 排名"""
    freq = Counter()
    for d in hist[-200:]:
        for n in get_numbers(d):
            freq[n] += 1

    cold_sorted = sorted(range(1, MAX_NUM + 1), key=lambda n: freq.get(n, 0))
    bets = [sorted(cold_sorted[i*5:(i+1)*5]) for i in range(5)]
    return bets


def predict_hot_5bet(hist):
    """Hot 5bet: 全部用 Hot 排名"""
    freq = Counter()
    for d in hist[-200:]:
        for n in get_numbers(d):
            freq[n] += 1

    hot_sorted = sorted(range(1, MAX_NUM + 1), key=lambda n: freq.get(n, 0), reverse=True)
    bets = [sorted(hot_sorted[i*5:(i+1)*5]) for i in range(5)]
    return bets


def predict_mixed_signal_5bet(hist):
    """Mixed: Fourier(2注) + Gap(1注) + Hot(1注) + Cold(1注)"""
    sc = fourier_scores(hist, 500)
    ranked = [n for n in sorted(sc, key=lambda x: -sc[x]) if sc[n] > 0]

    bet1 = sorted(ranked[:5]) if len(ranked) >= 5 else sorted(TOTAL_NUMBERS[:5])
    bet2 = sorted(ranked[5:10]) if len(ranked) >= 10 else sorted(TOTAL_NUMBERS[5:10])
    used = set(bet1 + bet2)

    # Gap-based
    last_seen = {}
    for i, d in enumerate(hist):
        for n in get_numbers(d):
            last_seen[n] = i
    gap_scores = {n: len(hist) - last_seen.get(n, 0) for n in TOTAL_NUMBERS if n not in used}
    gap_ranked = sorted(gap_scores, key=gap_scores.get, reverse=True)
    bet3 = sorted(gap_ranked[:5])
    used.update(bet3)

    # Hot
    freq = Counter()
    for d in hist[-100:]:
        for n in get_numbers(d):
            freq[n] += 1
    hot = sorted([n for n in TOTAL_NUMBERS if n not in used], key=lambda n: freq.get(n, 0), reverse=True)
    bet4 = sorted(hot[:5])
    used.update(bet4)

    # Cold
    cold = sorted([n for n in TOTAL_NUMBERS if n not in used], key=lambda n: freq.get(n, 0))
    bet5 = sorted(cold[:5])

    return [bet1, bet2, bet3, bet4, bet5]


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    total_start = time.time()
    print("=" * 70)
    print("  539 5bet_fourier4_cold 標準回測")
    print("  M3+ 為主指標 | Walk-Forward | 三窗口 | Permutation Test")
    print("=" * 70)

    all_draws = load_data()

    STRATEGIES = {
        '5bet_fourier4_cold': predict_5bet,
        'fourier_only_5bet': predict_fourier_only_5bet,
        'cold_dominant_5bet': predict_cold_dominant_5bet,
        'hot_5bet': predict_hot_5bet,
        'mixed_signal_5bet': predict_mixed_signal_5bet,
    }

    all_results = {}

    # ── Phase 1: 三窗口穩定性 (全策略) ──
    print(f"\n{'='*70}")
    print(f"  PHASE 1: THREE-WINDOW STABILITY TEST (all strategies)")
    print(f"{'='*70}")

    for name, func in STRATEGIES.items():
        print(f"\n  ▸ {name}")
        tw = three_window_test(func, all_draws, seed=42)

        all_results[name] = {'three_window': tw}

        for period in [150, 500, 1500]:
            if period in tw:
                r = tw[period]
                print(f"    {period}p: M3+={r['ge3_rate']*100:.2f}% (edge={r['ge3_edge']*100:+.2f}%) "
                      f"z={r['z_ge3']['z']:.2f} p={r['z_ge3']['p']:.4f} | "
                      f"M2+={r['ge2_rate']*100:.2f}% (edge={r['ge2_edge']*100:+.2f}%) | "
                      f"cov={r['avg_unique_nums']:.1f}/{MAX_NUM} ovlp={r['avg_overlap']:.1f}")

        # Stability classification
        edges = {p: r['ge3_edge'] for p, r in tw.items()}
        if all(e > 0 for e in edges.values()):
            stability = 'STABLE'
        elif edges.get(1500, {}) and edges[1500] > 0 and edges.get(150, 0) <= 0:
            stability = 'LATE_BLOOMER'
        elif all(e <= 0 for e in edges.values()):
            stability = 'INEFFECTIVE'
        else:
            stability = 'MIXED'

        all_results[name]['stability'] = stability
        all_results[name]['edges'] = edges
        print(f"    → Stability: {stability}")

    # ── Phase 2: Permutation Test (top strategies) ──
    print(f"\n{'='*70}")
    print(f"  PHASE 2: PERMUTATION TEST (M3+ focus, 200 shuffles)")
    print(f"{'='*70}")

    # Only test strategies with positive 1500p edge
    perm_candidates = [name for name, r in all_results.items()
                        if r.get('edges', {}).get(1500, -1) > 0]

    if not perm_candidates:
        print("  [WARN] No strategy has positive 1500p M3+ edge. Testing top 2 anyway.")
        perm_candidates = sorted(all_results.keys(),
                                  key=lambda n: all_results[n].get('edges', {}).get(1500, -999),
                                  reverse=True)[:2]

    for name in perm_candidates:
        print(f"\n  ▸ Permutation test: {name}")
        perm = permutation_test(STRATEGIES[name], all_draws, test_periods=500, n_perms=200, seed=42)
        all_results[name]['permutation'] = perm

        print(f"    Actual M3+:     {perm['actual_rate']*100:.2f}%")
        print(f"    Shuffle mean:   {perm['perm_mean']*100:.2f}% (edge={perm['shuffle_mean_edge']*100:+.3f}%)")
        print(f"    Signal Edge:    {perm['signal_edge']*100:+.3f}%")
        print(f"    Total Edge:     {perm['total_edge']*100:+.3f}%")
        print(f"    z={perm['z_score']:.2f}, p(empirical)={perm['p_value_empirical']:.4f}, "
              f"p(normal)={perm['p_value_normal']:.4f}")
        print(f"    Cohen's d:      {perm['cohen_d']:.2f}")
        sig = perm['p_value_empirical'] < 0.05
        bonf = perm['p_value_empirical'] < 0.025  # Bonferroni/2
        print(f"    p<0.05: {'✓ SIGNAL' if sig else '✗ NO SIGNAL'}")
        print(f"    p<0.025 (Bonf/2): {'✓ PASS' if bonf else '✗ FAIL'}")

    # ── Phase 3: McNemar Test (策略 vs Random 5-bet) ──
    print(f"\n{'='*70}")
    print(f"  PHASE 3: MCNEMAR TEST (strategy vs random 5-bet)")
    print(f"{'='*70}")

    for name in perm_candidates:
        print(f"\n  ▸ McNemar: {name}")
        mc = mcnemar_vs_random(STRATEGIES[name], all_draws, test_periods=500, seed=42)
        all_results[name]['mcnemar'] = mc
        print(f"    Both hit: {mc['both_hit']} | Strat only: {mc['strat_only']} | Rand only: {mc['rand_only']} | Both miss: {mc['both_miss']}")
        print(f"    Net improvement: {mc['net_improvement']}")
        print(f"    χ²={mc['chi2']:.3f}, p={mc['p_value']:.4f} {'✓ SIGNIFICANT' if mc['significant'] else '✗'}")

    # ── Phase 4: Random Baseline Calibration ──
    print(f"\n{'='*70}")
    print(f"  PHASE 4: RANDOM 5-BET BASELINE CALIBRATION")
    print(f"{'='*70}")

    print("  Running 20 random seeds to calibrate baseline scatter...")
    rand_rates_m3 = []
    rand_rates_m2 = []
    for s in range(20):
        rand_func = predict_random_5bet(seed_val=s * 777)
        r = backtest_structured(rand_func, all_draws, 1500, seed=s + 50000)
        rand_rates_m3.append(r['ge3_rate'])
        rand_rates_m2.append(r['ge2_rate'])

    print(f"  Random M3+ mean={np.mean(rand_rates_m3)*100:.2f}% ± {np.std(rand_rates_m3)*100:.2f}%")
    print(f"           range=[{np.min(rand_rates_m3)*100:.2f}%, {np.max(rand_rates_m3)*100:.2f}%]")
    print(f"  Random M2+ mean={np.mean(rand_rates_m2)*100:.2f}% ± {np.std(rand_rates_m2)*100:.2f}%")
    print(f"  Theoretical M3+ 5-bet: {P_GE3_5*100:.2f}%")
    print(f"  Theoretical M2+ 5-bet: {P_GE2_5*100:.2f}%")

    # ── Phase 5: Summary ──
    elapsed = time.time() - total_start
    print(f"\n{'='*70}")
    print(f"  SUMMARY REPORT")
    print(f"{'='*70}")
    print(f"\n  ┌─ Strategy Comparison (M3+ focus, 1500p window) ─┐")
    print(f"  {'Name':<25} {'M3+%':>7} {'Edge%':>8} {'z':>6} {'Stab':<15}")
    print(f"  {'─'*62}")

    for name in STRATEGIES:
        r = all_results[name]
        tw1500 = r.get('three_window', {}).get(1500, {})
        m3r = tw1500.get('ge3_rate', 0) * 100
        m3e = tw1500.get('ge3_edge', 0) * 100
        z = tw1500.get('z_ge3', {}).get('z', 0)
        stab = r.get('stability', '?')
        print(f"  {name:<25} {m3r:>6.2f}% {m3e:>+7.2f}% {z:>5.2f}  {stab}")

    print(f"  {'─'*62}")
    print(f"  {'RANDOM BASELINE':<25} {np.mean(rand_rates_m3)*100:>6.2f}% {(np.mean(rand_rates_m3)-P_GE3_5)*100:>+7.2f}% {'':>5}  REFERENCE")
    print(f"  {'THEORETICAL':<25} {P_GE3_5*100:>6.2f}% {0:>+7.2f}%")
    print()

    # Highlight main strategy
    main = all_results.get('5bet_fourier4_cold', {})
    tw1500 = main.get('three_window', {}).get(1500, {})
    perm = main.get('permutation', {})
    mc = main.get('mcnemar', {})

    print(f"  ★ 5bet_fourier4_cold 綜合結論:")
    print(f"    1500p M3+ = {tw1500.get('ge3_rate', 0)*100:.2f}%  (edge = {tw1500.get('ge3_edge', 0)*100:+.2f}%)")
    print(f"    z-score = {tw1500.get('z_ge3', {}).get('z', 0):.2f},  p = {tw1500.get('z_ge3', {}).get('p', 1):.4f}")
    print(f"    Stability: {main.get('stability', '?')}")
    if perm:
        print(f"    Permutation: z={perm.get('z_score', 0):.2f}, p(emp)={perm.get('p_value_empirical', 1):.4f}, Cohen's d={perm.get('cohen_d', 0):.2f}")
        print(f"    Shuffle mean edge: {perm.get('shuffle_mean_edge', 0)*100:+.3f}%")
        print(f"    Signal edge:       {perm.get('signal_edge', 0)*100:+.3f}%")
        bonf = perm.get('p_value_empirical', 1) < 0.025
        print(f"    Bonferroni/2 (p<0.025): {'✓ PASS → VERIFIED' if bonf else '✗ FAIL → PROVISIONAL'}")
    if mc:
        print(f"    McNemar vs random: χ²={mc.get('chi2', 0):.3f}, p={mc.get('p_value', 1):.4f} "
              f"{'✓ SIGNIFICANT' if mc.get('significant') else '✗'}")

    print(f"\n  Total runtime: {elapsed:.1f}s")
    print("=" * 70)

    # ── Save results ──
    json_path = os.path.join(_base, '..', 'backtest_539_5bet_results.json')

    def make_serializable(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {str(k): make_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [make_serializable(i) for i in obj]
        return obj

    save_data = {
        'generated': datetime.now().isoformat(),
        'strategy_under_test': '5bet_fourier4_cold',
        'metric': 'M3+ (match≥3, any of 5 bets)',
        'baselines': {
            '5bet_M2+': P_GE2_5,
            '5bet_M3+': P_GE3_5,
            '1bet_M3+': P_GE3_1,
            'random_empirical_M3+_mean': float(np.mean(rand_rates_m3)),
            'random_empirical_M3+_std': float(np.std(rand_rates_m3)),
        },
        'results': {name: {k: v for k, v in r.items() if k != 'three_window' or True}
                    for name, r in all_results.items()},
        'random_calibration': {
            'm3_rates': [float(x) for x in rand_rates_m3],
            'm2_rates': [float(x) for x in rand_rates_m2],
        }
    }

    # Strip per-draw results from three_window to reduce size
    for name in save_data['results']:
        tw = save_data['results'][name].get('three_window', {})
        for period_key in tw:
            if 'results' in tw[period_key]:
                del tw[period_key]['results']

    with open(json_path, 'w') as f:
        json.dump(make_serializable(save_data), f, indent=2, ensure_ascii=False)
    print(f"\n[SAVED] {json_path}")


if __name__ == '__main__':
    main()
