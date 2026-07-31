import requests
import json
import sys

# Configuration
API_URL = "http://localhost:8002/api/predict-from-backend"
LOTTERY_TYPE = "BIG_LOTTO"

MODELS = [
    "backend_optimized",
    "ensemble",
    "xgboost",
    "lstm"
]

def get_prediction(model_name):
    print(f"🔮 Fetching prediction for {model_name}...")
    payload = {
        "lotteryType": LOTTERY_TYPE,
        "modelType": model_name
    }
    
    try:
        response = requests.post(API_URL, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def main():
    print(f"🎲 Generating Dual Bet Predictions for {LOTTERY_TYPE}")
    print("=" * 60)
    
    results = {}
    for model in MODELS:
        res = get_prediction(model)
        if res:
            results[model] = res

    # Strategy for Dual Bets
    # Bet 1: Ensemble (Most Robust)
    # Bet 2: XGBoost (Best Backtest Performance)
    
    bet1 = results.get("ensemble")
    bet2 = results.get("xgboost")
    
    print("\n🏆 Recommended Dual Bets:")
    print("-" * 60)
    
    if bet1:
        nums = bet1.get("numbers", [])
        spec = bet1.get("special", "N/A")
        print(f"🎫 Bet 1 (Ensemble - Robust):")
        print(f"   Numbers: {nums}")
        print(f"   Special: {spec}")
    else:
        print("🎫 Bet 1: (Unavailable)")

    print("-" * 30)

    if bet2:
        nums = bet2.get("numbers", [])
        spec = bet2.get("special", "N/A")
        print(f"🎫 Bet 2 (XGBoost - High Potential):")
        print(f"   Numbers: {nums}")
        print(f"   Special: {spec}")
    else:
        print("🎫 Bet 2: (Unavailable)")
        
    print("=" * 60)
    print("\n📊 Other Model Predictions (Reference):")
    for model, res in results.items():
        if model not in ["ensemble", "xgboost"]:
            print(f"- {model}: {res.get('numbers')} (Special: {res.get('special')})")

if __name__ == "__main__":
    main()
