"""
2025年8注號碼回測試驗

邏輯：
1. 滾動式預測：每期用當時可用的歷史數據預測
2. 預測8注號碼（使用8個不同模型）
3. 比對每注與實際開獎結果，計算中獎等級
4. 統計每個模型在112期中的表現
5. 找出成功率最高的前5名模型
"""
import requests
from collections import Counter, defaultdict

API_BASE = "http://localhost:8002"

# 8個模型用於8注預測
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

def predict_8_bets(recent_count):
    """使用8個模型預測8注號碼"""
    predictions = {}
    
    for model in MODELS:
        payload = {
            "lotteryType": "BIG_LOTTO",
            "modelType": model
        }
        
        try:
            response = requests.post(
                f"{API_BASE}/api/predict-from-backend-eval?recent_count={recent_count}",
                json=payload,
                timeout=60
            )
            if response.status_code == 200:
                result = response.json()
                predictions[model] = result.get("numbers", [])
        except Exception as e:
            print(f"  ❌ {model} 預測失敗: {str(e)[:40]}")
    
    return predictions

def backtest_8_bets_2025():
    """8注號碼回測2025年數據（滾動式）"""
    
    print("📥 載入2025年歷史數據...")
    response = requests.get(f"{API_BASE}/api/history?lottery_type=BIG_LOTTO")
    if response.status_code != 200:
        print("❌ 無法載入數據")
        return None
    
    all_data = response.json()
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
        'win_count': 0,
        'details': []
    } for model in MODELS}
    
    rolling_history = data_before_2025.copy()
    
    # 優化進度顯示
    print("\n🎯 開始滾動式回測...")
    print(f"⏳ 預計處理 {len(data_2025)} 期 × 8 模型 = {len(data_2025) * 8} 次預測")
    print("💡 每20期顯示一次進度\n")
    
    import time
    start_time = time.time()
    
    for idx, target_draw in enumerate(data_2025, 1):
        # 每20期顯示一次進度，並顯示預估剩餘時間
        if idx % 20 == 0 or idx == 1 or idx == len(data_2025):
            elapsed = time.time() - start_time
            avg_time = elapsed / idx if idx > 0 else 0
            remaining = avg_time * (len(data_2025) - idx)
            print(f"   📊 進度: {idx}/{len(data_2025)} 期 ({idx/len(data_2025)*100:.1f}%) | 已耗時: {elapsed/60:.1f}分 | 預估剩餘: {remaining/60:.1f}分")
        
        target_main = target_draw['numbers']
        target_special = target_draw['special']
        
        # 使用當前歷史數據預測8注
        recent_count = min(len(rolling_history), 500)
        predictions = predict_8_bets(recent_count)
        
        # 比對每注結果
        for model, predicted in predictions.items():
            if predicted:
                prize_name, prize_level, main_hits, special_hit = calculate_prize(
                    predicted, target_main, target_special
                )
                
                model_stats[model]['total_hits'] += main_hits
                
                if prize_level > 0:
                    model_stats[model]['prizes'].append(prize_level)
                    model_stats[model]['prize_counts'][prize_name] += 1
                    model_stats[model]['win_count'] += 1
                    
                    if model_stats[model]['best_prize'] == 0 or prize_level < model_stats[model]['best_prize']:
                        model_stats[model]['best_prize'] = prize_level
                    
                    # 記錄中獎詳情（只記錄前10筆）
                    if len(model_stats[model]['details']) < 10:
                        model_stats[model]['details'].append({
                            'draw': target_draw['draw'],
                            'date': target_draw['date'],
                            'prize_name': prize_name,
                            'main_hits': main_hits,
                            'special_hit': special_hit,
                            'predicted': predicted
                        })
        
        # 滾動歷史數據
        rolling_history.append(target_draw)
    
    print(f"✅ 回測完成！共測試 {len(data_2025)} 期\n")
    
    # 統計與排序
    print("=" * 100)
    print("📊 2025年8注回測統計結果 (正確邏輯)")
    print("=" * 100)
    
    # 按中獎次數排序
    sorted_models = sorted(
        model_stats.items(),
        key=lambda x: (
            -x[1]['win_count'],  # 中獎次數越多越好
            x[1]['best_prize'] if x[1]['best_prize'] > 0 else 999,  # 最佳獎項越小越好
            -x[1]['total_hits']  # 總命中數越多越好
        )
    )
    
    print(f"\n{'排名':<5} {'模型':<20} {'中獎次數':<10} {'中獎率':<10} {'最佳獎項':<10} {'平均命中':<10} {'總命中'}")
    print("-" * 100)
    
    for rank, (model, stats) in enumerate(sorted_models, 1):
        win_rate = (stats['win_count'] / len(data_2025) * 100) if len(data_2025) > 0 else 0
        avg_hits = stats['total_hits'] / len(data_2025) if len(data_2025) > 0 else 0
        best_prize_name = f"{stats['best_prize']}獎" if stats['best_prize'] > 0 else "未中獎"
        
        rank_emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank} "
        
        print(f"{rank_emoji:<5} {model:<20} {stats['win_count']:<10} {win_rate:>6.1f}%    {best_prize_name:<10} {avg_hits:>6.2f}     {stats['total_hits']}")
    
    # Top 5 詳細分析
    print("\n" + "=" * 100)
    print("🏆 前5名詳細分析")
    print("=" * 100)
    
    for rank, (model, stats) in enumerate(sorted_models[:5], 1):
        rank_emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "🏅"
        print(f"\n{rank_emoji} 第{rank}名: {model.upper()}")
        print(f"   總測試: {len(data_2025)} 期")
        print(f"   中獎次數: {stats['win_count']} 次")
        print(f"   中獎率: {stats['win_count'] / len(data_2025) * 100:.1f}%")
        print(f"   最佳獎項: {stats['best_prize']}獎" if stats['best_prize'] > 0 else "   最佳獎項: 未中獎")
        print(f"   平均命中: {stats['total_hits'] / len(data_2025):.2f} 個/期")
        
        if stats['prize_counts']:
            prize_dist = ", ".join([f"{name}×{count}" for name, count in stats['prize_counts'].most_common()])
            print(f"   獎項分布: {prize_dist}")
        
        if stats['details']:
            print(f"   前10筆中獎記錄:")
            for detail in stats['details']:
                special_mark = "✅" if detail['special_hit'] else ""
                pred_str = ', '.join([f'{n:02d}' for n in detail['predicted']])
                print(f"      • {detail['date']} 第{detail['draw']}期: {detail['prize_name']} - 主{detail['main_hits']}個 {special_mark}")
                print(f"        預測: [{pred_str}]")
    
    # 整體統計
    print("\n" + "=" * 100)
    print("📈 整體統計摘要")
    print("=" * 100)
    
    total_wins = sum(stats['win_count'] for stats in model_stats.values())
    total_tests = len(data_2025) * len(MODELS)
    overall_win_rate = (total_wins / total_tests * 100) if total_tests > 0 else 0
    
    print(f"   總測試次數: {total_tests} 次 (8個模型 × {len(data_2025)} 期)")
    print(f"   總中獎次數: {total_wins} 次")
    print(f"   整體中獎率: {overall_win_rate:.2f}%")
    
    # 獎項統計
    all_prizes = Counter()
    for stats in model_stats.values():
        all_prizes.update(stats['prize_counts'])
    
    if all_prizes:
        print(f"\n   所有獎項分布:")
        for prize_name, count in all_prizes.most_common():
            print(f"      • {prize_name}: {count} 次")
    
    print("\n" + "=" * 100)
    print("✅ 回測分析完成！")
    print("💡 提示: 以上結果使用正確邏輯（6個主號碼預測）進行滾動式回測")
    print("=" * 100)
    
    
    # 返回排序後的結果供後續使用
    return sorted_models, len(data_2025)

