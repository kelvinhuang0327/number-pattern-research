#!/usr/bin/env python3
"""
Strategy Leaderboard (自動策略評分儀表板)
系統化自動回測所有已知預測模型，找出「當前最強 Edge」。
支持多種彩種 (POWER_LOTTO, BIG_LOTTO)。
"""
import os
import sys
import numpy as np
from collections import Counter
import random
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

class StrategyLeaderboard:
    def __init__(self, lottery_type='POWER_LOTTO', db_path=None):
        if db_path is None:
            db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
        self.db = DatabaseManager(db_path)
        self.lottery_type = lottery_type
        self.draws = self.db.get_all_draws(lottery_type)
        self.draws = sorted(self.draws, key=lambda x: (x['date'], x['draw']))
        
        # Determine rules and baselines (經驗證的隨機基準)
        if lottery_type == 'BIG_LOTTO':
            self.max_num = 49
            self.rand_win_1 = 0.0178  # 6/49 單注 M3+ ≈ 1.78%
            self.rand_win_2 = 0.0350  # 2注不重疊 M3+ ≈ 3.50% (實測驗證)
        else:
            self.max_num = 38
            self.rand_win_1 = 0.0435
            self.rand_win_2 = 0.0855
            
    def get_hits(self, selection, target):
        return len(set(selection) & set(target))

    # --- Strategy Implementations ---
    
    def strat_frequency_hot(self, history, n_bets=1, window=100):
        """熱門號策略"""
        recent = history[-window:]
        all_nums = [n for d in recent for n in d['numbers']]
        freq = Counter(all_nums)
        sorted_nums = sorted(range(1, self.max_num + 1), key=lambda x: freq.get(x, 0), reverse=True)
        bets = []
        for i in range(n_bets):
            bets.append(sorted_nums[i*6 : (i+1)*6])
        return bets

    def strat_cold_numbers(self, history, n_bets=1, window=100):
        """冷門號策略"""
        recent = history[-window:]
        all_nums = [n for d in recent for n in d['numbers']]
        freq = Counter(all_nums)
        sorted_nums = sorted(range(1, self.max_num + 1), key=lambda x: freq.get(x, 0))
        bets = []
        for i in range(n_bets):
            bets.append(sorted_nums[i*6 : (i+1)*6])
        return bets

    def strat_twin_strike(self, history, n_bets=2, window=100):
        """冷號互補 (2注)"""
        return self.strat_cold_numbers(history, n_bets=2, window=window)

    def strat_cluster_pivot(self, history, n_bets=2, window=150):
        """聚類中心分析 (常用於大樂透)"""
        recent = history[-window:]
        cooccur = Counter()
        for d in recent:
            nums = sorted(d['numbers'])
            for pair in combinations(nums, 2):
                cooccur[pair] += 1
                
        num_scores = Counter()
        for (a, b), count in cooccur.items():
            num_scores[a] += count
            num_scores[b] += count
        centers = [num for num, _ in num_scores.most_common(n_bets)]
        
        bets = []
        exclude = set()
        for center in centers:
            candidates = Counter()
            for (a, b), count in cooccur.items():
                if a == center and b not in exclude: candidates[b] += count
                elif b == center and a not in exclude: candidates[a] += count
            
            # Expand to 6 numbers
            bet = [center]
            for n, _ in candidates.most_common(5):
                bet.append(n)
            
            # Fill if needed
            if len(bet) < 6:
                for n in range(1, self.max_num + 1):
                    if n not in bet and n not in exclude:
                        bet.append(n)
                    if len(bet) == 6: break
            
            bets.append(sorted(bet))
            exclude.update(bet[:2]) # Inter-ticket coverage diversity
        return bets

    def strat_markov(self, history, n_bets=1, window=100):
        """馬可夫轉移策略"""
        recent = history[-window:]
        transitions = Counter()
        for i in range(len(recent)-1):
            curr_set = set(recent[i]['numbers'])
            next_set = recent[i+1]['numbers']
            for n in next_set:
                for c in curr_set:
                    transitions[(c, n)] += 1
        
        last_draw = history[-1]['numbers']
        next_scores = Counter()
        for c in last_draw:
            for n in range(1, self.max_num + 1):
                next_scores[n] += transitions.get((c, n), 0)
        
        sorted_nums = sorted(range(1, self.max_num + 1), key=lambda x: next_scores[x], reverse=True)
        bets = []
        for i in range(n_bets):
            bets.append(sorted_nums[i*6 : (i+1)*6])
        return bets

    def strat_random(self, history, n_bets=1, **kwargs):
        """完全隨機 (對照組)"""
        bets = []
        for i in range(n_bets):
            bets.append(random.sample(range(1, self.max_num + 1), 6))
        return bets

    def strat_apriori(self, history, n_bets=2, window=150):
        """關聯規則策略 (Apriori 簡化版)"""
        recent = history[-window:]
        pair_counts = Counter()
        for d in recent:
            nums = sorted(d['numbers'])
            for pair in combinations(nums, 2): pair_counts[pair] += 1
            
        # Simplistic rule: If A appears, what B is most likely?
        # Use top pairs as "seeds"
        top_pairs = [p for p, _ in pair_counts.most_common(n_bets)]
        
        bets = []
        for seed_pair in top_pairs:
            # Expand seed pair into 6 numbers using freq or cooccur
            bet = list(seed_pair)
            exclude = set(bet)
            candidates = Counter()
            for (a, b), count in pair_counts.items():
                if a in bet and b not in exclude: candidates[b] += count
                elif b in bet and a not in exclude: candidates[a] += count
            
            for n, _ in candidates.most_common(4):
                bet.append(n)
            
            # Fill if needed
            if len(bet) < 6:
                for n in range(1, self.max_num + 1):
                    if n not in bet: bet.append(n)
                    if len(bet) == 6: break
            bets.append(sorted(bet))
        return bets

    def run_backtest(self, strategy_func, periods=150, **kwargs):
        hits_3_plus = 0
        total = 0
        for i in range(periods):
            idx = len(self.draws) - periods + i
            if idx <= 0: continue
            
            target = self.draws[idx]['numbers']
            history = self.draws[:idx]
            
            if len(history) < 150: continue # Standardize for Big Lotto
            
            bets = strategy_func(history, **kwargs)
            
            win = False
            for b in bets:
                if self.get_hits(b, target) >= 3:
                    win = True
                    break
            if win:
                hits_3_plus += 1
            total += 1
            
        return hits_3_plus / total if total > 0 else 0

    def generate_report(self, periods=150):
        if len(self.draws) < periods + 150:
            print(f"⚠️ Warning: Not enough history for {self.lottery_type}. Required: {periods + 150}, Found: {len(self.draws)}")
            
        print(f"\n📊 Strategy Leaderboard: {self.lottery_type} (N={periods})")
        print("="*75)
        print(f"{'Strategy Name':<30} | {'Bets':<5} | {'Win Rate':<10} | {'Edge vs Rand'}")
        print("-" * 75)
        
        strategies = [
            ("Cold Complement (Twin Strike)", self.strat_twin_strike, {"window": 150}, 2),
            ("Frequency (Hot) x2", self.strat_frequency_hot, {"n_bets": 2, "window": 150}, 2),
            ("Markov Transition x2", self.strat_markov, {"n_bets": 2, "window": 150}, 2),
            ("Random (Baseline) x2", self.strat_random, {"n_bets": 2}, 2),
        ]
        
        if self.lottery_type == 'BIG_LOTTO':
            strategies.append(("Cluster Pivot x2", self.strat_cluster_pivot, {"n_bets": 2, "window": 150}, 2))
            strategies.append(("Apriori (Top Pairs) x2", self.strat_apriori, {"n_bets": 2, "window": 150}, 2))
        
        if self.lottery_type == 'BIG_LOTTO':
            strategies.append(("Cluster Pivot x2", self.strat_cluster_pivot, {"n_bets": 2, "window": 150}, 2))
        
        results = []
        for name, func, args, n_bets in strategies:
            rate = self.run_backtest(func, periods=periods, **args)
            baseline = self.rand_win_1 if n_bets == 1 else self.rand_win_2
            edge = rate - baseline
            results.append((name, n_bets, rate, edge))
            
        results.sort(key=lambda x: x[2], reverse=True)
        for name, n_bets, rate, edge in results:
            edge_str = f"{edge*100:+.2f}%"
            print(f"{name:<30} | {n_bets:<5} | {rate*100:8.2f}% | {edge_str}")
            
        print("="*75)
        print(f"Random Baseline: 1-bet={self.rand_win_1*100:.2f}%, 2-bet={self.rand_win_2*100:.2f}%")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', default='POWER_LOTTO')
    parser.add_argument('--n', type=int, default=150)
    args = parser.parse_args()
    
    lb = StrategyLeaderboard(lottery_type=args.lottery)
    lb.generate_report(periods=args.n)
