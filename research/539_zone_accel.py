
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

def analyze_zone_acceleration():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    data = []
    for d in history:
        zones = Counter((n-1)//10 for n in d['numbers'])
        data.append([zones[z] for z in range(4)])
        
    df = pd.DataFrame(data, columns=['Z0', 'Z1', 'Z2', 'Z3'])
    
    # Acceleration
    vel = df.diff()
    acc = vel.diff()
    
    print("Zone Count Autocorrelation:")
    for z in range(4):
        print(f"Zone {z} Lag-1: {df['Z'+str(z)].autocorr(lag=1):.3f}")
        
    # Correlation between Velocity and Next Count
    for z in range(4):
        corr = vel['Z'+str(z)].shift(1).corr(df['Z'+str(z)])
        print(f"Zone {z} Velocity -> Next Count Corr: {corr:.3f}")

if __name__ == "__main__":
    analyze_zone_acceleration()
