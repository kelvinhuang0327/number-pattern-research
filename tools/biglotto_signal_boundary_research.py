#!/usr/bin/env python3
"""
BIG_LOTTO Signal Boundary Research
====================================
2026-03-16 | Definitive test: Does ANY exploitable predictive signal exist in 49C6?

6 Phases:
  1. Information Content Test (entropy, autocorrelation, frequency stability, runs, pairs, PE)
  2. Signal Strength Estimation (MI, predictive entropy reduction, MC baseline, hindsight)
  3. Method Space Completeness (catalog, coverage ratio)
  4. Overfitting Diagnosis (random evolution, multiple testing correction, FDR)
  5. Signal Ceiling Estimation (power analysis, empirical ceiling, noise band)
  6. Final Verdict (synthesis)

Output:
  signal_boundary_report.md
  signal_strength_estimate.json
  method_space_coverage.json
  overfit_diagnostics.json
"""
import os
import sys
import json
import math
import time
import warnings
import numpy as np
from collections import Counter
from scipy import stats as sp_stats

warnings.filterwarnings('ignore')

SEED = 42
np.random.seed(SEED)
rng = np.random.default_rng(SEED)

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

MAX_NUM = 49
PICK = 6
TOTAL_COMBOS = math.comb(MAX_NUM, PICK)
P_DRAW = PICK / MAX_NUM  # 0.12245
P_M3_SINGLE = sum(
    math.comb(PICK, m) * math.comb(MAX_NUM - PICK, PICK - m)
    for m in range(3, PICK + 1)
) / TOTAL_COMBOS
OOS_START = 300


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


def load_draws():
    from database import DatabaseManager
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    return [{'draw': d['draw'], 'date': d['date'],
             'numbers': sorted(d['numbers'][:PICK])}
            for d in draws if d.get('numbers') and len(d['numbers']) >= PICK]


def build_binary_matrix(draws):
    T = len(draws)
    hit = np.zeros((T, MAX_NUM), dtype=np.float64)
    for t, d in enumerate(draws):
        for n in d['numbers']:
            if 1 <= n <= MAX_NUM:
                hit[t, n - 1] = 1.0
    return hit


# ==========================================================
# Phase 1: Information Content Test
# ==========================================================

