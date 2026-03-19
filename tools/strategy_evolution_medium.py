#!/usr/bin/env python3
"""
Medium-Scale Strategy Evolution Engine v2 — Precomputed Signals
================================================================
CRITICAL OPTIMIZATION: Precompute all 4 signal score vectors once,
then evolution only combines precomputed scores (pure arithmetic).

Population: 200 | Generations: 50 | ~10,000 candidate evaluations
Signals: MicroFish, MidFreq, Markov, ACB (precomputed)
"""

import os
import sys
import json
import math
import time
import copy
import numpy as np
from collections import Counter

SEED = 42
np.random.seed(SEED)
rng = np.random.default_rng(SEED)

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

MAX_NUM = 39
PICK = 5
# P(M2+) = sum_{m=2..5} C(5,m)*C(34,5-m) / C(39,5)
TOTAL_COMBOS = math.comb(MAX_NUM, PICK)
BASELINE_RATE = sum(
    math.comb(PICK, m) * math.comb(MAX_NUM - PICK, PICK - m)
    for m in range(2, PICK + 1)
) / TOTAL_COMBOS  # ≈ 0.1140

POP_SIZE = 200
N_GEN = 50
ELITE_FRAC = 0.10
MUTATION_RATE = 0.35
CROSSOVER_RATE = 0.55
TOURNAMENT_SIZE = 5
WINDOWS = [150, 500, 1500]
N_PERM = 199
EVAL_WINDOW = 300  # draws for fast fitness eval

FUSION_TYPES = ['weighted_rank', 'score_blend', 'voting', 'rank_product']
NONLINEAR_TYPES = ['none', 'sqrt', 'square', 'log', 'sigmoid']
SIGNAL_NAMES = ['microfish', 'midfreq', 'markov', 'acb']


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
# Signal scoring functions (same as before)
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

    # freq_raw_150
    counter_150 = Counter()
    for n in range(1, max_num + 1):
        counter_150[n] = 0
    for d in W150:
        for n in d['numbers'][:pick]:
            if 1 <= n <= max_num:
                counter_150[n] += 1

    # parity even rate in 80
    even_count = 0
    total_nums = 0
    for d in W80:
        for n in d['numbers'][:pick]:
            if 1 <= n <= max_num:
                total_nums += 1
                if n % 2 == 0:
                    even_count += 1
    even_rate = even_count / max(total_nums, 1)

    # markov lag1 self-transition (window 100)
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

    # freq deficit / zscore (window 100)
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
# Precompute all signals for all draws
# ============================================================

def precompute_signals(draws, mf_features, mf_weights, start_idx=500):
    """Precompute 4 signal score arrays: shape (T, 39) each.
    Only precompute last 1600 draws (enough for 1500p validation + buffer).
    """
    T = len(draws)
    # Only need last 1600 draws for evaluation (1500 validation + 100 buffer)
    actual_start = max(start_idx, T - 1600)
    n_eval = T - actual_start
    print(f"  Precomputing signals for {n_eval} draws (idx {actual_start}..{T-1})...")
    print(f"  (Each signal uses window ≤150, so history[:t] sliced internally)")

    sig_mf = np.zeros((n_eval, MAX_NUM))
    sig_mid = np.zeros((n_eval, MAX_NUM))
    sig_markov = np.zeros((n_eval, MAX_NUM))
    sig_acb = np.zeros((n_eval, MAX_NUM))
    actuals = np.zeros((n_eval, MAX_NUM), dtype=bool)

    t0 = time.time()
    for idx, t in enumerate(range(actual_start, T)):
        # Only pass last 200 draws as history (all signals use window ≤ 150)
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

    return sig_mf, sig_mid, sig_markov, sig_acb, actuals


# ============================================================
# Genome operations (same as v1 but operates on precomputed arrays)
# ============================================================

def random_genome(n_bets=None):
    g = {
        'signal_weights': [rng.uniform(0.01, 1.0) for _ in range(4)],
        'fusion_type': rng.choice(FUSION_TYPES),
        'nonlinear': rng.choice(NONLINEAR_TYPES),
        'gate_signal': int(rng.choice([-1, 0, 1, 2, 3])),
        'gate_threshold': float(rng.uniform(0.3, 0.9)),
        'n_bets': n_bets if n_bets else int(rng.choice([1, 2, 3])),
        'orthogonal': True,
        'top_k_method': 'direct',
        'diversity_bonus': float(rng.uniform(0.0, 0.3)),
    }
    wsum = sum(g['signal_weights'])
    g['signal_weights'] = [w / wsum for w in g['signal_weights']]
    return g


