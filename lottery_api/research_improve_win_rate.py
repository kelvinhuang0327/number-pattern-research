#!/usr/bin/env python3
"""
深度研究：如何提高真实中奖率
测试多种方案找出最优配置
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from common import get_lottery_rules
from collections import defaultdict
import random

def get_2025_draws():
    """获取2025年数据"""
    all_draws = db_manager.get_all_draws('BIG_LOTTO')
    draws_2025 = [d for d in all_draws if d.get('date', '').startswith('2025')]
    draws_2025.sort(key=lambda x: x.get('draw', ''), reverse=True)
    return draws_2025

def test_multi_bet_strategy(draws, rules, num_bets=2, mode='optimal', min_history=50):
    """
    测试多注策略

    Args:
        num_bets: 投注数量（2, 3, 4, 6, 8）
    """
    results = {
        'total': 0,
        'any_bet_wins': 0,  # 至少一注中3+
        'details': []
    }

    # 所有可用策略
    all_strategies = [
        ('extreme_odd', prediction_engine.extreme_odd_predict),
        ('extreme_even', prediction_engine.extreme_even_predict),
        ('cold_number', prediction_engine.cold_number_predict),
        ('tail_repeat', prediction_engine.tail_repeat_predict),
        ('cold_hot_balanced', prediction_engine.cold_hot_balanced_predict),
        ('frequency', prediction_engine.frequency_predict),
        ('bayesian', prediction_engine.bayesian_predict),
        ('monte_carlo', prediction_engine.monte_carlo_predict),
    ]

    # 根据num_bets选择策略组合
    if num_bets == 2:
        if mode == 'optimal':
            selected = [all_strategies[0], all_strategies[2]]  # 极端奇数 + 冷号
        elif mode == 'balanced':
            selected = [all_strategies[5], all_strategies[0]]  # 热号 + 极端奇数
        else:
            selected = all_strategies[:2]
    elif num_bets == 3:
        # 3注：极端奇数 + 冷号 + 热号
        selected = [all_strategies[0], all_strategies[2], all_strategies[5]]
    elif num_bets == 4:
        # 4注：奇+偶+冷+热
        selected = [all_strategies[0], all_strategies[1], all_strategies[2], all_strategies[5]]
    elif num_bets == 6:
        # 6注：多样化组合
        selected = all_strategies[:6]
    elif num_bets == 8:
        # 8注：全部策略
        selected = all_strategies[:8]
    else:
        selected = all_strategies[:num_bets]

    for i in range(len(draws) - min_history):
        target_draw = draws[i]
        history = draws[i+1:]
        target_numbers = set(target_draw.get('numbers', []))

        try:
            # 执行所有选中的策略
            predictions = []
            for strategy_name, strategy_func in selected:
                try:
                    result = strategy_func(history, rules)
                    predictions.append(set(result['numbers']))
                except:
                    continue

            if not predictions:
                continue

            # 检查是否有任何一注中3+
            any_win = False
            match_counts = []
            for pred in predictions:
                match_count = len(pred & target_numbers)
                match_counts.append(match_count)
                if match_count >= 3:
                    any_win = True

            results['total'] += 1
            if any_win:
                results['any_bet_wins'] += 1

            results['details'].append({
                'draw': target_draw['draw'],
                'match_counts': match_counts,
                'any_win': any_win,
                'max_match': max(match_counts) if match_counts else 0
            })

        except Exception as e:
            continue

    return results

def test_conditional_betting(draws, rules, min_history=50):
    """
    测试条件性投注策略
    只在特定条件下投注，提高命中率
    """
    results = {
        'total_periods': 0,  # 总期数
        'bet_periods': 0,    # 实际投注期数
        'wins': 0,           # 中奖次数
        'details': []
    }

    for i in range(len(draws) - min_history):
        target_draw = draws[i]
        history = draws[i+1:]
        target_numbers = set(target_draw.get('numbers', []))

        results['total_periods'] += 1

        # 条件1：上期出现极端奇偶配比
        last_draw = history[0]
        last_numbers = last_draw.get('numbers', [])
        odd_count = len([n for n in last_numbers if n % 2 == 1])

        # 只在极端情况下投注（5-6奇或0-1奇）
        should_bet = (odd_count >= 5 or odd_count <= 1)

        if not should_bet:
            continue

        results['bet_periods'] += 1

        try:
            # 使用双注optimal
            double_result = prediction_engine.generate_double_bet(history, rules, mode='optimal')
            bet1_pred = set(double_result['bet1']['numbers'])
            bet2_pred = set(double_result['bet2']['numbers'])

            bet1_match = len(bet1_pred & target_numbers)
            bet2_match = len(bet2_pred & target_numbers)

            any_win = (bet1_match >= 3 or bet2_match >= 3)

            if any_win:
                results['wins'] += 1

            results['details'].append({
                'draw': target_draw['draw'],
                'condition': f'{odd_count}奇{6-odd_count}偶（极端）',
                'bet1_match': bet1_match,
                'bet2_match': bet2_match,
                'win': any_win
            })
        except:
            continue

    return results

def test_smart_filtering(draws, rules, min_history=50):
    """
    智能筛选：只在高置信度情况下投注
    """
    results = {
        'total_periods': 0,
        'bet_periods': 0,
        'wins': 0,
        'details': []
    }

    for i in range(len(draws) - min_history):
        target_draw = draws[i]
        history = draws[i+1:]
        target_numbers = set(target_draw.get('numbers', []))

        results['total_periods'] += 1

        try:
            # 执行多个策略，检查共识度
            strategies = [
                prediction_engine.extreme_odd_predict,
                prediction_engine.cold_number_predict,
                prediction_engine.frequency_predict,
                prediction_engine.bayesian_predict,
            ]

            all_predictions = []
            for strategy in strategies:
                try:
                    result = strategy(history, rules)
                    all_predictions.append(set(result['numbers']))
                except:
                    continue

            if len(all_predictions) < 3:
                continue

            # 计算共识度：至少3个策略都推荐的号码
            from collections import Counter
            all_nums = []
            for pred in all_predictions:
                all_nums.extend(pred)

            consensus = Counter(all_nums)
            high_consensus_nums = [n for n, count in consensus.items() if count >= 3]

            # 只在有足够共识时投注（至少有4个高共识号码）
            if len(high_consensus_nums) < 4:
                continue

            results['bet_periods'] += 1

            # 使用双注
            double_result = prediction_engine.generate_double_bet(history, rules, mode='optimal')
            bet1_pred = set(double_result['bet1']['numbers'])
            bet2_pred = set(double_result['bet2']['numbers'])

            bet1_match = len(bet1_pred & target_numbers)
            bet2_match = len(bet2_pred & target_numbers)

            any_win = (bet1_match >= 3 or bet2_match >= 3)

            if any_win:
                results['wins'] += 1

            results['details'].append({
                'draw': target_draw['draw'],
                'consensus_count': len(high_consensus_nums),
                'bet1_match': bet1_match,
                'bet2_match': bet2_match,
                'win': any_win
            })
        except:
            continue

    return results

def main():
    print("\n")
    print("╔" + "═" * 98 + "╗")
    print("║" + " " * 30 + "提高中奖率深度研究" + " " * 40 + "║")
    print("╚" + "═" * 98 + "╝")

    draws = get_2025_draws()
    rules = get_lottery_rules('BIG_LOTTO')

    print(f"\n数据: {len(draws)}期大乐透（2025年）")
    print(f"可测试: {len(draws) - 50}期\n")

    # ==================== 研究1: 多注策略 ====================
    print("=" * 100)
    print("【研究1】增加投注数量的效果")
    print("=" * 100)

    bet_configs = [
        (2, 'optimal', '双注-optimal'),
        (3, 'optimal', '三注组合'),
        (4, 'optimal', '四注组合'),
        (6, 'optimal', '六注组合'),
        (8, 'optimal', '八注组合'),
    ]

    multi_bet_results = []

    for num_bets, mode, name in bet_configs:
        print(f"\n测试: {name} ({num_bets}注)...")
        result = test_multi_bet_strategy(draws, rules, num_bets=num_bets, mode=mode)

        if result['total'] > 0:
            win_rate = result['any_bet_wins'] / result['total'] * 100
            cost_efficiency = win_rate / num_bets  # 每注的效益

            multi_bet_results.append({
                'name': name,
                'num_bets': num_bets,
                'total': result['total'],
                'wins': result['any_bet_wins'],
                'win_rate': win_rate,
                'cost_efficiency': cost_efficiency
            })

            print(f"  ✓ 中奖率: {win_rate:.1f}% ({result['any_bet_wins']}/{result['total']}期)")
            print(f"  ✓ 每注效益: {cost_efficiency:.2f}%")

    # 打印对比表
    print("\n" + "=" * 100)
    print(f"{'方案':<20} {'注数':<8} {'中奖率':<12} {'每注效益':<12} {'投注间隔':<15} {'性价比':<10}")
    print("-" * 100)

    for r in multi_bet_results:
        interval = f"每{100/r['win_rate']:.0f}期" if r['win_rate'] > 0 else "N/A"
        ratio = "⭐⭐⭐⭐⭐" if r['cost_efficiency'] > 2.0 else \
                "⭐⭐⭐⭐" if r['cost_efficiency'] > 1.5 else \
                "⭐⭐⭐" if r['cost_efficiency'] > 1.0 else "⭐⭐"

        print(f"{r['name']:<20} {r['num_bets']:<8} {r['win_rate']:<12.1f}% {r['cost_efficiency']:<12.2f}% {interval:<15} {ratio}")

    # ==================== 研究2: 条件性投注 ====================
    print("\n" + "=" * 100)
    print("【研究2】条件性投注策略（只在极端配比时投注）")
    print("=" * 100)

    conditional_result = test_conditional_betting(draws, rules)

    print(f"\n总期数: {conditional_result['total_periods']}期")
    print(f"满足条件（极端奇偶）: {conditional_result['bet_periods']}期")
    print(f"实际投注率: {conditional_result['bet_periods']/conditional_result['total_periods']*100:.1f}%")

    if conditional_result['bet_periods'] > 0:
        cond_win_rate = conditional_result['wins'] / conditional_result['bet_periods'] * 100
        print(f"中奖次数: {conditional_result['wins']}期")
        print(f"条件性投注中奖率: {cond_win_rate:.1f}%")
        print(f"vs 无条件投注: 4.6%")
        print(f"改进: {(cond_win_rate - 4.6) / 4.6 * 100:+.1f}%")

        # 显示中奖详情
        if conditional_result['wins'] > 0:
            print(f"\n中奖详情:")
            for detail in conditional_result['details']:
                if detail['win']:
                    print(f"  {detail['draw']}: {detail['condition']} - 注1:{detail['bet1_match']}个 注2:{detail['bet2_match']}个 ✓")

    # ==================== 研究3: 智能筛选 ====================
    print("\n" + "=" * 100)
    print("【研究3】智能筛选策略（高共识度时才投注）")
    print("=" * 100)

    smart_result = test_smart_filtering(draws, rules)

    print(f"\n总期数: {smart_result['total_periods']}期")
    print(f"满足条件（高共识度）: {smart_result['bet_periods']}期")
    print(f"实际投注率: {smart_result['bet_periods']/smart_result['total_periods']*100:.1f}%")

    if smart_result['bet_periods'] > 0:
        smart_win_rate = smart_result['wins'] / smart_result['bet_periods'] * 100
        print(f"中奖次数: {smart_result['wins']}期")
        print(f"智能筛选中奖率: {smart_win_rate:.1f}%")
        print(f"vs 无筛选投注: 4.6%")
        print(f"改进: {(smart_win_rate - 4.6) / 4.6 * 100:+.1f}%")

        if smart_result['wins'] > 0:
            print(f"\n中奖详情:")
            for detail in smart_result['details']:
                if detail['win']:
                    print(f"  {detail['draw']}: 共识{detail['consensus_count']}个 - 注1:{detail['bet1_match']}个 注2:{detail['bet2_match']}个 ✓")

    # ==================== 综合推荐 ====================
    print("\n" + "=" * 100)
    print("【综合分析与推荐】")
    print("=" * 100)

    # 找出最佳方案
    best_multi = max(multi_bet_results, key=lambda x: x['win_rate'])
    best_efficiency = max(multi_bet_results, key=lambda x: x['cost_efficiency'])

    print(f"\n1️⃣  最高中奖率方案:")
    print(f"   {best_multi['name']} - {best_multi['win_rate']:.1f}%")
    print(f"   成本: {best_multi['num_bets']}注/期")
    print(f"   预期: 每{100/best_multi['win_rate']:.0f}期中1次")

    print(f"\n2️⃣  最佳性价比方案:")
    print(f"   {best_efficiency['name']} - 每注效益{best_efficiency['cost_efficiency']:.2f}%")
    print(f"   成本: {best_efficiency['num_bets']}注/期")
    print(f"   中奖率: {best_efficiency['win_rate']:.1f}%")

    # 条件性投注评估
    if conditional_result['bet_periods'] > 0:
        cond_win_rate = conditional_result['wins'] / conditional_result['bet_periods'] * 100
        print(f"\n3️⃣  条件性投注方案:")
        print(f"   只在极端配比时投注（{conditional_result['bet_periods']}/{conditional_result['total_periods']}期）")
        print(f"   中奖率: {cond_win_rate:.1f}%")
        print(f"   优势: 减少{100-conditional_result['bet_periods']/conditional_result['total_periods']*100:.0f}%投注成本")

    # 智能筛选评估
    if smart_result['bet_periods'] > 0:
        smart_win_rate = smart_result['wins'] / smart_result['bet_periods'] * 100
        print(f"\n4️⃣  智能筛选方案:")
        print(f"   只在高共识时投注（{smart_result['bet_periods']}/{smart_result['total_periods']}期）")
        print(f"   中奖率: {smart_win_rate:.1f}%")
        print(f"   优势: 减少{100-smart_result['bet_periods']/smart_result['total_periods']*100:.0f}%投注成本")

    print("\n" + "=" * 100)
    print("【最终建议】")
    print("=" * 100)

    print(f"\n根据2025年{len(draws)-50}期回测数据分析：")
    print(f"\n推荐方案组合:")
    print(f"  1. 常规投注: {best_efficiency['name']} (性价比最优)")
    print(f"  2. 特殊情况: 当出现极端配比时，增加到{best_multi['name']}")
    print(f"  3. 预算控制: 使用条件性投注，只在高概率时投注")
    print(f"\n预期效果:")
    print(f"  - 常规中奖率: {best_efficiency['win_rate']:.1f}%")
    print(f"  - 极端情况: {best_multi['win_rate']:.1f}%")
    if conditional_result['bet_periods'] > 0:
        print(f"  - 条件性投注: {conditional_result['wins'] / conditional_result['bet_periods'] * 100:.1f}%")

    print("\n⚠️  重要提醒:")
    print("  - 即使是最佳方案，中奖率仍然较低")
    print("  - 彩票本质是低概率游戏")
    print("  - 理性投注，控制预算")
    print("  - 娱乐为主，不要沉迷\n")

if __name__ == "__main__":
    main()
