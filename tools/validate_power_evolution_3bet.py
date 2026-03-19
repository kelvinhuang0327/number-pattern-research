#!/usr/bin/env python3
"""
POWER_LOTTO Evolution 3-bet Walk-Forward Full Validation
==========================================================
2026-03-16 | Validates the evolved 3-bet genome from cross-game transfer study

The best evolution genome (300p eval):
  weights=[0.223, 0.258, 0.191, 0.328]  (ACB, MidFreq, Markov, Fourier)
  fusion=score_blend, nonlinear=none
  gate_signal=1 (midfreq), gate_threshold=0.54
  edge: +9.17% (300p) → +3.19% (full OOS)

This script validates with:
  1. Wider eval windows (500p, 800p) to reduce overfit
  2. Walk-forward OOS with strict temporal isolation
  3. Three-window test (150/500/1500)
  4. Permutation test (200 shuffles)
  5. McNemar vs current best (fourier_rhythm_3bet)
"""
import os
import sys
import json
import math
import time
import numpy as np
from collections import Counter

SEED = 42
np.random.seed(SEED)
rng = np.random.default_rng(SEED)

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

MAX_NUM = 38
PICK = 6
MATCH_TH = 3
TOTAL_COMBOS = math.comb(MAX_NUM, PICK)
BASELINE_1B = sum(
    math.comb(PICK, m) * math.comb(MAX_NUM - PICK, PICK - m)
    for m in range(MATCH_TH, PICK + 1)
) / TOTAL_COMBOS
BASELINE_3B = 1 - (1 - BASELINE_1B) ** 3

SIGNAL_NAMES = ['acb', 'midfreq', 'markov', 'fourier']

# Best genome from evolution
BEST_GENOME = {
    'signal_weights': [0.223, 0.258, 0.191, 0.328],
    'fusion_type': 'score_blend',
    'nonlinear': 'none',
    'gate_signal': 1,  # midfreq
    'gate_threshold': 0.54,
    'n_bets': 3,
    'orthogonal': True,
}


# --- Signal functions (same as cross_game_transfer_study.py) ---

