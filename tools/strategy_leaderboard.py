#!/usr/bin/env python3
"""
Power Lotto Strategy Leaderboard (自動策略評分儀表板)
系統化自動回測所有已知預測模型，找出「當前最強 Edge」。

Objectives:
1. 自動同步最近 100/200 期數據。
2. 統一回測各類模型 (頻率、轉移、冷號、包牌)。
3. 提供排序表作為 Ensemble 模型的權重依據。
"""
import os
import sys
import numpy as np
import pandas as pd
from collections import Counter
import random

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

class StrategyLeaderboard:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
        self.db = DatabaseManager(db_path)
        self.all_draws = self.db.get_all_draws('POWER_LOTTO')
        # Ensure draws are sorted by date
        self.all_draws = sorted(self.all_draws, key=lambda x: (x['date'], x['draw']))
        
    def get_hits(self, selection, target):
        return len(set(selection) & set(target))

    # --- Strategy Implementations ---
    
    def strat_frequency_hot(self, history, n_bets=1, window=100):
        """熱門號策略 (Top 6)"""
        recent = history[-window:]
        all_nums = [n for d in recent for n in d['numbers']]
        freq = Counter(all_nums)
        sorted_nums = sorted(range(1, 39), key=lambda x: freq.get(x, 0), reverse=True)
        bets = []
        for i in range(n_bets):
            bets.append(sorted_nums[i*6 : (i+1)*6])
        return bets

    def strat_cold_numbers(self, history, n_bets=1, window=100):
        """冷門號策略 (Top 6)"""
        recent = history[-window:]
        all_nums = [n for d in recent for n in d['numbers']]
        freq = Counter(all_nums)
        sorted_nums = sorted(range(1, 39), key=lambda x: freq.get(x, 0))
        bets = []
        for i in range(n_bets):
            bets.append(sorted_nums[i*6 : (i+1)*6])
        return bets

    def strat_twin_strike(self, history, window=100):
        """冷號互補 (2注)"""
        return self.strat_cold_numbers(history, n_bets=2, window=window)

    def strat_markov(self, history, n_bets=1):
        """馬可夫轉移策略"""
        # Simplistic implementation: for each ball in last draw, what balls likely follow?
        # Due to 6 balls, this is complex. Simplify: Aggregate all transitions.
        # This is a weak proxy.
        transitions = Counter()
        for i in range(len(history)-1):
            curr_set = set(history[i]['numbers'])
            next_set = history[i+1]['numbers']
            for n in next_set:
                for c in curr_set:
                    transitions[(c, n)] += 1
        
        last_draw = history[-1]['numbers']
        next_scores = Counter()
        for c in last_draw:
            for n in range(1, 39):
                next_scores[n] += transitions.get((c, n), 0)
        
        sorted_nums = sorted(range(1, 39), key=lambda x: next_scores[x], reverse=True)
        bets = []
        for i in range(n_bets):
            bets.append(sorted_nums[i*6 : (i+1)*6])
        return bets

    def run_backtest(self, strategy_func, periods=200, **kwargs):
        hits_3_plus = 0
        total = 0
        
        for i in range(periods):
            idx = len(self.all_draws) - periods + i
            if idx < 100: continue
            
            target = self.all_draws[idx]['numbers']
            history = self.all_draws[:idx]
            
            bets = strategy_func(history, **kwargs)
            
            round_win = False
            for b in bets:
                if self.get_hits(b, target) >= 3:
                    round_win = True
                    break
            
            if round_win:
                hits_3_plus += 1
            total += 1
            
        return hits_3_plus / total if total > 0 else 0

    def generate_report(self, periods=200):
        print(f"\n📊 Power Lotto Strategy Leaderboard (N={periods})")
        print("="*75)
        print(f"{'Strategy Name':<30} | {'Bets':<5} | {'Win Rate':<10} | {'Edge vs Rand'}")
        print("-" * 75)
        
        strategies = [
            ("Cold Complement (Twin Strike)", self.strat_twin_strike, {}, 2),
            ("Frequency (Hot) x2", self.strat_frequency_hot, {"n_bets": 2}, 2),
            ("Markov Transition x2", self.strat_markov, {"n_bets": 2}, 2),
            ("Cold (Bottom 6) x1", self.strat_cold_numbers, {"n_bets": 1}, 1),
            ("Frequency (Hot) x1", self.strat_frequency_hot, {"n_bets": 1}, 1),
            ("Markov Transition x1", self.strat_markov, {"n_bets": 1}, 1),
        ]
        
        # Baselines (Calculated once)
        rand_1 = 0.0435 # Theoretical for M3+
        rand_2 = 0.0855 # Theoretical for M3+
        
        results = []
        for name, func, args, n_bets in strategies:
            rate = self.run_backtest(func, periods=periods, **args)
            baseline = rand_1 if n_bets == 1 else rand_2
            edge = rate - baseline
            results.append((name, n_bets, rate, edge))
            
        # Sort by Win Rate Desc
        results.sort(key=lambda x: x[2], reverse=True)
        
        for name, n_bets, rate, edge in results:
            edge_str = f"{edge*100:+.2f}%"
            print(f"{name:<30} | {n_bets:<5} | {rate*100:8.2f}% | {edge_str}")
            
        print("="*75)
        print(f"Random Baseline: 1-bet={rand_1*100:.2f}%, 2-bet={rand_2*100:.2f}%")

if __name__ == "__main__":
    lb = StrategyLeaderboard()
    lb.generate_report(periods=200)
