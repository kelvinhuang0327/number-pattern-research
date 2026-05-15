#!/usr/bin/env python3
"""
H002 Backtest: 條件 ACB（前期熱號 Markov 條件化）
vs Baseline: ACB 1bet (Baseline_ACB_1bet)

Hypothesis:
  conditional_acb(n,t) = acb(n,t) * (1 + markov_boost * relative_markov(n))
  where relative_markov(n) = avg P(n | j in prev_draw) / P(n) - 1.0
  (how much more likely is n after seeing prev_draw vs unconditional)

Metric: M2+ (RSM standard for 539)
Baselines: {1: 0.1140}
Compare: Conditional_ACB vs Plain ACB (1-bet each)
"""
import json, sys, os, numpy as np, random
from collections import defaultdict

os.chdir('/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')

MAX_NUM = 39
WINDOW_ACB = 100
WINDOW_MARKOV = 500  # Markov transition estimation window
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

def markov_boost_scores(hist, prev_draw):
    """
    Compute relative Markov boost for each number given prev_draw.
    markov_boost(n) = avg_{j in prev_draw} [P(n|j) / P(n)] - 1.0
    where P(n|j) = empirical from last WINDOW_MARKOV periods
    P(n) = marginal frequency in same window
    """
    recent = hist[-WINDOW_MARKOV:]
    n_periods = len(recent)

    # Unconditional frequency
    freq_n = defaultdict(int)
    for d in recent:
        for n in d['numbers']:
            freq_n[n] += 1

    # Conditional frequency: count[j][n] = how often n appeared one period after j
    count_j = defaultdict(int)
    count_jn = defaultdict(lambda: defaultdict(int))
    for t in range(1, len(recent)):
        prev = recent[t-1]['numbers']
        curr = recent[t]['numbers']
        for j in prev:
            count_j[j] += 1
            for n in curr:
                count_jn[j][n] += 1

    p_n = {n: freq_n[n] / (n_periods * 5) for n in range(1, MAX_NUM+1)}  # unconditional

    boost = {}
    for n in range(1, MAX_NUM+1):
        relative_boosts = []
        for j in prev_draw:
            if count_j[j] > 0:
                p_n_given_j = count_jn[j][n] / count_j[j]
                p_n_val = p_n.get(n, 5/MAX_NUM)
                if p_n_val > 0:
                    relative_boosts.append(p_n_given_j / p_n_val - 1.0)
        boost[n] = np.mean(relative_boosts) if relative_boosts else 0.0

    return boost

def conditional_acb_scores(hist, prev_draw, markov_multiplier=0.3):
    """
    ACB score boosted by Markov conditional info from prev_draw
    """
    acb = acb_scores(hist)
    markov = markov_boost_scores(hist, prev_draw)
    scores = {}
    for n in range(1, MAX_NUM+1):
        scores[n] = acb[n] * (1.0 + markov_multiplier * markov.get(n, 0.0))
    return scores

def make_bet(scores, exclude=set(), top_n=5):
    cands = sorted([(s,n) for n,s in scores.items() if n not in exclude], reverse=True)
    return [n for _,n in cands[:top_n]]

def simulate_strategy(draws, use_conditional=False, start=600):
    """Need start>=WINDOW_MARKOV for valid Markov estimates"""
    hits = []
    for t in range(start, len(draws)):
        hist = draws[:t]
        actual = set(draws[t]['numbers'])
        prev_draw = draws[t-1]['numbers']

        if use_conditional:
            scores = conditional_acb_scores(hist, prev_draw)
        else:
            scores = acb_scores(hist)

        bet1 = make_bet(scores, set())
        m2 = sum(1 for x in bet1 if x in actual) >= 2

        hits.append({'is_m2plus_1bet': m2})

    return hits

def windowed_edge(hits, window, key='is_m2plus_1bet'):
    sub = hits[-window:]
    rate = sum(1 for h in sub if h[key]) / len(sub)
    baseline = BASELINES_539[1]
    return (rate - baseline) * 100

