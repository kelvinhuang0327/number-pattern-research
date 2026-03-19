import sys, os
import json

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from database import DatabaseManager

def test_sgp_integration():
    db = DatabaseManager('lottery_api/data/lottery_v2.db')
    draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    # We want to predict for the period AFTER the existing draws
    history = list(reversed(draws)) # predictors expect newest first
    
    engine = UnifiedPredictionEngine()
    
    rules = {
        'name': 'POWER_LOTTO',
        'minNumber': 1,
        'maxNumber': 38,
        'pickCount': 6,
        'hasSpecialNumber': True,
        'specialMinNumber': 1,
        'specialMaxNumber': 8
    }
    
    print("Testing SGP Strategy on Power Lotto...")
    result = engine.sgp_predict(history, rules)
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if result and 'numbers' in result and len(result['numbers']) == 6:
        print("\n✅ SGP Strategy integrated successfully!")
    else:
        print("\n❌ SGP Strategy integration failed.")

if __name__ == "__main__":
    test_sgp_integration()
