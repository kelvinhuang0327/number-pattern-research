#!/usr/bin/env python3
"""
Backtest Twin Strike Structure (N=150)
Strategy: Buy 2 Tickets ($200) per draw.
- Ticket A: V3 Rank 1,3,5,7,9,11 + Z2 Rank 1
- Ticket B: V3 Rank 2,4,6,8,10,12 + Z2 Rank 2
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

class BacktestTwinStrike:
    def __init__(self):
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery.db'))
        self.draws = self.db.get_all_draws('POWER_LOTTO')
        
    def get_v3_candidates_and_z2(self, history):
        # 1. V3 Logic (Cold + Anti-Popular)
        recent = history[-100:]
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
        v3_pool = [x[0] for x in sorted_nums[:12]] # Top 12
        
        # 2. Z2 Logic (Markov Transition)
        z2_data = [d.get('second_zone', d.get('special')) for d in history if d.get('second_zone') or d.get('special')]
        z2_data = [int(x) for x in z2_data if x is not None]
        
        z2_preds = []
        if not z2_data:
            z2_preds = random.sample(range(1, 9), 2)
        else:
            last_val = z2_data[-1]
            full_matrix = np.zeros((9, 9))
            for i in range(len(z2_data)-1):
                 if 1 <= z2_data[i] <= 8:
                    full_matrix[z2_data[i]][z2_data[i+1]] += 1
            
            if np.sum(full_matrix[last_val]) == 0:
                z2_preds = random.sample(range(1, 9), 2)
            else:
                next_probs = full_matrix[last_val] / np.sum(full_matrix[last_val])
                best_indices = np.argsort(next_probs)[::-1][:2]
                z2_preds = [int(x) for x in best_indices]
                
        # Ensure 2 Z2 preds
        while len(z2_preds) < 2:
            remaining = list(set(range(1, 9)) - set(z2_preds))
            z2_preds.append(random.choice(remaining))
            
        return v3_pool, z2_preds[:2]

    def run(self, periods=150):
        print(f"⚔️ Running Twin Strike Backtest (N={periods})...")
        
        total_wins_m3 = 0
        total_z2_hits = 0
        total_cost = periods * 200
        total_prize = 0
        
        wins_distribution = Counter()
        
        for i in range(periods):
            idx = len(self.draws) - periods + i
            target = self.draws[idx]
            history = self.draws[:idx]
            
            try:
                pool, z2s = self.get_v3_candidates_and_z2(history)
                
                # Ticket A: Odd indices (0, 2, 4...)
                ticket_a = set(pool[0::2])
                z2_a = z2s[0]
                
                # Ticket B: Even indices (1, 3, 5...)
                ticket_b = set(pool[1::2])
                z2_b = z2s[1]
                
                # Check Outcome
                actual = set(target['numbers'])
                actual_z2 = target.get('second_zone', target.get('special'))
                
                round_prize = 0
                round_hit = False
                
                # Check A
                hits_a = len(ticket_a & actual)
                if hits_a == 3: round_prize += 100
                elif hits_a == 4: round_prize += 2000
                elif hits_a >= 5: round_prize += 20000 
                if hits_a >= 3: 
                    wins_distribution[hits_a] += 1
                    round_hit = True
                    
                # Check B
                hits_b = len(ticket_b & actual)
                if hits_b == 3: round_prize += 100
                elif hits_b == 4: round_prize += 2000
                elif hits_b >= 5: round_prize += 20000 
                if hits_b >= 3: 
                    wins_distribution[hits_b] += 1
                    round_hit = True
                
                # Check Z2
                if actual_z2 == z2_a or actual_z2 == z2_b:
                    total_z2_hits += 1
                    
                if round_hit: total_wins_m3 += 1
                total_prize += round_prize
                
            except Exception as e:
                # print(e)
                continue

        roi = ((total_prize - total_cost) / total_cost) * 100
        
        print("-" * 60)
        print(f"📊 Twin Strike Results (N={periods})")
        print(f"   Win Rate M3+  : {total_wins_m3/periods*100:.2f}% (Vs Random 2-ticket: ~7.0%)")
        print(f"   Zone 2 Hit    : {total_z2_hits/periods*100:.2f}% (Theoretical: 25.0%)")
        print(f"   Match Dist    : M3:{wins_distribution[3]} | M4:{wins_distribution[4]} | M5:{wins_distribution[5]}")
        print(f"   Financials    : Cost ${total_cost} | Prize ${total_prize} | ROI {roi:.2f}%")
        print("-" * 60)
         
if __name__ == "__main__":
    bt = BacktestTwinStrike()
    bt.run()
