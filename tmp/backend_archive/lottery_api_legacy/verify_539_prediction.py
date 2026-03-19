#!/usr/bin/env python3
import sys
import os
import logging
import numpy as np
sys.path.insert(0, os.getcwd())
from database import db_manager
from models.unified_predictor import UnifiedPredictionEngine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from common import get_lottery_rules

# Quiet logs
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger('539Verify')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)

def main():
    lottery_type = 'DAILY_539'
    try:
        rules = get_lottery_rules(lottery_type)
    except Exception:
        # Fallback if rule name differs
        rules = {'pickCount': 5, 'minNumber': 1, 'maxNumber': 39, 'name': 'DAILY_539'}
        
    all_draws = db_manager.get_all_draws(lottery_type)
    if not all_draws:
        logger.error("❌ No data found for Daily 539")
        return

    # Sort correctly by date (newest first)
    all_draws.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    # Claude used 100 draws
    recent_100 = all_draws[:100]
    
    engine = UnifiedPredictionEngine()
    ensemble = OptimizedEnsemblePredictor(engine)
    
    print("\n" + "="*60)
    print("🧪 DAILY 539 VERIFICATION (Recent 100 Draws)")
    print("="*60)
    
    # 1. Run Optimized Ensemble (My Best)
    logger.info("🧠 Running Optimized Ensemble...")
    pred_ensemble = ensemble.predict_single(recent_100, rules)
    nums_ensemble = pred_ensemble['numbers']
    
    # 2. Run Monte Carlo specific (if possible via engine directly)
    logger.info("🎲 Running Monte Carlo Strategy...")
    # Using the engine method directly if available in ensemble strategies
    try:
        # We can call the engine method directly
        pred_mc = engine.monte_carlo_predict(recent_100, rules)
        nums_mc = pred_mc['numbers']
    except Exception as e:
        logger.warning(f"Monte Carlo run failed: {e}")
        nums_mc = []

    # 3. Comparison
    claude_nums = {4, 5, 7, 14, 28}
    claude_consensus_core = {5, 7, 14, 28}
    
    print("-" * 60)
    print(f"Claude's Prediction  : {sorted(list(claude_nums))}")
    print(f"My Ensemble Result   : {nums_ensemble}")
    print(f"My Monte Carlo Result: {nums_mc}")
    
    print("-" * 60)
    print("🔍 CONSENSUS ANALYSIS:")
    
    my_combined = set(nums_ensemble) | set(nums_mc)
    
    # Check overlap with Claude's full set
    overlap_full = my_combined & claude_nums
    print(f"Overlap with Claude's Full Set: {sorted(list(overlap_full))}")
    
    # Check overlap with Claude's consensus core
    overlap_core = my_combined & claude_consensus_core
    print(f"Overlap with Claude's Core 4  : {sorted(list(overlap_core))}")
    
    # Identify my strong recommendations (intersection of Ensemble & Monte Carlo)
    my_strong = set(nums_ensemble) & set(nums_mc)
    print(f"My Strong Consensus (Ens + MC): {sorted(list(my_strong))}")
    
    # Final recommendation logic
    final_recommendation = overlap_core | my_strong
    print("-" * 60)
    print(f"✅ FINAL SYTHESIZED RECOMMENDATION: {sorted(list(final_recommendation))}")

if __name__ == "__main__":
    main()
