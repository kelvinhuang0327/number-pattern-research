#!/usr/bin/env python3
"""
回測我推薦的4注配置 vs ClusterPivot
使用2025年全年95期數據
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database import DatabaseManager
from models.unified_predictor import UnifiedPredictionEngine

def test_my_4bet_config():
    """測試我推薦的4注配置"""
    
    db = DatabaseManager()
    all_draws = db.get_all_draws('POWER_LOTTO')
    
    print("=" * 80)
    print("回測我推薦的4注配置")
    print("=" * 80)
    print(f"總共回測期數: {len(all_draws) - 1} 期")
    print()
    
    # 取出2025年的數據 (假設最後95期是2025年)
    # 實際應該根據期號來判斷
    start_idx = max(0, len(all_draws) - 96)  # 保留最後1期作為預測目標
    test_draws = all_draws[start_idx:-1]
    target_draw = all_draws[-1]
    
    print(f"回測期間: 第 {len(all_draws)-len(test_draws)} 期 到 第 {len(all_draws)-1} 期")
    print(f"目標期號: {target_draw['draw']}")
    print()
    
    predictor = UnifiedPredictionEngine(all_draws[:-1])
    
    hit_count = 0
    hit_periods = []
    miss_count = 0
    
    predictions_log = []
    
    # 對每一期進行預測，然後與實際結果比對
    for i, test_draw in enumerate(test_draws):
        # 使用前面的數據作為歷史
        history = all_draws[:start_idx + i]
        predictor = UnifiedPredictionEngine(history)
        
        # 我推薦的4注配置
        try:
            # 注1: Ensemble (100窗)
            pred1 = predictor.ensemble_predict(window=100)
            
            # 注2: Ensemble (500窗)
            pred2 = predictor.ensemble_predict(window=500)
            
            # 注3: Zone_Balance + Bayesian
            pred3_zb = predictor.zone_balance_predict(window=200)
            pred3_bay = predictor.bayesian_predict(window=200)
            pred3_numbers = list(set(pred3_zb['numbers']) | set(pred3_bay['numbers']))[:6]
            pred3_special = (int(pred3_zb['special']) + int(pred3_bay['special'])) // 2
            pred3 = {'numbers': pred3_numbers, 'special': pred3_special}
            
            # 注4: Trend + Frequency
            pred4_trend = predictor.trend_predict(window=300)
            pred4_freq = predictor.frequency_predict(window=300)
            pred4_numbers = list(set(pred4_trend['numbers']) | set(pred4_freq['numbers']))[:6]
            pred4_special = (int(pred4_trend['special']) + int(pred4_freq['special'])) // 2
            pred4 = {'numbers': pred4_numbers, 'special': pred4_special}
            
            # 檢查是否命中
            actual_numbers = set(test_draw['numbers'])
            actual_special = int(test_draw['special'])
            
            hit = False
            hit_bets = []
            
            for bet_idx, pred in enumerate([pred1, pred2, pred3, pred4], 1):
                pred_numbers = set(pred['numbers'])
                pred_special = int(pred['special'])
                
                # 檢查號碼命中 (4個以上)
                match_count = len(actual_numbers & pred_numbers)
                special_match = (actual_special == pred_special)
                
                if match_count >= 4:  # 威力彩的中獎規則
                    hit = True
                    hit_bets.append(bet_idx)
            
            if hit:
                hit_count += 1
                hit_periods.append({
                    'issue': test_draw['draw'],
                    'actual': sorted(list(actual_numbers)),
                    'special': actual_special,
                    'hit_bets': hit_bets
                })
            else:
                miss_count += 1
            
            predictions_log.append({
                'issue': test_draw['draw'],
                'hit': hit,
                'hit_bets': hit_bets
            })
            
        except Exception as e:
            print(f"期號 {test_draw['draw']} 預測失敗: {e}")
            miss_count += 1
    
    print("=" * 80)
    print("【回測結果】我推薦的4注配置")
    print("=" * 80)
    print()
    print(f"命中期數: {hit_count}")
    print(f"未中期數: {miss_count}")
    print(f"總期數: {len(test_draws)}")
    print(f"命中率: {hit_count / len(test_draws) * 100:.2f}%")
    print(f"預期每N期中1次: {len(test_draws) / hit_count:.1f} 期")
    print()
    
    print("=" * 80)
    print("【對比】我推薦的4注 vs ClusterPivot")
    print("=" * 80)
    print()
    print(f"{'方法':<25} {'命中率':<15} {'期次':<15} {'成本':<15}")
    print("-" * 70)
    print(f"{'ClusterPivot 4注':<25} {'14.74%':<15} {'6.8期':<15} {'$400':<15}")
    print(f"{'我推薦的4注':<25} {f'{hit_count/len(test_draws)*100:.2f}%':<15} {f'{len(test_draws)/hit_count:.1f}期':<15} {'$400':<15}")
    print()
    
    improvement = (hit_count / len(test_draws) - 0.1474) / 0.1474 * 100
    print(f"提升幅度: {improvement:+.1f}%")
    print()
    
    print("=" * 80)
    print("【命中期號詳情】")
    print("=" * 80)
    print()
    
    for hit_record in hit_periods[:20]:  # 只顯示前20期
        print(f"期號 {hit_record['issue']}: {hit_record['hit_bets']} 注命中")
    
    if len(hit_periods) > 20:
        print(f"... 還有 {len(hit_periods) - 20} 期")
    
    print()
    print("=" * 80)
    
    # 保存詳細結果
    result = {
        'config': '我推薦的4注配置',
        'backtest_period': f"{start_idx} - {len(all_draws)-1}",
        'total_draws': len(test_draws),
        'hit_count': hit_count,
        'miss_count': miss_count,
        'hit_rate': f"{hit_count / len(test_draws) * 100:.2f}%",
        'every_n_period': f"{len(test_draws) / hit_count:.1f}",
        'comparison': {
            'cluster_pivot': '14.74%',
            'my_config': f"{hit_count / len(test_draws) * 100:.2f}%",
            'improvement': f"{improvement:+.1f}%"
        },
        'hit_periods': hit_periods
    }
    
    return result

if __name__ == '__main__':
    result = test_my_4bet_config()
    
    # 保存結果到JSON
    output_file = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/backtest_my_4bet_config_result.json'
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 詳細結果已保存到: {output_file}")
