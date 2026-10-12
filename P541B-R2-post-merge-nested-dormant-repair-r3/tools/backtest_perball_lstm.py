#!/usr/bin/env python3
"""
Per-Ball LSTM 回測工具
======================
回測 Per-Ball LSTM 模型在大樂透和威力彩上的表現

技術特點:
1. Per-Ball Position Encoding: 為每個球位建立獨立 LSTM 分支
2. Number Embedding: 用 Embedding 替代 One-Hot
3. Greedy Dedup Sampling: 確保預測號碼不重複
4. ReduceLROnPlateau: 動態調整學習率
5. Clipnorm: 防止梯度爆炸
"""
import os
import sys
import json
import argparse
from datetime import datetime
from collections import Counter

# 確保可以導入專案模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 抑制 TensorFlow 警告
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

from lottery_api.database import DatabaseManager


def load_history(lottery_type, db_path=None):
    """載入歷史數據"""
    if db_path is None:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'lottery_api', 'data', 'lottery_v2.db')
    
    db = DatabaseManager(db_path=db_path)
    res = db.get_draws(lottery_type, page_size=2000)
    history = res.get('draws', [])
    
    # 確保時間順序
    if history and history[0]['draw'] > history[-1]['draw']:
        history = history[::-1]
    
    return history


def run_backtest_perball_lstm(history, test_periods=100, train_window=200, 
                               window_size=5, num_balls=49, n_picks=6,
                               verbose=True):
    """
    執行 Per-Ball LSTM 回測
    
    Args:
        history: 歷史數據
        test_periods: 回測期數
        train_window: 訓練窗口
        window_size: LSTM 窗口
        num_balls: 號碼範圍
        n_picks: 每期選幾個號碼
        verbose: 是否顯示詳情
    
    Returns:
        dict: 回測結果
    """
    from lottery_api.models.perball_lstm import PerBallLSTMPredictor
    
    results = {
        'matches': [],
        'match_distribution': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0},
        'predictions': [],
        'total_periods': 0,
        'match_3plus': 0
    }
    
    min_required = train_window + window_size + 1
    if len(history) < min_required + test_periods:
        print(f"⚠️ 數據不足: 需要 {min_required + test_periods} 期，只有 {len(history)} 期")
        test_periods = len(history) - min_required
        if test_periods <= 0:
            return results
    
    if verbose:
        print(f"\n🔄 開始回測 Per-Ball LSTM")
        print(f"   測試期數: {test_periods}")
        print(f"   訓練窗口: {train_window}")
        print(f"   LSTM窗口: {window_size}")
        print(f"   號碼範圍: 1-{num_balls}")
        print("-" * 60)
    
    for i in range(test_periods):
        # 計算位置
        test_idx = len(history) - test_periods + i
        train_end = test_idx
        train_start = max(0, train_end - train_window)
        
        train_data = history[train_start:train_end]
        actual_draw = history[test_idx]
        actual_numbers = set(actual_draw['numbers'])
        
        try:
            # 訓練模型
            predictor = PerBallLSTMPredictor(
                num_balls=num_balls,
                n_picks=n_picks,
                window_size=window_size,
                embedding_dim=64,
                lstm_units=128,
                dropout_rate=0.3
            )
            
            predictor.train(train_data, epochs=40, verbose=0)
            
            # 預測
            predicted = predictor.predict(train_data, n_numbers=n_picks)
            
        except Exception as e:
            if verbose:
                print(f"   第 {i+1} 期發生錯誤: {e}")
            predicted = []
        
        # 計算命中
        match_count = len(set(predicted) & actual_numbers) if predicted else 0
        
        results['matches'].append(match_count)
        results['match_distribution'][match_count] += 1
        results['predictions'].append({
            'period': i + 1,
            'draw': actual_draw.get('draw', ''),
            'predicted': predicted,
            'actual': sorted(actual_numbers),
            'match': match_count
        })
        results['total_periods'] += 1
        
        if match_count >= 3:
            results['match_3plus'] += 1
        
        if verbose and (i + 1) % 10 == 0:
            avg_match = sum(results['matches']) / len(results['matches'])
            match3_rate = results['match_3plus'] / results['total_periods'] * 100
            print(f"   已完成 {i+1}/{test_periods} 期 | 平均命中: {avg_match:.2f} | 3+命中率: {match3_rate:.1f}%")
    
    # 計算統計
    results['avg_match'] = sum(results['matches']) / len(results['matches']) if results['matches'] else 0
    results['match_3plus_rate'] = results['match_3plus'] / results['total_periods'] * 100 if results['total_periods'] > 0 else 0
    
    # 計算隨機基線
    if num_balls == 49:  # 大樂透
        baseline_match3 = 2.17  # 理論值
    else:  # 威力彩 38
        baseline_match3 = 3.88  # 理論值
    
    results['baseline_match3_rate'] = baseline_match3
    results['edge'] = results['match_3plus_rate'] - baseline_match3
    
    return results


