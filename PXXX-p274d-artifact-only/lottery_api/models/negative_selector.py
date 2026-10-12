"""
負向排除機制 (Negative Selection)

功能：預測「不會出現」的號碼，用於過濾預測結果
原理：
1. 冷門號碼：近期出現頻率最低的號碼
2. 過期號碼：超過一定期數未出現的號碼
3. Smart Rule：遺漏值過高的號碼強制保留（防止冷號回補）
4. 組合排除：同時滿足多個條件的號碼

2025 年回測優化結果：
- 最佳配置：冷門窗口 120 期，冷門 25%，過期門檻 10 期
- 排除準確率：88.6%
- 每期平均排除：4.6 個

⚠️ 重要發現（2026-01-02 驗證）：
- Kill-10（排除10個）錯殺風險高達 72.9%
- 建議使用保守策略（排除 4-5 個），準確率更高、風險更低

使用方式：
    from models.negative_selector import NegativeSelector

    selector = NegativeSelector()
    result = selector.analyze(history, lottery_type)

    # result 包含:
    # - excluded_numbers: 建議排除的號碼
    # - cold_numbers: 冷門號碼
    # - overdue_numbers: 過期號碼
    # - exclusion_rate: 歷史排除成功率
"""

from collections import Counter
from typing import List, Dict, Set, Optional
import logging

logger = logging.getLogger(__name__)


