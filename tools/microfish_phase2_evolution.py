#!/usr/bin/env python3
"""
MicroFish Phase 2 — Strategy Evolution & Signal Amplification
=============================================================
2026-03-15 | Following Phase 1 feature discovery (best edge +4.73%)

Phase 1: Signal amplification (deficit×markov, deficit²×markov, etc.)
Phase 2: Strategy construction (20,000+ candidates via expanded evolution)
Phase 3: Coverage optimization (multi-bet orthogonal search)
Phase 4: Ensemble evolution (multi-strategy per draw)
Phase 5: Edge ceiling analysis (theoretical maximum estimation)
"""
import sys, os, json, time
import numpy as np
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

SEED = 20260315
MAX_NUM = 39
PICK = 5
TEST_PERIODS = 1500
MIN_HIST = 300
BASELINE_M2 = 0.1140  # single bet M2+ for 539
BASELINE_2BET = 0.2154  # 2-bet M2+ baseline (non-overlapping)
BASELINE_3BET = 0.3050  # 3-bet M2+ baseline (non-overlapping)

N_PERM = 500

rng = np.random.default_rng(SEED)


# ================================================================
# Reuse Phase 1 feature builder
# ================================================================
from tools.microfish_engine import build_feature_matrix, Genome, evaluate


# ================================================================
# Phase 1: Signal Amplification
# ================================================================

def phase1_signal_amplification(F, hit, feature_names, eval_start, eval_end):
    """Test mechanisms that amplify the discovered signals."""
    print(f"\n{'=' * 72}")
    print("  Phase 1: Signal Amplification")
    print(f"{'=' * 72}")
    t0 = time.time()

    T, N, n_f = F.shape
    name_idx = {n: i for i, n in enumerate(feature_names)}

    # Core signal indices
    core_signals = {
        'freq_raw_150': name_idx.get('freq_raw_150', 0),
        'freq_deficit_100': name_idx.get('freq_deficit_100', 0),
        'nl_sq_freq_deficit_100': name_idx.get('nl_sq_freq_deficit_100', 0),
        'markov_lag1_100': name_idx.get('markov_lag1_100', 0),
        'parity_even_boost_80': name_idx.get('parity_even_boost_80', 0),
        'gap_ratio_100': name_idx.get('gap_ratio_100', 0),
        'freq_zscore_100': name_idx.get('freq_zscore_100', 0),
    }

    # Build amplified features
    amplified = {}

    # 1. deficit × markov (multiplicative)
    fd = F[:, :, core_signals['freq_deficit_100']]
    mk = F[:, :, core_signals['markov_lag1_100']]
    amplified['deficit_x_markov'] = (fd * mk).astype(np.float32)

    # 2. deficit² × markov
    amplified['deficit_sq_x_markov'] = (fd * fd * mk).astype(np.float32)

    # 3. deficit³ (cubic amplification)
    amplified['deficit_cubed'] = (fd * fd * fd).astype(np.float32)

    # 4. deficit × markov × parity
    pb = F[:, :, core_signals['parity_even_boost_80']]
    amplified['deficit_x_markov_x_parity'] = (fd * mk * (1 + pb)).astype(np.float32)

    # 5. Conditional markov: weight markov more when deficit is high
    # Compute per-timestep 75th percentile across numbers
    pct75 = np.percentile(fd, 75, axis=1, keepdims=True)
    deficit_high = (fd > pct75).astype(np.float32)
    amplified['cond_markov_high_deficit'] = (mk * (1 + deficit_high * 1.5)).astype(np.float32)

    # 6. Conditional markov: weight markov when gap_ratio > 1
    gr = F[:, :, core_signals['gap_ratio_100']]
    amplified['cond_markov_overdue'] = (mk * (1 + (gr > 1.0).astype(np.float32))).astype(np.float32)

    # 7. Adaptive deficit threshold: rank-based instead of raw
    # Convert deficit to rank per time step
    deficit_rank = np.zeros_like(fd)
    for t in range(eval_start, eval_end):
        order = np.argsort(-fd[t])
        for rank, idx in enumerate(order):
            deficit_rank[t, idx] = (N - rank) / N  # 1.0 = highest deficit
    amplified['deficit_rank'] = deficit_rank.astype(np.float32)

    # 8. deficit_rank × markov
    amplified['deficit_rank_x_markov'] = (deficit_rank * mk).astype(np.float32)

    # 9. Temporal weighting: exponential decay on frequency
    # More recent periods weighted more (EMA-like)
    fr150 = F[:, :, core_signals['freq_raw_150']]
    fr_ema = np.zeros_like(fr150)
    alpha = 0.05
    for t in range(1, T):
        fr_ema[t] = alpha * hit[t - 1] + (1 - alpha) * fr_ema[t - 1]
    amplified['freq_ema'] = fr_ema.astype(np.float32)

    # 10. freq_ema × markov
    amplified['freq_ema_x_markov'] = (fr_ema * mk).astype(np.float32)

    # 11. Sigmoid-amplified deficit
    amplified['deficit_sigmoid'] = (1.0 / (1.0 + np.exp(-3 * fd / (np.std(fd[eval_start:eval_end]) + 1e-6)))).astype(np.float32)

    # 12. Log-amplified deficit × markov
    log_fd = np.log1p(np.abs(fd)) * np.sign(fd)
    amplified['log_deficit_x_markov'] = (log_fd * mk).astype(np.float32)

    # 13. Deficit z-score per time step × markov
    fz = F[:, :, core_signals['freq_zscore_100']]
    amplified['deficit_zscore_x_markov'] = (fz * mk).astype(np.float32)

    # 14. Power-law amplified deficit: deficit^1.5
    amplified['deficit_pow15'] = (np.sign(fd) * np.abs(fd) ** 1.5).astype(np.float32)

    # 15. Combined triple signal
    amplified['triple_signal'] = (fd * mk * gr).astype(np.float32)

    # Evaluate each amplified feature as single-feature strategy
    results = []
    for name, feat in amplified.items():
        # Extend F with new feature
        scores = feat[eval_start:eval_end]
        top_k = np.argpartition(-scores, PICK, axis=1)[:, :PICK]
        hits = 0
        for i in range(eval_end - eval_start):
            predicted = set(top_k[i] + 1)
            actual = set(np.where(hit[eval_start + i] > 0)[0] + 1)
            if len(predicted & actual) >= 2:
                hits += 1
        rate = hits / (eval_end - eval_start)
        edge = rate - BASELINE_M2

        # 3-window check
        windows = {}
        for w in [150, 500, 1500]:
            s = eval_end - w
            scores_w = feat[s:eval_end]
            top_k_w = np.argpartition(-scores_w, PICK, axis=1)[:, :PICK]
            hits_w = 0
            for i in range(eval_end - s):
                predicted = set(top_k_w[i] + 1)
                actual = set(np.where(hit[s + i] > 0)[0] + 1)
                if len(predicted & actual) >= 2:
                    hits_w += 1
            rate_w = hits_w / (eval_end - s)
            windows[w] = round((rate_w - BASELINE_M2) * 100, 2)

        results.append({
            'name': name, 'rate': float(rate), 'edge': float(edge),
            'edge_pct': round(edge * 100, 2),
            'windows': windows,
            'all_positive': all(v > 0 for v in windows.values()),
        })

    results.sort(key=lambda x: -x['edge'])

    # Compare with baseline features
    print(f"\n  Amplified Signal Results (vs baseline ACB +2.60%, MicroFish #1 +4.73%):")
    print(f"  {'Signal':<35} {'Rate':>7} {'Edge':>8} {'150p':>7} {'500p':>7} {'1500p':>7} {'Stable':>7}")
    print(f"  {'─' * 82}")

    for r in results:
        w = r['windows']
        stable = '✓' if r['all_positive'] else '✗'
        print(f"  {r['name']:<35} {r['rate']*100:>6.2f}% {r['edge_pct']:>+7.2f}% "
              f"{w[150]:>+6.2f}% {w[500]:>+6.2f}% {w[1500]:>+6.2f}% {stable:>6}")

    # Now test amplified features COMBINED with core features (multi-feature strategies)
    print(f"\n  Testing amplified + core feature combinations...")

    # Extend feature matrix with top amplified features
    top_amplified = [r for r in results if r['edge'] > 0][:8]
    amp_features = []
    amp_names = []
    for r in top_amplified:
        amp_features.append(amplified[r['name']])
        amp_names.append(f'amp_{r["name"]}')

    if amp_features:
        F_ext = np.concatenate([F] + [f[:, :, np.newaxis] for f in amp_features], axis=2)
        ext_names = feature_names + amp_names
        n_f_ext = F_ext.shape[2]

        # Evolve with extended features
        from tools.microfish_engine import run_evolution
        pop_amp, _, _ = run_evolution(F_ext, hit, ext_names, eval_start, eval_end)

        best_amp = pop_amp[0]
        best_amp_feats = [ext_names[fi] for fi in best_amp.features]
        best_amp_edge = (best_amp.fitness - BASELINE_M2) * 100

        print(f"\n  Best amplified strategy:")
        print(f"    Features: {best_amp_feats}")
        print(f"    Weights: {[round(w, 3) for w in best_amp.weights]}")
        print(f"    Edge: {best_amp_edge:+.2f}%")

        # Permutation test
        perm_result = _perm_test_raw(best_amp, F_ext, hit, eval_start, eval_end, 500)
        print(f"    Perm p: {perm_result['p']:.4f}, Signal: {perm_result['signal']*100:+.2f}%")
    else:
        F_ext = F
        ext_names = feature_names
        best_amp_edge = 0
        perm_result = {'p': 1.0, 'signal': 0}
        best_amp_feats = []

    elapsed = time.time() - t0
    print(f"\n  Phase 1 time: {elapsed:.0f}s")

    return {
        'single_feature_results': results,
        'best_combo_edge': best_amp_edge,
        'best_combo_features': best_amp_feats,
        'best_combo_perm_p': perm_result['p'],
        'F_ext': F_ext,
        'ext_names': ext_names,
    }


