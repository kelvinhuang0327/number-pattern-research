#!/usr/bin/env python3
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
from models.hpsb_optimizer import HPSBOptimizer

def analyze_overlap():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    engine = UnifiedPredictionEngine()
    ai_adapter = AIAdapter()
    hpsb = HPSBOptimizer(engine)
    
    periods = 100 # Fast check
    
    total_jaccard = 0
    total_intersection = 0
    
    print("🔬 Analyzing AI V3 vs DMS Overlap (100 periods)...")
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        history = all_draws[:target_idx]
        
        # Expert 1: AI V3
        ai_res = ai_adapter.get_ai_prediction('transformer_v3', history, rules)
        ai_set = set(ai_res.get('top_candidates', [])[:6])
        
        # Expert 2: DMS
        dms_res = hpsb.predict_hpsb_dms(history, rules)
        dms_set = set(dms_res.get('numbers', [])[:6])
        
        # Metrics
        intersection = len(ai_set & dms_set)
        union = len(ai_set | dms_set)
        jaccard = intersection / union if union > 0 else 0
        
        total_intersection += intersection
        total_jaccard += jaccard
        
    avg_int = total_intersection / periods
    avg_jac = total_jaccard / periods
    
    print("-" * 50)
    print(f"✅ Average Intersection: {avg_int:.2f} numbers")
    print(f"✅ Average Jaccard Similarity: {avg_jac:.2f}")
    print("-" * 50)
    if avg_int < 2.5:
        print("💡 Recommendation: High Orthogonality. Use in Parallel Bets.")
    else:
        print("⚠️ Recommendation: High Overlap. Redundant signals.")

if __name__ == "__main__":
    analyze_overlap()
