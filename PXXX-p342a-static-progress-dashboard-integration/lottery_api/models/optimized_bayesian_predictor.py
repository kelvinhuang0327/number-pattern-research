#!/usr/bin/env python3
"""
優化的 Bayesian 預測方法
基於 115000005 期回溯分析的建議實作

改進重點：
1. 增加冷門號先驗權重
2. 增加「無連號」組合的採樣機率
3. 異常模式感知的後驗調整
"""
import numpy as np
from collections import Counter
from typing import List, Dict, Set
import random


class OptimizedBayesianPredictor:
    """優化的貝葉斯預測器"""
    
    def __init__(self):
        self.min_num = 1
        self.max_num = 38
        self.pick_count = 6
    
    def predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        優化的貝葉斯預測
        
        Args:
            history: 歷史開獎記錄
            lottery_rules: 彩票規則
            
        Returns:
            預測結果字典
        """
        if len(history) < 50:
            return self._fallback_predict(lottery_rules)
        
        # 1. 計算優化的先驗分布
        prior = self._calculate_optimized_prior(history)
        
        # 2. 計算似然度
        likelihood = self._calculate_likelihood(history)
        
        # 3. 計算後驗分布
        posterior = {}
        for num in range(self.min_num, self.max_num + 1):
            posterior[num] = prior.get(num, 0) * likelihood.get(num, 0)
        
        # 正規化
        total = sum(posterior.values())
        if total > 0:
            posterior = {k: v / total for k, v in posterior.items()}
        
        # 4. 生成候選組合
        candidates = self._generate_candidates(posterior, n_candidates=200)
        
        # 5. 選擇最佳組合（考慮異常模式）
        best_combo = self._select_best_with_anomaly_awareness(candidates, history)
        
        # 6. 預測第二區
        from improved_special_predictor import ImprovedSpecialPredictor
        special_predictor = ImprovedSpecialPredictor()
        special_result = special_predictor.predict_with_confidence(history, best_combo)
        
        return {
            'numbers': sorted([int(n) for n in best_combo]),
            'special': int(special_result['special']),
            'confidence': self._calculate_confidence(best_combo, posterior),
            'method': 'optimized_bayesian',
            'special_confidence': special_result['confidence']
        }
    
    def _calculate_optimized_prior(self, history: List[Dict]) -> Dict[int, float]:
        """
        計算優化的先驗分布
        改進: 給予冷門號更高權重
        """
        # 基礎頻率統計（近100期）
        freq = Counter()
        for d in history[:100]:
            numbers = d.get('numbers', [])
            freq.update(numbers)
        
        # 計算期望值
        expected_freq = 100 * 6 / 38
        
        # 初始化先驗
        prior = {}
        
        for num in range(self.min_num, self.max_num + 1):
            actual_freq = freq.get(num, 0)
            
            # 基礎先驗（基於頻率）
            base_prior = (actual_freq + 1) / (100 + 38)  # Laplace smoothing
            
            # 冷門號加權
            if actual_freq < expected_freq * 0.5:
                # 冷門號（頻率低於期望值50%）增加先驗權重
                cold_bonus = 1.3
                prior[num] = base_prior * cold_bonus
            elif actual_freq < expected_freq * 0.8:
                # 偏冷號（頻率低於期望值80%）適度增加
                prior[num] = base_prior * 1.1
            else:
                prior[num] = base_prior
        
        # 正規化
        total = sum(prior.values())
        if total > 0:
            prior = {k: v / total for k, v in prior.items()}
        
        return prior
    
    def _calculate_likelihood(self, history: List[Dict]) -> Dict[int, float]:
        """計算似然度（基於趨勢）"""
        # 使用最近30期計算趨勢
        recent_freq = Counter()
        for d in history[:30]:
            numbers = d.get('numbers', [])
            recent_freq.update(numbers)
        
        # 轉換為似然度
        likelihood = {}
        total = sum(recent_freq.values())
        
        for num in range(self.min_num, self.max_num + 1):
            likelihood[num] = (recent_freq.get(num, 0) + 0.5) / (total + 19)  # Smoothing
        
        return likelihood
    
    def _generate_candidates(self, posterior: Dict[int, float], n_candidates: int = 200) -> List[List[int]]:
        """
        生成候選組合
        改進: 增加無連號組合的生成機率
        """
        candidates = []
        numbers = list(range(self.min_num, self.max_num + 1))
        weights = [posterior.get(n, 0) for n in numbers]
        
        # 正常候選組合（70%）
        normal_count = int(n_candidates * 0.7)
        for _ in range(normal_count):
            selected = self._weighted_sample(numbers, weights, self.pick_count)
            candidates.append(selected)
        
        # 無連號候選組合（30%）
        no_consecutive_count = n_candidates - normal_count
        for _ in range(no_consecutive_count):
            selected = self._generate_no_consecutive(numbers, weights)
            if selected:
                candidates.append(selected)
        
        return candidates
    
    def _weighted_sample(self, numbers: List[int], weights: List[float], k: int) -> List[int]:
        """加權抽樣（無放回）"""
        selected = []
        remaining_nums = numbers.copy()
        remaining_weights = weights.copy()
        
        for _ in range(k):
            if not remaining_nums:
                break
            
            # 正規化權重
            total_weight = sum(remaining_weights)
            if total_weight == 0:
                probs = [1/len(remaining_nums)] * len(remaining_nums)
            else:
                probs = [w / total_weight for w in remaining_weights]
            
            # 加權選擇
            idx = np.random.choice(len(remaining_nums), p=probs)
            selected.append(remaining_nums[idx])
            
            # 移除已選號碼
            remaining_nums.pop(idx)
            remaining_weights.pop(idx)
        
        return sorted(selected)
    
    def _generate_no_consecutive(self, numbers: List[int], weights: List[float]) -> List[int]:
        """生成無連號組合"""
        selected = []
        remaining_nums = numbers.copy()
        remaining_weights = weights.copy()
        
        for _ in range(self.pick_count):
            if not remaining_nums:
                break
            
            # 過濾掉與已選號碼相鄰的號碼
            filtered_nums = []
            filtered_weights = []
            
            for num, weight in zip(remaining_nums, remaining_weights):
                is_consecutive = False
                for s in selected:
                    if abs(num - s) == 1:
                        is_consecutive = True
                        break
                
                if not is_consecutive:
                    filtered_nums.append(num)
                    filtered_weights.append(weight)
            
            if not filtered_nums:
                # 如果無法避免連號，隨機選擇
                filtered_nums = remaining_nums
                filtered_weights = remaining_weights
            
            # 加權選擇
            total_weight = sum(filtered_weights)
            if total_weight == 0:
                probs = [1/len(filtered_nums)] * len(filtered_nums)
            else:
                probs = [w / total_weight for w in filtered_weights]
            
            idx = np.random.choice(len(filtered_nums), p=probs)
            selected_num = filtered_nums[idx]
            selected.append(selected_num)
            
            # 從剩餘列表中移除
            orig_idx = remaining_nums.index(selected_num)
            remaining_nums.pop(orig_idx)
            remaining_weights.pop(orig_idx)
        
        return sorted(selected) if len(selected) == self.pick_count else None
    
    def _select_best_with_anomaly_awareness(self, candidates: List[List[int]], 
                                           history: List[Dict]) -> List[int]:
        """
        選擇最佳組合（考慮異常模式）
        """
        if not candidates:
            return random.sample(range(self.min_num, self.max_num + 1), self.pick_count)
        
        # 評分每個候選組合
        scores = []
        for combo in candidates:
            score = self._score_candidate(combo, history)
            scores.append(score)
        
        # 選擇得分最高的
        best_idx = np.argmax(scores)
        return candidates[best_idx]
    
    def _score_candidate(self, combo: List[int], history: List[Dict]) -> float:
        """評分候選組合"""
        score = 0.0
        
        # 1. 奇偶比評分（偏好 2:4, 3:3, 4:2，但也接受 1:5, 5:1）
        odd_count = sum(1 for n in combo if n % 2 == 1)
        if odd_count in [2, 3, 4]:
            score += 10
        elif odd_count in [1, 5]:
            score += 5  # 異常模式也給予一定分數
        
        # 2. 區間分布評分
        zone_counts = [0, 0, 0]
        for n in combo:
            if n <= 13:
                zone_counts[0] += 1
            elif n <= 25:
                zone_counts[1] += 1
            else:
                zone_counts[2] += 1
        
        if all(c >= 1 for c in zone_counts):
            score += 10
        
        # 3. 連號評分（偏好少連號或無連號）
        consecutive_pairs = 0
        for i in range(len(combo) - 1):
            if combo[i+1] - combo[i] == 1:
                consecutive_pairs += 1
        
        if consecutive_pairs == 0:
            score += 8  # 無連號獎勵
        elif consecutive_pairs == 1:
            score += 5
        
        # 4. 和值評分
        total = sum(combo)
        if 85 <= total <= 155:
            score += 5
        
        # 5. 尾數多樣性
        tails = set(n % 10 for n in combo)
        score += len(tails)  # 4-6 種尾數
        
        return score
    
    def _calculate_confidence(self, combo: List[int], posterior: Dict[int, float]) -> float:
        """計算預測信心度"""
        # 基於後驗機率的信心度
        combo_posterior = sum(posterior.get(n, 0) for n in combo) / len(combo)
        return min(0.95, combo_posterior * 2)  # 縮放到合理範圍
    
    def _fallback_predict(self, lottery_rules: Dict) -> Dict:
        """備用預測"""
        numbers = random.sample(range(self.min_num, self.max_num + 1), self.pick_count)
        return {
            'numbers': sorted(numbers),
            'special': random.randint(1, 8),
            'confidence': 0.3,
            'method': 'fallback_random'
        }


# 測試函數
if __name__ == '__main__':
    import sys
    import os
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
    
    from database import DatabaseManager
    from common import get_lottery_rules
    
    print("=" * 80)
    print("測試優化的 Bayesian 預測器")
    print("=" * 80)
    
    # 載入數據
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    history = db.get_all_draws(lottery_type='POWER_LOTTO')
    rules = get_lottery_rules('POWER_LOTTO')
    
    if not history:
        print("❌ 無法獲取歷史數據")
        sys.exit(1)
    
    predictor = OptimizedBayesianPredictor()
    
    # 生成5個預測樣本
    print(f"\n使用歷史數據: {len(history)} 期")
    print(f"最新期數: {history[0]['draw']}\n")
    
    for i in range(5):
        result = predictor.predict(history, rules)
        
        print(f"預測 {i+1}:")
        print(f"  第一區: {', '.join([f'{n:02d}' for n in result['numbers']])}")
        print(f"  第二區: {result['special']:02d}")
        print(f"  信心度: {result['confidence']:.3f}")
        print(f"  第二區信心度: {result.get('special_confidence', 0):.3f}")
        print()
    
    print("=" * 80)
