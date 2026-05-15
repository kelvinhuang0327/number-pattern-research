#!/usr/bin/env python3
"""
H001 Backtest: ACB × MidFreq Product Score
vs Baseline: ACB*0.5 + MidFreq*0.5 (weighted average)

Methodology (consistent with backtest_ewma_mab_539.py):
  - Threshold: M2+ (any bet matches >= 2 numbers)
  - BASELINES: {1: 11.40, 2: 21.54, 3: 30.50}  (fixed empirical baselines)
  - Edge = rate - baseline  (absolute percentage points)
  - Permutation test: 200x vs random bets
  - McNemar paired comparison

Compare using:
  - 3-window Edge (150/500/1500p)
  - Permutation test (200x)
  - McNemar vs Baseline 2bet and 3bet
"""
import json, sys, os, numpy as np, random
from collections import defaultdict, Counter

project_root = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew'
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
os.chdir(os.path.join(project_root, 'lottery_api'))

MAX_NUM = 39
PICK = 5
WINDOW_ACB = 100
WINDOW_MID = 100   # matches _539_midfreq_bet window=100
RANDOM_SEED = 42

# Fixed empirical baselines (from backtest_ewma_mab_539.py)
BASELINES = {1: 11.40, 2: 21.54, 3: 30.50}


def load_539():
    from database import DatabaseManager
    db = DatabaseManager()
    raw = db.get_all_draws('DAILY_539')
    draws = [{'period': d['draw'],
              'numbers': sorted(json.loads(d['numbers']) if isinstance(d['numbers'], str) else d['numbers'])}
             for d in raw]
    draws.sort(key=lambda x: x['period'])
    print(f"Loaded {len(draws)} draws, last={draws[-1]['period']}")
    return draws


def _acb_bet(history, exclude=None, window=100):
    """Identical to quick_predict._539_acb_bet"""
    exclude = exclude or set()
    recent = history[-window:]
    counter = Counter(n for d in recent for n in d['numbers'])
    last_seen = {n: i for i, d in enumerate(recent) for n in d['numbers']}
    expected_freq = len(recent) * 5 / 39
    scores = {}
    for n in range(1, 40):
        if n in exclude:
            continue
        scores[n] = ((expected_freq - counter.get(n, 0)) * 0.4
                     + (len(recent) - last_seen.get(n, -1)) / (len(recent) / 2) * 0.6) \
                    * (1.2 if n <= 8 or n >= 35 else 1.0)
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:5])


def _midfreq_bet(history, exclude=None, window=100):
    """Identical to quick_predict._539_midfreq_bet"""
    exclude = exclude or set()
    recent = history[-window:]
    expected = len(recent) * 5 / 39
    freq = Counter(n for d in recent for n in d['numbers'])
    candidates = sorted([n for n in range(1, 40) if n not in exclude],
                        key=lambda x: abs(freq.get(x, 0) - expected))
    return sorted(candidates[:5])


def _acb_scores_raw(history, window=100):
    """Return raw ACB scores dict {n: score}"""
    recent = history[-window:]
    counter = Counter(n for d in recent for n in d['numbers'])
    last_seen = {n: i for i, d in enumerate(recent) for n in d['numbers']}
    expected_freq = len(recent) * 5 / 39
    scores = {}
    for n in range(1, 40):
        scores[n] = ((expected_freq - counter.get(n, 0)) * 0.4
                     + (len(recent) - last_seen.get(n, -1)) / (len(recent) / 2) * 0.6) \
                    * (1.2 if n <= 8 or n >= 35 else 1.0)
    return scores


def _midfreq_scores_raw(history, window=100):
    """Return raw MidFreq scores dict {n: score}"""
    recent = history[-window:]
    expected = len(recent) * 5 / 39
    freq = Counter(n for d in recent for n in d['numbers'])
    scores = {}
    for n in range(1, 40):
        f = freq.get(n, 0)
        # MidFreq: closer to expected = higher score
        # Use inverted distance: max_dist - dist, so closer=higher
        dist = abs(f - expected)
        scores[n] = -dist  # higher = more "mid-frequency"
    return scores


def _baseline_2bet(history):
    """Baseline: bet1=ACB, bet2=MidFreq(exclude bet1)
    This is the actual current production strategy for 2-bet."""
    bet1 = _acb_bet(history)
    bet2 = _midfreq_bet(history, exclude=set(bet1))
    return [bet1, bet2]


