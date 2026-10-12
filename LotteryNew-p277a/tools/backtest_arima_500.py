#!/usr/bin/env python3
"""
ARIMA (1,0,0) 獨立驗證 - 500 期回測
=====================================
Claude 獨立驗證 Gemini 提出的 ARIMA 方法。

驗證目標:
  - 威力彩 (POWER_LOTTO): 2注, 500期
  - 大樂透 (BIG_LOTTO): 4注, 500期

執行:
  python3 tools/backtest_arima_500.py
  python3 tools/backtest_arima_500.py --quick   # 50期快速測試
"""
import os
import sys
import json
import sqlite3
import argparse
import warnings
import numpy as np
import pandas as pd
from datetime import datetime
from collections import Counter
from statsmodels.tsa.arima.model import ARIMA

warnings.filterwarnings("ignore")

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

SEED = 42
np.random.seed(SEED)


def get_history(lottery_type):
    """從數據庫讀取歷史數據 (時間正序)"""
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    if not os.path.exists(db_path):
        db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, date, numbers, special FROM draws
        WHERE lottery_type = ?
        ORDER BY date ASC, draw ASC
    """, (lottery_type,))

    draws = []
    for row in cursor.fetchall():
        numbers = json.loads(row[2]) if row[2] else []
        draws.append({
            'draw': row[0],
            'date': row[1],
            'numbers': numbers,
            'special': row[3]
        })
    conn.close()
    return draws


def random_baseline(num_bets, num_balls, pick_count=6, n_simulations=10000):
    """計算隨機基準 M3+"""
    rng = np.random.RandomState(42)
    m3_count = 0
    total = n_simulations

    for _ in range(n_simulations):
        best_match = 0
        actual = set(rng.choice(range(1, num_balls + 1), size=pick_count, replace=False))
        for _ in range(num_bets):
            pred = set(rng.choice(range(1, num_balls + 1), size=pick_count, replace=False))
            match = len(pred & actual)
            best_match = max(best_match, match)
        if best_match >= 3:
            m3_count += 1

    return m3_count / total * 100


def arima_predict_numbers(history, pick_count, max_num, min_num=1, order=(1, 0, 0)):
    """
    用 ARIMA 對每個位置獨立預測。
    嚴格複製 Gemini 的方法邏輯。
    """
    if len(history) < 10:
        return []

    main_numbers = [draw['numbers'] for draw in history]
    df = pd.DataFrame(main_numbers)

    if df.shape[1] < pick_count:
        return []

    arima_results = []
    for col in range(pick_count):
        series = df.iloc[:, col].astype(float)
        try:
            model = ARIMA(series, order=order)
            model_fit = model.fit()
            forecast = model_fit.forecast(steps=1)
            val = int(round(forecast.iloc[0]))
            val = max(min_num, min(max_num, val))
            arima_results.append(val)
        except Exception:
            arima_results.append(int(round(series.iloc[-1])))

    # 處理重複 (Gemini 的邏輯)
    final_numbers = []
    for n in arima_results:
        if n not in final_numbers:
            final_numbers.append(n)
        else:
            for candidate in range(min_num, max_num + 1):
                if candidate not in final_numbers:
                    final_numbers.append(candidate)
                    break

    return sorted(final_numbers[:pick_count])


def backtest_arima(lottery_type, test_periods, num_bets, order=(1, 0, 0),
                   progress_interval=50):
    """
    ARIMA 滾動式回測 (嚴格防數據洩漏)
    """
    if lottery_type == 'POWER_LOTTO':
        max_num, pick_count = 38, 6
    else:
        max_num, pick_count = 49, 6

    history = get_history(lottery_type)
    print(f"  數據量: {len(history)} 期")

    if len(history) < test_periods + 50:
        print(f"  數據不足: 需要 {test_periods + 50}, 只有 {len(history)}")
        return None

    start_idx = len(history) - test_periods
    matches_list = []

    for i in range(test_periods):
        target_idx = start_idx + i
        target_draw = history[target_idx]
        actual_numbers = set(target_draw['numbers'])

        # 只用過去數據
        past_history = history[:target_idx]

        if len(past_history) < 20:
            continue

        # 多注預測
        best_match = 0
        for bet_idx in range(num_bets):
            if bet_idx == 0:
                # 第一注: 標準 ARIMA 預測
                pred = arima_predict_numbers(
                    past_history, pick_count, max_num, order=order
                )
            else:
                # 額外注: 使用不同訓練窗口增加多樣性
                window = max(20, len(past_history) - bet_idx * 30)
                pred = arima_predict_numbers(
                    past_history[-window:], pick_count, max_num, order=order
                )

            if pred:
                match = len(set(pred) & actual_numbers)
                best_match = max(best_match, match)

        matches_list.append(best_match)

        if (i + 1) % progress_interval == 0:
            current_m3 = sum(1 for m in matches_list if m >= 3) / len(matches_list) * 100
            print(f"    進度: {i+1}/{test_periods} | M3+: {current_m3:.2f}%")

    total = len(matches_list)
    if total == 0:
        return None

    m3_plus = sum(1 for m in matches_list if m >= 3) / total * 100
    m4_plus = sum(1 for m in matches_list if m >= 4) / total * 100
    avg_match = np.mean(matches_list)
    dist = Counter(matches_list)

    return {
        'test_periods': total,
        'm3_plus': m3_plus,
        'm4_plus': m4_plus,
        'avg_match': float(avg_match),
        'match_distribution': dict(sorted(dist.items())),
        'matches': matches_list,
    }


def main():
    parser = argparse.ArgumentParser(description='ARIMA (1,0,0) 獨立驗證')
    parser.add_argument('--quick', action='store_true', help='50 期快速測試')
    args = parser.parse_args()

    test_periods = 50 if args.quick else 500

    print("=" * 70)
    print("🔬 ARIMA (1,0,0) 獨立驗證 - Claude 回測")
    print("=" * 70)
    print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"測試期數: {test_periods}")
    print(f"ARIMA Order: (1, 0, 0)")
    print(f"隨機種子: {SEED}")

    configs = [
        {'type': 'POWER_LOTTO', 'name': '威力彩', 'bets': 2, 'balls': 38},
        {'type': 'BIG_LOTTO', 'name': '大樂透', 'bets': 4, 'balls': 49},
    ]

    all_results = {}

    for cfg in configs:
        print(f"\n{'='*70}")
        print(f"📊 {cfg['name']} ({cfg['bets']}注, {test_periods}期)")
        print(f"{'='*70}")

        # 隨機基準
        baseline = random_baseline(cfg['bets'], cfg['balls'])
        print(f"  隨機基準 M3+ ({cfg['bets']}注): {baseline:.2f}%")

        # ARIMA 回測
        result = backtest_arima(
            cfg['type'], test_periods, cfg['bets'],
            order=(1, 0, 0),
            progress_interval=50 if not args.quick else 10
        )

        if result:
            edge = result['m3_plus'] - baseline
            result['baseline'] = baseline
            result['edge'] = edge
            all_results[cfg['name']] = result

            print(f"\n  📊 結果:")
            print(f"     M3+ 勝率: {result['m3_plus']:.2f}%")
            print(f"     M4+ 勝率: {result['m4_plus']:.2f}%")
            print(f"     平均命中: {result['avg_match']:.2f}")
            print(f"     Edge: {edge:+.2f}% {'✅' if edge > 1.0 else '⚠️' if edge > 0 else '❌'}")

            print(f"\n  命中分佈:")
            for match, count in sorted(result['match_distribution'].items()):
                pct = count / result['test_periods'] * 100
                bar = "█" * int(pct / 2)
                print(f"    {match}中: {count:4d} ({pct:5.1f}%) {bar}")

    # 綜合報告
    print("\n" + "=" * 70)
    print("📊 綜合驗證報告")
    print("=" * 70)

    print(f"\n{'彩種':<10} {'注數':<6} {'M3+':<10} {'基準':<10} {'Edge':<12} {'結論':<10}")
    print("-" * 60)

    for name, r in all_results.items():
        if r['edge'] > 1.0:
            verdict = "✅ 有效"
        elif r['edge'] > 0:
            verdict = "⚠️ 微弱"
        else:
            verdict = "❌ 無效"
        print(f"{name:<10} {r['test_periods']:<6} {r['m3_plus']:<10.2f} {r['baseline']:<10.2f} {r['edge']:+.2f}%      {verdict}")

    # 與 Gemini 聲稱對比
    print("\n" + "-" * 70)
    print("📊 vs Gemini 聲稱:")
    print(f"{'彩種':<10} {'Gemini聲稱':<15} {'Claude實測':<15} {'差異':<10}")
    print("-" * 50)

    gemini_claims = {
        '威力彩': {'edge': 0.29, 'periods': 118},
        '大樂透': {'edge': 0.84, 'periods': 118},
    }

    for name, claim in gemini_claims.items():
        if name in all_results:
            actual = all_results[name]['edge']
            diff = actual - claim['edge']
            print(f"{name:<10} +{claim['edge']:.2f}% (N={claim['periods']})  {actual:+.2f}% (N={test_periods})  {diff:+.2f}%")

    # 結論
    print("\n" + "=" * 70)
    print("📌 結論")
    print("=" * 70)

    for name, r in all_results.items():
        if r['edge'] > 1.0:
            print(f"  ✅ {name}: Edge {r['edge']:+.2f}%, 可納入候選")
        elif r['edge'] > 0:
            print(f"  ⚠️ {name}: Edge {r['edge']:+.2f}%, 微弱正向但不顯著")
        else:
            print(f"  ❌ {name}: Edge {r['edge']:+.2f}%, 無效")

    # 與現有方法對比
    print("\n📊 與現有驗證方法對比:")
    print(f"  {'方法':<30} {'Edge':<12} {'N':<8}")
    print("  " + "-" * 50)
    print(f"  {'Attention LSTM (威力彩)':<30} {'+3.68%':<12} {'500':<8}")
    print(f"  {'Fourier Rhythm (威力彩)':<30} {'+0.95%':<12} {'1000':<8}")
    print(f"  {'Zonal Pruning (大樂透)':<30} {'+3.60%':<12} {'1000':<8}")
    print(f"  {'Cluster Pivot (大樂透)':<30} {'+1.70%':<12} {'150':<8}")
    for name, r in all_results.items():
        print(f"  {f'ARIMA (1,0,0) ({name})':<30} {r['edge']:+.2f}%      {r['test_periods']:<8}")

    # 保存結果
    output_dir = os.path.join(project_root, 'tools', 'data')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'arima_500_verification.json')

    save_data = {
        'timestamp': datetime.now().isoformat(),
        'seed': SEED,
        'order': [1, 0, 0],
        'test_periods': test_periods,
        'results': {
            name: {
                'test_periods': r['test_periods'],
                'm3_plus': r['m3_plus'],
                'm4_plus': r['m4_plus'],
                'avg_match': r['avg_match'],
                'baseline': r['baseline'],
                'edge': r['edge'],
                'match_distribution': r['match_distribution'],
            }
            for name, r in all_results.items()
        },
        'gemini_claims': gemini_claims,
    }

    with open(output_path, 'w') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)

    print(f"\n結果已保存至: {output_path}")


if __name__ == '__main__':
    main()
