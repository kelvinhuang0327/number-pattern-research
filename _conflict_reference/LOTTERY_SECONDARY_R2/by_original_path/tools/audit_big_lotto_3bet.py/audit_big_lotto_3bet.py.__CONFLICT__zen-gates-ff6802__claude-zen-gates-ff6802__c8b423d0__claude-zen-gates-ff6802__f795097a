import sys
import os
import time
import math
from collections import defaultdict, Counter

# Ensure project root is in path
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer

def calculate_probabilities(pick_count=6, max_number=49):
    """Calculate theoretical probabilities for Big Lotto"""
    def nCr(n, r):
        if r < 0 or r > n: return 0
        return math.comb(n, r)
    
    total_combinations = nCr(max_number, pick_count)
    
    # Probabilities for single bet
    p_m3 = nCr(pick_count, 3) * nCr(max_number - pick_count, pick_count - 3) / total_combinations
    p_m2 = nCr(pick_count, 2) * nCr(max_number - pick_count, pick_count - 2) / total_combinations
    
    return p_m2, p_m3

def run_3bet_audit():
    print("=" * 70)
    print("🚀 Big Lotto TRI-CORE 3-Bet Validation (150 Periods)")
    print("    Objective: Verify >9.0% Match-3+ Rate (Target Zone)")
    print("=" * 70)
    
    # 1. Establish Baselines
    p_m2, p_m3 = calculate_probabilities()
    # For 3 bets (assuming independence for simplification)
    baseline_m3_3bet = 1 - (1 - p_m3)**3
    
    print(f"📉 Math Baseline (3-bet): Match-3+: {baseline_m3_3bet:.4%}")
    print(f"🎯 Target: 9.00%+")
    print("-" * 70)

    # 2. Setup
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api/data/lottery_v2.db'))
    all_draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = MultiBetOptimizer()
    
    if len(all_draws) < 160:
        print("⚠️  Warning: Insufficient data. Using max available.")
        test_draws = all_draws[1:]
    else:
        test_draws = all_draws[1:151]

    stats = {
        'm3_plus_periods': 0, # How many periods had at least one M3+
        'total_m3': 0,
        'total_m4': 0,
        'total_bets': 0
    }
    
    total_periods = len(test_draws)
    print(f"🏁 Starting 3-Bet Audit on {total_periods} periods...")
    
    start_time = time.time()
    
    for i, target in enumerate(reversed(test_draws)):
        # Run Prediction
        idx = all_draws.index(target)
        history = all_draws[idx + 1 :]
        target_nums = set(target['numbers'])
        
        try:
            # Request 3 bets -> This triggers Tri-Core
            res = optimizer.generate_diversified_bets(
                history, rules, num_bets=3
            )
        except Exception as e:
            print(f"❌ Error in period {i}: {e}")
            continue

        # Check Hits
        period_has_m3 = False
        period_best_m = 0
        
        for bet in res['bets']:
            match = len(set(bet['numbers']) & target_nums)
            period_best_m = max(period_best_m, match)
            
            if match >= 3: 
                stats['total_m3'] += 1
                period_has_m3 = True
            if match >= 4:
                stats['total_m4'] += 1
                
            stats['total_bets'] += 1
            
        if period_has_m3:
            stats['m3_plus_periods'] += 1
        
        # Log Progress
        if (i+1) % 10 == 0:
            period_success_rate = stats['m3_plus_periods'] / (i+1)
            print(f"Progress: {i+1}/{total_periods} | Period Success: {period_success_rate:.2%} | M4 Hits: {stats['total_m4']}")

    # 4. Final Reporting
    duration = time.time() - start_time
    period_success_rate = stats['m3_plus_periods'] / total_periods
    
    print("=" * 70)
    print("📊 TRI-CORE AUDIT RESULTS")
    print(f"Total Periods: {total_periods}")
    print(f"Success Rate (At least one M3+): {period_success_rate:.2%}")
    print(f"Baseline (Random 3-bet): {baseline_m3_3bet:.2%} | Uplift: {period_success_rate/baseline_m3_3bet:.2f}x")
    print(f"Match-4+ Hits: {stats['total_m4']}")
    print("-" * 30)
    
    if period_success_rate >= 0.09:
        print("✅ VERDICT: SUCCESS (TARGET MET)")
    elif period_success_rate >= 0.06:
        print("⚠️ VERDICT: PARTIAL SUCCESS (ABOVE BASELINE, BELOW TARGET)")
    else:
        print("❌ VERDICT: FAILED")
    print("=" * 70)

if __name__ == "__main__":
    run_3bet_audit()
