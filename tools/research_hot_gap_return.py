#!/usr/bin/env python3
import os
import sys
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    test_periods = 1500
    baseline_rate = 6 / 49  # 12.2449%
    
    total_candidates = 0
    total_hits = 0
    
    periods_with_candidates = 0
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 100:
            continue
            
        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'])
        
        # Calculate gap and freq100 for all numbers 1-49
        freq100 = {n: 0 for n in range(1, 50)}
        gap = {n: 1000 for n in range(1, 50)}
        
        # Freq100
        hist100 = hist[-100:]
        for h in hist100:
            for n in h['numbers']:
                if 1 <= n <= 49:
                    freq100[n] += 1
                    
        # Gap
        for n in range(1, 50):
            g = 0
            for h in reversed(hist):
                if n in h['numbers']:
                    break
                g += 1
            gap[n] = g
            
        candidates = [n for n in range(1, 50) if freq100[n] >= 15 and gap[n] >= 10]
        
        if candidates:
            periods_with_candidates += 1
            total_candidates += len(candidates)
            hits = len(set(candidates) & actual)
            total_hits += hits
            
    if total_candidates > 0:
        hit_rate = total_hits / total_candidates
        edge = hit_rate - baseline_rate
        
        # z-test for proportion
        p0 = baseline_rate
        se = np.sqrt(p0 * (1 - p0) / total_candidates)
        z = (hit_rate - p0) / se if se > 0 else 0
        
        print("=" * 60)
        print("熱號休停回歸偵測 (Hot+HighGap) 研究")
        print("條件: freq100 >= 15 AND gap >= 10")
        print(f"測試期數: {test_periods} 期")
        print("=" * 60)
        print(f"出現此信號的期數: {periods_with_candidates} / {test_periods} ({periods_with_candidates/test_periods*100:.1f}%)")
        print(f"總候選號碼數: {total_candidates} (平均每期 {total_candidates/test_periods:.2f} 個)")
        print(f"命中次數: {total_hits}")
        print(f"命中率: {hit_rate*100:.2f}%")
        print(f"基準命中率: {baseline_rate*100:.2f}% (6/49)")
        print(f"Edge: {edge*100:+.2f}%")
        print(f"z-score: {z:+.2f}")
        if z > 1.96:
            print("判定: 顯著有效 (✅ PASS)")
        elif z < -1.96:
            print("判定: 顯著負效 (❌ FAIL)")
        else:
            print("判定: 無顯著差異 (⚠️ MARGINAL/NO SIGNAL)")
    else:
        print("沒有符合條件的候選號碼")

if __name__ == "__main__":
    main()
