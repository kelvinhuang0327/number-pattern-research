#!/usr/bin/env python3
"""
負向篩選模組 (Negative Selection) - 大樂透版本
==============================================

核心理念：
不是預測「什麼會中」，而是排除「什麼不會中」。

排除規則：
1. 極熱號排除 - 近 10 期出現 3+ 次的號碼（可能「燒盡」）
2. 極冷號排除 - 近 100 期出現 < 3 次的號碼（太冷）
3. 結構約束 - 排除不符合歷史模式的組合
4. 模式排除 - 排除近期出現過的號碼模式

使用方式：
    from lottery_api.models.negative_selection_biglotto import NegativeSelectionPredictor

    predictor = NegativeSelectionPredictor()
    bets = predictor.predict(history, num_bets=4)
"""

import random
import numpy as np
from collections import Counter
from typing import List, Dict, Set, Tuple
from itertools import combinations


class NegativeSelectionPredictor:
    """負向篩選預測器"""

    def __init__(self, max_num: int = 49, pick_count: int = 6):
        self.max_num = max_num
        self.pick_count = pick_count

    def predict(self, history: List[Dict], num_bets: int = 4) -> List[List[int]]:
        """
        生成預測

        Args:
            history: 歷史開獎數據 (從舊到新排序)
            num_bets: 注數

        Returns:
            List[List[int]]: 預測號碼組合
        """
        # 1. 建立候選池 (排除極端號碼)
        candidate_pool = self._build_candidate_pool(history)

        # 2. 生成多組候選
        candidates = self._generate_candidates(candidate_pool, history, num_bets * 100)

        # 3. 結構過濾
        filtered = self._structural_filter(candidates)

        # 4. 選出最佳的 num_bets 組
        selected = self._select_best(filtered, history, num_bets)

        return selected

    def _build_candidate_pool(self, history: List[Dict]) -> Set[int]:
        """建立候選號碼池 - 排除極端號碼"""
        all_numbers = set(range(1, self.max_num + 1))

        # 計算近期頻率
        recent_freq = Counter()
        for d in history[-10:]:  # 近 10 期
            nums = d.get('numbers', [])
            if isinstance(nums, str):
                nums = eval(nums)
            recent_freq.update(nums)

        # 計算長期頻率
        long_freq = Counter()
        for d in history[-100:]:  # 近 100 期
            nums = d.get('numbers', [])
            if isinstance(nums, str):
                nums = eval(nums)
            long_freq.update(nums)

        # 排除極熱號 (近 10 期出現 3+ 次)
        exclude_hot = {n for n, c in recent_freq.items() if c >= 3}

        # 排除極冷號 (近 100 期出現 < 3 次)
        exclude_cold = {n for n in all_numbers if long_freq.get(n, 0) < 3}

        # 候選池 = 全部 - 極熱 - 極冷
        candidate_pool = all_numbers - exclude_hot - exclude_cold

        # 確保候選池足夠大
        if len(candidate_pool) < 20:
            # 如果太小，只排除極熱號
            candidate_pool = all_numbers - exclude_hot

        return candidate_pool

    def _generate_candidates(
        self,
        pool: Set[int],
        history: List[Dict],
        num_candidates: int
    ) -> List[List[int]]:
        """生成候選組合"""
        pool_list = list(pool)
        candidates = []

        # 計算號碼權重 (基於長期頻率的逆)
        long_freq = Counter()
        for d in history[-100:]:
            nums = d.get('numbers', [])
            if isinstance(nums, str):
                nums = eval(nums)
            long_freq.update(nums)

        # 權重：頻率低的號碼權重高
        avg_freq = sum(long_freq.values()) / len(long_freq) if long_freq else 1
        weights = {}
        for n in pool_list:
            freq = long_freq.get(n, 0)
            # 逆頻率權重，但不要太極端
            weights[n] = 1.0 + max(0, (avg_freq - freq) / avg_freq * 0.5)

        total_weight = sum(weights.values())
        probs = [weights[n] / total_weight for n in pool_list]

        # 生成候選
        for _ in range(num_candidates):
            try:
                selected = np.random.choice(
                    pool_list,
                    size=self.pick_count,
                    replace=False,
                    p=probs
                )
                candidates.append(sorted(selected.tolist()))
            except:
                # 如果加權選擇失敗，使用均勻分布
                selected = random.sample(pool_list, min(self.pick_count, len(pool_list)))
                candidates.append(sorted(selected))

        return candidates

    def _structural_filter(self, candidates: List[List[int]]) -> List[List[int]]:
        """結構過濾 - 排除不符合歷史模式的組合"""
        filtered = []

        for nums in candidates:
            # 1. 區間平衡檢查 (1-16, 17-33, 34-49)
            zones = [0, 0, 0]
            for n in nums:
                if n <= 16:
                    zones[0] += 1
                elif n <= 33:
                    zones[1] += 1
                else:
                    zones[2] += 1

            # 排除單區過於集中 (>= 5 個)
            if max(zones) >= 5:
                continue

            # 排除單區為空
            if min(zones) == 0:
                continue

            # 2. 奇偶平衡檢查
            odd_count = sum(1 for n in nums if n % 2 == 1)
            # 排除極端 (0:6 或 6:0 或 1:5 或 5:1)
            if odd_count <= 1 or odd_count >= 5:
                continue

            # 3. 和值範圍檢查
            total = sum(nums)
            # 大樂透合理和值範圍約 100-200
            if total < 100 or total > 200:
                continue

            # 4. 連號檢查 (排除 4+ 連號)
            sorted_nums = sorted(nums)
            max_consecutive = 1
            current_consecutive = 1
            for i in range(1, len(sorted_nums)):
                if sorted_nums[i] - sorted_nums[i-1] == 1:
                    current_consecutive += 1
                    max_consecutive = max(max_consecutive, current_consecutive)
                else:
                    current_consecutive = 1

            if max_consecutive >= 4:
                continue

            filtered.append(nums)

        # 如果過濾後太少，放寬條件
        if len(filtered) < 10:
            return candidates[:100]

        return filtered

    def _select_best(
        self,
        candidates: List[List[int]],
        history: List[Dict],
        num_bets: int
    ) -> List[List[int]]:
        """選出最佳的 num_bets 組"""
        if len(candidates) <= num_bets:
            return candidates

        # 計算每組的「多樣性分數」
        # 目標：選出的組合之間要有足夠差異

        # 先選第一組 (隨機)
        selected = [candidates[0]]

        for _ in range(num_bets - 1):
            best_candidate = None
            best_diversity = -1

            for cand in candidates:
                if cand in selected:
                    continue

                # 計算與已選組合的最小差異
                min_diff = min(
                    len(set(cand) - set(s))
                    for s in selected
                )

                if min_diff > best_diversity:
                    best_diversity = min_diff
                    best_candidate = cand

            if best_candidate:
                selected.append(best_candidate)

        return selected


