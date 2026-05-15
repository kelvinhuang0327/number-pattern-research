#!/usr/bin/env python3
"""
回測我推薦的4注配置 - 簡化版本
使用2025年最後95期數據
"""

import json
import sys
from pathlib import Path

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
    print(f"總共可用期數: {len(all_draws)} 期")
    print()
    
    # 取最後95期作為回測期間
    test_count = 95
    start_idx = len(all_draws) - test_count - 1
    test_draws = all_draws[start_idx:start_idx + test_count]
    
    print(f"回測期間: {test_draws[0]['draw']} 到 {test_draws[-1]['draw']}")
    print(f"回測期數: {len(test_draws)} 期")
    print()
    
    # 初始化預測引擎（使用歷史數據）
    predictor = UnifiedPredictionEngine()
    
    hit_count = 0
    hit_periods = []
    
    # 對每一期進行預測
    for i, test_draw in enumerate(test_draws):
        try:
            # 使用前面的數據作為歷史 
            history = all_draws[:start_idx + i]
            
            # 我推薦的4注配置
            # 注1: Ensemble (100窗)
            pred1 = predictor.ensemble_predict(history, window=100)
            
            # 注2: Ensemble (500窗)
            pred2 = predictor.ensemble_predict(history, window=500)
            
            # 注3: Zone_Balance + Bayesian
            pred3_zb = predictor.zone_balance_predict(history, window=200)
            pred3_bay = predictor.bayesian_predict(history, window=200)
            pred3_numbers = list(set(pred3_zb['numbers']) | set(pred3_bay['numbers']))[:6]
            pred3_special = (int(pred3_zb['special']) + int(pred3_bay['special'])) // 2
            pred3 = {'numbers': pred3_numbers, 'special': pred3_special}
            
            # 注4: Trend + Frequency  
            pred4_trend = predictor.trend_predict(history, window=300)
            pred4_freq = predictor.frequency_predict(history, window=300)
            pred4_numbers = list(set(pred4_trend['numbers']) | set(pred4_freq['numbers']))[:6]
            pred4_special = (int(pred4_trend['special']) + int(pred4_freq['special'])) // 2
            pred4 = {'numbers': pred4_numbers, 'special': pred4_special}
            
            # 檢查是否命中
            actual_numbers = set(test_draw['numbers'])
            actual_special = int(test_draw['special'])
            
            hit = False
            hit_bets = []
            
            for bet_idx, pred in enumerate([pred1, pred2, pred3, pred4], 1):
                try:
                    pred_numbers = set(pred['numbers'])
                    pred_special = int(pred['special'])
                    
                    # 檢查號碼命中 (4個以上) - 威力彩中獎規則
                    match_count = len(actual_numbers & pred_numbers)
                    
                    if match_count >= 4:
                        hit = True
                        hit_bets.append(bet_idx)
                except:
                    pass
            
            if hit:
                hit_count += 1
                hit_periods.append({
                    'draw': test_draw['draw'],
                    'hit_bets': hit_bets,
                    'actual_numbers': sorted(list(actual_numbers)),
                    'actual_special': actual_special
                })
            
            # 進度顯示
            if (i + 1) % 20 == 0:
                print(f"已完成: {i+1}/{len(test_draws)} 期... 當前命中: {hit_count} 期")
            
        except Exception as e:
            print(f"期號 {test_draw['draw']} 預測失敗: {str(e)[:100]}")
            pass
    
    print()
    print("=" * 80)
    print("【回測結果】我推薦的4注配置")
    print("=" * 80)
    print()
    print(f"命中期數: {hit_count}")
    print(f"未中期數: {len(test_draws) - hit_count}")
    print(f"總期數: {len(test_draws)}")
    hit_rate = hit_count / len(test_draws) * 100
    print(f"命中率: {hit_rate:.2f}%")
    if hit_count > 0:
        print(f"預期每N期中1次: {len(test_draws) / hit_count:.1f} 期")
    print()
    
    print("=" * 80)
    print("【對比】我推薦的4注 vs ClusterPivot")
    print("=" * 80)
    print()
    print(f"{'方法':<25} {'命中率':<15} {'期次':<15} {'成本':<15}")
    print("-" * 70)
    print(f"{'ClusterPivot 4注':<25} {'14.74%':<15} {'6.8期':<15} {'$400':<15}")
    print(f"{'我推薦的4注':<25} {f'{hit_rate:.2f}%':<15} {f'{len(test_draws)/hit_count:.1f}期' if hit_count > 0 else 'N/A':<15} {'$400':<15}")
    print()
    
    if hit_count > 0:
        improvement = (hit_rate - 14.74) / 14.74 * 100
        print(f"提升幅度: {improvement:+.1f}%")
    else:
        print("⚠️  命中率為 0，無法計算提升幅度")
    print()
    
    print("=" * 80)
    print("【命中期號詳情】")
    print("=" * 80)
    print()
    
    if hit_periods:
        for hit_record in hit_periods[:15]:
            print(f"期號 {hit_record['draw']}: 注{hit_record['hit_bets']} 命中 | 實際號碼: {hit_record['actual_numbers']}")
        if len(hit_periods) > 15:
            print(f"... 還有 {len(hit_periods) - 15} 期")
    else:
        print("沒有命中記錄")
    
    print()
    print("=" * 80)
    
    # 保存結果到JSON
    result = {
        'config': '我推薦的4注配置',
        'backtest_draws': f"{test_draws[0]['draw']} - {test_draws[-1]['draw']}",
        'total_draws': len(test_draws),
        'hit_count': hit_count,
        'hit_rate_percent': f"{hit_rate:.2f}%",
        'every_n_period': f"{len(test_draws) / hit_count:.1f}" if hit_count > 0 else "N/A",
        'comparison': {
            'cluster_pivot': '14.74%',
            'my_config': f"{hit_rate:.2f}%",
            'improvement_percent': f"{(hit_rate - 14.74) / 14.74 * 100:+.1f}%" if hit_count > 0 else "N/A"
        },
        'hit_periods': hit_periods[:50]  # 只保存前50期
    }
    
    return result

if __name__ == '__main__':
    print("\n⏳ 開始回測，這可能需要幾分鐘... \n")
    result = test_my_4bet_config()
    
    # 保存結果到JSON
    output_file = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/backtest_my_4bet_result.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 詳細結果已保存到: {output_file}")
