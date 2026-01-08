#!/usr/bin/env python3
"""
測試玩法模式驗證邏輯
"""
import sys
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery-api')

from config import lottery_config
from utils.csv_validator import csv_validator

def test_play_mode_validation():
    print('=' * 60)
    print('🧪 測試玩法模式驗證邏輯')
    print('=' * 60)
    print()

    # 測試案例
    test_cases = [
        # (lottery_type, play_mode, should_pass, description)
        ('39_LOTTO', '二合', True, '39樂合彩 + 二合'),
        ('39_LOTTO', '三合', True, '39樂合彩 + 三合'),
        ('39_LOTTO', '四合', True, '39樂合彩 + 四合'),
        ('39_LOTTO', None, False, '39樂合彩 + 無玩法'),
        ('39_LOTTO', '五合', False, '39樂合彩 + 無效玩法'),

        ('49_LOTTO', '二合', True, '49樂合彩 + 二合'),
        ('49_LOTTO', '三合', True, '49樂合彩 + 三合'),
        ('49_LOTTO', '四合', True, '49樂合彩 + 四合'),

        ('38_LOTTO', '二合', True, '38樂合彩 + 二合'),
        ('38_LOTTO', '三合', True, '38樂合彩 + 三合'),
        ('38_LOTTO', '四合', True, '38樂合彩 + 四合'),

        ('BIG_LOTTO', None, True, '大樂透 + 無玩法'),
        ('BIG_LOTTO', '二合', False, '大樂透 + 不支援玩法'),

        ('DAILY_539', None, True, '今彩539 + 無玩法'),
        ('DAILY_539', '二合', False, '今彩539 + 不支援玩法'),
    ]

    passed = 0
    failed = 0

    for lottery_type, play_mode, should_pass, description in test_cases:
        is_valid, error_msg = csv_validator._validate_play_mode(lottery_type, play_mode)

        if is_valid == should_pass:
            print(f'✅ PASS: {description}')
            if not is_valid:
                print(f'   → 錯誤訊息: {error_msg}')
            passed += 1
        else:
            print(f'❌ FAIL: {description}')
            print(f'   → 預期: {"通過" if should_pass else "失敗"}')
            print(f'   → 實際: {"通過" if is_valid else "失敗"}')
            if error_msg:
                print(f'   → 錯誤訊息: {error_msg}')
            failed += 1

    print()
    print('=' * 60)
    print(f'測試結果: {passed} 通過, {failed} 失敗')
    print('=' * 60)

    return failed == 0

def test_effective_pick_count():
    print()
    print('=' * 60)
    print('🧪 測試有效號碼選取數量')
    print('=' * 60)
    print()

    test_cases = [
        ('39_LOTTO', '二合', 2),
        ('39_LOTTO', '三合', 3),
        ('39_LOTTO', '四合', 4),
        ('39_LOTTO', None, 5),  # 默認主遊戲pickCount

        ('49_LOTTO', '二合', 2),
        ('49_LOTTO', '三合', 3),
        ('49_LOTTO', '四合', 4),

        ('38_LOTTO', '二合', 2),
        ('38_LOTTO', '三合', 3),
        ('38_LOTTO', '四合', 4),

        ('BIG_LOTTO', None, 6),
        ('DAILY_539', None, 5),
        ('3_STAR', None, 3),
        ('4_STAR', None, 4),
    ]

    passed = 0
    failed = 0

    for lottery_type, play_mode, expected_count in test_cases:
        rules = lottery_config.get_rules(lottery_type)
        if not rules:
            print(f'❌ 找不到規則: {lottery_type}')
            failed += 1
            continue

        actual_count = csv_validator._get_effective_pick_count(rules, play_mode)

        if actual_count == expected_count:
            mode_str = f' ({play_mode})' if play_mode else ''
            print(f'✅ {lottery_type}{mode_str}: {actual_count} 個號碼')
            passed += 1
        else:
            print(f'❌ {lottery_type} + {play_mode}: 預期 {expected_count}, 實際 {actual_count}')
            failed += 1

    print()
    print('=' * 60)
    print(f'測試結果: {passed} 通過, {failed} 失敗')
    print('=' * 60)

    return failed == 0

if __name__ == '__main__':
    success1 = test_play_mode_validation()
    success2 = test_effective_pick_count()

    print()
    if success1 and success2:
        print('🎉 所有測試通過！')
        sys.exit(0)
    else:
        print('⚠️  部分測試失敗')
        sys.exit(1)
