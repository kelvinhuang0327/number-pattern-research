#!/usr/bin/env python3
"""
探索 #3: 中頻帶盲區統計量化
==============================
問題: #115000015 的 6 個開獎號全部在中頻帶 (100期頻率在 avg ±30% 內)。
      TS3 專攻兩端 (Fourier = 高頻共振, Cold = 低頻逆向)，對中頻帶天然失明。

目的: 量化「全部中頻」型開獎的歷史出現頻率。
  - 如果很少 (<10%)，不值得針對設計策略
  - 如果常見 (>20%)，TS3 有結構性盲區需要補強
"""
import os
import sys
import numpy as np
from collections import Counter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))

from lottery_api.database import DatabaseManager

MAX_NUM = 49
PICK = 6
FREQ_WINDOW = 100  # 計算頻率用的窗口


def classify_number(freq_val, avg_freq, threshold=0.30):
    """將號碼分類為 HOT / COLD / NORMAL"""
    if freq_val > avg_freq * (1 + threshold):
        return 'HOT'
    elif freq_val < avg_freq * (1 - threshold):
        return 'COLD'
    else:
        return 'NORMAL'


def main():
    print("=" * 70)
    print("🔬 探索 #3: 中頻帶盲區統計量化")
    print(f"   頻率窗口: {FREQ_WINDOW}期 | 閾值: ±30%")
    print("=" * 70)
    
    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'),
                   key=lambda x: (x.get('date', ''), x.get('draw', 0)))
    
    avg_freq = FREQ_WINDOW * PICK / MAX_NUM  # Expected frequency per number
    print(f"  Total draws: {len(draws)}")
    print(f"  Expected freq per number (in {FREQ_WINDOW}p): {avg_freq:.1f}")
    
    # Scan from draw #200 onwards (need enough history)
    start = max(200, FREQ_WINDOW)
    
    pattern_counts = Counter()  # e.g. "6N" = all normal, "3H2N1C" = mix
    all_normal_count = 0
    all_extreme_count = 0  # All HOT or all COLD
    total = 0
    
    # Also track: how many winning numbers are HOT/COLD/NORMAL
    hot_win_count = 0
    cold_win_count = 0
    normal_win_count = 0
    total_win_numbers = 0
    
    for idx in range(start, len(draws)):
        history = draws[idx - FREQ_WINDOW:idx]
        target = draws[idx]
        actual = target['numbers']
        
        # Calculate frequency in window
        freq = Counter(n for d in history for n in d['numbers'])
        
        classifications = []
        for n in actual:
            f = freq.get(n, 0)
            c = classify_number(f, avg_freq)
            classifications.append(c)
            if c == 'HOT':
                hot_win_count += 1
            elif c == 'COLD':
                cold_win_count += 1
            else:
                normal_win_count += 1
            total_win_numbers += 1
        
        # Pattern
        hot_count = classifications.count('HOT')
        cold_count = classifications.count('COLD')
        normal_count = classifications.count('NORMAL')
        
        pattern = f"H{hot_count}N{normal_count}C{cold_count}"
        pattern_counts[pattern] += 1
        
        if normal_count == 6:
            all_normal_count += 1
        if hot_count + cold_count == 6:
            all_extreme_count += 1
        
        total += 1
    
    # Results
    print(f"\n  Analyzed {total} draws\n")
    
    # Overall distribution
    print(f"  [1] 中獎號碼的頻率分佈:")
    print(f"      HOT:    {hot_win_count:>5} ({hot_win_count/total_win_numbers*100:5.1f}%)")
    print(f"      NORMAL: {normal_win_count:>5} ({normal_win_count/total_win_numbers*100:5.1f}%)")
    print(f"      COLD:   {cold_win_count:>5} ({cold_win_count/total_win_numbers*100:5.1f}%)")
    
    # All-normal draws
    print(f"\n  [2] 全部中頻 (6個號全NORMAL) 的出現頻率:")
    print(f"      {all_normal_count}/{total} = {all_normal_count/total*100:.1f}%")
    
    # All-extreme draws
    print(f"\n  [3] 全部極端 (6個號全HOT或全COLD，無NORMAL) 的出現頻率:")
    print(f"      {all_extreme_count}/{total} = {all_extreme_count/total*100:.1f}%")
    
    # Top patterns
    print(f"\n  [4] 最常見的開獎型態 (Top 10):")
    for pattern, count in pattern_counts.most_common(10):
        pct = count / total * 100
        bar = "█" * int(pct)
        print(f"      {pattern:<12} {count:>4} ({pct:5.1f}%) {bar}")
    
    # How often does TS3 have at least 1 HOT or COLD target?
    has_hot_or_cold = total - all_normal_count
    print(f"\n  [5] 至少有1個HOT或COLD號碼的開獎:")
    print(f"      {has_hot_or_cold}/{total} = {has_hot_or_cold/total*100:.1f}%")
    print(f"      (這些期次 TS3 的 Fourier/Cold 有機會捕獲)")
    
    print(f"\n  [6] 結論:")
    if all_normal_count / total > 0.20:
        print(f"      ⚠️ 全中頻型態佔 {all_normal_count/total*100:.1f}% (>20%)，TS3 存在顯著結構盲區")
    elif all_normal_count / total > 0.10:
        print(f"      ⚠️ 全中頻型態佔 {all_normal_count/total*100:.1f}% (10-20%)，值得關注但不嚴重")
    else:
        print(f"      ✅ 全中頻型態僅佔 {all_normal_count/total*100:.1f}% (<10%)，TS3 盲區影響有限")
    
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
