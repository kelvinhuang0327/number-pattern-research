import os
import sys
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
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

def generate_power_precision_3bet(history):
    f_rank = get_fourier_rank(history)
    idx_1 = 0
    while idx_1 < len(f_rank) and f_rank[idx_1] == 0: idx_1 += 1
    bet1 = sorted(f_rank[idx_1:idx_1+6].tolist())

    idx_2 = idx_1 + 6
    while idx_2 < len(f_rank) and f_rank[idx_2] == 0: idx_2 += 1
    bet2 = sorted(f_rank[idx_2:idx_2+6].tolist())

    exclude = set(bet1) | set(bet2)

    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'] if n <= 38 and n not in exclude]
    else:
        echo_nums = []

    recent = history[-100:]
    freq = Counter([n for d in recent for n in d['numbers']])
    remaining = [n for n in range(1, 39) if n not in exclude and n not in echo_nums]
    remaining.sort(key=lambda x: freq.get(x, 0))
    bet3 = sorted((echo_nums + remaining)[:6])
    return [bet1, bet2, bet3]

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    # History is everything in the DB (up to 115000012)
    history = all_draws
    
    # We know the winning numbers for 115000013
    target_draw_id = "115000013"
    actual_numbers = [6, 10, 22, 25, 32, 35]
    actual_special = 3

    print(f"Prediction Target: {target_draw_id}")
    print(f"History ends at: {history[-1]['draw']} ({history[-1]['date']})")
    print(f"Actual Winning Numbers for {target_draw_id}: {actual_numbers}")
    print(f"Actual Special Number for {target_draw_id}: {actual_special}")
    print("-" * 40)
    
    bets = generate_power_precision_3bet(history)
    
    winning_set = set(actual_numbers)
    for i, bet in enumerate(bets):
        matches = sorted(list(set(bet) & winning_set))
        label = ["Fourier 注1", "Fourier 注2", "Echo/Cold"][i]
        print(f"BET {i+1} ({label}): {bet} | Matches: {len(matches)} ({matches})")

if __name__ == "__main__":
    main()
