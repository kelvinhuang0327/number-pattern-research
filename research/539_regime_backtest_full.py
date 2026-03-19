
import os
import sys
import numpy as np
import pandas as pd
from collections import Counter
import random

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from tools.quick_predict import predict_539

def run_comparison_backtest(n_days=500):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    results = []
    
    print(f"Starting Backtest comparison (Last {n_days} draws)...")
    
    for i in range(len(history) - n_days, len(history)):
        hist_before = history[:i]
        actual_nums = set(history[i]['numbers'])
        
        # 1. Old Strategy: Fixed Fourier (We mimic the STABLE_REGIME logic)
        # In quick_predict, the stable regime uses Fourier for bet 3.
        # We'll force it by bypassing the momentum check.
        
        from tools.quick_predict import _539_acb_bet, _539_markov_bet, _539_fourier_scores, enforce_tail_diversity
        
        # Old 3-bet (Fixed Fourier)
        b1_old = _539_acb_bet(hist_before)
        b2_old = _539_markov_bet(hist_before, exclude=set(b1_old))
        sc_old = _539_fourier_scores(hist_before)
        b3_old_raw = sorted(sorted(sc_old, key=lambda x: -sc_old[x])[:15], key=lambda x: hash(str(x)+str(i)))[:5]
        bets_old = [{'numbers': b1_old}, {'numbers': b2_old}, {'numbers': sorted(b3_old_raw)}]
        bets_old = enforce_tail_diversity(bets_old, 2, 39, hist_before)
        
        # Calculate M2+ for old
        hits_old = [len(set(b['numbers']) & actual_nums) for b in bets_old]
        m2_old = any(h >= 2 for h in hits_old)
        m3_old = any(h >= 3 for h in hits_old)
        
        # 2. New Strategy: Regime-Aware (predict_539 directly)
        bets_new, strat_name = predict_539(hist_before, {}, num_bets=3)
        hits_new = [len(set(b['numbers']) & actual_nums) for b in bets_new]
        m2_new = any(h >= 2 for h in hits_new)
        m3_new = any(h >= 3 for h in hits_new)
        max_hits_new = max(hits_new)
        
        # Regime metric (for analysis)
        recent_repeats = [len(set(history[j]['numbers']) & set(history[j-1]['numbers'])) for j in range(i-10, i)]
        avg_repeats = np.mean(recent_repeats)
        
        results.append({
            'draw': history[i]['draw'],
            'm2_old': m2_old,
            'm2_new': m2_new,
            'm3_old': m3_old,
            'm3_new': m3_new,
            'max_hits_new': max_hits_new,
            'avg_repeats': avg_repeats,
            'is_momentum': avg_repeats >= 0.6
        })
        
    df = pd.DataFrame(results)
    
    print("\n" + "="*40)
    print(f"Overall Results (Last {n_days} draws)")
    print("="*40)
    print(f"Method       | M2+ Rate | M3+ Rate")
    print(f"Old (Static) | {df['m2_old'].mean():.2%}   | {df['m3_old'].mean():.2%}")
    print(f"New (Regime) | {df['m2_new'].mean():.2%}   | {df['m3_new'].mean():.2%}")
    
    print("\n" + "="*40)
    print("By Regime (New Method)")
    print("="*40)
    for mom in [True, False]:
        sub = df[df['is_momentum'] == mom]
        name = "MOMENTUM" if mom else "STABLE"
        print(f"Regime {name:8} (N={len(sub):3}) | M2+: {sub['m2_new'].mean():.2%} | M3+: {sub['m3_new'].mean():.2%}")
        
    # Check specifically for the high Link hits (M4)
    m4_new = len(df[df['max_hits_new'] >= 4])
    print(f"\nNew Method M4+ Hits: {m4_new}")
    
    # Calculate approximate Edge (vs 30.50% baseline)
    edge_new = (df['m2_new'].mean() * 100) - 30.50
    print(f"Estimated Edge (New): {edge_new:+.2f}%")

if __name__ == "__main__":
    run_comparison_backtest(300) # Testing last 300 draws for speed
