#!/usr/bin/env python3
import sys
import os
import json
import pandas as pd
import numpy as np
from collections import Counter

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

def analyze():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    
    df = pd.DataFrame(all_draws)
    # Parse numbers from JSON string
    df['numbers'] = df['numbers'].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
    
    # Target draw: 115000009
    target_nums = [9, 13, 27, 31, 32, 39]
    target_special = 19
    
    print("--- Exhaustive Feature Analysis for 115000009 ---")
    
    # 1. Odd/Even Ratio Frequency
    df['odd_count'] = df['numbers'].apply(lambda nums: sum(1 for n in nums if n % 2 == 1))
    odd_counts = df['odd_count'].value_counts(normalize=True).sort_index()
    print(f"\nOdd/Even Ratio Distribution:")
    print(odd_counts)
    print(f"Target Draw Odd Count: 5. Frequency of 5:1 Odd:Even = {odd_counts.get(5, 0)*100:.2f}%")
    
    # 2. Sum Distribution
    df['sum'] = df['numbers'].apply(sum)
    mean_sum = df['sum'].mean()
    std_sum = df['sum'].std()
    target_sum = sum(target_nums)
    z_score = (target_sum - mean_sum) / std_sum
    print(f"\nSum Stats: Mean={mean_sum:.1f}, Std={std_sum:.1f}")
    print(f"Target Draw Sum: {target_sum}. Z-Score: {z_score:.2f}")
    
    # 3. Tail (Unit digit) Analysis
    def get_tails(nums):
        return [n % 10 for n in nums]
    
    df['tails'] = df['numbers'].apply(get_tails)
    target_tails = get_tails(target_nums)
    target_tail_counts = Counter(target_tails)
    print(f"\nTarget Tails: {target_tails} (Tail 9 repeated twice)")
    
    # Frequency of 2 or more numbers having same tail
    df['max_tail_freq'] = df['tails'].apply(lambda tails: max(Counter(tails).values()))
    tail_freq_dist = df['max_tail_freq'].value_counts(normalize=True).sort_index()
    print(f"Max tail recurrence distribution:\n{tail_freq_dist}")
    
    # 4. Range (Max - Min)
    df['range'] = df['numbers'].apply(lambda nums: max(nums) - min(nums))
    avg_range = df['range'].mean()
    target_range = max(target_nums) - min(target_nums)
    print(f"\nRange: Avg={avg_range:.1f}, Target={target_range}")
    
    # 5. Consecutive Numbers
    def count_consecutive(nums):
        sorted_nums = sorted(nums)
        count = 0
        for i in range(len(sorted_nums)-1):
            if sorted_nums[i+1] - sorted_nums[i] == 1:
                count += 1
        return count
    
    df['consecutive'] = df['numbers'].apply(count_consecutive)
    consec_dist = df['consecutive'].value_counts(normalize=True).sort_index()
    print(f"\nConsecutive Count Distribution:\n{consec_dist}")
    print(f"Target Consecutive: 1 (Frequency: {consec_dist.get(1, 0)*100:.2f}%)")

    # 6. Special Number Relative to Main
    # Is Special Number usually a "missing" number from previous draws?
    # For now, just check its Odd/Even
    print(f"\nSpecial Number: {target_special} (Odd)")
    
if __name__ == "__main__":
    analyze()
