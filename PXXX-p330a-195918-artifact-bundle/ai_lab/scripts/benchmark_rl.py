#!/usr/bin/env python3
import torch
import torch.nn as nn
import json
import os
import sys
import numpy as np
import random
from collections import Counter
import contextlib
import io

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
sys.path.insert(0, os.path.join(project_root, 'ai_lab'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from models.hpsb_optimizer import HPSBOptimizer
from ai_models.transformer_v2 import HybridLotteryTransformer
from scripts.benchmark_hybrid import HybridPredictor

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

class RLPredictor(HybridPredictor):
    def predict(self, history, rules):
        # same logic as HybridPredictor but uses rl_gen3_best.pth
        return super().predict(history, rules)

def run_benchmark(name, predict_func, all_draws, rules, periods=200):
    set_seed(42)
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        if target_idx <= 0: continue
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = predict_func(history, rules)
            m = len(set(res['numbers']) & actual)
            if m >= 3: match_3_plus += 1
            match_dist[m] += 1
            total += 1
        except Exception as e:
            continue
    rate = match_3_plus / total * 100 if total > 0 else 0
    return rate, match_3_plus, total, match_dist

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    rl_model_path = os.path.join(project_root, 'ai_lab', 'ai_models', 'rl_gen3_best.pth')
    hybrid_model_path = os.path.join(project_root, 'ai_lab', 'ai_models', 'hybrid_best.pth')
    
    if not os.path.exists(rl_model_path):
        print("RL Model not found.")
        return
        
    rl_predictor = RLPredictor(rl_model_path)
    hybrid_predictor = HybridPredictor(hybrid_model_path)
    hpsb_v2 = HPSBOptimizer(UnifiedPredictionEngine())
    
    print("=" * 70)
    print("🔬 AI-Lab Phase 9: RL Reward Optimization Benchmark")
    print("=" * 70)
    
    strategies = [
        ("DMS (SOTA Baseline)", hpsb_v2.predict_hpsb_v2),
        ("Hybrid AI (Gen-2)", hybrid_predictor.predict),
        ("RL-Weighted (Gen-3)", rl_predictor.predict)
    ]
    
    for name, func in strategies:
        rate, count, total, dist = run_benchmark(name, func, all_draws, rules, 200)
        print(f"{name:20}: {rate:5.2f}% ({count:2d}/{total}) | M3:{dist[3]} M4:{dist[4]} M5:{dist[5]} M0:{dist[0]}")
    
    print("=" * 70)

if __name__ == "__main__":
    main()
