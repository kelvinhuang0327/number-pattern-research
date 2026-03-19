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

def run_big_lotto_audit():
    print("=" * 70)
    print("🔬 Big Lotto (大樂透) Baseline Audit (2024-2025)")
    print("Verifying 100 periods | Strategy: Existing Hyper-Precision Logic")
    print("=" * 70)
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api/data/lottery_v2.db'))
    all_draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = MultiBetOptimizer()
    
    # Select 100 most recent draws
    test_draws = all_draws[1:101]
    
    m3_hits = 0
    total_periods = len(test_draws)
    
    start_time = time.time()
    for i, target in enumerate(reversed(test_draws)):
        idx = all_draws.index(target)
        history = all_draws[idx + 1 :]
        
        target_nums = set(target['numbers'])
        
        # Strategy: High-Precision 2-bets (Current implementation)
        res = optimizer.generate_hyper_precision_2bets(
            history, rules, {}, num_bets=2
        )
        
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
            print(f"Progress: {i+1}/{total_periods} | M3+: {m3_hits} ({current_rate:.2%})")

    duration = time.time() - start_time
    print("-" * 70)
    print(f"✅ Audit Complete! Total Time: {duration:.2f}s")
    print(f"🎯 Final Match-3+ Hits: {m3_hits}/{total_periods}")
    print(f"📊 Success Rate: {m3_hits/total_periods:.2%}")
    print("=" * 70)

if __name__ == "__main__":
    run_big_lotto_audit()
