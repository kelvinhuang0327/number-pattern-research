#!/usr/bin/env python3
"""
威力彩 020期優化 — 修正回測 (v2)
================================
修正:
  1. Permutation test → Monte Carlo random strategy simulation
  2. hit_count 分佈 (≥2, ≥3 命中率)
  3. CSN threshold sensitivity sweep
  4. 比較 Fourier w100 vs w500 的具體差異
"""
import os
import sys
import math
import random
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))

MAX_NUM = 38
PICK = 6

# ===== Import from v1 =====
from tools.backtest_power_020_optimizations import (
    fourier_scores, deviation_echo_scores, markov_scores, echo_scores,
    generate_pp3v2, generate_pp3v2_5bet, generate_markov_echo_2bet,
    generate_pp3v1_legacy, generate_pp3v1_5bet_legacy,
    special_with_cold_safety_net,
)


def mc_pvalue(draws, strategy_fn, n_bets, start_offset=500, n_sims=500, seed=42):
    """Monte Carlo p-value: 隨機策略能達到同樣 edge 的概率"""
    total = len(draws)
    rng = random.Random(seed)

    # Actual strategy edge
    actual_hits = 0
    total_periods = total - start_offset
    for i in range(start_offset, total):
        history = draws[:i]
        actual = set(draws[i]['numbers'][:6])
        bets = strategy_fn(history)[:n_bets]
        all_pred = set()
        for bet in bets:
            all_pred.update(bet)
        if all_pred & actual:
            actual_hits += 1

    actual_rate = actual_hits / total_periods
    from math import comb
    p_miss_1 = comb(MAX_NUM - PICK, PICK) / comb(MAX_NUM, PICK)
    baseline = 1 - p_miss_1 ** n_bets
    actual_edge = actual_rate - baseline

    # Monte Carlo: random strategies
    count_ge = 0
    for sim in range(n_sims):
        sim_hits = 0
        for i in range(start_offset, total):
            actual = set(draws[i]['numbers'][:6])
            sim_pred = set()
            for _ in range(n_bets):
                sim_pred.update(sorted(rng.sample(range(1, MAX_NUM + 1), PICK)))
            if sim_pred & actual:
                sim_hits += 1
        sim_rate = sim_hits / total_periods
        sim_edge = sim_rate - baseline
        if sim_edge >= actual_edge:
            count_ge += 1

    return count_ge / n_sims, actual_edge, actual_rate, baseline


def detailed_hit_analysis(draws, strategy_fn, n_bets, start_offset=500, label=""):
    """詳細命中分析: hit≥1, hit≥2, hit≥3 分佈 + 三窗口"""
    total = len(draws)
    results = {'hit0': 0, 'hit1': 0, 'hit2': 0, 'hit3': 0, 'hit4p': 0}
    per_period = []

    for i in range(start_offset, total):
        history = draws[:i]
        actual = set(draws[i]['numbers'][:6])
        bets = strategy_fn(history)[:n_bets]

        all_pred = set()
        for bet in bets:
            all_pred.update(bet)
        hits = len(all_pred & actual)

        if hits == 0:
            results['hit0'] += 1
        elif hits == 1:
            results['hit1'] += 1
        elif hits == 2:
            results['hit2'] += 1
        elif hits == 3:
            results['hit3'] += 1
        else:
            results['hit4p'] += 1

        per_period.append(hits)

    n = len(per_period)
    avg_hits = sum(per_period) / n

    # 三窗口 avg hits
    windows = {
        '150p': per_period[-150:] if n >= 150 else per_period,
        '500p': per_period[-500:] if n >= 500 else per_period,
        f'all({n}p)': per_period,
    }

    # Expected average hits for k bets of 6 from 38
    # E[unique numbers] with k bets = 38*(1-(32/38)^k)... approximate
    # Simpler: each bet has E[hits]=6*6/38=0.947, but with unique pool...
    # For 2 bets, pool size≈12, E[hits]=12*6/38=1.894
    # For 3 bets, pool size≈18, E[hits]=18*6/38=2.842
    pool_size = min(n_bets * PICK, MAX_NUM)
    expected_avg = pool_size * PICK / MAX_NUM

    print(f"\n  {label}")
    print(f"  {'='*50}")
    print(f"  期數: {n}, 平均命中: {avg_hits:.3f} (期望: {expected_avg:.3f})")
    print(f"  Hit分佈: 0={results['hit0']}({results['hit0']/n*100:.1f}%) "
          f"1={results['hit1']}({results['hit1']/n*100:.1f}%) "
          f"2={results['hit2']}({results['hit2']/n*100:.1f}%) "
          f"3={results['hit3']}({results['hit3']/n*100:.1f}%) "
          f"4+={results['hit4p']}({results['hit4p']/n*100:.1f}%)")
    print(f"  Hit≥2: {(results['hit2']+results['hit3']+results['hit4p'])/n*100:.2f}%")
    print(f"  Hit≥3: {(results['hit3']+results['hit4p'])/n*100:.2f}%")

    for wname, wdata in windows.items():
        wn = len(wdata)
        wavg = sum(wdata) / wn
        wh2 = sum(1 for x in wdata if x >= 2)
        wh3 = sum(1 for x in wdata if x >= 3)
        print(f"  {wname}: avg_hit={wavg:.3f}, h≥2={wh2/wn*100:.1f}%, h≥3={wh3/wn*100:.1f}%")

    return per_period, results


