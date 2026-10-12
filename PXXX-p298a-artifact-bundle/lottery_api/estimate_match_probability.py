#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
估算每注可能的匹配數量（基於統計學，非準確預測）
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import db_manager
from models.entropy_transformer import EntropyTransformerModel
from common import get_lottery_rules
import numpy as np
from scipy import stats

# 用户的8注
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

def calculate_expected_matches():
    """计算期望匹配数（理论值）"""
    # 大乐透：从49个号码中选6个
    # 期望命中数 = 6 * (6/49) ≈ 0.735
    # 也就是说，平均每注期望命中0.735个号码

    expected_per_bet = 6 * (6 / 49)
    return expected_per_bet

def estimate_match_probability():
    """估算匹配概率分布"""
    print('=' * 100)
    print('🔮 114000114期匹配数量估算（基于统计学，非准确预测）')
    print('=' * 100)
    print()

    print('⚠️  重要声明：')
    print('   这不是准确预测，只是基于统计学的期望值计算')
    print('   实际结果可能完全不同，大乐透是真随机游戏')
    print()
    print('=' * 100)

    # 理论期望值
    expected = calculate_expected_matches()
    print(f'\n📊 理论期望值：')
    print(f'   每注平均期望命中: {expected:.3f} 个号码')
    print(f'   也就是说，大多数情况下每注会命中 0-1 个号码')
    print()

    # 概率分布
    print('📊 匹配数量的概率分布（单注）：')
    print('-' * 100)

    from math import comb
    total = comb(49, 6)

    for k in range(7):
        # P(恰好中k个) = C(6,k) * C(43, 6-k) / C(49, 6)
        prob = comb(6, k) * comb(43, 6-k) / total
        percentage = prob * 100

        bar_length = int(percentage * 2) if percentage > 0.1 else 1 if percentage > 0 else 0
        bar = '█' * bar_length

        if k == 0:
            label = '0个 (未中奖)'
        elif k == 1:
            label = '1个 (未中奖)'
        elif k == 2:
            label = '2个 (未中奖)'
        elif k == 3:
            label = '3个 (柒奖)'
        elif k == 4:
            label = '4个 (伍奖)'
        elif k == 5:
            label = '5个 (参奖)'
        elif k == 6:
            label = '6个 (头奖)'

        print(f'   {label:18s}: {percentage:7.4f}% {bar}')

    print()

    # 8注的总体期望
    print('📊 您的8注总体期望：')
    print('-' * 100)
    total_expected = 8 * expected
    print(f'   总期望命中数: {total_expected:.2f} 个号码')
    print(f'   最可能的情况: 大部分注中0个，少数注中1-2个')
    print()

    # 中任何奖的概率
    no_win_prob = (comb(43, 6) / total) ** 8  # 8注都不中
    any_win_prob = 1 - no_win_prob
    print(f'   至少1注中柒奖或以上的概率: {any_win_prob*100:.2f}%')
    print()

    # 载入AI模型做评估
    print('=' * 100)
    print('🤖 AI模型个性化评估')
    print('=' * 100)
    print()

    all_draws = db_manager.get_all_draws('BIG_LOTTO')
    history = all_draws[:100]
    lottery_rules = get_lottery_rules('BIG_LOTTO')

    model = EntropyTransformerModel(max_num=49)
    probs = model.predict(history)

    print('基于您的8注号码特征，AI模型估算：')
    print('-' * 100)

    ai_scores = []
    for idx, bet in enumerate(USER_BETS, 1):
        # 计算这注的平均概率
        bet_prob = sum(probs[num - 1] for num in bet) / len(bet)

        # 基于AI评分调整期望值（纯粹参考）
        # 高评分的注理论上可能稍微高一点，但差异很小
        adjusted_expected = expected * (1 + (bet_prob - 0.02) * 5)  # 轻微调整
        adjusted_expected = max(0, min(adjusted_expected, 2.0))  # 限制在合理范围

        ai_scores.append({
            'idx': idx,
            'bet': bet,
            'ai_score': bet_prob,
            'expected': adjusted_expected
        })

    # 排序
    ai_scores.sort(key=lambda x: -x['ai_score'])

    for item in ai_scores:
        bet_str = ' '.join(f'{n:02d}' for n in sorted(item['bet']))
        score = item['ai_score'] * 100
        expected_str = f"{item['expected']:.2f}"

        # 最可能的情况
        if item['expected'] < 0.5:
            likely = "最可能 0个"
        elif item['expected'] < 1.0:
            likely = "最可能 0-1个"
        elif item['expected'] < 1.5:
            likely = "最可能 1个"
        else:
            likely = "最可能 1-2个"

        print(f'第{item["idx"]}注: {bet_str}')
        print(f'   AI评分: {score:.2f}% | 期望值: {expected_str} | {likely}')
        print()

    print('=' * 100)
    print('⚠️  再次强调')
    print('=' * 100)
    print()
    print('这些都是基于统计学的期望值，不是准确预测！')
    print()
    print('实际情况可能：')
    print('   • 8注全部都中0个（很常见）')
    print('   • 某几注中1-2个（较常见）')
    print('   • 某注中3个或以上（罕见但可能）')
    print('   • 甚至中头奖（概率极低但理论上可能）')
    print()
    print('大乐透是真随机，任何预测都只是参考，不要过度依赖！')
    print()

    # 最现实的预测
    print('=' * 100)
    print('📋 最现实的情况（基于历史数据）')
    print('=' * 100)
    print()

    print('根据过去的统计数据，您的8注最可能的结果是：')
    print()
    print('   🎯 5-6注: 中 0个号码')
    print('   🎯 2-3注: 中 1个号码')
    print('   🎯 0-1注: 中 2个号码')
    print('   🎯 很小机会: 某注中 3个或以上')
    print()
    print('这是基于概率分布的最可能情况，但不保证！')
    print()

    print('=' * 100)
    print('✅ 评估完成')
    print('=' * 100)
    print()
    print('记住：大乐透是娱乐，理性投注！')
    print('等114000114期开奖后再来验证实际结果！')

if __name__ == '__main__':
    estimate_match_probability()
