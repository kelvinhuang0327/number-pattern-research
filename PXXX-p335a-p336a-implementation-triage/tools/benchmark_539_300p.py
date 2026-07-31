#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
import numpy as np
from datetime import datetime
from collections import Counter

# Add project root to sys.path
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)

# Import strategies and helper functions from the comprehensive backtest script
from tools.backtest_39lotto_comprehensive import (
    load_draws, run_backtest_single, 
    RandomStrategy, HotStrategy, ColdStrategy, RepeatStrategy, MeanReversionStrategy,
    FourierRhythmStrategy, DeviationEchoStrategy, ColdTwinStrategy, MarkovStrategy,
    TripleStrikeStrategy, BayesianStrategy, ConditionalEntropyStrategy, 
    GapAnalysisStrategy, HMMStrategy, ZoneBalanceStrategy, PairFrequencyStrategy,
    BASELINE_1BET_GE2, BASELINE_1BET_GE3
)

def main():
    print("=" * 80)
    print("39樂合彩 (DAILY_539) 300期最佳策略基準測試")
    print(f"啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    draws = load_draws()
    window = 300
    
    print(f"📊 載入 {len(draws)} 期歷史資料")
    print(f"🔬 測試窗口: 最近 {window} 期")
    print(f"📐 基準線: ≥2={BASELINE_1BET_GE2*100:.4f}%, ≥3={BASELINE_1BET_GE3*100:.4f}%")
    print("-" * 80)

    strategies = [
        RandomStrategy(seed=42),
        HotStrategy(window=30),
        HotStrategy(window=50),
        HotStrategy(window=100),
        ColdStrategy(window=50),
        ColdStrategy(window=100),
        RepeatStrategy(),
        MeanReversionStrategy(),
        FourierRhythmStrategy(window=500),
        FourierRhythmStrategy(window=300),
        FourierRhythmStrategy(window=100),
        DeviationEchoStrategy(window=100),
        DeviationEchoStrategy(window=50),
        ColdTwinStrategy(window=100),
        ColdTwinStrategy(window=50),
        MarkovStrategy(window=30),
        MarkovStrategy(window=50),
        TripleStrikeStrategy(fourier_window=500, cold_window=100),
        BayesianStrategy(alpha=1.0, window=200),
        ConditionalEntropyStrategy(window=200),
        GapAnalysisStrategy(window=300),
        HMMStrategy(window=100),
        ZoneBalanceStrategy(window=100),
        PairFrequencyStrategy(window=200),
    ]

    results = []
    print(f"{'Strategy':<30} | {'≥2 Rate':>8} | {'Edge':>8} | {'≥3 Rate':>8}")
    print("-" * 80)
    
    for s in strategies:
        res = run_backtest_single(s, draws, window)
        if res:
            results.append(res)
            print(f"{s.name:<30} | {res['ge2_rate']*100:7.2f}% | {res['ge2_edge']*100:+7.2f}% | {res['ge3_rate']*100:7.2f}%")

    print("\n🏆 排名前 5 的策略 (按 ≥2 Edge):")
    sorted_res = sorted(results, key=lambda x: -x['ge2_edge'])
    for i, r in enumerate(sorted_res[:5]):
        print(f"  #{i+1} {r['strategy']:<30} | Edge: {r['ge2_edge']*100:+6.2f}% | ≥2 Rate: {r['ge2_rate']*100:.2f}% | ≥3 Rate: {r['ge3_rate']*100:.2f}%")

    # Output to JSON for record
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "window": window,
        "results": results
    }
    with open("benchmark_539_300p_results.json", "w") as f:
        json.dump(output_data, f, indent=2)

if __name__ == "__main__":
    main()
