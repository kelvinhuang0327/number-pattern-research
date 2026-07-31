import sys
import os
import io
import json
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from common import get_lottery_rules
from database import DatabaseManager
from models.unified_predictor import UnifiedPredictionEngine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def generate_smart_2bet_prediction():
    print("=" * 60)
    print("🎰 Big Lotto Smart 2-Bet Strategy (Standardized)")
    print("=" * 60)
    
    # 1. Setup
    lottery_type = "BIG_LOTTO"
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type) # New -> Old
    
    if not all_draws:
        print("❌ No data found.")
        return

    latest_draw = all_draws[0]
    next_draw_id = int(latest_draw['draw']) + 1
    print(f"📅 Latest Draw: {latest_draw['draw']} ({latest_draw['date']})")
    print(f"🎯 Target Draw: {next_draw_id}")
    
    engine = UnifiedPredictionEngine()
    rules = get_lottery_rules(lottery_type)
    
    # History for prediction (all available)
    history = all_draws
    
    # 2. Bet 1: Conservative (True Frequency)
    # Rationale: Capture the most statistically probable numbers (Hot).
    print("\n[Bet 1] Generating Conservative Bet (True Frequency)...")
    
    # Use Frequency Window 50 (compatible with Power Lotto success)
    freq_rules = rules.copy()
    freq_rules['frequency_window'] = 50
    freq_rules['pickCount'] = 6
    
    pred_conservative = engine.true_frequency_predict(history, freq_rules)
    bet1 = sorted(pred_conservative['numbers'])
    
    print(f"   Numbers: {bet1}")
    print(f"   Confidence: {pred_conservative.get('confidence', 0)*100:.1f}%")
    
    # 3. Bet 2: Aggressive (Deviation)
    # Rationale: Capture numbers deviating from the mean (Rebound/Cold-Active).
    print("\n[Bet 2] Generating Aggressive Bet (Deviation)...")
    
    dev_rules = rules.copy()
    dev_rules['pickCount'] = 6
    
    # Deviation usually works on full history or long window
    pred_aggressive = engine.deviation_predict(history, dev_rules)
    bet2 = sorted(pred_aggressive['numbers'])
    
    print(f"   Numbers: {bet2}")
    print(f"   Confidence: {pred_aggressive.get('confidence', 0)*100:.1f}%")
    
    # 4. Save/Output
    prediction = {
        'lotteryType': lottery_type,
        'draw': str(next_draw_id),
        'predict_time': datetime.now().isoformat(),
        'strategy': 'Smart 2-Bet (Standardized)',
        'bets': [
            {'type': 'Conservative (True Frequency)', 'numbers': bet1},
            {'type': 'Aggressive (Deviation)', 'numbers': bet2}
        ]
    }
    
    # Save JSON?
    # outfile = f"prediction_biglotto_smart2bet_{next_draw_id}.json"
    # with open(outfile, 'w') as f:
    #     json.dump(prediction, f, indent=2)
    
    print("\n" + "-"*60)
    print("🎫 Final Recommendations:")
    print(f"1. [Conservative]: {bet1}")
    print(f"2. [Aggressive]  : {bet2}")
    print("-"*60)

if __name__ == "__main__":
    generate_smart_2bet_prediction()
