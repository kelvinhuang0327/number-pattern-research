#!/usr/bin/env python3
import json
import sqlite3
import os
import numpy as np
from scipy import stats
from collections import Counter
import random

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_api', 'data', 'lottery_v2.db')
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_v2.db')

POOL = 39
PICK = 5
BASELINE_1BET_GE2 = 0.113973

def load_draws():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = 'DAILY_539'
        ORDER BY date ASC, draw ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    draws = []
    for draw_id, date, numbers_str in rows:
        nums = json.loads(numbers_str)
        draws.append({'draw': draw_id, 'date': date, 'numbers': sorted(nums)})
    return draws

class RhythmStrategy:
    def __init__(self, history):
        self.history = history
        self.p_theoretical = PICK / POOL
        self.config = self._train(history)
        
    def _train(self, history):
        N = len(history)
        config = {}
        for n in range(1, POOL + 1):
            # 1. Best Lag
            best_lag = 1
            best_p = 1.0
            best_rate = 0.0
            for lag in range(1, 15):
                obs = 0
                total = 0
                for i in range(lag, N):
                    if n in history[i-lag]['numbers']:
                        total += 1
                        if n in history[i]['numbers']:
                            obs += 1
                if total > 50:
                    try:
                        p = stats.binomtest(obs, total, self.p_theoretical, alternative='greater').pvalue
                    except AttributeError:
                        p = stats.binom_test(obs, total, self.p_theoretical, alternative='greater')
                    if p < best_p:
                        best_p = p
                        best_lag = lag
                        best_rate = obs / total
            
            # 2. Fourier Phase prediction
            series = np.array([1 if n in d['numbers'] else 0 for d in history], dtype=float)
            fft_vals = np.fft.rfft(series - series.mean())
            power = np.abs(fft_vals) ** 2
            dom_idx = np.argmax(power[1:]) + 1 if len(power) > 1 else 1
            phase = np.angle(fft_vals[dom_idx])
            freq = dom_idx / len(series)
            
            config[n] = {
                'best_lag': best_lag,
                'lag_weight': max(0, best_rate - self.p_theoretical),
                'freq': freq,
                'phase': phase,
                'amp': np.abs(fft_vals[dom_idx]) / len(series)
            }
        return config

    def predict(self, current_history, history_len):
        scores = {}
        for n in range(1, POOL + 1):
            c = self.config[n]
            # Lag component
            lag_score = 0
            prev_idx = history_len - c['best_lag']
            if prev_idx >= 0:
                if n in current_history[prev_idx]['numbers']:
                    lag_score = c['lag_weight']
            
            # Fourier component
            f_score = c['amp'] * np.cos(2 * np.pi * c['freq'] * history_len + c['phase'])
            
            scores[n] = 0.7 * lag_score + 0.3 * f_score
            
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return [x[0] for x in ranked[:PICK]]

def run_test(draws, shuffle=False):
    if shuffle:
        # P3 Shuffle: preserve draw numbers but shuffle the sequence
        shuffled_draws = list(draws)
        random.shuffle(shuffled_draws)
        test_draws = shuffled_draws
    else:
        test_draws = draws

    # Split for walk-forward
    TRAIN_SIZE = 4000
    train_data = test_draws[:TRAIN_SIZE]
    test_data = test_draws[TRAIN_SIZE:]
    
    strat = RhythmStrategy(train_data)
    
    ge2_hits = 0
    for i in range(len(test_data)):
        pred = strat.predict(test_draws, TRAIN_SIZE + i)
        actual = test_data[i]['numbers']
        if len(set(pred) & set(actual)) >= 2:
            ge2_hits += 1
            
    return ge2_hits / len(test_data)

def main():
    draws = load_draws()
    real_rate = run_test(draws, shuffle=False)
    real_edge = real_rate - BASELINE_1BET_GE2
    print(f"Real Edge: {real_edge*100:+.4f}%")
    
    print("Running P3 Shuffle Test (20 iterations)...")
    shuffle_edges = []
    for i in range(20):
        rate = run_test(draws, shuffle=True)
        shuffle_edges.append(rate - BASELINE_1BET_GE2)
        print(f"  Shuffle {i+1}: {shuffle_edges[-1]*100:+.4f}%")
        
    p_val = np.mean([e >= real_edge for e in shuffle_edges])
    print(f"\nFinal P3 p-value: {p_val:.4f}")
    
    mean_shuff = np.mean(shuffle_edges)
    std_shuff = np.std(shuffle_edges)
    z_score = (real_edge - mean_shuff) / std_shuff if std_shuff > 0 else 0
    print(f"Cohen's d (approx): {z_score:.2f}")

if __name__ == "__main__":
    main()
