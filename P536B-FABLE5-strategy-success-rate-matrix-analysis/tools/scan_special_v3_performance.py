
import os
import sys
import numpy as np
from collections import Counter

# Set up project paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.models.special_predictor import PowerLottoSpecialPredictor

def scan_recent_performance(limit=50):
    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    rules = {'name': 'POWER_LOTTO', 'specialMinNumber': 1, 'specialMaxNumber': 8}
    predictor = PowerLottoSpecialPredictor(rules)
    
    test_draws = all_draws[-limit:]
    top1_hits = 0
    top3_hits = 0
    total = 0
    
    print(f"Scanning Special V3 (MAB) Recent Performance (Last {limit} Draws)...")
    print("-" * 60)
    
    for i in range(len(all_draws) - limit, len(all_draws)):
        history = all_draws[:i]
        target = all_draws[i]
        actual = target.get('special')
        
        if not actual: continue
        
        # Predict Top 3
        predictions = predictor.predict_top_n(history, n=3)
        
        if actual == predictions[0]:
            top1_hits += 1
        if actual in predictions:
            top3_hits += 1
        
        total += 1
        
    top1_rate = (top1_hits / total) * 100
    top3_rate = (top3_hits / total) * 100
    
    top1_baseline = 12.5
    top3_baseline = 37.5
    
    print(f"Total Tested: {total}")
    print(f"Top 1 Hits: {top1_hits} ({top1_rate:.2f}%) | Edge: {top1_rate - top1_baseline:+.2f}%")
    print(f"Top 3 Hits: {top3_hits} ({top3_rate:.2f}%) | Edge: {top3_rate - top3_baseline:+.2f}%")
    print("-" * 60)
    
    # Check last 5 specifically
    print("\nRecent 5 Tracking:")
    for i in range(len(all_draws)-5, len(all_draws)):
        h = all_draws[:i]
        t = all_draws[i]
        p = predictor.predict_top_n(h, n=3)
        actual = t.get('special')
        status = "✅ HIT (T1)" if actual == p[0] else ("✅ HIT (T3)" if actual in p else "❌ MISS")
        print(f"Draw {t['draw']}: Actual {actual} | Pred {p} | {status}")

if __name__ == "__main__":
    scan_recent_performance(50)
