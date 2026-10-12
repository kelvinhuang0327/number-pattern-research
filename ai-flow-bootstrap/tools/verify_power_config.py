#!/usr/bin/env python3
"""
威力彩配置驗證回測 — 確認還原後 Edge 正常
=========================================
2注 Fourier Rhythm + 3注 Power Precision
三窗口 (150/500/1500), 10-seed random baseline
"""
import os, sys
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from tools.predict_power_precision_3bet import generate_power_precision_3bet
from tools.power_fourier_rhythm import fourier_rhythm_predict

MAX_NUM = 38
PICK = 6

def random_predict(seed_val, draw_idx, n_bets):
    rng = np.random.RandomState(seed_val * 100000 + draw_idx)
    bets = []
    used = set()
    for _ in range(n_bets):
        pool = [n for n in range(1, MAX_NUM + 1) if n not in used]
        if len(pool) < PICK:
            pool = list(range(1, MAX_NUM + 1))
            used = set()
        chosen = sorted(rng.choice(pool, PICK, replace=False).tolist())
        used.update(chosen)
        bets.append(chosen)
    return bets

def count_matches(bet, actual):
    return len(set(bet) & set(actual))

def run_window(draws, strategy_fn, n_bets, window_size, label):
    total = len(draws)
    min_history = 500
    start_idx = max(min_history, total - window_size)
    end_idx = total
    n_tests = end_idx - start_idx

    m3_strategy = 0
    m3_random = {s: 0 for s in range(10)}

    for idx in range(start_idx, end_idx):
        history = draws[:idx]
        actual = set(draws[idx]['numbers'])

        try:
            bets = strategy_fn(history)
        except Exception as e:
            continue

        hit = any(count_matches(b, actual) >= 3 for b in bets)
        if hit: m3_strategy += 1

        for seed in range(10):
            r_bets = random_predict(seed, idx, n_bets)
            r_hit = any(count_matches(b, actual) >= 3 for b in r_bets)
            if r_hit: m3_random[seed] += 1

    avg_rnd = np.mean(list(m3_random.values()))
    rate_s = m3_strategy / n_tests * 100
    rate_r = avg_rnd / n_tests * 100
    edge = rate_s - rate_r

    return {
        'label': label, 'window': window_size, 'n_tests': n_tests,
        'm3': m3_strategy, 'rnd': avg_rnd,
        'rate': rate_s, 'rate_rnd': rate_r, 'edge': edge
    }

def main():
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    print(f"\n  威力彩資料: {len(draws)} 期, 最新: {draws[-1]['draw']}")
    print(f"  驗證方法: 三窗口 + 10-seed 隨機基準\n")

    strategies = [
        ('2注 Fourier Rhythm', 2, lambda h: fourier_rhythm_predict(h, n_bets=2, window=500)),
        ('3注 Power Precision', 3, lambda h: generate_power_precision_3bet(h)),
    ]

    for name, n_bets, fn in strategies:
        print("=" * 75)
        print(f"  {name}")
        print("=" * 75)
        results = []
        for w in [150, 500, 1500]:
            r = run_window(draws, fn, n_bets, w, name)
            results.append(r)
            status = "OK" if r['edge'] > 0 else "WARN"
            print(f"  {w:>5}期: M3+={r['m3']}/{r['n_tests']} ({r['rate']:.2f}%) "
                  f"vs Rnd {r['rnd']:.1f} ({r['rate_rnd']:.2f}%) "
                  f"| Edge={r['edge']:+.2f}% [{status}]")

        # Stability
        edges = [r['edge'] for r in results]
        all_pos = all(e > 0 for e in edges)
        decay = edges[0] - edges[2]
        if all_pos and abs(decay) < 3:
            stab = "STABLE"
        elif all_pos:
            stab = "MODERATE_DECAY"
        elif edges[2] > 0 and edges[0] < 0:
            stab = "LATE_BLOOMER"
        else:
            stab = "UNSTABLE"
        print(f"  → 穩定性: {edges[0]:+.2f}% / {edges[1]:+.2f}% / {edges[2]:+.2f}% → {stab}")
        print()

    print("=" * 75)
    print("  預期 Edge 對照:")
    print("    2注 Fourier Rhythm:  MEMORY 記錄 +1.91%")
    print("    3注 Power Precision: MEMORY 記錄 +2.30% (CLAUDE.md)")
    print("  若回測結果在 ±0.5% 內視為正常 (隨機種子差異)")
    print("=" * 75 + "\n")

if __name__ == '__main__':
    main()
