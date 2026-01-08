#!/usr/bin/env python3
"""
贝叶斯推断框架 - 检测真实偏差 vs 随机噪音
使用贝叶斯方法严格区分信号和噪音
"""
import numpy as np
from collections import Counter
from typing import List, Dict, Tuple
import json


class BayesianBiasAnalyzer:
    """贝叶斯偏差分析器"""

    def __init__(self, lottery_type: str, max_number: int = 49):
        self.lottery_type = lottery_type
        self.max_number = max_number

    def analyze_number_bias(self, history: List[Dict], confidence_level: float = 0.95) -> Dict:
        """
        分析号码偏差（贝叶斯方法）

        核心思想：
        1. 先验：假设所有号码概率相等（1/49）
        2. 更新：根据观测数据更新后验概率
        3. 判断：后验概率显著偏离先验 → 真实偏差
        """

        # 提取所有号码
        all_numbers = []
        for draw in history:
            all_numbers.extend(draw.get('numbers', []))

        total_count = len(all_numbers)

        # 计数
        observed = Counter(all_numbers)

        # 先验参数（Dirichlet分布）
        # 使用均匀先验：alpha = 1 for all numbers
        alpha_prior = np.ones(self.max_number)

        # 后验参数（Dirichlet分布）
        # alpha_posterior = alpha_prior + observed_counts
        alpha_posterior = alpha_prior.copy()
        for num in range(1, self.max_number + 1):
            alpha_posterior[num - 1] += observed.get(num, 0)

        # 后验期望（各号码的概率估计）
        posterior_mean = alpha_posterior / alpha_posterior.sum()

        # 理论概率（均匀分布）
        theoretical_prob = 1.0 / self.max_number

        # 计算可信区间（Credible Interval）
        # 使用Beta分布近似（对于Dirichlet的边缘分布）
        from scipy.stats import beta

        results = {}
        biased_numbers = {'hot': [], 'cold': []}

        for num in range(1, self.max_number + 1):
            count = observed.get(num, 0)
            alpha = alpha_posterior[num - 1]
            beta_param = alpha_posterior.sum() - alpha

            # 后验分布：Beta(alpha, beta)
            mean = alpha / (alpha + beta_param)

            # 95%可信区间
            lower = beta.ppf((1 - confidence_level) / 2, alpha, beta_param)
            upper = beta.ppf(1 - (1 - confidence_level) / 2, alpha, beta_param)

            # 判断是否显著偏离
            is_hot = lower > theoretical_prob  # 下界都超过理论值
            is_cold = upper < theoretical_prob  # 上界都低于理论值

            results[num] = {
                'count': int(count),
                'posterior_mean': float(mean),
                'credible_interval': (float(lower), float(upper)),
                'theoretical': float(theoretical_prob),
                'is_hot': bool(is_hot),
                'is_cold': bool(is_cold),
            }

            if is_hot:
                biased_numbers['hot'].append({
                    'number': int(num),
                    'count': int(count),
                    'prob': float(mean),
                    'confidence': float(confidence_level)
                })
            elif is_cold:
                biased_numbers['cold'].append({
                    'number': int(num),
                    'count': int(count),
                    'prob': float(mean),
                    'confidence': float(confidence_level)
                })

        # 排序
        biased_numbers['hot'].sort(key=lambda x: x['prob'], reverse=True)
        biased_numbers['cold'].sort(key=lambda x: x['prob'])

        return {
            'total_numbers_analyzed': total_count,
            'biased_numbers': biased_numbers,
            'all_numbers': results,
            'summary': {
                'hot_count': len(biased_numbers['hot']),
                'cold_count': len(biased_numbers['cold']),
                'confidence_level': confidence_level,
            }
        }

    def analyze_odd_even_bias(self, history: List[Dict]) -> Dict:
        """
        分析奇偶比的贝叶斯偏差

        发现：奇偶比分布存在显著偏差（p=0.0009）
        问题：这是真实偏差还是随机波动？
        """

        odd_counts = []
        for draw in history:
            odd = sum(1 for n in draw['numbers'] if n % 2 == 1)
            odd_counts.append(odd)

        # 统计分布
        dist = Counter(odd_counts)

        # 理论分布（二项分布 B(6, 0.5)）
        from scipy.stats import binom
        n_numbers = 6  # 大乐透选6个号码
        p_odd = 0.5  # 假设奇偶均等

        theoretical_dist = {}
        for k in range(n_numbers + 1):
            theoretical_dist[k] = binom.pmf(k, n_numbers, p_odd)

        # 贝叶斯推断：真实的p_odd是多少？
        # 先验：Beta(1, 1) - 均匀先验
        # 似然：二项分布
        # 后验：Beta(1 + 奇数总数, 1 + 偶数总数)

        total_odd = sum(odd_counts)
        total_even = len(odd_counts) * n_numbers - total_odd

        alpha_post = 1 + total_odd
        beta_post = 1 + total_even

        from scipy.stats import beta

        # 后验分布
        mean_p_odd = alpha_post / (alpha_post + beta_post)
        lower = beta.ppf(0.025, alpha_post, beta_post)
        upper = beta.ppf(0.975, alpha_post, beta_post)

        # 判断：95%可信区间是否包含0.5
        is_biased = not (lower <= 0.5 <= upper)

        return {
            'observed_distribution': dict(dist),
            'theoretical_distribution': theoretical_dist,
            'bayesian_inference': {
                'posterior_mean_p_odd': mean_p_odd,
                'credible_interval_95': (lower, upper),
                'is_biased': is_biased,
                'interpretation': (
                    f"奇数概率的95%可信区间为 [{lower:.4f}, {upper:.4f}]。"
                    + (" 不包含0.5，存在显著偏差！" if is_biased else " 包含0.5，偏差不显著。")
                )
            },
            'recommendation': (
                "利用奇偶比偏差调整预测策略"
                if is_biased
                else "奇偶比基本平衡，按理论分布即可"
            )
        }

    def detect_state_regime(self, history: List[Dict], window_size: int = 50) -> Dict:
        """
        状态检测：检测摇奖机是否在不同"状态"间切换

        方法：滚动窗口 + 贝叶斯模型比较
        """

        states = []

        for i in range(len(history) - window_size + 1):
            window = history[i:i + window_size]

            # 提取窗口内号码
            window_numbers = []
            for draw in window:
                window_numbers.extend(draw['numbers'])

            # 计算窗口统计特征
            freq = Counter(window_numbers)

            # 熵
            total = len(window_numbers)
            probs = [freq.get(n, 0) / total for n in range(1, self.max_number + 1)]
            entropy = -sum(p * np.log2(p) if p > 0 else 0 for p in probs)

            # 方差
            variance = np.var(list(freq.values()))

            # 奇偶比
            odd_count = sum(1 for n in window_numbers if n % 2 == 1)
            odd_ratio = odd_count / total

            states.append({
                'period': f"{history[i]['draw']} - {history[i+window_size-1]['draw']}",
                'entropy': entropy,
                'variance': variance,
                'odd_ratio': odd_ratio,
            })

        # 检测状态突变点
        # 使用简单的阈值法（可以改进为贝叶斯变点检测）
        entropy_mean = np.mean([s['entropy'] for s in states])
        entropy_std = np.std([s['entropy'] for s in states])

        changepoints = []
        for i in range(1, len(states)):
            # 熵的变化
            delta_entropy = states[i]['entropy'] - states[i - 1]['entropy']

            # 如果变化超过2个标准差，标记为变点
            if abs(delta_entropy) > 2 * entropy_std:
                changepoints.append({
                    'index': i,
                    'period': states[i]['period'],
                    'delta_entropy': delta_entropy,
                    'type': 'increase' if delta_entropy > 0 else 'decrease'
                })

        return {
            'states': states,
            'changepoints': changepoints,
            'summary': {
                'total_windows': len(states),
                'changepoints_detected': len(changepoints),
                'interpretation': (
                    "检测到多个状态切换点，可能存在外部因素影响（如更换球体、机械维护等）"
                    if len(changepoints) > 5
                    else "未检测到显著的状态切换，系统相对稳定"
                )
            }
        }

    def recommend_strategy(self, bias_analysis: Dict, odd_even_analysis: Dict) -> Dict:
        """根据贝叶斯分析结果推荐策略"""

        recommendations = []

        # 1. 号码偏差策略
        hot_numbers = bias_analysis['biased_numbers']['hot']
        cold_numbers = bias_analysis['biased_numbers']['cold']

        if len(hot_numbers) > 0:
            recommendations.append({
                'strategy': 'bayesian_hot_numbers',
                'description': f"选择{len(hot_numbers)}个贝叶斯显著热号",
                'numbers': [n['number'] for n in hot_numbers[:10]],
                'confidence': '95%',
                'expected_improvement': '微小但统计显著'
            })

        if len(cold_numbers) > 0:
            recommendations.append({
                'strategy': 'bayesian_cold_reversion',
                'description': f"选择{len(cold_numbers)}个贝叶斯显著冷号（回归策略）",
                'numbers': [n['number'] for n in cold_numbers[:10]],
                'confidence': '95%',
                'expected_improvement': '基于均值回归理论'
            })

        # 2. 奇偶比策略
        if odd_even_analysis['bayesian_inference']['is_biased']:
            mean_p = odd_even_analysis['bayesian_inference']['posterior_mean_p_odd']
            if mean_p > 0.5:
                recommendations.append({
                    'strategy': 'odd_bias_exploit',
                    'description': f"奇数概率偏高（{mean_p:.2%}），倾向选择更多奇数",
                    'suggested_ratio': '4奇2偶 或 5奇1偶',
                    'confidence': '95%',
                })
            else:
                recommendations.append({
                    'strategy': 'even_bias_exploit',
                    'description': f"偶数概率偏高（{1-mean_p:.2%}），倾向选择更多偶数",
                    'suggested_ratio': '2奇4偶 或 1奇5偶',
                    'confidence': '95%',
                })

        return {
            'recommendations': recommendations,
            'warning': (
                "贝叶斯分析只能检测统计显著性，不能保证预测准确。"
                "彩票仍是高度随机的游戏，请理性投注。"
            )
        }


