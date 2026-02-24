#!/usr/bin/env python3
"""
優化多注策略回測工具 (Optimized Multi-Bet Backtester)
支持 20, 50, 100 期回測，分析 Bet 1, 2, 3 及組合命中率。
"""
import os
import sys
import numpy as np
import json
import argparse
from datetime import datetime
from collections import Counter

# 確保可以導入專案模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lottery_api.database import DatabaseManager
from lottery_api.engine.multi_bet_optimizer import MultiBetOptimizer

def run_multi_term_backtest(lottery_type, periods=100, train_window=250, retrain_freq=1):
    lottery_name = '大樂透' if 'BIG' in lottery_type.upper() else '威力彩'
    print(f"\n" + "="*60)
    print(f"📊 開始 {lottery_name} 回測 | 總期數: {periods} | 訓練窗口: {train_window} | 重訓頻率: {retrain_freq}")
    print("="*60)

    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    res = db.get_draws(lottery_type, page_size=train_window + periods + 10)
    history = res['draws']
    if history and history[0]['draw'] > history[-1]['draw']:
        history = history[::-1]

    if len(history) < periods + 10:
        print(f"❌ 數據量不足: 需要 {periods + 10} 期，現有 {len(history)} 期")
        return None

    optimizer = MultiBetOptimizer(lottery_type=lottery_type)
    
    # 緩存模型以實現跳過重訓
    pb_predictor = None
    
    # 用於統計結果
    stats = {
        'bet1': {'matches': [], 'counts': Counter()},
        'bet2': {'matches': [], 'counts': Counter()},
        'bet3': {'matches': [], 'counts': Counter()},
        'combined_max': {'matches': [], 'counts': Counter()}, # 3注中拿最高分的
        'combined_win_rate_3plus': 0 # 組合命中 3+ 的比率
    }

    full_results = []

    for i in range(periods):
        test_idx = len(history) - periods + i
        actual_nums = set(history[test_idx]['numbers'])
        current_history = history[:test_idx]
        
        # 執行預測 (產生 3 注)
        # 為了加速回測，我們手動控制 optimizer 的行為
        if pb_predictor is None or i % retrain_freq == 0:
            from lottery_api.models.perball_lstm import PerBallLSTMPredictor
            pb_predictor = PerBallLSTMPredictor(
                num_balls=optimizer.num_balls, 
                n_picks=optimizer.n_picks,
                window_size=5
            )
            train_data = current_history[-train_window:]
            pb_predictor.train(train_data, epochs=35, verbose=0)
        
        pb_proba = pb_predictor.predict_proba(current_history)
        
        # 組合 3 注
        bets = []
        # Bet 1: Position Optimal
        bet1_nums = pb_predictor._greedy_dedup_sample(pb_proba, optimizer.n_picks)
        bets.append({'numbers': sorted(bet1_nums), 'style': '位置最優 (Per-Ball LSTM)'})
        
        # Bet 2: Zonal Cluster
        combined_proba = np.mean(pb_proba, axis=0)
        from lottery_api.engine.multi_bet_optimizer import ZonalDensityDetector
        anomalies = ZonalDensityDetector.detect_anomalies(combined_proba)
        if anomalies:
            top_zone = anomalies[0]['range']
            zone_indices = np.argsort(combined_proba[top_zone[0]-1:top_zone[1]])[::-1][:3]
            zone_nums = [idx + top_zone[0] for idx in zone_indices]
            all_indices = np.argsort(combined_proba)[::-1]
            for idx in all_indices:
                num = idx + 1
                if num not in zone_nums and len(zone_nums) < optimizer.n_picks:
                    zone_nums.append(num)
            bets.append({'numbers': sorted(zone_nums), 'style': '區域集群 (Anomaly Detection)'})
        else:
            bet2_nums = pb_predictor.predict_with_temperature(current_history, n_numbers=optimizer.n_picks, temperature=1.2, n_samples=1)[0]
            bets.append({'numbers': bet2_nums, 'style': '區域集群 (Low Anomaly)'})
            
        # Bet 3: Ensemble
        from lottery_api.models.unified_predictor import prediction_engine
        ensemble_res = prediction_engine.ensemble_predict(current_history, optimizer.rules)
        bets.append({'numbers': sorted(ensemble_res['numbers']), 'style': '穩定集成 (7-Method Ensemble)'})
        
        row = {'draw': history[test_idx]['draw'], 'actual': sorted(list(actual_nums)), 'bets': []}
        
        round_matches = []
        for j, b in enumerate(bets):
            match_set = set(b['numbers']) & actual_nums
            match_count = len(match_set)
            round_matches.append(match_count)
            
            stats[f'bet{j+1}']['matches'].append(match_count)
            stats[f'bet{j+1}']['counts'][match_count] += 1
            
            row['bets'].append({
                'style': b['style'],
                'numbers': b['numbers'],
                'match': match_count
            })

        max_match = max(round_matches)
        stats['combined_max']['matches'].append(max_match)
        stats['combined_max']['counts'][max_match] += 1
        
        full_results.append(row)
        
        if (i + 1) % 5 == 0 or i == periods - 1:
            avg_combined = np.mean(stats['combined_max']['matches'])
            print(f"   已完成 {i+1:3d}/{periods} 期 | 組合最高平均命中: {avg_combined:.2f}")

    # 計算 3+ 命中率
    comb_matches = stats['combined_max']['matches']
    win_3_plus = sum(1 for m in comb_matches if m >= 3)
    stats['combined_win_rate_3plus'] = (win_3_plus / periods) * 100

    return stats

