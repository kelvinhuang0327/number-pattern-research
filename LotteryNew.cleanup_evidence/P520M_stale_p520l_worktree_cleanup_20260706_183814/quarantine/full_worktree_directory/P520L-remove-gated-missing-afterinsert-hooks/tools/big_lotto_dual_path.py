import sys
import os
import io
import pandas as pd
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from models.unified_predictor import UnifiedPredictionEngine

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def simple_true_frequency(history, top_n, window=50):
    if not history: return []
    subset = history[:window]
    counts = {}
    for draw in subset:
        for n in draw['numbers']:
            counts[n] = counts.get(n, 0) + 1
    sorted_nums = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [x[0] for x in sorted_nums[:top_n]]

def analyze_dual_path_big():
    print("=" * 60)
    print("🔬 Big Lotto Dual-Path Optimization (Pool 49)")
    print("=" * 60)

    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    engine = UnifiedPredictionEngine()
    
    # Grid Search Parameters
    # Big Lotto has 49 numbers.
    # To get ~half pool coverage like Power Lotto (18/38=47%), we need ~23 numbers.
    # Try combinations summing to ~20-25.
    
    scenarios = [
        (12, 6),  # Conservative (18 nums, 36%)
        (15, 6),  # Balanced (21 nums, 42%)
        (15, 8),  # Aggressive (23 nums, 46%)
        (18, 6),  # Heavy Alpha (24 nums, 48%)
        (12, 12)  # Even Split (24 nums, 48%)
    ]
    
    print(f"Testing {len(scenarios)} scenarios on last 150 draws...")
    
    test_draws = all_draws[:150] # New -> Old
    
    results = []
    
    for alpha_n, beta_n in scenarios:
        hits_captured = 0
        total_drawn = 0
        perfect_6 = 0
        perfect_5 = 0
        
        for i in range(len(test_draws)):
            current_draw = test_draws[i]
            target_numbers = set(current_draw['numbers'])
            
            # History excluding current
            history = all_draws[i+1:]
            if len(history) < 100: break
            
            # Alpha: True Frequency
            # Use simple logic helper or engine
            alpha_set = set(simple_true_frequency(history, alpha_n, window=50))
            
            # Beta: Deviation (Deviation from Trend/Mean)
            # Engine deviation_predict returns top 6 by default
            beta_rules = {'pickCount': beta_n}
            # Engine expects Old->New history usually, but check implementation
            # UnifiedPredictionEngine usually handles sort, but best to pass Old to New for consistency if unsure
            # Actually engine handles it.
            
            beta_pred = engine.deviation_predict(history, beta_rules)
            beta_set = set(beta_pred['numbers'])
            
            # Combined
            combined_pool = alpha_set.union(beta_set)
            
            # Check coverage
            match = len(target_numbers.intersection(combined_pool))
            hits_captured += match
            total_drawn += 6
            
            if match == 6: perfect_6 += 1
            if match >= 5: perfect_5 += 1
            
        avg_capture = hits_captured / (len(test_draws))
        capture_rate = hits_captured / total_drawn * 100
        pool_size = alpha_n + beta_n # Approx (might overlap)
        
        res = {
            'Alpha': alpha_n,
            'Beta': beta_n,
            'PoolSize': pool_size,
            'AvgCapture': avg_capture,
            'CaptureRate': f"{capture_rate:.1f}%",
            'Match5+': perfect_5,
            'Match6': perfect_6
        }
        results.append(res)
        print(f"Scenario A{alpha_n}/B{beta_n}: Cap {capture_rate:.1f}%, M6: {perfect_6}, M5+: {perfect_5}")

    print("\n" + "="*60)
    print("🏆 Optimization Results")
    print("="*60)
    df = pd.DataFrame(results)
    print(df.to_string(index=False))
    
    # Recommendation
    best = max(results, key=lambda x: x['Match5+'])
    print(f"\n✅ Recommended: Alpha {best['Alpha']} / Beta {best['Beta']}")

if __name__ == "__main__":
    analyze_dual_path_big()
