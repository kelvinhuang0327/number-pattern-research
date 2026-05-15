"""
Zone Shift Detector - 區間相位反轉偵測器

115000050 期檢討產出：
系統未能偵測連續10期高區(Z3: 27-39)低產出後的爆發性回歸。
本模組使用滑動窗口偵測區間偏差，當某區嚴重欠缺時，
tilting 預測分配至該區以捕捉 phase reversal。

演算法：
1. 3 zones: Z1(1-13), Z2(14-26), Z3(27-39)
2. 滑動窗口(預設10期)統計各區實際出現次數
3. 計算 deviation = actual - expected
4. deviation < threshold → 標記為 underrepresented → 傾斜分配
5. 完全確定性(deterministic)，無隨機元素
"""

import math
from collections import Counter
from typing import List, Dict, Tuple, Optional, Set


class ZoneShiftDetector:
    """滑動窗口區間偏差偵測器"""

    def __init__(self, max_num: int = 39, n_zones: int = 3,
                 window: int = 10, threshold: float = -3.0):
        self.max_num = max_num
        self.n_zones = n_zones
        self.window = window
        self.threshold = threshold

        # 計算區間邊界
        zone_size = max_num // n_zones
        self.zones = {}
        for i in range(n_zones):
            start = i * zone_size + 1
            end = (i + 1) * zone_size if i < n_zones - 1 else max_num
            self.zones[i + 1] = (start, end)

    def _get_zone(self, num: int) -> int:
        """返回號碼所屬的區間 ID (1-based)"""
        for zone_id, (start, end) in self.zones.items():
            if start <= num <= end:
                return zone_id
        return self.n_zones

    def analyze(self, history: List[Dict]) -> Dict:
        """
        分析區間偏差

        Args:
            history: 歷史開獎數據 (ASC: 舊→新)

        Returns:
            zone_deviations: {zone_id: float}
            shift_detected: bool
            underrepresented_zones: List[int]
            recommended_allocation: tuple (每區應選幾個號碼)
        """
        if len(history) < self.window:
            return {
                'zone_deviations': {z: 0.0 for z in self.zones},
                'shift_detected': False,
                'underrepresented_zones': [],
                'recommended_allocation': self._default_allocation(5)
            }

        # 取最近 window 期
        recent = history[-self.window:]

        # 統計各區出現次數
        zone_counts = {z: 0 for z in self.zones}
        total_numbers = 0
        for draw in recent:
            for num in draw.get('numbers', []):
                zone_id = self._get_zone(num)
                zone_counts[zone_id] += 1
                total_numbers += 1

        # 期望值：每區應平均分配
        expected_per_zone = total_numbers / self.n_zones

        # 計算偏差
        zone_deviations = {}
        for zone_id in self.zones:
            zone_deviations[zone_id] = zone_counts[zone_id] - expected_per_zone

        # 偵測 underrepresented zones
        underrepresented = [
            z for z, dev in zone_deviations.items()
            if dev < self.threshold
        ]

        shift_detected = len(underrepresented) > 0

        # 計算推薦分配
        pick_count = 5  # 539 固定 5 個
        recommended = self._calculate_allocation(
            zone_deviations, pick_count, shift_detected
        )

        return {
            'zone_deviations': zone_deviations,
            'zone_counts': zone_counts,
            'expected_per_zone': expected_per_zone,
            'shift_detected': shift_detected,
            'underrepresented_zones': underrepresented,
            'recommended_allocation': recommended
        }

    def _default_allocation(self, pick_count: int) -> Tuple[int, ...]:
        """預設均等分配: (2, 2, 1) for pick=5, 3 zones"""
        base = pick_count // self.n_zones
        remainder = pick_count % self.n_zones
        alloc = [base] * self.n_zones
        for i in range(remainder):
            alloc[i] += 1
        return tuple(alloc)

    def _calculate_allocation(self, deviations: Dict[int, float],
                              pick_count: int, shift_detected: bool) -> Tuple[int, ...]:
        """
        根據偏差計算推薦分配

        偏差越負 → 分配越多號碼到該區
        """
        if not shift_detected:
            return self._default_allocation(pick_count)

        # 反轉偏差作為權重（偏差越負 → 權重越高）
        weights = {}
        for zone_id, dev in deviations.items():
            weights[zone_id] = max(0.1, -dev + 1.0)

        total_weight = sum(weights.values())

        # 按權重分配
        alloc = []
        remaining = pick_count
        sorted_zones = sorted(weights.items(), key=lambda x: -x[1])

        for i, (zone_id, weight) in enumerate(sorted_zones):
            if i == len(sorted_zones) - 1:
                alloc.append((zone_id, remaining))
            else:
                n = max(1, round(pick_count * weight / total_weight))
                n = min(n, remaining - (len(sorted_zones) - i - 1))
                alloc.append((zone_id, n))
                remaining -= n

        # 按 zone_id 排序
        alloc.sort(key=lambda x: x[0])
        return tuple(n for _, n in alloc)

    def predict(self, history: List[Dict], lottery_rules: Dict,
                exclude: Optional[Set[int]] = None) -> Dict:
        """
        生成預測

        Args:
            history: 歷史開獎數據 (ASC: 舊→新)
            lottery_rules: 彩票規則
            exclude: 需排除的號碼集合（用於正交化多注策略）

        Returns:
            標準預測結果 dict
        """
        exclude = exclude or set()
        pick_count = lottery_rules.get('pickCount', 5)
        max_num = lottery_rules.get('maxNumber', self.max_num)

        # 確保歷史順序正確 (ASC)
        if history and len(history) > 1:
            if history[0].get('date', '0') > history[-1].get('date', '9'):
                history = list(reversed(history))

        analysis = self.analyze(history)
        allocation = analysis['recommended_allocation']

        # 計算各區頻率 (用於選號)
        freq_window = min(100, len(history))
        freq = Counter()
        for draw in history[-freq_window:]:
            for num in draw.get('numbers', []):
                freq[num] += 1

        # 按分配從各區選號
        selected = []
        for zone_idx, (zone_id, (start, end)) in enumerate(self.zones.items()):
            target_count = allocation[zone_idx] if zone_idx < len(allocation) else 0
            if target_count <= 0:
                continue

            # 取該區所有號碼，按頻率排名（排除 exclude set）
            zone_nums = [n for n in range(start, end + 1) if n not in exclude]
            zone_nums.sort(key=lambda n: freq.get(n, 0), reverse=True)

            # 選取 top N (排除已選)
            for n in zone_nums:
                if n not in selected:
                    selected.append(n)
                    if len(selected) >= sum(allocation[:zone_idx + 1]):
                        break

        # 補足 (若某區不夠)
        if len(selected) < pick_count:
            all_nums = [n for n in range(1, max_num + 1) if n not in exclude]
            all_nums.sort(key=lambda n: freq.get(n, 0), reverse=True)
            for n in all_nums:
                if n not in selected:
                    selected.append(n)
                    if len(selected) >= pick_count:
                        break

        selected = sorted(selected[:pick_count])

        # 信心度
        base_confidence = 0.65
        if analysis['shift_detected']:
            # shift 偵測到 → 信心較高
            max_dev = max(abs(d) for d in analysis['zone_deviations'].values())
            shift_bonus = min(0.15, max_dev * 0.03)
            confidence = min(0.82, base_confidence + shift_bonus)
        else:
            confidence = base_confidence

        method = 'Zone Shift'
        if analysis['shift_detected']:
            under_zones = analysis['underrepresented_zones']
            method += f' (Phase Reversal: Z{",Z".join(str(z) for z in under_zones)})'
        else:
            method += f' (Normal: {allocation})'

        return {
            'numbers': selected,
            'confidence': float(confidence),
            'method': method,
            'zone_analysis': analysis
        }