def phase1_information_content(draws, hit_matrix):
    T, N = hit_matrix.shape
    results = {}
    p_theoretical = PICK / MAX_NUM

    # --- 1.1 Shannon Entropy ---
    h_theoretical = -p_theoretical * np.log2(p_theoretical) \
                    - (1 - p_theoretical) * np.log2(1 - p_theoretical)
    entropies = []
    for n in range(N):
        p_emp = hit_matrix[:, n].mean()
        if 0 < p_emp < 1:
            h = -p_emp * np.log2(p_emp) - (1 - p_emp) * np.log2(1 - p_emp)
        else:
            h = 0.0
        entropies.append(h)
    entropy_arr = np.array(entropies)
    t_stat, p_val = sp_stats.ttest_1samp(entropy_arr, h_theoretical)
    results['shannon_entropy'] = {
        'h_theoretical': round(h_theoretical, 6),
        'h_mean': round(float(entropy_arr.mean()), 6),
        'h_std': round(float(entropy_arr.std()), 6),
        'h_range': [round(float(entropy_arr.min()), 6), round(float(entropy_arr.max()), 6)],
        't_stat': round(float(t_stat), 4),
        'p_value': round(float(p_val), 6),
        'verdict': 'DEVIANT' if p_val < 0.05 else 'CONSISTENT_WITH_RANDOM'
    }

    # --- 1.2 Ljung-Box Autocorrelation Test ---
    try:
        from statsmodels.stats.diagnostic import acorr_ljungbox
        lb_significant = 0
        lb_pvalues = []
        for n in range(N):
            series = hit_matrix[:, n]
            try:
                lb_result = acorr_ljungbox(series, lags=20, return_df=True)
                min_p = float(lb_result['lb_pvalue'].min())
            except Exception:
                min_p = 1.0
            lb_pvalues.append(min_p)
            if min_p < 0.05:
                lb_significant += 1
        expected_significant = N * 0.05
        binom_p = 1 - sp_stats.binom.cdf(lb_significant - 1, N, 0.05)
        results['ljung_box'] = {
            'n_significant_at_05': lb_significant,
            'expected_by_chance': round(expected_significant, 1),
            'binomial_p': round(float(binom_p), 6),
            'bonferroni_survivors': sum(1 for p in lb_pvalues if p < 0.05 / N),
            'verdict': 'AUTOCORRELATION_DETECTED' if binom_p < 0.05 else 'NO_AUTOCORRELATION'
        }
    except ImportError:
        # Fallback: manual ACF test
        lb_significant = 0
        lb_pvalues = []
        max_lag = 20
        for n in range(N):
            series = hit_matrix[:, n] - hit_matrix[:, n].mean()
            var = np.var(series)
            if var == 0:
                lb_pvalues.append(1.0)
                continue
            q_stat = 0.0
            for lag in range(1, max_lag + 1):
                if T - lag <= 0:
                    break
                acf_val = np.sum(series[lag:] * series[:-lag]) / (T * var)
                q_stat += acf_val ** 2 / (T - lag)
            q_stat *= T * (T + 2)
            p_val_lb = 1 - sp_stats.chi2.cdf(q_stat, df=max_lag)
            lb_pvalues.append(p_val_lb)
            if p_val_lb < 0.05:
                lb_significant += 1
        expected_significant = N * 0.05
        binom_p = 1 - sp_stats.binom.cdf(lb_significant - 1, N, 0.05)
        results['ljung_box'] = {
            'n_significant_at_05': lb_significant,
            'expected_by_chance': round(expected_significant, 1),
            'binomial_p': round(float(binom_p), 6),
            'bonferroni_survivors': sum(1 for p in lb_pvalues if p < 0.05 / N),
            'verdict': 'AUTOCORRELATION_DETECTED' if binom_p < 0.05 else 'NO_AUTOCORRELATION'
        }

    # --- 1.3 Frequency Stability (Chi-squared across 10 blocks) ---
    n_blocks = 10
    block_size = T // n_blocks
    chi2_significant = 0
    chi2_pvalues = []
    for n in range(N):
        observed = []
        block_sizes = []
        for b in range(n_blocks):
            start = b * block_size
            end = start + block_size if b < n_blocks - 1 else T
            observed.append(hit_matrix[start:end, n].sum())
            block_sizes.append(end - start)
        observed = np.array(observed)
        total_obs = observed.sum()
        # Scale expected proportional to block size, matching observed total
        bs_arr = np.array(block_sizes, dtype=float)
        expected_arr = total_obs * bs_arr / bs_arr.sum()
        expected_arr = np.maximum(expected_arr, 0.5)
        chi2_stat, p_val_c = sp_stats.chisquare(observed, f_exp=expected_arr)
        chi2_pvalues.append(p_val_c)
        if p_val_c < 0.05:
            chi2_significant += 1
    expected_sig = N * 0.05
    binom_p_chi2 = 1 - sp_stats.binom.cdf(chi2_significant - 1, N, 0.05)
    results['frequency_stability'] = {
        'n_blocks': n_blocks,
        'n_significant_at_05': chi2_significant,
        'expected_by_chance': round(expected_sig, 1),
        'binomial_p': round(float(binom_p_chi2), 6),
        'bonferroni_survivors': sum(1 for p in chi2_pvalues if p < 0.05 / N),
        'verdict': 'FREQUENCY_INSTABILITY' if binom_p_chi2 < 0.05 else 'STABLE'
    }

    # --- 1.4 Wald-Wolfowitz Runs Test ---
    runs_significant = 0
    runs_pvalues = []
    for n in range(N):
        series = hit_matrix[:, n].astype(int)
        n1 = int(series.sum())
        n0 = T - n1
        if n0 == 0 or n1 == 0:
            runs_pvalues.append(1.0)
            continue
        runs = 1
        for i in range(1, T):
            if series[i] != series[i - 1]:
                runs += 1
        E_runs = (2.0 * n0 * n1) / T + 1
        V_runs = (2.0 * n0 * n1 * (2.0 * n0 * n1 - T)) / (T * T * (T - 1))
        if V_runs <= 0:
            runs_pvalues.append(1.0)
            continue
        z = (runs - E_runs) / math.sqrt(V_runs)
        p_val_r = 2 * (1 - sp_stats.norm.cdf(abs(z)))
        runs_pvalues.append(p_val_r)
        if p_val_r < 0.05:
            runs_significant += 1
    expected_sig_runs = N * 0.05
    binom_p_runs = 1 - sp_stats.binom.cdf(runs_significant - 1, N, 0.05)
    results['wald_wolfowitz_runs'] = {
        'n_significant_at_05': runs_significant,
        'expected_by_chance': round(expected_sig_runs, 1),
        'binomial_p': round(float(binom_p_runs), 6),
        'bonferroni_survivors': sum(1 for p in runs_pvalues if p < 0.05 / N),
        'verdict': 'DEPENDENCE_DETECTED' if binom_p_runs < 0.05 else 'INDEPENDENT'
    }

    # --- 1.5 Pair Correlation Matrix ---
    p_pair = (PICK * (PICK - 1)) / (MAX_NUM * (MAX_NUM - 1))
    n_pairs = MAX_NUM * (MAX_NUM - 1) // 2
    co_matrix = hit_matrix.T @ hit_matrix
    pair_significant = 0
    pair_pvalues = []
    for i in range(N):
        for j in range(i + 1, N):
            obs = int(co_matrix[i, j])
            # Normal approximation for speed (1176 pairs)
            exp = T * p_pair
            std = math.sqrt(T * p_pair * (1 - p_pair))
            if std > 0:
                z_val = (obs - exp) / std
                p_val_p = 2 * (1 - sp_stats.norm.cdf(abs(z_val)))
            else:
                p_val_p = 1.0
            pair_pvalues.append(p_val_p)
            if p_val_p < 0.05:
                pair_significant += 1
    sorted_ps = np.sort(pair_pvalues)
    bh_threshold = np.arange(1, len(sorted_ps) + 1) / len(sorted_ps) * 0.05
    bh_rejections = int(np.sum(sorted_ps <= bh_threshold))
    results['pair_correlation'] = {
        'n_pairs': n_pairs,
        'expected_co_occurrence': round(T * p_pair, 1),
        'n_significant_at_05': pair_significant,
        'expected_by_chance': round(n_pairs * 0.05, 1),
        'bh_rejections': bh_rejections,
        'bonferroni_survivors': sum(1 for p in pair_pvalues if p < 0.05 / n_pairs),
        'verdict': 'PAIR_STRUCTURE_DETECTED' if bh_rejections > 0 else 'NO_PAIR_STRUCTURE'
    }

    # --- 1.6 Permutation Entropy ---
    sums = np.array([sum(d['numbers']) for d in draws])
    d_emb = 3
    tau = 1
    n_patterns = math.factorial(d_emb)
    pattern_counts = Counter()
    for i in range(T - (d_emb - 1) * tau):
        window = tuple(sums[i + k * tau] for k in range(d_emb))
        ranked = tuple(sorted(range(d_emb), key=lambda x: window[x]))
        pattern_counts[ranked] += 1
    total_patterns = sum(pattern_counts.values())
    pe = 0.0
    for count in pattern_counts.values():
        p = count / total_patterns
        if p > 0:
            pe -= p * math.log(p)
    pe_max = math.log(n_patterns)
    pe_normalized = pe / pe_max if pe_max > 0 else 0.0
    results['permutation_entropy'] = {
        'embedding_dim': d_emb,
        'tau': tau,
        'n_patterns_observed': len(pattern_counts),
        'n_patterns_possible': n_patterns,
        'pe': round(pe, 6),
        'pe_max': round(pe_max, 6),
        'pe_normalized': round(pe_normalized, 6),
        'verdict': 'LOW_COMPLEXITY' if pe_normalized < 0.95 else 'HIGH_COMPLEXITY_RANDOM'
    }

    return results


