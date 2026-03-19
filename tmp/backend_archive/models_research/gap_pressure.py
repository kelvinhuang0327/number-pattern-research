"""
Gap Pressure Scorer - 遺漏壓力計分器

115000050 期檢討產出：
28 號 (gap=11, avg_interval=7.9) 和 35 號 (gap=12, avg_interval=7.7)
均為統計顯著遺漏號，但系統未能優先推薦。

本模組計算每個號碼的「遺漏壓力分數」：
- pressure_ratio = current_gap / avg_interval
- pressure_score = sigmoid(pressure_ratio - 1) * 2
- ratio > 1.0 表示已超過平均週期，壓力累積中
- ratio > 1.3 標記為 high_pressure

完全確定性(deterministic)，無隨機元素。
"""

import math
from collections import Counter
from typing import List, Dict, Optional, Set


class GapPressureScorer:
    """遺漏壓力計分器"""

    def __init__(self, max_num: int = 39, high_threshold: float = 1.3):
        self.max_num = max_num
        self.high_threshold = high_threshold

    @staticmethod
    def _sigmoid(x: float, steepness: float = 3.0) -> float:
        """Sigmoid function centered at 0, scaled to [0, 1]"""
        return 1.0 / (1.0 + math.exp(-steepness * x))

    def analyze(self, history: List[Dict]) -> Dict:
        """
        分析每個號碼的遺漏壓力

        Args:
            history: 歷史開獎數據 (ASC: 舊→新)

        Returns:
            scores: {num: pressure_score}  (0~2 scale)
            pressure_ratios: {num: ratio}
            high_pressure_numbers: List[int]
            details: {num: {gap, avg_interval, ratio, score}}
        """
        if not history:
            return {
                'scores': {},
                'pressure_ratios': {},
                'high_pressure_numbers': [],
                'details': {}
            }

        n_draws = len(history)
        scores = {}
        pressure_ratios = {}
        details = {}

        for num in range(1, self.max_num + 1):
            # 找出所有出現位置
            appearances = []
            for idx, draw in enumerate(history):
                if num in draw.get('numbers', []):
                    appearances.append(idx)

            if not appearances:
                # 從未出現 → 設定極高壓力
                scores[num] = 2.0
                pressure_ratios[num] = float('inf')
                details[num] = {
                    'gap': n_draws,
                    'avg_interval': n_draws,
                    'ratio': float('inf'),
                    'score': 2.0,
                    'count': 0
                }
                continue

            count = len(appearances)
            last_appearance = appearances[-1]
            current_gap = (n_draws - 1) - last_appearance

            # 計算平均間隔
            if count >= 2:
                intervals = [
                    appearances[i + 1] - appearances[i]
                    for i in range(count - 1)
                ]
                avg_interval = sum(intervals) / len(intervals)
            else:
                # 只出現過一次：用總期數/出現次數作為估計
                avg_interval = n_draws / count

            # 避免除以零
            avg_interval = max(avg_interval, 1.0)

            # 壓力比
            ratio = current_gap / avg_interval

            # 壓力分數 (sigmoid scaled to 0~2)
            score = self._sigmoid(ratio - 1.0) * 2.0

            scores[num] = score
            pressure_ratios[num] = ratio
            details[num] = {
                'gap': current_gap,
                'avg_interval': round(avg_interval, 2),
                'ratio': round(ratio, 3),
                'score': round(score, 4),
                'count': count
            }

        # 找出高壓力號碼
        high_pressure = sorted(
            [num for num, ratio in pressure_ratios.items()
             if ratio > self.high_threshold],
            key=lambda n: pressure_ratios[n],
            reverse=True
        )

        return {
            'scores': scores,
            'pressure_ratios': pressure_ratios,
            'high_pressure_numbers': high_pressure,
            'details': details
        }

    def predict(self, history: List[Dict], lottery_rules: Dict,
                exclude: Optional[Set[int]] = None) -> Dict:
        """
        基於遺漏壓力生成預測

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則
            exclude: 需排除的號碼集合（用於正交化多注策略）

        Returns:
            標準預測結果 dict
        """
        exclude = exclude or set()
        pick_count = lottery_rules.get('pickCount', 5)

        # 確保歷史順序正確 (ASC)
        if history and len(history) > 1:
            if history[0].get('date', '0') > history[-1].get('date', '9'):
                history = list(reversed(history))

        analysis = self.analyze(history)
        scores = analysis['scores']

        if not scores:
            # 無數據兜底
            remaining = [n for n in range(1, self.max_num + 1) if n not in exclude]
            return {
                'numbers': remaining[:pick_count],
                'confidence': 0.1,
                'method': 'Gap Pressure (No Data)'
            }

        # 排除上期已出的號碼 (gap=0) 及 exclude set
        last_draw_nums = set()
        if history:
            last_draw_nums = set(history[-1].get('numbers', []))

        # 按壓力分數排序 (排除 gap=0 及 exclude set)
        candidates = [
            (num, score) for num, score in scores.items()
            if num not in last_draw_nums and num not in exclude
        ]
        candidates.sort(key=lambda x: x[1], reverse=True)

        selected = [num for num, _ in candidates[:pick_count]]

        # 信心度：基於高壓力號碼的集中程度
        if candidates:
            top_scores = [s for _, s in candidates[:pick_count]]
            avg_top = sum(top_scores) / len(top_scores)
            # 平均壓力分數越高 → 信心越高
            confidence = min(0.82, 0.55 + avg_top * 0.15)
        else:
            confidence = 0.5

        high_count = len(analysis['high_pressure_numbers'])

        return {
            'numbers': sorted(selected),
            'confidence': float(confidence),
            'method': f'Gap Pressure ({high_count} high-pressure nums)',
            'gap_analysis': {
                'high_pressure_numbers': analysis['high_pressure_numbers'][:10],
                'details': {
                    num: analysis['details'][num]
                    for num in selected
                }
            }
        }
