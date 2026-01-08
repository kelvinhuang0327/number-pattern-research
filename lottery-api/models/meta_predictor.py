#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
元學習預測器 (Meta Predictor)

核心概念：
- 不依賴單一方法
- 整合所有預測方法的結果
- 根據情境動態調整權重
- 學習何時用哪種方法

混合策略 (建議配置)：
- 30% 熵驅動AI (創新方法，避開共識陷阱)
- 25% 偏差分析 (回測冠軍 3.68%)
- 20% 社群智慧 (避開熱門號碼，提升獨得獎金)
- 15% 異常檢測 (反向選號)
- 10% 量子隨機 (真隨機基準)
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from collections import Counter


class MetaPredictor:
    """元學習預測器：整合所有方法"""

    def __init__(self, max_num: int = 49):
        """
        初始化元預測器

        Args:
            max_num: 最大號碼
        """
        self.max_num = max_num

        # 預設權重配置
        self.default_weights = {
            'entropy': 0.30,      # 熵驅動 Transformer
            'deviation': 0.25,    # 偏差分析
            'social': 0.20,       # 社群智慧
            'anomaly': 0.15,      # 異常檢測
            'quantum': 0.10,      # 量子隨機
        }

        # 其他可選方法的權重（如果使用）
        self.optional_weights = {
            'frequency': 0.10,    # 頻率分析
            'trend': 0.08,        # 趨勢分析
            'bayesian': 0.12,     # 貝葉斯機率
            'hot_cold': 0.09,     # 熱冷混合
        }

    def predict_with_ensemble(
        self,
        predictions: Dict[str, List[int]],
        weights: Optional[Dict[str, float]] = None,
        pick_count: int = 6
    ) -> Tuple[List[int], Dict]:
        """
        使用加權集成預測

        Args:
            predictions: 各方法的預測結果 {'method_name': [numbers]}
            weights: 各方法的權重（可選，預設使用 default_weights）
            pick_count: 選號數量

        Returns:
            (預測號碼, 詳細資訊)
        """
        if weights is None:
            weights = self.default_weights

        # 建立號碼評分表
        number_scores = np.zeros(self.max_num)

        # 統計資訊
        method_contributions = {}

        for method, numbers in predictions.items():
            if method not in weights:
                continue

            weight = weights[method]

            # 給這些號碼加權
            for num in numbers:
                if 1 <= num <= self.max_num:
                    number_scores[num - 1] += weight

            method_contributions[method] = {
                'weight': weight,
                'numbers': numbers,
                'contribution': weight * len(numbers)
            }

        # 選擇分數最高的號碼
        top_indices = np.argsort(number_scores)[-pick_count:][::-1]
        predicted_numbers = sorted([int(idx + 1) for idx in top_indices])

        # 分析每個號碼來自哪些方法
        number_sources = {}
        for num in predicted_numbers:
            sources = [method for method, nums in predictions.items() if num in nums]
            number_sources[num] = sources

        details = {
            'method_contributions': method_contributions,
            'number_scores': number_scores,
            'number_sources': number_sources,
            'consensus_count': len([num for num, sources in number_sources.items() if len(sources) >= 3])
        }

        return predicted_numbers, details

    def predict_diversified(
        self,
        predictions: Dict[str, List[int]],
        n_bets: int = 8,
        pick_count: int = 6
    ) -> List[Dict]:
        """
        生成多樣化的N注號碼

        策略：
        - 注1-2: 高共識（多個方法推薦）
        - 注3-4: 中等共識
        - 注5-6: 低共識（獨特號碼）
        - 注7-8: 完全差異化

        Args:
            predictions: 各方法的預測結果
            n_bets: 生成幾注
            pick_count: 每注幾個號碼

        Returns:
            N注號碼及其資訊
        """
        bets = []

        # 統計每個號碼出現在幾個方法中
        number_frequency = Counter()
        for numbers in predictions.values():
            number_frequency.update(numbers)

        # 按頻率排序號碼
        sorted_by_freq = sorted(
            number_frequency.items(),
            key=lambda x: (-x[1], x[0])  # 頻率降序，號碼升序
        )

        # 策略1: 2注高共識
        for i in range(2):
            # 選擇最多方法推薦的號碼
            high_consensus = [num for num, freq in sorted_by_freq[:15]]

            # 添加一些變化
            selected = self._select_with_variation(high_consensus, pick_count, seed=i)

            bets.append({
                'numbers': selected,
                'strategy': '高共識',
                'consensus_level': 'high',
                'avg_frequency': np.mean([number_frequency[n] for n in selected])
            })

        # 策略2: 2注中等共識
        for i in range(2):
            medium_consensus = [num for num, freq in sorted_by_freq[10:30]]

            selected = self._select_with_variation(medium_consensus, pick_count, seed=i+2)

            bets.append({
                'numbers': selected,
                'strategy': '中等共識',
                'consensus_level': 'medium',
                'avg_frequency': np.mean([number_frequency[n] for n in selected])
            })

        # 策略3: 2注低共識
        for i in range(2):
            low_consensus = [num for num, freq in sorted_by_freq[25:45]]

            selected = self._select_with_variation(low_consensus, pick_count, seed=i+4)

            bets.append({
                'numbers': selected,
                'strategy': '低共識',
                'consensus_level': 'low',
                'avg_frequency': np.mean([number_frequency[n] for n in selected])
            })

        # 策略4: 2注完全差異化（冷門號碼）
        for i in range(2):
            # 找出沒有或很少被推薦的號碼
            all_recommended = set(number_frequency.keys())
            all_numbers = set(range(1, self.max_num + 1))
            cold_numbers = list(all_numbers - all_recommended)

            if len(cold_numbers) < pick_count:
                # 補充低頻號碼
                low_freq_numbers = [num for num, freq in sorted_by_freq[-15:]]
                cold_numbers.extend(low_freq_numbers)

            selected = self._select_with_variation(cold_numbers, pick_count, seed=i+6)

            bets.append({
                'numbers': selected,
                'strategy': '完全差異',
                'consensus_level': 'none',
                'avg_frequency': np.mean([number_frequency.get(n, 0) for n in selected])
            })

        return bets

    def _select_with_variation(
        self,
        candidates: List[int],
        pick_count: int,
        seed: int = 0
    ) -> List[int]:
        """
        從候選號碼中選擇，添加變化

        Args:
            candidates: 候選號碼
            pick_count: 選擇數量
            seed: 隨機種子

        Returns:
            選中的號碼
        """
        np.random.seed(seed)

        if len(candidates) <= pick_count:
            # 候選不夠，補充隨機號碼
            remaining = [n for n in range(1, self.max_num + 1) if n not in candidates]
            candidates = list(candidates) + list(np.random.choice(remaining, size=pick_count-len(candidates), replace=False))

        # 隨機選擇
        selected = np.random.choice(candidates, size=pick_count, replace=False)

        return sorted(selected.tolist())

    def analyze_bet_quality(
        self,
        numbers: List[int],
        predictions: Dict[str, List[int]]
    ) -> Dict:
        """
        分析這注號碼的質量

        Args:
            numbers: 號碼組合
            predictions: 各方法的預測結果

        Returns:
            質量分析
        """
        # 統計出現在幾個方法中
        number_sources = {}
        for num in numbers:
            sources = [method for method, nums in predictions.items() if num in nums]
            number_sources[num] = sources

        # 共識號碼（出現在多數方法中）
        consensus_nums = [num for num, sources in number_sources.items() if len(sources) >= len(predictions) / 2]
        unique_nums = [num for num, sources in number_sources.items() if len(sources) < len(predictions) / 2]

        # 奇偶比
        odd_count = sum(1 for num in numbers if num % 2 == 1)

        # 大小比
        high_count = sum(1 for num in numbers if num > 24)

        # 和值
        sum_value = sum(numbers)

        return {
            'consensus_numbers': consensus_nums,
            'unique_numbers': unique_nums,
            'consensus_ratio': len(consensus_nums) / len(numbers),
            'odd_even_ratio': f'{odd_count}:{len(numbers)-odd_count}',
            'high_low_ratio': f'{high_count}:{len(numbers)-high_count}',
            'sum': sum_value,
            'quality_grade': self._grade_quality(len(consensus_nums), len(unique_nums))
        }

    def _grade_quality(self, consensus_count: int, unique_count: int) -> str:
        """評級號碼質量"""
        if consensus_count >= 4:
            return 'A級 (高共識，穩健)'
        elif consensus_count >= 3:
            return 'B級 (中等共識，平衡)'
        elif unique_count >= 4:
            return 'C級 (獨特性高，激進)'
        else:
            return 'D級 (普通)'

    def adaptive_weights(
        self,
        history: List[Dict],
        context: Dict
    ) -> Dict[str, float]:
        """
        根據情境自適應調整權重

        Args:
            history: 歷史數據
            context: 情境資訊
                - 'recent_trend': 'stable' | 'volatile'
                - 'jackpot_accumulated': bool
                - 'special_date': bool

        Returns:
            調整後的權重
        """
        weights = self.default_weights.copy()

        # 情境1: 如果最近趨勢波動大，增加熵驅動和異常檢測權重
        if context.get('recent_trend') == 'volatile':
            weights['entropy'] += 0.05
            weights['anomaly'] += 0.05
            weights['deviation'] -= 0.05
            weights['social'] -= 0.05

        # 情境2: 如果頭獎累積很高，增加社群智慧權重（避開熱門）
        if context.get('jackpot_accumulated'):
            weights['social'] += 0.10
            weights['quantum'] -= 0.05
            weights['entropy'] -= 0.05

        # 情境3: 特殊日期（如節日），減少社群智慧（大家都會買）
        if context.get('special_date'):
            weights['social'] -= 0.10
            weights['anomaly'] += 0.10

        # 正規化權重
        total = sum(weights.values())
        weights = {k: v/total for k, v in weights.items()}

        return weights


