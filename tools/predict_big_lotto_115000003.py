import sys
import os
import json

# Setup path
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.multi_bet_optimizer import MultiBetOptimizer

def predict():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api/data/lottery_v2.db'))
    all_draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')
    optimizer = MultiBetOptimizer()
    
    if not all_draws:
        print("Error: No data found for BIG_LOTTO")
        return

    last_draw = all_draws[0]
    print(f"📅 Latest Draw: {last_draw['date']} (Issue: {last_draw['draw']})")
    print("-" * 50)
    
    # Generate 4 bets with Skewed Mode enabled
    try:
        res = optimizer.generate_diversified_bets(
            all_draws, rules, num_bets=4, 
            meta_config={
                'method': 'ensemble',
                'skewed_mode': True,  # Enable the new Skewed Mode
                'skewed_zone': 'low'  # Hint: Prefer low skew for insurance against Mean Reversion failure
                # Note: The underlying implementation picks a random zone, but skewed_mode=True is key
            }
        )
        
        print("\n🚀 Big Lotto Prediction (115000003) - Diversified Strategy")
        print("=" * 60)
        for i, bet in enumerate(res['bets'], 1):
            nums = ", ".join(f"{n:02d}" for n in bet['numbers'])
            desc = bet.get('source', 'unknown')
            print(f"💰 Bet {i}: [{nums}]  ({desc})")
        print("=" * 60)
        
    except Exception as e:
        print(f"Error during prediction: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    predict()
