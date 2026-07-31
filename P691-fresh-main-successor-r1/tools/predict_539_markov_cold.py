#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
from datetime import datetime

# Add project root to sys.path
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)

# Import necessary classes from the comprehensive backtest script
from tools.backtest_39lotto_comprehensive import (
    load_draws, MarkovStrategy, ColdStrategy
)

def main():
    # 1. Load data
    draws = load_draws()
    last_draw = draws[-1]
    
    # 2. Define Strategies with optimal windows identified in benchmark
    # Markov: S4_Markov_w30 (High Quality)
    # Cold: B4_Cold_w50 (High Frequency)
    s_markov = MarkovStrategy(window=30)
    s_cold = ColdStrategy(window=50)
    
    # 3. Generate Predictions
    # Note: Strategy.predict takes history as draws[:], so all data up to now
    pred_markov = s_markov.predict(draws)
    pred_cold = s_cold.predict(draws)
    
    # 4. Format Output
    print("=" * 60)
    print("      今彩539 (DAILY_539) 專家系統預測 (兩注組合)")
    print(f"      數據基準: 最後一期 #{last_draw['draw']} ({last_draw['date']})")
    print("=" * 60)
    
    print(f"\n核心組合 A (高質量型 - 馬可夫轉移矩陣):")
    print(f"👉 號碼: {pred_markov}")
    print(f"   原理: 分析號碼間的連結動能，追求 3-4 顆高品質命中。")
    
    print(f"\n核心組合 B (高頻率型 - 冷號機率回補):")
    print(f"👉 號碼: {pred_cold}")
    print(f"   原理: 捕捉近期未出的機率缺口，追求穩定命中領獎。")
    
    # Check for overlaps
    overlaps = sorted(list(set(pred_markov) & set(pred_cold)))
    print(f"\n{'─' * 60}")
    if overlaps:
        print(f"💡 兩注共同號碼: {overlaps} (強信號)")
    else:
        print(f"💡 兩注採取「完全正交/分散」覆蓋 (Max Coverage: 10/39)")
    print("=" * 60)

if __name__ == "__main__":
    main()
