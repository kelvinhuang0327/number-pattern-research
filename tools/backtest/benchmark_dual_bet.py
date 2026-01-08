#!/usr/bin/env python3
"""
雙注策略成功率比較基準測試
比較 雙注混合策略 vs 熱冷分離策略 的歷史命中率
"""

import sqlite3
import os
from collections import defaultdict
from datetime import datetime

# 數據庫路徑
DB_PATH = os.path.join(os.path.dirname(__file__), 'lottery-api', 'data', 'lottery.db')

def load_data(lottery_type='BIG_LOTTO', limit=None):
    """載入歷史數據（含特別號）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 查詢包含特別號
    query = """
        SELECT draw, date, numbers, special 
        FROM draws 
        WHERE lottery_type = ? 
        ORDER BY CAST(draw AS INTEGER) DESC
    """
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query, (lottery_type,))
    rows = cursor.fetchall()
    conn.close()
    
    data = []
    for row in rows:
        draw, date, numbers_str, special = row
        numbers = [int(n) for n in numbers_str.split(',') if n.strip().isdigit()]
        
        # 構建號碼集合（6 主號碼 + 特別號 = 7 個目標）
        numbers_set = set(numbers)
        if special is not None:
            numbers_set.add(int(special))  # 加入特別號
        
        data.append({
            'draw': draw,
            'date': date,
            'numbers': numbers_set,  # 現在包含 7 個號碼
            'main_numbers': numbers,  # 保留原始 6 個主號碼
            'special': special
        })
    
    return data

def calculate_frequency(data, min_num=1, max_num=49):
    """計算號碼頻率"""
    freq = defaultdict(int)
    for draw in data:
        for num in draw['numbers']:
            freq[num] += 1
    return freq

def predict_dual_bet_hybrid(historical_data, pick_count=6, min_num=1, max_num=49):
    """
    雙注混合策略模擬
    使用頻率、貝葉斯、統計、冷熱混合的結果
    簡化版：使用頻率+遺漏值+近期趨勢
    """
    if len(historical_data) < 30:
        return None, None
    
    scores = defaultdict(float)
    
    # 1. 頻率分析 (權重 30%)
    freq = calculate_frequency(historical_data)
    max_freq = max(freq.values()) if freq else 1
    for num in range(min_num, max_num + 1):
        scores[num] += (freq.get(num, 0) / max_freq) * 0.3 * 10
    
    # 2. 近期趨勢 (最近30期，權重 30%)
    recent_freq = calculate_frequency(historical_data[:30])
    max_recent = max(recent_freq.values()) if recent_freq else 1
    for num in range(min_num, max_num + 1):
        scores[num] += (recent_freq.get(num, 0) / max_recent) * 0.3 * 10
    
    # 3. 遺漏值回歸 (權重 20%)
    missing_counts = {}
    for num in range(min_num, max_num + 1):
        missing = 0
        for draw in historical_data:
            if num in draw['numbers']:
                break
            missing += 1
        missing_counts[num] = missing
    
    max_missing = max(missing_counts.values()) if missing_counts else 1
    for num in range(min_num, max_num + 1):
        # 遺漏越久，越可能出現
        scores[num] += (missing_counts[num] / max_missing) * 0.2 * 10
    
    # 4. 區間平衡 (權重 20%)
    zones = [range(1, 11), range(11, 21), range(21, 31), range(31, 41), range(41, 50)]
    zone_freq = defaultdict(int)
    for draw in historical_data[:50]:
        for num in draw['numbers']:
            for i, zone in enumerate(zones):
                if num in zone:
                    zone_freq[i] += 1
    
    # 選出得分最高的12個號碼
    sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_12 = [num for num, score in sorted_nums[:12]]
    
    bet1 = sorted(top_12[:pick_count])
    bet2 = sorted(top_12[pick_count:pick_count*2])
    
    return bet1, bet2

def predict_hot_cold_split(historical_data, pick_count=6, min_num=1, max_num=49):
    """
    熱冷分離策略
    第一注用熱號，第二注用冷號
    """
    if len(historical_data) < 30:
        return None, None
    
    freq = calculate_frequency(historical_data)
    
    sorted_by_freq = sorted(
        [(num, freq.get(num, 0)) for num in range(min_num, max_num + 1)],
        key=lambda x: x[1],
        reverse=True
    )
    
    # 熱門號碼（頻率最高）
    hot_numbers = sorted([num for num, _ in sorted_by_freq[:pick_count]])
    
    # 冷門號碼（頻率最低）
    cold_numbers = sorted([num for num, _ in sorted_by_freq[-pick_count:]])
    
    return hot_numbers, cold_numbers

def calculate_match_count(predicted, actual):
    """計算命中數"""
    return len(set(predicted) & actual)

def run_backtest(data, strategy_func, strategy_name, window_size=100, test_count=100):
    """
    執行回測
    使用滑動窗口：用前 window_size 期預測下一期
    """
    print(f"\n{'='*60}")
    print(f"策略: {strategy_name}")
    print(f"回測設定: 訓練窗口={window_size}期, 測試次數={test_count}")
    print('='*60)
    
    results = {
        'bet1_matches': defaultdict(int),  # {命中數: 次數}
        'bet2_matches': defaultdict(int),
        'combined_matches': defaultdict(int),  # 兩注合計最高命中
        'any_prize': 0,  # 任一注中3個以上
        'total_tests': 0
    }
    
    # 數據是降序排列（最新在前），所以我們要從後往前
    for i in range(test_count):
        test_idx = i + 1  # 測試的期數位置
        train_end = test_idx + window_size
        
        if train_end >= len(data):
            break
        
        # 訓練數據（歷史）
        train_data = data[test_idx:train_end]
        # 測試數據（下一期）
        actual_numbers = data[test_idx - 1]['numbers']
        
        bet1, bet2 = strategy_func(train_data)
        
        if bet1 is None or bet2 is None:
            continue
        
        results['total_tests'] += 1
        
        match1 = calculate_match_count(bet1, actual_numbers)
        match2 = calculate_match_count(bet2, actual_numbers)
        
        results['bet1_matches'][match1] += 1
        results['bet2_matches'][match2] += 1
        results['combined_matches'][max(match1, match2)] += 1
        
        if match1 >= 3 or match2 >= 3:
            results['any_prize'] += 1
    
    # 輸出結果
    total = results['total_tests']
    print(f"\n總測試次數: {total}")
    
    print(f"\n📊 第一注命中分佈:")
    for i in range(7):
        count = results['bet1_matches'][i]
        pct = count / total * 100 if total > 0 else 0
        bar = '█' * int(pct / 2)
        print(f"  {i}個: {count:4d} ({pct:5.1f}%) {bar}")
    
    print(f"\n📊 第二注命中分佈:")
    for i in range(7):
        count = results['bet2_matches'][i]
        pct = count / total * 100 if total > 0 else 0
        bar = '█' * int(pct / 2)
        print(f"  {i}個: {count:4d} ({pct:5.1f}%) {bar}")
    
    print(f"\n🎯 雙注合計 (取較高者):")
    for i in range(7):
        count = results['combined_matches'][i]
        pct = count / total * 100 if total > 0 else 0
        bar = '█' * int(pct / 2)
        print(f"  {i}個: {count:4d} ({pct:5.1f}%) {bar}")
    
    any_prize_pct = results['any_prize'] / total * 100 if total > 0 else 0
    print(f"\n🏆 任一注中3個以上: {results['any_prize']}/{total} ({any_prize_pct:.1f}%)")
    
    # 計算期望值
    expected_bet1 = sum(k * v for k, v in results['bet1_matches'].items()) / total if total > 0 else 0
    expected_bet2 = sum(k * v for k, v in results['bet2_matches'].items()) / total if total > 0 else 0
    expected_combined = sum(k * v for k, v in results['combined_matches'].items()) / total if total > 0 else 0
    
    print(f"\n📈 平均命中數:")
    print(f"  第一注: {expected_bet1:.2f}")
    print(f"  第二注: {expected_bet2:.2f}")
    print(f"  雙注最高: {expected_combined:.2f}")
    
    return results

def predict_optimized_ensemble(historical_data, pick_count=6, min_num=1, max_num=49):
    """
    優化集成策略模擬（完整版）
    模擬後端 OptimizedEnsemblePredictor 的完整邏輯
    包含：區域平衡、奇偶平衡、頻率、貝葉斯、蒙地卡羅、冷熱
    """
    if len(historical_data) < 50:
        return None, None
    
    # 權重設定 (參考 optimized_ensemble.py RECOMMENDED_WEIGHTS)
    strategies = {
        'zone_balance': 0.25,
        'odd_even': 0.22,
        'frequency': 0.18,
        'bayesian': 0.15,
        'monte_carlo': 0.12,
        'hot_cold': 0.08
    }
    
    scores = defaultdict(float)
    import numpy as np
    import random
    
    # 1. 頻率分析 (Frequency)
    freq = calculate_frequency(historical_data)
    max_freq = max(freq.values()) if freq else 1
    for num in range(min_num, max_num + 1):
        # 基礎頻率分
        f_score = freq.get(num, 0) / max_freq
        scores[num] += f_score * strategies['frequency'] * 10

    # 2. 貝葉斯 (Bayesian - Simplified)
    total_draws = len(historical_data)
    recent_window = 20
    recent_freq = calculate_frequency(historical_data[:recent_window])
    for num in range(min_num, max_num + 1):
        prior = freq.get(num, 0) / (total_draws * pick_count) if total_draws > 0 else 0
        likelihood = recent_freq.get(num, 0) / recent_window if recent_window > 0 else 0
        posterior = prior * 0.4 + likelihood * 0.6
        # Normalize posterior roughly to 0-1 range for scoring
        scores[num] += posterior * 100 * strategies['bayesian']

    # 3. 蒙地卡羅 (Monte Carlo)
    # 建立加權池
    mc_weights = []
    for num in range(min_num, max_num + 1):
        # 頻率權重 + 隨機擾動
        w = (freq.get(num, 0) / total_draws) * 10 + 1.0
        mc_weights.append(w)
    
    mc_weights = np.array(mc_weights)
    mc_weights /= mc_weights.sum()
    
    mc_results = defaultdict(int)
    simulations = 1000  # 模擬次數 (benchmarking 時減少次數以加快速度)
    
    valid_range = np.arange(min_num, max_num + 1)
    for _ in range(simulations):
        # 這裡需要注意：numpy choice 的 p 參數長度必須與 valid_range 一致
        if len(valid_range) == len(mc_weights):
            selected = np.random.choice(valid_range, size=pick_count, replace=False, p=mc_weights)
            for s in selected:
                mc_results[s] += 1
                
    max_mc = max(mc_results.values()) if mc_results else 1
    for num in range(min_num, max_num + 1):
        scores[num] += (mc_results.get(num, 0) / max_mc) * strategies['monte_carlo'] * 10

    # 4. 區域平衡 (Zone Balance)
    # 簡化版：固定三區 (1-16, 17-33, 34-49)
    zones = [
        range(1, 17),
        range(17, 34),
        range(34, 50)
    ]
    # 分析近期(10期)區域出號分佈
    recent_10 = historical_data[:10]
    zone_counts = [0, 0, 0]
    for draw in recent_10:
        for num in draw['numbers']:
            for i, z in enumerate(zones):
                if num in z:
                    zone_counts[i] += 1
    
    # 計算期望值 (平均分佈)
    total_recent = sum(zone_counts) if sum(zone_counts) > 0 else 1
    expected_ratio = 1.0 / 3.0
    
    # 如果某區出號少，該區號碼加分 (均值回歸)
    for i, z in enumerate(zones):
        ratio = zone_counts[i] / total_recent
        if ratio < expected_ratio:
            # 該區偏冷，加分
            boost = (expected_ratio - ratio) * 5
        else:
            boost = 0
            
        for num in z:
            scores[num] += boost * strategies['zone_balance']

    # 5. 奇偶平衡 (Odd/Even)
    # 分析近期奇偶比
    odd_count = 0
    total_nums = 0
    for draw in recent_10:
        for num in draw['numbers']:
            if num % 2 == 1:
                odd_count += 1
            total_nums += 1
            
    odd_ratio = odd_count / total_nums if total_nums > 0 else 0.5
    
    # 如果奇數少，奇數加分；偶數少，偶數加分
    target_ratio = 0.5
    if odd_ratio < target_ratio:
        # 奇數偏少，加分奇數
        odd_boost = (target_ratio - odd_ratio) * 5
        even_boost = 0
    else:
        # 偶數偏少，加分偶數
        odd_boost = 0
        even_boost = (odd_ratio - target_ratio) * 5
        
    for num in range(min_num, max_num + 1):
        if num % 2 == 1:
            scores[num] += odd_boost * strategies['odd_even']
        else:
            scores[num] += even_boost * strategies['odd_even']

    # 6. 冷熱混合 (Hot/Cold) - 簡化版
    # 這裡我們已經有 freq 分數了，這策略給予極冷和極熱號碼額外關注
    sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    hot_nums = {n for n, _ in sorted_freq[:10]}
    cold_nums = {n for n, _ in sorted_freq[-10:]}
    
    for num in range(min_num, max_num + 1):
        if num in hot_nums:
            scores[num] += 1.0 * strategies['hot_cold'] # 熱號追熱
        elif num in cold_nums:
            scores[num] += 0.5 * strategies['hot_cold'] # 冷號防回補

    # 選出最高分的號碼
    sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_12 = [num for num, score in sorted_nums[:15]] # 取前15個比較保險
    
    # 確保有足夠號碼
    if len(top_12) < pick_count * 2:
        remain = [n for n in range(min_num, max_num+1) if n not in top_12]
        top_12.extend(remain[:pick_count*2 - len(top_12)])
        
    bet1 = sorted(top_12[:pick_count])
    bet2 = sorted(top_12[pick_count:pick_count*2])
    
    return bet1, bet2


def main():
    print("🎰 雙注策略成功率比較（含優化集成）")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 載入數據
    print("\n📥 載入歷史數據...")
    data = load_data('BIG_LOTTO')
    print(f"✅ 共載入 {len(data)} 期數據")
    
    if len(data) < 200:
        print("❌ 數據量不足，需要至少 200 期")
        return
    
    # 測試參數
    window_size = 100
    test_count = min(500, len(data) - window_size - 1)
    
    # 測試優化集成策略
    results_optimized = run_backtest(
        data, 
        predict_optimized_ensemble, 
        "🏆 優化集成預測",
        window_size,
        test_count
    )
    
    # 測試雙注混合策略
    results_hybrid = run_backtest(
        data, 
        predict_dual_bet_hybrid, 
        "🎯 雙注混合策略",
        window_size,
        test_count
    )
    
    # 測試熱冷分離策略
    results_hotcold = run_backtest(
        data,
        predict_hot_cold_split,
        "🔥❄️ 熱冷分離策略",
        window_size,
        test_count
    )
    
    # 比較結果
    print("\n" + "="*60)
    print("📊 策略比較總結")
    print("="*60)
    
    optimized_any = results_optimized['any_prize'] / results_optimized['total_tests'] * 100
    hybrid_any = results_hybrid['any_prize'] / results_hybrid['total_tests'] * 100
    hotcold_any = results_hotcold['any_prize'] / results_hotcold['total_tests'] * 100
    
    optimized_exp = sum(k * v for k, v in results_optimized['combined_matches'].items()) / results_optimized['total_tests']
    hybrid_exp = sum(k * v for k, v in results_hybrid['combined_matches'].items()) / results_hybrid['total_tests']
    hotcold_exp = sum(k * v for k, v in results_hotcold['combined_matches'].items()) / results_hotcold['total_tests']
    
    print(f"\n任一注中3個以上的機率:")
    print(f"  🏆 優化集成: {optimized_any:.1f}%")
    print(f"  🎯 雙注混合: {hybrid_any:.1f}%")
    print(f"  🔥❄️ 熱冷分離: {hotcold_any:.1f}%")
    
    print(f"\n雙注最高平均命中數:")
    print(f"  🏆 優化集成: {optimized_exp:.2f}")
    print(f"  🎯 雙注混合: {hybrid_exp:.2f}")
    print(f"  🔥❄️ 熱冷分離: {hotcold_exp:.2f}")
    
    # 找出最佳策略
    results = [
        ("🏆 優化集成預測", optimized_any, optimized_exp),
        ("🎯 雙注混合策略", hybrid_any, hybrid_exp),
        ("🔥❄️ 熱冷分離策略", hotcold_any, hotcold_exp)
    ]
    best = max(results, key=lambda x: x[1])
    print(f"\n🥇 推薦策略: {best[0]} (中3+機率: {best[1]:.1f}%)")

if __name__ == '__main__':
    main()
