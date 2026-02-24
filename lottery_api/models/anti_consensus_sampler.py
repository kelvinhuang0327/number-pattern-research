#!/usr/bin/env python3
"""
Anti-Consensus Sampler and Entropy Maximization
反向共识过滤和熵最大化采样器

核心功能：
1. AntiConsensusFilter - 降低其他方法高频推荐号码的权重
2. EntropyMaximizedSampler - 生成差异化的8注号码
3. DiversityCalculator - 计算号码覆盖多样性
"""

import numpy as np
from scipy.stats import entropy
from itertools import combinations
import random


class AntiConsensusFilter:
    """
    反向共识过滤器
    核心思想：降低所有传统方法都推荐的"共识号码"的权重
    """

    def __init__(self, penalty_factor=0.7):
        """
        Args:
            penalty_factor: 惩罚系数 (0-1)，越小惩罚越重
                           0.7 = 对共识号码降权30%
                           0.5 = 对共识号码降权50%
        """
        self.penalty_factor = penalty_factor

    def filter(self, model_probs, consensus_numbers):
        """
        对共识号码应用惩罚

        Args:
            model_probs: 模型输出的49维概率向量
            consensus_numbers: 其他方法推荐的号码集合

        Returns:
            filtered_probs: 过滤后的概率分布
        """
        filtered_probs = model_probs.copy()

        for num in consensus_numbers:
            if 1 <= num <= len(filtered_probs):
                filtered_probs[num - 1] *= self.penalty_factor

        # 重新归一化
        filtered_probs /= (filtered_probs.sum() + 1e-10)

        return filtered_probs

    def calculate_anti_consensus_score(self, predicted_numbers, consensus_numbers):
        """
        计算反共识分数：预测号码与共识号码的差异度

        Args:
            predicted_numbers: 预测的号码列表
            consensus_numbers: 共识号码集合

        Returns:
            score: 反共识分数 (0-1)，越高表示越独特
        """
        predicted_set = set(predicted_numbers)
        consensus_set = set(consensus_numbers)

        # 计算差异
        unique_count = len(predicted_set - consensus_set)
        total_count = len(predicted_set)

        score = unique_count / total_count if total_count > 0 else 0

        return score


