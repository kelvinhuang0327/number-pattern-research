"""
反共識策略預測器 (Anti-Consensus Predictor)

核心理念：
1. 彩票中獎機率對所有號碼組合相同
2. 但獎金是由中獎者均分
3. 如果選擇「大眾不愛選的號碼」，中獎時獎金期望值更高

策略原理：
- 避開熱門號碼（近期頻繁出現的號碼）
- 避開生日號碼（1-31）
- 避開「幸運數字」（7, 8, 9 等）
- 選擇統計上合理但冷門的組合

P1 新增功能
"""

import random
from typing import List, Dict, Set, Tuple
from collections import Counter, defaultdict
import logging
import numpy as np

logger = logging.getLogger(__name__)


class AntiConsensusPredictor:
    """
    反共識策略預測器

    目標：選擇中獎時獎金期望值最高的號碼組合
    """

    def __init__(self):
        self.name = "anti_consensus"
        self.optimal_window = 200

        # 大眾偏好的號碼（基於行為研究）
        self.popular_patterns = {
            'birthday_numbers': set(range(1, 32)),  # 生日號碼 1-31
            'lucky_numbers': {7, 8, 9, 3, 6},  # 幸運數字
            'round_numbers': {10, 20, 30},  # 整十數
            'sequences': self._generate_sequences(),  # 連號模式
        }

    def _generate_sequences(self) -> Set[Tuple[int, ...]]:
        """生成常見連號序列"""
        sequences = set()
        # 連續3個數字的組合
        for start in range(1, 38):
            sequences.add((start, start + 1, start + 2))
        return sequences

    def analyze_popularity(self, history: List[Dict], lottery_rules: Dict) -> Dict[int, float]:
        """
        分析號碼的「大眾熱度」

        熱度來源：
        1. 近期出現頻率（人們傾向選擇近期開出的號碼）
        2. 是否為生日號碼
        3. 是否為幸運數字
        4. 是否為整十數

        Returns:
            {號碼: 熱度分數}，分數越高越熱門
        """
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 39)

        popularity = defaultdict(float)

        # 1. 近期頻率（權重: 0.4）
        recent_freq = Counter()
        
        # 智能檢測並獲取最近50期
        if not history:
            recent_draws = []
        elif history[0].get('date', '0') < history[-1].get('date', '9'):
            # ASC (Old -> New): taking last 50
            recent_draws = history[-50:]
        else:
            # DESC (New -> Old): taking first 50
            recent_draws = history[:50]
            
        for draw in recent_draws:
            for num in draw.get('numbers', []):
                recent_freq[num] += 1

        max_freq = max(recent_freq.values()) if recent_freq else 1
        for num in range(min_num, max_num + 1):
            freq_score = recent_freq.get(num, 0) / max_freq
            popularity[num] += freq_score * 0.4

        # 2. 生日號碼（權重: 0.3）
        for num in range(min_num, min(32, max_num + 1)):
            popularity[num] += 0.3

        # 3. 幸運數字（權重: 0.2）
        for num in self.popular_patterns['lucky_numbers']:
            if min_num <= num <= max_num:
                popularity[num] += 0.2

        # 4. 整十數（權重: 0.1）
        for num in self.popular_patterns['round_numbers']:
            if min_num <= num <= max_num:
                popularity[num] += 0.1

        return dict(popularity)

    def predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        反共識預測

        策略：
        1. 計算所有號碼的熱度
        2. 優先選擇熱度低的號碼
        3. 但仍需符合基本統計約束（奇偶比、總和範圍）
        """
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 39)
        pick_count = lottery_rules.get('pickCount', 5)

        # 計算熱度
        popularity = self.analyze_popularity(history, lottery_rules)

        # 按熱度排序（升序 = 越冷門越前面）
        ranked = sorted(popularity.items(), key=lambda x: x[1])

        # 取冷門號碼作為候選
        cold_numbers = [num for num, _ in ranked[:20]]

        # 應用組合約束
        selected = self._select_with_constraints(
            cold_numbers, pick_count, min_num, max_num, history
        )

        # 計算「反共識分數」（選中號碼的平均冷門程度）
        avg_popularity = sum(popularity[n] for n in selected) / len(selected)
        anti_consensus_score = 1 - avg_popularity  # 越冷門分數越高

        return {
            'numbers': sorted(selected),
            'confidence': round(0.5 + anti_consensus_score * 0.3, 2),
            'method': 'anti_consensus',
            'anti_consensus_score': round(anti_consensus_score, 3),
            'popularity_scores': {n: round(popularity[n], 3) for n in selected}
        }

    def _select_with_constraints(
        self,
        candidates: List[int],
        pick_count: int,
        min_num: int,
        max_num: int,
        history: List[Dict]
    ) -> List[int]:
        """選擇符合約束的號碼"""
        # 計算歷史總和範圍
        sums = [sum(d.get('numbers', [])) for d in history[:100] if d.get('numbers')]
        if sums:
            avg_sum = sum(sums) / len(sums)
            sum_range = (avg_sum * 0.7, avg_sum * 1.3)
        else:
            sum_range = (50, 130)

        # 補充候選（如果冷門號碼不夠）
        if len(candidates) < pick_count * 2:
            all_nums = list(range(min_num, max_num + 1))
            remaining = [n for n in all_nums if n not in candidates]
            candidates = candidates + remaining

        # 嘗試找到符合約束的組合
        best_combo = None
        best_score = -1

        for _ in range(200):
            # 從候選中隨機選擇
            sample = random.sample(candidates[:pick_count * 3], min(pick_count * 3, len(candidates)))
            combo = sample[:pick_count]

            # 檢查約束
            total = sum(combo)
            odd_count = sum(1 for n in combo if n % 2 == 1)

            score = 0
            # 總和在範圍內
            if sum_range[0] <= total <= sum_range[1]:
                score += 1
            # 奇偶平衡
            if 2 <= odd_count <= 3:
                score += 1
            # 沒有連續3個數字
            sorted_combo = sorted(combo)
            has_triple = any(
                sorted_combo[i+2] - sorted_combo[i] == 2
                for i in range(len(sorted_combo) - 2)
            )
            if not has_triple:
                score += 1

            if score > best_score:
                best_score = score
                best_combo = combo

            if score == 3:
                break

        return best_combo if best_combo else candidates[:pick_count]

    def predict_contrarian(self, history: List[Dict], lottery_rules: Dict,
                          base_predictions: List[List[int]] = None) -> Dict:
        """
        對立預測 - 專門與其他預測方法「唱反調」

        Args:
            base_predictions: 其他方法的預測結果

        策略：選擇其他方法都沒選的號碼
        """
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 39)
        pick_count = lottery_rules.get('pickCount', 5)

        # 收集其他方法選擇的號碼
        if base_predictions:
            consensus_numbers = set()
            for pred in base_predictions:
                consensus_numbers.update(pred)
        else:
            # 如果沒有提供，執行其他方法獲取
            consensus_numbers = self._get_consensus_numbers(history, lottery_rules)

        # 選擇沒有被選中的號碼
        all_numbers = set(range(min_num, max_num + 1))
        contrarian_candidates = list(all_numbers - consensus_numbers)

        if len(contrarian_candidates) < pick_count:
            # 如果候選不足，加入共識號碼中熱度較低的
            popularity = self.analyze_popularity(history, lottery_rules)
            remaining = sorted(
                [(n, popularity.get(n, 0)) for n in consensus_numbers],
                key=lambda x: x[1]
            )
            contrarian_candidates.extend([n for n, _ in remaining])

        # 應用約束選擇
        selected = self._select_with_constraints(
            contrarian_candidates, pick_count, min_num, max_num, history
        )

        return {
            'numbers': sorted(selected),
            'confidence': 0.55,
            'method': 'contrarian',
            'avoided_numbers': sorted(consensus_numbers)[:10]
        }

    def _get_consensus_numbers(self, history: List[Dict], lottery_rules: Dict) -> Set[int]:
        """獲取其他方法的共識號碼"""
        from .unified_predictor import prediction_engine

        consensus = set()
        methods = [
            prediction_engine.trend_predict,
            prediction_engine.zone_balance_predict,
            prediction_engine.bayesian_predict,
            prediction_engine.hot_cold_mix_predict,
        ]

        for method in methods:
            try:
                result = method(history[:200], lottery_rules)
                consensus.update(result.get('numbers', []))
            except:
                pass

        return consensus


class HighValuePredictor:
    """
    高價值預測器

    結合反共識策略與統計分析，追求最高獎金期望值
    """

    def __init__(self):
        self.name = "high_value"
        self.optimal_window = 200
        self.anti_consensus = AntiConsensusPredictor()

    def predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        高價值預測

        策略組合：
        1. 50% 權重：反共識（冷門號碼）
        2. 30% 權重：統計合理性（符合歷史分布）
        3. 20% 權重：間隔分析（該出現的號碼）
        """
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 39)
        pick_count = lottery_rules.get('pickCount', 5)

        # 計算各維度分數
        popularity = self.anti_consensus.analyze_popularity(history, lottery_rules)

        # 計算間隔分數
        from .gap_predictor import GapAnalysisPredictor
        gap_predictor = GapAnalysisPredictor()
        gap_stats = gap_predictor.calculate_gaps(history, max_num)

        # 綜合評分
        scores = {}
        for num in range(min_num, max_num + 1):
            # 反共識分數（熱度越低越好）
            anti_score = 1 - popularity.get(num, 0)

            # 間隔分數（gap_ratio 越高越好，但不要太極端）
            gap_ratio = gap_stats.get(num, {}).get('gap_ratio', 1)
            gap_score = min(1.0, gap_ratio / 2)  # 標準化到 0-1

            # 綜合分數
            scores[num] = anti_score * 0.5 + gap_score * 0.3 + random.random() * 0.2

        # 按分數排序
        ranked = sorted(scores.items(), key=lambda x: -x[1])

        # 選擇高分號碼並應用約束
        candidates = [num for num, _ in ranked[:pick_count * 3]]
        selected = self.anti_consensus._select_with_constraints(
            candidates, pick_count, min_num, max_num, history
        )

        return {
            'numbers': sorted(selected),
            'confidence': 0.6,
            'method': 'high_value',
            'scores': {n: round(scores[n], 3) for n in selected}
        }


