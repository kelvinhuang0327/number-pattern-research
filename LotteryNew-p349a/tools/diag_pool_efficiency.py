#!/usr/bin/env python3
"""
🔍 Pool Coverage Diagnostic
Goal: Determine if the bottleneck is Pool quality or Bet composition.
"""
import sys
import os
import io
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.biglotto_3bet_optimizer import BigLotto3BetOptimizer

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def run_diagnostic(test_periods=100):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    optimizer = BigLotto3BetOptimizer()
    
    print(f"🔬 Diagnosing Pool Efficiency over {test_periods} periods...")
    
    pool_hits_dist = Counter()
    best_bet_hits_dist = Counter()
    total = 0
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            import contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                res = optimizer.predict_3bets_diversified(history, rules)
            
            # Assuming res['candidates'] is a list of numbers, we first count them
            candidates_counter = Counter(res['candidates'])
            top_25 = [num for num, _ in candidates_counter.most_common(25)]
            pool_hits = len(set(top_25) & actual)
            pool_hits_dist[pool_hits] += 1
            
            best_bet = 0
            for b in res['bets']:
                match = len(set(b['numbers']) & actual)
                if match > best_bet:
                    best_bet = match
            best_bet_hits_dist[best_bet] += 1
            
            total += 1
        except:
            continue

    print("\n" + "=" * 60)
    print(f"📊 Pool Diagnostic Report (Top 18 Pool vs 3-Bet Slices)")
    print("-" * 60)
    print(f"{'Metric':<20} | {'Avg Hits':<10} | {'Match Dist (0/1/2/3/4/5+)'}")
    print("-" * 60)
    
    avg_pool = sum(m*c for m,c in pool_hits_dist.items()) / total
    dist_pool = f"{pool_hits_dist[0]}/{pool_hits_dist[1]}/{pool_hits_dist[2]}/{pool_hits_dist[3]}/{pool_hits_dist[4]}/{sum(pool_hits_dist[k] for k in pool_hits_dist if k >= 5)}"
    print(f"{'Top 18 Pool':<20} | {avg_pool:>9.2f} | {dist_pool}")
    
    avg_bet = sum(m*c for m,c in best_bet_hits_dist.items()) / total
    dist_bet = f"{best_bet_hits_dist[0]}/{best_bet_hits_dist[1]}/{best_bet_hits_dist[2]}/{best_bet_hits_dist[3]}/{best_bet_hits_dist[4]}/{sum(best_bet_hits_dist[k] for k in best_bet_hits_dist if k >= 5)}"
    print(f"{'Best of 3 Bets':<20} | {avg_bet:>9.2f} | {dist_bet}")
    
    # Efficiency calculation
    m3_pool = sum(pool_hits_dist[k] for k in pool_hits_dist if k >= 3)
    m3_bet = sum(best_bet_hits_dist[k] for k in best_bet_hits_dist if k >= 3)
    print("-" * 60)
    print(f"Pool M-3+ Rate: {m3_pool/total*100:.2f}% ({m3_pool} times)")
    print(f"Bet  M-3+ Rate: {m3_bet/total*100:.2f}% ({m3_bet} times)")
    print(f"Betting Efficiency: {m3_bet/m3_pool*100 if m3_pool > 0 else 0:.1f}%")
    print("=" * 60)

if __name__ == '__main__':
    run_diagnostic(150)
