#!/usr/bin/env python3
"""
Ultimate Power Lotto Prediction (The Grand Slam Combo)
Integrates:
1. Pool Selection: V3 Reverse Optimization (Cold + High EV)
2. Zone 2 Selector: Transition Matrix (Statistical Edge)
3. Betting Engine: Smart Wheel (Combinatorial Coverage)

Usage:
Run this script to generate the "Best Possible Bets" for the next draw.
"""
import sys
import os
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.reverse_optimization_anti_popular import ReverseOptimizerV2
from tools.smart_wheel_system import SmartWheel
from database import DatabaseManager

class UltimatePredictor:
    def __init__(self):
        self.reverse_opt = ReverseOptimizerV2()
        self.wheel_sys = SmartWheel()
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery.db'))
        
    def get_zone2_recommendations(self):
        """Re-implement transition logic from Zone2Analysis"""
        draws = self.db.get_all_draws('POWER_LOTTO')
        z2_data = [d.get('second_zone', d.get('special')) for d in draws if d.get('second_zone') or d.get('special')]
        z2_data = [int(x) for x in z2_data if x is not None]
        
        if not z2_data: return [1, 2] # Fallback
        
        last_val = z2_data[-1]
        
        # Transition Matrix
        full_matrix = np.zeros((9, 9))
        for i in range(len(z2_data)-1):
             if 1 <= z2_data[i] <= 8:
                full_matrix[z2_data[i]][z2_data[i+1]] += 1
        
        next_probs = full_matrix[last_val] / np.sum(full_matrix[last_val])
        best_transition = np.argsort(next_probs)[::-1][:2] # Top 2
        
        # Also check Cold/Due
        # last_indices = {n: -1 for n in range(1, 9)}
        # for i, val in enumerate(z2_data): last_indices[val] = i
        # gap = len(z2_data) - 1 - last_indices[1]
        
        return list(best_transition)

    def generate_grand_slam(self):
        print("🚀 Initiating Grand Slam Prediction Sequence...")
        print("-" * 60)
        
        # 1. Zone 1 Pool Selection (V3 Logic)
        print("🔹 Phase 1: Selecting High-EV Pool (V3 Anti-Popular)...")
        # Reuse internal logic of ReverseOptimizer to get POOL not just 6
        freqs = self.reverse_opt.get_real_frequency()
        avg_freq = sum(freqs.values()) / 38
        
        scores = {}
        for n in range(1, 39):
            f = freqs.get(n, 0)
            score = f * 10
            if n <= 31: score += 10
            else:
                if f < avg_freq: score -= 10
                else: score += 5
            scores[n] = score
            
        sorted_nums = sorted(scores.items(), key=lambda x: x[1])
        # Pick Top 12 numbers for the Wheel
        pool_15 = [x[0] for x in sorted_nums[:15]]
        
        print(f"   Pool Selected (15): {sorted(pool_15)}")
        
        # 2. Zone 2 Selection (Transition Logic)
        print("🔹 Phase 2: Analyzing Zone 2 Transitions...")
        z2_recs = self.get_zone2_recommendations()
        print(f"   Zone 2 Targets: {z2_recs} (Based on historic transition from last draw)")
        
        # 3. Smart Wheel Generation
        print("🔹 Phase 3: Generating Optimized Tickets...")
        
        # We need to map the pool to tickets.
        # Let's generate 10 tickets (Guarantee 3 if 5)
        raw_tickets = self.wheel_sys.generate_wheel(pool_15, guarantee_hits=3, if_numbers_drawn=5, numbers_per_ticket=6)
        
        print("\n" + "=" * 60)
        print("🏆 GRAND SLAM PREDICTION (Ultimate Combo)")
        print("=" * 60)
        
        print(f"🎱 Zone 1 Pool ({len(pool_15)} nums): {sorted(pool_15)}")
        print(f"🎯 Zone 2 Anchors: {z2_recs}\n")
        
        print(f"🎫 TICKET SET A (Zone 2 = {z2_recs[0]})")
        for i, t in enumerate(raw_tickets):
            print(f"   A-{i+1:02d}: {sorted(t)} + {z2_recs[0]}")
            
        if len(z2_recs) > 1:
            print(f"\n🎫 TICKET SET B (Zone 2 = {z2_recs[1]})")
            for i, t in enumerate(raw_tickets):
                print(f"   B-{i+1:02d}: {sorted(t)} + {z2_recs[1]}")
                
        total_tickets = len(raw_tickets) * len(z2_recs)
        print("-" * 60)
        print(f"💰 Total Investment: {total_tickets} Tickets (NT${total_tickets*100})")
        print("💡 Why this is the strongest?")
        print("   1. Pool: Avoids popular numbers (EV Maximization).")
        print("   2. Wheel: Guarantees coverage if pool hits (Safety).")
        print("   3. Zone 2: Uses statistical transition edge (Probability).")
        print("=" * 60)

if __name__ == "__main__":
    predictor = UltimatePredictor()
    predictor.generate_grand_slam()
