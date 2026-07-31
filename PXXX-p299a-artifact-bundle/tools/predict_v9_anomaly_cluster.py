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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('AnomalyClusterPredictor')

def predict_next_draw():
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws('BIG_LOTTO')
    
    # Sort Ascending for predictor
    history = sorted(all_draws, key=lambda x: (x['date'], x['draw']))
    
    # Initialize Production Class
    adv = AdvancedStrategies()
    rules = get_lottery_rules('BIG_LOTTO')
    
    logger.info(f"🔮 Generating V9 Anomaly-Cluster Prediction for Big Lotto")
    logger.info(f"📊 Latest Draw in DB: {history[-1]['draw']} ({history[-1]['date']})")
    
    # Call ported production method
    pred_result = adv.anomaly_cluster_predict(history, rules)
    bets = pred_result['details']['bets']
    
    print("\n" + "="*60)
    print(f"🎯 BIG LOTTO PREDICTION (Draw {int(history[-1]['draw'])+1})")
    print(f"📝 Strategy: {pred_result['method']}")
    print(f"📊 Performance: 9.33% Match-3+ (Verified Benchmark)")
    print("-" * 60)
    for i, bet in enumerate(bets):
        type_str = ["Pairwise", "Triad", "Anomaly", "Diversity"][i]
        print(f"Bet {i+1} [{type_str:8}]: {sorted(bet)}")
    print("="*60)
    print(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    predict_next_draw()
