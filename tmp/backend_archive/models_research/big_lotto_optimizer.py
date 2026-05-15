"""
大樂透預測優化器 - 基於 2025 年回測數據的優化
實施以下優化：
1. 連號約束 - 確保預測包含連號 (58.8% 開獎含連號)
2. 特別號權重調整 - 根據實際分布調整
3. 總和過濾器 - 過濾極端總和 (112-185)
4. 區域平衡 - 低/中/高區域平衡
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class BigLottoPredictionOptimizer:
    """
    大樂透預測優化器
    基於 2025 年回測數據分析結果
    """

    # === 基於回測的統計數據 ===

    # 常見連號組合 (出現次數 >= 3)
    COMMON_CONSECUTIVE_PAIRS = [
        (8, 9), (32, 33), (40, 41), (36, 37), (37, 38),
        (6, 7), (23, 24), (20, 21), (9, 10), (25, 26)
    ]

    # 特別號權重 (基於 2025 年分布，出現 4+ 次的號碼)
    # 28: +158%, 34: +158%, 2: +115%, 8: +115%, 33: +72%, 37: +72%...
    SPECIAL_NUMBER_HOT = [28, 34, 2, 8, 33, 37, 31, 42, 35, 27]
    SPECIAL_NUMBER_COLD = [3, 4, 5, 11, 16, 17, 19, 30, 39, 43, 45, 49]

    # 總和範圍 (基於分析: 平均 148.5 ± 36.1)
    SUM_RANGE_OPTIMAL = (112, 185)  # 平均 ± 1 標準差
    SUM_RANGE_ACCEPTABLE = (90, 210)

    # 區域分布目標 (低1-16/中17-33/高34-49)
    ZONE_TARGET = (2, 2, 2)  # 理想分布

    # 熱號 (2025 年出現最多)
    HOT_NUMBERS = [25, 7, 15, 26, 20, 2, 13]

    # 冷號 (2025 年出現最少)
    COLD_NUMBERS = [9, 27, 1, 12, 34, 28, 44]

    def __init__(self):
        self.optimization_stats = {
            'consecutive_added': 0,
            'sum_adjusted': 0,
            'zone_balanced': 0,
        }

    def optimize_prediction(
        self,
        predicted_numbers: List[int],
        predicted_special: Optional[int],
        history: List[Dict],
        rules: Dict
    ) -> Tuple[List[int], Optional[int]]:
        """
        優化預測結果

        注意：大樂透特別號是第7球（同池1-49），不需要預測
        只優化主號碼

        Args:
            predicted_numbers: 原始預測的主號碼
            predicted_special: 忽略（大樂透不預測特別號）
            history: 歷史數據
            rules: 彩票規則

        Returns:
            (優化後的主號碼, None)
        """
        min_num = rules.get('minNumber', 1)
        max_num = rules.get('maxNumber', 49)
        pick_count = rules.get('pickCount', 6)

        numbers = list(predicted_numbers[:pick_count])

        # 1. 連號約束
        numbers = self._ensure_consecutive(numbers, min_num, max_num)

        # 2. 總和約束
        numbers = self._optimize_sum(numbers, min_num, max_num)

        # 3. 區域平衡
        numbers = self._balance_zones(numbers, min_num, max_num)

        # 大樂透不預測特別號，返回 None
        return sorted(numbers), None

    def _ensure_consecutive(
        self,
        numbers: List[int],
        min_num: int,
        max_num: int
    ) -> List[int]:
        """
        確保預測包含連號 (58.8% 開獎含連號)
        使用溫和策略：優先調整現有號碼 ±1
        """
        numbers = sorted(numbers)

        # 檢查是否已有連號
        has_consecutive = any(
            numbers[i+1] - numbers[i] == 1
            for i in range(len(numbers) - 1)
        )

        if has_consecutive:
            return numbers

        # 只有 40% 機率應用連號約束（更保守，避免過度修改）
        if np.random.random() > 0.40:
            return numbers

        # === 策略1: 優先調整現有號碼 ±1 來創建連號 ===
        for i, n in enumerate(numbers):
            # 檢查 n+1 是否可以加入
            if n + 1 <= max_num and n + 1 not in numbers:
                for j, m in enumerate(numbers):
                    if i != j and m not in self.HOT_NUMBERS:
                        new_numbers = numbers.copy()
                        new_numbers[j] = n + 1
                        self.optimization_stats['consecutive_added'] += 1
                        return sorted(new_numbers)

            # 檢查 n-1 是否可以加入
            if n - 1 >= min_num and n - 1 not in numbers:
                for j, m in enumerate(numbers):
                    if i != j and m not in self.HOT_NUMBERS:
                        new_numbers = numbers.copy()
                        new_numbers[j] = n - 1
                        self.optimization_stats['consecutive_added'] += 1
                        return sorted(new_numbers)

        # === 策略2: 嘗試只替換一個非熱號 ===
        for pair in self.COMMON_CONSECUTIVE_PAIRS:
            n1, n2 = pair
            if n1 in numbers and n2 not in numbers:
                candidates = [n for n in numbers if n not in self.HOT_NUMBERS and n != n1]
                if candidates:
                    to_remove = candidates[0]
                    new_numbers = [n for n in numbers if n != to_remove]
                    new_numbers.append(n2)
                    self.optimization_stats['consecutive_added'] += 1
                    return sorted(new_numbers)[:6]
            elif n2 in numbers and n1 not in numbers:
                candidates = [n for n in numbers if n not in self.HOT_NUMBERS and n != n2]
                if candidates:
                    to_remove = candidates[0]
                    new_numbers = [n for n in numbers if n != to_remove]
                    new_numbers.append(n1)
                    self.optimization_stats['consecutive_added'] += 1
                    return sorted(new_numbers)[:6]

        return numbers

    def _optimize_sum(
        self,
        numbers: List[int],
        min_num: int,
        max_num: int
    ) -> List[int]:
        """
        優化總和到最佳範圍 (112-185)
        使用溫和策略：只在極端情況下調整
        """
        current_sum = sum(numbers)
        acceptable_min, acceptable_max = self.SUM_RANGE_ACCEPTABLE

        # 如果在可接受範圍內，不調整
        if acceptable_min <= current_sum <= acceptable_max:
            return numbers

        numbers = sorted(numbers)

        # 只調整非熱號，且幅度較小
        if current_sum < acceptable_min:
            diff = acceptable_min - current_sum
            for i, n in enumerate(numbers):
                if n not in self.HOT_NUMBERS:
                    target = min(n + min(diff + 5, 15), max_num)
                    while target in numbers and target <= max_num:
                        target += 1
                    if target <= max_num:
                        numbers[i] = target
                        self.optimization_stats['sum_adjusted'] += 1
                        break

        elif current_sum > acceptable_max:
            diff = current_sum - acceptable_max
            for i in range(len(numbers) - 1, -1, -1):
                if numbers[i] not in self.HOT_NUMBERS:
                    target = max(numbers[i] - min(diff + 5, 15), min_num)
                    while target in numbers and target >= min_num:
                        target -= 1
                    if target >= min_num:
                        numbers[i] = target
                        self.optimization_stats['sum_adjusted'] += 1
                        break

        return sorted(numbers)

    def _balance_zones(
        self,
        numbers: List[int],
        min_num: int,
        max_num: int
    ) -> List[int]:
        """
        平衡區域分布 (低1-16/中17-33/高34-49)
        目標: 2/2/2 分布
        """
        def get_zone(n):
            if n <= 16:
                return 'low'
            elif n <= 33:
                return 'mid'
            else:
                return 'high'

        zone_counts = {'low': 0, 'mid': 0, 'high': 0}
        for n in numbers:
            zone_counts[get_zone(n)] += 1

        # 只在極度不平衡時調整 (某區域 >= 5)
        # 大樂透範圍更大，允許更多不平衡
        max_in_zone = max(zone_counts.values())

        if max_in_zone < 5:
            return numbers  # 不調整，保持原預測

        self.optimization_stats['zone_balanced'] += 1

        excess_zone = max(zone_counts, key=zone_counts.get)
        deficit_zone = min(zone_counts, key=zone_counts.get)

        zone_ranges = {
            'low': (1, 16),
            'mid': (17, 33),
            'high': (34, 49)
        }

        # 只移動非熱號
        excess_nums = [n for n in numbers
                       if get_zone(n) == excess_zone and n not in self.HOT_NUMBERS]

        if not excess_nums:
            return numbers

        to_remove = excess_nums[0]

        # 優先選擇缺失區域中的熱號
        deficit_range = zone_ranges[deficit_zone]
        hot_in_deficit = [n for n in self.HOT_NUMBERS
                          if deficit_range[0] <= n <= deficit_range[1] and n not in numbers]

        if hot_in_deficit:
            replacement = hot_in_deficit[0]
        else:
            mid_val = (deficit_range[0] + deficit_range[1]) // 2
            replacement = mid_val
            while replacement in numbers:
                replacement += 1
                if replacement > deficit_range[1]:
                    replacement = deficit_range[0]
                    break

        if replacement not in numbers:
            numbers = [n for n in numbers if n != to_remove]
            numbers.append(replacement)

        return sorted(numbers)[:6]

    def _optimize_special(
        self,
        predicted_special: Optional[int],
        main_numbers: List[int],
        history: List[Dict]
    ) -> int:
        """
        優化特別號預測

        大樂透特別號範圍是 1-49，與主號同池
        考慮：
        1. 特別號歷史分布
        2. 避開已選的主號
        3. 近期出現情況
        """
        if predicted_special is None or predicted_special in main_numbers:
            # 從熱門特別號中選擇一個未被選為主號的
            for num in self.SPECIAL_NUMBER_HOT:
                if num not in main_numbers:
                    predicted_special = num
                    break
            else:
                # 如果熱門都被選了，隨機選一個
                available = [n for n in range(1, 50) if n not in main_numbers]
                predicted_special = np.random.choice(available)

        # 計算各號碼的分數
        scores = {}
        available_numbers = [n for n in range(1, 50) if n not in main_numbers]

        for num in available_numbers:
            score = 0.0

            # 1. 熱門特別號加分
            if num in self.SPECIAL_NUMBER_HOT:
                score += 0.4
            elif num in self.SPECIAL_NUMBER_COLD:
                score -= 0.2

            # 2. 近期遺漏值
            recent_specials = [d.get('special') for d in history[:15]]
            if num not in recent_specials:
                gap = 15
                for i, s in enumerate(recent_specials):
                    if s == num:
                        gap = i
                        break
                score += min(gap / 15, 0.3) * 0.4

            scores[num] = score

        # 選擇分數最高的，加入隨機性
        sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_5 = sorted_nums[:5]
        weights = [max(s + 0.5, 0.1) for _, s in top_5]
        total = sum(weights)

        if total > 0:
            probs = [w / total for w in weights]
            choice = np.random.choice([n for n, _ in top_5], p=probs)
            return int(choice)

        return predicted_special

    def get_optimization_stats(self) -> Dict:
        """獲取優化統計"""
        return self.optimization_stats.copy()


# 創建全局實例
big_lotto_optimizer = BigLottoPredictionOptimizer()


def optimize_big_lotto_prediction(
    predicted_numbers: List[int],
    predicted_special: Optional[int],
    history: List[Dict],
    rules: Dict
) -> Tuple[List[int], int]:
    """
    便捷函數：優化大樂透預測
    """
    return big_lotto_optimizer.optimize_prediction(
        predicted_numbers,
        predicted_special,
        history,
        rules
    )
