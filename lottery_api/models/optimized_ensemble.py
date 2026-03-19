
import numpy as np
import json
from collections import Counter
from typing import List, Dict, Set

class OptimizedEnsemblePredictor:
    """
    ROI 優化集成預測器 (Multi-Lottery Support)
    核心設計：
    1. Momentum Detector: 抓取極短線熱點 (重號/連號)
    2. Entropy Score: 確保球在空間分佈上的均衡度
    3. Lag Reversion: 捕捉有效遺漏窗口的號碼 (Power Lotto: 3-8期; Big Lotto: 6-12期)
    """
    
    def __init__(self, rules: Dict):
        self.rules = rules
        self.lottery_name = rules.get('name', 'UNKNOWN')
        self.is_power = 'POWER' in self.lottery_name or '威力彩' in self.lottery_name
        self.max_num = rules.get('maxNumber', 38 if self.is_power else 49)
        self.pick_count = rules.get('pickCount', 6)
        
        # Phase 52: Dynamic Config for Tuning (Updated with Best Tune Results)
        self.config = {
            'w_m': 0.4 if self.is_power else 0.4,
            'w_e': 0.3,
            'w_l': 0.3 if self.is_power else 0.2,
            'entropy_multiplier': 40.0,
            'lag_min': 3 if self.is_power else 6,
            'lag_max': 8 if self.is_power else 12,
            'momentum_window': 5,
            'repeat_bonus': 1.25 if self.is_power else 1.2
        }

    def update_config(self, new_config: Dict):
        """用於超參數調教"""
        self.config.update(new_config)
        
    def momentum_detector(self, history: List[Dict], window: int = None) -> Dict[int, float]:
        """動能偵測：針對近 N 期頻率與連續性加權"""
        if window is None: window = self.config['momentum_window']
        recent = history[-window:]
        scores = {i: 0.0 for i in range(1, self.max_num + 1)}
        
        for idx, d in enumerate(recent):
            # 越近的權重越高 (Exponential decay)
            weight = np.exp(idx / window)
            for n in d['numbers']:
                if n <= self.max_num:
                    scores[n] += weight
                
        # 額外獎勵「上一期」出現過的號碼 (重號傾向)
        last_draw = history[-1]['numbers']
        for n in last_draw:
            if n <= self.max_num:
                scores[n] *= self.config['repeat_bonus']
            
        return scores

    def entropy_scorer(self, history: List[Dict], window: int = 150) -> Dict[int, float]:
        """空間均衡分佈得分"""
        h_slice = history[-window:]
        all_nums = [n for d in h_slice for n in d['numbers']]
        freq = Counter(all_nums)
        
        scores = {}
        target_freq = (len(h_slice) * self.pick_count) / self.max_num
        for n in range(1, self.max_num + 1):
            f = freq.get(n, 0)
            # 偏離均值越小的，得分越高 (追求回歸均衡)
            scores[n] = 1.0 / (abs(f - target_freq) + 0.1)
            
        return scores

    def lag_reversion_scorer(self, history: List[Dict], window: int = 500) -> Dict[int, float]:
        """遺漏回歸得分"""
        last_seen = {i: -1 for i in range(1, self.max_num + 1)}
        for idx, d in enumerate(history):
            for n in d['numbers']:
                if n <= self.max_num:
                    last_seen[n] = idx
        
        current_idx = len(history)
        scores = {}
        
        # Power Lotto 與大樂透的遺漏回歸特徵不同
        lag_min = self.config['lag_min']
        lag_max = self.config['lag_max']
        
        for n in range(1, self.max_num + 1):
            lag = current_idx - last_seen[n]
            if lag_min <= lag <= lag_max:
                scores[n] = 1.5
            elif lag > 25: # 極冷號補償
                scores[n] = 1.25
            else:
                scores[n] = 1.0
        return scores

    def predict(self, history: List[Dict], n_bets: int = 1) -> Dict:
        """綜合預測邏輯 (ROI Stacked)"""
        if len(history) < 20:
            return {'numbers': list(range(1, 7))}
            
        m_scores = self.momentum_detector(history)
        e_scores = self.entropy_scorer(history)
        l_scores = self.lag_reversion_scorer(history)
        
        # 融合分數
        final_scores = np.zeros(self.max_num + 1)
        for n in range(1, self.max_num + 1):
            # 權重分配 (從動態 config 獲取)
            w_m = self.config['w_m']
            w_e = self.config['w_e']
            w_l = self.config['w_l']
            e_mult = self.config['entropy_multiplier']
            
            # 熵值分數需要量級校準
            final_scores[n] = (m_scores[n] * w_m) + (e_scores[n] * e_mult * w_e) + (l_scores[n] * w_l)
            
        # 排序
        sorted_indices = np.argsort(final_scores[1:])[::-1] + 1
        
        bets = []
        for i in range(n_bets):
            # ROI 策略：第 1 注拿最高分，第 2 注拿次高分或進行「非對稱」補位
            if i == 0:
                bets.append(sorted(sorted_indices[:self.pick_count].tolist()))
            else:
                # 貪婪補全：優先選擇與第一注不重疊且高分的號碼
                b1_set = set(bets[0])
                complement = [n for n in sorted_indices if n not in b1_set]
                # 混合 3 個新號 + 3 個高分號 (半正交)
                b_mix = complement[:3] + sorted_indices[:3].tolist()
                bets.append(sorted(list(set(b_mix))))
                
                # 補齊
                while len(bets[-1]) < self.pick_count:
                    for n in sorted_indices:
                        if n not in bets[-1]:
                            bets[-1].append(n)
                            if len(bets[-1]) >= self.pick_count: break
                bets[-1].sort()
            
        return {
            'numbers': bets[0] if bets else [],
            'all_bets': bets,
            'scores': final_scores.tolist(),
            'method': 'ROI_Stacked_Ensemble'
        }
