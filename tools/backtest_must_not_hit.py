#!/usr/bin/env python3
"""
Must-Not-Hit Prediction Accuracy Backtest
目標：驗證「殺號預測」的成功率 - 預測的 BOTTOM N 廢號真的沒開出幾個
"""
import sys
import os
import io
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from database import DatabaseManager
from common import get_lottery_rules

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class MustNotHitBacktester:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
        self.rules = get_lottery_rules(lottery_type)
        
    def get_data(self):
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))

    def predict_must_not_hit(self, history, bottom_n=10):
        """預測必不中號碼 - 基於冷號策略 (近100期最不頻繁)"""
        if len(history) < 100:
            return []
        freq = Counter([n for d in history[-100:] for n in d['numbers']])
        
        min_num = self.rules['minNumber']
        max_num = self.rules['maxNumber']
        
        all_scores = []
        for n in range(min_num, max_num + 1):
            all_scores.append((n, freq.get(n, 0)))
        
        # 頻率最低的 N 個
        all_scores.sort(key=lambda x: x[1])
        return [n for n, s in all_scores[:bottom_n]]

    def run(self, year=2025, bottom_n=10):
        all_draws = self.get_data()
        test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
        
        print(f"🚫 殺號預測 (Must-Not-Hit) 回測 (年份: {year})")
        print(f"配置: 預測 BOTTOM {bottom_n} 個必不中號碼")
        print("-" * 80)

        start_idx = all_draws.index(test_draws[0])
        total_rounds = 0
        total_leaks = 0
        perfect_rounds = 0 # 0 個漏網
        
        leak_distribution = Counter()
        
        for i, target_draw in enumerate(test_draws):
            current_idx = start_idx + i
            history = all_draws[:current_idx]
            
            must_not_hit_nums = set(self.predict_must_not_hit(history, bottom_n))
            actual_nums = set(target_draw['numbers'])
            
            leaks = len(must_not_hit_nums & actual_nums)
            total_leaks += leaks
            leak_distribution[leaks] += 1
            
            if leaks == 0:
                perfect_rounds += 1
                
            total_rounds += 1

        avg_leaks = total_leaks / total_rounds
        clean_rate = (perfect_rounds / total_rounds) * 100
        
        # 理想殺號成功率: 如果隨機殺 N 個號碼，有多少機率不命中任何中獎號？
        # P(0 命中) = C(43, 6) / C(49, 6) ≈ (隨機參考)
        # 簡化: 每個號碼有 6/49 ≈ 12.2% 機率被開
        # 殺 N 個全不中機率 ≈ (1 - 6/49)^N
        import math
        random_clean_rate = ((1 - 6/49) ** bottom_n) * 100
        
        print(f"回測結束: 共 {total_rounds} 期")
        print(f"殺 {bottom_n} 碼平均漏網: {avg_leaks:.2f} 個/期")
        print(f"殺號成功率 (Clean Rate): {clean_rate:.2f}% (隨機期望={random_clean_rate:.2f}%)")
        print(f"相對表現: {clean_rate/random_clean_rate:.2f}x")
        print("-" * 40)
        print("漏網分佈:")
        for l in sorted(leak_distribution.keys()):
            print(f"Leak {l}: {leak_distribution[l]} 次 ({leak_distribution[l]/total_rounds*100:.1f}%)")
        print("-" * 80)
        
        return avg_leaks, clean_rate

def main():
    backtester = MustNotHitBacktester()
    for bottom_n in [5, 10, 15]:
        print(f"\n{'='*80}")
        backtester.run(2025, bottom_n)

if __name__ == '__main__':
    main()
