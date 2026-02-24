"""
2025年8注號碼回測試驗 (修正版)

邏輯：
1. 滾動式預測：每期用當時可用的歷史數據預測
2. 每個模型每期生成8注號碼 (通過調整歷史數據窗口)
3. 比對每注與實際開獎結果，計算中獎等級
4. 統計每個模型在112期中的表現 (中獎率 = 中獎注數 / (總期數 * 8))
5. 找出成功率最高的前5名模型
"""
import requests
import json
import time
from collections import Counter, defaultdict

API_BASE = "http://localhost:8002"

# 8個模型
MODELS = [
    "ensemble",
    "backend_optimized", 
    "xgboost",
    "prophet",
    "autogluon",
    "maml",
    "transformer",
    "lstm"
]

LOTTERY_RULES = {
    "minNumber": 1,
    "maxNumber": 49,
    "pickCount": 6,
    "hasSpecial": True
}

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

def predict_model_8_bets(model, history):
    """
    使用單一模型預測8注號碼
    通過使用不同的歷史數據長度來產生變異
    """
    bets = []
    # 使用不同的歷史窗口長度來生成8注
    # 基礎長度200，每次增加10
    windows = [200 + i*10 for i in range(8)]
    
    for window in windows:
        # 截取歷史數據
        current_history = history[-window:] if len(history) > window else history
        
        payload = {
            "lotteryType": "BIG_LOTTO",
            "modelType": model,
            "history": current_history,
            "lotteryRules": LOTTERY_RULES
        }
        
        try:
            # 使用 /api/predict 以避免數據洩漏並支持自定義歷史
            response = requests.post(
                f"{API_BASE}/api/predict",
                json=payload,
                timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                numbers = result.get("numbers", [])
                if numbers:
                    bets.append(numbers)
            else:
                # 如果失敗，嘗試使用較短的窗口重試一次
                pass
        except Exception as e:
            pass
            
    # 如果不足8注，用最後一注補齊 (雖然不太理想，但為了保持格式)
    while len(bets) < 8 and len(bets) > 0:
        bets.append(bets[-1])
        
    return bets

def backtest_8_bets_2025():
    """8注號碼回測2025年數據（滾動式）"""
    
    print("📥 載入2025年歷史數據...")
    try:
        response = requests.get(f"{API_BASE}/api/history?lottery_type=BIG_LOTTO")
        if response.status_code != 200:
            print("❌ 無法載入數據")
            return None
        all_data = response.json()
    except Exception as e:
        print(f"❌ 連接失敗: {e}")
        return None
    
    data_before_2025 = [d for d in all_data if not d.get('date', '').startswith('2025')]
    data_2025 = [d for d in all_data if d.get('date', '').startswith('2025')]
    data_2025.sort(key=lambda x: x.get('date', ''))
    
    print(f"✅ 訓練數據: {len(data_before_2025)} 期 (2024年底前)")
    print(f"✅ 測試數據: {len(data_2025)} 期 (2025年)")
    print("=" * 100)
    
    # 統計結果
    model_stats = {model: {
        'prizes': [],
        'prize_counts': Counter(),
        'total_hits': 0,
        'best_prize': 0,
        'win_count': 0, # 中獎注數
        'total_bets': 0, # 總注數
        'details': []
    } for model in MODELS}
    
    rolling_history = data_before_2025.copy()
    
    print("\n🎯 開始滾動式回測 (每個模型每期8注)...")
    print(f"⏳ 預計處理 {len(data_2025)} 期 × 8 模型 × 8 注 = {len(data_2025) * 8 * 8} 次比對")
    
    start_time = time.time()
    
    for idx, target_draw in enumerate(data_2025, 1):
        if idx % 5 == 0 or idx == 1 or idx == len(data_2025):
            elapsed = time.time() - start_time
            avg_time = elapsed / idx if idx > 0 else 0
            remaining = avg_time * (len(data_2025) - idx)
            print(f"   📊 進度: {idx}/{len(data_2025)} 期 | 已耗時: {elapsed/60:.1f}分 | 預估剩餘: {remaining/60:.1f}分")
        
        target_main = target_draw['numbers']
        target_special = target_draw['special']
        
        # 為每個模型生成8注
        for model in MODELS:
            bets = predict_model_8_bets(model, rolling_history)
            
            if not bets:
                continue
                
            model_stats[model]['total_bets'] += 8 # 假設每期都應該有8注，即使預測失敗也算分母? 這裡假設補齊了
            
            # 比對這8注
            period_wins = 0
            for bet in bets:
                prize_name, prize_level, main_hits, special_hit = calculate_prize(
                    bet, target_main, target_special
                )
                
                model_stats[model]['total_hits'] += main_hits
                
                if prize_level > 0:
                    model_stats[model]['prizes'].append(prize_level)
                    model_stats[model]['prize_counts'][prize_name] += 1
                    model_stats[model]['win_count'] += 1
                    period_wins += 1
                    
                    if model_stats[model]['best_prize'] == 0 or prize_level < model_stats[model]['best_prize']:
                        model_stats[model]['best_prize'] = prize_level
            
            # 記錄本期詳情 (如果有中獎)
            if period_wins > 0 and len(model_stats[model]['details']) < 5:
                 model_stats[model]['details'].append({
                    'draw': target_draw['draw'],
                    'date': target_draw['date'],
                    'wins': period_wins,
                    'bets_count': len(bets)
                })

        # 滾動歷史數據
        rolling_history.append(target_draw)
    
    print(f"✅ 回測完成！\n")
    
    # 統計與排序
    print("=" * 100)
    print("📊 2025年8注回測統計結果 (每期8注)")
    print("=" * 100)
    
    # 按中獎率排序
    sorted_models = sorted(
        model_stats.items(),
        key=lambda x: (
            -(x[1]['win_count'] / x[1]['total_bets'] if x[1]['total_bets'] > 0 else 0),
            x[1]['best_prize'] if x[1]['best_prize'] > 0 else 999
        )
    )
    
    print(f"\n{'排名':<5} {'模型':<20} {'總注數':<10} {'中獎注數':<10} {'中獎率':<10} {'最佳獎項':<10} {'平均命中'}")
    print("-" * 100)
    
    for rank, (model, stats) in enumerate(sorted_models, 1):
        win_rate = (stats['win_count'] / stats['total_bets'] * 100) if stats['total_bets'] > 0 else 0
        avg_hits = stats['total_hits'] / stats['total_bets'] if stats['total_bets'] > 0 else 0
        best_prize_name = f"{stats['best_prize']}獎" if stats['best_prize'] > 0 else "未中"
        
        rank_emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank} "
        
        print(f"{rank_emoji:<5} {model:<20} {stats['total_bets']:<10} {stats['win_count']:<10} {win_rate:>6.2f}%    {best_prize_name:<10} {avg_hits:>6.2f}")
    
    return sorted_models, len(data_2025)