def _h001_2bet(history):
    """H001: product-score combined bet replaces bet2.
    bet1=ACB (same), bet2 = top-5 by ACB_normalized * MidFreq_normalized (exclude bet1)"""
    bet1 = _acb_bet(history)

    acb_raw = _acb_scores_raw(history)
    mid_raw = _midfreq_scores_raw(history)

    # Normalize both to [0,1]
    acb_vals = list(acb_raw.values())
    mid_vals = list(mid_raw.values())
    acb_min, acb_max = min(acb_vals), max(acb_vals)
    mid_min, mid_max = min(mid_vals), max(mid_vals)

    acb_range = acb_max - acb_min or 1.0
    mid_range = mid_max - mid_min or 1.0

    product_scores = {}
    for n in range(1, 40):
        if n in set(bet1):
            continue
        acb_norm = (acb_raw[n] - acb_min) / acb_range
        mid_norm = (mid_raw[n] - mid_min) / mid_range
        product_scores[n] = acb_norm * mid_norm

    ranked = sorted(product_scores, key=lambda x: -product_scores[x])
    bet2 = sorted(ranked[:5])
    return [bet1, bet2]


def _baseline_3bet(history):
    """Baseline 3-bet: ACB + MidFreq(excl) + ACB_residual(excl both).
    Using same structure as current midfreq_acb_2bet extended to 3."""
    bet1 = _acb_bet(history)
    bet2 = _midfreq_bet(history, exclude=set(bet1))
    # bet3: ACB again with both excluded (cold pool fallback)
    bet3 = _acb_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


def _h001_3bet(history):
    """H001 3-bet: product bet replaces bet2, bet3=ACB_residual."""
    bets = _h001_2bet(history)
    bet1, bet2 = bets[0], bets[1]
    bet3 = _acb_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


def simulate(draws, strategy_func, start=300):
    """Rolling backtest, returns list of 0/1 per period (1 = M2+)."""
    hits = []
    for t in range(start, len(draws)):
        hist = draws[:t]
        actual = set(draws[t]['numbers'])
        bets = strategy_func(hist)
        any_m2plus = any(sum(1 for x in bet if x in actual) >= 2 for bet in bets)
        hits.append(1 if any_m2plus else 0)
    return hits


def windowed_edge(hits, window, n_bets):
    sub = hits[-window:]
    rate = sum(sub) / len(sub) * 100
    return rate - BASELINES[n_bets]


def permutation_test(hits_strategy, hits_baseline, n_perm=200, seed=42):
    """One-sided permutation test: P(random_diff >= observed_diff)."""
    random.seed(seed)
    obs_diff = sum(hits_strategy) - sum(hits_baseline)
    combined = list(zip(hits_strategy, hits_baseline))
    count = 0
    for _ in range(n_perm):
        perm_s = sum(random.choice([hs, hb]) for hs, hb in combined)
        perm_b = sum(hb for _, hb in combined)
        if (perm_s - perm_b) >= obs_diff:
            count += 1
    return count / n_perm


def mcnemar(hits_a, hits_b):
    from scipy.stats import binomtest
    n01 = sum(1 for a, b in zip(hits_a, hits_b) if not a and b)
    n10 = sum(1 for a, b in zip(hits_a, hits_b) if a and not b)
    net = n10 - n01
    p = float(binomtest(n10, n01 + n10, 0.5).pvalue) if (n01 + n10) > 0 else 1.0
    return {'n01': n01, 'n10': n10, 'net': net, 'p': round(p, 4)}


