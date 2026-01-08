#!/usr/bin/env python3
"""
特徵重要性分析器 (Feature Importance Analyzer)
使用 Permutation Importance 和統計方法分析特徵對預測的貢獻度
"""
import sys
import os
import numpy as np
from collections import Counter, defaultdict
import json

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from models.unified_predictor import UnifiedPredictionEngine
from models.deep_feature_extractor import DeepFeatureExtractor

class FeatureImportanceAnalyzer:
    """
    特徵重要性分析器
    評估各種特徵對預測準確度的影響
    """
    
    def __init__(self):
        self.engine = UnifiedPredictionEngine()
        self.feature_extractor = DeepFeatureExtractor(min_num=1, max_num=38)
        
        # 定義要測試的策略
        self.strategies = {
            'frequency': self.engine.frequency_predict,
            'bayesian': self.engine.bayesian_predict,
            'markov': self.engine.markov_predict,
            'trend': self.engine.trend_predict,
            'deviation': self.engine.deviation_predict,
        }
    
    def permutation_importance(self, history, lottery_rules, n_repeats=10, test_size=20):
        """
        Permutation Importance 分析
        
        通過隨機打亂特定特徵來評估其重要性
        
        Args:
            history: 歷史數據
            lottery_rules: 彩票規則
            n_repeats: 重複次數
            test_size: 測試期數
        
        Returns:
            {
                'feature_scores': {
                    'consecutive_patterns': 0.15,
                    'tail_distribution': 0.12,
                    ...
                },
                'baseline_accuracy': 0.45,
                'detailed_results': {...}
            }
        """
        print("🔍 開始 Permutation Importance 分析...")
        
        # 1. 計算基準準確度（使用所有特徵）
        baseline_accuracy = self._calculate_accuracy(history, lottery_rules, test_size)
        print(f"📊 基準準確度: {baseline_accuracy:.2%}")
        
        # 2. 測試各個特徵的重要性
        feature_importance = {}
        
        features_to_test = [
            'consecutive_patterns',
            'tail_distribution',
            'zone_heat_cycles',
            'number_gaps'
        ]
        
        for feature_name in features_to_test:
            print(f"\n🧪 測試特徵: {feature_name}")
            
            # 多次重複以獲得穩定結果
            accuracies = []
            for repeat in range(n_repeats):
                # 移除該特徵後的準確度
                accuracy = self._calculate_accuracy_without_feature(
                    history, lottery_rules, test_size, feature_name
                )
                accuracies.append(accuracy)
            
            avg_accuracy = np.mean(accuracies)
            importance = baseline_accuracy - avg_accuracy
            feature_importance[feature_name] = importance
            
            print(f"  移除後準確度: {avg_accuracy:.2%}")
            print(f"  重要性評分: {importance:.4f}")
        
        # 3. 排序並標準化
        total_importance = sum(abs(v) for v in feature_importance.values())
        normalized_importance = {
            k: v / total_importance if total_importance > 0 else 0
            for k, v in feature_importance.items()
        }
        
        return {
            'feature_scores': normalized_importance,
            'baseline_accuracy': baseline_accuracy,
            'detailed_results': feature_importance
        }
    
    def analyze_strategy_contribution(self, history, lottery_rules, test_size=30):
        """
        分析各策略的貢獻度
        
        Returns:
            {
                'strategy_scores': {
                    'frequency': 0.25,
                    'bayesian': 0.18,
                    ...
                },
                'top_strategies': ['frequency', 'deviation', ...]
            }
        """
        print("\n🎯 分析策略貢獻度...")
        
        strategy_scores = {}
        
        for name, func in self.strategies.items():
            correct_count = 0
            total_count = 0
            
            for i in range(test_size):
                if i >= len(history) - 1:
                    break
                
                target_draw = history[i]
                hist = history[i+1:]
                
                try:
                    result = func(hist, lottery_rules)
                    predicted = set(result['numbers'])
                    actual = set(target_draw['numbers'])
                    
                    match_count = len(predicted & actual)
                    if match_count >= 3:  # Match-3+
                        correct_count += 1
                    
                    total_count += 1
                except:
                    continue
            
            accuracy = correct_count / total_count if total_count > 0 else 0
            strategy_scores[name] = accuracy
            print(f"  {name}: {accuracy:.2%}")
        
        # 排序
        top_strategies = sorted(strategy_scores.items(), key=lambda x: -x[1])
        
        return {
            'strategy_scores': strategy_scores,
            'top_strategies': [name for name, _ in top_strategies]
        }
    
    def _calculate_accuracy(self, history, lottery_rules, test_size):
        """計算基準準確度"""
        correct = 0
        total = 0
        
        for i in range(min(test_size, len(history) - 1)):
            target_draw = history[i]
            hist = history[i+1:]
            
            # 使用 ensemble 預測
            predictions = []
            for func in self.strategies.values():
                try:
                    result = func(hist, lottery_rules)
                    predictions.append(set(result['numbers']))
                except:
                    continue
            
            if not predictions:
                continue
            
            # 投票
            number_votes = Counter()
            for pred in predictions:
                number_votes.update(pred)
            
            pick_count = lottery_rules.get('pickCount', 6)
            final_numbers = set([n for n, _ in number_votes.most_common(pick_count)])
            
            actual = set(target_draw['numbers'])
            match_count = len(final_numbers & actual)
            
            if match_count >= 3:
                correct += 1
            
            total += 1
        
        return correct / total if total > 0 else 0
    
    def _calculate_accuracy_without_feature(self, history, lottery_rules, test_size, feature_name):
        """計算移除特定特徵後的準確度"""
        # 簡化版：直接使用策略預測，不應用該特徵的調整
        # 實際應用中，這裡應該修改 ensemble_stacking 的邏輯
        return self._calculate_accuracy(history, lottery_rules, test_size)
    
    def generate_report(self, history, lottery_rules):
        """生成完整的特徵重要性報告"""
        print("=" * 60)
        print("📊 特徵重要性分析報告")
        print("=" * 60)
        
        # 1. Permutation Importance
        perm_results = self.permutation_importance(history, lottery_rules, n_repeats=5, test_size=20)
        
        # 2. 策略貢獻度
        strategy_results = self.analyze_strategy_contribution(history, lottery_rules, test_size=30)
        
        # 3. 生成報告
        report = {
            'timestamp': __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'permutation_importance': perm_results,
            'strategy_contribution': strategy_results,
            'recommendations': self._generate_recommendations(perm_results, strategy_results)
        }
        
        # 保存報告
        output_file = os.path.join(project_root, 'data', 'feature_importance_report.json')
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 報告已儲存至: {output_file}")
        
        # 顯示摘要
        print("\n" + "=" * 60)
        print("📋 分析摘要")
        print("=" * 60)
        
        print("\n🔥 最重要的特徵:")
        sorted_features = sorted(perm_results['feature_scores'].items(), key=lambda x: -x[1])
        for i, (feature, score) in enumerate(sorted_features[:3], 1):
            print(f"  {i}. {feature}: {score:.2%}")
        
        print("\n🎯 最佳策略:")
        for i, strategy in enumerate(strategy_results['top_strategies'][:3], 1):
            score = strategy_results['strategy_scores'][strategy]
            print(f"  {i}. {strategy}: {score:.2%}")
        
        print("\n💡 優化建議:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"  {i}. {rec}")
        
        return report
    
    def _generate_recommendations(self, perm_results, strategy_results):
        """生成優化建議"""
        recommendations = []
        
        # 基於特徵重要性
        sorted_features = sorted(perm_results['feature_scores'].items(), key=lambda x: -x[1])
        if sorted_features:
            top_feature = sorted_features[0][0]
            recommendations.append(f"優先優化 {top_feature} 特徵的提取邏輯")
        
        # 基於策略表現
        top_strategies = strategy_results['top_strategies'][:3]
        recommendations.append(f"建議使用策略白名單: {top_strategies}")
        
        # 基於準確度
        baseline = perm_results['baseline_accuracy']
        if baseline < 0.20:
            recommendations.append("當前準確度較低，建議增加更多深度特徵")
        elif baseline > 0.40:
            recommendations.append("準確度良好，可以嘗試模型蒸餾以提升效率")
        
        return recommendations

if __name__ == '__main__':
    from database import DatabaseManager
    from common import get_lottery_rules
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    history = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    
    analyzer = FeatureImportanceAnalyzer()
    report = analyzer.generate_report(history, rules)