# 便捷函數
def anti_consensus_predict(history: List[Dict], lottery_rules: Dict) -> Dict:
    """反共識預測便捷函數"""
    predictor = AntiConsensusPredictor()
    return predictor.predict(history, lottery_rules)


def high_value_predict(history: List[Dict], lottery_rules: Dict) -> Dict:
    """高價值預測便捷函數"""
    predictor = HighValuePredictor()
    return predictor.predict(history, lottery_rules)


def contrarian_predict(history: List[Dict], lottery_rules: Dict) -> Dict:
    """對立預測便捷函數"""
    predictor = AntiConsensusPredictor()
    return predictor.predict_contrarian(history, lottery_rules)


# 測試
if __name__ == '__main__':
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    # 模擬數據
    history = []
    for i in range(200):
        # 偏向生日號碼和熱門數字
        numbers = sorted(random.sample(range(1, 40), 5))
        history.append({
            'draw': f'test_{200-i:03d}',
            'date': f'2025-01-{(i%28)+1:02d}',
            'numbers': numbers
        })

    rules = {
        'minNumber': 1,
        'maxNumber': 39,
        'pickCount': 5,
        'hasSpecialNumber': False
    }

    print("=" * 60)
    print("反共識策略測試")
    print("=" * 60)

    # 測試反共識預測
    anti = AntiConsensusPredictor()
    result = anti.predict(history, rules)
    print(f"\n反共識預測: {result['numbers']}")
    print(f"反共識分數: {result['anti_consensus_score']}")
    print(f"各號碼熱度: {result['popularity_scores']}")

    # 測試對立預測
    result = anti.predict_contrarian(history, rules)
    print(f"\n對立預測: {result['numbers']}")
    print(f"避開的號碼: {result['avoided_numbers']}")

    # 測試高價值預測
    hv = HighValuePredictor()
    result = hv.predict(history, rules)
    print(f"\n高價值預測: {result['numbers']}")
    print(f"各號碼綜合分數: {result['scores']}")
