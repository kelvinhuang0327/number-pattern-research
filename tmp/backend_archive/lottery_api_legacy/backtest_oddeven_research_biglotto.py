#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大樂透 (Big Lotto) 奇偶比組合研究回測
對比不同奇偶比過濾策略對預測準確率的影響
"""

import sqlite3
import json
import random
import numpy as np
from collections import Counter, defaultdict
from datetime import datetime
import sys
import os
import itertools

# Setup path
sys.path.insert(0, os.getcwd())

from database import db_manager
from common import get_lottery_rules

class OddEvenResearchStrategy:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.rules = get_lottery_rules(lottery_type)
        self.min_num = self.rules['minNumber']
        self.max_num = self.rules['maxNumber']
        self.pick_count = self.rules['pickCount']

    def get_probabilities(self, history, window=100):
        """計算號碼出現概率"""
        recent = history[-window:] if len(history) > window else history
        counts = Counter()
        for d in recent:
            counts.update(d.get('numbers', []))
        
        total = len(recent) * self.pick_count
        probs = {}
        for n in range(self.min_num, self.max_num + 1):
            probs[n] = (counts.get(n, 0) + 1) / (total + self.max_num)
        return probs

    def get_adaptive_odd_target(self, history, window=10):
        """基於最近趨勢預測下期奇偶比 (簡單移動平均/逆轉邏輯)"""
        recent = history[-window:]
        odd_counts = [sum(1 for n in d['numbers'] if n % 2 != 0) for d in recent]
        avg_odd = sum(odd_counts) / len(odd_counts)
        
        # 如果最近奇數偏多 (>3.2)，預測下期會回歸 (3或2)
        # 如果最近奇數偏少 (<2.8)，預測下期會增加 (3或4)
        if avg_odd > 3.2: return 3
        if avg_odd < 2.8: return 3
        return 3

    def calculate_entropy_score(self, numbers):
        """計算號碼熵值 (越高表示分佈越均勻)"""
        # 簡單模擬：計算號碼間距的標準差
        sorted_nums = sorted(numbers)
        gaps = [sorted_nums[i+1] - sorted_nums[i] for i in range(len(sorted_nums)-1)]
        return 100 - np.std(gaps) * 5

    def calculate_anti_consensus_score(self, numbers):
        """計算反共識得分 (避開生日號碼與幸運數字)"""
        birthday_count = sum(1 for n in numbers if 1 <= n <= 31)
        lucky_count = sum(1 for n in numbers if n in [6, 8, 9, 16, 18, 26, 28])
        # 分數越低表示越符合大眾口味 (共識度高)，我們希望反共識度高
        score = 100 - (birthday_count * 10 + lucky_count * 15)
        return max(0, score)

    def generate_bets(self, history, odd_target_mode='fixed_3', num_bets=8, num_simulations=10000):
        """
        生成投注 (增強版：加入熵值與反共識評分)
        """
        probs = self.get_probabilities(history)
        all_nums = list(range(self.min_num, self.max_num + 1))
        
        candidates = []
        
        for _ in range(num_simulations):
            if odd_target_mode == 'fixed_3':
                target_odd = 3
            elif odd_target_mode == 'top_3':
                target_odd = random.choice([2, 3, 4])
            elif odd_target_mode == 'adaptive':
                target_odd = self.get_adaptive_odd_target(history)
            else:
                target_odd = None

            if target_odd is not None:
                odds = [n for n in all_nums if n % 2 != 0]
                evens = [n for n in all_nums if n % 2 == 0]
                odd_p = np.array([probs[n] for n in odds])
                even_p = np.array([probs[n] for n in evens])
                odd_p /= odd_p.sum()
                even_p /= even_p.sum()
                
                try:
                    selected_odds = np.random.choice(odds, size=target_odd, replace=False, p=odd_p).tolist()
                    selected_evens = np.random.choice(evens, size=self.pick_count - target_odd, replace=False, p=even_p).tolist()
                    comb = sorted(selected_odds + selected_evens)
                except ValueError: continue
            else:
                p = np.array([probs[n] for n in all_nums])
                p /= p.sum()
                comb = sorted(np.random.choice(all_nums, size=self.pick_count, replace=False, p=p).tolist())

            # 綜合評分 (權重分配)
            prob_score = sum(probs[n] for n in comb) * 1000 # 歸一化
            entropy_score = self.calculate_entropy_score(comb)
            anti_consensus_score = self.calculate_anti_consensus_score(comb)
            
            # 加權總分 (40% 概率 + 30% 熵值 + 30% 反共識)
            total_score = (prob_score * 0.4 + entropy_score * 0.3 + anti_consensus_score * 0.3)
            candidates.append((comb, total_score))

        candidates.sort(key=lambda x: x[1], reverse=True)
        
        unique_bets = []
        seen = set()
        for comb, score in candidates:
            c_tuple = tuple(comb)
            if c_tuple not in seen:
                unique_bets.append(comb)
                seen.add(c_tuple)
            if len(unique_bets) >= num_bets:
                break
        return unique_bets

def run_backtest():
    lottery_type = 'BIG_LOTTO'
    from database import DatabaseManager
    local_db = DatabaseManager(db_path="data/lottery.db")
    all_draws = local_db.get_all_draws(lottery_type)
    all_draws.sort(key=lambda x: x['date'])
    
    train_data = []
    test_data = []
    for d in all_draws:
        date_str = str(d.get('date', ''))
        if date_str.startswith('2025'):
            test_data.append(d)
        else:
            train_data.append(d)
    
    print(f"🚀 開始高級組合研究回測 (2025年, {len(test_data)}期, 每期8注, 採樣1000次)")
    print("權重配置: 40% 概率 + 30% 熵值 + 30% 反共識")
    
    modes = ['none', 'fixed_3', 'top_3', 'adaptive']
    results_map = {mode: {'total_wins': 0, 'total_matches': 0, 'draws': 0} for mode in modes}
    
    strategy = OddEvenResearchStrategy()

    for i, target in enumerate(test_data):
        history = train_data + test_data[:i]
        actual = set(target['numbers'])
        special = int(target['special']) if target.get('special') else -1
        
        if (i+1) % 20 == 0:
            print(f"   已處理 {i+1}/{len(test_data)} 期...")

        for mode in modes:
            # Use 1000 simulations for faster research
            bets = strategy.generate_bets(history, odd_target_mode=mode, num_bets=8, num_simulations=1000)
            
            mode_won = False
            for bet in bets:
                m_cnt = len(set(bet) & actual)
                has_special = special in set(bet)
                
                results_map[mode]['total_matches'] += m_cnt
                
                # 中獎判定 (3碼+ 或 2碼+特別號)
                if m_cnt >= 3 or (m_cnt == 2 and has_special):
                    results_map[mode]['total_wins'] += 1
                    mode_won = True
            
            results_map[mode]['draws'] += 1

    # 輸出報告
    print("\n" + "="*80)
    print("🏆 奇偶組合策略性能對比報告 (2025 全年回測)")
    print("="*80)
    print(f"{'策略模式':<15} | {'總投注':<8} | {'總中獎':<8} | {'單注勝率':<10} | {'平均匹配'}")
    print("-" * 80)
    
    for mode in modes:
        res = results_map[mode]
        total_bets = res['draws'] * 8
        win_rate = res['total_wins'] / total_bets if total_bets > 0 else 0
        avg_match = res['total_matches'] / total_bets if total_bets > 0 else 0
        
        mode_name = {
            'none': '無過濾',
            'fixed_3': '固定 3:3',
            'top_3': '領先比例(2,3,4)',
            'adaptive': '趨勢自適應'
        }.get(mode, mode)
        
        print(f"{mode_name:<15} | {total_bets:<8} | {res['total_wins']:<8} | {win_rate:7.2%} | {avg_match:.3f}")
    print("="*80)

if __name__ == '__main__':
    run_backtest()