def _perm_test_raw(genome, F, hit, t0, t1, n_perm):
    """Permutation test for a genome on feature matrix F."""
    fi = genome.features
    w = genome.weights
    scores = F[t0:t1, :, :][:, :, fi].dot(w)
    top_k_indices = np.argpartition(-scores, PICK, axis=1)[:, :PICK]
    predicted_sets = [set(top_k_indices[i] + 1) for i in range(t1 - t0)]
    actual_indices = list(range(t0, t1))

    real_hits = 0
    for i in range(t1 - t0):
        actual = set(np.where(hit[t0 + i] > 0)[0] + 1)
        if len(predicted_sets[i] & actual) >= 2:
            real_hits += 1
    real = real_hits / (t1 - t0)

    perm_rates = []
    for p_i in range(n_perm):
        p_rng = np.random.RandomState(p_i * 7919 + 42)
        shuffled = list(actual_indices)
        p_rng.shuffle(shuffled)
        hits = 0
        for i in range(t1 - t0):
            actual = set(np.where(hit[shuffled[i]] > 0)[0] + 1)
            if len(predicted_sets[i] & actual) >= 2:
                hits += 1
        perm_rates.append(hits / (t1 - t0))

    p_val = (sum(1 for pr in perm_rates if pr >= real) + 1) / (n_perm + 1)
    return {'real': float(real), 'perm_mean': float(np.mean(perm_rates)),
            'signal': float(real - np.mean(perm_rates)), 'p': float(p_val)}


# ================================================================
# Phase 2: Strategy Construction (20,000+ candidates)
# ================================================================

