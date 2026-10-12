
import os
import sys
import numpy as np
from typing import List, Dict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.models.regime_detector import RegimeDetector

def check_power_regime():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    history = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    detector = RegimeDetector()
    regime_info = detector.detect_regime(history)
    
    print("=" * 60)
    print("🔍 POWER LOTTO REGIME ANALYSIS (Next Draw: 115000013)")
    print("=" * 60)
    print(f"Detected Regime: {regime_info['regime']}")
    print(f"Entropy: {regime_info['entropy']:.4f}")
    print(f"Hurst Exponent: {regime_info['hurst']:.4f}")
    print(f"Confidence: {regime_info['confidence']:.2f}")
    print("-" * 60)
    
    # Analyze specific characteristics for Power Lotto
    recent = history[-5:]
    hot_nums = []
    for d in recent: hot_nums.extend(d['numbers'])
    hot_counts = {k: v for k, v in dict(np.array(np.unique(hot_nums, return_counts=True)).T).items()}
    
    print(f"Recent Hot Numbers (5 draws): {[int(k) for k, v in hot_counts.items() if v >= 2]}")
    
    if regime_info['regime'] == 'ORDER':
        print("\n💡 ADVISORY: Momentum is strong. Bias towards Hot/Repeat numbers.")
    elif regime_info['regime'] == 'CHAOS':
        print("\n💡 ADVISORY: System is chaotic. Bias towards Oversold/Cold numbers (Mean Reversion).")
    else:
        print("\n💡 ADVISORY: Transitioning. Maintain balanced coverage with Orthogonal strategy.")
    print("=" * 60)

if __name__ == "__main__":
    check_power_regime()
