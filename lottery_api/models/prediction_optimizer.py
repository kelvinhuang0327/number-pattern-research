"""
預測優化器 - 基於 2025 年回測數據的優化
實施以下優化：
1. 連號約束 - 確保預測包含連號
2. 特別號權重調整 - 根據實際分布調整
3. 總和過濾器 - 過濾極端總和
4. 主號與特別號關聯 - 加入關聯預測
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class PowerLottoPredictionOptimizer:
    """
    威力彩預測優化器
    基於 2025 年回測數據分析結果
    """

    # === 基於回測的統計數據 ===

    # 常見連號組合 (出現次數 >= 7)
    COMMON_CONSECUTIVE_PAIRS = [
        (24, 25), (16, 17), (10, 11), (7, 8), (1, 2),
        (2, 3), (13, 14), (36, 37), (23, 24), (15, 16)
    ]

    # 特別號權重 (基於 2025 年分布)
    # 2: +70%, 4: +37%, 5: +5%, 6: -3%, 3: -11%, 7: -19%, 8: -27%, 1: -52%
    SPECIAL_NUMBER_WEIGHTS = {
        1: 0.48,  # -52%
        2: 1.70,  # +70% (最熱)
        3: 0.89,  # -11%
        4: 1.37,  # +37%
        5: 1.05,  # +5%
        6: 0.97,  # -3%
        7: 0.81,  # -19%
        8: 0.73,  # -27%
    }

    # 總和範圍 (基於分析)
    SUM_RANGE_OPTIMAL = (89, 136)  # 平均 113.3 ± 23.7
    SUM_RANGE_ACCEPTABLE = (70, 155)

    # 區域分布目標 (低1-13/中14-26/高27-38)
    ZONE_TARGET = (2, 2, 2)  # 理想分布

    # 奇偶分布目標
    ODD_EVEN_TARGET = 3  # 理想奇數個數

    # 熱號 (平均間隔 < 5.5)
    HOT_NUMBERS = [14, 20, 17, 11, 38, 15, 24]

    # 冷號 (平均間隔 > 8)
    COLD_NUMBERS = [28, 34, 32, 10, 1]

    # 特別號與主號關聯
    SPECIAL_MAIN_CORRELATION = {
        1: [23, 18, 2],
        2: [33, 31, 20],
        3: [14, 38, 25],
        4: [18, 29, 2],
        5: [15, 17, 22],
        6: [21, 11, 17],
        7: [25, 4, 29],
        8: [3, 20, 25],
    }

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
    ) -> Tuple[List[int], int]:
        """
        優化預測結果

        Args:
            predicted_numbers: 原始預測的主號碼
            predicted_special: 原始預測的特別號
            history: 歷史數據
            rules: 彩票規則

        Returns:
            (優化後的主號碼, 優化後的特別號)
        """
        min_num = rules.get('minNumber', 1)
        max_num = rules.get('maxNumber', 38)
        pick_count = rules.get('pickCount', 6)

        numbers = list(predicted_numbers[:pick_count])

        # 1. 連號約束
        numbers = self._ensure_consecutive(numbers, min_num, max_num)

        # 2. 總和約束
        numbers = self._optimize_sum(numbers, min_num, max_num)

        # 3. 區域平衡
        numbers = self._balance_zones(numbers, min_num, max_num)

        # 4. 優化特別號
        special = self._optimize_special(predicted_special, numbers, history)

        return sorted(numbers), special

    def _ensure_consecutive(
        self,
        numbers: List[int],
        min_num: int,
        max_num: int
    ) -> List[int]:
        """
        確保預測包含連號 (60% 開獎含連號)
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

        # 60% 機率應用連號約束（匹配實際開獎分布）
        if np.random.random() > 0.60:
            return numbers

        # === 策略1: 優先調整現有號碼 ±1 來創建連號 ===
        # 嘗試將某個號碼 +1 或 -1，與另一個現有號碼形成連號
        for i, n in enumerate(numbers):
            # 檢查 n+1 是否可以加入
            if n + 1 <= max_num and n + 1 not in numbers:
                # 找一個可以被替換的號碼（優先非熱號）
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

        # === 策略2: 如果策略1失敗，嘗試只替換一個非熱號 ===
        # 找出一個可以形成連號的常見組合
        for pair in self.COMMON_CONSECUTIVE_PAIRS:
            n1, n2 = pair
            # 如果已有其中一個，只需加另一個
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

        # 不強制修改，保持原預測
        return numbers

    def _optimize_sum(
        self,
        numbers: List[int],
        min_num: int,
        max_num: int
    ) -> List[int]:
        """
        優化總和到最佳範圍 (89-136)
        使用溫和策略：只在極端情況下調整
        """
        current_sum = sum(numbers)
        acceptable_min, acceptable_max = self.SUM_RANGE_ACCEPTABLE  # 使用寬鬆範圍

        # 如果在可接受範圍內，不調整
        if acceptable_min <= current_sum <= acceptable_max:
            return numbers

        numbers = sorted(numbers)

        # 只調整非熱號，且幅度較小
        if current_sum < acceptable_min:
            diff = acceptable_min - current_sum
            # 找一個非熱號來調整
            for i, n in enumerate(numbers):
                if n not in self.HOT_NUMBERS:
                    # 小幅調整，不超過 diff + 3
                    target = min(n + min(diff + 3, 10), max_num)
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
                    target = max(numbers[i] - min(diff + 3, 10), min_num)
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
        平衡區域分布 (低2/中2/高2)
        使用溫和策略：只在極度不平衡時調整
        """
        def get_zone(n):
            if n <= 13:
                return 'low'
            elif n <= 26:
                return 'mid'
            else:
                return 'high'

        zone_counts = {'low': 0, 'mid': 0, 'high': 0}
        for n in numbers:
            zone_counts[get_zone(n)] += 1

        # 只在極度不平衡時調整 (某區域 >= 5 或全部集中在兩區)
        max_in_zone = max(zone_counts.values())
        min_in_zone = min(zone_counts.values())

        # 只處理極端情況：5+ 在同一區域，或某區域完全空白
        if max_in_zone < 5 and min_in_zone > 0:
            return numbers  # 不調整

        self.optimization_stats['zone_balanced'] += 1

        # 找出過多和過少的區域
        excess_zone = max(zone_counts, key=zone_counts.get)
        deficit_zone = min(zone_counts, key=zone_counts.get)

        zone_ranges = {
            'low': (1, 13),
            'mid': (14, 26),
            'high': (27, 38)
        }

        # 只移動非熱號
        excess_nums = [n for n in numbers
                       if get_zone(n) == excess_zone and n not in self.HOT_NUMBERS]

        if not excess_nums:
            return numbers  # 全是熱號，不調整

        to_remove = excess_nums[0]

        # 優先選擇缺失區域中的熱號
        deficit_range = zone_ranges[deficit_zone]
        hot_in_deficit = [n for n in self.HOT_NUMBERS
                          if deficit_range[0] <= n <= deficit_range[1] and n not in numbers]

        if hot_in_deficit:
            replacement = hot_in_deficit[0]
        else:
            # 選擇區域中間的號碼
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

        考慮：
        1. 特別號權重 (2025 年分布)
        2. 主號關聯
        3. 近期出現情況
        """
        if predicted_special is None:
            predicted_special = 2  # 默認使用最熱的號碼

        # 計算各號碼的分數
        scores = {}

        for num in range(1, 9):
            score = 0.0

            # 1. 基礎權重 (基於 2025 年分布)
            score += self.SPECIAL_NUMBER_WEIGHTS.get(num, 1.0) * 0.4

            # 2. 主號關聯加分
            correlated_mains = self.SPECIAL_MAIN_CORRELATION.get(num, [])
            overlap = len(set(correlated_mains) & set(main_numbers))
            score += overlap * 0.2

            # 3. 近期遺漏值 (最近 10 期沒出現的號碼加分)
            recent_specials = [d.get('special') for d in history[:10]]
            if num not in recent_specials:
                gap = 10  # 10 期沒出現
                for i, s in enumerate(recent_specials):
                    if s == num:
                        gap = i
                        break
                score += min(gap / 10, 0.3) * 0.4

            scores[num] = score

        # 選擇分數最高的，但加入一些隨機性
        sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # 從 top 3 中按權重選擇
        top_3 = sorted_nums[:3]
        weights = [s for _, s in top_3]
        total = sum(weights)

        if total > 0:
            probs = [w / total for w in weights]
            choice = np.random.choice([n for n, _ in top_3], p=probs)
            return int(choice)

        return predicted_special

    def get_optimization_stats(self) -> Dict:
        """獲取優化統計"""
        return self.optimization_stats.copy()


# 創建全局實例
power_lotto_optimizer = PowerLottoPredictionOptimizer()


def optimize_power_lotto_prediction(
    predicted_numbers: List[int],
    predicted_special: Optional[int],
    history: List[Dict],
    rules: Dict
) -> Tuple[List[int], int]:
    """
    便捷函數：優化威力彩預測
    """
    return power_lotto_optimizer.optimize_prediction(
        predicted_numbers,
        predicted_special,
        history,
        rules
    )
