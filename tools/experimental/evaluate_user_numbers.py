import requests
import json
from collections import Counter

API_BASE = "http://localhost:8002"

USER_BETS = [
    [6, 23, 26, 40, 46, 49],
    [1, 5, 9, 23, 38, 44],
    [26, 30, 34, 35, 38, 49],
    [22, 26, 35, 36, 37, 49],
    [5, 12, 26, 34, 35, 49],
    [20, 26, 30, 33, 34, 38],
    [9, 35, 37, 41, 43, 47],
    [13, 28, 39, 43, 45, 48]
]

MODELS_TO_CHECK = ["maml", "prophet", "xgboost", "ensemble", "lstm"]

def get_history():
    try:
        response = requests.get(f"{API_BASE}/api/history?lottery_type=BIG_LOTTO")
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching history: {e}")
    return []

def get_model_predictions():
    predictions = {}
    print("正在獲取系統模型預測以進行比對...")
    for model in MODELS_TO_CHECK:
        print(f"  - 正在運行 {model}...")
        try:
            payload = {
                "lotteryType": "BIG_LOTTO",
                "modelType": model
            }
            response = requests.post(
                f"{API_BASE}/api/predict-from-backend-eval?recent_count=500",
                json=payload,
                timeout=60
            )
            if response.status_code == 200:
                result = response.json()
                predictions[model] = set(result.get("numbers", []))
        except Exception as e:
            print(f"    {model} 預測失敗: {e}")
    return predictions

def analyze_numbers(history):
    # Analyze last 50 draws for hot/cold
    recent_50 = history[:50] if len(history) >= 50 else history
    all_nums = []
    for draw in recent_50:
        all_nums.extend(draw['numbers'])
    
    counts = Counter(all_nums)
    hot_nums = {n for n, c in counts.most_common(10)}
    cold_nums = {n for n, c in counts.most_common()[:-11:-1]}
    
    return hot_nums, cold_nums, counts

def evaluate_bets():
    history = get_history()
    if not history:
        print("無法獲取歷史數據，無法進行分析。")
        return

    hot_nums, cold_nums, counts = analyze_numbers(history)
    model_preds = get_model_predictions()
    
    # Create a pool of all model predicted numbers
    all_model_nums = set()
    for nums in model_preds.values():
        all_model_nums.update(nums)
        
    print("\n" + "="*80)
    print("📊 用戶號碼系統評估報告")
    print("="*80)
    print(f"🔥 近50期熱門號碼: {sorted(list(hot_nums))}")
    print(f"❄️ 近50期冷門號碼: {sorted(list(cold_nums))}")
    print(f"🤖 系統模型推薦號碼池: {sorted(list(all_model_nums))}")
    print("-" * 80)
    
    print(f"{'注數':<4} {'號碼組合':<30} {'熱門':<5} {'冷門':<5} {'模型支持':<10} {'系統信心'}")
    print("-" * 80)
    
    for i, bet in enumerate(USER_BETS, 1):
        bet_set = set(bet)
        
        # Analysis
        hot_hits = len(bet_set.intersection(hot_nums))
        cold_hits = len(bet_set.intersection(cold_nums))
        model_hits = len(bet_set.intersection(all_model_nums))
        
        # Check specific model support
        supporting_models = []
        for model, preds in model_preds.items():
            overlap = len(bet_set.intersection(preds))
            if overlap >= 3: # If a model predicts 3 or more numbers from this bet
                supporting_models.append(f"{model}({overlap})")
        
        # Calculate simple confidence score
        # Base score: 50
        # +5 for each hot number
        # +2 for each cold number (sometimes cold numbers are due)
        # +10 for each number supported by ANY model
        # +20 for each model that strongly supports (>=3 numbers)
        
        score = 50 + (hot_hits * 5) + (cold_hits * 2) + (model_hits * 10) + (len(supporting_models) * 15)
        confidence = min(score, 99)
        
        bet_str = str(sorted(bet))
        support_str = ", ".join(supporting_models) if supporting_models else "無強烈支持"
        
        print(f"#{i:<3} {bet_str:<30} {hot_hits:<5} {cold_hits:<5} {model_hits:<10} {confidence}%")
        if supporting_models:
             print(f"     ↳ 模型支持: {support_str}")
        
        # Detailed breakdown for high confidence bets
        if confidence > 80:
             print(f"     ✨ 推薦原因: 包含 {hot_hits} 個熱門號, {model_hits} 個系統推薦號")

    print("="*80)

if __name__ == "__main__":
    evaluate_bets()
