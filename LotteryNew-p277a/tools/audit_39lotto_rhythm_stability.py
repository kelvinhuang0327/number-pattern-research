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
            lag_score = 0
            prev_idx = history_len - c['best_lag']
            if prev_idx >= 0:
                if n in current_history[prev_idx]['numbers']:
                    lag_score = c['lag_weight']
            f_score = c['amp'] * np.cos(2 * np.pi * c['freq'] * history_len + c['phase'])
            scores[n] = 0.7 * lag_score + 0.3 * f_score
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return [x[0] for x in ranked[:PICK]]

def main():
    draws = load_draws()
    TRAIN_SIZE = 4000
    train_data = draws[:TRAIN_SIZE]
    test_data = draws[TRAIN_SIZE:]
    
    strat = RhythmStrategy(train_data)
    
    # Split test_data into 3 segments
    seg_size = len(test_data) // 3
    print(f"Stability Audit (3 segments of {seg_size} draws):")
    
    for s in range(3):
        start = s * seg_size
        end = (s + 1) * seg_size if s < 2 else len(test_data)
        segment = test_data[start:end]
        
        ge2_hits = 0
        for i in range(len(segment)):
            pred = strat.predict(draws, TRAIN_SIZE + start + i)
            actual = segment[i]['numbers']
            if len(set(pred) & set(actual)) >= 2:
                ge2_hits += 1
        
        rate = ge2_hits / len(segment)
        edge = rate - BASELINE_1BET_GE2
        print(f"  Segment {s+1}: Edge={edge*100:+.4f}% (Rate={rate*100:.2f}%)")

if __name__ == "__main__":
    main()
