#!/usr/bin/env python3
"""
Chaos Full Analysis (混沌全歷史分析)
Goal: 
1. Test Chaos Entropy logic on ALL data.
2. Test applicability to Zone 2.
3. Statistically determine the correlation between "Entropy State" and "Outcome Type" (Hot vs Cold hit).
"""
import sys
import os
import math
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules

class ChaosFullAnalyzer:
    def __init__(self, lottery_type='POWER_LOTTO'):
        self.lottery_type = lottery_type
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
        self.rules = get_lottery_rules(lottery_type)
        self.draws = self.db.get_all_draws(lottery_type)
        
    def calculate_entropy(self, data):
        if not data: return 0
        counts = Counter(data)
        total = sum(counts.values())
        entropy = 0
        for k, v in counts.items():
            p = v / total
            if p > 0: entropy -= p * math.log2(p)
        return entropy

    def get_gap_distribution(self, history, zone='zone1'):
        max_n = 38 if zone == 'zone1' else 8
        last_seen = {n: -1 for n in range(1, max_n + 1)}
        current_gaps = []
        
        start_scan = max(0, len(history) - 200) # Optimization: Only scan recent history
        # Actually need full scan for accurate gaps? No, just reverse scan until found.
        # For speed in full history loop, we should maintain state.
        # But here we are stateless per call. Let's do a quick full scan.
        
        # Optimization: history is growing.
        # We will handle this in the main loop to avoid O(N^2).
        pass

    def run_analysis(self, zone='zone1'):
        print(f"\n🌀 Running Chaos Analysis for {zone.upper()} (All Data)...")
        
        max_n = 38 if zone == 'zone1' else 8
        
        # State Tracking
        last_seen = {n: -1 for n in range(1, max_n + 1)}
        entropy_history = []
        
        # Stats
        stats = {
            'Stable': {'total': 0, 'cold_hits': 0, 'hot_hits': 0},
            'Chaotic': {'total': 0, 'cold_hits': 0, 'hot_hits': 0},
            'Normal': {'total': 0, 'cold_hits': 0, 'hot_hits': 0}
        }
        
        # We need a rolling window for entropy.
        # Let's say we start analysis after 100 draws.
        
        for i, draw in enumerate(self.draws):
            # 1. Update Gaps (Before Draw)
            current_gaps = []
            for n in range(1, max_n + 1):
                if last_seen[n] == -1: gap = i # treated as never seen
                else: gap = i - 1 - last_seen[n]
                current_gaps.append(gap)
                
            # 2. Update Last Seen (For next loop)
            target_nums = draw['numbers'] if zone == 'zone1' else [draw.get('second_zone', draw.get('special'))]
            # Ensure int
            if zone == 'zone2':
                if target_nums[0] is None: target_nums=[1] # fix weird data
                target_nums=[int(target_nums[0])]

            for n in target_nums:
                last_seen[n] = i
                
            if i < 100: continue # Warmup
            
            # 3. Calculate Entropy of Gaps
            # Binning
            bins = [0]*5
            for g in current_gaps:
                if g <= 5: bins[0]+=1
                elif g <= 10: bins[1]+=1
                elif g <= 20: bins[2]+=1
                elif g <= 30: bins[3]+=1
                else: bins[4]+=1
            
            total = sum(bins)
            e = 0
            for b in bins:
                p = b / total
                if p > 0: e -= p * math.log2(p)
            entropy_history.append(e)
            
            if len(entropy_history) < 10: continue
            
            # 4. Determine State
            # (Using same logic as before)
            recent_ent = entropy_history[-10:]
            slope, _ = np.polyfit(np.arange(10), np.array(recent_ent), 1)
            curr_ent = recent_ent[-1]
            avg_ent = np.mean(recent_ent)
            
            status = "Normal"
            # Adjusted thresholds slightly for robustness
            if curr_ent < 1.0 and slope < 0: status = "Stable"
            elif curr_ent > 1.4 or slope > 0.05: status = "Chaotic"
            
            # 5. Analyze Outcome (The numbers that actually hit in THIS draw)
            # Was it a Cold hit or Hot hit?
            # We define Cold Hit as: The number calculate gap was > Avg Gap (approx 8 for Z1, 8 for Z2)
            # Let's say Gap > 10 is Cold. Gap <= 5 is Hot.
            
            cold_hit_count = 0
            hot_hit_count = 0
            
            # We must look at the gaps calculated BEFORE the update. 
            # Luckily current_gaps is from before update.
            
            for n in target_nums:
                gap = current_gaps[n-1]
                if gap > 10: cold_hit_count += 1
                elif gap <= 5: hot_hit_count += 1
                
            # For Zone 1, we care about "Did ANY cold number hit?"
            # Or average number of cold hits?
            # Let's count "Cold Dominance"
            
            stats[status]['total'] += 1
            stats[status]['cold_hits'] += cold_hit_count
            stats[status]['hot_hits'] += hot_hit_count

        # Report
        print(f"\n📊 Results for {zone.upper()} (Total Samples: {len(self.draws)-100})")
        print(f"{'State':<10} | {'Samples':<8} | {'Avg Cold Hits':<15} | {'Avg Hot Hits':<15} | {'Ratio (C/H)'}")
        print("-" * 70)
        
        for state, d in stats.items():
            if d['total'] == 0: continue
            avg_cold = d['cold_hits'] / d['total']
            avg_hot = d['hot_hits'] / d['total']
            ratio = avg_cold / avg_hot if avg_hot > 0 else 0
            print(f"{state:<10} | {d['total']:<8} | {avg_cold:<15.2f} | {avg_hot:<15.2f} | {ratio:.2f}")

        # Interpretation
        print("\n💡 Interpretation:")
        print("   If Ratio > 1.0, Cold numbers hit more often than Hot numbers.")
        print("   Compare 'Stable' ratio vs 'Chaotic' ratio.")

if __name__ == "__main__":
    analyzer = ChaosFullAnalyzer()
    analyzer.run_analysis(zone='zone1')
    analyzer.run_analysis(zone='zone2')