if __name__ == '__main__':
    print("Loading data...")
    draws = load_539()
    START = 300

    print("Simulating Baseline 2-bet (ACB + MidFreq)...")
    hits_base2 = simulate(draws, _baseline_2bet, start=START)

    print("Simulating H001 2-bet (ACB + Product)...")
    hits_h001_2 = simulate(draws, _h001_2bet, start=START)

    print("Simulating Baseline 3-bet (ACB + MidFreq + ACB_residual)...")
    hits_base3 = simulate(draws, _baseline_3bet, start=START)

    print("Simulating H001 3-bet (ACB + Product + ACB_residual)...")
    hits_h001_3 = simulate(draws, _h001_3bet, start=START)

    n = len(hits_base2)
    print(f"\n=== Results (n={n} periods) ===")
    print(f"Threshold: M2+ (any bet >= 2 matches)")
    print(f"Baselines: 2bet={BASELINES[2]}%, 3bet={BASELINES[3]}%")

    # --- 2-bet ---
    print(f"\n--- 2-bet ---")
    for name, hits in [('Baseline(ACB+MidFreq)', hits_base2), ('H001(ACB+Product)', hits_h001_2)]:
        e150 = windowed_edge(hits, 150, 2)
        e500 = windowed_edge(hits, 500, 2)
        e1500 = windowed_edge(hits, 1500, 2)
        r150 = sum(hits[-150:]) / 150 * 100
        r500 = sum(hits[-500:]) / 500 * 100
        r1500 = sum(hits[-1500:]) / 1500 * 100
        print(f"  {name}:")
        print(f"    rate: 150p={r150:.2f}% 500p={r500:.2f}% 1500p={r1500:.2f}%")
        print(f"    edge: 150p={e150:+.2f}pp 500p={e500:+.2f}pp 1500p={e1500:+.2f}pp")

    mcn2 = mcnemar(hits_h001_2, hits_base2)
    pp2 = permutation_test(hits_h001_2, hits_base2)
    print(f"  McNemar (H001 vs Base): net={mcn2['net']:+d} n01={mcn2['n01']} n10={mcn2['n10']} p={mcn2['p']:.4f} {'SIG' if mcn2['p'] < 0.05 else 'ns'}")
    print(f"  Perm test (H001 vs Base, 200x): p={pp2:.4f} {'SIGNAL' if pp2 < 0.05 else 'no signal'}")

    # --- 3-bet ---
    print(f"\n--- 3-bet ---")
    for name, hits in [('Baseline(ACB+Mid+ACB_r)', hits_base3), ('H001(ACB+Prod+ACB_r)', hits_h001_3)]:
        e150 = windowed_edge(hits, 150, 3)
        e500 = windowed_edge(hits, 500, 3)
        e1500 = windowed_edge(hits, 1500, 3)
        r150 = sum(hits[-150:]) / 150 * 100
        r500 = sum(hits[-500:]) / 500 * 100
        r1500 = sum(hits[-1500:]) / 1500 * 100
        print(f"  {name}:")
        print(f"    rate: 150p={r150:.2f}% 500p={r500:.2f}% 1500p={r1500:.2f}%")
        print(f"    edge: 150p={e150:+.2f}pp 500p={e500:+.2f}pp 1500p={e1500:+.2f}pp")

    mcn3 = mcnemar(hits_h001_3, hits_base3)
    pp3 = permutation_test(hits_h001_3, hits_base3)
    print(f"  McNemar (H001 vs Base): net={mcn3['net']:+d} n01={mcn3['n01']} n10={mcn3['n10']} p={mcn3['p']:.4f} {'SIG' if mcn3['p'] < 0.05 else 'ns'}")
    print(f"  Perm test (H001 vs Base, 200x): p={pp3:.4f} {'SIGNAL' if pp3 < 0.05 else 'no signal'}")

    # --- Verdict ---
    e2_base = windowed_edge(hits_base2, 1500, 2)
    e2_h001 = windowed_edge(hits_h001_2, 1500, 2)
    e3_base = windowed_edge(hits_base3, 1500, 3)
    e3_h001 = windowed_edge(hits_h001_3, 1500, 3)

    print(f"\n=== VERDICT ===")
    if e2_h001 > e2_base and mcn2['net'] > 0 and mcn2['p'] < 0.05:
        verdict = 'ADOPT'
    elif abs(e2_h001 - e2_base) < 0.5 and mcn2['p'] >= 0.05:
        verdict = 'EQUIVALENT'
    elif e2_h001 < e2_base - 0.5 or (mcn2['net'] < 0 and mcn2['p'] < 0.05):
        verdict = 'REJECT'
    else:
        verdict = 'MARGINAL'

    print(f"  2bet: Baseline={e2_base:+.2f}pp → H001={e2_h001:+.2f}pp | delta={e2_h001-e2_base:+.2f}pp | McNemar net={mcn2['net']} p={mcn2['p']} → {verdict}")
    print(f"  3bet: Baseline={e3_base:+.2f}pp → H001={e3_h001:+.2f}pp | delta={e3_h001-e3_base:+.2f}pp | McNemar net={mcn3['net']} p={mcn3['p']}")

    result = {
        'hypothesis': 'H001',
        'name': 'ACB x MidFreq Product Score (normalized)',
        'methodology': 'M2+ threshold, BASELINES={1:11.40,2:21.54,3:30.50}, edge=rate-baseline (pp)',
        'n_periods': n,
        'baseline_2bet': {
            'e150': windowed_edge(hits_base2, 150, 2),
            'e500': windowed_edge(hits_base2, 500, 2),
            'e1500': e2_base,
        },
        'h001_2bet': {
            'e150': windowed_edge(hits_h001_2, 150, 2),
            'e500': windowed_edge(hits_h001_2, 500, 2),
            'e1500': e2_h001,
        },
        'baseline_3bet': {
            'e150': windowed_edge(hits_base3, 150, 3),
            'e500': windowed_edge(hits_base3, 500, 3),
            'e1500': e3_base,
        },
        'h001_3bet': {
            'e150': windowed_edge(hits_h001_3, 150, 3),
            'e500': windowed_edge(hits_h001_3, 500, 3),
            'e1500': e3_h001,
        },
        'mcnemar_2bet': mcn2,
        'mcnemar_3bet': mcn3,
        'perm_p_2bet': pp2,
        'perm_p_3bet': pp3,
        'verdict': verdict,
    }

    out = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/tools/backtest_539_h001_product_results.json'
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {out}")
