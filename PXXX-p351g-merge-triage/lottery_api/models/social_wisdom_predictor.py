#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
社群智慧預測器 (Social Wisdom Predictor)

核心概念：
- 避開大眾最常選擇的號碼
- 理論：中獎機率相同，但獨得獎金機會更高
- 利用人性偏好：生日號碼(1-31)、幸運數字(7,8,9)

策略：
1. 識別「熱門號碼」（大眾喜愛）
2. 降低這些號碼的權重
3. 提升「冷門號碼」的選擇機率
4. 目標：中獎時獨得或少數人分獎金
"""

import numpy as np
from typing import List, Set, Dict
from collections import Counter


class SocialWisdomPredictor:
    """社群智慧預測器"""

    def __init__(self, max_num: int = 49):
        """
        初始化預測器

        Args:
            max_num: 最大號碼 (大樂透是49)
        """
        self.max_num = max_num

        # 定義熱門號碼（基於人性偏好的假設）
        self.popular_numbers = self._define_popular_numbers()

    def _define_popular_numbers(self) -> Set[int]:
        """
        定義熱門號碼（大眾常選）

        Returns:
            熱門號碼集合
        """
        popular = set()

        # 1. 生日號碼 (1-31) - 最多人選
        popular.update(range(1, 32))

        # 2. 幸運數字
        lucky_numbers = [7, 8, 9, 18, 28, 38, 48, 6, 16, 26, 36, 46]
        popular.update(lucky_numbers)

        # 3. 整十數字 (10, 20, 30, 40)
        popular.update([10, 20, 30, 40])

        # 4. 連號組合的起點 (1, 2, 3...)
        popular.update(range(1, 6))

        # 確保在合法範圍內
        popular = {num for num in popular if 1 <= num <= self.max_num}

        return popular

    def _calculate_unpopular_scores(self) -> np.ndarray:
        """
        計算每個號碼的「非熱門分數」

        Returns:
            非熱門分數陣列 (索引0對應號碼1)
        """
        scores = np.ones(self.max_num)

        for num in range(1, self.max_num + 1):
            # 基礎分數
            base_score = 1.0

            # 生日號碼懲罰（1-31最嚴重）
            if 1 <= num <= 31:
                # 1號最熱門（生日、心理偏好）
                if num == 1:
                    base_score *= 0.3
                # 7號次熱門（幸運數字）
                elif num == 7:
                    base_score *= 0.35
                # 8號（發財數字）
                elif num == 8:
                    base_score *= 0.35
                # 9號（長久）
                elif num == 9:
                    base_score *= 0.4
                # 其他1-31號碼
                else:
                    base_score *= 0.5
            else:
                # 32-49是冷門號碼，給予更高分數
                base_score *= 1.5

            # 幸運數字額外懲罰
            if num in [6, 16, 18, 26, 28, 36, 38, 46, 48]:
                base_score *= 0.7

            # 整十數字懲罰
            if num in [10, 20, 30, 40]:
                base_score *= 0.6

            # 特別獎勵：42-49 (極少人選)
            if 42 <= num <= 49:
                base_score *= 1.8

            scores[num - 1] = base_score

        # 歸一化
        scores /= scores.sum()

        return scores

    def predict(self, history: List[Dict], pick_count: int = 6) -> List[int]:
        """
        預測號碼（避開熱門號碼）

        Args:
            history: 歷史開獎數據（本方法主要不依賴歷史，但可用於微調）
            pick_count: 要選幾個號碼

        Returns:
            預測的號碼列表
        """
        # 獲取非熱門分數
        unpopular_scores = self._calculate_unpopular_scores()

        # 可選：結合歷史頻率（輕微調整）
        if history and len(history) > 0:
            historical_freq = self._calculate_historical_frequency(history)
            # 混合：70% 非熱門分數 + 30% 歷史頻率
            combined_scores = 0.7 * unpopular_scores + 0.3 * historical_freq
        else:
            combined_scores = unpopular_scores

        # 選擇分數最高的號碼
        top_indices = np.argsort(combined_scores)[-pick_count:][::-1]
        predicted_numbers = sorted([int(idx + 1) for idx in top_indices])

        return predicted_numbers

    def _calculate_historical_frequency(self, history: List[Dict]) -> np.ndarray:
        """
        計算歷史頻率（歸一化）

        Args:
            history: 歷史開獎數據

        Returns:
            頻率陣列
        """
        freq = np.zeros(self.max_num)

        for draw in history[:50]:  # 只看最近50期
            numbers = draw.get('numbers', [])
            for num in numbers:
                if 1 <= num <= self.max_num:
                    freq[num - 1] += 1

        # 歸一化
        if freq.sum() > 0:
            freq /= freq.sum()
        else:
            freq = np.ones(self.max_num) / self.max_num

        return freq

    def predict_with_balance(
        self,
        history: List[Dict],
        pick_count: int = 6,
        cold_ratio: float = 0.67
    ) -> List[int]:
        """
        平衡策略：混合冷門號碼和部分熱門號碼

        Args:
            history: 歷史數據
            pick_count: 選號數量
            cold_ratio: 冷門號碼比例 (0.67 = 4個冷門 + 2個熱門)

        Returns:
            預測號碼
        """
        cold_count = int(pick_count * cold_ratio)
        hot_count = pick_count - cold_count

        # 獲取非熱門分數
        unpopular_scores = self._calculate_unpopular_scores()

        # 選擇冷門號碼
        cold_indices = np.argsort(unpopular_scores)[-cold_count:]
        cold_numbers = [int(idx + 1) for idx in cold_indices]

        # 選擇熱門號碼（從歷史頻率中選）
        if history and len(history) > 0:
            historical_freq = self._calculate_historical_frequency(history)
            # 排除已選的冷門號碼
            for num in cold_numbers:
                historical_freq[num - 1] = 0
            hot_indices = np.argsort(historical_freq)[-hot_count:]
            hot_numbers = [int(idx + 1) for idx in hot_indices]
        else:
            # 如果沒有歷史數據，隨機選擇
            remaining = [n for n in range(1, self.max_num + 1) if n not in cold_numbers]
            hot_numbers = np.random.choice(remaining, size=hot_count, replace=False).tolist()

        # 合併並排序
        predicted_numbers = sorted(cold_numbers + hot_numbers)

        return predicted_numbers

    def generate_8_bets(
        self,
        history: List[Dict],
        pick_count: int = 6
    ) -> List[Dict]:
        """
        生成8注號碼（多樣化策略）

        策略分配：
        - 4注：激進冷門 (80-100%冷門號碼)
        - 2注：平衡策略 (60-70%冷門)
        - 2注：保守策略 (40-50%冷門)

        Returns:
            8注號碼及其策略資訊
        """
        bets = []

        # 獲取基礎分數
        unpopular_scores = self._calculate_unpopular_scores()
        historical_freq = self._calculate_historical_frequency(history) if history else None

        # 策略1：4注激進冷門
        for i in range(4):
            # 使用高權重的冷門分數
            noise = np.random.normal(0, 0.1, self.max_num)  # 添加隨機性避免重複
            scores = unpopular_scores + noise * (i + 1)
            scores = np.clip(scores, 0, None)
            scores /= scores.sum()

            top_indices = np.argsort(scores)[-pick_count:]
            numbers = sorted([int(idx + 1) for idx in top_indices])

            bets.append({
                'numbers': numbers,
                'strategy': '激進冷門',
                'cold_ratio': 0.9,
                'score': scores[top_indices].mean()
            })

        # 策略2：2注平衡
        for i in range(2):
            if historical_freq is not None:
                scores = 0.65 * unpopular_scores + 0.35 * historical_freq
            else:
                scores = unpopular_scores

            noise = np.random.normal(0, 0.15, self.max_num)
            scores = scores + noise * (i + 1)
            scores = np.clip(scores, 0, None)
            scores /= scores.sum()

            top_indices = np.argsort(scores)[-pick_count:]
            numbers = sorted([int(idx + 1) for idx in top_indices])

            bets.append({
                'numbers': numbers,
                'strategy': '平衡策略',
                'cold_ratio': 0.65,
                'score': scores[top_indices].mean()
            })

        # 策略3：2注保守（更多熱門號碼）
        for i in range(2):
            if historical_freq is not None:
                scores = 0.45 * unpopular_scores + 0.55 * historical_freq
            else:
                scores = np.ones(self.max_num) / self.max_num

            noise = np.random.normal(0, 0.2, self.max_num)
            scores = scores + noise * (i + 1)
            scores = np.clip(scores, 0, None)
            scores /= scores.sum()

            top_indices = np.argsort(scores)[-pick_count:]
            numbers = sorted([int(idx + 1) for idx in top_indices])

            bets.append({
                'numbers': numbers,
                'strategy': '保守策略',
                'cold_ratio': 0.45,
                'score': scores[top_indices].mean()
            })

        return bets

    def analyze_popularity(self, numbers: List[int]) -> Dict:
        """
        分析一組號碼的熱門程度

        Args:
            numbers: 要分析的號碼

        Returns:
            分析結果
        """
        popular_count = sum(1 for num in numbers if num in self.popular_numbers)
        unpopular_count = len(numbers) - popular_count

        # 計算平均分數
        unpopular_scores = self._calculate_unpopular_scores()
        avg_score = sum(unpopular_scores[num - 1] for num in numbers) / len(numbers)

        # 分類號碼
        birthday_nums = [num for num in numbers if 1 <= num <= 31]
        lucky_nums = [num for num in numbers if num in [6, 7, 8, 9, 16, 18, 26, 28, 36, 38, 46, 48]]
        high_nums = [num for num in numbers if num >= 40]

        return {
            'popular_count': popular_count,
            'unpopular_count': unpopular_count,
            'popularity_ratio': popular_count / len(numbers),
            'avg_unpopular_score': avg_score,
            'birthday_numbers': birthday_nums,
            'lucky_numbers': lucky_nums,
            'high_numbers': high_nums,
            'uniqueness_grade': self._grade_uniqueness(avg_score)
        }

    def _grade_uniqueness(self, score: float) -> str:
        """評級獨特性"""
        if score > 0.025:
            return 'S級 (極度獨特，幾乎無人選)'
        elif score > 0.022:
            return 'A級 (非常獨特)'
        elif score > 0.020:
            return 'B級 (獨特)'
        elif score > 0.018:
            return 'C級 (略微獨特)'
        else:
            return 'D級 (普通/熱門)'


# 測試函數
if __name__ == '__main__':
    predictor = SocialWisdomPredictor(max_num=49)

    print('=' * 100)
    print('🧠 社群智慧預測器測試')
    print('=' * 100)
    print()

    # 測試基本預測
    print('📊 策略1：激進冷門號碼')
    print('-' * 100)
    cold_numbers = predictor.predict([], pick_count=6)
    print(f'預測號碼: {cold_numbers}')

    analysis = predictor.analyze_popularity(cold_numbers)
    print(f'熱門號碼數量: {analysis["popular_count"]}/6')
    print(f'冷門號碼數量: {analysis["unpopular_count"]}/6')
    print(f'獨特性評級: {analysis["uniqueness_grade"]}')
    print()

    # 測試平衡策略
    print('📊 策略2：平衡策略 (67%冷門)')
    print('-' * 100)
    balanced_numbers = predictor.predict_with_balance([], pick_count=6, cold_ratio=0.67)
    print(f'預測號碼: {balanced_numbers}')

    analysis2 = predictor.analyze_popularity(balanced_numbers)
    print(f'熱門號碼數量: {analysis2["popular_count"]}/6')
    print(f'冷門號碼數量: {analysis2["unpopular_count"]}/6')
    print(f'獨特性評級: {analysis2["uniqueness_grade"]}')
    print()

    # 分析熱門組合
    print('=' * 100)
    print('🔥 熱門組合分析（大眾最愛）')
    print('=' * 100)
    print()

    popular_combo = [1, 7, 8, 9, 18, 28]
    print(f'組合: {popular_combo}')
    analysis3 = predictor.analyze_popularity(popular_combo)
    print(f'熱門度: {analysis3["popularity_ratio"]*100:.0f}%')
    print(f'獨特性評級: {analysis3["uniqueness_grade"]}')
    print(f'生日號碼: {analysis3["birthday_numbers"]}')
    print(f'幸運數字: {analysis3["lucky_numbers"]}')
    print()

    print('✅ 測試完成')
