#!/usr/bin/env python3
"""
簡化的第一區 Bayesian 預測器
基於統計驗證的教訓

移除:
1. ❌ 無連號約束（歷史僅24%無連號）
2. ❌ 冷門號加權（無數據支持）

保留:
3. ✅ 基礎 Bayesian 邏輯（先驗 × 似然度）
4. ✅ 歷史窗口多樣性
"""
import numpy as np
from collections import Counter
from typing import List, Dict
import random


class SimplifiedBayesianPredictor:
    """簡化的貝葉斯預測器"""
    
    def __init__(self):
        self.min_num = 1
        self.max_num = 38
        self.pick_count = 6
    
    def predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        簡化的貝葉斯預測
        
        Args:
            history: 歷史開獎記錄
            lottery_rules: 彩票規則
            
        Returns:
            預測結果字典
        """
        if len(history) < 50:
            return self._fallback_predict(lottery_rules)
        
        # 1. 計算先驗分布（基於頻率，不加權）
        prior = self._calculate_prior(history)
        
        # 2. 計算似然度（基於趨勢）
        likelihood = self._calculate_likelihood(history)
        
        # 3. 計算後驗分布
        posterior = {}
        for num in range(self.min_num, self.max_num + 1):
            posterior[num] = prior.get(num, 0) * likelihood.get(num, 0)
        
        # 正規化
        total = sum(posterior.values())
        if total > 0:
            posterior = {k: v / total for k, v in posterior.items()}
        
        # 4. 加權抽樣生成候選組合
        selected = self._weighted_sample(posterior, self.pick_count)
        
        # 5. 預測第二區（使用2階Markov）
        from models.markov_2nd_special_predictor import MarkovChain2ndOrderPredictor
        special_predictor = MarkovChain2ndOrderPredictor()
        special_result = special_predictor.predict_with_confidence(history)
        
        return {
            'numbers': sorted([int(n) for n in selected]),
            'special': int(special_result['special']),
            'confidence': self._calculate_confidence(selected, posterior),
            'method': 'simplified_bayesian',
            'special_confidence': special_result['confidence']
        }
    
    def _calculate_prior(self, history: List[Dict]) -> Dict[int, float]:
        """
        計算先驗分布（基於多窗口頻率）
        使用多個歷史窗口，增加穩健性
        """
        # 使用多個窗口: 50, 100, 200期
        windows = [50, 100, 200]
        window_weights = [0.5, 0.3, 0.2]  # 近期權重較高
        
        combined_prior = Counter()
        
        for window, weight in zip(windows, window_weights):
            freq = Counter()
            for d in history[:min(window, len(history))]:
                numbers = d.get('numbers', [])
                freq.update(numbers)
            
            # 加權累加
            for num, count in freq.items():
                combined_prior[num] += count * weight
        
        # Laplace smoothing
        prior = {}
        total = sum(combined_prior.values())
        for num in range(self.min_num, self.max_num + 1):
            prior[num] = (combined_prior.get(num, 0) + 1) / (total + 38)
        
        return prior
    
    def _calculate_likelihood(self, history: List[Dict]) -> Dict[int, float]:
        """計算似然度（基於近期趨勢）"""
        # 使用最近30期計算趨勢
        recent_freq = Counter()
        for d in history[:30]:
            numbers = d.get('numbers', [])
            recent_freq.update(numbers)
        
        likelihood = {}
        total = sum(recent_freq.values())
        
        for num in range(self.min_num, self.max_num + 1):
            likelihood[num] = (recent_freq.get(num, 0) + 0.5) / (total + 19)
        
        return likelihood
    
    def _weighted_sample(self, posterior: Dict[int, float], k: int) -> List[int]:
        """加權抽樣（無放回）"""
        selected = []
        remaining_nums = list(range(self.min_num, self.max_num + 1))
        remaining_weights = [posterior.get(n, 0) for n in remaining_nums]
        
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
    
    def _calculate_confidence(self, combo: List[int], posterior: Dict[int, float]) -> float:
        """計算預測信心度"""
        combo_posterior = sum(posterior.get(n, 0) for n in combo) / len(combo)
        return min(0.95, combo_posterior * 2)
    
    def _fallback_predict(self, lottery_rules: Dict) -> Dict:
        """備用預測"""
        numbers = random.sample(range(self.min_num, self.max_num + 1), self.pick_count)
        return {
            'numbers': sorted(numbers),
            'special': random.randint(1, 8),
            'confidence': 0.3,
            'method': 'fallback_random'
        }


# 測試
if __name__ == '__main__':
    import sys
    import os
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
    
    from database import DatabaseManager
    from common import get_lottery_rules
    
    print("=" * 80)
    print("測試簡化的 Bayesian 預測器")
    print("=" * 80)
    
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    history = db.get_all_draws(lottery_type='POWER_LOTTO')
    rules = get_lottery_rules('POWER_LOTTO')
    
    if not history:
        print("❌ 無法獲取歷史數據")
        sys.exit(1)
    
    predictor = SimplifiedBayesianPredictor()
    
    print(f"\n使用歷史數據: {len(history)} 期")
    print(f"最新期數: {history[0]['draw']}\n")
    
    # 生成5個預測樣本
    for i in range(5):
        result = predictor.predict(history, rules)
        
        print(f"預測 {i+1}:")
        print(f"  第一區: {', '.join([f'{n:02d}' for n in result['numbers']])}")
        print(f"  第二區: {result['special']:02d}")
        print(f"  第一區信心度: {result['confidence']:.3f}")
        print(f"  第二區信心度: {result.get('special_confidence', 0):.3f}")
        print()
    
    print("=" * 80)