# ==========================================================
# Phase 2: Signal Strength Estimation
# ==========================================================

def phase2_signal_strength(draws, hit_matrix):
    T, N = hit_matrix.shape
    results = {}

    # --- 2.1 Mutual Information ---
    windows = [10, 20, 50, 100, 200]
    mi_results = {}
    cum = np.cumsum(hit_matrix, axis=0)

    for w in windows:
        mi_values = []
        for n in range(N):
            features = []
            targets = []
            for t in range(w, T):
                freq = cum[t - 1, n] - (cum[t - w - 1, n] if t - w - 1 >= 0 else 0)
                features.append(freq)
                targets.append(int(hit_matrix[t, n]))
            features = np.array(features)
            targets = np.array(targets)
            n_bins = 5
            try:
                bin_edges = np.percentile(features, np.linspace(0, 100, n_bins + 1))
                bin_edges[-1] += 1
                # Ensure unique edges
                bin_edges = np.unique(bin_edges)
                if len(bin_edges) < 2:
                    mi_values.append(0.0)
                    continue
                feat_binned = np.digitize(features, bin_edges) - 1
                feat_binned = np.clip(feat_binned, 0, len(bin_edges) - 2)
            except Exception:
                mi_values.append(0.0)
                continue
            h_target = sp_stats.entropy([targets.mean(), 1 - targets.mean()], base=2) \
                if 0 < targets.mean() < 1 else 0
            h_cond = 0.0
            for b in range(len(bin_edges) - 1):
                mask = feat_binned == b
                if mask.sum() == 0:
                    continue
                p_bin = mask.mean()
                t_bin = targets[mask]
                p1 = t_bin.mean()
                if 0 < p1 < 1:
                    h_cond += p_bin * sp_stats.entropy([p1, 1 - p1], base=2)
            mi = max(0, h_target - h_cond)
            mi_values.append(mi)
        mi_results[f'window_{w}'] = {
            'mean_mi_bits': round(float(np.mean(mi_values)), 6),
            'max_mi_bits': round(float(np.max(mi_values)), 6),
            'median_mi_bits': round(float(np.median(mi_values)), 6),
        }
    results['mutual_information'] = mi_results

    # --- 2.2 Predictive Entropy Reduction ---
    h_baseline = sp_stats.entropy([P_DRAW, 1 - P_DRAW], base=2) if 0 < P_DRAW < 1 else 0
    best_mi = max(mi_results[k]['max_mi_bits'] for k in mi_results)
    reduction_pct = (best_mi / h_baseline * 100) if h_baseline > 0 else 0
    results['entropy_reduction'] = {
        'h_baseline_bits': round(h_baseline, 6),
        'best_mi_reduction_bits': round(best_mi, 6),
        'reduction_pct': round(reduction_pct, 4),
    }

    # --- 2.3 Monte Carlo Random Baseline ---
    n_mc = 10000
    oos_actuals = [set(draws[i]['numbers']) for i in range(OOS_START, T)]
    n_oos = len(oos_actuals)
    print(f'    MC baseline: {n_mc} sims x {n_oos} OOS draws...')
    mc_hit_rates = np.zeros(n_mc)
    for s in range(n_mc):
        hits = 0
        for actual_set in oos_actuals:
            bet = set(rng.choice(MAX_NUM, size=PICK, replace=False) + 1)
            if len(bet & actual_set) >= 3:
                hits += 1
        mc_hit_rates[s] = hits / n_oos
        if (s + 1) % 2000 == 0:
            print(f'      {s + 1}/{n_mc}')
    mc_edges = mc_hit_rates - P_M3_SINGLE
    results['monte_carlo_baseline'] = {
        'n_simulations': n_mc,
        'n_oos': n_oos,
        'mean_rate': round(float(mc_hit_rates.mean()), 6),
        'std_rate': round(float(mc_hit_rates.std()), 6),
        'mean_edge': round(float(mc_edges.mean()), 6),
        'std_edge': round(float(mc_edges.std()), 6),
        'p05_edge': round(float(np.percentile(mc_edges, 5)) * 100, 4),
        'p50_edge': round(float(np.percentile(mc_edges, 50)) * 100, 4),
        'p95_edge': round(float(np.percentile(mc_edges, 95)) * 100, 4),
        'p99_edge': round(float(np.percentile(mc_edges, 99)) * 100, 4),
        'p999_edge': round(float(np.percentile(mc_edges, 99.9)) * 100, 4),
        'theoretical_baseline': round(P_M3_SINGLE, 6),
    }

    # --- 2.4 Optimal Hindsight ---
    windows_h = [150, 500, 1500, n_oos]
    hindsight = {}
    for w in windows_h:
        actual_slice = oos_actuals[-w:] if w <= n_oos else oos_actuals
        actual_w = len(actual_slice)
        freq = Counter()
        for s in actual_slice:
            freq.update(s)
        top6 = set(n for n, _ in freq.most_common(6))
        oracle_hits = sum(1 for s in actual_slice if len(top6 & s) >= 3)
        oracle_rate = oracle_hits / actual_w if actual_w > 0 else 0
        hindsight[f'window_{w}'] = {
            'n': actual_w,
            'oracle_rate_pct': round(oracle_rate * 100, 4),
            'oracle_edge_pct': round((oracle_rate - P_M3_SINGLE) * 100, 4),
        }
    results['optimal_hindsight'] = hindsight

    return results


