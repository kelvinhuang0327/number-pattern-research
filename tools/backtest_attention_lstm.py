#!/usr/bin/env python3
"""
Attention LSTM 回測驗證腳本
============================
驗證 Attention LSTM 模型的預測效果

執行方式:
  python3 tools/backtest_attention_lstm.py --n 50    # 快速測試
  python3 tools/backtest_attention_lstm.py --n 150   # 標準測試
"""
import os
import sys
import json
import argparse
import numpy as np
from datetime import datetime
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

# 設置隨機種子
SEED = 42
np.random.seed(SEED)

def get_history_from_json(lottery_type='POWER_LOTTO'):
    """從 JSON 檔案讀取歷史數據"""
    json_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_history.json')
    with open(json_path, 'r') as f:
        data = json.load(f)

    draws = data.get('data_by_type', {}).get(lottery_type, [])
    draws.sort(key=lambda x: x['draw'])
    return draws

def calculate_match(predicted, actual):
    """計算命中數"""
    return len(set(predicted) & set(actual))

def random_baseline(num_bets=1, num_balls=38, numbers_per_bet=6, n_simulations=1000):
    """計算隨機基準 (蒙特卡羅模擬)"""
    match_counts = {i: 0 for i in range(7)}

    for _ in range(n_simulations):
        for _ in range(num_bets):
            pred = set(np.random.choice(range(1, num_balls + 1), size=numbers_per_bet, replace=False))
            actual = set(np.random.choice(range(1, num_balls + 1), size=numbers_per_bet, replace=False))
            match = len(pred & actual)
            match_counts[match] += 1

    total = n_simulations * num_bets
    match3_plus = sum(match_counts[i] for i in range(3, 7)) / total * 100

    return match3_plus

def backtest_attention_lstm(history, test_periods=50, train_window=200,
                            window_size=5, num_bets=1, verbose=True):
    """
    Attention LSTM 回測

    Args:
        history: 所有歷史數據
        test_periods: 測試期數
        train_window: 訓練窗口
        window_size: LSTM 輸入窗口
        num_bets: 每期預測注數
        verbose: 顯示詳細資訊

    Returns:
        results: 回測結果
    """
    # 延遲導入 (避免 TF 載入時間影響其他操作)
    from lottery_api.models.attention_lstm import AttentionLSTMPredictor

    if len(history) < train_window + test_periods:
        print(f"數據不足: 需要 {train_window + test_periods} 期, 只有 {len(history)} 期")
        return None

    results = {
        'method': 'Attention LSTM',
        'test_periods': test_periods,
        'train_window': train_window,
        'window_size': window_size,
        'num_bets': num_bets,
        'matches': [],
        'match_distribution': {i: 0 for i in range(7)},
        'predictions': []
    }

    start_idx = len(history) - test_periods

    for i in range(test_periods):
        target_idx = start_idx + i
        target_draw = history[target_idx]
        actual_numbers = set(target_draw['numbers'])

        # 訓練數據: 目標期之前的數據
        train_end = target_idx
        train_start = max(0, train_end - train_window)
        train_data = history[train_start:train_end]

        if len(train_data) < window_size + 10:
            continue

        # 訓練新模型 (每期重新訓練，確保無數據洩漏)
        predictor = AttentionLSTMPredictor(
            num_balls=38,
            window_size=window_size,
            lstm_units=64,
            dropout_rate=0.3
        )

        predictor.train(train_data, epochs=30, verbose=0)

        # 預測
        best_match = 0
        all_predictions = []

        for bet_idx in range(num_bets):
            if bet_idx == 0:
                # 第一注用 argmax
                pred_numbers = predictor.predict(train_data, n_numbers=6, temperature=1.0)
            else:
                # 其他注用 temperature sampling
                samples = predictor.predict_with_sampling(
                    train_data, n_numbers=6, temperature=0.8, n_samples=1
                )
                pred_numbers = samples[0] if samples else []

            if pred_numbers:
                match = calculate_match(pred_numbers, actual_numbers)
                best_match = max(best_match, match)
                all_predictions.append({
                    'bet': bet_idx + 1,
                    'numbers': pred_numbers,
                    'match': match
                })

        results['matches'].append(best_match)
        results['match_distribution'][best_match] += 1
        results['predictions'].append({
            'draw': target_draw['draw'],
            'actual': sorted(actual_numbers),
            'predictions': all_predictions,
            'best_match': best_match
        })

        if verbose and (i + 1) % 10 == 0:
            current_m3 = sum(1 for m in results['matches'] if m >= 3) / len(results['matches']) * 100
            print(f"  進度: {i+1}/{test_periods} | M3+: {current_m3:.1f}%")

    # 計算統計
    total = len(results['matches'])
    results['match3_plus'] = sum(1 for m in results['matches'] if m >= 3) / total * 100 if total > 0 else 0
    results['match4_plus'] = sum(1 for m in results['matches'] if m >= 4) / total * 100 if total > 0 else 0
    results['avg_match'] = np.mean(results['matches']) if results['matches'] else 0

    return results

