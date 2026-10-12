import sys
import os
import time
from collections import defaultdict

# Ensure project root is in path
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer

def run_benchmark():
    print("=" * 60)
    print("🧪 Phase 10: Elite Cluster Size Benchmarking (Big Lotto)")
    print("    Objective: Find optimal cluster size for 49 numbers")
    print("=" * 60)
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api/data/lottery_v2.db'))
    all_draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = MultiBetOptimizer()
    
    # 50 periods for speed, but sufficient for cluster density testing
    if len(all_draws) < 60:
         print("Insufficient data.")
         return
    test_draws = all_draws[1:51] 
    
    cluster_sizes = [15, 16, 18, 20, 22]
    results = {}
    
    for size in cluster_sizes:
        print(f"\n⚡ Testing Cluster Size: {size}...")
        hits = 0
        total_bets = 0
        start_t = time.time()
        
        for target in reversed(test_draws):
            idx = all_draws.index(target)
            history = all_draws[idx + 1 :]
            target_nums = set(target['numbers'])
            
            # Using custom score dict empty to force internal calculation
            try:
                # We need to manually inject scores? No, optimizer calculates them if passed empty dict? 
                # Actually generate_hyper_precision_2bets takes "number_scores".
                # We need to minimally compute scores or let previous methods do it.
                # The optimizer usually relies on UnifiedPredictor to provide scores.
                # However, generate_hyper_precision_2bets calculates its own MTFF/Final scores.
                # "number_scores" argument is used as base (usually LSTM/XGBoost).
                # To be fair, we should pass empty dict and let it rely on MTFF (feature fusion) heavily.
                # Or better, replicate the "Base Score" calculation briefly.
                # Let's use simple frequency for base to keep it fast and fair across sizes.
                
                # Mock base scores
                base_scores = defaultdict(float)
                for d in history[:50]:
                    for n in d['numbers']: base_scores[n] += 1
                
                res = optimizer.generate_hyper_precision_2bets(
                    history, rules, base_scores, num_bets=2, cluster_override=size
                )
                
                period_hit = False
                for bet in res['bets']:
                    match = len(set(bet['numbers']) & target_nums)
                    if match >= 3:
                        period_hit = True
                
                if period_hit: hits += 1
                
            except Exception as e:
                print(f"Error: {e}")
                
        rate = hits / len(test_draws)
        results[size] = rate
        print(f"   -> Result: {rate:.2%} ({hits}/{len(test_draws)}) in {time.time()-start_t:.1f}s")
        
    print("\n" + "="*60)
    print("🏆 FINAL RANKING")
    print("="*60)
    sorted_res = sorted(results.items(), key=lambda x: x[1], reverse=True)
    for size, rate in sorted_res:
        print(f"Cluster {size}: {rate:.2%}")
    print("="*60)

if __name__ == "__main__":
    run_benchmark()
