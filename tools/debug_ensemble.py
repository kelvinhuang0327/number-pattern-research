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

# Set logging to see what's happening
logging.basicConfig(level=logging.INFO)

engine = UnifiedPredictionEngine()
ensemble = OptimizedEnsemblePredictor(engine)

db_path = os.path.join(os.getcwd(), 'lottery_api', 'data', 'lottery_v2.db')
db_manager.db_path = db_path
all_draws = list(reversed(db_manager.get_all_draws(lottery_type='POWER_LOTTO')))
rules = get_lottery_rules('POWER_LOTTO')

# Test one prediction
history = all_draws[:100]
print("Starting prediction...")
try:
    res = ensemble.predict(history, rules, backtest_periods=1)
    print("Result:", res)
except Exception as e:
    print("Error:", e)
    import traceback
    traceback.print_exc()
