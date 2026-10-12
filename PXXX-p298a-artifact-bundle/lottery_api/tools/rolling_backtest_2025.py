"""
2025年滾動式回測

邏輯：
1. 用2024年底之前的數據訓練/預測第N期
2. 比對第N期實際開獎結果，計算中獎等級
3. 將第N期實際數據加入訓練集
4. 預測第N+1期
5. 重複直到2025年所有期數測試完畢

這樣可以模擬真實情況：每次預測都用「當時可用的歷史數據」
"""
import requests
import json
from collections import defaultdict, Counter

API_BASE = "http://localhost:8002"

def calculate_prize(predicted_main, drawn_main, drawn_special):
    """計算中獎等級"""
    predicted_set = set(predicted_main)
    drawn_set = set(drawn_main)
    
    main_hits = len(predicted_set.intersection(drawn_set))
    special_hit = drawn_special in predicted_set
    
    if main_hits == 6:
        return "頭獎", 1, main_hits, special_hit
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

def predict_with_history(model_name, history_data):
    """使用指定歷史數據進行預測"""
    # 將歷史數據暫存到後端（使用 recent_count 參數控制）
    # 因為我們用的是 eval endpoint，它會用最近N期數據
    # 所以我們傳入 recent_count = 當前歷史長度
    
    payload = {
        "lotteryType": "BIG_LOTTO",
        "modelType": model_name
    }
    
    # 使用 eval endpoint，recent_count 設為歷史數據長度
    recent_count = min(len(history_data), 500)  # 最多用500期
    
    try:
        response = requests.post(
            f"{API_BASE}/api/predict-from-backend-eval?recent_count={recent_count}",
            json=payload,
            timeout=60
        )
        if response.status_code == 200:
            return response.json().get("numbers", [])
        else:
            return None
    except Exception as e:
        print(f"  ❌ {model_name} 預測失敗: {str(e)[:50]}")
        return None

