#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
今彩539 蒙地卡罗策略回测
结合奇偶比优化 + 反共识分析 + 蒙地卡罗采样
"""

import sqlite3
import json
import random
import numpy as np
from collections import Counter, defaultdict
from datetime import datetime
import sys

class MonteCarloStrategy:
    """蒙地卡罗策略：使用概率采样 + 多目标优化"""

    def __init__(self):
        self.min_num = 1
        self.max_num = 39
        self.numbers_to_pick = 5

    def calculate_number_probabilities(self, history, window=100):
        """计算号码出现概率（基于最近window期）"""
        recent_history = history[-window:] if len(history) > window else history

        # 统计每个号码出现次数
        number_counts = Counter()
        for draw in recent_history:
            numbers = draw.get('numbers', [])
            for num in numbers:
                number_counts[num] += 1

        # 转换为概率（加入平滑避免0概率）
        total_draws = len(recent_history) * self.numbers_to_pick
        probs = {}
        for num in range(self.min_num, self.max_num + 1):
            count = number_counts.get(num, 0)
            # Laplace平滑
            probs[num] = (count + 1) / (total_draws + self.max_num)

        return probs

    def calculate_odd_even_target(self, history, window=50):
        """预测目标奇偶比（1或2个奇数）"""
        recent_history = history[-window:] if len(history) > window else history

        odd_counts = []
        for draw in recent_history:
            numbers = draw.get('numbers', [])
            odd_count = sum(1 for n in numbers if n % 2 == 1)
            odd_counts.append(odd_count)

        # 统计分布
        distribution = Counter(odd_counts)

        # 1奇4偶和2奇3偶是最常见的（占83.7%）
        count_1_odd = distribution.get(1, 0)
        count_2_odd = distribution.get(2, 0)

        # 返回更常见的配比
        if count_1_odd >= count_2_odd:
            return 1  # 1奇4偶
        else:
            return 2  # 2奇3偶

    def calculate_consensus_score(self, numbers):
        """计算共识度得分（越低越好）"""
        score = 0

        # 生日范围（1-31）权重
        birthday_count = sum(1 for n in numbers if 1 <= n <= 31)
        score += birthday_count * 50

        # 幸运数字
        lucky_numbers = {6, 8, 9, 18, 28, 38}
        score += sum(10 for n in numbers if n in lucky_numbers)

        # 不吉利数字（降低共识）
        unlucky_numbers = {4, 13}
        score -= sum(5 for n in numbers if n in unlucky_numbers)

        # 连号
        sorted_nums = sorted(numbers)
        consecutive_groups = 0
        for i in range(len(sorted_nums) - 1):
            if sorted_nums[i+1] - sorted_nums[i] == 1:
                consecutive_groups += 1
        score += consecutive_groups * 15

        # 对称号码对
        symmetry_pairs = 0
        for n in numbers:
            mirror = 40 - n
            if mirror in numbers and n < mirror:
                symmetry_pairs += 1
        score += symmetry_pairs * 10

        return score

    def calculate_diversity_score(self, numbers, recent_draws):
        """计算与最近开奖号码的差异度（越高越好）"""
        if not recent_draws:
            return 50

        # 统计最近3期出现的号码
        recent_numbers = set()
        for draw in recent_draws[-3:]:
            recent_numbers.update(draw.get('numbers', []))

        # 计算重复度
        overlap = len(set(numbers) & recent_numbers)
        diversity = 100 - (overlap * 20)  # 每重复1个减20分

        return max(0, diversity)

    def calculate_interval_score(self, numbers):
        """计算号码间隔合理性（越均匀越好）"""
        sorted_nums = sorted(numbers)
        intervals = []
        for i in range(len(sorted_nums) - 1):
            intervals.append(sorted_nums[i+1] - sorted_nums[i])

        # 理想间隔约为 39/5 ≈ 7-8
        ideal_interval = 7.5
        variance = np.var(intervals) if intervals else 100

        # 方差越小越好
        score = max(0, 100 - variance * 5)
        return score

    def score_combination(self, numbers, target_odd_count, number_probs, recent_draws):
        """综合评分一个号码组合"""
        scores = {}

        # 1. 奇偶比匹配度 (权重40%)
        actual_odd_count = sum(1 for n in numbers if n % 2 == 1)
        if actual_odd_count == target_odd_count:
            scores['odd_even'] = 100
        elif abs(actual_odd_count - target_odd_count) == 1:
            scores['odd_even'] = 60
        else:
            scores['odd_even'] = 20

        # 2. 号码频率得分 (权重20%)
        prob_score = sum(number_probs.get(n, 0) for n in numbers)
        scores['probability'] = min(100, prob_score * 1000)  # 归一化

        # 3. 反共识得分 (权重20%)
        consensus = self.calculate_consensus_score(numbers)
        scores['anti_consensus'] = max(0, 100 - consensus / 3)

        # 4. 差异度得分 (权重10%)
        scores['diversity'] = self.calculate_diversity_score(numbers, recent_draws)

        # 5. 间隔合理性 (权重10%)
        scores['interval'] = self.calculate_interval_score(numbers)

        # 加权总分
        weights = {
            'odd_even': 0.40,
            'probability': 0.20,
            'anti_consensus': 0.20,
            'diversity': 0.10,
            'interval': 0.10
        }

        total_score = sum(scores[key] * weights[key] for key in scores)

        return total_score, scores

    def generate_monte_carlo_prediction(self, history, num_simulations=10000):
        """蒙地卡罗模拟生成最优预测"""
        # 计算概率分布
        number_probs = self.calculate_number_probabilities(history)
        target_odd_count = self.calculate_odd_even_target(history)

        # 分离奇偶数池
        odd_numbers = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 1]
        even_numbers = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 0]

        # 获取概率权重
        odd_probs = [number_probs[n] for n in odd_numbers]
        even_probs = [number_probs[n] for n in even_numbers]

        # 归一化
        odd_probs = np.array(odd_probs) / sum(odd_probs)
        even_probs = np.array(even_probs) / sum(even_probs)

        best_combination = None
        best_score = -1
        best_details = None

        # 蒙地卡罗模拟
        for _ in range(num_simulations):
            # 根据目标奇偶比采样
            try:
                selected_odds = np.random.choice(
                    odd_numbers,
                    size=target_odd_count,
                    replace=False,
                    p=odd_probs
                ).tolist()

                selected_evens = np.random.choice(
                    even_numbers,
                    size=self.numbers_to_pick - target_odd_count,
                    replace=False,
                    p=even_probs
                ).tolist()

                combination = selected_odds + selected_evens

                # 评分
                score, details = self.score_combination(
                    combination,
                    target_odd_count,
                    number_probs,
                    history
                )

                # 更新最佳
                if score > best_score:
                    best_score = score
                    best_combination = sorted(combination)
                    best_details = details

            except ValueError:
                # 采样失败，跳过
                continue

        return {
            'numbers': best_combination,
            'odd_count': target_odd_count,
            'score': best_score,
            'details': best_details,
            'simulations': num_simulations
        }


def backtest_monte_carlo_2025():
    """2025年257期蒙地卡罗策略回测"""

    # 连接数据库
    db_path = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 获取今彩539数据
    cursor.execute("""
        SELECT draw, date, numbers
        FROM draws
        WHERE lottery_type = 'DAILY_539'
        ORDER BY draw
    """)

    all_draws = []
    for row in cursor.fetchall():
        draw_id, draw_date, numbers_str = row
        try:
            numbers = json.loads(numbers_str)
            all_draws.append({
                'draw': draw_id,
                'date': draw_date,
                'numbers': numbers
            })
        except:
            continue

    conn.close()

    print(f"总数据: {len(all_draws)}期")

    # 筛选2025年数据
    draws_2025 = [d for d in all_draws if d['date'] and d['date'].startswith('2025-')]
    print(f"2025年数据: {len(draws_2025)}期")

    if len(draws_2025) == 0:
        print("❌ 没有2025年数据")
        return

    # 获取2025年之前的数据作为初始训练集
    draws_before_2025 = [d for d in all_draws if d['date'] and d['date'] < '2025-01-01']
    print(f"2025年前数据: {len(draws_before_2025)}期")

    # 初始化策略
    mc_strategy = MonteCarloStrategy()

    # 回测结果
    results = {
        'monte_carlo': {
            'predictions': [],
            'hit_counts': [],
            'wins_3plus': 0,
            'total_tests': 0
        }
    }

    print("\n" + "="*80)
    print("开始蒙地卡罗策略回测...")
    print("="*80)

    # 滚动回测
    for i, test_draw in enumerate(draws_2025):
        # 使用该期之前的所有历史数据
        history = draws_before_2025 + draws_2025[:i]

        if len(history) < 50:
            continue

        actual_numbers = set(test_draw['numbers'])

        # 蒙地卡罗预测
        mc_pred = mc_strategy.generate_monte_carlo_prediction(history, num_simulations=5000)
        mc_numbers = set(mc_pred['numbers'])
        mc_hit = len(mc_numbers & actual_numbers)

        results['monte_carlo']['predictions'].append({
            'draw': test_draw['draw'],
            'date': test_draw['date'],
            'predicted': mc_pred['numbers'],
            'actual': list(actual_numbers),
            'hit': mc_hit,
            'odd_count': mc_pred['odd_count'],
            'score': mc_pred['score'],
            'details': mc_pred['details']
        })
        results['monte_carlo']['hit_counts'].append(mc_hit)
        results['monte_carlo']['total_tests'] += 1

        if mc_hit >= 3:
            results['monte_carlo']['wins_3plus'] += 1

        # 每50期打印一次进度
        if (i + 1) % 50 == 0:
            print(f"已测试 {i+1}/{len(draws_2025)} 期...")

    print("\n" + "="*80)
    print("回测完成！")
    print("="*80)

    return results, draws_2025


def analyze_results(results, draws_2025):
    """分析回测结果"""

    mc_stats = results['monte_carlo']
    total_tests = mc_stats['total_tests']

    print("\n" + "="*80)
    print("📊 蒙地卡罗策略回测结果（2025年）")
    print("="*80)

    print(f"\n测试期数: {total_tests}期")
    print(f"模拟次数: 5000次/期")

    # 命中数分布
    hit_counts = mc_stats['hit_counts']
    hit_distribution = Counter(hit_counts)

    avg_hit = sum(hit_counts) / len(hit_counts) if hit_counts else 0
    hit_rate = avg_hit / 5 * 100

    print(f"\n平均命中: {avg_hit:.2f}个/期")
    print(f"命中率: {hit_rate:.1f}%")

    print("\n命中数分布:")
    for i in range(6):
        count = hit_distribution.get(i, 0)
        percentage = count / total_tests * 100
        bar = "▓" * int(percentage)
        star = " ⭐" if i >= 3 else ""
        print(f"  {i}个: {count:3d}期 ({percentage:5.1f}%) {bar}{star}")

    # 中奖率
    wins_3plus = mc_stats['wins_3plus']
    win_rate_3plus = wins_3plus / total_tests * 100

    print(f"\n3+中奖率: {win_rate_3plus:.1f}% ({wins_3plus}期)")

    # 奇偶比预测准确率
    odd_even_correct = 0
    for pred in mc_stats['predictions']:
        actual_odd = sum(1 for n in pred['actual'] if n % 2 == 1)
        predicted_odd = pred['odd_count']

        # 允许±1的误差
        if abs(actual_odd - predicted_odd) <= 1:
            odd_even_correct += 1

    odd_even_acc = odd_even_correct / total_tests * 100
    print(f"\n奇偶比预测准确率: {odd_even_acc:.1f}% ({odd_even_correct}/{total_tests}期)")

    # ROI计算
    cost_per_bet = 50
    prize_3_match = 800

    total_cost = total_tests * cost_per_bet
    total_prize = wins_3plus * prize_3_match
    roi = (total_prize - total_cost) / total_cost * 100

    print(f"\n💰 投资回报分析:")
    print(f"总投入: {total_cost:,}元")
    print(f"总奖金: {total_prize:,}元 ({wins_3plus}次 × {prize_3_match}元)")
    print(f"净损益: {total_prize - total_cost:,}元")
    print(f"ROI: {roi:.1f}%")

    # 评分统计
    scores = [p['score'] for p in mc_stats['predictions']]
    avg_score = sum(scores) / len(scores) if scores else 0
    print(f"\n平均综合得分: {avg_score:.1f}/100")

    # 显示部分中奖案例
    winning_cases = [p for p in mc_stats['predictions'] if p['hit'] >= 3]
    if winning_cases:
        print(f"\n🎯 中奖案例（共{len(winning_cases)}期）:")
        for case in winning_cases[:5]:  # 显示前5个
            print(f"\n  {case['draw']}期 ({case['date']}):")
            print(f"    预测: {case['predicted']} (奇偶比: {case['odd_count']}奇{5-case['odd_count']}偶)")
            print(f"    实际: {case['actual']}")
            print(f"    命中: {case['hit']}个 ⭐")
            print(f"    得分: {case['score']:.1f}")

    return {
        'total_tests': total_tests,
        'avg_hit': avg_hit,
        'hit_rate': hit_rate,
        'win_rate_3plus': win_rate_3plus,
        'odd_even_accuracy': odd_even_acc,
        'roi': roi,
        'avg_score': avg_score
    }


def compare_with_anti_consensus():
    """与反共识策略对比"""
    print("\n" + "="*80)
    print("📊 策略对比：蒙地卡罗 vs 反共识")
    print("="*80)

    print("\n| 指标 | 蒙地卡罗 | 反共识 | 差异 | 优势方 |")
    print("|------|----------|--------|------|--------|")
    print("| 测试期数 | 257期 | 257期 | - | - |")
    print("| 平均命中 | 待测 | 0.66个 | 待测 | 待测 |")
    print("| 命中率 | 待测 | 13.2% | 待测 | 待测 |")
    print("| **3+中奖率** | 待测 | **1.6%** | 待测 | 待测 |")
    print("| **ROI** | 待测 | **-75.1%** | 待测 | 待测 |")
    print("| 奇偶比准确率 | 待测 | ~84% | 待测 | 待测 |")


if __name__ == "__main__":
    print("🎲 今彩539 蒙地卡罗策略回测")
    print("结合: 奇偶比优化 + 反共识分析 + 蒙地卡罗采样\n")

    # 运行回测
    results, draws_2025 = backtest_monte_carlo_2025()

    # 分析结果
    stats = analyze_results(results, draws_2025)

    # 对比
    compare_with_anti_consensus()

    # 保存结果
    output_file = 'data/monte_carlo_backtest_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'results': results,
            'stats': stats,
            'test_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 详细结果已保存到: {output_file}")

    print("\n" + "="*80)
    print("回测完成！")
    print("="*80)
