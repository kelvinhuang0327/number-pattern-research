import requests
import json
import sys
import time

# Configuration
API_URL = "http://localhost:8002/api/predict-from-backend"
LOTTERY_TYPE = "BIG_LOTTO"
TARGET_NUMBERS = {15, 23, 24, 41, 47}
TARGET_SPECIAL = 2

# Models to test
MODELS = [
    "prophet",
    "xgboost",
    "lstm",
    "transformer",
    "autogluon",
    "bayesian_ensemble",
    "maml",
    "backend_optimized",
    "ensemble",
    "optimized_ensemble"
]

def test_model(model_name):
    print(f"Testing model: {model_name}...")
    payload = {
        "lotteryType": LOTTERY_TYPE,
        "modelType": model_name
    }
    
    try:
        start_time = time.time()
        response = requests.post(API_URL, json=payload)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            predicted_nums = set(result.get("numbers", []))
            predicted_special = result.get("special", None)
            
            # Calculate hits (Main numbers)
            hits = predicted_nums.intersection(TARGET_NUMBERS)
            hit_count = len(hits)
            
            # Check special number
            special_hit = False
            if predicted_special is not None:
                if predicted_special == TARGET_SPECIAL:
                    special_hit = True
            
            # Dual bet check (if available)
            bet1_hits = 0
            bet2_hits = 0
            if "bet1" in result and result["bet1"]:
                b1_nums = set(result["bet1"].get("numbers", []))
                bet1_hits = len(b1_nums.intersection(TARGET_NUMBERS))
                
            if "bet2" in result and result["bet2"]:
                b2_nums = set(result["bet2"].get("numbers", []))
                bet2_hits = len(b2_nums.intersection(TARGET_NUMBERS))
            
            return {
                "model": model_name,
                "predicted": sorted(list(predicted_nums)),
                "special": predicted_special,
                "hits": hit_count,
                "hit_numbers": sorted(list(hits)),
                "special_hit": special_hit,
                "duration": f"{duration:.2f}s",
                "bet1_hits": bet1_hits,
                "bet2_hits": bet2_hits
            }
        else:
            print(f"Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def main():
    print(f"🎯 Target Numbers: {sorted(list(TARGET_NUMBERS))} + Special: {TARGET_SPECIAL}")
    print("-" * 60)
    
    results = []
    for model in MODELS:
        res = test_model(model)
        if res:
            results.append(res)
    
    # Sort by hits (descending)
    results.sort(key=lambda x: (x["hits"], x["special_hit"]), reverse=True)
    
    print("\n" + "=" * 80)
    print(f"{'Model':<25} | {'Hits':<5} | {'Special':<7} | {'Duration':<8} | {'Predicted Numbers'}")
    print("-" * 80)
    
    for r in results:
        special_mark = "✅" if r["special_hit"] else "❌"
        print(f"{r['model']:<25} | {r['hits']:<5} | {special_mark:<7} | {r['duration']:<8} | {r['predicted']}")
        
        if r['bet1_hits'] > 0 or r['bet2_hits'] > 0:
             print(f"  ↳ Dual Bet Hits: Bet1={r['bet1_hits']}, Bet2={r['bet2_hits']}")

    print("=" * 80)

if __name__ == "__main__":
    main()
