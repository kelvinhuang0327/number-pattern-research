#!/usr/bin/env python3
"""
統一 ML 預測器 (Unified ML Predictor)
整合 LSTM、Transformer、Ensemble Stacking 與深度特徵
"""
import sys
import os
import numpy as np
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.deep_feature_extractor import DeepFeatureExtractor
from models.ensemble_stacking import EnsembleStackingPredictor

try:
    from models.lstm_predictor import LSTMLotteryPredictor
    from models.transformer_predictor import TransformerLotteryPredictor
    ADVANCED_ML_AVAILABLE = True
except:
    ADVANCED_ML_AVAILABLE = False

class UnifiedMLPredictor:
    """
    統一 ML 預測器
    整合所有機器學習模型與深度特徵
    """
    
    def __init__(self, use_transformer=True, use_lstm=True):
        self.feature_extractor = DeepFeatureExtractor(min_num=1, max_num=38)
        self.ensemble = EnsembleStackingPredictor()
        
        self.use_transformer = use_transformer and ADVANCED_ML_AVAILABLE
        self.use_lstm = use_lstm and ADVANCED_ML_AVAILABLE
        
        if self.use_lstm:
            self.lstm_predictor = LSTMLotteryPredictor(num_numbers=38, sequence_length=30)
        else:
            self.lstm_predictor = None
        
        if self.use_transformer:
            self.transformer_predictor = TransformerLotteryPredictor(
                num_numbers=38,
                sequence_length=30,
                d_model=128,
                nhead=8,
                num_layers=4
            )
        else:
            self.transformer_predictor = None
    
    def predict_ultimate(self, history, lottery_rules, train_models=False):
        """
        終極預測方法
        整合所有模型的預測結果
        
        Args:
            history: 歷史數據
            lottery_rules: 彩票規則
            train_models: 是否訓練深度學習模型
        
        Returns:
            {
                'numbers': [1, 5, 12, ...],
                'special': 3,
                'confidence': 0.85,
                'method': 'unified_ml_predict',
                'model_predictions': {...},
                'feature_analysis': {...}
            }
        """
        pick_count = lottery_rules.get('pickCount', 6)
        
        # 1. 提取深度特徵
        deep_features = self.feature_extractor.extract_all_features(history)
        
        # 2. Ensemble Stacking 預測
        ensemble_result = self.ensemble.predict_with_features(history, lottery_rules, use_lstm=False)
        
        # 3. 收集所有模型預測
        model_predictions = {
            'ensemble': ensemble_result
        }
        
        number_votes = Counter()
        special_votes = Counter()
        
        # Ensemble 投票（基礎權重）
        for num in ensemble_result['numbers']:
            number_votes[num] += ensemble_result['confidence']
        special_votes[ensemble_result['special']] += ensemble_result['confidence']
        
        # 4. LSTM 預測（如果可用且已訓練）
        if self.use_lstm and self.lstm_predictor:
            try:
                if train_models:
                    print("🔧 訓練 LSTM 模型...")
                    self.lstm_predictor.train(history, epochs=20, batch_size=8)
                
                lstm_result = self.lstm_predictor.predict(history, lottery_rules)
                model_predictions['lstm'] = lstm_result
                
                # LSTM 權重 1.2x
                for num in lstm_result['numbers']:
                    number_votes[num] += lstm_result['confidence'] * 1.2
                special_votes[lstm_result['special']] += lstm_result['confidence'] * 1.2
            except Exception as e:
                print(f"⚠️ LSTM 預測失敗: {e}")
        
        # 5. Transformer 預測（如果可用且已訓練）
        if self.use_transformer and self.transformer_predictor:
            try:
                if train_models:
                    print("🔧 訓練 Transformer 模型...")
                    self.transformer_predictor.train(history, epochs=30, batch_size=8)
                
                transformer_result = self.transformer_predictor.predict(history, lottery_rules)
                model_predictions['transformer'] = transformer_result
                
                # Transformer 權重 1.5x（最高）
                for num in transformer_result['numbers']:
                    number_votes[num] += transformer_result['confidence'] * 1.5
                special_votes[transformer_result['special']] += transformer_result['confidence'] * 1.5
            except Exception as e:
                print(f"⚠️ Transformer 預測失敗: {e}")
        
        # 6. 應用深度特徵調整
        number_votes = self._apply_deep_feature_boost(number_votes, deep_features, pick_count)
        
        # 7. 最終選擇
        final_numbers = sorted([n for n, _ in number_votes.most_common(pick_count)])
        final_special = special_votes.most_common(1)[0][0] if special_votes else 1
        
        # 8. 計算綜合信心度
        top_votes = [v for _, v in number_votes.most_common(pick_count)]
        avg_confidence = sum(top_votes) / len(top_votes) if top_votes else 0.5
        
        # 標準化（考慮模型數量）
        num_models = len(model_predictions)
        normalized_confidence = min(0.95, avg_confidence / (num_models * 1.5))
        
        return {
            'numbers': final_numbers,
            'special': final_special,
            'confidence': normalized_confidence,
            'method': 'unified_ml_predict',
            'model_predictions': {k: v['numbers'] for k, v in model_predictions.items()},
            'feature_analysis': self._summarize_features(deep_features),
            'model_count': num_models
        }
    
    def _apply_deep_feature_boost(self, number_votes, deep_features, pick_count):
        """應用深度特徵增強"""
        adjusted_votes = Counter(number_votes)
        
        # 連號模式
        cons = deep_features['consecutive_patterns']
        for pair in cons.get('hot_pairs', []):
            if pair[0] in adjusted_votes and pair[1] in adjusted_votes:
                adjusted_votes[pair[0]] *= 1.15
                adjusted_votes[pair[1]] *= 1.15
        
        # 尾數平衡
        tail_dist = deep_features['tail_distribution']
        current_tails = Counter()
        for num in [n for n, _ in adjusted_votes.most_common(pick_count)]:
            current_tails[num % 10] += 1
        
        for tail, count in current_tails.items():
            if count >= 3:
                for num in adjusted_votes:
                    if num % 10 == tail:
                        adjusted_votes[num] *= 0.85
        
        for tail in tail_dist.get('missing_tails', []):
            for num in adjusted_votes:
                if num % 10 == tail:
                    adjusted_votes[num] *= 1.25
        
        # 區段冷熱
        zone_heat = deep_features['zone_heat_cycles']
        zones = {
            1: range(1, 11),
            2: range(11, 21),
            3: range(21, 31),
            4: range(31, 39)
        }
        
        for zone_id in zone_heat.get('cold_zones', []):
            for num in zones[zone_id]:
                if num in adjusted_votes:
                    adjusted_votes[num] *= 1.3
        
        return adjusted_votes
    
    def _summarize_features(self, deep_features):
        """總結特徵"""
        return {
            'consecutive_pairs': len(deep_features['consecutive_patterns'].get('hot_pairs', [])),
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
    
    print("=" * 60)
    print("🚀 統一 ML 預測系統 (Phase 2)")
    print("=" * 60)
    
    predictor = UnifiedMLPredictor(use_transformer=True, use_lstm=True)
    
    print("\n🎯 生成終極預測...")
    result = predictor.predict_ultimate(history, rules, train_models=False)
    
    print(f"\n預測號碼: {result['numbers']}")
    print(f"特別號: {result['special']}")
    print(f"信心度: {result['confidence']:.2%}")
    print(f"使用模型數: {result['model_count']}")
    
    print(f"\n各模型預測:")
    for model, nums in result['model_predictions'].items():
        print(f"  {model}: {nums}")
    
    print(f"\n特徵分析:")
    for key, value in result['feature_analysis'].items():
        print(f"  {key}: {value}")