def phase2_strategy_construction(F, hit, feature_names, eval_start, eval_end):
    """Evolve 20,000+ candidate strategies with diverse selection mechanisms."""
    print(f"\n{'=' * 72}")
    print("  Phase 2: Strategy Construction (20,000+ candidates)")
    print(f"{'=' * 72}")
    t0 = time.time()

    n_f = F.shape[2]
    T = F.shape[0]

    # --- Strategy Type A: Standard top-k (baseline, pop=200 gen=50) ---
    print("\n  [A] Standard top-k selection (pop=200 × gen=50 = 10,000)...")
    from tools.microfish_engine import run_evolution
    pop_a, cands_a, _ = run_evolution(F, hit, feature_names, eval_start, eval_end)
    best_a = pop_a[0]
    print(f"      Best A: edge={best_a.fitness - BASELINE_M2:+.4f} "
          f"feats={[feature_names[fi] for fi in best_a.features]}")

    # --- Strategy Type B: Rank-weighted selection ---
    # Instead of top-k, weight selection by rank
    print("\n  [B] Rank-weighted selection (pop=200 × gen=25 = 5,000)...")

    class RankGenome(Genome):
        def __init__(self, n_total, features=None, weights=None):
            super().__init__(n_total, features, weights)

    def evaluate_rank_weighted(genome, F, hit, t0, t1):
        """Score = rank-weighted probability."""
        fi = genome.features
        w = genome.weights
        scores = F[t0:t1, :, :][:, :, fi].dot(w)
        # Convert to ranks, then select top-5 by rank
        ranks = np.zeros_like(scores)
        for i in range(t1 - t0):
            order = np.argsort(-scores[i])
            for r, idx in enumerate(order):
                ranks[i, idx] = MAX_NUM - r
        top_k = np.argpartition(-ranks, PICK, axis=1)[:, :PICK]

        hits = 0
        for i in range(t1 - t0):
            predicted = set(top_k[i] + 1)
            actual = set(np.where(hit[t0 + i] > 0)[0] + 1)
            if len(predicted & actual) >= 2:
                hits += 1
        rate = hits / max(t1 - t0, 1)
        genome.fitness = rate
        return rate

    pop_b = [Genome(n_f) for _ in range(200)]
    for gen in range(25):
        for g in pop_b:
            if g.fitness < 0:
                evaluate_rank_weighted(g, F, hit, eval_start, eval_end)
        pop_b.sort(key=lambda g: -g.fitness)
        elite_n = 20
        new_pop = [g.copy() for g in pop_b[:elite_n]]
        while len(new_pop) < 200:
            if rng.random() < 0.6:
                from tools.microfish_engine import crossover_genomes
                p1 = max(rng.choice(pop_b[:100], size=5, replace=False), key=lambda g: g.fitness)
                p2 = max(rng.choice(pop_b[:100], size=5, replace=False), key=lambda g: g.fitness)
                child = crossover_genomes(p1, p2, n_f)
                if rng.random() < 0.3:
                    child.mutate(n_f)
                new_pop.append(child)
            else:
                parent = rng.choice(pop_b[:100])
                child = parent.copy()
                child.mutate(n_f)
                new_pop.append(child)
        pop_b = new_pop[:200]
    for g in pop_b:
        if g.fitness < 0:
            evaluate_rank_weighted(g, F, hit, eval_start, eval_end)
    pop_b.sort(key=lambda g: -g.fitness)
    best_b = pop_b[0]
    # Re-evaluate with standard M2+ for fair comparison
    evaluate(best_b, F, hit, eval_start, eval_end)
    print(f"      Best B: edge={best_b.fitness - BASELINE_M2:+.4f} "
          f"feats={[feature_names[fi] for fi in best_b.features]}")

    # --- Strategy Type C: Zone-constrained selection ---
    print("\n  [C] Zone-constrained selection (pop=200 × gen=25 = 5,000)...")

    zone_id = np.zeros(MAX_NUM, dtype=np.int32)
    for i in range(MAX_NUM):
        n = i + 1
        if n <= 13:
            zone_id[i] = 0
        elif n <= 26:
            zone_id[i] = 1
        else:
            zone_id[i] = 2

    def evaluate_zone_constrained(genome, F, hit, t0, t1):
        """Select top numbers respecting zone balance (2-2-1 or 2-1-2 or 1-2-2)."""
        fi = genome.features
        w = genome.weights
        scores = F[t0:t1, :, :][:, :, fi].dot(w)

        hits = 0
        for i in range(t1 - t0):
            s = scores[i]
            # Select top per zone
            zone_nums = [[], [], []]
            for n_idx in range(MAX_NUM):
                zone_nums[zone_id[n_idx]].append((s[n_idx], n_idx))
            for z in range(3):
                zone_nums[z].sort(key=lambda x: -x[0])

            # Try 2-2-1 distribution across zones (all 3 permutations)
            best_set = []
            best_score = -1e9
            for z_alloc in [(2, 2, 1), (2, 1, 2), (1, 2, 2)]:
                selected = []
                for z in range(3):
                    selected.extend([idx for _, idx in zone_nums[z][:z_alloc[z]]])
                if len(selected) == PICK:
                    total_score = sum(s[idx] for idx in selected)
                    if total_score > best_score:
                        best_score = total_score
                        best_set = selected

            if not best_set:
                best_set = list(np.argsort(-s)[:PICK])

            predicted = set(idx + 1 for idx in best_set)
            actual = set(np.where(hit[t0 + i] > 0)[0] + 1)
            if len(predicted & actual) >= 2:
                hits += 1

        rate = hits / max(t1 - t0, 1)
        genome.fitness = rate
        return rate

    pop_c = [Genome(n_f) for _ in range(200)]
    for gen in range(25):
        for g in pop_c:
            if g.fitness < 0:
                evaluate_zone_constrained(g, F, hit, eval_start, eval_end)
        pop_c.sort(key=lambda g: -g.fitness)
        elite_n = 20
        new_pop = [g.copy() for g in pop_c[:elite_n]]
        while len(new_pop) < 200:
            if rng.random() < 0.6:
                from tools.microfish_engine import crossover_genomes
                p1 = max(rng.choice(pop_c[:100], size=5, replace=False), key=lambda g: g.fitness)
                p2 = max(rng.choice(pop_c[:100], size=5, replace=False), key=lambda g: g.fitness)
                child = crossover_genomes(p1, p2, n_f)
                if rng.random() < 0.3:
                    child.mutate(n_f)
                new_pop.append(child)
            else:
                parent = rng.choice(pop_c[:100])
                child = parent.copy()
                child.mutate(n_f)
                new_pop.append(child)
        pop_c = new_pop[:200]
    for g in pop_c:
        if g.fitness < 0:
            evaluate_zone_constrained(g, F, hit, eval_start, eval_end)
    pop_c.sort(key=lambda g: -g.fitness)
    best_c = pop_c[0]
    # Re-evaluate with standard M2+ for fair comparison
    evaluate(best_c, F, hit, eval_start, eval_end)
    print(f"      Best C: edge={best_c.fitness - BASELINE_M2:+.4f} "
          f"feats={[feature_names[fi] for fi in best_c.features]}")

    # --- Strategy Type D: Sum-constrained selection ---
    print("\n  [D] Sum-constrained selection (pop=200 × gen=25 = 5,000)...")

    # Historical sum statistics
    draw_sums = np.zeros(T, dtype=np.float64)
    for t in range(T):
        hit_nums = np.where(hit[t] > 0)[0] + 1
        draw_sums[t] = hit_nums.sum() if len(hit_nums) >= PICK else 0

    def evaluate_sum_constrained(genome, F, hit, t0, t1):
        """Select top-5 with sum closest to historical mean."""
        fi = genome.features
        w = genome.weights
        scores = F[t0:t1, :, :][:, :, fi].dot(w)

        hits = 0
        for i in range(t1 - t0):
            t = t0 + i
            # Historical sum mean
            s_start = max(0, t - 300)
            hist_mean = np.mean(draw_sums[s_start:t]) if t > s_start else 100.0

            s = scores[i]
            top12 = np.argsort(-s)[:12]

            # From top-12, find best 5-combination by sum-closeness × score
            best_combo = None
            best_obj = -1e9
            # Greedy: start with top-5, swap to improve sum
            selected = list(top12[:PICK])
            sel_sum = sum(idx + 1 for idx in selected)
            sel_score = sum(s[idx] for idx in selected)

            # Try swapping worst-scoring selected with best unselected
            for _ in range(5):
                remaining = [idx for idx in top12 if idx not in selected]
                if not remaining:
                    break
                worst_sel_idx = min(range(len(selected)), key=lambda j: s[selected[j]])
                best_rem_idx = max(range(len(remaining)), key=lambda j: s[remaining[j]])
                # Check if swap improves sum-closeness
                new_sel = selected.copy()
                new_sel[worst_sel_idx] = remaining[best_rem_idx]
                new_sum = sum(idx + 1 for idx in new_sel)
                if abs(new_sum - hist_mean) < abs(sel_sum - hist_mean):
                    selected = new_sel
                    sel_sum = new_sum

            predicted = set(idx + 1 for idx in selected)
            actual = set(np.where(hit[t] > 0)[0] + 1)
            if len(predicted & actual) >= 2:
                hits += 1

        rate = hits / max(t1 - t0, 1)
        genome.fitness = rate
        return rate

    pop_d = [Genome(n_f) for _ in range(200)]
    for gen in range(25):
        for g in pop_d:
            if g.fitness < 0:
                evaluate_sum_constrained(g, F, hit, eval_start, eval_end)
        pop_d.sort(key=lambda g: -g.fitness)
        elite_n = 20
        new_pop = [g.copy() for g in pop_d[:elite_n]]
        while len(new_pop) < 200:
            if rng.random() < 0.6:
                from tools.microfish_engine import crossover_genomes
                p1 = max(rng.choice(pop_d[:100], size=5, replace=False), key=lambda g: g.fitness)
                p2 = max(rng.choice(pop_d[:100], size=5, replace=False), key=lambda g: g.fitness)
                child = crossover_genomes(p1, p2, n_f)
                if rng.random() < 0.3:
                    child.mutate(n_f)
                new_pop.append(child)
            else:
                parent = rng.choice(pop_d[:100])
                child = parent.copy()
                child.mutate(n_f)
                new_pop.append(child)
        pop_d = new_pop[:200]
    for g in pop_d:
        if g.fitness < 0:
            evaluate_sum_constrained(g, F, hit, eval_start, eval_end)
    pop_d.sort(key=lambda g: -g.fitness)
    best_d = pop_d[0]
    evaluate(best_d, F, hit, eval_start, eval_end)
    print(f"      Best D: edge={best_d.fitness - BASELINE_M2:+.4f} "
          f"feats={[feature_names[fi] for fi in best_d.features]}")

    # Collect all candidates count
    total_cands = 10000 + 5000 + 5000 + 5000
    all_strategies = {
        'A_standard': {'genome': best_a, 'edge': float(best_a.fitness - BASELINE_M2),
                       'features': [feature_names[fi] for fi in best_a.features]},
        'B_rank_weighted': {'genome': best_b, 'edge': float(best_b.fitness - BASELINE_M2),
                            'features': [feature_names[fi] for fi in best_b.features]},
        'C_zone_constrained': {'genome': best_c, 'edge': float(best_c.fitness - BASELINE_M2),
                                'features': [feature_names[fi] for fi in best_c.features]},
        'D_sum_constrained': {'genome': best_d, 'edge': float(best_d.fitness - BASELINE_M2),
                               'features': [feature_names[fi] for fi in best_d.features]},
    }

    # Permutation test top strategies
    print(f"\n  Running permutation tests on best strategies (n={N_PERM})...")
    for name, strat in all_strategies.items():
        g = strat['genome']
        pt = _perm_test_raw(g, F, hit, eval_start, eval_end, N_PERM)
        strat['perm_p'] = pt['p']
        strat['signal'] = pt['signal']
        print(f"    {name}: edge={strat['edge']*100:+.2f}% perm_p={pt['p']:.4f} signal={pt['signal']*100:+.2f}%")

    elapsed = time.time() - t0
    print(f"\n  Total candidates evaluated: {total_cands}")
    print(f"  Phase 2 time: {elapsed:.0f}s")

    return all_strategies


