#!/usr/bin/env python3
"""
Horizon Performance Analyzer
============================
Evaluates strategy performance across 3 time horizons:
- Short (N=150)
- Medium (N=500)
- Long (N=1000)
"""
import os
import sys
import pandas as pd

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.exhaustive_feature_sweep_v2 import ExhaustiveAnalyzer

def run_horizon_comparison(lottery='BIG_LOTTO'):
    analyzer = ExhaustiveAnalyzer(lottery)
    horizons = [150, 500, 1000]
    
    all_data = []
    
    for n in horizons:
        print(f"\n⏳ Testing Horizon: N={n}")
        df = analyzer.sweep_all(n_periods=n)
        df['Horizon'] = n
        all_data.append(df)
        
    final_df = pd.concat(all_data)
    
    # Pivot to compare features across horizons
    pivot = final_df.pivot(index='Feature/Method', columns='Horizon', values='Edge')
    
    print("\n" + "📅" + "="*58 + "📅")
    print(f"   HORIZON STABILITY REPORT: {lottery}")
    print(pivot.to_string())
    print("📅" + "="*58 + "📅")
    return pivot

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', default='BIG_LOTTO')
    args = parser.parse_args()
    
    run_horizon_comparison(args.lottery)
