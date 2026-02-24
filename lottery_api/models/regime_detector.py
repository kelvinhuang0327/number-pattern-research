import numpy as np
from collections import Counter
from typing import List, Dict

class RegimeDetector:
    """
    環境機制偵測器 (Regime Detector)
    分析彩票走勢的物理狀態：規律期 (Order)、紊亂期 (Chaos)、過渡期 (Transition)
    """
    
    def __init__(self, history_window: int = 50):
        self.history_window = history_window

    def detect_regime(self, history: List[Dict]) -> Dict:
        """
        偵測當前環境機制
        """
        if len(history) < 20:
            return {'regime': 'TRANSITION', 'confidence': 0.5, 'entropy': 1.0}

        # 1. 計算局部熵值 (Local Entropy) - 衡量分佈廣度
        recent_draws = history[-15:]
        all_nums = []
        for d in recent_draws:
            all_nums.extend(d['numbers'])
        
        counts = Counter(all_nums)
        probs = [c/len(all_nums) for c in counts.values()]
        entropy = -sum(p * np.log2(p) for p in probs)
        
        # 2. 計算簡化版 Hurst Exponent - 衡量趨勢持續性
        hurst = self._calculate_simple_hurst(history[-30:])
        
        # 3. 判定 Regime
        # 均勻 49 碼的理論最大熵約為 5.6 (ln 49)
        # 均勻 38 碼的理論最大熵約為 5.2 (ln 38)
        max_num = max([max(d['numbers']) for d in recent_draws])
        theoretical_max_entropy = np.log2(max_num)
        
        # 🔍 增強判定邏輯：針對 Cluster-to-Entropy 切換
        # 如果最近 5 期與最近 15 期的熵值發生顯著變化，標記為 TRANSITION
        short_draws = history[-5:]
        short_nums = [n for d in short_draws for n in d['numbers']]
        short_counts = Counter(short_nums)
        short_probs = [c/len(short_nums) for c in short_counts.values()]
        short_entropy = -sum(p * np.log2(p) for p in short_probs)
        
        entropy_shift = short_entropy - entropy
        
        # 4. 偵測間距對稱性 (Gap Symmetry)
        symmetry_score = self.detect_gap_symmetry(history[-10:])
        
        if abs(entropy_shift) > 0.4:
            regime = 'TRANSITION'
        elif entropy < (theoretical_max_entropy * 0.75) or hurst > 0.6 or symmetry_score > 0.7:
            regime = 'ORDER'  # 高對稱性視為一種「隱性秩序」
        elif entropy > (theoretical_max_entropy * 0.82) or hurst < 0.4:
            regime = 'CHAOS'
        else:
            regime = 'TRANSITION'
            
        return {
            'regime': regime,
            'entropy': float(entropy),
            'short_entropy': float(short_entropy),
            'entropy_shift': float(entropy_shift),
            'hurst': float(hurst),
            'symmetry_score': float(symmetry_score),
            'confidence': 0.8 if regime != 'TRANSITION' else 0.5
        }

    def detect_gap_symmetry(self, history: List[Dict]) -> float:
        """
        偵測開獎號碼間距的對稱性 (Gap Symmetry)
        例如：3-5-7-7-3 具有高度對稱性
        """
        if not history: return 0.0
        
        recent_draws = history[-5:]
        symmetry_scores = []
        
        for d in recent_draws:
            nums = sorted(d['numbers'])
            if len(nums) < 4: continue
            
            gaps = [nums[i+1] - nums[i] for i in range(len(nums)-1)]
            
            # 計算對稱度
            # 例如 gaps = [3, 5, 7, 7, 3] -> reverse = [3, 7, 7, 5, 3]
            # 我們比較 gaps 的前半部分與後半部分的鏡像
            half = len(gaps) // 2
            first_half = gaps[:half]
            second_half_mirrored = gaps[-half:][::-1]
            
            # 使用相關性或簡單差異
            if first_half:
                diff = sum(abs(a - b) for a, b in zip(first_half, second_half_mirrored))
                # diff = 0 代表完美對稱
                score = 1.0 / (1.0 + diff)
                symmetry_scores.append(score)
        
        return np.mean(symmetry_scores) if symmetry_scores else 0.0

    def _calculate_simple_hurst(self, history: List[Dict]) -> float:
        """
        計算簡化版 Hurst Exponent (0-1)
        0.5 代表隨機行走，>0.5 代表趨勢持續，<0.5 代表均值回歸
        """
        if len(history) < 10: return 0.5
        
        # 取每期號碼的和值作為序列
        sums = [sum(d['numbers']) for d in history]
        # 計算累積偏差
        mean = np.mean(sums)
        
        # 簡單估算 R/S
        rs_values = []
        for n in [5, 10, 20]:
            if len(sums) < n: continue
            chunk = sums[-n:]
            r = np.max(chunk) - np.min(chunk)
            s = np.std(chunk) or 1.0
            rs_values.append(np.log(r/s + 1e-10) / np.log(n))
            
        return np.mean(rs_values) if rs_values else 0.5

    def get_weight_adjustments(self, regime_info: Dict, lottery_type: str = 'BIG_LOTTO') -> Dict[str, float]:
        """
        根據環境機制提供權重調整建議
        """
        regime = regime_info['regime']
        is_big_lotto = 'BIG' in lottery_type or '大樂透' in lottery_type
        
        if regime == 'ORDER':
            # 規律期：強化趨勢與馬可夫
            return {
                'markov': 1.4,
                'trend_predict': 1.3,
                'fourier_main': 1.25,
                'smart_markov_predict': 1.35,
                'lag_reversion': 0.4  # 規律期，追號失效
            }
        elif regime == 'CHAOS':
            # 紊亂期：強化遺漏回歸與熵值平衡
            return {
                'lag_reversion': 1.6,
                'entropy_predict': 1.5,
                'anomaly_detection': 1.4,
                'deviation_predict': 1.3,
                'markov': 0.6,
                'trend_predict': 0.7
            }
        elif regime == 'TRANSITION':
            # 過渡期：強化通用集成與共識
            return {
                'ensemble': 1.3,
                'consensus': 1.2,
                'adaptive_weight': 1.2,
                'statistical_predict': 1.1
            }
        else:
            return {}
