"""
增強型預測器 - 基於研究分析設計的新預測方法

主要改進：
1. 連號友善策略 - 不迴避上期出現的號碼（歷史數據顯示 55% 機率有重複）
2. 冷號回歸預測 - 專門追蹤即將回歸的冷號
3. 約束條件優化 - 加入奇偶比、和值範圍等統計約束
4. 多重時間窗口 - 結合短中長期分析
5. 覆蓋率優化 - 基於組合數學的覆蓋設計
"""

import numpy as np
from collections import Counter
from typing import List, Dict, Tuple, Set
import random
from itertools import combinations


class EnhancedPredictor:
    """增強型預測器"""

    def __init__(self):
        self.name = "EnhancedPredictor"

    # ==================== 方法 1: 連號友善策略 ====================
    def consecutive_friendly_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        連號友善策略 - 不迴避上期號碼，反而給予適當權重

        歷史分析顯示：
        - 55.3% 的開獎有與上期重複的號碼
        - 39.1% 有 1 個重複，14.1% 有 2 個重複
        """
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))

        if len(history) < 10:
            return {'numbers': random.sample(range(min_num, max_num + 1), pick_count)}

        # 上期號碼
        last_numbers = set(history[0]['numbers'])

        # 計算各號碼的分數
        scores = {}
        for num in range(min_num, max_num + 1):
            score = 0

            # 1. 基礎頻率分數 (近 50 期)
            freq = sum(1 for h in history[:50] if num in h['numbers'])
            score += freq * 2

            # 2. 連號加分 - 上期出現的號碼有 55% 機率再出現至少一個
            if num in last_numbers:
                score += 15  # 給予連號加分

            # 3. 近期趨勢 (近 10 期出現次數)
            recent_freq = sum(1 for h in history[:10] if num in h['numbers'])
            score += recent_freq * 3

            # 4. 間隔分析 - 找到適當回歸週期的號碼
            gap = self._calculate_gap(history, num)
            avg_gap = self._calculate_avg_gap(history, num)
            if avg_gap > 0 and gap >= avg_gap * 0.8:
                score += 10  # 接近平均間隔的號碼加分

            scores[num] = score

        # 選擇得分最高的號碼
        sorted_nums = sorted(scores.keys(), key=lambda x: -scores[x])

        # 確保至少包含 1-2 個上期號碼（如果分數夠高）
        selected = []
        last_included = 0

        for num in sorted_nums:
            if len(selected) >= pick_count:
                break
            if num in last_numbers and last_included < 2:
                selected.append(num)
                last_included += 1
            elif num not in last_numbers:
                selected.append(num)

        # 補足數量
        for num in sorted_nums:
            if len(selected) >= pick_count:
                break
            if num not in selected:
                selected.append(num)

        return {
            'numbers': sorted(selected[:pick_count]),
            'confidence': 0.75,
            'method': 'consecutive_friendly'
        }

    # ==================== 方法 2: 冷號回歸預測 (改進版) ====================
    def cold_number_comeback_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        冷號回歸策略 (改進版) - 預測即將回歸的冷號

        改進重點：
        1. 降低臨界閾值 - 當間隔達到平均值的 80% 就開始關注
        2. 加入「臨界區間」概念 - 接近平均間隔時給予高權重
        3. 使用歷史間隔分佈計算回歸機率
        4. 區分「即將回歸」和「嚴重過期」兩種情況
        5. 考慮號碼的間隔穩定性
        """
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))

        if len(history) < 50:
            return {'numbers': random.sample(range(min_num, max_num + 1), pick_count)}

        comeback_scores = {}
        comeback_details = {}  # 用於調試

        for num in range(min_num, max_num + 1):
            # 計算當前間隔
            current_gap = self._calculate_gap(history, num)
            # 計算平均間隔
            avg_gap = self._calculate_avg_gap(history, num)
            # 計算間隔標準差（穩定性指標）
            gap_std = self._calculate_gap_std(history, num)
            # 計算歷史間隔分佈中，當前間隔的百分位數
            gap_percentile = self._calculate_gap_percentile(history, num, current_gap)

            if avg_gap == 0:
                comeback_scores[num] = 0
                continue

            score = 0
            gap_ratio = current_gap / avg_gap

            # ====== 核心改進：多層次回歸評分 ======

            # 1. 臨界區間評分（接近平均間隔時開始加分）
            #    這是主要改進 - 讓 gap_ratio 0.8-1.2 的號碼得到更高關注
            if gap_ratio >= 2.0:
                # 嚴重過期 - 可能有異常，給中高分
                score = 85
            elif gap_ratio >= 1.5:
                # 明顯過期 - 高機率回歸
                score = 95
            elif gap_ratio >= 1.2:
                # 超過平均 - 進入回歸高峰期 ★ 主要改進點
                score = 100  # 提高分數，這是最佳回歸時機
            elif gap_ratio >= 1.0:
                # 達到平均 - 開始進入回歸期 ★ 主要改進點
                score = 90
            elif gap_ratio >= 0.8:
                # 接近平均 - 即將進入回歸期 ★ 主要改進點
                score = 75
            elif gap_ratio >= 0.6:
                # 中間階段
                score = 50
            else:
                # 剛出現不久
                score = 20

            # 2. 歷史間隔分佈加成（基於實際數據的回歸機率）
            #    如果當前間隔在歷史上經常出現回歸，加分
            if gap_percentile >= 70:
                # 當前間隔已超過歷史 70% 的間隔，回歸機率高
                score += 25
            elif gap_percentile >= 50:
                score += 15
            elif gap_percentile >= 30:
                score += 5

            # 3. 穩定性加成（間隔穩定的號碼更容易預測）
            if gap_std > 0 and avg_gap > 0:
                cv = gap_std / avg_gap  # 變異係數
                if cv < 0.5:
                    # 間隔很穩定，預測更可靠
                    score *= 1.2
                elif cv < 0.8:
                    score *= 1.1

            # 4. 頻率正常性加成（過濾異常號碼）
            total_freq = sum(1 for h in history if num in h['numbers'])
            # 使用 pick_count 而非硬編碼，適應不同彩券類型
            expected_freq = len(history) * pick_count / max_num
            freq_ratio = total_freq / expected_freq if expected_freq > 0 else 1

            if 0.85 <= freq_ratio <= 1.15:
                # 頻率正常，更值得信賴
                score *= 1.15
            elif freq_ratio < 0.7:
                # 頻率過低，可能是真正的冷號，額外加分
                score *= 1.1

            # 5. 近期趨勢修正
            #    如果近期（10期內）完全沒出現，但又接近平均間隔，額外加分
            recent_appearances = sum(1 for h in history[:10] if num in h['numbers'])
            if recent_appearances == 0 and gap_ratio >= 0.8:
                score += 15

            comeback_scores[num] = score
            comeback_details[num] = {
                'current_gap': current_gap,
                'avg_gap': round(avg_gap, 1),
                'gap_ratio': round(gap_ratio, 2),
                'gap_percentile': round(gap_percentile, 1),
                'score': round(score, 1)
            }

        # ====== 改進的選號策略：分層選號 ======
        # 問題：極端過期的號碼會搶走所有位置，導致「最佳回歸區間」的號碼被忽略
        # 解決：分層選號，確保各個回歸階段都有代表

        # 將號碼按回歸階段分類
        optimal_zone = []      # 間隔比 1.0-1.5（最佳回歸時機）
        overdue_zone = []      # 間隔比 1.5-2.5（明顯過期）
        extreme_zone = []      # 間隔比 > 2.5（極端過期，可能有異常）
        approaching_zone = []  # 間隔比 0.7-1.0（即將到達平均）

        for num in range(min_num, max_num + 1):
            if num not in comeback_details:
                continue
            ratio = comeback_details[num]['gap_ratio']
            score = comeback_scores[num]

            if 1.0 <= ratio < 1.5:
                optimal_zone.append((num, score))
            elif 1.5 <= ratio < 2.5:
                overdue_zone.append((num, score))
            elif ratio >= 2.5:
                extreme_zone.append((num, score))
            elif 0.7 <= ratio < 1.0:
                approaching_zone.append((num, score))

        # 對每個區間按分數排序
        optimal_zone.sort(key=lambda x: -x[1])
        overdue_zone.sort(key=lambda x: -x[1])
        extreme_zone.sort(key=lambda x: -x[1])
        approaching_zone.sort(key=lambda x: -x[1])

        # 分層選號策略（根據 pick_count 動態調整比例）
        # 適應不同彩券類型：威力彩(6), 大樂透(6), 今彩539(5), 雙贏彩(12)
        selected = []

        # 計算各區間的選號數量（按比例分配）
        # 最佳回歸區: 50%, 過期區: 33%, 即將到達區: 17%
        target_optimal = max(1, round(pick_count * 0.5))
        target_overdue = max(1, round(pick_count * 0.33))
        target_approaching = max(1, round(pick_count * 0.17))

        # 1. 從最佳回歸區選號（這是我們主要改進的地方）
        optimal_count = min(target_optimal, len(optimal_zone), pick_count)
        for num, _ in optimal_zone[:optimal_count]:
            selected.append(num)

        # 2. 從明顯過期區選號
        overdue_count = min(target_overdue, len(overdue_zone), pick_count - len(selected))
        for num, _ in overdue_zone[:overdue_count]:
            if num not in selected:
                selected.append(num)

        # 3. 從即將到達區選號（捕捉即將進入最佳區的號碼）
        approaching_count = min(target_approaching, len(approaching_zone), pick_count - len(selected))
        for num, _ in approaching_zone[:approaching_count]:
            if num not in selected:
                selected.append(num)

        # 4. 如果還不夠，從極端過期區補充（但要謹慎）
        if len(selected) < pick_count and extreme_zone:
            for num, _ in extreme_zone:
                if num not in selected:
                    selected.append(num)
                if len(selected) >= pick_count:
                    break

        # 5. 最後用高分號碼補足
        if len(selected) < pick_count:
            sorted_nums = sorted(comeback_scores.keys(), key=lambda x: -comeback_scores[x])
            for num in sorted_nums:
                if num not in selected:
                    selected.append(num)
                if len(selected) >= pick_count:
                    break

        selected = selected[:pick_count]

        # 計算平均信心度
        avg_score = np.mean([comeback_scores[n] for n in selected])
        confidence = min(0.85, 0.5 + avg_score / 300)

        return {
            'numbers': sorted(selected),
            'confidence': confidence,
            'method': 'cold_comeback_v2',
            'details': {n: comeback_details[n] for n in selected},
            'zone_distribution': {
                'optimal': [n for n, _ in optimal_zone[:3]],
                'overdue': [n for n, _ in overdue_zone[:3]],
                'approaching': [n for n, _ in approaching_zone[:3]],
                'extreme': [n for n, _ in extreme_zone[:3]]
            }
        }

    def _calculate_gap_std(self, history: List[Dict], num: int) -> float:
        """計算號碼間隔的標準差"""
        appearances = [i for i, h in enumerate(history) if num in h['numbers']]
        if len(appearances) < 3:
            return 5.0  # 默認標準差

        gaps = [appearances[i+1] - appearances[i] for i in range(len(appearances)-1)]
        return float(np.std(gaps))

    def _calculate_gap_percentile(self, history: List[Dict], num: int, current_gap: int) -> float:
        """計算當前間隔在歷史間隔分佈中的百分位數"""
        appearances = [i for i, h in enumerate(history) if num in h['numbers']]
        if len(appearances) < 3:
            return 50.0  # 默認中位數

        gaps = [appearances[i+1] - appearances[i] for i in range(len(appearances)-1)]
        # 計算有多少比例的歷史間隔小於當前間隔
        smaller_count = sum(1 for g in gaps if g < current_gap)
        return (smaller_count / len(gaps)) * 100

    # ==================== 方法 3: 約束條件優化 ====================
    def constrained_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        約束條件優化策略 - 基於統計約束選號

        約束條件：
        1. 奇偶比: 4:2 或 3:3 最常見（合計 59%）
        2. 和值範圍: 128-173（中間 50%）
        3. 區間分佈: 每個區間 1-2 個
        4. 連號考慮: 允許 1-2 個上期號碼
        """
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))

        # 計算候選號碼的分數
        scores = self._calculate_base_scores(history, min_num, max_num)

        # 生成多組候選組合
        best_combo = None
        best_score = -1

        for _ in range(1000):  # 嘗試 1000 次
            # 根據分數加權隨機選擇
            weights = [scores[n] + 1 for n in range(min_num, max_num + 1)]
            total_weight = sum(weights)
            probs = [w / total_weight for w in weights]

            candidates = list(range(min_num, max_num + 1))
            selected = np.random.choice(candidates, size=pick_count, replace=False, p=probs)
            selected = sorted(selected.tolist())

            # 檢查約束條件
            constraint_score = self._evaluate_constraints(selected, history)
            total_score = sum(scores[n] for n in selected) + constraint_score * 10

            if total_score > best_score:
                best_score = total_score
                best_combo = selected

        return {
            'numbers': best_combo,
            'confidence': 0.78,
            'method': 'constrained'
        }

    def _evaluate_constraints(self, numbers: List[int], history: List[Dict]) -> float:
        """評估約束條件滿足程度"""
        score = 0

        # 1. 奇偶比約束 (4:2 或 3:3 最佳)
        odd_count = sum(1 for n in numbers if n % 2 == 1)
        if odd_count in [3, 4]:
            score += 20
        elif odd_count in [2, 5]:
            score += 10

        # 2. 和值約束 (128-173 最佳)
        total_sum = sum(numbers)
        if 128 <= total_sum <= 173:
            score += 20
        elif 100 <= total_sum <= 200:
            score += 10

        # 3. 區間分佈約束
        zones = [(1, 10), (11, 20), (21, 30), (31, 40), (41, 49)]
        zone_counts = []
        for z_min, z_max in zones:
            count = sum(1 for n in numbers if z_min <= n <= z_max)
            zone_counts.append(count)

        # 理想分佈：每個區間 1-2 個
        good_zones = sum(1 for c in zone_counts if 1 <= c <= 2)
        score += good_zones * 4

        # 4. 連號約束 - 允許 1-2 個上期號碼
        if history:
            last_nums = set(history[0]['numbers'])
            overlap = len(set(numbers) & last_nums)
            if overlap in [1, 2]:
                score += 15

        return score

    # ==================== 方法 4: 多重時間窗口融合 ====================
    def multi_window_fusion_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        多重時間窗口融合 - 結合短期、中期、長期分析

        - 短期 (10期): 捕捉近期熱門趨勢
        - 中期 (30期): 識別穩定模式
        - 長期 (100期): 驗證整體頻率
        """
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))

        # 各時間窗口的頻率分析
        short_freq = Counter()
        mid_freq = Counter()
        long_freq = Counter()

        for i, h in enumerate(history[:100]):
            for num in h['numbers']:
                if i < 10:
                    short_freq[num] += 3  # 短期權重高
                if i < 30:
                    mid_freq[num] += 2
                long_freq[num] += 1

        # 融合分數
        fusion_scores = {}
        for num in range(min_num, max_num + 1):
            # 加權融合
            score = (
                short_freq.get(num, 0) * 0.4 +
                mid_freq.get(num, 0) * 0.35 +
                long_freq.get(num, 0) * 0.25
            )

            # 一致性獎勵：在多個時間窗口都表現好的號碼
            windows_active = sum([
                1 if short_freq.get(num, 0) >= 2 else 0,
                1 if mid_freq.get(num, 0) >= 4 else 0,
                1 if long_freq.get(num, 0) >= 10 else 0
            ])
            if windows_active >= 2:
                score *= 1.3

            fusion_scores[num] = score

        # 選擇得分最高的
        sorted_nums = sorted(fusion_scores.keys(), key=lambda x: -fusion_scores[x])
        selected = sorted_nums[:pick_count]

        return {
            'numbers': sorted(selected),
            'confidence': 0.76,
            'method': 'multi_window_fusion'
        }

    # ==================== 方法 5: 覆蓋率優化策略 ====================
    def coverage_optimized_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        覆蓋率優化策略 - 基於組合數學的覆蓋設計

        目標：選擇能覆蓋更多可能組合的號碼
        """
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))

        # 計算各號碼的基礎分數
        base_scores = self._calculate_base_scores(history, min_num, max_num)

        # 選擇高分號碼池（前 15-20 個）
        sorted_nums = sorted(base_scores.keys(), key=lambda x: -base_scores[x])
        candidate_pool = sorted_nums[:18]

        # 使用貪婪算法選擇覆蓋率最高的組合
        selected = []
        remaining = set(candidate_pool)

        while len(selected) < pick_count and remaining:
            best_num = None
            best_coverage = -1

            for num in remaining:
                # 計算加入此號碼後的覆蓋分數
                coverage = self._calculate_coverage_score(selected + [num], history)
                if coverage > best_coverage:
                    best_coverage = coverage
                    best_num = num

            if best_num is not None:
                selected.append(best_num)
                remaining.remove(best_num)

        return {
            'numbers': sorted(selected),
            'confidence': 0.74,
            'method': 'coverage_optimized'
        }

    def _calculate_coverage_score(self, numbers: List[int], history: List[Dict]) -> float:
        """計算號碼組合的覆蓋分數"""
        if len(numbers) == 0:
            return 0

        score = 0
        numbers_set = set(numbers)

        # 1. 區間覆蓋
        zones = [(1, 10), (11, 20), (21, 30), (31, 40), (41, 49)]
        covered_zones = set()
        for num in numbers:
            for i, (z_min, z_max) in enumerate(zones):
                if z_min <= num <= z_max:
                    covered_zones.add(i)
        score += len(covered_zones) * 10

        # 2. 數字分散度
        if len(numbers) > 1:
            numbers_sorted = sorted(numbers)
            gaps = [numbers_sorted[i+1] - numbers_sorted[i] for i in range(len(numbers_sorted)-1)]
            avg_gap = np.mean(gaps)
            # 理想間隔約 8 (49/6)
            if 5 <= avg_gap <= 12:
                score += 15

        # 3. 歷史配對頻率
        if len(history) > 20 and len(numbers) >= 2:
            pair_freq = Counter()
            for h in history[:50]:
                h_nums = h['numbers']
                for pair in combinations(h_nums, 2):
                    pair_freq[tuple(sorted(pair))] += 1

            # 檢查當前組合中的配對
            for pair in combinations(numbers, 2):
                if pair_freq.get(tuple(sorted(pair)), 0) >= 2:
                    score += 3

        return score

    # ==================== 方法 6: 綜合增強預測 ====================
    def enhanced_ensemble_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        綜合增強預測 - 融合所有新方法的優點
        """
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))

        # 收集各方法的預測
        methods = [
            self.consecutive_friendly_predict,
            self.cold_number_comeback_predict,
            self.constrained_predict,
            self.multi_window_fusion_predict,
            self.coverage_optimized_predict,
        ]

        # 投票統計
        votes = Counter()

        for method in methods:
            try:
                result = method(history, lottery_rules)
                for num in result['numbers']:
                    votes[num] += 1
            except:
                pass

        # 加入基礎分數調整
        base_scores = self._calculate_base_scores(history, min_num, max_num)

        final_scores = {}
        for num in range(min_num, max_num + 1):
            # 投票分數 + 基礎分數
            final_scores[num] = votes.get(num, 0) * 20 + base_scores.get(num, 0)

        # 選擇最高分的號碼
        sorted_nums = sorted(final_scores.keys(), key=lambda x: -final_scores[x])

        # 應用約束條件篩選
        best_combo = None
        best_score = -1

        for _ in range(500):
            # 從高分號碼中加權選擇
            top_candidates = sorted_nums[:20]
            weights = [final_scores[n] + 1 for n in top_candidates]
            total_w = sum(weights)
            probs = [w / total_w for w in weights]

            selected = np.random.choice(top_candidates, size=pick_count, replace=False, p=probs)
            selected = sorted(selected.tolist())

            # 評估約束條件
            constraint_score = self._evaluate_constraints(selected, history)
            total = sum(final_scores[n] for n in selected) + constraint_score * 5

            if total > best_score:
                best_score = total
                best_combo = selected

        return {
            'numbers': best_combo,
            'confidence': 0.82,
            'method': 'enhanced_ensemble'
        }

    # ==================== 輔助方法 ====================
    def _calculate_gap(self, history: List[Dict], num: int) -> int:
        """計算號碼距離上次出現的間隔"""
        for i, h in enumerate(history):
            if num in h['numbers']:
                return i
        return len(history)

    def _calculate_avg_gap(self, history: List[Dict], num: int) -> float:
        """計算號碼的平均出現間隔"""
        appearances = [i for i, h in enumerate(history) if num in h['numbers']]
        if len(appearances) < 2:
            return 8.0  # 默認間隔

        gaps = [appearances[i+1] - appearances[i] for i in range(len(appearances)-1)]
        return np.mean(gaps)

    def _calculate_max_gap(self, history: List[Dict], num: int) -> int:
        """計算號碼的最大間隔"""
        appearances = [i for i, h in enumerate(history) if num in h['numbers']]
        if len(appearances) < 2:
            return 20

        gaps = [appearances[i+1] - appearances[i] for i in range(len(appearances)-1)]
        return max(gaps)

    def _calculate_base_scores(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """計算各號碼的基礎分數"""
        scores = {}

        for num in range(min_num, max_num + 1):
            score = 0

            # 頻率分數
            freq_50 = sum(1 for h in history[:50] if num in h['numbers'])
            freq_20 = sum(1 for h in history[:20] if num in h['numbers'])
            freq_10 = sum(1 for h in history[:10] if num in h['numbers'])

            score += freq_50 * 1
            score += freq_20 * 2
            score += freq_10 * 3

            # 間隔分數
            gap = self._calculate_gap(history, num)
            avg_gap = self._calculate_avg_gap(history, num)

            if avg_gap > 0:
                gap_ratio = gap / avg_gap
                if 0.8 <= gap_ratio <= 1.5:
                    score += 10

            scores[num] = score

        return scores


# 測試函數
def test_enhanced_predictor():
    """測試增強型預測器"""
    import sqlite3
    import json

    # 載入數據
    conn = sqlite3.connect('data/lottery.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, numbers, special, date
        FROM draws
        WHERE lottery_type = 'BIG_LOTTO'
        ORDER BY date DESC
        LIMIT 300
    """)
    rows = cursor.fetchall()
    conn.close()

    history = []
    for row in rows:
        draw, numbers_str, special, draw_date = row
        numbers = json.loads(numbers_str) if numbers_str.startswith('[') else [int(x) for x in numbers_str.split(',')]
        history.append({
            'draw_id': draw,
            'numbers': numbers,
            'special_number': special,
            'draw_date': draw_date
        })

    lottery_rules = {
        'pick_count': 6,
        'min_number': 1,
        'max_number': 49,
        'has_special': True
    }

    predictor = EnhancedPredictor()

    methods = [
        ('consecutive_friendly_predict', '連號友善'),
        ('cold_number_comeback_predict', '冷號回歸'),
        ('constrained_predict', '約束優化'),
        ('multi_window_fusion_predict', '多窗口融合'),
        ('coverage_optimized_predict', '覆蓋率優化'),
        ('enhanced_ensemble_predict', '綜合增強'),
    ]

    print('=' * 60)
    print('增強型預測器測試結果')
    print('=' * 60)

    for method_name, display_name in methods:
        method = getattr(predictor, method_name)
        result = method(history, lottery_rules)
        print(f'\n{display_name}:')
        print(f'  預測號碼: {result["numbers"]}')
        print(f'  信心度: {result["confidence"]:.1%}')


if __name__ == '__main__':
    test_enhanced_predictor()
