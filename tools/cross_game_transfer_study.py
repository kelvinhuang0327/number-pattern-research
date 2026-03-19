#!/usr/bin/env python3
"""
Cross-Game Strategy Transfer Study
====================================
2026-03-16 | Transfer 539 methodology to BIG_LOTTO & POWER_LOTTO

7 Phases:
  1. Signal Re-Training (ACB, MidFreq, Markov, Fourier per game)
  2. Single Bet Benchmark (walk-forward, 3-window, perm test)
  3. Multi-Bet Orthogonal Strategy (1-5 bets)
  4. Strategy Evolution (pop=200, gen=50)
  5. Strategy Space Exploration (pool, fusion, efficiency frontier)
  6. Statistical Validation (full perm test + McNemar)
  7. Economic Reality Check (EV, ROI, Monte Carlo bankroll)

Usage: python3 tools/cross_game_transfer_study.py
"""
import os
import sys
import json
import math
import time
import copy
import numpy as np
from collections import Counter
from itertools import combinations

SEED = 42
np.random.seed(SEED)
rng = np.random.default_rng(SEED)

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager


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


# ==============================================================
# Game Configurations
# ==============================================================

GAMES = {
    'BIG_LOTTO': {
        'max_num': 49, 'pick': 6,
        'boundary_low': 8, 'boundary_high': 44,
        'cost': 50,
        'prizes': {3: 400, 4: 5000, 5: 200_000, 6: 25_000_000},
        'match_threshold': 3,
    },
    'POWER_LOTTO': {
        'max_num': 38, 'pick': 6,
        'boundary_low': 6, 'boundary_high': 33,
        'cost': 100,
        'prizes': {3: 400, 4: 1000, 5: 20_000, 6: 100_000_000},
        'match_threshold': 3,
    },
}

# Reference from 539
REF_539 = {
    'max_num': 39, 'pick': 5, 'baseline_m2': 0.1140,
    'best_1bet_edge': 0.0327, 'best_2bet_edge': 0.0813,
    'best_3bet_edge': 0.0850,
}


def compute_baseline(max_num, pick, match_threshold, n_bets=1):
    """Exact M{match_threshold}+ baseline for n bets."""
    total = math.comb(max_num, pick)
    p_single = sum(
        math.comb(pick, m) * math.comb(max_num - pick, pick - m)
        for m in range(match_threshold, pick + 1)
    ) / total
    return 1 - (1 - p_single) ** n_bets, p_single


# ==============================================================
# Phase 1: Signal Functions (parameterized)
# ==============================================================

def compute_acb(history, max_num, pick, window=100):
    """ACB signal: freq_deficit*0.4 + gap_score*0.6 + boundary + mod3."""
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
    bl = max_num // 6  # ~boundary low
    bh = max_num - bl   # ~boundary high
    scores = np.zeros(max_num)
    for n in range(1, max_num + 1):
        fd = expected - counter[n]
        gs = (len(recent) - last_seen.get(n, -1)) / max(len(recent) / 2, 1)
        bb = 1.2 if (n <= bl or n >= bh) else 1.0
        mb = 1.1 if n % 3 == 0 else 1.0
        scores[n - 1] = (fd * 0.4 + gs * 0.6) * bb * mb
    return scores


def compute_midfreq(history, max_num, pick, window=100):
    """MidFreq signal: numbers closest to expected frequency."""
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


def compute_markov(history, max_num, pick, window=30):
    """Markov transition signal from last draw."""
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


def compute_fourier(history, max_num, pick, window=500):
    """Fourier FFT cycle phase score."""
    from numpy.fft import fft, fftfreq
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    if w < 50:
        return np.zeros(max_num)
    scores = np.zeros(max_num)
    for n in range(1, max_num + 1):
        bh = np.zeros(w)
        for idx, d in enumerate(h):
            if n in d['numbers'][:pick]:
                bh[idx] = 1
        if sum(bh) < 2:
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)[0]
        if len(idx_pos) == 0:
            continue
        pos_yf = np.abs(yf[idx_pos])
        pos_xf = xf[idx_pos]
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n - 1] = 1.0 / (abs(gap - period) + 1.0)
    return scores


SIGNAL_FUNCS = {
    'acb': compute_acb,
    'midfreq': compute_midfreq,
    'markov': compute_markov,
    'fourier': compute_fourier,
}
SIGNAL_NAMES = list(SIGNAL_FUNCS.keys())


# ==============================================================
# Phase 1: Precompute signals
# ==============================================================

def precompute_signals(draws, max_num, pick, start_idx=200):
    """Precompute all 4 signal score arrays for walk-forward."""
    T = len(draws)
    actual_start = max(start_idx, T - 1800)
    n_eval = T - actual_start
    print(f"  Precomputing signals for {n_eval} draws (idx {actual_start}..{T-1})...")

    sigs = {name: np.zeros((n_eval, max_num)) for name in SIGNAL_NAMES}
    actuals = np.zeros((n_eval, max_num), dtype=bool)

    t0 = time.time()
    for idx, t in enumerate(range(actual_start, T)):
        hist_slice = draws[max(0, t - 600):t]
        for name, fn in SIGNAL_FUNCS.items():
            sigs[name][idx] = fn(hist_slice, max_num, pick)
        actual = set(draws[t]['numbers'][:pick])
        for n in actual:
            if 1 <= n <= max_num:
                actuals[idx, n - 1] = True
        if (idx + 1) % 300 == 0:
            print(f"    {idx+1}/{n_eval} done ({time.time()-t0:.1f}s)")
    print(f"  Signal precomputation: {time.time()-t0:.1f}s")
    return sigs, actuals, actual_start


# ==============================================================
# Phase 2: Single Bet Benchmark
# ==============================================================