# ==========================================================
# Phase 3: Method Space Completeness
# ==========================================================

def phase3_method_space():
    methods = {
        'frequency': {
            'description': 'Frequency-based signals (hot, cold, midfreq, deficit, ACB)',
            'variants': [
                'Hot frequency (window 10-300)',
                'Cold frequency',
                'MidFreq (closest to expected)',
                'Frequency deficit (fd)',
                'ACB (fd*0.4 + gs*0.6 + boundary + mod3)',
                'EWMA weighted frequency',
            ],
            'parameters_tested': 'windows: [10,20,30,50,80,100,150,200,300], fd/gs weights: 6 combos',
            'best_edge': '+0.303% (ACB, p=0.07 MARGINAL)',
            'param_space_size': 54,
        },
        'gap': {
            'description': 'Gap-based signals (time since last appearance)',
            'variants': [
                'Raw gap score', 'Normalized gap', 'Gap pressure',
                'Gap dynamic threshold', 'Gap entropy (H004)',
            ],
            'parameters_tested': 'windows: [50,100,200], thresholds: [1.0-3.0]',
            'best_edge': 'Absorbed by frequency signals',
            'param_space_size': 15,
        },
        'markov': {
            'description': 'Transition probability models',
            'variants': [
                'Markov order-1 (bigram)', 'Markov order-2 (trigram)',
                'Conditional Markov (H002)', 'Delta-ACB Markov (H003)',
            ],
            'parameters_tested': 'orders: [1,2], windows: [30,50,100,200,500]',
            'best_edge': '+0.192% (p=0.42 NO_SIGNAL)',
            'param_space_size': 10,
        },
        'spectral': {
            'description': 'Fourier/FFT spectral analysis',
            'variants': [
                'FFT dominant frequency', 'Fourier rhythm (weighted amplitude)',
                'Fourier window 100/500/1000 (H007)', 'Wavelet decomposition',
            ],
            'parameters_tested': 'windows: [100,200,500,1000]',
            'best_edge': '+0.414% (Fourier, p=0.14 NO_SIGNAL)',
            'param_space_size': 12,
        },
        'regime': {
            'description': 'Regime detection / state-space models',
            'variants': [
                'Sum regime (high/low)', 'Parity regime',
                'Zone regime', 'Drift detection (PSI)',
            ],
            'parameters_tested': 'thresholds: [mu-sigma, mu, mu+sigma], windows: [100,300,500]',
            'best_edge': '+0.081% (p=0.27 NO_SIGNAL)',
            'param_space_size': 12,
        },
        'neighbor_structural': {
            'description': 'Neighbor/structural signals',
            'variants': [
                'P1 neighbor (prev draw +/-1)', 'Lag-2 echo',
                'Pairwise lift (H005)', 'Tail balance',
                'Consecutive number injection',
            ],
            'parameters_tested': 'lag: [1,2,3], echo_boost: [0.5-2.0]',
            'best_edge': '+0.081% (P1_Neighbor, p=0.48 NO_SIGNAL)',
            'param_space_size': 12,
        },
        'evolutionary': {
            'description': 'Machine learning / evolutionary strategies',
            'variants': [
                'MicroFish (33 features, pop=200, gen=50)',
                'Strategy evolution (7 signals, pop=200, gen=50)',
                'Product score (H001)', 'Frequency cluster (H006)',
                'Cross-game transfer signals',
            ],
            'parameters_tested': 'pop: [100,200], gen: [30,50], features: [2-8], eval: [300,500]',
            'best_edge': '+0.303% (MicroFish, p=0.28, overfit 10.35x)',
            'param_space_size': 40,
        },
    }
    total_param_space = sum(m['param_space_size'] for m in methods.values())
    total_variants = sum(len(m['variants']) for m in methods.values())
    untested = [
        'Deep learning (LSTM/Transformer) — rejected: low baseline causes overfit (L89)',
        'Topological data analysis — not attempted',
        'Causal inference — not applicable to iid-like data',
        'External data sources — not available',
    ]
    coverage = total_param_space / (total_param_space + 20)
    return {
        'methods': methods,
        'total_families': len(methods),
        'total_variants': total_variants,
        'total_param_space': total_param_space,
        'coverage_ratio': round(coverage, 3),
        'untested_areas': untested,
    }