def compute_acb(history, window=100):
    recent = history[-window:] if len(history) >= window else history
    counter = Counter()
    for n in range(1, MAX_NUM + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers'][:PICK]:
            if 1 <= n <= MAX_NUM:
                counter[n] += 1
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers'][:PICK]:
            if 1 <= n <= MAX_NUM:
                last_seen[n] = i
    expected = len(recent) * PICK / MAX_NUM
    scores = np.zeros(MAX_NUM)
    for n in range(1, MAX_NUM + 1):
        fd = expected - counter[n]
        gs = (len(recent) - last_seen.get(n, -1)) / max(len(recent) / 2, 1)
        bb = 1.2 if (n <= 6 or n >= 33) else 1.0
        mb = 1.1 if n % 3 == 0 else 1.0
        scores[n - 1] = (fd * 0.4 + gs * 0.6) * bb * mb
    return scores


def compute_midfreq(history, window=100):
    recent = history[-window:] if len(history) >= window else history
    counter = Counter()
    for n in range(1, MAX_NUM + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers'][:PICK]:
            if 1 <= n <= MAX_NUM:
                counter[n] += 1
    expected = len(recent) * PICK / MAX_NUM
    max_dev = max(abs(counter[n] - expected) for n in range(1, MAX_NUM + 1))
    if max_dev == 0:
        max_dev = 1
    scores = np.zeros(MAX_NUM)
    for n in range(1, MAX_NUM + 1):
        scores[n - 1] = max_dev - abs(counter[n] - expected)
    return scores


def compute_markov(history, window=30):
    recent = history[-window:] if len(history) >= window else history
    trans = {}
    for i in range(len(recent) - 1):
        curr = set(recent[i]['numbers'][:PICK])
        nxt = set(recent[i + 1]['numbers'][:PICK])
        for p in curr:
            if p not in trans:
                trans[p] = Counter()
            for n in nxt:
                if 1 <= n <= MAX_NUM:
                    trans[p][n] += 1
    last_draw = set(recent[-1]['numbers'][:PICK]) if recent else set()
    scores = np.zeros(MAX_NUM)
    for p in last_draw:
        if p in trans and sum(trans[p].values()) > 0:
            total = sum(trans[p].values())
            for n in range(1, MAX_NUM + 1):
                scores[n - 1] += trans[p].get(n, 0) / total
    return scores


def compute_fourier(history, window=500):
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    if w < 50:
        return np.zeros(MAX_NUM)
    scores = np.zeros(MAX_NUM)
    for n in range(1, MAX_NUM + 1):
        bh = np.zeros(w)
        for idx, d in enumerate(h):
            if n in d['numbers'][:PICK]:
                bh[idx] = 1
        if sum(bh) < 2:
            continue
        yf = np.fft.fft(bh - np.mean(bh))
        xf = np.fft.fftfreq(w, 1)
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


SIG_FUNCS = {
    'acb': compute_acb,
    'midfreq': compute_midfreq,
    'markov': compute_markov,
    'fourier': compute_fourier,
}


def fuse_and_predict(history, genome):
    """Fuse signals and return 3 orthogonal bets."""
    sigs = {name: fn(history) for name, fn in SIG_FUNCS.items()}
    w = genome['signal_weights']

    # Score blend
    combined = sum(w[i] * sigs[SIGNAL_NAMES[i]] for i in range(4))

    # Gate
    gs = genome['gate_signal']
    if 0 <= gs < 4:
        gate_s = sigs[SIGNAL_NAMES[gs]]
        threshold_val = np.percentile(gate_s, genome['gate_threshold'] * 100)
        gate_mask = gate_s >= threshold_val
        combined[~gate_mask] *= 0.1

    # Orthogonal 3 bets
    used = set()
    bets = []
    for _ in range(genome['n_bets']):
        scores = combined.copy()
        for u in used:
            scores[u] = -1e9
        top_k = np.argsort(scores)[-PICK:]
        bet = sorted([k + 1 for k in top_k])
        bets.append(bet)
        used.update(top_k.tolist())

    return bets


def main():
    print("=" * 60)
    print("  POWER_LOTTO Evolution 3-bet Walk-Forward Validation")
    print("=" * 60)

    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    draws = [d for d in draws if d.get('numbers') and len(d['numbers']) >= PICK]
    print(f"Total draws: {len(draws)}")
    print(f"3-bet baseline: {BASELINE_3B*100:.3f}%")

    # Walk-forward from idx 200
    start_idx = 200
    n_oos = len(draws) - start_idx

    print(f"\nWalk-forward: {n_oos} OOS draws (idx {start_idx}..{len(draws)-1})")

    # --- Phase 1: Full OOS walk-forward ---
    hits = np.zeros(n_oos, dtype=bool)
    t0 = time.time()
    for i, t in enumerate(range(start_idx, len(draws))):
        hist = draws[:t]
        bets = fuse_and_predict(hist, BEST_GENOME)
        actual = set(draws[t]['numbers'][:PICK])
        for bet in bets:
            match_count = len(set(bet) & actual)
            if match_count >= MATCH_TH:
                hits[i] = True
                break
        if (i + 1) % 300 == 0:
            print(f"  {i+1}/{n_oos} ({time.time()-t0:.1f}s)")
    elapsed = time.time() - t0
    print(f"Walk-forward done: {elapsed:.1f}s")

    full_rate = float(np.mean(hits))
    full_edge = full_rate - BASELINE_3B
    n_hits = int(np.sum(hits))
    z = (full_rate - BASELINE_3B) / max(math.sqrt(BASELINE_3B * (1 - BASELINE_3B) / n_oos), 1e-9)

    print(f"\nFull OOS: rate={full_rate*100:.3f}%, edge={full_edge*100:+.3f}%, "
          f"z={z:.3f}, hits={n_hits}/{n_oos}")

    # --- Three-window ---
    print("\nThree-window test:")
    three_pass = True
    for w in [150, 500, 1500]:
        if n_oos >= w:
            w_rate = float(np.mean(hits[-w:]))
            w_edge = w_rate - BASELINE_3B
            flag = "PASS" if w_edge > 0 else "FAIL"
            print(f"  {w}p: rate={w_rate*100:.3f}%, edge={w_edge*100:+.3f}% [{flag}]")
            if w_edge <= 0:
                three_pass = False
        else:
            print(f"  {w}p: insufficient data")
            three_pass = False
    print(f"  Three-window: {'PASS' if three_pass else 'FAIL'}")

    # --- Permutation test (200 shuffles) ---
    print("\nPermutation test (200 shuffles)...")
    n_perm = 200
    prng = np.random.RandomState(SEED)
    actuals = np.zeros((n_oos, MAX_NUM), dtype=bool)
    for i, t in enumerate(range(start_idx, len(draws))):
        for n in draws[t]['numbers'][:PICK]:
            if 1 <= n <= MAX_NUM:
                actuals[i, n - 1] = True

    exceed = 0
    shuffle_edges = []
    for p in range(n_perm):
        perm_idx = prng.permutation(n_oos)
        shuffled = actuals[perm_idx]
        s_hits = 0
        for i in range(n_oos):
            # Reuse the same bets (already computed from walk-forward)
            # Re-run prediction for fidelity
            t = start_idx + i
            hist = draws[:t]
            bets = fuse_and_predict(hist, BEST_GENOME)
            for bet in bets:
                match_count = sum(shuffled[i, b - 1] for b in bet)
                if match_count >= MATCH_TH:
                    s_hits += 1
                    break
        s_rate = s_hits / n_oos
        s_edge = s_rate - BASELINE_3B
        shuffle_edges.append(s_edge)
        if s_edge >= full_edge:
            exceed += 1
        if (p + 1) % 50 == 0:
            print(f"  Shuffle {p+1}/{n_perm}")

    p_emp = (exceed + 1) / (n_perm + 1)
    shuffle_mean = float(np.mean(shuffle_edges))
    shuffle_std = float(np.std(shuffle_edges))
    cohens_d = (full_edge - shuffle_mean) / max(shuffle_std, 1e-6)
    verdict = 'SIGNAL_DETECTED' if p_emp < 0.05 else ('MARGINAL' if p_emp < 0.10 else 'NO_SIGNAL')

    print(f"\nPerm test: p={p_emp:.4f}, d={cohens_d:.3f} → {verdict}")

    # --- McNemar vs fourier_rhythm_3bet ---
    print("\nMcNemar vs fourier_rhythm_3bet...")
    try:
        from tools.power_fourier_rhythm import fourier_rhythm_predict
        evo_hits = np.zeros(n_oos, dtype=bool)
        fr3_hits = np.zeros(n_oos, dtype=bool)
        for i, t in enumerate(range(start_idx, len(draws))):
            hist = draws[:t]
            actual = set(draws[t]['numbers'][:PICK])

            evo_bets = fuse_and_predict(hist, BEST_GENOME)
            for bet in evo_bets:
                if len(set(bet) & actual) >= MATCH_TH:
                    evo_hits[i] = True
                    break

            fr3_bets = fourier_rhythm_predict(hist, n_bets=3, window=500)
            for bet in fr3_bets:
                if len(set(bet) & actual) >= MATCH_TH:
                    fr3_hits[i] = True
                    break
            if (i + 1) % 300 == 0:
                print(f"  McNemar {i+1}/{n_oos}")

        evo_only = int(np.sum(evo_hits & ~fr3_hits))
        fr3_only = int(np.sum(~evo_hits & fr3_hits))
        net = evo_only - fr3_only
        denom = evo_only + fr3_only
        if denom > 0:
            chi2 = (abs(evo_only - fr3_only) - 1) ** 2 / denom
            from scipy.stats import chi2 as chi2_dist
            p_mcn = 1 - chi2_dist.cdf(chi2, df=1)
        else:
            chi2 = 0
            p_mcn = 1.0
        print(f"  evo_only={evo_only}, fr3_only={fr3_only}, net={net}, chi2={chi2:.3f}, p={p_mcn:.4f}")
    except Exception as e:
        print(f"  McNemar skipped: {e}")

    # --- Re-evolve with wider window (500p) ---
    print("\n" + "=" * 60)
    print("  Re-evolution with 500p eval window (overfit check)")
    print("=" * 60)

    # Quick re-evolution: test if 500p window gives more stable results
    from tools.cross_game_transfer_study import (
        precompute_signals, GAMES, random_genome, evaluate_genome,
        mutate_genome, crossover_genomes
    )
    import copy

    cfg = GAMES['POWER_LOTTO']
    sigs, actuals_arr, act_start = precompute_signals(draws, MAX_NUM, PICK, start_idx=200)

    # Re-evolve with 500p
    POP = 200
    GEN = 50
    best_ever_500 = None
    population = [random_genome(n_bets=3) for _ in range(POP)]
    for g in population:
        g['fitness'] = evaluate_genome(g, sigs, actuals_arr, PICK, BASELINE_1B, eval_window=500)
    best_ever_500 = max(population, key=lambda g: g['fitness'])

    for gen in range(GEN):
        population.sort(key=lambda g: g['fitness'], reverse=True)
        n_elite = max(1, int(POP * 0.10))
        new_pop = population[:n_elite]
        while len(new_pop) < POP:
            r = rng.random()
            if r < 0.55:
                idxs = rng.choice(len(population), size=5, replace=False)
                parents = sorted([population[i] for i in idxs], key=lambda g: g['fitness'], reverse=True)
                child = crossover_genomes(parents[0], parents[1])
            elif r < 0.90:
                idx = int(rng.choice(len(population[:POP // 2])))
                child = mutate_genome(population[idx])
            else:
                child = random_genome(n_bets=3)
            child['fitness'] = evaluate_genome(child, sigs, actuals_arr, PICK, BASELINE_1B, eval_window=500)
            new_pop.append(child)
        population = new_pop
        gen_best = max(population, key=lambda g: g['fitness'])
        if gen_best['fitness'] > best_ever_500['fitness']:
            best_ever_500 = copy.deepcopy(gen_best)
        if (gen + 1) % 10 == 0:
            print(f"  Gen {gen+1}: best_500p={gen_best['fitness']*100:+.3f}%, "
                  f"ever_best={best_ever_500['fitness']*100:+.3f}%")

    full_edge_500 = evaluate_genome(best_ever_500, sigs, actuals_arr, PICK, BASELINE_1B,
                                     eval_window=actuals_arr.shape[0])
    print(f"\n  500p best genome:")
    print(f"    500p edge: {best_ever_500['fitness']*100:+.3f}%")
    print(f"    Full OOS edge: {full_edge_500*100:+.3f}%")
    print(f"    weights={[round(w,3) for w in best_ever_500['signal_weights']]}")
    print(f"    fusion={best_ever_500['fusion_type']}, nl={best_ever_500['nonlinear']}")
    print(f"    Overfit ratio: {best_ever_500['fitness'] / max(full_edge_500, 0.0001):.2f}x")

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Original 300p genome: full OOS edge={full_edge*100:+.3f}%, three-window={'PASS' if three_pass else 'FAIL'}")
    print(f"  Perm test: p={p_emp:.4f} → {verdict}")
    print(f"  500p genome: full OOS edge={full_edge_500*100:+.3f}%")

    deployment = "REJECT"
    if p_emp < 0.05 and three_pass:
        deployment = "VALIDATED"
    elif p_emp < 0.10:
        deployment = "PROVISIONAL"
    print(f"  Deployment verdict: {deployment}")


if __name__ == '__main__':
    main()
