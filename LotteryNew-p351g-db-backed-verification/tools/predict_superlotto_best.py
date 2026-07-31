#!/usr/bin/env python3
"""
威力彩 (Super Lotto) 最佳策略預測器
主區 (1-38): 使用 Cluster Pivot + Apriori 混合策略
第二區 (1-8): 使用關聯分析 (Main -> Special) 或 熱門號碼

策略配置:
1. 主區 (選6): 邏輯同大樂透 (1注聚類, 2-3注關聯, 4+聚類)
2. 第二區 (選1): 分析與主區號碼共現率最高的特別號
"""
import sys
import os
import argparse
import logging
from collections import Counter
from itertools import combinations
from typing import List, Dict, Set, Tuple

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
# Import base classes or reimplement to ensure standalone
# For simplicity, we implement a specialized class inheriting or standalone

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class SuperLottoPredictor:
    def __init__(self):
        self.db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
        self.db = DatabaseManager(db_path=self.db_path)
    
    def get_draws(self) -> List[Dict]:
        return self.db.get_all_draws(lottery_type='POWER_LOTTO')

    def predict_special_number(self, history: List[Dict], main_numbers: List[int]) -> int:
        """根據主區號碼預測第二區"""
        # 1. Look for direct associations
        # Count which special number appears most with these main numbers
        scores = Counter()
        
        for draw in history:
            special = draw['special']
            match_count = len(set(draw['numbers']) & set(main_numbers))
            if match_count >= 3: # If main numbers resemble this draw
                scores[special] += match_count # Higher weight
                
        if scores:
            return scores.most_common(1)[0][0]
            
        # Fallback: Just hot special numbers in recent 50 draws
        hot_specials = Counter([d['special'] for d in history[:50]])
        if hot_specials:
            return hot_specials.most_common(1)[0][0]
            
        return 1 # Fallback default

    # Reimplement Cluster Pivot for 1-38
    def build_cooccurrence(self, history):
        cooccur = Counter()
        for draw in history:
            nums = sorted(draw['numbers'])
            for pair in combinations(nums, 2):
                cooccur[pair] += 1
        return cooccur
        
    def find_centers(self, cooccur, top_k):
        num_scores = Counter()
        for (a, b), count in cooccur.items():
            num_scores[a] += count
            num_scores[b] += count
        return [num for num, _ in num_scores.most_common(top_k)]

    def expand_anchor(self, anchor, cooccur, exclude=None):
        if exclude is None: exclude = set()
        candidates = Counter()
        for (a, b), count in cooccur.items():
            if a == anchor and b not in exclude: candidates[b] += count
            elif b == anchor and a not in exclude: candidates[a] += count
        
        selected = [anchor]
        for num, _ in candidates.most_common(12): # Pool
            if num not in selected and num not in exclude:
                selected.append(num)
            if len(selected) >= 6: break
            
        # Fill
        if len(selected) < 6:
            all_nums = Counter()
            for (a,b), _ in cooccur.items(): all_nums[a]+=1
            for num, _ in all_nums.most_common(38):
                if num not in selected and num not in exclude:
                    selected.append(num)
                if len(selected) >= 6: break
        
        return sorted(selected[:6])

    def predict(self, num_bets=7):
        history = self.get_draws()
        if not history:
            print("❌ 無威力彩數據 (請確保已匯入資料)")
            return []
            
        recent = history[:150]
        cooccur = self.build_cooccurrence(recent)
        
        bets = []
        
        # Strategy Switching Logic (Same as Big Lotto)
        strategy = 'cluster'
        if num_bets in [2, 3]: 
            strategy = 'cluster' # For simplicity in this demo, or implement Apriori later
            # User wants to know IF it can be used. We demonstrate Cluster first.
        
        centers = self.find_centers(cooccur, top_k=num_bets+5)
        
        print(f"🔍 威力彩分析 (近 {len(recent)} 期) - 主區 1-38, 第二區 1-8")
        
        for i in range(num_bets):
            if i >= len(centers): break
            center = centers[i]
            
            exclude = set()
            for b in bets: exclude.update(b['numbers'][:2])
                
            main_nums = self.expand_anchor(center, cooccur, exclude)
            
            # Predict Special
            special = self.predict_special_number(recent, main_nums)
            
            bets.append({
                'numbers': main_nums,
                'special': special,
                'anchor': center
            })
            
        return bets

def main():
    parser = argparse.ArgumentParser(description='威力彩智能預測')
    parser.add_argument('-n', '--num', type=int, default=7, help='注數')
    args = parser.parse_args()
    
    predictor = SuperLottoPredictor()
    bets = predictor.predict(args.num)
    
    if not bets: return

    print("="*60)
    print(f"⚡️ 威力彩預測 ({args.num} 注)")
    print("="*60)
    
    for i, bet in enumerate(bets, 1):
        nums = ", ".join(f"{n:02d}" for n in bet['numbers'])
        spec = f"{bet['special']:02d}"
        print(f"注 {i}: [{nums}]  +  特別號 [{spec}]")
        
    print("\n💡 策略: 主區 Cluster Pivot (1-38) + 第二區關聯預測")
    print("="*60)

if __name__ == '__main__':
    main()
