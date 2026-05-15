#!/usr/bin/env python3
import sys
import os
import logging
from typing import List, Dict
import pandas as pd
import numpy as np
from collections import Counter

# Setup path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.feature_analyzer import LotteryFeatureAnalyzer
from common import load_backend_history

# Disable logs
logging.getLogger().setLevel(logging.ERROR)

def analyze_feature_importance():
    lottery_type = 'BIG_LOTTO'
    history, rules = load_backend_history(lottery_type)
    
    print("=" * 60)
    print(f"🔍 自動化特徵重要性分析 (大樂透 歷史數據: {len(history)} 期)")
    print("=" * 60)

    analyzer = LotteryFeatureAnalyzer()
    
    feature_history = []
    
    # Analyze correlation between feature and "Next Win"
    # To keep it simple, we see if a high/low feature value predicts certain number properties
    
    for i in range(len(history) - 1):
        prev_draws = history[i+1 : i+21] # Context: last 20 draws
        current_draw = history[i] # Target: current winning numbers
        
        if len(prev_draws) < 10: continue
        
        # Calculate features for the winning numbers
        win_nums = current_draw['numbers']
        
        # Calculate features
        stats = {
            'entropy': analyzer.calculate_entropy(win_nums),
            'harmonic_mean': analyzer.calculate_harmonic_mean(win_nums),
            'gap_variance': analyzer.calculate_gap_variance(win_nums),
            'ac_value': analyzer.calculate_ac_value(win_nums),
            'even_ratio': sum(1 for n in win_nums if n % 2 == 0) / len(win_nums),
            'sum': sum(win_nums)
        }
        feature_history.append(stats)

    df = pd.DataFrame(feature_history)
    
    # Calculate stability and distribution
    print(f"{'特徵名稱':<15} | {'平均值':<10} | {'標準差':<10} | {'預測價值 (Signal)'}")
    print("-" * 60)
    
    for col in df.columns:
        mean = df[col].mean()
        std = df[col].std()
        # "Signal" defined as (1 - CV) where CV is coef of variation
        # Higher signal means the feature is more concentrated in a specific range for winners
        cv = std / mean if mean != 0 else 1
        signal = max(0, 1 - cv)
        
        stars = "⭐" * int(signal * 10)
        print(f"{col:<15} | {mean:10.2f} | {std:10.2f} | {stars}")

    print("=" * 60)
    print("💡 結論：星等越高 (Signal 越高)，代表該特徵在開獎組合中分佈越集中。")
    print("   這代表我們應該給予這些特徵更高的「正則化」權重。")

if __name__ == '__main__':
    analyze_feature_importance()
