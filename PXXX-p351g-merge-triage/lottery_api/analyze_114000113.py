#!/usr/bin/env python3
"""
分析114000113期的预测结果
比对八注预测号码与实际开奖号码
"""

# 实际开奖号码：15, 17, 24, 26, 40, 47 + 33（特别号）
ACTUAL_NUMBERS = [15, 17, 24, 26, 40, 47]
ACTUAL_SPECIAL = 33

# 八注预测（来自predict_biglotto_8_bets.py的输出）
PREDICTIONS = [
    {
        'method': '頻率分析',
        'numbers': [7, 13, 25, 29, 37, 39],
        'confidence': 84.83
    },
    {
        'method': '貝葉斯機率',
        'numbers': [7, 13, 25, 33, 37, 39],
        'confidence': 79.48
    },
    {
        'method': '趨勢分析',
        'numbers': [7, 13, 25, 29, 30, 39],
        'confidence': 75.00
    },
    {
        'method': '熱冷號混合',
        'numbers': [7, 13, 25, 29, 33, 40],
        'confidence': 73.20
    },
    {
        'method': '蒙地卡羅模擬',
        'numbers': [2, 7, 13, 20, 25, 41],
        'confidence': 72.00
    },
    {
        'method': '區域平衡',
        'numbers': [2, 7, 13, 20, 25, 29],
        'confidence': 69.65
    },
    {
        'method': '優化集成-第1組',
        'numbers': [2, 7, 13, 20, 25, 29],
        'confidence': 66.33
    },
    {
        'method': '優化集成-第2組',
        'numbers': [12, 26, 33, 34, 37, 39],
        'confidence': 21.76
    }
]

def analyze_match(predicted, actual, special):
    """分析预测号码与实际号码的匹配度"""
    predicted_set = set(predicted)
    actual_set = set(actual)

    # 一般号码匹配
    normal_matches = predicted_set.intersection(actual_set)

    # 特别号匹配
    special_match = special in predicted_set

    # 总匹配数
    total_matches = len(normal_matches)

    return {
        'normal_matches': sorted(list(normal_matches)),
        'normal_count': len(normal_matches),
        'special_match': special_match,
        'total_matches': total_matches
    }

def get_prize_info(normal_count, has_special):
    """根据匹配数返回中奖信息"""
    if normal_count == 6:
        return '🏆 頭獎 - 6個號碼全中'
    elif normal_count == 5 and has_special:
        return '🥈 貳獎 - 5個號碼 + 特別號'
    elif normal_count == 5:
        return '🥉 參獎 - 5個號碼'
    elif normal_count == 4 and has_special:
        return '🎖️ 肆獎 - 4個號碼 + 特別號'
    elif normal_count == 4:
        return '🎖️ 伍獎 - 4個號碼'
    elif normal_count == 3 and has_special:
        return '🎫 陸獎 - 3個號碼 + 特別號'
    elif normal_count == 3:
        return '🎫 柒獎 - 3個號碼'
    elif normal_count == 2 and has_special:
        return '🎁 普獎 - 2個號碼 + 特別號'
    else:
        return '❌ 未中獎'

print('=' * 100)
print('🎯 114000113期預測結果分析')
print('=' * 100)
print()
print(f'📊 實際開獎號碼: {", ".join(f"{n:02d}" for n in sorted(ACTUAL_NUMBERS))} + 特別號: {ACTUAL_SPECIAL:02d}')
print()
print('=' * 100)
print('📈 各方法預測結果比對')
print('=' * 100)
print()

results = []
for idx, pred in enumerate(PREDICTIONS, 1):
    match_result = analyze_match(pred['numbers'], ACTUAL_NUMBERS, ACTUAL_SPECIAL)
    prize_info = get_prize_info(match_result['normal_count'], match_result['special_match'])

    results.append({
        'idx': idx,
        'method': pred['method'],
        'numbers': pred['numbers'],
        'confidence': pred['confidence'],
        'match_count': match_result['normal_count'],
        'matched_numbers': match_result['normal_matches'],
        'has_special': match_result['special_match'],
        'prize': prize_info
    })

    numbers_str = ', '.join(f'{n:02d}' for n in sorted(pred['numbers']))
    matched_str = ', '.join(f'{n:02d}' for n in match_result['normal_matches']) if match_result['normal_matches'] else '無'
    special_str = f' + 特別號{ACTUAL_SPECIAL:02d}' if match_result['special_match'] else ''

    print(f'第{idx}注 [{pred["method"]:15s}] 信心度: {pred["confidence"]:5.2f}%')
    print(f'   預測號碼: [{numbers_str}]')
    print(f'   匹配號碼: [{matched_str}]{special_str}')
    print(f'   匹配數量: {match_result["normal_count"]}/6')
    print(f'   中獎結果: {prize_info}')
    print()

