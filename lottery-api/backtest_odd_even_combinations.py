#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
今彩539 奇偶比组合策略完整回测
测试奇偶比与各种方法的组合，找出最佳搭配
"""

import sqlite3
import json
import random
import numpy as np
from collections import Counter, defaultdict
from datetime import datetime

class OddEvenCombinationStrategies:
    """奇偶比组合策略集合"""

    def __init__(self):
        self.min_num = 1
        self.max_num = 39
        self.numbers_to_pick = 5

    def predict_odd_even_ratio(self, history, window=50):
        """预测目标奇偶比（1或2个奇数）"""
        recent_history = history[-window:] if len(history) > window else history

        odd_counts = []
        for draw in recent_history:
            numbers = draw.get('numbers', [])
            odd_count = sum(1 for n in numbers if n % 2 == 1)
            odd_counts.append(odd_count)

        distribution = Counter(odd_counts)
        count_1_odd = distribution.get(1, 0)
        count_2_odd = distribution.get(2, 0)

        # 返回更常见的配比
        if count_1_odd >= count_2_odd:
            return 1  # 1奇4偶
        else:
            return 2  # 2奇3偶

    def get_number_frequencies(self, history, window=100):
        """获取号码频率"""
        recent_history = history[-window:] if len(history) > window else history

        freq = Counter()
        for draw in recent_history:
            freq.update(draw.get('numbers', []))

        return freq

    def calculate_consensus_score(self, numbers):
        """计算共识度得分（越低越好）"""
        score = 0

        # 生日范围（1-31）
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
        for i in range(len(sorted_nums) - 1):
            if sorted_nums[i+1] - sorted_nums[i] == 1:
                score += 15

        return score

    # ==================== 组合策略1: 奇偶比 + 反共识 ====================
    def odd_even_plus_anti_consensus(self, history):
        """奇偶比 + 反共识策略"""
        target_odd = self.predict_odd_even_ratio(history)

        # 分离奇偶数
        odd_numbers = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 1]
        even_numbers = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 0]

        # 反共识优先：大号（32+）、不吉利数字
        odd_big = [n for n in odd_numbers if n >= 32]
        odd_unlucky = [n for n in odd_numbers if n in {13}]
        odd_rest = [n for n in odd_numbers if n < 32 and n not in {13}]

        even_big = [n for n in even_numbers if n >= 32]
        even_unlucky = [n for n in even_numbers if n in {4}]
        even_rest = [n for n in even_numbers if n < 32 and n not in {4}]

        # 选择奇数
        selected_odds = []
        if target_odd > 0:
            # 优先大号和不吉利数字
            pool = odd_unlucky + odd_big + odd_rest
            selected_odds = random.sample(pool, min(target_odd, len(pool)))

        # 选择偶数
        selected_evens = []
        even_needed = self.numbers_to_pick - len(selected_odds)
        if even_needed > 0:
            pool = even_unlucky + even_big + even_rest
            selected_evens = random.sample(pool, min(even_needed, len(pool)))

        return sorted(selected_odds + selected_evens)

    # ==================== 组合策略2: 奇偶比 + 热号 ====================
    def odd_even_plus_hot_numbers(self, history):
        """奇偶比 + 热号策略"""
        target_odd = self.predict_odd_even_ratio(history)
        freq = self.get_number_frequencies(history, window=100)

        # 分离奇偶热号
        odd_hot = [(n, freq[n]) for n in range(self.min_num, self.max_num + 1)
                   if n % 2 == 1]
        even_hot = [(n, freq[n]) for n in range(self.min_num, self.max_num + 1)
                    if n % 2 == 0]

        odd_hot.sort(key=lambda x: x[1], reverse=True)
        even_hot.sort(key=lambda x: x[1], reverse=True)

        # 选择热门奇数
        selected_odds = [n for n, _ in odd_hot[:target_odd]]

        # 选择热门偶数
        even_needed = self.numbers_to_pick - len(selected_odds)
        selected_evens = [n for n, _ in even_hot[:even_needed]]

        return sorted(selected_odds + selected_evens)

    # ==================== 组合策略3: 奇偶比 + 冷号回归 ====================
    def odd_even_plus_cold_numbers(self, history):
        """奇偶比 + 冷号回归策略"""
        target_odd = self.predict_odd_even_ratio(history)
        freq = self.get_number_frequencies(history, window=100)

        # 分离奇偶冷号
        odd_cold = [(n, freq.get(n, 0)) for n in range(self.min_num, self.max_num + 1)
                    if n % 2 == 1]
        even_cold = [(n, freq.get(n, 0)) for n in range(self.min_num, self.max_num + 1)
                     if n % 2 == 0]

        odd_cold.sort(key=lambda x: x[1])  # 从低到高
        even_cold.sort(key=lambda x: x[1])

        # 选择最冷的奇数
        selected_odds = [n for n, _ in odd_cold[:target_odd]]

        # 选择最冷的偶数
        even_needed = self.numbers_to_pick - len(selected_odds)
        selected_evens = [n for n, _ in even_cold[:even_needed]]

        return sorted(selected_odds + selected_evens)

    # ==================== 组合策略4: 奇偶比 + 频率权重采样 ====================
    def odd_even_plus_weighted_sample(self, history):
        """奇偶比 + 频率权重采样"""
        target_odd = self.predict_odd_even_ratio(history)
        freq = self.get_number_frequencies(history, window=100)

        # 分离奇偶并计算权重
        odd_numbers = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 1]
        even_numbers = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 0]

        odd_weights = [freq.get(n, 1) for n in odd_numbers]
        even_weights = [freq.get(n, 1) for n in even_numbers]

        # 归一化
        odd_weights = np.array(odd_weights) / sum(odd_weights)
        even_weights = np.array(even_weights) / sum(even_weights)

        # 加权采样
        try:
            selected_odds = np.random.choice(
                odd_numbers, size=target_odd, replace=False, p=odd_weights
            ).tolist()
        except:
            selected_odds = random.sample(odd_numbers, target_odd)

        try:
            selected_evens = np.random.choice(
                even_numbers,
                size=self.numbers_to_pick - target_odd,
                replace=False,
                p=even_weights
            ).tolist()
        except:
            selected_evens = random.sample(even_numbers, self.numbers_to_pick - target_odd)

        return sorted(selected_odds + selected_evens)

    # ==================== 组合策略5: 奇偶比 + 大小号平衡 ====================
    def odd_even_plus_big_small_balance(self, history):
        """奇偶比 + 大小号平衡（2-3个大号）"""
        target_odd = self.predict_odd_even_ratio(history)

        # 定义大小号（以20为界）
        odd_big = [n for n in range(21, self.max_num + 1) if n % 2 == 1]
        odd_small = [n for n in range(self.min_num, 21) if n % 2 == 1]
        even_big = [n for n in range(21, self.max_num + 1) if n % 2 == 0]
        even_small = [n for n in range(self.min_num, 21) if n % 2 == 0]

        # 目标：2-3个大号
        target_big = random.choice([2, 3])

        # 分配大小号到奇偶
        if target_odd > 0:
            odd_big_count = min(1, target_odd, len(odd_big))
            odd_small_count = target_odd - odd_big_count

            selected_odds = (
                random.sample(odd_big, odd_big_count) +
                random.sample(odd_small, min(odd_small_count, len(odd_small)))
            )
        else:
            selected_odds = []

        even_needed = self.numbers_to_pick - len(selected_odds)
        even_big_count = max(0, target_big - (len(selected_odds) - len([n for n in selected_odds if n >= 21])))
        even_small_count = even_needed - even_big_count

        selected_evens = (
            random.sample(even_big, min(even_big_count, len(even_big))) +
            random.sample(even_small, min(even_small_count, len(even_small)))
        )

        return sorted(selected_odds + selected_evens)

    # ==================== 组合策略6: 奇偶比 + 热号28固定 ====================
    def odd_even_plus_hot_28(self, history):
        """奇偶比 + 固定包含热号28"""
        target_odd = self.predict_odd_even_ratio(history)

        # 固定包含28（偶数）
        selected = [28]

        # 分离奇偶（排除28）
        odd_numbers = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 1]
        even_numbers = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 0 and n != 28]

        # 获取频率
        freq = self.get_number_frequencies(history, window=100)

        # 按频率排序
        odd_sorted = sorted(odd_numbers, key=lambda x: freq.get(x, 0), reverse=True)
        even_sorted = sorted(even_numbers, key=lambda x: freq.get(x, 0), reverse=True)

        # 选择奇数
        selected.extend(odd_sorted[:target_odd])

        # 选择偶数（已有28，还需3个或2个）
        even_needed = self.numbers_to_pick - len(selected)
        selected.extend(even_sorted[:even_needed])

        return sorted(selected)

    # ==================== 组合策略7: 奇偶比 + 间隔优化 ====================
    def odd_even_plus_interval_optimization(self, history):
        """奇偶比 + 间隔优化（号码分布均匀）"""
        target_odd = self.predict_odd_even_ratio(history)

        # 生成多组候选，选择间隔最优的
        best_combo = None
        best_score = -1

        for _ in range(100):
            odd_numbers = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 1]
            even_numbers = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 0]

            selected_odds = random.sample(odd_numbers, target_odd)
            selected_evens = random.sample(even_numbers, self.numbers_to_pick - target_odd)
            combo = sorted(selected_odds + selected_evens)

            # 计算间隔方差（越小越好）
            intervals = [combo[i+1] - combo[i] for i in range(len(combo) - 1)]
            variance = np.var(intervals) if intervals else 100
            score = 100 - variance * 2

            if score > best_score:
                best_score = score
                best_combo = combo

        return best_combo

    # ==================== 组合策略8: 奇偶比 + 最近趋势 ====================
    def odd_even_plus_recent_trend(self, history):
        """奇偶比 + 最近趋势（最近10期频繁号码）"""
        target_odd = self.predict_odd_even_ratio(history)
        freq = self.get_number_frequencies(history, window=10)  # 只看最近10期

        # 分离奇偶
        odd_trend = [(n, freq.get(n, 0)) for n in range(self.min_num, self.max_num + 1)
                     if n % 2 == 1]
        even_trend = [(n, freq.get(n, 0)) for n in range(self.min_num, self.max_num + 1)
                      if n % 2 == 0]

        odd_trend.sort(key=lambda x: x[1], reverse=True)
        even_trend.sort(key=lambda x: x[1], reverse=True)

        # 选择最近热门
        selected_odds = [n for n, _ in odd_trend[:target_odd]]
        selected_evens = [n for n, _ in even_trend[:self.numbers_to_pick - target_odd]]

        return sorted(selected_odds + selected_evens)

    # ==================== 组合策略9: 奇偶比 + 多样性优化 ====================
    def odd_even_plus_diversity(self, history):
        """奇偶比 + 多样性优化（避开最近出现的号码）"""
        target_odd = self.predict_odd_even_ratio(history)

        # 统计最近3期出现的号码
        recent_numbers = set()
        for draw in history[:3]:
            recent_numbers.update(draw.get('numbers', []))

        # 分离奇偶，优先选择未在最近出现的
        odd_numbers = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 1]
        even_numbers = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 0]

        odd_fresh = [n for n in odd_numbers if n not in recent_numbers]
        odd_used = [n for n in odd_numbers if n in recent_numbers]

        even_fresh = [n for n in even_numbers if n not in recent_numbers]
        even_used = [n for n in even_numbers if n in recent_numbers]

        # 优先选择fresh号码
        selected_odds = random.sample(odd_fresh, min(target_odd, len(odd_fresh)))
        if len(selected_odds) < target_odd:
            selected_odds.extend(random.sample(odd_used, target_odd - len(selected_odds)))

        even_needed = self.numbers_to_pick - len(selected_odds)
        selected_evens = random.sample(even_fresh, min(even_needed, len(even_fresh)))
        if len(selected_evens) < even_needed:
            selected_evens.extend(random.sample(even_used, even_needed - len(selected_evens)))

        return sorted(selected_odds + selected_evens)

    # ==================== 组合策略10: 奇偶比 + 综合蒙地卡罗 ====================
    def odd_even_plus_monte_carlo(self, history):
        """奇偶比 + 综合蒙地卡罗（简化版）"""
        target_odd = self.predict_odd_even_ratio(history)
        freq = self.get_number_frequencies(history, window=100)

        # 计算概率权重
        odd_numbers = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 1]
        even_numbers = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 0]

        best_combo = None
        best_score = -1

        # 500次采样
        for _ in range(500):
            # 反共识权重
            odd_weights = []
            for n in odd_numbers:
                weight = freq.get(n, 1)
                if n >= 32:  # 大号加权
                    weight *= 1.5
                if n in {13}:  # 不吉利数字加权
                    weight *= 1.3
                odd_weights.append(weight)

            even_weights = []
            for n in even_numbers:
                weight = freq.get(n, 1)
                if n >= 32:
                    weight *= 1.5
                if n in {4}:
                    weight *= 1.3
                even_weights.append(weight)

            # 归一化
            odd_weights = np.array(odd_weights) / sum(odd_weights)
            even_weights = np.array(even_weights) / sum(even_weights)

            try:
                selected_odds = np.random.choice(
                    odd_numbers, size=target_odd, replace=False, p=odd_weights
                ).tolist()
                selected_evens = np.random.choice(
                    even_numbers, size=self.numbers_to_pick - target_odd,
                    replace=False, p=even_weights
                ).tolist()

                combo = sorted(selected_odds + selected_evens)

                # 评分：反共识 + 间隔
                consensus = self.calculate_consensus_score(combo)
                intervals = [combo[i+1] - combo[i] for i in range(len(combo) - 1)]
                interval_score = 100 - np.var(intervals) * 2

                score = -consensus + interval_score

                if score > best_score:
                    best_score = score
                    best_combo = combo
            except:
                continue

        return best_combo if best_combo else sorted(
            random.sample(odd_numbers, target_odd) +
            random.sample(even_numbers, self.numbers_to_pick - target_odd)
        )


def backtest_all_combinations():
    """回测所有奇偶比组合策略"""

    # 连接数据库
    db_path = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery-api/data/lottery_v2.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

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
        return None

    draws_before_2025 = [d for d in all_draws if d['date'] and d['date'] < '2025-01-01']

    # 初始化策略
    strategies = OddEvenCombinationStrategies()

    # 定义所有组合策略
    strategy_methods = {
        '奇偶比+反共识': strategies.odd_even_plus_anti_consensus,
        '奇偶比+热号': strategies.odd_even_plus_hot_numbers,
        '奇偶比+冷号回归': strategies.odd_even_plus_cold_numbers,
        '奇偶比+频率权重': strategies.odd_even_plus_weighted_sample,
        '奇偶比+大小平衡': strategies.odd_even_plus_big_small_balance,
        '奇偶比+热号28': strategies.odd_even_plus_hot_28,
        '奇偶比+间隔优化': strategies.odd_even_plus_interval_optimization,
        '奇偶比+最近趋势': strategies.odd_even_plus_recent_trend,
        '奇偶比+多样性': strategies.odd_even_plus_diversity,
        '奇偶比+蒙地卡罗': strategies.odd_even_plus_monte_carlo,
    }

    # 初始化结果
    results = {name: {
        'predictions': [],
        'hit_counts': [],
        'wins_3plus': 0,
        'total_tests': 0
    } for name in strategy_methods.keys()}

    print("\n" + "="*80)
    print("开始回测所有奇偶比组合策略...")
    print("="*80)

    # 滚动回测
    for i, test_draw in enumerate(draws_2025):
        history = draws_before_2025 + draws_2025[:i]

        if len(history) < 50:
            continue

        actual_numbers = set(test_draw['numbers'])

        # 测试每个策略
        for name, method in strategy_methods.items():
            try:
                predicted = method(history)
                predicted_set = set(predicted)
                hit = len(predicted_set & actual_numbers)

                results[name]['predictions'].append({
                    'draw': test_draw['draw'],
                    'predicted': predicted,
                    'actual': list(actual_numbers),
                    'hit': hit
                })
                results[name]['hit_counts'].append(hit)
                results[name]['total_tests'] += 1

                if hit >= 3:
                    results[name]['wins_3plus'] += 1
            except Exception as e:
                print(f"策略 {name} 在第 {i} 期出错: {e}")
                continue

        if (i + 1) % 50 == 0:
            print(f"已测试 {i+1}/{len(draws_2025)} 期...")

    print("\n" + "="*80)
    print("回测完成！")
    print("="*80)

    return results, draws_2025


def analyze_and_compare(results):
    """分析并对比所有策略"""

    print("\n" + "="*80)
    print("📊 所有奇偶比组合策略对比")
    print("="*80)

    # 收集统计数据
    stats = []

    for name, data in results.items():
        if data['total_tests'] == 0:
            continue

        hit_counts = data['hit_counts']
        avg_hit = sum(hit_counts) / len(hit_counts) if hit_counts else 0
        hit_rate = avg_hit / 5 * 100
        win_rate_3plus = data['wins_3plus'] / data['total_tests'] * 100

        # ROI计算
        cost_per_bet = 50
        prize_3_match = 800
        total_cost = data['total_tests'] * cost_per_bet
        total_prize = data['wins_3plus'] * prize_3_match
        roi = (total_prize - total_cost) / total_cost * 100

        stats.append({
            'name': name,
            'total_tests': data['total_tests'],
            'avg_hit': avg_hit,
            'hit_rate': hit_rate,
            'wins_3plus': data['wins_3plus'],
            'win_rate_3plus': win_rate_3plus,
            'roi': roi,
            'total_cost': total_cost,
            'total_prize': total_prize
        })

    # 按中奖率排序
    stats.sort(key=lambda x: x['win_rate_3plus'], reverse=True)

    # 显示完整对比表
    print("\n| 排名 | 策略 | 测试期数 | 平均命中 | 命中率 | 3+中奖率 | ROI | 评价 |")
    print("|------|------|----------|----------|--------|----------|-----|------|")

    for i, s in enumerate(stats, 1):
        stars = "⭐" * min(5, int(s['win_rate_3plus'] / 0.4))
        print(f"| {i} | {s['name']} | {s['total_tests']}期 | "
              f"{s['avg_hit']:.2f}个 | {s['hit_rate']:.1f}% | "
              f"**{s['win_rate_3plus']:.1f}%** ({s['wins_3plus']}期) | "
              f"{s['roi']:.1f}% | {stars} |")

    # 详细分析前3名
    print("\n" + "="*80)
    print("🏆 TOP 3 策略详细分析")
    print("="*80)

    for i, s in enumerate(stats[:3], 1):
        print(f"\n第{i}名: {s['name']}")
        print(f"{'='*60}")
        print(f"  测试期数: {s['total_tests']}期")
        print(f"  平均命中: {s['avg_hit']:.2f}个/期 ({s['hit_rate']:.1f}%)")
        print(f"  3+中奖率: {s['win_rate_3plus']:.1f}% ({s['wins_3plus']}期)")
        print(f"  投资回报: {s['roi']:.1f}%")
        print(f"  总投入: {s['total_cost']:,}元")
        print(f"  总奖金: {s['total_prize']:,}元")
        print(f"  净损益: {s['total_prize'] - s['total_cost']:,}元")

        # 显示命中分布
        strategy_data = results[s['name']]
        hit_distribution = Counter(strategy_data['hit_counts'])
        print(f"\n  命中数分布:")
        for j in range(6):
            count = hit_distribution.get(j, 0)
            percentage = count / s['total_tests'] * 100
            bar = "▓" * int(percentage / 2)
            star = " ⭐" if j >= 3 else ""
            print(f"    {j}个: {count:3d}期 ({percentage:5.1f}%) {bar}{star}")

    return stats


if __name__ == "__main__":
    print("🎲 今彩539 奇偶比组合策略完整回测")
    print("测试10种奇偶比 + X 的组合\n")

    # 运行回测
    results, draws_2025 = backtest_all_combinations()

    if results:
        # 分析对比
        stats = analyze_and_compare(results)

        # 保存结果
        output_file = 'data/odd_even_combinations_backtest.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            # 转换results为可序列化格式
            serializable_results = {}
            for name, data in results.items():
                serializable_results[name] = {
                    'total_tests': data['total_tests'],
                    'wins_3plus': data['wins_3plus'],
                    'hit_counts': data['hit_counts'],
                    'predictions': data['predictions'][:10]  # 只保存前10个示例
                }

            json.dump({
                'results': serializable_results,
                'stats': stats,
                'test_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 详细结果已保存到: {output_file}")

        # 显示最优策略
        if stats:
            best = stats[0]
            print("\n" + "="*80)
            print("🌟 最佳组合策略")
            print("="*80)
            print(f"\n策略: {best['name']}")
            print(f"3+中奖率: {best['win_rate_3plus']:.1f}%")
            print(f"ROI: {best['roi']:.1f}%")
            print(f"少亏: {-best['roi']:.1f}%")

            print("\n推荐使用此策略进行预测！")

        print("\n" + "="*80)
        print("测试完成！")
        print("="*80)
