#!/usr/bin/env python3
"""
=============================================================================
539 P0-B: 3注 F500Top5 + Cold100Top5 + Fmid21-25 回測
=============================================================================
測試問題：
  注1: Fourier 500p rank 1-5 (主要週期信號)
  注2: Cold 近100期前5，排除注1 (逾期冷號)
  注3: Fourier 500p rank 21-25，排除注1+2 (修補rank盲區)

研究背景 (115000051期檢討):
  開獎 [3,6,9,31,39] — #31 是 F rank 22 的結構性盲區
  現有5注架構 rank 1-20 + Cold，rank 21-25 完全無覆蓋
  本3注設計以更低成本 NT$150 vs NT$250 探索是否有足夠 Edge

採納標準 (依 CLAUDE.md 驗證標準):
  - 三窗口全正 (150/500/1500p Edge > 0)
  - Permutation test p ≤ 0.05 (SIGNAL_DETECTED)
  - 零重疊 (unique nums = 15)
  - M2+ 為主指標 (3注)

Output: backtest_539_3bet_f_cold_fmid_results.json
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
N_BETS = 3
TOTAL_NUMBERS = list(range(1, MAX_NUM + 1))
SEED = 42

# Theoretical baselines (hypergeometric)
from math import comb
C39_5 = comb(39, 5)  # 575757

def _p_match_exactly(k):
    return comb(5, k) * comb(34, 5 - k) / C39_5

P_MATCH = {k: _p_match_exactly(k) for k in range(6)}
P_GE2_1 = sum(P_MATCH[k] for k in range(2, 6))
P_GE3_1 = sum(P_MATCH[k] for k in range(3, 6))

# 3-bet baselines
P_GE2_3 = 1 - (1 - P_GE2_1) ** N_BETS
P_GE3_3 = 1 - (1 - P_GE3_1) ** N_BETS

# 5-bet baselines (for McNemar comparison)
P_GE3_5 = 1 - (1 - P_GE3_1) ** 5

print(f"[BASELINE] 3-bet M2+ = {P_GE2_3*100:.2f}%  ← 主指標")
print(f"[BASELINE] 3-bet M3+ = {P_GE3_3*100:.3f}%")
print(f"[BASELINE] 5-bet M3+ = {P_GE3_5*100:.2f}%  (對照組)")
print(f"[BASELINE] 1-bet M2+ = {P_GE2_1*100:.2f}%")


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
#  SIGNAL FUNCTIONS
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
        last_hit_arr = np.where(bh == 1)[0]
        if len(last_hit_arr) == 0:
            scores[n] = 0.0
            continue
        last_hit = last_hit_arr[-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return scores


def cold_scores(hist, window=100):
    """近100期冷號分數 (出現次數越少分越高)"""
    freq = Counter()
    for d in hist[-window:]:
        for n in get_numbers(d):
            freq[n] += 1
    return freq  # 升序=冷


# ═══════════════════════════════════════════════════════════════════
#  STRATEGIES
# ═══════════════════════════════════════════════════════════════════

def predict_3bet_f_cold_fmid(hist):
    """
    P0-B 3注策略: F500Top5 + Cold100Top5 + Fmid21-25

    注1: Fourier 500p rank 1-5 (最強週期信號)
    注2: Cold 近100期前5，排除注1 (逾期冷號，均值回歸)
    注3: Fourier 500p rank 21-25，排除前2注 (中間帶盲區覆蓋)

    設計目標:
    - 零重疊 (15 unique nums)
    - 覆蓋 Fourier Top 信號 + 冷號信號 + Fourier 中間帶
    - NT$150 成本 (vs 5注 NT$250)
    """
    # Fourier 排名
    sc = fourier_scores(hist, 500)
    ranked = [n for n in sorted(sc, key=lambda x: -sc[x]) if sc[n] > 0]
    # 補足不夠時用 fallback
    if len(ranked) < 25:
        missing = [n for n in TOTAL_NUMBERS if n not in ranked]
        ranked.extend(missing)

    # 注1: F rank 1-5
    bet1 = sorted(ranked[:5])
    excl = set(bet1)

    # 注2: Cold 100p 前5，排除注1
    freq = cold_scores(hist, 100)
    cold_sorted = sorted(TOTAL_NUMBERS, key=lambda n: freq.get(n, 0))
    bet2 = sorted([n for n in cold_sorted if n not in excl][:5])
    excl.update(bet2)

    # 注3: F rank 21-25，排除前2注
    # 從 rank 20 開始往後取，跳過已用號碼，直到取滿5個
    bet3_pool = [n for n in ranked[20:] if n not in excl]
    bet3 = sorted(bet3_pool[:5])

    # 邊界保護：若不足5個，用剩餘號碼補足
    if len(bet3) < 5:
        remaining = [n for n in TOTAL_NUMBERS if n not in excl and n not in bet3]
        bet3 = sorted((bet3 + remaining)[:5])

    return [bet1, bet2, bet3]


def predict_3bet_f_only(hist):
    """對照組A: 純Fourier 3注 (rank 1-5, 6-10, 11-15)"""
    sc = fourier_scores(hist, 500)
    ranked = [n for n in sorted(sc, key=lambda x: -sc[x]) if sc[n] > 0]
    if len(ranked) < 15:
        missing = [n for n in TOTAL_NUMBERS if n not in ranked]
        ranked.extend(missing)
    return [sorted(ranked[0:5]), sorted(ranked[5:10]), sorted(ranked[10:15])]


def predict_3bet_f_cold_only(hist):
    """對照組B: F500Top5 + Cold Top5 + Cold Top5第二組 (不含Fmid)"""
    sc = fourier_scores(hist, 500)
    ranked = [n for n in sorted(sc, key=lambda x: -sc[x]) if sc[n] > 0]
    if len(ranked) < 5:
        missing = [n for n in TOTAL_NUMBERS if n not in ranked]
        ranked.extend(missing)

    bet1 = sorted(ranked[:5])
    excl = set(bet1)

    freq = cold_scores(hist, 100)
    cold_sorted = sorted(TOTAL_NUMBERS, key=lambda n: freq.get(n, 0))

    bet2 = sorted([n for n in cold_sorted if n not in excl][:5])
    excl.update(bet2)

    bet3 = sorted([n for n in cold_sorted if n not in excl][:5])

    return [bet1, bet2, bet3]


def predict_5bet_f4cold(hist):
    """現有5注策略 (用於 McNemar 對照)"""
    sc = fourier_scores(hist, 500)
    ranked = [n for n in sorted(sc, key=lambda x: -sc[x]) if sc[n] > 0]
    if len(ranked) < 20:
        missing = [n for n in TOTAL_NUMBERS if n not in ranked]
        ranked.extend(missing)

    bets = [sorted(ranked[i*5:(i+1)*5]) for i in range(4)]
    excl = set(sum(bets, []))

    freq = cold_scores(hist, 100)
    cold_sorted = sorted(TOTAL_NUMBERS, key=lambda n: freq.get(n, 0))
    bet5 = sorted([n for n in cold_sorted if n not in excl][:5])
    bets.append(bet5)
    return bets


def predict_random_3bet(seed_val):
    """Random 3-bet baseline — 3注隨機不重疊 (15 unique nums)"""
    def _predict(hist):
        rng = random.Random(seed_val)
        pool = list(TOTAL_NUMBERS)
        rng.shuffle(pool)
        return [sorted(pool[i*5:(i+1)*5]) for i in range(3)]
    return _predict


# ═══════════════════════════════════════════════════════════════════
#  BACKTEST ENGINE (Walk-Forward, Leakage-Free)
# ═══════════════════════════════════════════════════════════════════
def backtest_structured(predict_func, all_draws, test_periods=1500, seed=42, min_train=500):
    """
    Walk-forward backtest for structured multi-bet strategy.
    Returns M2+ and M3+ rates across N bets (any-hit).
    """
    random.seed(seed)
    np.random.seed(seed)

    results = []

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < min_train:
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]   # 嚴格 walk-forward
        actual = set(get_numbers(target))

        try:
            bets = predict_func(hist)
        except Exception:
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

        all_nums = set(sum([list(b) for b in bets], []))
        coverage = len(all_nums & actual)
        overlap_count = sum(len(b) for b in bets) - len(all_nums)

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
        return {'total': 0, 'ge2_rate': 0, 'ge3_rate': 0, 'ge2_hits': 0, 'ge3_hits': 0,
                'ge2_edge': 0, 'ge3_edge': 0, 'avg_unique_nums': 0, 'avg_overlap': 0,
                'avg_coverage': 0, 'results': []}

    ge2_hits = sum(1 for r in results if r['ge2'])
    ge3_hits = sum(1 for r in results if r['ge3'])

    return {
        'total': total,
        'n_bets': N_BETS,
        'ge2_hits': ge2_hits,
        'ge3_hits': ge3_hits,
        'ge2_rate': ge2_hits / total,
        'ge3_rate': ge3_hits / total,
        'ge2_edge': ge2_hits / total - P_GE2_3,
        'ge3_edge': ge3_hits / total - P_GE3_3,
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
        return {'z': 0, 'p': 1.0, 'rate': rate, 'se': 0}
    z = (rate - baseline) / se
    p = 1 - scipy_stats.norm.cdf(z)
    return {'z': z, 'p': p, 'rate': rate, 'se': se}


def three_window_test(predict_func, all_draws, seed=42, min_train=500):
    """三窗口穩定性：150 / 500 / 1500 期"""
    results = {}
    for period in [150, 500, 1500]:
        if len(all_draws) < period + min_train:
            print(f"  [SKIP] {period}p: 不夠數據 (need {period+min_train}, have {len(all_draws)})")
            continue
        r = backtest_structured(predict_func, all_draws, period, seed, min_train)
        z_ge2 = z_test(r['ge2_hits'], r['total'], P_GE2_3)
        z_ge3 = z_test(r['ge3_hits'], r['total'], P_GE3_3)
        results[period] = {
            'total': r['total'],
            'ge2_hits': r['ge2_hits'],
            'ge2_rate': r['ge2_rate'],
            'ge2_edge': r['ge2_edge'],
            'ge3_hits': r['ge3_hits'],
            'ge3_rate': r['ge3_rate'],
            'ge3_edge': r['ge3_edge'],
            'z_ge2': z_ge2,
            'z_ge3': z_ge3,
            'avg_unique_nums': r['avg_unique_nums'],
            'avg_overlap': r['avg_overlap'],
            'avg_coverage': r['avg_coverage'],
        }
    return results


def permutation_test(predict_func, all_draws, test_periods=500, n_perms=200, seed=42, min_train=500):
    """
    Permutation test vs random 3-bet (15 unique / 非重疊) baseline.
    主指標: M2+
    """
    print(f"  [PERM] actual backtest ({test_periods}p)...", end='', flush=True)
    actual = backtest_structured(predict_func, all_draws, test_periods, seed, min_train)
    actual_rate = actual['ge2_rate']
    print(f" M2+={actual_rate*100:.2f}%")

    perm_rates = []
    print(f"  [PERM] {n_perms} random shuffles...", end='', flush=True)
    for i in range(n_perms):
        rand_func = predict_random_3bet(seed_val=seed * 1000 + i)
        r = backtest_structured(rand_func, all_draws, test_periods, seed + i + 10000, min_train)
        perm_rates.append(r['ge2_rate'])
        if (i + 1) % 50 == 0:
            print(f" {i+1}", end='', flush=True)

    print()

    perm_mean = np.mean(perm_rates)
    perm_std = np.std(perm_rates, ddof=1) if len(perm_rates) > 1 else 1e-10
    if perm_std < 1e-10:
        perm_std = 1e-10

    z = (actual_rate - perm_mean) / perm_std
    p = (np.sum(np.array(perm_rates) >= actual_rate) + 1) / (n_perms + 1)

    cohen_d = (actual_rate - perm_mean) / perm_std

    return {
        'actual_rate': actual_rate,
        'actual_hits': actual['ge2_hits'],
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
        'shuffle_mean_edge': perm_mean - P_GE2_3,
        'signal_edge': actual_rate - perm_mean,
        'total_edge': actual_rate - P_GE2_3,
    }


def mcnemar_3bet_vs_5bet(all_draws, test_periods=500, seed=42, min_train=500):
    """
    McNemar's test: 3注 F+Cold+Fmid vs 5注 F4+Cold
    3注用 M2+；5注用 M3+（各自的主指標）
    """
    random.seed(seed)
    np.random.seed(seed)

    a = 0; b = 0; c = 0; d = 0
    total = 0
    hit3_list = []
    hit5_list = []

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < min_train:
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(get_numbers(target))

        try:
            bets3 = predict_3bet_f_cold_fmid(hist)
            bets5 = predict_5bet_f4cold(hist)
        except Exception:
            continue

        hit3 = any(len(set(b) & actual) >= 2 for b in bets3)  # 3注主指標 M2+
        hit5 = any(len(set(b) & actual) >= 3 for b in bets5)  # 5注主指標 M3+
        hit3_list.append(hit3)
        hit5_list.append(hit5)

        if hit3 and hit5:
            a += 1
        elif hit3 and not hit5:
            b += 1
        elif not hit3 and hit5:
            c += 1
        else:
            d += 1
        total += 1

    if b + c > 0:
        chi2 = (abs(b - c) - 1) ** 2 / (b + c)
        p = 1 - scipy_stats.chi2.cdf(chi2, 1)
    else:
        chi2 = 0; p = 1.0

    rate3 = sum(hit3_list) / len(hit3_list) if hit3_list else 0
    rate5 = sum(hit5_list) / len(hit5_list) if hit5_list else 0

    return {
        'total': total,
        'both_hit': a, 'bet3_only': b, 'bet5_only': c, 'both_miss': d,
        'bet3_M2_rate': rate3,
        'bet5_M3_rate': rate5,
        'net_advantage': b - c,
        'chi2': chi2, 'p_value': p,
        'significant': p < 0.05,
        'note': '3注M2+ vs 5注M3+ (各注各自主指標)',
    }


def mcnemar_3bet_vs_3bet(func_a, func_b, label_a, label_b, all_draws, test_periods=500, seed=42, min_train=500):
    """通用3注 McNemar: 兩策略 M2+ 直接對比"""
    a = 0; b = 0; c = 0; d = 0; total = 0

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < min_train:
            continue
        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(get_numbers(target))
        try:
            bets_a = func_a(hist)
            bets_b = func_b(hist)
        except Exception:
            continue

        hit_a = any(len(set(b) & actual) >= 2 for b in bets_a)
        hit_b = any(len(set(b) & actual) >= 2 for b in bets_b)

        if hit_a and hit_b: a += 1
        elif hit_a and not hit_b: b += 1
        elif not hit_a and hit_b: c += 1
        else: d += 1
        total += 1

    if b + c > 0:
        chi2 = (abs(b - c) - 1) ** 2 / (b + c)
        p = 1 - scipy_stats.chi2.cdf(chi2, 1)
    else:
        chi2 = 0; p = 1.0

    return {
        'label_a': label_a, 'label_b': label_b,
        'total': total, 'both_hit': a, 'a_only': b, 'b_only': c, 'both_miss': d,
        'rate_a': (a + b) / total if total else 0,
        'rate_b': (a + c) / total if total else 0,
        'net_advantage_a': b - c, 'chi2': chi2, 'p_value': p, 'significant': p < 0.05,
    }


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    t0 = time.time()
    print("=" * 70)
    print("  539 P0-B: 3注 F500Top5 + Cold100Top5 + Fmid21-25 回測")
    print("  研究背景: 115000051期 #31 F_rank22 結構性盲區修補")
    print("  M2+ 為主指標 | Walk-Forward | 三窗口 | Permutation Test")
    print("=" * 70)

    all_draws = load_data()
    MIN_TRAIN = 500

    report = {
        'timestamp': datetime.now().isoformat(),
        'strategy': 'F500Top5 + Cold100Top5_ortho + Fmid_rank21-25_ortho',
        'research_context': '115000051期 #31(Fmid rank22)結構性盲區',
        'n_bets': N_BETS,
        'baselines': {
            'M2+_3bet': P_GE2_3,
            'M3+_3bet': P_GE3_3,
            'M3+_5bet': P_GE3_5,
            'M2+_1bet': P_GE2_1,
        },
        'data_size': len(all_draws),
    }

    # ── 0. 零重疊驗證 ─────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("  [0] SANITY CHECK — 零重疊驗證")
    print(f"{'='*70}")
    overlap_checks = []
    for i in range(10):
        idx = len(all_draws) - 11 + i
        hist = all_draws[:idx]
        bets = predict_3bet_f_cold_fmid(hist)
        all_nums = set(sum([list(b) for b in bets], []))
        unique_count = len(all_nums)
        overlap = sum(len(b) for b in bets) - unique_count
        overlap_checks.append({'unique': unique_count, 'overlap': overlap})
        print(f"  Draw {idx}: bets={[sorted(b) for b in bets]}  unique={unique_count}  overlap={overlap}")

    avg_unique = np.mean([c['unique'] for c in overlap_checks])
    avg_overlap = np.mean([c['overlap'] for c in overlap_checks])
    print(f"\n  平均: unique={avg_unique:.1f}  overlap={avg_overlap:.1f}")
    if avg_overlap > 0:
        print("  ⚠️  WARNING: 非零重疊！")
    else:
        print("  ✅ 零重疊確認 — 每次預測 15 個唯一號碼")
    report['sanity_check'] = {
        'avg_unique': float(avg_unique),
        'avg_overlap': float(avg_overlap),
        'zero_overlap': bool(avg_overlap == 0),
    }

    # ── 1. 三窗口穩定性 (所有策略) ──────────────────────────────
    STRATEGIES = {
        '3bet_F_Cold_Fmid': predict_3bet_f_cold_fmid,      # 主策略
        '3bet_F_only':       predict_3bet_f_only,           # 對照A
        '3bet_F_Cold_only':  predict_3bet_f_cold_only,      # 對照B
    }

    print(f"\n{'='*70}")
    print("  [1] THREE-WINDOW STABILITY TEST (M2+ 主指標)")
    print(f"{'='*70}")

    all_tw_results = {}
    for name, func in STRATEGIES.items():
        print(f"\n  ▸ {name}")
        tw = three_window_test(func, all_draws, seed=SEED, min_train=MIN_TRAIN)
        all_tw_results[name] = tw

        for period in [150, 500, 1500]:
            if period in tw:
                r = tw[period]
                print(f"    {period}p: M2+={r['ge2_rate']*100:.2f}% (edge={r['ge2_edge']*100:+.2f}%) "
                      f"z={r['z_ge2']['z']:.2f} p={r['z_ge2']['p']:.4f} | "
                      f"M3+={r['ge3_rate']*100:.2f}% (edge={r['ge3_edge']*100:+.2f}%) | "
                      f"cov_avg={r['avg_coverage']:.2f} unique={r['avg_unique_nums']:.1f}")

        edges_m2 = {p: tw[p]['ge2_edge'] for p in tw}
        if all(e > 0 for e in edges_m2.values()):
            stability = 'STABLE_ALL_POSITIVE'
        elif edges_m2.get(1500, -1) > 0 and edges_m2.get(150, 0) <= 0:
            stability = 'LATE_BLOOMER'
        elif all(e <= 0 for e in edges_m2.values()):
            stability = 'INEFFECTIVE'
        else:
            stability = 'MIXED'
        print(f"    → M2+ 穩定性: {stability}")
        all_tw_results[name]['_stability'] = stability

    report['three_window'] = {}
    for name, tw in all_tw_results.items():
        report['three_window'][name] = {
            str(p): {k: v for k, v in data.items() if k not in ['z_ge2', 'z_ge3']
                     and not isinstance(v, list)}
            for p, data in tw.items() if isinstance(p, int)
        }

    # ── 2. Permutation Test ──────────────────────────────────────
    print(f"\n{'='*70}")
    print("  [2] PERMUTATION TEST (主策略 vs random 3-bet, M2+, 200次)")
    print(f"{'='*70}")

    perm = permutation_test(predict_3bet_f_cold_fmid, all_draws,
                            test_periods=500, n_perms=200, seed=SEED, min_train=MIN_TRAIN)
    report['permutation_test'] = perm

    print(f"\n  主策略 3bet_F_Cold_Fmid:")
    print(f"  Actual M2+:     {perm['actual_rate']*100:.2f}%  ({perm['actual_hits']}/{perm['actual_total']})")
    print(f"  Shuffle mean:   {perm['perm_mean']*100:.2f}% ± {perm['perm_std']*100:.3f}%")
    print(f"  Shuffle range:  [{perm['perm_min']*100:.2f}%, {perm['perm_max']*100:.2f}%]")
    print(f"  Signal Edge:    {perm['signal_edge']*100:+.3f}%")
    print(f"  Total Edge:     {perm['total_edge']*100:+.3f}%")
    print(f"  Shuffle bias:   {perm['shuffle_mean_edge']*100:+.3f}% (分布偏好)")
    print(f"  z={perm['z_score']:.2f},  p(empirical)={perm['p_value_empirical']:.4f},  "
          f"p(normal)={perm['p_value_normal']:.4f}")
    print(f"  Cohen's d:      {perm['cohen_d']:.2f}")
    sig = perm['p_value_empirical'] <= 0.05
    bonf = perm['p_value_empirical'] <= 0.025
    print(f"  p≤0.05:  {'✅ SIGNAL_DETECTED' if sig else '❌ NO_SIGNAL'}")
    print(f"  p≤0.025: {'✅ BONF_PASS' if bonf else '❌ BONF_FAIL'}")

    # ── 3. McNemar 3bet vs 5bet ──────────────────────────────────
    print(f"\n{'='*70}")
    print("  [3] McNEMAR: 3注 vs 5注 (各注自主指標)")
    print(f"{'='*70}")

    mc_5bet = mcnemar_3bet_vs_5bet(all_draws, test_periods=500, seed=SEED, min_train=MIN_TRAIN)
    report['mcnemar_vs_5bet'] = mc_5bet
    print(f"  3注 M2+ rate: {mc_5bet['bet3_M2_rate']*100:.2f}%")
    print(f"  5注 M3+ rate: {mc_5bet['bet5_M3_rate']*100:.2f}%")
    print(f"  3注獨贏: {mc_5bet['bet3_only']}  5注獨贏: {mc_5bet['bet5_only']}")
    print(f"  Net: {mc_5bet['net_advantage']:+d}  χ²={mc_5bet['chi2']:.3f}  p={mc_5bet['p_value']:.4f}")
    print(f"  {'✅ SIGNIFICANT' if mc_5bet['significant'] else '◎ NOT_SIGNIFICANT'}")
    print(f"  注: 3注以 M2+(NT$150) vs 5注以 M3+(NT$250)，不同獲利門檻")

    # ── 4. McNemar 主策略 vs 對照組 ─────────────────────────────
    print(f"\n{'='*70}")
    print("  [4] McNEMAR: 主策略 vs 對照組 (M2+, 500p)")
    print(f"{'='*70}")

    mc_vs_a = mcnemar_3bet_vs_3bet(
        predict_3bet_f_cold_fmid, predict_3bet_f_only,
        '3bet_F_Cold_Fmid', '3bet_F_only',
        all_draws, 500, SEED, MIN_TRAIN
    )
    mc_vs_b = mcnemar_3bet_vs_3bet(
        predict_3bet_f_cold_fmid, predict_3bet_f_cold_only,
        '3bet_F_Cold_Fmid', '3bet_F_Cold_only',
        all_draws, 500, SEED, MIN_TRAIN
    )
    report['mcnemar_vs_controls'] = {'vs_F_only': mc_vs_a, 'vs_F_Cold_only': mc_vs_b}

    for mc, label in [(mc_vs_a, 'vs 3bet_F_only'), (mc_vs_b, 'vs 3bet_F_Cold_only')]:
        print(f"\n  主策略 {label}:")
        print(f"    主策略 M2+: {mc['rate_a']*100:.2f}%  對照 M2+: {mc['rate_b']*100:.2f}%")
        print(f"    主策略獨贏: {mc['a_only']}  對照獨贏: {mc['b_only']}  Net: {mc['net_advantage_a']:+d}")
        print(f"    χ²={mc['chi2']:.3f}  p={mc['p_value']:.4f}  {'✅ SIGNIFICANT' if mc['significant'] else '◎ NOT_SIGNIFICANT'}")

    # ── 5. Random Baseline Calibration ──────────────────────────
    print(f"\n{'='*70}")
    print("  [5] RANDOM 3-BET BASELINE CALIBRATION")
    print(f"{'='*70}")
    rand_m2 = []; rand_m3 = []
    for s in range(20):
        rf = predict_random_3bet(seed_val=s * 7777)
        r = backtest_structured(rf, all_draws, 1500, seed=s + 50000, min_train=MIN_TRAIN)
        rand_m2.append(r['ge2_rate']); rand_m3.append(r['ge3_rate'])

    print(f"  Random 3-bet M2+ mean={np.mean(rand_m2)*100:.2f}% ± {np.std(rand_m2)*100:.2f}%")
    print(f"           range=[{np.min(rand_m2)*100:.2f}%, {np.max(rand_m2)*100:.2f}%]")
    print(f"  Random 3-bet M3+ mean={np.mean(rand_m3)*100:.2f}% ± {np.std(rand_m3)*100:.2f}%")
    print(f"  Theoretical 3-bet M2+: {P_GE2_3*100:.2f}%")
    print(f"  Theoretical 3-bet M3+: {P_GE3_3*100:.2f}%")

    report['random_calibration'] = {
        'm2_mean': float(np.mean(rand_m2)), 'm2_std': float(np.std(rand_m2)),
        'm3_mean': float(np.mean(rand_m3)), 'm3_std': float(np.std(rand_m3)),
    }

    # ── 6. 綜合決策 ─────────────────────────────────────────────
    elapsed = time.time() - t0
    print(f"\n{'='*70}")
    print("  [6] FINAL DECISION")
    print(f"{'='*70}")

    tw_main = all_tw_results['3bet_F_Cold_Fmid']
    tw_stable = all(tw_main.get(p, {}).get('ge2_edge', -1) > 0 for p in [150, 500, 1500] if p in tw_main)
    perm_signal = perm['p_value_empirical'] <= 0.05
    zero_overlap = bool(avg_overlap == 0)
    positive_total_edge = perm['total_edge'] > 0
    beats_5bet = mc_5bet['bet3_M2_rate'] >= mc_5bet['bet5_M3_rate']  # cost-adjusted comparison

    pass_criteria = {
        '三窗口全正_M2+': tw_stable,
        'perm_p_le_005': perm_signal,
        '零重疊': zero_overlap,
        'total_edge_positive': positive_total_edge,
    }
    all_pass = all(pass_criteria.values())

    print(f"\n  通過標準檢查:")
    for criterion, passed in pass_criteria.items():
        print(f"  {'✅' if passed else '❌'} {criterion}")

    print(f"\n  ★ 主策略 3bet_F_Cold_Fmid 三窗口 M2+ Edge:")
    for p in [150, 500, 1500]:
        if p in tw_main:
            r = tw_main[p]
            print(f"    {p}p: {r['ge2_rate']*100:.2f}% (edge={r['ge2_edge']*100:+.2f}%) "
                  f"z={r['z_ge2']['z']:.2f}")

    print(f"\n  Permutation: z={perm['z_score']:.2f}, p={perm['p_value_empirical']:.4f}, "
          f"Cohen's d={perm['cohen_d']:.2f}")

    cost_note = f"NT$150 (3注) vs NT$250 (5注), 成本節省40%"
    if all_pass:
        decision = 'PASS → PROVISIONAL'
        note = f"三窗口全正 + Permutation 通過。採用 PROVISIONAL 狀態，需200期後重驗。{cost_note}"
    elif not tw_stable and perm_signal:
        decision = 'FAIL → MARGINAL (窗口不穩定)'
        note = "信號存在但三窗口不全正，拒絕採納。"
    elif tw_stable and not perm_signal:
        decision = 'FAIL → MARGINAL (時序信號不顯著)'
        note = "三窗口全正但時序信號不顯著，記錄為 LATE_BLOOMER 候選。"
    else:
        decision = 'FAIL → REJECT'
        note = "未通過驗證，歸檔至 rejected/。"

    print(f"\n  {'='*50}")
    print(f"  最終決策: {decision}")
    print(f"  說明: {note}")
    print(f"  {'='*50}")
    print(f"\n  Total runtime: {elapsed:.1f}s")
    print("=" * 70)

    report['pass_criteria'] = pass_criteria
    report['decision'] = decision
    report['decision_note'] = note
    report['elapsed_seconds'] = round(elapsed, 1)

    # ── 儲存 JSON ────────────────────────────────────────────────
    def _clean(obj):
        if isinstance(obj, (np.bool_,)): return bool(obj)
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating, np.float64)): return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        if isinstance(obj, dict): return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list): return [_clean(v) for v in obj]
        return obj

    out_path = os.path.join(_base, '..', 'backtest_539_3bet_f_cold_fmid_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(_clean(report), f, indent=2, ensure_ascii=False)
    print(f"\n[SAVED] {out_path}")


if __name__ == '__main__':
    main()
