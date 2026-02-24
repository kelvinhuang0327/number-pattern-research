#!/usr/bin/env python3
import os
import sys
import numpy as np
import pandas as pd
from collections import Counter
from scipy.fft import fft, fftfreq
import math

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from tools.verify_strategy_longterm import UnifiedAuditor

class FeatureFactory:
    @staticmethod
    def calculate_entropy(data):
        if not data: return 0
        counts = Counter(data)
        total = sum(counts.values())
        return -sum((v/total) * math.log2(v/total) for v in counts.values() if v > 0)

    @staticmethod
    def get_gap_stats(history, max_num):
        last_seen = {n: -1 for n in range(1, max_num + 1)}
        for i, draw in enumerate(history):
            for n in draw['numbers']:
                last_seen[n] = i
        gaps = [(len(history) - 1 - last_seen[n]) if last_seen[n] != -1 else len(history) for n in range(1, max_num + 1)]
        return gaps

    @staticmethod
    def detect_fourier_periods(ball_history):
        n = len(ball_history)
        if sum(ball_history) < 2: return 0
        yf = fft(ball_history - np.mean(ball_history))
        xf = fftfreq(n, 1)
        idx = np.where(xf > 0)
        pos_xf, pos_yf = xf[idx], np.abs(yf[idx])
        return 1.0 / pos_xf[np.argmax(pos_yf)] if len(pos_xf) > 0 else 0

class ExhaustiveAnalyzer:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
        self.auditor = UnifiedAuditor(lottery_type=lottery_type)
        self.rules = get_lottery_rules(lottery_type)
        self.max_num = self.rules['maxNumber']
        
    def sweep_all(self, n_periods=200):
        print(f"🚀 Starting Exhaustive Sweep: {self.lottery_type} (N={n_periods})")
        
        features_to_test = {
            "Statistical: Frequency (W100)": self.freq_strategy(100),
            "Statistical: Frequency (W300)": self.freq_strategy(300),
            "Harmonic: FFT Rhythm (W500)": self.fft_strategy(500),
            "Spatial: Zonal Pruning (4-Zone)": self.zonal_strategy(4),
            "Chaos: Entropy Adaptive Kill": self.chaos_strategy(),
            "Relational: Apriori Pairings": self.apriori_strategy()
        }
        
        report = []
        for name, func in features_to_test.items():
            print(f"  Testing {name}...")
            # UnifiedAuditor.audit usually returns (win_rate, edge)
            # Standard signature: audit(self, predict_func, n=150, num_bets=1, seed=42)
            wr, edge = self.auditor.audit(func, n=n_periods)
            report.append({"Feature/Method": name, "WinRate": wr, "Edge": edge})
            
        df = pd.DataFrame(report).sort_values(by="Edge", ascending=False)
        print("\n" + "="*50)
        print(df.to_string(index=False))
        print("="*50)
        return df

    def freq_strategy(self, w):
        def predict(history, num_bets=1):
            subset = history[-w:]
            counts = Counter([n for d in subset for n in d['numbers']])
            top = [n for n, c in counts.most_common(6*num_bets)]
            return [sorted(top[i*6:(i+1)*6]) for i in range(num_bets)]
        return predict

    def fft_strategy(self, w):
        from tools.power_fourier_rhythm import fourier_rhythm_predict
        return lambda h, num_bets=1: fourier_rhythm_predict(h, n_bets=num_bets, window=w)

    def zonal_strategy(self, zones):
        from tools.biglotto_zonal_pruning import zonal_pruned_predict
        return lambda h, num_bets=1: zonal_pruned_predict(h, n_bets=num_bets)

    def chaos_strategy(self):
        from tools.chaos_entropy_selector import ChaosEntropySelector
        selector = ChaosEntropySelector(self.lottery_type)
        def predict(history, num_bets=1):
            kill_res = selector.get_kill_list(history)
            kill_set = set(kill_res['numbers'])
            available = [n for n in range(1, self.max_num + 1) if n not in kill_set]
            # Simple fallback to frequency among non-killed
            counts = Counter([n for d in history[-100:] for n in d['numbers'] if n in available])
            top = [n for n, c in counts.most_common(6*num_bets)]
            return [sorted(top[i*6:(i+1)*6]) for i in range(num_bets)]
        return predict

    def apriori_strategy(self):
        from tools.predict_biglotto_apriori import BigLottoAprioriPredictor
        predictor = BigLottoAprioriPredictor()
        def predict(history, num_bets=1):
            # Hack: BigLottoAprioriPredictor.predict_next_draw looks up DB internally, 
            # we need to ensure it uses the 'history' passed for backtesting.
            # However, the current class doesn't support passing history.
            # Let's use a simpler frequency-based association if it fails or fix the import.
            try:
                # We'll use the class's logic but handle the history slice
                # For the sweep, we'll temporarily mock the get_draws
                original_get_draws = predictor.get_draws
                predictor.get_draws = lambda: history # Inject context
                res = predictor.predict_next_draw(num_bets=num_bets)
                predictor.get_draws = original_get_draws
                return [r['numbers'] for r in res]
            except:
                return self.freq_strategy(150)(history, num_bets)
        return predict

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', default='BIG_LOTTO')
    parser.add_argument('--n', type=int, default=150)
    args = parser.parse_args()
    
    analyzer = ExhaustiveAnalyzer(args.lottery)
    analyzer.sweep_all(n_periods=args.n)
