import sys
import os
import time
from collections import defaultdict, Counter

# Ensure project root is in path
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.multi_bet_optimizer import MultiBetOptimizer

def run_benchmark():
    print("=" * 70)
    print("🔬 Power Lotto 4-Bet ClusterPivot Benchmark (Anchors [7, 15])")
    print("Testing 102 periods from 2025...")
    print("=" * 70)
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api/data/lottery_v2.db'))
    all_draws = db.get_all_draws('POWER_LOTTO')
    rules = get_lottery_rules('POWER_LOTTO')
    optimizer = MultiBetOptimizer()
    
    # 2025 draws
    test_draws = [d for d in all_draws if d['date'].startswith('2025') or d['date'].startswith('114')][:102]
    
    m3_hits = 0
    prize8_hits = 0
    total_periods = 102
    
    start_time = time.time()
    for i, target in enumerate(reversed(test_draws)):
        idx = all_draws.index(target)
        # Use previous 500 draws as history
        history = all_draws[idx + 1 : idx + 501]
        
        target_nums = set(target['numbers'])
        target_sp = int(target['special'])
        
        # Strategy: Standard ClusterPivot (No forced anchors)
        res = optimizer.generate_diversified_bets(
            history, rules, num_bets=4, 
            meta_config={
                'method': 'cluster_pivot',
                'anchor_count': 2,
                'resilience': True
            }
        )
        
        period_m3 = False
        period_prize8 = False
        for bet in res['bets']:
            m = len(set(bet['numbers']) & target_nums)
            s = (int(bet['special']) == target_sp)
            
            # Match 3+ main numbers
            if m >= 3:
                period_m3 = True
            
            # Match 3+ OR 8th Prize (2+1)
            if m >= 3 or (m == 2 and s):
                period_prize8 = True
        
        if period_m3: m3_hits += 1
        if period_prize8: prize8_hits += 1
            
        if (i+1) % 10 == 0:
            print(f"Progress: {i+1}/{total_periods} | M3+: {m3_hits} | M3+ or 2+1: {prize8_hits}")

    duration = time.time() - start_time
    print("-" * 70)
    print(f"✅ Benchmark Complete! Total Time: {duration:.2f}s")
    print(f"🎯 Final Match-3+ Hits: {m3_hits}/{total_periods}")
    print(f"📊 Success Rate: {m3_hits/total_periods:.2%}")
    print("=" * 70)

if __name__ == "__main__":
    run_benchmark()
