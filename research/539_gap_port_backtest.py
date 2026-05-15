
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

def get_gap_portfolio_bet(history, exclude=None):
    exclude = exclude or set()
    gaps = {n: 0 for n in range(1, 40)}
    for n in range(1, 40):
        for i, d in enumerate(reversed(history)):
            if n in d['numbers']:
                gaps[n] = i
                break
        else:
            gaps[n] = 999
            
    # Categories
    cats = {
        'Echo': [n for n in range(1, 40) if gaps[n] == 0 and n not in exclude],
        'Hot': [n for n in range(1, 40) if 1 <= gaps[n] <= 3 and n not in exclude],
        'Warm': [n for n in range(1, 40) if 4 <= gaps[n] <= 10 and n not in exclude],
        'Cold': [n for n in range(1, 40) if 11 <= gaps[n] <= 25 and n not in exclude],
        'Extreme': [n for n in range(1, 40) if gaps[n] > 25 and n not in exclude]
    }
    
    # Selection: Need 5 numbers. 
    # Use Fourier scores to break ties within categories
    sc = _539_fourier_scores(history)
    
    bet = []
    for cname in ['Echo', 'Hot', 'Warm', 'Cold', 'Extreme']:
        pool = cats[cname]
        if pool:
            best = max(pool, key=lambda n: sc.get(n, 0))
            bet.append(best)
            
    # Fill if missing
    if len(bet) < 5:
        remaining = sorted([n for n in range(1, 40) if n not in set(bet) and n not in exclude], key=lambda n: -sc.get(n, 0))
        bet.extend(remaining[:5-len(bet)])
        
    return sorted(bet[:5])

def run_gap_portfolio_backtest(n_days=500):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    results = []
    for i in range(len(history) - n_days, len(history)):
        hist_before = history[:i]
        actual_nums = set(history[i]['numbers'])
        
        b1 = _539_acb_bet(hist_before)
        b2 = _539_markov_bet(hist_before, exclude=set(b1))
        
        # Comparison: Fourier (Ctrl) vs Gap Portfolio (Test)
        sc = _539_fourier_scores(hist_before)
        b3_ctrl = sorted([n for n in range(1, 40) if n not in set(b1)|set(b2)], key=lambda n: -sc.get(n, 0))[:5]
        
        b3_test = get_gap_portfolio_bet(hist_before, exclude=set(b1)|set(b2))
        
        hits_ctrl = len(set(b3_ctrl) & actual_nums)
        hits_test = len(set(b3_test) & actual_nums)
        
        results.append({
            'draw': history[i]['draw'],
            'hits_ctrl': hits_ctrl,
            'hits_test': hits_test
        })
        
    df = pd.DataFrame(results)
    print(f"Gap Portfolio Backtest (Last {n_days} draws):")
    print(f"Mean Hits (Fourier): {df['hits_ctrl'].mean():.3f}")
    print(f"Mean Hits (Gap Port): {df['hits_test'].mean():.3f}")
    print(f"Delta: {df['hits_test'].mean() - df['hits_ctrl'].mean():+.3f}")
    
    # 062 check simulation (it's not in DB yet so we simulate if n_days=1)
    # Actually I know 062 gaps. 
    # Echo: 12, 32. Hot: 17. Cold: 11. Extreme: 14.
    # Gap Portfolio would try to pick one from each!

if __name__ == "__main__":
    run_gap_portfolio_backtest(300)
