#!/usr/bin/env python3
"""
威力彩 115000002 期 - 四注推薦配置預測
使用窗口變異型配置 (方案B)
"""

import sys
import os
import json

# 確保路徑正確
script_dir = os.path.dirname(os.path.abspath(__file__))
lottery_api_dir = os.path.join(script_dir, 'lottery-api')
if lottery_api_dir not in sys.path:
    sys.path.insert(0, lottery_api_dir)

try:
    from database import db_manager
    from models.unified_predictor import UnifiedPredictionEngine
    from common import get_lottery_rules
except ImportError as e:
    print(f"❌ 導入失敗: {e}")
    print(f"Python path: {sys.path[:3]}")
    sys.exit(1)

def predict_power_lotto_four_bets(draw_id='115000002'):
    """
    使用四注推薦配置預測威力彩號碼
    
    配置:
      注1: Ensemble (窗口100)
      注2: Ensemble (窗口500)
      注3: Zone_Balance + Bayesian 混合 (窗口200)
      注4: Trend + Anti-Consensus 混合 (窗口300)
    """
    
    print("\n" + "="*80)
    print(f"🎯 威力彩 {draw_id} 期 - 四注推薦配置預測")
    print("="*80)
    
    # 初始化
    lottery_type = 'POWER_LOTTO'
    engine = UnifiedPredictionEngine()
    lottery_rules = get_lottery_rules(lottery_type)
    
    # 加載所有數據
    all_draws = db_manager.get_all_draws(lottery_type)
    
    if not all_draws:
        print("❌ 未找到威力彩數據")
        return
    
    print(f"\n📊 已加載 {len(all_draws)} 期威力彩數據")
    
    # 找到目標期號
    target_idx = -1
    for i, draw in enumerate(all_draws):
        if draw.get('draw') == draw_id or draw.get('draw') == int(draw_id):
            target_idx = i
            break
    
    if target_idx == -1:
        print(f"❌ 未找到期號 {draw_id}")
        print(f"最新期號: {all_draws[0]['draw']}")
        return
    
    print(f"✅ 找到期號 {draw_id}")
    
    # 獲取該期之後的全部歷史 (防止數據洩漏)
    available_history = all_draws[target_idx + 1:]
    
    print(f"📈 可用歷史數據: {len(available_history)} 期")
    
    # ========== 注1: Ensemble(100窗) ==========
    print("\n" + "-"*80)
    print("注1: Ensemble (窗口100) - 靈活反應型")
    print("-"*80)
    
    try:
        history_100 = available_history[:100] if len(available_history) >= 100 else available_history
        result1 = engine.ensemble_predict(history_100, lottery_rules, window_size=100)
        
        print(f"✅ 預測號碼: {sorted(result1['numbers'])}")
        print(f"✅ 特別號: {result1.get('special', '未預測')}")
        
        bet1 = result1
    except Exception as e:
        print(f"❌ 預測失敗: {e}")
        bet1 = None
    
    # ========== 注2: Ensemble(500窗) ==========
    print("\n" + "-"*80)
    print("注2: Ensemble (窗口500) - 穩定預測型")
    print("-"*80)
    
    try:
        history_500 = available_history[:500] if len(available_history) >= 500 else available_history
        result2 = engine.ensemble_predict(history_500, lottery_rules, window_size=500)
        
        print(f"✅ 預測號碼: {sorted(result2['numbers'])}")
        print(f"✅ 特別號: {result2.get('special', '未預測')}")
        
        bet2 = result2
    except Exception as e:
        print(f"❌ 預測失敗: {e}")
        bet2 = None
    
    # ========== 注3: Zone_Balance + Bayesian 混合 ==========
    print("\n" + "-"*80)
    print("注3: Zone_Balance + Bayesian 混合 (窗口200) - 平衡概率型")
    print("-"*80)
    
    try:
        history_200 = available_history[:200] if len(available_history) >= 200 else available_history
        
        # 獲取兩個方法的預測
        zb_result = engine.zone_balance_predict(history_200, lottery_rules)
        bay_result = engine.bayesian_predict(history_200, lottery_rules)
        
        print(f"   Zone_Balance: {sorted(zb_result['numbers'])}")
        print(f"   Bayesian: {sorted(bay_result['numbers'])}")
        
        # 混合預測 (權重 50-50)
        blended_numbers = {}
        for num in zb_result['numbers']:
            blended_numbers[num] = blended_numbers.get(num, 0) + 0.5
        for num in bay_result['numbers']:
            blended_numbers[num] = blended_numbers.get(num, 0) + 0.5
        
        # 選擇權重最高的 6 個號碼
        sorted_nums = sorted(blended_numbers.items(), key=lambda x: x[1], reverse=True)
        result3_numbers = [num for num, _ in sorted_nums[:6]]
        
        # 特別號多數投票
        special_votes = {zb_result.get('special'): 1, bay_result.get('special'): 1}
        result3_special = max(special_votes, key=special_votes.get)
        
        print(f"✅ 混合預測號碼: {sorted(result3_numbers)}")
        print(f"✅ 特別號: {result3_special}")
        
        bet3 = {'numbers': result3_numbers, 'special': result3_special}
    except Exception as e:
        print(f"❌ 預測失敗: {e}")
        bet3 = None
    
    # ========== 注4: Trend + Anti-Consensus 混合 ==========
    print("\n" + "-"*80)
    print("注4: Trend + Anti-Consensus 混合 (窗口300) - 趨勢逆向型")
    print("-"*80)
    
    try:
        history_300 = available_history[:300] if len(available_history) >= 300 else available_history
        
        # 獲取兩個方法的預測
        trend_result = engine.trend_predict(history_300, lottery_rules)
        
        # Anti-consensus (如果存在)
        if hasattr(engine, 'anti_consensus_predict'):
            ac_result = engine.anti_consensus_predict(history_300, lottery_rules)
        else:
            # 如果不存在, 使用 frequency 作為替代
            ac_result = engine.frequency_predict(history_300, lottery_rules)
        
        print(f"   Trend: {sorted(trend_result['numbers'])}")
        print(f"   Anti-Consensus/Frequency: {sorted(ac_result['numbers'])}")
        
        # 混合預測 (權重 60% Trend, 40% AC)
        blended_numbers = {}
        for num in trend_result['numbers']:
            blended_numbers[num] = blended_numbers.get(num, 0) + 0.6
        for num in ac_result['numbers']:
            blended_numbers[num] = blended_numbers.get(num, 0) + 0.4
        
        # 選擇權重最高的 6 個號碼
        sorted_nums = sorted(blended_numbers.items(), key=lambda x: x[1], reverse=True)
        result4_numbers = [num for num, _ in sorted_nums[:6]]
        
        # 特別號多數投票
        special_votes = {trend_result.get('special'): 1, ac_result.get('special'): 1}
        result4_special = max(special_votes, key=special_votes.get)
        
        print(f"✅ 混合預測號碼: {sorted(result4_numbers)}")
        print(f"✅ 特別號: {result4_special}")
        
        bet4 = {'numbers': result4_numbers, 'special': result4_special}
    except Exception as e:
        print(f"❌ 預測失敗: {e}")
        bet4 = None
    
    # ========== 預測結果總結 ==========
    print("\n" + "="*80)
    print("📋 完整預測結果")
    print("="*80)
    
    results = [
        ("注1 (Ensemble-100)", bet1),
        ("注2 (Ensemble-500)", bet2),
        ("注3 (Zone+Bayesian)", bet3),
        ("注4 (Trend+AC)", bet4),
    ]
    
    for i, (name, result) in enumerate(results, 1):
        if result:
            print(f"\n{name}:")
            print(f"  主號: {sorted(result['numbers'])}")
            print(f"  特別號: {result.get('special', '未知')}")
        else:
            print(f"\n{name}: ❌ 預測失敗")
    
    # ========== 推薦購買號碼 ==========
    print("\n" + "="*80)
    print("💰 推薦購買號碼組合")
    print("="*80)
    
    valid_bets = [b for b in [bet1, bet2, bet3, bet4] if b is not None]
    
    if len(valid_bets) == 4:
        print("\n✅ 四注均預測成功\n")
        
        for i, (name, result) in enumerate(results, 1):
            if result:
                numbers_str = ' '.join(f"{n:2d}" for n in sorted(result['numbers']))
                special = result.get('special', '?')
                print(f"注{i}: {numbers_str} + 特別號 {special}")
        
        # 計算覆蓋面
        all_numbers = set()
        for bet in valid_bets:
            all_numbers.update(bet['numbers'])
        
        coverage = len(all_numbers) / 38 * 100
        print(f"\n📊 號碼覆蓋: {len(all_numbers)}/38 個 ({coverage:.1f}%)")
        print(f"📊 覆蓋號碼: {sorted(all_numbers)}")
        
        # 統計各特別號預測次數
        special_stats = {}
        for bet in valid_bets:
            s = bet.get('special')
            special_stats[s] = special_stats.get(s, 0) + 1
        
        print(f"\n📊 特別號預測統計:")
        for special, count in sorted(special_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"   特別號 {special}: {count}/4 注預測")
    else:
        print(f"\n⚠️  僅成功預測 {len(valid_bets)}/4 注")
    
    # ========== 保存結果 ==========
    output_file = f'power_lotto_prediction_{draw_id}.json'
    
    output_data = {
        'draw_id': draw_id,
        'timestamp': '2026-01-05',
        'method': '四注推薦配置 (方案B)',
        'bets': []
    }
    
    for name, result in results:
        if result:
            output_data['bets'].append({
                'name': name,
                'numbers': sorted(result['numbers']),
                'special': result.get('special')
            })
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 結果已保存至: {output_file}")
    
    print("\n" + "="*80)

if __name__ == '__main__':
    predict_power_lotto_four_bets('115000002')
