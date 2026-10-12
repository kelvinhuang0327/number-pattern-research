#!/usr/bin/env python3
"""
Chaos Entropy Selector (混沌熵值過濾器)
Based on Shannon Entropy and Chaos Theory.

Hypothesis:
Lottery systems oscillate between "Order" (Low Entropy) and "Chaos" (High Entropy).
- Low Entropy State: Patterns repeat. We can aggressively Kill numbers (e.g. Cold numbers stay cold).
- High Entropy State: Randomness prevails. We must be Conservative (Cold numbers might suddenly appear).

Method:
1. Calculate Entropy of the 'Gap Distribution' for the last N draws.
2. Determine Trend: Is Entropy increasing or decreasing?
3. Adjust Kill Count accordingly.
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

class ChaosEntropySelector:
    def __init__(self, lottery_type='POWER_LOTTO'):
        self.lottery_type = lottery_type
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
        self.rules = get_lottery_rules(lottery_type)
        self.max_num = self.rules['maxNumber']
        
    def calculate_entropy(self, data):
        """Calculate Shannon Entropy of a distribution"""
        if not data: return 0
        
        counts = Counter(data)
        total = sum(counts.values())
        entropy = 0
        
        for k, v in counts.items():
            p = v / total
            if p > 0:
                entropy -= p * math.log2(p)
                
        return entropy

    def get_gap_distribution(self, history):
        """Get the distribution of gaps (time since last appearance) for all numbers"""
        last_seen = {n: -1 for n in range(1, self.max_num + 1)}
        current_gaps = []
        
        # Calculate gaps up to the end of history
        # We need to scan the whole history to find the last seen index for each number
        total_len = len(history)
        for i, draw in enumerate(history):
            for n in draw['numbers']:
                last_seen[n] = i
                
        for n in range(1, self.max_num + 1):
            if last_seen[n] != -1:
                gap = total_len - 1 - last_seen[n]
                current_gaps.append(gap)
            else:
                current_gaps.append(total_len) # Never seen
                
        return current_gaps

    def analyze_chaos_state(self, draws, lookback=10):
        """
        Analyze the entropy trend over the last 'lookback' periods.
        Returns: 'Stable', 'Chaotic', 'Transition'
        """
        entropy_history = []
        
        # We calculate the Snapshot Entropy for each of the last N steps
        for i in range(lookback):
            # Slice history ending at (Now - i)
            # We need enough history to calc gaps, say 100 draws
            end_idx = len(draws) - (lookback - 1 - i)
            if end_idx < 100: continue
            
            sub_history = draws[:end_idx]
            gaps = self.get_gap_distribution(sub_history)
            
            # We bin the gaps to make a distribution: [0-5], [6-10], [11-20], [20+]
            # Or just raw gaps? Binning is more stable.
            bins = [0] * 5
            for g in gaps:
                if g <= 5: bins[0] += 1
                elif g <= 10: bins[1] += 1
                elif g <= 20: bins[2] += 1
                elif g <= 30: bins[3] += 1
                else: bins[4] += 1
            
            # Expand bins into a list for entropy calc
            # Or just pass the counts? calculate_entropy takes list of items.
            # Let's pass the bin counts directly to a custom entropy calc
            
            # Custom Entropy for Bins
            total = sum(bins)
            e = 0
            for b in bins:
                p = b / total
                if p > 0: e -= p * math.log2(p)
            
            entropy_history.append(e)
            
        if not entropy_history: return "Unknown", 0
        
        # Determine Trend (Slope)
        x = np.arange(len(entropy_history))
        y = np.array(entropy_history)
        slope, _ = np.polyfit(x, y, 1)
        
        current_entropy = entropy_history[-1]
        avg_entropy = np.mean(entropy_history)
        
        # Logic:
        # High Entropy (> Avg) + Positive Slope = Increasing Chaos -> DANGER (Kill Less)
        # Low Entropy (< Avg) + Negative Slope = Increasing Order -> SAFE (Kill More)
        
        status = "Normal"
        if current_entropy < 2.0 and slope < 0: status = "Stable (Order)"
        elif current_entropy > 2.2 or slope > 0.02: status = "Chaotic (Disorder)"
        
        return status, current_entropy

    def get_kill_list(self, history):
        status, entropy = self.analyze_chaos_state(history)
        
        # 1. Base Strategy: Kill Coldest Numbers
        # (Numbers that have not appeared for a long time)
        gaps = self.get_gap_distribution(history)
        # Pair (Number, Gap)
        gap_map = []
        for i, g in enumerate(gaps):
            gap_map.append( (i+1, g) )
            
        # Sort by Gap Descending (Coldest first)
        gap_map.sort(key=lambda x: x[1], reverse=True)
        
        # 2. Dynamic Count
        if "Stable" in status:
            kill_count = 12 # Aggressive
            # In Stable state, Cold numbers tend to STAY Cold.
        elif "Chaotic" in status:
            kill_count = 6  # Conservative
            # In Chaotic state, Cold numbers might rebound (Mean Reversion).
        else:
            kill_count = 9  # Normal
            
        kill_candidates = [x[0] for x in gap_map[:kill_count]]
        
        return {
            'status': status,
            'entropy': entropy,
            'kill_count': kill_count,
            'numbers': sorted(kill_candidates)
        }

    def backtest(self, periods=50):
        all_draws = self.db.get_all_draws(self.lottery_type)
        
        total_killed = 0
        total_mistakes = 0  # Killed a winning number
        
        print(f"🌀 Chaos Entropy Backtest (N={periods})")
        print(f"{'Draw':<10} | {'State':<15} | {'Entr':<5} | {'Kill#':<5} | {'Mistakes'}")
        print("-" * 60)
        
        for i in range(periods):
            idx = len(all_draws) - periods + i
            target = all_draws[idx]
            history = all_draws[:idx]
            
            res = self.get_kill_list(history)
            
            actual = set(target['numbers'])
            killed = set(res['numbers'])
            
            mistakes = len(actual & killed)
            
            total_killed += len(killed)
            total_mistakes += mistakes
            
            mistake_str = "✅ Perfect" if mistakes == 0 else f"❌ {mistakes}"
            state_icon = "🌊" if "Chaotic" in res['status'] else ("🧊" if "Stable" in res['status'] else "⚖️")
            
            draw_val = target.get('draw', target.get('period', 'Unknown'))
            print(f"{draw_val:<10} | {state_icon} {res['status']:<13} | {res['entropy']:.2f}  | {res['kill_count']:<5} | {mistake_str}")
            
        avg_kill = total_killed / periods
        accuracy = (1 - (total_mistakes / total_killed)) * 100
        
        print("-" * 60)
        print(f"📊 Final Accuracy: {accuracy:.2f}% (Non-Error Rate)")
        print(f"   Avg Killed  : {avg_kill:.1f} nums/draw")
        print(f"   Total Errors: {total_mistakes} (in {periods} draws)")
        print("   Goal: Errors should be < 0.5 per draw (Total < 25)")

if __name__ == "__main__":
    selector = ChaosEntropySelector()
    selector.backtest()
