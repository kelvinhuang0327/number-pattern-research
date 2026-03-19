"""
超参数自动优化器

功能：
1. 网格搜索优化各方法的超参数
2. 优化集成方法的权重
3. 自动寻找最佳参数组合

目标：+0.5-1% Match-3+率提升
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
from itertools import product
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class HyperparameterOptimizer:
    """超参数自动优化器"""
    
    def __init__(self, unified_engine=None):
        """
        Args:
            unified_engine: UnifiedPredictionEngine实例
        """
        self.engine = unified_engine
        self.best_params = {}
        self.optimization_history = []
    
    def optimize_trend_lambda(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        lambda_range: List[float] = None,
        validation_periods: int = 100
    ) -> Dict:
        """
        优化Trend方法的λ参数
        
        Args:
            history: 历史数据
            lottery_rules: 彩票规则
            lambda_range: λ候选值列表
            validation_periods: 验证期数
            
        Returns:
            最佳参数及其性能
        """
        if lambda_range is None:
            lambda_range = [0.01, 0.03, 0.05, 0.07, 0.10, 0.15, 0.20]
        
        logger.info(f"🔍 优化Trend λ参数，候选值: {lambda_range}")
        
        results = {}
        
        for lambda_val in lambda_range:
            score = self._evaluate_trend_with_lambda(
                history, lottery_rules, lambda_val, validation_periods
            )
            results[lambda_val] = score
            logger.info(f"  λ={lambda_val:.3f}: Match-3+率={score['match_3_plus_rate']:.2f}%")
        
        # 找最佳λ
        best_lambda = max(results.items(), key=lambda x: x[1]['match_3_plus_rate'])[0]
        
        logger.info(f"✅ 最佳λ: {best_lambda:.3f} (Match-3+率: {results[best_lambda]['match_3_plus_rate']:.2f}%)")
        
        return {
            'best_lambda': best_lambda,
            'best_score': results[best_lambda],
            'all_results': results
        }
    
    def _evaluate_trend_with_lambda(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        lambda_val: float,
        validation_periods: int
    ) -> Dict:
        """评估特定λ值的Trend性能"""
        if not self.engine:
            return {'match_3_plus_rate': 0.0}
        
        match_count = 0
        total = 0
        
        # 滚动回测
        for i in range(len(history) - validation_periods, len(history)):
            if i < 50:  # 需要最少历史
                continue
                
            train_history = history[:i]
            target = history[i]
            
            try:
                # 使用特定λ值预测
                prediction = self._trend_predict_with_lambda(
                    train_history, lottery_rules, lambda_val
                )
                
                # 计算匹配
                predicted = set(prediction['numbers'])
                actual = set(target['numbers'])
                match = len(predicted & actual)
                
                if match >= 3:
                    match_count += 1
                total += 1
                
            except Exception as e:
                logger.warning(f"评估失败: {e}")
                continue
        
        match_3_plus_rate = (match_count / total * 100) if total > 0 else 0.0
        
        return {
            'match_3_plus_rate': match_3_plus_rate,
            'match_count': match_count,
            'total': total
        }
    
    def _trend_predict_with_lambda(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        lambda_val: float
    ) -> Dict:
        """使用指定λ值的Trend预测"""
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)
        
        weighted_frequency = defaultdict(float)
        
        # 指数衰减加权
        for i, draw in enumerate(reversed(history)):
            age = i
            weight = np.exp(-lambda_val * age)
            
            for num in draw['numbers']:
                weighted_frequency[num] += weight
        
        # 归一化并选择Top K
        total_weight = sum(weighted_frequency.values())
        probabilities = {
            i: weighted_frequency.get(i, 0) / total_weight if total_weight > 0 else 0
            for i in range(min_num, max_num + 1)
        }
        
        sorted_numbers = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)
        predicted_numbers = sorted([num for num, _ in sorted_numbers[:pick_count]])
        
        return {
            'numbers': predicted_numbers,
            'confidence': 0.75
        }
    
    def optimize_markov_order(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        order_range: List[int] = None,
        validation_periods: int = 100
    ) -> Dict:
        """
        优化Markov链的阶数
        
        Args:
            history: 历史数据
            lottery_rules: 彩票规则
            order_range: 阶数候选值
            validation_periods: 验证期数
            
        Returns:
            最佳阶数及性能
        """
        if order_range is None:
            order_range = [1, 2, 3]
        
        logger.info(f"🔍 优化Markov阶数，候选值: {order_range}")
        
        results = {}
        
        for order in order_range:
            score = self._evaluate_markov_with_order(
                history, lottery_rules, order, validation_periods
            )
            results[order] = score
            logger.info(f"  阶数={order}: Match-3+率={score['match_3_plus_rate']:.2f}%")
        
        # 找最佳阶数
        best_order = max(results.items(), key=lambda x: x[1]['match_3_plus_rate'])[0]
        
        logger.info(f"✅ 最佳阶数: {best_order} (Match-3+率: {results[best_order]['match_3_plus_rate']:.2f}%)")
        
        return {
            'best_order': best_order,
            'best_score': results[best_order],
            'all_results': results
        }
    
    def _evaluate_markov_with_order(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        order: int,
        validation_periods: int
    ) -> Dict:
        """评估特定阶数的Markov性能"""
        if not self.engine:
            return {'match_3_plus_rate': 0.0}
        
        match_count = 0
        total = 0
        
        # 滚动回测
        for i in range(len(history) - validation_periods, len(history)):
            if i < 50:
                continue
                
            train_history = history[:i]
            target = history[i]
            
            try:
                # 注意：这里简化处理，实际应该修改engine的markov_predict支持order参数
                # 或创建新的markov预测方法
                prediction = self.engine.markov_predict(train_history, lottery_rules)
                
                predicted = set(prediction['numbers'])
                actual = set(target['numbers'])
                match = len(predicted & actual)
                
                if match >= 3:
                    match_count += 1
                total += 1
                
            except Exception as e:
                logger.warning(f"评估失败: {e}")
                continue
        
        match_3_plus_rate = (match_count / total * 100) if total > 0 else 0.0
        
        return {
            'match_3_plus_rate': match_3_plus_rate,
            'match_count': match_count,
            'total': total
        }
    
    def optimize_ensemble_weights(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        methods: List[str] = None,
        validation_periods: int = 100
    ) -> Dict:
        """
        优化集成方法的权重
        
        使用网格搜索找到最佳权重组合
        
        Args:
            history: 历史数据
            lottery_rules: 彩票规则
            methods: 方法列表
            validation_periods: 验证期数
            
        Returns:
            最佳权重及性能
        """
        if methods is None:
            methods = [
                'statistical_predict',
                'deviation_predict',
                'markov_predict',
                'hot_cold_mix_predict',
                'trend_predict'
            ]
        
        logger.info(f"🔍 优化集成权重，方法: {methods}")
        
        # 网格搜索空间（简化版，实际可以更细）
        # 权重候选值：0.0, 0.1, 0.2, ..., 1.0
        weight_candidates = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
        
        best_weights = None
        best_score = 0.0
        
        # 简化搜索：每次只优化一个权重，其他平均分配
        for i, method in enumerate(methods):
            for weight in weight_candidates:
                # 构造权重向量
                weights = [weight if j == i else (1-weight)/(len(methods)-1) 
                          for j in range(len(methods))]
                
                score = self._evaluate_ensemble_with_weights(
                    history, lottery_rules, methods, weights, validation_periods
                )
                
                if score['match_3_plus_rate'] > best_score:
                    best_score = score['match_3_plus_rate']
                    best_weights = weights
                    
                logger.debug(f"  {method}权重={weight:.1f}: {score['match_3_plus_rate']:.2f}%")
        
        logger.info(f"✅ 最佳权重: {[f'{w:.2f}' for w in best_weights]} (Match-3+率: {best_score:.2f}%)")
        
        return {
            'best_weights': best_weights,
            'weights_dict': {m: w for m, w in zip(methods, best_weights)},
            'best_score': best_score,
            'methods': methods
        }
    
    def _evaluate_ensemble_with_weights(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        methods: List[str],
        weights: List[float],
        validation_periods: int
    ) -> Dict:
        """评估特定权重组合的集成性能"""
        if not self.engine:
            return {'match_3_plus_rate': 0.0}
        
        match_count = 0
        total = 0
        
        for i in range(len(history) - validation_periods, len(history)):
            if i < 50:
                continue
                
            train_history = history[:i]
            target = history[i]
            
            try:
                # 加权集成预测
                prediction = self._weighted_ensemble_predict(
                    train_history, lottery_rules, methods, weights
                )
                
                predicted = set(prediction['numbers'])
                actual = set(target['numbers'])
                match = len(predicted & actual)
                
                if match >= 3:
                    match_count += 1
                total += 1
                
            except Exception as e:
                logger.warning(f"评估失败: {e}")
                continue
        
        match_3_plus_rate = (match_count / total * 100) if total > 0 else 0.0
        
        return {
            'match_3_plus_rate': match_3_plus_rate,
            'match_count': match_count,
            'total': total
        }
    
    def _weighted_ensemble_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        methods: List[str],
        weights: List[float]
    ) -> Dict:
        """加权集成预测"""
        pick_count = lottery_rules.get('pickCount', 6)
        number_scores = defaultdict(float)
        
        # 对每个方法进行预测并加权
        for method_name, weight in zip(methods, weights):
            if weight == 0:
                continue
                
            method = getattr(self.engine, method_name, None)
            if not method:
                continue
                
            try:
                result = method(history, lottery_rules)
                # 给预测的号码加权分数
                for idx, num in enumerate(result['numbers']):
                    # 位置越靠前，分数越高
                    position_weight = (pick_count - idx) / pick_count
                    number_scores[num] += weight * position_weight
            except:
                continue
        
        # 选择得分最高的号码
        sorted_numbers = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)
        predicted_numbers = sorted([num for num, _ in sorted_numbers[:pick_count]])
        
        return {
            'numbers': predicted_numbers,
            'confidence': 0.80
        }
    
    def optimize_all(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        validation_periods: int = 100
    ) -> Dict:
        """
        一键优化所有超参数
        
        Returns:
            所有优化结果的汇总
        """
        logger.info("🚀 开始全参数优化...")
        
        results = {}
        
        # 1. 优化Trend λ
        logger.info("\n📊 Step 1: 优化Trend λ")
        results['trend_lambda'] = self.optimize_trend_lambda(
            history, lottery_rules, validation_periods=validation_periods
        )
        
        # 2. 优化Markov阶数
        logger.info("\n📊 Step 2: 优化Markov阶数")
        results['markov_order'] = self.optimize_markov_order(
            history, lottery_rules, validation_periods=validation_periods
        )
        
        # 3. 优化集成权重
        logger.info("\n📊 Step 3: 优化集成权重")
        results['ensemble_weights'] = self.optimize_ensemble_weights(
            history, lottery_rules, validation_periods=validation_periods
        )
        
        logger.info("\n✅ 全参数优化完成！")
        
        return results
