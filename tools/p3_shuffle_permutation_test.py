#!/usr/bin/env python3
"""
P3 Shuffle Permutation Test — Adversarial Validation
=====================================================
Destroy temporal order by shuffling draw assignments, then re-run strategy.
If edge persists → artifact (overfitting to data distribution, not temporal signal).
If edge disappears → real temporal signal exists.

Protocol:
  1. Take real draws and compute real edge (strategy vs baseline)
  2. Shuffle: randomly reassign which numbers belong to which draw position
     (preserves marginal distribution, destroys temporal structure)
  3. Run same strategy on shuffled data → compute shuffled edge
  4. Repeat N times → build null distribution of edges
  5. Permutation p-value = fraction of shuffled edges >= real edge

Results (2026-02-17):
  Big Lotto TS3+Markov4 (500 periods, 20 shuffles):
    Real edge: +2.37%
    Shuffle mean: +0.17%, std: 1.22%
    Permutation p-value: 0.050 (borderline)
    Cohen's d: 1.80
    Verdict: SIGNAL DETECTED (borderline)

  Power Lotto PowerPrecision 3bet (500 periods, 20 shuffles):
    Real edge: +2.43%
    Shuffle mean: +0.38%, std: 1.60%
    Permutation p-value: 0.100 (marginal)
    Cohen's d: 1.28
    Verdict: MARGINAL

Usage:
    python3 tools/p3_shuffle_permutation_test.py
    python3 tools/p3_shuffle_permutation_test.py --lottery BIG_LOTTO --shuffles 50
    python3 tools/p3_shuffle_permutation_test.py --lottery POWER_LOTTO --shuffles 50
"""
import os
import sys
import time
import json
import argparse
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

# ============================================================
# Constants
# ============================================================
SEED = 42

# Big Lotto
BL_MAX_NUM = 49
BL_PICK = 6
BL_P_SINGLE = 0.0186
BL_BASELINES = {n: 1 - (1 - BL_P_SINGLE) ** n for n in range(1, 8)}

# Power Lotto
PL_MAX_NUM = 38
PL_PICK = 6
PL_P_SINGLE = 0.0387
PL_BASELINES = {n: 1 - (1 - PL_P_SINGLE) ** n for n in range(1, 8)}

MIN_HISTORY = 200

