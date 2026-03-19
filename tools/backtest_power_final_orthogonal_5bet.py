
import os
import sys
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

MAX_NUM = 38

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
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0: continue
        period = 1 / freq_val
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return np.argsort(scores)[::-1]

def generate_orthogonal_5bet(history):
    # 1. Bets 1-3: Power Precision
    f_rank = get_fourier_rank(history)
    idx_1 = 0
    while idx_1 < len(f_rank) and f_rank[idx_1] == 0: idx_1 += 1
    bet1 = sorted(f_rank[idx_1:idx_1+6].tolist())
    bet2 = sorted(f_rank[idx_1+6:idx_1+12].tolist())
    
    exclude = set(bet1) | set(bet2)
    echo_nums = [n for n in history[-2]['numbers'] if n <= MAX_NUM and n not in exclude] if len(history) >= 2 else []
    
    recent = history[-100:]
    freq = Counter([n for d in recent for n in d['numbers']])
    rem_b3 = [n for n in range(1, 39) if n not in exclude and n not in echo_nums]
    rem_b3.sort(key=lambda x: freq.get(x, 0))
    bet3 = sorted((echo_nums + rem_b3)[:6])
    
    # 2. Bets 4-5: Orthogonal Frequency Ranked
    used = set(bet1) | set(bet2) | set(bet3)
    leftover = [n for n in range(1, 39) if n not in used]
    # Rank by frequency in last 100 draws (Highest frequency first)
    leftover.sort(key=lambda x: freq.get(x, 0), reverse=True)
    
    bet4 = sorted(leftover[:6])
    bet5 = sorted(leftover[6:12])
    
    return [bet1, bet2, bet3, bet4, bet5]

def run_backtest_final(periods_list=[150, 500, 1500]):
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    print("=" * 70)
    print("📊 FINAL ORTHOGONAL 5-BET BACKTEST (MAIN NUMBERS ONLY)")
    print("=" * 70)
    
    baseline = 18.20 # Using User's verified baseline
    
    for periods in periods_list:
        hits = 0
        total = 0
        
        for i in range(len(all_draws) - periods, len(all_draws)):
            history = all_draws[:i]
            if len(history) < 500: continue
            
            target = all_draws[i]
            actual = set(target['numbers'])
            bets = generate_orthogonal_5bet(history)
            
            win = False
            for b in bets:
                if len(set(b) & actual) >= 3:
                    win = True
                    break
            if win: hits += 1
            total += 1
            
        rate = (hits / total) * 100 if total > 0 else 0
        edge = rate - baseline
        print(f"[{periods:4d}期] M3+ 勝率: {rate:5.2f}% | 基準: {baseline:5.2f}% | Edge: {edge:+5.2f}%")

if __name__ == "__main__":
    run_backtest_final()
