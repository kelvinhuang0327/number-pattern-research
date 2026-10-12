import numpy as np
import pandas as pd
from scipy import stats
import sqlite3
import os

class ThreeStarInferenceEngine:
    """
    3星彩推理與期望值優化引擎 (Step 7-9 實作)
    """
    def __init__(self, history_df):
        self.history = history_df
        self.models = {}
        
    def get_frequency_scores(self, window=100):
        """模型 A: 頻率分數"""
        recent = self.history.tail(window)
        scores = np.zeros((3, 10))
        for i, col in enumerate(['Num1', 'Num2', 'Num3']):
            counts = recent[col].value_counts().reindex(range(10), fill_value=0)
            scores[i] = counts.values / window
        return scores

    def get_markov_scores(self):
        """模型 B: 一階馬可夫分數 (捕捉號碼連續性)"""
        if len(self.history) < 10:
            return np.ones((3, 10)) * 0.1
        
        last_nums = self.history.iloc[-1][['Num1', 'Num2', 'Num3']].values
        scores = np.zeros((3, 10))
        
        for i, col in enumerate(['Num1', 'Num2', 'Num3']):
            transitions = []
            values = self.history[col].values
            for j in range(len(values)-1):
                if values[j] == last_nums[i]:
                    transitions.append(values[j+1])
            
            if transitions:
                counts = np.bincount(transitions, minlength=10)
                scores[i] = counts / len(transitions)
            else:
                scores[i] = np.ones(10) * 0.1
        return scores

    def ensemble_inference(self):
        """集成學習推理"""
        f_scores = self.get_frequency_scores()
        m_scores = self.get_markov_scores()
        
        # 動態權重 (範例配置)
        w_f = 0.4
        w_m = 0.6
        
        final_probs = (f_scores * w_f) + (m_scores * w_m)
        # 歸一化
        final_probs = final_probs / final_probs.sum(axis=1)[:, None]
        
        return final_probs

    def generate_recommendation(self, odds=500, bankroll=1000):
        """期望值優化與投注建議"""
        probs = self.ensemble_inference()
        
        # 尋找聯合機率最高的前 5 名
        # 簡化處理: 每位取 Prob 最高的
        recommendation = []
        for i in range(3):
            best_num = np.argmax(probs[i])
            p = probs[i][best_num]
            recommendation.append((best_num, p))
            
        combined_p = np.prod([p for _, p in recommendation])
        ev = (combined_p * odds) - (1 * (1 - combined_p))
        
        # 凱利準則
        b = odds - 1
        kelly_f = (b * combined_p - (1 - combined_p)) / b if combined_p > (1/odds) else 0
        
        print("\n--- [STEP 9] 智慧投注建議 ---")
        print(f"預測號碼: {''.join([str(n) for n, _ in recommendation])}")
        print(f"預估勝率: {combined_p:.6f} (理論隨機: 0.001000)")
        print(f"單注期望值 (EV): {ev:.4f}")
        print(f"建議投注比例 (Kelly): {kelly_f * 100:.2f}% (建議金額: {bankroll * kelly_f:.1f})")
        
        return recommendation

if __name__ == "__main__":
    # 生成模擬數據測試引擎
    from system_core import ThreeStarAnalyzer
    analyzer = ThreeStarAnalyzer()
    df = analyzer.generate_synthetic_data(n_draws=1000, bias_type='seq')
    
    engine = ThreeStarInferenceEngine(df)
    engine.generate_recommendation()
