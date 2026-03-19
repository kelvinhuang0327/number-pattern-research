
import os
import sys
import numpy as np
from collections import Counter

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def get_enhanced_serial_scouring(history, window=30, weights=None):
    """
    Enhanced Serial Scoring:
    - Markov (Lag-1 transition probabilities)
    - Echo (Lag-2, Lag-3 repetition)
    - Neighbors (Lag-1 numbers +/- 1)
    """
    if weights is None:
        weights = {'markov': 1.0, 'echo': 0.8, 'neighbor': 0.5}
    
    MAX_NUM = 39
    scores = Counter()
    
    prev_draw = history[-1]['numbers']
    
    # 1. Markov (Lag-1 Transitions)
    transitions = {}
    h_subset = history[-window:]
    for i in range(len(h_subset) - 1):
        for pn in h_subset[i]['numbers']:
            if pn not in transitions: transitions[pn] = Counter()
            for nn in h_subset[i+1]['numbers']:
                transitions[pn][nn] += 1
    
    m_scores = Counter()
    for pn in prev_draw:
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for n, cnt in trans.items():
                m_scores[n] += cnt / total
    
    # 2. Echo (Lag-1, Lag-2, Lag-3)
    e_scores = Counter()
    if len(history) >= 1:
        for n in history[-1]['numbers']: e_scores[n] += 1.5 # Lag-1 is strongest
    if len(history) >= 2:
        for n in history[-2]['numbers']: e_scores[n] += 1.0
    if len(history) >= 3:
        for n in history[-3]['numbers']: e_scores[n] += 0.5
        
    # 3. Neighbors (Lag-1)
    n_scores = Counter()
    for n in prev_draw:
        for d in [-1, 1]:
            nn = n + d
            if 1 <= nn <= 39:
                n_scores[nn] += 1.0

    # Combine with weights
    m_max = max(m_scores.values()) if m_scores else 1
    e_max = max(e_scores.values()) if e_scores else 1
    n_max = max(n_scores.values()) if n_scores else 1
    
    combined = Counter()
    for n in range(1, MAX_NUM + 1):
        s_m = (m_scores[n] / m_max) * weights['markov']
        s_e = (e_scores[n] / e_max) * weights['echo']
        s_n = (n_scores[n] / n_max) * weights['neighbor']
        combined[n] = s_m + s_e + s_n
        
    return combined

def run_test():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    # Target 115000062
    target_nums = {11, 12, 14, 17, 32}
    hist_for_pred = history
    
    print(f"Testing Enhanced Serial Method on 115000062...")
    print(f"Target: {sorted(list(target_nums))}")
    
    # Strategy 1: Standard Markov (Top 5)
    from tools.quick_predict import _539_markov_bet
    std_markov = _539_markov_bet(hist_for_pred)
    hits_std = set(std_markov) & target_nums
    print(f"Standard Markov: {std_markov} | Hits: {sorted(list(hits_std))} ({len(hits_std)})")
    
    # Strategy 2: Enhanced Serial
    scores = get_enhanced_serial_scouring(hist_for_pred)
    enh_serial = sorted(scores.keys(), key=lambda x: -scores[x])[:5]
    hits_enh = set(enh_serial) & target_nums
    print(f"Enhanced Serial Top-5: {sorted(enh_serial)} | Hits: {sorted(list(hits_enh))} ({len(hits_enh)})")
    
    enh_serial_10 = sorted(scores.keys(), key=lambda x: -scores[x])[:10]
    hits_10 = set(enh_serial_10) & target_nums
    print(f"Enhanced Serial Top-10: {sorted(enh_serial_10)} | Hits: {sorted(list(hits_10))} ({len(hits_10)})")

    print("\nScores for Target Numbers:")
    for n in sorted(list(target_nums)):
        rank = sorted(scores.keys(), key=lambda x: -scores[x]).index(n) + 1
        print(f"Num {n:02d}: Score {scores[n]:.3f} | Rank: {rank}")

if __name__ == "__main__":
    run_test()
