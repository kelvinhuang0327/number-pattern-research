#!/usr/bin/env python3
import sys
import os
import json
from collections import Counter, defaultdict

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def analyze_cross_section_correlation():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    # 按照第一區總和分組，統計第二區分佈
    sum_to_special = defaultdict(list)
    parity_to_special = defaultdict(list)
    
    print(f"📊 正在分析 {len(all_draws)} 期威力彩跨區關聯...")
    
    for draw in all_draws:
        nums = draw['numbers']
        special = draw['special']
        
        # 1. 總和特徵 (以 10 為區間)
        s_val = sum(nums)
        s_bin = (s_val // 10) * 10
        sum_to_special[s_bin].append(special)
        
        # 2. 奇偶特徵 (奇數注數)
        odds = len([n for n in nums if n % 2 != 0])
        parity_to_special[odds].append(special)
        
    print("-" * 60)
    print("📈 總和分佈 vs 第二區熱訊 (Top 3 Specials):")
    for s_bin in sorted(sum_to_special.keys()):
        specials = sum_to_special[s_bin]
        if len(specials) < 50: continue # 樣本數太小跳過
        top_s = Counter(specials).most_common(3)
        print(f"總和 [{s_bin:3d}-{s_bin+9:3d}] (樣本:{len(specials):4d}) -> 熱門特別號: {top_s}")

    print("-" * 60)
    print("📈 奇偶比 (奇數個數) vs 第二區熱訊:")
    for odd_count in sorted(parity_to_special.keys()):
        specials = parity_to_special[odd_count]
        if len(specials) < 100: continue
        top_s = Counter(specials).most_common(3)
        print(f"奇數 [{odd_count} 碼] (樣本:{len(specials):4d}) -> 熱門特別號: {top_s}")

if __name__ == '__main__':
    analyze_cross_section_correlation()
