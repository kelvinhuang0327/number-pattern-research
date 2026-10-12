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
    os.chdir(os.path.join(project_root, 'lottery_api'))
    history, rules = load_backend_history(lottery_type)
    os.chdir(project_root)
    
    # Special Number Fourier
    special_res = fourier_predictor.predict(history, window_sizes=[64, 128, 256, 512, 1024])
    sorted_specials = sorted(special_res.items(), key=lambda x: x[1], reverse=True)
    print(f"Local Fourier Special Ranking: {[(s, round(p, 4)) for s, p in sorted_specials[:5]]}")

if __name__ == "__main__":
    analyze_claude_prediction()
