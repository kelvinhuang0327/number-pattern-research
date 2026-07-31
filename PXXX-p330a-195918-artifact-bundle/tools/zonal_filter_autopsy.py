#!/usr/bin/env python3
"""
Zonal Filter Autopsy
Measures how many historical WINNING draws pass the Zonal Equilibrium check.
If this is low, the filter is fundamentally flawed for prediction.
"""

import json
import sqlite3
import os
from typing import List

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"

def check_zonal_thermodynamics(numbers: List[int], max_num: int) -> bool:
    if not numbers: return False
    zone_size = 7 if max_num > 40 else 8
    num_zones = (max_num // zone_size) + 1
    profile = [0] * num_zones
    for n in numbers:
        z_idx = (n - 1) // zone_size
        if z_idx < num_zones:
            profile[z_idx] += 1
    max_in_zone = max(profile)
    zones_covered = sum(1 for x in profile if x > 0)
    
    # The criteria I implemented:
    # 1. max_in_zone <= 2
    # 2. 3 <= zones_covered <= 5
    is_valid = (max_in_zone <= 2) and (3 <= zones_covered <= 5)
    return is_valid

def run_autopsy(lottery_type, max_num):
    db_path = os.path.join(project_root, 'lottery_api/data/lottery_v2.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT numbers FROM draws WHERE lottery_type = ? ORDER BY draw DESC LIMIT 1000", (lottery_type,))
    rows = cursor.fetchall()
    conn.close()
    
    total = len(rows)
    passed = 0
    failures = {"clustering": 0, "dispersion": 0}
    
    for row in rows:
        nums = json.loads(row[0])
        z_size = 7 if max_num > 40 else 8
        num_zones = (max_num // z_size) + 1
        profile = [0] * num_zones
        for n in nums:
            z_idx = (n - 1) // z_size
            if z_idx < num_zones: profile[z_idx] += 1
        
        max_in_zone = max(profile)
        zones_covered = sum(1 for x in profile if x > 0)
        
        valid = True
        if max_in_zone > 2:
            failures["clustering"] += 1
            valid = False
        if zones_covered < 3 or zones_covered > 5:
            failures["dispersion"] += 1
            valid = False
            
        if valid: passed += 1
            
    print(f"\nAutopsy Report: {lottery_type}")
    print(f"Total Winning Draws Analyzed: {total}")
    print(f"Passed Zonal Filter: {passed} ({passed/total*100:.1f}%)")
    print(f"Rejected Winning Draws: {total - passed} ({(total-passed)/total*100:.1f}%)")
    print(f"  - Failed Clustering (>2 in zone): {failures['clustering']}")
    print(f"  - Failed Dispersion (<3 or >5 zones): {failures['dispersion']}")

if __name__ == "__main__":
    run_autopsy('BIG_LOTTO', 49)
    run_autopsy('POWER_LOTTO', 38)
