#!/usr/bin/env python3
"""
Attention LSTM 最佳配置驗證
============================
使用最佳參數進行完整驗證
"""
import os
import sys
import json
import numpy as np
import torch
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

# 不同種子測試以排除運氣因素
SEEDS = [42, 123, 456, 789, 1024]

def get_history():
    json_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_history.json')
    with open(json_path, 'r') as f:
        data = json.load(f)
    draws = data.get('data_by_type', {}).get('POWER_LOTTO', [])
    draws.sort(key=lambda x: x['draw'])
    return draws

def random_baseline(num_bets=2, n_simulations=10000):
    np.random.seed(42)
    match_counts = {i: 0 for i in range(7)}
    for _ in range(n_simulations):
        for _ in range(num_bets):
            pred = set(np.random.choice(range(1, 39), size=6, replace=False))
            actual = set(np.random.choice(range(1, 39), size=6, replace=False))
            match = len(pred & actual)
            match_counts[match] += 1
    total = n_simulations * num_bets
    return sum(match_counts[i] for i in range(3, 7)) / total * 100

def backtest_with_seed(history, seed, test_periods=30, config=None):
    """使用特定種子進行回測"""
    from lottery_api.models.attention_lstm_torch import AttentionLSTMPredictor

    np.random.seed(seed)
    torch.manual_seed(seed)

    if config is None:
        config = {'window_size': 10, 'hidden_size': 64, 'train_window': 70}

    num_bets = 2
    matches = []

    start_idx = len(history) - test_periods

    for i in range(test_periods):
        target_idx = start_idx + i
        if target_idx >= len(history):
            break

        target_draw = history[target_idx]
        actual_numbers = set(target_draw['numbers'])

        train_end = target_idx
        train_start = max(0, train_end - config['train_window'])
        train_data = history[train_start:train_end]

        if len(train_data) < config['window_size'] + 5:
            continue

        predictor = AttentionLSTMPredictor(
            num_balls=38,
            window_size=config['window_size'],
            hidden_size=config['hidden_size'],
            dropout=0.3
        )

        predictor.train(train_data, epochs=30, verbose=0)

        best_match = 0
        for bet_idx in range(num_bets):
            if bet_idx == 0:
                pred = predictor.predict(train_data, n_numbers=6, temperature=1.0)
            else:
                samples = predictor.predict_with_sampling(train_data, n_numbers=6, temperature=0.8, n_samples=1)
                pred = samples[0] if samples else []

            if pred:
                match = len(set(pred) & actual_numbers)
                best_match = max(best_match, match)

        matches.append(best_match)

    m3_plus = sum(1 for m in matches if m >= 3) / len(matches) * 100 if matches else 0
    avg_match = np.mean(matches) if matches else 0

    return {
        'seed': seed,
        'm3_plus': m3_plus,
        'avg_match': avg_match,
        'test_periods': len(matches),
        'match_distribution': Counter(matches)
    }

def main():
    print("=" * 70)
    print("🔬 Attention LSTM 最佳配置驗證 (多種子)")
    print("=" * 70)

    history = get_history()
    print(f"數據量: {len(history)} 期")

    # 最佳配置
    best_config = {'window_size': 10, 'hidden_size': 64, 'train_window': 70}
    print(f"配置: {best_config}")

    # 計算可用測試期數
    max_test_periods = len(history) - best_config['train_window'] - best_config['window_size']
    test_periods = min(30, max_test_periods)
    print(f"測試期數: {test_periods}")

    # 隨機基準
    baseline = random_baseline(num_bets=2)
    print(f"隨機基準: {baseline:.2f}%")

    print("\n" + "-" * 70)
    print("執行多種子測試以排除運氣因素...")
    print("-" * 70)

    all_results = []
    for seed in SEEDS:
        print(f"  Seed {seed}...", end=" ", flush=True)
        result = backtest_with_seed(history, seed, test_periods, best_config)
        all_results.append(result)
        edge = result['m3_plus'] - baseline
        indicator = "✅" if edge > 0 else "❌"
        print(f"M3+: {result['m3_plus']:.1f}%, Edge: {edge:+.2f}% {indicator}")

    # 統計分析
    m3_values = [r['m3_plus'] for r in all_results]
    mean_m3 = np.mean(m3_values)
    std_m3 = np.std(m3_values)
    mean_edge = mean_m3 - baseline

    print("\n" + "=" * 70)
    print("📊 統計分析")
    print("=" * 70)
    print(f"M3+ 平均: {mean_m3:.2f}% ± {std_m3:.2f}%")
    print(f"Edge 平均: {mean_edge:+.2f}%")
    print(f"隨機基準: {baseline:.2f}%")

    # 置信區間
    ci_lower = mean_m3 - 1.96 * std_m3 / np.sqrt(len(SEEDS))
    ci_upper = mean_m3 + 1.96 * std_m3 / np.sqrt(len(SEEDS))
    print(f"95% 置信區間: [{ci_lower:.2f}%, {ci_upper:.2f}%]")

    # 結論
    print("\n" + "=" * 70)
    print("📌 結論")
    print("=" * 70)

    if mean_edge > 2.0 and ci_lower > baseline:
        print("✅ 模型顯示顯著正 Edge (置信區間不包含隨機基準)")
        print("   建議: 納入候選方法，與現有策略對比")
    elif mean_edge > 0:
        print("⚠️ 模型顯示正 Edge，但需要更多數據驗證")
        print("   建議: 等待更多歷史數據後再次驗證")
    else:
        print("❌ 模型未顯示穩定正 Edge")
        print("   建議: 需要改進架構或參數")

    # 與現有方法對比
    print("\n📊 與現有驗證方法對比:")
    print(f"  Fourier Rhythm (1000期): +0.95% Edge")
    print(f"  冷號互補 (200期):        +0.45% Edge")
    print(f"  Attention LSTM ({test_periods}期): {mean_edge:+.2f}% Edge ± {std_m3:.2f}%")

    # 警告
    print("\n⚠️ 重要提醒:")
    print(f"  - 測試樣本僅 {test_periods} 期，結果可能不穩定")
    print(f"  - 高 Edge 可能是小樣本波動，需謹慎解讀")
    print(f"  - 建議累積至少 100 期再做最終判斷")

if __name__ == '__main__':
    main()
