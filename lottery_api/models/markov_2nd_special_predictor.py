#!/usr/bin/env python3
"""
第二區 2階 Markov Chain 預測器
基於統計驗證的務實優化

改進點:
1. P(next | last_2) 而非 P(next | last_1)
2. 加入「多久沒出現」特徵
3. 避免過度工程化
"""
from collections import Counter, defaultdict
from typing import List, Dict, Tuple
import numpy as np


class MarkovChain2ndOrderPredictor:
    """2階 Markov Chain 第二區預測器"""
    
    def __init__(self):
        self.min_special = 1
        self.max_special = 8
    
    def predict(self, history: List[Dict]) -> int:
        """
        預測第二區號碼
        
        Args:
            history: 歷史開獎記錄（降序，最新在前）
            
        Returns:
            預測的第二區號碼 (1-8)
        """
        if not history or len(history) < 3:
            return self._fallback_predict()
        
        # 獲取最近兩期的第二區號碼
        last_1 = history[0].get('special', history[0].get('special_number'))
        last_2 = history[1].get('special', history[1].get('special_number'))
        
        if not last_1 or not last_2:
            return self._fallback_predict()
        
        # 1. 計算2階轉移機率 P(next | last_2, last_1)
        transition_2nd = self._calculate_2nd_order_transition(history, last_2, last_1)
        
        # 2. 計算1階轉移機率 P(next | last_1) 作為備用
        transition_1st = self._calculate_1st_order_transition(history, last_1)
        
        # 3. 計算基礎頻率
        base_freq = self._calculate_base_frequency(history[:50])
        
        # 4. 計算「間隔」特徵（多久沒出現）
        gap_scores = self._calculate_gap_scores(history)
        
        # 5. 綜合機率（加權平均）
        probs = {}
        for num in range(1, 9):
            # 權重分配:
            # - 2階轉移: 40%（如果有足夠數據）
            # - 1階轉移: 30%
            # - 基礎頻率: 20%
            # - 間隔特徵: 10%
            
            p_2nd = transition_2nd.get(num, 0)
            p_1st = transition_1st.get(num, 0)
            p_base = base_freq.get(num, 0)
            p_gap = gap_scores.get(num, 0)
            
            # 如果2階轉移數據充足，增加權重
            if sum(transition_2nd.values()) >= 5:  # 至少5次歷史轉移
                probs[num] = 0.4 * p_2nd + 0.3 * p_1st + 0.2 * p_base + 0.1 * p_gap
            else:
                # 數據不足，降低2階權重
                probs[num] = 0.2 * p_2nd + 0.4 * p_1st + 0.3 * p_base + 0.1 * p_gap
        
        # 正規化
        total = sum(probs.values())
        if total > 0:
            probs = {k: v / total for k, v in probs.items()}
        
        # 選擇機率最高的號碼
        if not probs:
            return self._fallback_predict()
        
        best_num = max(probs.items(), key=lambda x: x[1])[0]
        return best_num
    
    def predict_with_confidence(self, history: List[Dict]) -> Dict:
        """
        預測並返回信心度
        
        Returns:
            {
                'special': int,
                'confidence': float,
                'probabilities': dict,
                'method': str,
                'transition_support': int
            }
        """
        if not history or len(history) < 3:
            return {
                'special': self._fallback_predict(),
                'confidence': 0.125,
                'probabilities': {i: 1/8 for i in range(1, 9)},
                'method': 'fallback_uniform',
                'transition_support': 0
            }
        
        last_1 = history[0].get('special', history[0].get('special_number'))
        last_2 = history[1].get('special', history[1].get('special_number'))
        
        if not last_1 or not last_2:
            return {
                'special': self._fallback_predict(),
                'confidence': 0.125,
                'probabilities': {i: 1/8 for i in range(1, 9)},
                'method': 'fallback_uniform',
                'transition_support': 0
            }
        
        # 計算各成分
        transition_2nd = self._calculate_2nd_order_transition(history, last_2, last_1)
        transition_1st = self._calculate_1st_order_transition(history, last_1)
        base_freq = self._calculate_base_frequency(history[:50])
        gap_scores = self._calculate_gap_scores(history)
        
        # 計算支持度
        support = sum(transition_2nd.values())
        
        # 綜合機率
        probs = {}
        for num in range(1, 9):
            p_2nd = transition_2nd.get(num, 0)
            p_1st = transition_1st.get(num, 0)
            p_base = base_freq.get(num, 0)
            p_gap = gap_scores.get(num, 0)
            
            if support >= 5:
                probs[num] = 0.4 * p_2nd + 0.3 * p_1st + 0.2 * p_base + 0.1 * p_gap
            else:
                probs[num] = 0.2 * p_2nd + 0.4 * p_1st + 0.3 * p_base + 0.1 * p_gap
        
        total = sum(probs.values())
        if total > 0:
            probs = {k: v / total for k, v in probs.items()}
        
        best_num = max(probs.items(), key=lambda x: x[1])[0]
        confidence = probs[best_num]
        
        return {
            'special': best_num,
            'confidence': confidence,
            'probabilities': probs,
            'method': 'markov_2nd_order',
            'transition_support': support
        }
    
    def _calculate_2nd_order_transition(self, history: List[Dict], 
                                       state_2: int, state_1: int) -> Dict[int, float]:
        """
        計算2階轉移機率 P(next | state_2, state_1)
        """
        transitions = Counter()
        
        # 遍歷歷史，找出所有 (state_2, state_1) -> next 的轉移
        for i in range(len(history) - 2):
            s2 = history[i+2].get('special', history[i+2].get('special_number'))
            s1 = history[i+1].get('special', history[i+1].get('special_number'))
            next_state = history[i].get('special', history[i].get('special_number'))
            
            if s2 == state_2 and s1 == state_1 and next_state:
                transitions[next_state] += 1
        
        # 轉換為機率
        total = sum(transitions.values())
        if total > 0:
            probs = {k: v / total for k, v in transitions.items()}
        else:
            probs = {}
        
        # 平滑處理
        for num in range(1, 9):
            if num not in probs:
                probs[num] = 0.01
        
        # 重新正規化
        total = sum(probs.values())
        if total > 0:
            probs = {k: v / total for k, v in probs.items()}
        
        return probs
    
    def _calculate_1st_order_transition(self, history: List[Dict], 
                                       current_state: int) -> Dict[int, float]:
        """計算1階轉移機率 P(next | current_state)"""
        transitions = Counter()
        
        for i in range(len(history) - 1):
            curr = history[i].get('special', history[i].get('special_number'))
            next_state = history[i-1].get('special', history[i-1].get('special_number')) if i > 0 else None
            
            # 修正: 應該是 history[i] 是當前, history[i-1] 是下一個（降序）
            # 實際上應該反過來
            if i < len(history) - 1:
                curr = history[i+1].get('special', history[i+1].get('special_number'))
                next_state = history[i].get('special', history[i].get('special_number'))
                
                if curr == current_state and next_state:
                    transitions[next_state] += 1
        
        total = sum(transitions.values())
        if total > 0:
            probs = {k: v / total for k, v in transitions.items()}
        else:
            probs = {}
        
        for num in range(1, 9):
            if num not in probs:
                probs[num] = 0.01
        
        total = sum(probs.values())
        if total > 0:
            probs = {k: v / total for k, v in probs.items()}
        
        return probs
    
    def _calculate_base_frequency(self, history: List[Dict]) -> Dict[int, float]:
        """計算基礎頻率"""
        freq = Counter()
        for d in history:
            special = d.get('special', d.get('special_number'))
            if special:
                freq[special] += 1
        
        total = sum(freq.values())
        if total > 0:
            probs = {k: v / total for k, v in freq.items()}
        else:
            probs = {}
        
        for num in range(1, 9):
            if num not in probs:
                probs[num] = 0.01
        
        total = sum(probs.values())
        if total > 0:
            probs = {k: v / total for k, v in probs.items()}
        
        return probs
    
    def _calculate_gap_scores(self, history: List[Dict]) -> Dict[int, float]:
        """
        計算「間隔」分數
        多久沒出現的號碼得分較高
        """
        gaps = {i: 0 for i in range(1, 9)}
        
        # 記錄每個號碼最後出現的位置
        for i, d in enumerate(history):
            special = d.get('special', d.get('special_number'))
            if special and special in gaps:
                if gaps[special] == 0:  # 第一次遇到
                    gaps[special] = i
        
        # 轉換為分數（間隔越大，分數越高）
        max_gap = max(gaps.values()) if gaps else 1
        scores = {}
        
        for num, gap in gaps.items():
            if gap == 0:
                gap = len(history)  # 從未出現，設為最大
            # 正規化到 [0, 1]
            scores[num] = gap / max_gap if max_gap > 0 else 0
        
        # 正規化
        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}
        
        return scores
    
    def _fallback_predict(self) -> int:
        """備用預測"""
        import random
        return random.randint(1, 8)


# 測試
if __name__ == '__main__':
    import sys
    import os
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
    
    from database import DatabaseManager
    
    print("=" * 80)
    print("測試 2階 Markov Chain 第二區預測器")
    print("=" * 80)
    
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    if not history:
        print("❌ 無法獲取歷史數據")
        sys.exit(1)
    
    predictor = MarkovChain2ndOrderPredictor()
    
    print(f"\n使用歷史數據: {len(history)} 期")
    print(f"最新期數: {history[0]['draw']}")
    print(f"最近兩期第二區: {history[1].get('special')} -> {history[0].get('special')}")
    print()
    
    # 生成5個預測
    for i in range(5):
        result = predictor.predict_with_confidence(history)
        
        print(f"預測 {i+1}:")
        print(f"  預測第二區: {result['special']:02d}")
        print(f"  信心度: {result['confidence']:.3f}")
        print(f"  2階轉移支持度: {result['transition_support']} 次歷史轉移")
        print(f"  機率分布: {', '.join([f'{k}:{v:.2f}' for k, v in sorted(result['probabilities'].items())])}")
        print()
    
    print("=" * 80)