def evaluate_signal_single_bet(sig_scores, actuals, pick, baseline, windows=[150, 500, 1500]):
    """Walk-forward evaluation of a single signal (precomputed)."""
    n_eval = sig_scores.shape[0]
    hits = np.zeros(n_eval, dtype=bool)
    for t in range(n_eval):
        top_k = np.argsort(sig_scores[t])[-pick:]
        actual = actuals[t]
        match_count = sum(actual[k] for k in top_k)
        hits[t] = match_count >= 3  # M3+
    # Three-window
    results = {}
    for w in windows:
        if n_eval < w:
            results[f'edge_{w}p'] = None
            results[f'rate_{w}p'] = None
            continue
        window_hits = hits[-w:]
        rate = float(np.mean(window_hits))
        edge = rate - baseline
        results[f'edge_{w}p'] = round(edge, 5)
        results[f'rate_{w}p'] = round(rate, 5)
    # Full OOS
    full_rate = float(np.mean(hits))
    full_edge = full_rate - baseline
    n_hits = int(np.sum(hits))
    # z-score
    if n_eval > 0 and baseline > 0:
        z = (full_rate - baseline) / max(math.sqrt(baseline * (1 - baseline) / n_eval), 1e-9)
    else:
        z = 0.0
    results['full_rate'] = round(full_rate, 5)
    results['full_edge'] = round(full_edge, 5)
    results['n_hits'] = n_hits
    results['n_oos'] = n_eval
    results['z_score'] = round(z, 3)
    results['hits'] = hits
    # Three-window stability
    w_edges = [results.get(f'edge_{w}p') for w in windows]
    results['three_window_pass'] = all(e is not None and e > 0 for e in w_edges)
    return results


def permutation_test_precomputed(sig_scores, actuals, pick, baseline, n_perm=99, seed=42):
    """Permutation test using precomputed signals: shuffle actuals rows."""
    n_eval = sig_scores.shape[0]
    # Real edge
    hits = np.zeros(n_eval, dtype=bool)
    for t in range(n_eval):
        top_k = np.argsort(sig_scores[t])[-pick:]
        hits[t] = sum(actuals[t, k] for k in top_k) >= 3
    real_rate = float(np.mean(hits))
    real_edge = real_rate - baseline

    prng = np.random.RandomState(seed)
    exceed = 0
    shuffle_edges = []
    for _ in range(n_perm):
        perm_idx = prng.permutation(n_eval)
        shuffled_actuals = actuals[perm_idx]
        s_hits = np.zeros(n_eval, dtype=bool)
        for t in range(n_eval):
            top_k = np.argsort(sig_scores[t])[-pick:]
            s_hits[t] = sum(shuffled_actuals[t, k] for k in top_k) >= 3
        s_rate = float(np.mean(s_hits))
        s_edge = s_rate - baseline
        shuffle_edges.append(s_edge)
        if s_edge >= real_edge:
            exceed += 1

    p_emp = (exceed + 1) / (n_perm + 1)
    shuffle_mean = float(np.mean(shuffle_edges))
    shuffle_std = float(np.std(shuffle_edges)) if np.std(shuffle_edges) > 0 else 1e-6
    cohens_d = (real_edge - shuffle_mean) / shuffle_std

    if p_emp < 0.05:
        verdict = 'SIGNAL_DETECTED'
    elif p_emp < 0.10:
        verdict = 'MARGINAL'
    else:
        verdict = 'NO_SIGNAL'

    return {
        'real_edge': round(real_edge, 5),
        'real_rate': round(real_rate, 5),
        'p_emp': round(p_emp, 4),
        'cohens_d': round(cohens_d, 3),
        'verdict': verdict,
        'n_perm': n_perm,
        'shuffle_mean': round(shuffle_mean, 5),
        'shuffle_std': round(shuffle_std, 5),
    }


def run_phase2(game_name, cfg, draws):
    """Phase 2: Evaluate each signal independently."""
    print(f"\n{'='*60}")
    print(f"  Phase 2: Single Bet Benchmark — {game_name}")
    print(f"{'='*60}")

    max_num = cfg['max_num']
    pick = cfg['pick']
    baseline_nb, baseline_1b = compute_baseline(max_num, pick, cfg['match_threshold'], 1)
    print(f"  M3+ single-bet baseline: {baseline_1b*100:.3f}%")
    print(f"  Total draws: {len(draws)}")

    sigs, actuals, start_idx = precompute_signals(draws, max_num, pick)
    results = {}
    for sig_name in SIGNAL_NAMES:
        print(f"\n  --- {sig_name.upper()} ---")
        res = evaluate_signal_single_bet(sigs[sig_name], actuals, pick, baseline_1b)
        print(f"  Full OOS: rate={res['full_rate']*100:.3f}%, edge={res['full_edge']*100:+.3f}%, "
              f"z={res['z_score']:.3f}, hits={res['n_hits']}/{res['n_oos']}")
        for w in [150, 500, 1500]:
            e = res.get(f'edge_{w}p')
            r = res.get(f'rate_{w}p')
            if e is not None:
                print(f"    {w}p: rate={r*100:.3f}%, edge={e*100:+.3f}%")
        print(f"  Three-window pass: {res['three_window_pass']}")

        # Permutation test (99 shuffles for screening)
        perm = permutation_test_precomputed(sigs[sig_name], actuals, pick, baseline_1b, n_perm=99)
        print(f"  Perm test: p={perm['p_emp']:.4f}, d={perm['cohens_d']:.3f} → {perm['verdict']}")

        res_clean = {k: v for k, v in res.items() if k != 'hits'}
        res_clean['perm'] = perm
        results[sig_name] = res_clean

    return results, sigs, actuals, start_idx, baseline_1b


# ==============================================================
# Phase 3: Multi-Bet Orthogonal Strategy
# ==============================================================

def build_orthogonal_bets(sigs, signal_order, t, pick, max_num):
    """Build orthogonal bets at time t using signal ranking."""
    used = set()
    bets = []
    for sig_name in signal_order:
        scores = sigs[sig_name][t].copy()
        for u in used:
            scores[u] = -1e9  # exclude already used
        top_k = np.argsort(scores)[-pick:]
        bet = set(top_k)
        bets.append(bet)
        used.update(bet)
    return bets


