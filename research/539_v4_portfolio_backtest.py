
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

def get_affinity_data(history):
    affinities = {n: {'Echo': 1, 'Neighbor': 1, 'Total': 3} for n in range(1, 40)}
    for i in range(1, len(history)):
        curr = set(history[i]['numbers'])
        prev = set(history[i-1]['numbers'])
        for n in curr:
            if n in prev: affinities[n]['Echo'] += 1
            if (n-1 in prev) or (n+1 in prev): affinities[n]['Neighbor'] += 1
            affinities[n]['Total'] += 1
    return {n: {k: v/affinities[n]['Total'] for k, v in affinities[n].items() if k != 'Total'} for n in range(1, 40)}

def _get_zone_clusters(history, window=500):
    h = history[-window:]
    w = len(h)
    z_likely = []
    for z in range(4):
        ts = np.array([1 if len([n for n in d['numbers'] if (n-1)//10 == z]) >= 3 else 0 for d in h])
        if sum(ts) < 5: continue
        yf = fft(ts - np.mean(ts))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_yf = np.abs(yf[idx_pos])
        pos_xf = xf[idx_pos]
        peak_idx = np.argmax(pos_yf)
        period = 1/pos_xf[peak_idx]
        last_idx = np.where(ts == 1)[0][-1]
        gap = (w - 1) - last_idx
        if abs(gap % period - period) < 1.0 or gap % period < 1.0:
            z_likely.append(z)
    return z_likely

def predict_539_portfolio_candidate(history, num_bets=3):
    """V4 Portfolio: Combine signals into Bet 3 without displacing Fourier entirely."""
    b1 = _539_acb_bet(history)
    b2 = _539_markov_bet(history, exclude=set(b1))
    
    # --- Bet 3: Selection from 3 signals ---
    sc_f = _539_fourier_scores(history)
    aff = get_affinity_data(history)
    z_likely = _get_zone_clusters(history)
    prev = set(history[-1]['numbers'])
    
    exclude = set(b1) | set(b2)
    pool_f = sorted([n for n in sc_f if n not in exclude], key=lambda x: -sc_f[x])
    
    # 1. Fourier Baseline (Top 2)
    b3_picks = pool_f[:2]
    exclude.update(b3_picks)
    
    # 2. Habit/Affinity Signal (Top 2)
    habit_scores = {}
    for n in range(1, 40):
        if n in exclude: continue
        score = 0
        if n in prev: score += aff[n]['Echo']
        if (n-1 in prev) or (n+1 in prev): score += aff[n]['Neighbor']
        habit_scores[n] = score
    
    pool_h = sorted(habit_scores.keys(), key=lambda n: -habit_scores[n])
    if pool_h:
        picks_h = pool_h[:2]
        b3_picks.extend(picks_h)
        exclude.update(picks_h)
        
    # 3. Zone Signal (Top 1)
    zone_pool = [n for n in range(1, 40) if n not in exclude and (n-1)//10 in z_likely]
    if zone_pool:
        best_z = max(zone_pool, key=lambda n: sc_f.get(n, 0))
        b3_picks.append(best_z)
        
    # Fill to 5
    if len(b3_picks) < 5:
        remaining = sorted([n for n in range(1, 40) if n not in set(b3_picks) and n not in set(b1)|set(b2)], key=lambda n: -sc_f.get(n, 0))
        b3_picks.extend(remaining[:5-len(b3_picks)])
        
    bets = [{'numbers': b1}, {'numbers': b2}, {'numbers': sorted(b3_picks[:5])}]
    return enforce_tail_diversity(bets, 2, 39, history)

def run_portfolio_backtest():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    for n_days in [150, 500, 1500]:
        results = []
        print(f"\nPortfolio Backtest (150/500/1500) - {n_days} draws...")
        for i in range(len(history) - n_days, len(history)):
            hb = history[:i]
            actual = set(history[i]['numbers'])
            
            from tools.quick_predict import predict_539 as predict_ctrl
            bets_ctrl, _ = predict_ctrl(hb, {}, num_bets=3)
            bets_test = predict_539_portfolio_candidate(hb, num_bets=3)
            
            m2_ctrl = any(len(set(b['numbers']) & actual) >= 2 for b in bets_ctrl)
            m2_test = any(len(set(b['numbers']) & actual) >= 2 for b in bets_test)
            m3_ctrl = any(len(set(b['numbers']) & actual) >= 3 for b in bets_ctrl)
            m3_test = any(len(set(b['numbers']) & actual) >= 3 for b in bets_test)
            
            results.append({'m2_c': m2_ctrl, 'm2_t': m2_test, 'm3_c': m3_ctrl, 'm3_t': m3_test})
            
        df = pd.DataFrame(results)
        print(f"[{n_days}p] M2+: Ctrl={df.m2_c.mean():.2%} Test={df.m2_t.mean():.2%} | M3+: Ctrl={df.m3_c.mean():.1%} Test={df.m3_t.mean():.1%}")

if __name__ == "__main__":
    run_portfolio_backtest()
