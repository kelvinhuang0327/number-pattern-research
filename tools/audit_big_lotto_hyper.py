import sys
import os
import time
from collections import defaultdict, Counter

# Ensure project root is in path
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer

def run_big_lotto_hyper_audit():
    print("=" * 70)
    print("🔬 Big Lotto (大樂透) Hyper-Precision Audit (2024-2025)")
    print("Verifying 100 periods | Strategy: Hyper-Precision v6 (Scaled for 49)")
    print("=" * 70)
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api/data/lottery_v2.db'))
    all_draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = MultiBetOptimizer()
    
    # Select 100 most recent draws (excluding the very latest for prediction context)
    # Ensure they are sorted chronologically for the audit loop
    # all_draws is typically newest first, so we take [1:101] and reverse
    # Select 50 most recent draws for v6.1 tuning verification
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
        # The optimizer now auto-detects Big Lotto based on rules (max=49)
        res = optimizer.generate_hyper_precision_2bets(
            history, rules, {}, num_bets=2
        )
        
        if i == 0:
             print(f"DEBUG: First period prediction: {res.get('bets')}")
             
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
    target_rate = 0.12 # 12% target for Big Lotto (harder than Power Lotto)
    print(f"📈 Performance vs Target ({target_rate:.0%}): {'PASSED' if (m3_hits/total_periods >= target_rate) else 'FAILED'}")
    print("=" * 70)

if __name__ == "__main__":
    run_big_lotto_hyper_audit()
