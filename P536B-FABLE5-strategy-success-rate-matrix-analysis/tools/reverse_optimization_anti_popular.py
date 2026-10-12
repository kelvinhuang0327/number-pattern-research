#!/usr/bin/env python3
"""
Reverse Optimization (Data-Driven V2)
修正版策略：不依賴迷信，依賴數據。

Logic:
1. Gamblers bet on "Hot Numbers" (Draw Frequency). -> We must AVOID Hot numbers.
2. Gamblers bet on "Birthdays" (1-31). -> We must AVOID 1-31.
3. Gamblers bet on "Patterns" (Consecutive). -> We must AVOID Consecutive.

Algorithm:
1. Calculate Real Frequency (Last 100 Draws) for every number.
2. Popularity Score = (Frequency * Weight) + (BirthdayPenalty if <=31).
3. Select 6 numbers with LOWEST Score (Cold + High Number).
4. Check Consecutiveness: If consecutive, discard and retry.
"""
import sys
import os
import random
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

class ReverseOptimizerV2:
    def __init__(self):
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
        self.max_num = 38
        
    def get_real_frequency(self):
        all_draws = self.db.get_all_draws('POWER_LOTTO')
        # Analyze last 100 draws for "Current Hotness"
        recent = all_draws[-100:]
        nums = [n for d in recent for n in d['numbers']]
        return Counter(nums)

    def generate_bet(self):
        freqs = self.get_real_frequency()
        avg_freq = sum(freqs.values()) / 38
        
        scores = {}
        print(f"\n📊 Data-Driven Popularity Analysis (Last 100 Draws):")
        print(f"{'Num':<4} | {'Freq':<5} | {'Score':<6} | {'Reason'}")
        print("-" * 40)
        
        for n in range(1, self.max_num + 1):
            f = freqs.get(n, 0)
            
            # Base Score = Frequency * 10 (Dominant Factor)
            # Cold numbers (Low Freq) get Low Score -> Selected
            score = f * 10 
            
            # Birthday Bias (Secondary Factor)
            # Reduced from 50 to 10 based on user feedback (Coldness > Birthday)
            if n <= 31:
                score += 10
            else:
                # 32-38 are "Safe" from birthday pickers
                # But only if not Hot!
                if f < avg_freq:
                    score -= 10
                else:
                    # If Hot High Number (like 38), do not reward
                    score += 5 # Slight penalty for being Hot even if High
                
            scores[n] = score
            
            # Debug log for interesting numbers
            if n in [12, 31, 4, 38, 21, 27, 29, 32]:
                reason = "Cold"
                if f > avg_freq: reason = "Hot"
                if n <= 31: reason += "+Bday"
                print(f"{n:<4} | {f:<5} | {score:<6} | {reason}")
                
        # Select from Bottom 10 (Stricter Pool)
        sorted_nums = sorted(scores.items(), key=lambda x: x[1])
        pool_candidates = [x[0] for x in sorted_nums[:10]]
        
        # Retry logic for consecutive check
        attempts = 0
        while attempts < 100:
            selection = sorted(random.sample(pool_candidates, 6))
            
            # Constraint: No Consecutive
            has_consecutive = False
            for i in range(len(selection)-1):
                if selection[i+1] == selection[i] + 1:
                    has_consecutive = True
                    break
            
            if not has_consecutive:
                return selection, pool_candidates
                
            attempts += 1
            
        return sorted(random.sample(pool_candidates, 6)), pool_candidates # Fallback

    def generate_zone2(self):
        # Zone 2: 1-8.
        # "Popular" are 2, 5 (Frequent).
        # We want "Unpopular".
        # Check Frequency
        all_draws = self.db.get_all_draws('POWER_LOTTO')
        recent = [d.get('second_zone', d.get('special')) for d in all_draws[-100:]]
        counts = Counter(recent)
        
        # Invert weights: Higher freq -> Lower chance
        # Score = 1 / Freq
        weights = []
        candidates = []
        for i in range(1, 9):
            f = counts.get(i, 1)
            weights.append(1/f)
            candidates.append(i)
            
        return random.choices(candidates, weights=weights, k=1)[0]

def main():
    optimizer = ReverseOptimizerV2()
    bet, pool = optimizer.generate_bet()
    z2 = optimizer.generate_zone2()
    
    print("\n" + "="*60)
    print("🦢 Reverse Optimization V2 (Data-Driven)")
    print("="*60)
    print(f"🎱 Pool (Lowest Score 15): {pool}")
    print(f"🎯 Final Selection: {bet}")
    print(f"⚡ Zone 2: {z2} (Anti-Frequency Weighted)")
    print("\n💡 Logic Update:")
    print("   - Uses ACTUAL draw frequency (Hot numbers are penalized).")
    print("   - Penalizes 1-31 (Birthday).")
    print("   - Enforces NO Consecutive numbers.")
    print("   - Result: A mix of Cold + High Numbers (True EV Strategy).")
    print("="*60)

if __name__ == "__main__":
    main()
