"""
號碼集中度優化器 (Concentrated Pool Predictor) - P0 優化策略

核心理論：
1. 從全號碼池 (1-49) 中篩選出高機率候選池 (~25-30個號碼)
2. 通過縮小選擇範圍，提高覆蓋密度
3. 多維度評分系統確保篩選品質

維度分析：
1. 頻率維度 - 近期出現頻率 (熱門號碼)
2. 遺漏維度 - 遺漏期數分析 (回歸期望)
3. 區間維度 - 各區間平衡選擇
4. 趨勢維度 - 短期vs長期趨勢變化
5. 組合維度 - 號碼配對關聯性

目標：單注中獎率從 4.31% 提升至 6-8%
"""

import numpy as np
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass
import random
import logging

logger = logging.getLogger(__name__)


@dataclass
class NumberScore:
    """號碼評分結構"""
    number: int
    frequency_score: float = 0.0  # 頻率分數
    gap_score: float = 0.0        # 遺漏分數
    zone_score: float = 0.0       # 區間分數
    trend_score: float = 0.0      # 趨勢分數
    pair_score: float = 0.0       # 配對分數
    total_score: float = 0.0      # 總分


class ConcentratedPoolPredictor:
    """
    號碼集中度優化預測器

    策略：先篩選高機率候選池，再從中選號
    """

    def __init__(self, pool_size: int = 28,
                 weights: Dict[str, float] = None):
        """
        初始化預測器

        Args:
            pool_size: 候選池大小 (預設28個，約57%的號碼池)
            weights: 各維度權重
        """
        self.name = "ConcentratedPoolPredictor"
        self.pool_size = pool_size

        # 預設權重 (可透過回測調整)
        self.weights = weights or {
            'frequency': 0.25,   # 頻率權重
            'gap': 0.20,         # 遺漏權重
            'zone': 0.15,        # 區間權重
            'trend': 0.25,       # 趨勢權重
            'pair': 0.15         # 配對權重
        }

        # 區間定義 (大樂透 1-49 分5區)
        self.zones = [
            (1, 10),   # 區間1
            (11, 20),  # 區間2
            (21, 30),  # 區間3
            (31, 40),  # 區間4
            (41, 49),  # 區間5
        ]

    def _calculate_frequency_scores(self, history: List[Dict],
                                     min_num: int, max_num: int,
                                     window: int = 50) -> Dict[int, float]:
        """
        計算頻率分數

        使用最近 window 期的出現頻率
        """
        recent_history = history[:window]
        freq = Counter()

        for draw in recent_history:
            freq.update(draw.get('numbers', []))

        max_freq = max(freq.values()) if freq else 1

        scores = {}
        for num in range(min_num, max_num + 1):
            # 歸一化到 0-1
            scores[num] = freq.get(num, 0) / max_freq

        return scores

    def _calculate_gap_scores(self, history: List[Dict],
                               min_num: int, max_num: int) -> Dict[int, float]:
        """
        計算遺漏分數

        遺漏期數越長，回歸期望越高
        使用 S 形曲線：太短或太長都不好
        """
        # 計算每個號碼的遺漏期數
        last_seen = {num: len(history) for num in range(min_num, max_num + 1)}

        for i, draw in enumerate(history):
            for num in draw.get('numbers', []):
                if num in last_seen and last_seen[num] == len(history):
                    last_seen[num] = i

        scores = {}

        # 理想遺漏期數（根據機率計算）
        # 大樂透每期選6個，號碼期望出現間隔 ≈ 49/6 ≈ 8期
        ideal_gap = (max_num - min_num + 1) / 6

        for num, gap in last_seen.items():
            # S形曲線：遺漏期數接近 ideal_gap 的 1.5-2.5 倍時分數最高
            optimal_low = ideal_gap * 1.2
            optimal_high = ideal_gap * 2.5

            if gap < optimal_low:
                # 太近期出現，分數較低
                scores[num] = gap / optimal_low * 0.5
            elif gap <= optimal_high:
                # 最佳回歸區間
                scores[num] = 1.0
            else:
                # 太久沒出現，可能冷門
                decay = 0.9 ** ((gap - optimal_high) / ideal_gap)
                scores[num] = max(0.3, decay)

        return scores

    def _calculate_zone_scores(self, history: List[Dict],
                                min_num: int, max_num: int,
                                window: int = 30) -> Dict[int, float]:
        """
        計算區間分數

        各區間的熱門號碼獲得加分
        """
        recent_history = history[:window]

        # 統計各區間頻率
        zone_freq = defaultdict(Counter)

        for draw in recent_history:
            for num in draw.get('numbers', []):
                for i, (low, high) in enumerate(self.zones):
                    if low <= num <= high:
                        zone_freq[i][num] += 1
                        break

        scores = {}

        for i, (low, high) in enumerate(self.zones):
            zone_counter = zone_freq[i]
            max_freq = max(zone_counter.values()) if zone_counter else 1

            for num in range(low, high + 1):
                if num > max_num:
                    break
                # 區間內相對頻率
                scores[num] = zone_counter.get(num, 0) / max_freq

        return scores

    def _calculate_trend_scores(self, history: List[Dict],
                                 min_num: int, max_num: int) -> Dict[int, float]:
        """
        計算趨勢分數

        比較短期 (10期) vs 長期 (50期) 的頻率變化
        上升趨勢獲得加分
        """
        short_window = min(10, len(history))
        long_window = min(50, len(history))

        short_freq = Counter()
        for draw in history[:short_window]:
            short_freq.update(draw.get('numbers', []))

        long_freq = Counter()
        for draw in history[:long_window]:
            long_freq.update(draw.get('numbers', []))

        scores = {}

        for num in range(min_num, max_num + 1):
            short_rate = short_freq.get(num, 0) / short_window
            long_rate = long_freq.get(num, 0) / long_window

            # 趨勢比率
            if long_rate > 0:
                trend_ratio = short_rate / long_rate
            else:
                trend_ratio = 1.0 if short_rate > 0 else 0.5

            # 上升趨勢加分，下降趨勢減分
            # 使用 sigmoid-like 轉換
            if trend_ratio >= 1.5:
                scores[num] = 1.0  # 強上升
            elif trend_ratio >= 1.0:
                scores[num] = 0.6 + 0.4 * (trend_ratio - 1.0) / 0.5
            elif trend_ratio >= 0.5:
                scores[num] = 0.3 + 0.3 * (trend_ratio - 0.5) / 0.5
            else:
                scores[num] = 0.3 * trend_ratio / 0.5

        return scores

    def _calculate_pair_scores(self, history: List[Dict],
                                min_num: int, max_num: int,
                                window: int = 100) -> Dict[int, float]:
        """
        計算配對分數

        經常同時出現的號碼獲得關聯加分
        """
        recent_history = history[:window]

        # 統計號碼配對
        pair_count = defaultdict(int)

        for draw in recent_history:
            numbers = draw.get('numbers', [])
            for i, n1 in enumerate(numbers):
                for n2 in numbers[i+1:]:
                    pair_count[(min(n1, n2), max(n1, n2))] += 1

        # 計算每個號碼的配對熱度
        pair_heat = defaultdict(float)

        for (n1, n2), count in pair_count.items():
            pair_heat[n1] += count
            pair_heat[n2] += count

        max_heat = max(pair_heat.values()) if pair_heat else 1

        scores = {}
        for num in range(min_num, max_num + 1):
            scores[num] = pair_heat.get(num, 0) / max_heat

        return scores

    def build_concentrated_pool(self, history: List[Dict],
                                 lottery_rules: Dict) -> List[NumberScore]:
        """
        建構集中候選池

        整合多維度評分，篩選高分號碼
        """
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))

        # 計算各維度分數
        freq_scores = self._calculate_frequency_scores(history, min_num, max_num)
        gap_scores = self._calculate_gap_scores(history, min_num, max_num)
        zone_scores = self._calculate_zone_scores(history, min_num, max_num)
        trend_scores = self._calculate_trend_scores(history, min_num, max_num)
        pair_scores = self._calculate_pair_scores(history, min_num, max_num)

        # 整合評分
        number_scores = []

        for num in range(min_num, max_num + 1):
            score = NumberScore(number=num)
            score.frequency_score = freq_scores.get(num, 0)
            score.gap_score = gap_scores.get(num, 0)
            score.zone_score = zone_scores.get(num, 0)
            score.trend_score = trend_scores.get(num, 0)
            score.pair_score = pair_scores.get(num, 0)

            # 加權總分
            score.total_score = (
                self.weights['frequency'] * score.frequency_score +
                self.weights['gap'] * score.gap_score +
                self.weights['zone'] * score.zone_score +
                self.weights['trend'] * score.trend_score +
                self.weights['pair'] * score.pair_score
            )

            number_scores.append(score)

        # 按總分排序，取前 pool_size 個
        number_scores.sort(key=lambda x: -x.total_score)

        return number_scores[:self.pool_size]

    def predict(self, history: List[Dict], lottery_rules: Dict,
                strategy: str = 'balanced') -> Dict:
        """
        從集中池中預測號碼

        Args:
            history: 歷史數據
            lottery_rules: 彩票規則
            strategy: 選號策略
                - 'top': 直接選最高分
                - 'balanced': 考慮區間平衡
                - 'weighted_random': 加權隨機

        Returns:
            預測結果
        """
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))

        # 建構集中池
        pool = self.build_concentrated_pool(history, lottery_rules)
        pool_numbers = [s.number for s in pool]
        pool_scores = {s.number: s.total_score for s in pool}

        logger.info(f"[ConcentratedPool] 候選池大小: {len(pool)}, "
                   f"最高分: {pool[0].total_score:.3f}, "
                   f"最低分: {pool[-1].total_score:.3f}")

        # 根據策略選號
        if strategy == 'top':
            predicted = [s.number for s in pool[:pick_count]]

        elif strategy == 'balanced':
            predicted = self._select_balanced(pool, pick_count, lottery_rules)

        elif strategy == 'weighted_random':
            predicted = self._select_weighted_random(pool, pick_count)

        else:
            predicted = [s.number for s in pool[:pick_count]]

        # 特別號預測
        special = None
        if lottery_rules.get('hasSpecialNumber', False):
            special = self._predict_special(history, lottery_rules)

        return {
            'numbers': sorted(predicted),
            'special': special,
            'method': f'concentrated_pool_{strategy}',
            'confidence': 0.65,  # 預估信心度
            'pool_size': len(pool),
            'pool_coverage': len(pool) / (lottery_rules.get('maxNumber', 49) - lottery_rules.get('minNumber', 1) + 1),
            'top_scores': [(s.number, round(s.total_score, 3)) for s in pool[:10]]
        }

    def _select_balanced(self, pool: List[NumberScore],
                         pick_count: int,
                         lottery_rules: Dict) -> List[int]:
        """
        平衡選號策略

        確保選出的號碼在各區間分佈均衡
        """
        selected = []
        zone_counts = [0] * len(self.zones)
        target_per_zone = pick_count / len(self.zones)

        # 按分數排序的候選
        candidates = sorted(pool, key=lambda x: -x.total_score)

        for score in candidates:
            if len(selected) >= pick_count:
                break

            num = score.number

            # 找出所屬區間
            zone_idx = None
            for i, (low, high) in enumerate(self.zones):
                if low <= num <= high:
                    zone_idx = i
                    break

            if zone_idx is None:
                continue

            # 檢查區間是否已滿
            if zone_counts[zone_idx] < target_per_zone + 0.5:
                selected.append(num)
                zone_counts[zone_idx] += 1

        # 如果還不夠，從剩餘候選中補充
        if len(selected) < pick_count:
            remaining = [s.number for s in candidates if s.number not in selected]
            selected.extend(remaining[:pick_count - len(selected)])

        return selected[:pick_count]

    def _select_weighted_random(self, pool: List[NumberScore],
                                 pick_count: int) -> List[int]:
        """
        加權隨機選號

        分數越高，被選中機率越高
        """
        numbers = [s.number for s in pool]
        scores = np.array([s.total_score for s in pool])

        # 轉換為機率
        probs = scores / scores.sum()

        # 不重複抽樣
        selected = np.random.choice(numbers, size=pick_count, replace=False, p=probs)

        return selected.tolist()

    def _predict_special(self, history: List[Dict],
                         lottery_rules: Dict) -> int:
        """預測特別號"""
        special_min = lottery_rules.get('specialMinNumber',
                                        lottery_rules.get('specialMin', 1))
        special_max = lottery_rules.get('specialMaxNumber',
                                        lottery_rules.get('specialMax', 49))

        # 統計特別號頻率
        special_freq = Counter()
        for draw in history[:100]:
            special = draw.get('special_number') or draw.get('special')
            if special is not None:
                special_freq[special] += 1

        if special_freq:
            # 選擇最常出現的
            return special_freq.most_common(1)[0][0]
        else:
            return (special_min + special_max) // 2

    def predict_multi_bet(self, history: List[Dict],
                          lottery_rules: Dict,
                          num_bets: int = 2) -> Dict:
        """
        多注預測

        生成互補的多注組合
        """
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))

        # 建構集中池
        pool = self.build_concentrated_pool(history, lottery_rules)

        bets = []
        used_numbers = set()

        # 第1注：最高分組合 (top策略)
        bet1 = self._select_balanced(pool, pick_count, lottery_rules)
        bets.append({
            'numbers': sorted(bet1),
            'source': 'concentrated_top',
            'strategy': 'balanced'
        })
        used_numbers.update(bet1)

        if num_bets >= 2:
            # 第2注：次高分 + 遺漏回歸號碼
            remaining_pool = [s for s in pool if s.number not in used_numbers]

            if len(remaining_pool) >= pick_count:
                # 優先選遺漏分數高的
                remaining_pool.sort(key=lambda x: -(x.gap_score * 0.6 + x.total_score * 0.4))
                bet2 = [s.number for s in remaining_pool[:pick_count]]
            else:
                # 補充加權隨機
                bet2 = self._select_weighted_random(pool, pick_count)

            bets.append({
                'numbers': sorted(bet2),
                'source': 'concentrated_gap_focus',
                'strategy': 'gap_emphasis'
            })
            used_numbers.update(bet2)

        # 更多注：覆蓋優化
        for i in range(2, num_bets):
            remaining_pool = [s for s in pool if s.number not in used_numbers or len(used_numbers) > len(pool) * 0.8]

            if len(remaining_pool) >= pick_count:
                bet = self._select_weighted_random(remaining_pool, pick_count)
            else:
                bet = self._select_weighted_random(pool, pick_count)

            bets.append({
                'numbers': sorted(bet),
                'source': f'concentrated_diverse_{i+1}',
                'strategy': 'weighted_random'
            })
            used_numbers.update(bet)

        # 特別號
        specials = None
        if lottery_rules.get('hasSpecialNumber', False):
            specials = self._predict_multiple_specials(history, lottery_rules, num_bets)

        # 計算覆蓋率
        all_covered = set()
        for bet in bets:
            all_covered.update(bet['numbers'])

        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        coverage = len(all_covered) / (max_num - min_num + 1)

        return {
            'bets': bets,
            'specials': specials,
            'coverage': coverage,
            'pool_size': len(pool),
            'total_unique_numbers': len(all_covered),
            'method': 'concentrated_pool_multi'
        }

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

        # 補足
        while len(specials) < num_bets:
            for num in range(special_min, special_max + 1):
                if num not in specials:
                    specials.append(num)
                    if len(specials) >= num_bets:
                        break

        return specials[:num_bets]