def run_phase3(game_name, cfg, sigs, actuals, signal_order, baseline_1b):
    """Phase 3: Multi-bet orthogonal evaluation."""
    print(f"\n{'='*60}")
    print(f"  Phase 3: Multi-Bet Orthogonal — {game_name}")
    print(f"{'='*60}")

    max_num = cfg['max_num']
    pick = cfg['pick']
    n_eval = actuals.shape[0]

    results = {}
    for n_bets in range(1, min(6, len(signal_order) + 1)):
        baseline_nb, _ = compute_baseline(max_num, pick, cfg['match_threshold'], n_bets)
        signals_used = signal_order[:n_bets]

        hits = np.zeros(n_eval, dtype=bool)
        for t in range(n_eval):
            bets = build_orthogonal_bets(sigs, signals_used, t, pick, max_num)
            for bet in bets:
                match_count = sum(actuals[t, k] for k in bet)
                if match_count >= 3:
                    hits[t] = True
                    break

        rate = float(np.mean(hits))
        edge = rate - baseline_nb
        n_hits = int(np.sum(hits))
        z = (rate - baseline_nb) / max(math.sqrt(baseline_nb * (1 - baseline_nb) / n_eval), 1e-9)

        w_results = {}
        for w in [150, 500, 1500]:
            if n_eval >= w:
                w_rate = float(np.mean(hits[-w:]))
                w_results[f'edge_{w}p'] = round(w_rate - baseline_nb, 5)
                w_results[f'rate_{w}p'] = round(w_rate, 5)
        three_pass = all(w_results.get(f'edge_{w}p', -1) > 0 for w in [150, 500, 1500])

        print(f"\n  {n_bets}-bet ({', '.join(signals_used)}):")
        print(f"    baseline={baseline_nb*100:.3f}%, rate={rate*100:.3f}%, edge={edge*100:+.3f}%, "
              f"z={z:.3f}, hits={n_hits}/{n_eval}")
        for w in [150, 500, 1500]:
            e = w_results.get(f'edge_{w}p')
            if e is not None:
                print(f"    {w}p: edge={e*100:+.3f}%")
        print(f"    Three-window pass: {three_pass}")

        marginal_edge = edge - (results.get(n_bets - 1, {}).get('edge', 0) if n_bets > 1 else 0)

        results[n_bets] = {
            'n_bets': n_bets,
            'signals': signals_used,
            'baseline': round(baseline_nb, 5),
            'rate': round(rate, 5),
            'edge': round(edge, 5),
            'z_score': round(z, 3),
            'n_hits': n_hits,
            'n_oos': n_eval,
            'three_window_pass': three_pass,
            'marginal_edge': round(marginal_edge, 5),
            **w_results,
        }

    return results


# ==============================================================
# Phase 4: Strategy Evolution
# ==============================================================

FUSION_TYPES = ['weighted_rank', 'score_blend', 'voting', 'rank_product']
NONLINEAR_TYPES = ['none', 'sqrt', 'square', 'log', 'sigmoid']
POP_SIZE = 200
N_GEN = 50
ELITE_FRAC = 0.10
MUTATION_RATE = 0.35
CROSSOVER_RATE = 0.55
TOURNAMENT_SIZE = 5


def random_genome(n_bets=None):
    g = {
        'signal_weights': [rng.uniform(0.01, 1.0) for _ in range(4)],
        'fusion_type': str(rng.choice(FUSION_TYPES)),
        'nonlinear': str(rng.choice(NONLINEAR_TYPES)),
        'gate_signal': int(rng.choice([-1, 0, 1, 2, 3])),
        'gate_threshold': float(rng.uniform(0.3, 0.9)),
        'n_bets': n_bets if n_bets else int(rng.choice([1, 2, 3])),
        'orthogonal': True,
        'diversity_bonus': float(rng.uniform(0.0, 0.3)),
    }
    wsum = sum(g['signal_weights'])
    g['signal_weights'] = [w / wsum for w in g['signal_weights']]
    return g


def mutate_genome(g):
    g = copy.deepcopy(g)
    mt = rng.choice(['weights', 'fusion', 'nonlinear', 'gate', 'diversity'])
    if mt == 'weights':
        idx = int(rng.integers(0, 4))
        g['signal_weights'][idx] = float(rng.uniform(0.01, 1.0))
        wsum = sum(g['signal_weights'])
        g['signal_weights'] = [w / wsum for w in g['signal_weights']]
    elif mt == 'fusion':
        g['fusion_type'] = str(rng.choice(FUSION_TYPES))
    elif mt == 'nonlinear':
        g['nonlinear'] = str(rng.choice(NONLINEAR_TYPES))
    elif mt == 'gate':
        g['gate_signal'] = int(rng.choice([-1, 0, 1, 2, 3]))
        g['gate_threshold'] = float(rng.uniform(0.3, 0.9))
    else:
        g['diversity_bonus'] = float(rng.uniform(0.0, 0.3))
    return g


def crossover_genomes(a, b):
    child = copy.deepcopy(a)
    alpha = float(rng.uniform(0.3, 0.7))
    child['signal_weights'] = [alpha * a['signal_weights'][i] + (1 - alpha) * b['signal_weights'][i]
                                for i in range(4)]
    wsum = sum(child['signal_weights'])
    child['signal_weights'] = [w / wsum for w in child['signal_weights']]
    for field in ['fusion_type', 'nonlinear', 'gate_signal', 'gate_threshold', 'diversity_bonus']:
        if rng.random() < 0.5:
            child[field] = copy.deepcopy(b[field])
    return child


def apply_nonlinear(scores, nl_type):
    if nl_type == 'none':
        return scores
    elif nl_type == 'sqrt':
        return np.sign(scores) * np.sqrt(np.abs(scores))
    elif nl_type == 'square':
        return np.sign(scores) * scores ** 2
    elif nl_type == 'log':
        return np.sign(scores) * np.log1p(np.abs(scores))
    elif nl_type == 'sigmoid':
        return 1.0 / (1.0 + np.exp(-scores))
    return scores


