#!/usr/bin/env python3
"""
Strategy Space Exploration Research Engine
==========================================
2026-03-15 | DAILY_539 | Beyond signal discovery

4 Research Objectives:
  1. Coverage Matrix Optimization (pool-based subset selection)
  2. Strategy Diversity Analysis (cross-signal pool merging)
  3. Long-Horizon Risk Simulation (10M MC)
  4. Portfolio Efficiency Frontier (1-6 bets)

Reuses precomputed signal infrastructure from strategy_evolution_medium.py.
"""

import os
import sys
import json
import math
import time
import numpy as np
from collections import Counter
from itertools import combinations

SEED = 42
np.random.seed(SEED)
rng = np.random.default_rng(SEED)

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

MAX_NUM = 39
PICK = 5
TOTAL_COMBOS = math.comb(MAX_NUM, PICK)
BASELINE_RATE = sum(
    math.comb(PICK, m) * math.comb(MAX_NUM - PICK, PICK - m)
    for m in range(2, PICK + 1)
) / TOTAL_COMBOS  # ≈ 0.1140

# Correct prize table (L64 verified)
PRIZES = {2: 50, 3: 300, 4: 20000, 5: 8_000_000}
COST = 50

WINDOWS = [150, 500, 1500]
N_PERM = 99
SIGNAL_NAMES = ['microfish', 'midfreq', 'markov', 'acb']


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


# ============================================================
# Data loading
# ============================================================

def load_draws():
    from database import DatabaseManager
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    draws = sorted(db.get_all_draws('DAILY_539'), key=lambda x: (x['date'], x['draw']))
    return [d for d in draws if d.get('numbers') and len(d['numbers']) >= PICK]


def load_microfish_genome():
    with open(os.path.join(project_root, 'validated_strategy_set.json')) as f:
        vss = json.load(f)
    top = vss['valid'][0]
    return top['features'], top['weights']


# ============================================================
# Signal scoring functions (from strategy_evolution_medium.py)
# ============================================================

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
    scores = np.zeros(max_num)
    for n in range(1, max_num + 1):
        fd = expected - counter[n]
        gs = (len(recent) - last_seen.get(n, -1)) / max(len(recent) / 2, 1)
        bb = 1.2 if (n <= 8 or n >= 35) else 1.0
        mb = 1.1 if n % 3 == 0 else 1.0
        scores[n - 1] = (fd * 0.4 + gs * 0.6) * bb * mb
    return scores


