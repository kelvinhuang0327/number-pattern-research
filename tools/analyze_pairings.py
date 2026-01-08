#!/usr/bin/env python3
"""
Lottery Number Pairing Analyzer
分析號碼之間的「配對規律」，尋找最強關聯性對子，以支持「鄰域坍縮」策略。
"""
import sys
import os
import io
import json
from collections import Counter, defaultdict
from itertools import combinations

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from database import DatabaseManager

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def analyze_pairings(lottery_type='BIG_LOTTO', top_n=30):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type=lottery_type)
    
    # 限制在最近 300 期，捕捉近期相關性，但也看全局
    recent_draws = all_draws[:300]
    
    pair_counter = Counter()
    number_freq = Counter()
    
    for draw in all_draws:
        numbers = sorted(draw['numbers'])
        # 統計號碼頻率
        for n in numbers:
            number_freq[n] += 1
        # 統計對子頻率
        for pair in combinations(numbers, 2):
            pair_counter[pair] += 1
            
    # 計算「條件概率」: P(A|B) = Count(A,B) / Count(B)
    correlation_map = defaultdict(dict)
    for (a, b), count in pair_counter.items():
        # A 出現時 B 也出現的機率
        correlation_map[a][b] = count / number_freq[a]
        # B 出現時 A 也出現的機率
        correlation_map[b][a] = count / number_freq[b]
        
    print(f"📊 大樂透號碼關聯性分析 (總期數: {len(all_draws)})")
    print("-" * 50)
    print("🔥 最常出現的對子 Top 15:")
    for pair, count in pair_counter.most_common(15):
        print(f"對子 {pair}: 出現 {count} 次")
        
    print("-" * 50)
    print("🎯 高強度關聯號碼 (當號碼 A 出現時，號碼 B 高機率伴隨):")
    
    # 找出 P(A|B) 最高的
    results = []
    for a, targets in correlation_map.items():
        for b, prob in targets.items():
            if number_freq[a] > 50: # 號碼 A 必須有足夠樣本
                results.append((a, b, prob, pair_counter[tuple(sorted((a,b)))]))
    
    results.sort(key=lambda x: x[2], reverse=True)
    
    for a, b, prob, count in results[:20]:
        print(f"當 {a:02d} 出現時 -> {b:02d} 出現機率 {prob:.2%} (共伴隨 {count} 次)")

if __name__ == '__main__':
    analyze_pairings()
