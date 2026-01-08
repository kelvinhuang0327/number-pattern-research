#!/usr/bin/env python3
"""
威力彩專用預測器 - 新方法實作
目標：提升單注效率，減少達成33%所需注數

新方法：
1. 約束滿足預測法 (Constraint Satisfaction)
2. 負向篩選法 (Negative Filtering)
3. 號碼聚合法 (Number Clustering)
4. 動態窗口法 (Adaptive Window)
5. 歷史模式匹配法 (Pattern Matching)
"""

import random
from collections import Counter, defaultdict
from typing import List, Dict, Set, Tuple
import math


class PowerLottoPredictor:
    """威力彩專用預測器"""

    def __init__(self):
        self.min_num = 1
        self.max_num = 38
        self.pick_count = 6
        self.special_min = 1
        self.special_max = 8

    # ============================================================
    # 方法1: 約束滿足預測法 (Constraint Satisfaction)
    # ============================================================
    def constraint_satisfaction_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        約束滿足預測法
        同時滿足多個統計約束，縮小號碼空間

        約束條件：
        1. 和值範圍 (歷史85%區間)
        2. 奇偶比例 (2:4 到 4:2)
        3. 區間分布 (每區至少1個)
        4. 連號約束 (最多1組連號)
        5. 尾數分布 (至少4種不同尾數)
        """
        numbers_history = [d['numbers'] for d in history if 'numbers' in d]

        if len(numbers_history) < 50:
            return self._fallback_predict(lottery_rules)

        # 1. 計算和值範圍約束
        sums = [sum(nums) for nums in numbers_history[:100]]
        sums.sort()
        sum_low = sums[int(len(sums) * 0.1)]   # 10th percentile
        sum_high = sums[int(len(sums) * 0.9)]  # 90th percentile

        # 2. 計算號碼權重 (基於頻率)
        freq = Counter()
        for nums in numbers_history[:100]:
            freq.update(nums)

        # 3. 區間定義 (38號分3區)
        zones = [(1, 13), (14, 25), (26, 38)]

        # 4. 生成候選組合並檢查約束
        best_combo = None
        best_score = -1

        for _ in range(5000):  # 嘗試5000次
            # 從每個區間選擇號碼，確保分布
            combo = []
            for zone_start, zone_end in zones:
                zone_nums = list(range(zone_start, zone_end + 1))
                # 按頻率加權選擇
                weights = [freq.get(n, 1) + 1 for n in zone_nums]
                if len(combo) < 2:
                    selected = random.choices(zone_nums, weights=weights, k=2)
                else:
                    selected = random.choices(zone_nums, weights=weights, k=2)
                combo.extend(selected)

            combo = list(set(combo))[:6]

            if len(combo) < 6:
                # 補足號碼
                remaining = [n for n in range(1, 39) if n not in combo]
                weights = [freq.get(n, 1) + 1 for n in remaining]
                extra = random.choices(remaining, weights=weights, k=6-len(combo))
                combo.extend(extra)

            combo = sorted(combo[:6])

            # 檢查約束
            score = self._check_constraints(combo, sum_low, sum_high, zones)

            if score > best_score:
                best_score = score
                best_combo = combo

        # 特別號預測
        special_freq = Counter()
        for d in history[:50]:
            if 'special' in d and d['special']:
                special_freq[d['special']] += 1

        if special_freq:
            special = special_freq.most_common(1)[0][0]
        else:
            special = random.randint(1, 8)

        return {
            'numbers': [int(n) for n in best_combo],
            'special': int(special),
            'confidence': min(0.7, best_score / 5),
            'method': 'constraint_satisfaction_predict',
            'constraints_score': best_score
        }

    def _check_constraints(self, combo: List[int], sum_low: int, sum_high: int, zones: List[Tuple]) -> int:
        """檢查組合滿足多少約束，返回分數"""
        score = 0

        # 1. 和值約束
        total = sum(combo)
        if sum_low <= total <= sum_high:
            score += 1

        # 2. 奇偶約束 (2:4 到 4:2)
        odd_count = sum(1 for n in combo if n % 2 == 1)
        if 2 <= odd_count <= 4:
            score += 1

        # 3. 區間分布約束 (每區至少1個)
        zone_counts = [0, 0, 0]
        for n in combo:
            if n <= 13:
                zone_counts[0] += 1
            elif n <= 25:
                zone_counts[1] += 1
            else:
                zone_counts[2] += 1
        if all(c >= 1 for c in zone_counts):
            score += 1

        # 4. 連號約束 (最多1組)
        consecutive_count = 0
        sorted_combo = sorted(combo)
        for i in range(len(sorted_combo) - 1):
            if sorted_combo[i+1] - sorted_combo[i] == 1:
                consecutive_count += 1
        if consecutive_count <= 1:
            score += 1

        # 5. 尾數分布約束 (至少4種不同尾數)
        tails = set(n % 10 for n in combo)
        if len(tails) >= 4:
            score += 1

        return score

    # ============================================================
    # 方法2: 負向篩選法 (Negative Filtering)
    # ============================================================
    def negative_filtering_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        負向篩選法
        先排除不太可能的號碼，再從剩餘號碼中選擇

        排除條件：
        1. 極度冷門號 (近50期未出現)
        2. 極度熱門號 (近10期出現3次以上，可能即將轉冷)
        3. 連續3期以上重複的號碼
        4. 上期全部號碼 (完全重複機率極低)
        """
        numbers_history = [d['numbers'] for d in history if 'numbers' in d]

        if len(numbers_history) < 50:
            return self._fallback_predict(lottery_rules)

        all_numbers = set(range(1, 39))
        excluded = set()

        # 1. 排除極度冷門號 (近50期未出現)
        recent_50 = Counter()
        for nums in numbers_history[:50]:
            recent_50.update(nums)

        for n in all_numbers:
            if recent_50[n] == 0:
                excluded.add(n)

        # 2. 排除過熱號 (近10期出現3次以上)
        recent_10 = Counter()
        for nums in numbers_history[:10]:
            recent_10.update(nums)

        for n, count in recent_10.items():
            if count >= 3:
                excluded.add(n)

        # 3. 排除連續重複號 (連續3期都出現的號碼)
        if len(numbers_history) >= 3:
            common_3 = set(numbers_history[0]) & set(numbers_history[1]) & set(numbers_history[2])
            excluded.update(common_3)

        # 4. 排除上期全部號碼
        if numbers_history:
            last_draw = set(numbers_history[0])
            # 只排除一半，保留可能重複的
            excluded.update(list(last_draw)[:3])

        # 從剩餘號碼中選擇
        remaining = all_numbers - excluded

        if len(remaining) < 6:
            remaining = all_numbers - set(list(excluded)[:len(excluded)//2])

        # 計算剩餘號碼的權重
        freq = Counter()
        for nums in numbers_history[:100]:
            freq.update(nums)

        remaining_list = list(remaining)
        weights = [freq.get(n, 1) + 1 for n in remaining_list]

        # 加權選擇
        selected = []
        for _ in range(6):
            if not remaining_list:
                break
            idx = random.choices(range(len(remaining_list)), weights=weights, k=1)[0]
            selected.append(remaining_list[idx])
            weights.pop(idx)
            remaining_list.pop(idx)

        # 補足號碼
        while len(selected) < 6:
            n = random.randint(1, 38)
            if n not in selected:
                selected.append(n)

        # 特別號
        special = self._predict_special(history)

        return {
            'numbers': sorted([int(n) for n in selected[:6]]),
            'special': int(special),
            'confidence': 0.6,
            'method': 'negative_filtering_predict',
            'excluded_count': len(excluded),
            'remaining_pool': len(remaining)
        }

    # ============================================================
    # 方法3: 號碼聚合法 (Number Clustering)
    # ============================================================
    def number_clustering_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        號碼聚合法
        分析歷史上常常一起出現的號碼組合
        """
        numbers_history = [d['numbers'] for d in history if 'numbers' in d]

        if len(numbers_history) < 100:
            return self._fallback_predict(lottery_rules)

        # 統計號碼對共現頻率
        pair_freq = Counter()
        for nums in numbers_history[:200]:
            nums = sorted(nums)
            for i in range(len(nums)):
                for j in range(i + 1, len(nums)):
                    pair_freq[(nums[i], nums[j])] += 1

        # 找出最常共現的號碼對
        top_pairs = pair_freq.most_common(20)

        # 從高頻對中選擇號碼
        selected = set()
        for (n1, n2), count in top_pairs:
            if len(selected) >= 6:
                break
            if n1 not in selected and len(selected) < 6:
                selected.add(n1)
            if n2 not in selected and len(selected) < 6:
                selected.add(n2)

        # 補足號碼
        freq = Counter()
        for nums in numbers_history[:50]:
            freq.update(nums)

        while len(selected) < 6:
            for n, _ in freq.most_common():
                if n not in selected:
                    selected.add(n)
                    break

        special = self._predict_special(history)

        return {
            'numbers': sorted([int(n) for n in list(selected)[:6]]),
            'special': int(special),
            'confidence': 0.55,
            'method': 'number_clustering_predict',
            'top_pairs': [list(p) for p, c in top_pairs[:5]]
        }

    # ============================================================
    # 方法4: 動態窗口法 (Adaptive Window)
    # ============================================================
    def adaptive_window_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        動態窗口法
        根據號碼的「週期性」動態選擇最佳窗口
        """
        numbers_history = [d['numbers'] for d in history if 'numbers' in d]

        if len(numbers_history) < 100:
            return self._fallback_predict(lottery_rules)

        # 為每個號碼計算最佳窗口
        number_scores = {}

        for num in range(1, 39):
            best_window = 50
            best_score = 0

            # 測試不同窗口
            for window in [30, 50, 80, 100, 150]:
                if window > len(numbers_history):
                    continue

                # 計算該窗口內的表現
                appearances = sum(1 for nums in numbers_history[:window] if num in nums)
                expected = window * 6 / 38

                # 計算近期趨勢
                recent = sum(1 for nums in numbers_history[:10] if num in nums)
                recent_expected = 10 * 6 / 38

                # 綜合評分：頻率穩定且近期活躍
                stability = 1 - abs(appearances - expected) / expected if expected > 0 else 0
                momentum = recent / recent_expected if recent_expected > 0 else 0

                score = stability * 0.4 + momentum * 0.6

                if score > best_score:
                    best_score = score
                    best_window = window

            number_scores[num] = {
                'score': best_score,
                'window': best_window
            }

        # 選擇得分最高的號碼
        ranked = sorted(number_scores.items(), key=lambda x: x[1]['score'], reverse=True)
        selected = [n for n, _ in ranked[:6]]

        special = self._predict_special(history)

        return {
            'numbers': sorted([int(n) for n in selected]),
            'special': int(special),
            'confidence': 0.6,
            'method': 'adaptive_window_predict',
            'top_scores': {n: round(s['score'], 3) for n, s in ranked[:6]}
        }

    # ============================================================
    # 方法5: 歷史模式匹配法 (Pattern Matching)
    # ============================================================
    def pattern_matching_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        歷史模式匹配法
        找出與當前狀態最相似的歷史時刻，參考其下一期結果
        """
        numbers_history = [d['numbers'] for d in history if 'numbers' in d]

        if len(numbers_history) < 100:
            return self._fallback_predict(lottery_rules)

        # 當前狀態特徵
        current_features = self._extract_features(numbers_history[:5])

        # 尋找歷史上最相似的時刻
        best_match_idx = None
        best_similarity = -1

        for i in range(10, len(numbers_history) - 5):
            historical_features = self._extract_features(numbers_history[i:i+5])
            similarity = self._calculate_similarity(current_features, historical_features)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match_idx = i

        # 使用匹配時刻的下一期作為參考
        if best_match_idx and best_match_idx > 0:
            reference = numbers_history[best_match_idx - 1]

            # 結合當前頻率
            freq = Counter()
            for nums in numbers_history[:50]:
                freq.update(nums)

            # 70% 參考歷史模式，30% 使用頻率
            selected = []
            for n in reference:
                if random.random() < 0.7:
                    selected.append(n)

            while len(selected) < 6:
                for n, _ in freq.most_common():
                    if n not in selected:
                        selected.append(n)
                        break

            selected = selected[:6]
        else:
            # 無匹配，使用頻率
            freq = Counter()
            for nums in numbers_history[:50]:
                freq.update(nums)
            selected = [n for n, _ in freq.most_common(6)]

        special = self._predict_special(history)

        return {
            'numbers': sorted([int(n) for n in selected]),
            'special': int(special),
            'confidence': 0.55,
            'method': 'pattern_matching_predict',
            'similarity': round(best_similarity, 3) if best_similarity > 0 else 0
        }

    def _extract_features(self, recent_draws: List[List[int]]) -> Dict:
        """提取特徵向量"""
        if not recent_draws:
            return {}

        all_nums = []
        for nums in recent_draws:
            all_nums.extend(nums)

        return {
            'mean': sum(all_nums) / len(all_nums) if all_nums else 0,
            'odd_ratio': sum(1 for n in all_nums if n % 2 == 1) / len(all_nums) if all_nums else 0,
            'high_ratio': sum(1 for n in all_nums if n > 19) / len(all_nums) if all_nums else 0,
            'unique_count': len(set(all_nums)),
        }

    def _calculate_similarity(self, f1: Dict, f2: Dict) -> float:
        """計算特徵相似度"""
        if not f1 or not f2:
            return 0

        diff = 0
        for key in f1:
            if key in f2:
                diff += abs(f1[key] - f2[key])

        return 1 / (1 + diff)

    # ============================================================
    # 方法6: 綜合優化法 (Hybrid Optimizer)
    # ============================================================
    def hybrid_optimizer_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        綜合優化法
        結合多種方法的優點，進行加權投票
        """
        # 執行所有方法
        results = []

        try:
            results.append(self.constraint_satisfaction_predict(history, lottery_rules))
        except:
            pass

        try:
            results.append(self.negative_filtering_predict(history, lottery_rules))
        except:
            pass

        try:
            results.append(self.number_clustering_predict(history, lottery_rules))
        except:
            pass

        try:
            results.append(self.adaptive_window_predict(history, lottery_rules))
        except:
            pass

        if not results:
            return self._fallback_predict(lottery_rules)

        # 加權投票
        number_votes = Counter()
        for r in results:
            confidence = r.get('confidence', 0.5)
            for n in r['numbers']:
                number_votes[n] += confidence

        # 選擇得票最高的6個
        selected = [n for n, _ in number_votes.most_common(6)]

        # 特別號投票
        special_votes = Counter()
        for r in results:
            if 'special' in r:
                special_votes[r['special']] += 1

        special = special_votes.most_common(1)[0][0] if special_votes else random.randint(1, 8)

        return {
            'numbers': sorted([int(n) for n in selected]),
            'special': int(special),
            'confidence': 0.65,
            'method': 'hybrid_optimizer_predict',
            'methods_used': len(results)
        }

    # ============================================================
    # 輔助方法
    # ============================================================
    def _predict_special(self, history: List[Dict]) -> int:
        """預測特別號"""
        special_freq = Counter()
        for d in history[:30]:
            if 'special' in d and d['special']:
                special_freq[d['special']] += 1

        if special_freq:
            # 選擇近期最熱門但未連續出現的
            last_special = history[0].get('special', 0) if history else 0
            for s, _ in special_freq.most_common():
                if s != last_special:
                    return s
            return special_freq.most_common(1)[0][0]

        return random.randint(1, 8)

    def _fallback_predict(self, lottery_rules: Dict) -> Dict:
        """備用預測"""
        numbers = random.sample(range(1, 39), 6)
        return {
            'numbers': sorted(numbers),
            'special': random.randint(1, 8),
            'confidence': 0.3,
            'method': 'fallback_random'
        }


# 創建全局實例
power_lotto_predictor = PowerLottoPredictor()
