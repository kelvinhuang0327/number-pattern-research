#!/usr/bin/env python3
"""
H003 Backtest: ΔACB 頻率動量作為 ACB 補充過濾器
vs Baseline: ACB 1bet

Design:
  delta_acb(n) = freq_300(n)/300 - freq_30(n)/30  [負值 = 近期更冷 = ACB 信號強化]
  H003: 在 ACB top-N 候選中，依 ACB + alpha * norm(ΔACB) 排序取 top-5

Gate 結果警示：Pure ΔACB Top-5 Lift=0.985 < 1.0 → 作為過濾器可能也無效

Metric: M2+ (RSM standard for 539)
"""
import json, sys, os, numpy as np, random
from collections import defaultdict
from scipy.stats import binomtest

os.chdir('/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')

MAX_NUM = 39
WINDOW_ACB = 100
WINDOW_SHORT = 30
WINDOW_LONG = 300
RANDOM_SEED = 42

BASELINES_539 = {1: 0.1140, 2: 0.2154, 3: 0.3050}

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

def acb_scores(hist):
    freq = defaultdict(int)
    for d in hist[-WINDOW_ACB:]:
        for n in d['numbers']:
            freq[n] += 1
    last_seen = {}
    for i, d in enumerate(hist):
        for n in d['numbers']:
            last_seen[n] = i
    cur = len(hist) - 1
    expected = WINDOW_ACB * 5 / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM+1):
        gap = cur - last_seen.get(n, -50)
        fd = max(0, expected - freq.get(n,0)) / expected
        gs = min(gap/20, 1.0)
        boundary = 1.2 if (n <= 8 or n >= MAX_NUM-4) else 1.0
        scores[n] = (fd*0.4 + gs*0.6) * boundary
    return scores

def delta_acb_scores(hist):
    """
    ΔACB(n) = freq_long(n)/WINDOW_LONG - freq_short(n)/WINDOW_SHORT
    Negative value = number is cooling down recently (ACB signal stronger)
    We want to prioritize numbers with HIGH positive ΔACB (= more below long-term average recently)
    Actually: delta = long_rate - short_rate
    If long_rate > short_rate → number appeared less recently → cooler → ΔACB positive = good signal
    """
    freq_short = defaultdict(int)
    for d in hist[-WINDOW_SHORT:]:
        for n in d['numbers']:
            freq_short[n] += 1

    freq_long = defaultdict(int)
    for d in hist[-WINDOW_LONG:]:
        for n in d['numbers']:
            freq_long[n] += 1

    delta = {}
    for n in range(1, MAX_NUM+1):
        rate_short = freq_short[n] / WINDOW_SHORT
        rate_long = freq_long[n] / WINDOW_LONG
        delta[n] = rate_long - rate_short  # positive = cooling recently

    return delta

def normalize_scores(scores):
    """Normalize to [0,1]"""
    vals = list(scores.values())
    mn, mx = min(vals), max(vals)
    if mx == mn:
        return {n: 0.5 for n in scores}
    return {n: (v - mn) / (mx - mn) for n, v in scores.items()}

def make_bet_h003(acb, delta, pool_size=20, alpha=0.5):
    """
    Take ACB top-pool_size, then re-rank by ACB + alpha * norm(ΔACB), take top-5
    """
    acb_norm = normalize_scores(acb)
    delta_norm = normalize_scores(delta)

    # Step 1: ACB top-20 candidate pool
    acb_pool = sorted(acb.keys(), key=lambda n: acb[n], reverse=True)[:pool_size]

    # Step 2: re-rank by combined score
    combined = {n: acb_norm[n] + alpha * delta_norm[n] for n in acb_pool}
    return sorted(acb_pool, key=lambda n: combined[n], reverse=True)[:5]

def make_bet_acb(acb):
    return sorted(acb.keys(), key=lambda n: acb[n], reverse=True)[:5]

def simulate_strategy(draws, alpha=0.5, pool_size=20, start=WINDOW_LONG):
    hits_base = []
    hits_h003 = []
    for t in range(start, len(draws)):
        hist = draws[:t]
        actual = set(draws[t]['numbers'])

        acb = acb_scores(hist)
        delta = delta_acb_scores(hist)

        bet_base = make_bet_acb(acb)
        bet_h003 = make_bet_h003(acb, delta, pool_size=pool_size, alpha=alpha)

        hits_base.append(sum(1 for x in bet_base if x in actual) >= 2)
        hits_h003.append(sum(1 for x in bet_h003 if x in actual) >= 2)

    return hits_base, hits_h003

def windowed_edge(hits, window):
    sub = hits[-window:]
    rate = sum(sub) / len(sub)
    return (rate - BASELINES_539[1]) * 100