# ================================================================
# Phase 3: Coverage Optimization (multi-bet)
# ================================================================

def phase3_coverage_optimization(F, hit, feature_names, eval_start, eval_end, strategies):
    """Search for optimal multi-bet coverage."""
    print(f"\n{'=' * 72}")
    print("  Phase 3: Coverage Optimization (Multi-Bet)")
    print(f"{'=' * 72}")
    t0 = time.time()

    n_f = F.shape[2]

    # Get the best strategies from Phase 2
    best_key = max(strategies, key=lambda k: strategies[k]['edge'])
    best_genome = strategies[best_key]['genome']

    # --- 2-bet orthogonal strategies ---
    print("\n  [2-bet] Testing orthogonal number sets...")

    def evaluate_2bet(genome1, genome2, F, hit, t0_eval, t1_eval):
        """Evaluate 2-bet strategy (no overlap between bets)."""
        fi1, w1 = genome1.features, genome1.weights
        fi2, w2 = genome2.features, genome2.weights
        scores1 = F[t0_eval:t1_eval, :, :][:, :, fi1].dot(w1)
        scores2 = F[t0_eval:t1_eval, :, :][:, :, fi2].dot(w2)

        hits = 0
        for i in range(t1_eval - t0_eval):
            # Bet 1: top-5
            bet1 = set(np.argsort(-scores1[i])[:PICK] + 1)
            # Bet 2: top-5 from remaining
            s2 = scores2[i].copy()
            for n in bet1:
                s2[n - 1] = -1e9
            bet2 = set(np.argsort(-s2)[:PICK] + 1)

            actual = set(np.where(hit[t0_eval + i] > 0)[0] + 1)
            hit1 = len(bet1 & actual) >= 2
            hit2 = len(bet2 & actual) >= 2
            if hit1 or hit2:
                hits += 1

        return hits / max(t1_eval - t0_eval, 1)

    # Test different bet2 feature combinations
    # For bet2, try features that are orthogonal to bet1
    bet2_candidates = []

    # Candidate bet2 strategies from Phase 2
    for name, strat in strategies.items():
        g2 = strat['genome']
        rate = evaluate_2bet(best_genome, g2, F, hit, eval_start, eval_end)
        edge = rate - BASELINE_2BET
        bet2_candidates.append({
            'bet1': best_key, 'bet2': name,
            'rate': float(rate), 'edge': float(edge),
        })

    # Also try raw feature strategies for bet2
    core_features = {
        'freq_deficit_300': feature_names.index('freq_deficit_300'),
        'gap_ratio_100': feature_names.index('gap_ratio_100'),
        'markov_lag1_100': feature_names.index('markov_lag1_100'),
        'fourier_phase': feature_names.index('fourier_phase'),
        'tail_deficit_100': feature_names.index('tail_deficit_100'),
        'parity_even_boost_80': feature_names.index('parity_even_boost_80'),
    }
    for name, fi in core_features.items():
        g2 = Genome(n_f, [fi], np.array([1.0]))
        rate = evaluate_2bet(best_genome, g2, F, hit, eval_start, eval_end)
        edge = rate - BASELINE_2BET
        bet2_candidates.append({
            'bet1': best_key, 'bet2': f'single_{name}',
            'rate': float(rate), 'edge': float(edge),
        })

    # Evolve a dedicated bet2 strategy
    print("    Evolving dedicated bet2 strategy...")

    def evaluate_bet2_only(genome, F, hit, t0_eval, t1_eval, g1=best_genome):
        """Evaluate genome as bet2 (orthogonal to g1)."""
        fi1, w1 = g1.features, g1.weights
        fi2, w2 = genome.features, genome.weights
        scores1 = F[t0_eval:t1_eval, :, :][:, :, fi1].dot(w1)
        scores2 = F[t0_eval:t1_eval, :, :][:, :, fi2].dot(w2)

        hits = 0
        for i in range(t1_eval - t0_eval):
            bet1 = set(np.argsort(-scores1[i])[:PICK] + 1)
            s2 = scores2[i].copy()
            for n in bet1:
                s2[n - 1] = -1e9
            bet2 = set(np.argsort(-s2)[:PICK] + 1)

            actual = set(np.where(hit[t0_eval + i] > 0)[0] + 1)
            if len(bet1 & actual) >= 2 or len(bet2 & actual) >= 2:
                hits += 1

        rate = hits / max(t1_eval - t0_eval, 1)
        genome.fitness = rate
        return rate

    pop_b2 = [Genome(n_f) for _ in range(200)]
    for gen in range(25):
        for g in pop_b2:
            if g.fitness < 0:
                evaluate_bet2_only(g, F, hit, eval_start, eval_end)
        pop_b2.sort(key=lambda g: -g.fitness)
        elite_n = 20
        new_pop = [g.copy() for g in pop_b2[:elite_n]]
        while len(new_pop) < 200:
            if rng.random() < 0.6:
                from tools.microfish_engine import crossover_genomes
                p1 = max(rng.choice(pop_b2[:100], size=5, replace=False), key=lambda g: g.fitness)
                p2 = max(rng.choice(pop_b2[:100], size=5, replace=False), key=lambda g: g.fitness)
                child = crossover_genomes(p1, p2, n_f)
                if rng.random() < 0.3:
                    child.mutate(n_f)
                new_pop.append(child)
            else:
                parent = rng.choice(pop_b2[:100])
                child = parent.copy()
                child.mutate(n_f)
                new_pop.append(child)
        pop_b2 = new_pop[:200]
    for g in pop_b2:
        if g.fitness < 0:
            evaluate_bet2_only(g, F, hit, eval_start, eval_end)
    pop_b2.sort(key=lambda g: -g.fitness)
    best_b2 = pop_b2[0]
    rate_b2 = evaluate_2bet(best_genome, best_b2, F, hit, eval_start, eval_end)
    edge_b2 = rate_b2 - BASELINE_2BET
    bet2_candidates.append({
        'bet1': best_key, 'bet2': 'evolved_orthogonal',
        'rate': float(rate_b2), 'edge': float(edge_b2),
        'bet2_features': [feature_names[fi] for fi in best_b2.features],
    })

    bet2_candidates.sort(key=lambda x: -x['edge'])
    print(f"\n  2-bet Results (baseline: {BASELINE_2BET*100:.2f}%):")
    print(f"  {'Bet2 Strategy':<30} {'Rate':>7} {'Edge':>8}")
    print(f"  {'─' * 50}")
    for c in bet2_candidates[:10]:
        print(f"  {c['bet2']:<30} {c['rate']*100:>6.2f}% {c['edge']*100:>+7.2f}%")

    # --- 3-bet optimization ---
    print(f"\n  [3-bet] Testing 3-bet orthogonal strategies...")
    best_b2_genome = best_b2

    def evaluate_3bet(g1, g2, g3, F, hit, t0_eval, t1_eval):
        """Evaluate 3-bet strategy (no overlap between bets)."""
        fi1, w1 = g1.features, g1.weights
        fi2, w2 = g2.features, g2.weights
        fi3, w3 = g3.features, g3.weights
        s1 = F[t0_eval:t1_eval, :, :][:, :, fi1].dot(w1)
        s2 = F[t0_eval:t1_eval, :, :][:, :, fi2].dot(w2)
        s3 = F[t0_eval:t1_eval, :, :][:, :, fi3].dot(w3)

        hits = 0
        for i in range(t1_eval - t0_eval):
            bet1 = set(np.argsort(-s1[i])[:PICK] + 1)
            sc2 = s2[i].copy()
            for n in bet1:
                sc2[n - 1] = -1e9
            bet2 = set(np.argsort(-sc2)[:PICK] + 1)
            sc3 = s3[i].copy()
            for n in bet1 | bet2:
                sc3[n - 1] = -1e9
            bet3 = set(np.argsort(-sc3)[:PICK] + 1)

            actual = set(np.where(hit[t0_eval + i] > 0)[0] + 1)
            if (len(bet1 & actual) >= 2 or len(bet2 & actual) >= 2
                    or len(bet3 & actual) >= 2):
                hits += 1

        return hits / max(t1_eval - t0_eval, 1)

    # Evolve bet3
    print("    Evolving dedicated bet3 strategy...")

    def evaluate_bet3_only(genome, F, hit, t0_eval, t1_eval):
        fi1, w1 = best_genome.features, best_genome.weights
        fi2, w2 = best_b2_genome.features, best_b2_genome.weights
        fi3, w3 = genome.features, genome.weights
        s1 = F[t0_eval:t1_eval, :, :][:, :, fi1].dot(w1)
        s2 = F[t0_eval:t1_eval, :, :][:, :, fi2].dot(w2)
        s3 = F[t0_eval:t1_eval, :, :][:, :, fi3].dot(w3)

        hits = 0
        for i in range(t1_eval - t0_eval):
            bet1 = set(np.argsort(-s1[i])[:PICK] + 1)
            sc2 = s2[i].copy()
            for n in bet1:
                sc2[n - 1] = -1e9
            bet2 = set(np.argsort(-sc2)[:PICK] + 1)
            sc3 = s3[i].copy()
            for n in bet1 | bet2:
                sc3[n - 1] = -1e9
            bet3 = set(np.argsort(-sc3)[:PICK] + 1)

            actual = set(np.where(hit[t0_eval + i] > 0)[0] + 1)
            if len(bet1 & actual) >= 2 or len(bet2 & actual) >= 2 or len(bet3 & actual) >= 2:
                hits += 1

        rate = hits / max(t1_eval - t0_eval, 1)
        genome.fitness = rate
        return rate

    pop_b3 = [Genome(n_f) for _ in range(200)]
    for gen in range(25):
        for g in pop_b3:
            if g.fitness < 0:
                evaluate_bet3_only(g, F, hit, eval_start, eval_end)
        pop_b3.sort(key=lambda g: -g.fitness)
        elite_n = 20
        new_pop = [g.copy() for g in pop_b3[:elite_n]]
        while len(new_pop) < 200:
            if rng.random() < 0.6:
                from tools.microfish_engine import crossover_genomes
                p1 = max(rng.choice(pop_b3[:100], size=5, replace=False), key=lambda g: g.fitness)
                p2 = max(rng.choice(pop_b3[:100], size=5, replace=False), key=lambda g: g.fitness)
                child = crossover_genomes(p1, p2, n_f)
                if rng.random() < 0.3:
                    child.mutate(n_f)
                new_pop.append(child)
            else:
                parent = rng.choice(pop_b3[:100])
                child = parent.copy()
                child.mutate(n_f)
                new_pop.append(child)
        pop_b3 = new_pop[:200]
    for g in pop_b3:
        if g.fitness < 0:
            evaluate_bet3_only(g, F, hit, eval_start, eval_end)
    pop_b3.sort(key=lambda g: -g.fitness)
    best_b3 = pop_b3[0]

    rate_3bet = evaluate_3bet(best_genome, best_b2, best_b3, F, hit, eval_start, eval_end)
    edge_3bet = rate_3bet - BASELINE_3BET

    print(f"\n  3-bet Results:")
    print(f"    Bet1: {[feature_names[fi] for fi in best_genome.features]}")
    print(f"    Bet2: {[feature_names[fi] for fi in best_b2.features]}")
    print(f"    Bet3: {[feature_names[fi] for fi in best_b3.features]}")
    print(f"    Combined rate: {rate_3bet*100:.2f}% (baseline {BASELINE_3BET*100:.2f}%)")
    print(f"    Edge: {edge_3bet*100:+.2f}%")

    # Permutation test for 2-bet and 3-bet
    print(f"\n  Permutation tests (n={N_PERM})...")

    # 2-bet perm test
    best_2bet = bet2_candidates[0]
    if 'bet2_features' in best_2bet:
        g2_perm = best_b2
    else:
        # Find the genome for the best bet2
        g2_name = best_2bet['bet2']
        if g2_name in strategies:
            g2_perm = strategies[g2_name]['genome']
        else:
            fi_name = g2_name.replace('single_', '')
            fi_idx = feature_names.index(fi_name) if fi_name in feature_names else 0
            g2_perm = Genome(n_f, [fi_idx], np.array([1.0]))

    actual_indices = list(range(eval_start, eval_end))
    fi1, w1 = best_genome.features, best_genome.weights
    fi2, w2 = g2_perm.features, g2_perm.weights
    scores1 = F[eval_start:eval_end, :, :][:, :, fi1].dot(w1)
    scores2 = F[eval_start:eval_end, :, :][:, :, fi2].dot(w2)

    # Build predicted sets
    pred_2bet = []
    for i in range(eval_end - eval_start):
        bet1 = set(np.argsort(-scores1[i])[:PICK] + 1)
        s2 = scores2[i].copy()
        for n in bet1:
            s2[n - 1] = -1e9
        bet2 = set(np.argsort(-s2)[:PICK] + 1)
        pred_2bet.append((bet1, bet2))

    real_2bet_hits = 0
    for i in range(eval_end - eval_start):
        actual = set(np.where(hit[eval_start + i] > 0)[0] + 1)
        if len(pred_2bet[i][0] & actual) >= 2 or len(pred_2bet[i][1] & actual) >= 2:
            real_2bet_hits += 1
    real_2bet_rate = real_2bet_hits / (eval_end - eval_start)

    perm_2bet_rates = []
    for p_i in range(N_PERM):
        p_rng = np.random.RandomState(p_i * 7919 + 42)
        shuffled = list(actual_indices)
        p_rng.shuffle(shuffled)
        hits = 0
        for i in range(eval_end - eval_start):
            actual = set(np.where(hit[shuffled[i]] > 0)[0] + 1)
            if len(pred_2bet[i][0] & actual) >= 2 or len(pred_2bet[i][1] & actual) >= 2:
                hits += 1
        perm_2bet_rates.append(hits / (eval_end - eval_start))

    p_2bet = (sum(1 for pr in perm_2bet_rates if pr >= real_2bet_rate) + 1) / (N_PERM + 1)
    signal_2bet = real_2bet_rate - np.mean(perm_2bet_rates)
    print(f"    2-bet: rate={real_2bet_rate*100:.2f}% perm_mean={np.mean(perm_2bet_rates)*100:.2f}% "
          f"signal={signal_2bet*100:+.2f}% p={p_2bet:.4f}")

    elapsed = time.time() - t0
    print(f"\n  Phase 3 time: {elapsed:.0f}s")

    return {
        'bet2_candidates': bet2_candidates[:10],
        'best_2bet_rate': float(real_2bet_rate),
        'best_2bet_edge': float(real_2bet_rate - BASELINE_2BET),
        'best_2bet_perm_p': float(p_2bet),
        'best_2bet_signal': float(signal_2bet),
        'best_3bet_rate': float(rate_3bet),
        'best_3bet_edge': float(edge_3bet),
        'bet1_features': [feature_names[fi] for fi in best_genome.features],
        'bet2_features': [feature_names[fi] for fi in best_b2.features],
        'bet3_features': [feature_names[fi] for fi in best_b3.features],
    }


