#!/usr/bin/env python3
"""
大樂透蒙地卡羅預測8注
使用蒙地卡羅模擬方法生成8組不同的號碼組合
"""
import sys
import asyncio
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')

from database import db_manager
from models.unified_predictor import prediction_engine
from common import get_lottery_rules
import numpy as np

async def predict_monte_carlo_8_bets():
    print('=' * 80)
    print('🎲 大樂透蒙地卡羅模擬預測8注')
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

    print('🎲 開始蒙地卡羅模擬預測（8次獨立運行）...')
    print('=' * 80)
    print()

    bets = []

    # 執行8次蒙地卡羅預測，每次都會產生不同結果
    for i in range(8):
        print(f'正在運行第 {i+1}/8 次蒙地卡羅模擬...')
        try:
            # 每次調用都會重新隨機模擬
            result = prediction_engine.monte_carlo_predict(history, lottery_rules)

            numbers = sorted([int(n) for n in result['numbers']])
            confidence = result.get('confidence', 0)

            bets.append({
                'run': i + 1,
                'numbers': numbers,
                'confidence': confidence
            })

            numbers_str = ', '.join(f'{n:02d}' for n in numbers)
            print(f'✅ 第{i+1}組: [{numbers_str}] - 信心度: {confidence:.2%}')

        except Exception as e:
            print(f'❌ 第{i+1}組失敗: {str(e)}')

        print()

    # 顯示最終結果
    print('=' * 80)
    print('📊 蒙地卡羅模擬8注結果')
    print('=' * 80)
    print()

    if len(bets) >= 8:
        # 按信心度排序
        bets_sorted = sorted(bets, key=lambda x: x['confidence'], reverse=True)

        for idx, bet in enumerate(bets_sorted, 1):
            numbers_str = ', '.join(f'{n:02d}' for n in bet['numbers'])
            confidence_bar = '█' * int(bet['confidence'] * 20)

            print(f'🎯 第{idx}注 [蒙地卡羅模擬-{bet["run"]}]')
            print(f'   號碼: {numbers_str}')
            print(f'   信心度: {bet["confidence"]:6.2%} {confidence_bar}')
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
        high_freq = [n for n, c in sorted_numbers if c >= 5]
        mid_high_freq = [n for n, c in sorted_numbers if 3 <= c < 5]
        mid_freq = [n for n, c in sorted_numbers if c == 2]
        low_freq = [n for n, c in sorted_numbers if c == 1]

        if high_freq:
            high_freq_str = ', '.join(f'{n:02d}({number_count[n]}次)' for n in high_freq)
            print(f'🔥 超高頻號碼（5次以上）: {high_freq_str}')

        if mid_high_freq:
            mid_high_freq_str = ', '.join(f'{n:02d}({number_count[n]}次)' for n in mid_high_freq)
            print(f'⭐ 高頻號碼（3-4次）: {mid_high_freq_str}')

        if mid_freq:
            mid_freq_str = ', '.join(f'{n:02d}({number_count[n]}次)' for n in mid_freq)
            print(f'💫 中頻號碼（2次）: {mid_freq_str}')

        if low_freq:
            low_freq_str = ', '.join(f'{n:02d}' for n in low_freq)
            print(f'◦  低頻號碼（1次）: {low_freq_str}')

        print()
        print('=' * 80)
        print('💡 蒙地卡羅方法說明')
        print('=' * 80)
        print()
        print('📊 蒙地卡羅模擬特點:')
        print('  • 基於隨機抽樣的統計方法')
        print('  • 每次運行產生不同結果（隨機性）')
        print('  • 透過大量模擬找出統計上的最佳組合')
        print('  • 考慮號碼出現的機率分布')
        print()
        print('🎯 這8注的優勢:')
        print('  • 每注都是獨立模擬產生，覆蓋不同可能性')
        print('  • 高頻號碼是多次模擬共同看好的號碼')
        print('  • 提供較大的號碼覆蓋範圍')
        print()
        print('⚠️  重要提醒')
        print('   • 蒙地卡羅方法具隨機性，但基於統計原理')
        print('   • 8注提供多樣化覆蓋，但不保證中獎')
        print('   • 投入金額: NT$ 400（8注×50元）')
        print('   • 請理性投注，以娛樂心態參與')
        print()
        print('=' * 80)

        # 計算平均信心度
        avg_confidence = sum(b['confidence'] for b in bets_sorted) / len(bets_sorted)
        print(f'📊 平均信心度: {avg_confidence:.2%}')
        print(f'📅 預測基準: 期號 {history[0]["draw"]} ({history[0]["date"]})')
        print(f'💰 投注金額: NT$ {len(bets_sorted) * 50}')
        print(f'🎲 模擬方法: 蒙地卡羅隨機模擬 (8次獨立運行)')
        print('=' * 80)

    else:
        print(f'⚠️  僅成功生成 {len(bets)} 注預測')

    return bets

if __name__ == '__main__':
    asyncio.run(predict_monte_carlo_8_bets())