class EntropyMaximizedSampler:
    """
    熵最大化采样器
    生成差异化的8注号码，最大化覆盖熵
    """

    def __init__(self, n_bets=8, numbers_per_bet=6):
        self.n_bets = n_bets
        self.numbers_per_bet = numbers_per_bet

    def sample(self, probs, diversity_weight=0.5):
        """
        生成熵最大化的8注号码

        Args:
            probs: 49维概率向量
            diversity_weight: 多样性权重 (0-1)
                             0.5 = 50%概率 + 50%多样性

        Returns:
            all_bets: 8注号码列表
            coverage_entropy: 覆盖熵分数
        """
        all_bets = []
        remaining_probs = probs.copy()

        for i in range(self.n_bets):
            # 从剩余概率中采样
            bet = self._sample_one_bet(remaining_probs)
            all_bets.append(sorted(bet))

            # 降低已选号码的概率，鼓励差异化
            for num in bet:
                remaining_probs[num - 1] *= diversity_weight

            # 重新归一化
            remaining_probs /= (remaining_probs.sum() + 1e-10)

        # 计算覆盖熵
        coverage_entropy = self._calculate_coverage_entropy(all_bets)

        return all_bets, coverage_entropy

    def _sample_one_bet(self, probs):
        """
        从概率分布中采样一注号码（6个）

        Args:
            probs: 49维概率向量

        Returns:
            numbers: 6个号码的列表
        """
        # 使用概率加权采样
        numbers = np.random.choice(
            range(1, len(probs) + 1),
            size=self.numbers_per_bet,
            replace=False,
            p=probs
        )

        return numbers.tolist()

    def _calculate_coverage_entropy(self, all_bets):
        """
        计算8注号码的覆盖熵

        Args:
            all_bets: 8注号码列表

        Returns:
            coverage_entropy: 覆盖熵分数
        """
        # 统计每个号码出现的次数
        number_counts = {}
        for bet in all_bets:
            for num in bet:
                number_counts[num] = number_counts.get(num, 0) + 1

        # 计算频率分布
        total_numbers = sum(number_counts.values())
        freq_dist = np.array([number_counts.get(i, 0) for i in range(1, 50)]) / total_numbers

        # 计算信息熵
        coverage_entropy = entropy(freq_dist + 1e-10)

        return coverage_entropy

    def generate_diverse_8_bets(self, probs, strategy='balanced'):
        """
        生成多样化的8注，支持不同策略

        Args:
            probs: 49维概率向量
            strategy: 'balanced' - 平衡策略
                     'aggressive' - 激进策略（更多冷门号）
                     'conservative' - 保守策略（更多热门号）

        Returns:
            all_bets: 8注号码
            metadata: 元数据（包括各注的特征）
        """
        if strategy == 'aggressive':
            # 激进：反转概率，鼓励冷门
            inverted_probs = 1.0 - probs
            inverted_probs /= inverted_probs.sum()
            bets, _ = self.sample(inverted_probs, diversity_weight=0.3)

        elif strategy == 'conservative':
            # 保守：使用原始概率
            bets, _ = self.sample(probs, diversity_weight=0.7)

        else:  # balanced
            # 平衡：4注热门 + 4注冷门
            hot_bets, _ = self.sample(probs, diversity_weight=0.7)
            hot_bets = hot_bets[:4]

            inverted_probs = 1.0 - probs
            inverted_probs /= inverted_probs.sum()
            cold_bets, _ = self.sample(inverted_probs, diversity_weight=0.3)
            cold_bets = cold_bets[:4]

            bets = hot_bets + cold_bets

        # 计算元数据
        metadata = self._calculate_bets_metadata(bets, probs)

        return bets, metadata

    def _calculate_bets_metadata(self, bets, probs):
        """计算每注的元数据"""
        metadata = []

        for bet in bets:
            bet_prob = sum(probs[num - 1] for num in bet) / len(bet)
            odd_count = sum(1 for num in bet if num % 2 == 1)
            sum_value = sum(bet)

            metadata.append({
                'numbers': bet,
                'avg_prob': bet_prob,
                'odd_count': odd_count,
                'sum': sum_value,
                'type': 'hot' if bet_prob > 0.02 else 'cold'
            })

        return metadata


