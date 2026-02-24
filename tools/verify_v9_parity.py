import os
import sys
import logging
from collections import Counter

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.advanced_strategies import AdvancedStrategies
from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.utils.backtest_safety import (
    validate_chronological_order, 
    get_safe_backtest_slice
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ParityVerification')

def run_parity_test(periods: int = 150):
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = validate_chronological_order(db.get_all_draws('BIG_LOTTO'))
    
    # Initialize Production Class
    adv = AdvancedStrategies()
    rules = get_lottery_rules('BIG_LOTTO')
    
    results = {
        'Anomaly-Cluster (Production)': {'m3+': 0, 'm4+': 0},
    }
    
    test_data = all_draws[-periods:]
    logger.info(f"🚀 Starting Parity Backtest: {periods} periods (Using Production Code)")
    
    for i, target_draw in enumerate(test_data):
        target_idx = all_draws.index(target_draw)
        history = get_safe_backtest_slice(all_draws, target_idx)
        actual = set(target_draw['numbers'])
        
        # Call ported production method
        # Note: anomaly_cluster_predict already returns 4 bets in 'details'
        pred_result = adv.anomaly_cluster_predict(history, rules)
        bets = pred_result['details']['bets']
        
        max_h = 0
        for b in bets:
            h = len(set(b) & actual)
            max_h = max(max_h, h)
            
        if max_h >= 3: results['Anomaly-Cluster (Production)']['m3+'] += 1
        if max_h >= 4: results['Anomaly-Cluster (Production)']['m4+'] += 1
        
        if (i+1) % 20 == 0:
            logger.info(f"Progress: {i+1}/{periods}...")

    # Report
    print("\n" + "="*60)
    print(f"{'Strategy':30} | {'M3+':5} | {'M4+':5} | {'M3 Rate':8}")
    print("-" * 60)
    for name, stat in results.items():
        rate = (stat['m3+'] / periods) * 100
        print(f"{name:30} | {stat['m3+']:5d} | {stat['m4+']:5d} | {rate:7.2f}%")
    print("="*60)
    
    # Comparison check
    if results['Anomaly-Cluster (Production)']['m3+'] == 14:
        print("✅ SUCCESS: Production code exactly matches Research benchmark (14 hits / 9.33%)")
    else:
        print(f"❌ FAILURE: Mismatch detected. Production: {results['Anomaly-Cluster (Production)']['m3+']} Research: 14")

if __name__ == "__main__":
    run_parity_test(150)
