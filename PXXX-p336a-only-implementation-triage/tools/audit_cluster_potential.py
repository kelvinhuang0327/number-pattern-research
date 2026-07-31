#!/usr/bin/env python3
import os
import sys
import torch
import json
from collections import Counter

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.hpsb_optimizer import HPSBOptimizer
from ai_lab.adapter import AIAdapter

def audit_cluster_potential():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    from models.unified_predictor import UnifiedPredictionEngine
    engine = UnifiedPredictionEngine()
    ai_adapter = AIAdapter()
    hpsb = HPSBOptimizer(engine)
    
    periods = 100 # Audit 100 periods for speed
    cluster_sizes = [15, 18, 21, 24]
    results = {size: Counter() for size in cluster_sizes}
    
    print(f"Auditing Cluster Potential over {periods} periods...")
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        # Get Candidates
        dms_res = hpsb.predict_hpsb_dms(history, rules)
        dms_c = dms_res.get('hpsb_details', {}).get('top_candidates', [])
        
        ai_res = ai_adapter.get_ai_prediction('transformer_v3', history, rules)
        ai_c = ai_res.get('top_candidates', ai_res.get('numbers', [])) if ai_res else []
        if i == 0: print(f"Sample Period AI Count: {len(ai_c)}")
        
        # Fusion
        f_scores = Counter()
        for i_n, n in enumerate(dms_c[:20]): f_scores[n] += (20 - i_n)
        for i_n, n in enumerate(ai_c[:20]): f_scores[n] += (20 - i_n) * 1.5
        
        sorted_fusion = [n for n, s in f_scores.most_common(24)]
        
        for size in cluster_sizes:
            cluster = set(sorted_fusion[:size])
            hits = len(cluster & actual)
            results[size][hits] += 1
            
    print("\n" + "="*40)
    print("📈 CLUSTER POTENTIAL REPORT")
    print("="*40)
    for size in cluster_sizes:
        res = results[size]
        m3_plus = sum(res[h] for h in range(3, 7))
        m4_plus = sum(res[h] for h in range(4, 7))
        m5_plus = sum(res[h] for h in range(5, 7))
        print(f"Cluster Size {size}:")
        print(f"  Match-3+ Coverage: {m3_plus}%")
        print(f"  Match-4+ Coverage: {m4_plus}%")
        print(f"  Match-5+ Coverage: {m5_plus}%")
        print(f"  M6 inside: {res[6]} times")
        print("-" * 20)

if __name__ == "__main__":
    audit_cluster_potential()