# ================================================================
# Phase 4: Ensemble Evolution
# ================================================================

def phase4_ensemble_evolution(F, hit, feature_names, eval_start, eval_end, strategies):
    """Test ensemble methods (multiple strategies per draw)."""
    print(f"\n{'=' * 72}")
    print("  Phase 4: Ensemble Evolution")
    print(f"{'=' * 72}")
    t0 = time.time()

    n_f = F.shape[2]

    # Collect all viable strategies
    viable = [(name, strat['genome']) for name, strat in strategies.items()
              if strat['edge'] > 0]

    if len(viable) < 2:
        print("  Insufficient viable strategies for ensemble. Skipping.")
        return {}

    # Method 1: Vote ensemble (majority voting)
    print("\n  [M1] Vote Ensemble (all strategies vote, majority wins)...")
    vote_hits = 0
    for i in range(eval_end - eval_start):
        t = eval_start + i
        votes = np.zeros(MAX_NUM, dtype=np.float64)
        for name, g in viable:
            fi, w = g.features, g.weights
            scores = F[t, :, :][:, fi].dot(w)
            top_k = np.argsort(-scores)[:PICK]
            for idx in top_k:
                votes[idx] += 1
        selected = set(np.argsort(-votes)[:PICK] + 1)
        actual = set(np.where(hit[t] > 0)[0] + 1)
        if len(selected & actual) >= 2:
            vote_hits += 1
    vote_rate = vote_hits / (eval_end - eval_start)
    vote_edge = vote_rate - BASELINE_M2
    print(f"    Rate: {vote_rate*100:.2f}% Edge: {vote_edge*100:+.2f}%")

    # Method 2: Edge-weighted ensemble
    print("\n  [M2] Edge-Weighted Ensemble (weight by historical edge)...")
    ew_hits = 0
    for i in range(eval_end - eval_start):
        t = eval_start + i
        votes = np.zeros(MAX_NUM, dtype=np.float64)
        for name, g in viable:
            edge_w = max(strategies[name]['edge'], 0.001)
            fi, w = g.features, g.weights
            scores = F[t, :, :][:, fi].dot(w)
            top_k = np.argsort(-scores)[:PICK]
            for idx in top_k:
                votes[idx] += edge_w
        selected = set(np.argsort(-votes)[:PICK] + 1)
        actual = set(np.where(hit[t] > 0)[0] + 1)
        if len(selected & actual) >= 2:
            ew_hits += 1
    ew_rate = ew_hits / (eval_end - eval_start)
    ew_edge = ew_rate - BASELINE_M2
    print(f"    Rate: {ew_rate*100:.2f}% Edge: {ew_edge*100:+.2f}%")

    # Method 3: Score fusion (average raw scores then select)
    print("\n  [M3] Score Fusion (average raw scores)...")
    sf_hits = 0
    for i in range(eval_end - eval_start):
        t = eval_start + i
        fused = np.zeros(MAX_NUM, dtype=np.float64)
        for name, g in viable:
            fi, w = g.features, g.weights
            scores = F[t, :, :][:, fi].dot(w)
            # Normalize scores to [0, 1]
            s_min, s_max = scores.min(), scores.max()
            if s_max > s_min:
                scores = (scores - s_min) / (s_max - s_min)
            fused += scores * max(strategies[name]['edge'], 0.001)
        selected = set(np.argsort(-fused)[:PICK] + 1)
        actual = set(np.where(hit[t] > 0)[0] + 1)
        if len(selected & actual) >= 2:
            sf_hits += 1
    sf_rate = sf_hits / (eval_end - eval_start)
    sf_edge = sf_rate - BASELINE_M2
    print(f"    Rate: {sf_rate*100:.2f}% Edge: {sf_edge*100:+.2f}%")

    # Method 4: Regime-switching (use sum z-score to select strategy)
    print("\n  [M4] Regime-Switching (sum z-score selects strategy)...")
    name_idx = {n: i for i, n in enumerate(feature_names)}
    sum_z_idx = name_idx.get('sum_zscore_100', 0)

    rs_hits = 0
    for i in range(eval_end - eval_start):
        t = eval_start + i
        sum_z = F[t, 0, sum_z_idx]  # broadcast feature

        # When sum is high (z>0.5), use gap-oriented strategy
        # When sum is low (z<-0.5), use frequency strategy
        # Otherwise use best overall strategy
        if sum_z > 0.5 and 'C_zone_constrained' in strategies:
            g = strategies['C_zone_constrained']['genome']
        elif sum_z < -0.5 and 'D_sum_constrained' in strategies:
            g = strategies['D_sum_constrained']['genome']
        else:
            g = strategies['A_standard']['genome']

        fi, w = g.features, g.weights
        scores = F[t, :, :][:, fi].dot(w)
        selected = set(np.argsort(-scores)[:PICK] + 1)
        actual = set(np.where(hit[t] > 0)[0] + 1)
        if len(selected & actual) >= 2:
            rs_hits += 1
    rs_rate = rs_hits / (eval_end - eval_start)
    rs_edge = rs_rate - BASELINE_M2
    print(f"    Rate: {rs_rate*100:.2f}% Edge: {rs_edge*100:+.2f}%")

    # Method 5: Dynamic allocation (rolling 100-period best strategy)
    print("\n  [M5] Dynamic Allocation (rolling 100-period best)...")
    da_hits = 0
    window = 100
    for i in range(eval_end - eval_start):
        t = eval_start + i
        if i >= window:
            # Evaluate each strategy on last 100 periods
            best_name = None
            best_rolling = -1
            for name, g in viable:
                fi, w = g.features, g.weights
                rolling_hits = 0
                for j in range(max(0, i - window), i):
                    tj = eval_start + j
                    scores = F[tj, :, :][:, fi].dot(w)
                    sel = set(np.argsort(-scores)[:PICK] + 1)
                    act = set(np.where(hit[tj] > 0)[0] + 1)
                    if len(sel & act) >= 2:
                        rolling_hits += 1
                rolling_rate = rolling_hits / window
                if rolling_rate > best_rolling:
                    best_rolling = rolling_rate
                    best_name = name
            g = strategies[best_name]['genome']
        else:
            g = strategies['A_standard']['genome']

        fi, w = g.features, g.weights
        scores = F[t, :, :][:, fi].dot(w)
        selected = set(np.argsort(-scores)[:PICK] + 1)
        actual = set(np.where(hit[t] > 0)[0] + 1)
        if len(selected & actual) >= 2:
            da_hits += 1
    da_rate = da_hits / (eval_end - eval_start)
    da_edge = da_rate - BASELINE_M2
    print(f"    Rate: {da_rate*100:.2f}% Edge: {da_edge*100:+.2f}%")

    # Summary
    ensemble_results = {
        'M1_vote': {'rate': float(vote_rate), 'edge': float(vote_edge)},
        'M2_edge_weighted': {'rate': float(ew_rate), 'edge': float(ew_edge)},
        'M3_score_fusion': {'rate': float(sf_rate), 'edge': float(sf_edge)},
        'M4_regime_switch': {'rate': float(rs_rate), 'edge': float(rs_edge)},
        'M5_dynamic_alloc': {'rate': float(da_rate), 'edge': float(da_edge)},
    }

    best_ensemble = max(ensemble_results, key=lambda k: ensemble_results[k]['edge'])
    best_single = max(strategies, key=lambda k: strategies[k]['edge'])

    print(f"\n  Summary:")
    print(f"    Best single strategy: {best_single} edge={strategies[best_single]['edge']*100:+.2f}%")
    print(f"    Best ensemble:        {best_ensemble} edge={ensemble_results[best_ensemble]['edge']*100:+.2f}%")
    print(f"    Ensemble {'IMPROVES' if ensemble_results[best_ensemble]['edge'] > strategies[best_single]['edge'] else 'DOES NOT IMPROVE'} over single strategy")

    elapsed = time.time() - t0
    print(f"\n  Phase 4 time: {elapsed:.0f}s")

    return ensemble_results