def compute_midfreq(history, max_num=MAX_NUM, pick=PICK, window=100):
    recent = history[-window:] if len(history) >= window else history
    counter = Counter()
    for n in range(1, max_num + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers'][:pick]:
            if 1 <= n <= max_num:
                counter[n] += 1
    expected = len(recent) * pick / max_num
    max_dev = max(abs(counter[n] - expected) for n in range(1, max_num + 1))
    if max_dev == 0:
        max_dev = 1
    scores = np.zeros(max_num)
    for n in range(1, max_num + 1):
        scores[n - 1] = max_dev - abs(counter[n] - expected)
    return scores


def compute_markov(history, max_num=MAX_NUM, pick=PICK, window=30):
    recent = history[-window:] if len(history) >= window else history
    trans = {}
    for i in range(len(recent) - 1):
        curr = set(recent[i]['numbers'][:pick])
        nxt = set(recent[i + 1]['numbers'][:pick])
        for p in curr:
            if p not in trans:
                trans[p] = Counter()
            for n in nxt:
                if 1 <= n <= max_num:
                    trans[p][n] += 1
    last_draw = set(recent[-1]['numbers'][:pick]) if recent else set()
    scores = np.zeros(max_num)
    for p in last_draw:
        if p in trans and sum(trans[p].values()) > 0:
            total = sum(trans[p].values())
            for n in range(1, max_num + 1):
                scores[n - 1] += trans[p].get(n, 0) / total
    return scores


def compute_microfish(history, features, weights, max_num=MAX_NUM, pick=PICK):
    W150 = history[-150:] if len(history) >= 150 else history
    W100 = history[-100:] if len(history) >= 100 else history
    W80 = history[-80:] if len(history) >= 80 else history

    if len(W150) < 10:
        return np.zeros(max_num)

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

    scores = np.zeros(max_num)
    for n in range(1, max_num + 1):
        s = 0.0
        for fi, fname in enumerate(features):
            if fname in feat_map:
                s += weights[fi] * feat_map[fname](n)
        scores[n - 1] = s
    return scores


# ============================================================
# Precompute signals
# ============================================================

def precompute_signals(draws, mf_features, mf_weights, start_idx=500):
    T = len(draws)
    actual_start = max(start_idx, T - 1600)
    n_eval = T - actual_start
    print(f"  Precomputing signals for {n_eval} draws (idx {actual_start}..{T-1})...")

    sig_mf = np.zeros((n_eval, MAX_NUM))
    sig_mid = np.zeros((n_eval, MAX_NUM))
    sig_markov = np.zeros((n_eval, MAX_NUM))
    sig_acb = np.zeros((n_eval, MAX_NUM))
    actuals = np.zeros((n_eval, MAX_NUM), dtype=bool)

    t0 = time.time()
    for idx, t in enumerate(range(actual_start, T)):
        hist_slice = draws[max(0, t - 200):t]
        sig_mf[idx] = compute_microfish(hist_slice, mf_features, mf_weights)
        sig_mid[idx] = compute_midfreq(hist_slice)
        sig_markov[idx] = compute_markov(hist_slice)
        sig_acb[idx] = compute_acb(hist_slice)

        actual = set(draws[t]['numbers'][:PICK])
        for n in actual:
            if 1 <= n <= MAX_NUM:
                actuals[idx, n - 1] = True

        if (idx + 1) % 200 == 0:
            elapsed = time.time() - t0
            print(f"    {idx+1}/{n_eval} done ({elapsed:.1f}s)")

    elapsed = time.time() - t0
    print(f"  Signal precomputation complete: {elapsed:.1f}s")
    return sig_mf, sig_mid, sig_markov, sig_acb, actuals, actual_start


# ============================================================
# Helpers
# ============================================================

def pick_top_indices(scores, k, exclude=None):
    """Return top-k indices (0-based) from score array, excluding given indices."""
    exclude = exclude or set()
    ranked = np.argsort(-scores)
    result = []
    for idx in ranked:
        if idx in exclude:
            continue
        result.append(idx)
        if len(result) >= k:
            break
    return result


def check_m2_hit(bet_indices, actual_row):
    """Check if a bet (list of 0-based indices) has M2+ match against actual."""
    return sum(actual_row[i] for i in bet_indices) >= 2


def check_any_m2_hit(bets, actual_row):
    """Check if any bet in list has M2+ match."""
    for bet in bets:
        if sum(actual_row[i] for i in bet) >= 2:
            return True
    return False


def count_matches(bet_indices, actual_row):
    """Count how many numbers in a bet match actual draw."""
    return sum(actual_row[i] for i in bet_indices)


def compute_payout(bet_indices, actual_row):
    """Compute payout for a single bet given actual draw."""
    m = count_matches(bet_indices, actual_row)
    return PRIZES.get(m, 0)


def three_window_eval(hit_details, windows=WINDOWS):
    """Compute edge for each window from end of hit_details array."""
    results = {}
    n = len(hit_details)
    for w in windows:
        if w > n:
            w = n
        segment = hit_details[-w:]
        rate = np.mean(segment)
        edge = rate - BASELINE_RATE
        z = edge / max(np.sqrt(BASELINE_RATE * (1 - BASELINE_RATE) / w), 1e-9)
        results[w] = {'rate': float(rate), 'edge_pct': float(edge * 100),
                      'edge_raw': float(edge), 'z': float(z)}
    return results


def three_window_eval_multi(hit_details, n_bets, windows=WINDOWS):
    """Three-window eval for multi-bet (baseline = 1-(1-p)^n)."""
    baseline = 1 - (1 - BASELINE_RATE) ** n_bets
    results = {}
    n = len(hit_details)
    for w in windows:
        if w > n:
            w = n
        segment = hit_details[-w:]
        rate = np.mean(segment)
        edge = rate - baseline
        z = edge / max(np.sqrt(baseline * (1 - baseline) / w), 1e-9)
        results[w] = {'rate': float(rate), 'edge_pct': float(edge * 100),
                      'edge_raw': float(edge), 'z': float(z),
                      'baseline': float(baseline)}
    return results


# ============================================================
# OBJECTIVE 1: Coverage Matrix Optimization
# ============================================================

def objective1_coverage_matrix(sigs, actuals, draws, eval_start_offset):
    print("\n" + "=" * 72)
    print("  OBJECTIVE 1: Coverage Matrix Optimization")
    print("  Pool-based subset selection vs direct top-5")
    print("=" * 72)

    n_eval = len(actuals)
    sig_list = [sigs[0], sigs[1], sigs[2], sigs[3]]
    sig_names = SIGNAL_NAMES

    # Historical sum statistics for sum constraint
    all_sums = []
    for d in draws:
        nums = [n for n in d['numbers'][:PICK] if 1 <= n <= MAX_NUM]
        if len(nums) == PICK:
            all_sums.append(sum(nums))
    sum_mu = np.mean(all_sums[-500:]) if len(all_sums) >= 500 else np.mean(all_sums)
    sum_sigma = np.std(all_sums[-500:]) if len(all_sums) >= 500 else np.std(all_sums)

    pool_sizes = [5, 7, 9, 12]
    results = {'single_signal': [], 'multi_bet': []}

    # --- Part A: Single signal, varying pool sizes ---
    print("\n  Part A: Single signal pool optimization")
    for si, sname in enumerate(sig_names):
        for ps in pool_sizes:
            hit_details = []
            diff_count = 0

            for t in range(n_eval):
                scores = sig_list[si][t].copy()

                if ps == 5:
                    # Direct top-5
                    bet = pick_top_indices(scores, 5)
                else:
                    # Pool-based: get top-ps, then find best C(ps,5) subset
                    pool = pick_top_indices(scores, ps)
                    best_bet = None
                    best_quality = -1e18

                    for combo in combinations(pool, 5):
                        # Quality = sum of signal scores
                        q = sum(scores[i] for i in combo)
                        # Sum constraint penalty
                        s = sum(i + 1 for i in combo)  # 1-based numbers
                        sum_penalty = -0.1 * abs(s - sum_mu) / max(sum_sigma, 1)
                        # Zone diversity penalty
                        zones = [min(i // 13, 2) for i in combo]
                        zone_counts = Counter(zones)
                        zone_penalty = -0.2 * max(0, max(zone_counts.values()) - 2)
                        q += sum_penalty + zone_penalty

                        if q > best_quality:
                            best_quality = q
                            best_bet = list(combo)

                    # Track how often pool selection differs from direct top-5
                    direct = set(pick_top_indices(scores, 5))
                    if set(best_bet) != direct:
                        diff_count += 1
                    bet = best_bet

                hit = check_m2_hit(bet, actuals[t])
                hit_details.append(1 if hit else 0)

            hit_details = np.array(hit_details)
            tw = three_window_eval(hit_details)
            diff_pct = diff_count / n_eval * 100 if ps > 5 else 0.0

            entry = {
                'signal': sname, 'pool_size': ps,
                'edge_1500p': tw[1500]['edge_pct'] if 1500 in tw else tw[max(tw.keys())]['edge_pct'],
                'rate_1500p': tw[1500]['rate'] if 1500 in tw else tw[max(tw.keys())]['rate'],
                'z_1500p': tw[1500]['z'] if 1500 in tw else tw[max(tw.keys())]['z'],
                'three_window': tw,
                'diff_from_direct_pct': diff_pct,
            }
            results['single_signal'].append(entry)

            tw_1500 = tw.get(1500, tw[max(tw.keys())])
            print(f"    {sname:10s} pool={ps:2d}: "
                  f"edge={tw_1500['edge_pct']:+.2f}% "
                  f"z={tw_1500['z']:.2f} "
                  f"diff={diff_pct:.1f}%")

    # --- Part B: Multi-bet pool optimization ---
    print("\n  Part B: Multi-bet pool optimization (3-bet)")
    # Signal assignment for 3-bet: MicroFish, MidFreq, Markov
    multi_bet_sigs = [0, 1, 2]  # indices into sig_list
    multi_bet_names = ['microfish', 'midfreq', 'markov']

    for ps in [5, 7, 9, 12]:
        hit_details = []
        for t in range(n_eval):
            bets = []
            excluded = set()

            for bi, si in enumerate(multi_bet_sigs):
                scores = sig_list[si][t].copy()

                if ps == 5:
                    bet = pick_top_indices(scores, 5, exclude=excluded)
                else:
                    pool = pick_top_indices(scores, ps + len(excluded), exclude=None)
                    # Remove excluded from pool
                    pool = [p for p in pool if p not in excluded][:ps]
                    if len(pool) < 5:
                        # Fallback: just pick top-5 excluding used
                        bet = pick_top_indices(scores, 5, exclude=excluded)
                    else:
                        best_bet = None
                        best_quality = -1e18
                        for combo in combinations(pool, 5):
                            q = sum(scores[i] for i in combo)
                            s = sum(i + 1 for i in combo)
                            sum_penalty = -0.1 * abs(s - sum_mu) / max(sum_sigma, 1)
                            zones = [min(i // 13, 2) for i in combo]
                            zone_counts = Counter(zones)
                            zone_penalty = -0.2 * max(0, max(zone_counts.values()) - 2)
                            q += sum_penalty + zone_penalty
                            if q > best_quality:
                                best_quality = q
                                best_bet = list(combo)
                        bet = best_bet

                bets.append(bet)
                excluded.update(bet)

            hit = check_any_m2_hit(bets, actuals[t])
            hit_details.append(1 if hit else 0)

        hit_details = np.array(hit_details)
        tw = three_window_eval_multi(hit_details, 3)
        tw_1500 = tw.get(1500, tw[max(tw.keys())])

        entry = {
            'config': f'3bet_pool{ps}',
            'pool_size': ps,
            'edge_1500p': tw_1500['edge_pct'],
            'rate_1500p': tw_1500['rate'],
            'z_1500p': tw_1500['z'],
            'baseline': tw_1500['baseline'],
            'three_window': tw,
        }
        results['multi_bet'].append(entry)
        print(f"    3-bet pool={ps:2d}: "
              f"rate={tw_1500['rate']:.2%} edge={tw_1500['edge_pct']:+.2f}% "
              f"z={tw_1500['z']:.2f}")

    return results


# ============================================================
# OBJECTIVE 2: Strategy Diversity Analysis
# ============================================================

def objective2_diversity(sigs, actuals):
    print("\n" + "=" * 72)
    print("  OBJECTIVE 2: Strategy Diversity Analysis")
    print("  Cross-signal pool merging")
    print("=" * 72)

    n_eval = len(actuals)
    sig_list = [sigs[0], sigs[1], sigs[2], sigs[3]]

    configs = [
        {'name': 'current_orthogonal', 'signal_indices': [0, 1, 2], 'top_k': 5, 'method': 'independent'},
        {'name': 'union_top7_x3', 'signal_indices': [0, 1, 2], 'top_k': 7, 'method': 'union_greedy'},
        {'name': 'union_top9_x3', 'signal_indices': [0, 1, 2], 'top_k': 9, 'method': 'union_greedy'},
        {'name': 'union_top5_x4', 'signal_indices': [0, 1, 2, 3], 'top_k': 5, 'method': 'union_greedy'},
        {'name': 'union_top7_x4', 'signal_indices': [0, 1, 2, 3], 'top_k': 7, 'method': 'union_greedy'},
        {'name': 'max_coverage', 'signal_indices': [0, 1, 2], 'top_k': 9, 'method': 'max_coverage'},
    ]

    results = []
    for cfg in configs:
        hit_details = []
        overlap_counts = []
        unique_counts = []

        for t in range(n_eval):
            if cfg['method'] == 'independent':
                # Current architecture: each signal independently selects top-5
                bets = []
                excluded = set()
                for si in cfg['signal_indices']:
                    bet = pick_top_indices(sig_list[si][t].copy(), 5, exclude=excluded)
                    bets.append(bet)
                    excluded.update(bet)
            elif cfg['method'] == 'union_greedy':
                # Merge all signal top-K into super-pool, then greedily construct bets
                super_pool = set()
                pool_scores = {}
                for si in cfg['signal_indices']:
                    top_k = pick_top_indices(sig_list[si][t].copy(), cfg['top_k'])
                    for idx in top_k:
                        super_pool.add(idx)
                        # Use max signal score as the candidate's value
                        if idx not in pool_scores:
                            pool_scores[idx] = sig_list[si][t][idx]
                        else:
                            pool_scores[idx] = max(pool_scores[idx], sig_list[si][t][idx])

                # Count overlap (numbers appearing in multiple signal top-K lists)
                per_signal_sets = []
                for si in cfg['signal_indices']:
                    top_k = pick_top_indices(sig_list[si][t].copy(), cfg['top_k'])
                    per_signal_sets.append(set(top_k))

                if len(per_signal_sets) >= 2:
                    total_overlap = 0
                    for i in range(len(per_signal_sets)):
                        for j in range(i + 1, len(per_signal_sets)):
                            total_overlap += len(per_signal_sets[i] & per_signal_sets[j])
                    overlap_counts.append(total_overlap)

                # Greedy construction: sort by score, assign to bets
                ranked_pool = sorted(super_pool, key=lambda x: -pool_scores[x])
                bets = [[], [], []]
                for idx in ranked_pool:
                    # Assign to first bet that isn't full
                    for b in range(3):
                        if len(bets[b]) < 5:
                            bets[b].append(idx)
                            break
                # Fill any short bets with remaining numbers
                all_used = set(sum(bets, []))
                for b in range(3):
                    if len(bets[b]) < 5:
                        for n in range(MAX_NUM):
                            if n not in all_used and len(bets[b]) < 5:
                                bets[b].append(n)
                                all_used.add(n)
            elif cfg['method'] == 'max_coverage':
                # For each number, compute coverage value = max across signals
                coverage_vals = np.zeros(MAX_NUM)
                for si in cfg['signal_indices']:
                    top_k = pick_top_indices(sig_list[si][t].copy(), cfg['top_k'])
                    for idx in top_k:
                        coverage_vals[idx] = max(coverage_vals[idx], sig_list[si][t][idx])

                # Select top-15 by coverage value, split into 3 bets of 5
                ranked = np.argsort(-coverage_vals)
                top15 = ranked[:15]
                bets = [list(top15[0:5]), list(top15[5:10]), list(top15[10:15])]

            all_nums = set()
            for b in bets:
                all_nums.update(b)
            unique_counts.append(len(all_nums))

            hit = check_any_m2_hit(bets, actuals[t])
            hit_details.append(1 if hit else 0)

        hit_details = np.array(hit_details)
        tw = three_window_eval_multi(hit_details, 3)
        tw_1500 = tw.get(1500, tw[max(tw.keys())])

        entry = {
            'config': cfg['name'],
            'method': cfg['method'],
            'n_signals': len(cfg['signal_indices']),
            'top_k': cfg['top_k'],
            'edge_1500p': tw_1500['edge_pct'],
            'rate_1500p': tw_1500['rate'],
            'z_1500p': tw_1500['z'],
            'three_window': tw,
            'avg_unique_nums': float(np.mean(unique_counts)),
            'avg_overlap': float(np.mean(overlap_counts)) if overlap_counts else 0.0,
        }
        results.append(entry)
        print(f"    {cfg['name']:25s}: "
              f"rate={tw_1500['rate']:.2%} edge={tw_1500['edge_pct']:+.2f}% "
              f"z={tw_1500['z']:.2f} "
              f"unique={entry['avg_unique_nums']:.1f} "
              f"overlap={entry['avg_overlap']:.1f}")

    return results


# ============================================================
# OBJECTIVE 3: Long-Horizon Risk Simulation
# ============================================================

def objective3_risk_simulation():
    print("\n" + "=" * 72)
    print("  OBJECTIVE 3: Long-Horizon Risk Simulation")
    print("  10M Monte Carlo draws")
    print("=" * 72)

    N_SIM = 10_000_000

    # Precompute match probabilities (exact)
    match_probs = {}
    for m in range(PICK + 1):
        match_probs[m] = (math.comb(PICK, m) * math.comb(MAX_NUM - PICK, PICK - m)
                          / TOTAL_COMBOS)

    results = {}

    for n_bets in [1, 2, 3]:
        print(f"\n  Simulating {n_bets}-bet ({N_SIM:,} draws)...")
        t0 = time.time()

        # For each draw, probability of at least one M2+ across n_bets independent bets
        p_hit_baseline = 1 - (1 - BASELINE_RATE) ** n_bets
        cost_per_draw = n_bets * COST

        # --- Simulate match counts ---
        # For each bet, draw match count from the exact distribution
        match_values = np.arange(PICK + 1)
        match_prob_arr = np.array([match_probs[m] for m in range(PICK + 1)])

        # Vectorized simulation: for each of N_SIM draws, simulate n_bets independent bets
        all_payouts = np.zeros(N_SIM)
        all_best_matches = np.zeros(N_SIM, dtype=int)
        all_any_m2 = np.zeros(N_SIM, dtype=bool)

        for b in range(n_bets):
            matches = rng.choice(match_values, size=N_SIM, p=match_prob_arr)
            payouts = np.zeros(N_SIM)
            for m, prize in PRIZES.items():
                payouts[matches == m] = prize
            all_payouts += payouts
            all_best_matches = np.maximum(all_best_matches, matches)
            all_any_m2 |= (matches >= 2)

        net = all_payouts - cost_per_draw
        elapsed = time.time() - t0

        # --- Loss streak distribution ---
        is_loss = ~all_any_m2
        loss_streaks = []
        current_streak = 0
        for loss in is_loss:
            if loss:
                current_streak += 1
            else:
                if current_streak > 0:
                    loss_streaks.append(current_streak)
                current_streak = 0
        if current_streak > 0:
            loss_streaks.append(current_streak)

        loss_streaks = np.array(loss_streaks) if loss_streaks else np.array([0])
        streak_percentiles = {
            'p50': float(np.percentile(loss_streaks, 50)),
            'p75': float(np.percentile(loss_streaks, 75)),
            'p90': float(np.percentile(loss_streaks, 90)),
            'p95': float(np.percentile(loss_streaks, 95)),
            'p99': float(np.percentile(loss_streaks, 99)),
            'max': int(np.max(loss_streaks)),
        }

        # --- Expected waiting times ---
        waiting_m2 = []
        waiting_m3 = []
        waiting_m4 = []
        gap_m2 = 0
        gap_m3 = 0
        gap_m4 = 0
        for i in range(N_SIM):
            gap_m2 += 1
            gap_m3 += 1
            gap_m4 += 1
            if all_best_matches[i] >= 2:
                waiting_m2.append(gap_m2)
                gap_m2 = 0
            if all_best_matches[i] >= 3:
                waiting_m3.append(gap_m3)
                gap_m3 = 0
            if all_best_matches[i] >= 4:
                waiting_m4.append(gap_m4)
                gap_m4 = 0

        waiting_times = {
            'M2+': {
                'median': float(np.median(waiting_m2)) if waiting_m2 else None,
                'mean': float(np.mean(waiting_m2)) if waiting_m2 else None,
                'count': len(waiting_m2),
            },
            'M3+': {
                'median': float(np.median(waiting_m3)) if waiting_m3 else None,
                'mean': float(np.mean(waiting_m3)) if waiting_m3 else None,
                'count': len(waiting_m3),
            },
            'M4+': {
                'median': float(np.median(waiting_m4)) if waiting_m4 else None,
                'mean': float(np.mean(waiting_m4)) if waiting_m4 else None,
                'count': len(waiting_m4),
            },
        }

        # --- Bankroll survival ---
        initial_bankrolls = [5000, 10000, 50000]
        survival = {}
        checkpoints = [100, 500, 1000, 5000]

        # Use smaller subsample for trajectory analysis (10K trajectories)
        N_TRAJ = 10000
        traj_len = 5000

        for br in initial_bankrolls:
            survival[str(br)] = {}
            # Simulate N_TRAJ trajectories of traj_len draws
            bankrolls = np.full(N_TRAJ, float(br))
            peaks = bankrolls.copy()
            max_drawdowns = np.zeros(N_TRAJ)
            ruined = np.zeros(N_TRAJ, dtype=bool)

            for step in range(traj_len):
                # Each trajectory draws n_bets independent outcomes
                step_payout = np.zeros(N_TRAJ)
                for _ in range(n_bets):
                    matches = rng.choice(match_values, size=N_TRAJ, p=match_prob_arr)
                    for m, prize in PRIZES.items():
                        step_payout[matches == m] += prize

                bankrolls += step_payout - cost_per_draw
                # Track ruin
                ruined |= (bankrolls <= 0)
                # Track drawdown
                peaks = np.maximum(peaks, bankrolls)
                dd = (peaks - bankrolls) / np.maximum(peaks, 1)
                max_drawdowns = np.maximum(max_drawdowns, dd)

                if (step + 1) in checkpoints:
                    alive = np.sum(~ruined) / N_TRAJ
                    survival[str(br)][str(step + 1)] = float(alive)

            survival[str(br)]['ruin_rate'] = float(np.mean(ruined))
            survival[str(br)]['avg_max_drawdown_pct'] = float(np.mean(max_drawdowns) * 100)
            survival[str(br)]['median_final_bankroll'] = float(np.median(bankrolls[~ruined])) if np.sum(~ruined) > 0 else 0.0

        # --- Summary ---
        mc_ev = float(np.mean(all_payouts))
        mc_roi = float((mc_ev - cost_per_draw) / cost_per_draw * 100)
        hit_rate_mc = float(np.mean(all_any_m2))

        results[f'{n_bets}bet'] = {
            'n_bets': n_bets,
            'cost_per_draw': cost_per_draw,
            'mc_ev': mc_ev,
            'mc_roi_pct': mc_roi,
            'hit_rate': hit_rate_mc,
            'baseline_hit_rate': float(p_hit_baseline),
            'loss_streak_distribution': streak_percentiles,
            'waiting_times': waiting_times,
            'bankroll_survival': survival,
            'elapsed_s': round(time.time() - t0, 1),
        }

        print(f"    EV={mc_ev:.2f} NTD  ROI={mc_roi:+.2f}%  "
              f"hit_rate={hit_rate_mc:.4f}  "
              f"max_streak={streak_percentiles['max']}")
        print(f"    Waiting: M2+={waiting_times['M2+']['median']:.0f} draws median  "
              f"M3+={waiting_times['M3+']['median']:.0f}  "
              f"M4+={waiting_times['M4+']['median']:.0f}")
        for br in initial_bankrolls:
            s = survival[str(br)]
            print(f"    Bankroll={br:,}: ruin@5000={s['ruin_rate']:.1%}  "
                  f"max_dd={s['avg_max_drawdown_pct']:.1f}%")

    return results


# ============================================================
# OBJECTIVE 4: Portfolio Efficiency Frontier
# ============================================================

def objective4_efficiency_frontier(sigs, actuals):
    print("\n" + "=" * 72)
    print("  OBJECTIVE 4: Portfolio Efficiency Frontier")
    print("  1-6 bets efficiency mapping")
    print("=" * 72)

    n_eval = len(actuals)
    sig_list = [sigs[0], sigs[1], sigs[2], sigs[3]]

    # Signal assignment for 1-6 bets
    # 1: MF, 2: +MidFreq, 3: +Markov, 4: +ACB
    # 5: +MF-residual (top-5 from remaining), 6: +MidFreq-residual
    signal_order = [0, 1, 2, 3, 0, 1]  # signal indices for bets 1-6
    signal_labels = ['MicroFish', 'MidFreq', 'Markov', 'ACB',
                     'MicroFish-res', 'MidFreq-res']

    frontier = []

    for n_bets in range(1, 7):
        hit_details = []
        per_bet_hits = [[] for _ in range(n_bets)]
        unique_coverage = []

        for t in range(n_eval):
            bets = []
            excluded = set()

            for b in range(n_bets):
                si = signal_order[b]
                scores = sig_list[si][t].copy()
                bet = pick_top_indices(scores, 5, exclude=excluded)
                bets.append(bet)
                excluded.update(bet)

            # Track unique coverage
            all_nums = set()
            for b in bets:
                all_nums.update(b)
            unique_coverage.append(len(all_nums))

            # Track per-bet hits
            for b_idx, bet in enumerate(bets):
                per_bet_hits[b_idx].append(1 if check_m2_hit(bet, actuals[t]) else 0)

            hit = check_any_m2_hit(bets, actuals[t])
            hit_details.append(1 if hit else 0)

        hit_details = np.array(hit_details)
        baseline = 1 - (1 - BASELINE_RATE) ** n_bets
        tw = three_window_eval_multi(hit_details, n_bets)
        tw_1500 = tw.get(1500, tw[max(tw.keys())])

        # Per-bet individual edge
        per_bet_edges = []
        for b_idx in range(n_bets):
            b_rate = np.mean(per_bet_hits[b_idx])
            b_edge = b_rate - BASELINE_RATE
            per_bet_edges.append({
                'bet': b_idx + 1,
                'signal': signal_labels[b_idx],
                'rate': float(b_rate),
                'edge': float(b_edge),
            })

        # EV computation (using correct prizes)
        # For n_bets, EV per draw = sum of EV per bet
        # EV per bet = sum(P(m) * prize(m)) for m=2..5
        ev_per_bet = sum(
            math.comb(PICK, m) * math.comb(MAX_NUM - PICK, PICK - m)
            / TOTAL_COMBOS * PRIZES.get(m, 0)
            for m in range(2, PICK + 1)
        )
        total_ev = ev_per_bet * n_bets
        total_cost = n_bets * COST
        roi = (total_ev - total_cost) / total_cost * 100

        entry = {
            'n_bets': n_bets,
            'signals': signal_labels[:n_bets],
            'hit_rate': tw_1500['rate'],
            'baseline': float(baseline),
            'edge': tw_1500['edge_pct'],
            'z': tw_1500['z'],
            'cost': total_cost,
            'ev_baseline': float(total_ev),
            'roi_baseline_pct': float(roi),
            'avg_unique_coverage': float(np.mean(unique_coverage)),
            'coverage_pct': float(np.mean(unique_coverage) / MAX_NUM * 100),
            'per_bet_edges': per_bet_edges,
            'three_window': tw,
        }
        frontier.append(entry)

        print(f"    {n_bets}-bet: rate={tw_1500['rate']:.2%} "
              f"edge={tw_1500['edge_pct']:+.2f}% z={tw_1500['z']:.2f} "
              f"coverage={entry['avg_unique_coverage']:.0f}/{MAX_NUM} "
              f"({entry['coverage_pct']:.0f}%)")

    # Marginal improvement
    for i in range(1, len(frontier)):
        frontier[i]['marginal_edge'] = frontier[i]['edge'] - frontier[i - 1]['edge']
    frontier[0]['marginal_edge'] = frontier[0]['edge']

    # Diminishing returns point
    dr_point = None
    for i in range(1, len(frontier)):
        if frontier[i]['marginal_edge'] < 0.5:  # <0.5pp
            dr_point = frontier[i - 1]['n_bets']
            break

    print(f"\n  Diminishing returns point: {dr_point or 'not reached within 6 bets'}")

    return {
        'frontier': frontier,
        'diminishing_returns_point': dr_point,
    }


# ============================================================
# Validation: Permutation Test
# ============================================================

def permutation_test_config(sigs, actuals, n_bets, signal_order, pool_size=5,
                            method='independent', n_perm=N_PERM):
    """Permutation test for a given bet configuration."""
    n_eval = len(actuals)
    sig_list = [sigs[0], sigs[1], sigs[2], sigs[3]]

    def evaluate(act):
        hits = 0
        for t in range(n_eval):
            bets = []
            excluded = set()
            for b in range(n_bets):
                si = signal_order[b]
                scores = sig_list[si][t].copy()
                bet = pick_top_indices(scores, 5, exclude=excluded)
                bets.append(bet)
                excluded.update(bet)
            if check_any_m2_hit(bets, act[t]):
                hits += 1
        return hits / n_eval

    real_rate = evaluate(actuals)
    exceed = 0
    for p in range(n_perm):
        perm_idx = rng.permutation(n_eval)
        shuffled = actuals[perm_idx]
        perm_rate = evaluate(shuffled)
        if perm_rate >= real_rate:
            exceed += 1
        if (p + 1) % 20 == 0:
            print(f"      perm {p+1}/{n_perm} (exceed={exceed})")

    p_val = (exceed + 1) / (n_perm + 1)
    return {'real_rate': float(real_rate), 'perm_p': float(p_val),
            'n_perm': n_perm, 'exceed': exceed}


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 72)
    print("  Strategy Space Exploration Research Engine")
    print("  DAILY_539 | 2026-03-15")
    print("=" * 72)

    t_start = time.time()

    # Load data
    print("\n  Loading data...")
    draws = load_draws()
    print(f"  Total draws: {len(draws)}")
    mf_features, mf_weights = load_microfish_genome()
    print(f"  MicroFish genome: {mf_features}")

    # Precompute signals
    print("\n  Precomputing signals...")
    sig_mf, sig_mid, sig_markov, sig_acb, actuals, eval_start = precompute_signals(
        draws, mf_features, mf_weights
    )
    sigs = (sig_mf, sig_mid, sig_markov, sig_acb)
    n_eval = len(actuals)
    print(f"  Evaluation period: {n_eval} draws")

    all_results = {
        'metadata': {
            'date': '2026-03-15',
            'n_draws': len(draws),
            'n_eval': n_eval,
            'eval_start_idx': eval_start,
            'seed': SEED,
            'baseline_rate': float(BASELINE_RATE),
            'prizes': PRIZES,
            'cost': COST,
        },
    }

    # Objective 1
    all_results['obj1_coverage_matrix'] = objective1_coverage_matrix(
        sigs, actuals, draws, eval_start
    )

    # Objective 2
    all_results['obj2_diversity'] = objective2_diversity(sigs, actuals)

    # Objective 3
    all_results['obj3_risk_simulation'] = objective3_risk_simulation()

    # Objective 4
    all_results['obj4_efficiency_frontier'] = objective4_efficiency_frontier(sigs, actuals)

    # Validation: Permutation tests for key configurations
    print("\n" + "=" * 72)
    print("  VALIDATION: Permutation Tests")
    print("=" * 72)

    validation = {}

    # Test current 3-bet (baseline reference)
    print("\n  Permutation test: current 3-bet (MF+MidFreq+Markov)...")
    validation['current_3bet'] = permutation_test_config(
        sigs, actuals, 3, [0, 1, 2], n_perm=N_PERM
    )
    print(f"    p={validation['current_3bet']['perm_p']:.4f}")

    # Test 4-bet (frontier extension)
    print("\n  Permutation test: 4-bet (MF+MidFreq+Markov+ACB)...")
    validation['frontier_4bet'] = permutation_test_config(
        sigs, actuals, 4, [0, 1, 2, 3], n_perm=N_PERM
    )
    print(f"    p={validation['frontier_4bet']['perm_p']:.4f}")

    # Test 5-bet
    print("\n  Permutation test: 5-bet (MF+MidFreq+Markov+ACB+MF-res)...")
    validation['frontier_5bet'] = permutation_test_config(
        sigs, actuals, 5, [0, 1, 2, 3, 0], n_perm=N_PERM
    )
    print(f"    p={validation['frontier_5bet']['perm_p']:.4f}")

    all_results['validation'] = validation

    # Summary
    t_total = time.time() - t_start
    print(f"\n  Total elapsed: {t_total:.1f}s")
    all_results['metadata']['elapsed_s'] = round(t_total, 1)

    # Save results
    out_path = os.path.join(project_root, 'strategy_space_exploration_results.json')
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2, cls=NumpyEncoder)
    print(f"\n  Results saved: {out_path}")


if __name__ == '__main__':
    main()
