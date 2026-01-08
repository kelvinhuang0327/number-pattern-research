#!/usr/bin/env python3
"""
分析用户提供的8注号码
计算中奖机率和评估质量
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import db_manager
from models.unified_predictor import prediction_engine
from models.entropy_transformer import EntropyTransformerModel
from models.anti_consensus_sampler import DiversityCalculator
from common import get_lottery_rules
from collections import Counter
import numpy as np

# 用户提供的8注号码
USER_BETS = [
    [8, 14, 30, 32, 34, 47],
    [2, 7, 11, 25, 29, 35],
    [15, 23, 26, 27, 30, 41],
    [1, 8, 13, 28, 35, 49],
    [8, 15, 23, 30, 35, 41],
    [2, 11, 30, 32, 41, 49],
    [7, 8, 25, 29, 35, 43],
    [1, 13, 23, 26, 41, 45]
]


def calculate_jackpot_probability():
    """
    计算大樂透头奖机率（理论值）
    """
    # C(49, 6) = 49! / (6! * 43!) = 13,983,816
    from math import comb
    total_combinations = comb(49, 6)
    jackpot_prob = 1 / total_combinations

    return jackpot_prob, total_combinations


def analyze_user_bets():
    """分析用户的8注号码"""

    print('=' * 100)
    print('🎯 用户8注号码分析报告')
    print('=' * 100)
    print()

    # 1. 显示用户号码
    print('📋 您提供的8注号码：')
    print('-' * 100)
    for idx, bet in enumerate(USER_BETS, 1):
        bet_str = ', '.join(f'{n:02d}' for n in sorted(bet))
        print(f'第{idx}注: [{bet_str}]')
    print()

    # 2. 计算头奖机率
    print('=' * 100)
    print('🎲 中奖机率计算')
    print('=' * 100)
    print()

    jackpot_prob, total_combinations = calculate_jackpot_probability()

    print(f'📊 大樂透头奖（6个号码全中）：')
    print(f'   • 单注中奖机率: 1/{total_combinations:,} = {jackpot_prob:.10%}')
    print(f'   • 您的8注中奖机率: 8/{total_combinations:,} = {jackpot_prob*8:.10%}')
    print()

    # 其他奖项机率
    print(f'📊 其他奖项机率（单注）：')

    from math import comb

    # 贰奖：5个号码 + 特别号
    # C(6,5) * C(1,1) * C(42,0) / C(49,6) = 6 / 13,983,816
    second_prize = 6 / total_combinations
    print(f'   • 贰奖（5个+特别号）: 1/{total_combinations//6:,} = {second_prize:.8%}')

    # 参奖：5个号码
    # C(6,5) * C(42,1) / C(49,6) = 252 / 13,983,816
    third_prize = 252 / total_combinations
    print(f'   • 参奖（5个号码）: 1/{int(total_combinations/252):,} = {third_prize:.6%}')

    # 肆奖：4个号码 + 特别号
    fourth_prize = comb(6, 4) * 1 * comb(42, 1) / total_combinations
    print(f'   • 肆奖（4个+特别号）: 1/{int(total_combinations/fourth_prize):,} = {fourth_prize:.5%}')

    # 伍奖：4个号码
    fifth_prize = comb(6, 4) * comb(43, 2) / total_combinations
    print(f'   • 伍奖（4个号码）: 1/{int(total_combinations/fifth_prize):,} = {fifth_prize:.4%}')

    # 柒奖：3个号码
    seventh_prize = comb(6, 3) * comb(43, 3) / total_combinations
    print(f'   • 柒奖（3个号码）: 1/{int(total_combinations/seventh_prize):,} = {seventh_prize:.3%}')

    print()
    print(f'💰 您的8注中任何奖项的总机率约: {(1-(1-seventh_prize)**8)*100:.2f}%')
    print()

    # 3. 号码多样性分析
    print('=' * 100)
    print('📊 号码多样性分析')
    print('=' * 100)
    print()

    DiversityCalculator.print_diversity_report(USER_BETS)

    # 4. 号码频率分析
    print()
    print('=' * 100)
    print('🔥 号码分布分析')
    print('=' * 100)
    print()

    all_numbers = []
    for bet in USER_BETS:
        all_numbers.extend(bet)

    freq = Counter(all_numbers)

    print('📈 高频号码（出现≥3次）：')
    high_freq = {num: count for num, count in freq.items() if count >= 3}
    if high_freq:
        for num, count in sorted(high_freq.items(), key=lambda x: -x[1]):
            bar = '█' * count + '░' * (8 - count)
            print(f'   {num:02d}: {bar} {count}/8注 ({count/8*100:.0f}%)')
    else:
        print('   无')

    print()
    print('📉 单次号码（仅出现1次）：')
    low_freq = [num for num, count in freq.items() if count == 1]
    if low_freq:
        print(f'   {sorted(low_freq)}')
    else:
        print('   无')

    # 5. 与最新历史开奖对比
    print()
    print('=' * 100)
    print('🔍 与历史开奖对比')
    print('=' * 100)
    print()

    all_draws = db_manager.get_all_draws('BIG_LOTTO')
    recent_5 = all_draws[:5]

    print('📅 最近5期开奖号码：')
    for draw in recent_5:
        numbers_str = ', '.join(f'{n:02d}' for n in sorted(draw['numbers']))
        special = draw.get('special', 0)
        special_str = f' + 特別號: {special:02d}' if special else ''
        print(f'   {draw["draw"]} ({draw["date"]}): [{numbers_str}]{special_str}')

    # 计算与最近5期的重叠度
    print()
    print('🔄 与最近5期的号码重叠分析：')

    recent_numbers = set()
    for draw in recent_5:
        recent_numbers.update(draw['numbers'])

    user_numbers = set(all_numbers)
    overlap = user_numbers.intersection(recent_numbers)

    print(f'   您的号码中有 {len(overlap)}/{len(user_numbers)} 个出现在最近5期')
    print(f'   重叠号码: {sorted(list(overlap))}')

    # 6. 载入模型评估
    print()
    print('=' * 100)
    print('🤖 AI模型评估')
    print('=' * 100)
    print()

    history = all_draws[:100]
    lottery_rules = get_lottery_rules('BIG_LOTTO')

    print('🧠 使用熵驱动 Transformer 模型评估您的号码...')
    model = EntropyTransformerModel(max_num=49)
    probs = model.predict(history)

    # 计算每注的模型评分
    print()
    print('📊 每注的AI模型评分（基于12维特征）：')
    print('-' * 100)

    bet_scores = []
    for idx, bet in enumerate(USER_BETS, 1):
        # 计算这注的平均概率
        bet_prob = sum(probs[num - 1] for num in bet) / len(bet)
        bet_scores.append({
            'idx': idx,
            'bet': bet,
            'score': bet_prob
        })

    # 排序
    bet_scores.sort(key=lambda x: -x['score'])

    for rank, item in enumerate(bet_scores, 1):
        bet_str = ', '.join(f'{n:02d}' for n in sorted(item['bet']))
        score = item['score'] * 100

        # 评级
        if score > 2.5:
            rating = '⭐⭐⭐ 优秀'
        elif score > 2.0:
            rating = '⭐⭐ 良好'
        elif score > 1.5:
            rating = '⭐ 中等'
        else:
            rating = '💫 一般'

        print(f'{rank}. 第{item["idx"]}注 [{bet_str}]')
        print(f'   AI评分: {score:.2f}% | 评级: {rating}')
        print()

    # 7. 与熵方法预测对比
    print('=' * 100)
    print('🔬 与熵驱动预测对比')
    print('=' * 100)
    print()

    # 获取熵方法预测
    entropy_result = prediction_engine.entropy_transformer_predict(history, lottery_rules)
    entropy_nums = set(entropy_result['numbers'])

    print(f'🆕 熵驱动方法推荐: {sorted(list(entropy_nums))}')
    print()

    # 计算每注与熵方法的相似度
    print('📊 您的号码与熵方法的相似度：')
    for idx, bet in enumerate(USER_BETS, 1):
        overlap_count = len(set(bet).intersection(entropy_nums))
        bet_str = ', '.join(f'{n:02d}' for n in sorted(bet))

        similarity_mark = '✓✓✓' if overlap_count >= 4 else '✓✓' if overlap_count >= 3 else '✓' if overlap_count >= 2 else '○'

        print(f'   第{idx}注 [{bet_str}]: {overlap_count}/6 匹配 {similarity_mark}')

    # 8. 总结建议
    print()
    print('=' * 100)
    print('💡 总结与建议')
    print('=' * 100)
    print()

    diversity_score = DiversityCalculator.calculate_diversity_score(USER_BETS)
    coverage_rate = DiversityCalculator.calculate_coverage_rate(USER_BETS)

    print(f'✅ 您的8注号码质量评估：')
    print(f'   • 多样性分数: {diversity_score:.3f} {"(优秀)" if diversity_score > 0.5 else "(良好)" if diversity_score > 0.4 else "(中等)"}')
    print(f'   • 覆盖率: {coverage_rate*100:.1f}%')
    print(f'   • 号码重复度: {"低" if len(high_freq) <= 2 else "中" if len(high_freq) <= 4 else "高"}')
    print()

    if diversity_score > 0.5:
        print('🌟 您的号码选择具有良好的多样性，覆盖面广！')
    else:
        print('⚠️  建议增加号码多样性，避免过多重复号码')

    print()
    print('🎯 投注建议：')
    print('   • 大樂透是纯随机游戏，每注中头奖机率都是 1/13,983,816')
    print('   • 多样性高的8注可以提高中小奖的机会')
    print('   • 但请记住：彩券是娱乐，理性投注最重要')
    print()

    print('=' * 100)
    print('✅ 分析完成！祝您好运！')
    print('=' * 100)


if __name__ == '__main__':
    analyze_user_bets()
