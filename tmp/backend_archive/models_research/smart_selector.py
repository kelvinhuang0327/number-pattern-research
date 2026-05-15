
from typing import List, Dict
from collections import Counter, defaultdict
import numpy as np

class SmartSelector:
    """
    智能選號器 (SmartSelector)
    負責從完整號碼池中篩選出 'Elite Pool' (精英號碼池)
    目標：將 49 個號碼縮減至 18-24 個高潛力號碼
    """

    def __init__(self):
        pass

    def select_elite_numbers(self, history: List[Dict], rules: Dict, pool_size: int = 24) -> List[int]:
        """
        篩選精英號碼
        策略：混合 HPSB (Hybrid Position-Structure-Behavior) 評分
        1. 頻率分數 (長期)
        2. 近期熱度 (短期)
        3. 遺漏值 (Gap) 回補潛力
        """
        min_num = rules.get('minNumber', 1)
        max_num = rules.get('maxNumber', 49)
        
        # 1. 計算基礎頻率 (長期 500期)
        long_window = 500
        long_history = history[-long_window:] if len(history) > long_window else history
        long_freq = Counter([n for d in long_history for n in d['numbers']])
        
        # 2. 計算近期熱度 (短期 50期)
        short_window = 50
        short_history = history[-short_window:] if len(history) > short_window else history
        short_freq = Counter([n for d in short_history for n in d['numbers']])
        
        # 3. 計算遺漏值 (Gap)
        gaps = {}
        for num in range(min_num, max_num + 1):
            for i, draw in enumerate(reversed(history)):
                if num in draw['numbers']:
                    gaps[num] = i
                    break
            if num not in gaps:
                gaps[num] = len(history)
        
        # 綜合評分
        scores = {}
        max_long_freq = max(long_freq.values()) if long_freq else 1
        max_short_freq = max(short_freq.values()) if short_freq else 1
        max_gap = max(gaps.values()) if gaps else 1
        
        for num in range(min_num, max_num + 1):
            # 分數構成：
            # 40% 長期頻率 (穩定性)
            # 30% 短期熱度 (趨勢)
            # 30% 遺漏回補 (機會) - 注意：這裡只給適度回補加分，過大 Gap 反而是死號
            
            s1 = long_freq.get(num, 0) / max_long_freq
            s2 = short_freq.get(num, 0) / max_short_freq
            
            # Gap 分數計算：
            # 我們喜歡 "蓄力待發" 的號碼 (Gap ~ 10-20)，不喜歡 "死號" (Gap > 50)
            gap = gaps.get(num, 0)
            if gap > 50:
                s3 = 0.2  # 死號懲罰
            elif gap > 30:
                s3 = 0.5  # 冷號
            elif gap > 10:
                s3 = 1.0  # 最佳回補區
            else:
                s3 = 0.6  # 熱號 (Gap 小)
            
            scores[num] = 0.4 * s1 + 0.3 * s2 + 0.3 * s3
            
        # 排序並選取前 N 個
        sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        elite_numbers = [n for n, s in sorted_nums[:pool_size]]
        
        return sorted(elite_numbers)

