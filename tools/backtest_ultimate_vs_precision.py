#!/usr/bin/env python3
"""
正式對比回測: Power Ultimate vs Power Precision (3注)
====================================================
三窗口驗證 (150/500/1500期), seed=42
無數據洩漏: history = draws[:idx]
"""
import os, sys
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

MAX_NUM = 38
PICK = 6
N_BETS = 3
BASELINE_3BET = 1 - (1 - 1/((38*37*36*35*34*33)/(6*5*4*3*2*1) / (6*5*4*3*2*1 / (3*2*1 * 3*2*1))))**3

# --- Fourier Rank (shared) ---
def get_fourier_rank(history, window=500):
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    bitstreams = {i: np.zeros(w) for i in range(1, MAX_NUM + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= MAX_NUM: bitstreams[n][idx] = 1
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bh = bitstreams[n]
        if sum(bh) < 2: continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_yf = np.abs(yf[idx_pos])
        pos_xf = xf[idx_pos]
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0: continue
        period = 1 / freq_val
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return np.argsort(scores)[::-1]

# --- Power Precision 3-Bet ---
def precision_predict(history):
    f_rank = get_fourier_rank(history)
    idx_1 = 0
    while idx_1 < len(f_rank) and f_rank[idx_1] == 0: idx_1 += 1
    bet1 = sorted(f_rank[idx_1:idx_1+6].tolist())
    idx_2 = idx_1 + 6
    while idx_2 < len(f_rank) and f_rank[idx_2] == 0: idx_2 += 1
    bet2 = sorted(f_rank[idx_2:idx_2+6].tolist())
    exclude = set(bet1) | set(bet2)

    echo_nums = []
    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'] if n <= MAX_NUM and n not in exclude]
    recent = history[-100:]
    freq = Counter([n for d in recent for n in d['numbers']])
    remaining = [n for n in range(1, MAX_NUM+1) if n not in exclude and n not in echo_nums]
    remaining.sort(key=lambda x: freq.get(x, 0))
    bet3 = sorted((echo_nums + remaining)[:6])
    return [bet1, bet2, bet3]

# --- Power Ultimate 3-Bet ---
def ultimate_predict(history):
    # Kill list
    recent_200 = history[-200:]
    last_seen = {n: -1 for n in range(1, MAX_NUM + 1)}
    gaps_db = {n: [] for n in range(1, MAX_NUM + 1)}
    for i, d in enumerate(recent_200):
        for n in d['numbers']:
            if n <= MAX_NUM:
                if last_seen[n] != -1: gaps_db[n].append(i - last_seen[n])
                last_seen[n] = i
    curr_idx = len(recent_200)
    kill_list = set()
    for n in range(1, MAX_NUM + 1):
        avg_g = np.mean(gaps_db[n]) if gaps_db[n] else 6.3
        curr_g = curr_idx - last_seen[n] if last_seen[n] != -1 else 0
        if 0.9 <= (curr_g / (avg_g + 0.01)) <= 1.1: kill_list.add(n)

    f_rank = [int(n) for n in get_fourier_rank(history) if n > 0]
    f_filtered = [n for n in f_rank if n not in kill_list]

    # Bet 1: Fourier
    bet1_pool = f_filtered if len(f_filtered) >= 6 else f_rank
    bet1 = sorted(bet1_pool[:6])
    exclude = set(bet1)

    # Bet 2: Lag-3 + Lag-15
    echo_pool = []
    if len(history) >= 15:
        l3 = set(history[-3]['numbers'])
        l15 = set(history[-15]['numbers'])
        echo_pool = [n for n in (l3 | l15) if n <= MAX_NUM and n not in kill_list]
        if not echo_pool:
            echo_pool = [n for n in (l3 | l15) if n <= MAX_NUM]
    bet2_nums = [n for n in echo_pool if n not in exclude]
    if len(bet2_nums) < 6:
        rem = [n for n in f_rank if n not in exclude and n not in bet2_nums]
        bet2_nums.extend(rem[:6-len(bet2_nums)])
    bet2 = sorted(bet2_nums[:6])
    exclude |= set(bet2)

    # Bet 3: L-Zone
    l_zone_nums = [n for n in range(1, 13) if n not in exclude and n not in kill_list]
    if len(l_zone_nums) < 6:
        l_zone_nums = [n for n in range(1, 13) if n not in exclude]
    if len(l_zone_nums) < 6:
        recent_100 = history[-100:]
        freq_100 = Counter([n for d in recent_100 for n in d['numbers']])
        rem_all = [n for n in range(1, 39) if n not in exclude and n not in l_zone_nums]
        rem_all.sort(key=lambda x: freq_100.get(x, 0))
        l_zone_nums.extend(rem_all[:6-len(l_zone_nums)])
    bet3 = sorted(l_zone_nums[:6])
    return [bet1, bet2, bet3]

# --- Random baseline (seed-controlled) ---
def random_predict(seed_val, draw_idx):
    rng = np.random.RandomState(seed_val * 100000 + draw_idx)
    bets = []
    used = set()
    for _ in range(N_BETS):
        pool = [n for n in range(1, MAX_NUM + 1) if n not in used]
        chosen = sorted(rng.choice(pool, PICK, replace=False).tolist())
        used.update(chosen)
        bets.append(chosen)
    return bets

def count_matches(bet, actual):
    return len(set(bet) & set(actual))

def run_backtest(draws, strategy_fn, label, windows=[150, 500, 1500]):
    total = len(draws)
    min_history = 500  # Need at least 500 for Fourier window

    results = {}
    for window in windows:
        start_idx = max(min_history, total - window)
        end_idx = total
        n_tests = end_idx - start_idx

        m3_strategy = 0
        m3_random_seeds = {s: 0 for s in range(10)}

        for idx in range(start_idx, end_idx):
            history = draws[:idx]
            actual = set(draws[idx]['numbers'])

            # Strategy prediction
            try:
                bets = strategy_fn(history)
            except:
                continue

            # Check M3+ for strategy
            hit = False
            for bet in bets:
                if count_matches(bet, actual) >= 3:
                    hit = True
                    break
            if hit:
                m3_strategy += 1

            # Random baselines (10 seeds)
            for seed in range(10):
                r_bets = random_predict(seed, idx)
                r_hit = False
                for bet in r_bets:
                    if count_matches(bet, actual) >= 3:
                        r_hit = True
                        break
                if r_hit:
                    m3_random_seeds[seed] += 1

        avg_random = np.mean(list(m3_random_seeds.values()))
        rate_strategy = m3_strategy / n_tests * 100
        rate_random = avg_random / n_tests * 100
        edge = rate_strategy - rate_random

        results[window] = {
            'n_tests': n_tests,
            'm3_strategy': m3_strategy,
            'avg_random': avg_random,
            'rate_strategy': rate_strategy,
            'rate_random': rate_random,
            'edge': edge,
        }

        print(f"  {label} | {window}期: M3+={m3_strategy}/{n_tests} "
              f"({rate_strategy:.2f}%) vs Random {avg_random:.1f} ({rate_random:.2f}%) "
              f"| Edge={edge:+.2f}%")

    return results

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    print(f"\n  威力彩資料: {len(draws)} 期")
    print(f"  回測基準: 3注隨機 M3+ = 11.17%")
    print(f"  Random seeds: 0-9 (10種子平均)")

    print("\n" + "=" * 80)
    print("  Power Precision (F2 + Echo/Cold) — 我方已驗證")
    print("=" * 80)
    r_precision = run_backtest(draws, precision_predict, "Precision")

    print("\n" + "=" * 80)
    print("  Power Ultimate (Fourier + Lag3/15 + L-Zone) — Gemini 推薦")
    print("=" * 80)
    r_ultimate = run_backtest(draws, ultimate_predict, "Ultimate")

    # --- Head-to-Head ---
    print("\n" + "=" * 80)
    print("  正面對決: Precision vs Ultimate")
    print("=" * 80)
    print(f"  {'窗口':>6} | {'Precision Edge':>15} | {'Ultimate Edge':>15} | {'差距':>10} | 勝者")
    print("-" * 80)
    for w in [150, 500, 1500]:
        pe = r_precision[w]['edge']
        ue = r_ultimate[w]['edge']
        diff = pe - ue
        winner = "Precision ★" if diff > 0 else ("Ultimate" if diff < 0 else "TIE")
        print(f"  {w:>5}期 | {pe:>+13.2f}% | {ue:>+13.2f}% | {diff:>+8.2f}% | {winner}")

    # Stability classification
    print("\n  穩定性分類:")
    for label, results in [("Precision", r_precision), ("Ultimate", r_ultimate)]:
        edges = [results[w]['edge'] for w in [150, 500, 1500]]
        all_positive = all(e > 0 for e in edges)
        decay = edges[0] - edges[2]
        if all_positive and abs(decay) < 2:
            stability = "STABLE ★"
        elif all_positive:
            stability = "MODERATE_DECAY"
        elif edges[2] > 0 and edges[0] < 0:
            stability = "LATE_BLOOMER"
        elif edges[0] > 0 and edges[2] < 0:
            stability = "SHORT_MOMENTUM ✗"
        else:
            stability = "FAIL ✗"
        print(f"    {label}: {edges[0]:+.2f}% / {edges[1]:+.2f}% / {edges[2]:+.2f}% → {stability}")

    print("\n" + "=" * 80)
    print("  結論: 長期 Edge 較高且三窗口全正者為推薦策略")
    print("=" * 80 + "\n")

if __name__ == '__main__':
    main()