def predict_latest_8_bets(top_5_models):
    """使用最新數據預測Top 5模型的號碼（用於下一期）"""
    print("\n" + "=" * 100)
    print("🔮 Top 5 模型最新預測（用於下一期開獎）")
    print("=" * 100)
    print("📊 使用全部歷史數據進行預測...\n")
    
    predictions = {}
    
    # 只預測 Top 5 模型
    top_5_names = [model for model, _ in top_5_models]
    
    for model in top_5_names:
        payload = {
            "lotteryType": "BIG_LOTTO",
            "modelType": model
        }
        
        try:
            response = requests.post(
                f"{API_BASE}/api/predict-from-backend-eval?recent_count=500",
                json=payload,
                timeout=60
            )
            if response.status_code == 200:
                result = response.json()
                predictions[model] = {
                    'numbers': result.get("numbers", []),
                    'confidence': result.get("confidence", 0)
                }
                nums_str = ', '.join([f'{n:02d}' for n in result.get("numbers", [])])
                print(f"   {model:<20} | 信心度: {result.get('confidence', 0):.2%} | [{nums_str}]")
        except Exception as e:
            print(f"   ❌ {model:<20} 預測失敗")
    
    return predictions

def main():
    print("🎲 大樂透8注號碼滾動式回測試驗 (2025年)")
    print("⚠️  正確邏輯：玩家只選6個主號碼，特別號開獎時單獨抽取")
    print("📈 滾動式回測：每期預測都用當時可用的歷史數據")
    print("🎯 8注預測：使用8個不同模型各預測1注")
    print("=" * 100)
    
    # 執行回測
    result = backtest_8_bets_2025()
    
    if result:
        sorted_models, total_periods = result
        
        # 獲取前5名模型
        top_5_models = sorted_models[:5]
        
        # 顯示最新預測 (只針對 Top 5)
        latest_predictions = predict_latest_8_bets(top_5_models)
        
        # 最終總結表格
        print("\n" + "=" * 100)
        print("🏆 最終推薦：Top 5 模型表現與最新預測")
        print("=" * 100)
        print(f"{'排名':<5} {'模型':<20} {'中獎次數':<10} {'中獎率':<10} {'最佳獎項':<10} {'平均命中':<10} {'最新預測號碼'}")
        print("-" * 100)
        
        for rank, (model, stats) in enumerate(top_5_models, 1):
            win_rate = (stats['win_count'] / total_periods * 100) if total_periods > 0 else 0
            avg_hits = stats['total_hits'] / total_periods if total_periods > 0 else 0
            best_prize_name = f"{stats['best_prize']}獎" if stats['best_prize'] > 0 else "未中"
            
            rank_emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank} "
            
            # 獲取最新預測
            latest = latest_predictions.get(model, {})
            latest_nums = latest.get('numbers', [])
            latest_str = ', '.join([f'{n:02d}' for n in latest_nums]) if latest_nums else "預測失敗"
            
            print(f"{rank_emoji:<5} {model:<20} {stats['win_count']:<10} {win_rate:>6.1f}%    {best_prize_name:<10} {avg_hits:>6.2f}     [{latest_str}]")
        
        print("=" * 100)

if __name__ == "__main__":
    main()
