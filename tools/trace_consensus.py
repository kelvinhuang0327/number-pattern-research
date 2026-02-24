#!/usr/bin/env python3
import torch
import os
import sys
import numpy as np

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from ai_lab.adapter import AIAdapter
from ai_lab.scripts.consensus_predictor import CrossExpertConsensus

def debug_consensus():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    engine = UnifiedPredictionEngine()
    ai_adapter = AIAdapter()
    predictor = CrossExpertConsensus(engine, ai_adapter)
    
    print("🔍 Tracing Consensus Prediction (Last 5 periods)...")
    
    for i in range(5):
        target_idx = len(all_draws) - 5 + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = sorted(target_draw['numbers'])
        
        # Expert Raw Check
        ai_res = ai_adapter.get_ai_prediction('transformer_v3', history, rules)
        ai_c = ai_res.get('numbers', []) if ai_res else []
        
        dms_res = engine.markov_predict(history, rules)
        dms_c = dms_res.get('numbers', [])
        
        fusion_res = predictor.predict_single_precision(history, rules)
        fusion_bet = fusion_res['numbers']
        
        print(f"\nPeriod {target_idx}:")
        print(f"  Actual: {actual}")
        print(f"  AI Rank 1: {ai_c}")
        print(f"  DMS Rank 1: {dms_c}")
        print(f"  Fusion Bet: {fusion_bet}")
        
        m = len(set(fusion_bet) & set(actual))
        print(f"  Match Count: {m}")

if __name__ == "__main__":
    debug_consensus()
