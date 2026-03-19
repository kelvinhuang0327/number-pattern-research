#!/usr/bin/env python3
import sys
import os
import logging
sys.path.insert(0, os.getcwd())
from database import db_manager
from models.unified_predictor import UnifiedPredictionEngine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from common import get_lottery_rules

# Quiet logs
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger('Comparison')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)

def main():
    lottery_type = 'POWER_LOTTO'
    rules = get_lottery_rules(lottery_type)
    all_draws = db_manager.get_all_draws(lottery_type)
    # Sort correctly by date
    all_draws.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    # 1. Full History (My previous run)
    # We already know this result, skipping re-run to save time, or just logging it.
    
    # 2. Last 100 Draws Only (Claude's config)
    recent_100 = all_draws[:100]
    
    engine = UnifiedPredictionEngine()
    ensemble = OptimizedEnsemblePredictor(engine)
    
    logger.info("🧠 Running Ensemble on Recent 100 Draws Only...")
    prediction_100 = ensemble.predict_single(recent_100, rules)
    
    nums_100 = prediction_100['numbers']
    spec_100 = prediction_100['special']
    
    print("\n" + "="*50)
    print("🧪 SIMULATION: Recent 100 Draws Strategy")
    print("="*50)
    print(f"Numbers: {nums_100}")
    print(f"Special: {spec_100}")
    print(f"Confidence: {prediction_100.get('confidence'):.2f}")
    
    # Comparison
    claude_nums = {5, 8, 9, 15, 20, 37}
    my_full_nums = {3, 6, 15, 23, 24, 38}
    current_100_nums = set(nums_100)
    
    print("\n🔍 Overlap Analysis:")
    print(f"Vs Claude ({sorted(list(claude_nums))}): {len(current_100_nums & claude_nums)} match")
    print(f"   Common: {current_100_nums & claude_nums}")
    print(f"Vs Full History ({sorted(list(my_full_nums))}): {len(current_100_nums & my_full_nums)} match")
    print(f"   Common: {current_100_nums & my_full_nums}")

if __name__ == "__main__":
    main()
