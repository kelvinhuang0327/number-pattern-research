#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
import numpy as np
import time
from typing import List, Dict
from collections import Counter
import logging

# Setup paths
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.unified_predictor import UnifiedPredictionEngine
from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer
from lottery_api.common import load_backend_history

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_benchmark(lottery_type: str, periods: int, resume: bool = True):
    # Change CWD to lottery_api to ensure relative paths for database work correctly
    original_cwd = os.getcwd()
    os.chdir(os.path.join(project_root, 'lottery_api'))
    
    try:
        # 修正：確保庫路徑正確，如果是從 tools 執行
        sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
        from common import load_backend_history
        history, rules = load_backend_history(lottery_type)
    finally:
        os.chdir(original_cwd)
    
    # 確保歷史從新到舊
    if int(history[0]['draw']) < int(history[-1]['draw']):
        history = list(reversed(history))
    
    engine = UnifiedPredictionEngine()
    optimizer = MultiBetOptimizer()
    
    checkpoint_file = f"benchmark_{lottery_type}_{periods}_checkpoint.json"
    start_idx = 0
    methods = {
        'Orthogonal_3Bet': {'hits': 0, 'm3': 0, 'm4': 0, 'm5': 0, 'm6': 0},
        'VAE_Single': {'hits': 0, 'm3': 0, 'm4': 0, 'm5': 0, 'm6': 0},
        'Frequency_Baseline': {'hits': 0, 'm3': 0, 'm4': 0, 'm5': 0, 'm6': 0},
        'Random_3Bet': {'hits': 0, 'm3': 0, 'm4': 0, 'm5': 0, 'm6': 0},
        'Frequency_3Bet': {'hits': 0, 'm3': 0, 'm4': 0, 'm5': 0, 'm6': 0}
    }

    if resume and os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, "r") as f:
                ckpt = json.load(f)
                start_idx = ckpt['last_idx'] + 1
                methods = ckpt['methods']
                print(f"🔄 Resuming {lottery_type} from checkpoint: draw {start_idx}/{periods}")
        except Exception as e:
            print(f"⚠️ Failed to load checkpoint: {e}")

    print(f"\n🚀 Starting Benchmark: {lottery_type} | {periods} Draw Periods")
    print("=" * 60)
    
    start_time = time.time()
    
    for i in range(start_idx, periods):
        if i >= len(history) - 1: break
        
        target_draw = history[i]
        target_nums = set(target_draw['numbers'])
        history_for_prediction = history[i+1:]
        
        if (i + 1) % 50 == 0:
            elapsed = time.time() - start_time
            print(f"⌛ Progress: {i+1}/{periods} draws processed... (Avg: {elapsed/(i+1-start_idx):.2f}s/draw)")
            # Save checkpoint
            with open(checkpoint_file, "w") as f:
                json.dump({'last_idx': i, 'methods': methods}, f)

        # 1. Orthogonal 3-Bet (Target Strategy)
        try:
            res = optimizer.generate_diversified_bets(history_for_prediction, rules, num_bets=3)
            best_match = 0
            for b in res['bets']:
                match_count = len(set(b['numbers']) & target_nums)
                best_match = max(best_match, match_count)
            
            if best_match >= 3:
                methods['Orthogonal_3Bet']['hits'] += 1
                methods['Orthogonal_3Bet'][f'm{min(best_match, 6)}'] += 1
        except: pass

        # 2. VAE (Single Bet)
        try:
            vae_epochs = 20 if i % 50 == 0 else 0
            vae_res = engine.vae_predict(history_for_prediction, rules, epochs=vae_epochs)
            match_count = len(set(vae_res['numbers']) & target_nums)
            if match_count >= 3:
                methods['VAE_Single']['hits'] += 1
                methods['VAE_Single'][f'm{min(match_count, 6)}'] += 1
        except: pass

        # 3. Frequency Baseline (Single Bet)
        try:
            pick_count = rules.get('pickCount', 6)
            all_nums = [n for d in history_for_prediction[:100] for n in d['numbers']]
            top_6 = [n for n, c in Counter(all_nums).most_common(pick_count)]
            match_count = len(set(top_6) & target_nums)
            if match_count >= 3:
                methods['Frequency_Baseline']['hits'] += 1
                methods['Frequency_Baseline'][f'm{min(match_count, 6)}'] += 1
        except: pass

        # 4. RANDOM 3-Bet (New Crucial Baseline: Apples-to-Apples)
        try:
            import random as py_random
            max_num = rules.get('maxNumber', 49)
            min_num = rules.get('minNumber', 1)
            pick_count = rules.get('pickCount', 6)
            
            # Generate 3 orthogonal random bets
            all_pool = list(range(min_num, max_num + 1))
            py_random.shuffle(all_pool)
            
            best_match_rnd = 0
            for k in range(3):
                # Orthogonal selection
                subset = all_pool[k*pick_count : (k+1)*pick_count]
                if len(subset) < pick_count:
                    # Fill with random if pool exhausted (unlikely for 38/49)
                    remaining = list(set(range(min_num, max_num+1)) - set(subset))
                    subset.extend(py_random.sample(remaining, pick_count - len(subset)))
                
                match_count = len(set(subset) & target_nums)
                best_match_rnd = max(best_match_rnd, match_count)
            
            if best_match_rnd >= 3:
                methods['Random_3Bet']['hits'] += 1
                methods['Random_3Bet'][f'm{min(best_match_rnd, 6)}'] += 1
        except: pass

        # 5. Frequency 3-Bet (New Crucial Baseline: Apples-to-Apples)
        try:
            pick_count = rules.get('pickCount', 6)
            all_nums = [n for d in history_for_prediction[:100] for n in d['numbers']]
            top_18 = [n for n, c in Counter(all_nums).most_common(pick_count * 3)]
            
            best_match_freq3 = 0
            for k in range(3):
                subset = top_18[k*pick_count : (k+1)*pick_count]
                if len(subset) < pick_count: break
                match_count = len(set(subset) & target_nums)
                best_match_freq3 = max(best_match_freq3, match_count)
                
            if best_match_freq3 >= 3:
                methods['Frequency_3Bet']['hits'] += 1
                methods['Frequency_3Bet'][f'm{min(best_match_freq3, 6)}'] += 1
        except: pass

    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "="*60)
    print(f"📊 BENCHMARK RESULTS ({lottery_type} | {periods} Draws) - Duration: {duration:.1f}s")
    print("-" * 60)
    print(f"{'Method':<20} | {'M3+ Rate':<10} | {'Hits':<5} | {'M3/M4/M5/M6'}")
    print("-" * 60)
    
    total_processed = min(periods, len(history) - 1)
    for name, stats in methods.items():
        rate = (stats['hits'] / total_processed) * 100
        detail = f"{stats['m3']}/{stats['m4']}/{stats['m5']}/{stats['m6']}"
        print(f"{name:<20} | {rate:>7.2f}% | {stats['hits']:<5} | {detail}")
    
    print("=" * 60)
    
    # Save final results
    result_data = {
        'lottery_type': lottery_type,
        'periods': periods,
        'duration': duration,
        'methods': methods,
        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(f"benchmark_{lottery_type}_{periods}.json", "w") as f:
        json.dump(result_data, f, indent=4)
    
    # Clean up checkpoint
    if os.path.exists(checkpoint_file):
        os.remove(checkpoint_file)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Multi-Strategy Benchmark')
    parser.add_argument('type', choices=['POWER_LOTTO', 'BIG_LOTTO'], help='Lottery type')
    parser.add_argument('periods', type=int, nargs='*', default=[150, 500, 1500], help='Draw periods to test')
    parser.add_argument('--no-resume', action='store_false', dest='resume', help='Disable resume from checkpoint')
    
    args = parser.parse_args()
    
    for p in args.periods:
        run_benchmark(args.type, p, resume=args.resume)