def main():
    """测试贝叶斯分析器"""
    import sys
    import os
    sys.path.insert(0, os.getcwd())

    from database import db_manager

    lottery_type = 'BIG_LOTTO'
    analyzer = BayesianBiasAnalyzer(lottery_type, max_number=49)

    # 获取数据
    history = db_manager.get_all_draws(lottery_type)
    history.sort(key=lambda x: x['draw'], reverse=True)

    print("=" * 80)
    print("【贝叶斯偏差分析】")
    print("=" * 80)

    # 1. 号码偏差分析
    print("\n正在分析号码偏差...")
    bias_result = analyzer.analyze_number_bias(history[:300], confidence_level=0.95)

    print(f"\n✅ 分析完成！")
    print(f"分析数据: 最近300期")
    print(f"显著热号数量: {bias_result['summary']['hot_count']}")
    print(f"显著冷号数量: {bias_result['summary']['cold_count']}")

    if bias_result['summary']['hot_count'] > 0:
        print(f"\n【贝叶斯显著热号】（95%可信）")
        for item in bias_result['biased_numbers']['hot'][:5]:
            print(f"  号码{item['number']:2d}: 出现{item['count']}次, 概率{item['prob']:.4f}")

    if bias_result['summary']['cold_count'] > 0:
        print(f"\n【贝叶斯显著冷号】（95%可信）")
        for item in bias_result['biased_numbers']['cold'][:5]:
            print(f"  号码{item['number']:2d}: 出现{item['count']}次, 概率{item['prob']:.4f}")

    # 2. 奇偶比分析
    print("\n" + "=" * 80)
    print("正在分析奇偶比偏差...")
    odd_even_result = analyzer.analyze_odd_even_bias(history[:300])

    print(f"\n{odd_even_result['bayesian_inference']['interpretation']}")
    print(f"推荐: {odd_even_result['recommendation']}")

    # 3. 状态检测
    print("\n" + "=" * 80)
    print("正在检测状态切换...")
    state_result = analyzer.detect_state_regime(history[:300], window_size=50)

    print(f"\n{state_result['summary']['interpretation']}")
    print(f"检测到{state_result['summary']['changepoints_detected']}个潜在变点")

    # 4. 策略推荐
    print("\n" + "=" * 80)
    print("【策略推荐】")
    print("=" * 80)

    strategy_result = analyzer.recommend_strategy(bias_result, odd_even_result)

    for i, rec in enumerate(strategy_result['recommendations'], 1):
        print(f"\n策略{i}: {rec['strategy']}")
        print(f"  描述: {rec['description']}")
        if 'numbers' in rec:
            print(f"  推荐号码: {rec['numbers']}")
        if 'suggested_ratio' in rec:
            print(f"  建议奇偶比: {rec['suggested_ratio']}")
        print(f"  可信度: {rec['confidence']}")

    print(f"\n⚠️  {strategy_result['warning']}")

    # 保存结果
    output = {
        'bias_analysis': bias_result,
        'odd_even_analysis': odd_even_result,
        'state_detection': state_result,
        'recommendations': strategy_result
    }

    with open('data/bayesian_analysis_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n详细结果已保存: data/bayesian_analysis_results.json")


if __name__ == "__main__":
    main()
