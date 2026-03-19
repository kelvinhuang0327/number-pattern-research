#!/usr/bin/env python3
"""
H001 Backtest v2: ACB × MidFreq Product Score
vs Baseline: ACB*0.5 + MidFreq*0.5 (weighted average)

FIXED:
- Use M2+ metric (matching RSM definition for 539)
- Correct baseline: {2: 0.2154, 3: 0.3050}
- Edge = rate - baseline (absolute, not percentage)
"""
import json, sys, os, numpy as np, random
from collections import defaultdict

os.chdir('/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')

MAX_NUM = 39
WINDOW_ACB = 100
WINDOW_MID = 200
RANDOM_SEED = 42

# RSM baselines for DAILY_539 (M2+)
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

def midfreq_scores(hist):
    freq = defaultdict(int)
    for d in hist[-WINDOW_MID:]:
        for n in d['numbers']:
            freq[n] += 1
    expected = WINDOW_MID * 5 / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM+1):
        f = freq.get(n, 0)
        ratio = f / expected if expected > 0 else 0
        scores[n] = (1.0 - abs(ratio - 1.0)) if 0.5 <= ratio <= 1.5 else 0.0
    return scores

def make_bet(scores, exclude=set(), top_n=5):
    cands = sorted([(s,n) for n,s in scores.items() if n not in exclude], reverse=True)
    return [n for _,n in cands[:top_n]]

def combined_baseline(acb, mid):
    """Current: weighted average 50/50"""
    return {n: acb.get(n,0)*0.5 + mid.get(n,0)*0.5 for n in range(1, MAX_NUM+1)}

def combined_product(acb, mid):
    """H001: product score - normalize both to [0,1] first"""
    acb_max = max(acb.values()) or 1
    mid_max = max(mid.values()) or 1
    return {n: (acb.get(n,0)/acb_max) * (mid.get(n,0)/mid_max) for n in range(1, MAX_NUM+1)}

def simulate_strategy(draws, use_product=False, start=300):
    hits = []
    for t in range(start, len(draws)):
        hist = draws[:t]
        actual = set(draws[t]['numbers'])
        acb = acb_scores(hist)
        mid = midfreq_scores(hist)

        if use_product:
            comb = combined_product(acb, mid)
        else:
            comb = combined_baseline(acb, mid)

        # 2-bet: bet1=ACB top5, bet2=combined top5 excl bet1
        bet1 = make_bet(acb, set())
        bet2 = make_bet(comb, set(bet1))

        # 3-bet: add bet3=midfreq top5 excl bet1+bet2
        bet3 = make_bet(mid, set(bet1)|set(bet2))

        # M2+ (2 or more correct) - RSM metric for 539
        def m2plus(bets):
            return max(sum(1 for x in b if x in actual) for b in bets) >= 2

        hits.append({
            'is_m2plus_2bet': m2plus([bet1, bet2]),
            'is_m2plus_3bet': m2plus([bet1, bet2, bet3]),
        })
    return hits

def windowed_edge(hits, window, n_bets):
    sub = hits[-window:]
    key = 'is_m2plus_2bet' if n_bets == 2 else 'is_m2plus_3bet'
    rate = sum(1 for h in sub if h[key]) / len(sub)
    baseline = BASELINES_539[n_bets]
    return (rate - baseline) * 100  # in percentage points

def permutation_test(hits_strategy, hits_baseline, n_bets, n_perm=200, seed=42):
    random.seed(seed)
    key = 'is_m2plus_2bet' if n_bets == 2 else 'is_m2plus_3bet'
    obs_diff = sum(h[key] for h in hits_strategy) - sum(h[key] for h in hits_baseline)
    combined = list(zip(hits_strategy, hits_baseline))
    count = 0
    for _ in range(n_perm):
        perm_s = sum(random.choice([hs[key], hb[key]]) for hs, hb in combined)
        perm_b = sum(hb[key] for _, hb in combined)
        if (perm_s - perm_b) >= obs_diff:
            count += 1
    return count / n_perm

def mcnemar(hits_a, hits_b, n_bets):
    from scipy.stats import binomtest
    key = 'is_m2plus_2bet' if n_bets == 2 else 'is_m2plus_3bet'
    n01 = sum(1 for a,b in zip(hits_a, hits_b) if not a[key] and b[key])
    n10 = sum(1 for a,b in zip(hits_a, hits_b) if a[key] and not b[key])
    net = n10 - n01
    p = float(binomtest(n10, n01+n10, 0.5).pvalue) if (n01+n10) > 0 else 1.0
    return {'n01': n01, 'n10': n10, 'net': net, 'p': round(p, 4)}

