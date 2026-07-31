#!/usr/bin/env python3
"""
Double Ticket Predictor (The "Twin Strike" Strategy)
Goal: Optimize for the common $200 budget (2 Tickets).

Strategy:
1. Zone 1: Select Top 12 "High EV" candidates (Cold/High). 
   - Split into Ticket A and Ticket B (Interleaved).
   - Covers 12 unique numbers (31% of the board).
2. Zone 2: Hedge betting.
   - Ticket A: Primary Markov Prediction.
   - Ticket B: Secondary Markov Prediction.
   - Doubles Zone 2 hit rate from 12.5% to 25%.
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

class DoublePredictor:
    def __init__(self):
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery.db'))
        self.draws = self.db.get_all_draws('POWER_LOTTO')
        
    def get_v3_candidates(self):
        """Get best 12 numbers using V3 Logic"""
        recent = self.draws[-100:]
        all_nums = [x for d in recent for x in d['numbers']]
        counts = Counter(all_nums)
        avg_freq = sum(counts.values()) / 38
        
        scores = {}
        for n in range(1, 39):
            f = counts.get(n, 0)
            score = f * 10
            if n <= 31: score += 10
            else:
                if f < avg_freq: score -= 10
                else: score += 5
            scores[n] = score
            
        sorted_nums = sorted(scores.items(), key=lambda x: x[1])
        # Top 12 candidates
        candidates = [x[0] for x in sorted_nums[:12]]
        return candidates

    def get_z2_predictions(self):
        """Get Top 2 Zone 2 numbers"""
        z2_data = [d.get('second_zone', d.get('special')) for d in self.draws if d.get('second_zone') or d.get('special')]
        z2_data = [int(x) for x in z2_data if x is not None]
        
        if not z2_data: return [1, 2]
        
        last_val = z2_data[-1]
        
        full_matrix = np.zeros((9, 9))
        for i in range(len(z2_data)-1):
             if 1 <= z2_data[i] <= 8:
                full_matrix[z2_data[i]][z2_data[i+1]] += 1
        
        if np.sum(full_matrix[last_val]) == 0:
            return random.sample(range(1, 9), 2)
            
        next_probs = full_matrix[last_val] / np.sum(full_matrix[last_val])
        best_indices = np.argsort(next_probs)[::-1][:2]
        return [int(x) for x in best_indices]

    def predict(self):
        pool = self.get_v3_candidates()
        z2_preds = self.get_z2_predictions()
        
        # Ensure we have 2 Z2 preds
        while len(z2_preds) < 2:
            remaining = list(set(range(1, 9)) - set(z2_preds))
            z2_preds.append(random.choice(remaining))
            
        # Strategy: Interleave the pool to balance "Best" and "Next Best"
        # Pool is sorted by Score (Best First)
        # Ticket A: 1st, 3rd, 5th, 7th, 9th, 11th
        # Ticket B: 2nd, 4th, 6th, 8th, 10th, 12th
        
        ticket_a = sorted(pool[0::2])
        ticket_b = sorted(pool[1::2])
        
        print("\n" + "="*60)
        print("⚔️ Twin Strike Prediction (2 Tickets - $200)")
        print("="*60)
        
        print(f"🎫 Ticket A (Alpha): {ticket_a}")
        print(f"   Zone 2: {z2_preds[0]:02d} (Primary Target)")
        
        print("\n" + "-"*30 + "\n")
        
        print(f"🎫 Ticket B (Beta) : {ticket_b}")
        print(f"   Zone 2: {z2_preds[1]:02d} (Hedge Target)")
        
        print("="*60)
        print("💡 Why 2 Tickets?")
        print("   1. Coverage: You cover 12 numbers (31% of Zone 1).")
        print("   2. Hedging: You cover Top 2 likely Zone 2 outcomes (25% chance).")
        print("   3. Efficiency: Optimized for standard betting budget.")
        print("="*60)

if __name__ == "__main__":
    predictor = DoublePredictor()
    predictor.predict()
