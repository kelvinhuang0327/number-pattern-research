
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
    # Laplace smoothed counts of (Echo|Hit) and (Neighbor|Hit)
    habits = {n: {'Echo': 1, 'Neighbor': 1, 'Hits': 5} for n in range(1, 40)}
    for i in range(1, len(history)):
        curr = set(history[i]['numbers'])
        prev = set(history[i-1]['numbers'])
        for n in curr:
            habits[n]['Hits'] += 1
            if n in prev: habits[n]['Echo'] += 1
            if (n-1 in prev) or (n+1 in prev): habits[n]['Neighbor'] += 1
    return {n: {k: v/habits[n]['Hits'] for k, v in habits[n].items() if k != 'Hits'} for n in range(1, 40)}

def get_zone_likelihood(history, window=500):
    h = history[-window:]
    w = len(h)
    likelihood = [0.0] * 4
    for z in range(4):
        ts = np.array([1 if len([n for n in d['numbers'] if (n-1)//10 == z]) >= 3 else 0 for d in h])
        if sum(ts) < 5: continue
        yf = fft(ts - np.mean(ts)); xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0); pos_yf = np.abs(yf[idx_pos]); pos_xf = xf[idx_pos]
        peak_idx = np.argmax(pos_yf)
        strength = pos_yf[peak_idx]
        period = 1/pos_xf[peak_idx]
        last_idx = np.where(ts == 1)[0][-1]
        gap = (w - 1) - last_idx
        dist = abs(gap % period - period)
        if dist < 1.0 or gap % period < 1.0:
            likelihood[z] = strength / 100.0 # Strength-based bonus
    return likelihood

def predict_539_v5_fusion(history):
    b1 = _539_acb_bet(history)
    b2 = _539_markov_bet(history, exclude=set(b1))
    
    sc = _539_fourier_scores(history)
    habits = get_habit_probs(history)
    z_likes = get_zone_likelihood(history)
    prev = set(history[-1]['numbers'])
    
    fusion_scores = {}
    for n in range(1, 40):
        if n in set(b1) | set(b2): continue
        base = sc.get(n, 0.0)
        
        # 1. Habit Bonus (if it matches current state)
        h_bonus = 0.0
        if n in prev: h_bonus += habits[n]['Echo'] * 2.0
        if (n-1 in prev) or (n+1 in prev): h_bonus += habits[n]['Neighbor'] * 2.0
        
        # 2. Zone Bonus
        z = (n-1)//10
        z_bonus = z_likes[z] if z < 4 else 0.0
        
        fusion_scores[n] = base * (1.0 + h_bonus + z_bonus)
        
    b3 = sorted(fusion_scores.keys(), key=lambda n: -fusion_scores[n])[:5]
    bets = [{'numbers': b1}, {'numbers': b2}, {'numbers': sorted(b3)}]
    return enforce_tail_diversity(bets, 2, 39, history)

def run_v5_backtest():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    for n_days in [150, 500, 1500]:
        results = []
        print(f"\nFusion V5 Backtest - {n_days} draws...")
        for i in range(len(history) - n_days, len(history)):
            hb = history[:i]; actual = set(history[i]['numbers'])
            from tools.quick_predict import predict_539 as p_ctrl
            b_c, _ = p_ctrl(hb, {}, 3); b_t = predict_539_v5_fusion(hb)
            m2_c = any(len(set(b['numbers'])&actual)>=2 for b in b_c)
            m2_t = any(len(set(b['numbers'])&actual)>=2 for b in b_t)
            m3_c = any(len(set(b['numbers'])&actual)>=3 for b in b_c)
            m3_t = any(len(set(b['numbers'])&actual)>=3 for b in b_t)
            results.append({'m2_c': m2_c, 'm2_t': m2_t, 'm3_c': m3_c, 'm3_t': m3_t})
        df = pd.DataFrame(results)
        print(f"[{n_days}p] M2+: Ctrl={df.m2_c.mean():.2%} Test={df.m2_t.mean():.2%} | M3+: Ctrl={df.m3_c.mean():.2%} Test={df.m3_t.mean():.2%}")

if __name__ == "__main__":
    run_v5_backtest()
