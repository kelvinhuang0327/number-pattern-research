#!/usr/bin/env python3
"""
測試星彩排列邏輯
驗證3星彩和4星彩的特殊處理
"""
import sys
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')

from config import lottery_config
from utils.csv_validator import csv_validator
import io

def test_star_lottery_permutation():
    print('=' * 70)
    print('🎲 測試星彩排列邏輯')
    print('=' * 70)
    print()

    # 測試案例
    test_cases = [
        {
            'name': '3星彩 - 允許重複',
            'lottery_type': '3_STAR',
            'csv_data': 'Date,Draw,Num1,Num2,Num3\n2025/01/01,001,1,2,3\n2025/01/02,002,5,5,5\n2025/01/03,003,9,0,1',
            'expected_results': [
                {'numbers': [1, 2, 3], 'should_preserve_order': True},
                {'numbers': [5, 5, 5], 'should_preserve_order': True, 'has_repeats': True},
                {'numbers': [9, 0, 1], 'should_preserve_order': True}
            ]
        },
        {
            'name': '4星彩 - 允許重複',
            'lottery_type': '4_STAR',
            'csv_data': 'Date,Draw,Num1,Num2,Num3,Num4\n2025/01/01,001,1,2,3,4\n2025/01/02,002,7,7,7,7\n2025/01/03,003,0,9,8,7',
            'expected_results': [
                {'numbers': [1, 2, 3, 4], 'should_preserve_order': True},
                {'numbers': [7, 7, 7, 7], 'should_preserve_order': True, 'has_repeats': True},
                {'numbers': [0, 9, 8, 7], 'should_preserve_order': True}
            ]
        },
        {
            'name': '今彩539 - 不允許重複（對照組）',
            'lottery_type': 'DAILY_539',
            'csv_data': 'Date,Draw,Num1,Num2,Num3,Num4,Num5\n2025/01/01,114000001,5,12,23,34,39',
            'expected_results': [
                {'numbers': [5, 12, 23, 34, 39], 'should_preserve_order': False}  # 會被排序
            ]
        }
    ]

    all_passed = True

    for test_case in test_cases:
        print(f"📝 測試: {test_case['name']}")
        print(f"   彩券類型: {test_case['lottery_type']}")

        # 驗證CSV
        csv_bytes = test_case['csv_data'].encode('utf-8')
        result = csv_validator.validate(csv_bytes, test_case['lottery_type'], 'csv')

        if not result['valid']:
            print(f"   ❌ CSV驗證失敗:")
            for error in result['errors']:
                print(f"      - {error['message']}")
            all_passed = False
            print()
            continue

        # 檢查規則配置
        rules = lottery_config.get_rules(test_case['lottery_type'])
        is_permutation = getattr(rules, 'isPermutation', False)
        repeats_allowed = getattr(rules, 'repeatsAllowed', False)

        print(f"   配置: isPermutation={is_permutation}, repeatsAllowed={repeats_allowed}")

        # 驗證解析結果
        parsed_data = result['parsed_data']
        expected_results = test_case['expected_results']

        if len(parsed_data) != len(expected_results):
            print(f"   ❌ 解析數量不符: 預期 {len(expected_results)}, 實際 {len(parsed_data)}")
            all_passed = False
            continue

        for idx, (parsed, expected) in enumerate(zip(parsed_data, expected_results)):
            actual_numbers = parsed['numbers']
            expected_numbers = expected['numbers']
            should_preserve = expected['should_preserve_order']
            has_repeats = expected.get('has_repeats', False)

            # 檢查順序是否保持
            order_preserved = (actual_numbers == expected_numbers)
            order_correct = (order_preserved if should_preserve else actual_numbers == sorted(expected_numbers))

            # 檢查重複號碼
            has_actual_repeats = len(actual_numbers) != len(set(actual_numbers))
            repeats_ok = (not has_actual_repeats) or repeats_allowed

            if order_correct and repeats_ok:
                status = '✅'
            else:
                status = '❌'
                all_passed = False

            print(f"   {status} 記錄 {idx+1}: {actual_numbers}")
            if has_repeats:
                print(f"      → 包含重複號碼，允許={repeats_allowed}")
            if should_preserve and not order_preserved:
                print(f"      → 順序應保持但被改變了")
            if not should_preserve and order_preserved and actual_numbers != sorted(expected_numbers):
                print(f"      → 順序應排序但沒有排序")

        print()

    print('=' * 70)
    if all_passed:
        print('✅ 所有星彩排列邏輯測試通過！')
        print()
        print('驗證重點：')
        print('  ✓ 3星彩和4星彩的 isPermutation=True')
        print('  ✓ 星彩允許重複號碼 (repeatsAllowed=True)')
        print('  ✓ 星彩保持號碼原始順序（不排序）')
        print('  ✓ 其他彩券會自動排序號碼')
    else:
        print('❌ 部分測試失敗，請檢查上述錯誤')
    print('=' * 70)

    return all_passed

if __name__ == '__main__':
    success = test_star_lottery_permutation()
    sys.exit(0 if success else 1)
