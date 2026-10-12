#!/usr/bin/env python3
"""
ARIMA 與 Ensemble 多維度回測腳本
==============================
評估短、中、長期下的預測表現。
- 短期: 20 期
- 中期: 50 期
- 長期: 118 期
"""
import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime
from collections import Counter

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.unified_predictor import UnifiedPredictionEngine
from lottery_api.models.ensemble_stacking import EnsembleStackingPredictor

import argparse

def random_baseline(num_bets=1, num_balls=49, numbers_per_bet=6, n_simulations=10000):
    """計算隨機基準"""
    match_counts = {i: 0 for i in range(7)}
    for _ in range(n_simulations):
        pred = set(np.random.choice(range(1, num_balls + 1), size=numbers_per_bet, replace=False))
        actual = set(np.random.choice(range(1, num_balls + 1), size=numbers_per_bet, replace=False))
        match = len(pred & actual)
        match_counts[match] += 1
    return sum(match_counts[i] for i in range(3, 7)) / n_simulations * 100

def backtest(method_name, predict_func, history, rules, test_periods):
    """執行回測"""
    total_periods = min(test_periods, len(history) - 20)
    matches = []
    
    start_idx = len(history) - total_periods
    
    for i in range(total_periods):
        target_idx = start_idx + i
        target_draw = history[target_idx]
        train_data = history[:target_idx]
        
        try:
            res = predict_func(train_data, rules)
            pred = set(res['numbers'])
            actual = set(target_draw['numbers'])
            match = len(pred & actual)
            matches.append(match)
        except Exception as e:
            continue
            
    if not matches:
        return 0, 0
        
    m3_plus_rate = sum(1 for m in matches if m >= 3) / len(matches) * 100
    avg_match = np.mean(matches)
    return m3_plus_rate, avg_match

def run_multi_term_report():
    parser = argparse.ArgumentParser(description='ARIMA 與 Ensemble 多維度回測')
    parser.add_argument('--type', type=str, default='BIG_LOTTO', help='彩種 (BIG_LOTTO 或 POWER_LOTTO)')
    args = parser.parse_args()
    
    lottery_type = args.type
    
    print("=" * 80)
    print(f"📊 ARIMA 與 Ensemble 多維度（短、中、長）回測 - {lottery_type}")
    print("=" * 80)
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = list(reversed(db.get_all_draws(lottery_type=lottery_type)))
    rules = get_lottery_rules(lottery_type)
    
    if not history:
        print(f"❌ 無法讀取歷史數據 for {lottery_type}")
        return

    num_balls = rules.get('maxNumber', 49)
    random_m3 = random_baseline(num_balls=num_balls)
    print(f"隨機基準 (M3+): {random_m3:.2f}%")
    
    engine = UnifiedPredictionEngine()
    ensemble = EnsembleStackingPredictor()
    
    terms = {
        "短期 (150期)": 150,
        "中期 (500期)": 500,
        "長期 (全部)": len(history) - 50  # 保留50期作為最初訓練
    }
    
    methods = {
        "ARIMA (1,0,0)": lambda h, r: engine.arima_predict(h, r),
        "Ensemble (ARIMA + Bi-LSTM)": lambda h, r: ensemble.predict_with_features(h, r, use_lstm=True)
    }
    
    report_data = []
    
    for term_name, periods in terms.items():
        print(f"\n🏃 執行 {term_name} 回測 (n={periods})...")
        
        # 為該 Term 訓練 LSTM (使用之前的歷史數據)
        if hasattr(ensemble, 'train_lstm'):
            start_idx = len(history) - periods
            train_data = history[:start_idx]
            print(f"  [LSTM] 正在為 {term_name} 進行預訓練 (樣本數: {len(train_data)})...")
            ensemble.train_lstm(train_data, epochs=30, num_balls=num_balls)
            
        for method_label, func in methods.items():
            m3_rate, avg_m = backtest(method_label, func, history, rules, periods)
            edge = m3_rate - random_m3
            report_data.append({
                "Lottery": lottery_type,
                "Term": term_name,
                "Method": method_label,
                "M3+ Rate": f"{m3_rate:.2f}%",
                "Avg Match": f"{avg_m:.2f}",
                "Edge": f"{edge:+.2f}%"
            })
            print(f"  [{method_label}]: M3+ = {m3_rate:.2f}%, Edge = {edge:+.2f}%")

    df = pd.DataFrame(report_data)
    print("\n" + "=" * 80)
    print(f"🏆 最終彙總報告 - {lottery_type}")
    print("=" * 80)
    print(df.drop(columns=['Lottery']).to_string(index=False))
    
    # Save to JSON for records
    fn = f"arima_multi_term_results_{lottery_type.lower()}.json"
    output_path = os.path.join(project_root, 'tools', 'data', fn)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    print(f"\n結果已保存至: {output_path}")

if __name__ == "__main__":
    run_multi_term_report()
