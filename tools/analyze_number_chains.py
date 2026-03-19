#!/usr/bin/env python3
"""
Lottery Number-Chain Analyzer (Quads & Graph Cliques)
分析號碼之間的「長鏈關聯」(Chain Correlations)。
尋找四元組 (Quads) 與五元組 (Pents)，並構建號碼連通圖。
"""
import sys
import os
import io
import json
import argparse
from collections import Counter, defaultdict
from itertools import combinations

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def analyze_chains(lottery_type='BIG_LOTTO', min_cooccurrence=4):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type=lottery_type)
    rules = get_lottery_rules(lottery_type)
    max_num = rules.get('maxNumber', 49)
    
    quad_counter = Counter()
    pair_counter = Counter()
    trio_counter = Counter()
    
    print(f"⛓ 正在分析號碼長鏈 (總期數: {len(all_draws)}) ...")
    
    for draw in all_draws:
        numbers = sorted(draw['numbers'])
        # 統計對子、三元組、四元組
        for pair in combinations(numbers, 2):
            pair_counter[pair] += 1
        for trio in combinations(numbers, 3):
            trio_counter[trio] += 1
        for quad in combinations(numbers, 4):
            quad_counter[quad] += 1
            
    print("-" * 60)
    print(f"🔥 黃金四元組 (Golden Quads) - 出現次數 >= {min_cooccurrence}:")
    
    # 找出出現頻率最高的四元組
    sorted_quads = sorted(quad_counter.items(), key=lambda x: x[1], reverse=True)
    
    count_found = 0
    for quad, count in sorted_quads:
        if count >= min_cooccurrence:
            # 計算強度：這 4 個號碼出現時，其中任意 3 個號碼出現的頻率平均值
            # 輔助判斷這是否是一個穩固的「鏈路」
            trios_in_quad = list(combinations(quad, 3))
            avg_trio_freq = sum(trio_counter[t] for t in trios_in_quad) / 4
            
            print(f"四元組 {quad}: 出現 {count} 次 | (子組三元平均頻率: {avg_trio_freq:.1f})")
            count_found += 1
        if count_found >= 30: # 只顯示前 30 個
            break

    print("-" * 60)
    print("🎯 連動鏈挖掘 (Chain Discovery):")
    
    # 從最強對子出發，遞迴尋找延伸路徑
    top_pairs = pair_counter.most_common(50)
    chains = []
    
    for pair, p_count in top_pairs:
        # 尋找最強的第三個號碼
        candidates = []
        for n in range(1, max_num + 1):
            if n not in pair:
                trio = tuple(sorted(list(pair) + [n]))
                if trio_counter[trio] > 5:
                    candidates.append((n, trio_counter[trio]))
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        if candidates:
            best_n3, n3_count = candidates[0]
            # 尋找最強的第四個號碼
            quad_candidates = []
            current_trio = tuple(sorted(list(pair) + [best_n3]))
            for n4 in range(1, max_num + 1):
                if n4 not in current_trio:
                    quad = tuple(sorted(list(current_trio) + [n4]))
                    if quad_counter[quad] > 2:
                        quad_candidates.append((n4, quad_counter[quad]))
            
            quad_candidates.sort(key=lambda x: x[1], reverse=True)
            if quad_candidates:
                best_n4, n4_count = quad_candidates[0]
                chain = (pair[0], pair[1], best_n3, best_n4)
                chains.append((chain, n4_count))

    # 去重並列出最強鏈路
    unique_chains = {}
    for c, score in chains:
        sc = tuple(sorted(c))
        if sc not in unique_chains or score > unique_chains[sc]:
            unique_chains[sc] = score
            
    sorted_chains = sorted(unique_chains.items(), key=lambda x: x[1], reverse=True)
    for chain, score in sorted_chains[:15]:
        print(f"鏈路路徑: {chain[0]:02d} -> {chain[1]:02d} -> {chain[2]:02d} -> {chain[3]:02d} (四者共存 {score} 次)")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery_type', type=str, default='BIG_LOTTO')
    parser.add_argument('--min_count', type=int, default=4)
    args = parser.parse_args()
    
    analyze_chains(lottery_type=args.lottery_type, min_cooccurrence=args.min_count)