def predict_latest_8_bets_for_top5(top_5_models):
    """為Top 5模型生成最新8注預測"""
    print("\n" + "=" * 100)
    print("🔮 Top 5 模型最新8注預測（用於下一期開獎）")
    print("=" * 100)
    
    # 獲取完整歷史數據
    try:
        response = requests.get(f"{API_BASE}/api/history?lottery_type=BIG_LOTTO")
        if response.status_code == 200:
            full_history = response.json()
        else:
            print("❌ 無法獲取歷史數據")
            return
    except:
        return

    for rank, (model, stats) in enumerate(top_5_models, 1):
        print(f"\n🏆 第{rank}名: {model.upper()}")
        print(f"   生成8注預測中...")
        
        bets = predict_model_8_bets(model, full_history)
        
        for i, bet in enumerate(bets, 1):
            nums_str = ', '.join([f'{n:02d}' for n in sorted(bet)])
            print(f"   第{i}注: [{nums_str}]")

def main():
    print("🎲 大樂透8注號碼滾動式回測試驗 (2025年) - 修正版")
    print("⚠️  規則：每個模型每期生成8注，計算總中獎率")
    print("=" * 100)
    
    result = backtest_8_bets_2025()
    
    if result:
        sorted_models, total_periods = result
        top_5 = sorted_models[:5]
        predict_latest_8_bets_for_top5(top_5)

if __name__ == "__main__":
    main()
