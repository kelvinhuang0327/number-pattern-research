
from typing import List, Dict, Tuple
from .smart_selector import SmartSelector
from .unified_predictor import UnifiedPredictionEngine
from collections import Counter
import random

class Orthogonal2BetOptimizer:
    """
    Smart-2Bet (Orthogonal System) 優化器
    目標：產生 2 注『正交』(互補) 的預測號碼，最大化覆蓋並提升勝率
    """

    def __init__(self, config: Dict = None):
        self.selector = SmartSelector()
        self.engine = UnifiedPredictionEngine()
        # Default config (Manual Strategy)
        self.config = {
            'trend_window': 500,
            'gap_window': 50,
            'elite_pool_size': 30
        }
        if config:
            self.config.update(config)

    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        """
        執行正交雙注預測
        """
        # 1. 建立精英號碼池 (Elite Pool)
        # 篩選 N 個高潛力號碼
        pool_size = self.config.get('elite_pool_size', 30)
        elite_pool = self.selector.select_elite_numbers(history, rules, pool_size=pool_size)
        
        # 2. 生成注1: Trend-Master (趨勢專家)
        # 策略：在精英池中，選擇統計趨勢最強的號碼 (Window=500)
        bet1_nums = self._generate_trend_bet(history, elite_pool, rules)
        
        # 3. 生成注2: Gap-Hunter (遺漏獵人)
        # 策略：在精英池中，選擇遺漏偏差大、具回補潛力的號碼 (Window=50)
        # 關鍵：嚴格不重疊 (Orthogonal)
        bet2_nums = self._generate_gap_bet(history, elite_pool, rules, exclude=bet1_nums)
        
        return {
            'bets': [
                {'numbers': bet1_nums, 'strategy': 'Trend-Master (統計熱點)'},
                {'numbers': bet2_nums, 'strategy': 'Gap-Hunter (遺漏回補)'}
            ],
            'elite_pool': elite_pool,
            'meta': {
                'bet1_size': len(bet1_nums),
                'bet2_size': len(bet2_nums),
                'overlap': len(set(bet1_nums) & set(bet2_nums))
            }
        }

    def _generate_trend_bet(self, history: List[Dict], pool: List[int], rules: Dict) -> List[int]:
        """
        生成趨勢型注單 (基於長期權重 + 近期熱度)
        """
        # 使用 config 視窗
        window = self.config.get('trend_window', 500)
        data = history[-window:] if len(history) > window else history
        
        # 計算加權頻率 (近期權重高)
        weighted_scores = {}
        for i, draw in enumerate(data):
            # i 越大越新
            weight = 1 + (i / len(data)) * 0.5  # 1.0 ~ 1.5
            for num in draw['numbers']:
                if num in pool:
                    weighted_scores[num] = weighted_scores.get(num, 0) + weight
                    
        # 排序取前 6
        sorted_nums = sorted(weighted_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted([n for n, s in sorted_nums[:6]])

    def _generate_gap_bet(self, history: List[Dict], pool: List[int], rules: Dict, exclude: List[int]) -> List[int]:
        """
        生成遺漏型注單 (基於乖離率 + 遺漏值)
        """
        # 使用 config 視窗
        window = self.config.get('gap_window', 50)
        data = history[-window:] if len(history) > window else history
        
        # 計算遺漏值
        gaps = {}
        min_num = rules.get('minNumber', 1)
        max_num = rules.get('maxNumber', 49)
        
        for num in pool:
            # 如果已經在注1，強制排除 (Strict Exclusion)
            if num in exclude:
                gaps[num] = -9999
                continue
            
            # 找遺漏值
            gap = len(history)
            for i, draw in enumerate(reversed(history)):
                if num in draw['numbers']:
                    gap = i
                    break
            
            # 評分：我們喜歡 "適度遺漏" (Gap 10-25)，它是回補甜蜜點
            # 太短 (Gap < 5) 是熱號 (那是 Trend 的工作)
            # 太長 (Gap > 40) 是死號
            score = 0
            if 10 <= gap <= 25:
                score = 100  # 最佳回補
            elif 5 <= gap < 10:
                score = 60
            elif 25 < gap <= 40:
                score = 50
            else:
                score = 10
                
            # 加上偏差分數 (近期出現次數是否低於期望)
            flat_nums = [n for d in data for n in d['numbers']]
            freq = flat_nums.count(num)
            expected = len(data) * 6 / 49
            if freq < expected:
                score += (expected - freq) * 20
                
            gaps[num] = score

        # 排序取前 6
        sorted_nums = sorted(gaps.items(), key=lambda x: x[1], reverse=True)
        return sorted([n for n, s in sorted_nums[:6]])
