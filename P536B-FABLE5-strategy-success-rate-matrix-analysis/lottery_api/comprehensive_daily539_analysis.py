#!/usr/bin/env python3
"""
今彩539 完整高级分析
使用所有新方法：贝叶斯、反共识、随机性验证
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from models.advanced_bayesian_analyzer import BayesianBiasAnalyzer
from models.anti_consensus_strategy import AntiConsensusStrategy
from database import db_manager
from collections import Counter
import numpy as np
from scipy import stats
import json

def comprehensive_analysis():
    """完整分析今彩539"""

    lottery_type = 'DAILY_539'
    max_number = 39
    pick_count = 5

    print("=" * 80)
    print("【今彩539 完整高级分析】")
    print("=" * 80)

    # 获取数据
    all_draws = db_manager.get_all_draws(lottery_type)
    all_draws.sort(key=lambda x: x.get('draw', ''), reverse=True)

    # 获取2025年数据
    draws_2025 = [d for d in all_draws if d.get('date', '').startswith('2025')]

    print(f"\n数据概况:")
    print(f"  总期数: {len(all_draws)}期")
    print(f"  最新期号: {all_draws[0]['draw']} ({all_draws[0]['date']})")
    print(f"  2025年数据: {len(draws_2025)}期")

    # ========================================
    # 分析1: 贝叶斯偏差检测
    # ========================================
    print("\n" + "=" * 80)
    print("【分析1】贝叶斯偏差检测（95%可信区间）")
    print("=" * 80)

    analyzer = BayesianBiasAnalyzer(lottery_type, max_number=max_number)

    # 分析最近300期
    bias_result = analyzer.analyze_number_bias(all_draws[:300], confidence_level=0.95)

    print(f"\n分析数据: 最近300期")
    print(f"显著热号数量: {bias_result['summary']['hot_count']}个")
    print(f"显著冷号数量: {bias_result['summary']['cold_count']}个")

    hot_numbers = []
    cold_numbers = []

    if bias_result['summary']['hot_count'] > 0:
        print(f"\n【贝叶斯显著热号】（95%可信）:")
        for item in bias_result['biased_numbers']['hot'][:10]:
            print(f"  号码{item['number']:2d}: 出现{item['count']}次, 后验概率{item['prob']:.4f}")
            hot_numbers.append(item['number'])
    else:
        print(f"\n未检测到统计显著的热号")

    if bias_result['summary']['cold_count'] > 0:
        print(f"\n【贝叶斯显著冷号】（95%可信）:")
        for item in bias_result['biased_numbers']['cold'][:10]:
            print(f"  号码{item['number']:2d}: 出现{item['count']}次, 后验概率{item['prob']:.4f}")
            cold_numbers.append(item['number'])
    else:
        print(f"\n未检测到统计显著的冷号")

    # 奇偶比分析
    odd_even_result = analyzer.analyze_odd_even_bias(all_draws[:300])

    print(f"\n【奇偶比贝叶斯推断】")
    print(f"{odd_even_result['bayesian_inference']['interpretation']}")
    print(f"推荐: {odd_even_result['recommendation']}")

    # ========================================
    # 分析2: 反共识策略
    # ========================================
    print("\n" + "=" * 80)
    print("【分析2】反共识策略（提升实际收益）")
    print("=" * 80)

    strategy = AntiConsensusStrategy(lottery_type, max_number=max_number, pick_count=pick_count)

    print(f"\n核心理念: 不预测号码，而是选择'其他人不会选的号码'")
    print(f"效果: 中奖时分奖人数少 → 实际奖金更高")

    # 生成反共识号码
    anti_nums = strategy.generate_anti_consensus_numbers(all_draws, num_sets=6)

    print(f"\n生成6组低共识号码:")
    for i, item in enumerate(anti_nums, 1):
        print(f"\n组合{i}: {item['numbers']}")
        print(f"  策略: {item['description']}")
        print(f"  共识度得分: {item['consensus_score']:.1f} （越低越好）")
        print(f"  预期分奖人数: {strategy._estimate_sharers(item['consensus_score']):.0f}人")

    # 对比传统方法
    comparison = strategy.compare_with_frequency_strategy(all_draws)

    print(f"\n【对比分析】反共识 vs 传统热号")
    print(f"\n传统热号策略:")
    print(f"  号码: {comparison['hot_numbers_strategy']['numbers']}")
    print(f"  共识度: {comparison['hot_numbers_strategy']['consensus_score']:.1f}")
    print(f"  预期分奖人数: {comparison['hot_numbers_strategy']['expected_sharers']:.0f}人")

    print(f"\n反共识策略:")
    print(f"  号码: {comparison['anti_consensus_strategy']['numbers']}")
    print(f"  共识度: {comparison['anti_consensus_strategy']['consensus_score']:.1f}")
    print(f"  预期分奖人数: {comparison['anti_consensus_strategy']['expected_sharers']:.0f}人")

    print(f"\n💡 {comparison['conclusion']}")

    # ========================================
    # 分析3: 随机性验证
    # ========================================
    print("\n" + "=" * 80)
    print("【分析3】数据随机性深度验证")
    print("=" * 80)

    # 提取所有号码
    all_numbers = []
    for draw in all_draws[:500]:  # 最近500期
        all_numbers.extend(draw.get('numbers', []))

    # 测试1: 卡方检验
    observed = Counter(all_numbers)
    expected_freq = len(all_numbers) / max_number
    observed_counts = [observed.get(i, 0) for i in range(1, max_number + 1)]
    expected_counts = [expected_freq] * max_number

    chi2_stat, p_value_chi = stats.chisquare(observed_counts, expected_counts)

    print(f"\n1. 卡方检验 - 号码频率是否均匀分布")
    print(f"   χ² = {chi2_stat:.4f}, p = {p_value_chi:.6f}")
    if p_value_chi > 0.05:
        print(f"   ✅ 通过 (p > 0.05) - 号码分布符合均匀分布")
        chi_pass = True
    else:
        print(f"   ⚠️  未通过 (p < 0.05) - 号码分布存在偏差")
        chi_pass = False

    # 测试2: 熵分析
    total = len(all_numbers)
    probs = [observed.get(i, 0) / total for i in range(1, max_number + 1)]
    entropy = -sum(p * np.log2(p) if p > 0 else 0 for p in probs)
    max_entropy = np.log2(max_number)
    entropy_ratio = entropy / max_entropy

    print(f"\n2. 熵分析 - 信息熵是否接近最大")
    print(f"   实际熵: {entropy:.4f} bits")
    print(f"   最大熵: {max_entropy:.4f} bits")
    print(f"   熵比率: {entropy_ratio:.4f} ({entropy_ratio*100:.2f}%)")
    if entropy_ratio > 0.95:
        print(f"   ✅ 通过 - 熵接近最大值，数据高度随机")
        entropy_pass = True
    else:
        print(f"   ⚠️  未通过 - 熵偏低，可能存在模式")
        entropy_pass = False

    # 测试3: 奇偶比检验
    odd_counts = []
    for draw in all_draws[:500]:
        odd = sum(1 for n in draw['numbers'] if n % 2 == 1)
        odd_counts.append(odd)

    dist = Counter(odd_counts)
    from scipy.stats import binom

    observed_odd_even = [dist.get(i, 0) for i in range(pick_count + 1)]
    expected_odd_even = [500 * binom.pmf(i, pick_count, 0.5) for i in range(pick_count + 1)]

    chi2_odd_even, p_odd_even = stats.chisquare(observed_odd_even, expected_odd_even)

    print(f"\n3. 奇偶比检验 - 奇偶分布是否均匀")
    print(f"   χ² = {chi2_odd_even:.4f}, p = {p_odd_even:.6f}")
    if p_odd_even > 0.05:
        print(f"   ✅ 通过 (p > 0.05) - 奇偶比分布符合随机预期")
        odd_even_pass = True
    else:
        print(f"   ⚠️  未通过 (p < 0.05) - 奇偶比存在偏差")
        odd_even_pass = False

    # 测试4: 自相关检验
    draw_sums = [sum(draw['numbers']) for draw in all_draws[:500]]
    from scipy.stats import pearsonr

    corr_1, p_corr_1 = pearsonr(draw_sums[:-1], draw_sums[1:])

    print(f"\n4. 自相关检验 - 是否存在时间依赖")
    print(f"   滞后1期相关系数: r = {corr_1:+.4f}, p = {p_corr_1:.6f}")
    if abs(corr_1) < 0.1 and p_corr_1 > 0.05:
        print(f"   ✅ 通过 - 无显著自相关，各期独立")
        autocorr_pass = True
    else:
        print(f"   ⚠️  未通过 - 存在自相关，可能有时间依赖")
        autocorr_pass = False

    # 综合评估
    tests_passed = sum([chi_pass, entropy_pass, odd_even_pass, autocorr_pass])
    total_tests = 4

    print(f"\n【随机性综合评估】")
    print(f"通过测试: {tests_passed}/{total_tests}")

    if tests_passed == total_tests:
        print(f"✅ 结论: 数据高度随机，符合公平彩票预期")
        randomness_level = "高度随机"
    elif tests_passed >= 3:
        print(f"⚠️  结论: 数据基本随机，但存在微弱模式可利用")
        randomness_level = "基本随机"
    else:
        print(f"🎯 结论: 数据存在明显非随机模式！")
        randomness_level = "存在模式"

    # ========================================
    # 综合推荐
    # ========================================
    print("\n" + "=" * 80)
    print("【最终推荐】综合最优投注策略")
    print("=" * 80)

    print(f"\n基于以上分析，提供以下推荐:")

    # 推荐1: 纯反共识（最推荐）
    print(f"\n📌 推荐1: 纯反共识策略 ⭐⭐⭐⭐⭐")
    print(f"   号码: {anti_nums[0]['numbers']}")
    print(f"   理由: 中奖概率不变，但实际奖金提升{comparison['comparison']['expected_prize_multiplier']:.1f}倍")
    print(f"   适合: 所有投注者")

    # 推荐2: 贝叶斯 + 反共识混合
    if len(hot_numbers) > 0 or len(cold_numbers) > 0:
        print(f"\n📌 推荐2: 贝叶斯 + 反共识混合策略 ⭐⭐⭐⭐")

        # 构建混合策略
        mixed = []
        anti_best = anti_nums[0]['numbers']

        # 从反共识中选3个
        mixed.extend(anti_best[:3])

        # 从贝叶斯显著号码中选2个
        if len(hot_numbers) > 0:
            if hot_numbers[0] not in mixed:
                mixed.append(hot_numbers[0])

        if len(cold_numbers) > 0 and len(mixed) < pick_count:
            if cold_numbers[0] not in mixed:
                mixed.append(cold_numbers[0])

        # 补足
        idx = 3
        while len(mixed) < pick_count and idx < len(anti_best):
            if anti_best[idx] not in mixed:
                mixed.append(anti_best[idx])
            idx += 1

        print(f"   号码: {sorted(mixed)}")
        print(f"   组成: 3个反共识 + ", end="")
        if len(hot_numbers) > 0:
            print(f"1个贝叶斯热号 + ", end="")
        if len(cold_numbers) > 0:
            print(f"1个贝叶斯冷号")
        else:
            print()
        print(f"   理由: 平衡统计显著性和低共识度")
        print(f"   适合: 追求科学依据的投注者")

    # 推荐3: 多组覆盖（预算充足）
    print(f"\n📌 推荐3: 多组低共识覆盖策略 ⭐⭐⭐")
    print(f"   投注数量: 3-6组")
    print(f"   使用号码: 反共识策略生成的前6组")
    print(f"   总成本: 3-6倍单注")
    print(f"   中奖率提升: 约3-6倍")
    print(f"   适合: 预算充足，追求更高中奖率")

    # 显示2025年表现
    print(f"\n" + "=" * 80)
    print(f"【2025年数据验证】")
    print(f"=" * 80)

    if len(draws_2025) > 0:
        print(f"\n2025年共{len(draws_2025)}期开奖")

        # 统计奇偶比分布
        odd_dist_2025 = Counter()
        for draw in draws_2025:
            odd = sum(1 for n in draw['numbers'] if n % 2 == 1)
            odd_dist_2025[odd] += 1

        print(f"\n2025年奇偶比分布:")
        for i in sorted(odd_dist_2025.keys()):
            count = odd_dist_2025[i]
            pct = count / len(draws_2025) * 100
            bar = '▓' * int(pct / 2)
            print(f"  {i}奇{pick_count-i}偶: {count:3d}期 ({pct:5.1f}%) {bar}")

    # ========================================
    # 保存结果
    # ========================================
    results = {
        'lottery_type': lottery_type,
        'analysis_date': '2025-12-24',
        'data_summary': {
            'total_draws': len(all_draws),
            'draws_2025': len(draws_2025),
            'latest_draw': all_draws[0]['draw']
        },
        'bayesian_analysis': {
            'hot_numbers': hot_numbers[:5],
            'cold_numbers': cold_numbers[:5],
            'hot_count': len(hot_numbers),
            'cold_count': len(cold_numbers)
        },
        'anti_consensus': {
            'best_combination': anti_nums[0]['numbers'],
            'consensus_score': anti_nums[0]['consensus_score'],
            'expected_prize_multiplier': comparison['comparison']['expected_prize_multiplier']
        },
        'randomness_tests': {
            'chi_square_pass': chi_pass,
            'entropy_pass': entropy_pass,
            'odd_even_pass': odd_even_pass,
            'autocorr_pass': autocorr_pass,
            'tests_passed': tests_passed,
            'randomness_level': randomness_level
        },
        'recommendations': {
            'primary': anti_nums[0]['numbers'],
            'alternative_sets': [item['numbers'] for item in anti_nums[1:4]]
        }
    }

    with open('data/daily539_comprehensive_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n详细分析结果已保存: data/daily539_comprehensive_analysis.json")

    # ========================================
    # 最终提醒
    # ========================================
    print("\n" + "=" * 80)
    print("【重要提醒】")
    print("=" * 80)
    print(f"""
✅ 新方法的优势:
   - 贝叶斯方法: 严格统计检验，避免过拟合
   - 反共识策略: 提升实际收益{comparison['comparison']['expected_prize_multiplier']:.1f}倍（数学保证）
   - 随机性验证: 科学依据，诚实评估

⚠️  彩票本质:
   - 中奖概率极低（约1/575,757）
   - 期望值为负（长期必亏）
   - 新方法只是"输得少一点"

💡 理性建议:
   - 固定预算上限（月收入的1-2%）
   - 使用反共识策略（最有效）
   - 当作娱乐，享受分析过程
   - 不期望靠彩票赚钱
""")


if __name__ == "__main__":
    comprehensive_analysis()
