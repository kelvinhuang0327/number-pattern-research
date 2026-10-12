#!/usr/bin/env python3
import json
import sqlite3
import os
import numpy as np
from scipy import stats
from collections import Counter

from pathlib import Path


def _p291u_repo_root():
    current = Path(__file__)
    if not current.is_absolute():
        raise FileNotFoundError(f"Source file path is not absolute: {current}")
    for parent in (current.parent, *current.parents):
        if (parent / "lottery_api").is_dir():
            return parent
    raise FileNotFoundError(f"Unable to locate repository root from source file: {current}")


def _p291u_default_db_path():
    db_path = _p291u_repo_root() / "lottery_api" / "data" / "lottery_v2.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Default lottery DB path is missing or non-regular: {db_path}")
    return db_path


def _p291u_resolve_db_path(db_path=None):
    if db_path is None:
        return _p291u_default_db_path()
    path = Path(db_path)
    if not path.is_absolute():
        raise ValueError(f"Explicit DB path must be absolute: {db_path}")
    if not path.is_file():
        raise FileNotFoundError(f"Explicit DB path is missing or non-regular: {path}")
    return path


def _p291u_connect_resolved(db_path):
    return sqlite3.connect(str(_p291u_resolve_db_path(db_path)))


DB_PATH = str(_p291u_resolve_db_path())

POOL = 39
PICK = 5
BASELINE_1BET_GE2 = 0.113973

def load_draws():
    conn = _p291u_connect_resolved(DB_PATH)
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

def train_rhythms(history):
    N = len(history)
    p_theoretical = PICK / POOL
    best_lags = {}
    for n in range(1, POOL + 1):
        lags_p = []
        for lag in range(1, 15):
            obs = 0
            total = 0
            for i in range(lag, N):
                if n in history[i-lag]['numbers']:
                    total += 1
                    if n in history[i]['numbers']:
                        obs += 1
            if total > 20:
                try:
                    p = stats.binomtest(obs, total, p_theoretical, alternative='greater').pvalue
                except AttributeError:
                    p = stats.binom_test(obs, total, p_theoretical, alternative='greater')
                lags_p.append((lag, p, obs/total if total > 0 else 0))
        
        if lags_p:
            lags_p.sort(key=lambda x: x[1])
            best_lags[n] = lags_p[0] # (lag, p, rate)
        else:
            best_lags[n] = (1, 1.0, 0.0)
    return best_lags

def main():
    draws = load_draws()
    # Split: first 4000 training, rest testing
    TRAIN_SIZE = 4000
    train_data = draws[:TRAIN_SIZE]
    test_data = draws[TRAIN_SIZE:]
    p_theoretical = PICK / POOL
    
    print(f"Training on {len(train_data)} draws, Testing on {len(test_data)} draws...")
    
    # Discovery phase
    best_lags = train_rhythms(train_data)
    
    # Backtest phase
    ge2_hits = 0
    total_test = len(test_data)
    
    for i in range(total_test):
        # We can update the rhythms periodically, but let's start with static ones discovered in train
        scores = {}
        for n in range(1, POOL + 1):
            lag, p, rate = best_lags[n]
            # Prediction: if the number appeared 'lag' steps ago, it gets a score
            # Score is based on the 'rate' or '1-p'
            
            # Context for current test draw i (absolute index TRAIN_SIZE + i)
            history_idx = TRAIN_SIZE + i
            if history_idx >= lag:
                if n in draws[history_idx - lag]['numbers']:
                    # Use the edge as the weight
                    scores[n] = rate - p_theoretical
                else:
                    scores[n] = 0.0
            else:
                scores[n] = 0.0
        
        # Rank numbers by score
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        prediction = set([x[0] for x in ranked[:PICK]])
        actual = set(test_data[i]['numbers'])
        
        if len(prediction & actual) >= 2:
            ge2_hits += 1
            
    rate = ge2_hits / total_test
    edge = rate - BASELINE_1BET_GE2
    
    print(f"Test Results:")
    print(f"  >=2 Rate: {rate*100:.4f}%")
    print(f"  Edge: {edge*100:+.4f}%")
    
    # Now try a "Frequentist" approach: just pick the 5 numbers with highest train rate
    print("\nBaseline: Top-5 Historical Freq (from train only)")
    train_freq = Counter()
    for d in train_data:
        for n in d['numbers']:
            train_freq[n] += 1
    top5_freq = [x[0] for x in train_freq.most_common(5)]
    
    ge2_hits_f = 0
    for d in test_data:
        if len(set(top5_freq) & set(d['numbers'])) >= 2:
            ge2_hits_f += 1
    rate_f = ge2_hits_f / total_test
    print(f"  >=2 Rate: {rate_f*100:.4f}%")
    print(f"  Edge: {rate_f - BASELINE_1BET_GE2:+.4f}")

if __name__ == "__main__":
    main()
