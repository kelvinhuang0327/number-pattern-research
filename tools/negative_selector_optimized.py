#!/usr/bin/env python3
"""
Negative Selector (Kill Model) - Optimized (Smart 10)
"""
import sys
import os
import io
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules

# Fix encoding
# sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import math

class NegativeSelector:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
        self.db = DatabaseManager(db_path=self.db_path)
        self.rules = get_lottery_rules(lottery_type)
        
    def get_data(self, limit=1000):
        # Get data ASC (Oldest -> Newest)
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))[:limit]

    def _calculate_regional_entropy(self, history, num_zones=5):
        """計算近期開獎的區域熵值 (Regional Entropy)"""
        if not history:
            return 0
        
        max_num = self.rules['maxNumber']
        zone_size = max_num / num_zones
        
        # 統計各區間命中次數
        zone_counts = [0] * num_zones
        for draw in history:
            for n in draw['numbers']:
                zone_idx = min(int((n-1) / zone_size), num_zones - 1)
                zone_counts[zone_idx] += 1
        
        total_hits = sum(zone_counts)
        if total_hits == 0:
            return 0
            
        # 計算熵
        entropy = 0
        for count in zone_counts:
            p = count / total_hits
            if p > 0:
                entropy -= p * math.log2(p)
                
        return entropy

    def predict_kill_numbers(self, base_count=10):
        """
        🚀 P1: 動態殺號門檻 (Dynamic Kill Threshold)
        根據近期 30 期的區域熵值，自動調整殺號數量與策略
        """
        all_draws = self.get_data()
        if len(all_draws) < 30:
            return []
            
        recent_30 = all_draws[-30:]
        entropy = self._calculate_regional_entropy(recent_30, num_zones=5)
        
        # 1. 動態調整殺號數量
        # 理想熵值約為 log2(5) = 2.32
        # 熵低 (< 2.0): 群聚特徵明顯，殺號應保守 (避免殺到群聚爆發區)
        # 熵高 (> 2.2): 分佈極端平均，可增加殺號強度 (排除長期不出的冷號更安全)
        
        if entropy < 2.0:
            # 熵低: 群聚特徵。可以在「非聚集區」適度增加殺號。
            dynamic_count = min(15, base_count + 2)
            strategy = "targeted_cold"
        elif entropy > 2.2:
            # 熵高: 開號極其分散 (混亂)。殺任何號都危險，應大幅減少殺號數量。
            dynamic_count = max(5, base_count - 5)
            strategy = "safe_conservative"
        else:
            dynamic_count = base_count
            strategy = "balanced"

        # 2. 計算特徵 (頻率與遺漏)
        freq_100 = Counter([n for d in all_draws[-100:] for n in d['numbers']])
        gaps = {n: 999 for n in range(1, self.rules['maxNumber'] + 1)}
        for i, draw in enumerate(reversed(all_draws)):
            for n in draw['numbers']:
                if gaps[n] == 999:
                    gaps[n] = i
                    
        # 3. 執行策略性選號
        scores = []
        for n in range(1, self.rules['maxNumber'] + 1):
            f = freq_100.get(n, 0)
            g = gaps[n]
            
            # 分數算法：頻率越高分數越高。殺號時選擇分數最低的（最冷）
            # P1 偵測：如果策略是激進，則對「極高頻且近期連開」的號碼也進行少量殺號（防歇火）
            score = f
            
            # 風險控制：長期遺漏號 (> 22 期) 不殺 (防回補回歸)
            if g > 22:
                score += 100 
            
            if strategy == "aggressive_mixed" and g == 0 and f > 20:
                # 極熱號且剛開過，在激進模式下適度增加被殺機率 (分數調低)
                score *= 0.5

            scores.append((n, score))
            
        scores.sort(key=lambda x: x[1])
        kill_nums = [n for n, s in scores[:dynamic_count]]
        
        print(f"📊 區域熵值: {entropy:.4f} | 執行策略: {strategy} | 殺號數量: {dynamic_count}")
        return sorted(kill_nums)

def main():
    selector = NegativeSelector()
    kill_nums = selector.predict_kill_numbers(base_count=10)
    
    print("================================================================================")
    print(f"負向排除模型 (P1 Dynamic Thresholding)")
    print("================================================================================")
    print(f"動態殺號清單: {kill_nums}")
    print("================================================================================")

if __name__ == '__main__':
    main()
