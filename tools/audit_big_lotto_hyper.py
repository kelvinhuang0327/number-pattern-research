import sys
import os
import time
from collections import defaultdict, Counter

# Ensure project root is in path
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.multi_bet_optimizer import MultiBetOptimizer

def run_big_lotto_audit():
    print("=" * 70)
    print("🔬 Big Lotto (大樂透) Hyper-Precision Audit (100 Periods)")
    print("Strategy: Scale-Aware Clustering (18 numbers) + FSMS + Window Pivot")
    print("Target: Match-3+ Rate >= 12%")
    print("=" * 70)
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api/data/lottery_v2.db'))
    all_draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = MultiBetOptimizer()
    
    # Audit recent 100 draws
    test_draws = all_draws[1:101]
    
    m3_hits = 0
    total_periods = len(test_draws)
    
    start_time = time.time()
    for i, target in enumerate(reversed(test_draws)):
        idx = all_draws.index(target)
        # history is everything older than current target
        history = all_draws[idx + 1 :]
        
        target_nums = set(target['numbers'])
        
        # Strategy: Hyper-Precision 2-bets
        res = optimizer.generate_hyper_precision_2bets(
            history, rules, {}, num_bets=2
        )
        
        if i == 0:
            print(f"DEBUG: First period ({target['draw']}) prediction: {[b['numbers'] for b in res.get('bets')]}")
            print(f"DEBUG: Elite Cluster Size: {len(res.get('elite_cluster', []))}")
            print(f"DEBUG: Elite Cluster: {res.get('elite_cluster')}")
        
        period_hit = False
        for bet in res['bets']:
            m = len(set(bet['numbers']) & target_nums)
            if m >= 3:
                period_hit = True
                break
        
        if period_hit:
            m3_hits += 1
            
        if (i+1) % 10 == 0:
            current_rate = m3_hits / (i+1)
            elapsed = time.time() - start_time
            eta = elapsed / (i+1) * (total_periods - (i+1))
            print(f"Progress: {i+1}/{total_periods} | M3+: {m3_hits} ({current_rate:.2%}) | ETA: {eta:.0f}s")

    duration = time.time() - start_time
    print("-" * 70)
    print(f"✅ Audit Complete! Total Time: {duration:.2f}s")
    print(f"🎯 Final Match-3+ Hits: {m3_hits}/{total_periods}")
    print(f"📊 Success Rate: {m3_hits/total_periods:.2%}")
    print(f"📈 Performance vs 12% Goal: {'PASSED 🏆' if (m3_hits/total_periods >= 0.12) else 'FAILED'}")
    print("=" * 70)

if __name__ == "__main__":
    run_big_lotto_audit()
