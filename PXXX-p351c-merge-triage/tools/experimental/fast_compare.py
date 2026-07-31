import sys
import os
import asyncio
import json

# Setup path to import backend modules
sys.path.append(os.path.join(os.getcwd(), 'lottery_api'))

from models.unified_predictor import prediction_engine
from common import normalize_lottery_type, load_backend_history, get_lottery_rules

async def run_fast_compare():
    target_numbers = [5, 23, 27, 28, 31]
    lottery_type_id = "DAILY_539"
    
    print(f"🔄 Running FAST comparison for {lottery_type_id}...")
    
    lottery_type = normalize_lottery_type(lottery_type_id)
    history, rules = load_backend_history(lottery_type)
    
    if not history:
        print("❌ No history data found.")
        return

    # Statistical strategies (should be fast)
    # Map strategy name to method name on prediction_engine
    strategies = {
        "frequency": "frequency_predict",
        "trend": "trend_predict",
        "statistical": "statistical_predict",
        "hot_cold": "hot_cold_predict",
        "bayesian": "bayesian_predict",
        "zone_balance": "zone_balance_predict"
    }

    results = []
    
    for name, method_name in strategies.items():
        try:
            print(f"Testing {name}...")
            
            # Get the method from the engine instance
            if not hasattr(prediction_engine, method_name):
                print(f"Method {method_name} not found on engine")
                continue
                
            method = getattr(prediction_engine, method_name)
            
            # Call the method
            res = method(history, rules)
            
            # If res is a coroutine (unlikely for stats but possible), await it
            if asyncio.iscoroutine(res):
                res = await res
                
            nums = res.get('numbers', [])
            hits = len(set(nums) & set(target_numbers))
            
            results.append({
                "strategy": name,
                "predicted": nums,
                "hits": hits,
                "match_rate": f"{(hits/5)*100:.0f}%"
            })
        except Exception as e:
            print(f"Error {name}: {e}")

    results.sort(key=lambda x: x['hits'], reverse=True)
    
    print("\n" + "="*40)
    print("🏆 FAST COMPARISON RESULTS")
    print("="*40)
    for r in results:
        print(f"[{r['hits']} Hits] {r['strategy'].ljust(15)} | Match: {r['match_rate']}")
        print(f"   Numbers: {r['predicted']}")

if __name__ == "__main__":
    try:
        asyncio.run(run_fast_compare())
    except Exception as e:
        print(f"Fatal error: {e}")
