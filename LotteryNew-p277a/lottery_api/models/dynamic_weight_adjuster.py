#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
動態權重調整器（Phase 2 優化）

核心功能：
- 追蹤每個預測方法的歷史表現
- 根據最近表現動態調整權重
- 表現好的方法獲得更高權重
- 表現差的方法自動降權
"""

import numpy as np
from typing import Dict, List, Optional
from collections import deque, defaultdict
import json
import os


class DynamicWeightAdjuster:
    """動態權重調整器"""

    def __init__(self, history_size: int = 20, persistence_file: Optional[str] = None):
        """
        初始化動態權重調整器

        Args:
            history_size: 保留最近多少次預測記錄
            persistence_file: 權重持久化文件路徑（可選）
        """
        self.history_size = history_size
        self.persistence_file = persistence_file

        # 每個方法的表現歷史（使用雙端隊列，自動限制大小）
        self.performance_history = defaultdict(lambda: deque(maxlen=history_size))

        # 當前權重
        self.current_weights = {}

        # 預設權重（基於回測結果初始化）
        # 表現優於隨機(0.9474)的方法獲得較高權重
        self.default_weights = {
            # 優秀方法 (平均命中 > 1.0)
            'dynamic_ensemble': 0.18,   # 1.11 avg hits (+17%)
            'clustering': 0.16,         # 1.09 avg hits (+15%)
            'bayesian': 0.16,           # 1.09 avg hits (+15%)
            'trend': 0.12,              # 1.03 avg hits (+8.7%)
            'statistical': 0.10,        # 1.00 avg hits (+5.5%)
            'markov': 0.08,             # 需要驗證修復後的表現

            # 中等方法 (接近隨機)
            'random_forest': 0.05,      # 0.96 avg hits
            'monte_carlo': 0.05,        # 0.95 avg hits
            'entropy': 0.05,            # 0.95 avg hits
            'zone_balance': 0.03,       # 0.94 avg hits

            # 低權重方法 (低於隨機)
            'hot_cold': 0.01,           # 0.91 avg hits
            'ensemble': 0.005,          # 0.88 avg hits (原始版本)
            'frequency': 0.005,         # 0.88 avg hits
            'deviation': 0.00,          # 0.86 avg hits (最差，移除)
        }

        # 如果有持久化文件，嘗試載入
        if persistence_file and os.path.exists(persistence_file):
            self._load_state()
        else:
            self.current_weights = self.default_weights.copy()

    def update_performance(
        self,
        method: str,
        actual_numbers: List[int],
        predicted_numbers: List[int]
    ):
        """
        更新方法的表現記錄

        Args:
            method: 預測方法名稱
            actual_numbers: 實際開獎號碼
            predicted_numbers: 預測號碼
        """
        # 計算匹配數
        matches = len(set(actual_numbers) & set(predicted_numbers))

        # 添加到歷史記錄
        self.performance_history[method].append(matches)

        # 更新權重
        self.current_weights = self.calculate_dynamic_weights()

        # 持久化
        if self.persistence_file:
            self._save_state()

    def calculate_dynamic_weights(self) -> Dict[str, float]:
        """
        計算動態權重

        Returns:
            各方法的權重字典
        """
        weights = {}

        for method in self.default_weights.keys():
            history = self.performance_history.get(method, [])

            if not history:
                # 沒有歷史數據，使用預設權重
                weights[method] = self.default_weights[method]
            else:
                # 計算平均匹配數
                avg_matches = np.mean(history)

                # 計算標準差（穩定性）
                std_matches = np.std(history) if len(history) > 1 else 0

                # 計算趨勢（最近5次 vs 前面的）
                if len(history) >= 10:
                    recent = np.mean(list(history)[-5:])
                    previous = np.mean(list(history)[:-5])
                    trend = (recent - previous) / (previous + 1e-10)
                else:
                    trend = 0

                # 綜合評分
                # 1. 平均表現（60%）- 匹配越多越好
                performance_score = avg_matches / 6.0  # 歸一化到 0-1

                # 2. 穩定性（20%）- 標準差越小越好
                stability_score = max(0, 1 - std_matches / 3.0)

                # 3. 趨勢（20%）- 近期上升趨勢加分
                trend_score = max(0, min(1, 0.5 + trend))

                # 綜合評分
                combined_score = (
                    performance_score * 0.6 +
                    stability_score * 0.2 +
                    trend_score * 0.2
                )

                # 轉換為權重（基礎權重 + 浮動）
                # 權重範圍：0.05 ~ 0.40
                weights[method] = max(0.05, min(0.40, combined_score * 0.5))

        # 正規化（確保總和為1）
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        else:
            weights = self.default_weights.copy()

        return weights

    def get_weights(self) -> Dict[str, float]:
        """
        獲取當前權重

        Returns:
            當前權重字典
        """
        return self.current_weights.copy()

    def get_performance_summary(self) -> Dict[str, Dict]:
        """
        獲取表現摘要

        Returns:
            各方法的表現摘要
        """
        summary = {}

        for method, history in self.performance_history.items():
            if history:
                summary[method] = {
                    'avg_matches': float(np.mean(history)),
                    'std_matches': float(np.std(history)) if len(history) > 1 else 0,
                    'total_tests': len(history),
                    'current_weight': self.current_weights.get(method, 0),
                    'recent_5': list(history)[-5:] if len(history) >= 5 else list(history)
                }
            else:
                summary[method] = {
                    'avg_matches': 0,
                    'std_matches': 0,
                    'total_tests': 0,
                    'current_weight': self.default_weights.get(method, 0),
                    'recent_5': []
                }

        return summary

    def reset(self):
        """重置所有歷史記錄和權重"""
        self.performance_history.clear()
        self.current_weights = self.default_weights.copy()

        if self.persistence_file and os.path.exists(self.persistence_file):
            os.remove(self.persistence_file)

    def _save_state(self):
        """保存狀態到文件"""
        if not self.persistence_file:
            return

        state = {
            'current_weights': self.current_weights,
            'performance_history': {
                method: list(history)
                for method, history in self.performance_history.items()
            }
        }

        try:
            os.makedirs(os.path.dirname(self.persistence_file), exist_ok=True)
            with open(self.persistence_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存權重狀態失敗: {e}")

    def _load_state(self):
        """從文件載入狀態"""
        if not self.persistence_file or not os.path.exists(self.persistence_file):
            return

        try:
            with open(self.persistence_file, 'r', encoding='utf-8') as f:
                state = json.load(f)

            self.current_weights = state.get('current_weights', self.default_weights.copy())

            history_data = state.get('performance_history', {})
            for method, history in history_data.items():
                self.performance_history[method] = deque(history, maxlen=self.history_size)

        except Exception as e:
            print(f"⚠️ 載入權重狀態失敗: {e}")
            self.current_weights = self.default_weights.copy()


# 測試代碼
if __name__ == '__main__':
    print("測試動態權重調整器...")

    adjuster = DynamicWeightAdjuster(history_size=20)

    # 模擬幾次預測結果
    test_data = [
        ('entropy', [1, 2, 3, 4, 5, 6], [1, 2, 7, 8, 9, 10]),  # 2個匹配
        ('entropy', [1, 2, 3, 4, 5, 6], [1, 2, 3, 8, 9, 10]),  # 3個匹配
        ('deviation', [1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]),  # 0個匹配
        ('deviation', [1, 2, 3, 4, 5, 6], [1, 8, 9, 10, 11, 12]),  # 1個匹配
    ]

    print("\n模擬預測結果...")
    for method, actual, predicted in test_data:
        matches = len(set(actual) & set(predicted))
        adjuster.update_performance(method, actual, predicted)
        print(f"  {method}: 匹配 {matches} 個")

    print("\n當前權重:")
    for method, weight in adjuster.get_weights().items():
        print(f"  {method}: {weight:.3f}")

    print("\n表現摘要:")
    summary = adjuster.get_performance_summary()
    for method, info in summary.items():
        print(f"  {method}:")
        print(f"    平均匹配: {info['avg_matches']:.2f}")
        print(f"    當前權重: {info['current_weight']:.3f}")

    print("\n✅ 動態權重調整器測試完成！")