def mutate_genome(g):
    g = copy.deepcopy(g)
    mt = rng.choice(['weights', 'fusion', 'nonlinear', 'gate', 'diversity', 'perturb'])
    if mt == 'weights':
        idx = int(rng.integers(0, 4))
        g['signal_weights'][idx] = float(rng.uniform(0.01, 1.0))
    elif mt == 'perturb':
        for i in range(4):
            g['signal_weights'][i] *= float(rng.uniform(0.7, 1.4))
        g['signal_weights'] = [max(0.01, w) for w in g['signal_weights']]
    elif mt == 'fusion':
        g['fusion_type'] = rng.choice(FUSION_TYPES)
    elif mt == 'nonlinear':
        g['nonlinear'] = rng.choice(NONLINEAR_TYPES)
    elif mt == 'gate':
        g['gate_signal'] = int(rng.choice([-1, 0, 1, 2, 3]))
        g['gate_threshold'] = float(rng.uniform(0.3, 0.9))
    elif mt == 'diversity':
        g['diversity_bonus'] = float(rng.uniform(0.0, 0.3))
    wsum = sum(g['signal_weights'])
    g['signal_weights'] = [w / wsum for w in g['signal_weights']]
    return g


def crossover_genomes(a, b):
    child = copy.deepcopy(a)
    alpha = float(rng.uniform(0.3, 0.7))
    child['signal_weights'] = [alpha * a['signal_weights'][i] + (1 - alpha) * b['signal_weights'][i] for i in range(4)]
    if rng.random() < 0.5: child['fusion_type'] = b['fusion_type']
    if rng.random() < 0.5: child['nonlinear'] = b['nonlinear']
    if rng.random() < 0.5:
        child['gate_signal'] = b['gate_signal']
        child['gate_threshold'] = b['gate_threshold']
    if rng.random() < 0.5: child['diversity_bonus'] = b['diversity_bonus']
    wsum = sum(child['signal_weights'])
    child['signal_weights'] = [w / wsum for w in child['signal_weights']]
    return child


# ============================================================
# Fast genome execution on precomputed signals (vectorized)
# ============================================================

def apply_nl_vec(arr, nl):
    """Apply nonlinear transform to numpy array."""
    if nl == 'none':
        return arr
    elif nl == 'sqrt':
        return np.sign(arr) * np.sqrt(np.abs(arr))
    elif nl == 'square':
        return arr * np.abs(arr)
    elif nl == 'log':
        return np.sign(arr) * np.log1p(np.abs(arr))
    elif nl == 'sigmoid':
        return 1.0 / (1.0 + np.exp(-np.clip(arr, -500, 500)))
    return arr


