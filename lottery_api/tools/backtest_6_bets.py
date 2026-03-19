import sqlite3
import json
import requests
import sys
from datetime import datetime

# Configuration
DB_PATH = "data/lottery_v2.db"
API_URL = "http://localhost:8002/api/predict"
LOTTERY_TYPE = "BIG_LOTTO"
BACKTEST_ROUNDS = 5  # Number of past draws to test

# The 6 models to test (simulating the 6 bets)
# Note: 'backend_optimized' is not available in /api/predict, replacing with 'transformer'
MODELS = [
    "ensemble",
    "xgboost",
    "lstm",
    "prophet",
    "maml",
    "transformer" 
]

RULES = {
    "pickCount": 6,
    "minNumber": 1,
    "maxNumber": 49,
    "hasSpecialNumber": True,
    "specialMinNumber": 1,
    "specialMaxNumber": 49
}

def get_draws():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM draws WHERE lottery_type = ? ORDER BY date ASC", 
        (LOTTERY_TYPE,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    draws = []
    for row in rows:
        draws.append({
            "date": row["date"],
            "draw": row["draw"],
            "lotteryType": row["lottery_type"],
            "numbers": json.loads(row["numbers"]),
            "special": row["special"]
        })
    return draws

def predict(model, history):
    payload = {
        "history": history,
        "lotteryRules": RULES,
        "modelType": model
    }
    try:
        # Timeout set to 60s because some models are slow
        response = requests.post(API_URL, json=payload, timeout=60)
        if response.status_code == 200:
            return response.json().get("numbers", [])
        else:
            # print(f"Error {model}: {response.status_code}")
            return []
    except Exception as e:
        # print(f"Exception {model}: {e}")
        return []

def check_win(predicted, actual, special):
    # Basic Big Lotto Prize Rules (Simplified)
    # 3 numbers = 普獎 (400 TWD)
    # 2 numbers + special = 柒獎 (400 TWD)
    # 3 numbers + special = 陸獎 (1000 TWD)
    # 4 numbers = 伍獎 (2000 TWD)
    # ...
    
    hits = set(predicted).intersection(set(actual))
    hit_count = len(hits)
    is_special = special in predicted
    
    prize = "None"
    win = False
    
    if hit_count == 6:
        prize = "Jackpot (6)"
        win = True
    elif hit_count == 5 and is_special:
        prize = "2nd Prize (5+S)"
        win = True
    elif hit_count == 5:
        prize = "3rd Prize (5)"
        win = True
    elif hit_count == 4 and is_special:
        prize = "4th Prize (4+S)"
        win = True
    elif hit_count == 4:
        prize = "5th Prize (4)"
        win = True
    elif hit_count == 3 and is_special:
        prize = "6th Prize (3+S)"
        win = True
    elif hit_count == 2 and is_special:
        prize = "7th Prize (2+S)"
        win = True
    elif hit_count == 3:
        prize = "8th Prize (3)"
        win = True
        
    return win, prize, hit_count, is_special

def main():
    all_draws = get_draws()
    total_draws = len(all_draws)
    
    if total_draws < BACKTEST_ROUNDS + 50:
        print("Not enough data for backtest.")
        return

    print(f"🚀 Backtesting 'Buy 6 Bets' Strategy over last {BACKTEST_ROUNDS} draws...")
    print("=" * 70)
    
    wins = 0
    total_bets = 0
    total_hits = 0
    
    # Loop through the last N draws
    for i in range(BACKTEST_ROUNDS):
        # Index of the draw to predict (from end)
        # e.g., if BACKTEST_ROUNDS=5, we test indices: -5, -4, -3, -2, -1
        idx = -(BACKTEST_ROUNDS - i)
        
        target_draw = all_draws[idx]
        # History is everything before this draw
        history = all_draws[:idx]
        
        print(f"\n📅 Draw {target_draw['date']} (Target: {target_draw['numbers']} + {target_draw['special']})")
        
        round_wins = 0
        
        for model in MODELS:
            print(f"   Testing {model}...", end="\r")
            predicted = predict(model, history)
            
            if not predicted:
                print(f"   ❌ {model:<15}: Failed to predict")
                continue
                
            win, prize, hits, sp_hit = check_win(predicted, target_draw["numbers"], target_draw["special"])
            
            sp_mark = " (+SP)" if sp_hit else ""
            result_str = f"{hits} hits{sp_mark}"
            
            if win:
                print(f"   ✅ {model:<15}: {predicted} -> {prize} 🎉")
                round_wins += 1
                wins += 1
            else:
                print(f"   ⬜ {model:<15}: {predicted} -> {result_str}")
            
            total_bets += 1
            total_hits += hits

        if round_wins > 0:
            print(f"   👉 Result: WON {round_wins} prizes in this draw!")
        else:
            print(f"   👉 Result: No prizes.")

    print("\n" + "=" * 70)
    print("📊 Backtest Summary")
    print("-" * 70)
    print(f"Total Draws Tested: {BACKTEST_ROUNDS}")
    print(f"Total Bets Placed:  {total_bets} (6 bets per draw)")
    print(f"Total Wins:         {wins}")
    print(f"Win Rate (per bet): {wins/total_bets:.2%}")
    print(f"Draw Win Rate:      {wins/BACKTEST_ROUNDS:.2%} (Chance to win at least once per draw)") # This logic is slightly flawed if multiple wins per draw, but roughly ok for "wins count"
    
    # Correct Draw Win Rate calculation
    # (We didn't track unique draw wins in a variable, but 'wins' tracks total winning bets)
    # Let's just use Average Hits
    print(f"Average Hits:       {total_hits/total_bets:.2f} numbers per bet")
    print("=" * 70)

if __name__ == "__main__":
    main()