def permutation_test(hits_strategy, hits_baseline, key='is_m2plus_1bet', n_perm=200, seed=42):
    random.seed(seed)
    obs_diff = sum(h[key] for h in hits_strategy) - sum(h[key] for h in hits_baseline)
    combined = list(zip(hits_strategy, hits_baseline))
    count = 0
    for _ in range(n_perm):
        perm_s = sum(random.choice([hs[key], hb[key]]) for hs, hb in combined)
        perm_b = sum(hb[key] for _, hb in combined)
        if (perm_s - perm_b) >= obs_diff:
            count += 1
    return count / n_perm

def mcnemar(hits_a, hits_b, key='is_m2plus_1bet'):
    from scipy.stats import binomtest
    n01 = sum(1 for a,b in zip(hits_a, hits_b) if not a[key] and b[key])
    n10 = sum(1 for a,b in zip(hits_a, hits_b) if a[key] and not b[key])
    net = n10 - n01
    p = float(binomtest(n10, n01+n10, 0.5).pvalue) if (n01+n10) > 0 else 1.0
    return {'n01': n01, 'n10': n10, 'net': net, 'p': round(p, 4)}

if __name__ == '__main__':
    print("Loading data...")
    draws = load_539()
    START = 600  # Need 600 periods for WINDOW_MARKOV=500 + WINDOW_ACB=100

    print("Simulating Baseline ACB 1bet...")
    hits_base = simulate_strategy(draws, use_conditional=False, start=START)

    print("Simulating H002 Conditional ACB 1bet (markov_mult=0.3)...")
    hits_cond = simulate_strategy(draws, use_conditional=True, start=START)

    n = len(hits_base)
    print(f"\n=== H002 Results (n={n} periods) ===")
    print(f"Metric: M2+ | Baseline 1bet={BASELINES_539[1]*100:.2f}%")

    for name, hits in [('Baseline_ACB', hits_base), ('H002_CondACB', hits_cond)]:
        e150 = windowed_edge(hits, 150)
        e500 = windowed_edge(hits, 500)
        e1500 = windowed_edge(hits, 1500)
        print(f"  {name}: 150p={e150:+.2f}pp 500p={e500:+.2f}pp 1500p={e1500:+.2f}pp")

    mcn = mcnemar(hits_cond, hits_base)
    pp = permutation_test(hits_cond, hits_base)
    print(f"\n  McNemar (H002 vs Base): net={mcn['net']:+d} n01={mcn['n01']} n10={mcn['n10']} p={mcn['p']:.4f} {'SIG ✓' if mcn['p']<0.05 else 'ns'}")
    print(f"  Perm test (H002 vs Base): p={pp:.4f} {'SIGNAL ✓' if pp<0.05 else 'no signal'}")

    e_base_1500 = windowed_edge(hits_base, 1500)
    e_cond_1500 = windowed_edge(hits_cond, 1500)

    print("\n=== VERDICT ===")
    if e_cond_1500 > e_base_1500 and mcn['net'] > 0 and mcn['p'] < 0.1:
        verdict = 'ADOPT'
    elif abs(e_cond_1500 - e_base_1500) < 0.5 and mcn['p'] > 0.3:
        verdict = 'EQUIVALENT'
    else:
        verdict = 'REJECT'
    print(f"  1bet: Base={e_base_1500:+.2f}pp → H002={e_cond_1500:+.2f}pp | McNemar net={mcn['net']:+d} → {verdict}")

    result = {
        'hypothesis': 'H002',
        'name': '條件 ACB（Markov 條件化）',
        'metric': 'M2+',
        'baseline_1bet': {'e150': windowed_edge(hits_base, 150), 'e500': windowed_edge(hits_base, 500), 'e1500': e_base_1500},
        'h002_1bet': {'e150': windowed_edge(hits_cond, 150), 'e500': windowed_edge(hits_cond, 500), 'e1500': e_cond_1500},
        'mcnemar': mcn,
        'perm_p': pp,
        'n_periods': n,
        'start': START,
        'markov_window': WINDOW_MARKOV,
        'markov_multiplier': 0.3,
        'verdict': verdict
    }

    out = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/tools/backtest_539_h002_results.json'
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Saved to {out}")
