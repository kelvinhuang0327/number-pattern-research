import requests
import json

API_BASE = "http://localhost:8002"

def test_model(model_name):
    print(f"Testing {model_name}...")
    payload = {
        "lotteryType": "BIG_LOTTO",
        "modelType": model_name
    }
    try:
        response = requests.post(
            f"{API_BASE}/api/predict-from-backend-eval?recent_count=500",
            json=payload,
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            print(f"Keys: {data.keys()}")
            if "probabilities" in data and data["probabilities"]:
                print(f"Probabilities length: {len(data['probabilities'])}")
            else:
                print("No probabilities returned.")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_model("backend_optimized")
    test_model("xgboost")
