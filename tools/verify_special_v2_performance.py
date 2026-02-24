import os
import sys
import logging
from collections import Counter

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.special_predictor import PowerLottoSpecialPredictor
from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.utils.backtest_safety import (
    validate_chronological_order, 
    get_safe_backtest_slice
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SpecialV2Verify')

def run_special_v2_verification(periods: int = 500):
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = validate_chronological_order(db.get_all_draws('POWER_LOTTO'))
    
    rules = get_lottery_rules('POWER_LOTTO')
    predictor = PowerLottoSpecialPredictor(rules)
    
    hits = 0
    test_data = all_draws[-periods:]
    logger.info(f"🚀 Starting Special Zone V2 Verification: {periods} periods")
    
    for i, target_draw in enumerate(test_data):
        target_idx = all_draws.index(target_draw)
        history = get_safe_backtest_slice(all_draws, target_idx)
        actual_special = target_draw.get('special')
        
        # Predict special number
        pred_special = predictor.predict(history)
        
        if pred_special == actual_special:
            hits += 1
        
        if (i+1) % 100 == 0:
            current_rate = (hits / (i+1)) * 100
            logger.info(f"Progress: {i+1}/{periods} | Current Hit Rate: {current_rate:.2f}%")

    # Report
    rate = (hits / periods) * 100
    print("\n" + "="*60)
    print(f"🎯 POWER LOTTO SPECIAL ZONE (SECTION 2) VERIFICATION")
    print(f"📊 Periods: {periods}")
    print(f"🎯 Hits: {hits}")
    print(f"📈 Hit Rate: {rate:.2f}%")
    print(f"🎲 Random Baseline: 12.50%")
    print("-" * 60)
    
    if rate >= 14.5:
        print(f"✅ SUCCESS: Special V2 achieved {rate:.2f}% hit rate (Clear statistical edge!)")
    elif rate > 13.0:
        print(f"📈 IMPROVEMENT: Special V2 achieved {rate:.2f}% hit rate.")
    else:
        print(f"⚠️ NEUTRAL: Special V2 hit rate at {rate:.2f}%")
    print("="*60)

if __name__ == "__main__":
    run_special_v2_verification(500)
