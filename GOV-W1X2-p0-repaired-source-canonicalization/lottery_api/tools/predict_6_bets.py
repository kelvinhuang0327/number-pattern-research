import requests
import json
import sys
from datetime import datetime

# Configuration
API_URL = "http://localhost:8002/api/predict-from-backend"
LOTTERY_TYPE = "BIG_LOTTO"

# List of models to query to get diverse predictions
MODELS = [
    "ensemble",           # 1. Super Ensemble (High Confidence)
    "backend_optimized",  # 2. Optimized Statistical (Baseline)
    "xgboost",            # 3. Gradient Boosting (Best Backtest)
    "lstm",               # 4. Deep Learning (RNN)
    "prophet",            # 5. Time Series (Facebook)
    "transformer",        # 6. Attention Mechanism
    "autogluon",          # 7. AutoML (Backup)
    "maml"                # 8. Meta Learning (Backup)
]

def get_prediction(model_name):
    print(f"🔮 Fetching prediction for {model_name}...", end="\r")
    payload = {
        "lotteryType": LOTTERY_TYPE,
        "modelType": model_name
    }
    
    try:
        response = requests.post(API_URL, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        return None

def main():
    print(f"🎲 Generating 6 High-Potential Bets for {LOTTERY_TYPE}")
    print("=" * 70)
    
    predictions = []
    
    # 1. Fetch all predictions
    for model in MODELS:
        result = get_prediction(model)
        if result:
            predictions.append({
                "model": model,
                "method": result.get("method", model),
                "numbers": result.get("numbers", []),
                "special": result.get("special", "N/A"),
                "confidence": result.get("confidence", 0)
            })
            print(f"✅ {model:<20} fetched. Confidence: {result.get('confidence', 0):.2%}")
        else:
            print(f"❌ {model:<20} failed.")

    # 2. Sort by confidence (descending)
    predictions.sort(key=lambda x: x["confidence"], reverse=True)
    
    # 3. Select Top 6 Unique Bets
    # Ensure we don't have duplicate number sets
    unique_bets = []
    seen_sets = set()
    
    for p in predictions:
        num_tuple = tuple(sorted(p["numbers"]))
        if num_tuple not in seen_sets:
            seen_sets.add(num_tuple)
            unique_bets.append(p)
        
        if len(unique_bets) >= 6:
            break
            
    # 4. Display Results
    print("\n🏆 Top 6 Recommended Bets (Ranked by Success Rate)")
    print("=" * 70)
    print(f"{'Rank':<5} | {'Model / Strategy':<25} | {'Confidence':<10} | {'Numbers':<25} | {'Special'}")
    print("-" * 70)
    
    for i, bet in enumerate(unique_bets, 1):
        nums_str = ", ".join(f"{n:02d}" for n in bet['numbers'])
        special_str = str(bet['special'])
        if special_str != "N/A" and special_str != "None" and bet['special'] is not None:
             try:
                special_str = f"{int(special_str):02d}"
             except:
                pass
        
        print(f"#{i:<4} | {bet['model']:<25} | {bet['confidence']:.2%}    | {nums_str} | {special_str}")
        
    print("=" * 70)
    
    # 5. Analysis
    all_nums = [n for bet in unique_bets for n in bet['numbers']]
    from collections import Counter
    common = Counter(all_nums).most_common(5)
    print("\n🔥 Hot Numbers in these 6 bets:")
    print(", ".join([f"{num:02d} (x{count})" for num, count in common]))

if __name__ == "__main__":
    main()
