#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
異常檢測預測器 (Anomaly Detection Predictor)

核心概念：
- 訓練模型識別「正常」的號碼組合
- 預測「異常」組合
- 反向思維：大家都預測正常→異常可能開出
- 使用 Isolation Forest 檢測異常

策略：
1. 從歷史數據學習「正常」組合的特徵
2. 生成候選組合並評分
3. 選擇最「異常」的組合作為預測
"""

import numpy as np
from typing import List, Dict, Tuple
from collections import Counter
import random

# 嘗試導入 sklearn，如果沒有則使用簡化版
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print('⚠️  sklearn 未安裝，將使用簡化版異常檢測')


class AnomalyPredictor:
    """異常檢測預測器"""

    def __init__(self, max_num: int = 49, contamination: float = 0.1):
        """
        初始化預測器

        Args:
            max_num: 最大號碼
            contamination: 異常比例 (0.1 = 10%被視為異常)
        """
        self.max_num = max_num
        self.contamination = contamination
        self.model = None
        self.scaler = None
        self.is_trained = False

    def _extract_features(self, numbers: List[int]) -> np.ndarray:
        """
        從號碼組合中提取特徵

        Args:
            numbers: 號碼列表

        Returns:
            特徵向量 (12維)
        """
        if not numbers:
            return np.zeros(12)

        numbers = sorted(numbers)

        # 特徵1: 和值
        sum_value = sum(numbers)

        # 特徵2: 奇數個數
        odd_count = sum(1 for n in numbers if n % 2 == 1)

        # 特徵3: 大號個數 (>24)
        high_count = sum(1 for n in numbers if n > 24)

        # 特徵4-5: 最小值和最大值
        min_val = min(numbers)
        max_val = max(numbers)

        # 特徵6: 間隔變異數
        gaps = [numbers[i+1] - numbers[i] for i in range(len(numbers)-1)]
        gap_variance = np.var(gaps) if len(gaps) > 0 else 0

        # 特徵7: 連號數量
        consecutive_count = sum(1 for i in range(len(numbers)-1) if numbers[i+1] - numbers[i] == 1)

        # 特徵8-12: 五區分佈 (1-10, 11-20, 21-30, 31-40, 41-49)
        zone_counts = [0] * 5
        for num in numbers:
            if 1 <= num <= 10:
                zone_counts[0] += 1
            elif 11 <= num <= 20:
                zone_counts[1] += 1
            elif 21 <= num <= 30:
                zone_counts[2] += 1
            elif 31 <= num <= 40:
                zone_counts[3] += 1
            elif 41 <= num <= 49:
                zone_counts[4] += 1

        features = np.array([
            sum_value,
            odd_count,
            high_count,
            min_val,
            max_val,
            gap_variance,
            consecutive_count,
            *zone_counts
        ])

        return features

    def fit(self, history: List[Dict]) -> None:
        """
        訓練異常檢測模型

        Args:
            history: 歷史開獎數據
        """
        if not history:
            print('⚠️  無歷史數據，無法訓練')
            return

        # 提取所有歷史組合的特徵
        X = []
        for draw in history:
            numbers = draw.get('numbers', [])
            if numbers:
                features = self._extract_features(numbers)
                X.append(features)

        X = np.array(X)

        if len(X) == 0:
            print('⚠️  無法提取特徵')
            return

        if SKLEARN_AVAILABLE:
            # 使用 Isolation Forest
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)

            self.model = IsolationForest(
                contamination=self.contamination,
                random_state=42,
                n_estimators=100
            )
            self.model.fit(X_scaled)
            self.is_trained = True
        else:
            # 簡化版：記錄歷史特徵的統計資訊
            self.mean_features = np.mean(X, axis=0)
            self.std_features = np.std(X, axis=0)
            # 保存歷史特徵矩陣（用於馬氏距離計算）
            self.historical_features = X
            self.is_trained = True

    def _calculate_anomaly_score_sklearn(self, numbers: List[int]) -> float:
        """
        使用 sklearn 計算異常分數

        Args:
            numbers: 號碼組合

        Returns:
            異常分數（越低越異常）
        """
        features = self._extract_features(numbers).reshape(1, -1)
        features_scaled = self.scaler.transform(features)
        score = self.model.score_samples(features_scaled)[0]
        return score

    def _calculate_anomaly_score_simple(self, numbers: List[int]) -> float:
        """
        簡化版異常分數計算（優化版 - 使用馬氏距離）

        改進：
        - 使用馬氏距離（Mahalanobis distance）而非簡單歐氏距離
        - 考慮特徵之間的相關性
        - 更準確地衡量多維異常

        Args:
            numbers: 號碼組合

        Returns:
            異常分數（越高越異常）
        """
        features = self._extract_features(numbers)

        # 計算與歷史均值的距離
        if not hasattr(self, 'mean_features'):
            return 0.0

        if not hasattr(self, 'historical_features'):
            # 如果沒有歷史特徵矩陣，回退到簡單距離
            distances = np.abs(features - self.mean_features) / (self.std_features + 1e-10)
            return np.mean(distances)

        try:
            # 使用馬氏距離（考慮特徵間的相關性）
            diff = features - self.mean_features

            # 計算協方差矩陣
            cov_matrix = np.cov(self.historical_features.T)

            # 添加正則化以避免奇異矩陣
            cov_matrix += np.eye(cov_matrix.shape[0]) * 1e-6

            # 計算協方差矩陣的逆（使用偽逆以增強穩定性）
            inv_cov = np.linalg.pinv(cov_matrix)

            # 馬氏距離
            mahalanobis_dist = np.sqrt(diff @ inv_cov @ diff.T)

            return float(mahalanobis_dist)

        except Exception as e:
            # 如果計算失敗，回退到簡單距離
            distances = np.abs(features - self.mean_features) / (self.std_features + 1e-10)
            return np.mean(distances)

    def predict_anomaly(
        self,
        history: List[Dict],
        pick_count: int = 6,
        n_candidates: int = 10000,
        top_k: int = 1
    ) -> List[Tuple[List[int], float]]:
        """
        預測異常組合

        Args:
            history: 歷史數據（用於訓練）
            pick_count: 選號數量
            n_candidates: 候選組合數量
            top_k: 返回前k個最異常的組合

        Returns:
            [(號碼, 異常分數), ...] 列表
        """
        # 如果未訓練，先訓練
        if not self.is_trained:
            self.fit(history)

        if not self.is_trained:
            # 訓練失敗，返回隨機組合
            random_numbers = sorted(random.sample(range(1, self.max_num + 1), pick_count))
            return [(random_numbers, 0.0)]

        # 生成候選組合
        candidates = []

        for _ in range(n_candidates):
            numbers = sorted(random.sample(range(1, self.max_num + 1), pick_count))

            # 計算異常分數
            if SKLEARN_AVAILABLE:
                score = self._calculate_anomaly_score_sklearn(numbers)
                # sklearn 的 score 越低越異常，我們取負值
                anomaly_score = -score
            else:
                anomaly_score = self._calculate_anomaly_score_simple(numbers)

            candidates.append((numbers, anomaly_score))

        # 選擇最異常的
        candidates.sort(key=lambda x: -x[1])  # 降序排列（異常分數高的在前）

        return candidates[:top_k]

    def predict(self, history: List[Dict], pick_count: int = 6) -> List[int]:
        """
        預測號碼（返回最異常的組合）

        Args:
            history: 歷史數據
            pick_count: 選號數量

        Returns:
            預測號碼
        """
        results = self.predict_anomaly(history, pick_count, n_candidates=10000, top_k=1)

        if results:
            return results[0][0]
        else:
            # Fallback
            return sorted(random.sample(range(1, self.max_num + 1), pick_count))

    def generate_8_bets(
        self,
        history: List[Dict],
        pick_count: int = 6
    ) -> List[Dict]:
        """
        生成8注異常組合

        策略：
        - 4注：極度異常（前4名）
        - 2注：中等異常（第10-20名）
        - 2注：輕微異常（第50-100名）

        Returns:
            8注號碼及其異常分數
        """
        # 訓練模型
        if not self.is_trained:
            self.fit(history)

        # 生成大量候選
        candidates = self.predict_anomaly(
            history,
            pick_count,
            n_candidates=20000,
            top_k=200
        )

        bets = []

        # 4注極度異常
        for i in range(4):
            if i < len(candidates):
                numbers, score = candidates[i]
                bets.append({
                    'numbers': numbers,
                    'strategy': '極度異常',
                    'anomaly_score': score,
                    'rank': i + 1
                })

        # 2注中等異常
        for i in range(10, 30):
            if i < len(candidates) and len(bets) < 6:
                numbers, score = candidates[i]
                bets.append({
                    'numbers': numbers,
                    'strategy': '中等異常',
                    'anomaly_score': score,
                    'rank': i + 1
                })

        # 2注輕微異常
        for i in range(50, 150):
            if i < len(candidates) and len(bets) < 8:
                numbers, score = candidates[i]
                bets.append({
                    'numbers': numbers,
                    'strategy': '輕微異常',
                    'anomaly_score': score,
                    'rank': i + 1
                })

        # 如果不夠8注，補隨機
        while len(bets) < 8:
            numbers = sorted(random.sample(range(1, self.max_num + 1), pick_count))
            bets.append({
                'numbers': numbers,
                'strategy': '隨機補充',
                'anomaly_score': 0.0,
                'rank': 999
            })

        return bets

    def analyze_combination(self, numbers: List[int], history: List[Dict]) -> Dict:
        """
        分析一組號碼的異常程度

        Args:
            numbers: 號碼組合
            history: 歷史數據

        Returns:
            分析結果
        """
        # 訓練模型
        if not self.is_trained:
            self.fit(history)

        # 計算異常分數
        if SKLEARN_AVAILABLE and self.is_trained:
            score = self._calculate_anomaly_score_sklearn(numbers)
            is_anomaly = self.model.predict(
                self.scaler.transform(self._extract_features(numbers).reshape(1, -1))
            )[0] == -1
        else:
            score = self._calculate_anomaly_score_simple(numbers)
            is_anomaly = score > 1.5  # 簡化判定

        # 提取特徵分析
        features = self._extract_features(numbers)

        return {
            'anomaly_score': float(score),
            'is_anomaly': bool(is_anomaly),
            'sum': int(features[0]),
            'odd_count': int(features[1]),
            'high_count': int(features[2]),
            'consecutive_count': int(features[6]),
            'zone_distribution': features[7:12].tolist(),
            'grade': self._grade_anomaly(score)
        }

    def _grade_anomaly(self, score: float) -> str:
        """評級異常程度"""
        if SKLEARN_AVAILABLE:
            # sklearn score 是負值，越負越異常
            if score < -0.6:
                return 'S級 (極度異常)'
            elif score < -0.4:
                return 'A級 (非常異常)'
            elif score < -0.2:
                return 'B級 (異常)'
            elif score < 0:
                return 'C級 (略微異常)'
            else:
                return 'D級 (正常)'
        else:
            # 簡化版 score 是正值，越大越異常
            if score > 2.0:
                return 'S級 (極度異常)'
            elif score > 1.5:
                return 'A級 (非常異常)'
            elif score > 1.0:
                return 'B級 (異常)'
            elif score > 0.5:
                return 'C級 (略微異常)'
            else:
                return 'D級 (正常)'


# 測試函數
if __name__ == '__main__':
    print('=' * 100)
    print('🔍 異常檢測預測器測試')
    print('=' * 100)
    print()

    # 創建模擬歷史數據
    print('📊 生成模擬歷史數據...')
    mock_history = []
    for i in range(100):
        # 模擬「正常」的號碼組合（和值約150, 奇偶平衡）
        numbers = sorted(random.sample(range(1, 50), 6))
        mock_history.append({'numbers': numbers})

    predictor = AnomalyPredictor(max_num=49, contamination=0.1)

    # 測試1：訓練模型
    print('📊 測試1：訓練異常檢測模型')
    print('-' * 100)
    predictor.fit(mock_history)
    print(f'✅ 模型訓練完成 (使用 {"sklearn" if SKLEARN_AVAILABLE else "簡化版"})')
    print()

    # 測試2：預測異常組合
    print('📊 測試2：預測最異常的組合')
    print('-' * 100)
    anomaly_numbers = predictor.predict(mock_history, pick_count=6)
    print(f'預測號碼: {anomaly_numbers}')

    analysis = predictor.analyze_combination(anomaly_numbers, mock_history)
    print(f'異常分數: {analysis["anomaly_score"]:.3f}')
    print(f'是否異常: {"✅ 是" if analysis["is_anomaly"] else "❌ 否"}')
    print(f'異常評級: {analysis["grade"]}')
    print()

    # 測試3：分析正常組合
    print('📊 測試3：分析正常組合')
    print('-' * 100)
    normal_numbers = [7, 13, 21, 28, 35, 42]  # 等差數列
    analysis_normal = predictor.analyze_combination(normal_numbers, mock_history)
    print(f'正常號碼: {normal_numbers}')
    print(f'異常分數: {analysis_normal["anomaly_score"]:.3f}')
    print(f'異常評級: {analysis_normal["grade"]}')
    print()

    # 測試4：生成8注
    print('📊 測試4：生成8注異常組合')
    print('-' * 100)
    bets = predictor.generate_8_bets(mock_history, pick_count=6)

    for idx, bet in enumerate(bets, 1):
        print(f'第{idx}注: {" ".join(f"{n:02d}" for n in bet["numbers"])} | '
              f'{bet["strategy"]:8s} | 分數: {bet["anomaly_score"]:6.3f}')

    print()
    print('✅ 測試完成')
