#!/usr/bin/env python3
import torch
import os
import sys
import numpy as np

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from ai_lab.adapter import AIAdapter

def trace_logits():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    
    ai_adapter = AIAdapter()
    
    print("🔬 Tracing AI V3 Confidence (Last 10 periods)...")
    
    for i in range(10):
        target_idx = len(all_draws) - 10 + i
        history = all_draws[:target_idx]
        
        # We need to modify AIAdapter to return raw probs or just look at them here
        # For now, let's just use the adapter and assume we can get them if we modify it
        res = ai_adapter.get_ai_prediction('transformer_v3', history, {})
        
        print(f"\nPeriod {target_idx}:")
        print(f"  Top Numbers: {res['numbers']}")
        # We'll modify AIAdapter in the next tool call to include max_prob
        print(f"  Confidence: {res.get('confidence', 'N/A')}")

if __name__ == "__main__":
    trace_logits()
