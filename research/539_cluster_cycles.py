
import os
import sys
import numpy as np
import pandas as pd
from numpy.fft import fft, fftfreq

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def analyze_cluster_periodicity():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    for z in range(4):
        # Time series of "is cluster in zone z?"
        cluster_ts = []
        for d in history:
            count = len([n for n in d['numbers'] if (n-1)//10 == z])
            cluster_ts.append(1 if count >= 3 else 0)
            
        cluster_ts = np.array(cluster_ts)
        w = len(cluster_ts)
        if sum(cluster_ts) < 5: continue
            
        yf = fft(cluster_ts - np.mean(cluster_ts))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_yf = np.abs(yf[idx_pos])
        pos_xf = xf[idx_pos]
        
        peak_indices = np.argsort(pos_yf)[-3:][::-1]
        print(f"\nZone {z} (Cluster >= 3) Periods:")
        for idx in peak_indices:
            p = 1 / pos_xf[idx]
            str_val = pos_yf[idx]
            print(f"  Period: {p:.2f} draws | Strength: {str_val:.2f}")

if __name__ == "__main__":
    analyze_cluster_periodicity()
