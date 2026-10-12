#!/usr/bin/env python3
import torch
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

from ai_lab.adapter import AIAdapter
from ai_lab.scripts.elite_portfolio_optimizer import HighPrizePredictor

# Add lottery_api to path to fix 'from database' issue
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    engine = UnifiedPredictionEngine()
    ai_adapter = AIAdapter()
    predictor = HighPrizePredictor(engine, ai_adapter)
    
    print("=" * 80)
    print("🔬 Phase 14: AI-Lab High-Prize Elite (5-Bet) Benchmark")
    print("=" * 80)
    
    periods = 200
    total = 0
    wins = 0
    match_dist = Counter()
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        if target_idx <= 0: continue
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            # We don't need to redirect stdout here as it's cleaner
            res = predictor.predict_high_prize(history, rules)
            bets = res['bets']
            
            # Winner if ANY bet in portfolio hits Match-3+
            best_m = 0
            for b in bets:
                m = len(set(b) & actual)
                if m > best_m: best_m = m
            
            if best_m >= 3: wins += 1
            match_dist[best_m] += 1
            total += 1
            
            if (i+1) % 20 == 0:
                print(f"Processed {i+1}/{periods}... Current M3+ Rate: {wins/total*100:.2f}% | M4+: {match_dist[4]+match_dist[5]+match_dist[6]}")
                
        except Exception as e:
            # logger.error(f"Error: {e}")
            continue

    rate = wins / total * 100 if total > 0 else 0
    print("-" * 80)
    print(f"✅ Final High-Prize Elite Success Rate (200期): {rate:.2f}%")
    print(f"📊 Match Distribution: M3:{match_dist[3]} M4:{match_dist[4]} M5:{match_dist[5]} M6:{match_dist[6]} M0:{match_dist[0]+match_dist[1]+match_dist[2]}")
    
    # Analyze high-prize efficiency
    m4_plus = match_dist[4] + match_dist[5] + match_dist[6]
    print(f"🚀 High-Prize Efficiency: {m4_plus} Match-4+ hits in 200 periods.")
    print("=" * 80)

if __name__ == "__main__":
    main()
