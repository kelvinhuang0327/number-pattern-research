#!/usr/bin/env python3
import sys
import os
import json
import numpy as np
from collections import defaultdict
from datetime import datetime

# Add lottery_api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from cvaa_predictor import CVAAPredictor

def run_window_benchmark():
    db_path = os.path.join(os.path.dirname(__file__), 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = db.get_all_draws('DAILY_539')
    
    # 2025 test set (100 draws)
    draws_2025 = [d for d in all_draws if '2025' in d['date'] or d['draw'].startswith('114')][:100]
    rules = get_lottery_rules('DAILY_539')
    cvaa = CVAAPredictor(rules)
    
    window_sizes = [50, 100, 200, 300, 500]
    results = {}
    
    print(f"🔬 Testing CVAA Window Size Sensitivity...")
    
    for w in window_sizes:
        stats = {"matches": 0, "win3": 0, "total": 0}
        
        for target_draw in draws_2025:
            idx = all_draws.index(target_draw)
            history = all_draws[idx+1 : idx+1+w]
            
            if len(history) < w * 0.8: continue
            
            res = cvaa.predict(history)
            if res:
                m = len(set(res['numbers']) & set(target_draw['numbers']))
                stats["matches"] += m
                if m >= 3: stats["win3"] += 1
                stats["total"] += 1
        
        if stats["total"] > 0:
            avg = stats["matches"] / stats["total"]
            wr3 = stats["win3"] / stats["total"]
            results[w] = {"avg": avg, "wr3": wr3, "win3_count": stats["win3"]}
            print(f"  Window {w:3d} | Avg Matches: {avg:.3f} | Win 3+ Rate: {wr3:.2%}")

    print("\n" + "="*50)
    print("🏆 CVAA Window Size Optimization Results")
    print("="*50)
    best_w = max(results.items(), key=lambda x: x[1]['wr3'])
    print(f"🏅 Best Window Size: {best_w[0]} periods")
    print(f"   Win 3+ Rate: {best_w[1]['wr3']:.2%}")
    print(f"   Avg Matches: {best_w[1]['avg']:.3f}")

if __name__ == "__main__":
    run_window_benchmark()