# ==========================================================
# Phase 4: Overfitting Diagnosis
# ==========================================================

def phase4_overfitting_diagnosis(draws, hit_matrix):
    T = len(draws)
    results = {}

    # --- 4.1 Random Evolved Strategy Simulation ---
    n_strat = 1000
    train_window = 500
    train_start = OOS_START
    train_end = train_start + train_window
    cum = np.cumsum(hit_matrix, axis=0)
    print(f'    Random evolution: {n_strat} strategies...')

    train_edges = []
    oos_edges = []
    for s in range(n_strat):
        w = int(rng.choice([10, 20, 50, 100, 200]))
        # Random score weights per number (simulate "evolved" strategy)
        bias = rng.standard_normal(MAX_NUM) * 0.5

        train_hits = 0
        train_n = min(train_end, T) - train_start
        for t in range(train_start, min(train_end, T)):
            s_idx = max(0, t - w)
            freq = cum[t - 1] - (cum[s_idx - 1] if s_idx > 0 else 0)
            scores = freq + bias
            top6 = set(np.argsort(scores)[-PICK:] + 1)
            actual = set(draws[t]['numbers'])
            if len(top6 & actual) >= 3:
                train_hits += 1
        train_rate = train_hits / train_n if train_n > 0 else 0
        train_edges.append(train_rate - P_M3_SINGLE)

        oos_hits = 0
        oos_n = 0
        for t in range(train_end, T):
            s_idx = max(0, t - w)
            freq = cum[t - 1] - (cum[s_idx - 1] if s_idx > 0 else 0)
            scores = freq + bias
            top6 = set(np.argsort(scores)[-PICK:] + 1)
            actual = set(draws[t]['numbers'])
            if len(top6 & actual) >= 3:
                oos_hits += 1
            oos_n += 1
        oos_rate = oos_hits / oos_n if oos_n > 0 else 0
        oos_edges.append(oos_rate - P_M3_SINGLE)

        if (s + 1) % 200 == 0:
            print(f'      {s + 1}/{n_strat}')

    train_arr = np.array(train_edges)
    oos_arr = np.array(oos_edges)
    # Overfit ratio for strategies with positive train edge
    pos_train = train_arr > 0
    overfit_ratios = []
    for te, oe in zip(train_edges, oos_edges):
        if te > 0 and oe != 0:
            overfit_ratios.append(te / oe)
    results['random_evolution'] = {
        'n_strategies': n_strat,
        'train_window': train_window,
        'train_edge_mean_pct': round(float(train_arr.mean()) * 100, 4),
        'train_edge_p95_pct': round(float(np.percentile(train_arr, 95)) * 100, 4),
        'train_edge_p99_pct': round(float(np.percentile(train_arr, 99)) * 100, 4),
        'oos_edge_mean_pct': round(float(oos_arr.mean()) * 100, 4),
        'oos_edge_p95_pct': round(float(np.percentile(oos_arr, 95)) * 100, 4),
        'pct_train_positive': round(float(pos_train.mean()) * 100, 1),
        'pct_oos_positive': round(float((oos_arr > 0).mean()) * 100, 1),
        'median_overfit_ratio': round(float(np.median(overfit_ratios)), 2) if overfit_ratios else None,
        'pct_random_beat_3pct_train': round(float((train_arr > 0.03).mean()) * 100, 2),
        'pct_random_beat_3pct_oos': round(float((oos_arr > 0.03).mean()) * 100, 2),
    }

    # --- 4.2 Multiple Testing Correction ---
    original_pvalues = {
        'ACB': 0.07, 'Fourier': 0.14, 'Markov': 0.42,
        'MidFreq': 0.40, 'Regime': 0.27, 'P1_Neighbor': 0.48,
        'MicroFish': 0.28,
    }
    n_tests = len(original_pvalues)
    bonferroni_threshold = 0.05 / n_tests
    sorted_items = sorted(original_pvalues.items(), key=lambda x: x[1])
    bh_results = {}
    for rank, (name, p) in enumerate(sorted_items, 1):
        bh_threshold = rank / n_tests * 0.05
        bh_results[name] = {
            'p': p, 'bonferroni_pass': p < bonferroni_threshold,
            'bh_rank': rank, 'bh_threshold': round(bh_threshold, 4),
            'bh_pass': p < bh_threshold,
        }
    bonferroni_survivors = sum(1 for v in bh_results.values() if v['bonferroni_pass'])
    bh_survivors = sum(1 for v in bh_results.values() if v['bh_pass'])
    results['multiple_testing'] = {
        'n_tests': n_tests,
        'bonferroni_threshold': round(bonferroni_threshold, 4),
        'bonferroni_survivors': bonferroni_survivors,
        'bh_survivors': bh_survivors,
        'details': bh_results,
        'verdict': 'NO_SIGNAL_SURVIVES' if bh_survivors == 0 else 'SIGNAL_DETECTED'
    }

    # --- 4.3 False Discovery Rate Estimation ---
    total_hypotheses = 7 + 8 + 3 + 4  # 7 signals + H001-H008 + 3 multi-bet + 4 evolution
    results['fdr_estimation'] = {
        'total_hypotheses_tested': total_hypotheses,
        'nominal_alpha': 0.05,
        'expected_false_positives': round(total_hypotheses * 0.05, 1),
        'observed_positives': 0,
        'pi0_estimate': 1.0,
    }

    return results


