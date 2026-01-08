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
from models.backtest_framework import RollingBacktester, DataLeakageError

def run_verification():
    print("=" * 70)
    print("🔬 Power Lotto 4-Bet Verification: ClusterPivot + Forced Anchors [7, 15]")
    print("=" * 70)
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api/data/lottery_v2.db'))
    all_draws = db.get_all_draws('POWER_LOTTO')
    rules = get_lottery_rules('POWER_LOTTO')
    optimizer = MultiBetOptimizer()
    
    # 2025 draws
    test_draws = [d for d in all_draws if d['date'].startswith('2025') or d['date'].startswith('114')]
    # Ensure chronological order for testing
    test_draws = sorted(test_draws, key=lambda x: x['date'])
    
    m3_hits = 0
    prize8_hits = 0 # 2+1
    total_periods = len(test_draws)
    
    print(f"Testing {total_periods} periods...")
    
    for i, target in enumerate(test_draws):
        # Strict History Slicing (Integrity Check)
        target_idx = all_draws.index(target)
        # Verify slice - Strict 500 period window to match benchmark_user_claim.py
        history = all_draws[target_idx + 1 : target_idx + 501]
        
        # Double check integrity
        if any(d['draw'] == target['draw'] for d in history):
            raise DataLeakageError(f"Leakage detected for {target['draw']}")

        target_nums = set(target['numbers'])
        target_sp = int(target['special'])
        
        # Strategy: ClusterPivot with Forced Anchors [7, 15]
        try:
            res = optimizer.generate_diversified_bets(
                history, rules, num_bets=4, 
                meta_config={
                    'method': 'cluster_pivot',
                    'forced_anchors': [7, 15],
                    'anchor_count': 2,
                    'resilience': True
                }
            )
        except Exception as e:
            print(f"Error generating bets for {target['draw']}: {e}")
            continue
        
        period_m3 = False
        period_2plus1 = False
        
        for bet in res['bets']:
            m = len(set(bet['numbers']) & target_nums)
            s = (int(bet['special']) == target_sp)
            
            if m >= 3:
                period_m3 = True
            if m == 2 and s:
                period_2plus1 = True
        
        if period_m3: m3_hits += 1
        if period_m3 or period_2plus1: prize8_hits += 1
            
        if (i+1) % 20 == 0:
            print(f"Progress: {i+1}/{total_periods} | M3+: {m3_hits} ({m3_hits/(i+1):.2%})")

    print("-" * 70)
    print(f"🎯 Final Match-3+ Hits: {m3_hits}/{total_periods}")
    print(f"📊 Success Rate (M3+): {m3_hits/total_periods:.2%}")
    print(f"💰 Valid Prize Hits (M3+ or 2+1): {prize8_hits}/{total_periods} ({prize8_hits/total_periods:.2%})")
    print("=" * 70)

if __name__ == "__main__":
    run_verification()
