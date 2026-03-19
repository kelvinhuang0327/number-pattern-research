#!/usr/bin/env python3
"""Permutation test for best regime-enhanced strategy"""
import os, sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'tools'))

from backtest_biglotto_sum_regime import (
    load_draws, backtest_strategy, ts3_regime_3bet,
    generate_triple_strike, regime_fourier_cold_2bet,
    ts3_regime_aggressive_3bet, MAX_NUM
)
import numpy as np
import random

draws = load_draws()
print(f"Loaded {len(draws)} draws")

def permutation_test_fast(draws, strategy_func, n_bets, test_periods, n_perms=200):
    """Permutation: shuffle actual numbers only in target draws"""
    # Real edge
    real = backtest_strategy(draws, strategy_func, n_bets, test_periods, "real")
    real_edge = real['edge']
    real_rate = real['rate']
    print(f"  Real: {real['m3_hits']}/{real['total']} ({real_rate:.2f}%) Edge={real_edge:+.2f}%")

    count_ge = 0
    rng = random.Random(42)

    for p in range(n_perms):
        # Shuffle only target draws, keep history intact
        m3_hits = 0
        total = 0
        for i in range(test_periods):
            target_idx = len(draws) - test_periods + i
            if target_idx < 100:
                continue
            hist = draws[:target_idx]
            # Random actual numbers
            fake_actual = set(sorted(rng.sample(range(1, MAX_NUM + 1), 6)))

            try:
                bets = strategy_func(hist)
                hit = any(len(set(bet) & fake_actual) >= 3 for bet in bets)
                if hit:
                    m3_hits += 1
                total += 1
            except:
                total += 1

        if total > 0:
            perm_rate = m3_hits / total * 100
            p1 = 1.86 / 100
            baseline = (1 - (1 - p1) ** n_bets) * 100
            perm_edge = perm_rate - baseline
            if perm_edge >= real_edge:
                count_ge += 1

        if (p + 1) % 50 == 0:
            print(f"    perm {p+1}/{n_perms} done...")

    p_value = count_ge / n_perms
    return real_edge, p_value

# Test TS3 baseline
print("\n=== TS3 baseline (3-bet, 1500p) ===")
edge_base, pval_base = permutation_test_fast(draws, generate_triple_strike, 3, 1500, 200)
print(f"  Edge={edge_base:+.2f}%, p={pval_base:.4f}")

# Test TS3+Regime (best 3-bet candidate)
print("\n=== TS3 + Regime s=0.3 th=5 (3-bet, 1500p) ===")
edge_regime, pval_regime = permutation_test_fast(draws, ts3_regime_3bet, 3, 1500, 200)
print(f"  Edge={edge_regime:+.2f}%, p={pval_regime:.4f}")

# Test 2-bet Regime
print("\n=== 2bet Regime Fourier+Cold (2-bet, 1500p) ===")
edge_2b, pval_2b = permutation_test_fast(draws, regime_fourier_cold_2bet, 2, 1500, 200)
print(f"  Edge={edge_2b:+.2f}%, p={pval_2b:.4f}")

# Summary
print("\n" + "=" * 60)
print("  Permutation Test Summary")
print("=" * 60)
print(f"  TS3 baseline:        Edge={edge_base:+.2f}%, perm p={pval_base:.4f} {'SIG' if pval_base < 0.05 else 'NS'}")
print(f"  TS3+Regime(s=0.3):   Edge={edge_regime:+.2f}%, perm p={pval_regime:.4f} {'SIG' if pval_regime < 0.05 else 'NS'}")
print(f"  2bet Regime F+C:     Edge={edge_2b:+.2f}%, perm p={pval_2b:.4f} {'SIG' if pval_2b < 0.05 else 'NS'}")
print(f"\n  Regime improvement over baseline: {edge_regime - edge_base:+.2f}%")
