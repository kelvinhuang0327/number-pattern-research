"""
組合約束過濾預測器 (Constraint Filter Predictor)

核心理論：
不是預測「哪些號碼會出現」，而是過濾掉「哪些組合不太可能出現」

根據歷史統計，以下類型的組合出現機率較低：
1. 全奇或全偶 (約5%的組合)
2. 連續6個號碼 (如 1,2,3,4,5,6)
3. 全在同一區間 (如全在1-10)
4. 和值過大或過小 (正常範圍 120-180)
5. 尾數全相同 (如 1,11,21,31,41, ...)

策略：生成符合約束的高品質組合
"""

import numpy as np
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Set, Optional
from itertools import combinations
import random
import logging

logger = logging.getLogger(__name__)


class ConstraintFilterPredictor:
    """
    組合約束過濾預測器

    通過統計約束過濾不合理組合，生成高品質預測
    """

    def __init__(self):
        self.name = "ConstraintFilterPredictor"

        # 約束規則 (基於歷史統計)
        self.constraints = {
            'odd_even_ratio': (2, 4),     # 奇數個數範圍 [2,4]
            'zone_distribution': (3, 5),   # 至少分佈在3-5個區間
            'sum_range': (120, 180),       # 和值範圍
            'max_consecutive': 2,          # 最多允許2個連號
            'tail_diversity': 4,           # 至少4種不同尾數
        }

        # 區間定義
        self.zones = [
            (1, 10), (11, 20), (21, 30), (31, 40), (41, 49)
        ]

    def _check_odd_even(self, numbers: List[int]) -> bool:
        """檢查奇偶比例"""
        odd_count = sum(1 for n in numbers if n % 2 == 1)
        min_odd, max_odd = self.constraints['odd_even_ratio']
        return min_odd <= odd_count <= max_odd

    def _check_zone_distribution(self, numbers: List[int]) -> bool:
        """檢查區間分佈"""
        zones_covered = set()
        for num in numbers:
            for i, (low, high) in enumerate(self.zones):
                if low <= num <= high:
                    zones_covered.add(i)
                    break
        min_zones, max_zones = self.constraints['zone_distribution']
        return len(zones_covered) >= min_zones

    def _check_sum_range(self, numbers: List[int]) -> bool:
        """檢查和值範圍"""
        total = sum(numbers)
        min_sum, max_sum = self.constraints['sum_range']
        return min_sum <= total <= max_sum

    def _check_consecutive(self, numbers: List[int]) -> bool:
        """檢查連號數量"""
        sorted_nums = sorted(numbers)
        max_consecutive = 1
        current_consecutive = 1

        for i in range(1, len(sorted_nums)):
            if sorted_nums[i] == sorted_nums[i-1] + 1:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 1

        return max_consecutive <= self.constraints['max_consecutive']

    def _check_tail_diversity(self, numbers: List[int]) -> bool:
        """檢查尾數多樣性"""
        tails = set(n % 10 for n in numbers)
        return len(tails) >= self.constraints['tail_diversity']

    def passes_all_constraints(self, numbers: List[int]) -> Tuple[bool, List[str]]:
        """
        檢查組合是否通過所有約束

        Returns:
            (是否通過, 失敗原因列表)
        """
        failures = []

        if not self._check_odd_even(numbers):
            failures.append('odd_even')
        if not self._check_zone_distribution(numbers):
            failures.append('zone_distribution')
        if not self._check_sum_range(numbers):
            failures.append('sum_range')
        if not self._check_consecutive(numbers):
            failures.append('consecutive')
        if not self._check_tail_diversity(numbers):
            failures.append('tail_diversity')

        return len(failures) == 0, failures

    def calculate_number_weights(self, history: List[Dict],
                                  min_num: int, max_num: int,
                                  window: int = 100) -> Dict[int, float]:
        """
        計算號碼權重 (結合頻率和遺漏)
        """
        recent = history[:window]

        # 頻率統計
        freq = Counter()
        for draw in recent:
            freq.update(draw.get('numbers', []))

        # 遺漏統計
        last_seen = {n: window for n in range(min_num, max_num + 1)}
        for i, draw in enumerate(recent):
            for num in draw.get('numbers', []):
                if last_seen[num] == window:
                    last_seen[num] = i

        # 計算權重: 頻率分數 + 遺漏回歸分數
        weights = {}
        max_freq = max(freq.values()) if freq else 1

        for num in range(min_num, max_num + 1):
            freq_score = freq.get(num, 0) / max_freq

            # 遺漏分數：8-15期未出現時權重最高
            gap = last_seen[num]
            if gap < 8:
                gap_score = gap / 8 * 0.5
            elif gap <= 15:
                gap_score = 1.0
            else:
                gap_score = max(0.3, 0.9 ** ((gap - 15) / 5))

            weights[num] = 0.5 * freq_score + 0.5 * gap_score

        return weights

    def generate_valid_combination(self, weights: Dict[int, float],
                                    pick_count: int,
                                    max_attempts: int = 1000) -> Optional[List[int]]:
        """
        生成一個符合所有約束的組合
        """
        numbers = list(weights.keys())
        probs = np.array([weights[n] for n in numbers])
        probs = probs / probs.sum()

        for _ in range(max_attempts):
            try:
                selected = np.random.choice(numbers, size=pick_count,
                                           replace=False, p=probs)
                selected = sorted(selected.tolist())

                passed, _ = self.passes_all_constraints(selected)
                if passed:
                    return selected
            except:
                continue

        # 備用：純隨機生成
        return sorted(random.sample(numbers, pick_count))

    def predict(self, history: List[Dict], lottery_rules: Dict,
                num_combinations: int = 1) -> Dict:
        """
        生成符合約束的預測組合
        """
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))

        # 計算號碼權重
        weights = self.calculate_number_weights(history, min_num, max_num)

        # 生成組合
        combinations_list = []
        used_combos = set()

        for _ in range(num_combinations):
            combo = self.generate_valid_combination(weights, pick_count)
            if combo and tuple(combo) not in used_combos:
                combinations_list.append(combo)
                used_combos.add(tuple(combo))

        # 特別號
        special = None
        if lottery_rules.get('hasSpecialNumber', False):
            special = self._predict_special(history, lottery_rules)

        return {
            'numbers': combinations_list[0] if combinations_list else [],
            'all_combinations': combinations_list,
            'special': special,
            'method': 'constraint_filter',
            'confidence': 0.6,
            'constraints_applied': list(self.constraints.keys())
        }

    def predict_multi_bet(self, history: List[Dict],
                          lottery_rules: Dict,
                          num_bets: int = 2) -> Dict:
        """
        生成多注互補組合

        策略：
        1. 第一注：純約束過濾 (高權重號碼)
        2. 第二注：反向策略 (選擇權重次高且與第一注不重疊的號碼)
        """
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))

        weights = self.calculate_number_weights(history, min_num, max_num)

        bets = []
        all_used = set()

        for bet_idx in range(num_bets):
            if bet_idx == 0:
                # 第一注：標準權重
                adjusted_weights = weights.copy()
            else:
                # 後續注：降低已使用號碼的權重，增加覆蓋率
                adjusted_weights = {}
                for num, w in weights.items():
                    if num in all_used:
                        adjusted_weights[num] = w * 0.3  # 降低權重但不完全排除
                    else:
                        adjusted_weights[num] = w * 1.2  # 提高未使用號碼權重

            combo = self.generate_valid_combination(adjusted_weights, pick_count)
            if combo:
                bets.append({
                    'numbers': combo,
                    'source': f'constraint_filter_{bet_idx+1}'
                })
                all_used.update(combo)

        # 特別號
        specials = None
        if lottery_rules.get('hasSpecialNumber', False):
            specials = self._predict_multiple_specials(history, lottery_rules, num_bets)

        # 覆蓋率
        coverage = len(all_used) / (max_num - min_num + 1)

        return {
            'bets': bets,
            'specials': specials,
            'coverage': coverage,
            'total_unique_numbers': len(all_used),
            'method': 'constraint_filter_multi'
        }

    def _predict_special(self, history: List[Dict], lottery_rules: Dict) -> int:
        """預測特別號"""
        special_min = lottery_rules.get('specialMinNumber',
                                        lottery_rules.get('specialMin', 1))
        special_max = lottery_rules.get('specialMaxNumber',
                                        lottery_rules.get('specialMax', 49))

        special_freq = Counter()
        for draw in history[:100]:
            special = draw.get('special_number') or draw.get('special')
            if special is not None:
                special_freq[special] += 1

        if special_freq:
            return special_freq.most_common(1)[0][0]
        return (special_min + special_max) // 2

    def _predict_multiple_specials(self, history: List[Dict],
                                    lottery_rules: Dict,
                                    num_bets: int) -> List[int]:
        """預測多個特別號"""
        special_min = lottery_rules.get('specialMinNumber',
                                        lottery_rules.get('specialMin', 1))
        special_max = lottery_rules.get('specialMaxNumber',
                                        lottery_rules.get('specialMax', 8))

        special_freq = Counter()
        for draw in history[:100]:
            special = draw.get('special_number') or draw.get('special')
            if special is not None:
                special_freq[special] += 1

        specials = [s for s, _ in special_freq.most_common(num_bets)]

        while len(specials) < num_bets:
            for num in range(special_min, special_max + 1):
                if num not in specials:
                    specials.append(num)
                    if len(specials) >= num_bets:
                        break

        return specials[:num_bets]

    def analyze_historical_constraints(self, history: List[Dict],
                                        lottery_rules: Dict,
                                        window: int = 200) -> Dict:
        """
        分析歷史數據中各約束的符合率
        """
        recent = history[:window]
        stats = {
            'total': len(recent),
            'odd_even_pass': 0,
            'zone_pass': 0,
            'sum_pass': 0,
            'consecutive_pass': 0,
            'tail_pass': 0,
            'all_pass': 0,
        }

        for draw in recent:
            numbers = draw.get('numbers', [])
            if len(numbers) < 6:
                continue

            passed, failures = self.passes_all_constraints(numbers)

            if 'odd_even' not in failures:
                stats['odd_even_pass'] += 1
            if 'zone_distribution' not in failures:
                stats['zone_pass'] += 1
            if 'sum_range' not in failures:
                stats['sum_pass'] += 1
            if 'consecutive' not in failures:
                stats['consecutive_pass'] += 1
            if 'tail_diversity' not in failures:
                stats['tail_pass'] += 1
            if passed:
                stats['all_pass'] += 1

        # 計算百分比
        total = stats['total']
        if total > 0:
            stats['odd_even_pct'] = stats['odd_even_pass'] / total
            stats['zone_pct'] = stats['zone_pass'] / total
            stats['sum_pct'] = stats['sum_pass'] / total
            stats['consecutive_pct'] = stats['consecutive_pass'] / total
            stats['tail_pct'] = stats['tail_pass'] / total
            stats['all_pass_pct'] = stats['all_pass'] / total

        return stats


