import random
import logging
import numpy as np
from typing import List, Dict, Optional
from collections import Counter

logger = logging.getLogger(__name__)

class PowerLottoSpecialPredictor:
    """
    威力彩第二區 (Section 2) 專屬預測器
    優化版：多策略融合 + 動態權重調整
    """
    def __init__(self, lottery_rules: Dict):
        self.min_num = lottery_rules.get('specialMinNumber', 1)
        self.max_num = lottery_rules.get('specialMaxNumber', 8)
        self.lottery_type = lottery_rules.get('name', '')

    def predict(self, history: List[Dict], main_numbers: List[int] = None) -> int:
        """
        預測第二區號碼 (優化版)
        使用多策略融合：
        1. 近期熱號 (最近 10 期出現頻率)
        2. 中期平衡 (最近 30 期的平衡)
        3. 週期模式 (是否有週期性規律)
        4. 趨勢分析 (上升/下降趨勢)
        """
        if not history:
            return random.randint(self.min_num, self.max_num)

        # 獲取所有策略分數
        scores = {}
        for num in range(self.min_num, self.max_num + 1):
            scores[num] = 0.0

        # 策略1: 近期熱號 (最近10期，權重 25%)
        recent_scores = self._recent_hot_strategy(history[:10])
        for num, score in recent_scores.items():
            scores[num] += score * 0.25

        # 策略2: 中期平衡 (最近30期，權重 25%)
        balance_scores = self._balance_strategy(history[:30])
        for num, score in balance_scores.items():
            scores[num] += score * 0.25

        # 策略3: 週期分析 (權重 20%)
        cycle_scores = self._cycle_strategy(history[:60])
        for num, score in cycle_scores.items():
            scores[num] += score * 0.20

        # 策略4: 趨勢分析 (權重 20%)
        trend_scores = self._trend_strategy(history[:20])
        for num, score in trend_scores.items():
            scores[num] += score * 0.20

        # 策略5: 主號關聯 (權重 10%)
        if main_numbers:
            assoc_scores = self._main_association_strategy(history[:50], main_numbers)
            for num, score in assoc_scores.items():
                scores[num] += score * 0.10

        # 選擇最高分 (加入少量隨機性避免過度確定)
        sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # 從 top 3 中隨機選擇 (按權重)
        top_3 = sorted_nums[:3]
        weights = [s[1] for s in top_3]
        total_weight = sum(weights)

        if total_weight > 0:
            probs = [w / total_weight for w in weights]
            choice_idx = np.random.choice(len(top_3), p=probs)
            return top_3[choice_idx][0]

        return sorted_nums[0][0]

    def _recent_hot_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """近期熱號策略：最近出現過的號碼權重較高"""
        scores = {n: 0.0 for n in range(self.min_num, self.max_num + 1)}
        if not history:
            return scores

        for i, d in enumerate(history):
            special = d.get('special')
            if special and self.min_num <= special <= self.max_num:
                # 越近期權重越高 (指數衰減)
                weight = np.exp(-i * 0.2)
                scores[special] += weight

        # 正規化到 0-1
        max_score = max(scores.values()) if scores else 1
        if max_score > 0:
            scores = {k: v / max_score for k, v in scores.items()}

        return scores

    def _balance_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """平衡策略：出現次數較少的號碼權重較高"""
        scores = {n: 0.0 for n in range(self.min_num, self.max_num + 1)}
        if not history:
            return scores

        special_nums = [d.get('special') for d in history if d.get('special')]
        freq = Counter(special_nums)

        total = len(special_nums) if special_nums else 1
        expected = total / (self.max_num - self.min_num + 1)

        for num in range(self.min_num, self.max_num + 1):
            count = freq.get(num, 0)
            # 低於期望值的號碼獲得較高分數
            if expected > 0:
                deviation = (expected - count) / expected
                scores[num] = max(0, min(1, 0.5 + deviation * 0.5))
            else:
                scores[num] = 0.5

        return scores

    def _cycle_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """週期策略：分析號碼出現的週期性"""
        scores = {n: 0.0 for n in range(self.min_num, self.max_num + 1)}
        if len(history) < 10:
            return {n: 0.5 for n in range(self.min_num, self.max_num + 1)}

        for num in range(self.min_num, self.max_num + 1):
            # 找出這個號碼的出現位置
            positions = []
            for i, d in enumerate(history):
                if d.get('special') == num:
                    positions.append(i)

            if len(positions) >= 2:
                # 計算平均間隔
                intervals = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
                avg_interval = sum(intervals) / len(intervals)

                # 距離上次出現的期數
                last_gap = positions[0] if positions else len(history)

                # 如果接近平均間隔，給予較高分數
                if avg_interval > 0:
                    cycle_score = 1 - abs(last_gap - avg_interval) / avg_interval
                    scores[num] = max(0, min(1, cycle_score))
            else:
                scores[num] = 0.3  # 出現太少次，給予中等分數

        return scores

    def _trend_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """趨勢策略：分析數值的上升/下降趨勢"""
        scores = {n: 0.5 for n in range(self.min_num, self.max_num + 1)}
        if len(history) < 5:
            return scores

        special_nums = [d.get('special') for d in history[:10] if d.get('special')]
        if len(special_nums) < 3:
            return scores

        # 計算最近的趨勢 (上升/下降)
        recent_avg = sum(special_nums[:5]) / 5 if len(special_nums) >= 5 else sum(special_nums) / len(special_nums)

        # 如果趨勢向上，給高數字較高分數
        # 如果趨勢向下，給低數字較高分數
        mid = (self.min_num + self.max_num) / 2

        for num in range(self.min_num, self.max_num + 1):
            if recent_avg > mid:
                # 趨勢向上，但可能回調
                scores[num] = 0.5 + (num - mid) / (self.max_num - mid) * 0.3
            else:
                # 趨勢向下，但可能反彈
                scores[num] = 0.5 + (mid - num) / (mid - self.min_num) * 0.3

        return scores

    def _main_association_strategy(self, history: List[Dict], main_numbers: List[int]) -> Dict[int, float]:
        """主號關聯策略：分析主號與特別號的關聯"""
        scores = {n: 0.5 for n in range(self.min_num, self.max_num + 1)}
        if not history or not main_numbers:
            return scores

        # 統計當主號包含某些數字時，特別號的分布
        relevant_specials = []
        for d in history:
            main = set(d.get('numbers', []))
            overlap = len(main & set(main_numbers))
            if overlap >= 2:  # 至少有2個號碼重疊
                special = d.get('special')
                if special:
                    relevant_specials.append(special)

        if relevant_specials:
            freq = Counter(relevant_specials)
            max_freq = max(freq.values())
            for num in range(self.min_num, self.max_num + 1):
                scores[num] = freq.get(num, 0) / max_freq if max_freq > 0 else 0.5

        return scores


def get_enhanced_special_prediction(history: List[Dict], lottery_rules: Dict, main_predicted: List[int] = None) -> int:
    """
    獲取增強版特別號預測 (僅限威力彩)
    """
    lottery_name = lottery_rules.get('name', '')
    if 'POWER_LOTTO' in lottery_name or '威力彩' in lottery_name:
        predictor = PowerLottoSpecialPredictor(lottery_rules)
        return predictor.predict(history, main_numbers=main_predicted)
    return None
