#!/usr/bin/env python3
"""
Must-Hit Prediction Accuracy Backtest
目標：驗證「必中號碼預測」的成功率 - 預測的 TOP N 號碼實際開出了幾個
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

class MustHitBacktester:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
        self.rules = get_lottery_rules(lottery_type)
        
    def get_data(self):
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))

    def predict_must_hit(self, history, top_n=10):
        """預測必中號碼 - 基於熱號策略 (近50期最頻繁)"""
        if len(history) < 50:
            return []
        freq = Counter([n for d in history[-50:] for n in d['numbers']])
        return [n for n, c in freq.most_common(top_n)]

    def run(self, year=2025, top_n=10):
        all_draws = self.get_data()
        test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
        
        print(f"🎯 必中號碼預測 (Must-Hit) 回測 (年份: {year})")
        print(f"配置: 預測 TOP {top_n} 個必中號碼")
        print("-" * 80)

        start_idx = all_draws.index(test_draws[0])
        total_rounds = 0
        total_hits = 0
        perfect_rounds = 0 # 6 個全命中
        high_hit_rounds = 0 # 命中 4+ 個
        
        hit_distribution = Counter()
        
        for i, target_draw in enumerate(test_draws):
            current_idx = start_idx + i
            history = all_draws[:current_idx]
            
            must_hit_nums = set(self.predict_must_hit(history, top_n))
            actual_nums = set(target_draw['numbers'])
            
            hits = len(must_hit_nums & actual_nums)
            total_hits += hits
            hit_distribution[hits] += 1
            
            if hits == 6:
                perfect_rounds += 1
            if hits >= 4:
                high_hit_rounds += 1
                
            total_rounds += 1

        avg_hits = total_hits / total_rounds
        hit_rate = (total_hits / (total_rounds * 6)) * 100
        
        print(f"回測結束: 共 {total_rounds} 期")
        print(f"TOP {top_n} 號碼平均命中: {avg_hits:.2f} 個/期")
        print(f"命中率 (Hit Rate): {hit_rate:.2f}% (理想值={top_n/49*100:.2f}%)")
        print(f"高命中期數 (4+): {high_hit_rounds} ({high_hit_rounds/total_rounds*100:.2f}%)")
        print("-" * 40)
        print("命中分佈:")
        for h in sorted(hit_distribution.keys(), reverse=True):
            print(f"Hit {h}: {hit_distribution[h]} 次 ({hit_distribution[h]/total_rounds*100:.1f}%)")
        print("-" * 80)
        
        return avg_hits, hit_rate

def main():
    backtester = MustHitBacktester()
    for top_n in [6, 10, 15]:
        print(f"\n{'='*80}")
        backtester.run(2025, top_n)

if __name__ == '__main__':
    main()
