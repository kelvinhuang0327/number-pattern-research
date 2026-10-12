#!/usr/bin/env python3
"""
獨立驗證：Markov 2注 vs Triple Strike 2注 (僅 M3+ 主號)
========================================================
使用 CLAUDE.md 記錄的原版實作，排除特別號干擾
只看主號命中 3 號以上 (M3+)

2026-01-30 Independent Verification
"""
import os
import sys
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

np.random.seed(42)

# 大樂透基準
BASELINE_1BET = 1.86  # 1注 M3+
BASELINE_2BET = 3.69  # 2注 M3+ = 1 - (1 - 0.0186)^2

# ========== 原版 Markov (from strategy_leaderboard.py) ==========

def markov_2bet(history, window=100):
    """原版 Markov 實作 (2注)"""
    recent = history[-window:]
    transitions = Counter()
    for i in range(len(recent)-1):
        curr_set = set(recent[i]['numbers'])
        next_set = recent[i+1]['numbers']
        for n in next_set:
            for c in curr_set:
                transitions[(c, n)] += 1

    last_draw = history[-1]['numbers']
    next_scores = Counter()
    for c in last_draw:
        for n in range(1, 50):
            next_scores[n] += transitions.get((c, n), 0)

    sorted_nums = sorted(range(1, 50), key=lambda x: next_scores[x], reverse=True)
    bet1 = sorted_nums[0:6]
    bet2 = sorted_nums[6:12]
    return [bet1, bet2]


# ========== Triple Strike 2注 (Fourier + Cold) ==========

def fourier_bet_biglotto(history, window=500):
    """Fourier Rhythm for Big Lotto"""
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    max_num = 49

    bitstreams = {i: np.zeros(w) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= max_num:
                bitstreams[n][idx] = 1

    scores = np.zeros(max_num + 1)
    for n in range(1, max_num + 1):
        bh = bitstreams[n]
        if sum(bh) < 2:
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        if len(idx_pos[0]) == 0:
            continue
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            dist_to_peak = abs(gap - period)
            scores[n] = 1.0 / (dist_to_peak + 1.0)

    all_idx = np.arange(1, max_num + 1)
    sorted_idx = all_idx[np.argsort(scores[1:])[::-1]]
    return sorted(sorted_idx[:6].tolist())


def cold_bet_biglotto(history, window=100, exclude=None):
    """Cold Numbers for Big Lotto"""
    if exclude is None:
        exclude = set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    candidates = [n for n in range(1, 50) if n not in exclude]
    sorted_cold = sorted(candidates, key=lambda x: freq.get(x, 0))
    return sorted(sorted_cold[:6])


def triple_strike_2bet(history):
    """Triple Strike 2注 (Fourier + Cold)"""
    bet1 = fourier_bet_biglotto(history, window=500)
    exclude1 = set(bet1)
    bet2 = cold_bet_biglotto(history, window=100, exclude=exclude1)
    return [bet1, bet2]


# ========== 回測框架 ==========

def run_backtest(strategy_func, draws, test_periods, strategy_name):
    """滾動式回測 (只看 M3+)"""
    m3_wins = 0

    for i in range(test_periods):
        target_idx = len(draws) - test_periods + i
        if target_idx <= 500:
            continue

        target_draw = draws[target_idx]
        hist = draws[:target_idx]
        actual = set(target_draw['numbers'])

        try:
            bets = strategy_func(hist)
            hits = [len(set(bet) & actual) for bet in bets]
            if max(hits) >= 3:
                m3_wins += 1
        except:
            pass

    valid_periods = min(test_periods, len(draws) - 501)
    m3_rate = m3_wins / valid_periods * 100
    edge = m3_rate - BASELINE_2BET

    return {
        'name': strategy_name,
        'periods': valid_periods,
        'm3_wins': m3_wins,
        'm3_rate': m3_rate,
        'edge': edge
    }


def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))

    print("=" * 80)
    print("  獨立驗證：Markov 2注 vs Triple Strike 2注 (僅 M3+ 主號)")
    print("=" * 80)
    print(f"  資料庫: lottery_v2.db")
    print(f"  總期數: {len(draws)}")
    print(f"  2注隨機基準 (M3+): {BASELINE_2BET:.2f}%")
    print(f"  Seed: 42")
    print("=" * 80)
    print()

    test_configs = [
        (150, "短期"),
        (500, "中期"),
        (1000, "長期"),
    ]

    print(f"{'測試週期':<12} {'策略':<20} {'M3+ 率':<12} {'Edge':<12} {'驗證'}")
    print("-" * 80)

    for periods, label in test_configs:
        # Markov
        markov_res = run_backtest(markov_2bet, draws, periods, f"Markov 2注")
        print(f"{label} ({periods}期){'':<3} {'Markov 2注':<20} {markov_res['m3_rate']:.2f}%{'':<6} {markov_res['edge']:+.2f}%{'':<6} {'✅' if markov_res['edge'] > 0 else '❌'}")

        # Triple Strike
        ts_res = run_backtest(triple_strike_2bet, draws, periods, f"Triple Strike 2注")
        print(f"{'':<15} {'Triple Strike 2注':<20} {ts_res['m3_rate']:.2f}%{'':<6} {ts_res['edge']:+.2f}%{'':<6} {'✅' if ts_res['edge'] > 0 else '❌'}")
        print()

    print("=" * 80)
    print("  驗證說明")
    print("=" * 80)
    print("  1. 使用 CLAUDE.md 記錄的原版 Markov 實作 (strategy_leaderboard.py)")
    print("  2. 只計算主號命中 3 號以上 (M3+)，排除特別號")
    print("  3. 滾動式回測，不使用未來數據")
    print("  4. Seed=42 確保可復現")
    print("=" * 80)


if __name__ == '__main__':
    main()
