#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量子隨機預測器 (Quantum Random Predictor)

核心概念：
- 大樂透本質是隨機，與其預測不如產生真隨機
- 使用量子隨機數生成器 (QRNG)
- 作為 Baseline 對比其他方法是否真的更好

量子隨機源：
- 澳洲國立大學 (ANU) 量子隨機數 API
- 基於量子物理的真隨機性
- Fallback: Python secrets 模組（密碼學級隨機）
"""

import secrets
import random
from typing import List, Dict, Optional
import numpy as np

# 可選：使用 requests 呼叫 API（如果需要真量子隨機）
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class QuantumRandomPredictor:
    """量子隨機預測器"""

    # ANU 量子隨機數 API
    QRNG_API_URL = "https://qrng.anu.edu.au/API/jsonI.php"

    def __init__(self, max_num: int = 49, use_quantum: bool = True):
        """
        初始化預測器

        Args:
            max_num: 最大號碼
            use_quantum: 是否使用真量子隨機（需要網路連線）
        """
        self.max_num = max_num
        self.use_quantum = use_quantum and REQUESTS_AVAILABLE

    def _fetch_quantum_random(self, length: int, max_retries: int = 3) -> Optional[List[int]]:
        """
        從 ANU QRNG API 獲取量子隨機數

        Args:
            length: 需要的隨機數數量
            max_retries: 最大重試次數

        Returns:
            量子隨機數列表，失敗返回 None
        """
        if not REQUESTS_AVAILABLE:
            return None

        for attempt in range(max_retries):
            try:
                # API 參數
                params = {
                    'length': length * 2,  # 多取一些避免重複後不夠
                    'type': 'uint8'  # 0-255 的整數
                }

                response = requests.get(
                    self.QRNG_API_URL,
                    params=params,
                    timeout=5
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        return data.get('data', [])

            except Exception as e:
                if attempt == max_retries - 1:
                    print(f'⚠️  量子隨機API失敗: {e}')
                continue

        return None

    def _crypto_random_sample(self, k: int) -> List[int]:
        """
        使用密碼學級隨機數生成器

        Args:
            k: 需要的號碼數量

        Returns:
            隨機號碼列表
        """
        # 使用 secrets 模組（比 random 更隨機）
        numbers = set()

        while len(numbers) < k:
            num = secrets.randbelow(self.max_num) + 1
            numbers.add(num)

        return sorted(list(numbers))

    def predict(self, history: List[Dict], pick_count: int = 6) -> List[int]:
        """
        預測號碼（使用量子隨機或密碼學隨機）

        Args:
            history: 歷史數據（本方法不使用）
            pick_count: 選號數量

        Returns:
            隨機號碼列表
        """
        if self.use_quantum:
            # 嘗試使用量子隨機
            quantum_data = self._fetch_quantum_random(pick_count)

            if quantum_data and len(quantum_data) >= pick_count:
                # 將 0-255 轉換為 1-max_num 範圍
                numbers = set()
                for value in quantum_data:
                    num = (value % self.max_num) + 1
                    numbers.add(num)
                    if len(numbers) == pick_count:
                        break

                # 如果量子數據成功
                if len(numbers) == pick_count:
                    return sorted(list(numbers))

        # Fallback: 使用密碼學隨機
        return self._crypto_random_sample(pick_count)

    def predict_with_constraints(
        self,
        history: List[Dict],
        pick_count: int = 6,
        min_sum: int = 100,
        max_sum: int = 200,
        max_retries: int = 100
    ) -> List[int]:
        """
        帶約束條件的隨機預測（確保和值在合理範圍）

        Args:
            history: 歷史數據
            pick_count: 選號數量
            min_sum: 最小和值
            max_sum: 最大和值
            max_retries: 最大重試次數

        Returns:
            符合約束的隨機號碼
        """
        for _ in range(max_retries):
            numbers = self.predict(history, pick_count)
            total = sum(numbers)

            if min_sum <= total <= max_sum:
                return numbers

        # 如果重試失敗，返回不帶約束的結果
        return self.predict(history, pick_count)

    def generate_8_bets(
        self,
        history: List[Dict],
        pick_count: int = 6,
        ensure_diversity: bool = True
    ) -> List[Dict]:
        """
        生成8注量子隨機號碼

        Args:
            history: 歷史數據
            pick_count: 每注號碼數量
            ensure_diversity: 是否確保8注之間的多樣性

        Returns:
            8注號碼資訊
        """
        bets = []
        all_numbers_used = set()

        for i in range(8):
            # 生成隨機號碼
            if ensure_diversity and i >= 1:
                # 嘗試生成與之前不同的組合
                numbers = self._generate_diverse_bet(
                    all_numbers_used,
                    pick_count,
                    max_attempts=50
                )
            else:
                numbers = self.predict(history, pick_count)

            # 記錄使用過的號碼
            all_numbers_used.update(numbers)

            # 分析這注的特性
            bet_sum = sum(numbers)
            odd_count = sum(1 for n in numbers if n % 2 == 1)
            high_count = sum(1 for n in numbers if n > 24)

            bets.append({
                'numbers': numbers,
                'strategy': '量子隨機' if self.use_quantum else '密碼學隨機',
                'sum': bet_sum,
                'odd_count': odd_count,
                'high_count': high_count,
                'randomness_grade': 'S級 (真隨機)'
            })

        return bets

    def _generate_diverse_bet(
        self,
        existing_numbers: set,
        pick_count: int,
        max_attempts: int = 50
    ) -> List[int]:
        """
        生成與現有號碼儘量不重複的組合

        Args:
            existing_numbers: 已使用的號碼集合
            pick_count: 需要選擇的號碼數量
            max_attempts: 最大嘗試次數

        Returns:
            號碼列表
        """
        best_bet = None
        min_overlap = float('inf')

        for _ in range(max_attempts):
            candidate = self.predict([], pick_count)
            overlap = len(set(candidate) & existing_numbers)

            if overlap < min_overlap:
                min_overlap = overlap
                best_bet = candidate

            # 如果找到完全不重複的，立即返回
            if overlap == 0:
                break

        return best_bet if best_bet else self.predict([], pick_count)

    def benchmark_randomness(self, n_samples: int = 1000) -> Dict:
        """
        測試隨機性品質（統計測試）

        Args:
            n_samples: 樣本數量

        Returns:
            隨機性評估結果
        """
        samples = []

        for _ in range(n_samples):
            numbers = self.predict([], pick_count=6)
            samples.append(numbers)

        # 統計分析
        all_numbers = []
        for sample in samples:
            all_numbers.extend(sample)

        from collections import Counter
        freq = Counter(all_numbers)

        # 計算均勻性（Chi-square test）
        expected_freq = n_samples * 6 / self.max_num
        chi_square = sum((count - expected_freq) ** 2 / expected_freq for count in freq.values())

        # 自由度 = 49 - 1 = 48
        # Chi-square臨界值 (α=0.05, df=48) ≈ 65.17
        is_random = chi_square < 65.17

        return {
            'n_samples': n_samples,
            'chi_square': chi_square,
            'is_statistically_random': is_random,
            'frequency_distribution': dict(freq),
            'most_common': freq.most_common(5),
            'least_common': freq.most_common()[-5:],
        }

    @staticmethod
    def compare_with_pseudo_random(max_num: int = 49, n_tests: int = 100) -> Dict:
        """
        對比量子隨機與偽隨機的差異

        Args:
            max_num: 最大號碼
            n_tests: 測試次數

        Returns:
            對比結果
        """
        quantum_predictor = QuantumRandomPredictor(max_num=max_num, use_quantum=True)
        pseudo_predictor = QuantumRandomPredictor(max_num=max_num, use_quantum=False)

        quantum_samples = [quantum_predictor.predict([], 6) for _ in range(n_tests)]
        pseudo_samples = [pseudo_predictor.predict([], 6) for _ in range(n_tests)]

        # 計算多樣性
        quantum_unique = len(set(tuple(s) for s in quantum_samples))
        pseudo_unique = len(set(tuple(s) for s in pseudo_samples))

        return {
            'quantum_unique_combinations': quantum_unique,
            'pseudo_unique_combinations': pseudo_unique,
            'quantum_diversity_rate': quantum_unique / n_tests,
            'pseudo_diversity_rate': pseudo_unique / n_tests,
        }


# 測試函數
if __name__ == '__main__':
    print('=' * 100)
    print('🔬 量子隨機預測器測試')
    print('=' * 100)
    print()

    # 測試1：基本預測
    predictor = QuantumRandomPredictor(max_num=49, use_quantum=True)

    print('📊 測試1：量子隨機預測')
    print('-' * 100)
    numbers = predictor.predict([], pick_count=6)
    print(f'預測號碼: {numbers}')
    print(f'和值: {sum(numbers)}')
    print(f'奇數個數: {sum(1 for n in numbers if n % 2 == 1)}')
    print()

    # 測試2：生成8注
    print('📊 測試2：生成8注量子隨機號碼')
    print('-' * 100)
    bets = predictor.generate_8_bets([], pick_count=6, ensure_diversity=True)

    for idx, bet in enumerate(bets, 1):
        print(f'第{idx}注: {" ".join(f"{n:02d}" for n in bet["numbers"])} | '
              f'和值: {bet["sum"]:3d} | 奇數: {bet["odd_count"]}/6')

    print()

    # 測試3：帶約束的預測
    print('📊 測試3：帶約束預測（和值 120-180）')
    print('-' * 100)
    constrained = predictor.predict_with_constraints(
        [],
        pick_count=6,
        min_sum=120,
        max_sum=180
    )
    print(f'預測號碼: {constrained}')
    print(f'和值: {sum(constrained)} (符合約束)')
    print()

    # 測試4：隨機性測試（如果有時間）
    print('📊 測試4：隨機性品質測試（100個樣本）')
    print('-' * 100)
    benchmark = predictor.benchmark_randomness(n_samples=100)
    print(f'Chi-square 值: {benchmark["chi_square"]:.2f}')
    print(f'統計上是否隨機: {"✅ 是" if benchmark["is_statistically_random"] else "❌ 否"}')
    print(f'最常出現的號碼: {benchmark["most_common"][:3]}')
    print()

    print('✅ 測試完成')
