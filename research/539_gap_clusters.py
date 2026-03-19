
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

def analyze_gap_clusters():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    gaps = {n: 0 for n in range(1, 40)}
    data = []
    
    for i in range(len(history)):
        curr = set(history[i]['numbers'])
        
        # Current gaps
        curr_gaps = [gaps[n] for n in curr]
        
        # Categorize gaps
        # 0: Echo (Lag-1)
        # 1-3: Hot
        # 4-10: Warm
        # 11-20: Cold
        # 21+: Extreme
        categories = []
        for g in curr_gaps:
            if g == 0: categories.append('Echo')
            elif g <= 3: categories.append('Hot')
            elif g <= 10: categories.append('Warm')
            elif g <= 20: categories.append('Cold')
            else: categories.append('Extreme')
            
        data.append(Counter(categories))
        
        # Update gaps
        for n in range(1, 40):
            if n in curr: gaps[n] = 0
            else: gaps[n] += 1
            
    df = pd.DataFrame(data).fillna(0)
    print("539 Gap Category Clusters (Counts per draw):")
    print(df.mean())
    
    # 062 check
    print("\n062 Check (Recent Draw Context):")
    # I'll manually check 062 later if I find high variance.
    print(df.tail(5))
    
    # Is there a "Warm Cluster" syndrome?
    # Prob(Warm >= 3)
    print(f"\nProb(Echo >= 2): {len(df[df['Echo'] >= 2]) / len(df):.2%}")
    print(f"Prob(Warm >= 3): {len(df[df['Warm'] >= 3]) / len(df):.2%}")

if __name__ == "__main__":
    analyze_gap_clusters()
