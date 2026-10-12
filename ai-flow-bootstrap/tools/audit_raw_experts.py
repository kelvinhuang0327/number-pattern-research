#!/usr/bin/env python3
import torch
import os
import sys
import numpy as np
from collections import Counter

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from ai_lab.adapter import AIAdapter

def run_expert_audit():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    engine = UnifiedPredictionEngine()
    ai_adapter = AIAdapter()
    
    periods = 150
    perf = {'HPSB_DMS': Counter(), 'AI_V3': Counter(), 'RANDOM': Counter()}
    
    from models.hpsb_optimizer import HPSBOptimizer
    hpsb = HPSBOptimizer(engine)
    
    print(f"Auditing Raw Expert Match Distribution over {periods} periods...")
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        # 1. HPSB DMS
        dms_res = hpsb.predict_hpsb_dms(history, rules)
        m_dms = len(set(dms_res['numbers']) & actual)
        perf['HPSB_DMS'][m_dms] += 1
        
        # 2. AI V3
        ai_res = ai_adapter.get_ai_prediction('transformer_v3', history, rules)
        if ai_res:
            m_ai = len(set(ai_res['numbers']) & actual)
            perf['AI_V3'][m_ai] += 1
        
        # 3. Random
        import random
        r_bet = random.sample(range(1, 50), 6)
        m_r = len(set(r_bet) & actual)
        perf['RANDOM'][m_r] += 1
        
    print("\n" + "="*50)
    print("📈 RAW EXPERT MATCH DISTRIBUTION")
    print("="*50)
    for k, dist in perf.items():
        m3_plus = sum(dist[h] for h in range(3, 7))
        m4_plus = sum(dist[h] for h in range(4, 7))
        print(f"{k}:")
        print(f"  M3+: {m3_plus/periods*100:.2f}% ({m3_plus})")
        print(f"  M4+: {m4_plus} hits")
        print(f"  Dists: M3:{dist[3]} M4:{dist[4]} M5:{dist[5]} M6:{dist[6]}")
        print("-" * 30)

if __name__ == "__main__":
    run_expert_audit()
