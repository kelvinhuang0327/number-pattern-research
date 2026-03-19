
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

def strategy_cycle_momentum(history, window=500):
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
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    top12 = np.argsort(scores)[::-1][:12]
    bet = sorted(top12[:6].tolist())
    return [int(n) for n in bet]

def strategy_structural_defense(history, exclude=None):
    exclude = exclude or set()
    recent = history[-100:]
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    tails = Counter(n % 10 for n in all_nums)
    top_tail = tails.most_common(1)[0][0]
    candidates = []
    hot_seeds = sorted([n for n in range(1, 49) if n not in exclude], key=lambda x: freq.get(x, 0), reverse=True)
    seeds = [n for n in hot_seeds if n <= 48]
    if seeds:
        n = seeds[0]
        candidates.extend([n, n+1])
    tail_candidates = [n for n in range(1, 49) if n % 10 == top_tail and n not in exclude and n not in candidates]
    candidates.extend(tail_candidates[:2])
    rem = [n for n in range(1, 50) if n not in exclude and n not in candidates]
    rem.sort(key=lambda x: freq.get(x, 0), reverse=True)
    candidates.extend(rem[:6-len(candidates)])
    return sorted([int(n) for n in candidates[:6]])

def strategy_extreme_compensation(history, exclude=None):
    exclude = exclude or set()
    gaps = {n: 0 for n in range(1, 50)}
    for n in range(1, 50):
        for i, d in enumerate(history[::-1]):
            if n in d['numbers']:
                gaps[n] = i
                break
            gaps[n] = len(history)
    rem = [n for n in range(1, 50) if n not in exclude]
    rem.sort(key=lambda x: gaps[x], reverse=True)
    return sorted([int(n) for n in rem[:6]])

def run_backtest(periods_list=[150, 500, 1500]):
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    print("=" * 80)
    print("📊 BIG LOTTO TRIPLE STRIKE V2 (THREE-BODY) BACKTEST")
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
            
            b1 = strategy_cycle_momentum(history)
            b2 = strategy_structural_defense(history, exclude=set(b1))
            b3 = strategy_extreme_compensation(history, exclude=set(b1)|set(b2))
            
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
