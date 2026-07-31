#!/usr/bin/env python3
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.ensemble_stacking import EnsembleStackingPredictor

def verify():
    print("🚀 Starting ARIMA Integration Verification")
    
    # Create mock history (15 periods of linear trend)
    history = []
    for i in range(15):
        # A simple linear trend: [1+i, 2+i, 3+i, 4+i, 5+i, 6+i]
        history.append({
            'draw': 100 + i,
            'numbers': [1 + i, 5 + i, 10 + i, 15 + i, 20 + i, 25 + i],
            'special': 1 + (i % 8)
        })
        
    rules = {
        'name': 'POWER_LOTTO',
        'pickCount': 6,
        'minNumber': 1,
        'maxNumber': 38,
        'hasSpecialNumber': True,
        'specialMinNumber': 1,
        'specialMaxNumber': 8
    }
    
    predictor = EnsembleStackingPredictor()
    
    print("\n🔮 Running prediction with ARIMA enabled...")
    # By default, EnzymeStackingPredictor now has 'arima' in base_models
    result = predictor.predict_with_features(history, rules, use_lstm=False)
    
    print(f"\n✅ Prediction Result:")
    print(f"Numbers: {result['numbers']}")
    print(f"Special: {result['special']}")
    print(f"Confidence: {result['confidence']:.2%}")
    print(f"Model Votes: {result['model_votes']}")
    
    if 'arima' in result['model_votes']:
        print("\n✨ ARIMA successfully contributed to the prediction!")
    else:
        print("\n❌ ARIMA did NOT contribute to the prediction.")
        sys.exit(1)

if __name__ == "__main__":
    verify()
