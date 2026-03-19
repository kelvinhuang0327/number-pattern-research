
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
from tools.quick_predict import predict_539

def enforce_sum_balance_test(bets, history, mu=100, sigma=25):
    """Post-processing to shift bets towards the mean sum (100)."""
    # mu for 539 (1..39) is (1+39)/2 * 5 = 100
    # sigma is roughly 25-30
    target_lo = mu - 0.7 * sigma
    target_hi = mu + 0.7 * sigma
    
    new_bets = []
    for bet in bets:
        nums = list(bet['numbers'])
        s = sum(nums)
        if target_lo <= s <= target_hi:
            new_bets.append(bet)
            continue
            
        # Try to fix by swapping 1 number
        fixed = False
        if s < target_lo:
            # Need to increase sum: swap min/low for a higher number
            # (Simplified for test)
            pass
        elif s > target_hi:
            # Need to decrease sum
            pass
        new_bets.append(bet)
    
    return new_bets

def run_sum_constraint_backtest(n_days=500):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    sums = [sum(d['numbers']) for d in history]
    mu, sigma = np.mean(sums), np.std(sums)
    print(f"539 Historical Sum: mu={mu:.2f}, sigma={sigma:.2f}")
    
    results = []
    for i in range(len(history) - n_days, len(history)):
        hist_before = history[:i]
        actual_nums = set(history[i]['numbers'])
        actual_sum = sum(history[i]['numbers'])
        
        bets, _ = predict_539(hist_before, {}, num_bets=3)
        
        # Check if they pass constraint
        passed = 0
        hits_total = 0
        for b in bets:
            s = sum(b['numbers'])
            hits = len(set(b['numbers']) & actual_nums)
            hits_total += hits
            if mu - 0.7*sigma <= s <= mu + 0.7*sigma:
                passed += 1
                
        results.append({
            'draw': history[i]['draw'],
            'hits_avg': hits_total / 3,
            'passed_count': passed,
            'actual_in_range': mu - 0.7*sigma <= actual_sum <= mu + 0.7*sigma
        })
        
    df = pd.DataFrame(results)
    print("\nSum Constraint Analysis:")
    print(f"Avg Hits: {df['hits_avg'].mean():.3f}")
    print(f"Prop of bets currently in target range: {df['passed_count'].mean()/3:.2%}")
    print(f"Prop of ACTUAL draws in target range: {df['actual_in_range'].mean():.2%}")
    
    # Correlation between "passed count" and hits?
    corr = df['passed_count'].corr(df['hits_avg'])
    print(f"Correlation (Passed Count vs Hits): {corr:.3f}")

if __name__ == "__main__":
    run_sum_constraint_backtest(500)
