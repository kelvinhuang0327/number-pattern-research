
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

def generate_stratified_5bet(history):
    # Core PP3
    f_rank = get_fourier_rank(history)
    idx = 0
    while idx < len(f_rank) and f_rank[idx] == 0: idx += 1
    bet1 = sorted(f_rank[idx:idx+6].tolist())
    bet2 = sorted(f_rank[idx+6:idx+12].tolist())
    
    exclude = set(bet1) | set(bet2)
    
    # Echo numbers
    echo_nums = []
    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'] if n <= 38 and n not in exclude]
    
    recent = history[-100:]
    freq = Counter([n for d in recent for n in d['numbers']])
    cold_ranks = [n for n in range(1, 39) if n not in exclude and n not in echo_nums]
    cold_ranks.sort(key=lambda x: freq.get(x, 0))
    
    bet3 = sorted((echo_nums + cold_ranks)[:6])
    exclude |= set(bet3)
    
    # Additional 2 Stratified Bets
    remaining = [n for n in range(1, 39) if n not in exclude]
    # Sort remaining by "Medium Frequency" (Gray Zone)
    remaining.sort(key=lambda x: abs(freq.get(x, (100*6/38)) - (100*6/38)))
    
    bet4 = sorted(remaining[:6])
    exclude |= set(bet4)
    
    remaining_final = [n for n in range(1, 39) if n not in exclude]
    # Rest are purely random or next coldest
    bet5 = sorted(remaining_final[:6]) if len(remaining_final) >= 6 else sorted(range(1, 7))
    
    return [bet1, bet2, bet3, bet4, bet5]

def run_backtest():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    draws_2025 = [d for d in all_draws if '2025' in str(d.get('date', ''))]
    hits = 0
    total = 0
    
    print(f"Running Stratified 5-Bet Backtest (Total Coverage: 30/38)...")
    
    for target in draws_2025:
        idx = -1
        for i, d in enumerate(all_draws):
            if d['draw'] == target['draw']:
                idx = i
                break
        if idx <= 500: continue
        
        history = all_draws[:idx]
        actual = set(target['numbers'])
        bets = generate_stratified_5bet(history)
        
        win = False
        for b in bets:
            if len(set(b) & actual) >= 3:
                win = True
                break
        if win: hits += 1
        total += 1
        
    rate = (hits / total) * 100 if total > 0 else 0
    baseline = 17.91
    print(f"Results: {hits}/{total} ({rate:.2f}%) | Baseline: {baseline:.2f}% | Edge: {rate-baseline:+.2f}%")

if __name__ == "__main__":
    run_backtest()
