
import os
import sys
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

MAX_NUM = 49

def fourier_rhythm_bet(history, window=500):
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
        pos_xf, pos_yf = xf[idx_pos], np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0: continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
    sorted_idx = np.argsort(scores[1:])[::-1] + 1
    return sorted(sorted_idx[:6].tolist())

def cold_numbers_bet(history, window=100, exclude=None):
    if exclude is None: exclude = set()
    recent = history[-window:]
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    candidates = [n for n in range(1, 50) if n not in exclude]
    sorted_cold = sorted(candidates, key=lambda x: freq.get(x, 0))
    return sorted(sorted_cold[:6])

def tail_balance_bet(history, window=100, exclude=None):
    if exclude is None: exclude = set()
    recent = history[-window:]
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    tail_groups = {i: [] for i in range(10)}
    for n in range(1, 50):
        if n not in exclude:
            tail_groups[n % 10].append((n, freq.get(n, 0)))
    for t in tail_groups: tail_groups[t].sort(key=lambda x: x[1], reverse=True)
    selected = []
    available_tails = sorted([t for t in range(10) if tail_groups[t]], key=lambda t: tail_groups[t][0][1], reverse=True)
    idx_in_group = {t: 0 for t in range(10)}
    while len(selected) < 6:
        for tail in available_tails:
            if len(selected) >= 6: break
            if idx_in_group[tail] < len(tail_groups[tail]):
                num = tail_groups[tail][idx_in_group[tail]][0]
                if num not in selected:
                    selected.append(num)
                    idx_in_group[tail] += 1
        if all(idx_in_group[t] >= len(tail_groups[t]) for t in available_tails): break
    return sorted(selected[:6])

def run_backtest(periods_list=[150, 500, 1500]):
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    print("=" * 80)
    print("📊 ORIGINAL BIG LOTTO TRIPLE STRIKE BACKTEST")
    print("=" * 80)
    
    baseline = 5.49
    
    for periods in periods_list:
        hits = 0
        total = 0
        test_draws = all_draws[-periods:]
        for i in range(len(all_draws) - len(test_draws), len(all_draws)):
            if i < 500: continue
            history = all_draws[:i]
            target = all_draws[i]
            actual = set(target['numbers'])
            
            b1 = fourier_rhythm_bet(history)
            b2 = cold_numbers_bet(history, exclude=set(b1))
            b3 = tail_balance_bet(history, exclude=set(b1)|set(b2))
            
            win = False
            for b in [b1, b2, b3]:
                if len(set(b) & actual) >= 3:
                    win = True
                    break
            if win: hits += 1
            total += 1
            
        rate = (hits / total) * 100 if total > 0 else 0
        edge = rate - baseline
        print(f"[{periods:4d}期] 勝率: {rate:5.2f}% | 基準: {baseline:5.2f}% | Edge: {edge:+5.2f}%")

if __name__ == "__main__":
    run_backtest()
