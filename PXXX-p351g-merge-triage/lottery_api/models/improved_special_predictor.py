#!/usr/bin/env python3
"""
改進的第二區號碼預測器
基於 115000005 期回溯分析的建議實作

改進重點：
1. 排除近3期重複（降權而非完全排除）
2. 考慮第一區奇偶比，調整第二區機率
3. 使用 Markov Chain 轉移機率
"""
from collections import Counter
from typing import List, Dict
import numpy as np


class ImprovedSpecialPredictor:
    """改進的第二區號碼預測器"""
    
    def __init__(self):
        self.min_special = 1
        self.max_special = 8
    
    def predict(self, history: List[Dict], first_area_prediction: List[int] = None) -> int:
        """
        預測第二區號碼
        
        Args:
            history: 歷史開獎記錄（降序，最新在前）
            first_area_prediction: 第一區預測結果（可選）
            
        Returns:
            預測的第二區號碼 (1-8)
        """
        if not history or len(history) < 10:
            return self._fallback_predict()
        
        # 1. 基礎頻率統計（近30期）
        freq = Counter()
        for d in history[:30]:
            special = d.get('special', d.get('special_number'))
            if special:
                freq[special] += 1
        
        # 轉換為機率分布
        probs = {i: freq.get(i, 0) for i in range(1, 9)}
        total = sum(probs.values())
        if total > 0:
            probs = {k: v / total for k, v in probs.items()}
        else:
            probs = {i: 1/8 for i in range(1, 9)}
        
        # 2. 降低近3期已出現號碼的權重
        recent_3 = []
        for d in history[:3]:
            special = d.get('special', d.get('special_number'))
            if special:
                recent_3.append(special)
        
        for s in set(recent_3):
            probs[s] *= 0.5  # 降權50%
        
        # 3. 考慮第一區奇偶比（保持整體平衡）
        if first_area_prediction:
            even_count = sum(1 for n in first_area_prediction if n % 2 == 0)
            
            # 如果第一區偏偶數（4個以上），第二區偏好奇數
            if even_count >= 4:
                for s in [1, 3, 5, 7]:
                    probs[s] *= 1.5
            
            # 如果第一區偏奇數（4個以上），第二區偏好偶數
            elif even_count <= 2:
                for s in [2, 4, 6, 8]:
                    probs[s] *= 1.5
        
        # 4. Markov Chain 轉移機率加權
        if len(history) >= 2:
            last_special = history[0].get('special', history[0].get('special_number'))
            transition_probs = self._calculate_transition_probs(history, last_special)
            
            # 混合頻率機率和轉移機率 (70% 頻率 + 30% 轉移)
            for s in range(1, 9):
                probs[s] = 0.7 * probs.get(s, 0) + 0.3 * transition_probs.get(s, 0)
        
        # 5. 重新正規化
        total = sum(probs.values())
        if total > 0:
            probs = {k: v / total for k, v in probs.items()}
        
        # 6. 選擇機率最高的號碼
        best_special = max(probs.items(), key=lambda x: x[1])[0]
        
        return best_special
    
    def _calculate_transition_probs(self, history: List[Dict], current_special: int) -> Dict[int, float]:
        """
        計算 Markov Chain 轉移機率
        P(next | current)
        """
        transitions = Counter()
        
        # 統計轉移次數
        for i in range(len(history) - 1):
            curr = history[i].get('special', history[i].get('special_number'))
            next_val = history[i + 1].get('special', history[i + 1].get('special_number'))
            
            if curr == current_special and next_val:
                transitions[next_val] += 1
        
        # 轉換為機率
        total = sum(transitions.values())
        if total > 0:
            probs = {k: v / total for k, v in transitions.items()}
        else:
            # 如果沒有轉移數據，使用均勻分布
            probs = {i: 1/8 for i in range(1, 9)}
        
        # 確保所有號碼都有機率（平滑處理）
        for i in range(1, 9):
            if i not in probs:
                probs[i] = 0.01
        
        return probs
    
    def predict_with_confidence(self, history: List[Dict], 
                               first_area_prediction: List[int] = None) -> Dict:
        """
        預測第二區號碼並返回信心度
        
        Returns:
            {
                'special': int,
                'confidence': float,
                'probabilities': dict,
                'method': str
            }
        """
        if not history or len(history) < 10:
            return {
                'special': self._fallback_predict(),
                'confidence': 0.125,  # 1/8 均勻分布
                'probabilities': {i: 1/8 for i in range(1, 9)},
                'method': 'fallback_uniform'
            }
        
        # 計算完整機率分布
        freq = Counter()
        for d in history[:30]:
            special = d.get('special', d.get('special_number'))
            if special:
                freq[special] += 1
        
        probs = {i: freq.get(i, 0) for i in range(1, 9)}
        total = sum(probs.values())
        if total > 0:
            probs = {k: v / total for k, v in probs.items()}
        else:
            probs = {i: 1/8 for i in range(1, 9)}
        
        # 應用調整
        recent_3 = [d.get('special', d.get('special_number')) 
                   for d in history[:3] if d.get('special') or d.get('special_number')]
        for s in set(recent_3):
            probs[s] *= 0.5
        
        if first_area_prediction:
            even_count = sum(1 for n in first_area_prediction if n % 2 == 0)
            if even_count >= 4:
                for s in [1, 3, 5, 7]:
                    probs[s] *= 1.5
            elif even_count <= 2:
                for s in [2, 4, 6, 8]:
                    probs[s] *= 1.5
        
        # Markov Chain
        if len(history) >= 2:
            last_special = history[0].get('special', history[0].get('special_number'))
            transition_probs = self._calculate_transition_probs(history, last_special)
            for s in range(1, 9):
                probs[s] = 0.7 * probs.get(s, 0) + 0.3 * transition_probs.get(s, 0)
        
        # 正規化
        total = sum(probs.values())
        if total > 0:
            probs = {k: v / total for k, v in probs.items()}
        
        best_special = max(probs.items(), key=lambda x: x[1])[0]
        confidence = probs[best_special]
        
        return {
            'special': best_special,
            'confidence': confidence,
            'probabilities': probs,
            'method': 'improved_markov_balanced'
        }
    
    def _fallback_predict(self) -> int:
        """備用預測（隨機）"""
        import random
        return random.randint(1, 8)


