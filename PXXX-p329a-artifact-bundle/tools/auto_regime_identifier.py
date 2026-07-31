#!/usr/bin/env python3
import os
import sys
import json
import numpy as np
import pandas as pd
from typing import Dict, List

# Setup paths
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

def identify_regimes(lottery_type: str = "POWER_LOTTO"):
    """
    Automatically identifies performance differences between short-term and long-term backtests.
    Reads existing benchmark files (150p, 500p, 1500p).
    """
    windows = [150, 500, 1500]
    results = {}
    
    print(f"🔍 Analyzing Backtest Stability for {lottery_type}...")
    print("=" * 60)
    
    # 1. Load results
    for w in windows:
        filename = f"benchmark_{lottery_type}_{w}.json"
        if not os.path.exists(filename):
            print(f"⚠️ Missing {filename}, skipping window {w}...")
            continue
            
        with open(filename, "r") as f:
            data = json.load(f)
            results[w] = data['methods']
            
    if not results:
        print("❌ No benchmark data found. Please run benchmark_new_strategies.py first.")
        return

    # 2. Comparative Analysis
    strategies = list(results[list(results.keys())[0]].keys())
    comparison = []

    for strat in strategies:
        row = {"Strategy": strat}
        for w in windows:
            if w in results and strat in results[w]:
                hits = results[w][strat]['hits']
                # Calculate hit rate
                rate = (hits / w) * 100
                row[f"{w}p_Rate"] = rate
            else:
                row[f"{w}p_Rate"] = None
        comparison.append(row)

    df = pd.DataFrame(comparison)
    
    # 3. Categorization Logic
    def categorize(row):
        r150 = row.get("150p_Rate")
        r500 = row.get("500p_Rate")
        r1500 = row.get("1500p_Rate")
        
        if r150 is None or r1500 is None:
            return "UNKNOWN (Insufficient Data)"
            
        # Decay Thresholds
        decay = r150 - r1500
        relative_decay = decay / r1500 if r1500 > 0 else 0
        
        if decay > 2.0 and relative_decay > 0.2:
            return "⚠️ SHORT-TERM ALPHA (Potential Overfit / Momentum)"
        elif abs(decay) < 0.5:
            return "✅ ROBUST (Long-term Stable)"
        elif decay < -1.0:
            return "📈 LATE BLOOMER (Needs Large Sample)"
        else:
            return "⚖️ MODERATE DECAY (Standard AI Behavior)"

    df["Status"] = df.apply(categorize, axis=1)
    
    # 4. Display Report
    print(df.to_string(index=False))
    print("\n" + "=" * 60)
    print("💡 Recommendations:")
    for _, row in df.iterrows():
        strat = row["Strategy"]
        status = row["Status"]
        if "SHORT-TERM" in status:
            print(f"- {strat}: Only trust for < 50 draws or use Regime Monitor to exit early.")
        elif "ROBUST" in status:
            print(f"- {strat}: Safe for long-term systematic betting.")

    # Save Report
    report_file = f"stability_audit_{lottery_type}.md"
    with open(report_file, "w") as f:
        f.write(f"# Stability Audit Report: {lottery_type}\n\n")
        f.write(df.to_string(index=False))
        f.write("\n\n## Expert Analysis\n")
        f.write("- **Decay Rate**: Strategies with high decay from 150p to 1500p are likely capturing transient noise.\n")
        f.write("- **Consistency**: Robust strategies exhibit < 0.5% variance in hit rates across all windows.\n")
        
    print(f"✅ Report saved to {report_file}")

if __name__ == "__main__":
    lottery = sys.argv[1] if len(sys.argv) > 1 else "POWER_LOTTO"
    identify_regimes(lottery)
