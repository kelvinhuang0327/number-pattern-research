
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

def analyze_zone_starvation_recovery():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    data = []
    # Track gaps for all numbers
    gaps = {n: 0 for n in range(1, 40)}
    
    for i in range(len(history)):
        curr = set(history[i]['numbers'])
        
        # Zone Gap Sum before this draw
        zone_gaps = [0, 0, 0, 0] # 1-9, 10-19, 20-29, 30-39
        for n in range(1, 40):
            z = (n-1)//10
            if 0 <= z <= 3: zone_gaps[z] += gaps[n]
            
        # Zones in curr draw
        zones_curr = [0, 0, 0, 0]
        for n in curr:
            z = (n-1)//10
            if 0 <= z <= 3: zones_curr[z] += 1
            
        if i > 100: # Warm up
            data.append({
                'draw': history[i]['draw'],
                'zone_gap_sums': zone_gaps.copy(),
                'zones_curr': zones_curr.copy(),
                'max_zone_count': max(zones_curr)
            })
            
        # Update gaps
        for n in range(1, 40):
            if n in curr: gaps[n] = 0
            else: gaps[n] += 1
            
    # Analysis
    results = []
    for z in range(4):
        z_gap_avg = np.mean([d['zone_gap_sums'][z] for d in data])
        # High gap condition (>1.5 std dev)
        z_gap_std = np.std([d['zone_gap_sums'][z] for d in data])
        threshold = z_gap_avg + 1.5 * z_gap_std
        
        starved_draws = [d for d in data if d['zone_gap_sums'][z] > threshold]
        hits_in_starved = np.mean([d['zones_curr'][z] for d in starved_draws])
        prob_cluster_in_starved = len([d for d in starved_draws if d['zones_curr'][z] >= 3]) / len(starved_draws)
        
        baseline_hits = np.mean([d['zones_curr'][z] for d in data])
        baseline_cluster = len([d for d in data if d['zones_curr'][z] >= 3]) / len(data)
        
        results.append({
            'zone': z,
            'starved_hits': hits_in_starved,
            'starved_cluster': prob_cluster_in_starved,
            'baseline_hits': baseline_hits,
            'baseline_cluster': baseline_cluster
        })
        
    res_df = pd.DataFrame(results)
    print("Zone Gap (Starvation) Analysis:")
    print(res_df)

if __name__ == "__main__":
    analyze_zone_starvation_recovery()
