#!/usr/bin/env python3
import torch
import os
import sys
import numpy as np
import random
from collections import Counter

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from ai_lab.adapter import AIAdapter
from ai_lab.scripts.structural_ai_predictor import StructuralAIPredictor

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    engine = UnifiedPredictionEngine()
    ai_adapter = AIAdapter()
    predictor = StructuralAIPredictor(engine, ai_adapter)
    
    print("=" * 80)
    print("🔬 Phase 22+: Structural AI 3-Bet Portfolio Benchmark")
    print("=" * 80)
    
    periods = 150
    total = 0
    wins = 0
    match_dist = Counter()
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            res = predictor.predict_portfolio(history, rules, num_bets=3)
            bets = res['bets']
            
            # Check if any bet won
            round_best = 0
            hit = False
            for bet in bets:
                m = len(set(bet) & actual)
                if m > round_best: round_best = m
                if m >= 3: hit = True
            
            if hit: wins += 1
            match_dist[round_best] += 1
            total += 1
            
            if (i+1) % 30 == 0:
                print(f"Processed {i+1}/{periods}... Current 3-Bet Win Rate: {wins/total*100:.2f}%")
                
        except Exception as e:
            # print(e)
            continue

    rate = wins / total * 100 if total > 0 else 0
    print("-" * 80)
    print(f"✅ Final Structural AI 3-Bet Success Rate (150期): {rate:.2f}%")
    print(f"📊 Match Distribution (Best per Round): M3:{match_dist[3]} M4:{match_dist[4]} M5:{match_dist[5]} M6:{match_dist[6]} M0:{match_dist[0]+match_dist[1]+match_dist[2]}")
    print("=" * 80)

if __name__ == "__main__":
    main()
