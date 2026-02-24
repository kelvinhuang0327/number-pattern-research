
#!/usr/bin/env python3
"""
Market Temperature Analyzer (市場溫度計)
目標：分析近期開獎號碼的 "冷熱屬性"，回答 "現在是熱號多還是冷號回補多？"
定義：
- Hot (熱號): Gap < 5 (近 5 期內開過)
- Warm (溫號): 5 <= Gap < 10
- Cold (冷號): Gap >= 10 (遺漏 10 期以上)
"""
import sys
import os
import argparse
import pandas as pd
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

def analyze_temperature(windows=[20, 50, 100]):
    print("=" * 80)
    print(f"🌡️ Market Temperature Analysis (Hot vs Cold)")
    print("=" * 80)
    
    # 1. 準備數據
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    all_draws = sorted(all_draws, key=lambda x: x['date'])
    
    total_draws = len(all_draws)
    if total_draws < 100:
        print("❌ Not enough data")
        return

    # 計算每一期開出號碼的 Gap 屬性
    # 我們需要回溯計算每期開獎時，該號碼當下的 Gap
    
    results = []
    
    # 為了效能，我們只分析最後 max(windows) 期
    start_idx = total_draws - max(windows)
    
    for i in range(start_idx, total_draws):
        target_draw = all_draws[i]
        history = all_draws[:i]
        date = target_draw['date']
        numbers = target_draw['numbers']
        
        draw_stats = {'Hot': 0, 'Warm': 0, 'Cold': 0}
        
        for num in numbers:
            gap = 999
            # Find gap in history (reversed)
            for j, past_draw in enumerate(reversed(history)):
                if num in past_draw['numbers']:
                    gap = j
                    break
            
            if gap < 5:
                draw_stats['Hot'] += 1
            elif gap < 10:
                draw_stats['Warm'] += 1
            else:
                draw_stats['Cold'] += 1
                
        results.append(draw_stats)

    # 統計匯總
    print(f"{'Period (Recent)':<15} | {'Hot (<5)':<15} | {'Warm (5-10)':<15} | {'Cold (>10)':<15} | {'Dominant'}")
    print("-" * 80)
    
    for w in windows:
        subset = results[-w:]
        total_nums = w * 6
        
        sum_hot = sum(r['Hot'] for r in subset)
        sum_warm = sum(r['Warm'] for r in subset)
        sum_cold = sum(r['Cold'] for r in subset)
        
        pct_hot = (sum_hot / total_nums) * 100
        pct_warm = (sum_warm / total_nums) * 100
        pct_cold = (sum_cold / total_nums) * 100
        
        if pct_hot > 40: dom = "🔥 HOT"
        elif pct_cold > 30: dom = "🧊 COLD"
        else: dom = "⚖️ MIXED"
        
        print(f"Last {w:<10} | {pct_hot:5.1f}% ({sum_hot})   | {pct_warm:5.1f}% ({sum_warm})   | {pct_cold:5.1f}% ({sum_cold})   | {dom}")

    print("-" * 80)
    
    # Trend Check (Last 10 draws detail)
    print("\n🔍 Recent 10 Draws Detail:")
    recent_10 = all_draws[-10:]
    recent_stats = results[-10:]
    
    for i, draw in enumerate(recent_10):
        stats = recent_stats[i]
        print(f"Draw {draw['draw']} ({draw['date']}): Hot:{stats['Hot']}, Warm:{stats['Warm']}, Cold:{stats['Cold']}")

    # 結論建議
    last_50_hot = sum(r['Hot'] for r in results[-50:]) / (50*6)
    last_50_cold = sum(r['Cold'] for r in results[-50:]) / (50*6)
    
    print("\n💡 Conclusion:")
    if last_50_hot > 0.5:
        print("👉 Market is VERY HOT. Follow the trend (Trend/Markov).")
    elif last_50_hot > 0.4:
        print("👉 Market is WARM-HOT. Mix of Trend and Smart-2Bet.")
    elif last_50_cold > 0.35:
        print("👉 Market is COLD (Correction Mode). Focus on Gap/Deviation.")
    else:
        print("👉 Market is BALANCED. Use Orthogonal strategies.")

if __name__ == '__main__':
    analyze_temperature()