# ================================================================
# Phase 5: Edge Ceiling Analysis
# ================================================================

def phase5_edge_ceiling(F, hit, feature_names, eval_start, eval_end):
    """Estimate theoretical maximum edge for this lottery."""
    print(f"\n{'=' * 72}")
    print("  Phase 5: Edge Ceiling Analysis")
    print(f"{'=' * 72}")
    t0 = time.time()

    T = eval_end - eval_start
    N = MAX_NUM

    # 1. Perfect oracle edge (upper bound)
    print("\n  [1] Perfect Oracle Analysis...")
    # If we could perfectly predict, what's the max hit rate?
    # Perfect oracle always picks 5 correct numbers → M5+ = 100%, M2+ = 100%
    # But with 5/39, even a partial oracle matters
    # Test: what if we could see the MOST LIKELY numbers?

    # Measure actual frequency stability
    freq_100 = np.zeros((T, N), dtype=np.float64)
    for i in range(T):
        t = eval_start + i
        s = max(0, t - 100)
        for j in range(s, t):
            freq_100[i] += hit[j]
    freq_100 /= np.maximum(np.arange(T).reshape(-1, 1).clip(1, 100), 1)

    # Ideal hit rate if we always pick top-5 by TRUE frequency
    # (This is a HINDSIGHT oracle — uses all past data correctly)
    oracle_hits = 0
    for i in range(T):
        t = eval_start + i
        # Use ALL past data to rank
        if t > 0:
            cumfreq = hit[:t].sum(axis=0)
            top5 = set(np.argsort(-cumfreq)[:PICK] + 1)
            actual = set(np.where(hit[t] > 0)[0] + 1)
            if len(top5 & actual) >= 2:
                oracle_hits += 1
    oracle_rate = oracle_hits / T
    oracle_edge = oracle_rate - BASELINE_M2
    print(f"    Cumulative frequency oracle: rate={oracle_rate*100:.2f}% edge={oracle_edge*100:+.2f}%")

    # 2. Entropy analysis
    print("\n  [2] Entropy Analysis...")
    # Individual number entropy (binary: drawn or not)
    entropies = []
    for n_idx in range(N):
        p = hit[eval_start:eval_end, n_idx].mean()
        if 0 < p < 1:
            h = -(p * np.log2(p) + (1 - p) * np.log2(1 - p))
        else:
            h = 0
        entropies.append(h)
    mean_entropy = np.mean(entropies)
    max_entropy = 1.0  # binary entropy maximum
    redundancy = 1 - mean_entropy / max_entropy

    print(f"    Mean per-number binary entropy: {mean_entropy:.4f} bits (max: {max_entropy:.4f})")
    print(f"    Redundancy: {redundancy*100:.2f}%")
    print(f"    Interpretation: {redundancy*100:.2f}% of information is 'predictable'")

    # Joint entropy of 5-number draws
    # Approximation: sum of individual entropies (assumes independence)
    joint_entropy_indep = mean_entropy * PICK
    # Theoretical max joint entropy for choosing 5 from 39
    from math import comb, log2
    max_joint_entropy = log2(comb(39, 5))  # log2(C(39,5)) = log2(575757) ≈ 19.13 bits
    print(f"    Joint entropy (indep approx): {joint_entropy_indep:.2f} bits")
    print(f"    Max draw entropy: {max_joint_entropy:.2f} bits (C(39,5) = {comb(39, 5)})")

    # 3. Auto-correlation analysis
    print("\n  [3] Auto-Correlation Analysis...")
    # Test if number appearances are auto-correlated
    max_lag = 20
    ac_results = []
    for lag in range(1, max_lag + 1):
        correlations = []
        for n_idx in range(N):
            series = hit[eval_start:eval_end, n_idx]
            if len(series) > lag:
                c = np.corrcoef(series[:-lag], series[lag:])[0, 1]
                if not np.isnan(c):
                    correlations.append(c)
        mean_ac = np.mean(correlations) if correlations else 0
        ac_results.append({'lag': lag, 'mean_ac': float(mean_ac)})
    print(f"    Lag | Mean AC")
    for ac in ac_results[:10]:
        star = ' ★' if abs(ac['mean_ac']) > 2 / np.sqrt(T) else ''
        print(f"      {ac['lag']:2d} | {ac['mean_ac']:+.4f}{star}")

    # 4. Monte Carlo simulation of theoretical edge limits
    print("\n  [4] Monte Carlo Theoretical Edge Limits...")
    mc_rng = np.random.RandomState(42)
    n_mc = 50000

    # Simulate: if we have a strategy with true edge e%, what's the observed variance?
    true_edges = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10]
    mc_results = []
    for true_edge_pct in true_edges:
        true_rate = BASELINE_M2 + true_edge_pct / 100
        observed = mc_rng.binomial(T, true_rate, n_mc) / T
        mean_obs = np.mean(observed)
        std_obs = np.std(observed)
        p95 = np.percentile(observed, [2.5, 97.5])
        mc_results.append({
            'true_edge': true_edge_pct,
            'true_rate': true_rate * 100,
            'observed_mean': float(mean_obs * 100),
            'observed_std': float(std_obs * 100),
            'ci95': [float(p95[0] * 100), float(p95[1] * 100)],
        })

    print(f"    {'True Edge':>10} {'Observed Mean':>15} {'Std':>8} {'95% CI':>20}")
    for mc in mc_results:
        print(f"    {mc['true_edge']:>+9.0f}% {mc['observed_mean']:>14.2f}% "
              f"{mc['observed_std']:>7.2f}% [{mc['ci95'][0]:.2f}%, {mc['ci95'][1]:.2f}%]")

    # 5. Signal strength estimation
    print("\n  [5] Signal Strength Estimation...")

    # Our best strategy's edge in context
    best_edge = 4.73  # from Phase 1
    se = np.sqrt(BASELINE_M2 * (1 - BASELINE_M2) / T)
    z_score = (best_edge / 100) / se
    print(f"    Best observed edge: +{best_edge:.2f}%")
    print(f"    Standard error: {se*100:.2f}%")
    print(f"    z-score: {z_score:.2f}")

    # Bonferroni-corrected significance (221 features tested)
    n_tests = 221
    bonferroni_alpha = 0.05 / n_tests
    from scipy.stats import norm
    z_bonferroni = norm.ppf(1 - bonferroni_alpha)
    significant_after_bonf = z_score > z_bonferroni
    print(f"    Bonferroni threshold (n={n_tests}): z>{z_bonferroni:.2f} (α={bonferroni_alpha:.5f})")
    print(f"    Passes Bonferroni: {'YES' if significant_after_bonf else 'NO'}")

    # 6. Ceiling estimation
    print("\n  [6] Edge Ceiling Estimation...")
    # Based on entropy analysis:
    # If redundancy = R%, then at most R% of draws are "predictable"
    # The theoretical max edge ≈ redundancy × (1 - baseline) for M2+ metric
    # But more conservatively: max edge ≈ sqrt(redundancy) × baseline × constant
    theoretical_max_edge = redundancy * BASELINE_M2 * 100  # rough upper bound
    print(f"    Theoretical max edge (entropy-based): ~{theoretical_max_edge:.1f}%")

    # Based on auto-correlation:
    max_ac = max(abs(ac['mean_ac']) for ac in ac_results)
    ac_based_max = max_ac * 100  # very rough
    print(f"    Max auto-correlation signal: {max_ac:.4f} → edge ceiling ~{ac_based_max:.1f}%")

    # Based on oracle:
    print(f"    Cumulative frequency oracle edge: {oracle_edge*100:+.2f}%")

    # Final ceiling estimate
    ceiling = max(theoretical_max_edge, oracle_edge * 100, 5.0)
    print(f"\n    ╔════════════════════════════════════════════════╗")
    print(f"    ║  Estimated Edge Ceiling: ~{ceiling:.1f}%                ║")
    print(f"    ║  Current Best Edge:      +{best_edge:.2f}%               ║")
    print(f"    ║  Utilization:            {best_edge/ceiling*100:.0f}%                    ║")
    print(f"    ╚════════════════════════════════════════════════╝")

    elapsed = time.time() - t0
    print(f"\n  Phase 5 time: {elapsed:.0f}s")

    return {
        'oracle_rate': float(oracle_rate),
        'oracle_edge': float(oracle_edge),
        'mean_entropy': float(mean_entropy),
        'redundancy': float(redundancy),
        'auto_correlations': ac_results,
        'max_autocorrelation': float(max_ac),
        'z_score': float(z_score),
        'bonferroni_pass': significant_after_bonf,
        'mc_simulations': mc_results,
        'ceiling_estimate': float(ceiling),
        'current_best_edge': float(best_edge),
        'utilization': float(best_edge / ceiling),
    }


