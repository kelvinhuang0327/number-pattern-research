import sys
import os
import io
import argparse
from collections import Counter
import random

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def get_special_history(periods=500):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    # Get all, correct order (Old -> New) for training, but we need reversed for limitation
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    # We want the LAST `periods` draws for testing, but we need history BEFORE that.
    # So let's just get all available.
    return [d['special'] for d in all_draws if d.get('special')]

def strat_random(hist):
    return random.randint(1, 8)

def strat_hot(hist, window=50):
    # Most frequent in last window
    subset = hist[-window:]
    counts = Counter(subset)
    most_common = counts.most_common()
    if not most_common: return random.randint(1, 8)
    # Return number with highest count. Break ties randomly or by recent?
    # Let's simple return top 1
    return most_common[0][0]

def strat_cold(hist, window=100):
    # Least frequent or "Due" (Longest Gap)
    # Let's use Longest Gap (Gap Theory)
    last_seen = {}
    for idx, num in enumerate(hist):
        last_seen[num] = idx
    
    # Calculate gap for each number 1-8
    current_idx = len(hist)
    gaps = []
    for n in range(1, 9):
        last = last_seen.get(n, -1)
        gap = current_idx - last if last != -1 else 999
        gaps.append((n, gap))
    
    # Sort by gap descending (Coldest first)
    gaps.sort(key=lambda x: x[1], reverse=True)
    return gaps[0][0]

def strat_markov(hist, order=1):
    if len(hist) < order + 1: return random.randint(1, 8)
    
    current_state = tuple(hist[-order:])
    # Build transition map
    transitions = {}
    for i in range(len(hist) - order - 1):
        state = tuple(hist[i:i+order])
        next_val = hist[i+order]
        if state not in transitions: transitions[state] = []
        transitions[state].append(next_val)
        
    options = transitions.get(current_state)
    if not options: return strat_hot(hist) # Fallback
    
    # Return most frequent next state
    return Counter(options).most_common(1)[0][0]

def strat_repeater(hist):
    if not hist: return random.randint(1, 8)
    return hist[-1]

def analyze_and_test():
    full_history = get_special_history()
    total_samples = len(full_history)
    test_periods = 500
    
    print(f"Total History: {total_samples}")
    print(f"Testing Last: {test_periods} Periods")
    
    strategies = {
        'Random': strat_random,
        'Hot (50)': lambda h: strat_hot(h, 50),
        'Cold (Gap)': strat_cold,
        'Markov (O1)': lambda h: strat_markov(h, 1),
        'Repeater': strat_repeater
    }
    
    results = {name: 0 for name in strategies}
    
    for i in range(test_periods):
        # Index in full_history
        # predicting index `idx` using `0` to `idx-1`
        idx = total_samples - test_periods + i
        if idx < 50: continue # Skip early
        
        hist = full_history[:idx]
        actual = full_history[idx]
        
        for name, func in strategies.items():
            pred = func(hist)
            if pred == actual:
                results[name] += 1
                
    print("\nResults (Hit Rate):")
    print(f"Baseline (1/8): 12.50%")
    print("-" * 30)
    
    # Check biases in the test set itself
    test_set = full_history[-test_periods:]
    counts = Counter(test_set)
    print(f"Distribution in Test Set: {sorted(counts.items())}")
    
    for name, hits in sorted(results.items(), key=lambda x: x[1], reverse=True):
        rate = hits / test_periods * 100
        print(f"{name:15s}: {hits:3d}/{test_periods} ({rate:.2f}%)")

if __name__ == "__main__":
    analyze_and_test()
