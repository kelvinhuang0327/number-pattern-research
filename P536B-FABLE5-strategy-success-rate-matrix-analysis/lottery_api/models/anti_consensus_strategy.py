#!/usr/bin/env python3
"""
反共识策略 - 提高中奖时的实际收益

核心思想：
不是预测中奖号码，而是选择"其他人不会选的号码"
→ 中奖时分奖人数少 → 实际奖金更高

理论基础：
1. 大多数人倾向选择生日号码（1-31）
2. 大多数人喜欢连号、对称号
3. 大多数人避开"不吉利"号码（4, 13等）

策略：
→ 避开这些热门模式，选择"冷门组合"
"""
import numpy as np
from typing import List, Dict, Set
from collections import Counter


class AntiConsensusStrategy:
    """反共识号码选择策略"""

    def __init__(self, lottery_type: str, max_number: int = 49, pick_count: int = 6):
        self.lottery_type = lottery_type
        self.max_number = max_number
        self.pick_count = pick_count

        # 人类心理偏好模式
        self.human_bias = self._define_human_bias()

    def _define_human_bias(self) -> Dict:
        """定义人类选号的心理偏好"""

        return {
            # 生日范围（1-31）权重高
            'birthday_range': set(range(1, 32)),

            # 常见幸运数字
            'lucky_numbers': {6, 8, 9, 18, 28, 38},

            # 避开的"不吉利"数字
            'unlucky_numbers': {4, 13, 14},

            # 常见模式
            'common_patterns': {
                'consecutive': True,  # 连号
                'symmetry': True,  # 对称（如 1-49, 2-48）
                'arithmetic': True,  # 等差数列
                'repeated_digits': True,  # 重复尾数
            }
        }

    def calculate_consensus_score(self, numbers: List[int]) -> float:
        """
        计算号码组合的"共识度"得分

        得分越高 = 越多人可能选择 = 应该避开
        得分越低 = 越少人选择 = 反共识策略的好选择
        """

        score = 0.0

        # 1. 生日号码惩罚（1-31）
        birthday_count = sum(1 for n in numbers if n in self.human_bias['birthday_range'])
        birthday_ratio = birthday_count / len(numbers)
        score += birthday_ratio * 50  # 权重50

        # 2. 幸运数字加分
        lucky_count = sum(1 for n in numbers if n in self.human_bias['lucky_numbers'])
        score += lucky_count * 10  # 每个幸运数字+10分

        # 3. 不吉利数字减分
        unlucky_count = sum(1 for n in numbers if n in self.human_bias['unlucky_numbers'])
        score -= unlucky_count * 5  # 每个不吉利数字-5分

        # 4. 连号惩罚
        sorted_nums = sorted(numbers)
        consecutive_groups = 0
        for i in range(len(sorted_nums) - 1):
            if sorted_nums[i + 1] - sorted_nums[i] == 1:
                consecutive_groups += 1
        score += consecutive_groups * 15  # 每组连号+15分

        # 5. 对称性惩罚
        # 检查是否有对称号码对（如1和49）
        symmetry_count = 0
        for n in numbers:
            mirror = self.max_number + 1 - n
            if mirror in numbers and mirror != n:
                symmetry_count += 1
        score += (symmetry_count / 2) * 10  # 每对对称号码+10分

        # 6. 等差数列惩罚
        if self._is_arithmetic_sequence(sorted_nums):
            score += 30

        # 7. 尾数重复惩罚
        tails = [n % 10 for n in numbers]
        tail_repeats = len(tails) - len(set(tails))
        score += tail_repeats * 8  # 每个重复尾数+8分

        # 8. 全奇或全偶惩罚
        odd_count = sum(1 for n in numbers if n % 2 == 1)
        if odd_count == 0 or odd_count == len(numbers):
            score += 20

        # 9. 数字和惩罚（人们倾向选择和为整数倍的组合）
        num_sum = sum(numbers)
        if num_sum % 10 == 0:
            score += 15

        return score

    def _is_arithmetic_sequence(self, sorted_nums: List[int]) -> bool:
        """检查是否为等差数列"""
        if len(sorted_nums) < 3:
            return False

        diffs = [sorted_nums[i + 1] - sorted_nums[i] for i in range(len(sorted_nums) - 1)]
        return len(set(diffs)) == 1  # 所有差值相同

    def generate_anti_consensus_numbers(
        self,
        history: List[Dict],
        num_sets: int = 1,
        optimize_for: str = 'minimum_consensus'
    ) -> List[Dict]:
        """
        生成反共识号码组合

        参数:
            history: 历史数据（用于参考，但不是主要依据）
            num_sets: 生成多少组号码
            optimize_for: 优化目标
                - 'minimum_consensus': 最小化共识度（最冷门）
                - 'balanced': 平衡冷门度和历史模式
        """

        results = []

        # 策略1: 全大号策略（32-49）
        # 理由：避开生日号码范围
        large_numbers = list(range(32, self.max_number + 1))
        for _ in range(num_sets // 3 + 1):
            selected = np.random.choice(large_numbers, self.pick_count, replace=False).tolist()
            consensus = self.calculate_consensus_score(selected)
            results.append({
                'numbers': sorted(selected),
                'strategy': 'anti_birthday',
                'consensus_score': consensus,
                'description': '全大号策略（避开生日范围1-31）'
            })

        # 策略2: 不吉利数字优先
        # 理由：大多数人避开这些号码
        unlucky_heavy = list(self.human_bias['unlucky_numbers'])
        remaining = [n for n in range(1, self.max_number + 1) if n not in unlucky_heavy]

        for _ in range(num_sets // 3 + 1):
            # 至少选2个不吉利数字
            selected = list(np.random.choice(unlucky_heavy, min(2, len(unlucky_heavy)), replace=False))
            # 其余从非热门号码中选
            needed = self.pick_count - len(selected)
            # 优先选32+的大号
            candidates = [n for n in remaining if n >= 32]
            if len(candidates) < needed:
                candidates = remaining
            selected.extend(np.random.choice(candidates, needed, replace=False).tolist())

            consensus = self.calculate_consensus_score(selected)
            results.append({
                'numbers': sorted(selected),
                'strategy': 'unlucky_priority',
                'consensus_score': consensus,
                'description': '不吉利数字优先（4, 13等）'
            })

        # 策略3: 无模式随机（避开所有常见模式）
        max_attempts = 1000
        for _ in range(num_sets // 3 + 1):
            best_score = float('inf')
            best_numbers = None

            for attempt in range(max_attempts):
                # 随机选择，但避开生日范围
                candidates = list(range(1, self.max_number + 1))
                # 从1-31中最多选2个
                birthday_pick = min(2, self.pick_count // 3)
                non_birthday_pick = self.pick_count - birthday_pick

                selected = []
                if birthday_pick > 0:
                    selected.extend(np.random.choice(range(1, 32), birthday_pick, replace=False).tolist())
                selected.extend(np.random.choice(range(32, self.max_number + 1), non_birthday_pick, replace=False).tolist())

                consensus = self.calculate_consensus_score(selected)

                # 检查是否有常见模式
                if self._has_common_patterns(selected):
                    continue

                if consensus < best_score:
                    best_score = consensus
                    best_numbers = selected

            if best_numbers:
                results.append({
                    'numbers': sorted(best_numbers),
                    'strategy': 'pattern_free',
                    'consensus_score': best_score,
                    'description': '无模式随机（避开连号、对称等）'
                })

        # 按共识度排序（越低越好）
        results.sort(key=lambda x: x['consensus_score'])

        return results[:num_sets]

    def _has_common_patterns(self, numbers: List[int]) -> bool:
        """检查是否包含常见模式"""

        # 连号检查
        sorted_nums = sorted(numbers)
        for i in range(len(sorted_nums) - 1):
            if sorted_nums[i + 1] - sorted_nums[i] == 1:
                return True

        # 等差数列检查
        if self._is_arithmetic_sequence(sorted_nums):
            return True

        # 全奇或全偶
        odd_count = sum(1 for n in numbers if n % 2 == 1)
        if odd_count == 0 or odd_count == len(numbers):
            return True

        return False

    def compare_with_frequency_strategy(self, history: List[Dict]) -> Dict:
        """
        对比：反共识策略 vs 传统热号策略

        展示为什么反共识可能更好
        """

        # 传统热号策略
        all_numbers = []
        for draw in history[:100]:
            all_numbers.extend(draw['numbers'])

        freq = Counter(all_numbers)
        hot_numbers = [n for n, _ in freq.most_common(self.pick_count)]

        # 反共识策略
        anti_consensus = self.generate_anti_consensus_numbers(history, num_sets=1)[0]

        # 计算共识度
        hot_consensus = self.calculate_consensus_score(hot_numbers)
        anti_consensus_score = anti_consensus['consensus_score']

        return {
            'hot_numbers_strategy': {
                'numbers': sorted(hot_numbers),
                'consensus_score': hot_consensus,
                'expected_sharers': self._estimate_sharers(hot_consensus),
                'description': '传统热号策略（大多数人的选择）'
            },
            'anti_consensus_strategy': {
                'numbers': anti_consensus['numbers'],
                'consensus_score': anti_consensus_score,
                'expected_sharers': self._estimate_sharers(anti_consensus_score),
                'description': anti_consensus['description']
            },
            'comparison': {
                'consensus_reduction': hot_consensus - anti_consensus_score,
                'sharers_reduction': self._estimate_sharers(hot_consensus) - self._estimate_sharers(anti_consensus_score),
                'expected_prize_multiplier': self._estimate_sharers(hot_consensus) / max(self._estimate_sharers(anti_consensus_score), 1)
            },
            'conclusion': (
                f"反共识策略预期减少{self._estimate_sharers(hot_consensus) - self._estimate_sharers(anti_consensus_score):.0f}个分奖者，"
                f"实际奖金可能提升{self._estimate_sharers(hot_consensus) / max(self._estimate_sharers(anti_consensus_score), 1):.1f}倍"
            )
        }

    def _estimate_sharers(self, consensus_score: float) -> float:
        """
        估算分奖人数

        简化模型：consensus_score越高，选择的人越多
        """
        # 基准：假设每期有1000人中奖
        # 共识度每增加10分，分奖人数增加20%

        base_sharers = 1000
        multiplier = 1 + (consensus_score / 10) * 0.2

        return base_sharers * multiplier


def main():
    """测试反共识策略"""
    import sys
    import os
    sys.path.insert(0, os.getcwd())

    from database import db_manager

    lottery_type = 'BIG_LOTTO'
    strategy = AntiConsensusStrategy(lottery_type, max_number=49, pick_count=6)

    # 获取数据
    history = db_manager.get_all_draws(lottery_type)

    print("=" * 80)
    print("【反共识策略】提高中奖时的实际收益")
    print("=" * 80)

    print("\n核心理念:")
    print("  不是预测中奖号码，而是选择'其他人不会选的号码'")
    print("  → 中奖时分奖人数少 → 实际奖金更高")

    # 生成反共识号码
    print("\n" + "=" * 80)
    print("生成反共识号码组合...")
    print("=" * 80)

    anti_numbers = strategy.generate_anti_consensus_numbers(history, num_sets=6)

    print(f"\n生成了{len(anti_numbers)}组低共识号码：")
    for i, item in enumerate(anti_numbers, 1):
        print(f"\n组合{i}: {item['numbers']}")
        print(f"  策略: {item['description']}")
        print(f"  共识度得分: {item['consensus_score']:.1f} （越低越好）")
        print(f"  预期分奖人数: {strategy._estimate_sharers(item['consensus_score']):.0f}人")

    # 对比分析
    print("\n" + "=" * 80)
    print("【对比分析】反共识 vs 传统热号")
    print("=" * 80)

    comparison = strategy.compare_with_frequency_strategy(history)

    print(f"\n传统热号策略:")
    print(f"  号码: {comparison['hot_numbers_strategy']['numbers']}")
    print(f"  共识度: {comparison['hot_numbers_strategy']['consensus_score']:.1f}")
    print(f"  预期分奖人数: {comparison['hot_numbers_strategy']['expected_sharers']:.0f}人")

    print(f"\n反共识策略:")
    print(f"  号码: {comparison['anti_consensus_strategy']['numbers']}")
    print(f"  共识度: {comparison['anti_consensus_strategy']['consensus_score']:.1f}")
    print(f"  预期分奖人数: {comparison['anti_consensus_strategy']['expected_sharers']:.0f}人")

    print(f"\n对比结果:")
    print(f"  共识度降低: {comparison['comparison']['consensus_reduction']:.1f}分")
    print(f"  分奖人数减少: {comparison['comparison']['sharers_reduction']:.0f}人")
    print(f"  实际奖金提升: {comparison['comparison']['expected_prize_multiplier']:.1f}倍")

    print(f"\n💡 {comparison['conclusion']}")

    print("\n" + "=" * 80)
    print("【重要提醒】")
    print("=" * 80)
    print("""
反共识策略的优势：
  ✅ 中奖概率不变（仍是随机）
  ✅ 中奖时实际奖金更高（分奖人数少）
  ✅ 期望收益提升

但请注意：
  ⚠️  中奖概率仍然极低
  ⚠️  彩票期望值仍为负
  ⚠️  只是"输得少一点"的策略

理性建议：
  → 如果一定要买彩票，使用反共识策略更理性
  → 但最好的策略仍是：不买或小额娱乐
""")


if __name__ == "__main__":
    main()
