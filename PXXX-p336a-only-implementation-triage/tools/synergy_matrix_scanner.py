#!/usr/bin/env python3
"""
Signal Synergy Scanner
======================
Evaluates the 'Interaction Effect' between different feature families.
Goal: Find a pair (A, B) such that Edge(A+B) > max(Edge(A), Edge(B)).
"""
import os
import sys
import numpy as np
import pandas as pd
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.exhaustive_feature_sweep_v2 import ExhaustiveAnalyzer
from tools.verify_strategy_longterm import UnifiedAuditor

class SynergyScanner(ExhaustiveAnalyzer):
    def scan_synergies(self, n_periods=200):
        print(f"🕵️ Scanning Synergy Matrix for {self.lottery_type} (N={n_periods})")
        
        # 1. Get Individual Base Strategies
        methods = {
            "Zonal": self.zonal_strategy(4),
            "FFT": self.fft_strategy(500),
            "Entropy": self.chaos_strategy(),
            "Wavelet": lambda h, num_bets=1: wavelet_mra_predict(h, n_bets=num_bets)
        }
        from tools.power_wavelet_mra import wavelet_mra_predict
        
        # 2. Audit Individuals First
        base_results = {}
        # We also need the raw rankings/scores to do proper Rank Fusion
        print("--- Auditing Base Features ---")
        for name, func in methods.items():
            wr, edge = self.auditor.audit(func, n=n_periods)
            base_results[name] = edge
            
        # 3. Audit Pairs (Rank Fusion / Borda Count approach)
        pair_results = []
        print("\n--- Auditing Synergies (Rank Fusion) ---")
        for (name1, feat1), (name2, feat2) in combinations(methods.items(), 2):
            print(f"  Testing Synergy: {name1} + {name2}...")
            
            def combined_predict(history, num_bets=1):
                # Proper Rank Fusion:
                # 1. Get candidates (assuming they return sorted top 6)
                res1 = feat1(history, num_bets=1)[0]
                res2 = feat2(history, num_bets=1)[0]
                
                # Borda Count: Highest rank = highest points
                points = {}
                for i, n in enumerate(res1): points[n] = points.get(n, 0) + (6 - i)
                for i, n in enumerate(res2): points[n] = points.get(n, 0) + (6 - i)
                
                # Sort by points
                merged = sorted(points.keys(), key=lambda x: points[x], reverse=True)
                return [sorted(merged[:6])]

            wr, edge = self.auditor.audit(combined_predict, n=n_periods)
            
            expected_max = max(base_results[name1], base_results[name2])
            interaction_gain = edge - expected_max
            
            pair_results.append({
                "Pair": f"{name1}+{name2}",
                "Base1": base_results[name1],
                "Base2": base_results[name2],
                "Combined": edge,
                "Gain": interaction_gain
            })
            
        df = pd.DataFrame(pair_results).sort_values(by="Gain", ascending=False)
        print("\n" + "💎" + "="*58 + "💎")
        print(f"   SYNERGY REPORT: {self.lottery_type}")
        print(df.to_string(index=False))
        print("💎" + "="*58 + "💎")
        return df

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', default='BIG_LOTTO')
    parser.add_argument('--n', type=int, default=150)
    args = parser.parse_args()
    
    scanner = SynergyScanner(args.lottery)
    scanner.scan_synergies(n_periods=args.n)
