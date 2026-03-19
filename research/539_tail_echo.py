
import os
import sys
import numpy as np
import pandas as pd
from collections import Counter

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def analyze_tail_echo():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    total_draws = len(history)
    echo_counts = Counter() # How many times tail T echoed
    tail_appearances = Counter() # Total draws tail T appeared
    
    for i in range(1, total_draws):
        prev_tails = set(n % 10 for n in history[i-1]['numbers'])
        curr_tails = set(n % 10 for n in history[i]['numbers'])
        
        for t in prev_tails:
            tail_appearances[t] += 1
            if t in curr_tails:
                echo_counts[t] += 1
                
    results = []
    for t in range(10):
        prob = echo_counts[t] / tail_appearances[t] if tail_appearances[t] > 0 else 0
        results.append({
            'tail': t,
            'echo_prob': prob,
            'base_prob': 1 - (0.9 ** 5) # Prob(tail T hits in random 5/39) approx 41%
        })
        # Note: Base prob is 1 - (P(not hitting T in 5 tries))
        # P(tail T) = 4/39 or 3/39. Average 0.1
        # 1 - (0.9)^5 = 0.4095
        
    df = pd.DataFrame(results)
    df['lift'] = df['echo_prob'] / df['base_prob']
    print("Tail Echo (Serial Tail Repetition) Statistics:")
    print(df)
    
    # Global echo rate
    global_echo = sum(echo_counts.values()) / sum(tail_appearances.values())
    print(f"\nGlobal Tail Echo Rate: {global_echo:.2%} (vs Baseline ~41%)")

if __name__ == "__main__":
    analyze_tail_echo()