def run_comparison_backtest(history, test_periods=100, train_window=200,
                            num_balls=49, n_picks=6, verbose=True):
    """
    對比 Per-Ball LSTM 與 Attention LSTM
    """
    from lottery_api.models.perball_lstm import PerBallLSTMPredictor
    from lottery_api.models.attention_lstm import AttentionLSTMPredictor
    
    results = {
        'perball_lstm': {
            'matches': [],
            'match_3plus': 0
        },
        'attention_lstm': {
            'matches': [],
            'match_3plus': 0
        }
    }
    
    min_required = train_window + 10
    if len(history) < min_required + test_periods:
        test_periods = len(history) - min_required
        if test_periods <= 0:
            return results
    
    if verbose:
        print(f"\n🔄 開始對比回測")
        print(f"   測試期數: {test_periods}")
        print("-" * 60)
    
    for i in range(test_periods):
        test_idx = len(history) - test_periods + i
        train_end = test_idx
        train_start = max(0, train_end - train_window)
        
        train_data = history[train_start:train_end]
        actual_draw = history[test_idx]
        actual_numbers = set(actual_draw['numbers'])
        
        # Per-Ball LSTM
        try:
            pb_predictor = PerBallLSTMPredictor(
                num_balls=num_balls,
                n_picks=n_picks,
                window_size=5,
                embedding_dim=64,
                lstm_units=128
            )
            pb_predictor.train(train_data, epochs=30, verbose=0)
            pb_pred = pb_predictor.predict(train_data, n_numbers=n_picks)
            pb_match = len(set(pb_pred) & actual_numbers)
        except:
            pb_match = 0
        
        results['perball_lstm']['matches'].append(pb_match)
        if pb_match >= 3:
            results['perball_lstm']['match_3plus'] += 1
        
        # Attention LSTM
        try:
            attn_predictor = AttentionLSTMPredictor(
                num_balls=num_balls,
                window_size=5,
                lstm_units=64
            )
            attn_predictor.train(train_data, epochs=30, verbose=0)
            attn_pred = attn_predictor.predict(train_data, n_numbers=n_picks)
            attn_match = len(set(attn_pred) & actual_numbers)
        except:
            attn_match = 0
        
        results['attention_lstm']['matches'].append(attn_match)
        if attn_match >= 3:
            results['attention_lstm']['match_3plus'] += 1
        
        if verbose and (i + 1) % 10 == 0:
            pb_avg = sum(results['perball_lstm']['matches']) / len(results['perball_lstm']['matches'])
            attn_avg = sum(results['attention_lstm']['matches']) / len(results['attention_lstm']['matches'])
            print(f"   {i+1}/{test_periods} | Per-Ball: {pb_avg:.2f} | Attention: {attn_avg:.2f}")
    
    # 計算統計
    for model in ['perball_lstm', 'attention_lstm']:
        m = results[model]
        m['avg_match'] = sum(m['matches']) / len(m['matches']) if m['matches'] else 0
        m['match_3plus_rate'] = m['match_3plus'] / test_periods * 100 if test_periods > 0 else 0
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Per-Ball LSTM 回測工具')
    parser.add_argument('--lottery', type=str, default='big_lotto',
                       choices=['big_lotto', 'power_lotto', 'both'],
                       help='彩種類型')
    parser.add_argument('--periods', type=int, default=100,
                       help='回測期數')
    parser.add_argument('--train-window', type=int, default=200,
                       help='訓練窗口')
    parser.add_argument('--compare', action='store_true',
                       help='與 Attention LSTM 對比')
    parser.add_argument('--output', type=str, default=None,
                       help='結果輸出路徑')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("Per-Ball LSTM 回測工具")
    print("=" * 70)
    print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"回測期數: {args.periods}")
    print(f"訓練窗口: {args.train_window}")
    
    all_results = {}
    
    lotteries = []
    if args.lottery == 'both':
        lotteries = ['big_lotto', 'power_lotto']
    else:
        lotteries = [args.lottery]
    
    for lottery in lotteries:
        lottery_type = 'BIG_LOTTO' if lottery == 'big_lotto' else 'POWER_LOTTO'
        num_balls = 49 if lottery == 'big_lotto' else 38
        name = '大樂透' if lottery == 'big_lotto' else '威力彩'
        
        print(f"\n{'='*70}")
        print(f"🎰 {name} 回測")
        print(f"{'='*70}")
        
        history = load_history(lottery_type)
        print(f"載入 {len(history)} 期歷史數據")
        
        if args.compare:
            results = run_comparison_backtest(
                history,
                test_periods=args.periods,
                train_window=args.train_window,
                num_balls=num_balls,
                n_picks=6
            )
            
            print(f"\n📊 {name} 對比結果:")
            print("-" * 50)
            print(f"{'模型':<20} {'平均命中':<12} {'3+命中率'}")
            print("-" * 50)
            print(f"{'Per-Ball LSTM':<20} {results['perball_lstm']['avg_match']:.2f}/6       {results['perball_lstm']['match_3plus_rate']:.2f}%")
            print(f"{'Attention LSTM':<20} {results['attention_lstm']['avg_match']:.2f}/6       {results['attention_lstm']['match_3plus_rate']:.2f}%")
            
            all_results[lottery] = results
        else:
            results = run_backtest_perball_lstm(
                history,
                test_periods=args.periods,
                train_window=args.train_window,
                num_balls=num_balls,
                n_picks=6
            )
            
            print(f"\n📊 {name} 回測結果:")
            print("-" * 50)
            print(f"總測試期數: {results['total_periods']}")
            print(f"平均命中數: {results['avg_match']:.2f}/6")
            print(f"3+命中期數: {results['match_3plus']}")
            print(f"3+命中率:   {results['match_3plus_rate']:.2f}%")
            print(f"隨機基線:   {results['baseline_match3_rate']:.2f}%")
            print(f"優勢邊際:   {results['edge']:+.2f}%")
            print(f"\n命中分佈:")
            for n in range(7):
                count = results['match_distribution'].get(n, 0)
                pct = count / results['total_periods'] * 100 if results['total_periods'] > 0 else 0
                bar = '█' * int(pct / 2)
                print(f"  {n}個: {count:3d} ({pct:5.1f}%) {bar}")
            
            all_results[lottery] = results
    
    # 保存結果
    output_path = args.output
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), 'data', 'perball_lstm_backtest.json')
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 移除不可序列化的內容
    save_results = {}
    for lottery, res in all_results.items():
        save_results[lottery] = {
            'avg_match': res.get('avg_match', 0),
            'match_3plus_rate': res.get('match_3plus_rate', 0),
            'baseline_match3_rate': res.get('baseline_match3_rate', 0),
            'edge': res.get('edge', 0),
            'total_periods': res.get('total_periods', 0),
            'match_distribution': res.get('match_distribution', {}),
            'timestamp': datetime.now().isoformat()
        }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(save_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 結果已保存至: {output_path}")
    print("=" * 70)


if __name__ == '__main__':
    main()