def fuse_signals(sigs_t, genome, max_num):
    """Fuse 4 signal scores at time t using genome parameters."""
    w = genome['signal_weights']
    nl = genome['nonlinear']
    fusion = genome['fusion_type']

    transformed = []
    for i, name in enumerate(SIGNAL_NAMES):
        s = apply_nonlinear(sigs_t[name].copy(), nl)
        transformed.append(s)

    if genome['gate_signal'] >= 0 and genome['gate_signal'] < 4:
        gate_s = transformed[genome['gate_signal']]
        threshold_val = np.percentile(gate_s, genome['gate_threshold'] * 100)
        gate_mask = gate_s >= threshold_val
    else:
        gate_mask = np.ones(max_num, dtype=bool)

    if fusion == 'score_blend':
        combined = sum(w[i] * transformed[i] for i in range(4))
    elif fusion == 'weighted_rank':
        ranks = [np.argsort(np.argsort(s)).astype(float) for s in transformed]
        combined = sum(w[i] * ranks[i] for i in range(4))
    elif fusion == 'voting':
        combined = np.zeros(max_num)
        for i in range(4):
            top10 = np.argsort(transformed[i])[-10:]
            for rank, idx in enumerate(top10):
                combined[idx] += w[i] * (rank + 1) / 10
    elif fusion == 'rank_product':
        log_ranks = np.zeros(max_num)
        for i in range(4):
            ranks = np.argsort(np.argsort(transformed[i])).astype(float) + 1
            log_ranks += w[i] * np.log(ranks)
        combined = log_ranks
    else:
        combined = sum(w[i] * transformed[i] for i in range(4))

    combined[~gate_mask] *= 0.1
    return combined


def evaluate_genome(genome, sigs_dict, actuals, pick, baseline, eval_window=300):
    """Evaluate genome fitness on last eval_window draws."""
    n_eval = actuals.shape[0]
    start = max(0, n_eval - eval_window)
    n_bets = genome['n_bets']
    max_num = actuals.shape[1]

    hits = 0
    total = 0
    for t in range(start, n_eval):
        sigs_t = {name: sigs_dict[name][t] for name in SIGNAL_NAMES}
        combined = fuse_signals(sigs_t, genome, max_num)

        used = set()
        any_hit = False
        for b in range(n_bets):
            scores = combined.copy()
            for u in used:
                scores[u] = -1e9
            top_k = np.argsort(scores)[-pick:]
            match_count = sum(actuals[t, k] for k in top_k)
            if match_count >= 3:
                any_hit = True
            if genome['orthogonal']:
                used.update(top_k.tolist())

        if any_hit:
            hits += 1
        total += 1

    rate = hits / max(total, 1)
    nb_baseline, _ = compute_baseline(max_num, pick, 3, n_bets)
    edge = rate - nb_baseline
    return edge


