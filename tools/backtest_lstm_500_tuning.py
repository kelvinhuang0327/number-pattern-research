#!/usr/bin/env python3
"""
Attention LSTM 500期標準回測
============================
使用標準 500 期進行超參數調優驗證
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

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules

def random_baseline(num_balls=49, pick_count=6, n_simulations=10000):
    """計算隨機基準"""
    match_counts = {i: 0 for i in range(7)}
    for _ in range(n_simulations):
        pred = set(np.random.choice(range(1, num_balls + 1), size=pick_count, replace=False))
        actual = set(np.random.choice(range(1, num_balls + 1), size=pick_count, replace=False))
        match = len(pred & actual)
        match_counts[match] += 1
    return sum(match_counts[i] for i in range(3, 7)) / n_simulations * 100

def backtest_lstm(history, test_periods, config, num_balls=49, pick_count=6):
    """執行 LSTM 回測"""
    from lottery_api.models.attention_lstm_torch import AttentionLSTMPredictor
    
    window_size = config.get('window_size', 5)
    hidden_size = config.get('hidden_size', 64)
    train_window = config.get('train_window', 60)
    dropout = config.get('dropout', 0.3)
    epochs = config.get('epochs', 30)
    
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
            num_balls=num_balls,
            window_size=window_size,
            hidden_size=hidden_size,
            dropout=dropout,
            bidirectional=False  # 已驗證 Bi-LSTM 無效
        )
        
        predictor.train(train_data, epochs=epochs, verbose=0)
        pred = predictor.predict(train_data, n_numbers=pick_count)
        
        if pred:
            match = len(set(pred) & actual_numbers)
            matches.append(match)
        
        # 進度顯示
        if (i + 1) % 50 == 0:
            print(f"    進度: {i+1}/{test_periods}")
    
    if not matches:
        return None
    
    m3_plus = sum(1 for m in matches if m >= 3) / len(matches) * 100
    avg_match = np.mean(matches)
    return {'m3_plus': m3_plus, 'avg_match': avg_match, 'total': len(matches)}

def run_grid_search(lottery_type='BIG_LOTTO', test_periods=500):
    """執行 Grid Search"""
    print("=" * 70)
    print(f"🔧 Attention LSTM 500期標準回測 - {lottery_type}")
    print("=" * 70)
    
    # 載入數據
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = list(reversed(db.get_all_draws(lottery_type=lottery_type)))
    rules = get_lottery_rules(lottery_type)
    
    num_balls = rules.get('maxNumber', 49)
    pick_count = rules.get('pickCount', 6)
    
    print(f"數據量: {len(history)} 期")
    print(f"測試期數: {test_periods}")
    print(f"號碼範圍: 1-{num_balls}, 選 {pick_count} 個")
    
    # 計算隨機基準
    baseline = random_baseline(num_balls=num_balls, pick_count=pick_count)
    print(f"隨機基準 (M3+): {baseline:.2f}%\n")
    
    # 參數配置
    configs = [
        {'window_size': 3, 'hidden_size': 32, 'train_window': 40, 'epochs': 25, 'dropout': 0.3},
        {'window_size': 5, 'hidden_size': 32, 'train_window': 50, 'epochs': 25, 'dropout': 0.3},
        {'window_size': 5, 'hidden_size': 64, 'train_window': 60, 'epochs': 30, 'dropout': 0.3},
        {'window_size': 5, 'hidden_size': 128, 'train_window': 60, 'epochs': 30, 'dropout': 0.3},
        {'window_size': 7, 'hidden_size': 64, 'train_window': 70, 'epochs': 30, 'dropout': 0.3},
        {'window_size': 10, 'hidden_size': 64, 'train_window': 80, 'epochs': 30, 'dropout': 0.3},
        {'window_size': 5, 'hidden_size': 64, 'train_window': 60, 'epochs': 30, 'dropout': 0.2},
        {'window_size': 5, 'hidden_size': 64, 'train_window': 60, 'epochs': 30, 'dropout': 0.4},
    ]
    
    results = []
    
    for i, cfg in enumerate(configs):
        print(f"\n📊 配置 {i+1}/{len(configs)}: {cfg}")
        
        result = backtest_lstm(
            history, 
            test_periods=test_periods,
            config=cfg,
            num_balls=num_balls,
            pick_count=pick_count
        )
        
        if result:
            edge = result['m3_plus'] - baseline
            results.append({
                **cfg,
                'm3_plus': result['m3_plus'],
                'avg_match': result['avg_match'],
                'edge': edge
            })
            indicator = "✅" if edge > 0 else "❌"
            print(f"   M3+: {result['m3_plus']:.2f}%, Edge: {edge:+.2f}% {indicator}")
        else:
            print("   ❌ 數據不足")
    
    # 排序結果
    results.sort(key=lambda x: x['edge'], reverse=True)
    
    print("\n" + "=" * 70)
    print("📊 結果排名")
    print("=" * 70)
    print(f"{'排名':<4} {'Win':<6} {'Hid':<6} {'Train':<6} {'Epoch':<6} {'Drop':<6} {'M3+':<8} {'Edge':<10}")
    print("-" * 70)
    
    for i, r in enumerate(results):
        indicator = "⭐" if r['edge'] > 0 else ""
        print(f"{i+1:<4} {r['window_size']:<6} {r['hidden_size']:<6} {r['train_window']:<6} "
              f"{r['epochs']:<6} {r['dropout']:<6.1f} {r['m3_plus']:<8.2f} {r['edge']:+.2f}% {indicator}")
    
    # 保存結果
    output_path = os.path.join(project_root, 'tools', 'data', f'lstm_tuning_results_{lottery_type.lower()}.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump({'baseline': baseline, 'results': results}, f, indent=2, ensure_ascii=False)
    print(f"\n結果已保存至: {output_path}")
    
    # 最佳配置
    if results and results[0]['edge'] > 0:
        best = results[0]
        print(f"\n🏆 最佳配置:")
        print(f"   Window Size: {best['window_size']}")
        print(f"   Hidden Size: {best['hidden_size']}")
        print(f"   Train Window: {best['train_window']}")
        print(f"   Epochs: {best['epochs']}")
        print(f"   Dropout: {best['dropout']}")
        print(f"   Edge: {best['edge']:+.2f}%")
    else:
        print("\n⚠️ 所有配置 Edge 皆為負或零")
    
    return results

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--type', type=str, default='BIG_LOTTO')
    parser.add_argument('--periods', type=int, default=500)
    args = parser.parse_args()
    
    run_grid_search(lottery_type=args.type, test_periods=args.periods)
