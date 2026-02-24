#!/usr/bin/env python3
import os
import sys
import json
import numpy as np
from collections import Counter

# Setup paths
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.unified_predictor import UnifiedPredictionEngine
from lottery_api.common import load_backend_history
from lottery_api.models.fourier_rhythm import fourier_predictor

def analyze_claude_prediction():
    lottery_type = 'POWER_LOTTO'
    
    # Correct the path for DB access
    os.chdir(os.path.join(project_root, 'lottery_api'))
    history, rules = load_backend_history(lottery_type)
    os.chdir(project_root)
    
    print(f"History length: {len(history)}")
    
    # Generate Fourier prediction
    fourier_res = fourier_predictor.predict_main_numbers(history, max_num=38, window_sizes=[64, 128, 256, 512, 1024])
    
    # Debug: print sample scores
    print("\nSample Scores (Fourier):")
    for n in range(1, 10):
        print(f"Num {n}: {fourier_res.get(n, 0):.4f}")
        
    sorted_nums = sorted(fourier_res.items(), key=lambda x: x[1], reverse=True)
    top_18 = [n for n, s in sorted_nums[:18]]
    print(f"Top 18 (Fourier): {top_18}")
    
    # Check if history is DESC as expected
    print(f"Latest draw in history: {history[0]['draw']} ({history[0]['date']})")
    print(f"Oldest draw in history: {history[-1]['draw']} ({history[-1]['date']})")

if __name__ == "__main__":
    analyze_claude_prediction()
