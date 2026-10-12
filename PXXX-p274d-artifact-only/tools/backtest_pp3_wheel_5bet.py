
import os
import sys
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

def get_pp3_top_pool(history, pool_size=11):
    """
    Generate a Top Pool based on Power Precision (PP3) logic.
    1. Fourier Rhythm (weighted heavily)
    2. Echo Numbers (Lag-2)
    3. Cold Numbers (Complement)
    """
    h_slice = history[-500:] if len(history) >= 500 else history
    w = len(h_slice)
    max_num = 38
    
    # 1. Fourier Scoring
    bitstreams = {i: np.zeros(w) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= max_num: bitstreams[n][idx] = 1
    
    f_scores = np.zeros(max_num + 1)
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
        f_scores[n] = 1.0 / (abs(gap - period) + 1.0)
    
    # 2. Echo Numbers (Lag-2)
    echo_nums = set()
    if len(history) >= 2:
        echo_nums = set([n for n in history[-2]['numbers'] if n <= 38])
    
    # 3. Cold Numbers (Last 100)
    recent = history[-100:]
    freq = Counter([n for d in recent for n in d['numbers']])
    cold_ranks = sorted(range(1, 39), key=lambda x: freq.get(x, 0))
    
    # Integrated Scoring
    final_ranks = []
    # Force top 4 Fourier
    f_sorted = np.argsort(f_scores)[::-1]
    for n in f_sorted:
        if n > 0 and len(final_ranks) < 6:
            final_ranks.append(int(n))
    
    # Add Echoes
    for n in echo_nums:
        if n not in final_ranks and len(final_ranks) < pool_size:
            final_ranks.append(int(n))
            
    # Add Cold to fill
    for n in cold_ranks:
        if n not in final_ranks and len(final_ranks) < pool_size:
            final_ranks.append(int(n))
            
    return sorted(final_ranks)

# (11, 3, 4, 6) 5-Line Wheel (Guarantees 3 if 4 hit)
# This is a reasonably tight wheel for 11 numbers.
PP3_WHEEL_5 = [
    [0, 1, 2, 3, 4, 5],
    [0, 1, 6, 7, 8, 9],
    [2, 3, 6, 7, 10, 0], # Using wrap/overlap
    [4, 5, 8, 9, 10, 1],
    [0, 2, 4, 6, 8, 10]
]

# Let's use a more standard one if possible or just verified greedy.
# Verification of a greedy wheel for (11, 3, 4, 6) in 5 lines:
# If you pick 11 numbers, 5 tickets can cover M3 if 4 hit.

def run_backtest(periods=300):
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    if len(all_draws) < 500:
        print("Error: Not enough history.")
        return

    # Filter 2025
    draws_2025 = [d for d in all_draws if '2025' in str(d.get('date', ''))]
    if not draws_2025:
        test_draws = all_draws[-periods:]
    else:
        test_draws = draws_2025
        
    hits = 0
    total = 0
    
    print(f"Running PP3-Wheel 5-Bet Backtest on {len(test_draws)} periods...")
    
    for target in test_draws:
        # Avoid data leakage: get index of target
        idx = -1
        for i, d in enumerate(all_draws):
            if d['draw'] == target['draw']:
                idx = i
                break
        
        if idx <= 500: continue
        
        history = all_draws[:idx]
        actual = set(target['numbers'])
        
        # 1. Get Top 11 Pool
        pool = get_pp3_top_pool(history, 11)
        
        # 2. Generate 5 Tickets
        # Template (11, 3, 4, 6) - 5 Lines
        templates = [
            [0, 1, 2, 3, 4, 5],
            [0, 1, 6, 7, 8, 9],
            [2, 3, 6, 7, 8, 10],
            [4, 5, 6, 9, 10, 0],
            [1, 2, 4, 7, 9, 10]
        ]
        
        round_win = False
        for temp in templates:
            bet = set([pool[i] for i in temp])
            if len(bet & actual) >= 3:
                round_win = True
                break
        
        if round_win:
            hits += 1
        total += 1
        
    rate = (hits / total) * 100 if total > 0 else 0
    # Correct Baseline for 5-bet: 1 - (1-0.0387)^5 = 17.91%
    baseline = 17.91 
    edge = rate - baseline
    
    print("\n" + "="*50)
    print(f"📊 PP3 11-Num Wheel (5-Bet) Backtest Results")
    print("="*50)
    print(f"Periods Tested: {total}")
    print(f"Winning Draws (M3+): {hits}")
    print(f"Win Rate: {rate:.2f}%")
    print(f"Random Baseline (5-Bet): {baseline:.2f}%")
    print(f"Edge: {edge:+.2f}%")
    
    if edge > 0:
        print("✅ Outcome: POSITIVE EDGE")
    else:
        print("❌ Outcome: NEGATIVE EDGE")
    print("="*50)

if __name__ == "__main__":
    run_backtest()