def main():
    parser = argparse.ArgumentParser(description='多策略 3 注優化回測')
    parser.add_argument('--lottery', type=str, default='big_lotto', choices=['big_lotto', 'power_lotto'])
    parser.add_argument('--terms', type=str, default='150,500,1000', help='回測期數列表 (逗號分隔)')
    parser.add_argument('--retrain-freq', type=int, default=5, help='LSTM 重訓頻率 (預設每 5 期訓練一次以加速)')
    args = parser.parse_args()

    lottery_type = 'BIG_LOTTO' if args.lottery == 'big_lotto' else 'POWER_LOTTO'
    
    # 處理期數
    terms = []
    for t_str in args.terms.split(','):
        t_str = t_str.strip().lower()
        if t_str == 'all':
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api', 'data', 'lottery_v2.db')
            import sqlite3
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM draws WHERE lottery_type=?", (lottery_type,))
            count = c.fetchone()[0]
            conn.close()
            terms.append(count - 250)
        else:
            terms.append(int(t_str))
    
    final_report = {}

    for t in terms:
        stats = run_multi_term_backtest(lottery_type, periods=t, retrain_freq=args.retrain_freq)
        if stats:
            final_report[f'{t}_periods'] = {
                'avg_bet1': np.mean(stats['bet1']['matches']),
                'avg_bet2': np.mean(stats['bet2']['matches']),
                'avg_bet3': np.mean(stats['bet3']['matches']),
                'avg_combined': np.mean(stats['combined_max']['matches']),
                'win_rate_3plus': stats['combined_win_rate_3plus']
            }

    # 輸出最終報告樣式
    print("\n" + "#"*60)
    print(f"📊 {lottery_type} 綜合回測報告")
    print("#"*60)
    
    print(f"\n{'回測期數':<10} | {'Bet1':<10} | {'Bet2':<10} | {'Bet3':<10} | {'組合最高':<10} | {'3+命中率':<10}")
    print("-" * 75)
    for term, data in final_report.items():
        print(f"{term:<10} | {data['avg_bet1']:<10.2f} | {data['avg_bet2']:<10.2f} | {data['avg_bet3']:<10.2f} | {data['avg_combined']:<10.2f} | {data['win_rate_3plus']:<9.1f}%")

    # 保存結果
    output_path = f'tools/data/backtest_multi_{args.lottery}.json'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(final_report, f, indent=2)
    print(f"\n✅ 報告已保存至: {output_path}")

if __name__ == "__main__":
    main()
