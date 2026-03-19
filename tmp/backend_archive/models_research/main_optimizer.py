import random
from typing import List, Dict
import numpy as np

class MainZoneSmartOptimizer:
    """
    主號區「全效能」優化器 (V1)
    目標：在承認隨機性的前提下，透過「反共識」與「統計常態」篩選最佳投注組合。
    """
    def __init__(self, rules: Dict):
        self.min_num = rules.get('minNumber', 1)
        self.max_num = rules.get('maxNumber', 49)
        self.pick_count = rules.get('pickCount', 6)

    def is_normative(self, numbers: List[int]) -> bool:
        """
        常態篩選：剔除機率極低、不符合經驗分布的「極端組合」。
        """
        # 1. 總和過濾 (Sum Filter)
        # 例如 6/49 的總和平均約 150，常態分布在 100-200 之間
        total_sum = sum(numbers)
        if total_sum < 90 or total_sum > 210: return False
        
        # 2. 奇偶平衡 (Odd/Even Balance)
        odds = sum(1 for n in numbers if n % 2 != 0)
        if odds == 0 or odds == 6: return False # 剔除全奇或全偶 (機率 < 3%)
        
        # 3. 大小平衡 (Low/High Balance)
        mid = self.max_num / 2
        lows = sum(1 for n in numbers if n <= mid)
        if lows == 0 or lows == 6: return False # 剔除全大或全小
        
        # 4. 連號過濾 (Consecutive)
        sorted_nums = sorted(numbers)
        consecutive_count = 0
        for i in range(len(sorted_nums) - 1):
            if sorted_nums[i+1] - sorted_nums[i] == 1:
                consecutive_count += 1
        if consecutive_count > 2: return False # 剔除三連號以上 (如 1,2,3,4)
        
        return True

    def calculate_ev_score(self, numbers: List[int]) -> float:
        """
        EV 評分：避開「大眾喜好」，最大化中獎時的獎金分配。
        """
        score = 100.0
        # 避開生日熱區 (1-31)
        consensus_count = sum(1 for n in numbers if n <= 31)
        score -= (consensus_count ** 1.5) * 5 # 懲罰 1-31 過多的組合
        
        # 鼓勵高位數 (32+)
        unpopular_count = sum(1 for n in numbers if n > 31)
        score += unpopular_count * 10
        
        return score

    def generate_smart_bets(self, count: int = 7) -> List[List[int]]:
        """
        生成 N 組「智慧型」隨機注
        """
        bets = []
        attempts = 0
        while len(bets) < count and attempts < 1000:
            candidate = sorted(random.sample(range(self.min_num, self.max_num + 1), self.pick_count))
            attempts += 1
            
            # 必須符合常態分布
            if not self.is_normative(candidate): continue
            
            # 檢查與現有注的重複度 (Diversity)
            too_similar = False
            for b in bets:
                overlap = len(set(candidate) & set(b))
                if overlap >= 4: # 重複 4 個以上則視為過於接近
                    too_similar = True
                    break
            
            if not too_similar:
                bets.append(candidate)
                
        # 最後將結果依據 EV 分數排序 (選出最好的 N 組)
        bets.sort(key=lambda x: self.calculate_ev_score(x), reverse=True)
        return bets[:count]