def main():
    parser = argparse.ArgumentParser(description='Attention LSTM 回測')
    parser.add_argument('--n', type=int, default=50, help='測試期數')
    parser.add_argument('--bets', type=int, default=1, help='每期注數')
    parser.add_argument('--window', type=int, default=200, help='訓練窗口')
    parser.add_argument('--lstm-window', type=int, default=5, help='LSTM 輸入窗口')
    parser.add_argument('--lottery', type=str, default='POWER_LOTTO', help='彩種')
    parser.add_argument('-v', '--verbose', action='store_true', help='顯示詳細資訊')
    args = parser.parse_args()

    print("=" * 70)
    print("🧠 Attention LSTM 回測驗證")
    print("=" * 70)
    print(f"彩種: {args.lottery}")
    print(f"測試期數: {args.n}")
    print(f"每期注數: {args.bets}")
    print(f"訓練窗口: {args.window}")
    print(f"LSTM 窗口: {args.lstm_window}")
    print(f"隨機種子: {SEED}")
    print("-" * 70)

    # 載入數據
    print("\n📊 載入數據...")
    history = get_history_from_json(args.lottery)
    print(f"共 {len(history)} 期歷史數據")

    if len(history) < args.window + args.n:
        print(f"❌ 數據不足! 需要至少 {args.window + args.n} 期")
        return

    # 計算隨機基準
    print("\n📈 計算隨機基準...")
    random_m3 = random_baseline(num_bets=args.bets, num_balls=38, n_simulations=10000)
    print(f"隨機基準 (M3+): {random_m3:.2f}%")

    # 執行回測
    print("\n🔄 執行 Attention LSTM 回測...")
    print("   (每期重新訓練模型，確保無數據洩漏)")

    results = backtest_attention_lstm(
        history,
        test_periods=args.n,
        train_window=args.window,
        window_size=args.lstm_window,
        num_bets=args.bets,
        verbose=True
    )

    if results is None:
        print("❌ 回測失敗")
        return

    # 輸出結果
    print("\n" + "=" * 70)
    print("📊 回測結果")
    print("=" * 70)

    print(f"\n命中分佈:")
    for match, count in sorted(results['match_distribution'].items()):
        pct = count / results['test_periods'] * 100
        bar = "█" * int(pct / 2)
        print(f"  {match} 中: {count:3d} ({pct:5.1f}%) {bar}")

    print(f"\n關鍵指標:")
    print(f"  M3+ 勝率: {results['match3_plus']:.2f}%")
    print(f"  M4+ 勝率: {results['match4_plus']:.2f}%")
    print(f"  平均命中: {results['avg_match']:.2f}")

    # 計算 Edge
    edge = results['match3_plus'] - random_m3
    edge_indicator = "✅" if edge > 0 else "❌"

    print(f"\n📈 Edge 分析:")
    print(f"  Attention LSTM: {results['match3_plus']:.2f}%")
    print(f"  隨機基準:       {random_m3:.2f}%")
    print(f"  Edge:           {edge:+.2f}% {edge_indicator}")

    # 結論
    print("\n" + "=" * 70)
    print("📌 結論")
    print("=" * 70)

    if edge > 1.0:
        print("✅ Attention LSTM 顯示顯著正 Edge，值得進一步驗證")
        recommendation = "建議進行 150 期長期驗證"
    elif edge > 0:
        print("⚠️ Attention LSTM 顯示微弱正 Edge，需要更多樣本確認")
        recommendation = "建議擴大樣本至 150 期"
    else:
        print("❌ Attention LSTM 未顯示正 Edge，可能需要調整參數或架構")
        recommendation = "建議調整超參數或嘗試其他架構"

    print(f"\n建議: {recommendation}")

    # 顯示部分預測詳情
    if args.verbose and results['predictions']:
        print("\n" + "-" * 70)
        print("最近 5 期預測詳情:")
        for pred in results['predictions'][-5:]:
            print(f"  期號 {pred['draw']}: 實際 {pred['actual']}")
            for p in pred['predictions']:
                match_indicator = "⭐" * p['match'] if p['match'] > 0 else "❌"
                print(f"    注{p['bet']}: {p['numbers']} -> 命中 {p['match']}/6 {match_indicator}")

    # 保存結果
    output_path = os.path.join(project_root, 'tools', 'data', 'attention_lstm_backtest.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    save_results = {
        'timestamp': datetime.now().isoformat(),
        'config': {
            'lottery': args.lottery,
            'test_periods': args.n,
            'num_bets': args.bets,
            'train_window': args.window,
            'lstm_window': args.lstm_window,
            'seed': SEED
        },
        'results': {
            'match3_plus': results['match3_plus'],
            'match4_plus': results['match4_plus'],
            'avg_match': results['avg_match'],
            'match_distribution': results['match_distribution'],
            'random_baseline': random_m3,
            'edge': edge
        }
    }

    with open(output_path, 'w') as f:
        json.dump(save_results, f, indent=2, ensure_ascii=False)

    print(f"\n結果已保存至: {output_path}")

if __name__ == '__main__':
    main()
