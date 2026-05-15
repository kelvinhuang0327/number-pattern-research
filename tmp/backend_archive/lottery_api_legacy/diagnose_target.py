#!/usr/bin/env python3
import sys
import os
import json
import numpy as np

sys.path.insert(0, os.getcwd())
from database import db_manager

def calculate_ac_value(numbers):
    """Calculate the Arithmetic Complexity (AC) value"""
    diffs = set()
    nums = sorted(numbers)
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            diffs.add(nums[j] - nums[i])
    return len(diffs) - (len(nums) - 1)

def analyze_draw(numbers, special):
    nums = sorted(numbers)
    return {
        'sum': sum(nums),
        'ac': calculate_ac_value(nums),
        'odd_even': f"{len([n for n in nums if n % 2 != 0])}:{len([n for n in nums if n % 2 == 0])}",
        'gaps': [nums[i+1] - nums[i] for i in range(len(nums)-1)],
        'special': special
    }

def main():
    target_nums = [8, 15, 16, 21, 29, 37]
    target_special = 5
    target_stats = analyze_draw(target_nums, target_special)
    
    all_draws = db_manager.get_all_draws('POWER_LOTTO')
    recent_draws = all_draws[:500]
    
    history_stats = []
    for d in recent_draws:
        try:
            nums = json.loads(d['numbers']) if isinstance(d['numbers'], str) else d['numbers']
            history_stats.append(analyze_draw(nums, d['special']))
        except:
            continue
            
    avg_sum = np.mean([s['sum'] for s in history_stats])
    avg_ac = np.mean([s['ac'] for s in history_stats])
    
    print("-" * 60)
    print("📊 STATISTICAL ANALYSIS: TARGET vs. HISTORY (W=500)")
    print("-" * 60)
    print(f"Feature      | Target     | History Avg")
    print("-" * 60)
    print(f"Sum          | {target_stats['sum']:10d} | {avg_sum:10.2f}")
    print(f"AC Value     | {target_stats['ac']:10d} | {avg_ac:10.2f}")
    print(f"Odd:Even     | {target_stats['odd_even']:10s} | N/A")
    print(f"Gaps         | {str(target_stats['gaps']):10s} | N/A")
    print(f"Special      | {target_stats['special']:10d} | N/A")
    print("-" * 60)
    
    # Check if target sum is within 1 std dev
    sum_std = np.std([s['sum'] for s in history_stats])
    if abs(target_stats['sum'] - avg_sum) > sum_std:
        print(f"⚠️  Sum {target_stats['sum']} is an outlier (StdDev: {sum_std:.2f})")
    else:
        print(f"✅ Sum {target_stats['sum']} is within normal range.")

    # Check for consecutive numbers
    consecutive = [g for g in target_stats['gaps'] if g == 1]
    if consecutive:
        print(f"⚠️  Has consecutive numbers: {consecutive}")

if __name__ == '__main__':
    main()
