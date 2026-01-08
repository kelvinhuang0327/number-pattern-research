#!/usr/bin/env python3
"""
測試今彩539各種預測方法對特定號碼的匹配度
目標號碼: 05, 23, 27, 28, 31
"""
import sys
import asyncio
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery-api')

from database import db_manager
from models.unified_predictor import prediction_engine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from models.bayesian_ensemble import BayesianEnsemblePredictor
from common import get_lottery_rules

async def test_all_prediction_methods():
    print('=' * 80)
    print('🎯 測試今彩539雙注預測方法匹配度')
    print('=' * 80)
    print()
    print('目標號碼: 05, 23, 27, 28, 31')
    print()

    # 獲取今彩539的歷史數據
    print('📊 載入今彩539歷史數據...')
    all_draws = db_manager.get_all_draws('DAILY_539')

    if not all_draws:
        print('❌ 找不到今彩539的歷史數據')
        print('請先上傳數據到資料庫')
        return

    # 使用最近100期作為訓練數據
    history = all_draws[:100]
    print(f'✅ 載入 {len(history)} 期數據')
    print(f'   日期範圍: {history[-1]["date"]} ~ {history[0]["date"]}')
    print()

    lottery_rules = get_lottery_rules('DAILY_539')
    target_numbers = {5, 23, 27, 28, 31}

    # 測試各種預測方法
    prediction_methods = [
        ('頻率分析', 'frequency'),
        ('趨勢分析', 'trend'),
        ('貝葉斯機率', 'bayesian'),
        ('蒙地卡羅模擬', 'monte_carlo'),
        ('熱冷號混合', 'hot_cold'),
        ('區域平衡', 'zone_balance'),
        ('奇偶平衡', 'odd_even'),
    ]

    results = []

    print('🔍 開始測試各種預測方法...')
    print('-' * 80)

    for method_name, method_type in prediction_methods:
        try:
            # 呼叫對應的預測方法
            if method_type == 'frequency':
                result = prediction_engine.frequency_predict(history, lottery_rules)
            elif method_type == 'trend':
                result = prediction_engine.trend_predict(history, lottery_rules)
            elif method_type == 'bayesian':
                result = prediction_engine.bayesian_predict(history, lottery_rules)
            elif method_type == 'monte_carlo':
                result = prediction_engine.monte_carlo_predict(history, lottery_rules)
            elif method_type == 'hot_cold':
                result = prediction_engine.hot_cold_mix_predict(history, lottery_rules)
            elif method_type == 'zone_balance':
                result = prediction_engine.zone_balance_predict(history, lottery_rules)
            elif method_type == 'odd_even':
                result = prediction_engine.odd_even_balance_predict(history, lottery_rules)

            predicted_numbers = set(result.get('numbers', []))
            matches = len(predicted_numbers & target_numbers)

            results.append({
                'name': method_name,
                'numbers': result.get('numbers', []),
                'matches': matches,
                'confidence': result.get('confidence', 0)
            })

            match_str = ', '.join(str(n) for n in sorted(predicted_numbers & target_numbers))
            print(f'📌 {method_name:15s} | 預測: {result["numbers"]} | 命中: {matches}/5 [{match_str or "無"}]')

        except Exception as e:
            print(f'❌ {method_name:15s} | 錯誤: {str(e)}')

    print('-' * 80)
    print()

    # 測試雙注預測方法
    print('🎲 測試雙注預測方法...')
    print('-' * 80)

    double_bet_results = []

    # 1. 優化集成預測
    try:
        print('正在執行優化集成預測...')
        optimized_predictor = OptimizedEnsemblePredictor(prediction_engine)
        opt_result = optimized_predictor.predict(history, lottery_rules)

        bet1_numbers = set(opt_result['bet1']['numbers'])
        bet2_numbers = set(opt_result['bet2']['numbers'])

        bet1_matches = len(bet1_numbers & target_numbers)
        bet2_matches = len(bet2_numbers & target_numbers)
        max_matches = max(bet1_matches, bet2_matches)

        double_bet_results.append({
            'name': '優化集成雙注',
            'bet1': opt_result['bet1']['numbers'],
            'bet2': opt_result['bet2']['numbers'],
            'bet1_matches': bet1_matches,
            'bet2_matches': bet2_matches,
            'max_matches': max_matches
        })

        print(f'✅ 優化集成雙注')
        print(f'   第一注: {opt_result["bet1"]["numbers"]} | 命中: {bet1_matches}/5')
        print(f'   第二注: {opt_result["bet2"]["numbers"]} | 命中: {bet2_matches}/5')
        print(f'   最佳命中: {max_matches}/5')

    except Exception as e:
        print(f'❌ 優化集成雙注錯誤: {str(e)}')

    print()

    # 2. 貝葉斯優化集成預測
    try:
        print('正在執行貝葉斯優化集成預測...')
        bayesian_predictor = BayesianEnsemblePredictor(prediction_engine)
        bay_result = bayesian_predictor.predict(history, lottery_rules)

        bet1_numbers = set(bay_result['bet1']['numbers'])
        bet2_numbers = set(bay_result['bet2']['numbers'])

        bet1_matches = len(bet1_numbers & target_numbers)
        bet2_matches = len(bet2_numbers & target_numbers)
        max_matches = max(bet1_matches, bet2_matches)

        double_bet_results.append({
            'name': '貝葉斯優化雙注',
            'bet1': bay_result['bet1']['numbers'],
            'bet2': bay_result['bet2']['numbers'],
            'bet1_matches': bet1_matches,
            'bet2_matches': bet2_matches,
            'max_matches': max_matches
        })

        print(f'✅ 貝葉斯優化雙注')
        print(f'   第一注: {bay_result["bet1"]["numbers"]} | 命中: {bet1_matches}/5')
        print(f'   第二注: {bay_result["bet2"]["numbers"]} | 命中: {bet2_matches}/5')
        print(f'   最佳命中: {max_matches}/5')

    except Exception as e:
        print(f'❌ 貝葉斯優化雙注錯誤: {str(e)}')

    print('-' * 80)
    print()

    # 排序並顯示結果
    print('=' * 80)
    print('📊 單注預測排名（按命中數）')
    print('=' * 80)

    results.sort(key=lambda x: x['matches'], reverse=True)
    for idx, r in enumerate(results, 1):
        matched = set(r['numbers']) & target_numbers
        match_str = ', '.join(str(n) for n in sorted(matched)) if matched else '無'
        medal = '🥇' if idx == 1 else '🥈' if idx == 2 else '🥉' if idx == 3 else '  '
        print(f'{medal} {idx}. {r["name"]:15s} | 命中 {r["matches"]}/5 | 號碼: {match_str}')

    print()
    print('=' * 80)
    print('🎲 雙注預測排名（按最佳命中數）')
    print('=' * 80)

    double_bet_results.sort(key=lambda x: x['max_matches'], reverse=True)
    for idx, r in enumerate(double_bet_results, 1):
        medal = '🥇' if idx == 1 else '🥈'
        print(f'{medal} {idx}. {r["name"]}')

        bet1_matched = set(r['bet1']) & target_numbers
        bet2_matched = set(r['bet2']) & target_numbers

        bet1_match_str = ', '.join(str(n) for n in sorted(bet1_matched)) if bet1_matched else '無'
        bet2_match_str = ', '.join(str(n) for n in sorted(bet2_matched)) if bet2_matched else '無'

        print(f'   第一注: {r["bet1"]} | 命中 {r["bet1_matches"]}/5 | 號碼: {bet1_match_str}')
        print(f'   第二注: {r["bet2"]} | 命中 {r["bet2_matches"]}/5 | 號碼: {bet2_match_str}')

    print()
    print('=' * 80)
    print('💡 結論')
    print('=' * 80)

    if results:
        best_single = results[0]
        print(f'單注最佳: {best_single["name"]} (命中 {best_single["matches"]}/5)')

    if double_bet_results:
        best_double = double_bet_results[0]
        print(f'雙注最佳: {best_double["name"]} (最佳命中 {best_double["max_matches"]}/5)')

    print()
    print('註: 命中數越高，表示預測方法越接近目標號碼')
    print('=' * 80)

if __name__ == '__main__':
    asyncio.run(test_all_prediction_methods())
