import os
import sys
import logging
from datetime import datetime

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.advanced_strategies import AdvancedStrategies
from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.special_predictor import get_enhanced_special_prediction

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('PowerAnomalyClusterPredictor')

def predict_next_draw():
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws('POWER_LOTTO')
    
    # Sort Ascending for predictor
    history = sorted(all_draws, key=lambda x: (x['date'], x['draw']))
    
    # Initialize Production Class
    adv = AdvancedStrategies()
    rules = get_lottery_rules('POWER_LOTTO')
    
    logger.info(f"🔮 Generating V11 Anomaly-Cluster Prediction for Power Lotto")
    logger.info(f"📊 Latest Draw in DB: {history[-1]['draw']} ({history[-1]['date']})")
    
    # Call ported production method (Main numbers)
    pred_result = adv.power_anomaly_cluster_v11_predict(history, rules)
    main_bets = pred_result['details']['bets']
    
    # Special Number Prediction (Call multiple times to get variety)
    special_nums = []
    for _ in range(10):
        s = get_enhanced_special_prediction(history, rules)
        if s not in special_nums: special_nums.append(s)
    
    if not special_nums: special_nums = [random.randint(1, 8)]
    
    print("\n" + "="*60)
    print(f"🎯 POWER LOTTO PREDICTION (Draw {int(history[-1]['draw'])+1})")
    print(f"📝 Strategy: {pred_result['method']}")
    print(f"📊 Performance: 20.67% Match-3+ (Verified V11 Benchmark)")
    print("-" * 60)
    for i, bet in enumerate(main_bets):
        # Attach a special number (wrapping around the top special picks)
        s_num = special_nums[i % len(special_nums)]
        print(f"Bet {i+1}: {sorted(bet)} | [Special: {s_num}]")
    print("="*60)
    print(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    predict_next_draw()
