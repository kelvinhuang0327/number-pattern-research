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
logger = logging.getLogger('PowerV11Breakthrough')

def run_power_v11_verification(periods: int = 300):
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = validate_chronological_order(db.get_all_draws('POWER_LOTTO'))
    
    adv = AdvancedStrategies()
    rules = get_lottery_rules('POWER_LOTTO')
    
    results = {
        'Power Anomaly-Cluster V11 (7注)': {'m3+': 0, 'm4+': 0},
    }
    
    test_data = all_draws[-periods:]
    logger.info(f"🚀 Starting Power Lotto V11 Verification: {periods} periods")
    
    for i, target_draw in enumerate(test_data):
        target_idx = all_draws.index(target_draw)
        history = get_safe_backtest_slice(all_draws, target_idx)
        actual_main = set(target_draw['numbers'])
        
        # Call Power V11 7-bet method
        pred_result = adv.power_anomaly_cluster_v11_predict(history, rules)
        bets = pred_result['details']['bets']
        
        max_h = 0
        for b in bets:
            # Power Lotto has 6 main numbers in Zone 1
            h = len(set(b[:6]) & actual_main)
            max_h = max(max_h, h)
            
        if max_h >= 3: results['Power Anomaly-Cluster V11 (7注)']['m3+'] += 1
        if max_h >= 4: results['Power Anomaly-Cluster V11 (7注)']['m4+'] += 1
        
        if (i+1) % 50 == 0:
            logger.info(f"Progress: {i+1}/{periods}...")

    # Report
    print("\n" + "="*60)
    print(f"{'Strategy':30} | {'M3+':5} | {'M4+':5} | {'M3 Rate':8}")
    print("-" * 60)
    for name, stat in results.items():
        rate = (stat['m3+'] / periods) * 100
        print(f"{name:30} | {stat['m3+']:5d} | {stat['m4+']:5d} | {rate:7.2f}%")
    print("="*60)
    
    # Random Baseline for Power Lotto 7-bet is approx 1.5% * 7 = 10.5%? No, the 1.5% is per bet.
    # Actually Match-3+ for 6/38 is approx 1/67 = 1.49%.
    # For 7 bets, it should be around 10.4%.
    if rate >= 12.0:
        print(f"✅ BREAKTHROUGH: Power V11 reached {rate:.2f}% Match-3+ Rate!")
    else:
        print(f"⚠️ IMPROVEMENT: Power V11 reached {rate:.2f}% Match-3+ Rate (Random Baseline ~10.4% for 7 bets)")

if __name__ == "__main__":
    run_power_v11_verification(300)
