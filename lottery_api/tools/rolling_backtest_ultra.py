"""
滾動回測：UltraOptimizedPredictor vs 既有方法

測試 2025 年威力彩數據，比較各預測方法的命中率
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import json
from collections import Counter, defaultdict
import numpy as np

# Import predictors
from models.ultra_optimized_predictor import UltraOptimizedPredictor, detect_lottery_type
from models.enhanced_predictor import EnhancedPredictor

def load_power_lotto_data():
    """載入所有威力彩數據"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'lottery.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT draw, date, numbers, special
        FROM draws
        WHERE lottery_type = 'POWER_LOTTO'
        ORDER BY date DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        numbers = json.loads(row[2]) if isinstance(row[2], str) else row[2]
        results.append({
            'draw_term': row[0],
            'date': row[1],
            'numbers': numbers,
            'special': int(row[3]) if row[3] else None
        })

    return results


def rolling_backtest_2025():
    """滾動回測 2025 年威力彩"""
    print("=" * 70)
    print("滾動回測：UltraOptimizedPredictor vs 既有方法")
    print("=" * 70)

    # 載入數據
    all_data = load_power_lotto_data()
    print(f"總數據筆數: {len(all_data)}")

    # 分離 2025 年數據 (測試集) 和之前數據 (訓練集)
    test_data = [d for d in all_data if d['date'].startswith('2025')]
    print(f"2025 年數據筆數: {len(test_data)}")

    if len(test_data) == 0:
        print("找不到 2025 年數據！")
        return

    # 威力彩規則
    lottery_rules = {
        'lotteryType': 'POWER_LOTTO',
        'maxNumber': 38,
        'pickCount': 6,
        'minNumber': 1,
        'hasSpecialNumber': True,
        'specialNumberMax': 8
    }

    # 初始化預測器
    ultra_predictor = UltraOptimizedPredictor()
    enhanced_predictor = EnhancedPredictor()

    # 追蹤各方法的命中結果
    results = {
        'ultra_optimized': {'matches': [], 'name': 'Ultra Optimized (新)'},
        'cold_comeback': {'matches': [], 'name': '冷號回歸 v2'},
        'temporal': {'matches': [], 'name': '時序分析'},
        'feature_eng': {'matches': [], 'name': '特徵工程'},
        'enhanced_ensemble': {'matches': [], 'name': '綜合增強'},
        'random': {'matches': [], 'name': '隨機基準'},
    }

    print(f"\n開始滾動回測 {len(test_data)} 期...")
    print("-" * 70)

    for i, test_draw in enumerate(reversed(test_data)):  # 從舊到新
        draw_term = test_draw['draw_term']
        actual_numbers = set(test_draw['numbers'])

        # 找出該期之前的所有歷史數據
        draw_date = test_draw['date']
        history = [d for d in all_data if d['date'] < draw_date]

        if len(history) < 100:
            continue

        # 各方法預測
        predictions = {}

        # 1. Ultra Optimized
        try:
            pred = ultra_predictor.predict(history, lottery_rules)
            predictions['ultra_optimized'] = set(pred['numbers'])
        except Exception as e:
            predictions['ultra_optimized'] = set()

        # 2. Cold Comeback
        try:
            pred = enhanced_predictor.cold_number_comeback_predict(history, lottery_rules)
            predictions['cold_comeback'] = set(pred['numbers'])
        except Exception as e:
            predictions['cold_comeback'] = set()

        # 3. Temporal (from unified_predictor)
        try:
            from models.unified_predictor import prediction_engine
            pred = prediction_engine.temporal_predict(history, lottery_rules)
            predictions['temporal'] = set(pred['numbers'])
        except Exception as e:
            predictions['temporal'] = set()

        # 4. Feature Engineering (from unified_predictor)
        try:
            from models.unified_predictor import prediction_engine
            pred = prediction_engine.feature_engineering_predict(history, lottery_rules)
            predictions['feature_eng'] = set(pred['numbers'])
        except Exception as e:
            predictions['feature_eng'] = set()

        # 5. Enhanced Ensemble
        try:
            pred = enhanced_predictor.enhanced_ensemble_predict(history, lottery_rules)
            predictions['enhanced_ensemble'] = set(pred['numbers'])
        except Exception as e:
            predictions['enhanced_ensemble'] = set()

        # 6. Random baseline
        import random
        random_pred = set(random.sample(range(1, 39), 6))
        predictions['random'] = random_pred

        # 計算命中數
        for method, pred_nums in predictions.items():
            matches = len(pred_nums & actual_numbers)
            results[method]['matches'].append(matches)

        # 每 20 期顯示進度
        if (i + 1) % 20 == 0:
            print(f"已完成 {i + 1}/{len(test_data)} 期")

    # 輸出結果統計
    print("\n" + "=" * 70)
    print("回測結果統計")
    print("=" * 70)

    summary_data = []

    for method, data in results.items():
        matches = data['matches']
        if len(matches) == 0:
            continue

        avg_match = np.mean(matches)
        max_match = max(matches)
        match_dist = Counter(matches)

        # 計算各命中數的比例
        total = len(matches)
        dist_str = ', '.join([f"{k}中:{match_dist.get(k, 0)}" for k in range(0, 7)])

        summary_data.append({
            'name': data['name'],
            'avg': avg_match,
            'max': max_match,
            'total': total,
            'dist': match_dist,
            'matches': matches
        })

    # 按平均命中排序
    summary_data.sort(key=lambda x: -x['avg'])

    print(f"\n{'方法':<20} {'期數':>6} {'平均命中':>10} {'最高':>6} {'0中':>6} {'1中':>6} {'2中':>6} {'3中':>6} {'4+中':>6}")
    print("-" * 80)

    for s in summary_data:
        dist = s['dist']
        four_plus = sum(dist.get(k, 0) for k in range(4, 7))
        print(f"{s['name']:<20} {s['total']:>6} {s['avg']:>10.3f} {s['max']:>6} "
              f"{dist.get(0, 0):>6} {dist.get(1, 0):>6} {dist.get(2, 0):>6} "
              f"{dist.get(3, 0):>6} {four_plus:>6}")

    # 檢驗 Ultra Optimized 相對表現
    print("\n" + "=" * 70)
    print("Ultra Optimized 相對表現分析")
    print("=" * 70)

    ultra_matches = results['ultra_optimized']['matches']
    if ultra_matches:
        # 與各方法的逐期比較
        for method, data in results.items():
            if method == 'ultra_optimized':
                continue
            other_matches = data['matches']
            if len(other_matches) != len(ultra_matches):
                continue

            wins = sum(1 for u, o in zip(ultra_matches, other_matches) if u > o)
            ties = sum(1 for u, o in zip(ultra_matches, other_matches) if u == o)
            losses = sum(1 for u, o in zip(ultra_matches, other_matches) if u < o)

            print(f"vs {data['name']:<15}: 勝 {wins:>3}, 平 {ties:>3}, 負 {losses:>3}")

        # 最佳表現期數
        best_periods = [(i, m) for i, m in enumerate(ultra_matches) if m >= 3]
        if best_periods:
            print(f"\nUltra Optimized 命中 3+ 的期數: {len(best_periods)}")
            for idx, match_count in best_periods[:10]:  # 只顯示前10
                print(f"  第 {idx+1} 期: 命中 {match_count} 個")


if __name__ == '__main__':
    rolling_backtest_2025()
