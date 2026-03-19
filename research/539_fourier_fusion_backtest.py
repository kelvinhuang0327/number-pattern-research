
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
from tools.quick_predict import _539_acb_bet, _539_markov_bet

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

def run_fourier_fusion_backtest(n_days=500):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    
    results = []
    for i in range(len(history) - n_days, len(history)):
        hb = history[:i]
        actual = set(history[i]['numbers'])
        
        b1 = _539_acb_bet(hb)
        b2 = _539_markov_bet(hb, exclude=set(b1))
        
        # Method A: Global Fourier 500p (Ctrl)
        sf_500 = _fourier_scores(hb, 500)
        b3_ctrl = sorted([n for n in range(1, 40) if n not in set(b1)|set(b2)], key=lambda n: -sf_500.get(n, 0))[:5]
        
        # Method B: Fusion (500p + 100p)
        sf_100 = _fourier_scores(hb, 100)
        fusion = {n: 0.5*sf_500.get(n,0) + 0.5*sf_100.get(n,0) for n in range(1, 40)}
        b3_fusion = sorted([n for n in range(1, 40) if n not in set(b1)|set(b2)], key=lambda n: -fusion.get(n, 0))[:5]
        
        results.append({
            'draw': history[i]['draw'],
            'h_ctrl': len(set(b3_ctrl) & actual),
            'h_fusion': len(set(b3_fusion) & actual)
        })
        
    df = pd.DataFrame(results)
    print(f"Fourier Fusion Backtest (Last {n_days} draws):")
    print(f"Mean Hits (500p):   {df['h_ctrl'].mean():.3f}")
    print(f"Mean Hits (Fusion): {df['h_fusion'].mean():.3f}")
    print(f"Delta: {df['h_fusion'].mean() - df['h_ctrl'].mean():+.3f}")

if __name__ == "__main__":
    run_fourier_fusion_backtest(300)
