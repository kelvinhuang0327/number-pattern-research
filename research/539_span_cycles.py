
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

def analyze_span_cycles():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    spans = [max(d['numbers']) - min(d['numbers']) for d in history]
    spans = np.array(spans)
    
    # Autocorrelation
    df = pd.Series(spans)
    print("Span Autocorrelation (Lag 1-5):")
    for i in range(1, 6):
        print(f"Lag {i}: {df.autocorr(lag=i):.3f}")
        
    # Fourier on spans
    w = len(spans)
    yf = fft(spans - np.mean(spans))
    xf = fftfreq(w, 1)
    idx_pos = np.where(xf > 0)
    pos_yf = np.abs(yf[idx_pos])
    pos_xf = xf[idx_pos]
    peak_indices = np.argsort(pos_yf)[-3:][::-1]
    print("\nSpan Periods:")
    for idx in peak_indices:
        p = 1 / pos_xf[idx]
        print(f"  Period: {p:.2f} draws")

if __name__ == "__main__":
    analyze_span_cycles()
