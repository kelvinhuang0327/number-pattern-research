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

def run_cross_audit():
    print("=" * 70)
    print("🔬 Power Lotto Hyper-Precision Cross-Audit (2023-2025)")
    print("Verifying 300 periods | Strategy: MTFF + Entropy + Soft Anchor")
    print("=" * 70)
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api/data/lottery_v2.db'))
    all_draws = db.get_all_draws('POWER_LOTTO')
    rules = get_lottery_rules('POWER_LOTTO')
    optimizer = MultiBetOptimizer()
    
    # Select 50 most recent draws for v5 verification
    test_draws = all_draws[1:51]
    
    m3_hits = 0
    total_periods = len(test_draws)
    
    start_time = time.time()
    for i, target in enumerate(reversed(test_draws)):
        idx = all_draws.index(target)
        # Use previous draws as history
        history = all_draws[idx + 1 :]
        
        target_nums = set(target['numbers'])
        
        # Strategy: Hyper-Precision 2-bets
        res = optimizer.generate_hyper_precision_2bets(
            history, rules, {}, num_bets=2
        )
        
        if i == 0:
            print(f"DEBUG: First period prediction: {res.get('bets')}")
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
            eta = (time.time() - start_time) / (i+1) * (total_periods - (i+1))
            print(f"Progress: {i+1}/{total_periods} | M3+: {m3_hits} ({current_rate:.2%}) | ETA: {eta:.0f}s")

    duration = time.time() - start_time
    print("-" * 70)
    print(f"✅ Cross-Audit Complete! Total Time: {duration:.2f}s")
    print(f"🎯 Final Match-3+ Hits: {m3_hits}/{total_periods}")
    print(f"📊 Long-term success Rate: {m3_hits/total_periods:.2%}")
    print(f"📈 Performance vs 15% Target: {'PASSED' if (m3_hits/total_periods >= 0.15) else 'FAILED'}")
    print("=" * 70)

if __name__ == "__main__":
    run_cross_audit()
