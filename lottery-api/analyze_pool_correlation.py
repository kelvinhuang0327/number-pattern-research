#!/usr/bin/env python3
import sys
import os
import json
import pandas as pd
import numpy as np
from scipy import stats

sys.path.insert(0, os.getcwd())
from database import db_manager

def main():
    lottery_type = 'POWER_LOTTO'
    all_draws = db_manager.get_all_draws(lottery_type)
    
    if not all_draws:
        print("No data found.")
        return

    # Prepare DataFrame
    data = []
    for d in all_draws:
        nums = sorted(d['numbers'])
        special = int(d['special'])
        data.append({
            'draw': d['draw'],
            'sum_s1': sum(nums),
            'avg_s1': np.mean(nums),
            'min_s1': min(nums),
            'max_s1': max(nums),
            'special': special,
            'overlap': 1 if special in nums else 0,
            'numbers': nums
        })
    
    df = pd.DataFrame(data).sort_values('draw')
    
    print("=" * 60)
    print(f"📊 POWER_LOTTO CROSS-POOL CORRELATION ANALYSIS ({len(df)} draws)")
    print("=" * 60)
    
    # 1. Overlap Analysis
    overlap_count = df['overlap'].sum()
    overlap_rate = overlap_count / len(df)
    theoretical_overlap = 6 / 38 # Expectation: around 15.7%
    print(f"1. Overlap Analysis (Special number also in Section 1):")
    print(f"   Actual Overlap: {overlap_count} draws ({overlap_rate:.2%})")
    print(f"   Theoretical   : {theoretical_overlap:.2%}")
    print(f"   Interpretation: {'Similar to random' if abs(overlap_rate - theoretical_overlap) < 0.02 else 'Slightly skewed'}")
    print("-" * 60)
    
    # 2. Statistical Correlation (Contemporaneous)
    print("2. Contemporaneous Correlation (S1 Features vs S2):")
    for feature in ['sum_s1', 'avg_s1', 'min_s1', 'max_s1']:
        corr, p_val = stats.pearsonr(df[feature], df['special'])
        print(f"   - {feature:6} vs Special: Correlation={corr:.4f}, p-value={p_val:.4f}")
    
    print("-" * 60)
    
    # 3. Lag Correlation (Previous S1 vs Current S2)
    df['prev_sum_s1'] = df['sum_s1'].shift(1)
    df['prev_special'] = df['special'].shift(1)
    
    print("3. Lag Correlation (Previous Draw vs Current Special):")
    valid_df = df.dropna()
    corr_lag, p_val_lag = stats.pearsonr(valid_df['prev_sum_s1'], valid_df['special'])
    print(f"   - Previous S1 Sum vs Current Special: Correlation={corr_lag:.4f}, p-value={p_val_lag:.4f}")
    
    corr_rep, p_val_rep = stats.pearsonr(valid_df['prev_special'], valid_df['special'])
    print(f"   - Previous Special vs Current Special: Correlation={corr_rep:.4f}, p-value={p_val_rep:.4f}")
    
    print("-" * 60)
    
    # 4. Odd/Even Ratio Correlation
    df['s1_odd_count'] = df['numbers'].apply(lambda x: sum(1 for n in x if n % 2 != 0))
    df['s2_is_odd'] = df['special'].apply(lambda x: 1 if x % 2 != 0 else 0)
    
    # Chi-square for independence: S1 Odd count vs S2 Odd/Even
    contingency_table = pd.crosstab(df['s1_odd_count'], df['s2_is_odd'])
    chi2, p_chi2, dof, ex = stats.chi2_contingency(contingency_table)
    print("4. Odd/Even Consistency Analysis:")
    print(f"   - S1 Odd Count vs S2 Odd/Even Chi2 p-value: {p_chi2:.4f}")
    print(f"   - Interpretation: {'Identified correlation!' if p_chi2 < 0.05 else 'No significant correlation'}")
    
    print("-" * 60)

if __name__ == '__main__':
    main()