# 單例
concentrated_pool_predictor = ConcentratedPoolPredictor()


def test_concentrated_pool():
    """測試集中池預測器"""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    from database import DatabaseManager
    from common import get_lottery_rules

    print("=" * 80)
    print("號碼集中度優化器測試 - 大樂透")
    print("=" * 80)

    db = DatabaseManager(db_path=os.path.join(os.path.dirname(__file__), '..', 'data', 'lottery_v2.db'))
    draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')

    print(f"\n數據: {len(draws)} 期")

    predictor = ConcentratedPoolPredictor(pool_size=28)

    # 測試單注預測
    print("\n" + "=" * 60)
    print("單注預測測試")
    print("=" * 60)

    for strategy in ['top', 'balanced', 'weighted_random']:
        result = predictor.predict(draws[1:], rules, strategy=strategy)
        print(f"\n策略: {strategy}")
        print(f"  預測號碼: {result['numbers']}")
        print(f"  候選池大小: {result['pool_size']}")
        print(f"  覆蓋率: {result['pool_coverage']:.1%}")
        print(f"  前10高分: {result['top_scores']}")

    # 測試多注預測
    print("\n" + "=" * 60)
    print("多注預測測試 (2注)")
    print("=" * 60)

    multi_result = predictor.predict_multi_bet(draws[1:], rules, num_bets=2)
    for i, bet in enumerate(multi_result['bets']):
        print(f"  第{i+1}注: {bet['numbers']} (策略: {bet['source']})")
    print(f"  覆蓋率: {multi_result['coverage']:.1%}")
    print(f"  不重複號碼數: {multi_result['total_unique_numbers']}")

    return predictor


if __name__ == '__main__':
    test_concentrated_pool()
