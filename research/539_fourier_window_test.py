
import os
import sys
import numpy as np
import pandas as pd
from collections import Counter
from numpy.fft import fft, fftfreq

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

def _fourier_scores(h, window=500):
    subset = h[-window:]
    w = len(subset)
    scores = {}
    for n in range(1, 40):
        bh = np.zeros(w)
        for idx, d in enumerate(subset):
            if n in d['numbers']: bh[idx] = 1
        if sum(bh) < 2: scores[n] = 0; continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_yf = np.abs(yf[idx_pos])
        pos_xf = xf[idx_pos]
        peak_idx = np.argmax(pos_yf)
        scores[n] = pos_yf[peak_idx] / (abs((w-1-np.where(bh==1)[0][-1]) - (1/pos_xf[peak_idx])) + 1.0)
    return scores

def run_fourier_window_test(n_days=100):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    results = []
    for i in range(len(history) - n_days, len(history)):
        hb = history[:i]
        actual = set(history[i]['numbers'])
        
        s100 = _fourier_scores(hb, 100)
        s200 = _fourier_scores(hb, 200)
        s500 = _fourier_scores(hb, 500)
        
        t100 = sorted(s100.keys(), key=lambda n: -s100[n])[:5]
        t200 = sorted(s200.keys(), key=lambda n: -s200[n])[:5]
        t500 = sorted(s500.keys(), key=lambda n: -s500[n])[:5]
        
        results.append({
            'h100': len(set(t100) & actual),
            'h200': len(set(t200) & actual),
            'h500': len(set(t500) & actual)
        })
        
    df = pd.DataFrame(results)
    print("539 Fourier Window Comparison:")
    print(df.mean())

if __name__ == "__main__":
    run_fourier_window_test(300)
