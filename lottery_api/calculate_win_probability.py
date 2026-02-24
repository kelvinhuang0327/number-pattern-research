#!/usr/bin/env python3
"""
計算今彩539中獎機率
分析要達到50%以上中獎率需要購買多少注
"""
import math
from itertools import combinations

def calculate_combination(n, r):
    """計算組合數 C(n, r)"""
    return math.comb(n, r)

def calculate_match_probability(total_numbers, pick_count, match_count):
    """
    計算中獎機率
    total_numbers: 總號碼數（今彩539為39）
    pick_count: 每注選幾個號碼（今彩539為5）
    match_count: 要中幾個號碼
    """
    # 總共有多少種組合
    total_combinations = calculate_combination(total_numbers, pick_count)

    # 中match_count個號碼的組合數
    # = C(5, match_count) * C(34, 5-match_count)
    # 5個號碼中選match_count個中獎，34個號碼中選(5-match_count)個不中獎
    winning_combinations = (
        calculate_combination(pick_count, match_count) *
        calculate_combination(total_numbers - pick_count, pick_count - match_count)
    )

    probability = winning_combinations / total_combinations
    return probability, total_combinations, winning_combinations

def calculate_cumulative_probability(single_prob, num_bets):
    """
    計算買num_bets注後至少中一次的機率
    P(至少中一次) = 1 - P(全部不中)
    P(全部不中) = (1 - p)^n
    """
    prob_all_miss = (1 - single_prob) ** num_bets
    prob_at_least_one = 1 - prob_all_miss
    return prob_at_least_one

