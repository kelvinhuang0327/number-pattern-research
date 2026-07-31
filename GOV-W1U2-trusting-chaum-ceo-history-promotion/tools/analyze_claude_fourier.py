#!/usr/bin/env python3
import os
import sys
import json
import numpy as np

# Setup paths
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.unified_predictor import UnifiedPredictionEngine
from lottery_api.common import load_backend_history
from lottery_api.models.fourier_rhythm import fourier_predictor

def analyze_claude_prediction():
    lottery_type = 'POWER_LOTTO'
    history, rules = load_backend_history(lottery_type)
    
    # history should be ASC for models usually, but load_backend_history returns DESC (newest first)
    # UnifiedPredictionEngine.fourier_main_predict expects DESC history (it handles reversal internally or in fourier_rhythm)
    
    engine = UnifiedPredictionEngine()
    
    # 1. Generate Fourier prediction using our own engine
    print("\n🔍 Generating Fourier prediction using local system (1000 draws window)...")
    # We'll use a larger window to match Claude's "1000 draws validation"
    fourier_res = fourier_predictor.predict_main_numbers(history, max_num=38, window_sizes=[64, 128, 256, 512, 1024])
    
    sorted_nums = sorted(fourier_res.items(), key=lambda x: x[1], reverse=True)
    top_18 = [n for n, s in sorted_nums[:18]]
    top_6 = sorted(top_18[:6])
    
    print(f"Top 6 (Fourier): {top_6}")
    print(f"Top 18 (Fourier): {top_18}")
    
    # 2. Analyze Claude's numbers
    claude_bets = [
        [5, 11, 12, 23, 30, 38],
        [14, 15, 25, 27, 35, 37],
        [8, 16, 20, 21, 22, 34]
    ]
    
    print("\n📊 Analyzing Claude's Prediction vs. Local Fourier Engine:")
    for idx, bet in enumerate(claude_bets):
        overlap = set(bet) & set(top_18)
        print(f"Bet {idx+1}: {bet} | Overlap with Top 18: {sorted(list(overlap))} (Count: {len(overlap)})")
        
    # 3. Check Special Numbers
    special_res = fourier_predictor.predict(history, window_sizes=[64, 128, 256, 512, 1024])
    sorted_specials = sorted(special_res.items(), key=lambda x: x[1], reverse=True)
    print(f"\n✨ Local Fourier Special Recommendation: {[s for s, p in sorted_specials[:3]]}")
    print(f"Claude's Recommendation: 2 > 4 > 3")

    # 4. Expert Opinion Summary
    print("\n============================================================")
    print("🤖 AI PAIR PROGRAMMER OPINION")
    print("------------------------------------------------------------")
    print("1. METHODOLOGY: Fourier Rhythm is a valid cyclical analysis technique.")
    print("2. ALIGNMENT: I'll check the overlap in the output.")
    print("3. VERDICT: Let's see the numbers first.")
    print("============================================================\n")

if __name__ == "__main__":
    analyze_claude_prediction()
