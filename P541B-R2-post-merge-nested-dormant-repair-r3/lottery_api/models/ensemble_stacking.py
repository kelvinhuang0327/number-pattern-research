#!/usr/bin/env python3
"""
Ensemble Stacking 整合框架
結合多個預測模型的輸出，產生最終預測
"""
import sys
import os
import numpy as np
from collections import Counter, defaultdict

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.unified_predictor import UnifiedPredictionEngine
from models.deep_feature_extractor import DeepFeatureExtractor
from config import lottery_config

try:
    from models.attention_lstm_torch import AttentionLSTMPredictor
    LSTM_AVAILABLE = True
except:
    LSTM_AVAILABLE = False

class EnsembleStackingPredictor:
    """
    Ensemble Stacking 預測器
    整合多個基礎模型的預測結果
    """
    
    def __init__(self):
        self.base_engine = UnifiedPredictionEngine()
        self.feature_extractor = DeepFeatureExtractor(min_num=1, max_num=38)
        
        if LSTM_AVAILABLE:
            # ⚠️ Bi-LSTM 已被驗證無效 (Edge 為負)，暫時停用
            # 保留原始 Attention LSTM，但默認不載入
            self.lstm_predictor = None
        else:
            self.lstm_predictor = None
        
        # 基礎模型列表（優化版：只使用 Top 3）
        # 根據 2025 回測結果：Markov (16.10%), Bayesian (12.71%), Trend (12.71%)
        # ⚠️ ARIMA (1,0,0) 已被 500 期獨立驗證拒絕 (Edge -3.46% ~ -3.86%)
        self.base_models = {
            'markov': {
                'func': self.base_engine.markov_predict,
                'weight': 1.5  # 最佳方法，給予最高權重
            },
            'bayesian': {
                'func': self.base_engine.bayesian_predict,
                'weight': 1.2  # 次佳方法
            },
            'trend': {
                'func': self.base_engine.trend_predict,
                'weight': 1.0  # 基準權重
            }
            # ARIMA 已移除 - 500 期回測 Edge 為負 (-3.46% ~ -3.86%)
        }
    
    def train_lstm(self, history, epochs=30, num_balls=38):
        """訓練內置的 LSTM 模型"""
        if LSTM_AVAILABLE:
            # 始終根據當前 ball count 重建 predictor
            self.lstm_predictor = AttentionLSTMPredictor(num_balls=num_balls, hidden_size=64)
            self.lstm_predictor.train(history, epochs=epochs, verbose=0)
            return True
        return False

    def predict_with_features(self, history, lottery_rules, use_lstm=False):
        """
        使用深度特徵增強的預測
        """
        pick_count = lottery_rules.get('pickCount', 6)
        max_num = lottery_rules.get('maxNumber', 38)
        
        # 1. 提取深度特徵
        deep_features = self.feature_extractor.extract_all_features(history)
        
        # 2. 收集所有基礎模型的預測
        model_predictions = {}
        number_votes = Counter()
        special_votes = Counter()
        
        for name, model_info in self.base_models.items():
            try:
                func = model_info['func']
                weight = model_info['weight']
                
                result = func(history, lottery_rules)
                model_predictions[name] = result
                
                confidence = result.get('confidence', 0.5)
                vote_power = confidence * weight
                
                for num in result['numbers']:
                    number_votes[num] += vote_power
                
                if 'special' in result:
                    special_votes[result['special']] += vote_power
            except:
                continue
        
        # 3. LSTM 預測（如果可用且已針對當前 lottery 訓練）
        if use_lstm and self.lstm_predictor:
            try:
                # 確認 LSTM 已經針對正確的球數進行訓練
                if self.lstm_predictor.num_balls == max_num and self.lstm_predictor.is_trained:
                    lstm_result = self.lstm_predictor.predict(history, n_numbers=pick_count)
                    if lstm_result:
                        model_predictions['lstm'] = {'numbers': lstm_result}
                        for num in lstm_result:
                            number_votes[num] += 0.6 * 1.5 # 給予 LSTM 較高權重
            except Exception as e:
                print(f"LSTM Prediction Error: {e}")
        
        # 4. 應用深度特徵調整
        number_votes = self._apply_feature_adjustments(number_votes, deep_features, pick_count, max_num)
        
        # 5. 選擇最終號碼
        final_numbers = sorted([n for n, _ in number_votes.most_common(pick_count)])
        
        # 6. 選擇特別號
        final_special = special_votes.most_common(1)[0][0] if special_votes else 1
        
        # 7. 計算信心度
        top_votes = [v for _, v in number_votes.most_common(pick_count)]
        avg_confidence = sum(top_votes) / len(top_votes) if top_votes else 0.5
        normalized_confidence = min(0.95, avg_confidence / (len(self.base_models) + 1))
        
        return {
            'numbers': final_numbers,
            'special': final_special,
            'confidence': normalized_confidence,
            'method': 'ensemble_stacking',
            'feature_scores': self._summarize_features(deep_features),
            'model_votes': {k: len(v['numbers']) for k, v in model_predictions.items()}
        }
    
    def _apply_feature_adjustments(self, number_votes, deep_features, pick_count, max_num):
        """應用深度特徵調整號碼權重"""
        adjusted_votes = Counter(number_votes)
        
        cons_patterns = deep_features['consecutive_patterns']
        for pair in cons_patterns.get('hot_pairs', []):
            if pair[0] in adjusted_votes and pair[1] in adjusted_votes:
                adjusted_votes[pair[0]] *= 1.2
                adjusted_votes[pair[1]] *= 1.2
        
        tail_dist = deep_features['tail_distribution']
        current_tails = Counter()
        for num in [n for n, _ in adjusted_votes.most_common(pick_count)]:
            current_tails[num % 10] += 1
        
        for tail, count in current_tails.items():
            if count >= 3:
                for num in adjusted_votes:
                    if num % 10 == tail:
                        adjusted_votes[num] *= 0.8
        
        for tail in tail_dist.get('missing_tails', []):
            for num in adjusted_votes:
                if num % 10 == tail:
                    adjusted_votes[num] *= 1.3
        
        zone_heat = deep_features['zone_heat_cycles']
        # 自動適配區域劃分
        z_size = max_num // 4
        zones = {
            1: range(1, z_size + 1),
            2: range(z_size + 1, z_size * 2 + 1),
            3: range(z_size * 2 + 1, z_size * 3 + 1),
            4: range(z_size * 3 + 1, max_num + 1)
        }
        
        for zone_id in zone_heat.get('cold_zones', []):
            if zone_id in zones:
                for num in zones[zone_id]:
                    if num in adjusted_votes:
                        adjusted_votes[num] *= 1.4
        
        return adjusted_votes
    
    def _summarize_features(self, deep_features):
        return {
            'consecutive_score': len(deep_features['consecutive_patterns'].get('hot_pairs', [])),
            'tail_balance': deep_features['tail_distribution'].get('tail_balance_score', 0),
            'cold_zones': deep_features['zone_heat_cycles'].get('cold_zones', []),
            'avg_gap': deep_features['number_gaps'].get('avg_gap', 0)
        }

if __name__ == '__main__':
    from database import DatabaseManager
    from common import get_lottery_rules
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    
    ensemble = EnsembleStackingPredictor()
    result = ensemble.predict_with_features(history, rules, use_lstm=False)
    print(f"Prediction: {result['numbers']}")
