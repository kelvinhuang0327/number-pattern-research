#!/usr/bin/env python3
"""
大樂透最佳6注預測
使用多種高信心度預測方法生成6組不同的號碼組合
"""
import sys
import asyncio
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')

from database import db_manager
from models.unified_predictor import prediction_engine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from models.bayesian_ensemble import BayesianEnsemblePredictor
from common import get_lottery_rules

async def predict_best_6_bets():
    print('=' * 80)
    print('🎯 大樂透最佳6注預測（下期預測）')
    print('=' * 80)
    print()

    # 獲取大樂透的歷史數據
    print('📊 載入大樂透歷史數據...')
    all_draws = db_manager.get_all_draws('BIG_LOTTO')

    if not all_draws:
        print('❌ 找不到大樂透的歷史數據')
        return

    # 使用最近100期作為訓練數據
    history = all_draws[:100]
    print(f'✅ 載入 {len(history)} 期數據')
    print(f'   最新開獎: {history[0]["date"]} - 期號 {history[0]["draw"]}')
    print(f'   訓練範圍: {history[-1]["date"]} ~ {history[0]["date"]}')
    print()

    lottery_rules = get_lottery_rules('BIG_LOTTO')

    print('🎲 開始生成最佳6注預測...')
    print('=' * 80)
    print()

    bets = []

    # 第1注：頻率分析（歷史統計最可靠）
    print('正在計算第1注 [頻率分析]...')
    try:
        result = prediction_engine.frequency_predict(history, lottery_rules)
        bets.append({
            'method': '頻率分析',
            'numbers': sorted(result['numbers']),
            'confidence': result.get('confidence', 0),
            'description': '基於歷史出現頻率的統計分析'
        })
        print(f'✅ 完成 - 信心度: {result.get("confidence", 0):.2%}')
    except Exception as e:
        print(f'❌ 失敗: {str(e)}')
    print()

    # 第2注：趨勢分析（近期走勢）
    print('正在計算第2注 [趨勢分析]...')
    try:
        result = prediction_engine.trend_predict(history, lottery_rules)
        bets.append({
            'method': '趨勢分析',
            'numbers': sorted(result['numbers']),
            'confidence': result.get('confidence', 0),
            'description': '基於近期趨勢的權重分析'
        })
        print(f'✅ 完成 - 信心度: {result.get("confidence", 0):.2%}')
    except Exception as e:
        print(f'❌ 失敗: {str(e)}')
    print()

    # 第3注：貝葉斯機率（條件機率）
    print('正在計算第3注 [貝葉斯機率]...')
    try:
        result = prediction_engine.bayesian_predict(history, lottery_rules)
        bets.append({
            'method': '貝葉斯機率',
            'numbers': sorted(result['numbers']),
            'confidence': result.get('confidence', 0),
            'description': '基於條件機率的貝葉斯推論'
        })
        print(f'✅ 完成 - 信心度: {result.get("confidence", 0):.2%}')
    except Exception as e:
        print(f'❌ 失敗: {str(e)}')
    print()

    # 第4注：熱冷號混合（平衡策略）
    print('正在計算第4注 [熱冷號混合]...')
    try:
        result = prediction_engine.hot_cold_mix_predict(history, lottery_rules)
        bets.append({
            'method': '熱冷號混合',
            'numbers': sorted(result['numbers']),
            'confidence': result.get('confidence', 0),
            'description': '熱門號碼與冷門號碼的平衡組合'
        })
        print(f'✅ 完成 - 信心度: {result.get("confidence", 0):.2%}')
    except Exception as e:
        print(f'❌ 失敗: {str(e)}')
    print()

    # 第5-6注：優化集成雙注（集成多種方法）
    print('正在計算第5-6注 [優化集成雙注]...')
    try:
        optimized_predictor = OptimizedEnsemblePredictor(prediction_engine)
        opt_result = optimized_predictor.predict(history, lottery_rules)

        bets.append({
            'method': '優化集成-第1組',
            'numbers': sorted(opt_result['bet1']['numbers']),
            'confidence': opt_result['bet1'].get('confidence', 0),
            'description': '集成多種預測方法的優化組合'
        })

        bets.append({
            'method': '優化集成-第2組',
            'numbers': sorted(opt_result['bet2']['numbers']),
            'confidence': opt_result['bet2'].get('confidence', 0),
            'description': '集成預測的差異化組合'
        })

        print(f'✅ 完成 - 第1組信心度: {opt_result["bet1"].get("confidence", 0):.2%}')
        print(f'         第2組信心度: {opt_result["bet2"].get("confidence", 0):.2%}')
    except Exception as e:
        print(f'❌ 失敗: {str(e)}')
    print()

    # 顯示最終結果
    print('=' * 80)
    print('📊 最佳6注預測結果')
    print('=' * 80)
    print()

    if len(bets) >= 6:
        # 按信心度排序
        bets_sorted = sorted(bets, key=lambda x: x['confidence'], reverse=True)

        for idx, bet in enumerate(bets_sorted, 1):
            numbers_str = ', '.join(f'{n:02d}' for n in bet['numbers'])
            confidence_bar = '█' * int(bet['confidence'] * 20)

            print(f'🎯 第{idx}注 [{bet["method"]:15s}]')
            print(f'   號碼: {numbers_str}')
            print(f'   信心度: {bet["confidence"]:6.2%} {confidence_bar}')
            print(f'   說明: {bet["description"]}')
            print()

        print('=' * 80)
        print('📋 投注清單（複製使用）')
        print('=' * 80)
        print()

        for idx, bet in enumerate(bets_sorted, 1):
            numbers_str = ' '.join(f'{n:02d}' for n in bet['numbers'])
            print(f'{idx}. {numbers_str}')

        print()
        print('=' * 80)
        print('📈 號碼出現統計')
        print('=' * 80)
        print()

        # 統計號碼出現次數
        number_count = {}
        for bet in bets_sorted:
            for num in bet['numbers']:
                number_count[num] = number_count.get(num, 0) + 1

        # 按出現次數排序
        sorted_numbers = sorted(number_count.items(), key=lambda x: (-x[1], x[0]))

        # 分組顯示
        high_freq = [n for n, c in sorted_numbers if c >= 4]
        mid_freq = [n for n, c in sorted_numbers if 2 <= c < 4]
        low_freq = [n for n, c in sorted_numbers if c == 1]

        if high_freq:
            high_freq_str = ', '.join(f'{n:02d}({number_count[n]}次)' for n in high_freq)
            print(f'🔥 高頻號碼（4次以上）: {high_freq_str}')

        if mid_freq:
            mid_freq_str = ', '.join(f'{n:02d}({number_count[n]}次)' for n in mid_freq)
            print(f'⭐ 中頻號碼（2-3次）: {mid_freq_str}')

        if low_freq:
            low_freq_str = ', '.join(f'{n:02d}' for n in low_freq)
            print(f'💫 低頻號碼（1次）: {low_freq_str}')

        print()
        print('=' * 80)
        print('💡 投注建議')
        print('=' * 80)
        print()
        print('✓ 6注號碼已按信心度由高到低排序')
        print('✓ 建議優先投注前3-4注（信心度較高）')
        print('✓ 高頻號碼出現在多組預測中，值得關注')
        print('✓ 各組號碼涵蓋不同預測策略，提高覆蓋率')
        print()
        print('⚠️  重要提醒')
        print('   • 彩券為機率遊戲，無法保證中獎')
        print('   • 預測僅供參考，請理性投注')
        print('   • 請勿過度投資，以娛樂心態參與')
        print()
        print('=' * 80)

        # 計算平均信心度
        avg_confidence = sum(b['confidence'] for b in bets_sorted) / len(bets_sorted)
        print(f'📊 平均信心度: {avg_confidence:.2%}')
        print(f'📅 預測基準: 期號 {history[0]["draw"]} ({history[0]["date"]})')
        print('=' * 80)

    else:
        print(f'⚠️  僅成功生成 {len(bets)} 注預測')

    return bets

if __name__ == '__main__':
    asyncio.run(predict_best_6_bets())