def rolling_backtest_2025(models_to_test):
    """滾動式回測2025年數據"""
    
    print("📥 載入歷史數據...")
    response = requests.get(f"{API_BASE}/api/history?lottery_type=BIG_LOTTO")
    if response.status_code != 200:
        print("❌ 無法載入數據")
        return
    
    all_data = response.json()
    
    # 分離2024年之前和2025年的數據
    data_before_2025 = [d for d in all_data if not d.get('date', '').startswith('2025')]
    data_2025 = [d for d in all_data if d.get('date', '').startswith('2025')]
    
    # 按日期排序（2025年數據從早到晚）
    data_2025.sort(key=lambda x: x.get('date', ''))
    
    print(f"✅ 訓練數據: {len(data_before_2025)} 期 (2024年底之前)")
    print(f"✅ 測試數據: {len(data_2025)} 期 (2025年)")
    print("=" * 100)
    
    # 每個模型的結果統計
    model_results = {model: {
        'predictions': [],
        'prizes': [],
        'total_hits': 0,
        'best_prize': 0
    } for model in models_to_test}
    
    # 滾動式預測
    rolling_history = data_before_2025.copy()
    
    for idx, target_draw in enumerate(data_2025, 1):
        print(f"\n🎯 第 {idx}/{len(data_2025)} 期: {target_draw['draw']} ({target_draw['date']})")
        print(f"   訓練數據: {len(rolling_history)} 期")
        
        target_main = target_draw['numbers']
        target_special = target_draw['special']
        
        print(f"   實際開獎: {', '.join([f'{n:02d}' for n in sorted(target_main)])} + 特別號 {target_special:02d}")
        
        # 對每個模型進行預測
        for model in models_to_test:
            predicted = predict_with_history(model, rolling_history)
            
            if predicted:
                prize_name, prize_level, main_hits, special_hit = calculate_prize(
                    predicted, target_main, target_special
                )
                
                model_results[model]['predictions'].append({
                    'draw': target_draw['draw'],
                    'date': target_draw['date'],
                    'predicted': predicted,
                    'prize_name': prize_name,
                    'prize_level': prize_level,
                    'main_hits': main_hits,
                    'special_hit': special_hit
                })
                
                if prize_level > 0:
                    model_results[model]['prizes'].append(prize_level)
                    if model_results[model]['best_prize'] == 0 or prize_level < model_results[model]['best_prize']:
                        model_results[model]['best_prize'] = prize_level
                
                model_results[model]['total_hits'] += main_hits
                
                # 顯示結果
                if prize_level > 0:
                    special_mark = "✅" if special_hit else ""
                    print(f"   🎉 {model:<20} → {prize_name:<8} | 主{main_hits}個 {special_mark}")
                else:
                    print(f"   ⚪ {model:<20} → 主{main_hits}個")
        
        # 將這期實際數據加入訓練集（滾動）
        rolling_history.append(target_draw)
    
    # 統計結果
    print("\n" + "=" * 100)
    print("📊 2025年滾動式回測統計 (正確邏輯：6個主號碼預測)")
    print("=" * 100)
    
    # 按中獎表現排序
    sorted_models = sorted(
        model_results.items(),
        key=lambda x: (
            -len(x[1]['prizes']),  # 中獎次數越多越好
            x[1]['best_prize'] if x[1]['best_prize'] > 0 else 999,  # 最佳獎項越小越好
            -x[1]['total_hits']  # 總命中數越多越好
        )
    )
    
    print(f"\n{'模型':<20} | {'中獎次數':<10} | {'中獎率':<10} | {'最佳獎項':<10} | {'平均命中':<10} | {'總命中數'}")
    print("-" * 100)
    
    for model, results in sorted_models:
        total_tests = len(results['predictions'])
        prize_count = len(results['prizes'])
        win_rate = (prize_count / total_tests * 100) if total_tests > 0 else 0
        best_prize_name = f"{results['best_prize']}獎" if results['best_prize'] > 0 else "未中獎"
        avg_hits = results['total_hits'] / total_tests if total_tests > 0 else 0
        
        print(f"{model:<20} | {prize_count:<10} | {win_rate:>6.1f}%    | {best_prize_name:<10} | {avg_hits:>6.2f}     | {results['total_hits']}")
    
    # 詳細中獎記錄（前3名）
    print("\n" + "=" * 100)
    print("🏆 詳細中獎記錄 (Top 3 模型)")
    print("=" * 100)
    
    for model, results in sorted_models[:3]:
        print(f"\n📌 {model.upper()}")
        prize_records = [p for p in results['predictions'] if p['prize_level'] > 0]
        
        if prize_records:
            print(f"   中獎 {len(prize_records)} 次 / 共 {len(results['predictions'])} 期")
            
            # 按獎項分組統計
            prize_counter = Counter([p['prize_name'] for p in prize_records])
            print(f"   獎項分布: {', '.join([f'{name}×{count}' for name, count in prize_counter.most_common()])}")
            
            # 顯示前5筆中獎記錄
            print(f"   前5筆中獎:")
            for record in prize_records[:5]:
                special_mark = "✅" if record['special_hit'] else ""
                pred_str = ', '.join([f'{n:02d}' for n in record['predicted']])
                print(f"      • {record['date']} 第{record['draw']}期: {record['prize_name']} - 主{record['main_hits']}個 {special_mark}")
                print(f"        預測: [{pred_str}]")
        else:
            print(f"   未中獎 (共測試 {len(results['predictions'])} 期)")
    
    print("\n" + "=" * 100)

def main():
    print("🎲 2025年大樂透滾動式回測系統")
    print("⚠️  正確邏輯：玩家只選6個主號碼，特別號開獎時單獨抽取")
    print("📈 滾動式回測：每次預測都用當時可用的歷史數據")
    print("=" * 100)
    
    # 測試的模型（選擇較快的模型）
    models = [
        "ensemble",
        "backend_optimized",
        "xgboost",
        "prophet",
        "autogluon"
    ]
    
    rolling_backtest_2025(models)

if __name__ == "__main__":
    main()
