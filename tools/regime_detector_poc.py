#!/usr/bin/env python3
"""
Phase 81: Level 3 Dynamic Waterline PoC
=======================================
Detects "Performance Regimes" (Hot/Cold streaks) in prediction results.
Uses Moving Average Hit Rate to identify periods of clustering.
"""

import pandas as pd
import numpy as np
import random
import matplotlib.pyplot as plt

def simulate_performance(periods=500, base_hit_rate=0.06):
    """
    Simulates hit results (0/1) with clustering effect (Markov Chain).
    Real world lottery hits often exhibit clustering due to methodology bias.
    """
    results = []
    current_state = 0 # 0: Cold, 1: Hot
    
    for _ in range(periods):
        # Transition probabilities
        if current_state == 0: # Cold streak
            hit = 1 if random.random() < base_hit_rate * 0.5 else 0
            if random.random() < 0.05: current_state = 1 # Break cold streak
        else: # Hot streak
            hit = 1 if random.random() < base_hit_rate * 2.5 else 0
            if random.random() < 0.2: current_state = 0 # End hot streak
        results.append(hit)
    return np.array(results)

def detect_regimes(hits, window=20):
    ma_hits = pd.Series(hits).rolling(window=window).mean()
    global_mean = np.mean(hits)
    
    regimes = []
    for val in ma_hits:
        if pd.isna(val):
            regimes.append("N/A")
        elif val < global_mean * 0.5:
            regimes.append("COLD (Low Waterline)")
        elif val > global_mean * 1.5:
            regimes.append("HOT (Momentum)")
        else:
            regimes.append("STABLE (Neutral)")
            
    return ma_hits, regimes

def analyze():
    print("--- Phase 81: Level 3 Dynamic Waterline Simulation ---")
    
    # 1. Simulate 500 periods of '3-bet' hits (M3+ Target: 6%)
    hits = simulate_performance(periods=500, base_hit_rate=0.06)
    
    # 2. Detect Regimes
    ma, regimes = detect_regimes(hits)
    
    # 3. Report Current State (Last 5 periods)
    print("\n[近期水線診斷 - Last 5 Periods]")
    for i in range(-5, 0):
        print(f"Draw t{i}: MA Hit Rate: {ma.iloc[i]*100:.2f}% | 推薦水位: {regimes[i]}")
        
    # 4. Statistical Summary
    counts = pd.Series(regimes).value_counts()
    print("\n[系統體質總結]")
    for regime, count in counts.items():
        if regime != "N/A":
            print(f"- {regime}: 佔比 {count/len(regimes)*100:.1f}%")
            
    print("\n結論: Level 3 管理旨在『趨勢低谷』時減少不必要虧損，在『均值回歸』期捕捉暴衝收益。")

if __name__ == "__main__":
    analyze()
