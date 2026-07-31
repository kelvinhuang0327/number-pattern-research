#!/usr/bin/env python3
"""
Rigorous Evolutionary GUM Auditor
=================================
1. Strict Zero-Leakage: Predicts Draw[T] using only History[0...T-1].
2. Regime-Aware: Audits the engine's ability to switch between Frontiers and Stable Anchors.
3. Multi-Term Verification: N=150, 500, 1000, Full History.
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

# Suppress engine logs during audit
logging.basicConfig(level=logging.ERROR)

from tools.predict_evolutionary_gum import EvolutionaryGUM

class EvoAuditor:
    def __init__(self, lottery_type='POWER_LOTTO'):
        self.lottery_type = lottery_type
        self.engine = EvolutionaryGUM(lottery_type=lottery_type)
        self.history_full = self.engine.history
        self.baseline = self.engine.lb.rand_win_2
        
    def run_milestone(self, periods):
        if periods > len(self.history_full):
            periods = len(self.history_full) - 200
            
        hits_3_plus = 0
        total = 0
        
        # Performance tracking by regime
        regime_stats = {}
        
        print(f"🔍 [AUDIT] Running {self.lottery_type} | Milestone N={periods}...")
        
        for i in range(periods):
            idx = len(self.history_full) - periods + i
            if idx <= 0: continue
            
            # 1. Strict Isolation
            target = self.history_full[idx]['numbers'] # FUTURE
            history_slice = self.history_full[:idx]    # PAST (training/regime reference)
            
            if len(history_slice) < 150: continue
            
            # 2. Inject slice into engine
            self.engine.history = history_slice
            
            # 3. Predict (Evo-Logic: Stacking / Switching)
            bets, scores, regime, recipes = self.engine.predict(num_bets=2)
            
            # 4. Score
            win = False
            for b in bets:
                hit_count = 0
                for n in b:
                    if n in target: hit_count += 1
                if hit_count >= 3:
                    win = True
                    break
            
            if win: hits_3_plus += 1
            total += 1
            
            # Track regime performance
            if regime not in regime_stats:
                regime_stats[regime] = {"wins": 0, "total": 0}
            regime_stats[regime]["total"] += 1
            if win: regime_stats[regime]["wins"] += 1

        win_rate = hits_3_plus / total if total > 0 else 0
        edge = win_rate - self.baseline
        
        return {
            "periods": periods,
            "win_rate": win_rate,
            "baseline": self.baseline,
            "edge": edge,
            "total_tested": total,
            "regime_stats": regime_stats
        }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', default='POWER_LOTTO', choices=['POWER_LOTTO', 'BIG_LOTTO'])
    args = parser.parse_args()
    
    auditor = EvoAuditor(lottery_type=args.lottery)
    
    milestones = [150, 500, 1000, 99999]
    
    print("="*80)
    print(f"🚀 COMPREHENSIVE EVOLUTIONARY AUDIT: {args.lottery}")
    print(f"Engine: EvolutionaryGUM (Regime-Aware / 61-Theories)")
    print("="*80)
    print(f"{'Milestone':<12} | {'Tested':<8} | {'Win Rate':<10} | {'Baseline':<10} | {'Edge'}")
    print("-" * 80)
    
    for m in milestones:
        res = auditor.run_milestone(m)
        label = f"N={m}" if m < 90000 else "Full History"
        edge_str = f"{res['edge']*100:+.2f}%"
        print(f"{label:<12} | {res['total_tested']:<8} | {res['win_rate']*100:8.2f}% | {res['baseline']*100:8.2f}% | {edge_str}")
        
        # Print breakdown for major milestones
        if m in [500, 99999]:
            for r, stats in res['regime_stats'].items():
                r_rate = stats['wins'] / stats['total'] if stats['total'] > 0 else 0
                print(f"   ∟ {r:<15}: {r_rate*100:6.2f}% ({stats['wins']}/{stats['total']})")

    print("="*80)

if __name__ == "__main__":
    main()
