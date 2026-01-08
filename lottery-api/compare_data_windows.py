#!/usr/bin/env python3
"""
比較不同數據窗口大小對預測結果的影響
"""
import sys
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery-api')

from database import db_manager
from models.unified_predictor import prediction_engine
from common import get_lottery_rules

def compare_windows():
    print('=' * 80)
    print('🔍 數據窗口大小對預測結果的影響分析')
    print('=' * 80)
    print()

    all_draws = db_manager.get_all_draws('BIG_LOTTO')
    lottery_rules = get_lottery_rules('BIG_LOTTO')

    windows = [50, 100, 200, 500, 1000, 2000]

    print(f'資料庫總期數: {len(all_draws)}')
    print()

    results = {}

    for window_size in windows:
        if window_size > len(all_draws):
            continue

        print(f'📊 使用最近 {window_size} 期數據...')
        history = all_draws[:window_size]

        try:
            # 頻率分析
            freq_result = prediction_engine.frequency_predict(history, lottery_rules)
            freq_numbers = sorted(freq_result['numbers'])

            results[window_size] = {
                'numbers': freq_numbers,
                'confidence': freq_result.get('confidence', 0),
                'date_range': f'{history[-1]["date"]} ~ {history[0]["date"]}'
            }

            numbers_str = ', '.join(f'{n:02d}' for n in freq_numbers)
            print(f'   預測號碼: {numbers_str}')
            print(f'   信心度: {freq_result.get("confidence", 0):.2%}')
            print(f'   時間範圍: {history[-1]["date"]} ~ {history[0]["date"]}')
            print()

        except Exception as e:
            print(f'   ❌ 錯誤: {str(e)}')
            print()

    # 比較結果
    print('=' * 80)
    print('📈 結果比較分析')
    print('=' * 80)
    print()

    # 統計各號碼出現次數
    all_numbers = {}
    for window_size, data in results.items():
        for num in data['numbers']:
            if num not in all_numbers:
                all_numbers[num] = []
            all_numbers[num].append(window_size)

    # 顯示穩定號碼（在多個窗口都出現）
    stable_numbers = {num: windows for num, windows in all_numbers.items() if len(windows) >= 4}

    if stable_numbers:
        print('🔥 穩定號碼（在4個以上窗口都出現）:')
        for num in sorted(stable_numbers.keys()):
            window_list = ', '.join(str(w) for w in stable_numbers[num])
            print(f'   {num:02d} - 出現在窗口: {window_list}')
        print()

    # 顯示短期熱門（僅在小窗口出現）
    short_term = {num: windows for num, windows in all_numbers.items()
                  if len(windows) <= 2 and min(windows) <= 100}

    if short_term:
        print('⚡ 短期熱門（僅在小窗口出現）:')
        for num in sorted(short_term.keys()):
            window_list = ', '.join(str(w) for w in short_term[num])
            print(f'   {num:02d} - 僅出現在窗口: {window_list}')
        print()

    # 顯示長期穩定（僅在大窗口出現）
    long_term = {num: windows for num, windows in all_numbers.items()
                 if len(windows) <= 2 and min(windows) >= 500}

    if long_term:
        print('📊 長期穩定（僅在大窗口出現）:')
        for num in sorted(long_term.keys()):
            window_list = ', '.join(str(w) for w in long_term[num])
            print(f'   {num:02d} - 僅出現在窗口: {window_list}')
        print()

    print('=' * 80)
    print('💡 結論')
    print('=' * 80)
    print()
    print('✓ 不同數據窗口會產生不同的預測結果')
    print('✓ 小窗口（50-100期）：反映短期趨勢，變化快')
    print('✓ 大窗口（1000-2000期）：反映長期平均，較穩定')
    print('✓ 這就是為什麼不同AI agent的預測結果會有差異')
    print()
    print('=' * 80)

if __name__ == '__main__':
    compare_windows()