# 測試函數
if __name__ == '__main__':
    print('=' * 100)
    print('🎯 元學習預測器測試')
    print('=' * 100)
    print()

    meta = MetaPredictor(max_num=49)

    # 模擬各方法的預測結果
    mock_predictions = {
        'entropy': [1, 6, 19, 23, 37, 45],
        'deviation': [7, 13, 25, 29, 37, 39],
        'social': [32, 35, 41, 43, 46, 49],
        'anomaly': [3, 8, 17, 28, 38, 44],
        'quantum': [5, 12, 21, 27, 34, 48],
    }

    print('📊 測試1：加權集成預測')
    print('-' * 100)
    print('各方法預測:')
    for method, nums in mock_predictions.items():
        weight = meta.default_weights.get(method, 0)
        print(f'  {method:12s} ({weight*100:4.0f}%): {nums}')
    print()

    numbers, details = meta.predict_with_ensemble(mock_predictions, pick_count=6)
    print(f'✅ 集成預測結果: {numbers}')
    print(f'   共識號碼數量: {details["consensus_count"]}')
    print()

    # 測試2：多樣化8注
    print('📊 測試2：生成8注多樣化號碼')
    print('-' * 100)
    bets = meta.predict_diversified(mock_predictions, n_bets=8, pick_count=6)

    for idx, bet in enumerate(bets, 1):
        nums_str = ' '.join(f'{n:02d}' for n in bet['numbers'])
        print(f'第{idx}注: {nums_str} | {bet["strategy"]:8s} | 平均頻率: {bet["avg_frequency"]:.1f}')

    print()

    # 測試3：質量分析
    print('📊 測試3：號碼質量分析')
    print('-' * 100)
    test_numbers = [1, 7, 19, 25, 37, 45]
    quality = meta.analyze_bet_quality(test_numbers, mock_predictions)
    print(f'測試號碼: {test_numbers}')
    print(f'共識號碼: {quality["consensus_numbers"]}')
    print(f'獨特號碼: {quality["unique_numbers"]}')
    print(f'質量評級: {quality["quality_grade"]}')
    print()

    # 測試4：自適應權重
    print('📊 測試4：情境自適應權重')
    print('-' * 100)

    context1 = {'recent_trend': 'volatile', 'jackpot_accumulated': False, 'special_date': False}
    weights1 = meta.adaptive_weights([], context1)
    print('情境1: 波動大')
    for method, weight in weights1.items():
        print(f'  {method:12s}: {weight*100:5.1f}%')
    print()

    context2 = {'recent_trend': 'stable', 'jackpot_accumulated': True, 'special_date': False}
    weights2 = meta.adaptive_weights([], context2)
    print('情境2: 頭獎累積高')
    for method, weight in weights2.items():
        print(f'  {method:12s}: {weight*100:5.1f}%')
    print()

    print('✅ 測試完成')