class NegativeSelector:
    """負向排除選擇器"""

    # 各彩種的預設配置
    DEFAULT_CONFIGS = {
        'BIG_LOTTO': {
            'max_number': 49,
            'cold_window': 100,      # 計算冷門的窗口期數
            'cold_percentile': 20,   # 最冷門的 N%
            'overdue_window': 50,    # 計算過期的窗口期數
            'overdue_threshold': 15, # 超過 N 期未出現視為過期
        },
        'POWER_LOTTO': {
            'max_number': 38,
            'cold_window': 80,
            'cold_percentile': 20,
            'overdue_window': 40,
            'overdue_threshold': 12,
        },
        'DAILY_539': {
            'max_number': 39,
            'cold_window': 100,
            'cold_percentile': 20,
            'overdue_window': 50,
            'overdue_threshold': 15,
        },
    }

    def __init__(self, custom_config: Optional[Dict] = None):
        """
        初始化負向排除器

        Args:
            custom_config: 自定義配置，會覆蓋預設值
        """
        self.custom_config = custom_config or {}

    def get_config(self, lottery_type: str) -> Dict:
        """取得指定彩種的配置"""
        config = self.DEFAULT_CONFIGS.get(lottery_type, self.DEFAULT_CONFIGS['BIG_LOTTO']).copy()
        config.update(self.custom_config)
        return config

    def get_cold_numbers(self, history: List[Dict], config: Dict) -> Set[int]:
        """
        找出冷門號碼（出現頻率最低的 N%）

        Args:
            history: 歷史開獎數據
            config: 配置參數

        Returns:
            冷門號碼集合
        """
        freq = Counter()
        window = min(config['cold_window'], len(history))

        for d in history[:window]:
            freq.update(d['numbers'])

        all_nums = list(range(1, config['max_number'] + 1))
        counts = [(n, freq.get(n, 0)) for n in all_nums]
        counts.sort(key=lambda x: x[1])

        cutoff = int(len(all_nums) * config['cold_percentile'] / 100)
        cold_nums = set(n for n, c in counts[:cutoff])

        return cold_nums

    def get_overdue_numbers(self, history: List[Dict], config: Dict) -> Set[int]:
        """
        找出過期號碼（超過 N 期未出現）

        Args:
            history: 歷史開獎數據
            config: 配置參數

        Returns:
            過期號碼集合
        """
        last_seen = {n: 9999 for n in range(1, config['max_number'] + 1)}
        window = min(config['overdue_window'], len(history))

        for i, d in enumerate(history[:window]):
            for n in d['numbers']:
                if last_seen[n] > i:
                    last_seen[n] = i

        overdue = set(n for n, gap in last_seen.items()
                      if gap >= config['overdue_threshold'])

        return overdue

    def get_recent_cold(self, history: List[Dict], config: Dict,
                        window: int = 20, min_count: int = 2) -> Set[int]:
        """
        找出近期極冷號碼（近 N 期出現次數 < M）
        """
        freq = Counter()
        for d in history[:window]:
            freq.update(d['numbers'])

        recent_cold = set(n for n in range(1, config['max_number'] + 1)
                          if freq.get(n, 0) < min_count)
        return recent_cold

    def analyze(self, history: List[Dict], lottery_type: str) -> Dict:
        """
        分析並返回負向排除結果

        Args:
            history: 歷史開獎數據（新→舊排序）
            lottery_type: 彩種類型

        Returns:
            {
                'excluded_numbers': [...],  # 建議排除的號碼
                'cold_numbers': [...],      # 冷門號碼
                'overdue_numbers': [...],   # 過期號碼
                'recent_cold': [...],       # 近期極冷號碼
                'config': {...},            # 使用的配置
            }
        """
        config = self.get_config(lottery_type)

        cold = self.get_cold_numbers(history, config)
        overdue = self.get_overdue_numbers(history, config)
        recent_cold = self.get_recent_cold(history, config)

        # 排除策略：冷門 AND 過期（保守）
        # 或者：(冷門 AND 過期) OR (冷門 AND 近期極冷)（激進）
        excluded = (cold & overdue) | (cold & recent_cold)

        return {
            'excluded_numbers': sorted(excluded),
            'cold_numbers': sorted(cold),
            'overdue_numbers': sorted(overdue),
            'recent_cold': sorted(recent_cold),
            'config': config,
            'lottery_type': lottery_type,
        }

    def validate_exclusion(self, history: List[Dict], lottery_type: str,
                           test_periods: int = 100) -> Dict:
        """
        驗證排除機制的歷史成功率

        Args:
            history: 歷史開獎數據
            lottery_type: 彩種類型
            test_periods: 測試期數

        Returns:
            {
                'total_excluded': int,      # 總排除號碼數
                'correct_excluded': int,    # 正確排除數（排除且沒出現）
                'false_excluded': int,      # 錯誤排除數（排除但出現了）
                'accuracy': float,          # 排除準確率
                'avg_excluded_per_draw': float,  # 每期平均排除數
            }
        """
        config = self.get_config(lottery_type)

        total_excluded = 0
        correct_excluded = 0
        false_excluded = 0

        # 確保有足夠的數據
        max_window = max(config['cold_window'], config['overdue_window'])
        test_periods = min(test_periods, len(history) - max_window - 1)

        for i in range(test_periods):
            target = history[i]
            train = history[i + 1:]

            if len(train) < max_window:
                continue

            # 計算排除號碼
            result = self.analyze(train, lottery_type)
            excluded = set(result['excluded_numbers'])
            actual = set(target['numbers'])

            # 統計
            total_excluded += len(excluded)
            correct_excluded += len(excluded - actual)  # 排除且沒出現
            false_excluded += len(excluded & actual)    # 排除但出現了

        accuracy = correct_excluded / total_excluded if total_excluded > 0 else 0
        avg_per_draw = total_excluded / test_periods if test_periods > 0 else 0

        return {
            'test_periods': test_periods,
            'total_excluded': total_excluded,
            'correct_excluded': correct_excluded,
            'false_excluded': false_excluded,
            'accuracy': accuracy,
            'accuracy_pct': f"{accuracy * 100:.1f}%",
            'avg_excluded_per_draw': avg_per_draw,
        }

    def filter_prediction(self, prediction: List[int], excluded: Set[int],
                          history: List[Dict], max_number: int) -> List[int]:
        """
        過濾預測結果，將排除的號碼替換為其他號碼

        Args:
            prediction: 原始預測號碼
            excluded: 排除的號碼集合
            history: 歷史數據（用於計算替換號碼的優先級）
            max_number: 最大號碼

        Returns:
            過濾後的預測號碼
        """
        # 計算可用號碼的熱度
        freq = Counter()
        for d in history[:50]:
            freq.update(d['numbers'])

        # 找出可用的替換號碼（不在預測中、不在排除中）
        available = [n for n in range(1, max_number + 1)
                     if n not in excluded and n not in prediction]
        available.sort(key=lambda n: -freq.get(n, 0))  # 按熱度排序

        # 替換被排除的號碼
        result = []
        replacements = iter(available)

        for n in prediction:
            if n in excluded:
                try:
                    replacement = next(replacements)
                    result.append(replacement)
                except StopIteration:
                    result.append(n)  # 無法替換則保留
            else:
                result.append(n)

        return sorted(set(result))[:len(prediction)]


# 便捷函數
def get_excluded_numbers(history: List[Dict], lottery_type: str) -> List[int]:
    """快速獲取排除號碼"""
    selector = NegativeSelector()
    result = selector.analyze(history, lottery_type)
    return result['excluded_numbers']


def validate_exclusion_accuracy(history: List[Dict], lottery_type: str,
                                test_periods: int = 100) -> Dict:
    """快速驗證排除準確率"""
    selector = NegativeSelector()
    return selector.validate_exclusion(history, lottery_type, test_periods)