print('=' * 100)
print('🏆 綜合分析')
print('=' * 100)
print()

# 按匹配数排序
results_sorted = sorted(results, key=lambda x: (-x['match_count'], -int(x['has_special']), -x['confidence']))

print('📊 按匹配度排序:')
print('-' * 100)
for rank, r in enumerate(results_sorted, 1):
    numbers_str = ', '.join(f'{n:02d}' for n in sorted(r['numbers']))
    matched_str = ', '.join(f'{n:02d}' for n in r['matched_numbers']) if r['matched_numbers'] else '無'
    special_mark = '✓' if r['has_special'] else '✗'

    print(f'{rank}. {r["method"]:15s} - {r["match_count"]}/6匹配 | 特別號:{special_mark} | 信心度:{r["confidence"]:.2f}%')
    print(f'   預測: [{numbers_str}]')
    print(f'   中獎: {r["prize"]}')
    if r['matched_numbers']:
        print(f'   匹配號碼: {matched_str}')
    print()

# 统计
max_matches = max(r['match_count'] for r in results)
best_methods = [r for r in results if r['match_count'] == max_matches]

print('=' * 100)
print('💡 結論')
print('=' * 100)
print()

if max_matches == 0:
    print('❌ 所有方法都未能預測中任何一般號碼')
    special_methods = [r for r in results if r['has_special']]
    if special_methods:
        print(f'\n⭐ 但以下方法預測到了特別號 {ACTUAL_SPECIAL:02d}:')
        for r in special_methods:
            print(f'   • {r["method"]} (信心度: {r["confidence"]:.2f}%)')
else:
    print(f'🎯 最佳預測方法（{max_matches}個號碼匹配）:')
    for r in best_methods:
        numbers_str = ', '.join(f'{n:02d}' for n in sorted(r['numbers']))
        matched_str = ', '.join(f'{n:02d}' for n in r['matched_numbers'])
        special_mark = f' + 特別號{ACTUAL_SPECIAL:02d}' if r['has_special'] else ''
        print(f'\n   • {r["method"]}')
        print(f'     信心度: {r["confidence"]:.2f}%')
        print(f'     預測號碼: [{numbers_str}]')
        print(f'     匹配號碼: [{matched_str}]{special_mark}')
        print(f'     中獎結果: {r["prize"]}')

# 号码频率分析
print('\n' + '=' * 100)
print('📊 預測號碼頻率 vs 實際開獎號碼')
print('=' * 100)
print()

from collections import Counter
all_predicted = []
for pred in PREDICTIONS:
    all_predicted.extend(pred['numbers'])

predicted_freq = Counter(all_predicted)
actual_with_special = ACTUAL_NUMBERS + [ACTUAL_SPECIAL]

print('🔥 預測高頻號碼（出現≥3次）:')
high_freq = [(num, count) for num, count in predicted_freq.most_common() if count >= 3]
for num, count in high_freq:
    in_actual = '✅ 開出' if num in actual_with_special else '❌ 未開'
    bar = '█' * count + '░' * (8 - count)
    print(f'   {num:02d}: {bar} {count}/8注 {in_actual}')

print(f'\n📋 實際開獎號碼: {", ".join(f"{n:02d}" for n in sorted(ACTUAL_NUMBERS))} + 特別號: {ACTUAL_SPECIAL:02d}')

print('\n🔍 開獎號碼在預測中的出現次數:')
for num in sorted(actual_with_special):
    count = predicted_freq.get(num, 0)
    if count > 0:
        percentage = (count / 8) * 100
        mark = '⭐' if count >= 3 else '○'
        special_mark = ' (特別號)' if num == ACTUAL_SPECIAL else ''
        print(f'   {mark} {num:02d}{special_mark}: 出現在 {count}/8 注預測中 ({percentage:.0f}%)')
    else:
        special_mark = ' (特別號)' if num == ACTUAL_SPECIAL else ''
        print(f'   ✗ {num:02d}{special_mark}: 未出現在任何預測中')

print()
print('=' * 100)
print('✅ 分析完成')
print('=' * 100)
