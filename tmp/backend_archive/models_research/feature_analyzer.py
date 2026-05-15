import numpy as np
from typing import List, Dict

class LotteryFeatureAnalyzer:
    """
    分析彩票號碼組合的全局特徵
    """
    @staticmethod
    def calculate_ac_value(numbers: List[int]) -> int:
        """計算算術複雜度 (AC Value)"""
        if not numbers: return 0
        diffs = set()
        nums = sorted(numbers)
        n = len(nums)
        for i in range(n):
            for j in range(i + 1, n):
                diffs.add(nums[j] - nums[i])
        return len(diffs) - (n - 1)

    @staticmethod
    def calculate_sum(numbers: List[int]) -> int:
        """計算總和"""
        return sum(numbers)

    @staticmethod
    def calculate_odd_even_ratio(numbers: List[int]) -> float:
        """計算奇偶比 (奇數/總數)"""
        if not numbers: return 0.5
        odds = len([n for n in numbers if n % 2 != 0])
        return odds / len(numbers)

    @staticmethod
    def get_consecutive_count(numbers: List[int]) -> int:
        """計算連號組數"""
        if not numbers: return 0
        nums = sorted(numbers)
        count = 0
        for i in range(len(nums) - 1):
            if nums[i+1] - nums[i] == 1:
                count += 1
        return count

    @staticmethod
    def calculate_entropy(numbers: List[int], max_num: int = 49) -> float:
        """計算號碼組合的熵 (Entropy)"""
        if not numbers: return 0.0
        # 計算號碼間隔的分佈熵
        nums = sorted(numbers)
        gaps = [nums[0]] + [nums[i+1] - nums[i] for i in range(len(nums)-1)] + [max_num - nums[-1]]
        total_gap = sum(gaps)
        probs = [g/total_gap for g in gaps if g > 0]
        return -sum(p * np.log2(p) for p in probs)

    @staticmethod
    def calculate_harmonic_mean(numbers: List[int]) -> float:
        """計算調和平均數"""
        if not numbers or 0 in numbers: return 0.0
        return len(numbers) / sum(1.0/n for n in numbers)

    @staticmethod
    def calculate_gap_variance(numbers: List[int]) -> float:
        """計算間隔方差 (衡量號碼分佈的均勻度)"""
        if len(numbers) < 2: return 0.0
        nums = sorted(numbers)
        gaps = [nums[i+1] - nums[i] for i in range(len(nums)-1)]
        return float(np.var(gaps))

    @staticmethod
    def get_draw_stats(draws: List[Dict]) -> Dict:
        """從歷史開獎中提取統計分佈"""
        import json
        sums = []
        acs = []
        for d in draws:
            try:
                nums = d.get('numbers', [])
                if isinstance(nums, str):
                    nums = json.loads(nums)
                if nums:
                    sums.append(sum(nums))
                    acs.append(LotteryFeatureAnalyzer.calculate_ac_value(nums))
            except:
                continue
        
        if not sums:
            return {'sum_avg': 0, 'sum_std': 0, 'ac_avg': 0, 'ac_std': 0}
            
        return {
            'sum_avg': float(np.mean(sums)),
            'sum_std': float(np.std(sums)),
            'ac_avg': float(np.mean(acs)),
            'ac_std': float(np.std(acs))
        }
