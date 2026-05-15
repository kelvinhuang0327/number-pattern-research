
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

def get_zone_rhythm_likely(history, window=500):
    h = history[-window:]
    w = len(h)
    likely_zones = []
    for z in range(4):
        ts = np.array([1 if len([n for n in d['numbers'] if (n-1)//10 == z]) >= 3 else 0 for d in h])
        if sum(ts) < 5: continue
        yf = fft(ts - np.mean(ts)); xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0); pos_yf = np.abs(yf[idx_pos]); pos_xf = xf[idx_pos]
        peak_idx = np.argmax(pos_yf); period = 1/pos_xf[peak_idx]
        gap = (w - 1) - np.where(ts == 1)[0][-1]
        if abs(gap % period - period) < 1.0 or gap % period < 1.0:
            likely_zones.append(z)
    return likely_zones

def predict_539_v6_rebalanced(history):
    b1 = _539_acb_bet(history)
    b2 = _539_markov_bet(history, exclude=set(b1))
    
    sc = _539_fourier_scores(history)
    likely_zones = get_zone_rhythm_likely(history)
    exclude = set(b1) | set(b2)
    
    # Selection:
    # 1. Start with the absolute best globally
    sorted_global = sorted([n for n in sc if n not in exclude], key=lambda n: -sc[n])
    
    # 2. If there are likely zones, ensure we have representation
    b3 = []
    if likely_zones:
        for z in likely_zones:
            z_candidates = [n for n in sorted_global if (n-1)//10 == z]
            if z_candidates: b3.append(z_candidates[0])
            
    # 3. Fill the rest with best global
    for n in sorted_global:
        if len(b3) >= 5: break
        if n not in set(b3): b3.append(n)
        
    bets = [{'numbers': b1}, {'numbers': b2}, {'numbers': sorted(b3[:5])}]
    return enforce_tail_diversity(bets, 2, 39, history)

def run_v6_backtest():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    for n_days in [150, 500, 1500]:
        results = []
        print(f"\nRebalanced V6 Backtest - {n_days} draws...")
        for i in range(len(history) - n_days, len(history)):
            hb = history[:i]; actual = set(history[i]['numbers'])
            from tools.quick_predict import predict_539 as p_ctrl
            b_c, _ = p_ctrl(hb, {}, 3); b_t = predict_539_v6_rebalanced(hb)
            m2_c = any(len(set(b['numbers'])&actual)>=2 for b in b_c)
            m2_t = any(len(set(b['numbers'])&actual)>=2 for b in b_t)
            m3_c = any(len(set(b['numbers'])&actual)>=3 for b in b_c)
            m3_t = any(len(set(b['numbers'])&actual)>=3 for b in b_t)
            results.append({'m2_c': m2_c, 'm2_t': m2_t, 'm3_c': m3_c, 'm3_t': m3_t})
        df = pd.DataFrame(results)
        print(f"[{n_days}p] M2+: Ctrl={df.m2_c.mean():.2%} Test={df.m2_t.mean():.2%} | M3+: Ctrl={df.m3_c.mean():.2%} Test={df.m3_t.mean():.2%}")

if __name__ == "__main__":
    run_v6_backtest()
