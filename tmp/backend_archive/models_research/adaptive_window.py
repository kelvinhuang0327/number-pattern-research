#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自適應時間窗口計算器（Phase 2 優化）

核心功能：
- 根據號碼的波動性自動調整窗口大小
- 波動大的號碼使用小窗口（只看最近）
- 波動小的號碼使用大窗口（看更長歷史）
"""

import numpy as np
from typing import List, Dict


class AdaptiveWindowCalculator:
    """自適應窗口計算器"""

    def __init__(
        self,
        min_window: int = 20,
        medium_window: int = 50,
        max_window: int = 100
    ):
        """
        初始化自適應窗口計算器

        Args:
            min_window: 最小窗口大小（用於高波動號碼）
            medium_window: 中等窗口大小
            max_window: 最大窗口大小（用於低波動號碼）
        """
        self.min_window = min_window
        self.medium_window = medium_window
        self.max_window = max_window

    def calculate_optimal_window(
        self,
        number: int,
        history: List[Dict]
    ) -> int:
        """
        計算某個號碼的最佳窗口大小

        Args:
            number: 號碼
            history: 歷史開獎數據

        Returns:
            最佳窗口大小
        """
        # 收集該號碼出現的所有位置
        positions = []
        for i, draw in enumerate(history):
            if number in draw.get('numbers', []):
                positions.append(i)

        if len(positions) < 2:
            # 出現次數太少，使用預設中等窗口
            return self.medium_window

        # 計算相鄰出現的間隔
        intervals = []
        for i in range(len(positions) - 1):
            interval = positions[i + 1] - positions[i]
            intervals.append(interval)

        if not intervals:
            return self.medium_window

        # 計算統計量
        mean_interval = np.mean(intervals)
        std_interval = np.std(intervals)

        # 變異係數（CV）= 標準差 / 平均值
        # CV越大，波動性越大
        cv = std_interval / mean_interval if mean_interval > 0 else 0

        # 根據變異係數決定窗口大小
        if cv > 1.0:
            # 高波動性 → 小窗口（只看最近）
            return self.min_window
        elif cv > 0.5:
            # 中等波動性 → 中等窗口
            return self.medium_window
        else:
            # 低波動性 → 大窗口（看更長歷史）
            return self.max_window

    def calculate_all_windows(
        self,
        history: List[Dict],
        min_num: int = 1,
        max_num: int = 49
    ) -> Dict[int, int]:
        """
        計算所有號碼的最佳窗口

        Args:
            history: 歷史開獎數據
            min_num: 最小號碼
            max_num: 最大號碼

        Returns:
            各號碼的最佳窗口字典
        """
        windows = {}

        for num in range(min_num, max_num + 1):
            windows[num] = self.calculate_optimal_window(num, history)

        return windows

    def get_window_statistics(
        self,
        windows: Dict[int, int]
    ) -> Dict:
        """
        獲取窗口統計信息

        Args:
            windows: 號碼窗口字典

        Returns:
            統計信息
        """
        if not windows:
            return {}

        window_values = list(windows.values())

        return {
            'min': min(window_values),
            'max': max(window_values),
            'mean': np.mean(window_values),
            'median': np.median(window_values),
            'std': np.std(window_values),
            'small_window_count': sum(1 for w in window_values if w == self.min_window),
            'medium_window_count': sum(1 for w in window_values if w == self.medium_window),
            'large_window_count': sum(1 for w in window_values if w == self.max_window)
        }


# 測試代碼
if __name__ == '__main__':
    print("測試自適應時間窗口計算器...")

    # 創建模擬歷史數據
    import random

    history = []
    for i in range(100):
        numbers = sorted(random.sample(range(1, 50), 6))
        history.append({'numbers': numbers, 'draw': f'{i+1:05d}'})

    calculator = AdaptiveWindowCalculator(
        min_window=20,
        medium_window=50,
        max_window=100
    )

    # 計算幾個號碼的最佳窗口
    test_numbers = [1, 7, 13, 25, 42]

    print("\n各號碼的最佳窗口大小:")
    for num in test_numbers:
        window = calculator.calculate_optimal_window(num, history)
        print(f"  號碼 {num:2d}: {window} 期")

    # 計算所有號碼的窗口
    all_windows = calculator.calculate_all_windows(history, 1, 49)

    # 獲取統計信息
    stats = calculator.get_window_statistics(all_windows)

    print("\n窗口統計:")
    print(f"  平均窗口: {stats['mean']:.1f} 期")
    print(f"  最小窗口: {stats['min']} 期")
    print(f"  最大窗口: {stats['max']} 期")
    print(f"  小窗口(20期)數量: {stats['small_window_count']}")
    print(f"  中窗口(50期)數量: {stats['medium_window_count']}")
    print(f"  大窗口(100期)數量: {stats['large_window_count']}")

    print("\n✅ 自適應時間窗口計算器測試完成！")
