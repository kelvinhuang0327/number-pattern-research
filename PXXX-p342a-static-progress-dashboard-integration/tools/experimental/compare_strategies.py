import sys
import os
import asyncio
import json
from typing import List

# Setup path to import backend modules
sys.path.append(os.path.join(os.getcwd(), 'lottery_api'))

# Import directly from the modules in lottery_api
from predictors import (
    get_bayesian_ensemble_predictor, 
    get_prophet_predictor,
    get_xgboost_predictor,
    get_lstm_predictor
)
from models.unified_predictor import prediction_engine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from common import normalize_lottery_type, load_backend_history, get_lottery_rules

async def run_comparison(target_numbers: List[int], lottery_type_id: str = "DAILY_539"):
    print(f"🔄 Running comparison for {lottery_type_id} against target: {target_numbers}")
    
    # Load data
    lottery_type = normalize_lottery_type(lottery_type_id)
    history, rules = load_backend_history(lottery_type)
    
    if not history:
        print("❌ No history data found.")
        return

    print(f"📚 Loaded {len(history)} draws.")
    
    strategies = {
        "dual_bet_hybrid": "雙注混合策略",
        "optimized_ensemble": "優化集成預測",
        "hot_cold_split": "冷熱分離策略 (Simulated)", # Need to implement sim manually if logic is only in frontend
        "prophet": "Prophet",
        "lstm": "LSTM",
        "xgboost": "XGBoost",
        "bayesian_ensemble": "貝葉斯集成"
    }

    results = []

    for strategy_key, strategy_name in strategies.items():
        print(f"🚀 Testing {strategy_name} ({strategy_key})...")
        predicted_numbers = []
        
        try:
            if strategy_key == "optimized_ensemble":
                ensemble = OptimizedEnsemblePredictor(prediction_engine)
                res = ensemble.predict(history, rules)
                # Ensure we handle the structure correctly (bet1/bet2)
                predicted_numbers = res.get('bet1', {}).get('numbers', [])
                
            elif strategy_key == "dual_bet_hybrid":
                # Simulation of hybrid logic: simplistic here as real one is complex fn in App.js
                # We will use 'ensemble_combined' from backend if available, or just ensemble
                res = prediction_engine.ensemble_predict(history, rules)
                predicted_numbers = res.get('numbers', [])
                
            elif strategy_key in ["prophet", "xgboost", "lstm", "bayesian_ensemble"]:
                predictor = None
                if strategy_key == "prophet": predictor = get_prophet_predictor()
                elif strategy_key == "xgboost": predictor = get_xgboost_predictor()
                elif strategy_key == "lstm": predictor = get_lstm_predictor()
                elif strategy_key == "bayesian_ensemble": predictor = get_bayesian_ensemble_predictor()
                
                res = await predictor.predict(history, rules)
                predicted_numbers = res.get('numbers', [])
            
            else:
                # Fallback for strategies strictly in frontend (hot_cold_split)
                # Skipping or mocking
                print(f"⚠️ Strategy {strategy_key} logic is primarily frontend/complex. Skipping simulation.")
                continue

            # Compare
            hits = len(set(predicted_numbers) & set(target_numbers))
            results.append({
                "strategy": strategy_name,
                "predicted": predicted_numbers,
                "hits": hits,
                "match_rate": f"{(hits/len(target_numbers))*100:.1f}%"
            })
            
        except Exception as e:
            print(f"❌ Error in {strategy_name}: {e}")

    # Print Report
    print("\n" + "="*50)
    print(f"🎯 COMPARISON REPORT FOR {lottery_type_id}")
    print(f"Target: {target_numbers}")
    print("="*50)
    
    results.sort(key=lambda x: x['hits'], reverse=True)
    
    for r in results:
        print(f"[{r['hits']} Hits] {r['strategy']}")
        print(f"   Predicted: {r['predicted']}")
        print(f"   Match: {r['match_rate']}")
        print("-" * 30)

if __name__ == "__main__":
    # Target: 05, 23, 27, 28, 31
    target = [5, 23, 27, 28, 31]
    asyncio.run(run_comparison(target))
