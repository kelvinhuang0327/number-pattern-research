
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

def analyze_structural_features():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    data = []
    for i in range(1, len(history)):
        curr = set(history[i]['numbers'])
        prev = set(history[i-1]['numbers'])
        
        # Current draw structure
        zones = [0, 0, 0, 0] # 1-9, 10-19, 20-29, 30-39
        for n in curr:
            z = (n-1)//10
            if 0 <= z <= 3: zones[z] += 1
        max_zone_count = max(zones)
        
        # Lag features
        repeats = len(curr & prev)
        neighbors = 0
        for pn in prev:
            if (pn-1 in curr) or (pn+1 in curr):
                neighbors += 1
                
        # Tail repeats
        tails = [n % 10 for n in curr]
        tail_counts = Counter(tails)
        max_tail_repeat = max(tail_counts.values())
        
        data.append({
            'draw': history[i]['draw'],
            'max_zone_count': max_zone_count,
            'repeats': repeats,
            'neighbors': neighbors,
            'serial_links': repeats + neighbors,
            'max_tail_repeat': max_tail_repeat,
            'sum': sum(curr),
            'prev_max_zone_count': (data[-1]['max_zone_count'] if data else 0),
            'prev_repeats': (data[-1]['repeats'] if data else 0)
        })
        
    df = pd.DataFrame(data)
    
    print("539 Structural Statistics:")
    print(f"Total draws: {len(df)}")
    print(f"Prob(Zone Cluster >= 4): {len(df[df['max_zone_count'] >= 4]) / len(df):.2%}")
    print(f"Prob(Tail Repeat >= 2): {len(df[df['max_tail_repeat'] >= 2]) / len(df):.2%}")
    
    # Correlation analysis
    corr = df[['max_zone_count', 'repeats', 'neighbors', 'serial_links', 'max_tail_repeat', 'sum']].corr()
    print("\nFeature Correlation Matrix:")
    print(corr)
    
    # Predictability of Zone Cluster?
    print("\nZone Cluster Predictability:")
    # If prev draw had a cluster, does curr draw have one?
    cluster_after_cluster = len(df[(df['prev_max_zone_count'] >= 3) & (df['max_zone_count'] >= 3)]) / len(df[df['prev_max_zone_count'] >= 3])
    baseline_cluster = len(df[df['max_zone_count'] >= 3]) / len(df)
    print(f"Prob(Cluster >= 3 | Prev Cluster >= 3): {cluster_after_cluster:.2%} (Baseline: {baseline_cluster:.2%})")
    
    # Predictability of Repetitions?
    repeat_after_high_serial = len(df[(df['serial_links'].shift(1) >= 3) & (df['repeats'] >= 1)]) / len(df[df['serial_links'].shift(1) >= 3])
    baseline_repeat = len(df[df['repeats'] >= 1]) / len(df)
    print(f"Prob(Repeat >= 1 | Prev Serial Links >= 3): {repeat_after_high_serial:.2%} (Baseline: {baseline_repeat:.2%})")

if __name__ == "__main__":
    analyze_structural_features()
