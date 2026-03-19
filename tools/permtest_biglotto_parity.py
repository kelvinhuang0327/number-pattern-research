#!/usr/bin/env python3
"""
Permutation test for TS3+Competitive+Parity (best 3bet variant)
and also test parity-only on current TS3+Regime baseline.
"""
import os, sys, json, sqlite3
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'tools'))

from backtest_biglotto_competitive import (
    load_draws, backtest_strategy, z_score,
    ts3_competitive_parity_3bet, ts3_regime_baseline,
    enforce_parity, MAX_NUM
)
from predict_biglotto_regime import (
    detect_sum_regime, fourier_regime_bet, cold_regime_bet
)
from predict_biglotto_triple_strike import (
    tail_balance_bet, generate_triple_strike
)


def ts3_regime_parity_baseline(history):
    """Current TS3+Regime but with parity constraint added"""
    regime, consec, strength = detect_sum_regime(history)
    if regime == 'NEUTRAL':
        bets = generate_triple_strike(history)
    else:
        bet1 = fourier_regime_bet(history, window=500, regime=regime, regime_strength=0.3)
        used = set(bet1)
        bet2 = cold_regime_bet(history, window=100, exclude=used, regime=regime)
        used.update(bet2)
        bet3 = tail_balance_bet(history, window=100, exclude=used)
        bets = [bet1, bet2, bet3]
    return [enforce_parity(b, max_same=5) for b in bets]


def permutation_test(draws, strategy_func, n_bets, test_periods, n_perms=200):
    """Permutation test: shuffle actual numbers and re-test"""
    real = backtest_strategy(draws, strategy_func, n_bets, test_periods)
    real_hits = real['m3_hits']
    real_total = real['total']

    perm_hits_list = []
    rng = np.random.RandomState(42)

    for p in range(n_perms):
        shuffled_draws = []
        for d in draws:
            nums = list(d['numbers'])
            shuffled = sorted(rng.choice(range(1, MAX_NUM + 1), size=6, replace=False))
            shuffled_draws.append({
                'draw': d['draw'], 'date': d['date'],
                'numbers': shuffled
            })

        perm_r = backtest_strategy(shuffled_draws, strategy_func, n_bets, test_periods)
        perm_hits_list.append(perm_r['m3_hits'])

        if (p + 1) % 50 == 0:
            print(f"    Permutation {p + 1}/{n_perms}")

    perm_arr = np.array(perm_hits_list)
    p_value = np.mean(perm_arr >= real_hits)

    return {
        'real_hits': real_hits,
        'real_total': real_total,
        'real_rate': real_hits / real_total * 100,
        'perm_mean': np.mean(perm_arr),
        'perm_std': np.std(perm_arr),
        'p_value': p_value,
        'significant': p_value < 0.05,
        'n_perms': n_perms,
    }


if __name__ == '__main__':
    draws = load_draws()
    print(f"Loaded {len(draws)} draws\n")

    test_periods = 1500

    # Test 1: TS3+Regime+Parity (new addition to current baseline)
    print("=" * 70)
    print("  Permutation Test: TS3+Regime+Parity (parity added to baseline)")
    print("=" * 70)
    r1 = permutation_test(draws, ts3_regime_parity_baseline, 3, test_periods, 200)
    print(f"\n  Real hits: {r1['real_hits']}/{r1['real_total']} = {r1['real_rate']:.2f}%")
    print(f"  Perm mean: {r1['perm_mean']:.1f} ± {r1['perm_std']:.1f}")
    print(f"  p-value:   {r1['p_value']:.4f}")
    print(f"  Significant (p<0.05): {r1['significant']}")

    # Test 2: TS3+Competitive+Parity (full new variant)
    print(f"\n{'=' * 70}")
    print("  Permutation Test: TS3+Competitive+Parity (full new variant)")
    print("=" * 70)
    r2 = permutation_test(draws, ts3_competitive_parity_3bet, 3, test_periods, 200)
    print(f"\n  Real hits: {r2['real_hits']}/{r2['real_total']} = {r2['real_rate']:.2f}%")
    print(f"  Perm mean: {r2['perm_mean']:.1f} ± {r2['perm_std']:.1f}")
    print(f"  p-value:   {r2['p_value']:.4f}")
    print(f"  Significant (p<0.05): {r2['significant']}")

    # Test 3: Original baseline for comparison
    print(f"\n{'=' * 70}")
    print("  Permutation Test: TS3+Regime (current baseline, no parity)")
    print("=" * 70)
    r3 = permutation_test(draws, ts3_regime_baseline, 3, test_periods, 200)
    print(f"\n  Real hits: {r3['real_hits']}/{r3['real_total']} = {r3['real_rate']:.2f}%")
    print(f"  Perm mean: {r3['perm_mean']:.1f} ± {r3['perm_std']:.1f}")
    print(f"  p-value:   {r3['p_value']:.4f}")
    print(f"  Significant (p<0.05): {r3['significant']}")

    # Summary
    print(f"\n{'=' * 70}")
    print("  SUMMARY")
    print("=" * 70)
    print(f"  {'Strategy':<40s} {'Hits':>5s} {'Rate':>7s} {'p-val':>7s} {'Sig':>5s}")
    print("  " + "-" * 65)
    for name, r in [("TS3+Regime (baseline)", r3),
                     ("TS3+Regime+Parity", r1),
                     ("TS3+Competitive+Parity", r2)]:
        sig = "YES" if r['significant'] else "NO"
        print(f"  {name:<40s} {r['real_hits']:5d} {r['real_rate']:6.2f}% {r['p_value']:6.4f} {sig:>5s}")
