
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

def analyze_zone_density_cycles():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    data = []
    for d in history:
        nums = sorted(d['numbers'])
        # Avg distance between numbers in the same zone
        zones = {}
        for n in nums:
            z = (n-1)//10
            zones.setdefault(z, []).append(n)
            
        densities = []
        for z, ns in zones.items():
            if len(ns) >= 2:
                # Density = inverse of avg diff
                densities.append(1.0 / np.mean(np.diff(ns)))
                
        avg_density = np.mean(densities) if densities else 0
        data.append(avg_density)
        
    df = pd.Series(data)
    # Autocorrelation
    print("Density Autocorrelation (Lag 1-5):")
    for i in range(1, 6):
        print(f"Lag {i}: {df.autocorr(lag=i):.3f}")
        
    # Moving average trend
    df_ma = df.rolling(10).mean()
    print(f"\nRecent Density Trend (Last 5):")
    print(df_ma.tail(5))

if __name__ == "__main__":
    analyze_zone_density_cycles()
