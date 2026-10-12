import os
import sys
import logging

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.unified_predictor import UnifiedPredictionEngine
from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.utils.backtest_safety import (
    validate_chronological_order, 
    get_safe_backtest_slice
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GNNVerify')

def run_gnn_verification(periods: int = 500):
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = validate_chronological_order(db.get_all_draws('POWER_LOTTO'))
    
    rules = get_lottery_rules('POWER_LOTTO')
    engine = UnifiedPredictionEngine()
    
    hits = 0
    test_data = all_draws[-periods:]
    
    logger.info(f"🚀 Starting GNN (1-bet) Verification: {periods} periods")
    
    for i, target_draw in enumerate(test_data):
        target_idx = all_draws.index(target_draw)
        history = get_safe_backtest_slice(all_draws, target_idx)
        actual_numbers = set(target_draw['numbers'])
        
        # 使用 GNN 預測
        result = engine.gnn_predict(history, rules)
        predicted = set(result['numbers'])
        
        matches = len(predicted & actual_numbers)
        if matches >= 3:
            hits += 1
            
        if (i+1) % 50 == 0:
            current_rate = (hits / (i+1)) * 100
            logger.info(f"Progress: {i+1}/{periods} | M3+ Hit Rate: {current_rate:.2f}%")

    # Report
    rate = (hits / periods) * 100
    
    print("\n" + "="*60)
    print(f"🎯 POWER LOTTO GNN (1-BET) VERIFICATION")
    print(f"📊 Periods: {periods}")
    print(f"🎯 Hits (M3+): {hits}")
    print(f"📈 Hit Rate: {rate:.2f}%")
    print(f"🎲 Random Baseline (1-bet): 3.87%")
    print("-" * 60)
    
    edge = rate - 3.87
    if edge > 0:
        print(f"✅ SUCCESS: GNN achieved {rate:.2f}% hit rate (+{edge:.2f}% Edge)")
    else:
        print(f"❌ FAILURE: Hit rate at {rate:.2f}% ({edge:.2f}% Edge)")
    print("="*60)

if __name__ == "__main__":
    import sys
    periods = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    run_gnn_verification(periods)
