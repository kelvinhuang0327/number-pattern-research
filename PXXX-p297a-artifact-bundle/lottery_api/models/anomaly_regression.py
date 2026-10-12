"""
异常检测+回归预测策略

核心思想:
1. 检测最近期数是否出现异常模式（全大号、全奇数、多连号等）
2. 如果异常 → 预测回归号码（反向补偿）
3. 如果正常 → 使用标准集成方法

理论基础:
- 均值回归理论 (Mean Reversion)
- 异常检测后的反向纠偏
- 基于大数定律的长期平衡

预期效果: +1-2% Match-3+ 率
"""
import numpy as np
from typing import List, Dict, Optional
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class AnomalyRegressionPredictor:
    """异常检测+回归预测器"""

    def __init__(self):
        self.anomaly_threshold = {
            'all_large_ratio': 0.8,  # 80%以上是大号
            'all_small_ratio': 0.8,  # 80%以上是小号
            'all_odd_ratio': 0.8,   # 80%以上是奇数
            'all_even_ratio': 0.8,  # 80%以上是偶数
            'consecutive_count': 3,  # 连号3个以上
            'same_zone_count': 4,    # 同一区域4个以上
        }

    def predict(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        unified_engine=None
    ) -> Dict:
        """
        主预测方法

        Args:
            history: 历史开奖数据
            lottery_rules: 彩票规则
            unified_engine: UnifiedPredictionEngine实例（用于标准预测）

        Returns:
            预测结果字典
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # Step 1: 检测最近是否有异常
        anomaly_info = self.detect_recent_anomaly(history, window=5)

        # Step 2: 根据异常情况选择策略
        if anomaly_info['has_anomaly']:
            logger.info(f"🔍 检测到异常模式: {anomaly_info['anomaly_types']}")
            result = self._regression_predict(
                anomaly_info, history, lottery_rules
            )
            result['method'] = f"异常回归策略 (检测到: {', '.join(anomaly_info['anomaly_types'])})"
            result['is_regression'] = True
        else:
            # 无异常，使用标准集成方法
            if unified_engine:
                # 使用5ME集成（当前最佳）
                result = self._ensemble_predict(unified_engine, history, lottery_rules)
                result['method'] = "标准集成策略 (5ME)"
            else:
                # 降级到简单统计
                result = self._fallback_predict(history, lottery_rules)
                result['method'] = "降级统计策略"
            result['is_regression'] = False

        result['anomaly_info'] = anomaly_info
        return result

    def detect_recent_anomaly(
        self,
        history: List[Dict],
        window: int = 5
    ) -> Dict:
        """
        检测最近window期是否有异常模式

        Args:
            history: 历史开奖数据
            window: 检测窗口（最近几期）

        Returns:
            {
                'has_anomaly': bool,
                'anomaly_types': List[str],
                'details': Dict
            }
        """
        if len(history) < window:
            return {'has_anomaly': False, 'anomaly_types': [], 'details': {}}

        recent_draws = history[-window:]
        anomaly_types = []
        details = {}

        # 分析最近一期（权重最高）
        latest_draw = history[-1]
        latest_nums = latest_draw.get('numbers', [])

        if not latest_nums:
            return {'has_anomaly': False, 'anomaly_types': [], 'details': {}}

        # 检测1: 全大号/全小号
        mid_point = (min(latest_nums) + max(latest_nums)) // 2
        if not mid_point:
            mid_point = 25  # 默认中点

        large_count = sum(1 for n in latest_nums if n > mid_point)
        small_count = len(latest_nums) - large_count

        if large_count / len(latest_nums) >= self.anomaly_threshold['all_large_ratio']:
            anomaly_types.append('全大号')
            details['all_large'] = True
        elif small_count / len(latest_nums) >= self.anomaly_threshold['all_small_ratio']:
            anomaly_types.append('全小号')
            details['all_small'] = True

        # 检测2: 全奇数/全偶数
        odd_count = sum(1 for n in latest_nums if n % 2 == 1)
        even_count = len(latest_nums) - odd_count

        if odd_count / len(latest_nums) >= self.anomaly_threshold['all_odd_ratio']:
            anomaly_types.append('全奇数')
            details['all_odd'] = True
        elif even_count / len(latest_nums) >= self.anomaly_threshold['all_even_ratio']:
            anomaly_types.append('全偶数')
            details['all_even'] = True

        # 检测3: 连号过多
        sorted_nums = sorted(latest_nums)
        consecutive_count = 1
        max_consecutive = 1

        for i in range(1, len(sorted_nums)):
            if sorted_nums[i] == sorted_nums[i-1] + 1:
                consecutive_count += 1
                max_consecutive = max(max_consecutive, consecutive_count)
            else:
                consecutive_count = 1

        if max_consecutive >= self.anomaly_threshold['consecutive_count']:
            anomaly_types.append(f'{max_consecutive}连号')
            details['many_consecutive'] = True
            details['consecutive_count'] = max_consecutive

        # 检测4: 同区域集中
        # 分5个区域
        num_range = max(latest_nums) - min(latest_nums) + 1
        zone_size = num_range // 5 or 10
        zone_counts = Counter()

        for num in latest_nums:
            zone = (num - 1) // zone_size
            zone_counts[zone] += 1

        max_zone_count = max(zone_counts.values()) if zone_counts else 0
        if max_zone_count >= self.anomaly_threshold['same_zone_count']:
            anomaly_types.append(f'区域集中')
            details['zone_concentrated'] = True
            details['max_zone_count'] = max_zone_count

        # 检测5: 历史罕见组合（进阶检测）
        # 计算最近一期号码的总和
        latest_sum = sum(latest_nums)
        
        # 计算历史总和的均值和标准差
        historical_sums = [sum(draw.get('numbers', [])) for draw in history[:-1]]
        if historical_sums:
            mean_sum = np.mean(historical_sums)
            std_sum = np.std(historical_sums)
            
            # 如果总和偏离均值超过2.5个标准差
            if std_sum > 0:
                z_score = abs((latest_sum - mean_sum) / std_sum)
                if z_score > 2.5:
                    anomaly_types.append(f'总和异常(z={z_score:.1f})')
                    details['sum_anomaly'] = True
                    details['sum_z_score'] = z_score

        return {
            'has_anomaly': len(anomaly_types) > 0,
            'anomaly_types': anomaly_types,
            'anomaly_count': len(anomaly_types),
            'details': details,
            'latest_numbers': latest_nums
        }

    def _regression_predict(
        self,
        anomaly_info: Dict,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        异常后的回归预测

        核心策略: 反向补偿异常模式
        - 如果全大号 → 增加小号权重
        - 如果全奇数 → 增加偶数权重
        - 如果多连号 → 降低连号权重
        - 如果区域集中 → 分散到其他区域
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # 初始化所有号码的基础分数
        scores = np.ones(max_num + 1) * 0.5  # 基础分数0.5
        details = anomaly_info['details']

        # 反向补偿策略
        mid_point = (min_num + max_num) // 2

        # 补偿1: 大小号反转
        if details.get('all_large'):
            # 上期全大号 → 加权小号
            for i in range(min_num, mid_point + 1):
                scores[i] += 0.8
            logger.info("🔄 反转策略: 全大号 → 增加小号权重")

        elif details.get('all_small'):
            # 上期全小号 → 加权大号
            for i in range(mid_point + 1, max_num + 1):
                scores[i] += 0.8
            logger.info("🔄 反转策略: 全小号 → 增加大号权重")

        # 补偿2: 奇偶反转
        if details.get('all_odd'):
            # 上期全奇数 → 加权偶数
            for i in range(min_num, max_num + 1):
                if i % 2 == 0:
                    scores[i] += 0.8
            logger.info("🔄 反转策略: 全奇数 → 增加偶数权重")

        elif details.get('all_even'):
            # 上期全偶数 → 加权奇数
            for i in range(min_num, max_num + 1):
                if i % 2 == 1:
                    scores[i] += 0.8
            logger.info("🔄 反转策略: 全偶数 → 增加奇数权重")

        # 补偿3: 避免连号
        if details.get('many_consecutive'):
            latest_nums = anomaly_info['latest_numbers']
            sorted_nums = sorted(latest_nums)

            # 降低上期连号及其邻近号码的权重
            for num in sorted_nums:
                if num - 1 >= min_num:
                    scores[num - 1] *= 0.5
                scores[num] *= 0.3  # 上期号码大幅降权
                if num + 1 <= max_num:
                    scores[num + 1] *= 0.5

            logger.info("🔄 反转策略: 多连号 → 避免连号区域")

        # 补偿4: 区域分散
        if details.get('zone_concentrated'):
            # 计算上期号码的区域分布
            latest_nums = anomaly_info['latest_numbers']
            zone_size = (max_num - min_num + 1) // 5
            zone_counts = Counter()

            for num in latest_nums:
                zone = (num - min_num) // zone_size
                zone_counts[zone] += 1

            # 找出集中的区域
            max_zone = max(zone_counts, key=zone_counts.get)
            
            # 降低集中区域的权重，增加其他区域
            for i in range(min_num, max_num + 1):
                current_zone = (i - min_num) // zone_size
                if current_zone == max_zone:
                    scores[i] *= 0.4  # 集中区域降权
                else:
                    scores[i] += 0.6  # 其他区域加权

            logger.info(f"🔄 反转策略: 区域集中 → 避开区域{max_zone}")

        # 综合选号
        predicted_numbers = self._select_top_numbers(scores, pick_count, min_num, max_num)

        # 计算信心度（基于异常强度）
        anomaly_count = anomaly_info['anomaly_count']
        confidence = min(0.85, 0.65 + anomaly_count * 0.1)  # 异常越多，信心越高

        return {
            'numbers': predicted_numbers,
            'confidence': float(confidence),
            'scores': scores[min_num:max_num+1].tolist(),
            'regression_details': {
                'anomaly_types': anomaly_info['anomaly_types'],
                'compensation_applied': True
            }
        }

    def _select_top_numbers(
        self,
        scores: np.ndarray,
        pick_count: int,
        min_num: int,
        max_num: int
    ) -> List[int]:
        """根据分数选择Top K号码"""
        valid_scores = [(i, scores[i]) for i in range(min_num, max_num + 1)]
        sorted_scores = sorted(valid_scores, key=lambda x: x[1], reverse=True)
        
        # 选择前pick_count个
        selected = [num for num, score in sorted_scores[:pick_count]]
        
        return sorted(selected)

    def _ensemble_predict(
        self,
        unified_engine,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        使用集成方法预测（5ME）
        
        方法组合: Statistical + Deviation + Markov + Hot_Cold + Trend
        """
        methods = [
            'statistical_predict',
            'deviation_predict',
            'markov_predict',
            'hot_cold_mix_predict',
            'trend_predict'
        ]

        all_predictions = []
        for method_name in methods:
            method = getattr(unified_engine, method_name, None)
            if method:
                try:
                    result = method(history, lottery_rules)
                    all_predictions.append(result['numbers'])
                except Exception as e:
                    logger.warning(f"方法 {method_name} 失败: {e}")

        if not all_predictions:
            # 降级
            return self._fallback_predict(history, lottery_rules)

        # 融合：统计各号码出现次数
        number_votes = Counter()
        for pred in all_predictions:
            number_votes.update(pred)

        # 选择得票最多的号码
        pick_count = lottery_rules.get('pickCount', 6)
        top_numbers = [num for num, count in number_votes.most_common(pick_count)]

        return {
            'numbers': sorted(top_numbers),
            'confidence': 0.75,
            'ensemble_size': len(all_predictions)
        }

    def _fallback_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """降级预测：简单频率统计"""
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # 统计频率
        all_numbers = []
        for draw in history[-100:]:  # 最近100期
            all_numbers.extend(draw.get('numbers', []))

        freq = Counter(all_numbers)
        
        # 选择高频号码
        top_numbers = []
        for num, count in freq.most_common(max_num):
            if min_num <= num <= max_num:
                top_numbers.append(num)
            if len(top_numbers) >= pick_count:
                break

        # 如果不够，随机补充
        while len(top_numbers) < pick_count:
            candidate = np.random.randint(min_num, max_num + 1)
            if candidate not in top_numbers:
                top_numbers.append(candidate)

        return {
            'numbers': sorted(top_numbers),
            'confidence': 0.50
        }
