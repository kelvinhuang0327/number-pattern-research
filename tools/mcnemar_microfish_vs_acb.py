#!/usr/bin/env python3
"""
McNemar Gate Test: MicroFish_1bet vs ACB_1bet
=============================================
Final deployment gate for MicroFish replacing ACB as 1-bet primary.

Pass criteria: net >= +20, McNemar p < 0.05
"""

import os
import sys
import json
import math
import numpy as np
from collections import Counter

SEED = 42
np.random.seed(SEED)

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

MAX_NUM = 39
PICK = 5
BASELINE_RATE = sum(
    math.comb(PICK, m) * math.comb(MAX_NUM - PICK, PICK - m)
    for m in range(2, PICK + 1)
) / math.comb(MAX_NUM, PICK)


def load_draws():
    from database import DatabaseManager
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    draws = sorted(db.get_all_draws('DAILY_539'), key=lambda x: (x['date'], x['draw']))
    return [d for d in draws if d.get('numbers') and len(d['numbers']) >= PICK]


def compute_acb(history, max_num=MAX_NUM, pick=PICK, window=100):
    recent = history[-window:] if len(history) >= window else history
    counter = Counter()
    for n in range(1, max_num + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers'][:pick]:
            if 1 <= n <= max_num:
                counter[n] += 1
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers'][:pick]:
            if 1 <= n <= max_num:
                last_seen[n] = i
    expected = len(recent) * pick / max_num
    scores = {}
    for n in range(1, max_num + 1):
        fd = expected - counter[n]
        gs = (len(recent) - last_seen.get(n, -1)) / max(len(recent) / 2, 1)
        bb = 1.2 if (n <= 8 or n >= 35) else 1.0
        mb = 1.1 if n % 3 == 0 else 1.0
        scores[n] = (fd * 0.4 + gs * 0.6) * bb * mb
    return scores


def compute_microfish(history, features, weights, max_num=MAX_NUM, pick=PICK):
    W150 = history[-150:] if len(history) >= 150 else history
    W100 = history[-100:] if len(history) >= 100 else history
    W80 = history[-80:] if len(history) >= 80 else history

    if len(W150) < 10:
        return {n: 0 for n in range(1, max_num + 1)}

    counter_150 = Counter()
    for n in range(1, max_num + 1):
        counter_150[n] = 0
    for d in W150:
        for n in d['numbers'][:pick]:
            if 1 <= n <= max_num:
                counter_150[n] += 1

    even_count = 0
    total_nums = 0
    for d in W80:
        for n in d['numbers'][:pick]:
            if 1 <= n <= max_num:
                total_nums += 1
                if n % 2 == 0:
                    even_count += 1
    even_rate = even_count / max(total_nums, 1)

    appeared_prev = {n: 0 for n in range(1, max_num + 1)}
    appeared_both = {n: 0 for n in range(1, max_num + 1)}
    for i in range(len(W100) - 1):
        curr = set(W100[i]['numbers'][:pick])
        nxt = set(W100[i + 1]['numbers'][:pick])
        for n in range(1, max_num + 1):
            if n in curr:
                appeared_prev[n] += 1
                if n in nxt:
                    appeared_both[n] += 1

    counter_100 = Counter()
    for n in range(1, max_num + 1):
        counter_100[n] = 0
    for d in W100:
        for n in d['numbers'][:pick]:
            if 1 <= n <= max_num:
                counter_100[n] += 1
    expected_100 = len(W100) * pick / max_num
    vals_100 = [counter_100[n] for n in range(1, max_num + 1)]
    std_100 = max(np.std(vals_100), 0.001)

    feat_map = {
        'freq_raw_150': lambda n: float(counter_150[n]),
        'parity_even_boost_80': lambda n: (0.5 - even_rate) if n % 2 == 0 else -(0.5 - even_rate),
        'markov_lag1_100': lambda n: appeared_both[n] / appeared_prev[n] if appeared_prev[n] > 0 else 0.0,
        'nl_sq_freq_deficit_100': lambda n: (expected_100 - counter_100[n]) * abs(expected_100 - counter_100[n]),
        'nl_sqrt_freq_zscore_100': lambda n: math.copysign(
            math.sqrt(abs((counter_100[n] - expected_100) / std_100)),
            counter_100[n] - expected_100),
    }

    scores = {}
    for n in range(1, max_num + 1):
        s = 0.0
        for fi, fname in enumerate(features):
            if fname in feat_map:
                s += weights[fi] * feat_map[fname](n)
        scores[n] = s
    return scores


def pick_top5(scores_dict):
    ranked = sorted(scores_dict, key=lambda x: -scores_dict[x])
    return sorted(ranked[:5])


def check_m2(bet, actual_set):
    return len(set(bet) & actual_set) >= 2


def main():
    print("=" * 60)
    print("  McNemar Gate: MicroFish_1bet vs ACB_1bet")
    print("=" * 60)

    draws = load_draws()
    print(f"  Total draws: {len(draws)}")

    # Load MicroFish genome
    with open(os.path.join(project_root, 'validated_strategy_set.json')) as f:
        vss = json.load(f)
    top = vss['valid'][0]
    mf_features, mf_weights = top['features'], top['weights']
    print(f"  MicroFish genome: {mf_features}")

    # Walk-forward evaluation over last 1600 draws
    T = len(draws)
    n_eval = min(1600, T - 200)
    eval_start = T - n_eval

    mf_hits = []
    acb_hits = []

    print(f"  Evaluating {n_eval} draws (idx {eval_start}..{T-1})...")

    for t in range(eval_start, T):
        hist = draws[max(0, t - 200):t]
        actual = set(draws[t]['numbers'][:PICK])

        # MicroFish prediction
        mf_scores = compute_microfish(hist, mf_features, mf_weights)
        mf_bet = pick_top5(mf_scores)
        mf_hit = check_m2(mf_bet, actual)

        # ACB prediction
        acb_scores = compute_acb(hist)
        acb_bet = pick_top5(acb_scores)
        acb_hit = check_m2(acb_bet, actual)

        mf_hits.append(1 if mf_hit else 0)
        acb_hits.append(1 if acb_hit else 0)

    mf_hits = np.array(mf_hits)
    acb_hits = np.array(acb_hits)

    # McNemar contingency table
    both_hit = np.sum((mf_hits == 1) & (acb_hits == 1))
    mf_only = np.sum((mf_hits == 1) & (acb_hits == 0))
    acb_only = np.sum((mf_hits == 0) & (acb_hits == 1))
    neither = np.sum((mf_hits == 0) & (acb_hits == 0))

    net = mf_only - acb_only

    # McNemar chi-squared (with continuity correction)
    discordant = mf_only + acb_only
    if discordant > 0:
        chi2 = (abs(mf_only - acb_only) - 1) ** 2 / discordant
        # Approximate p-value from chi2 with 1 df
        from scipy.stats import chi2 as chi2_dist
        p_value = 1 - chi2_dist.cdf(chi2, df=1)
    else:
        chi2 = 0
        p_value = 1.0

    # Rates
    mf_rate = np.mean(mf_hits)
    acb_rate = np.mean(acb_hits)
    mf_edge = (mf_rate - BASELINE_RATE) * 100
    acb_edge = (acb_rate - BASELINE_RATE) * 100

    print(f"\n  {'='*50}")
    print(f"  Results (N={n_eval})")
    print(f"  {'='*50}")
    print(f"  MicroFish: rate={mf_rate:.4f} edge={mf_edge:+.2f}%")
    print(f"  ACB:       rate={acb_rate:.4f} edge={acb_edge:+.2f}%")
    print(f"  Baseline:  rate={BASELINE_RATE:.4f}")
    print(f"\n  McNemar Contingency Table:")
    print(f"    Both hit:    {both_hit:4d}")
    print(f"    MF only:     {mf_only:4d}")
    print(f"    ACB only:    {acb_only:4d}")
    print(f"    Neither:     {neither:4d}")
    print(f"    Net (MF-ACB): {net:+d}")
    print(f"\n  McNemar chi2={chi2:.4f}, p={p_value:.6f}")

    # Three-window comparison
    print(f"\n  Three-window comparison:")
    for w in [150, 500, 1500]:
        if w > n_eval:
            w = n_eval
        mf_w = np.mean(mf_hits[-w:])
        acb_w = np.mean(acb_hits[-w:])
        print(f"    {w:4d}p: MF={mf_w:.4f}({(mf_w-BASELINE_RATE)*100:+.2f}%) "
              f"ACB={acb_w:.4f}({(acb_w-BASELINE_RATE)*100:+.2f}%) "
              f"delta={((mf_w-acb_w)*100):+.2f}%")

    # Gate decision
    print(f"\n  {'='*50}")
    print(f"  GATE DECISION")
    print(f"  {'='*50}")
    gate_net = net >= 20
    gate_p = p_value < 0.05
    print(f"  Net >= +20:   {'PASS' if gate_net else 'FAIL'} (net={net:+d})")
    print(f"  p < 0.05:     {'PASS' if gate_p else 'FAIL'} (p={p_value:.6f})")
    if gate_net and gate_p:
        print(f"  --> GATE PASSED: MicroFish formally replaces ACB as 1-bet primary")
    else:
        print(f"  --> GATE FAILED: Cannot formally replace; maintain ACB as 1-bet primary")

    # Save results
    result = {
        'test': 'McNemar_MicroFish_vs_ACB_1bet',
        'n_eval': n_eval,
        'microfish': {'rate': float(mf_rate), 'edge_pct': float(mf_edge)},
        'acb': {'rate': float(acb_rate), 'edge_pct': float(acb_edge)},
        'baseline_rate': float(BASELINE_RATE),
        'mcnemar': {
            'both_hit': int(both_hit),
            'mf_only': int(mf_only),
            'acb_only': int(acb_only),
            'neither': int(neither),
            'net': int(net),
            'chi2': float(chi2),
            'p_value': float(p_value),
        },
        'gate': {
            'net_threshold': 20,
            'p_threshold': 0.05,
            'net_pass': bool(gate_net),
            'p_pass': bool(gate_p),
            'overall': bool(gate_net and gate_p),
        },
    }

    out_path = os.path.join(project_root, 'mcnemar_microfish_vs_acb_results.json')
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\n  Results saved: {out_path}")


if __name__ == '__main__':
    main()
