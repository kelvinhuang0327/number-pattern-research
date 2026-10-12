
import os
import sys
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

# Set paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))

from lottery_api.database import DatabaseManager

MAX_NUM = 49 # Big Lotto
PICK = 6

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

def generate_big_lotto_orthogonal_5bet(history):
    # 1. Bets 1-3: Power Precision Logic (Applied to Big Lotto)
    f_rank = get_fourier_rank(history)
    idx_1 = 0
    while idx_1 < len(f_rank) and f_rank[idx_1] == 0: idx_1 += 1
    bet1 = sorted(f_rank[idx_1:idx_1+6].tolist())
    
    idx_2 = idx_1 + 6
    while idx_2 < len(f_rank) and f_rank[idx_2] == 0: idx_2 += 1
    bet2 = sorted(f_rank[idx_2:idx_2+6].tolist())
    
    exclude = set(bet1) | set(bet2)
    # Echo numbers (Lag-2)
    echo_nums = [n for n in history[-2]['numbers'] if n <= MAX_NUM and n not in exclude] if len(history) >= 2 else []
    
    recent = history[-100:]
    freq = Counter([n for d in recent for n in d['numbers']])
    rem_b3 = [n for n in range(1, MAX_NUM + 1) if n not in exclude and n not in echo_nums]
    rem_b3.sort(key=lambda x: freq.get(x, 0)) # Coldest first
    bet3 = sorted((echo_nums + rem_b3)[:6])
    
    # 2. Bets 4-5: Orthogonal Frequency Ranked
    used = set(bet1) | set(bet2) | set(bet3)
    leftover = [n for n in range(1, MAX_NUM + 1) if n not in used]
    leftover.sort(key=lambda x: freq.get(x, 0), reverse=True) # Highest frequency first
    
    bet4 = sorted(leftover[:6])
    bet5 = sorted(leftover[6:12])
    
    return [bet1, bet2, bet3, bet4, bet5]

def run_backtest(periods_list=[150, 500, 1500]):
    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    print("=" * 70)
    print("📊 BIG LOTTO ORTHOGONAL 5-BET BACKTEST")
    print("=" * 70)
    
    # Big Lotto M3+ baseline for 1 bet is approx 1/54.7 = 1.828%
    p1 = 1 / 54.7
    baseline = (1 - (1 - p1)**5) * 100
    
    for periods in periods_list:
        test_draws = all_draws[-periods:]
        hits = 0
        total = 0
        
        for i in range(len(all_draws) - len(test_draws), len(all_draws)):
            if i < 500: continue
            history = all_draws[:i]
            target = all_draws[i]
            actual = set(target['numbers'])
            bets = generate_big_lotto_orthogonal_5bet(history)
            
            win = False
            for b in bets:
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
