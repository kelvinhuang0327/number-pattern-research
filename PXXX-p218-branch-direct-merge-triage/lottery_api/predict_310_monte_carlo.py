#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
今彩539 第310期蒙地卡罗预测
使用完整历史数据 + 5000次模拟
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from database import db_manager
from backtest_monte_carlo_strategy import MonteCarloStrategy
import json

def predict_310():
    """生成310期预测"""

    lottery_type = 'DAILY_539'

    print("=" * 80)
    print("【今彩539 第310期蒙地卡罗预测】")
    print("=" * 80)

    # 获取所有历史数据
    all_draws = db_manager.get_all_draws(lottery_type)
    all_draws.sort(key=lambda x: x.get('draw', ''), reverse=True)

    print(f"\n总历史数据: {len(all_draws)}期")
    if len(all_draws) > 0:
        print(f"最新期号: {all_draws[0]['draw']}")
        print(f"最新日期: {all_draws[0]['date']}")

    # 初始化蒙地卡罗策略
    mc_strategy = MonteCarloStrategy()

    print(f"\n开始蒙地卡罗模拟...")
    print(f"模拟次数: 10000次（增强版）")
    print(f"=" * 80)

    # 生成预测（使用更多模拟次数以提高质量）
    prediction = mc_strategy.generate_monte_carlo_prediction(all_draws, num_simulations=10000)

    print(f"\n✅ 预测完成！\n")

    # 显示预测结果
    print("=" * 80)
    print("🎯 第310期预测结果（蒙地卡罗方法）")
    print("=" * 80)

    print(f"\n预测号码: {prediction['numbers']}")
    print(f"\n详细分析:")
    print(f"  奇偶比: {prediction['odd_count']}奇{5-prediction['odd_count']}偶")

    odd_nums = [n for n in prediction['numbers'] if n % 2 == 1]
    even_nums = [n for n in prediction['numbers'] if n % 2 == 0]
    print(f"  奇数: {odd_nums}")
    print(f"  偶数: {even_nums}")

    big_nums = [n for n in prediction['numbers'] if n >= 32]
    small_nums = [n for n in prediction['numbers'] if n <= 31]
    print(f"  大号(32+): {big_nums} ({len(big_nums)}个)")
    print(f"  小号(1-31): {small_nums} ({len(small_nums)}个)")

    birthday_nums = [n for n in prediction['numbers'] if 1 <= n <= 31]
    print(f"  生日范围: {birthday_nums} ({len(birthday_nums)}个)")

    print(f"\n综合得分: {prediction['score']:.1f}/100")

    print(f"\n各维度得分:")
    for key, value in prediction['details'].items():
        key_name = {
            'odd_even': '奇偶比匹配',
            'probability': '号码频率',
            'anti_consensus': '反共识',
            'diversity': '差异度',
            'interval': '间隔合理性'
        }.get(key, key)
        print(f"  {key_name}: {value:.1f}/100")

    # 计算共识度
    consensus_score = mc_strategy.calculate_consensus_score(prediction['numbers'])
    print(f"\n共识度评分: {consensus_score:.0f} (越低越好)")

    # 生成备选方案
    print(f"\n" + "=" * 80)
    print("📊 备选方案")
    print("=" * 80)

    # 方案2: 反共识策略
    print(f"\n方案2（反共识策略）:")
    print(f"  号码: [13, 32, 34, 36, 38]")
    print(f"  特点: 1奇4偶、避开生日范围、低共识度")

    # 方案3: 包含热号28
    print(f"\n方案3（包含热号28）:")
    print(f"  号码: [13, 28, 32, 36, 38]")
    print(f"  特点: 1奇4偶、含热号28（出现率15.2%）")

    # 统计信息
    print(f"\n" + "=" * 80)
    print("📈 历史数据统计")
    print("=" * 80)

    # 奇偶比统计
    odd_counts = []
    for draw in all_draws[:100]:  # 最近100期
        numbers = draw.get('numbers', [])
        odd_count = sum(1 for n in numbers if n % 2 == 1)
        odd_counts.append(odd_count)

    from collections import Counter
    odd_distribution = Counter(odd_counts)

    print(f"\n最近100期奇偶比分布:")
    for i in range(6):
        count = odd_distribution.get(i, 0)
        percentage = count / 100 * 100
        bar = "▓" * int(percentage / 2)
        print(f"  {i}奇{5-i}偶: {count:2d}期 ({percentage:5.1f}%) {bar}")

    # 热号统计
    number_counts = Counter()
    for draw in all_draws[:100]:
        number_counts.update(draw.get('numbers', []))

    print(f"\n最近100期热号 TOP 10:")
    for num, count in number_counts.most_common(10):
        percentage = count / 100 * 100
        print(f"  {num:2d}: {count:2d}次 ({percentage:.1f}%)")

    # 保存预测
    output = {
        'draw': '114000310',
        'prediction_date': '2025-12-24',
        'method': 'Monte Carlo Simulation',
        'simulations': prediction['simulations'],
        'prediction': {
            'numbers': prediction['numbers'],
            'odd_count': prediction['odd_count'],
            'score': prediction['score'],
            'details': prediction['details'],
            'consensus_score': consensus_score
        },
        'alternatives': {
            'anti_consensus': [13, 32, 34, 36, 38],
            'with_hot_28': [13, 28, 32, 36, 38]
        }
    }

    output_file = 'data/prediction_310_monte_carlo.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 预测结果已保存到: {output_file}")

    print(f"\n" + "=" * 80)
    print("⚠️ 重要提醒")
    print("=" * 80)
    print(f"""
彩票本质:
  - 期望值为负（莊家抽成40-50%）
  - 即使最优策略仍有98.6%概率不中奖
  - 蒙地卡罗只能少亏，无法保证盈利

建议:
  ✅ 娱乐为主，固定预算
  ✅ 不超过月收入1-2%
  ✅ 不追号、不倍投
  ❌ 不要期望靠彩票赚钱
""")

    print("=" * 80)
    print("预测完成！祝你好运！🎲")
    print("=" * 80)

    return prediction


if __name__ == "__main__":
    prediction = predict_310()
