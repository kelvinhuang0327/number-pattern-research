#!/usr/bin/env python3
"""
Lottery Trio Correlation Analyzer
分析號碼之間的「三元關聯」(3-Number Clusters)。
目標：給定兩注號碼(A,B)，預測第 3 個號碼 C 的伴隨機率 P(C | A,B)。
"""
import sys
import os
import io
from collections import Counter, defaultdict
from itertools import combinations

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from database import DatabaseManager

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def analyze_trios(lottery_type='BIG_LOTTO'):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type=lottery_type)
    
    # 使用所有歷史數據以獲得足夠樣本
    trio_counter = Counter()
    pair_counter = Counter()
    
    for draw in all_draws:
        numbers = sorted(draw['numbers'])
        # 統計對子
        for pair in combinations(numbers, 2):
            pair_counter[pair] += 1
        # 統計三元組
        for trio in combinations(numbers, 3):
            trio_counter[trio] += 1
            
    # 計算 P(C | A,B) = Count(A,B,C) / Count(A,B)
    trio_conditional_prob = defaultdict(dict)
    for (a, b, c), count in trio_counter.items():
        # 對於（a,b,c）中的每一對，統計第三個號碼的機率
        for (n1, n2, n3) in [(a,b,c), (a,c,b), (b,c,a)]:
            pair = (n1, n2)
            trio_conditional_prob[pair][n3] = count / pair_counter[pair]
            
    print(f"📊 大樂透三元關聯分析 (總期數: {len(all_draws)})")
    print("-" * 60)
    print("🔥 最常出現的三元連動組 (Trio Clusters) Top 15:")
    for trio, count in trio_counter.most_common(15):
        print(f"組合 {trio}: 出現 {count} 次")
        
    print("-" * 60)
    print("🎯 強效「三元擴大」建議 (當對子 (A,B) 出現時，C 最可能伴隨):")
    
    # 找出機率最高的組合
    results = []
    for pair, targets in trio_conditional_prob.items():
        if pair_counter[pair] >= 10: # 對子必須出現超過 10 次才具參考價值
            for c, prob in targets.items():
                results.append((pair, c, prob, trio_counter[tuple(sorted(list(pair) + [c]))]))
                
    results.sort(key=lambda x: x[2], reverse=True)
    
    for pair, c, prob, count in results[:20]:
        print(f"當對子 {pair} 出現時 -> {c:02d} 出現機率 {prob:.2%} (三者共存 {count} 次)")

if __name__ == '__main__':
    analyze_trios()
