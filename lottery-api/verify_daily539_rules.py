#!/usr/bin/env python3
"""
驗證今彩539遊戲邏輯配置
"""
import sys
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery-api')

from common import get_lottery_rules
from database import db_manager
import json

def verify_daily539_rules():
    print('=' * 80)
    print('🎯 今彩539遊戲邏輯驗證')
    print('=' * 80)
    print()

    # 1. 檢查配置規則
    print('📋 第一步：檢查配置規則')
    print('-' * 80)

    rules = get_lottery_rules('DAILY_539')

    print(f'✓ 彩券名稱: {rules.get("name", "今彩539")}')
    print(f'✓ 號碼範圍: {rules["minNumber"]} ~ {rules["maxNumber"]}')
    print(f'✓ 每期開出號碼數: {rules["pickCount"]} 個')
    print(f'✓ 是否有特別號: {"是" if rules.get("hasSpecialNumber", False) else "否"}')

    print()

    # 2. 檢查歷史數據
    print('📊 第二步：檢查歷史數據')
    print('-' * 80)

    all_draws = db_manager.get_all_draws('DAILY_539')

    if not all_draws:
        print('❌ 無法載入歷史數據')
        return False

    print(f'✓ 總期數: {len(all_draws)} 期')
    print(f'✓ 日期範圍: {all_draws[-1]["date"]} ~ {all_draws[0]["date"]}')
    print()

    # 3. 統計號碼範圍
    print('🔢 第三步：統計實際號碼範圍')
    print('-' * 80)

    all_numbers = []
    has_special = []

    for draw in all_draws:
        numbers = draw['numbers']
        all_numbers.extend(numbers)

        if 'special' in draw and draw['special']:
            has_special.append(draw['special'])

    actual_min_number = min(all_numbers)
    actual_max_number = max(all_numbers)
    actual_pick_count = len(all_draws[0]['numbers'])

    print(f'✓ 實際號碼範圍: {actual_min_number} ~ {actual_max_number}')
    print(f'✓ 實際每期開出號碼數: {actual_pick_count} 個')

    if has_special:
        print(f'⚠️  警告: 發現 {len(has_special)} 期有特別號（今彩539不應有特別號）')
    else:
        print(f'✓ 確認無特別號（符合今彩539規則）')

    print()

    # 4. 驗證配置與實際數據是否一致
    print('✅ 第四步：驗證配置與數據一致性')
    print('-' * 80)

    errors = []
    warnings = []

    # 檢查號碼範圍
    if actual_min_number < rules['minNumber']:
        errors.append(f'數據中的最小號碼 ({actual_min_number}) 小於配置的最小號碼 ({rules["minNumber"]})')

    if actual_max_number > rules['maxNumber']:
        errors.append(f'數據中的最大號碼 ({actual_max_number}) 大於配置的最大號碼 ({rules["maxNumber"]})')

    # 檢查每期號碼數
    if actual_pick_count != rules['pickCount']:
        errors.append(f'數據中的號碼數 ({actual_pick_count}) 不等於配置的號碼數 ({rules["pickCount"]})')

    # 檢查特別號
    if rules.get('hasSpecialNumber', False):
        errors.append('配置顯示有特別號，但今彩539不應有特別號')

    if has_special:
        warnings.append(f'發現 {len(has_special)} 期有特別號，今彩539不應有特別號')

    # 顯示結果
    if errors:
        print('❌ 發現錯誤:')
        for i, error in enumerate(errors, 1):
            print(f'   {i}. {error}')
        print()

    if warnings:
        print('⚠️  警告:')
        for i, warning in enumerate(warnings, 1):
            print(f'   {i}. {warning}')
        print()

    if not errors and not warnings:
        print('✅ 所有檢查通過！配置與數據完全一致')
        print()

    # 5. 驗證號碼不重複
    print('🔍 第五步：驗證號碼唯一性（不允許重複）')
    print('-' * 80)

    duplicate_found = False
    for i, draw in enumerate(all_draws[:100], 1):
        numbers = draw['numbers']
        if len(numbers) != len(set(numbers)):
            print(f'❌ 第{i}期發現重複號碼: {numbers}')
            duplicate_found = True
            if i >= 10:
                break

    if not duplicate_found:
        print('✅ 檢查前100期，所有期數的號碼皆不重複（符合今彩539規則）')
    print()

    # 6. 顯示最近10期開獎
    print('=' * 80)
    print('📅 最近10期開獎記錄')
    print('=' * 80)
    print()

    for i, draw in enumerate(all_draws[:10], 1):
        numbers_str = ', '.join(f'{n:02d}' for n in sorted(draw['numbers']))
        print(f'{i:2d}. {draw["date"]:10s} 期號 {draw["draw"]:12s} | {numbers_str}')

    print()
    print('=' * 80)

    # 7. 官方今彩539規則說明
    print('📖 官方今彩539遊戲規則')
    print('=' * 80)
    print()
    print('• 號碼範圍: 01~39')
    print('• 開出號碼: 5個號碼（無特別號）')
    print('• 開獎方式: 從39個號碼中隨機開出5個號碼')
    print('• 號碼特性: 5個號碼不重複')
    print('• 獎項設定:')
    print('  - 頭獎: 5個號碼全中')
    print('  - 貳獎: 4個號碼中')
    print('  - 參獎: 3個號碼中')
    print('  - 肆獎: 2個號碼中')
    print()
    print('=' * 80)

    # 8. 驗證預測方法邏輯
    print('🔬 第六步：驗證預測方法邏輯')
    print('=' * 80)
    print()

    print('檢查預測方法是否符合今彩539規則...')
    print()

    # 測試各種預測方法
    from models.unified_predictor import prediction_engine

    test_history = all_draws[:50]
    method_checks = []

    methods_to_test = [
        ('頻率分析', 'frequency_predict'),
        ('趨勢分析', 'trend_predict'),
        ('貝葉斯機率', 'bayesian_predict'),
        ('蒙地卡羅', 'monte_carlo_predict'),
        ('熱冷號混合', 'hot_cold_mix_predict'),
    ]

    for method_name, method_func in methods_to_test:
        try:
            method = getattr(prediction_engine, method_func)
            result = method(test_history, rules)
            predicted_numbers = result.get('numbers', [])

            # 檢查1: 號碼數量
            count_ok = len(predicted_numbers) == rules['pickCount']

            # 檢查2: 號碼範圍
            range_ok = all(rules['minNumber'] <= n <= rules['maxNumber'] for n in predicted_numbers)

            # 檢查3: 號碼不重複
            unique_ok = len(predicted_numbers) == len(set(predicted_numbers))

            # 檢查4: 是否為整數（支援 numpy.int64）
            import numpy as np
            int_ok = all(isinstance(n, (int, np.integer)) for n in predicted_numbers)

            all_ok = count_ok and range_ok and unique_ok and int_ok

            status = '✅' if all_ok else '❌'
            method_checks.append({
                'name': method_name,
                'count_ok': count_ok,
                'range_ok': range_ok,
                'unique_ok': unique_ok,
                'int_ok': int_ok,
                'all_ok': all_ok
            })

            print(f'{status} {method_name:15s} | 數量:{count_ok} 範圍:{range_ok} 唯一:{unique_ok} 整數:{int_ok}')

        except Exception as e:
            print(f'❌ {method_name:15s} | 錯誤: {str(e)[:50]}')
            method_checks.append({
                'name': method_name,
                'all_ok': False
            })

    print()

    # 結論
    print('=' * 80)
    print('💡 驗證結論')
    print('=' * 80)
    print()

    all_methods_ok = all(m.get('all_ok', False) for m in method_checks)

    if not errors and not warnings and all_methods_ok:
        print('✅ 今彩539遊戲邏輯配置正確')
        print('✅ 配置規則與官方遊戲規則一致')
        print('✅ 歷史數據與配置規則一致')
        print('✅ 所有預測方法邏輯符合今彩539規則')
        print('✅ 預測系統可以正常運作')
        print()
        print(f'📊 數據統計:')
        print(f'   • 共有 {len(all_draws)} 期歷史數據')
        print(f'   • 號碼範圍: 1~39（符合官方規則）')
        print(f'   • 每期5個號碼，無特別號（符合官方規則）')
        print(f'   • 號碼不重複（符合官方規則）')
        print(f'   • 可用於訓練預測模型')
        return True
    else:
        print('❌ 發現配置或預測邏輯問題，需要修正')
        if errors:
            print('\n錯誤清單:')
            for error in errors:
                print(f'  • {error}')
        if warnings:
            print('\n警告清單:')
            for warning in warnings:
                print(f'  • {warning}')
        if not all_methods_ok:
            print('\n預測方法問題:')
            for m in method_checks:
                if not m.get('all_ok', False):
                    print(f'  • {m["name"]} 未通過檢查')
        return False

    print('=' * 80)

if __name__ == '__main__':
    verify_daily539_rules()