def main():
    print('=' * 80)
    print('🎯 今彩539中獎機率計算器')
    print('=' * 80)
    print()

    # 今彩539參數
    total_numbers = 39  # 號碼範圍 1-39
    pick_count = 5      # 每注選5個號碼

    print(f'遊戲規則:')
    print(f'  • 號碼範圍: 1-{total_numbers}')
    print(f'  • 每注選擇: {pick_count} 個號碼')
    print()

    # 計算各種中獎機率
    print('=' * 80)
    print('📊 單注中獎機率')
    print('=' * 80)
    print()

    match_levels = [
        (5, '頭獎（5個全中）'),
        (4, '貳獎（4個號碼）'),
        (3, '參獎（3個號碼）'),
        (2, '肆獎（2個號碼）'),
    ]

    probabilities = {}

    for match_count, prize_name in match_levels:
        prob, total_comb, winning_comb = calculate_match_probability(
            total_numbers, pick_count, match_count
        )
        probabilities[match_count] = prob

        print(f'{prize_name}:')
        print(f'  中獎組合數: {winning_comb:,}')
        print(f'  總組合數: {total_comb:,}')
        print(f'  中獎機率: {prob:.6%} (約 1/{int(1/prob):,})')
        print()

    # 重點分析：中3個號碼（參獎）
    print('=' * 80)
    print('🎯 重點分析：達到50%以上機率中3個號碼需要買幾注？')
    print('=' * 80)
    print()

    target_match = 3
    target_prob = 0.50  # 50%
    single_prob = probabilities[target_match]

    print(f'單注中3個號碼的機率: {single_prob:.6%}')
    print()

    # 計算需要的注數
    print('購買不同注數的累積中獎機率:')
    print('-' * 80)
    print(f'{"注數":>6s} | {"累積中獎機率":>15s} | {"需投入金額":>12s} | {"狀態"}')
    print('-' * 80)

    bet_price = 50  # 今彩539每注50元
    found_target = False
    target_bets = 0

    # 測試不同注數
    test_bets = [1, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100,
                 120, 150, 200, 250, 300, 350, 400, 450, 500]

    for num_bets in test_bets:
        cumulative_prob = calculate_cumulative_probability(single_prob, num_bets)
        total_cost = num_bets * bet_price

        if cumulative_prob >= target_prob and not found_target:
            status = '✅ 達標'
            found_target = True
            target_bets = num_bets
        elif cumulative_prob >= 0.90:
            status = '🔥 高機率'
        elif cumulative_prob >= target_prob:
            status = '✅'
        else:
            status = ''

        print(f'{num_bets:6d} | {cumulative_prob:14.2%} | NT$ {total_cost:8,} | {status}')

    print('-' * 80)
    print()

    # 結論
    print('=' * 80)
    print('💡 結論與建議')
    print('=' * 80)
    print()

    if target_bets > 0:
        cumulative_prob_target = calculate_cumulative_probability(single_prob, target_bets)
        total_cost_target = target_bets * bet_price

        print(f'✅ 要達到50%以上機率中3個號碼：')
        print(f'   • 需要購買: {target_bets} 注')
        print(f'   • 投入金額: NT$ {total_cost_target:,}')
        print(f'   • 達成機率: {cumulative_prob_target:.2%}')
        print()

    # 計算各種目標機率需要的注數
    print('不同目標機率所需注數:')
    print('-' * 80)
    print(f'{"目標機率":>10s} | {"所需注數":>10s} | {"投入金額":>12s}')
    print('-' * 80)

    target_probs = [0.30, 0.50, 0.70, 0.90, 0.95, 0.99]

    for target_p in target_probs:
        # 使用數學公式反推: n = ln(1-P) / ln(1-p)
        if target_p < 1.0:
            required_bets = math.ceil(
                math.log(1 - target_p) / math.log(1 - single_prob)
            )
            total_cost = required_bets * bet_price
            print(f'{target_p:9.0%} | {required_bets:10d} | NT$ {total_cost:8,}')

    print('-' * 80)
    print()

    # 參獎實際期望值分析
    print('=' * 80)
    print('📊 期望值分析（參獎獎金以200元計算）')
    print('=' * 80)
    print()

    prize_money = 200  # 假設參獎獎金200元

    print(f'如果購買 {target_bets} 注（投入 NT$ {target_bets * bet_price:,}）:')
    print()

    expected_wins = target_bets * single_prob
    expected_return = expected_wins * prize_money
    expected_loss = (target_bets * bet_price) - expected_return
    roi = (expected_return / (target_bets * bet_price) - 1) * 100

    print(f'  • 預期中獎次數: {expected_wins:.2f} 次')
    print(f'  • 預期獎金收入: NT$ {expected_return:,.0f}')
    print(f'  • 預期虧損: NT$ {expected_loss:,.0f}')
    print(f'  • 投資報酬率: {roi:.1f}%')
    print()

    # 重要提醒
    print('=' * 80)
    print('⚠️  重要提醒')
    print('=' * 80)
    print()
    print('1. 以上計算基於數學機率，實際結果仍有隨機性')
    print('2. 50%機率表示「長期來說」有一半機會中獎，單次仍可能不中')
    print('3. 彩券的期望值通常為負（長期會虧損）')
    print('4. 購買彩券應以娛樂為主，切勿過度投資')
    print('5. 即使購買大量彩券，中獎仍非必然')
    print()

    # 實際策略建議
    print('=' * 80)
    print('💡 實際策略建議')
    print('=' * 80)
    print()
    print('如果目標是提高中獎機會:')
    print('  ✓ 建議購買 5-10 注（投入 NT$ 250-500）')
    print('  ✓ 使用不同預測方法生成多樣化號碼組合')
    print('  ✓ 不要購買重複或相似的號碼組合')
    print('  ✓ 中3個號碼機率約 10-20%（比較實際的期望）')
    print()
    print(f'如果堅持要達到50%機率:')
    print(f'  ⚠️  需投入 NT$ {target_bets * bet_price:,}（{target_bets}注）')
    print(f'  ⚠️  但期望虧損約 NT$ {expected_loss:,.0f}')
    print(f'  ⚠️  不建議單次投入過多資金')
    print()
    print('=' * 80)

if __name__ == '__main__':
    main()