# 測試函數
if __name__ == '__main__':
    import sys
    import os
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
    
    from database import DatabaseManager
    
    print("=" * 80)
    print("測試改進的第二區預測器")
    print("=" * 80)
    
    # 載入歷史數據
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    if not history:
        print("❌ 無法獲取歷史數據")
        sys.exit(1)
    
    # 使用最近的數據測試
    test_history = history[:100]  # 最近100期
    
    predictor = ImprovedSpecialPredictor()
    
    # 測試不同的第一區奇偶比情境
    scenarios = [
        ([2, 4, 6, 8, 10, 12], "極端偶數 (6偶)"),
        ([1, 3, 5, 7, 9, 11], "極端奇數 (6奇)"),
        ([1, 2, 15, 16, 29, 30], "平衡 (3奇3偶)"),
    ]
    
    print(f"\n使用歷史數據: {len(test_history)} 期")
    print(f"最新期數: {test_history[0]['draw']}")
    print()
    
    for first_area, desc in scenarios:
        result = predictor.predict_with_confidence(test_history, first_area)
        
        print(f"情境: {desc}")
        print(f"  第一區: {first_area}")
        print(f"  預測第二區: {result['special']:02d}")
        print(f"  信心度: {result['confidence']:.3f}")
        print(f"  機率分布: {', '.join([f'{k}:{v:.2f}' for k, v in sorted(result['probabilities'].items())])}")
        print()
    
    print("=" * 80)