if __name__ == '__main__':
    print("Loading data...")
    draws = load_539()
    START = 300

    print("Simulating Baseline (weighted average 50/50)...")
    hits_base = simulate_strategy(draws, use_product=False, start=START)

    print("Simulating H001 (product score)...")
    hits_prod = simulate_strategy(draws, use_product=True, start=START)

    print(f"\n=== H001 Results (n={len(hits_base)} periods) ===")
    print(f"Metric: M2+ | Baselines: 2bet={BASELINES_539[2]*100:.2f}%, 3bet={BASELINES_539[3]*100:.2f}%")

    results = {}
    for n_bets, label in [(2, '2bet'), (3, '3bet')]:
        print(f"\n--- {n_bets}-bet ---")
        for name, hits in [('Baseline', hits_base), ('H001_Product', hits_prod)]:
            e150 = windowed_edge(hits, 150, n_bets)
            e500 = windowed_edge(hits, 500, n_bets)
            e1500 = windowed_edge(hits, 1500, n_bets)
            print(f"  {name}: 150p={e150:+.2f}pp 500p={e500:+.2f}pp 1500p={e1500:+.2f}pp")

        mcn = mcnemar(hits_prod, hits_base, n_bets)
        pp = permutation_test(hits_prod, hits_base, n_bets)
        print(f"  McNemar (H001 vs Base): net={mcn['net']:+d} n01={mcn['n01']} n10={mcn['n10']} p={mcn['p']:.4f} {'SIG ✓' if mcn['p']<0.05 else 'ns'}")
        print(f"  Perm test (H001 vs Base): p={pp:.4f} {'SIGNAL ✓' if pp<0.05 else 'no signal'}")
        results[label] = {'mcnemar': mcn, 'perm_p': pp}

    e2_base_1500 = windowed_edge(hits_base, 1500, 2)
    e2_prod_1500 = windowed_edge(hits_prod, 1500, 2)
    e3_base_1500 = windowed_edge(hits_base, 1500, 3)
    e3_prod_1500 = windowed_edge(hits_prod, 1500, 3)
    mcn2 = mcnemar(hits_prod, hits_base, 2)

    print("\n=== VERDICT ===")
    if e2_prod_1500 > e2_base_1500 and mcn2['net'] > 0 and mcn2['p'] < 0.1:
        verdict = 'ADOPT'
    elif abs(e2_prod_1500 - e2_base_1500) < 0.3 and mcn2['p'] > 0.3:
        verdict = 'EQUIVALENT'
    else:
        verdict = 'REJECT'
    print(f"  2bet: Base={e2_base_1500:+.2f}pp → H001={e2_prod_1500:+.2f}pp | McNemar net={mcn2['net']:+d} → {verdict}")
    print(f"  3bet: Base={e3_base_1500:+.2f}pp → H001={e3_prod_1500:+.2f}pp")

    result = {
        'hypothesis': 'H001',
        'name': 'ACB x MidFreq Product Score',
        'metric': 'M2+',
        'baselines': {'2bet': BASELINES_539[2], '3bet': BASELINES_539[3]},
        'n_periods': len(hits_base),
        'baseline_2bet': {'e150': windowed_edge(hits_base,150,2), 'e500': windowed_edge(hits_base,500,2), 'e1500': e2_base_1500},
        'product_2bet': {'e150': windowed_edge(hits_prod,150,2), 'e500': windowed_edge(hits_prod,500,2), 'e1500': e2_prod_1500},
        'baseline_3bet': {'e150': windowed_edge(hits_base,150,3), 'e500': windowed_edge(hits_base,500,3), 'e1500': e3_base_1500},
        'product_3bet': {'e150': windowed_edge(hits_prod,150,3), 'e500': windowed_edge(hits_prod,500,3), 'e1500': e3_prod_1500},
        'mcnemar_2bet': mcn2,
        'mcnemar_3bet': mcnemar(hits_prod, hits_base, 3),
        'perm_2bet': results['2bet']['perm_p'],
        'perm_3bet': results['3bet']['perm_p'],
        'verdict': verdict
    }

    out = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/tools/backtest_539_h001_v2_results.json'
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Saved to {out}")