# ================================================================
# Main
# ================================================================

def main():
    t_start = time.time()
    print("=" * 72)
    print("  MicroFish Phase 2 — Strategy Evolution & Signal Amplification")
    print("  DAILY_539 | 2026-03-15")
    print("=" * 72)

    from database import DatabaseManager
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    draws = sorted(db.get_all_draws('DAILY_539'), key=lambda x: (x['date'], x['draw']))
    draws = [d for d in draws if d.get('numbers') and len(d['numbers']) >= PICK]
    print(f"\n  Data: {len(draws)} draws, latest: {draws[-1]['draw']}")

    # Build feature matrix (reuse Phase 1 engine)
    print(f"\n  Building feature matrix...")
    F, feature_names, hit = build_feature_matrix(draws)

    eval_start = len(draws) - TEST_PERIODS
    eval_end = len(draws)
    print(f"  Eval window: [{eval_start}, {eval_end}) = {TEST_PERIODS} periods")

    # ---- Phase 1 ----
    p1_results = phase1_signal_amplification(F, hit, feature_names, eval_start, eval_end)

    # ---- Phase 2 ----
    p2_strategies = phase2_strategy_construction(F, hit, feature_names, eval_start, eval_end)

    # ---- Phase 3 ----
    p3_coverage = phase3_coverage_optimization(F, hit, feature_names, eval_start, eval_end, p2_strategies)

    # ---- Phase 4 ----
    p4_ensemble = phase4_ensemble_evolution(F, hit, feature_names, eval_start, eval_end, p2_strategies)

    # ---- Phase 5 ----
    p5_ceiling = phase5_edge_ceiling(F, hit, feature_names, eval_start, eval_end)

    # ---- Final Summary ----
    elapsed = time.time() - t_start
    print(f"\n{'=' * 72}")
    print("  FINAL RESEARCH SUMMARY")
    print(f"{'=' * 72}")

    best_single = max(p2_strategies, key=lambda k: p2_strategies[k]['edge'])
    best_single_edge = p2_strategies[best_single]['edge'] * 100

    best_ensemble_edge = max(p4_ensemble.values(), key=lambda x: x['edge'])['edge'] * 100 if p4_ensemble else 0
    best_ensemble_name = max(p4_ensemble, key=lambda k: p4_ensemble[k]['edge']) if p4_ensemble else 'N/A'

    print(f"\n  Phase 1 — Signal Amplification")
    print(f"    Best amplified combo edge: {p1_results.get('best_combo_edge', 0):+.2f}%")
    top_amp = p1_results['single_feature_results'][0] if p1_results['single_feature_results'] else None
    if top_amp:
        print(f"    Top amplified signal: {top_amp['name']} edge={top_amp['edge_pct']:+.2f}%")

    print(f"\n  Phase 2 — Strategy Construction")
    print(f"    Best strategy: {best_single} edge={best_single_edge:+.2f}%")
    for name, strat in p2_strategies.items():
        print(f"      {name}: edge={strat['edge']*100:+.2f}% perm_p={strat.get('perm_p', 'N/A')}")

    print(f"\n  Phase 3 — Coverage Optimization")
    print(f"    Best 2-bet edge: {p3_coverage['best_2bet_edge']*100:+.2f}% (p={p3_coverage['best_2bet_perm_p']:.4f})")
    print(f"    Best 3-bet edge: {p3_coverage['best_3bet_edge']*100:+.2f}%")

    print(f"\n  Phase 4 — Ensemble Evolution")
    print(f"    Best ensemble: {best_ensemble_name} edge={best_ensemble_edge:+.2f}%")
    print(f"    {'IMPROVES' if best_ensemble_edge > best_single_edge else 'DOES NOT IMPROVE'} over single strategy")

    print(f"\n  Phase 5 — Edge Ceiling")
    print(f"    Estimated ceiling: ~{p5_ceiling['ceiling_estimate']:.1f}%")
    print(f"    Current utilization: {p5_ceiling['utilization']*100:.0f}%")
    print(f"    Bonferroni significance: {'PASS' if p5_ceiling['bonferroni_pass'] else 'FAIL'}")

    print(f"\n  Total elapsed: {elapsed:.0f}s")

    # Save all results
    output = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_draws': len(draws),
        'eval_periods': TEST_PERIODS,
        'total_elapsed': round(elapsed, 1),
        'phase1_signal_amplification': {
            'single_features': p1_results['single_feature_results'],
            'best_combo_edge': p1_results.get('best_combo_edge', 0),
            'best_combo_features': p1_results.get('best_combo_features', []),
        },
        'phase2_strategies': {
            name: {
                'edge': strat['edge'],
                'features': strat['features'],
                'perm_p': strat.get('perm_p'),
                'signal': strat.get('signal'),
            }
            for name, strat in p2_strategies.items()
        },
        'phase3_coverage': {k: v for k, v in p3_coverage.items() if k != 'F_ext'},
        'phase4_ensemble': p4_ensemble,
        'phase5_ceiling': {k: v for k, v in p5_ceiling.items()},
    }

    out_path = os.path.join(project_root, 'microfish_phase2_results.json')
    with open(out_path, 'w') as fp:
        json.dump(output, fp, indent=2,
                  default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o))
    print(f"\n  Results saved: {out_path}")


if __name__ == '__main__':
    main()
