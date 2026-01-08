#!/usr/bin/env python3
"""
測試大樂透6注預測成功率
使用多種預測方法生成6注，評估命中率
"""
import sys
import asyncio
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery-api')

from database import db_manager
from models.unified_predictor import prediction_engine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from models.bayesian_ensemble import BayesianEnsemblePredictor
from common import get_lottery_rules

async def test_6_bets_prediction():
    print('=' * 80)
    print('🎯 大樂透6注預測測試')
    print('=' * 80)
    print()

    # 獲取大樂透的歷史數據
    print('📊 載入大樂透歷史數據...')
    all_draws = db_manager.get_all_draws('BIG_LOTTO')

    if not all_draws:
        print('❌ 找不到大樂透的歷史數據')
        print('請先上傳數據到資料庫')
        return

    # 使用最近100期作為訓練數據
    history = all_draws[:100]
    print(f'✅ 載入 {len(history)} 期數據')
    print(f'   日期範圍: {history[-1]["date"]} ~ {history[0]["date"]}')
    print()

    lottery_rules = get_lottery_rules('BIG_LOTTO')

    print('🎲 開始生成6注預測...')
    print('-' * 80)
    print()

    # 生成6注預測
    bets = []

    # 第1注：頻率分析
    try:
        result = prediction_engine.frequency_predict(history, lottery_rules)
        bets.append({
            'method': '頻率分析',
            'numbers': result['numbers'],
            'confidence': result.get('confidence', 0)
        })
        print(f'✅ 第1注 (頻率分析):')
        print(f'   號碼: {sorted(result["numbers"])}')
        print(f'   信心度: {result.get("confidence", 0):.2%}')
        print()
    except Exception as e:
        print(f'❌ 第1注失敗: {str(e)}')
        print()

    # 第2注：趨勢分析
    try:
        result = prediction_engine.trend_predict(history, lottery_rules)
        bets.append({
            'method': '趨勢分析',
            'numbers': result['numbers'],
            'confidence': result.get('confidence', 0)
        })
        print(f'✅ 第2注 (趨勢分析):')
        print(f'   號碼: {sorted(result["numbers"])}')
        print(f'   信心度: {result.get("confidence", 0):.2%}')
        print()
    except Exception as e:
        print(f'❌ 第2注失敗: {str(e)}')
        print()

    # 第3注：貝葉斯機率
    try:
        result = prediction_engine.bayesian_predict(history, lottery_rules)
        bets.append({
            'method': '貝葉斯機率',
            'numbers': result['numbers'],
            'confidence': result.get('confidence', 0)
        })
        print(f'✅ 第3注 (貝葉斯機率):')
        print(f'   號碼: {sorted(result["numbers"])}')
        print(f'   信心度: {result.get("confidence", 0):.2%}')
        print()
    except Exception as e:
        print(f'❌ 第3注失敗: {str(e)}')
        print()

    # 第4注：蒙地卡羅模擬
    try:
        result = prediction_engine.monte_carlo_predict(history, lottery_rules)
        bets.append({
            'method': '蒙地卡羅模擬',
            'numbers': result['numbers'],
            'confidence': result.get('confidence', 0)
        })
        print(f'✅ 第4注 (蒙地卡羅模擬):')
        print(f'   號碼: {sorted(result["numbers"])}')
        print(f'   信心度: {result.get("confidence", 0):.2%}')
        print()
    except Exception as e:
        print(f'❌ 第4注失敗: {str(e)}')
        print()

    # 第5-6注：優化集成雙注
    try:
        optimized_predictor = OptimizedEnsemblePredictor(prediction_engine)
        opt_result = optimized_predictor.predict(history, lottery_rules)

        bets.append({
            'method': '優化集成雙注-1',
            'numbers': opt_result['bet1']['numbers'],
            'confidence': opt_result['bet1'].get('confidence', 0)
        })

        bets.append({
            'method': '優化集成雙注-2',
            'numbers': opt_result['bet2']['numbers'],
            'confidence': opt_result['bet2'].get('confidence', 0)
        })

        print(f'✅ 第5注 (優化集成雙注-1):')
        print(f'   號碼: {sorted(opt_result["bet1"]["numbers"])}')
        print(f'   信心度: {opt_result["bet1"].get("confidence", 0):.2%}')
        print()

        print(f'✅ 第6注 (優化集成雙注-2):')
        print(f'   號碼: {sorted(opt_result["bet2"]["numbers"])}')
        print(f'   信心度: {opt_result["bet2"].get("confidence", 0):.2%}')
        print()
    except Exception as e:
        print(f'❌ 第5-6注失敗: {str(e)}')
        print()

    print('-' * 80)
    print()

    # 顯示預測摘要
    print('=' * 80)
    print('📊 6注預測摘要')
    print('=' * 80)
    print()

    if len(bets) >= 6:
        for idx, bet in enumerate(bets, 1):
            sorted_numbers = sorted(bet['numbers'])
            numbers_str = ', '.join(f'{n:02d}' for n in sorted_numbers)
            print(f'第{idx}注 [{bet["method"]:15s}]: {numbers_str}')

        print()
        print('-' * 80)
        print('💡 使用說明')
        print('-' * 80)
        print('• 以上6注使用不同預測方法生成，涵蓋多種分析角度')
        print('• 頻率分析：基於歷史出現頻率')
        print('• 趨勢分析：基於近期趨勢權重')
        print('• 貝葉斯機率：基於條件機率計算')
        print('• 蒙地卡羅：基於隨機模擬統計')
        print('• 優化集成雙注：結合多種方法的集成預測')
        print()
        print('⚠️  提醒：彩券是機率遊戲，請理性投注')

    else:
        print(f'⚠️  僅成功生成 {len(bets)} 注預測')

    print('=' * 80)

    # 返回預測結果供後續驗證使用
    return bets

if __name__ == '__main__':
    asyncio.run(test_6_bets_prediction())