class DiversityCalculator:
    """
    号码覆盖多样性计算器
    """

    @staticmethod
    def calculate_coverage_rate(all_bets, total_numbers=49):
        """
        计算号码覆盖率

        Args:
            all_bets: 8注号码列表
            total_numbers: 总号码数

        Returns:
            coverage_rate: 覆盖率 (0-1)
        """
        covered_numbers = set()
        for bet in all_bets:
            covered_numbers.update(bet)

        coverage_rate = len(covered_numbers) / total_numbers

        return coverage_rate

    @staticmethod
    def calculate_overlap_matrix(all_bets):
        """
        计算8注之间的重叠矩阵

        Returns:
            overlap_matrix: 8x8 矩阵，表示每两注的重叠数量
        """
        n_bets = len(all_bets)
        overlap_matrix = np.zeros((n_bets, n_bets))

        for i in range(n_bets):
            for j in range(i + 1, n_bets):
                overlap = len(set(all_bets[i]) & set(all_bets[j]))
                overlap_matrix[i][j] = overlap
                overlap_matrix[j][i] = overlap

        return overlap_matrix

    @staticmethod
    def calculate_diversity_score(all_bets):
        """
        计算整体多样性分数

        多样性 = 覆盖率 * (1 - 平均重叠度)

        Returns:
            diversity_score: 多样性分数 (0-1)
        """
        # 覆盖率
        coverage_rate = DiversityCalculator.calculate_coverage_rate(all_bets)

        # 平均重叠度
        overlap_matrix = DiversityCalculator.calculate_overlap_matrix(all_bets)
        avg_overlap = overlap_matrix.sum() / (len(all_bets) * (len(all_bets) - 1))
        normalized_overlap = avg_overlap / 6  # 最大重叠为6

        # 多样性分数
        diversity_score = coverage_rate * (1 - normalized_overlap)

        return diversity_score

    @staticmethod
    def print_diversity_report(all_bets):
        """打印详细的多样性报告"""
        print("=" * 80)
        print("📊 号码多样性分析报告")
        print("=" * 80)

        # 覆盖率
        covered = set()
        for bet in all_bets:
            covered.update(bet)

        print(f"\n📈 覆盖率: {len(covered)}/49 ({len(covered)/49*100:.1f}%)")
        print(f"   覆盖号码: {sorted(list(covered))}")

        # 号码频率
        freq = {}
        for bet in all_bets:
            for num in bet:
                freq[num] = freq.get(num, 0) + 1

        print(f"\n🔥 高频号码 (出现 ≥3 次):")
        hot = {num: count for num, count in freq.items() if count >= 3}
        for num, count in sorted(hot.items(), key=lambda x: -x[1]):
            print(f"   {num:02d}: {count}次")

        print(f"\n❄️  单次号码 (仅出现1次):")
        cold = {num: count for num, count in freq.items() if count == 1}
        print(f"   {sorted(cold.keys())}")

        # 重叠矩阵
        overlap_matrix = DiversityCalculator.calculate_overlap_matrix(all_bets)
        avg_overlap = overlap_matrix.sum() / (len(all_bets) * (len(all_bets) - 1))

        print(f"\n🔀 平均重叠数: {avg_overlap:.2f}/6")

        # 多样性分数
        diversity_score = DiversityCalculator.calculate_diversity_score(all_bets)
        print(f"\n✨ 多样性总分: {diversity_score:.3f}")

        print("=" * 80)


# 导出接口
__all__ = ['AntiConsensusFilter', 'EntropyMaximizedSampler', 'DiversityCalculator']


if __name__ == '__main__':
    # 测试
    print("=" * 80)
    print("🧪 反向共识采样器测试")
    print("=" * 80)

    # 模拟概率分布
    np.random.seed(42)
    probs = np.random.dirichlet(np.ones(49))  # 生成随机概率分布

    # 测试1: 反向共识过滤
    print("\n[测试1] 反向共识过滤")
    print("-" * 80)
    consensus_numbers = [7, 13, 25, 29, 37, 39]  # 模拟传统方法的共识号码
    print(f"共识号码: {consensus_numbers}")

    filter = AntiConsensusFilter(penalty_factor=0.7)
    filtered_probs = filter.filter(probs, consensus_numbers)

    print(f"过滤前 Top 6: {[i+1 for i in np.argsort(probs)[-6:][::-1]]}")
    print(f"过滤后 Top 6: {[i+1 for i in np.argsort(filtered_probs)[-6:][::-1]]}")

    # 测试2: 熵最大化采样
    print("\n[测试2] 熵最大化采样")
    print("-" * 80)
    sampler = EntropyMaximizedSampler()
    bets, coverage_entropy = sampler.sample(filtered_probs, diversity_weight=0.5)

    print(f"✅ 生成8注号码:")
    for i, bet in enumerate(bets, 1):
        print(f"   第{i}注: {bet}")

    print(f"\n📊 覆盖熵: {coverage_entropy:.3f}")

    # 测试3: 多样性计算
    print("\n[测试3] 多样性分析")
    print("-" * 80)
    DiversityCalculator.print_diversity_report(bets)

    # 测试4: 不同策略比较
    print("\n[测试4] 策略比较")
    print("-" * 80)

    strategies = ['balanced', 'aggressive', 'conservative']
    for strategy in strategies:
        bets, metadata = sampler.generate_diverse_8_bets(probs, strategy=strategy)
        diversity = DiversityCalculator.calculate_diversity_score(bets)
        coverage = DiversityCalculator.calculate_coverage_rate(bets)

        print(f"\n{strategy:15s}: 多样性={diversity:.3f}, 覆盖率={coverage:.3f}")

    print("\n" + "=" * 80)
    print("✅ 测试完成！")
    print("=" * 80)
