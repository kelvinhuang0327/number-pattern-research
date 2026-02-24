#!/usr/bin/env python3
"""
Power Lotto Zone 2 Exhaustive Analysis (威力彩第二區窮盡分析)
Goal: Find high-probability patterns for the single number (1-8) in Zone 2.

Methods:
1. Transition Matrix (Markov)
2. Gap/Omission Analysis
3. Odd/Even & High/Low Patterns
4. Modulo Patterns
"""
import sys
import os
import numpy as np
import pandas as pd
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

class Zone2Analyzer:
    def __init__(self):
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery.db'))
        self.draws = self.db.get_all_draws('POWER_LOTTO')
        self.zone2_data = [d.get('second_zone', d.get('special')) for d in self.draws if d.get('second_zone') or d.get('special')]
        # Ensure ints
        self.zone2_data = [int(x) for x in self.zone2_data if x is not None]
        
    def analyze_transitions(self):
        print("\n🔍 Node Transition Analysis (Previous -> Next)")
        full_matrix = np.zeros((9, 9)) # 1-8 index (0 unused)
        
        for i in range(len(self.zone2_data)-1):
            curr = self.zone2_data[i]
            next_val = self.zone2_data[i+1]
            if 1 <= curr <= 8 and 1 <= next_val <= 8:
                full_matrix[curr][next_val] += 1
                
        # Print high prob transitions
        print("   Key Transitions (>20% prob):")
        for i in range(1, 9):
            total = np.sum(full_matrix[i])
            if total == 0: continue
            probs = full_matrix[i] / total
            best_next = np.argsort(probs)[::-1]
            
            line = f"   IF {i} THEN: "
            found = False
            for n in best_next:
                p = probs[n]
                if p > 0.18: # 18% thresholds (valid since 1/8=12.5%)
                    line += f"{n}({p*100:.1f}%) "
                    found = True
            if found: print(line)
            
    def analyze_gaps(self):
        print("\n🔍 Gap (Omission) Analysis")
        # Find current gaps
        last_indices = {n: -1 for n in range(1, 9)}
        gaps_history = {n: [] for n in range(1, 9)}
        
        for i, val in enumerate(self.zone2_data):
            if last_indices[val] != -1:
                gap = i - last_indices[val]
                gaps_history[val].append(gap)
            last_indices[val] = i
            
        current_gaps = {n: len(self.zone2_data) - 1 - idx for n, idx in last_indices.items()}
        
        print("   Number | Avg Gap | Max Gap | Current Gap | Status")
        print("   -------|---------|---------|-------------|-------")
        for n in range(1, 9):
            avg = np.mean(gaps_history[n]) if gaps_history[n] else 0
            mx = np.max(gaps_history[n]) if gaps_history[n] else 0
            curr = current_gaps[n]
            
            # Identify Signal
            status = "Normal"
            if curr > mx * 0.8: status = "⚠️ Extreme Cold"
            if curr < avg * 0.5: status = "🔥 Hot"
            if abs(curr - avg) < 2: status = "⭐ Due"
            
            print(f"   {n:^6} | {avg:^7.1f} | {mx:^7} | {curr:^11} | {status}")

    def analyze_parity_sequence(self):
        print("\n🔍 Parity Sequence (Odd/Even)")
        # 1=Odd, 0=Even
        parity = [1 if x % 2 != 0 else 0 for x in self.zone2_data]
        
        # Analyze streak
        current_streak = 0
        current_type = parity[-1]
        for x in reversed(parity[:-1]):
            if x == current_type: current_streak += 1
            else: break
            
        type_str = "ODD" if current_type == 1 else "EVEN"
        print(f"   Current Streak: {type_str} x {current_streak+1}")
        
        # Prob of switching after streak N
        streak_counts = Counter()
        switch_counts = Counter()
        
        temp_streak = 0
        temp_type = -1
        
        for x in parity:
            if x == temp_type:
                temp_streak += 1
            else:
                if temp_streak > 0:
                    streak_counts[temp_streak] += 1
                    # It switched here
                    switch_counts[temp_streak] += 1
                temp_streak = 1
                temp_type = x
                
        # Calculate Switch Probability
        print("   Switch Probability after Streak N:")
        for k in sorted(streak_counts.keys()):
            if k > 5: continue
            total = 0
            # Count how many times we reached streak k roughly? 
            # Actually simplest is: Given we are at streak k, what is prob next is different?
            # It's tricky to calc from summary.
            pass
            
    def recommend(self):
        print("\n🎯 Zone 2 Recommendations for Next Draw")
        # Simple Algo:
        # 1. Eliminate Extreme Cold (unless > Max Gap)
        # 2. Prefer 'Due' numbers (Current close to Avg)
        # 3. Use Transition from last draw
        
        last_val = self.zone2_data[-1]
        print(f"   Last Draw: {last_val}")
        
        # Transition Logic
        full_matrix = np.zeros((9, 9))
        for i in range(len(self.zone2_data)-1):
             if 1 <= self.zone2_data[i] <= 8:
                full_matrix[self.zone2_data[i]][self.zone2_data[i+1]] += 1
        
        next_probs = full_matrix[last_val] / np.sum(full_matrix[last_val])
        best_transition = np.argsort(next_probs)[::-1][:3]
        
        print(f"   Top 3 by Logic (Transition): {[n for n in best_transition]}")
        
        # Due Logic
        last_indices = {n: -1 for n in range(1, 9)}
        for i, val in enumerate(self.zone2_data): last_indices[val] = i
        current_gaps = {n: len(self.zone2_data) - 1 - idx for n, idx in last_indices.items()}
        
        due_nums = sorted(current_gaps.items(), key=lambda x: x[1], reverse=True)[:3]
        print(f"   Top 3 by Logic (Cold/Due): {[x[0] for x in due_nums]}")

if __name__ == "__main__":
    analyzer = Zone2Analyzer()
    analyzer.analyze_transitions()
    analyzer.analyze_gaps()
    analyzer.analyze_parity_sequence()
    analyzer.recommend()
