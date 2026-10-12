#!/usr/bin/env python3
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
from models.hpsb_optimizer import HPSBOptimizer

def calculate_entropy(draws):
    # Zone entropy (7 zones)
    zone_counts = [0] * 7
    total = 0
    for d in draws:
        for n in d['numbers']:
            z = min((n-1)//7, 6)
            zone_counts[z] += 1
            total += 1
    
    probs = [c/total for c in zone_counts if c > 0]
    return -sum(p * np.log(p) for p in probs)

def audit_regime():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    engine = UnifiedPredictionEngine()
    ai_adapter = AIAdapter()
    hpsb = HPSBOptimizer(engine)
    
    periods = 200 # Look at last 200 to see trends
    
    # Features vs Outcome
    data = [] 
    
    print("🔬 Auditing Regime Correlations (200 periods)...")
    
    expert_wins = {'AI': 0, 'DMS': 0, 'Draw': 0}
    
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        # 1. Market Features (The State)
        recent_10 = history[-10:]
        
        # Feature A: Entropy (Chaos Level)
        ent = calculate_entropy(recent_10)
        
        # Feature B: Volatility (Mean Change)
        means = [np.mean(d['numbers']) for d in recent_10]
        vol = np.std(means)
        
        # Feature C: Repeat Rate (Stagnation)
        last_nums = set(history[-1]['numbers'])
        prev_nums = set(history[-2]['numbers'])
        rep = len(last_nums & prev_nums)
        
        # 2. Expert Performance (The Outcome)
        # AI
        ai_res = ai_adapter.get_ai_prediction('transformer_v3', history, rules)
        ai_hits = len(set(ai_res['top_candidates'][:6]) & actual)
        
        # DMS
        dms_res = hpsb.predict_hpsb_dms(history, rules)
        dms_hits = len(set(dms_res['numbers']) & actual)
        
        winner = 'Draw'
        if ai_hits > dms_hits: winner = 'AI'
        elif dms_hits > ai_hits: winner = 'DMS'
        
        expert_wins[winner] += 1
        data.append({'entropy': ent, 'volatility': vol, 'repeat': rep, 'winner': winner})
        
    print("-" * 60)
    print("🏆 Win Counts:", expert_wins)
    print("-" * 60)
    
    # Simple Correlation Check
    # Average Entropy when AI wins vs when DMS wins
    ai_ent = [d['entropy'] for d in data if d['winner'] == 'AI']
    dms_ent = [d['entropy'] for d in data if d['winner'] == 'DMS']
    
    ai_vol = [d['volatility'] for d in data if d['winner'] == 'AI']
    dms_vol = [d['volatility'] for d in data if d['winner'] == 'DMS']
    
    print(f"📊 Market State Analysis:")
    print(f"  Avg Entropy (AI Wins): {np.mean(ai_ent):.4f}")
    print(f"  Avg Entropy (DMS Wins): {np.mean(dms_ent):.4f}")
    print(f"  Diff: {np.mean(ai_ent) - np.mean(dms_ent):.4f}")
    print("  (Positive diff = AI prefers Chaos)")
    
    print(f"\n  Avg Volatility (AI Wins): {np.mean(ai_vol):.4f}")
    print(f"  Avg Volatility (DMS Wins): {np.mean(dms_vol):.4f}")
    print(f"  Diff: {np.mean(ai_vol) - np.mean(dms_vol):.4f}")
    
    # Hypothesis check
    if np.mean(ai_ent) > np.mean(dms_ent):
        print("\n✅ Hypothesis Supported: AI V3 performs better in high-entropy (Chaotic) markets.")
    else:
        print("\n❌ Hypothesis Weak: No clear regime separation detected.")

if __name__ == "__main__":
    audit_regime()
