"""
大樂透雙注優化器 (Big Lotto Dual Bet Optimizer)

專門針對「2注達成最高中獎率」的目標設計

核心策略：
1. 第一注 (保守)：高共識 + 熱門號碼
2. 第二注 (進攻)：遺漏回歸 + 反共識號碼

設計原則：
- 兩注之間最小化重疊，最大化覆蓋
- 第一注追求穩定命中
- 第二注追求高回報潛力
"""

import numpy as np
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Set, Optional
import random
import logging

logger = logging.getLogger(__name__)


class BigLottoDualBetOptimizer:
    """
    大樂透雙注優化器

    目標：用2注達成最高可能的中獎率
    """

    def __init__(self):
        self.name = "BigLottoDualBetOptimizer"
        self._load_strategies()

    def _load_strategies(self):
        """載入預測策略"""
        try:
            from .unified_predictor import prediction_engine
            self.engine = prediction_engine
        except:
            self.engine = None

    def analyze_number_potential(self, history: List[Dict],
                                   min_num: int, max_num: int) -> Dict[int, Dict]:
        """
        分析每個號碼的多維度潛力

        維度：
        1. 頻率得分 (近期熱度)
        2. 遺漏得分 (回歸潛力)
        3. 趨勢得分 (上升/下降)
        4. 配對得分 (關聯熱度)
        5. 區間得分 (區間平衡)
        """
        analysis = {}

        # 1. 頻率分析 (多窗口)
        short_freq = Counter()  # 近10期
        mid_freq = Counter()    # 近30期
        long_freq = Counter()   # 近100期

        for i, draw in enumerate(history):
            nums = draw.get('numbers', [])
            if i < 10:
                short_freq.update(nums)
            if i < 30:
                mid_freq.update(nums)
            if i < 100:
                long_freq.update(nums)

        # 2. 遺漏分析
        last_seen = {n: len(history) for n in range(min_num, max_num + 1)}
        for i, draw in enumerate(history):
            for num in draw.get('numbers', []):
                if last_seen[num] == len(history):
                    last_seen[num] = i

        # 3. 配對分析 (近100期)
        pair_heat = defaultdict(float)
        for draw in history[:100]:
            nums = draw.get('numbers', [])
            for i, n1 in enumerate(nums):
                for n2 in nums[i+1:]:
                    pair_heat[n1] += 1
                    pair_heat[n2] += 1

        # 4. 區間定義
        zones = [(1, 10), (11, 20), (21, 30), (31, 40), (41, 49)]

        def get_zone(num):
            for i, (low, high) in enumerate(zones):
                if low <= num <= high:
                    return i
            return 0

        # 正規化係數
        max_short = max(short_freq.values()) if short_freq else 1
        max_mid = max(mid_freq.values()) if mid_freq else 1
        max_long = max(long_freq.values()) if long_freq else 1
        max_pair = max(pair_heat.values()) if pair_heat else 1

        for num in range(min_num, max_num + 1):
            # 頻率得分 (短期權重高)
            freq_score = (
                0.5 * short_freq.get(num, 0) / max_short +
                0.3 * mid_freq.get(num, 0) / max_mid +
                0.2 * long_freq.get(num, 0) / max_long
            )

            # 遺漏得分 (S形曲線)
            gap = last_seen[num]
            ideal_gap = 8  # 理想回歸期 (49/6)
            if gap < ideal_gap * 0.8:
                gap_score = 0.3  # 太近期
            elif gap < ideal_gap * 1.5:
                gap_score = 0.6  # 正常
            elif gap < ideal_gap * 2.5:
                gap_score = 1.0  # 最佳回歸窗口
            else:
                gap_score = max(0.4, 0.9 ** ((gap - ideal_gap * 2.5) / 5))  # 衰減

            # 趨勢得分 (短期 vs 長期)
            short_rate = short_freq.get(num, 0) / 10 if 10 > 0 else 0
            long_rate = long_freq.get(num, 0) / 100 if 100 > 0 else 0
            if long_rate > 0:
                trend_ratio = short_rate / long_rate
            else:
                trend_ratio = 1.0

            if trend_ratio > 1.5:
                trend_score = 1.0  # 強上升
            elif trend_ratio > 1.0:
                trend_score = 0.7
            elif trend_ratio > 0.5:
                trend_score = 0.4
            else:
                trend_score = 0.2  # 下降趨勢

            # 配對得分
            pair_score = pair_heat.get(num, 0) / max_pair

            analysis[num] = {
                'freq_score': freq_score,
                'gap_score': gap_score,
                'trend_score': trend_score,
                'pair_score': pair_score,
                'zone': get_zone(num),
                'gap': gap
            }

        return analysis

    def select_consensus_numbers(self, history: List[Dict],
                                   lottery_rules: Dict,
                                   pick_count: int = 6) -> List[int]:
        """
        選擇高共識號碼 (第一注策略)

        綜合多個方法的預測，選擇出現頻率最高的號碼
        """
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # 獲取多個方法的預測
        predictions = []

        if self.engine:
            methods = [
                ('zone_balance', lambda: self.engine.zone_balance_predict(history[:500], lottery_rules)),
                ('bayesian', lambda: self.engine.bayesian_predict(history[:300], lottery_rules)),
                ('hot_cold', lambda: self.engine.hot_cold_mix_predict(history[:100], lottery_rules)),
                ('trend', lambda: self.engine.trend_predict(history[:300], lottery_rules)),
                ('ensemble', lambda: self.engine.ensemble_predict(history[:200], lottery_rules)),
            ]

            for name, method in methods:
                try:
                    result = method()
                    predictions.append((name, set(result['numbers'])))
                except Exception as e:
                    logger.warning(f"Method {name} failed: {e}")

        # 統計號碼出現次數
        vote_count = Counter()
        for name, nums in predictions:
            vote_count.update(nums)

        # 分析號碼潛力
        analysis = self.analyze_number_potential(history, min_num, max_num)

        # 綜合評分：投票 + 潛力
        final_scores = {}
        for num in range(min_num, max_num + 1):
            votes = vote_count.get(num, 0)
            potential = analysis[num]

            # 共識分數 (投票權重50%)
            consensus_score = votes / len(predictions) if predictions else 0

            # 潛力分數 (頻率30% + 趨勢20%)
            potential_score = (
                0.3 * potential['freq_score'] +
                0.2 * potential['trend_score']
            )

            final_scores[num] = 0.5 * consensus_score + 0.5 * potential_score

        # 選擇最高分，同時考慮區間平衡
        return self._select_balanced(final_scores, analysis, pick_count)

    def select_gap_regression_numbers(self, history: List[Dict],
                                        lottery_rules: Dict,
                                        pick_count: int = 6,
                                        exclude: Set[int] = None) -> List[int]:
        """
        選擇遺漏回歸號碼 (第二注策略)

        專注於長期未出現但統計上應該回歸的號碼
        """
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        exclude = exclude or set()

        analysis = self.analyze_number_potential(history, min_num, max_num)

        # 評分：遺漏為主，配對為輔
        final_scores = {}
        for num in range(min_num, max_num + 1):
            if num in exclude:
                # 降低已選號碼的分數但不完全排除
                penalty = 0.5
            else:
                penalty = 1.0

            potential = analysis[num]

            # 遺漏回歸分數 (遺漏60% + 配對20% + 頻率20%)
            score = (
                0.6 * potential['gap_score'] +
                0.2 * potential['pair_score'] +
                0.2 * potential['freq_score']
            ) * penalty

            final_scores[num] = score

        return self._select_balanced(final_scores, analysis, pick_count)

    def _select_balanced(self, scores: Dict[int, float],
                          analysis: Dict[int, Dict],
                          pick_count: int) -> List[int]:
        """
        區間平衡選號

        確保選出的號碼分佈在多個區間
        """
        # 按分數排序
        sorted_nums = sorted(scores.keys(), key=lambda x: -scores[x])

        selected = []
        zone_counts = [0, 0, 0, 0, 0]  # 5個區間
        max_per_zone = (pick_count // 3) + 1  # 每區間最多選幾個

        for num in sorted_nums:
            if len(selected) >= pick_count:
                break

            zone = analysis[num]['zone']

            # 區間平衡檢查
            if zone_counts[zone] < max_per_zone:
                selected.append(num)
                zone_counts[zone] += 1

        # 如果還不夠，放寬限制
        if len(selected) < pick_count:
            for num in sorted_nums:
                if num not in selected:
                    selected.append(num)
                    if len(selected) >= pick_count:
                        break

        return sorted(selected[:pick_count])

    def predict_dual_bet(self, history: List[Dict],
                          lottery_rules: Dict) -> Dict:
        """
        生成優化的雙注組合

        第一注：高共識策略 (穩定)
        第二注：遺漏回歸策略 (進攻)
        """
        pick_count = lottery_rules.get('pickCount', 6)

        # 第一注：共識策略
        bet1 = self.select_consensus_numbers(history, lottery_rules, pick_count)

        # 第二注：遺漏回歸 (盡量避免與第一注重疊)
        bet2 = self.select_gap_regression_numbers(
            history, lottery_rules, pick_count, exclude=set(bet1)
        )

        # 計算重疊
        overlap = len(set(bet1) & set(bet2))

        # 特別號預測
        specials = self._predict_specials(history, lottery_rules, 2)

        # 覆蓋率
        all_nums = set(bet1) | set(bet2)
        max_num = lottery_rules.get('maxNumber', 49)
        min_num = lottery_rules.get('minNumber', 1)
        coverage = len(all_nums) / (max_num - min_num + 1)

        return {
            'bets': [
                {'numbers': bet1, 'strategy': 'consensus', 'description': '高共識穩定策略'},
                {'numbers': bet2, 'strategy': 'gap_regression', 'description': '遺漏回歸進攻策略'}
            ],
            'specials': specials,
            'overlap': overlap,
            'coverage': coverage,
            'unique_numbers': len(all_nums),
            'method': 'big_lotto_dual_bet_optimizer'
        }

    def predict_single_best(self, history: List[Dict],
                             lottery_rules: Dict) -> Dict:
        """
        單注最佳預測 (混合策略)
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        analysis = self.analyze_number_potential(history, min_num, max_num)

        # 綜合評分
        final_scores = {}
        for num, data in analysis.items():
            # 平衡所有維度
            score = (
                0.30 * data['freq_score'] +
                0.25 * data['gap_score'] +
                0.20 * data['trend_score'] +
                0.15 * data['pair_score'] +
                0.10  # 基礎分
            )
            final_scores[num] = score

        selected = self._select_balanced(final_scores, analysis, pick_count)

        special = self._predict_specials(history, lottery_rules, 1)

        return {
            'numbers': selected,
            'special': special[0] if special else None,
            'method': 'big_lotto_hybrid_best',
            'confidence': 0.6
        }

    def _predict_specials(self, history: List[Dict],
                           lottery_rules: Dict,
                           count: int) -> List[int]:
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

        specials = [s for s, _ in special_freq.most_common(count)]

        while len(specials) < count:
            for num in range(special_min, special_max + 1):
                if num not in specials:
                    specials.append(num)
                    if len(specials) >= count:
                        break

        return specials[:count]


# 單例
big_lotto_dual_optimizer = BigLottoDualBetOptimizer()


def test_dual_optimizer():
    """測試雙注優化器"""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    from database import DatabaseManager
    from common import get_lottery_rules

    print("=" * 80)
    print("大樂透雙注優化器測試")
    print("=" * 80)

    db = DatabaseManager(db_path=os.path.join(os.path.dirname(__file__), '..', 'data', 'lottery_v2.db'))
    draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')

    print(f"\n數據: {len(draws)} 期")

    optimizer = BigLottoDualBetOptimizer()

    # 測試雙注預測
    print("\n雙注預測結果:")
    print("-" * 50)
    result = optimizer.predict_dual_bet(draws[1:], rules)

    for i, bet in enumerate(result['bets']):
        print(f"第{i+1}注 ({bet['strategy']}): {bet['numbers']}")
        print(f"        {bet['description']}")

    print(f"\n重疊號碼數: {result['overlap']}")
    print(f"覆蓋率: {result['coverage']*100:.1f}%")
    print(f"不重複號碼數: {result['unique_numbers']}")
    print(f"特別號: {result['specials']}")

    return optimizer


if __name__ == '__main__':
    test_dual_optimizer()
