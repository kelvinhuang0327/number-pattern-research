#!/usr/bin/env python3
import sys
import os
import json
import sqlite3
from collections import Counter
import numpy as np

# Add current directory to path
sys.path.insert(0, os.getcwd())

def analyze_distribution():
    print("=" * 80)
    print("📊 BIG_LOTTO vs BIG_LOTTO_BONUS Distribution Analysis")
    print("=" * 80)
    
    # Fix DB path logic - use absolute path if possible or relative to script
    # The script is in lottery_api/analyze_bonus_distribution.py
    # The DB is in lottery_api/data/lottery_v2.db
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # if we are running from root, current_dir might be just 'lottery_api' or similar if resolved relative
    # Let's try explicit paths
    
    possible_paths = [
        "data/lottery_v2.db", # If running from lottery_api dir
        "lottery_api/data/lottery_v2.db", # If running from root dir
        os.path.join(current_dir, "data/lottery_v2.db") # Relative to script
    ]
    
    db_path = None
    for p in possible_paths:
        if os.path.exists(p):
            db_path = p
            break
            
    if not db_path:
        print("❌ Database not found in standard locations.")
        return

    print(f"Using DB: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Get Standard Data
    cursor.execute("SELECT numbers FROM draws WHERE lottery_type = 'BIG_LOTTO'")
    standard_rows = cursor.fetchall()
    standard_nums = []
    for r in standard_rows:
        standard_nums.extend(json.loads(r['numbers']))
        
    # 2. Get Bonus Data
    cursor.execute("SELECT numbers FROM draws WHERE lottery_type = 'BIG_LOTTO_BONUS'")
    bonus_rows = cursor.fetchall()
    bonus_nums = []
    for r in bonus_rows:
        bonus_nums.extend(json.loads(r['numbers']))
        
    print(f"Sample Size:")
    print(f"  Standard Draws: {len(standard_rows)}")
    print(f"  Bonus Draws   : {len(bonus_rows)}")
    print("-" * 80)
    
    # Analyze Range 30-49
    high_range_start = 30
    high_range_end = 49
    
    def get_range_stats(nums, name):
        total = len(nums)
        if total == 0: return 0.0
        
        # Frequency of each number
        counts = Counter(nums)
        
        # Count in range
        in_range = sum(1 for n in nums if high_range_start <= n <= high_range_end)
        ratio = in_range / total
        
        print(f"[{name}]")
        print(f"  Total Numbers Picked: {total}")
        print(f"  Numbers in {high_range_start}-{high_range_end}: {in_range} ({ratio:.2%})")
        
        # Top 5 Hot Numbers
        top_5 = counts.most_common(5)
        print(f"  Top 5 Hot Numbers: {top_5}")
        
        # Check specific numbers user asked about: 34, 35, 39, 43, 45
        targets = [34, 35, 39, 43, 45]
        print(f"  Target Numbers Stats:")
        for t in targets:
            c = counts[t]
            p = c / total * 100
            print(f"    #{t}: {c} times ({p:.2%} of all balls)")
            
        return ratio
        
    r_std = get_range_stats(standard_nums, "Standard BIG_LOTTO")
    print("-" * 40)
    r_bonus = get_range_stats(bonus_nums, "BIG_LOTTO_BONUS")
    print("-" * 80)
    
    diff = r_bonus - r_std
    print(f"Conclusion: Bonus data has {diff:+.2%} more numbers in 30-49 range compared to Standard.")
    
    if diff > 0.05:
        print("👉 YES, Bonus data is significantly skewed towards high numbers.")
    elif diff < -0.05:
        print("👉 NO, Bonus data is skewed towards LOW numbers.")
    else:
        print("👉 NO SIGNIFICANT DIFFERENCE in overall range distribution.")

if __name__ == "__main__":
    analyze_distribution()