def mcnemar(hits_a, hits_b):
    n01 = sum(1 for a,b in zip(hits_a, hits_b) if not a and b)
    n10 = sum(1 for a,b in zip(hits_a, hits_b) if a and not b)
    net = n10 - n01
    p = float(binomtest(n10, n01+n10, 0.5).pvalue) if (n01+n10) > 0 else 1.0
    return {'n01': n01, 'n10': n10, 'net': net, 'p': round(p, 4)}

def perm_test(hits_a, hits_b, n_perm=200, seed=42):
    random.seed(seed)
    obs = sum(hits_a) - sum(hits_b)
    count = 0
    for _ in range(n_perm):
        ps = sum(random.choice([a, b]) for a, b in zip(hits_a, hits_b))
        pb = sum(hits_b)
        if (ps - pb) >= obs:
            count += 1
    return count / n_perm

if __name__ == '__main__':
    print("Loading data...")
    draws = load_539()
    START = WINDOW_LONG  # 300 periods warmup

    # === Parameter scan: alpha and pool_size ===
    print("\n=== H003 Parameter Scan (pool_size=20) ===")
    print(f"{'alpha':>6} | {'150p':>8} | {'500p':>8} | {'1500p':>8} | {'McN net':>9} | {'McN p':>8}")
    print("-" * 65)

    best_result = None
    best_e1500 = -999
    all_results = []

    for alpha in [0.2, 0.5, 1.0, 2.0]:
        hits_base, hits_h003 = simulate_strategy(draws, alpha=alpha, pool_size=20, start=START)
        e150 = windowed_edge(hits_h003, 150)
        e500 = windowed_edge(hits_h003, 500)
        e1500 = windowed_edge(hits_h003, 1500)
        mcn = mcnemar(hits_h003, hits_base)
        print(f"  {alpha:>4} | {e150:>+8.2f} | {e500:>+8.2f} | {e1500:>+8.2f} | {mcn['net']:>+9} | {mcn['p']:>8.4f}")
        if e1500 > best_e1500:
            best_e1500 = e1500
            best_result = (alpha, hits_base, hits_h003, e150, e500, e1500, mcn)
        all_results.append({'alpha': alpha, 'e150': e150, 'e500': e500, 'e1500': e1500, 'mcn': mcn})

    # Best alpha — full test
    best_alpha, hits_base, hits_h003, e150, e500, e1500, mcn = best_result
    print(f"\nBest alpha={best_alpha} (1500p={e1500:+.2f}pp)")

    e_base_150 = windowed_edge(hits_base, 150)
    e_base_500 = windowed_edge(hits_base, 500)
    e_base_1500 = windowed_edge(hits_base, 1500)
    print(f"\nBaseline ACB: 150p={e_base_150:+.2f}pp 500p={e_base_500:+.2f}pp 1500p={e_base_1500:+.2f}pp")
    print(f"H003 best:    150p={e150:+.2f}pp 500p={e500:+.2f}pp 1500p={e1500:+.2f}pp")

    pp = perm_test(hits_h003, hits_base)
    print(f"\nPerm test (H003 vs Base, n=200): p={pp:.4f} {'SIGNAL ✓' if pp<0.05 else 'no signal'}")
    print(f"McNemar: net={mcn['net']:+d} n01={mcn['n01']} n10={mcn['n10']} p={mcn['p']:.4f} {'SIG ✓' if mcn['p']<0.05 else 'ns'}")

    print("\n=== VERDICT ===")
    if e1500 > e_base_1500 and mcn['net'] > 0 and mcn['p'] < 0.1:
        verdict = 'ADOPT'
    elif abs(e1500 - e_base_1500) < 0.5 and mcn['p'] > 0.3:
        verdict = 'EQUIVALENT'
    else:
        verdict = 'REJECT'
    print(f"  1500p: Base={e_base_1500:+.2f}pp → H003={e1500:+.2f}pp | McNemar net={mcn['net']:+d} → {verdict}")

    result = {
        'hypothesis': 'H003',
        'name': 'ΔACB 頻率動量作為 ACB 補充過濾器',
        'metric': 'M2+',
        'n_periods': len(hits_base),
        'start': START,
        'param_scan': all_results,
        'best_alpha': best_alpha,
        'baseline_acb': {'e150': e_base_150, 'e500': e_base_500, 'e1500': e_base_1500},
        'h003_best': {'e150': e150, 'e500': e500, 'e1500': e1500},
        'mcnemar': mcn,
        'perm_p': pp,
        'verdict': verdict
    }

    out = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/tools/backtest_539_h003_results.json'
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Saved to {out}")