# 單例
constraint_filter_predictor = ConstraintFilterPredictor()


def test_constraint_filter():
    """測試約束過濾預測器"""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    from database import DatabaseManager
    from common import get_lottery_rules

    print("=" * 80)
    print("組合約束過濾預測器測試")
    print("=" * 80)

    db = DatabaseManager(db_path=os.path.join(os.path.dirname(__file__), '..', 'data', 'lottery_v2.db'))
    draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')

    predictor = ConstraintFilterPredictor()

    # 分析歷史約束符合率
    print("\n歷史數據約束符合率分析:")
    print("-" * 50)
    stats = predictor.analyze_historical_constraints(draws, rules)
    print(f"  奇偶比例 (2-4奇): {stats.get('odd_even_pct', 0)*100:.1f}%")
    print(f"  區間分佈 (≥3區): {stats.get('zone_pct', 0)*100:.1f}%")
    print(f"  和值範圍 (120-180): {stats.get('sum_pct', 0)*100:.1f}%")
    print(f"  連號限制 (≤2連): {stats.get('consecutive_pct', 0)*100:.1f}%")
    print(f"  尾數多樣 (≥4種): {stats.get('tail_pct', 0)*100:.1f}%")
    print(f"  全部通過: {stats.get('all_pass_pct', 0)*100:.1f}%")

    # 生成預測
    print("\n單注預測:")
    result = predictor.predict(draws[1:], rules)
    print(f"  號碼: {result['numbers']}")

    print("\n2注預測:")
    multi = predictor.predict_multi_bet(draws[1:], rules, num_bets=2)
    for i, bet in enumerate(multi['bets']):
        print(f"  第{i+1}注: {bet['numbers']}")
    print(f"  覆蓋率: {multi['coverage']*100:.1f}%")

    return predictor


if __name__ == '__main__':
    test_constraint_filter()
