
import os
import sys
import numpy as np
import pandas as pd
from collections import Counter
from numpy.fft import fft, fftfreq

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from tools.quick_predict import _539_acb_bet, _539_markov_bet, _539_fourier_scores, enforce_tail_diversity

def get_zone_rhythm_score(history, window=500):
    """Calculate which zone is most likely to cluster."""
    h_subset = history[-window:]
    w = len(h_subset)
    z_scores = []
    
    for z in range(4):
        ts = []
        for d in h_subset:
            cnt = len([n for n in d['numbers'] if (n-1)//10 == z])
            ts.append(1 if cnt >= 3 else 0)
        ts = np.array(ts)
        yf = fft(ts - np.mean(ts))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_yf = np.abs(yf[idx_pos])
        pos_xf = xf[idx_pos]
        
        # Max peak strength as score (simplified)
        peak_idx = np.argmax(pos_yf)
        strength = pos_yf[peak_idx]
        freq = pos_xf[peak_idx]
        period = 1/freq
        
        # Phase check: when was the last cluster?
        last_cluster_idx = np.where(ts == 1)[0][-1]
        gap = (w - 1) - last_cluster_idx
        
        # Scoring: closeness to period
        score = strength / (abs(gap - period) + 1.0)
        z_scores.append(score)
        
    return np.argmax(z_scores)

def run_zone_rhythm_backtest(n_days=500):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    results = []
    
    for i in range(len(history) - n_days, len(history)):
        hist_before = history[:i]
        actual_nums = set(history[i]['numbers'])
        
        # Control: Standard 3-bet (ACB + Markov + Global Fourier)
        b1 = _539_acb_bet(hist_before)
        b2 = _539_markov_bet(hist_before, exclude=set(b1))
        sc_global = _539_fourier_scores(hist_before)
        b3_ctrl = sorted([n for n in sc_global if n not in set(b1)|set(b2)], key=lambda n: -sc_global.get(n, 0))[:5]
        
        # Test: Zone Rhythm 3-bet
        best_z = get_zone_rhythm_score(hist_before)
        # Filter global fourier by zone
        sc_test = {n: sc_global[n] for n in sc_global if (n-1)//10 == best_z and n not in set(b1)|set(b2)}
        if len(sc_test) < 5:
            b3_test = sorted([n for n in sc_global if n not in set(b1)|set(b2)], key=lambda n: -sc_global.get(n, 0))[:5]
        else:
            b3_test = sorted(sc_test.keys(), key=lambda n: -sc_test[n])[:5]
            
        hits_ctrl = len(set(b3_ctrl) & actual_nums)
        hits_test = len(set(b3_test) & actual_nums)
        
        results.append({
            'draw': history[i]['draw'],
            'hits_ctrl': hits_ctrl,
            'hits_test': hits_test,
            'best_zone': best_z
        })
        
    df = pd.DataFrame(results)
    print(f"Zone Rhythm Backtest (Last {n_days} draws) - Bet 3 ONLY comparison:")
    print(f"Mean Hits (Global Fourier): {df['hits_ctrl'].mean():.3f}")
    print(f"Mean Hits (Zone Fourier):   {df['hits_test'].mean():.3f}")
    print(f"Delta: {df['hits_test'].mean() - df['hits_ctrl'].mean():+.3f}")
    
    # 062 specific check?
    res_062 = df[df['draw'].astype(str).str.contains('115000062')]
    if not res_062.empty:
        print(f"\n062 Study: Best Zone was {res_062.iloc[0]['best_zone']}, Hits Global={res_062.iloc[0]['hits_ctrl']}, Hits Zone={res_062.iloc[0]['hits_test']}")

if __name__ == "__main__":
    run_zone_rhythm_backtest(300)
