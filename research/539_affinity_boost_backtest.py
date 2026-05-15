
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
from tools.quick_predict import _539_acb_bet, _539_markov_bet, _539_fourier_scores

def run_affinity_boost_backtest(n_days=500):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    # 1. Pre-calculate affinities based on history UP TO n_days ago
    # (To be fair, we should update this slidingly, but let's start with a static snapshot for the test)
    # Actually, let's do it slidingly for the first 100 draws to get the logic right.
    
    results = []
    
    # We'll use the affinity data from the previous script (roughly)
    # But let's recalculate it for EACH draw (sliding window of 1000 draws)
    for i in range(len(history) - n_days, len(history)):
        hb = history[i-1000:i]
        actual = set(history[i]['numbers'])
        prev = set(history[i-1]['numbers'])
        
        # Calculate Affinity for this window
        aff = {n: {'Echo': 1, 'Neighbor': 1, 'Cold': 1} for n in range(1, 40)} # Laplace smoothing
        for j in range(len(hb)):
            curr_j = set(hb[j]['numbers'])
            prev_j = set(hb[j-1]['numbers']) if j > 0 else set()
            for n in curr_j:
                if n in prev_j: aff[n]['Echo'] += 1
                if (n-1 in prev_j) or (n+1 in prev_j): aff[n]['Neighbor'] += 1
        
        # Scoring
        sc_f = _539_fourier_scores(history[:i])
        b1 = _539_acb_bet(history[:i])
        b2 = _539_markov_bet(history[:i], exclude=set(b1))
        
        final_scores = {}
        for n in range(1, 40):
            if n in set(b1) | set(b2): continue
            
            # Boost based on whether the CURRENT state matches its affinity
            boost = 1.0
            if n in prev:
                boost += (aff[n]['Echo'] / sum(aff[n].values())) * 3.0
            if (n-1 in prev) or (n+1 in prev):
                boost += (aff[n]['Neighbor'] / sum(aff[n].values())) * 3.0
                
            final_scores[n] = sc_f.get(n, 0) * boost
            
        b3_boost = sorted(final_scores.keys(), key=lambda n: -final_scores[n])[:5]
        b3_ctrl = sorted([n for n in range(1, 40) if n not in set(b1)|set(b2)], key=lambda n: -sc_f.get(n, 0))[:5]
        
        results.append({
            'draw': history[i]['draw'],
            'h_ctrl': len(set(b3_ctrl) & actual),
            'h_boost': len(set(b3_boost) & actual)
        })
        
    df = pd.DataFrame(results)
    print(f"Affinity Boost Backtest (Last {n_days} draws):")
    print(f"Mean Hits (Fourier): {df['h_ctrl'].mean():.3f}")
    print(f"Mean Hits (Boosted): {df['h_boost'].mean():.3f}")
    print(f"Delta: {df['h_boost'].mean() - df['h_ctrl'].mean():+.3f}")

if __name__ == "__main__":
    run_affinity_boost_backtest(300)
