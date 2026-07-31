#!/usr/bin/env python3
"""
Strongest Single Ticket Predictor
Combines the only two "non-failed" components:
1. Zone 1: Reverse Optimization V3 (Cold + Anti-Popular) -> High EV.
2. Zone 2: Transition Matrix (Markov Chain) -> Slight Statistical Edge.

Goal:
Produce ONE optimized ticket that balances "Winning Probability" (Z1 random / Z2 edge) with "Prize Value" (Anti-Popularity).
"""
import sys
import os
import random
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

class StrongestSinglePredictor:
    def __init__(self):
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery.db'))
        self.draws = self.db.get_all_draws('POWER_LOTTO')
        
    def get_v3_selection(self):
        """
        Zone 1 Strategy: Reverse Optimization V3
        - Last 100 draws frequency
        - Penalize Hot numbers (Crowded)
        - Penalize Birthday numbers (Crowded) *Slightly*
        - Select 6 numbers from the 'Coldest & Highest' score pool
        """
        recent = self.draws[-100:]
        all_nums = [x for d in recent for x in d['numbers']]
        counts = Counter(all_nums)
        avg_freq = sum(counts.values()) / 38
        
        scores = {}
        for n in range(1, 39):
            f = counts.get(n, 0)
            score = f * 10
            if n <= 31: score += 10 # Birthday penalty
            else:
                if f < avg_freq: score -= 10 # Cold High bonus
                else: score += 5 # Hot High penalty
            scores[n] = score
            
        sorted_nums = sorted(scores.items(), key=lambda x: x[1])
        # Pool of top 10 candidates (Lowest scores)
        candidates = [x[0] for x in sorted_nums[:10]]
        
        # Select 6 randomly from the best 10 to rotate luck
        return sorted(random.sample(candidates, 6))

    def get_z2_prediction(self):
        """
        Zone 2 Strategy: Markov Transition
        - Based on Previous Draw -> Next Draw probability matrix
        """
        z2_data = [d.get('second_zone', d.get('special')) for d in self.draws if d.get('second_zone') or d.get('special')]
        z2_data = [int(x) for x in z2_data if x is not None]
        
        if not z2_data: return random.randint(1, 8)
        
        last_val = z2_data[-1]
        
        full_matrix = np.zeros((9, 9))
        for i in range(len(z2_data)-1):
             if 1 <= z2_data[i] <= 8:
                full_matrix[z2_data[i]][z2_data[i+1]] += 1
        
        if np.sum(full_matrix[last_val]) == 0:
            return random.randint(1, 8)
            
        next_probs = full_matrix[last_val] / np.sum(full_matrix[last_val])
        best_next = np.argmax(next_probs) # The single best
        
        # Check if probability is significant?
        # If flat, maybe fallback to Due?
        # Let's trust the Matrix Top 1.
        return int(best_next)

    def predict(self):
        z1 = self.get_v3_selection()
        z2 = self.get_z2_prediction()
        
        print("\n" + "="*60)
        print("🦄 Strongest Single Ticket (EV + Edge)")
        print("="*60)
        print(f"🎯 Zone 1: {z1} (V3 Cold Logic)")
        print(f"⚡ Zone 2: {z2:02d} (Markov Transition)")
        print("-" * 60)
        print("💡 Why this combination?")
        print("   1. Zone 1 uses 'Cold Numbers' to maximize theoretical payout (EV).")
        print("   2. Zone 2 uses 'Transition Probability' to seek a small statistical edge.")
        print("="*60)
        return z1, z2

if __name__ == "__main__":
    predictor = StrongestSinglePredictor()
    predictor.predict()
