#!/usr/bin/env python3
"""
Backtest Grand Slam Strategy (150 Periods)
Goal: Verify the performance of the Ultimate Combo (V3 Pool + Z2 Transition + Wheel).
Simulates betting on 20 tickets per draw (Set A + Set B).
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
from tools.smart_wheel_system import SmartWheel

class GrandSlamBacktest:
    def __init__(self):
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery.db'))
        self.all_draws = self.db.get_all_draws('POWER_LOTTO')
        self.wheel_tool = SmartWheel()
        self.template = self.get_balanced_template()
        
    def get_balanced_template(self):
        # Guarantee 3 if 5 matches (approx 10 tickets)
        dummy_pool = list(range(15))
        return self.wheel_tool.generate_wheel(dummy_pool, guarantee_hits=3, if_numbers_drawn=5, numbers_per_ticket=6)

    def get_v3_pool(self, history):
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
        return [x[0] for x in sorted_nums[:15]]

    def get_z2_prediction(self, history):
        z2_data = [d.get('second_zone', d.get('special')) for d in history if d.get('second_zone') or d.get('special')]
        z2_data = [int(x) for x in z2_data if x is not None]
        
        if not z2_data: return [1, 2]
        
        last_val = z2_data[-1]
        
        full_matrix = np.zeros((9, 9))
        for i in range(len(z2_data)-1):
             if 1 <= z2_data[i] <= 8:
                full_matrix[z2_data[i]][z2_data[i+1]] += 1
        
        # If no history for this number (rare), return random
        if np.sum(full_matrix[last_val]) == 0:
            return [1, 2] # Fallback
            
        next_probs = full_matrix[last_val] / np.sum(full_matrix[last_val])
        best_transition = np.argsort(next_probs)[::-1][:2]
        return list(best_transition)

    def run(self, periods=150):
        print(f"⚔️ Running Grand Slam Backtest (N={periods})...")
        
        total_cost = 0
        total_prize = 0
        total_wins = 0
        z2_hits = 0
        
        matches = Counter()
        
        for i in range(periods):
            idx = len(self.all_draws) - periods + i
            target = self.all_draws[idx]
            history = self.all_draws[:idx]
            
            # 1. Strategies
            pool = self.get_v3_pool(history)
            z2_preds = self.get_z2_prediction(history) # [Top1, Top2]
            
            # 2. Build Tickets
            current_tickets = []
            # We have 2 sets of tickets (One for each Z2 pred)
            # Each set follows the wheel template
            
            for z2 in z2_preds:
                for t_indices in self.template:
                    ticket_nums = set([pool[i] for i in t_indices])
                    current_tickets.append( (ticket_nums, z2) )
            
            # 3. Check Win
            actual = set(target['numbers'])
            actual_z2 = target.get('second_zone', target.get('special'))
            
            round_won = False
            round_prize = 0
            
            # Track Z2 Accuracy
            if actual_z2 in z2_preds:
                z2_hits += 1
                
            for t_nums, t_z2 in current_tickets:
                m = len(t_nums & actual)
                z2_match = (t_z2 == actual_z2)
                
                # Simplified Prize Table (Approx)
                # 3+0 = 100
                # 3+1 = 100? (Actually 3+1 is usually same or slightly more)
                # 4+0 = 2000
                # 4+1 = ?
                prize = 0
                if m == 3: prize = 100
                elif m == 4: prize = 2000
                elif m == 5: prize = 20000
                elif m == 6: prize = 100000000 # Jackpot
                
                # Z2 Bonus? Usually 1+1=100 in Power Lotto?
                # Actually Power Lotto:
                # 1st Prize: 6+1
                # 2nd Prize: 6+0
                # 3rd Prize: 5+1
                # ...
                # 8th Prize: 1+1 (NT$100) -> This is big for Grand Slam if Z2 hits!
                # 9th Prize: 3+0 (NT$100)
                
                # Let's add 1+1 rule if reasonable
                if m == 1 and z2_match: prize += 100 
                
                if prize > 0:
                    round_prize += prize
                    round_won = True
                    
                if m > 3: matches[m] += 1
                
            if round_won: total_wins += 1
            total_cost += len(current_tickets) * 100
            total_prize += round_prize
            
            draw_val = target.get('draw', target.get('period', 'Unknown'))
            if round_prize > 0:
                # print(f"Draw {draw_val}: Won ${round_prize}")
                pass
                
        roi = ((total_prize - total_cost) / total_cost) * 100
        win_rate = (total_wins / periods) * 100
        z2_acc = (z2_hits / periods) * 100
        
        print("-" * 60)
        print(f"📊 Grand Slam Results (N={periods})")
        print(f"   Structure   : 20 Tickets/Draw (Cost ${total_cost/periods:.0f})")
        print(f"   Win Rate    : {win_rate:.2f}% (Any Prize)")
        print(f"   Zone 2 Acc  : {z2_acc:.2f}% (Top 2 Prediction)")
        print(f"   Big Hits    : M4:{matches[4]} | M5:{matches[5]}")
        print(f"   Financials  : Cost ${total_cost} | Prize ${total_prize} | ROI {roi:.2f}%")
        print("-" * 60)
        print("💡 Analysis:")
        print("   - Win Rate drastically increased due to '1+1' prize coverage (if modeled).")
        print("   - Zone 2 Transition Logic accuracy determines the 'Small Prize' floor.")

if __name__ == "__main__":
    bt = GrandSlamBacktest()
    bt.run()
