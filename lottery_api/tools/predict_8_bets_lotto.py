import requests
import json

# Configuration
API_URL = "http://localhost:8002/api/predict-from-backend-eval"
LOTTERY_TYPE = "BIG_LOTTO"
RECENT_COUNT = 200  # Use consistent window for all models

# 8 Models for diversified predictions
MODELS = [
    "ensemble",
    "xgboost",
    "lstm",
    "prophet",
    "autogluon",
    "backend_optimized",
    "maml",
    "transformer"
]

def get_prediction(model_name):
    """Fetch prediction from evaluation endpoint"""
    print(f"🔮 Fetching {model_name}...", end="\r")
    payload = {
        "lotteryType": LOTTERY_TYPE,
        "modelType": model_name
    }
    
    try:
        # Use eval endpoint with fixed window
        response = requests.post(
            f"{API_URL}?recent_count={RECENT_COUNT}", 
            json=payload, 
            timeout=60
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ {model_name:<20} failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ {model_name:<20} error: {str(e)[:40]}")
        return None

def validate_prediction(numbers, lottery_type):
    """Validate BIG_LOTTO rules (6 main numbers only, no special)"""
    if len(numbers) != 6:
        return False, f"Invalid count: {len(numbers)}"
    
    for n in numbers:
        if n < 1 or n > 49:
            return False, f"Number {n} out of range"
    
    if len(numbers) != len(set(numbers)):
        return False, "Duplicate numbers"
    
    return True, "Valid"

def main():
    print(f"🎲 Generating 8 Consistent Bets for 大樂透 (BIG_LOTTO)")
    print(f"📊 Data Window: Recent {RECENT_COUNT} draws (fixed for all models)")
    print(f"🔧 Mode: Evaluation (static config, no cache)")
    print("=" * 85)
    
    predictions = []
    
    # Fetch all predictions
    for model in MODELS:
        result = get_prediction(model)
        if result:
            numbers = result.get("numbers", [])
            valid, msg = validate_prediction(numbers, LOTTERY_TYPE)
            
            predictions.append({
                "model": model,
                "method": result.get("method", model),
                "numbers": numbers,
                "confidence": result.get("confidence", 0),
                "valid": valid,
                "validation_msg": msg
            })
            
            status = "✅" if valid else "⚠️"
            print(f"{status} {model:<20} | Conf: {result.get('confidence', 0):.2%} | {msg}")
    
    # Filter valid predictions
    valid_predictions = [p for p in predictions if p["valid"]]
    
    if len(valid_predictions) < 8:
        print(f"\n⚠️ Only {len(valid_predictions)} valid predictions available")
    
    # Sort by confidence
    valid_predictions.sort(key=lambda x: x["confidence"], reverse=True)
    
    # Select Top 8 Unique Bets
    unique_bets = []
    seen_sets = set()
    
    for p in valid_predictions:
        num_tuple = tuple(sorted(p["numbers"]))
        if num_tuple not in seen_sets:
            seen_sets.add(num_tuple)
            unique_bets.append(p)
        
        if len(unique_bets) >= 8:
            break
    
    # Display Results
    print("\n" + "=" * 70)
    print("🏆 8 Recommended Bets for 大樂透 (6 Main Numbers Only)")
    print("=" * 70)
    print(f"{'#':<3} | {'Model':<20} | {'Confidence':<10} | {'Numbers'}")
    print("-" * 70)
    
    for i, bet in enumerate(unique_bets, 1):
        nums_str = ", ".join(f"{n:02d}" for n in bet['numbers'])
        print(f"{i:<3} | {bet['model']:<20} | {bet['confidence']:.2%}    | {nums_str}")
    
    print("=" * 70)
    
    # Hot Numbers Analysis
    all_nums = [n for bet in unique_bets for n in bet['numbers']]
    
    from collections import Counter
    hot_nums = Counter(all_nums).most_common(10)
    
    print("\n🔥 Hot Main Numbers (Most Frequent):")
    print("   " + ", ".join([f"{num:02d} (x{count})" for num, count in hot_nums]))
    
    # Validation Summary
    print("\n✅ Validation Summary:")
    print(f"   - All bets use same data window: {RECENT_COUNT} draws")
    print("   - All bets follow 大樂透 rules (6 main numbers only, 1-49)")
    print("   - backend_optimized uses fixed config (no adaptation)")
    print("   - No cache used (fresh predictions every time)")
    print("   - ⚠️ Special number will be drawn separately during lottery")
    print("=" * 70)

if __name__ == "__main__":
    main()
