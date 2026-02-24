from lottery_api.models.unified_predictor import prediction_engine
from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer
import json

def test_stability_id():
    # Mock data
    history = [{"draw": i, "numbers": [1,2,3,4,5,6], "date": f"202{i}-01-01"} for i in range(100)]
    rules = {"name": "POWER_LOTTO", "minNumber": 1, "maxNumber": 38, "pickCount": 6}
    
    print("--- Testing VAE Stability ID (POWER_LOTTO) ---")
    res_vae = prediction_engine.vae_predict(history, rules)
    print(f"VAE Status: {res_vae['stability_metrics']['status']}")
    print(f"VAE Description: {res_vae['stability_metrics']['description']}")
    
    print("\n--- Testing Orthogonal_3Bet Stability ID (POWER_LOTTO) ---")
    optimizer = MultiBetOptimizer()
    res_ortho = optimizer.generate_orthogonal_strategy_3bets(history, rules, {})
    print(f"Ortho Status: {res_ortho['stability_metrics']['status']}")
    print(f"Ortho Description: {res_ortho['stability_metrics']['description']}")

    print("\n--- Testing BIG_LOTTO Stability ID ---")
    rules_big = {"name": "BIG_LOTTO", "minNumber": 1, "maxNumber": 49, "pickCount": 6}
    res_big = prediction_engine.vae_predict(history, rules_big)
    print(f"BigLotto VAE Status: {res_big['stability_metrics']['status']}")
    print(f"BigLotto VAE Description: {res_big['stability_metrics']['description']}")

if __name__ == "__main__":
    test_stability_id()