class EnhancedNegativeSelection:
    """增強版負向篩選 - 結合 Cluster Pivot"""

    def __init__(self, max_num: int = 49, pick_count: int = 6):
        self.max_num = max_num
        self.pick_count = pick_count
        self.base_predictor = NegativeSelectionPredictor(max_num, pick_count)

    def predict(self, history: List[Dict], num_bets: int = 4) -> List[List[int]]:
        """
        結合負向篩選與共現分析

        策略：
        - 前 ceil(num_bets/2) 注：使用負向篩選
        - 後 floor(num_bets/2) 注：使用共現聚類
        """
        neg_bets = (num_bets + 1) // 2
        cluster_bets = num_bets - neg_bets

        # 負向篩選
        neg_predictions = self.base_predictor.predict(history, neg_bets)

        # 共現聚類
        cluster_predictions = self._cluster_based_predict(history, cluster_bets)

        # 合併，去重
        all_predictions = neg_predictions.copy()
        for pred in cluster_predictions:
            if pred not in all_predictions:
                all_predictions.append(pred)

        return all_predictions[:num_bets]

    def _cluster_based_predict(self, history: List[Dict], num_bets: int) -> List[List[int]]:
        """基於共現的預測"""
        # 建立共現矩陣
        cooccur = Counter()
        for d in history[-100:]:
            nums = d.get('numbers', [])
            if isinstance(nums, str):
                nums = eval(nums)
            for pair in combinations(sorted(nums), 2):
                cooccur[pair] += 1

        # 找聚類中心
        num_scores = Counter()
        for (a, b), count in cooccur.items():
            num_scores[a] += count
            num_scores[b] += count

        centers = [n for n, _ in num_scores.most_common(num_bets)]

        # 從每個中心擴展
        predictions = []
        used = set()

        for anchor in centers:
            # 找與錨點共現最多的號碼
            candidates = Counter()
            for (a, b), count in cooccur.items():
                if a == anchor:
                    candidates[b] += count
                elif b == anchor:
                    candidates[a] += count

            # 選擇
            selected = [anchor]
            for num, _ in candidates.most_common(self.pick_count - 1):
                if num not in selected:
                    selected.append(num)
                if len(selected) >= self.pick_count:
                    break

            # 補充
            while len(selected) < self.pick_count:
                for n in range(1, self.max_num + 1):
                    if n not in selected:
                        selected.append(n)
                        break

            pred = sorted(selected[:self.pick_count])
            if tuple(pred) not in used:
                predictions.append(pred)
                used.add(tuple(pred))

        return predictions[:num_bets]


# ============================================================
# 便捷函數
# ============================================================

def negative_selection_predict(history: List[Dict], rules: Dict, num_bets: int = 4) -> List[List[int]]:
    """便捷函數"""
    max_num = rules.get('maxNumber', 49)
    predictor = NegativeSelectionPredictor(max_num=max_num)
    return predictor.predict(history, num_bets)


def enhanced_negative_predict(history: List[Dict], rules: Dict, num_bets: int = 4) -> List[List[int]]:
    """增強版便捷函數"""
    max_num = rules.get('maxNumber', 49)
    predictor = EnhancedNegativeSelection(max_num=max_num)
    return predictor.predict(history, num_bets)


# ============================================================
# 測試
# ============================================================

if __name__ == '__main__':
    import sys
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)

    from lottery_api.utils.benchmark_framework import quick_benchmark

    # 測試負向篩選
    def negative_strategy(history, rules):
        return negative_selection_predict(history, rules, num_bets=4)

    result = quick_benchmark(
        strategy_fn=negative_strategy,
        strategy_name='Negative_Selection_4bet',
        lottery_type='BIG_LOTTO',
        num_bets=4
    )

    # 測試增強版
    def enhanced_strategy(history, rules):
        return enhanced_negative_predict(history, rules, num_bets=4)

    result2 = quick_benchmark(
        strategy_fn=enhanced_strategy,
        strategy_name='Enhanced_Negative_4bet',
        lottery_type='BIG_LOTTO',
        num_bets=4
    )
