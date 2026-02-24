#!/usr/bin/env python3
"""
Attention LSTM 短中長期回測
============================
- 短期: 50 期 (快速驗證)
- 中期: 150 期 (標準驗證)
- 長期: 500 期 (穩定性驗證)

執行方式:
  python3 tools/backtest_attention_lstm_comprehensive.py
  python3 tools/backtest_attention_lstm_comprehensive.py --quick  # 只跑短期
"""
import os
import sys
import json
import sqlite3
import argparse
import numpy as np
import torch
from datetime import datetime
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

# 固定種子
SEED = 42
np.random.seed(SEED)
torch.manual_seed(SEED)


def get_history_from_db(lottery_type='POWER_LOTTO', limit=None):
    """從數據庫讀取歷史數據"""
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    if not os.path.exists(db_path):
        db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
        SELECT draw, date, numbers, special FROM draws
        WHERE lottery_type = ?
        ORDER BY date ASC, draw ASC
    """
    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query, (lottery_type,))
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


def random_baseline(num_bets=2, num_balls=38, n_simulations=10000):
    """計算隨機基準"""
    np.random.seed(42)
    match_counts = {i: 0 for i in range(7)}

    for _ in range(n_simulations):
        for _ in range(num_bets):
            pred = set(np.random.choice(range(1, num_balls + 1), size=6, replace=False))
            actual = set(np.random.choice(range(1, num_balls + 1), size=6, replace=False))
            match = len(pred & actual)
            match_counts[match] += 1

    total = n_simulations * num_bets
    m3_plus = sum(match_counts[i] for i in range(3, 7)) / total * 100
    return m3_plus


def backtest_attention_lstm(history, test_periods, train_window=70,
                            window_size=10, hidden_size=64, num_bets=2,
                            verbose=True, progress_interval=10):
    """
    Attention LSTM 回測

    Args:
        history: 完整歷史數據
        test_periods: 測試期數
        train_window: 訓練窗口
        window_size: LSTM 輸入窗口
        hidden_size: LSTM 隱藏層大小
        num_bets: 每期注數
        verbose: 顯示進度
        progress_interval: 進度顯示間隔
    """
    from lottery_api.models.attention_lstm_torch import AttentionLSTMPredictor

    min_required = train_window + test_periods + window_size
    if len(history) < min_required:
        print(f"數據不足: 需要 {min_required} 期, 只有 {len(history)} 期")
        return None

    results = {
        'test_periods': test_periods,
        'train_window': train_window,
        'window_size': window_size,
        'num_bets': num_bets,
        'matches': [],
        'match_distribution': {i: 0 for i in range(7)},
    }

    start_idx = len(history) - test_periods

    for i in range(test_periods):
        target_idx = start_idx + i
        target_draw = history[target_idx]
        actual_numbers = set(target_draw['numbers'])

        # 訓練數據: 目標期之前
        train_end = target_idx
        train_start = max(0, train_end - train_window)
        train_data = history[train_start:train_end]

        if len(train_data) < window_size + 5:
            continue

        # 訓練模型
        predictor = AttentionLSTMPredictor(
            num_balls=38,
            window_size=window_size,
            hidden_size=hidden_size,
            dropout=0.3
        )

        predictor.train(train_data, epochs=25, verbose=0)

        # 預測多注
        best_match = 0
        for bet_idx in range(num_bets):
            if bet_idx == 0:
                pred = predictor.predict(train_data, n_numbers=6, temperature=1.0)
            else:
                samples = predictor.predict_with_sampling(
                    train_data, n_numbers=6, temperature=0.8, n_samples=1
                )
                pred = samples[0] if samples else []

            if pred:
                match = len(set(pred) & actual_numbers)
                best_match = max(best_match, match)

        results['matches'].append(best_match)
        results['match_distribution'][best_match] += 1

        if verbose and (i + 1) % progress_interval == 0:
            current_m3 = sum(1 for m in results['matches'] if m >= 3) / len(results['matches']) * 100
            print(f"    進度: {i+1}/{test_periods} | M3+: {current_m3:.1f}%")

    # 計算統計
    total = len(results['matches'])
    if total > 0:
        results['m3_plus'] = sum(1 for m in results['matches'] if m >= 3) / total * 100
        results['m4_plus'] = sum(1 for m in results['matches'] if m >= 4) / total * 100
        results['avg_match'] = np.mean(results['matches'])
    else:
        results['m3_plus'] = 0
        results['m4_plus'] = 0
        results['avg_match'] = 0

    return results


def main():
    parser = argparse.ArgumentParser(description='Attention LSTM 短中長期回測')
    parser.add_argument('--quick', action='store_true', help='只跑短期測試')
    parser.add_argument('--bets', type=int, default=2, help='每期注數')
    args = parser.parse_args()

    print("=" * 70)
    print("🧠 Attention LSTM 短中長期回測")
    print("=" * 70)
    print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"每期注數: {args.bets}")
    print(f"隨機種子: {SEED}")
    print(f"Device: {'cuda' if torch.cuda.is_available() else 'cpu'}")

    # 載入數據
    print("\n📊 載入數據...")
    history = get_history_from_db('POWER_LOTTO')
    print(f"共 {len(history)} 期歷史數據")
    print(f"期號範圍: {history[0]['draw']} ~ {history[-1]['draw']}")

    # 計算隨機基準
    print("\n📈 計算隨機基準...")
    baseline = random_baseline(num_bets=args.bets)
    print(f"隨機基準 (M3+, {args.bets}注): {baseline:.2f}%")

    # 定義測試配置
    if args.quick:
        test_configs = [
            {'name': '短期', 'periods': 50, 'progress': 10},
        ]
    else:
        test_configs = [
            {'name': '短期', 'periods': 50, 'progress': 10},
            {'name': '中期', 'periods': 150, 'progress': 25},
            {'name': '長期', 'periods': 500, 'progress': 50},
        ]

    # 最佳參數配置
    best_config = {
        'train_window': 70,
        'window_size': 10,
        'hidden_size': 64
    }

    all_results = []

    for cfg in test_configs:
        print(f"\n{'='*70}")
        print(f"🔄 {cfg['name']}回測 ({cfg['periods']} 期)")
        print(f"{'='*70}")
        print(f"配置: Window={best_config['window_size']}, Hidden={best_config['hidden_size']}, Train={best_config['train_window']}")

        result = backtest_attention_lstm(
            history,
            test_periods=cfg['periods'],
            train_window=best_config['train_window'],
            window_size=best_config['window_size'],
            hidden_size=best_config['hidden_size'],
            num_bets=args.bets,
            verbose=True,
            progress_interval=cfg['progress']
        )

        if result:
            edge = result['m3_plus'] - baseline
            result['name'] = cfg['name']
            result['edge'] = edge
            result['baseline'] = baseline
            all_results.append(result)

            print(f"\n  📊 {cfg['name']}結果:")
            print(f"     M3+ 勝率: {result['m3_plus']:.2f}%")
            print(f"     M4+ 勝率: {result['m4_plus']:.2f}%")
            print(f"     平均命中: {result['avg_match']:.2f}")
            print(f"     Edge: {edge:+.2f}% {'✅' if edge > 0 else '❌'}")

    # 總結報告
    print("\n" + "=" * 70)
    print("📊 綜合報告")
    print("=" * 70)

    print(f"\n{'測試':<8} {'期數':<8} {'M3+':<10} {'M4+':<10} {'平均命中':<10} {'Edge':<12} {'結果':<6}")
    print("-" * 70)

    for r in all_results:
        indicator = "✅" if r['edge'] > 0 else "❌"
        print(f"{r['name']:<8} {r['test_periods']:<8} {r['m3_plus']:<10.2f} {r['m4_plus']:<10.2f} {r['avg_match']:<10.2f} {r['edge']:+.2f}%      {indicator}")

    print(f"\n隨機基準: {baseline:.2f}%")

    # 命中分佈 (長期)
    if len(all_results) > 0:
        longest = max(all_results, key=lambda x: x['test_periods'])
        print(f"\n📊 {longest['name']}命中分佈 (N={longest['test_periods']}):")
        for match, count in sorted(longest['match_distribution'].items()):
            pct = count / longest['test_periods'] * 100
            bar = "█" * int(pct / 2)
            print(f"  {match} 中: {count:4d} ({pct:5.1f}%) {bar}")

    # Edge 趨勢分析
    print("\n📈 Edge 趨勢分析:")
    for r in all_results:
        indicator = "📈" if r['edge'] > 0 else "📉"
        stability = "穩定" if abs(r['edge']) < 2 else ("波動" if r['edge'] > 0 else "不佳")
        print(f"  {r['name']} ({r['test_periods']}期): {r['edge']:+.2f}% {indicator} [{stability}]")

    # 與其他方法對比
    print("\n📊 與現有驗證方法對比:")
    print(f"  {'方法':<25} {'驗證期數':<12} {'Edge':<12}")
    print("  " + "-" * 50)
    print(f"  {'Fourier Rhythm':<25} {'1000期':<12} {'+0.95%':<12}")
    print(f"  {'冷號互補':<25} {'200期':<12} {'+0.45%':<12}")
    for r in all_results:
        periods_str = f"{r['test_periods']}期"
        print(f"  {'Attention LSTM':<25} {periods_str:<12} {r['edge']:+.2f}%")

    # 結論
    print("\n" + "=" * 70)
    print("📌 結論")
    print("=" * 70)

    if all_results:
        # 檢查長期是否穩定
        long_term = [r for r in all_results if r['test_periods'] >= 100]
        short_term = [r for r in all_results if r['test_periods'] < 100]

        if long_term:
            lt_avg_edge = np.mean([r['edge'] for r in long_term])
            if lt_avg_edge > 1.0:
                print("✅ 長期測試顯示顯著正 Edge")
                print(f"   長期平均 Edge: {lt_avg_edge:+.2f}%")
                print("   建議: 可納入生產系統候選")
            elif lt_avg_edge > 0:
                print("⚠️ 長期測試顯示微弱正 Edge")
                print(f"   長期平均 Edge: {lt_avg_edge:+.2f}%")
                print("   建議: 與其他方法組合使用")
            else:
                print("❌ 長期測試 Edge 為負或接近零")
                print(f"   長期平均 Edge: {lt_avg_edge:+.2f}%")
                print("   建議: 需要改進模型或調整參數")
        else:
            st_avg_edge = np.mean([r['edge'] for r in short_term]) if short_term else 0
            print(f"⚠️ 僅完成短期測試 (Edge: {st_avg_edge:+.2f}%)")
            print("   建議: 執行 --full 進行完整測試")

    # 保存結果
    output_dir = os.path.join(project_root, 'tools', 'data')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'attention_lstm_comprehensive_backtest.json')

    save_data = {
        'timestamp': datetime.now().isoformat(),
        'seed': SEED,
        'num_bets': args.bets,
        'baseline': baseline,
        'config': best_config,
        'results': [{
            'name': r['name'],
            'test_periods': r['test_periods'],
            'm3_plus': r['m3_plus'],
            'm4_plus': r['m4_plus'],
            'avg_match': r['avg_match'],
            'edge': r['edge'],
            'match_distribution': r['match_distribution']
        } for r in all_results]
    }

    with open(output_path, 'w') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)

    print(f"\n結果已保存至: {output_path}")


if __name__ == '__main__':
    main()
