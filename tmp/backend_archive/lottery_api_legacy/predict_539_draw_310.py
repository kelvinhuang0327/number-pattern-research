#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
今彩539 第114000310期 預測腳本
基於研究出的最優組合：Top-3 奇偶過濾 + 高級評分權重 (40:30:30)
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

class Daily539Predictor310:
    def __init__(self):
        self.lottery_type = 'DAILY_539'
        self.min_num = 1
        self.max_num = 39
        self.pick_count = 5
        self.db = DatabaseManager(db_path="data/lottery_v2.db")

    def get_probabilities(self, history, window=100):
        recent = history[-window:]
        counts = Counter()
        for d in recent:
            counts.update(d.get('numbers', []))
        total = len(recent) * self.pick_count
        probs = {n: (counts.get(n, 0) + 1) / (total + self.max_num) for n in range(self.min_num, self.max_num + 1)}
        return probs

    def calculate_entropy_score(self, numbers):
        sorted_nums = sorted(numbers)
        gaps = [sorted_nums[i+1] - sorted_nums[i] for i in range(len(sorted_nums)-1)]
        std_val = np.std(gaps)
        # 539 理想差距約 7.8, 方差小表示號碼分佈均勻
        return 100 - std_val * 8

    def calculate_anti_consensus_score(self, numbers):
        # 避開常見生日號碼 (1-31)
        birthday_count = sum(1 for n in numbers if 1 <= n <= 31)
        score = 100 - (birthday_count * 15)
        return max(0, score)

    def generate_prediction(self, num_bets=8, num_simulations=50000):
        all_draws = self.db.get_all_draws(self.lottery_type)
        all_draws.sort(key=lambda x: x['date']) # 有些日期可能是 2025/12/20 格式
        history = all_draws
        
        probs = self.get_probabilities(history)
        all_nums = list(range(self.min_num, self.max_num + 1))
        candidates = []
        
        print(f"📊 正在進行 {num_simulations} 次蒙地卡羅模擬...")
        
        for _ in range(num_simulations):
            # 採用研究出的 Top-3 策略：允許奇數個數為 1, 2, 3, 4
            target_odd = random.choice([1, 2, 3, 4])
            
            odds = [n for n in all_nums if n % 2 != 0]
            evens = [n for n in all_nums if n % 2 == 0]
            
            odd_p = np.array([probs[n] for n in odds]); odd_p /= odd_p.sum()
            even_p = np.array([probs[n] for n in evens]); even_p /= even_p.sum()
            
            try:
                s_odds = np.random.choice(odds, size=target_odd, replace=False, p=odd_p).tolist()
                s_evens = np.random.choice(evens, size=self.pick_count - target_odd, replace=False, p=even_p).tolist()
                comb = sorted(s_odds + s_evens)
            except: continue

            p_score = sum(probs[n] for n in comb) * 1000
            e_score = self.calculate_entropy_score(comb)
            a_score = self.calculate_anti_consensus_score(comb)
            
            # 使用最優權重：40% 概率 + 30% 熵值 + 30% 反共識
            total_score = (p_score * 0.4 + e_score * 0.3 + a_score * 0.3)
            candidates.append((comb, total_score, target_odd))

        # 按分數排序並去重
        candidates.sort(key=lambda x: x[1], reverse=True)
        final_bets = []
        seen = set()
        for c, s, o in candidates:
            if tuple(c) not in seen:
                final_bets.append({'numbers': c, 'score': s, 'odd_count': o})
                seen.add(tuple(c))
            if len(final_bets) >= num_bets: break
            
        return final_bets

def run_prediction():
    predictor = Daily539Predictor310()
    results = predictor.generate_prediction()
    
    print("\n" + "="*80)
    print("🎯 今彩 539 第 114000310 期 推薦號碼 (進階研究優化版)")
    print("="*80)
    print(f"{'序號':<4} | {'推薦組合':<20} | {'奇偶比':<8} | {'綜合得分'}")
    print("-" * 80)
    
    for i, res in enumerate(results):
        nums_str = ", ".join([f"{n:02d}" for n in res['numbers']])
        odd_even = f"{res['odd_count']}奇{5-res['odd_count']}偶"
        print(f"注 {i+1:<2} | {nums_str:<20} | {odd_even:<8} | {res['score']:.1f}")
    
    print("="*80)
    print("💡 策略說明：")
    print("  - 使用蒙地卡羅模擬採樣與多目標優化評分。")
    print("  - 套用 4:3:3 權重配置 (概率、分佈均勻度、反共識度)。")
    print("  - 強制過濾極端奇偶比 (避開 0:5 與 5:0)。")
    print("="*80)

if __name__ == '__main__':
    run_prediction()
