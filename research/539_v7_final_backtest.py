
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

def get_habit_probs(history):
    # Calculate Echo/Neighbor probability per number
    habits = {n: {'Echo': 1, 'Neighbor': 1, 'Hits': 5} for n in range(1, 40)}
    for i in range(1, len(history)):
        curr = set(history[i]['numbers']); prev = set(history[i-1]['numbers'])
        for n in curr:
            habits[n]['Hits'] += 1
            if n in prev: habits[n]['Echo'] += 1
            if (n-1 in prev) or (n+1 in prev): habits[n]['Neighbor'] += 1
    return habits

def get_zone_likelihood(history, window=500):
    h = history[-window:]; w = len(h)
    z_likes = []
    for z in range(4):
        ts = np.array([1 if len([n for n in d['numbers'] if (n-1)//10 == z]) >= 3 else 0 for d in h])
        if sum(ts) < 5: continue
        yf = fft(ts - np.mean(ts)); xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0); pos_yf = np.abs(yf[idx_pos]); pos_xf = xf[idx_pos]
        peak_idx = np.argmax(pos_yf); period = 1/pos_xf[peak_idx]
        gap = (w - 1) - np.where(ts == 1)[0][-1]
        if abs(gap % period - period) < 1.0 or gap % period < 1.0:
            z_likes.append(z)
    return z_likes

def predict_539_v7_final(history):
    b1 = _539_acb_bet(history)
    b2 = _539_markov_bet(history, exclude=set(b1))
    
    habits = get_habit_probs(history)
    sc = _539_fourier_scores(history)
    likely_zones = get_zone_likelihood(history)
    prev = set(history[-1]['numbers'])
    exclude = set(b1) | set(b2)
    
    # 1. Selection in Likely Zones (with Habit awareness)
    b3 = []
    if likely_zones:
        for z in likely_zones:
            candidates = [n for n in range(1, 40) if (n-1)//10 == z and n not in exclude]
            if not candidates: continue
            
            # Habit score: probability of hitting in curr state
            def get_habit_score(n):
                s = 1.0
                if n in prev: s += habits[n]['Echo'] / habits[n]['Hits'] * 5.0
                if (n-1 in prev) or (n+1 in prev): s += habits[n]['Neighbor'] / habits[n]['Hits'] * 5.0
                return s
                
            best_in_zone = max(candidates, key=lambda n: sc.get(n, 0.0) * get_habit_score(n))
            b3.append(best_in_zone)
            exclude.add(best_in_zone)
            
    # 2. Fill the rest with global habits & fourier
    def global_score(n):
        s = 1.0
        if n in prev: s += habits[n]['Echo'] / habits[n]['Hits'] * 2.0 # Lower weight for global fill
        if (n-1 in prev) or (n+1 in prev): s += habits[n]['Neighbor'] / habits[n]['Hits'] * 2.0
        return sc.get(n, 0.0) * s
        
    remaining = sorted([n for n in range(1, 40) if n not in exclude], key=global_score, reverse=True)
    b3.extend(remaining[:5 - len(b3)])
    
    bets = [{'numbers': b1}, {'numbers': b2}, {'numbers': sorted(b3[:5])}]
    return enforce_tail_diversity(bets, 2, 39, history)

def run_v7_backtest():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    for n_days in [150, 500, 1500]:
        results = []
        print(f"\nFinal V7 Backtest (Affinity + Zone) - {n_days} draws...")
        for i in range(len(history) - n_days, len(history)):
            hb = history[:i]; actual = set(history[i]['numbers'])
            from tools.quick_predict import predict_539 as p_ctrl
            b_c, _ = p_ctrl(hb, {}, 3); b_t = predict_539_v7_final(hb)
            hits_c = [len(set(b['numbers'])&actual) for b in b_c]
            hits_t = [len(set(b['numbers'])&actual) for b in b_t]
            results.append({
                'm2_c': any(h>=2 for h in hits_c), 'm2_t': any(h>=2 for h in hits_t),
                'm3_c': any(h>=3 for h in hits_c), 'm3_t': any(h>=3 for h in hits_t)
            })
        df = pd.DataFrame(results)
        print(f"[{n_days}p] M2+: Ctrl={df.m2_c.mean():.2%} Test={df.m2_t.mean():.2%} | M3+: Ctrl={df.m3_c.mean():.2%} Test={df.m3_t.mean():.2%}")

if __name__ == "__main__":
    run_v7_backtest()