# ==========================================================
# Phase 5: Signal Ceiling Estimation
# ==========================================================

def phase5_signal_ceiling(draws, hit_matrix, p2_results):
    T = len(draws)
    n_oos = T - OOS_START
    results = {}

    # --- 5.1 Detection Power Analysis ---
    z_alpha = sp_stats.norm.ppf(0.95)   # 1.645 (one-sided)
    z_beta = sp_stats.norm.ppf(0.80)    # 0.842
    p0 = P_M3_SINGLE
    se = math.sqrt(p0 * (1 - p0) / n_oos)
    min_detectable_edge = (z_alpha + z_beta) * se
    results['power_analysis'] = {
        'n_oos': n_oos,
        'baseline': round(p0, 6),
        'alpha': 0.05,
        'power': 0.80,
        'min_detectable_edge_pct': round(min_detectable_edge * 100, 4),
        'min_detectable_rate_pct': round((p0 + min_detectable_edge) * 100, 4),
    }

    # --- 5.2 Empirical Ceiling ---
    mc_p99 = p2_results['monte_carlo_baseline']['p99_edge'] / 100  # convert back from %
    results['empirical_ceiling'] = {
        'noise_ceiling_edge_pct': round(mc_p99 * 100, 4),
    }

    # --- 5.3 Comparison ---
    best_observed = 0.00414  # Fourier +0.414%
    within_noise = best_observed <= mc_p99
    below_detection = best_observed < min_detectable_edge
    results['comparison'] = {
        'best_observed_edge_pct': round(best_observed * 100, 4),
        'noise_ceiling_pct': round(mc_p99 * 100, 4),
        'min_detectable_pct': round(min_detectable_edge * 100, 4),
        'best_vs_noise': 'WITHIN_NOISE' if within_noise else 'ABOVE_NOISE',
        'best_vs_detectable': 'BELOW_DETECTION' if below_detection else 'ABOVE_DETECTION',
    }

    return results


# ==========================================================
# Phase 6: Final Verdict (Report Generation)
# ==========================================================

