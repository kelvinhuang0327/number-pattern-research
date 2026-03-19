import os
import sys
import logging

# Set path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from database import db_manager
from common import get_lottery_rules

logging.basicConfig(level=logging.ERROR)

def inspect_lag():
    lottery_type = 'POWER_LOTTO'
    db_path = os.path.join(os.getcwd(), 'lottery_api', 'data', 'lottery_v2.db')
    db_manager.db_path = db_path
    
    all_draws = sorted(db_manager.get_all_draws(lottery_type), key=lambda x: (len(x['draw']), x['draw']))
    history = list(reversed(all_draws))
    
    engine = UnifiedPredictionEngine()
    rules = get_lottery_rules(lottery_type)
    
    print(f"🔬 INSPECTING LAG REVERSION FOR 115000010")
    print("-" * 60)
    
    res = engine.lag_reversion_predict(history, rules)
    print(f"Method: {res['method']}")
    print(f"Predicted Numbers: {res['numbers']}")
    print(f"Predicted Special: {res.get('special')}")
    
    # Check matches
    target_main = {1, 12, 14, 15, 27, 29}
    matches = set(res['numbers']) & target_main
    print(f"Matches: {matches}")
    
    # Raw scores inspection
    scores = engine.lag_predictor.calculate_scores(history)
    refined = engine.zone_refiner.refine(history, scores)
    
    sorted_refined = sorted(refined.items(), key=lambda x: x[1], reverse=True)
    print("\nTop 15 Refined Scores:")
    for n, s in sorted_refined[:15]:
        mark = "✓" if n in target_main else " "
        print(f"{mark} {n:>2}: {s:.4f}")

if __name__ == "__main__":
    inspect_lag()
