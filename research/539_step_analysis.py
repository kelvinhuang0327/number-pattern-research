
import os
import sys
import numpy as np
import pandas as pd
from collections import Counter

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def analyze_step_sequences():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    count_plus_1 = 0
    count_seq_1_2 = 0
    count_seq_1_2_3 = 0
    
    for d in history:
        nums = sorted(d['numbers'])
        diffs = np.diff(nums)
        
        # Check for +1, +2, +3
        has_1 = 1 in diffs
        has_1_2 = any((diffs[i] == 1 and diffs[i+1] == 2) or (diffs[i] == 2 and diffs[i+1] == 1) for i in range(len(diffs)-1))
        has_1_2_3 = any((diffs[i] == 1 and diffs[i+1] == 2 and diffs[i+2] == 3) for i in range(len(diffs)-2))
        
        if has_1: count_plus_1 += 1
        if has_1_2: count_seq_1_2 += 1
        if has_1_2_3: count_seq_1_2_3 += 1
        
    total = len(history)
    print(f"539 Step Sequence Statistics (N={total}):")
    print(f"Prob(Any +1 diff): {count_plus_1/total:.2%}")
    print(f"Prob(Seq +1, +2): {count_seq_1_2/total:.2%}")
    print(f"Prob(Seq +1, +2, +3): {count_seq_1_2_3/total:.2%}")

if __name__ == "__main__":
    analyze_step_sequences()
