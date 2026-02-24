"""
大樂透正確回測邏輯

大樂透開獎方式：
- 從49個號碼中開出6個一般號碼（主號碼）
- 再從剩餘43個號碼中開出1個特別號

玩家購買：
- 只選擇6個主號碼（不選特別號）

中獎規則：
- 頭獎（特獎）：6個號碼全中
- 二獎：5個號碼 + 特別號
- 三獎：5個號碼
- 四獎：4個號碼 + 特別號
- 五獎：4個號碼
- 六獎：3個號碼 + 特別號
- 七獎：3個號碼
- 八獎：2個號碼 + 特別號
- 普獎：特別號（只中特別號）
"""
import requests
import json
import sys

# Configuration
API_URL = "http://localhost:8002/api/predict-from-backend-eval"
LOTTERY_TYPE = "BIG_LOTTO"

# Models to test
MODELS = [
    "prophet",
    "xgboost",
    "lstm",
    "transformer",
    "autogluon",
    "backend_optimized",
    "maml",
    "ensemble"
]

def get_prediction(model_name, recent_count=200):
    """Get prediction for specific model"""
    print(f"🔮 Testing {model_name}...", end="\r")
    payload = {
        "lotteryType": LOTTERY_TYPE,
        "modelType": model_name
    }
    
    try:
        response = requests.post(
            f"{API_URL}?recent_count={recent_count}", 
            json=payload, 
            timeout=60
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ {model_name} failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ {model_name} error: {str(e)[:40]}")
        return None

def calculate_prize(predicted_main, drawn_main, drawn_special):
    """
    計算中獎等級
    
    Args:
        predicted_main: 預測的6個主號碼 (list)
        drawn_main: 開獎的6個主號碼 (list)
        drawn_special: 開獎的特別號 (int)
    
    Returns:
        prize_name: 中獎等級名稱
        prize_level: 中獎等級編號（1-9，數字越小越大獎）
        main_hits: 主號碼中了幾個
        special_hit: 是否中特別號
    """
    predicted_set = set(predicted_main)
    drawn_set = set(drawn_main)
    
    # 主號碼命中數
    main_hits = len(predicted_set.intersection(drawn_set))
    
    # 特別號是否命中（特別號必須在預測的6個號碼中）
    special_hit = drawn_special in predicted_set
    
    # 判定中獎等級
    if main_hits == 6:
        return "頭獎（特獎）", 1, main_hits, special_hit
    elif main_hits == 5 and special_hit:
        return "二獎", 2, main_hits, special_hit
    elif main_hits == 5:
        return "三獎", 3, main_hits, special_hit
    elif main_hits == 4 and special_hit:
        return "四獎", 4, main_hits, special_hit
    elif main_hits == 4:
        return "五獎", 5, main_hits, special_hit
    elif main_hits == 3 and special_hit:
        return "六獎", 6, main_hits, special_hit
    elif main_hits == 3:
        return "七獎", 7, main_hits, special_hit
    elif main_hits == 2 and special_hit:
        return "八獎", 8, main_hits, special_hit
    elif main_hits == 0 and special_hit:
        return "普獎", 9, main_hits, special_hit
    else:
        return "未中獎", 0, main_hits, special_hit

def backtest_predictions(historical_draws, max_tests=10):
    """
    使用歷史開獎數據回測預測
    
    Args:
        historical_draws: 歷史開獎數據列表 [{"draw": 期號, "numbers": [...], "special": ...}, ...]
        max_tests: 最多測試幾期
    """
    print(f"\n📊 開始回測：使用最近 {max_tests} 期歷史數據")
    print("=" * 90)
    
    all_results = []
    
    # 對每個模型進行測試
    for model in MODELS:
        result = get_prediction(model)
        if not result:
            continue
        
        predicted_main = result.get("numbers", [])
        
        # 對每期歷史數據測試
        model_results = []
        for i, draw in enumerate(historical_draws[-max_tests:]):
            drawn_main = draw.get("numbers", [])
            drawn_special = draw.get("special")
            
            prize_name, prize_level, main_hits, special_hit = calculate_prize(
                predicted_main, drawn_main, drawn_special
            )
            
            model_results.append({
                "draw": draw.get("draw"),
                "prize_name": prize_name,
                "prize_level": prize_level,
                "main_hits": main_hits,
                "special_hit": special_hit
            })
        
        # 統計結果
        best_prize = min([r["prize_level"] for r in model_results if r["prize_level"] > 0], default=0)
        total_prizes = len([r for r in model_results if r["prize_level"] > 0])
        avg_hits = sum([r["main_hits"] for r in model_results]) / len(model_results)
        
        all_results.append({
            "model": model,
            "predicted": predicted_main,
            "best_prize": best_prize,
            "total_prizes": total_prizes,
            "avg_hits": avg_hits,
            "details": model_results
        })
        
        print(f"✅ {model:<20} | 預測: {predicted_main} | 最佳獎項: {best_prize if best_prize > 0 else '未中'} | 中獎次數: {total_prizes}/{max_tests} | 平均命中: {avg_hits:.1f}")
    
    # 排序並顯示詳細結果
    all_results.sort(key=lambda x: (x["best_prize"] if x["best_prize"] > 0 else 999, -x["total_prizes"], -x["avg_hits"]))
    
    print("\n" + "=" * 90)
    print("🏆 回測結果詳情（按最佳獎項排序）")
    print("=" * 90)
    
    for res in all_results:
        print(f"\n📌 {res['model'].upper()}")
        print(f"   預測號碼: {', '.join([f'{n:02d}' for n in res['predicted']])}")
        print(f"   最佳獎項: {res['best_prize'] if res['best_prize'] > 0 else '未中獎'} | 總中獎: {res['total_prizes']}/{max_tests} | 平均命中: {res['avg_hits']:.1f}")
        
        # 顯示前3筆中獎記錄
        prizes = [d for d in res['details'] if d['prize_level'] > 0]
        if prizes:
            print(f"   中獎記錄:")
            for p in prizes[:3]:
                special_mark = "✅" if p["special_hit"] else ""
                print(f"      • 第{p['draw']}期: {p['prize_name']} (主號碼{p['main_hits']}個 {special_mark})")

def main():
    print("🎲 大樂透回測系統")
    print("⚠️ 正確邏輯：玩家只選6個主號碼，特別號是開獎時從剩餘43個號碼中抽取")
    print("⚠️ 中獎判定：用6個預測號碼去比對開獎的7個號碼（6主+1特別）")
    
    # 從資料庫載入歷史數據
    print("\n📥 載入歷史數據...")
    try:
        response = requests.get("http://localhost:8002/api/history?lottery_type=BIG_LOTTO")
        if response.status_code == 200:
            historical_draws = response.json()
            print(f"✅ 已載入 {len(historical_draws)} 期大樂透數據")
            
            # 執行回測
            backtest_predictions(historical_draws, max_tests=10)
        else:
            print(f"❌ 無法載入歷史數據: {response.status_code}")
    except Exception as e:
        print(f"❌ 錯誤: {e}")

if __name__ == "__main__":
    main()
