#!/usr/bin/env python3
"""
P1 Dynamic Kill Threshold Backtest Validation
比較「Smart-10 固定殺號」與「P1 動態區域熵殺號」在 2025 年的表現。
"""
import sys
import os
import io
from collections import Counter
import numpy as np

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from tools.negative_selector import NegativeSelector

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class P1Validator:
    def __init__(self):
        self.lottery_type = 'BIG_LOTTO'
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
        self.rules = get_lottery_rules(self.lottery_type)
        self.selector = NegativeSelector(self.lottery_type)
        
    def get_data(self):
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))

    def run_comparison(self, year=2025):
        all_draws = self.get_data()
        test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
        
        print(f"🔬 P1 動態殺號 vs Smart-10 固定殺號 回測對比 ({year})")
        print("=" * 80)
        
        start_idx = all_draws.index(test_draws[0])
        
        # Stats
        total = 0
        s10_leaks = 0
        s10_clean = 0
        p1_leaks = 0
        p1_clean = 0
        p1_kill_counts = []
        
        for i, target in enumerate(test_draws):
            current_idx = start_idx + i
            history = all_draws[:current_idx]
            winning_nums = set(target['numbers'])
            
            # 1. Baseline: Smart-10 (We simulate it using the logic before P1 or forcing count=10)
            # Actually our current selector is upgraded. To get smart-10 we can 
            # bypass the entropy logic if we had a flag, but we'll just use a mock for comparison 
            # or use the old logic if we wanted.
            # For simplicity, let's compare P1 with a fixed 10 logic.
            
            # --- Baseline Smart-10 Logic ---
            freq_100 = Counter([n for d in history[-100:] for n in d['numbers']])
            gaps = {}
            for n in range(1, 50):
                gaps[n] = 999
                for j, d in enumerate(reversed(history)):
                    if n in d['numbers']:
                        gaps[n] = j
                        break
            
            s10_scores = []
            for n in range(1, 50):
                if gaps[n] > 20: s10_scores.append((n, 9999))
                else: s10_scores.append((n, freq_100.get(n, 0)))
            s10_scores.sort(key=lambda x: x[1])
            s10_kill = set([n for n, s in s10_scores[:10]])
            
            # --- P1 Dynamic Logic ---
            p1_kill = set(self.selector.predict_kill_numbers(count=10, history=history))
            p1_kill_counts.append(len(p1_kill))
            
            # Eval
            s10_hit = len(s10_kill & winning_nums)
            p1_hit = len(p1_kill & winning_nums)
            
            s10_leaks += s10_hit
            if s10_hit == 0: s10_clean += 1
            
            p1_leaks += p1_hit
            if p1_hit == 0: p1_clean += 1
            
            total += 1
            
        print(f"{'Metric':<25} | {'Smart-10 (Fix)':<15} | {'P1 Dynamic':<15}")
        print("-" * 80)
        print(f"{'Total Periods':<25} | {total:<15} | {total:<15}")
        print(f"{'Clean Kill Rate (%)':<25} | {s10_clean/total*100:6.2f}%       | {p1_clean/total*100:6.2f}%")
        print(f"{'Average Leaks':<25} | {s10_leaks/total:6.2f}          | {p1_leaks/total:6.2f}")
        print(f"{'Avg Kill Count':<25} | {10.0:<15.1f} | {np.mean(p1_kill_counts):<15.1f}")
        print("=" * 80)
        
        improvement = (p1_clean/total) - (s10_clean/total)
        print(f"🚀 P1 每期誤殺率減少: {(s10_leaks - p1_leaks) / total:.4f}")
        print(f"🚀 P1 完全正確率提升: {improvement*100:.2f}%")

if __name__ == "__main__":
    validator = P1Validator()
    validator.run_comparison()
