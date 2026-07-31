#!/usr/bin/env python3
"""
Attention LSTM 超參數調優
==========================
測試不同參數組合，找出最佳配置
"""
import os
import sys
import json
import numpy as np
import torch
from datetime import datetime
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

SEED = 42
np.random.seed(SEED)
torch.manual_seed(SEED)

def get_history():
    json_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_history.json')
    with open(json_path, 'r') as f:
        data = json.load(f)
    draws = data.get('data_by_type', {}).get('POWER_LOTTO', [])
    draws.sort(key=lambda x: x['draw'])
    return draws

def random_baseline(num_bets=1, n_simulations=5000):
    match_counts = {i: 0 for i in range(7)}
    for _ in range(n_simulations):
        for _ in range(num_bets):
            pred = set(np.random.choice(range(1, 39), size=6, replace=False))
            actual = set(np.random.choice(range(1, 39), size=6, replace=False))
            match = len(pred & actual)
            match_counts[match] += 1
    total = n_simulations * num_bets
    return sum(match_counts[i] for i in range(3, 7)) / total * 100

def quick_backtest(history, test_periods=20, train_window=50, window_size=5,
                   hidden_size=64, num_bets=1, epochs=30):
    """快速回測"""
    from lottery_api.models.attention_lstm_torch import AttentionLSTMPredictor

    if len(history) < train_window + test_periods:
        return None

    matches = []
    start_idx = len(history) - test_periods

    for i in range(test_periods):
        target_idx = start_idx + i
        target_draw = history[target_idx]
        actual_numbers = set(target_draw['numbers'])

        train_end = target_idx
        train_start = max(0, train_end - train_window)
        train_data = history[train_start:train_end]

        if len(train_data) < window_size + 5:
            continue

        predictor = AttentionLSTMPredictor(
            num_balls=38,
            window_size=window_size,
            hidden_size=hidden_size,
            dropout=0.3
        )

        predictor.train(train_data, epochs=epochs, verbose=0)

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
    return m3_plus

def main():
    print("=" * 70)
    print("🔧 Attention LSTM 超參數調優")
    print("=" * 70)

    history = get_history()
    print(f"數據量: {len(history)} 期")

    # 測試配置
    configs = [
        {'window_size': 3, 'hidden_size': 32, 'train_window': 40},
        {'window_size': 5, 'hidden_size': 32, 'train_window': 40},
        {'window_size': 5, 'hidden_size': 64, 'train_window': 50},
        {'window_size': 5, 'hidden_size': 128, 'train_window': 50},
        {'window_size': 7, 'hidden_size': 64, 'train_window': 60},
        {'window_size': 10, 'hidden_size': 64, 'train_window': 70},
    ]

    test_periods = 25
    num_bets = 2

    print(f"\n測試期數: {test_periods}, 注數: {num_bets}")
    print("-" * 70)

    # 計算基準
    baseline = random_baseline(num_bets=num_bets)
    print(f"隨機基準: {baseline:.2f}%\n")

    results = []
    for i, cfg in enumerate(configs):
        print(f"測試配置 {i+1}/{len(configs)}: {cfg}...", end=" ", flush=True)

        m3_plus = quick_backtest(
            history,
            test_periods=test_periods,
            train_window=cfg['train_window'],
            window_size=cfg['window_size'],
            hidden_size=cfg['hidden_size'],
            num_bets=num_bets,
            epochs=25
        )

        if m3_plus is not None:
            edge = m3_plus - baseline
            results.append({**cfg, 'm3_plus': m3_plus, 'edge': edge})
            indicator = "✅" if edge > 0 else "❌"
            print(f"M3+: {m3_plus:.1f}%, Edge: {edge:+.2f}% {indicator}")
        else:
            print("數據不足")

    # 排序結果
    results.sort(key=lambda x: x['edge'], reverse=True)

    print("\n" + "=" * 70)
    print("📊 結果排名")
    print("=" * 70)
    print(f"{'排名':<4} {'Window':<8} {'Hidden':<8} {'Train':<8} {'M3+':<8} {'Edge':<10}")
    print("-" * 70)

    for i, r in enumerate(results):
        indicator = "⭐" if r['edge'] > 0 else ""
        print(f"{i+1:<4} {r['window_size']:<8} {r['hidden_size']:<8} {r['train_window']:<8} {r['m3_plus']:<8.1f} {r['edge']:+.2f}% {indicator}")

    if results and results[0]['edge'] > 0:
        best = results[0]
        print(f"\n🏆 最佳配置:")
        print(f"   Window Size: {best['window_size']}")
        print(f"   Hidden Size: {best['hidden_size']}")
        print(f"   Train Window: {best['train_window']}")
        print(f"   Edge: {best['edge']:+.2f}%")

if __name__ == '__main__':
    main()
