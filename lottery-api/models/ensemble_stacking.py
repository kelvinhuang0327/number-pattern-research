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
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from models.unified_predictor import UnifiedPredictionEngine
from models.deep_feature_extractor import DeepFeatureExtractor

try:
    from models.lstm_predictor import LSTMLotteryPredictor
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
            self.lstm_predictor = LSTMLotteryPredictor(num_numbers=38, sequence_length=30)
        else:
            self.lstm_predictor = None
        
        # 基礎模型列表（優化版：只使用 Top 3）
        # 根據 2025 回測結果：Markov (16.10%), Bayesian (12.71%), Trend (12.71%)
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
        }
    
    def predict_with_features(self, history, lottery_rules, use_lstm=False):
        """
        使用深度特徵增強的預測
        
        Args:
            history: 歷史數據
            lottery_rules: 彩票規則
            use_lstm: 是否使用 LSTM 模型
        
        Returns:
            {
                'numbers': [1, 5, 12, ...],
                'special': 3,
                'confidence': 0.75,
                'method': 'ensemble_stacking',
                'feature_scores': {...},
                'model_votes': {...}
            }
        """
        pick_count = lottery_rules.get('pickCount', 6)
        
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
                
                # 投票（應用模型權重）
                confidence = result.get('confidence', 0.5)
                vote_power = confidence * weight
                
                for num in result['numbers']:
                    number_votes[num] += vote_power
                
                if 'special' in result:
                    special_votes[result['special']] += vote_power
            except:
                continue
        
        # 3. LSTM 預測（如果可用）
        if use_lstm and self.lstm_predictor:
            try:
                lstm_result = self.lstm_predictor.predict(history, lottery_rules)
                model_predictions['lstm'] = lstm_result
                
                # LSTM 給予更高權重
                for num in lstm_result['numbers']:
                    number_votes[num] += lstm_result.get('confidence', 0.5) * 1.5
                
                if 'special' in lstm_result:
                    special_votes[lstm_result['special']] += lstm_result.get('confidence', 0.5) * 1.5
            except:
                pass
        
        # 4. 應用深度特徵調整
        number_votes = self._apply_feature_adjustments(number_votes, deep_features, pick_count)
        
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
    
    def _apply_feature_adjustments(self, number_votes, deep_features, pick_count):
        """應用深度特徵調整號碼權重"""
        adjusted_votes = Counter(number_votes)
        
        # 1. 連號模式調整
        cons_patterns = deep_features['consecutive_patterns']
        for pair in cons_patterns.get('hot_pairs', []):
            # 如果連號對都在候選中，提升權重
            if pair[0] in adjusted_votes and pair[1] in adjusted_votes:
                adjusted_votes[pair[0]] *= 1.2
                adjusted_votes[pair[1]] *= 1.2
        
        # 2. 尾數平衡調整
        tail_dist = deep_features['tail_distribution']
        current_tails = Counter()
        for num in [n for n, _ in adjusted_votes.most_common(pick_count)]:
            current_tails[num % 10] += 1
        
        # 如果某個尾數過多，降低該尾數號碼的權重
        for tail, count in current_tails.items():
            if count >= 3:  # 同一尾數出現3次以上
                for num in adjusted_votes:
                    if num % 10 == tail:
                        adjusted_votes[num] *= 0.8
        
        # 提升缺失尾數的權重
        for tail in tail_dist.get('missing_tails', []):
            for num in adjusted_votes:
                if num % 10 == tail:
                    adjusted_votes[num] *= 1.3
        
        # 3. 區段冷熱調整
        zone_heat = deep_features['zone_heat_cycles']
        zones = {
            1: range(1, 11),
            2: range(11, 21),
            3: range(21, 31),
            4: range(31, 39)
        }
        
        # 提升冷區號碼權重（即將反彈）
        for zone_id in zone_heat.get('cold_zones', []):
            for num in zones[zone_id]:
                if num in adjusted_votes:
                    adjusted_votes[num] *= 1.4
        
        return adjusted_votes
    
    def _summarize_features(self, deep_features):
        """總結特徵分數"""
        return {
            'consecutive_score': len(deep_features['consecutive_patterns'].get('hot_pairs', [])),
            'tail_balance': deep_features['tail_distribution'].get('tail_balance_score', 0),
            'cold_zones': deep_features['zone_heat_cycles'].get('cold_zones', []),
            'avg_gap': deep_features['number_gaps'].get('avg_gap', 0)
        }

if __name__ == '__main__':
    from database import DatabaseManager
    from common import get_lottery_rules
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    history = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    
    print("=" * 60)
    print("🎯 Ensemble Stacking 預測系統")
    print("=" * 60)
    
    ensemble = EnsembleStackingPredictor()
    
    print("\n🔮 生成預測...")
    result = ensemble.predict_with_features(history, rules, use_lstm=False)
    
    print(f"\n預測號碼: {result['numbers']}")
    print(f"特別號: {result['special']}")
    print(f"信心度: {result['confidence']:.2%}")
    print(f"\n特徵評分:")
    for key, value in result['feature_scores'].items():
        print(f"  {key}: {value}")
    print(f"\n模型投票:")
    for model, votes in result['model_votes'].items():
        print(f"  {model}: {votes} 票")