def run_phase4(game_name, cfg, sigs, actuals):
    """Phase 4: Strategy Evolution."""
    print(f"\n{'='*60}")
    print(f"  Phase 4: Strategy Evolution — {game_name}")
    print(f"{'='*60}")

    max_num = cfg['max_num']
    pick = cfg['pick']
    _, baseline_1b = compute_baseline(max_num, pick, cfg['match_threshold'], 1)

    results = {}
    for target_bets in [1, 2, 3]:
        print(f"\n  --- Evolution for {target_bets}-bet ---")
        nb_baseline, _ = compute_baseline(max_num, pick, cfg['match_threshold'], target_bets)

        # Initialize population
        population = [random_genome(n_bets=target_bets) for _ in range(POP_SIZE)]
        for g in population:
            g['fitness'] = evaluate_genome(g, sigs, actuals, pick, baseline_1b, eval_window=300)

        best_ever = max(population, key=lambda g: g['fitness'])
        t0 = time.time()

        for gen in range(N_GEN):
            # Sort by fitness
            population.sort(key=lambda g: g['fitness'], reverse=True)
            n_elite = max(1, int(POP_SIZE * ELITE_FRAC))
            new_pop = population[:n_elite]

            while len(new_pop) < POP_SIZE:
                r = rng.random()
                if r < CROSSOVER_RATE:
                    # Tournament selection
                    idxs = rng.choice(len(population), size=TOURNAMENT_SIZE, replace=False)
                    parents = sorted([population[i] for i in idxs], key=lambda g: g['fitness'], reverse=True)
                    child = crossover_genomes(parents[0], parents[1])
                elif r < CROSSOVER_RATE + MUTATION_RATE:
                    idx = int(rng.choice(len(population[:POP_SIZE // 2])))
                    child = mutate_genome(population[idx])
                else:
                    child = random_genome(n_bets=target_bets)

                child['fitness'] = evaluate_genome(child, sigs, actuals, pick, baseline_1b, eval_window=300)
                new_pop.append(child)

            population = new_pop
            gen_best = max(population, key=lambda g: g['fitness'])
            if gen_best['fitness'] > best_ever['fitness']:
                best_ever = copy.deepcopy(gen_best)

            if (gen + 1) % 10 == 0:
                print(f"    Gen {gen+1}: best_edge={gen_best['fitness']*100:+.3f}%, "
                      f"ever_best={best_ever['fitness']*100:+.3f}%")

        elapsed = time.time() - t0
        print(f"    Evolution done: {elapsed:.1f}s")
        print(f"    Best genome: edge={best_ever['fitness']*100:+.3f}%")
        print(f"      weights={[round(w,3) for w in best_ever['signal_weights']]}")
        print(f"      fusion={best_ever['fusion_type']}, nl={best_ever['nonlinear']}")
        print(f"      gate={best_ever['gate_signal']}, gate_th={best_ever['gate_threshold']:.2f}")

        # Full validation of best
        full_edge = evaluate_genome(best_ever, sigs, actuals, pick, baseline_1b, eval_window=actuals.shape[0])
        print(f"    Full OOS edge: {full_edge*100:+.3f}%")

        best_clean = {k: v for k, v in best_ever.items() if k != 'fitness'}
        best_clean['fitness'] = best_ever['fitness']
        best_clean['full_edge'] = full_edge
        results[target_bets] = best_clean

    return results


# ==============================================================
# Phase 5: Strategy Space Exploration
# ==============================================================

def run_phase5(game_name, cfg, sigs, actuals, signal_order, baseline_1b):
    """Phase 5: Pool expansion, fusion vs orthogonal, efficiency frontier."""
    print(f"\n{'='*60}")
    print(f"  Phase 5: Strategy Space Exploration — {game_name}")
    print(f"{'='*60}")

    max_num = cfg['max_num']
    pick = cfg['pick']
    n_eval = actuals.shape[0]
    results = {}

    # 5a. Pool expansion test
    print("\n  --- 5a. Pool Expansion ---")
    pool_results = {}
    for pool_size in [pick, pick + 2, pick + 4, pick + 6]:
        for sig_name in SIGNAL_NAMES:
            pool_hits = 0
            for t in range(n_eval):
                top_k = np.argsort(sigs[sig_name][t])[-pool_size:]
                # Try all C(pool, pick) subsets — but only if pool small enough
                if pool_size <= pick + 2:
                    for combo in combinations(top_k, pick):
                        match = sum(actuals[t, k] for k in combo)
                        if match >= 3:
                            pool_hits += 1
                            break
                else:
                    # Just take top-pick from pool
                    top_p = top_k[-pick:]
                    match = sum(actuals[t, k] for k in top_p)
                    if match >= 3:
                        pool_hits += 1
            rate = pool_hits / n_eval
            edge = rate - baseline_1b
            key = f"{sig_name}_pool{pool_size}"
            pool_results[key] = {'rate': round(rate, 5), 'edge': round(edge, 5)}
            print(f"    {key}: rate={rate*100:.3f}%, edge={edge*100:+.3f}%")
    results['pool_expansion'] = pool_results

    # 5b. Efficiency frontier (1-5 bets)
    print("\n  --- 5b. Efficiency Frontier ---")
    frontier = {}
    prev_edge = 0
    for n_bets in range(1, 6):
        nb_baseline, _ = compute_baseline(max_num, pick, cfg['match_threshold'], n_bets)
        sig_used = signal_order[:min(n_bets, len(signal_order))]
        hits = np.zeros(n_eval, dtype=bool)
        for t in range(n_eval):
            bets = build_orthogonal_bets(sigs, sig_used, t, pick, max_num)
            for bet in bets:
                if sum(actuals[t, k] for k in bet) >= 3:
                    hits[t] = True
                    break
        rate = float(np.mean(hits))
        edge = rate - nb_baseline
        marginal = edge - prev_edge
        cost = n_bets * cfg['cost']
        efficiency = edge / cost * 10000 if cost > 0 else 0
        frontier[n_bets] = {
            'n_bets': n_bets,
            'baseline': round(nb_baseline, 5),
            'rate': round(rate, 5),
            'edge': round(edge, 5),
            'marginal_edge': round(marginal, 5),
            'cost': cost,
            'efficiency': round(efficiency, 3),
        }
        print(f"    {n_bets}-bet: edge={edge*100:+.3f}%, marginal={marginal*100:+.3f}%, "
              f"cost={cost}, eff={efficiency:.3f}")
        prev_edge = edge
    results['efficiency_frontier'] = frontier

    return results


# ==============================================================
# Phase 6: Statistical Validation
# ==============================================================

def mcnemar_test(hits_a, hits_b):
    """McNemar head-to-head test. Returns dict with net, chi2, p_value."""
    a_only = int(np.sum(hits_a & ~hits_b))  # A hits but B misses
    b_only = int(np.sum(~hits_a & hits_b))  # B hits but A misses
    both = int(np.sum(hits_a & hits_b))
    neither = int(np.sum(~hits_a & ~hits_b))
    net = a_only - b_only
    denom = a_only + b_only
    if denom == 0:
        return {'net': 0, 'chi2': 0.0, 'p_value': 1.0, 'a_only': a_only, 'b_only': b_only}
    chi2 = (abs(a_only - b_only) - 1) ** 2 / denom  # continuity correction
    from scipy.stats import chi2 as chi2_dist
    p_value = 1 - chi2_dist.cdf(chi2, df=1)
    return {
        'net': net,
        'chi2': round(chi2, 3),
        'p_value': round(p_value, 4),
        'a_only': a_only,
        'b_only': b_only,
        'both': both,
        'neither': neither,
    }


def run_phase6(game_name, cfg, sigs, actuals, signal_order, baseline_1b):
    """Phase 6: Full validation for best candidates."""
    print(f"\n{'='*60}")
    print(f"  Phase 6: Statistical Validation — {game_name}")
    print(f"{'='*60}")

    max_num = cfg['max_num']
    pick = cfg['pick']
    n_eval = actuals.shape[0]
    results = {}

    # Full perm test (200 shuffles) for each signal
    for sig_name in signal_order[:3]:  # Top 3 signals only
        print(f"\n  --- Full perm test: {sig_name} (200 shuffles) ---")
        perm = permutation_test_precomputed(sigs[sig_name], actuals, pick, baseline_1b, n_perm=200)
        print(f"    p={perm['p_emp']:.4f}, d={perm['cohens_d']:.3f} → {perm['verdict']}")
        results[f'{sig_name}_full_perm'] = perm

    # McNemar: best signal vs 2nd best
    if len(signal_order) >= 2:
        print(f"\n  --- McNemar: {signal_order[0]} vs {signal_order[1]} ---")
        hits_a = np.zeros(n_eval, dtype=bool)
        hits_b = np.zeros(n_eval, dtype=bool)
        for t in range(n_eval):
            top_a = np.argsort(sigs[signal_order[0]][t])[-pick:]
            top_b = np.argsort(sigs[signal_order[1]][t])[-pick:]
            hits_a[t] = sum(actuals[t, k] for k in top_a) >= 3
            hits_b[t] = sum(actuals[t, k] for k in top_b) >= 3
        mcn = mcnemar_test(hits_a, hits_b)
        print(f"    net={mcn['net']}, chi2={mcn['chi2']}, p={mcn['p_value']}")
        results['mcnemar_top2'] = mcn

    # Best orthogonal multi-bet: full perm test
    for n_bets in [2, 3]:
        print(f"\n  --- Full perm test: {n_bets}-bet orthogonal ---")
        nb_baseline, _ = compute_baseline(max_num, pick, cfg['match_threshold'], n_bets)
        sig_used = signal_order[:min(n_bets, len(signal_order))]

        # Real hits
        hits = np.zeros(n_eval, dtype=bool)
        for t in range(n_eval):
            bets = build_orthogonal_bets(sigs, sig_used, t, pick, max_num)
            for bet in bets:
                if sum(actuals[t, k] for k in bet) >= 3:
                    hits[t] = True
                    break
        real_rate = float(np.mean(hits))
        real_edge = real_rate - nb_baseline

        # Shuffle
        prng = np.random.RandomState(SEED)
        exceed = 0
        n_perm = 200
        for _ in range(n_perm):
            perm_idx = prng.permutation(n_eval)
            shuffled = actuals[perm_idx]
            s_hits = np.zeros(n_eval, dtype=bool)
            for t in range(n_eval):
                bets = build_orthogonal_bets(sigs, sig_used, t, pick, max_num)
                for bet in bets:
                    if sum(shuffled[t, k] for k in bet) >= 3:
                        s_hits[t] = True
                        break
            s_rate = float(np.mean(s_hits))
            if s_rate - nb_baseline >= real_edge:
                exceed += 1

        p_emp = (exceed + 1) / (n_perm + 1)
        verdict = 'SIGNAL_DETECTED' if p_emp < 0.05 else ('MARGINAL' if p_emp < 0.10 else 'NO_SIGNAL')
        print(f"    edge={real_edge*100:+.3f}%, p={p_emp:.4f} → {verdict}")
        results[f'{n_bets}bet_perm'] = {
            'real_edge': round(real_edge, 5),
            'p_emp': round(p_emp, 4),
            'verdict': verdict,
            'n_perm': n_perm,
        }

    return results


# ==============================================================
# Phase 7: Economic Reality Check
# ==============================================================

def run_phase7(game_name, cfg, best_edge, n_bets_best):
    """Phase 7: EV, ROI, Monte Carlo bankroll simulation."""
    print(f"\n{'='*60}")
    print(f"  Phase 7: Economic Reality Check — {game_name}")
    print(f"{'='*60}")

    max_num = cfg['max_num']
    pick = cfg['pick']
    cost = cfg['cost']
    prizes = cfg['prizes']
    total = math.comb(max_num, pick)

    # Exact probabilities
    probs = {}
    for m in range(0, pick + 1):
        p = math.comb(pick, m) * math.comb(max_num - pick, pick - m) / total
        probs[m] = p
        print(f"  P(M{m}) = {p:.6f} ({p*100:.4f}%)")

    # EV without edge
    ev_base = sum(prizes.get(m, 0) * probs[m] for m in range(pick + 1))
    roi_base = (ev_base - cost) / cost * 100
    print(f"\n  Base EV = {ev_base:.2f} NTD (cost={cost}), ROI = {roi_base:+.2f}%")

    # EV with edge (approximate: scale M3+ probability by (1 + edge/baseline))
    baseline_1b = sum(probs[m] for m in range(3, pick + 1))
    if baseline_1b > 0 and best_edge > 0:
        boost = 1 + best_edge / baseline_1b
        ev_edge = sum(prizes.get(m, 0) * probs[m] * (boost if m >= 3 else 1.0) for m in range(pick + 1))
        roi_edge = (ev_edge - cost) / cost * 100
        print(f"  With edge ({best_edge*100:+.3f}%): EV = {ev_edge:.2f} NTD, ROI = {roi_edge:+.2f}%")
    else:
        ev_edge = ev_base
        roi_edge = roi_base

    # Breakeven edge
    deficit = cost - ev_base
    if deficit > 0 and baseline_1b > 0:
        # What M3+ rate is needed for EV = cost?
        ev_m3_plus = sum(prizes.get(m, 0) * probs[m] for m in range(3, pick + 1))
        if ev_m3_plus > 0:
            breakeven_mult = deficit / ev_m3_plus + 1
            breakeven_edge = baseline_1b * (breakeven_mult - 1)
            print(f"  Breakeven edge needed: +{breakeven_edge*100:.2f}% (M3+ rate ×{breakeven_mult:.2f})")

    # Monte Carlo bankroll simulation
    print(f"\n  --- Monte Carlo Bankroll Simulation ---")
    n_trajectories = 10000
    n_draws = 2000  # per trajectory
    initial_bankrolls = [5000, 10000, 50000]

    mc_results = {}
    for bankroll_init in initial_bankrolls:
        ruin_count = 0
        max_drawdowns = []
        final_bankrolls = []

        mc_rng = np.random.RandomState(SEED + bankroll_init)
        for _ in range(n_trajectories):
            bankroll = bankroll_init
            peak = bankroll_init
            max_dd = 0
            bet_cost = cost * n_bets_best

            for _ in range(n_draws):
                if bankroll < bet_cost:
                    ruin_count += 1
                    break
                bankroll -= bet_cost
                # Simulate hits
                for _ in range(n_bets_best):
                    r = mc_rng.random()
                    cumul = 0
                    for m in range(pick, -1, -1):
                        cumul += probs[m]
                        if r < cumul:
                            bankroll += prizes.get(m, 0)
                            break
                if bankroll > peak:
                    peak = bankroll
                dd = (peak - bankroll) / max(peak, 1)
                if dd > max_dd:
                    max_dd = dd

            max_drawdowns.append(max_dd)
            final_bankrolls.append(bankroll)

        ruin_rate = ruin_count / n_trajectories * 100
        median_final = float(np.median(final_bankrolls))
        p5_final = float(np.percentile(final_bankrolls, 5))
        median_dd = float(np.median(max_drawdowns)) * 100

        mc_results[bankroll_init] = {
            'ruin_rate': round(ruin_rate, 2),
            'median_final': round(median_final, 0),
            'p5_final': round(p5_final, 0),
            'median_max_drawdown': round(median_dd, 1),
        }
        print(f"    Bankroll={bankroll_init}: ruin={ruin_rate:.1f}%, "
              f"median_final={median_final:.0f}, p5={p5_final:.0f}, "
              f"max_dd_median={median_dd:.1f}%")

    return {
        'ev_base': round(ev_base, 2),
        'roi_base': round(roi_base, 2),
        'ev_with_edge': round(ev_edge, 2),
        'roi_with_edge': round(roi_edge, 2),
        'match_probabilities': {f'M{m}': round(probs[m], 6) for m in range(pick + 1)},
        'monte_carlo': mc_results,
    }


# ==============================================================
# Report Generation
# ==============================================================

def generate_game_report(game_name, cfg, phase2, phase3, phase4, phase5, phase6, phase7):
    """Generate markdown report for one game."""
    lines = [
        f"# {game_name} Strategy Transfer Report",
        f"",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"## Game Parameters",
        f"- Pool: {cfg['max_num']} numbers, pick {cfg['pick']}",
        f"- Match threshold: M{cfg['match_threshold']}+",
        f"- Cost per bet: {cfg['cost']} NTD",
        f"",
    ]

    # Phase 2: Signal Benchmark
    lines.append("## Phase 2: Signal Benchmark (Single Bet)")
    lines.append("")
    lines.append("| Signal | Full Edge | z-score | 150p | 500p | 1500p | 3-Win | Perm p | Verdict |")
    lines.append("|--------|-----------|---------|------|------|-------|-------|--------|---------|")
    for sig_name in SIGNAL_NAMES:
        r = phase2.get(sig_name, {})
        p = r.get('perm', {})
        lines.append(
            f"| {sig_name} | {r.get('full_edge', 0)*100:+.3f}% | {r.get('z_score', 0):.3f} | "
            f"{r.get('edge_150p', 0)*100 if r.get('edge_150p') is not None else 'N/A':>5} | "
            f"{r.get('edge_500p', 0)*100 if r.get('edge_500p') is not None else 'N/A':>5} | "
            f"{r.get('edge_1500p', 0)*100 if r.get('edge_1500p') is not None else 'N/A':>5} | "
            f"{'PASS' if r.get('three_window_pass') else 'FAIL'} | "
            f"{p.get('p_emp', 'N/A')} | {p.get('verdict', 'N/A')} |"
        )
    lines.append("")

    # Phase 3: Multi-bet
    lines.append("## Phase 3: Multi-Bet Orthogonal")
    lines.append("")
    lines.append("| N-Bet | Baseline | Rate | Edge | z-score | 3-Win | Marginal |")
    lines.append("|-------|----------|------|------|---------|-------|----------|")
    for n_bets in sorted(phase3.keys()):
        r = phase3[n_bets]
        lines.append(
            f"| {n_bets} | {r['baseline']*100:.3f}% | {r['rate']*100:.3f}% | "
            f"{r['edge']*100:+.3f}% | {r['z_score']:.3f} | "
            f"{'PASS' if r['three_window_pass'] else 'FAIL'} | "
            f"{r['marginal_edge']*100:+.3f}% |"
        )
    lines.append("")

    # Phase 4: Evolution
    lines.append("## Phase 4: Strategy Evolution")
    lines.append("")
    for n_bets, r in phase4.items():
        lines.append(f"### {n_bets}-bet Best Genome")
        lines.append(f"- Edge (300p): {r['fitness']*100:+.3f}%")
        lines.append(f"- Edge (full OOS): {r['full_edge']*100:+.3f}%")
        lines.append(f"- Weights: {[round(w,3) for w in r['signal_weights']]}")
        lines.append(f"- Fusion: {r['fusion_type']}, Nonlinear: {r['nonlinear']}")
        lines.append(f"- Gate: signal={r['gate_signal']}, threshold={r['gate_threshold']:.2f}")
        lines.append("")

    # Phase 5: Exploration
    lines.append("## Phase 5: Strategy Space Exploration")
    lines.append("")
    lines.append("### Efficiency Frontier")
    lines.append("| N-Bet | Edge | Marginal | Cost | Efficiency |")
    lines.append("|-------|------|----------|------|------------|")
    for n, r in sorted(phase5.get('efficiency_frontier', {}).items()):
        lines.append(f"| {n} | {r['edge']*100:+.3f}% | {r['marginal_edge']*100:+.3f}% | "
                     f"{r['cost']} | {r['efficiency']:.3f} |")
    lines.append("")

    # Phase 6: Validation
    lines.append("## Phase 6: Statistical Validation")
    lines.append("")
    for key, r in phase6.items():
        if 'verdict' in r:
            lines.append(f"- **{key}**: edge={r.get('real_edge',0)*100:+.3f}%, p={r.get('p_emp','N/A')}, {r.get('verdict','N/A')}")
        elif 'net' in r:
            lines.append(f"- **{key}**: net={r['net']}, chi2={r['chi2']}, p={r['p_value']}")
    lines.append("")

    # Phase 7: Economics
    lines.append("## Phase 7: Economic Reality Check")
    lines.append("")
    lines.append(f"- Base EV: {phase7['ev_base']:.2f} NTD, ROI: {phase7['roi_base']:+.2f}%")
    lines.append(f"- With best edge: EV={phase7['ev_with_edge']:.2f} NTD, ROI: {phase7['roi_with_edge']:+.2f}%")
    lines.append("")
    lines.append("### Monte Carlo Bankroll Simulation")
    lines.append("| Initial | Ruin Rate | Median Final | P5 Final | Max DD |")
    lines.append("|---------|-----------|--------------|----------|--------|")
    for init, r in phase7.get('monte_carlo', {}).items():
        lines.append(f"| {init} | {r['ruin_rate']}% | {r['median_final']:.0f} | "
                     f"{r['p5_final']:.0f} | {r['median_max_drawdown']}% |")
    lines.append("")

    return '\n'.join(lines)


def generate_comparison_report(results_all):
    """Generate cross-game comparison report."""
    lines = [
        "# Cross-Game Strategy Transfer Comparison",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Signal Transfer Results",
        "",
        "| Signal | 539 Edge | BIG_LOTTO Edge | BIG_LOTTO Verdict | POWER_LOTTO Edge | POWER_LOTTO Verdict |",
        "|--------|----------|----------------|-------------------|------------------|---------------------|",
    ]
    ref_539_edges = {'acb': '+3.27%', 'midfreq': '+5.06%', 'markov': '~0', 'fourier': '~+1%'}
    for sig in SIGNAL_NAMES:
        bl = results_all.get('BIG_LOTTO', {}).get('phase2', {}).get(sig, {})
        pl = results_all.get('POWER_LOTTO', {}).get('phase2', {}).get(sig, {})
        bl_perm = bl.get('perm', {})
        pl_perm = pl.get('perm', {})
        lines.append(
            f"| {sig} | {ref_539_edges.get(sig, 'N/A')} | "
            f"{bl.get('full_edge', 0)*100:+.3f}% | {bl_perm.get('verdict', 'N/A')} | "
            f"{pl.get('full_edge', 0)*100:+.3f}% | {pl_perm.get('verdict', 'N/A')} |"
        )
    lines.append("")

    # Key findings
    lines.append("## Key Findings")
    lines.append("")
    for game_name in ['BIG_LOTTO', 'POWER_LOTTO']:
        gres = results_all.get(game_name, {})
        p2 = gres.get('phase2', {})
        signals_detected = [s for s in SIGNAL_NAMES
                            if p2.get(s, {}).get('perm', {}).get('verdict') == 'SIGNAL_DETECTED']
        marginal = [s for s in SIGNAL_NAMES
                    if p2.get(s, {}).get('perm', {}).get('verdict') == 'MARGINAL']
        lines.append(f"### {game_name}")
        lines.append(f"- Signals detected: {signals_detected if signals_detected else 'NONE'}")
        lines.append(f"- Marginal signals: {marginal if marginal else 'NONE'}")
        p7 = gres.get('phase7', {})
        lines.append(f"- Base ROI: {p7.get('roi_base', 'N/A')}%")
        lines.append(f"- Best strategy ROI: {p7.get('roi_with_edge', 'N/A')}%")
        lines.append("")

    lines.append("## Final Answers")
    lines.append("")
    lines.append("1. **Do 539 signals transfer?** — See signal table above")
    lines.append("2. **New unique signals?** — None discovered (same signal families tested)")
    lines.append("3. **Best multi-bet structure?** — See Phase 3 results per game")
    lines.append("4. **Statistically validated edge?** — See Phase 6 validation")
    lines.append("5. **Does any strategy reduce house edge?** — See Phase 7 economics")
    lines.append("")

    return '\n'.join(lines)


# ==============================================================
# Main
# ==============================================================

def main():
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    results_all = {}

    for game_name, cfg in GAMES.items():
        print(f"\n{'#'*60}")
        print(f"  GAME: {game_name}")
        print(f"  {cfg['max_num']}C{cfg['pick']}, M{cfg['match_threshold']}+ threshold")
        print(f"{'#'*60}")

        draws = sorted(db.get_all_draws(game_name), key=lambda x: (x['date'], x['draw']))
        draws = [d for d in draws if d.get('numbers') and len(d['numbers']) >= cfg['pick']]
        print(f"  Total draws: {len(draws)}")

        # Phase 2: Single bet benchmark
        phase2, sigs, actuals, start_idx, baseline_1b = run_phase2(game_name, cfg, draws)

        # Rank signals by full edge
        signal_order = sorted(SIGNAL_NAMES, key=lambda s: phase2[s].get('full_edge', -1), reverse=True)
        print(f"\n  Signal ranking: {signal_order}")

        # Phase 3: Multi-bet orthogonal
        phase3 = run_phase3(game_name, cfg, sigs, actuals, signal_order, baseline_1b)

        # Phase 4: Strategy evolution
        phase4 = run_phase4(game_name, cfg, sigs, actuals)

        # Phase 5: Strategy space exploration
        phase5 = run_phase5(game_name, cfg, sigs, actuals, signal_order, baseline_1b)

        # Phase 6: Statistical validation
        phase6 = run_phase6(game_name, cfg, sigs, actuals, signal_order, baseline_1b)

        # Phase 7: Economic reality check
        best_edge = max(phase2[s].get('full_edge', 0) for s in SIGNAL_NAMES)
        phase7 = run_phase7(game_name, cfg, best_edge, n_bets_best=3)

        results_all[game_name] = {
            'config': cfg,
            'n_draws': len(draws),
            'signal_order': signal_order,
            'phase2': phase2,
            'phase3': {str(k): v for k, v in phase3.items()},
            'phase4': {str(k): v for k, v in phase4.items()},
            'phase5': phase5,
            'phase6': phase6,
            'phase7': phase7,
        }

        # Generate per-game report
        report = generate_game_report(game_name, cfg, phase2, phase3, phase4, phase5, phase6, phase7)
        report_path = os.path.join(project_root, f'{game_name}_strategy_report.md')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n  Report saved: {report_path}")

    # Save all results
    results_path = os.path.join(project_root, 'strategy_transfer_results.json')
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(results_all, f, indent=2, cls=NumpyEncoder)
    print(f"\n  Results saved: {results_path}")

    # Generate comparison report
    comp_report = generate_comparison_report(results_all)
    comp_path = os.path.join(project_root, 'cross_game_comparison.md')
    with open(comp_path, 'w', encoding='utf-8') as f:
        f.write(comp_report)
    print(f"  Comparison saved: {comp_path}")

    print(f"\n{'='*60}")
    print(f"  STUDY COMPLETE")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
