#!/usr/bin/env python3
"""
威力彩 115000002 期 - 四注推薦配置預測
使用回測框架中的方法
"""

import os
import sys

# 確保在 lottery-api 目錄中運行
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import UnifiedPredictionEngine
from common import get_lottery_rules
import json

def predict_power_lotto_four_bets(draw_id='115000002'):
    """使用四注推薦配置預測威力彩號碼"""
    
    print("\n" + "="*80)
    print(f"🎯 威力彩 {draw_id} 期 - 四注推薦配置預測")
    print("="*80)
    
    lottery_type = 'POWER_LOTTO'
    engine = UnifiedPredictionEngine()
    lottery_rules = get_lottery_rules(lottery_type)
    
    # 加載所有數據
    all_draws = db_manager.get_all_draws(lottery_type)
    
    if not all_draws:
        print("❌ 未找到威力彩數據")
        return
    
    print(f"\n📊 已加載 {len(all_draws)} 期威力彩數據")
    print(f"最新期號: {all_draws[0].get('draw', '未知')}")
    
    # 如果期號不存在, 使用最新的數據做預測
    target_idx = 0  # 預測最新期號
    available_history = all_draws[target_idx + 1:] if target_idx + 1 < len(all_draws) else all_draws
    
    print(f"✅ 可用歷史數據: {len(available_history)} 期")
    
    predictions = []
    
    # ========== 注1: Ensemble(100窗) ==========
    print("\n" + "-"*80)
    print("注1: Ensemble (窗口100) - 靈快反應型")
    print("-"*80)
    
    try:
        history_100 = available_history[:min(100, len(available_history))]
        result1 = engine.ensemble_predict(history_100, lottery_rules)
        
        print(f"✅ 預測號碼: {sorted(result1['numbers'])}")
        print(f"✅ 特別號: {result1.get('special', '?')}")
        predictions.append(("Ensemble(100)", result1))
    except Exception as e:
        print(f"⚠️  預測失敗: {str(e)[:100]}")
    
    # ========== 注2: Ensemble(500窗) ==========
    print("\n" + "-"*80)
    print("注2: Ensemble (窗口500) - 穩定預測型")
    print("-"*80)
    
    try:
        history_500 = available_history[:min(500, len(available_history))]
        result2 = engine.ensemble_predict(history_500, lottery_rules)
        
        print(f"✅ 預測號碼: {sorted(result2['numbers'])}")
        print(f"✅ 特別號: {result2.get('special', '?')}")
        predictions.append(("Ensemble(500)", result2))
    except Exception as e:
        print(f"⚠️  預測失敗: {str(e)[:100]}")
    
    # ========== 注3: Zone_Balance + Bayesian 混合 ==========
    print("\n" + "-"*80)
    print("注3: Zone_Balance + Bayesian 混合 (窗口200)")
    print("-"*80)
    
    try:
        history_200 = available_history[:min(200, len(available_history))]
        zb_result = engine.zone_balance_predict(history_200, lottery_rules)
        bay_result = engine.bayesian_predict(history_200, lottery_rules)
        
        print(f"   Zone_Balance: {sorted(zb_result['numbers'])}")
        print(f"   Bayesian: {sorted(bay_result['numbers'])}")
        
        # 混合 (50-50)
        blended = {}
        for num in zb_result['numbers']:
            blended[num] = blended.get(num, 0) + 0.5
        for num in bay_result['numbers']:
            blended[num] = blended.get(num, 0) + 0.5
        
        sorted_nums = sorted(blended.items(), key=lambda x: x[1], reverse=True)
        result3_numbers = [int(num) for num, _ in sorted_nums[:6]]
        result3_special = zb_result.get('special', 1)
        
        print(f"✅ 混合預測: {sorted(result3_numbers)}")
        print(f"✅ 特別號: {result3_special}")
        predictions.append(("ZB+Bayesian", {'numbers': result3_numbers, 'special': result3_special}))
    except Exception as e:
        print(f"⚠️  預測失敗: {str(e)[:100]}")
    
    # ========== 注4: Trend + 頻率 混合 ==========
    print("\n" + "-"*80)
    print("注4: Trend + 頻率 混合 (窗口300)")
    print("-"*80)
    
    try:
        history_300 = available_history[:min(300, len(available_history))]
        trend_result = engine.trend_predict(history_300, lottery_rules)
        freq_result = engine.frequency_predict(history_300, lottery_rules)
        
        print(f"   Trend: {sorted(trend_result['numbers'])}")
        print(f"   Frequency: {sorted(freq_result['numbers'])}")
        
        # 混合 (60% Trend, 40% Freq)
        blended = {}
        for num in trend_result['numbers']:
            blended[num] = blended.get(num, 0) + 0.6
        for num in freq_result['numbers']:
            blended[num] = blended.get(num, 0) + 0.4
        
        sorted_nums = sorted(blended.items(), key=lambda x: x[1], reverse=True)
        result4_numbers = [int(num) for num, _ in sorted_nums[:6]]
        result4_special = trend_result.get('special', 2)
        
        print(f"✅ 混合預測: {sorted(result4_numbers)}")
        print(f"✅ 特別號: {result4_special}")
        predictions.append(("Trend+Freq", {'numbers': result4_numbers, 'special': result4_special}))
    except Exception as e:
        print(f"⚠️  預測失敗: {str(e)[:100]}")
    
    # ========== 結果總結 ==========
    print("\n" + "="*80)
    print("📋 完整預測結果")
    print("="*80)
    
    if predictions:
        for i, (name, result) in enumerate(predictions, 1):
            numbers = sorted(result['numbers'])
            special = result.get('special', '?')
            print(f"\n注{i} ({name}):")
            print(f"  主號: {numbers}")
            print(f"  特別號: {special}")
        
        # 計算覆蓋面
        all_numbers = set()
        for _, result in predictions:
            all_numbers.update(result['numbers'])
        
        coverage = len(all_numbers) / 38 * 100
        print(f"\n📊 號碼覆蓋: {len(all_numbers)}/38 個 ({coverage:.1f}%)")
        print(f"📊 覆蓋號碼: {sorted(all_numbers)}")
        
        # 保存結果
        output_file = f'../power_lotto_prediction_{draw_id}.json'
        output_data = {
            'draw_id': draw_id,
            'timestamp': '2026-01-05',
            'method': '四注推薦配置',
            'bets': [
                {
                    'name': name,
                    'numbers': [int(n) for n in sorted(result['numbers'])],
                    'special': int(result.get('special', 0))
                } for name, result in predictions
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ 結果已保存至: {output_file}")
    else:
        print("❌ 沒有成功的預測")
    
    print("\n" + "="*80)

if __name__ == '__main__':
    predict_power_lotto_four_bets()
