
import os
import sys
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

def get_fourier_rank(history, window=500):
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    max_num = 38
    bitstreams = {i: np.zeros(w) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= max_num: bitstreams[n][idx] = 1
    scores = np.zeros(max_num + 1)
    for n in range(1, max_num + 1):
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

def generate_orthogonal_5bet():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    history = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    # 1. Bets 1-3 (PP3 Core)
    f_rank = get_fourier_rank(history)
    idx_1 = 0
    while idx_1 < len(f_rank) and f_rank[idx_1] == 0: idx_1 += 1
    bet1 = sorted(f_rank[idx_1:idx_1+6].tolist())
    
    idx_2 = idx_1 + 6
    while idx_2 < len(f_rank) and f_rank[idx_2] == 0: idx_2 += 1
    bet2 = sorted(f_rank[idx_2:idx_2+6].tolist())
    
    exclude_for_bet3 = set(bet1) | set(bet2)
    
    # PP3 Bet 3: Echo + Cold
    echo_nums = []
    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'] if n <= 38 and n not in exclude_for_bet3]
    
    recent = history[-100:]
    freq_counter = Counter([n for d in recent for n in d['numbers']])
    remaining_for_cold = [n for n in range(1, 39) if n not in exclude_for_bet3 and n not in echo_nums]
    remaining_for_cold.sort(key=lambda x: freq_counter.get(x, 0))
    
    bet3 = sorted((echo_nums + remaining_for_cold)[:6])
    
    # 2. Bets 4-5 (Orthogonal Frequency Ranked)
    used_numbers = set(bet1) | set(bet2) | set(bet3)
    remaining_20 = [n for n in range(1, 39) if n not in used_numbers]
    
    # Rank by frequency in last 100 draws (Highest frequency first)
    remaining_20.sort(key=lambda x: freq_counter.get(x, 0), reverse=True)
    
    bet4 = sorted(remaining_20[:6])
    bet5 = sorted(remaining_20[6:12])
    
    return [bet1, bet2, bet3, bet4, bet5], used_numbers, remaining_20[:12]

if __name__ == "__main__":
    bets, used, added = generate_orthogonal_5bet()
    print("DRAW_ID: 115000013")
    for i, b in enumerate(bets, 1):
        print(f"BET_{i}: {b}")