# ============================================================
# Big Lotto TS3+Markov4 Strategy
# ============================================================
def bl_fourier_rhythm_bet(history, window=500):
    MAX_NUM = BL_MAX_NUM
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    bitstreams = {i: np.zeros(w) for i in range(1, MAX_NUM + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= MAX_NUM:
                bitstreams[n][idx] = 1
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bh = bitstreams[n]
        if sum(bh) < 2:
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
    sorted_idx = np.argsort(scores[1:])[::-1] + 1
    return sorted(sorted_idx[:6].tolist())


def bl_cold_numbers_bet(history, window=100, exclude=None):
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    candidates = [n for n in range(1, BL_MAX_NUM + 1) if n not in exclude]
    return sorted(sorted(candidates, key=lambda x: freq.get(x, 0))[:6])


def bl_tail_balance_bet(history, window=100, exclude=None):
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    tail_groups = {i: [] for i in range(10)}
    for n in range(1, BL_MAX_NUM + 1):
        if n not in exclude:
            tail_groups[n % 10].append((n, freq.get(n, 0)))
    for t in tail_groups:
        tail_groups[t].sort(key=lambda x: x[1], reverse=True)
    selected = []
    available_tails = sorted(
        [t for t in range(10) if tail_groups[t]],
        key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0,
        reverse=True
    )
    idx_in_group = {t: 0 for t in range(10)}
    while len(selected) < 6:
        added = False
        for tail in available_tails:
            if len(selected) >= 6:
                break
            if idx_in_group[tail] < len(tail_groups[tail]):
                num, _ = tail_groups[tail][idx_in_group[tail]]
                if num not in selected:
                    selected.append(num)
                    added = True
                idx_in_group[tail] += 1
        if not added:
            break
    if len(selected) < 6:
        remaining = [n for n in range(1, BL_MAX_NUM + 1) if n not in selected and n not in exclude]
        remaining.sort(key=lambda x: freq.get(x, 0), reverse=True)
        selected.extend(remaining[:6 - len(selected)])
    return sorted(selected[:6])


def bl_markov_orthogonal_bet(history, exclude=None, markov_window=30):
    exclude = exclude or set()
    window = min(markov_window, len(history))
    recent = history[-window:]
    transitions = Counter()
    for i in range(len(recent) - 1):
        for p in recent[i]['numbers']:
            for n in recent[i + 1]['numbers']:
                transitions[(p, n)] += 1
    if len(history) < 2:
        candidates = [n for n in range(1, BL_MAX_NUM + 1) if n not in exclude]
        return sorted(candidates[:6])
    scores = Counter()
    for prev_num in history[-1]['numbers']:
        for n in range(1, BL_MAX_NUM + 1):
            scores[n] += transitions.get((prev_num, n), 0)
    candidates = [(n, scores[n]) for n in range(1, BL_MAX_NUM + 1) if n not in exclude]
    candidates.sort(key=lambda x: -x[1])
    selected = [n for n, _ in candidates[:6]]
    if len(selected) < 6:
        remaining = [n for n in range(1, BL_MAX_NUM + 1) if n not in exclude and n not in selected]
        selected.extend(remaining[:6 - len(selected)])
    return sorted(selected[:6])


def bl_ts3_markov4(history):
    bet1 = bl_fourier_rhythm_bet(history)
    bet2 = bl_cold_numbers_bet(history, exclude=set(bet1))
    bet3 = bl_tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    ts3_used = set(bet1) | set(bet2) | set(bet3)
    bet4 = bl_markov_orthogonal_bet(history, exclude=ts3_used, markov_window=30)
    return [bet1, bet2, bet3, bet4]


def bl_freq_orthogonal_bet(history, window=200, exclude=None):
    """5th bet: Frequency Orthogonal — highest frequency from remaining pool"""
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    candidates = [(n, freq.get(n, 0)) for n in range(1, BL_MAX_NUM + 1) if n not in exclude]
    candidates.sort(key=lambda x: -x[1])
    return sorted([n for n, _ in candidates[:6]])


def bl_ts3_markov4_freqortho5(history):
    """Big Lotto PRODUCTION 5-bet: TS3+Markov+FreqOrtho"""
    bet1 = bl_fourier_rhythm_bet(history)
    bet2 = bl_cold_numbers_bet(history, exclude=set(bet1))
    bet3 = bl_tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    ts3_used = set(bet1) | set(bet2) | set(bet3)
    bet4 = bl_markov_orthogonal_bet(history, exclude=ts3_used, markov_window=30)
    used_4 = ts3_used | set(bet4)
    bet5 = bl_freq_orthogonal_bet(history, window=200, exclude=used_4)
    return [bet1, bet2, bet3, bet4, bet5]


# ============================================================
# Power Lotto PowerPrecision 3bet Strategy
# ============================================================
def pl_fourier_rhythm_bet(history, window=500, top_n=6, skip=0):
    MAX_NUM = PL_MAX_NUM
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    bitstreams = {i: np.zeros(w) for i in range(1, MAX_NUM + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= MAX_NUM:
                bitstreams[n][idx] = 1
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bh = bitstreams[n]
        if sum(bh) < 2:
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
    sorted_idx = np.argsort(scores[1:])[::-1] + 1
    return sorted(sorted_idx[skip:skip + top_n].tolist())


def pl_lag2_echo_bet(history, window=100, exclude=None):
    exclude = exclude or set()
    if len(history) < 3:
        candidates = [n for n in range(1, PL_MAX_NUM + 1) if n not in exclude]
        return sorted(candidates[:6])
    lag2_draw = history[-2]['numbers']
    freq = Counter(n for d in history[-window:] for n in d['numbers'])
    scored = []
    for n in lag2_draw:
        if n not in exclude and n <= PL_MAX_NUM:
            scored.append((n, freq.get(n, 0) + 10))
    remaining = [(n, freq.get(n, 0)) for n in range(1, PL_MAX_NUM + 1)
                 if n not in exclude and n not in [x[0] for x in scored]]
    remaining.sort(key=lambda x: -x[1])
    all_candidates = scored + remaining
    return sorted([n for n, _ in all_candidates[:6]])


def pl_power_precision_3bet(history):
    bet1 = pl_fourier_rhythm_bet(history, window=500, top_n=6, skip=0)
    bet2 = pl_fourier_rhythm_bet(history, window=500, top_n=6, skip=6)
    used = set(bet1) | set(bet2)
    bet3 = pl_lag2_echo_bet(history, window=100, exclude=used)
    return [bet1, bet2, bet3]


# ============================================================
# Shuffle Engine
# ============================================================
def shuffle_draws(draws, rng):
    """
    Shuffle draw assignments: keep all number sets, randomly reassign
    which set belongs to which draw position.
    This preserves the marginal distribution of numbers but destroys
    temporal structure.
    """
    shuffled = []
    number_sets = [d['numbers'][:] for d in draws]
    rng.shuffle(number_sets)
    for i, d in enumerate(draws):
        new_d = dict(d)
        new_d['numbers'] = number_sets[i]
        shuffled.append(new_d)
    return shuffled


def run_single_backtest(draws, strategy_func, n_bets, n_periods, p_single):
    baseline = 1 - (1 - p_single) ** n_bets
    start_idx = max(MIN_HISTORY, len(draws) - n_periods)

    hits = 0
    total = 0

    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        history = draws[:i]

        try:
            bets = strategy_func(history)
        except Exception:
            total += 1
            continue

        any_hit = False
        for b in bets:
            if len(set(b) & target) >= 3:
                any_hit = True
                break

        if any_hit:
            hits += 1
        total += 1

    win_rate = hits / total if total > 0 else 0
    edge = win_rate - baseline
    return {
        'total': total,
        'hits': hits,
        'win_rate': win_rate,
        'baseline': baseline,
        'edge': edge,
    }


# ============================================================
# Permutation Test
# ============================================================
def run_permutation_test(draws, strategy_func, n_bets, n_periods, p_single,
                         n_shuffles=20, seed=42):
    # 1. Real edge
    real_result = run_single_backtest(draws, strategy_func, n_bets, n_periods, p_single)
    real_edge = real_result['edge']

    # 2. Shuffled edges
    rng = np.random.RandomState(seed)
    shuffle_edges = []
    for s in range(n_shuffles):
        shuffled = shuffle_draws(draws, rng)
        sr = run_single_backtest(shuffled, strategy_func, n_bets, n_periods, p_single)
        shuffle_edges.append(sr['edge'])

    # 3. Permutation p-value
    n_greater = sum(1 for se in shuffle_edges if se >= real_edge)
    p_value = (n_greater + 1) / (n_shuffles + 1)  # Conservative adjustment

    # 4. Cohen's d
    shuffle_mean = np.mean(shuffle_edges)
    shuffle_std = np.std(shuffle_edges) if np.std(shuffle_edges) > 0 else 0.001
    cohens_d = (real_edge - shuffle_mean) / shuffle_std

    return {
        'real_edge': real_edge,
        'real_result': real_result,
        'shuffle_edges': shuffle_edges,
        'shuffle_mean': shuffle_mean,
        'shuffle_std': shuffle_std,
        'p_value': p_value,
        'cohens_d': cohens_d,
        'n_shuffles': n_shuffles,
    }


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='P3 Shuffle Permutation Test')
    parser.add_argument('--lottery', type=str, default='BOTH',
                       choices=['BIG_LOTTO', 'POWER_LOTTO', 'BOTH'],
                       help='Which lottery to test')
    parser.add_argument('--shuffles', type=int, default=200,
                       help='Number of shuffle permutations (default: 200)')
    parser.add_argument('--periods', type=int, default=1500,
                       help='Backtest periods (default: 1500)')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)

    print("=" * 80)
    print("  P3 Shuffle Permutation Test — Adversarial Validation")
    print("=" * 80)
    print(f"  Shuffles: {args.shuffles}")
    print(f"  Periods: {args.periods}")
    print(f"  Seed: {args.seed}")
    print("=" * 80)

    results = {}

    # ====== Big Lotto ======
    if args.lottery in ['BIG_LOTTO', 'BOTH']:
        bl_draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))

        # --- 5-bet (PRODUCTION) ---
        print("\n" + "=" * 80)
        print("  Big Lotto: TS3+Markov+FreqOrtho (5-bet PRODUCTION)")
        print("=" * 80)
        print(f"  Draws: {len(bl_draws)}")

        t0 = time.time()
        bl5_result = run_permutation_test(
            bl_draws, bl_ts3_markov4_freqortho5, 5, args.periods,
            BL_P_SINGLE, args.shuffles, args.seed
        )
        elapsed = time.time() - t0

        print(f"\n  Real edge:     {bl5_result['real_edge']*100:+.2f}%")
        print(f"  Shuffle mean:  {bl5_result['shuffle_mean']*100:+.2f}%")
        print(f"  Shuffle std:   {bl5_result['shuffle_std']*100:.2f}%")
        print(f"  Permutation p: {bl5_result['p_value']:.4f}")
        print(f"  Cohen's d:     {bl5_result['cohens_d']:.2f}")
        print(f"  Time: {elapsed:.1f}s")

        if bl5_result['p_value'] <= 0.05:
            verdict = "SIGNAL DETECTED"
        elif bl5_result['p_value'] <= 0.10:
            verdict = "MARGINAL"
        else:
            verdict = "NO SIGNAL (likely artifact)"
        print(f"  Verdict: {verdict}")

        # Show histogram summary (not all 200 lines)
        edges_sorted = sorted(bl5_result['shuffle_edges'])
        print(f"\n  Shuffle distribution summary (n={args.shuffles}):")
        print(f"    Min: {min(edges_sorted)*100:+.2f}%")
        print(f"    25%: {np.percentile(edges_sorted, 25)*100:+.2f}%")
        print(f"    50%: {np.percentile(edges_sorted, 50)*100:+.2f}%")
        print(f"    75%: {np.percentile(edges_sorted, 75)*100:+.2f}%")
        print(f"    95%: {np.percentile(edges_sorted, 95)*100:+.2f}%")
        print(f"    Max: {max(edges_sorted)*100:+.2f}%")
        print(f"    Real: {bl5_result['real_edge']*100:+.2f}% (rank: top {bl5_result['p_value']*100:.1f}%)")

        results['BIG_LOTTO_5BET'] = bl5_result

        # --- 4-bet (reference) ---
        print("\n" + "-" * 80)
        print("  Big Lotto: TS3+Markov4 (4-bet reference)")
        print("-" * 80)

        t0 = time.time()
        bl4_result = run_permutation_test(
            bl_draws, bl_ts3_markov4, 4, args.periods,
            BL_P_SINGLE, args.shuffles, args.seed
        )
        elapsed = time.time() - t0

        print(f"\n  Real edge:     {bl4_result['real_edge']*100:+.2f}%")
        print(f"  Shuffle mean:  {bl4_result['shuffle_mean']*100:+.2f}%")
        print(f"  Shuffle std:   {bl4_result['shuffle_std']*100:.2f}%")
        print(f"  Permutation p: {bl4_result['p_value']:.4f}")
        print(f"  Cohen's d:     {bl4_result['cohens_d']:.2f}")
        print(f"  Time: {elapsed:.1f}s")

        if bl4_result['p_value'] <= 0.05:
            verdict = "SIGNAL DETECTED"
        elif bl4_result['p_value'] <= 0.10:
            verdict = "MARGINAL"
        else:
            verdict = "NO SIGNAL (likely artifact)"
        print(f"  Verdict: {verdict}")

        results['BIG_LOTTO_4BET'] = bl4_result

    # ====== Power Lotto ======
    if args.lottery in ['POWER_LOTTO', 'BOTH']:
        print("\n" + "=" * 80)
        print("  Power Lotto: PowerPrecision (3-bet)")
        print("=" * 80)

        pl_draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
        print(f"  Draws: {len(pl_draws)}")

        t0 = time.time()
        pl_result = run_permutation_test(
            pl_draws, pl_power_precision_3bet, 3, args.periods,
            PL_P_SINGLE, args.shuffles, args.seed
        )
        elapsed = time.time() - t0

        print(f"\n  Real edge:     {pl_result['real_edge']*100:+.2f}%")
        print(f"  Shuffle mean:  {pl_result['shuffle_mean']*100:+.2f}%")
        print(f"  Shuffle std:   {pl_result['shuffle_std']*100:.2f}%")
        print(f"  Permutation p: {pl_result['p_value']:.4f}")
        print(f"  Cohen's d:     {pl_result['cohens_d']:.2f}")
        print(f"  Time: {elapsed:.1f}s")

        if pl_result['p_value'] <= 0.05:
            verdict = "SIGNAL DETECTED"
        elif pl_result['p_value'] <= 0.10:
            verdict = "MARGINAL"
        else:
            verdict = "NO SIGNAL (likely artifact)"
        print(f"  Verdict: {verdict}")

        edges_sorted = sorted(pl_result['shuffle_edges'])
        print(f"\n  Shuffle distribution summary (n={args.shuffles}):")
        print(f"    Min: {min(edges_sorted)*100:+.2f}%")
        print(f"    25%: {np.percentile(edges_sorted, 25)*100:+.2f}%")
        print(f"    50%: {np.percentile(edges_sorted, 50)*100:+.2f}%")
        print(f"    75%: {np.percentile(edges_sorted, 75)*100:+.2f}%")
        print(f"    95%: {np.percentile(edges_sorted, 95)*100:+.2f}%")
        print(f"    Max: {max(edges_sorted)*100:+.2f}%")
        print(f"    Real: {pl_result['real_edge']*100:+.2f}% (rank: top {pl_result['p_value']*100:.1f}%)")

        results['POWER_LOTTO'] = pl_result

    # ====== Summary ======
    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80)

    for lottery, r in results.items():
        p = r['p_value']
        d = r['cohens_d']
        if p <= 0.05:
            verdict = "SIGNAL DETECTED"
        elif p <= 0.10:
            verdict = "MARGINAL"
        else:
            verdict = "NO SIGNAL"
        print(f"  {lottery:<20s}: p={p:.4f}, d={d:.2f}, verdict={verdict}")

    print("\n  Interpretation Guide:")
    print("    p <= 0.05: Real edge significantly exceeds shuffle distribution")
    print("    p 0.05-0.10: Borderline — temporal signal may exist")
    print("    p > 0.10: Edge is likely a distributional artifact")
    print("    Cohen's d > 0.8: Large effect size")
    print("    Cohen's d 0.5-0.8: Medium effect size")
    print("    Cohen's d < 0.5: Small effect size")

    # Save results
    output = {
        'date': '2026-02-17',
        'protocol': 'P3 Shuffle Permutation Test',
        'parameters': {
            'n_shuffles': args.shuffles,
            'n_periods': args.periods,
            'seed': args.seed,
        },
    }
    for lottery, r in results.items():
        output[lottery] = {
            'real_edge': round(r['real_edge'] * 100, 2),
            'shuffle_mean': round(r['shuffle_mean'] * 100, 2),
            'shuffle_std': round(r['shuffle_std'] * 100, 2),
            'p_value': round(r['p_value'], 3),
            'cohens_d': round(r['cohens_d'], 2),
            'shuffle_edges': [round(se * 100, 2) for se in r['shuffle_edges']],
        }

    out_path = os.path.join(project_root, 'docs', 'P3_SHUFFLE_PERMUTATION_RESULTS.json')
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {out_path}")


if __name__ == '__main__':
    main()
