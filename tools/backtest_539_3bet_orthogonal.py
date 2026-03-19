#!/usr/bin/env python3
"""
=============================================================================
539 3bet Orthogonal 回測
=============================================================================
測試問題：正交化 3-bet (SumRange + GapPressure + ZoneShift)
         透過 exclude set 強制零重疊，M2+ 是否優於 random 3-bet baseline？

L30 根因: 原版3注平均13.4 unique nums (34.4%), random=15 (38.5%)
本版: chain exclusion → bet2 排除 bet1, bet3 排除 bet1+bet2 → 保證15 unique

回測協議：
  - Walk-forward（嚴格無數據洩漏）
  - 三窗口穩定性：150 / 500 / 1500 期
  - Permutation test（200 次）
  - Z-test vs 理論基線
  - Random 3-bet baseline 對照
  - McNemar paired test (new vs old)
  - M2+ 為主指標

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

print(f"[BASELINE] 3-bet M2+ = {P_GE2_3*100:.2f}%   ← 主指標")
print(f"[BASELINE] 3-bet M3+ = {P_GE3_3*100:.3f}%")
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
#  STRATEGIES
# ═══════════════════════════════════════════════════════════════════

_engine = None
def _get_engine():
    global _engine
    if _engine is None:
        from models.unified_predictor import UnifiedPredictionEngine
        _engine = UnifiedPredictionEngine()
    return _engine


RULES_539 = {'pickCount': 5, 'minNumber': 1, 'maxNumber': 39, 'name': 'DAILY_539'}


def predict_3bet_ortho(hist):
    """ORTHOGONAL: SumRange + GapPressure(exclude) + ZoneShift(exclude)

    Chain exclusion ensures zero overlap:
    - bet1: SumRange (5 numbers)
    - bet2: GapPressure excluding bet1 (5 numbers)
    - bet3: ZoneShift excluding bet1+bet2 (5 numbers)
    Total: exactly 15 unique numbers (38.5% coverage)
    """
    from models.gap_pressure import GapPressureScorer
    from models.zone_shift_detector import ZoneShiftDetector

    engine = _get_engine()
    bets = []

    # bet1: sum_range (no exclusion)
    r1 = engine.sum_range_predict(hist, RULES_539)
    bet1 = sorted([int(n) for n in r1['numbers'][:PICK]])
    bets.append(bet1)
    used = set(bet1)

    # bet2: gap_pressure (exclude bet1)
    gap_scorer = GapPressureScorer(max_num=MAX_NUM)
    r2 = gap_scorer.predict(hist, RULES_539, exclude=used)
    bet2 = sorted([int(n) for n in r2['numbers'][:PICK]])
    bets.append(bet2)
    used.update(bet2)

    # bet3: zone_shift (exclude bet1 + bet2)
    zone_det = ZoneShiftDetector(max_num=MAX_NUM)
    r3 = zone_det.predict(hist, RULES_539, exclude=used)
    bet3 = sorted([int(n) for n in r3['numbers'][:PICK]])
    bets.append(bet3)

    return bets


def predict_3bet_old(hist):
    """OLD: SumRange + Bayesian + ZoneBalance (current production)"""
    engine = _get_engine()
    bets = []

    r1 = engine.sum_range_predict(hist, RULES_539)
    bets.append(sorted([int(n) for n in r1['numbers'][:PICK]]))

    r2 = engine.bayesian_predict(hist, RULES_539)
    bets.append(sorted([int(n) for n in r2['numbers'][:PICK]]))

    r3 = engine.zone_balance_predict(hist, RULES_539)
    bets.append(sorted([int(n) for n in r3['numbers'][:PICK]]))

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
def backtest_structured(predict_func, all_draws, test_periods=1500, seed=42, min_train=300):
    """
    Walk-forward backtest for structured multi-bet strategy.
    predict_func(hist) → list of N bets (each bet = list of 5 numbers)
    """
    random.seed(seed)
    np.random.seed(seed)

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
        return {'z': 0, 'p': 1}
    z = (rate - baseline) / se
    p = 1 - scipy_stats.norm.cdf(z)
    return {'z': z, 'p': p, 'rate': rate, 'se': se}


def three_window_test(predict_func, all_draws, seed=42, min_train=300):
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
        }
    return results


def permutation_test(predict_func, all_draws, test_periods=500, n_perms=200, seed=42, min_train=300):
    """
    Permutation test vs random 3-bet baseline.
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

    cohen_d = (actual_rate - perm_mean) / perm_std if perm_std > 1e-10 else 0

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


