
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

def analyze_gregariousness():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    total_hits = Counter()
    cluster_hits = Counter() # Hit when its zone had >= 3 hits
    neighbor_hits = Counter() # Hit when at least one neighbor hit
    
    for d in history:
        nums = set(d['numbers'])
        zones = Counter((n-1)//10 for n in nums)
        
        for n in nums:
            total_hits[n] += 1
            z = (n-1)//10
            if zones[z] >= 3:
                cluster_hits[n] += 1
            if (n-1 in nums) or (n+1 in nums):
                neighbor_hits[n] += 1
                
    g_data = []
    for n in range(1, 40):
        g_index = cluster_hits[n] / total_hits[n] if total_hits[n] > 0 else 0
        n_index = neighbor_hits[n] / total_hits[n] if total_hits[n] > 0 else 0
        g_data.append({
            'num': n,
            'total_hits': total_hits[n],
            'cluster_g': g_index,
            'neighbor_g': n_index
        })
        
    df = pd.DataFrame(g_data)
    print("Top Gregarious Numbers (Cluster Mode):")
    print(df.sort_values('cluster_g', ascending=False).head(10))
    
    print("\nTop Gregarious Numbers (Neighbor Mode):")
    print(df.sort_values('neighbor_g', ascending=False).head(10))
    
    # Check 062 numbers
    print("\n062 Numbers G-Indices:")
    print(df[df['num'].isin([11, 12, 14, 17, 32])])

if __name__ == "__main__":
    analyze_gregariousness()
