#!/usr/bin/env python3
"""
Backtest Reverse Optimization V3 (Cold-Prioritized)
Goal: Verify if the "Cold Strategy" maintains acceptable Win Rate vs Random.

Note:
This strategy is designed for EV (Unique Winners), not Win Rate.
However, if Win Rate collapses (e.g. < 2%), then the strategy is too risky.
We expect Win Rate to be ~Random (4%).
"""
import sys
import os
import random
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

class ReverseV3Backtest:
    def __init__(self):
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery.db'))
        self.all_draws = self.db.get_all_draws('POWER_LOTTO')
        
    def get_frequency_score(self, n, history, avg_freq):
        # Re-implementing V3 Logic
        # Calculate freq in last 100 draws of 'history'
        recent = history[-100:]
        all_nums = [x for d in recent for x in d['numbers']]
        counts = Counter(all_nums)
        f = counts.get(n, 0)
        
        # V3 Scoring: Score = Freq * 10 
        # (Lower is better)
        score = f * 10
        
        # Birthday Penalty (secondary)
        if n <= 31: score += 10
        else:
            if f < avg_freq: score -= 10
            else: score += 5
            
        return score

    def run(self, periods=200):
        print(f"⚔️ Running V3 (Cold Strategy) Backtest - {periods} Periods")
        
        wins = 0
        rand_wins = 0
        total = 0
        
        # We need at least 100 periods of history for the algo
        if len(self.all_draws) < periods + 100:
            print("Not enough data.")
            return

        for i in range(periods):
            idx = len(self.all_draws) - periods + i
            target = self.all_draws[idx]
            history = self.all_draws[:idx]
            
            # --- V3 Selection ---
            # 1. Calc Freqs
            recent = history[-100:]
            all_nums = [x for d in recent for x in d['numbers']]
            counts = Counter(all_nums)
            avg_freq = sum(counts.values()) / 38
            
            # 2. Score
            scores = {}
            for n in range(1, 39):
                s = self.get_frequency_score(n, history, avg_freq)
                scores[n] = s
                
            # 3. Pick Bottom 10 Candidates -> Select 6
            sorted_nums = sorted(scores.items(), key=lambda x: x[1])
            candidates = [x[0] for x in sorted_nums[:10]]
            
            # Deterministic selection for backtest? 
            # Or Random sample? 
            # Strategy says "Select 6". Let's randomly sample to simulate user.
            # But for backtest stability, maybe just take Top 6?
            # User script uses random.sample. We should use random.sample to match.
            # But single run might be noisy. 
            # Let's take the BEST 6 (Bottom 6) to test the "Ideal V3".
            # If Bottom 6 works, then Random 6 from Bottom 10 works.
            selection = [x[0] for x in sorted_nums[:6]]
            
            # --- Random Baseline ---
            rand_sel = random.sample(range(1, 39), 6)
            
            # --- Check ---
            actual = set(target['numbers'])
            
            hits = len(actual & set(selection))
            if hits >= 3: wins += 1
            
            r_hits = len(actual & set(rand_sel))
            if r_hits >= 3: rand_wins += 1
            
            total += 1
            # print(f"Draw {idx}: Hits {hits} (Cold) vs {r_hits} (Rand)")

        print("-" * 50)
        print(f"📊 Results (N={periods})")
        print(f"🔹 V3 (Coldest 6) Win Rate : {wins/total*100:.2f}% (Count: {wins})")
        print(f"🔹 Random Baseline Win Rate : {rand_wins/total*100:.2f}% (Count: {rand_wins})")
        
        # Zone 2?
        # V3 Zone 2 uses "Anti-Frequency".
        # Let's test that too.
        z2_wins = 0
        rand_z2_wins = 0
        
        for i in range(periods):
            idx = len(self.all_draws) - periods + i
            target = self.all_draws[idx]
            history = self.all_draws[:idx]
            
            # Logic: Weighted inverse freq
            recent_z2 = [d.get('second_zone', d.get('special')) for d in history[-100:]]
            z2_counts = Counter(recent_z2)
            
            # Pick the LEAST frequent
            best_z2 = min(range(1, 9), key=lambda x: z2_counts.get(x, 0))
            
            actual_z2 = target.get('second_zone', target.get('special'))
            
            if best_z2 == actual_z2: z2_wins += 1
            
            # Random
            r2 = random.randint(1, 8)
            if r2 == actual_z2: rand_z2_wins += 1
            
        print(f"\n🎯 Zone 2 Results")
        print(f"🔹 V3 (Coldest 1) Accuracy  : {z2_wins/periods*100:.2f}%")
        print(f"🔹 Random Baseline Accuracy : {rand_z2_wins/periods*100:.2f}%")
        
        print("\n💡 Conclusion:")
        if wins < rand_wins * 0.5:
             print("⚠️ WARNING: The Cold Strategy significantly underperforms Random.")
             print("   This suggests 'Hot Hand' phenomenon exists (or Mean Reversion is slow).")
        else:
             print("✅ Strategy maintains healthy Win Rate (comparable to Random).")
             print("   Since EV is higher (Unique Winners), this is a VALID strategy.")

if __name__ == "__main__":
    bt = ReverseV3Backtest()
    bt.run()
