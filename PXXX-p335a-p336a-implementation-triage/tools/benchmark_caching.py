import os
import sys
import time
import logging

# Set path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from database import db_manager
from common import get_lottery_rules

# Disable noisy logs
logging.basicConfig(level=logging.ERROR)

def benchmark():
    lottery_type = 'POWER_LOTTO'
    rules = get_lottery_rules(lottery_type)
    
    # Fix DB path
    db_path = os.path.join(os.getcwd(), 'lottery_api', 'data', 'lottery_v2.db')
    db_manager.db_path = db_path
        
    all_draws = sorted(db_manager.get_all_draws(lottery_type), key=lambda x: x['draw'])
    test_draws = all_draws[-20:]
    
    engine = UnifiedPredictionEngine()
    ensemble = OptimizedEnsemblePredictor(engine)
    
    print(f"🚀 Starting 20-period benchmark...")
    start_all = time.time()
    
    for i, target in enumerate(test_draws):
        t0 = time.time()
        draw_id = target['draw']
        
        target_pos = next(idx for idx, d in enumerate(all_draws) if d['draw'] == draw_id)
        history = list(reversed(all_draws[:target_pos]))
        
        # Predict 1 bet
        res = ensemble.predict(history, rules, backtest_periods=10, num_bets=1)
        
        t1 = time.time()
        print(f"[{i+1}/20] Draw {draw_id}: {t1-t0:.2f}s")
        
    end_all = time.time()
    print(f"✅ Total Time: {end_all-start_all:.2f}s")
    print(f"📈 Avg Time per period: {(end_all-start_all)/20:.2f}s")

if __name__ == "__main__":
    benchmark()
