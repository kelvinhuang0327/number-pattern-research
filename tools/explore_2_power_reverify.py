#!/usr/bin/env python3
"""
探索 #2: 威力彩策略穩定性重驗證
================================
重跑威力彩已登記策略的 1500 期回測，確認 Edge 未衰退。

已登記策略:
  - Fourier Rhythm 2注: Edge +1.91%
  - Power Precision 3注: Edge +2.30%
  - Power Quad Precision 4注: Edge +1.95%

威力彩參數: 6/38, P_single(M3+) = 3.87%
"""
import os
import sys
import time
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))

from lottery_api.database import DatabaseManager

P_SINGLE_POWER = 0.0387
MIN_HISTORY = 200
SEED = 42

BASELINES = {
    2: (1 - (1 - P_SINGLE_POWER) ** 2) * 100,  # 7.59%
    3: (1 - (1 - P_SINGLE_POWER) ** 3) * 100,  # 11.17%
    4: (1 - (1 - P_SINGLE_POWER) ** 4) * 100,  # 14.60%
}


def backtest_power_strategy(draws, strategy_func, n_bets, n_periods=1500):
    """通用威力彩回測引擎"""
    np.random.seed(SEED)

    start_idx = max(MIN_HISTORY, len(draws) - n_periods)
    test_draws = draws[start_idx:]
    baseline = BASELINES[n_bets]

    hits = 0
    total = 0

    for target_draw in test_draws:
        target_idx = draws.index(target_draw)
        if target_idx < MIN_HISTORY:
            continue

        history = draws[:target_idx]
        actual = set(target_draw['numbers'])

        try:
            bets = strategy_func(history)
            won = False
            for b in bets:
                nums = set(b) if isinstance(b, list) else set(b)
                if len(nums & actual) >= 3:
                    won = True
                    break
            if won:
                hits += 1
        except Exception as e:
            pass

        total += 1

    rate = (hits / total * 100) if total > 0 else 0
    edge = rate - baseline
    return hits, total, rate, baseline, edge


def main():
    print("=" * 70)
    print("🔬 探索 #2: 威力彩策略穩定性重驗證 (1500期)")
    print("=" * 70)

    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('POWER_LOTTO'),
                   key=lambda x: (x.get('date', ''), x.get('draw', 0)))

    print(f"  Total Power Lotto draws: {len(draws)}")
    print(f"  Last draw: {draws[-1]['draw']} | {draws[-1]['date']}")

    # Strategy 1: Fourier Rhythm 2-bet
    print(f"\n--- Fourier Rhythm 2注 (claimed Edge +1.91%) ---")
    try:
        from tools.power_fourier_rhythm import fourier_rhythm_predict
        t0 = time.time()
        h, t, r, bl, e = backtest_power_strategy(
            draws, lambda hist: fourier_rhythm_predict(hist, n_bets=2, window=500), 2)
        elapsed = time.time() - t0
        v = "✅" if e > 0 else "❌"
        print(f"  Rate: {r:5.2f}% | Baseline: {bl:5.2f}% | Edge: {e:+5.2f}% | "
              f"Hits: {h}/{t} | {v} ({elapsed:.1f}s)")
    except Exception as ex:
        print(f"  ERROR: {ex}")

    # Strategy 2: Power Precision 3-bet
    print(f"\n--- Power Precision 3注 (claimed Edge +2.30%) ---")
    try:
        from tools.predict_power_precision_3bet import generate_power_precision_3bet
        t0 = time.time()
        h, t, r, bl, e = backtest_power_strategy(
            draws, generate_power_precision_3bet, 3)
        elapsed = time.time() - t0
        v = "✅" if e > 0 else "❌"
        print(f"  Rate: {r:5.2f}% | Baseline: {bl:5.2f}% | Edge: {e:+5.2f}% | "
              f"Hits: {h}/{t} | {v} ({elapsed:.1f}s)")
    except Exception as ex:
        print(f"  ERROR: {ex}")

    # Strategy 3: Power Quad Precision 4-bet
    print(f"\n--- Power Quad Precision 4注 (claimed Edge +1.95%) ---")
    try:
        from tools.predict_power_quad_precision import generate_power_quad_precision
        t0 = time.time()
        h, t, r, bl, e = backtest_power_strategy(
            draws, generate_power_quad_precision, 4)
        elapsed = time.time() - t0
        v = "✅" if e > 0 else "❌"
        print(f"  Rate: {r:5.2f}% | Baseline: {bl:5.2f}% | Edge: {e:+5.2f}% | "
              f"Hits: {h}/{t} | {v} ({elapsed:.1f}s)")
    except Exception as ex:
        print(f"  ERROR: {ex}")

    print(f"\n{'='*70}")
    print("  ⚠️ 以上數據請您獨立驗證。")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