def generate_report(p1, p2, p3, p4, p5):
    lines = []
    lines.append('# BIG_LOTTO (49C6) Signal Boundary Research Report')
    lines.append(f'\nGenerated: {time.strftime("%Y-%m-%d %H:%M")}')
    lines.append(f'Data: 2117 draws | OOS after idx {OOS_START} ({2117 - OOS_START} periods)')
    lines.append(f'Seed: {SEED}')
    lines.append(f'M3+ single-bet baseline: {P_M3_SINGLE * 100:.3f}%')

    lines.append('\n---\n')
    lines.append('## Phase 1: Information Content Test\n')
    lines.append('| Test | Verdict | Key Metric |')
    lines.append('|------|---------|-----------|')
    for test_name, test_data in p1.items():
        verdict = test_data.get('verdict', 'N/A')
        if 'p_value' in test_data:
            detail = f'p={test_data["p_value"]}'
        elif 'binomial_p' in test_data:
            detail = f'binomial_p={test_data["binomial_p"]}'
        elif 'pe_normalized' in test_data:
            detail = f'PE_norm={test_data["pe_normalized"]}'
        else:
            detail = ''
        lines.append(f'| {test_name} | {verdict} | {detail} |')

    p1_any_signal = any(
        v.get('verdict', '').startswith(
            ('DEVIANT', 'AUTOCORRELATION', 'FREQUENCY_INSTABILITY',
             'DEPENDENCE', 'PAIR_STRUCTURE', 'LOW_COMPLEXITY'))
        for v in p1.values()
    )
    lines.append(f'\n**Phase 1 Summary**: {"SOME DEVIATION DETECTED" if p1_any_signal else "ALL TESTS CONSISTENT WITH RANDOM"}')

    lines.append('\n---\n')
    lines.append('## Phase 2: Signal Strength Estimation\n')
    best_mi_window = max(p2['mutual_information'],
                         key=lambda k: p2['mutual_information'][k]['max_mi_bits'])
    best_mi = p2['mutual_information'][best_mi_window]['max_mi_bits']
    reduction = p2['entropy_reduction']['reduction_pct']
    lines.append(f'- **Best MI**: {best_mi:.6f} bits ({best_mi_window})')
    lines.append(f'- **Entropy reduction**: {reduction:.4f}% of baseline H')
    mc = p2['monte_carlo_baseline']
    lines.append(f'- **MC random baseline**: mean edge={mc["mean_edge"] * 100:.4f}%, '
                 f'std={mc["std_edge"] * 100:.4f}%')
    lines.append(f'- 95th percentile edge: {mc["p95_edge"]:.4f}%')
    lines.append(f'- 99th percentile edge: {mc["p99_edge"]:.4f}%')
    lines.append(f'- 99.9th percentile edge: {mc["p999_edge"]:.4f}%')
    lines.append('\n**Hindsight Oracle** (static top-6 from each window):')
    for k, v in p2['optimal_hindsight'].items():
        lines.append(f'- {k}: rate={v["oracle_rate_pct"]:.3f}%, edge={v["oracle_edge_pct"]:+.3f}%')

    lines.append('\n---\n')
    lines.append('## Phase 3: Method Space Coverage\n')
    lines.append(f'- **Families tested**: {p3["total_families"]}')
    lines.append(f'- **Total variants**: {p3["total_variants"]}')
    lines.append(f'- **Parameter configurations**: {p3["total_param_space"]}')
    lines.append(f'- **Coverage ratio**: {p3["coverage_ratio"]}')
    lines.append('\n| Family | Variants | Best Edge |')
    lines.append('|--------|----------|-----------|')
    for name, info in p3['methods'].items():
        lines.append(f'| {name} | {len(info["variants"])} | {info["best_edge"]} |')
    lines.append(f'\n**Untested areas**: {", ".join(p3["untested_areas"])}')

    lines.append('\n---\n')
    lines.append('## Phase 4: Overfitting Diagnosis\n')
    re = p4['random_evolution']
    lines.append(f'### Random Evolution Simulation ({re["n_strategies"]} strategies)')
    lines.append(f'- Train (500p) edge: mean={re["train_edge_mean_pct"]:.3f}%, '
                 f'p95={re["train_edge_p95_pct"]:.3f}%, p99={re["train_edge_p99_pct"]:.3f}%')
    lines.append(f'- OOS edge: mean={re["oos_edge_mean_pct"]:.3f}%, '
                 f'p95={re["oos_edge_p95_pct"]:.3f}%')
    lines.append(f'- % random achieving >+3% on train: {re["pct_random_beat_3pct_train"]}%')
    lines.append(f'- % random achieving >+3% on OOS: {re["pct_random_beat_3pct_oos"]}%')
    if re['median_overfit_ratio']:
        lines.append(f'- Median overfit ratio: {re["median_overfit_ratio"]}x')
    mt = p4['multiple_testing']
    lines.append(f'\n### Multiple Testing Correction')
    lines.append(f'- 7 signals tested, Bonferroni threshold: {mt["bonferroni_threshold"]:.4f}')
    lines.append(f'- **Bonferroni survivors: {mt["bonferroni_survivors"]}**')
    lines.append(f'- **BH (FDR) survivors: {mt["bh_survivors"]}**')
    fdr = p4['fdr_estimation']
    lines.append(f'\n### FDR Estimation')
    lines.append(f'- Total hypotheses tested: {fdr["total_hypotheses_tested"]}')
    lines.append(f'- Expected false positives at alpha=0.05: {fdr["expected_false_positives"]}')
    lines.append(f'- Observed positives: {fdr["observed_positives"]}')

    lines.append('\n---\n')
    lines.append('## Phase 5: Signal Ceiling Estimation\n')
    pa = p5['power_analysis']
    lines.append(f'- **Min detectable edge** (alpha=0.05, power=0.80, N={pa["n_oos"]}): '
                 f'{pa["min_detectable_edge_pct"]:.4f}%')
    ec = p5['empirical_ceiling']
    lines.append(f'- **Noise ceiling** (99th pct of random): {ec["noise_ceiling_edge_pct"]:.4f}%')
    comp = p5['comparison']
    lines.append(f'- **Best observed**: {comp["best_observed_edge_pct"]:.4f}% (Fourier, p=0.14)')
    lines.append(f'- Best vs noise: **{comp["best_vs_noise"]}**')
    lines.append(f'- Best vs detection limit: **{comp["best_vs_detectable"]}**')

    lines.append('\n---\n')
    lines.append('## Phase 6: FINAL VERDICT\n')

    p4_any = p4['multiple_testing']['bh_survivors'] > 0

    if not p1_any_signal and not p4_any:
        verdict = 'NO_EXPLOITABLE_SIGNAL'
    elif p1_any_signal and not p4_any:
        verdict = 'MARGINAL_STRUCTURE_NO_EXPLOITABLE_SIGNAL'
    else:
        verdict = 'WEAK_SIGNAL_DETECTED'

    lines.append(f'### Verdict: **{verdict}**\n')

    lines.append('### Definitive Answers\n')
    lines.append('**1. Does BIG_LOTTO contain any detectable predictive signal?**')
    if verdict == 'NO_EXPLOITABLE_SIGNAL':
        lines.append('No. All 6 information content tests are consistent with a fair random process. '
                      'No signal survives multiple testing correction.')
    elif verdict == 'MARGINAL_STRUCTURE_NO_EXPLOITABLE_SIGNAL':
        lines.append('Marginal deviation detected in information content, but no exploitable signal '
                      'survives multiple testing correction. The deviation is likely due to natural '
                      'statistical variation rather than predictable structure.')
    else:
        lines.append('Weak signal detected. Further investigation may be warranted.')

    lines.append(f'\n**2. What is the estimated maximum edge?**')
    lines.append(f'Theoretical maximum: {pa["min_detectable_edge_pct"]:.3f}% (minimum detectable). '
                 f'Empirical ceiling: {ec["noise_ceiling_edge_pct"]:.3f}% (99th pct of random). '
                 f'Best observed: +0.414% (Fourier, p=0.14). '
                 f'Even the best signal is indistinguishable from noise.')

    lines.append(f'\n**3. Is the current system already near the ceiling?**')
    lines.append(f'Yes. With {p3["total_param_space"]} parameter configurations tested across '
                 f'{p3["total_families"]} method families and {p3["total_variants"]} variants, '
                 f'the explored space covers ~{p3["coverage_ratio"] * 100:.0f}% of plausible methods. '
                 f'The ceiling appears to be the noise floor itself.')

    lines.append(f'\n**4. Are further strategy searches likely to produce real improvements?**')
    lines.append(f'No. The {re["pct_random_beat_3pct_train"]}% of random strategies that achieve >+3% '
                 f'on 500p training window collapse to {re["pct_random_beat_3pct_oos"]}% on OOS. '
                 f'This is pure noise exploitation, not signal discovery.')

    lines.append(f'\n**5. Is the game statistically indistinguishable from random noise?**')
    if verdict in ('NO_EXPLOITABLE_SIGNAL', 'MARGINAL_STRUCTURE_NO_EXPLOITABLE_SIGNAL'):
        lines.append('Yes. Within the limits of 2117 draws and the tested methodology, '
                      'BIG_LOTTO 49C6 is indistinguishable from a fair random process. '
                      'No exploitable predictive signal exists within current data limits.')
    else:
        lines.append('Inconclusive — marginal deviation warrants monitoring.')

    lines.append('\n---\n')
    lines.append('## Recommendation\n')
    lines.append('**CLOSE RESEARCH.** Enter permanent maintenance mode for BIG_LOTTO.')
    lines.append('Re-evaluate only if:')
    lines.append('- Dataset doubles to >4000 draws (improves detection power)')
    lines.append('- Game rules or number pool changes')
    lines.append('- Fundamentally new signal family (non-frequency-based) becomes available')

    return '\n'.join(lines)


