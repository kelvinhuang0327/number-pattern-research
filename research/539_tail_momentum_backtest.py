
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
from tools.quick_predict import _539_acb_bet

def run_tail_momentum_backtest(n_days=500):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    results = []
    for i in range(len(history) - n_days, len(history)):
        hist_before = history[:i]
        actual_nums = set(history[i]['numbers'])
        
        # 1. Base Score (ACB)
        # We'll use a simplified version for the test
        from tools.quick_predict import _539_acb_bet
        base_bet = _539_acb_bet(hist_before)
        
        # 2. Tail Momentum
        # Count frequency of each tail in the last 5 draws
        recent_tails = [n % 10 for d in hist_before[-5:] for n in d['numbers']]
        tail_momentum = Counter(recent_tails)
        
        # New Scoring: ACB numbers with high tail momentum?
        # Let's try to RE-RANK the whole pool
        all_nums = range(1, 40)
        
        # Get ACB raw scores if possible? 
        # (Quick check: just prioritize ACB numbers that match tail momentum)
        
        # Actually, let's create a NEW strategy: "Tail-Echo Boost"
        # Score = (Gap * 0.6) + (Tail_Freq_Last_5 * 2.0)
        gaps = {n: 0 for n in all_nums}
        for n in all_nums:
            for d in reversed(hist_before):
                if n in d['numbers']: break
                gaps[n] += 1
        
        tm_scores = {}
        for n in all_nums:
            t = n % 10
            # Normalize gap and momentum
            tm_scores[n] = (gaps[n] / 20.0) * 0.5 + (tail_momentum[t] / 5.0) * 0.5
            
        top5_tm = sorted(all_nums, key=lambda n: -tm_scores[n])[:5]
        
        hits_acb = len(set(base_bet) & actual_nums)
        hits_tm = len(set(top5_tm) & actual_nums)
        
        results.append({
            'draw': history[i]['draw'],
            'hits_acb': hits_acb,
            'hits_tm': hits_tm
        })
        
    df = pd.DataFrame(results)
    print(f"Tail Momentum Backtest (Last {n_days} draws):")
    print(f"Mean Hits (ACB): {df['hits_acb'].mean():.3f}")
    print(f"Mean Hits (Tail Momentum): {df['hits_tm'].mean():.3f}")
    print(f"Delta: {df['hits_tm'].mean() - df['hits_acb'].mean():+.3f}")

if __name__ == "__main__":
    run_tail_momentum_backtest(300)