def mcnemar_ortho_vs_old(all_draws, test_periods=500, seed=42, min_train=300):
    """McNemar's test: ORTHO 3-bet vs OLD 3-bet, per-draw paired comparison."""
    random.seed(seed)
    np.random.seed(seed)

    a = 0  # both hit
    b = 0  # new hit, old miss
    c = 0  # new miss, old hit
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
            new_bets = predict_3bet_ortho(hist)
            old_bets = predict_3bet_old(hist)
        except Exception:
            continue

        new_hit = any(len(set(b) & actual) >= 2 for b in new_bets)
        old_hit = any(len(set(b) & actual) >= 2 for b in old_bets)

        if new_hit and old_hit:
            a += 1
        elif new_hit and not old_hit:
            b += 1
        elif not new_hit and old_hit:
            c += 1
        else:
            d += 1
        total += 1

    # McNemar's chi-squared
    if b + c > 0:
        chi2 = (abs(b - c) - 1) ** 2 / (b + c)  # with continuity correction
        p = 1 - scipy_stats.chi2.cdf(chi2, df=1)
    else:
        chi2 = 0
        p = 1.0

    return {
        'total': total,
        'both_hit': a,
        'new_only': b,
        'old_only': c,
        'both_miss': d,
        'new_rate': (a + b) / total if total > 0 else 0,
        'old_rate': (a + c) / total if total > 0 else 0,
        'chi2': chi2,
        'p_value': p,
        'new_advantage': b - c,
    }


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    t0 = time.time()
    all_draws = load_data()

    report = {
        'timestamp': datetime.now().isoformat(),
        'strategy_ortho': 'SumRange + GapPressure(excl) + ZoneShift(excl)',
        'strategy_old': 'SumRange + Bayesian + ZoneBalance',
        'n_bets': N_BETS,
        'baselines': {
            'M2+_3bet': P_GE2_3,
            'M3+_3bet': P_GE3_3,
            'M2+_1bet': P_GE2_1,
        },
        'data_size': len(all_draws),
    }

    # ── 0. Quick sanity check: verify zero overlap ─────────────────
    print("\n" + "="*60)
    print("  [0] SANITY CHECK — Zero-Overlap Verification")
    print("="*60)
    # Test on last 10 draws
    overlap_checks = []
    for i in range(10):
        idx = len(all_draws) - 11 + i
        hist = all_draws[:idx]
        bets = predict_3bet_ortho(hist)
        all_nums = set(sum([list(b) for b in bets], []))
        unique_count = len(all_nums)
        overlap = sum(len(b) for b in bets) - unique_count
        overlap_checks.append({'unique': unique_count, 'overlap': overlap})
        print(f"  Draw {idx}: bets={[b for b in bets]}  unique={unique_count}  overlap={overlap}")

    avg_unique = np.mean([c['unique'] for c in overlap_checks])
    avg_overlap = np.mean([c['overlap'] for c in overlap_checks])
    print(f"\n  Average: unique={avg_unique:.1f}  overlap={avg_overlap:.1f}")
    if avg_overlap > 0:
        print("  ⚠️  WARNING: Non-zero overlap detected!")
    else:
        print("  ✅ Zero overlap confirmed — 15 unique numbers per prediction")

    report['sanity_check'] = {
        'avg_unique': avg_unique,
        'avg_overlap': avg_overlap,
        'zero_overlap': avg_overlap == 0,
    }

    # ── 1. Three-Window Stability (ORTHO strategy) ─────────────────
    print("\n" + "="*60)
    print("  [1] THREE-WINDOW STABILITY TEST (ORTHO)")
    print("="*60)
    tw_ortho = three_window_test(predict_3bet_ortho, all_draws, seed=42, min_train=300)
    report['three_window_ortho'] = {}
    for period, data in tw_ortho.items():
        print(f"\n  [{period}p] M2+: {data['ge2_rate']*100:.2f}% (edge={data['ge2_edge']*100:+.2f}%)")
        print(f"         M3+: {data['ge3_rate']*100:.2f}% (edge={data['ge3_edge']*100:+.2f}%)")
        print(f"         Z(M2+)={data['z_ge2']['z']:.2f}  p={data['z_ge2']['p']:.4f}")
        print(f"         Unique nums={data['avg_unique_nums']:.1f}  Overlap={data['avg_overlap']:.1f}")
        report['three_window_ortho'][str(period)] = {
            k: v for k, v in data.items()
            if not isinstance(v, dict) or k in ['z_ge2', 'z_ge3']
        }

    # ── 2. Three-Window Stability (OLD strategy) ─────────────────
    print("\n" + "="*60)
    print("  [2] THREE-WINDOW STABILITY TEST (OLD)")
    print("="*60)
    tw_old = three_window_test(predict_3bet_old, all_draws, seed=42, min_train=300)
    report['three_window_old'] = {}
    for period, data in tw_old.items():
        print(f"\n  [{period}p] M2+: {data['ge2_rate']*100:.2f}% (edge={data['ge2_edge']*100:+.2f}%)")
        print(f"         M3+: {data['ge3_rate']*100:.2f}% (edge={data['ge3_edge']*100:+.2f}%)")
        print(f"         Z(M2+)={data['z_ge2']['z']:.2f}  p={data['z_ge2']['p']:.4f}")
        report['three_window_old'][str(period)] = {
            k: v for k, v in data.items()
            if not isinstance(v, dict) or k in ['z_ge2', 'z_ge3']
        }

    # ── 3. Permutation Test (ORTHO vs Random) ─────────────────────
    print("\n" + "="*60)
    print("  [3] PERMUTATION TEST (ORTHO vs Random)")
    print("="*60)
    perm = permutation_test(predict_3bet_ortho, all_draws, test_periods=500, n_perms=200, seed=42, min_train=300)
    report['permutation_test'] = perm
    print(f"  Actual M2+:  {perm['actual_rate']*100:.2f}%")
    print(f"  Random mean: {perm['perm_mean']*100:.2f}% ± {perm['perm_std']*100:.2f}%")
    print(f"  Signal Edge: {perm['signal_edge']*100:+.2f}%")
    print(f"  Z-score:     {perm['z_score']:.2f}")
    print(f"  p-value:     {perm['p_value_empirical']:.4f}")
    print(f"  Cohen d:     {perm['cohen_d']:.2f}")

    # ── 4. McNemar (ORTHO vs OLD) ──────────────────────────────────
    print("\n" + "="*60)
    print("  [4] McNEMAR TEST (ORTHO vs OLD)")
    print("="*60)
    mcn = mcnemar_ortho_vs_old(all_draws, test_periods=500, seed=42, min_train=300)
    report['mcnemar'] = mcn
    print(f"  ORTHO M2+ rate: {mcn['new_rate']*100:.2f}%")
    print(f"  OLD   M2+ rate: {mcn['old_rate']*100:.2f}%")
    print(f"  Ortho only: {mcn['new_only']}  Old only: {mcn['old_only']}")
    print(f"  Advantage:    {mcn['new_advantage']:+d} draws")
    print(f"  Chi2:         {mcn['chi2']:.2f}   p={mcn['p_value']:.4f}")

    # ── 5. Decision ──────────────────────────────────────────────
    print("\n" + "="*60)
    print("  [5] DECISION")
    print("="*60)

    # Check pass criteria
    pass_criteria = {
        'perm_p_lt_005': perm['p_value_empirical'] < 0.05,
        'positive_edge': perm['signal_edge'] > 0,
        'ortho_beats_old': mcn['new_advantage'] > 0,
    }

    # Three-window stability: all windows must have positive M2+ edge
    tw_stable = all(
        tw_ortho.get(p, {}).get('ge2_edge', -1) > 0
        for p in [150, 500, 1500]
        if p in tw_ortho
    )
    pass_criteria['three_window_stable'] = tw_stable

    # Zero overlap check
    pass_criteria['zero_overlap'] = avg_overlap == 0

    all_pass = all(pass_criteria.values())

    report['pass_criteria'] = pass_criteria
    report['decision'] = 'PASS' if all_pass else 'FAIL'

    for criterion, passed in pass_criteria.items():
        status = '✅' if passed else '❌'
        print(f"  {status} {criterion}")

    if all_pass:
        print(f"\n  ✅ DECISION: PASS — 正交化3注策略通過所有驗證，可部署")
    else:
        print(f"\n  ❌ DECISION: FAIL — 正交化3注策略未通過驗證")

    elapsed = time.time() - t0
    report['elapsed_seconds'] = round(elapsed, 1)
    print(f"\n  [TIME] {elapsed:.1f}s")

    # ── Save Report ──────────────────────────────────────────────
    out_path = os.path.join(_base, '..', 'backtest_539_3bet_ortho_results.json')
    # Make JSON serializable
    def _clean(obj):
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean(v) for v in obj]
        return obj

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(_clean(report), f, indent=2, ensure_ascii=False)
    print(f"  [SAVED] {out_path}")


if __name__ == '__main__':
    main()
