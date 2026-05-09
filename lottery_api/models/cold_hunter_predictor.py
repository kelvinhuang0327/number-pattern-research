"""
冷號獵手預測器 (Cold Hunter Predictor)
基於 115000006 期檢討會議開發

核心理念：
1. 冷號獵手：專門追蹤高遺漏值號碼
2. 短期窗口偏差：使用 50 期滾動窗口取代全歷史
3. 大號回擺檢測：連續偏態後的反轉預測
4. 區域動量：追蹤各區域的短期趨勢

開發日期: 2026-01-21
觸發事件: 115000006 期全軍覆沒檢討
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Set
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class ColdHunterPredictor:
    """冷號獵手預測器"""

    def __init__(self):
        self.name = "ColdHunter"
        logger.info("ColdHunterPredictor 初始化完成")

    def calculate_gaps(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, int]:
        """
        計算每個號碼的遺漏期數

        Returns:
            {號碼: 遺漏期數}，遺漏期數越大表示越久沒開出
        """
        gaps = {}
        for num in range(min_num, max_num + 1):
            for i, draw in enumerate(history):
                if num in draw['numbers']:
                    gaps[num] = i
                    break
            if num not in gaps:
                gaps[num] = len(history)  # 從未出現
        return gaps

    def cold_hunter_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        cold_count: int = 2,
        hot_count: int = 3,
        warm_count: int = 1
    ) -> Dict:
        """
        冷號獵手策略 V2：混合選號（熱+溫+冷）

        基於 115000006 檢討發現：實際開獎通常是 3熱+1溫+2冷 的結構

        Args:
            history: 歷史開獎數據（最新在前）
            lottery_rules: 彩票規則
            cold_count: 冷號數量（遺漏>=10）
            hot_count: 熱號數量（遺漏<=3）
            warm_count: 溫號數量（遺漏 4-9）

        Returns:
            預測結果
        """
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)

        # 計算遺漏值
        gaps = self.calculate_gaps(history, min_num, max_num)

        # 分類號碼
        hot_nums = [(n, g) for n, g in gaps.items() if g <= 3]  # 熱號
        warm_nums = [(n, g) for n, g in gaps.items() if 4 <= g <= 9]  # 溫號
        cold_nums = [(n, g) for n, g in gaps.items() if g >= 10]  # 冷號

        # 按遺漏值排序
        hot_nums.sort(key=lambda x: x[1])  # 熱號選最熱的
        warm_nums.sort(key=lambda x: x[1], reverse=True)  # 溫號選偏冷的
        cold_nums.sort(key=lambda x: x[1], reverse=True)  # 冷號選最冷的

        predicted = []

        # 選熱號
        for num, gap in hot_nums[:hot_count]:
            predicted.append(num)

        # 選溫號
        for num, gap in warm_nums[:warm_count]:
            if num not in predicted:
                predicted.append(num)

        # 選冷號
        for num, gap in cold_nums[:cold_count]:
            if num not in predicted:
                predicted.append(num)

        # 補足至 pick_count
        all_sorted = sorted(gaps.items(), key=lambda x: x[1], reverse=True)
        for num, gap in all_sorted:
            if len(predicted) >= pick_count:
                break
            if num not in predicted:
                predicted.append(num)

        predicted = sorted(predicted[:pick_count])

        return {
            'numbers': predicted,
            'confidence': 0.70,
            'method': f'冷號獵手V2 ({hot_count}熱+{warm_count}溫+{cold_count}冷)',
            'meta_info': {
                'hot_selected': [n for n in predicted if gaps[n] <= 3],
                'warm_selected': [n for n in predicted if 4 <= gaps[n] <= 9],
                'cold_selected': [n for n in predicted if gaps[n] >= 10],
                'structure': f'{len([n for n in predicted if gaps[n] <= 3])}熱+{len([n for n in predicted if 4 <= gaps[n] <= 9])}溫+{len([n for n in predicted if gaps[n] >= 10])}冷'
            }
        }

    def short_window_deviation_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        window_size: int = 50
    ) -> Dict:
        """
        短期窗口偏差策略：只使用最近 N 期計算偏差

        相比全歷史 Deviation，這個方法對短期趨勢更敏感
        """
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)
        total_numbers = max_num - min_num + 1

        # 只使用最近 window_size 期
        recent_history = history[:window_size]

        if len(recent_history) < 10:
            recent_history = history  # 數據不足時使用全部

        # 計算短期頻率
        all_numbers = [num for draw in recent_history for num in draw['numbers']]
        frequency = Counter(all_numbers)

        # 計算期望頻率
        expected_freq = (len(recent_history) * pick_count) / total_numbers

        # 計算偏差分數（低於期望的得高分）
        scores = {}
        for num in range(min_num, max_num + 1):
            actual = frequency.get(num, 0)
            deviation = expected_freq - actual  # 正數表示低於期望
            scores[num] = max(0, deviation)  # 只考慮負偏差

        # 加入遺漏值權重（25%，提升自 10%）
        gaps = self.calculate_gaps(recent_history, min_num, max_num)
        max_gap = max(gaps.values()) if gaps else 1

        for num in range(min_num, max_num + 1):
            gap_score = gaps.get(num, 0) / max_gap
            scores[num] = scores.get(num, 0) * 0.75 + gap_score * 0.25

        # 選擇得分最高的號碼
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        predicted = sorted([num for num, score in sorted_scores[:pick_count]])

        # 計算信心度
        top_scores = [score for num, score in sorted_scores[:pick_count]]
        confidence = min(0.85, 0.55 + np.mean(top_scores) * 0.1)

        return {
            'numbers': predicted,
            'confidence': float(confidence),
            'method': f'短期偏差 ({window_size}期窗口)',
            'meta_info': {
                'window_size': window_size,
                'actual_periods': len(recent_history)
            }
        }

    def detect_large_number_rebound(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        consecutive_threshold: int = 3,
        max_large_count: int = 2
    ) -> Dict:
        """
        大號回擺檢測器 V2

        當連續 N 期大號數量 <= max_large_count 時，預測大號回擺

        Returns:
            {
                'should_rebound': bool,
                'consecutive_small_periods': int,
                'recommended_large_count': int,
                'recent_large_counts': List[int]
            }
        """
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)
        mid_point = (min_num + max_num) // 2

        # 計算最近幾期的大號數量
        recent_large_counts = []
        consecutive_small = 0
        found_break = False

        for draw in history[:10]:  # 只看最近 10 期
            large_count = sum(1 for n in draw['numbers'] if n > mid_point)
            recent_large_counts.append(large_count)

            if not found_break:
                if large_count <= max_large_count:
                    consecutive_small += 1
                else:
                    found_break = True  # 不再連續

        should_rebound = consecutive_small >= consecutive_threshold

        # 根據歷史統計，連續小號偏態後的平均大號數 3.09
        # 40% 機率出現 4+ 個大號
        recommended_large = 4 if should_rebound else 3

        return {
            'should_rebound': should_rebound,
            'consecutive_small_periods': consecutive_small,
            'recommended_large_count': recommended_large,
            'recent_large_counts': recent_large_counts[:5],
            'trigger_condition': f'連續{consecutive_small}期大號<={max_large_count}'
        }

    def rebound_aware_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        回擺感知預測 V2：根據大號回擺信號調整預測

        混合策略：熱+冷混合 + 大小號平衡
        """
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)
        mid_point = (min_num + max_num) // 2

        # 檢測回擺信號
        rebound_info = self.detect_large_number_rebound(history, lottery_rules)

        # 計算遺漏值
        gaps = self.calculate_gaps(history, min_num, max_num)

        # 分離大號和小號
        large_nums = {n: g for n, g in gaps.items() if n > mid_point}
        small_nums = {n: g for n, g in gaps.items() if n <= mid_point}

        # 根據回擺信號決定大小號比例
        if rebound_info['should_rebound']:
            # 需要回擺：多選大號（4個大號，2個小號）
            target_large = 4
            target_small = 2
            logger.info(f"🔄 偵測到回擺信號！{rebound_info['trigger_condition']}")
        else:
            # 正常情況：3:3
            target_large = 3
            target_small = 3

        predicted = []

        # 從大號中選（混合熱+冷）
        # 1個熱大號 + 1個冷大號 + 其餘溫大號
        large_hot = [(n, g) for n, g in large_nums.items() if g <= 3]
        large_cold = [(n, g) for n, g in large_nums.items() if g >= 10]
        large_warm = [(n, g) for n, g in large_nums.items() if 4 <= g <= 9]

        large_hot.sort(key=lambda x: x[1])
        large_cold.sort(key=lambda x: x[1], reverse=True)
        large_warm.sort(key=lambda x: x[1], reverse=True)

        # 選 1 熱大號
        if large_hot:
            predicted.append(large_hot[0][0])
        # 選 1 冷大號
        if large_cold:
            for n, g in large_cold:
                if n not in predicted:
                    predicted.append(n)
                    break
        # 補足大號
        for n, g in large_warm + large_cold[1:] + large_hot[1:]:
            if len([p for p in predicted if p > mid_point]) >= target_large:
                break
            if n not in predicted:
                predicted.append(n)

        # 從小號中選（同樣混合策略）
        small_hot = [(n, g) for n, g in small_nums.items() if g <= 3]
        small_cold = [(n, g) for n, g in small_nums.items() if g >= 10]
        small_warm = [(n, g) for n, g in small_nums.items() if 4 <= g <= 9]

        small_hot.sort(key=lambda x: x[1])
        small_cold.sort(key=lambda x: x[1], reverse=True)
        small_warm.sort(key=lambda x: x[1], reverse=True)

        # 選 1 熱小號
        if small_hot:
            for n, g in small_hot:
                if n not in predicted:
                    predicted.append(n)
                    break
        # 補足小號
        for n, g in small_warm + small_cold + small_hot[1:]:
            if len([p for p in predicted if p <= mid_point]) >= target_small:
                break
            if n not in predicted:
                predicted.append(n)

        predicted = sorted(predicted[:pick_count])

        return {
            'numbers': predicted,
            'confidence': 0.75 if rebound_info['should_rebound'] else 0.65,
            'method': '回擺感知V2',
            'meta_info': {
                'rebound_detected': rebound_info['should_rebound'],
                'trigger': rebound_info['trigger_condition'],
                'recent_large_counts': rebound_info['recent_large_counts'],
                'target_ratio': f"大{target_large}:小{target_small}",
                'actual_ratio': f"大{len([p for p in predicted if p > mid_point])}:小{len([p for p in predicted if p <= mid_point])}"
            }
        }

    def calculate_zone_momentum(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        window_size: int = 10
    ) -> Dict[int, float]:
        """
        計算區域動量

        動量 > 0：該區域近期出現頻率高於歷史平均
        動量 < 0：該區域近期出現頻率低於歷史平均
        """
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        # 定義 5 個區域
        zone_size = (max_num - min_num + 1) // 5
        zones = {}
        for i in range(1, 6):
            start = min_num + (i - 1) * zone_size
            end = max_num if i == 5 else min_num + i * zone_size - 1
            zones[i] = list(range(start, end + 1))

        # 計算長期區域分布（全歷史）
        long_term_counts = {i: 0 for i in zones}
        for draw in history:
            for num in draw['numbers']:
                for zone_id, zone_nums in zones.items():
                    if num in zone_nums:
                        long_term_counts[zone_id] += 1

        total_long = sum(long_term_counts.values())
        long_term_ratio = {z: c / total_long if total_long > 0 else 0.2
                          for z, c in long_term_counts.items()}

        # 計算短期區域分布（最近 window_size 期）
        short_term_counts = {i: 0 for i in zones}
        for draw in history[:window_size]:
            for num in draw['numbers']:
                for zone_id, zone_nums in zones.items():
                    if num in zone_nums:
                        short_term_counts[zone_id] += 1

        total_short = sum(short_term_counts.values())
        short_term_ratio = {z: c / total_short if total_short > 0 else 0.2
                           for z, c in short_term_counts.items()}

        # 計算動量（短期 - 長期）
        momentum = {z: short_term_ratio[z] - long_term_ratio[z] for z in zones}

        return {
            'momentum': momentum,
            'zones': zones,
            'long_term_ratio': long_term_ratio,
            'short_term_ratio': short_term_ratio
        }

    def zone_momentum_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        區域動量預測：從負動量區域（近期偏少，需要補償）選號
        """
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)

        # 計算區域動量
        zone_info = self.calculate_zone_momentum(history, lottery_rules)
        momentum = zone_info['momentum']
        zones = zone_info['zones']

        # 按動量排序（負動量優先 = 需要補償）
        sorted_zones = sorted(momentum.items(), key=lambda x: x[1])

        # 計算遺漏值
        gaps = self.calculate_gaps(history, min_num, max_num)

        # 從負動量區域中選號（優先遺漏值高的）
        predicted = []
        for zone_id, mom in sorted_zones:
            if len(predicted) >= pick_count:
                break

            zone_nums = zones[zone_id]
            # 該區域的號碼按遺漏值排序
            zone_gaps = [(n, gaps.get(n, 0)) for n in zone_nums]
            zone_gaps.sort(key=lambda x: x[1], reverse=True)

            # 從該區域選 1-2 個
            count = 2 if mom < -0.05 else 1  # 負動量越大選越多
            for num, gap in zone_gaps:
                if num not in predicted:
                    predicted.append(num)
                    if len(predicted) >= pick_count:
                        break
                    count -= 1
                    if count <= 0:
                        break

        predicted = sorted(predicted[:pick_count])

        return {
            'numbers': predicted,
            'confidence': 0.65,
            'method': '區域動量預測',
            'meta_info': {
                'zone_momentum': {f'Z{k}': f'{v:+.3f}' for k, v in momentum.items()},
                'negative_momentum_zones': [z for z, m in sorted_zones if m < 0]
            }
        }

    def pure_cold_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        top_n: int = 6
    ) -> Dict:
        """
        純冷號策略：專門選遺漏值最高的號碼（用於覆蓋極端冷號）
        """
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)

        gaps = self.calculate_gaps(history, min_num, max_num)
        sorted_by_gap = sorted(gaps.items(), key=lambda x: x[1], reverse=True)

        predicted = sorted([num for num, gap in sorted_by_gap[:top_n]])

        return {
            'numbers': predicted,
            'confidence': 0.55,
            'method': f'純冷號 (Top {top_n})',
            'meta_info': {
                'selected_gaps': [(num, gaps[num]) for num in predicted]
            }
        }

    def ensemble_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        num_bets: int = 3
    ) -> Dict:
        """
        組合預測 V2：結合所有新方法產生多注

        策略組合（正交設計，最大化覆蓋）:
        - 注1: 冷號獵手V2 (3熱+1溫+2冷混合)
        - 注2: 回擺感知V2 (大小號平衡 + 熱冷混合)
        - 注3: 純冷號 (覆蓋極端冷號)
        - 注4: 區域動量 (區域平衡)
        """
        bets = []
        rebound_info = self.detect_large_number_rebound(history, lottery_rules)

        # 注1: 冷號獵手V2 (混合策略)
        cold_result = self.cold_hunter_predict(history, lottery_rules)
        bets.append({
            'numbers': cold_result['numbers'],
            'source': 'ColdHunterV2',
            'confidence': cold_result['confidence'],
            'meta': cold_result.get('meta_info', {})
        })

        # 注2: 回擺感知V2
        rebound_result = self.rebound_aware_predict(history, lottery_rules)
        bets.append({
            'numbers': rebound_result['numbers'],
            'source': 'ReboundV2',
            'confidence': rebound_result['confidence'],
            'meta': rebound_result.get('meta_info', {})
        })

        if num_bets >= 3:
            # 注3: 純冷號（覆蓋極端冷號，與其他注正交）
            pure_cold_result = self.pure_cold_predict(history, lottery_rules)
            bets.append({
                'numbers': pure_cold_result['numbers'],
                'source': 'PureCold',
                'confidence': pure_cold_result['confidence'],
                'meta': pure_cold_result.get('meta_info', {})
            })

        if num_bets >= 4:
            # 注4: 區域動量
            zone_result = self.zone_momentum_predict(history, lottery_rules)
            bets.append({
                'numbers': zone_result['numbers'],
                'source': 'ZoneMomentum',
                'confidence': zone_result['confidence'],
                'meta': zone_result.get('meta_info', {})
            })

        return {
            'bets': bets[:num_bets],
            'method': f'ColdHunter Ensemble V2 ({num_bets} bets)',
            'meta_info': {
                'rebound_info': rebound_info,
                'zone_momentum': self.calculate_zone_momentum(history, lottery_rules)['momentum']
            }
        }


    def moderate_rank_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        exclude_last_draw: bool = True,
        hot_rank_range: Tuple[int, int] = (5, 15),
        cold_gap_range: Tuple[int, int] = (8, 14)
    ) -> Dict:
        """
        中值選號策略 (Moderate Rank Selection)

        基於 115000006 檢討發現：
        - 上一期號碼幾乎不會重複
        - 實際開獎是「中等排名」而非極端值
        - 熱號排名 7, 13, 17（不是前3）
        - 冷號排名 10, 11（不是前6）

        策略：
        1. 排除上一期開獎號碼（遺漏=0）
        2. 熱號選排名 5-15，不選前 3
        3. 冷號選遺漏 8-14，不選遺漏 >15
        """
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)
        mid_point = (min_num + max_num) // 2

        # 計算遺漏值
        gaps = self.calculate_gaps(history, min_num, max_num)

        # 排除上一期號碼
        if exclude_last_draw and history:
            last_draw_nums = set(history[0]['numbers'])
        else:
            last_draw_nums = set()

        # 過濾掉上期號碼
        filtered_gaps = {n: g for n, g in gaps.items() if n not in last_draw_nums}

        # 分類（排除上期後）
        hot_nums = [(n, g) for n, g in filtered_gaps.items() if g <= 3]
        warm_nums = [(n, g) for n, g in filtered_gaps.items() if 4 <= g <= 7]
        moderate_cold = [(n, g) for n, g in filtered_gaps.items()
                        if cold_gap_range[0] <= g <= cold_gap_range[1]]

        # 排序
        hot_nums.sort(key=lambda x: x[1])  # 遺漏小的在前
        warm_nums.sort(key=lambda x: x[1], reverse=True)  # 遺漏大的在前
        moderate_cold.sort(key=lambda x: x[1], reverse=True)

        predicted = []

        # 選中等排名的熱號（跳過前幾名）
        hot_start, hot_end = hot_rank_range
        selected_hot = hot_nums[hot_start:hot_end]

        # 從中等熱號中選 2-3 個（平衡大小號）
        hot_small = [n for n, g in selected_hot if n <= mid_point]
        hot_large = [n for n, g in selected_hot if n > mid_point]

        # 選 1 小熱 + 1 大熱
        if hot_small:
            predicted.append(hot_small[0])
        if hot_large:
            predicted.append(hot_large[0])
        # 補充到 3 個熱號
        for n, g in selected_hot:
            if len([p for p in predicted if gaps.get(p, 0) <= 3]) >= 3:
                break
            if n not in predicted:
                predicted.append(n)

        # 選 1 個溫號
        for n, g in warm_nums[:3]:
            if n not in predicted:
                predicted.append(n)
                break

        # 選 2 個中等冷號（遺漏 8-14）
        cold_count = 0
        for n, g in moderate_cold:
            if cold_count >= 2:
                break
            if n not in predicted:
                predicted.append(n)
                cold_count += 1

        # 補足至 pick_count
        all_filtered = sorted(filtered_gaps.items(), key=lambda x: x[1])
        for n, g in all_filtered:
            if len(predicted) >= pick_count:
                break
            if n not in predicted:
                predicted.append(n)

        predicted = sorted(predicted[:pick_count])

        return {
            'numbers': predicted,
            'confidence': 0.70,
            'method': '中值選號 (排除上期+中等排名)',
            'meta_info': {
                'excluded_last_draw': list(last_draw_nums),
                'hot_rank_range': f'{hot_start}-{hot_end}',
                'cold_gap_range': f'{cold_gap_range[0]}-{cold_gap_range[1]}',
                'structure': {
                    'hot': [n for n in predicted if filtered_gaps.get(n, 99) <= 3],
                    'warm': [n for n in predicted if 4 <= filtered_gaps.get(n, 0) <= 7],
                    'cold': [n for n in predicted if filtered_gaps.get(n, 0) >= 8]
                }
            }
        }

    def anti_extreme_ensemble_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        num_bets: int = 3
    ) -> Dict:
        """
        反極端組合策略 (Anti-Extreme Ensemble)

        基於 115000006 深度診斷的新策略：
        - 注1: 中值選號（排除上期 + 中等排名）
        - 注2: 回擺感知 + 排除上期
        - 注3: 區域動量 + 排除上期
        """
        bets = []
        rebound_info = self.detect_large_number_rebound(history, lottery_rules)

        # 獲取上期號碼用於排除
        last_draw = set(history[0]['numbers']) if history else set()

        # 注1: 中值選號
        moderate_result = self.moderate_rank_predict(history, lottery_rules)
        bets.append({
            'numbers': moderate_result['numbers'],
            'source': 'ModerateRank',
            'confidence': moderate_result['confidence'],
            'meta': moderate_result.get('meta_info', {})
        })

        # 注2: 回擺感知 + 排除上期
        rebound_result = self.rebound_aware_predict(history, lottery_rules)
        rebound_nums = [n for n in rebound_result['numbers'] if n not in last_draw]
        # 補足被排除的號碼
        gaps = self.calculate_gaps(history, 1, 49)
        sorted_gaps = sorted(gaps.items(), key=lambda x: x[1], reverse=True)
        for n, g in sorted_gaps:
            if len(rebound_nums) >= 6:
                break
            if n not in rebound_nums and n not in last_draw:
                rebound_nums.append(n)
        rebound_nums = sorted(rebound_nums[:6])
        bets.append({
            'numbers': rebound_nums,
            'source': 'ReboundFiltered',
            'confidence': rebound_result['confidence'],
            'meta': {'excluded': list(last_draw)}
        })

        if num_bets >= 3:
            # 注3: 純冷號（中等冷，排除極端）
            moderate_cold_result = self.moderate_rank_predict(
                history, lottery_rules,
                hot_rank_range=(10, 20),  # 更後段的熱號
                cold_gap_range=(10, 16)   # 稍微更冷
            )
            bets.append({
                'numbers': moderate_cold_result['numbers'],
                'source': 'ModerateCold',
                'confidence': 0.60,
                'meta': moderate_cold_result.get('meta_info', {})
            })

        return {
            'bets': bets[:num_bets],
            'method': f'Anti-Extreme Ensemble ({num_bets} bets)',
            'meta_info': {
                'rebound_info': rebound_info,
                'excluded_last_draw': list(last_draw)
            }
        }


# 便捷函數
def get_cold_hunter_predictor():
    """獲取冷號獵手預測器實例"""
    return ColdHunterPredictor()
