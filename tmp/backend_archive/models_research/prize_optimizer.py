import random
import logging
from typing import List, Dict

logger = logging.getLogger('PrizeOptimizer')

class PrizeOptimizer:
    """
    不歡迎度 (EV) 計算工具
    目標：在主號隨機的前提下，盡量避開大眾喜好的號碼區間（如生日 1-31），
    以在偶爾中獎時，減少與他人平分獎金的機率。
    """
    
    def __init__(self, lottery_rules: Dict):
        self.max_num = lottery_rules.get('maxNumber', 49)
        self.pick_count = lottery_rules.get('pickCount', 6)

    def score_bet_unpopularity(self, numbers: List[int]) -> float:
        """
        計算組合的「冷門程度」。
        分數越高 = 越冷門 = 中獎時平均人均獎金可能越高。
        """
        score = 100.0
        sorted_nums = sorted(numbers)
        
        # 生日號碼懲罰 (1-31)
        birthday_count = sum(1 for n in numbers if n <= 31)
        score -= (birthday_count ** 2) * 5 
        
        # 高位數獎勵 (Numbers > 31)
        high_count = sum(1 for n in numbers if n > 31)
        score += high_count * 15
        
        # 連號懲罰 (人類喜歡選連號)
        for i in range(len(sorted_nums) - 1):
            if sorted_nums[i+1] - sorted_nums[i] == 1:
                score -= 20
        
        return score

    def get_ev_optimized_bet(self, candidates: List[List[int]]) -> List[int]:
        """從一組候選注中，選出最冷門的一組"""
        if not candidates: return []
        return max(candidates, key=lambda x: self.score_bet_unpopularity(x))

    def generate_sniper_sweep_bets(self, main_numbers: List[int], top_specials: List[int]) -> List[Dict]:
        """
        生成掃射組合 (用於科學審計與特區進攻)
        1 組主號 + 多個特別號
        """
        bets = []
        for s_num in top_specials:
            bets.append({
                'numbers': sorted(main_numbers),
                'special': s_num,
                'source': f'sniper_sweep_s{s_num}'
            })
        return bets