def csn_sensitivity_sweep(draws, start_offset=500):
    """CSN Gap 閾值敏感度掃描"""
    print("\n特別號 Cold Safety Net — Gap 閾值掃描")
    print("=" * 60)

    thresholds = [10, 12, 15, 18, 20, 25]

    for th in thresholds:
        csn_hits = 0
        total = 0
        for i in range(start_offset, len(draws)):
            history = draws[:i]
            actual_sp = draws[i].get('special', 0)
            if actual_sp == 0:
                continue
            total += 1
            csn_top = special_with_cold_safety_net(history, gap_threshold=th)
            if actual_sp in csn_top:
                csn_hits += 1

        rate = csn_hits / total if total > 0 else 0
        edge = (rate - 0.375) * 100
        print(f"  Gap≥{th:2d}: hit_rate={rate*100:.2f}% edge={edge:+.2f}% (n={total})")


def fourier_window_sweep(draws, start_offset=500):
    """Fourier 窗口大小掃描"""
    print("\nFourier 窗口大小掃描 (注1 Top6 hit≥1)")
    print("=" * 60)

    windows = [50, 100, 150, 200, 300, 500]
    for w in windows:
        hits = 0
        total = 0
        for i in range(start_offset, len(draws)):
            history = draws[:i]
            actual = set(draws[i]['numbers'][:6])
            f = fourier_scores(history, window=w)
            f_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: f[n], reverse=True)
            bet1 = set(f_ranked[:PICK])
            if bet1 & actual:
                hits += 1
            total += 1

        rate = hits / total
        from math import comb
        bl = 1 - comb(MAX_NUM - PICK, PICK) / comb(MAX_NUM, PICK)  # 1-bet baseline
        edge = (rate - bl) * 100
        # Recent 150p
        r150 = 0
        for i in range(max(start_offset, len(draws)-150), len(draws)):
            history = draws[:i]
            actual = set(draws[i]['numbers'][:6])
            f = fourier_scores(history, window=w)
            f_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: f[n], reverse=True)
            bet1 = set(f_ranked[:PICK])
            if bet1 & actual:
                r150 += 1
        r150_n = min(150, len(draws) - start_offset)
        r150_rate = r150 / r150_n if r150_n > 0 else 0

        print(f"  w={w:4d}: hit_rate={rate*100:.2f}% edge={edge:+.2f}% | 150p={r150_rate*100:.1f}%")


def main():
    from lottery_api.database import DatabaseManager
    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    print(f"總期數: {len(draws)}\n")

    # 1. 詳細命中分析
    print("=" * 70)
    print("PART 1: 詳細命中分析")
    print("=" * 70)

    strategies = [
        ('PP3v1 w500 (2bet)', generate_pp3v1_legacy, 2),
        ('PP3v2 w100+DE (2bet)', generate_pp3v2, 2),
        ('PP3v1 w500 (3bet)', generate_pp3v1_legacy, 3),
        ('PP3v2 w100+DE (3bet)', generate_pp3v2, 3),
        ('Markov+Echo (2bet)', generate_markov_echo_2bet, 2),
    ]

    for label, fn, nb in strategies:
        detailed_hit_analysis(draws, fn, nb, label=label)

    # 2. Fourier window sweep
    print("\n" + "=" * 70)
    print("PART 2: Fourier 窗口掃描")
    print("=" * 70)
    fourier_window_sweep(draws)

    # 3. CSN sensitivity
    print("\n" + "=" * 70)
    print("PART 3: 特別號 CSN 閾值掃描")
    print("=" * 70)
    csn_sensitivity_sweep(draws)

    # 4. Monte Carlo p-value (only for key strategies, since it's slow)
    print("\n" + "=" * 70)
    print("PART 4: Monte Carlo p-value (200 simulations)")
    print("=" * 70)

    mc_strategies = [
        ('PP3v1 w500 (2bet)', generate_pp3v1_legacy, 2),
        ('PP3v2 w100+DE (2bet)', generate_pp3v2, 2),
        ('Markov+Echo (2bet)', generate_markov_echo_2bet, 2),
    ]

    for label, fn, nb in mc_strategies:
        p, edge, rate, bl = mc_pvalue(draws, fn, nb, n_sims=200)
        sig = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""
        print(f"  {label}: edge={edge*100:+.2f}% p={p:.3f} {sig}")


if __name__ == "__main__":
    main()
