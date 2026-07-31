import requests
import json

# Configuration
API_URL = "http://localhost:8002/api/predict-from-backend"
LOTTERY_TYPE = "DAILY_539"

# 今彩539 Rules
RULES = {
    "pickCount": 5,
    "minNumber": 1,
    "maxNumber": 39,
    "hasSpecialNumber": False
}

# Models to query (diversified)
MODELS = [
    "ensemble",           # 1. Super Ensemble (Most Robust)
    "xgboost",            # 2. XGBoost (Best Backtest)
    "lstm",               # 3. LSTM (Deep Learning)
    "prophet",            # 4. Prophet (Time Series)
    "backend_optimized",  # 5. Optimized Statistical
    "autogluon",          # 6. AutoML
    "maml",               # 7. Meta Learning (Backup)
    "transformer"         # 8. Transformer (Backup)
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
            print(f"❌ {model_name:<20} failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ {model_name:<20} failed: {str(e)[:50]}")
        return None

def validate_prediction(numbers):
    """Validate if the prediction follows 今彩539 rules"""
    # Rule 1: Must have exactly 5 numbers
    if len(numbers) != 5:
        return False, f"Invalid count: {len(numbers)} (should be 5)"
    
    # Rule 2: All numbers must be in range [1, 39]
    for n in numbers:
        if n < 1 or n > 39:
            return False, f"Number {n} out of range [1-39]"
    
    # Rule 3: No duplicates
    if len(numbers) != len(set(numbers)):
        return False, "Contains duplicate numbers"
    
    # Rule 4: Numbers should be sorted
    if numbers != sorted(numbers):
        return False, "Numbers not sorted (correctable)"
    
    return True, "Valid"

def main():
    print(f"🎲 Generating 6 High-Potential Bets for 今彩539 (DAILY_539)")
    print(f"📋 Game Rules: Pick 5 numbers from 1-39 (No special number)")
    print("=" * 80)
    
    predictions = []
    
    # 1. Fetch all predictions
    for model in MODELS:
        result = get_prediction(model)
        if result:
            numbers = result.get("numbers", [])
            
            # Validate
            valid, msg = validate_prediction(numbers)
            
            predictions.append({
                "model": model,
                "method": result.get("method", model),
                "numbers": numbers,
                "confidence": result.get("confidence", 0),
                "valid": valid,
                "validation_msg": msg
            })
            
            status = "✅" if valid else "⚠️"
            print(f"{status} {model:<20} fetched. Confidence: {result.get('confidence', 0):.2%} | {msg}")
    
    # 2. Filter only valid predictions
    valid_predictions = [p for p in predictions if p["valid"]]
    
    if len(valid_predictions) < 6:
        print(f"\n⚠️ Warning: Only {len(valid_predictions)} valid predictions (need 6)")
        print("Using all available valid predictions...")
    
    # 3. Sort by confidence (descending)
    valid_predictions.sort(key=lambda x: x["confidence"], reverse=True)
    
    # 4. Select Top 6 Unique Bets
    unique_bets = []
    seen_sets = set()
    
    for p in valid_predictions:
        num_tuple = tuple(sorted(p["numbers"]))
        if num_tuple not in seen_sets:
            seen_sets.add(num_tuple)
            unique_bets.append(p)
        
        if len(unique_bets) >= 6:
            break
    
    # 5. Display Results
    print("\n🏆 Top 6 Recommended Bets for 今彩539 (Ranked by Success Rate)")
    print("=" * 80)
    print(f"{'Rank':<5} | {'Model / Strategy':<25} | {'Confidence':<10} | {'Numbers (5 picks)'}")
    print("-" * 80)
    
    for i, bet in enumerate(unique_bets, 1):
        nums_str = ", ".join(f"{n:02d}" for n in bet['numbers'])
        print(f"#{i:<4} | {bet['model']:<25} | {bet['confidence']:.2%}    | {nums_str}")
    
    print("=" * 80)
    
    # 6. Hot Numbers Analysis
    all_nums = [n for bet in unique_bets for n in bet['numbers']]
    from collections import Counter
    common = Counter(all_nums).most_common(8)
    
    print("\n🔥 Hot Numbers in these 6 bets:")
    print(", ".join([f"{num:02d} (x{count})" for num, count in common]))
    
    # 7. Final Validation Check
    print("\n✅ Final Validation:")
    print(f"- All bets follow 今彩539 rules (5 numbers from 1-39)")
    print(f"- No special number included (今彩539 has no special number)")
    print(f"- All numbers are unique within each bet")
    print("=" * 80)

if __name__ == "__main__":
    main()
