
import numpy as np
from collections import defaultdict, Counter
from typing import List, Dict

class AdaptiveGapManager:
    """
    自適應遺漏管理系統 (Adaptive Gap Manager)
    
    核心機制：
    1. 計算每個號碼的遺漏值 (Current Gap)
    2. 評估每個號碼的『遺漏飽和度』(Gap Saturation) - 目前遺漏 / 歷史平均大遺漏
    3. 預測『回補動能』(Rebound Momentum)
    """
    
    def __init__(self, history_window: int = 500):
        self.history_window = history_window

    def analyze_gaps(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        全量分析遺漏狀態
        """
        max_num = lottery_rules.get('maxNumber', 49)
        min_num = lottery_rules.get('minNumber', 1)
        
        # 1. 獲取當前遺漏
        current_gaps = {}
        for n in range(min_num, max_num + 1):
            gap = 0
            found = False
            for i, d in enumerate(history):
                if n in d['numbers']:
                    current_gaps[n] = i
                    found = True
                    break
            if not found:
                current_gaps[n] = len(history)

        # 2. 獲取每個號碼的歷史遺漏分佈 (Gap Profile)
        gap_profiles = defaultdict(list)
        for n in range(min_num, max_num + 1):
            last_idx = -1
            # 反轉歷史為從舊到新，以便計算間隔
            ordered_history = history[::-1]
            for i, d in enumerate(ordered_history):
                if n in d['numbers']:
                    if last_idx != -1:
                        gap_profiles[n].append(i - last_idx - 1)
                    last_idx = i
        
        # 3. 計算回補指標
        gap_scores = {}
        for n in range(min_num, max_num + 1):
            gaps = gap_profiles[n]
            if not gaps:
                # 無歷史數據時使用理論均值
                avg_gap = (max_num / 6)
                max_gap = avg_gap * 3
            else:
                avg_gap = np.mean(gaps)
                max_gap = np.max(gaps)
            
            curr = current_gaps[n]
            
            # 飽和度指標 (Saturation Index)
            # 如果目前遺漏已經接近歷史最大遺漏，則回補機率極高
            saturation = curr / max_gap if max_gap > 0 else 0
            
            # 超時補償 (Overdue Bonus)
            # 如果目前遺漏大於平均遺漏，開始獲得指數增益
            overdue_ratio = curr / avg_gap if avg_gap > 0 else 0
            
            # 綜合分數
            # 飽和度權重 0.6, 超時權重 0.4
            score = (saturation * 0.6) + (min(2.0, overdue_ratio) * 0.4)
            
            # 增加權重到近期熱號如果它剛好也在歷史短遺漏週期
            # (這部分可以結合動能，暫時只看遺漏)
            
            gap_scores[n] = {
                'current_gap': curr,
                'avg_gap': float(avg_gap),
                'max_gap': float(max_gap),
                'saturation': float(saturation),
                'rebound_score': float(score)
            }
            
        return gap_scores

    def get_top_gaps(self, gap_scores: Dict, count: int = 6) -> List[int]:
        """獲取回補動能最強的號碼"""
        sorted_nums = sorted(gap_scores.items(), key=lambda x: x[1]['rebound_score'], reverse=True)
        return [n for n, s in sorted_nums[:count]]
