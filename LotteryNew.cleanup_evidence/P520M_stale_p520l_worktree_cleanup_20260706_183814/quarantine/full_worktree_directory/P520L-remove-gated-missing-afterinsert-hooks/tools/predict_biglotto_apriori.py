#!/usr/bin/env python3
"""
大樂透 Apriori 關聯規則預測器 (Advanced Structural Strategy)
核心邏輯：挖掘高置信度 (Confidence) 的強關聯規則，用於構建「膽拖」組合。
不同於 Cluster Pivot 的「聚類」，這裡是「有向規則」：
規則：{A, B} -> {C} (Confidence > 0.6)
表示當 A 和 B 同時出現時，C 有 >60% 機率也會出現。
"""
import sys
import os
import logging
from collections import Counter, defaultdict
from itertools import combinations
from typing import List, Dict, Set, Tuple

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class BigLottoAprioriPredictor:
    def __init__(self):
        self.db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
        
    def get_draws(self) -> List[Dict]:
        db = DatabaseManager(db_path=self.db_path)
        return db.get_all_draws(lottery_type='BIG_LOTTO')
        
    def mine_frequent_itemsets(self, history: List[Dict], min_support: int = 5) -> Dict:
        """挖掘頻繁項集 (2-itemsets & 3-itemsets)"""
        counts = defaultdict(int)
        
        for draw in history:
            nums = sorted(draw['numbers'])
            # 1-itemsets
            for n in nums:
                counts[(n,)] += 1
            # 2-itemsets
            for pair in combinations(nums, 2):
                counts[pair] += 1
            # 3-itemsets
            for trio in combinations(nums, 3):
                counts[trio] += 1
                
        # Filter by min_support
        frequent = {k: v for k, v in counts.items() if v >= min_support}
        return frequent

    def generate_rules(self, frequent_itemsets: Dict, min_confidence: float = 0.5) -> List[Dict]:
        """生成關聯規則 {A} -> {B} 或 {A,B} -> {C}"""
        rules = []
        
        for itemset, support_union in frequent_itemsets.items():
            k = len(itemset)
            if k < 2: continue
            
            # Generate all possible logical implications
            # For {A, B}, check A -> B and B -> A
            # For {A, B, C}, check {A, B} -> C etc.
            
            # We focus on Antecedent size = k-1 (Predicting the last one)
            for consequent in combinations(itemset, 1):
                consequent = consequent[0]
                antecedent = tuple(sorted(set(itemset) - {consequent}))
                
                if antecedent in frequent_itemsets:
                    support_antecedent = frequent_itemsets[antecedent]
                    confidence = support_union / support_antecedent
                    
                    if confidence >= min_confidence:
                        rules.append({
                            'antecedent': antecedent,
                            'consequent': consequent,
                            'confidence': confidence,
                            'support': support_union,
                            'lift': confidence / (frequent_itemsets[(consequent,)] / 150) # Approx Life
                        })
                        
        return sorted(rules, key=lambda x: x['confidence'], reverse=True)

    def predict_next_draw(self, num_bets: int = 6, window: int = 150) -> Dict:
        all_draws = self.get_draws()
        recent_history = all_draws[:window] # Newest 150
        
        print(f"🔍 Apriori 規則挖掘 (近 {window} 期)...")
        
        # 1. Mine Frequent Sets
        frequent = self.mine_frequent_itemsets(recent_history, min_support=3)
        
        # 2. Generate Rules
        rules = self.generate_rules(frequent, min_confidence=0.4) # Slightly lower thresh for lottery
        
        print(f"   挖掘到 {len(rules)} 條強關聯規則 (Conf >= 40%)")
        if rules:
            print(f"   Top Rule: {rules[0]['antecedent']} -> {rules[0]['consequent']} (Conf: {rules[0]['confidence']:.2f})")
        
        bets = []
        
        # Strategy: Build bets around Top Rules
        # "If A, B appear, Pick C"
        # Problem: We don't know if A, B will appear next.
        # Solution: Pick A, B that are "Due" or "Hot", then attach C.
        # Or: Pick the STRONGEST rules overall (most frequent high-conf patterns)
        
        used_rules = set()
        
        for i in range(num_bets):
            # Pick a distinct high-confidence rule to build a bet around
            # We want diverse rules (different antecedents)
            
            target_rule = None
            for r in rules:
                r_key = r['antecedent']
                if r_key not in used_rules:
                    target_rule = r
                    used_rules.add(r_key)
                    break
            
            if not target_rule:
                break # No more distinct rules
                
            # Build bet: Antecedent + Consequent + Fillers
            core = list(target_rule['antecedent']) + [target_rule['consequent']]
            
            # Fill remaining with numbers strongly associated with 'consequent'
            # (Chain reaction: C -> D)
            current_nums = sorted(list(set(core)))
            
            # Iteratively add numbers using rules
            while len(current_nums) < 6:
                best_next = None
                best_conf = 0
                
                # Check rules where current_nums (subset) -> next
                # Simplify: Check rules where (Last Num) -> Next
                last_num = current_nums[-1]
                
                # Filter rules where antecedent contains last_num
                candidates = []
                for r in rules:
                    if r['consequent'] not in current_nums:
                        if r['antecedent'] == (last_num,) or (len(r['antecedent'])==1 and r['antecedent'][0] in current_nums):
                             candidates.append(r)
                
                if candidates:
                    candidates.sort(key=lambda x: x['confidence'], reverse=True)
                    best_next = candidates[0]['consequent']
                else:
                    # Fallback: Co-occurrence (Cluster Pivot logic simpler)
                    # Or just frequent numbers
                    remaining = [n for n in range(1, 50) if n not in current_nums]
                    import random
                    best_next = remaining[i % len(remaining)] # Deterministic filler
                
                current_nums.append(best_next)
                current_nums = sorted(list(set(current_nums)))
                
            bets.append({
                'numbers': sorted(current_nums[:6]),
                'strategy': f"Rule: {target_rule['antecedent']}->{target_rule['consequent']} (Conf {target_rule['confidence']:.2f})",
                'rule_strength': target_rule['confidence']
            })
            
        return bets

def main():
    predictor = BigLottoAprioriPredictor()
    bets = predictor.predict_next_draw(num_bets=7, window=150)
    
    next_draw = "115000008"
    
    print("\n" + "="*60)
    print(f"🔗 Apriori 關聯規則預測 (第 {next_draw} 期)")
    print("="*60)
    
    for i, bet in enumerate(bets, 1):
        nums = ", ".join(f"{n:02d}" for n in bet['numbers'])
        print(f"注 {i} [{bet['strategy']}]:")
        print(f"👉 {nums}")
        print("-" * 30)
        
    print("\n💡 策略說明: 基於強關聯規則 (Confidence > 40%) 構建連鎖反應。")
    print("   適合捕捉「拖牌」效應。")
    print("="*60)

if __name__ == '__main__':
    main()
