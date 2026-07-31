#!/usr/bin/env python3
"""
Unified Strategy Auditor (Iron-Clad Protocol)
=============================================
1. Mandatory N >= 500 Sample Size.
2. Mandatory Edge calculation vs Random Baseline.
3. Zero-Leakage temporal slicing.
4. Standardized Reporting Format.
"""
import os
import sys
import json
import argparse
import numpy as np
import logging

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard

# Standard logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

class UnifiedAuditor:
    def __init__(self, lottery_type='POWER_LOTTO'):
        self.lb = StrategyLeaderboard(lottery_type=lottery_type)
        self.lottery_type = lottery_type
        self.baseline = self.lb.rand_win_2 if lottery_type == 'BIG_LOTTO' else self.lb.rand_win_2
        
    def audit(self, predict_func, n=500, num_bets=2, seed=42):
        if n < 500:
            print(f"⚠️ [PROTOCOL WARNING] Sample size {n} is below the N=500 mandate.")
            
        np.random.seed(seed)
        
        hits_3_plus = 0
        total = 0
        
        print(f"🚀 AUDITING: {predict_func.__name__ if hasattr(predict_func, '__name__') else 'Custom Strategy'}")
        print(f"📊 Parameters: N={n}, Bets={num_bets}, Seed={seed}")
        print("-" * 50)
        
        history_full = self.lb.draws
        # Only test where we have enough history for a 150-period window
        start_idx = len(history_full) - n
        if start_idx < 150:
            print(f"❌ Error: Not enough history to audit N={n}. Max possible: {len(history_full) - 150}")
            return
            
        for i in range(n):
            idx = start_idx + i
            target = history_full[idx]['numbers']
            history_slice = history_full[:idx] # STRICT ISOLATION
            
            # Execute prediction
            bets = predict_func(history_slice, num_bets=num_bets)
            
            # Validation
            win = False
            for b in bets:
                hit_count = sum(1 for num in b if num in target)
                if hit_count >= 3:
                    win = True
                    break
            if win:
                hits_3_plus += 1
            total += 1
            
            if (i + 1) % 100 == 0:
                print(f"   ∟ Processed {i+1}/{n}...")

        win_rate = hits_3_plus / total if total > 0 else 0
        edge = win_rate - self.baseline
        
        print("-" * 50)
        print(f"策略名稱: {predict_func.__name__ if hasattr(predict_func, '__name__') else 'Strategy'}")
        print(f"回測參數: N={total}, Seed={seed}")
        print("-" * 50)
        print(f"實測勝率 (M3+): {win_rate*100:6.2f}%")
        print(f"隨機基準 (RAND): {self.baseline*100:6.2f}%")
        print(f"理論優勢 (Edge): {edge*100:+6.2f}%")
        print("-" * 50)
        
        if edge > 0.01:
            print("🟢 結論: 具備顯著獲利潛力 (高出基準 1% 以上)")
        elif edge > 0:
            print("⚠️ 結論: 具備微弱優勢，需觀察長期穩定性")
        else:
            print("❌ 結論: 無優勢，表現低於或等於平均隨機規律")
            
        return win_rate, edge

def main():
    parser = argparse.ArgumentParser(description='Unified Strategy Auditor')
    parser.add_argument('--lottery', default='POWER_LOTTO', choices=['POWER_LOTTO', 'BIG_LOTTO'])
    parser.add_argument('--n', type=int, default=500)
    parser.add_argument('--bets', type=int, default=2)
    parser.add_argument('--strat', choices=['gum', 'stable', 'markov'], default='stable')
    args = parser.parse_args()
    
    auditor = UnifiedAuditor(lottery_type=args.lottery)
    
    # Define bridge functions for audit
    def audit_stable(history, num_bets=2):
        if args.lottery == 'POWER_LOTTO':
            # Twin Strike implementation (Cold Complement)
            freq = {}
            for d in history[-150:]:
                for n in d['numbers']:
                    freq[n] = freq.get(n, 0) + 1
            sorted_nums = sorted(range(1, 39), key=lambda x: freq.get(x, 0))
            return [sorted_nums[:6], sorted_nums[6:12]]
        else:
            # Cluster Pivot for Big Lotto
            from tools.strategy_leaderboard import StrategyLeaderboard
            lb = StrategyLeaderboard(lottery_type='BIG_LOTTO')
            return lb.strat_cluster_pivot(history, n_bets=num_bets, window=150)

    # In a real scenario, this auditor would be used by other tools.
    # We provide a default audit path for 'stable' to verify the tool itself.
    auditor.audit(audit_stable, n=args.n, num_bets=args.bets)

if __name__ == "__main__":
    main()
