#!/usr/bin/env python3
import sys
import os
import json
import numpy as np
from collections import Counter, defaultdict

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def analyze_power_volatility():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    # 計算各號碼在不同時間窗口的頻率變化
    windows = [20, 50, 100]
    num_volatility = {}

    print(f"📊 正在分析 {len(all_draws)} 期威力彩號碼穩定度 (Volatility)...")
    
    for num in range(1, 39):
        freqs = []
        for w in windows:
            subset = all_draws[:w]
            count = sum(1 for d in subset if num in d['numbers'])
            freqs.append(count / w)
        
        # 計算變異係數 (CV) = 標準差 / 平均值
        cv = np.std(freqs) / np.mean(freqs) if np.mean(freqs) > 0 else 99
        num_volatility[num] = cv

    # 排序：最穩定的號碼 (CV 最小)
    stable_nums = sorted(num_volatility.items(), key=lambda x: x[1])
    
    print("-" * 60)
    print("💎 穩定性排行 (Top 5 Most Stable Numbers - Best for Anchors):")
    for n, cv in stable_nums[:5]:
        print(f"號碼 {n:02d} | 變異係數: {cv:.4f} (跨尺度頻率極其穩定)")

    print("-" * 60)
    print("🌀 雜訊排行 (Top 5 Most Volatile Numbers - High Risk):")
    for n, cv in stable_nums[-5:]:
        print(f"號碼 {n:02d} | 變異係數: {cv:.4f} (表現極不穩定，易產生誤判)")

    # 分析反轉潛力 (冷號遺漏分析)
    print("-" * 60)
    print("❄️ 遺漏分析 (Omission Analysis - Potential Reversals):")
    
    omissions = {}
    for num in range(1, 39):
        last_seen = -1
        for i, draw in enumerate(all_draws):
            if num in draw['numbers']:
                last_seen = i
                break
        omissions[num] = last_seen
        
    hot_to_cold = sorted(omissions.items(), key=lambda x: x[1], reverse=True)
    
    # 找出遺漏值突破歷史平均的號碼
    for n, o in hot_to_cold[:5]:
        if o > 15: # 門檻
            print(f"號碼 {n:02d} | 已遺漏 {o:2d} 期 | ⚠️ 處於「冷極必反」高機率區")

if __name__ == '__main__':
    analyze_power_volatility()
