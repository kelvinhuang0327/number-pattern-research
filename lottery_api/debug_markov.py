import sys
import os

# Add current directory to path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from common import get_lottery_rules

def debug_markov():
    lottery_type = 'POWER_LOTTO'
    rules = get_lottery_rules(lottery_type)
    all_draws = db_manager.get_all_draws(lottery_type)
    
    if not all_draws:
        print("No data")
        return

    print(f"Testing Markov (Main) with {len(all_draws)} draws")
    try:
        res = prediction_engine.markov_predict(all_draws, rules)
        print("Markov Main success:", res['numbers'])
    except Exception as e:
        import traceback
        print("Markov Main failed!")
        traceback.print_exc()

    print("\nTesting Markov (Special) via predict_pool_numbers")
    from models.unified_predictor import predict_pool_numbers
    try:
        res = predict_pool_numbers(all_draws, rules, pool_type='special', strategy_name='markov')
        print("Markov Special success:", res['numbers'])
    except Exception as e:
        import traceback
        print("Markov Special failed!")
        traceback.print_exc()

if __name__ == "__main__":
    debug_markov()
