#!/usr/bin/env python3
import sys
import os
import logging
from collections import Counter
sys.path.insert(0, os.getcwd())
from database import db_manager
from models.unified_predictor import UnifiedPredictionEngine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from common import get_lottery_rules

# Quiet logs
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger('BigLottoPredict')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)

def main():
    lottery_type = 'BIG_LOTTO'
    rules = get_lottery_rules(lottery_type)
    
    # 1. Load Data
    all_draws = db_manager.get_all_draws(lottery_type)
    all_draws.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    if not all_draws:
        print("❌ No data found.")
        return

    last_draw = all_draws[0]
    print(f"📅 Last Draw: {last_draw['draw']} ({last_draw['date']})")
    print("-" * 60)
    
    engine = UnifiedPredictionEngine()
    ensemble = OptimizedEnsemblePredictor(engine)
    
    # 2. Strategy A: Full History (SOTA/Long-term patterns)
    logger.info("🧠 Strategy A: Full History Optimized Ensemble...")
    pred_full = ensemble.predict_single(all_draws, rules)
    nums_full = set(pred_full['numbers'])
    
    # 3. Strategy B: Recent 100 Draws (Short-term heatmap)
    logger.info("🔥 Strategy B: Recent 100 Draws (Trend Analysis)...")
    recent_100 = all_draws[:100]
    pred_100 = ensemble.predict_single(recent_100, rules)
    nums_100 = set(pred_100['numbers'])

    # 4. Consensus Analysis
    intersection = nums_full & nums_100
    union = nums_full | nums_100
    
    print("\n" + "="*60)
    print("✨ BIG LOTTO PREDICTION ANALYSIS ✨")
    print("="*60)
    
    print(f"\n🅰️  Full History Model   : {sorted(list(nums_full))}")
    print(f"🅱️  Recent 100 Model     : {sorted(list(nums_100))}")
    
    print(f"\n🔗 Consensus (Strongest): {sorted(list(intersection))}")
    if intersection:
        print("   -> These numbers appear in BOTH long-term and short-term models.")
    else:
        print("   -> No strict consensus found, patterns are shifting.")
        
    # Recommendation Logic
    recommendation = list(intersection)
    
    # Fill remaining from Full History first (usually more stable for Big Lotto), then Recent
    remaining_slots = 6 - len(recommendation)
    if remaining_slots > 0:
        # Prioritize numbers from Full History that are not in intersection
        candidates_full = sorted(list(nums_full - intersection))
        recommendation.extend(candidates_full[:remaining_slots])
        
    remaining_slots = 6 - len(recommendation)
    if remaining_slots > 0:
         # Then numbers from Recent 100
        candidates_100 = sorted(list(nums_100 - intersection))
        recommendation.extend(candidates_100[:remaining_slots])
        
    recommendation = sorted(recommendation)
    
    print("-" * 60)
    print(f"🎯 FINAL RECOMMENDATION: {recommendation}")
    print(f"   (Confidence: {pred_full.get('confidence', 0.8):.1%})")
    print("=" * 60)

if __name__ == "__main__":
    main()
