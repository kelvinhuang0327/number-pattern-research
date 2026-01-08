#!/usr/bin/env python3
"""
測試雙注預測是否涵蓋所有遊戲類型
"""
import sys
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery-api')

from config import lottery_config

def test_double_bet_coverage():
    print('=' * 70)
    print('🎯 測試雙注預測模式是否涵蓋所有遊戲類型')
    print('=' * 70)
    print()

    all_types = lottery_config.get_all_types()

    issues = []
    warnings = []

    for type_id, rules in all_types.items():
        pick_count = rules.pickCount
        is_sub = getattr(rules, 'isSubGame', False)
        play_modes = getattr(rules, 'playModes', None)
        repeats_allowed = getattr(rules, 'repeatsAllowed', False)
        is_permutation = getattr(rules, 'isPermutation', False)
        min_num = rules.minNumber
        max_num = rules.maxNumber

        # 計算雙注需要的號碼數量
        double_bet_needs = pick_count * 2
        available_numbers = max_num - min_num + 1

        print(f'📊 {type_id} ({rules.name})')
        print(f'   號碼範圍: {min_num}~{max_num} ({available_numbers} 個)')
        print(f'   單注需要: {pick_count} 個號碼')
        print(f'   雙注需要: {double_bet_needs} 個號碼')

        # 檢查是否有足夠號碼支援雙注
        if is_permutation:
            # 排列型遊戲（可重複）
            print(f'   ✅ 排列型遊戲，號碼可重複，雙注可行')
        elif repeats_allowed:
            print(f'   ✅ 允許重複號碼，雙注可行')
        elif available_numbers >= double_bet_needs:
            print(f'   ✅ 號碼充足 ({available_numbers} >= {double_bet_needs})，雙注可行')
        elif available_numbers >= pick_count:
            ratio = available_numbers / pick_count
            print(f'   ⚠️  號碼有限 (比率: {ratio:.1f}x)，雙注可能重複')
            warnings.append(f'{type_id}: 號碼數量有限，雙注可能有部分重複')
        else:
            print(f'   ❌ 號碼不足，無法組成一注')
            issues.append(f'{type_id}: 可用號碼 ({available_numbers}) < 單注需求 ({pick_count})')

        # 檢查樂合彩多玩法
        if is_sub and play_modes:
            print(f'   📌 子遊戲（依附: {getattr(rules, "dependsOn", "N/A")}），支援多玩法：')
            for mode_name, mode in play_modes.items():
                mode_pick = mode.pickCount
                mode_double = mode_pick * 2

                if available_numbers >= mode_double:
                    print(f'      ✅ {mode_name} ({mode_pick}個號碼): 雙注可行 ({mode_double} <= {available_numbers})')
                else:
                    print(f'      ⚠️  {mode_name} ({mode_pick}個號碼): 號碼有限 ({mode_double} vs {available_numbers})')

        print()

    print('=' * 70)
    print('📝 總結報告')
    print('=' * 70)

    if not issues and not warnings:
        print('✅ 所有遊戲類型都完整支援雙注預測模式！')
    else:
        if issues:
            print(f'❌ 發現 {len(issues)} 個問題：')
            for issue in issues:
                print(f'   - {issue}')
            print()

        if warnings:
            print(f'⚠️  發現 {len(warnings)} 個警告：')
            for warning in warnings:
                print(f'   - {warning}')
            print()

    # 特別說明
    print('💡 說明：')
    print('   - 賓果賓果 (20個號碼): 雙注共需40個，可用80個，完全足夠')
    print('   - 雙贏彩 (12個號碼): 雙注共需24個，正好可用24個，剛好足夠')
    print('   - 今彩539 (5個號碼): 雙注共需10個，可用39個，充足')
    print('   - 大樂透 (6個號碼): 雙注共需12個，可用49個，充足')
    print('   - 星彩系列: 允許重複且為排列型，完全支援雙注')
    print()

    return len(issues) == 0

if __name__ == '__main__':
    success = test_double_bet_coverage()
    sys.exit(0 if success else 1)
