#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
今彩539 (Daily 539) 奇偶比組合研究回測
對比不同奇偶比過濾策略對預測準確率的影響 (5/39 規則)
"""

import sqlite3
import json
import random
import numpy as np
from collections import Counter
import sys
import os

# Setup path
sys.path.insert(0, os.getcwd())

from database import DatabaseManager
from common import get_lottery_rules

class OddEvenResearch539:
    def __init__(self):
        self.lottery_type = 'DAILY_539'
        self.rules = get_lottery_rules(self.lottery_type)
        self.min_num = 1
        self.max_num = 39
        self.pick_count = 5

    def get_probabilities(self, history, window=100):
        recent = history[-window:] if len(history) > window else history
        counts = Counter()
        for d in recent:
            counts.update(d.get('numbers', []))
        total = len(recent) * self.pick_count
        probs = {n: (counts.get(n, 0) + 1) / (total + self.max_num) for n in range(self.min_num, self.max_num + 1)}
        return probs

    def calculate_entropy_score(self, numbers):
        sorted_nums = sorted(numbers)
        gaps = [sorted_nums[i+1] - sorted_nums[i] for i in range(len(sorted_nums)-1)]
        return 100 - np.std(gaps) * 8 # Adjusted scale for 5 nums

    def calculate_anti_consensus_score(self, numbers):
        birthday_count = sum(1 for n in numbers if 1 <= n <= 31)
        score = 100 - (birthday_count * 15)
        return max(0, score)

    def generate_bets(self, history, mode='none', num_bets=8, num_simulations=1000):
        probs = self.get_probabilities(history)
        all_nums = list(range(self.min_num, self.max_num + 1))
        candidates = []
        
        for _ in range(num_simulations):
            if mode == 'fixed_balanced':
                target_odd = random.choice([2, 3])
            elif mode == 'top_3':
                target_odd = random.choice([1, 2, 3, 4])
            else:
                target_odd = None

            if target_odd is not None:
                odds = [n for n in all_nums if n % 2 != 0]
                evens = [n for n in all_nums if n % 2 == 0]
                odd_p = np.array([probs[n] for n in odds]); odd_p /= odd_p.sum()
                even_p = np.array([probs[n] for n in evens]); even_p /= even_p.sum()
                try:
                    s_odds = np.random.choice(odds, size=target_odd, replace=False, p=odd_p).tolist()
                    s_evens = np.random.choice(evens, size=self.pick_count - target_odd, replace=False, p=even_p).tolist()
                    comb = sorted(s_odds + s_evens)
                except: continue
            else:
                p = np.array([probs[n] for n in all_nums]); p /= p.sum()
                comb = sorted(np.random.choice(all_nums, size=self.pick_count, replace=False, p=p).tolist())

            p_score = sum(probs[n] for n in comb) * 1000
            e_score = self.calculate_entropy_score(comb)
            a_score = self.calculate_anti_consensus_score(comb)
            total_score = (p_score * 0.4 + e_score * 0.3 + a_score * 0.3)
            candidates.append((comb, total_score))

        candidates.sort(key=lambda x: x[1], reverse=True)
        unique_bets = []
        seen = set()
        for c, s in candidates:
            if tuple(c) not in seen:
                unique_bets.append(c)
                seen.add(tuple(c))
            if len(unique_bets) >= num_bets: break
        return unique_bets

def run_backtest():
    db = DatabaseManager(db_path="data/lottery_v2.db")
    all_draws = db.get_all_draws('DAILY_539')
    all_draws.sort(key=lambda x: x['date'])
    
    test_data = [d for d in all_draws if str(d.get('date', '')).startswith('2025')]
    train_data = [d for d in all_draws if d not in test_data]
    
    print(f"🚀 開始 今彩539 研究回測 (2025年, {len(test_data)}期, 每期8注)")
    
    modes = ['none', 'fixed_balanced', 'top_3']
    results = {m: {'wins': 0, 'draws': 0} for m in modes}
    strategy = OddEvenResearch539()

    for i, target in enumerate(test_data):
        history = train_data + test_data[:i]
        actual = set(target['numbers'])
        
        for mode in modes:
            bets = strategy.generate_bets(history, mode=mode)
            for bet in bets:
                if len(set(bet) & actual) >= 2: # 539 中2就有獎
                    results[mode]['wins'] += 1
            results[mode]['draws'] += 1
        
        if (i+1) % 50 == 0: print(f"   已處理 {i+1}/{len(test_data)} 期...")

    print("\n" + "="*60)
    print("🏆 今彩539 奇偶組合回測報告 (2025)")
    print("-" * 60)
    for mode in modes:
        res = results[mode]
        win_rate = res['wins'] / (res['draws'] * 8) * 100
        print(f"{mode:15} | 勝率: {win_rate:6.2f}% | 中獎注數: {res['wins']}")
    print("="*60)

if __name__ == '__main__':
    run_backtest()
