"""
Permutation Test Utility — Shared Module
=========================================
Generic P3-style temporal shuffle permutation test.

Correct Usage (destroy temporal structure, not hits):
    1. Run strategy on real draws → real_edge
    2. Shuffle: randomly reassign number-sets across draw positions
       (preserves marginal distribution, destroys temporal order)
    3. Re-run same strategy on shuffled draws → shuffle_edge
    4. Repeat N times → null distribution
    5. p_emp = fraction of shuffle_edges >= real_edge

Do NOT shuffle the hits array — that is invalid for multi-bet OR strategies
because mean(hits) is invariant under permutation.

Usage:
    from lottery_api.engine.perm_test import perm_test

    result = perm_test(
        history=draws,          # list of draw dicts: [{'numbers': [...], ...}, ...]
        predict_fn=my_fn,       # callable(history) -> list[list[int]]
        baseline=0.0896,        # n-bet geometric baseline (required)
        n_perm=200,             # number of shuffles (default 200)
        seed=42,
    )
    # result keys:
    #   real_edge, shuffle_mean, shuffle_std
    #   p_emp, cohens_d, z_score, verdict
    #   n_oos, n_perm
"""

import math
import numpy as np


def _shuffle_draws(draws, rng):
    """
    Shuffle number-sets across draw positions.
    Preserves marginal distribution but destroys temporal structure.
    """
    number_sets = [d['numbers'][:] for d in draws]
    rng.shuffle(number_sets)
    result = []
    for i, d in enumerate(draws):
        nd = dict(d)
        nd['numbers'] = number_sets[i]
        result.append(nd)
    return result


def _run_walk_forward(draws, predict_fn, hit_fn, min_history):
    """Single walk-forward OOS backtest. Returns list of bool hits."""
    hits = []
    for i in range(min_history, len(draws)):
        history = draws[:i]
        actual = set(draws[i]['numbers'])
        try:
            bets = predict_fn(history)
            hit = any(hit_fn(b, actual) for b in bets)
        except Exception:
            hit = False
        hits.append(hit)
    return hits


def perm_test(
    history,
    predict_fn,
    baseline,
    hit_fn=None,
    min_history=200,
    n_perm=200,
    seed=42,
    verbose=False,
):
    """
    Temporal shuffle permutation test.

    Parameters
    ----------
    history    : list of draw dicts [{'numbers': [int, ...], ...}, ...]
    predict_fn : callable(history) -> list[list[int]]  (list of bets)
    baseline   : float  n-bet geometric baseline (e.g. 0.0896 for 5-bet BIG_LOTTO)
    hit_fn     : callable(bet, actual_set) -> bool  (default: M3+ match)
    min_history: int  minimum training window before OOS starts (default 200)
    n_perm     : int  number of shuffle iterations (default 200)
    seed       : int  random seed for reproducibility
    verbose    : bool print progress

    Returns
    -------
    dict with keys:
        n_oos        : int   OOS periods evaluated
        real_edge    : float strategy edge vs baseline (fraction)
        real_rate    : float strategy hit rate (fraction)
        shuffle_mean : float mean shuffled edge
        shuffle_std  : float std of shuffled edges
        p_emp        : float empirical permutation p-value (conservative)
        cohens_d     : float effect size
        z_score      : float (real_edge - shuffle_mean) / shuffle_std
        verdict      : str   'SIGNAL_DETECTED' | 'MARGINAL' | 'NO_SIGNAL'
    """
    if hit_fn is None:
        def hit_fn(bet, actual_set):
            return len(set(bet) & actual_set) >= 3

    # 1. Real edge
    real_hits = _run_walk_forward(history, predict_fn, hit_fn, min_history)
    n_oos = len(real_hits)
    real_rate = sum(real_hits) / n_oos if n_oos else 0.0
    real_edge = real_rate - baseline

    if verbose:
        print(f"  [perm_test] OOS={n_oos}  real_rate={real_rate*100:.2f}%  "
              f"real_edge={real_edge*100:+.2f}%  running {n_perm} shuffles...",
              flush=True)

    # 2. Shuffled edges
    rng = np.random.RandomState(seed)
    shuffle_edges = []
    for s in range(n_perm):
        shuffled = _shuffle_draws(history, rng)
        s_hits = _run_walk_forward(shuffled, predict_fn, hit_fn, min_history)
        n_s = len(s_hits)
        s_rate = sum(s_hits) / n_s if n_s else 0.0
        shuffle_edges.append(s_rate - baseline)
        if verbose and (s + 1) % 50 == 0:
            print(f"    shuffle {s+1}/{n_perm}", flush=True)

    # 3. Statistics
    shuffle_mean = float(np.mean(shuffle_edges))
    shuffle_std = float(np.std(shuffle_edges)) if np.std(shuffle_edges) > 0 else 1e-6

    n_greater = sum(1 for se in shuffle_edges if se >= real_edge)
    p_emp = (n_greater + 1) / (n_perm + 1)  # conservative adjustment

    cohens_d = (real_edge - shuffle_mean) / shuffle_std
    z_score = cohens_d  # same formula for effect size vs null distribution

    if p_emp < 0.05:
        verdict = 'SIGNAL_DETECTED'
    elif p_emp < 0.10:
        verdict = 'MARGINAL'
    else:
        verdict = 'NO_SIGNAL'

    return {
        'n_oos': n_oos,
        'real_edge': real_edge,
        'real_rate': real_rate,
        'shuffle_mean': shuffle_mean,
        'shuffle_std': shuffle_std,
        'p_emp': round(p_emp, 4),
        'cohens_d': round(cohens_d, 3),
        'z_score': round(z_score, 3),
        'verdict': verdict,
        'n_perm': n_perm,
        'shuffle_edges': shuffle_edges,
    }


def perm_test_report(result, label='Strategy', baseline_label=None):
    """Print a formatted permutation test report."""
    e = result['real_edge'] * 100
    sm = result['shuffle_mean'] * 100
    ss = result['shuffle_std'] * 100
    verdict = result['verdict']
    icon = {'SIGNAL_DETECTED': '✅', 'MARGINAL': '⚠️', 'NO_SIGNAL': '❌'}.get(verdict, '?')
    bl = f"  baseline: {baseline_label}" if baseline_label else ''
    print(f"  [{label}] OOS={result['n_oos']}  real_edge={e:+.2f}%{bl}")
    print(f"  shuffle: mean={sm:+.2f}%  std={ss:.2f}%  N={result['n_perm']}")
    print(f"  p_emp={result['p_emp']:.4f}  Cohen's d={result['cohens_d']:.3f}")
    print(f"  → {verdict} {icon}")
