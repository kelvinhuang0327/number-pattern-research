import os
import sys
import logging

# Set path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from database import db_manager
from common import get_lottery_rules

logging.basicConfig(level=logging.ERROR)

def test_multi_bet():
    lottery_type = 'POWER_LOTTO'
    db_path = os.path.join(os.getcwd(), 'lottery_api', 'data', 'lottery_v2.db')
    db_manager.db_path = db_path
    
    target_draw_id = "115000010"
    target_main = {1, 12, 14, 15, 27, 29}
    target_special = 5
    
    all_draws = sorted(db_manager.get_all_draws(lottery_type), key=lambda x: (len(x['draw']), x['draw']))
    history = list(reversed(all_draws))
    
    engine = UnifiedPredictionEngine()
    ensemble = OptimizedEnsemblePredictor(engine)
    rules = get_lottery_rules(lottery_type)
    
    print(f"🎯 MULTI-BET TEST FOR DRAW {target_draw_id}")
    print(f"Target: {sorted(list(target_main))} | {target_special}")
    print("-" * 60)
    
    res = ensemble.predict(history, rules, num_bets=3, backtest_periods=5)
    
    # Extract bets from dictionary (handles both 'bets' list and 'betN' keys)
    bets = res.get('bets', [])
    if not bets:
        for k in sorted(res.keys()):
            if k.startswith('bet') and k[3:].isdigit():
                bets.append(res[k])
    
    any_prize = False
    for i, bet in enumerate(bets):
        nums = set(bet['numbers'])
        spec = bet['special']
        matches = len(nums & target_main)
        s_hit = (spec == target_special)
        prize = (s_hit or matches >= 3)
        if prize: any_prize = True
        
        s_mark = "★" if s_hit else " "
        print(f"Bet {i+1}: {sorted(list(nums))} | {s_mark} {spec} | Matches: {matches} | Prize: {'YES' if prize else 'NO'}")

    print("-" * 60)
    print(f"Overall Result: {'SUCCESS' if any_prize else 'FAILURE'}")

if __name__ == "__main__":
    test_multi_bet()
