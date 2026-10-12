#!/usr/bin/env python3
"""
Backtest Smart Wheel System (150 Periods)
Goal: Verify the performance (Win Rate & ROI) of the "Smart Wheel" strategy (15-Number Pool, 11 Tickets).

Optimization:
The combinatorial structure of a wheel is agnostic to the specific numbers.
We preserve the "Index Pattern" from one generation and reuse it for all draws.
"""
import sys
import os
import random
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from tools.smart_wheel_system import SmartWheel
from tools.reverse_optimization_anti_popular import ReverseOptimizerV2

class SmartWheelBacktest:
    def __init__(self):
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery.db'))
        self.all_draws = self.db.get_all_draws('POWER_LOTTO')
        self.wheel_tool = SmartWheel()
        self.strategy_tool = ReverseOptimizerV2()
        
    def get_balanced_template(self):
        """
        Generate a static index-based wheel template for 15 numbers.
        Returns a list of tuples, e.g., [(0,1,2,3,4,5), (0,1,6,7,8,9)...]
        """
        print("⚙️ Pre-calculating Wheel Template for 15 numbers...")
        # Use dummy pool 0-14
        dummy_pool = list(range(15))
        # Guarantee 3 if 5 matches
        tickets = self.wheel_tool.generate_wheel(dummy_pool, guarantee_hits=3, if_numbers_drawn=5, numbers_per_ticket=6)
        print(f"✅ Template Ready: {len(tickets)} tickets pattern.")
        return tickets

    def run(self, periods=150):
        print(f"⚔️ Running Smart Wheel Backtest (N={periods})...")
        
        # 1. Get Template
        template = self.get_balanced_template()
        tickets_per_draw = len(template)
        cost_per_draw = tickets_per_draw * 100
        
        total_cost = 0
        total_prize = 0
        total_wins = 0 # Rounds with at least one win
        
        matches = Counter()
        
        # Prizes (Approx Taiwan Power Lotto)
        # M3 + Z0 = 100
        # M3 + Z1 = 0? (Actually strict rules: 3+0=100, 3+1=?, let's simplify)
        # Simplified:
        # Match 3 (Zone 1): $100
        # Match 4 (Zone 1): $2000 (Approx)
        # Match 5 (Zone 1): $20000 (Approx)
        # Match 6 (Zone 1): Jackpot
        # Note: Zone 2 affects prize, but we test Zone 1 Wheel here.
        # Let's assume Z2 is random for prize calculation or just track Match counts.
        
        draw_results = []

        for i in range(periods):
            idx = len(self.all_draws) - periods + i
            target = self.all_draws[idx]
            history = self.all_draws[:idx]
            
            # --- Generate V3 Pool (15 Numbers) ---
            # Re-implement V3 logic for pool selection
            # Logic: Last 100 draws freq
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
            pool = [x[0] for x in sorted_nums[:15]] # Top 15 Cold/High
            
            # --- Map Template to Pool ---
            current_tickets = []
            for t_indices in template:
                # Map index to number
                ticket = [pool[i] for i in t_indices]
                current_tickets.append(set(ticket))
                
            # --- Check Win ---
            actual = set(target['numbers'])
            
            round_won = False
            round_prize = 0
            round_max_match = 0
            
            for ticket in current_tickets:
                m = len(ticket & actual)
                if m > round_max_match: round_max_match = m
                
                if m == 3: round_prize += 100
                elif m == 4: round_prize += 2000
                elif m == 5: round_prize += 20000
                elif m == 6: round_prize += 1000000 # Jackpot proxy
                
                if m >= 3: round_won = True
                
            matches[round_max_match] += 1
            if round_won: total_wins += 1
            
            total_cost += cost_per_draw
            total_prize += round_prize
            
            draw_val = target.get('draw', target.get('period', 'Unknown'))
            # Print significant wins
            if round_max_match >= 4:
                print(f"Draw {draw_val}: Pool Hit {len(set(pool) & actual)} -> Best Ticket Match {round_max_match} (Prize ${round_prize})")

        # Report
        roi = ((total_prize - total_cost) / total_cost) * 100
        win_rate = (total_wins / periods) * 100
        
        print("-" * 60)
        print(f"📊 Smart Wheel Results (N={periods})")
        print(f"   Structure   : 15 Numbers -> {tickets_per_draw} Tickets (Cost ${cost_per_draw}/draw)")
        print(f"   Win Rate    : {win_rate:.2f}% (Rounds with at least one winning ticket)")
        print(f"   Match Dist  : M3:{matches[3]} | M4:{matches[4]} | M5:{matches[5]} | M6:{matches[6]}")
        print(f"   Financials  : Cost ${total_cost} | Prize ${total_prize} | ROI {roi:.2f}%")
        print("-" * 60)
        print("💡 Analysis:")
        print("   - Compare Win Rate to Single Ticket (3.5%).")
        print("   - Did we catch any M4 or M5 big prizes?")

if __name__ == "__main__":
    bt = SmartWheelBacktest()
    bt.run()
