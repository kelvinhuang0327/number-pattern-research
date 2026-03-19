
import os
import sys
import numpy as np
from collections import Counter
import pandas as pd

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
def get_enhanced_serial_scouring(history, window=30, weights=None):
    if weights is None:
        weights = {'markov': 1.0, 'echo': 0.8, 'neighbor': 0.5}
    MAX_NUM = 39
    scores = Counter()
    prev_draw = history[-1]['numbers']
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
    e_scores = Counter()
    if len(history) >= 1:
        for n in history[-1]['numbers']: e_scores[n] += 1.5
    if len(history) >= 2:
        for n in history[-2]['numbers']: e_scores[n] += 1.0
    if len(history) >= 3:
        for n in history[-3]['numbers']: e_scores[n] += 0.5
    n_scores = Counter()
    for n in prev_draw:
        for d in [-1, 1]:
            nn = n + d
            if 1 <= nn <= 39:
                n_scores[nn] += 1.0
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

def run_backtest(n_days=150):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    results = []
    
    for i in range(len(history) - n_days, len(history)):
        hist_before = history[:i]
        actual_nums = set(history[i]['numbers'])
        
        # Calculate last serial linkage (feature for regime)
        curr_prev = set(history[i-1]['numbers'])
        prev_prev = set(history[i-2]['numbers'])
        repeats = len(curr_prev & prev_prev)
        
        # Enhanced Serial
        scores = get_enhanced_serial_scouring(hist_before)
        top5 = sorted(scores.keys(), key=lambda x: -scores[x])[:5]
        hits = len(set(top5) & actual_nums)
        
        results.append({
            'draw': history[i]['draw'],
            'hits': hits,
            'prev_repeats': repeats
        })
        
    df = pd.DataFrame(results)
    
    # Calculate rolling serial links indicator (Regime Metric)
    # We need to compute this for the history BEFORE the draw
    regime_data = []
    for i in range(len(history) - n_days, len(history)):
        window_hist = history[i-11:i] # Look back 10 draws
        # Calculate local seriality
        links = []
        for j in range(1, len(window_hist)):
            curr = set(window_hist[j]['numbers'])
            prev = set(window_hist[j-1]['numbers'])
            links.append(len(curr & prev))
        regime_data.append(np.mean(links))
        
    df['regime_metric'] = regime_data
    
    print(f"Backtest Results (Last {n_days} draws):")
    
    # Correlation between regime_metric (prev 10-draw repetition rate) and actual hits
    corr = df['regime_metric'].corr(df['hits'])
    print(f"Correlation (Regime Metric vs Hits): {corr:.3f}")
    
    # Slice by Regime
    low_momentum = df[df['regime_metric'] < 0.6]
    high_momentum = df[df['regime_metric'] >= 0.6]
    
    print(f"Low Momentum Regime (<0.6, N={len(low_momentum)}) -> Mean Hits: {low_momentum['hits'].mean():.3f}, M2+: {len(low_momentum[low_momentum['hits'] >= 2])/len(low_momentum):.2%}")
    print(f"High Momentum Regime (>=0.6, N={len(high_momentum)}) -> Mean Hits: {high_momentum['hits'].mean():.3f}, M2+: {len(high_momentum[high_momentum['hits'] >= 2])/len(high_momentum):.2%}")

if __name__ == "__main__":
    run_backtest()
