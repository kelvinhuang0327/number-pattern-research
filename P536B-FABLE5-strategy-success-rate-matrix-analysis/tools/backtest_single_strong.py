#!/usr/bin/env python3
"""
Backtest Strongest Single Ticket (N=200)
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
from tools.predict_single_strong import StrongestSinglePredictor

class BacktestSingle:
    def __init__(self):
        self.predictor = StrongestSinglePredictor()
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery.db'))
        self.draws = self.db.get_all_draws('POWER_LOTTO')
        
    def run(self, periods=200):
        print(f"⚔️ Running Single Ticket Backtest (N={periods})...")
        wins = 0
        z2_wins = 0
        rand_wins = 0
        
        for i in range(periods):
            # Hack: Mock the internal 'draws' of predictor to be 'history'
            idx = len(self.draws) - periods + i
            target = self.draws[idx]
            history = self.draws[:idx]
            self.predictor.draws = history # Inject history
            
            # Predict
            try:
                p1 = self.predictor.get_v3_selection()
                p2 = self.predictor.get_z2_prediction()
                
                # Check
                actual = set(target['numbers'])
                actual_z2 = target.get('second_zone', target.get('special'))
                
                hits = len(actual & set(p1))
                if hits >= 3: wins += 1
                if p2 == actual_z2: z2_wins += 1
                
                # Random comparison
                r1 = set(random.sample(range(1, 39), 6))
                if len(actual & r1) >= 3: rand_wins += 1
                
            except Exception as e:
                # print(e)
                continue
                
        print(f"📊 Results (N={periods})")
        print(f"   Win Rate (M3+) : {wins/periods*100:.2f}% (Vs Random: {rand_wins/periods*100:.2f}%)")
        print(f"   Zone 2 Accuracy: {z2_wins/periods*100:.2f}% (Random Exp: 12.50%)")
        print("-" * 40)
        
        if z2_wins/periods > 0.14:
            print("✅ Zone 2 Edge Confirmed (>12.5%)")
        else:
            print("⚠️ Zone 2 Edge NOT Confirmed (<=12.5%)")

if __name__ == "__main__":
    bt = BacktestSingle()
    bt.run()