def execute_genome_on_draw(genome, sigs_at_t, rng_state=None):
    """Execute genome for a single draw. sigs_at_t = [mf(39,), mid(39,), markov(39,), acb(39,)]
    Returns list of bets, each bet = list of 5 number indices (0-based).
    """
    w = genome['signal_weights']
    nl = genome['nonlinear']

    transformed = [apply_nl_vec(s.copy(), nl) for s in sigs_at_t]

    # Gating
    if genome['gate_signal'] >= 0:
        gs_idx = genome['gate_signal']
        gate_vals = transformed[gs_idx]
        thresh = np.percentile(gate_vals, genome['gate_threshold'] * 100)
        mask = gate_vals < thresh
        for sig in transformed:
            sig[mask] *= 0.1

    fusion = genome['fusion_type']

    if fusion == 'weighted_rank':
        ranks = [np.zeros(MAX_NUM) for _ in range(4)]
        for i in range(4):
            order = np.argsort(-transformed[i])
            for rank, idx in enumerate(order):
                ranks[i][idx] = MAX_NUM - rank
        combined = sum(w[i] * ranks[i] for i in range(4))

    elif fusion == 'score_blend':
        normalized = []
        for sig in transformed:
            mn, mx = sig.min(), sig.max()
            rng_val = mx - mn if mx > mn else 1.0
            normalized.append((sig - mn) / rng_val)
        combined = sum(w[i] * normalized[i] for i in range(4))

    elif fusion == 'voting':
        combined = np.zeros(MAX_NUM)
        for i in range(4):
            top10 = np.argsort(-transformed[i])[:10]
            for rank, idx in enumerate(top10):
                combined[idx] += w[i] * (10 - rank)

    elif fusion == 'rank_product':
        ranks = []
        for sig in transformed:
            order = np.argsort(-sig)
            r = np.zeros(MAX_NUM)
            for rank, idx in enumerate(order):
                r[idx] = rank + 1
            ranks.append(r)
        log_rp = sum(w[i] * np.log(ranks[i]) for i in range(4))
        combined = -log_rp  # higher = better
    else:
        combined = np.zeros(MAX_NUM)

    # Diversity bonus
    if genome['diversity_bonus'] > 0:
        db = genome['diversity_bonus']
        top5_idx = np.argsort(-combined)[:5]
        zone_counts = [0, 0, 0]
        for idx in top5_idx:
            z = min(idx // 13, 2)
            zone_counts[z] += 1
        for idx in range(MAX_NUM):
            z = min(idx // 13, 2)
            if zone_counts[z] == 0:
                combined[idx] += db * combined.max()

    # Select bets
    bets = []
    used = set()
    for bet_idx in range(genome['n_bets']):
        available = np.array([combined[i] if i not in used else -1e10 for i in range(MAX_NUM)])
        if np.sum(available > -1e9) < PICK:
            break
        top_k = np.argsort(-available)[:PICK]
        bets.append(top_k)
        if genome['orthogonal']:
            used.update(top_k.tolist())

    return bets


def evaluate_genome_fast_precomputed(genome, sigs, actuals, start, end):
    """Evaluate genome on precomputed signals. Returns edge."""
    n_bets = genome['n_bets']
    baseline = 1 - (1 - BASELINE_RATE) ** n_bets
    total = 0
    hits = 0
    for t in range(start, end):
        sigs_at_t = [sigs[i][t] for i in range(4)]
        bets = execute_genome_on_draw(genome, sigs_at_t)
        any_hit = False
        for bet_indices in bets:
            if np.sum(actuals[t, bet_indices]) >= 2:
                any_hit = True
                break
        if any_hit:
            hits += 1
        total += 1
    rate = hits / total if total > 0 else 0
    return rate - baseline, rate


def evaluate_genome_full_precomputed(genome, sigs, actuals, start, end):
    """Full evaluation returning hit_details."""
    n_bets = genome['n_bets']
    hit_details = []
    for t in range(start, end):
        sigs_at_t = [sigs[i][t] for i in range(4)]
        bets = execute_genome_on_draw(genome, sigs_at_t)
        any_hit = 0
        for bet_indices in bets:
            if np.sum(actuals[t, bet_indices]) >= 2:
                any_hit = 1
                break
        hit_details.append(any_hit)
    return hit_details


# ============================================================
# Reference strategies on precomputed signals
# ============================================================

def eval_reference_precomputed(sigs, actuals, start, end):
    """Evaluate reference strategies on precomputed signals."""
    sig_mf, sig_mid, sig_markov, sig_acb = sigs
    results = {}

    # Accumulators
    dets = {'mf1': [], 'mfmid2': [], 'mfmidmar3': [], 'midacb2': []}

    for t in range(start, end):
        actual = actuals[t]

        # 1-bet MicroFish
        mf_top5 = np.argsort(-sig_mf[t])[:5]
        h_mf1 = 1 if np.sum(actual[mf_top5]) >= 2 else 0
        dets['mf1'].append(h_mf1)

        # 2-bet MicroFish+MidFreq orthogonal
        mid_scores = sig_mid[t].copy()
        mid_scores[mf_top5] = -1e10
        mid_top5 = np.argsort(-mid_scores)[:5]
        h_mfmid2 = 1 if (h_mf1 or np.sum(actual[mid_top5]) >= 2) else 0
        dets['mfmid2'].append(h_mfmid2)

        # 3-bet MF+MidFreq+Markov orthogonal
        markov_scores = sig_markov[t].copy()
        used = set(mf_top5.tolist()) | set(mid_top5.tolist())
        for idx in used:
            markov_scores[idx] = -1e10
        markov_top5 = np.argsort(-markov_scores)[:5]
        h_3 = 1 if (h_mfmid2 or np.sum(actual[markov_top5]) >= 2) else 0
        dets['mfmidmar3'].append(h_3)

        # 2-bet MidFreq+ACB orthogonal (current production)
        mid_top5_prod = np.argsort(-sig_mid[t])[:5]
        acb_scores = sig_acb[t].copy()
        acb_scores[mid_top5_prod] = -1e10
        acb_top5 = np.argsort(-acb_scores)[:5]
        h_midacb2 = 1 if (np.sum(actual[mid_top5_prod]) >= 2 or np.sum(actual[acb_top5]) >= 2) else 0
        dets['midacb2'].append(h_midacb2)

    def metrics(name, hit_details, n_bets):
        rate = np.mean(hit_details)
        bl = 1 - (1 - BASELINE_RATE) ** n_bets
        edge = rate - bl
        z = edge / math.sqrt(bl * (1 - bl) / len(hit_details))
        return {'name': name, 'rate': rate, 'edge': edge, 'z': z, 'n_bets': n_bets,
                'hit_details': hit_details}

    results['MicroFish_1bet'] = metrics('MicroFish_1bet', dets['mf1'], 1)
    results['MF+MidFreq_2bet'] = metrics('MF+MidFreq_2bet', dets['mfmid2'], 2)
    results['MF+MidFreq+Markov_3bet'] = metrics('MF+MidFreq+Markov_3bet', dets['mfmidmar3'], 3)
    results['MidFreq+ACB_2bet'] = metrics('MidFreq+ACB_2bet', dets['midacb2'], 2)
    return results


# ============================================================
# Permutation test
# ============================================================

def permutation_test_genome(genome, sigs, actuals, start, end, n_perm=N_PERM):
    """Correct permutation test: shuffle time mapping between predictions and actuals.

    For each permutation, we keep the predictions fixed but randomly reassign
    which actual draws they are compared against. This breaks the temporal
    relationship and gives a null distribution.
    """
    # Real hit details
    real_details = evaluate_genome_full_precomputed(genome, sigs, actuals, start, end)
    real_rate = np.mean(real_details)

    n_draws = end - start
    exceed = 0
    for _ in range(n_perm):
        # Shuffle actuals rows (which draw outcome pairs with which prediction)
        perm_idx = rng.permutation(n_draws)
        shuffled_actuals = actuals[start:end][perm_idx]
        # Re-evaluate with shuffled actuals
        hits = 0
        for t in range(n_draws):
            sigs_at_t = [sigs[i][start + t] for i in range(4)]
            bets = execute_genome_on_draw(genome, sigs_at_t)
            for bet_indices in bets:
                if np.sum(shuffled_actuals[t, bet_indices]) >= 2:
                    hits += 1
                    break
        perm_rate = hits / n_draws
        if perm_rate >= real_rate:
            exceed += 1

    p = (exceed + 1) / (n_perm + 1)
    return p, real_rate


def permutation_test_reference(hit_details_func, sigs, actuals, start, end, n_perm=N_PERM):
    """Permutation test for reference strategies.
    hit_details_func: callable(sigs, actuals, start, end) -> list of hit details
    """
    real_details = hit_details_func(sigs, actuals, start, end)
    real_rate = np.mean(real_details)

    n_draws = end - start
    exceed = 0
    for _ in range(n_perm):
        perm_idx = rng.permutation(n_draws)
        shuffled_actuals = actuals.copy()
        shuffled_actuals[start:end] = actuals[start:end][perm_idx]
        perm_details = hit_details_func(sigs, shuffled_actuals, start, end)
        perm_rate = np.mean(perm_details)
        if perm_rate >= real_rate:
            exceed += 1

    p = (exceed + 1) / (n_perm + 1)
    return p, real_rate


# ============================================================
# MAIN
# ============================================================

def main():
    t_global = time.time()
    print("=" * 72)
    print("  MEDIUM-SCALE STRATEGY EVOLUTION ENGINE v2")
    print("  Precomputed Signals | Pop 200 × Gen 50 | ~10K candidates")
    print("=" * 72)

    draws = load_draws()
    print(f"\n  Loaded {len(draws)} DAILY_539 draws")

    mf_features, mf_weights = load_microfish_genome()
    print(f"  MicroFish genome: {mf_features}")

    # Precompute signals
    START_IDX = 500
    sig_mf, sig_mid, sig_markov, sig_acb, actuals = precompute_signals(
        draws, mf_features, mf_weights, start_idx=START_IDX)
    sigs = [sig_mf, sig_mid, sig_markov, sig_acb]
    N_EVAL = len(actuals)
    print(f"  Evaluation range: {N_EVAL} draws (idx {START_IDX}..{len(draws)-1})")

    # ================================================================
    # PHASE 1: Genome Design
    # ================================================================
    print(f"\n{'='*72}")
    print("  PHASE 1: Strategy Genome Design")
    print(f"{'='*72}")
    sample = random_genome(1)
    print(f"  Fields: {list(sample.keys())}")
    print(f"  Fusion types: {FUSION_TYPES}")
    print(f"  Nonlinear types: {NONLINEAR_TYPES}")
    print(f"  Signals: {SIGNAL_NAMES}")
    print(f"  Population: {POP_SIZE}, Generations: {N_GEN}")

    # ================================================================
    # PHASE 2: Evolution
    # ================================================================
    print(f"\n{'='*72}")
    print("  PHASE 2: Evolutionary Search")
    print(f"{'='*72}")

    fast_start = max(0, N_EVAL - EVAL_WINDOW)
    fast_end = N_EVAL

    all_top_candidates = {}

    for target_bets in [1, 2, 3]:
        print(f"\n  --- Evolving {target_bets}-bet strategies ---")
        t_evo = time.time()

        population = [random_genome(n_bets=target_bets) for _ in range(POP_SIZE)]

        # Seed known-good configurations
        seeds = [
            {'signal_weights': [0.6, 0.1, 0.1, 0.2], 'fusion_type': 'weighted_rank',
             'nonlinear': 'none', 'gate_signal': -1, 'gate_threshold': 0.5,
             'n_bets': target_bets, 'orthogonal': True, 'top_k_method': 'direct', 'diversity_bonus': 0.0},
            {'signal_weights': [0.4, 0.3, 0.1, 0.2], 'fusion_type': 'score_blend',
             'nonlinear': 'none', 'gate_signal': -1, 'gate_threshold': 0.5,
             'n_bets': target_bets, 'orthogonal': True, 'top_k_method': 'direct', 'diversity_bonus': 0.0},
            {'signal_weights': [0.3, 0.25, 0.25, 0.2], 'fusion_type': 'rank_product',
             'nonlinear': 'sqrt', 'gate_signal': -1, 'gate_threshold': 0.5,
             'n_bets': target_bets, 'orthogonal': True, 'top_k_method': 'direct', 'diversity_bonus': 0.1},
            {'signal_weights': [0.5, 0.2, 0.15, 0.15], 'fusion_type': 'voting',
             'nonlinear': 'none', 'gate_signal': 0, 'gate_threshold': 0.5,
             'n_bets': target_bets, 'orthogonal': True, 'top_k_method': 'direct', 'diversity_bonus': 0.0},
        ]
        for i, s in enumerate(seeds):
            if i < POP_SIZE:
                population[i] = s

        best_history = []

        for gen in range(N_GEN):
            fitnesses = []
            for ind in population:
                edge, _ = evaluate_genome_fast_precomputed(ind, sigs, actuals, fast_start, fast_end)
                fitnesses.append(edge)

            paired = sorted(zip(fitnesses, population), key=lambda x: x[0], reverse=True)
            fitnesses = [p[0] for p in paired]
            population = [p[1] for p in paired]
            best_history.append(fitnesses[0])

            if gen % 10 == 0 or gen == N_GEN - 1:
                bl = 1 - (1 - BASELINE_RATE) ** target_bets
                rate = fitnesses[0] + bl
                print(f"    Gen {gen:3d}: best_edge={fitnesses[0]*100:+.2f}% "
                      f"rate={rate:.4f} "
                      f"median={np.median(fitnesses)*100:+.2f}% "
                      f"fusion={population[0]['fusion_type']} "
                      f"nl={population[0]['nonlinear']} "
                      f"w={[round(x,3) for x in population[0]['signal_weights']]}")

            # Reproduction
            n_elite = max(1, int(POP_SIZE * ELITE_FRAC))
            new_pop = list(population[:n_elite])
            while len(new_pop) < POP_SIZE:
                r = rng.random()
                if r < CROSSOVER_RATE:
                    idxs_a = rng.choice(POP_SIZE, size=TOURNAMENT_SIZE, replace=False)
                    idxs_b = rng.choice(POP_SIZE, size=TOURNAMENT_SIZE, replace=False)
                    child = crossover_genomes(population[min(idxs_a)], population[min(idxs_b)])
                    child['n_bets'] = target_bets
                    new_pop.append(child)
                elif r < CROSSOVER_RATE + MUTATION_RATE:
                    idxs = rng.choice(POP_SIZE, size=TOURNAMENT_SIZE, replace=False)
                    child = mutate_genome(population[min(idxs)])
                    child['n_bets'] = target_bets
                    new_pop.append(child)
                else:
                    new_pop.append(random_genome(n_bets=target_bets))
            population = new_pop[:POP_SIZE]

        # Full evaluation of top 20 on 1500p
        print(f"\n    Full 1500p evaluation of top 20:")
        full_start = max(0, N_EVAL - 1500)
        top_candidates = []
        for ind in population[:20]:
            edge, rate = evaluate_genome_fast_precomputed(ind, sigs, actuals, full_start, N_EVAL)
            details = evaluate_genome_full_precomputed(ind, sigs, actuals, full_start, N_EVAL)
            bl = 1 - (1 - BASELINE_RATE) ** target_bets
            z = edge / math.sqrt(bl * (1 - bl) / len(details))
            top_candidates.append({
                'genome': ind, 'rate': rate, 'edge': edge, 'z': z,
                'hit_details': details, 'fitness_history': best_history,
            })

        # Sort by edge
        top_candidates.sort(key=lambda x: x['edge'], reverse=True)
        for i, c in enumerate(top_candidates[:5]):
            print(f"      #{i+1}: edge={c['edge']*100:+.2f}% z={c['z']:.2f} "
                  f"fusion={c['genome']['fusion_type']} "
                  f"nl={c['genome']['nonlinear']} "
                  f"w={[round(x,3) for x in c['genome']['signal_weights']]}")

        all_top_candidates[target_bets] = top_candidates
        print(f"    {target_bets}-bet evolution: {time.time()-t_evo:.0f}s")

    # ================================================================
    # PHASE 3: Validation
    # ================================================================
    print(f"\n{'='*72}")
    print("  PHASE 3: Validation")
    print(f"{'='*72}")

    validated = {1: [], 2: [], 3: []}
    rejected = 0

    for n_bets in [1, 2, 3]:
        print(f"\n  --- Validating {n_bets}-bet ---")
        bl = 1 - (1 - BASELINE_RATE) ** n_bets

        for i, cand in enumerate(all_top_candidates.get(n_bets, [])[:10]):
            genome = cand['genome']

            # Three-window test
            tw = {}
            all_pos = True
            for win in WINDOWS:
                ws = max(0, N_EVAL - win)
                we = N_EVAL
                details = evaluate_genome_full_precomputed(genome, sigs, actuals, ws, we)
                rate = np.mean(details)
                edge = rate - bl
                n_d = len(details)
                z = edge / math.sqrt(bl * (1 - bl) / n_d) if n_d > 0 else 0
                tw[win] = {'rate': round(rate, 6), 'edge': round(edge * 100, 4), 'z': round(z, 2)}
                if edge <= 0:
                    all_pos = False

            if not all_pos:
                win_str = ', '.join(str(w) + 'p=' + format(tw[w]['edge'], '+.2f') + '%' for w in WINDOWS)
                print(f"    #{i}: REJECTED (unstable: [{win_str}])")
                rejected += 1
                continue

            # Permutation test on 1500p (shuffle time mapping, not hit_details)
            perm_start = max(0, N_EVAL - 1500)
            perm_p, _ = permutation_test_genome(genome, sigs, actuals, perm_start, N_EVAL, n_perm=99)

            if perm_p > 0.05:
                print(f"    #{i}: REJECTED (perm_p={perm_p:.3f})")
                rejected += 1
                continue

            # VALIDATED
            details_1500 = evaluate_genome_full_precomputed(genome, sigs, actuals,
                                                             max(0, N_EVAL-1500), N_EVAL)
            validated[n_bets].append({
                'genome': genome,
                'rate_1500': round(np.mean(details_1500), 6),
                'edge_1500': round((np.mean(details_1500) - bl) * 100, 4),
                'z_1500': tw[1500]['z'],
                'windows': {str(w): tw[w] for w in WINDOWS},
                'perm_p': round(perm_p, 4),
                'hit_details': details_1500,
            })
            print(f"    #{i}: VALIDATED edge={tw[1500]['edge']:+.2f}% z={tw[1500]['z']:.2f} "
                  f"perm_p={perm_p:.3f} "
                  f"[{tw[150]['edge']:+.1f}%|{tw[500]['edge']:+.1f}%|{tw[1500]['edge']:+.1f}%]")

    total_val = sum(len(v) for v in validated.values())
    print(f"\n  Summary: {total_val} validated, {rejected} rejected")

    # ================================================================
    # PHASE 4: Portfolio Optimization
    # ================================================================
    print(f"\n{'='*72}")
    print("  PHASE 4: Portfolio Optimization + Comparison")
    print(f"{'='*72}")

    # Reference strategies
    full_1500_start = max(0, N_EVAL - 1500)
    refs = eval_reference_precomputed(sigs, actuals, full_1500_start, N_EVAL)

    print(f"\n  Reference Strategies (1500p):")
    print(f"  {'Strategy':<35} {'Rate':<8} {'Edge%':<10} {'z':<8} {'Edge/NTD'}")
    print(f"  {'-'*35} {'-'*8} {'-'*10} {'-'*8} {'-'*12}")
    for name, r in refs.items():
        ent = r['edge'] / (r['n_bets'] * 50)
        print(f"  {name:<35} {r['rate']:.4f} {r['edge']*100:+.2f}% {r['z']:.2f} {ent:.6f}")

    print(f"\n  Best Evolved (validated):")
    best_evolved = {}
    for nb in [1, 2, 3]:
        if validated[nb]:
            best = max(validated[nb], key=lambda x: x['edge_1500'])
            best_evolved[nb] = best
            ent = best['edge_1500'] / 100 / (nb * 50)
            print(f"  Evolved_{nb}bet: edge={best['edge_1500']:+.2f}% z={best['z_1500']:.2f} "
                  f"perm_p={best['perm_p']:.3f} edge/NTD={ent:.6f}")
            g = best['genome']
            print(f"    genome: fusion={g['fusion_type']} nl={g['nonlinear']} "
                  f"gate={g['gate_signal']} "
                  f"w={[round(x,3) for x in g['signal_weights']]}")
        else:
            print(f"  Evolved_{nb}bet: NO VALIDATED CANDIDATES")

    # McNemar comparisons
    print(f"\n  Head-to-Head McNemar Tests:")
    comparisons = []

    try:
        from scipy.stats import chi2 as chi2_dist
    except ImportError:
        chi2_dist = None

    comp_pairs = [
        (1, 'MicroFish_1bet'),
        (2, 'MF+MidFreq_2bet'),
        (3, 'MF+MidFreq+Markov_3bet'),
    ]

    for nb, ref_name in comp_pairs:
        if nb in best_evolved and ref_name in refs:
            a = best_evolved[nb]['hit_details']
            b = refs[ref_name]['hit_details']
            n_min = min(len(a), len(b))
            a_only = sum(1 for i in range(n_min) if a[i] == 1 and b[i] == 0)
            b_only = sum(1 for i in range(n_min) if a[i] == 0 and b[i] == 1)
            disc = a_only + b_only
            chi2_val = (a_only - b_only) ** 2 / max(disc, 1)
            if chi2_dist:
                p_val = 1 - chi2_dist.cdf(chi2_val, df=1)
            else:
                p_val = 1.0  # fallback
            sig_str = "SIGNIFICANT" if p_val < 0.05 else "NOT significant"
            comparisons.append({
                'comparison': f'Evolved_{nb}bet vs {ref_name}',
                'a_only': a_only, 'b_only': b_only,
                'chi2': round(chi2_val, 2), 'p': round(p_val, 4),
                'significant': p_val < 0.05,
            })
            winner = f"Evolved wins ({a_only})" if a_only > b_only else f"Reference wins ({b_only})"
            print(f"  {nb}-bet: a_only={a_only} b_only={b_only} χ²={chi2_val:.2f} p={p_val:.4f} → {sig_str} | {winner}")

    # Marginal utility
    print(f"\n  Marginal Utility (best evolved):")
    prev = 0
    for nb in [1, 2, 3]:
        if nb in best_evolved:
            e = best_evolved[nb]['edge_1500']
            mg = e - prev
            print(f"  {nb}-bet: edge={e:+.2f}% marginal={mg:+.2f}pp edge/NTD={e/100/(nb*50):.6f}")
            prev = e

    # ================================================================
    # PHASE 5: Conclusion
    # ================================================================
    print(f"\n{'='*72}")
    print("  PHASE 5: Final Conclusion")
    print(f"{'='*72}")

    improvement_found = False
    significant_improvement = False
    worth_deploying = False

    for c in comparisons:
        if c['a_only'] > c['b_only']:
            improvement_found = True
            if c['significant']:
                significant_improvement = True
                worth_deploying = True

    # Check if any evolved strategy has higher edge than reference
    improvement_details = []
    for nb, ref_name in comp_pairs:
        if nb in best_evolved and ref_name in refs:
            evo_edge = best_evolved[nb]['edge_1500']
            ref_edge = refs[ref_name]['edge'] * 100
            delta = evo_edge - ref_edge
            improvement_details.append(f"{nb}-bet: evolved={evo_edge:+.2f}% vs ref={ref_edge:+.2f}% (Δ={delta:+.2f}pp)")
            if delta > 0.1:
                improvement_found = True

    further_search = "Unlikely — evolution converged and marginal gains are small" if not significant_improvement else \
                     "Possibly — but expect diminishing returns"

    print(f"""
  ┌──────────────────────────────────────────────────────────────────┐
  │  Q1: Did medium-scale evolution find improvement?               │
  │  A:  {'YES' if improvement_found else 'NO — current strategies are near-optimal'}                                           │
  │  {'   '.join(improvement_details) if improvement_details else ''}
  │                                                                │
  │  Q2: Is the improvement statistically significant?              │
  │  A:  {'YES (McNemar p<0.05)' if significant_improvement else 'NO — within noise band'}
  │                                                                │
  │  Q3: Is it worth deploying?                                     │
  │  A:  {'YES — deploy evolved strategy' if worth_deploying else 'NO — keep current production strategies'}
  │                                                                │
  │  Q4: Is further large-scale search likely worth extra compute?  │
  │  A:  {further_search}
  └──────────────────────────────────────────────────────────────────┘
""")

    # ================================================================
    # Save results
    # ================================================================
    elapsed = time.time() - t_global

    def ser_genome(g):
        return {k: v for k, v in g.items() if k != 'top_k_method' or True}

    evolved_pop = {}
    for nb in [1, 2, 3]:
        evolved_pop[str(nb)] = []
        for v in validated.get(nb, []):
            evolved_pop[str(nb)].append({
                'genome': ser_genome(v['genome']),
                'rate_1500': v['rate_1500'],
                'edge_1500_pct': v['edge_1500'],
                'z_1500': v['z_1500'],
                'windows': v['windows'],
                'perm_p': v['perm_p'],
            })

    ref_summary = {}
    for name, r in refs.items():
        ref_summary[name] = {
            'rate': round(r['rate'], 6), 'edge_pct': round(r['edge'] * 100, 4),
            'z': round(r['z'], 2), 'n_bets': r['n_bets'],
        }

    output = {
        'metadata': {
            'date': '2026-03-15', 'pop_size': POP_SIZE, 'generations': N_GEN,
            'total_evaluations': POP_SIZE * N_GEN * 3,
            'total_draws': len(draws), 'eval_draws': N_EVAL,
            'seed': SEED, 'elapsed_seconds': round(elapsed, 1),
        },
        'evolved_strategies': evolved_pop,
        'reference_strategies': ref_summary,
        'head_to_head': comparisons,
        'conclusion': {
            'improvement_found': improvement_found,
            'statistically_significant': significant_improvement,
            'worth_deploying': worth_deploying,
            'total_validated': total_val,
            'total_rejected': rejected,
        },
    }

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

    out_path = os.path.join(project_root, 'evolved_strategy_population.json')
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
    print(f"  Saved: {out_path}")

    val_path = os.path.join(project_root, 'validated_evolved_strategies.json')
    with open(val_path, 'w') as f:
        json.dump({'validated': evolved_pop, 'reference': ref_summary, 'comparisons': comparisons},
                  f, indent=2, cls=NumpyEncoder)
    print(f"  Saved: {val_path}")

    print(f"\n  Total elapsed: {elapsed:.0f}s")
    print(f"{'='*72}")
    print("  EVOLUTION ENGINE COMPLETE")
    print(f"{'='*72}\n")

    return output


if __name__ == '__main__':
    main()
