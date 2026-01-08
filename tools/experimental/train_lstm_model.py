#!/usr/bin/env python3
"""
訓練並回測 LSTM + Attention 模型
策略2: 時間序列深度學習
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lottery-api'))

import numpy as np
from database import DatabaseManager
from common import get_lottery_rules
from models.lstm_attention_predictor import LSTMAttentionPredictor

def rolling_backtest(predictor, draws, rules, test_periods=116):
    """
    滾動回測

    Args:
        predictor: 訓練好的預測器
        draws: 所有歷史數據 (新→舊)
        rules: 彩票規則
        test_periods: 測試期數

    Returns:
        回測結果
    """
    results = []
    win_count = 0
    total_matches = 0

    print(f"\n{'='*60}")
    print(f"開始回測 (測試期數: {test_periods})")
    print(f"{'='*60}")

    for i in range(test_periods):
        target = draws[i]
        target_numbers = set(target['numbers'])

        # 使用之後的數據作為歷史
        history = draws[i + 1:]

        if len(history) < 50:  # 需要足夠的歷史數據
            continue

        try:
            prediction = predictor.predict(history, rules)
            predicted_numbers = set(prediction['numbers'])
            matches = len(predicted_numbers & target_numbers)

            total_matches += matches
            if matches >= 3:
                win_count += 1
                status = "✓ 中獎"
            else:
                status = ""

            results.append({
                'draw': target['draw'],
                'predicted': sorted(predicted_numbers),
                'actual': sorted(target_numbers),
                'matches': matches,
                'matched_nums': sorted(predicted_numbers & target_numbers),
                'confidence': prediction['confidence']
            })

            if (i + 1) % 20 == 0:
                print(f"進度: {i+1}/{test_periods}, "
                      f"中獎率: {win_count/(i+1)*100:.2f}%, "
                      f"平均匹配: {total_matches/(i+1):.3f}")

        except Exception as e:
            print(f"預測錯誤 (期號 {target['draw']}): {e}")
            continue

    # 統計結果
    test_count = len(results)
    win_rate = win_count / test_count if test_count > 0 else 0
    avg_matches = total_matches / test_count if test_count > 0 else 0

    return {
        'test_count': test_count,
        'win_count': win_count,
        'win_rate': win_rate,
        'avg_matches': avg_matches,
        'details': results
    }


def main():
    print("="*80)
    print("🧠 策略2: LSTM + Attention 時間序列深度學習")
    print("="*80)

    # 載入數據
    db_path = os.path.join(os.path.dirname(__file__), 'lottery-api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')

    print(f"\n📊 數據概況:")
    print(f"   總期數: {len(draws)}")
    print(f"   最新期號: {draws[0]['draw']} ({draws[0]['date']})")

    # 篩選2025年數據作為測試集
    draws_2025 = [d for d in draws if d['date'].startswith('2025') or d['date'].startswith('114')]
    print(f"   2025年期數: {len(draws_2025)} (用於測試)")

    # 使用2025年之前的數據訓練
    train_start_idx = len(draws_2025)
    train_draws = draws[train_start_idx:]
    print(f"   訓練數據期數: {len(train_draws)}")

    # 初始化並訓練模型
    print(f"\n{'='*80}")
    print("🔧 開始訓練 LSTM + Attention 模型")
    print("{'='*80}")

    predictor = LSTMAttentionPredictor(
        num_range=49,
        seq_length=30,
        hidden_size=128,
        num_layers=2
    )

    history = predictor.train(
        draws=train_draws,
        epochs=100,
        batch_size=32,
        learning_rate=0.001,
        validation_split=0.2,
        early_stopping_patience=15,
        verbose=True
    )

    # 保存模型
    model_path = os.path.join(os.path.dirname(__file__), 'lottery-api', 'data', 'lstm_attention_model.pth')
    predictor.save(model_path)
    print(f"\n✅ 模型已保存至: {model_path}")

    # 回測2025年數據
    print(f"\n{'='*80}")
    print("📈 開始2025年回測驗證")
    print("{'='*80}")

    backtest_results = rolling_backtest(
        predictor=predictor,
        draws=draws,
        rules=rules,
        test_periods=len(draws_2025)
    )

    # 顯示結果
    print(f"\n{'='*80}")
    print("🏆 回測結果")
    print("{'='*80}")
    print(f"   測試期數: {backtest_results['test_count']}")
    print(f"   中獎次數: {backtest_results['win_count']}")
    print(f"   中獎率: {backtest_results['win_rate']*100:.2f}%")
    print(f"   平均匹配: {backtest_results['avg_matches']:.3f}")

    # 與基線比較
    baseline_win_rate = 4.31  # 區域平衡預測的中獎率
    improvement = (backtest_results['win_rate'] * 100 - baseline_win_rate) / baseline_win_rate * 100

    print(f"\n📊 與基線比較:")
    print(f"   基線 (區域平衡): {baseline_win_rate:.2f}%")
    print(f"   LSTM+Attention: {backtest_results['win_rate']*100:.2f}%")
    print(f"   提升幅度: {improvement:+.1f}%")

    # 顯示部分中獎案例
    print(f"\n{'='*80}")
    print("🎯 中獎案例")
    print("{'='*80}")
    win_cases = [r for r in backtest_results['details'] if r['matches'] >= 3]
    for case in win_cases[:10]:
        print(f"   期號 {case['draw']}: 命中 {case['matches']} 個 {case['matched_nums']}")

    return backtest_results


if __name__ == '__main__':
    main()
