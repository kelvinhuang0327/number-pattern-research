#!/usr/bin/env python3
"""
重新分析双注策略的真实中奖率
关键：中奖是看单注，不是组合总数
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from common import get_lottery_rules

def analyze_real_win_rate():
    """分析真实的单注中奖率"""

    lottery_type = 'BIG_LOTTO'
    rules = get_lottery_rules(lottery_type)

    # 获取2025年数据
    all_draws = db_manager.get_all_draws(lottery_type)
    draws_2025 = [d for d in all_draws if d.get('date', '').startswith('2025')]
    draws_2025.sort(key=lambda x: x.get('draw', ''), reverse=True)

    print("=" * 80)
    print("【重要分析】双注策略的真实单注中奖率")
    print("=" * 80)
    print("\n⚠️  关键：彩票中奖是按单注计算，需要单注命中3+个号码\n")

    min_history = 50
    results = {
        'single_freq': {'total': 0, 'bet_wins': 0, 'bet_3plus': []},
        'double_optimal': {'total': 0, 'bet1_wins': 0, 'bet2_wins': 0, 'any_bet_wins': 0, 'both_bet_wins': 0, 'details': []},
        'double_dynamic': {'total': 0, 'bet1_wins': 0, 'bet2_wins': 0, 'any_bet_wins': 0, 'both_bet_wins': 0},
        'double_balanced': {'total': 0, 'bet1_wins': 0, 'bet2_wins': 0, 'any_bet_wins': 0, 'both_bet_wins': 0}
    }

    # 滚动回测
    for i in range(len(draws_2025) - min_history):
        target_draw = draws_2025[i]
        history = draws_2025[i+1:]
        target_numbers = set(target_draw.get('numbers', []))

        # 1. 单注策略
        try:
            single_result = prediction_engine.frequency_predict(history, rules)
            single_pred = set(single_result['numbers'])
            single_match = len(single_pred & target_numbers)

            results['single_freq']['total'] += 1
            if single_match >= 3:
                results['single_freq']['bet_wins'] += 1
                results['single_freq']['bet_3plus'].append({
                    'draw': target_draw['draw'],
                    'matches': single_match
                })
        except:
            pass

        # 2. 双注optimal
        try:
            double_result = prediction_engine.generate_double_bet(history, rules, mode='optimal')
            bet1_pred = set(double_result['bet1']['numbers'])
            bet2_pred = set(double_result['bet2']['numbers'])

            bet1_match = len(bet1_pred & target_numbers)
            bet2_match = len(bet2_pred & target_numbers)
            combined_match = len((bet1_pred | bet2_pred) & target_numbers)

            results['double_optimal']['total'] += 1

            # 统计单注中奖
            bet1_win = bet1_match >= 3
            bet2_win = bet2_match >= 3

            if bet1_win:
                results['double_optimal']['bet1_wins'] += 1
            if bet2_win:
                results['double_optimal']['bet2_wins'] += 1
            if bet1_win or bet2_win:
                results['double_optimal']['any_bet_wins'] += 1
            if bet1_win and bet2_win:
                results['double_optimal']['both_bet_wins'] += 1

            # 记录详情
            results['double_optimal']['details'].append({
                'draw': target_draw['draw'],
                'bet1_match': bet1_match,
                'bet2_match': bet2_match,
                'combined_match': combined_match,
                'bet1_win': bet1_win,
                'bet2_win': bet2_win
            })
        except:
            pass

        # 3. 双注dynamic
        try:
            double_result = prediction_engine.generate_double_bet(history, rules, mode='dynamic')
            bet1_pred = set(double_result['bet1']['numbers'])
            bet2_pred = set(double_result['bet2']['numbers'])

            bet1_match = len(bet1_pred & target_numbers)
            bet2_match = len(bet2_pred & target_numbers)

            results['double_dynamic']['total'] += 1

            if bet1_match >= 3:
                results['double_dynamic']['bet1_wins'] += 1
            if bet2_match >= 3:
                results['double_dynamic']['bet2_wins'] += 1
            if bet1_match >= 3 or bet2_match >= 3:
                results['double_dynamic']['any_bet_wins'] += 1
            if bet1_match >= 3 and bet2_match >= 3:
                results['double_dynamic']['both_bet_wins'] += 1
        except:
            pass

        # 4. 双注balanced
        try:
            double_result = prediction_engine.generate_double_bet(history, rules, mode='balanced')
            bet1_pred = set(double_result['bet1']['numbers'])
            bet2_pred = set(double_result['bet2']['numbers'])

            bet1_match = len(bet1_pred & target_numbers)
            bet2_match = len(bet2_pred & target_numbers)

            results['double_balanced']['total'] += 1

            if bet1_match >= 3:
                results['double_balanced']['bet1_wins'] += 1
            if bet2_match >= 3:
                results['double_balanced']['bet2_wins'] += 1
            if bet1_match >= 3 or bet2_match >= 3:
                results['double_balanced']['any_bet_wins'] += 1
            if bet1_match >= 3 and bet2_match >= 3:
                results['double_balanced']['both_bet_wins'] += 1
        except:
            pass

    # 打印结果
    print("\n" + "=" * 80)
    print("【真实中奖率对比】单注 vs 双注")
    print("=" * 80)
    print(f"\n{'策略':<20} {'测试期数':<10} {'单注3+中奖':<15} {'实际中奖率':<15}")
    print("-" * 80)

    # 单注
    total = results['single_freq']['total']
    wins = results['single_freq']['bet_wins']
    win_rate = wins / total * 100 if total > 0 else 0
    print(f"{'单注（标准热号）':<20} {total:<10} {wins:<15} {win_rate:<15.1f}%")

    print("-" * 80)

    # 双注 - 关键对比
    for mode_name, mode_key in [('optimal', 'double_optimal'), ('dynamic', 'double_dynamic'), ('balanced', 'double_balanced')]:
        mode_data = results[mode_key]
        total = mode_data['total']

        # 关键：至少一注中奖的概率
        any_win = mode_data['any_bet_wins']
        any_win_rate = any_win / total * 100 if total > 0 else 0

        # 注1和注2单独的中奖率
        bet1_rate = mode_data['bet1_wins'] / total * 100 if total > 0 else 0
        bet2_rate = mode_data['bet2_wins'] / total * 100 if total > 0 else 0

        print(f"双注-{mode_name:<15} {total:<10} {any_win:<15} {any_win_rate:<15.1f}%")
        print(f"  ├─ 注1单独中奖: {mode_data['bet1_wins']}期 ({bet1_rate:.1f}%)")
        print(f"  ├─ 注2单独中奖: {mode_data['bet2_wins']}期 ({bet2_rate:.1f}%)")
        print(f"  └─ 两注都中: {mode_data['both_bet_wins']}期")

    # 详细分析optimal模式
    print("\n" + "=" * 80)
    print("【optimal模式详细分析】")
    print("=" * 80)

    opt_data = results['double_optimal']
    total = opt_data['total']

    print(f"\n测试期数: {total}期")
    print(f"\n单注中奖统计:")
    print(f"  注1（极端奇数）中3+: {opt_data['bet1_wins']}期 ({opt_data['bet1_wins']/total*100:.1f}%)")
    print(f"  注2（冷号回归）中3+: {opt_data['bet2_wins']}期 ({opt_data['bet2_wins']/total*100:.1f}%)")
    print(f"  至少一注中3+: {opt_data['any_bet_wins']}期 ({opt_data['any_bet_wins']/total*100:.1f}%)")
    print(f"  两注都中3+: {opt_data['both_bet_wins']}期")

    # 显示具体中奖期次
    if opt_data['any_bet_wins'] > 0:
        print(f"\n中奖期次详情:")
        for detail in opt_data['details']:
            if detail['bet1_win'] or detail['bet2_win']:
                bet1_str = f"注1:{detail['bet1_match']}个{'✓' if detail['bet1_win'] else ''}"
                bet2_str = f"注2:{detail['bet2_match']}个{'✓' if detail['bet2_win'] else ''}"
                comb_str = f"组合:{detail['combined_match']}个"
                print(f"  {detail['draw']}: {bet1_str}  {bet2_str}  {comb_str}")

    # 投资回报分析
    print("\n" + "=" * 80)
    print("【投资回报重新计算】")
    print("=" * 80)

    single_win_rate = results['single_freq']['bet_wins'] / results['single_freq']['total'] * 100
    double_any_win_rate = opt_data['any_bet_wins'] / opt_data['total'] * 100

    print(f"\n单注策略:")
    print(f"  投注成本: 1注/期")
    print(f"  中奖概率: {single_win_rate:.1f}%")
    print(f"  预期: 每{100/single_win_rate:.0f}期中1次" if single_win_rate > 0 else "  预期: 极低")

    print(f"\n双注optimal:")
    print(f"  投注成本: 2注/期")
    print(f"  至少一注中奖: {double_any_win_rate:.1f}%")
    print(f"  预期: 每{100/double_any_win_rate:.0f}期中1次" if double_any_win_rate > 0 else "  预期: 很低")

    if single_win_rate > 0 and double_any_win_rate > 0:
        improvement = (double_any_win_rate - single_win_rate) / single_win_rate * 100
        cost_efficiency = double_any_win_rate / 2  # 每注的期望中奖率
        single_efficiency = single_win_rate / 1

        print(f"\n对比:")
        print(f"  中奖率提升: {improvement:+.1f}%")
        print(f"  单注成本效益: {single_efficiency:.2f}%/注")
        print(f"  双注成本效益: {cost_efficiency:.2f}%/注")

        if cost_efficiency > single_efficiency:
            print(f"  ✅ 双注仍有优势（每注效益提升{(cost_efficiency/single_efficiency-1)*100:+.1f}%）")
        else:
            print(f"  ⚠️ 双注效益不足（每注效益下降{(1-cost_efficiency/single_efficiency)*100:.1f}%）")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    analyze_real_win_rate()
