
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
    """Calculate Echo/Neighbor/Cold affinity for each number (1-39)."""
    affinities = {n: {'Echo': 1, 'Neighbor': 1, 'Total': 3} for n in range(1, 40)} # Laplace
    for i in range(1, len(history)):
        curr = set(history[i]['numbers'])
        prev = set(history[i-1]['numbers'])
        for n in curr:
            if n in prev: affinities[n]['Echo'] += 1
            if (n-1 in prev) or (n+1 in prev): affinities[n]['Neighbor'] += 1
            affinities[n]['Total'] += 1
    
    # Probabilities
    probs = {}
    for n in range(1, 40):
        probs[n] = {
            'Echo': affinities[n]['Echo'] / affinities[n]['Total'],
            'Neighbor': affinities[n]['Neighbor'] / affinities[n]['Total']
        }
    return probs

def _get_zone_rhythm_boost(history, window=500):
    """Identify which zone is in a 'cluster-likely' phase."""
    h = history[-window:]
    w = len(h)
    z_boosts = [1.0, 1.0, 1.0, 1.0]
    
    for z in range(4):
        ts = np.array([1 if len([n for n in d['numbers'] if (n-1)//10 == z]) >= 3 else 0 for d in h])
        if sum(ts) < 5: continue
            
        yf = fft(ts - np.mean(ts))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_yf = np.abs(yf[idx_pos])
        pos_xf = xf[idx_pos]
        
        peak_idx = np.argmax(pos_yf)
        strength = pos_yf[peak_idx]
        period = 1/pos_xf[peak_idx]
        
        # Last cluster gap
        last_idx = np.where(ts == 1)[0][-1]
        gap = (w - 1) - last_idx
        
        # If we are near a multiple of the period, boost this zone
        dist = abs(gap % period - period) # Distance to next peak
        if dist < 1.0: # Very close to next peak window
            z_boosts[z] = 1.0 + (strength/100.0) # Boost relative to spectral strength
            
    return z_boosts

def predict_539_v3_candidate(history, num_bets=3):
    """New 3-bet strategy combining affinity and zone rhythm."""
    b1 = _539_acb_bet(history)
    b2 = _539_markov_bet(history, exclude=set(b1))
    
    if num_bets < 3:
        # Standard logic for 1 or 2 bets
        if num_bets == 1: return [{'numbers': b1}]
        return [{'numbers': b1}, {'numbers': b2}]
        
    # --- Bet 3: Affinity + Zone Rhythm Fusion ---
    aff = get_affinity_data(history)
    z_boosts = _get_zone_rhythm_boost(history)
    sc = _539_fourier_scores(history)
    prev = set(history[-1]['numbers'])
    
    f_scores = {}
    for n in range(1, 40):
        if n in set(b1) | set(b2): continue
        
        base = sc.get(n, 0.0)
        
        # 1. Affinity Boost (LocalHabit)
        # If n is in prev, boost by its Echo habit
        habit_boost = 1.0
        if n in prev:
            habit_boost += aff[n]['Echo'] * 5.0 # Scale habit by affinity prob
        if (n-1 in prev) or (n+1 in prev):
            habit_boost += aff[n]['Neighbor'] * 5.0
            
        # 2. Zone Rhythm Boost
        z = (n-1)//10
        zone_boost = z_boosts[z] if z < 4 else 1.0
        
        f_scores[n] = base * habit_boost * zone_boost
        
    b3 = sorted(f_scores, key=lambda x: -f_scores[x])[:5]
    bets = [{'numbers': b1}, {'numbers': b2}, {'numbers': sorted(b3)}]
    return enforce_tail_diversity(bets, 2, 39, history)

def run_rigorous_backtest(n_days_list=[150, 500, 1500]):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    baseline = 30.50 # M2+ for 3-bet 539
    
    for n_days in n_days_list:
        results = []
        print(f"\nRunning {n_days}-draw backtest...")
        
        for i in range(len(history) - n_days, len(history)):
            hb = history[:i]
            actual = set(history[i]['numbers'])
            
            # Control: ACB + Markov + Global Fourier
            from tools.quick_predict import predict_539 as predict_ctrl
            bets_ctrl, _ = predict_ctrl(hb, {}, num_bets=3)
            
            # Test: V3 Candidate
            bets_test = predict_539_v3_candidate(hb, num_bets=3)
            
            h_ctrl = [len(set(b['numbers']) & actual) for b in bets_ctrl]
            h_test = [len(set(b['numbers']) & actual) for b in bets_test]
            
            results.append({
                'm2_ctrl': any(h >= 2 for h in h_ctrl),
                'm3_ctrl': any(h >= 3 for h in h_ctrl),
                'm2_test': any(h >= 2 for h in h_test),
                'm3_test': any(h >= 3 for h in h_test)
            })
            
        df = pd.DataFrame(results)
        print(f"Results for {n_days} draws:")
        print(f"  M2+ Rate: Ctrl={df['m2_ctrl'].mean():.2%} | Test={df['m2_test'].mean():.2%}")
        print(f"  M3+ Rate: Ctrl={df['m3_ctrl'].mean():.2%} | Test={df['m3_test'].mean():.2%}")
        
if __name__ == "__main__":
    run_rigorous_backtest()