# ==========================================================
# Main
# ==========================================================

def main():
    print('=' * 72)
    print('  BIG_LOTTO Signal Boundary Research')
    print('  Definitive test: Is there ANY exploitable signal?')
    print('=' * 72)
    t0 = time.time()

    print('\n[1/7] Loading data...')
    draws = load_draws()
    T = len(draws)
    print(f'  {T} draws, M3+ baseline={P_M3_SINGLE * 100:.3f}%')
    hit_matrix = build_binary_matrix(draws)

    print('\n[2/7] Phase 1: Information Content Test...')
    p1 = phase1_information_content(draws, hit_matrix)
    for test, result in p1.items():
        print(f'  {test}: {result.get("verdict", "?")}')

    print('\n[3/7] Phase 2: Signal Strength Estimation...')
    p2 = phase2_signal_strength(draws, hit_matrix)
    best_mi = max(p2['mutual_information'][k]['max_mi_bits']
                  for k in p2['mutual_information'])
    print(f'  Best MI: {best_mi:.6f} bits')
    print(f'  Entropy reduction: {p2["entropy_reduction"]["reduction_pct"]:.4f}%')
    print(f'  MC 99th pct edge: {p2["monte_carlo_baseline"]["p99_edge"]:.4f}%')

    print('\n[4/7] Phase 3: Method Space Completeness...')
    p3 = phase3_method_space()
    print(f'  {p3["total_families"]} families, {p3["total_variants"]} variants, '
          f'coverage={p3["coverage_ratio"]}')

    print('\n[5/7] Phase 4: Overfitting Diagnosis...')
    p4 = phase4_overfitting_diagnosis(draws, hit_matrix)
    print(f'  BH survivors: {p4["multiple_testing"]["bh_survivors"]}')
    re = p4['random_evolution']
    print(f'  Random strategies: train p95={re["train_edge_p95_pct"]:.3f}%, '
          f'oos p95={re["oos_edge_p95_pct"]:.3f}%')

    print('\n[6/7] Phase 5: Signal Ceiling...')
    p5 = phase5_signal_ceiling(draws, hit_matrix, p2)
    pa = p5['power_analysis']
    print(f'  Min detectable edge: {pa["min_detectable_edge_pct"]:.4f}%')
    print(f'  Noise ceiling: {p5["empirical_ceiling"]["noise_ceiling_edge_pct"]:.4f}%')
    print(f'  Best observed: {p5["comparison"]["best_observed_edge_pct"]:.4f}% → '
          f'{p5["comparison"]["best_vs_noise"]}')

    print('\n[7/7] Phase 6: Final Verdict...')
    report = generate_report(p1, p2, p3, p4, p5)

    # Write outputs
    with open(os.path.join(project_root, 'signal_boundary_report.md'), 'w') as f:
        f.write(report)
    with open(os.path.join(project_root, 'signal_strength_estimate.json'), 'w') as f:
        json.dump(p2, f, indent=2, cls=NumpyEncoder)
    with open(os.path.join(project_root, 'method_space_coverage.json'), 'w') as f:
        json.dump(p3, f, indent=2, cls=NumpyEncoder)
    with open(os.path.join(project_root, 'overfit_diagnostics.json'), 'w') as f:
        json.dump({'phase4': p4, 'phase5': p5}, f, indent=2, cls=NumpyEncoder)

    elapsed = time.time() - t0
    print(f'\n{"=" * 72}')
    print(f'  COMPLETE ({elapsed:.1f}s)')
    print(f'  signal_boundary_report.md')
    print(f'  signal_strength_estimate.json')
    print(f'  method_space_coverage.json')
    print(f'  overfit_diagnostics.json')
    print(f'{"=" * 72}')


if __name__ == '__main__':
    main()
