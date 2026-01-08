"""
贝叶斯优化动态集成系统

基于贝叶斯优化自动调整策略权重，
相比固定权重或简单回测，能够更智能地适应数据变化。

特点:
1. 贝叶斯优化 (Bayesian Optimization) - 智能搜索最优权重
2. 高斯过程回归 (Gaussian Process) - 建模权重与性能关系
3. 采集函数 (Acquisition Function) - 平衡探索与利用
4. 动态更新 - 持续学习最新开奖模式
"""

import numpy as np
import logging
from typing import List, Dict, Tuple, Callable, Optional
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

# 尝试导入贝叶斯优化库
HAS_BAYESOPT = False
try:
    from scipy.optimize import minimize
    from scipy.stats import norm
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import RBF, ConstantKernel as C
    HAS_BAYESOPT = True
    logger.info("✓ Scipy + scikit-learn 可用，使用完整贝叶斯优化")
except ImportError:
    logger.warning("⚠️ 贝叶斯优化库不可用，将使用简化版本")


class BayesianOptimizer:
    """
    贝叶斯优化器

    使用高斯过程建模目标函数，使用采集函数指导搜索方向
    """

    def __init__(
        self,
        n_dimensions: int,
        bounds: List[Tuple[float, float]],
        random_state: int = 42
    ):
        """
        Args:
            n_dimensions: 优化维度（策略数量）
            bounds: 每个维度的取值范围 [(low, high), ...]
            random_state: 随机种子
        """
        self.n_dimensions = n_dimensions
        self.bounds = bounds
        self.random_state = random_state

        # 高斯过程配置
        kernel = C(1.0, (1e-3, 1e3)) * RBF(1.0, (1e-2, 1e2))
        self.gp = GaussianProcessRegressor(
            kernel=kernel,
            n_restarts_optimizer=10,
            random_state=random_state,
            alpha=1e-6,
            normalize_y=True
        )

        # 观测历史
        self.X_observed = []  # 已评估的权重配置
        self.y_observed = []  # 对应的性能得分

        np.random.seed(random_state)

    def _acquisition_function(
        self,
        X: np.ndarray,
        xi: float = 0.01,
        mode: str = 'ei'
    ) -> np.ndarray:
        """
        采集函数 (Acquisition Function)

        Args:
            X: 候选点 [n_samples, n_dimensions]
            xi: 探索参数（越大越倾向于探索）
            mode: 'ei' (Expected Improvement) 或 'ucb' (Upper Confidence Bound)

        Returns:
            采集值（越大越好）
        """
        if len(self.y_observed) == 0:
            return np.zeros(len(X))

        mu, sigma = self.gp.predict(X, return_std=True)

        if mode == 'ei':
            # Expected Improvement
            y_best = np.max(self.y_observed)
            improvement = mu - y_best - xi
            Z = improvement / (sigma + 1e-9)
            ei = improvement * norm.cdf(Z) + sigma * norm.pdf(Z)
            ei[sigma == 0.0] = 0.0
            return ei

        elif mode == 'ucb':
            # Upper Confidence Bound
            kappa = 2.0
            return mu + kappa * sigma

        else:
            raise ValueError(f"Unknown mode: {mode}")

    def _suggest_next_point(self) -> np.ndarray:
        """
        建议下一个评估点

        使用采集函数找到最有希望的权重配置
        """
        # 生成随机候选点
        n_candidates = 1000
        X_candidates = np.random.uniform(
            low=[b[0] for b in self.bounds],
            high=[b[1] for b in self.bounds],
            size=(n_candidates, self.n_dimensions)
        )

        # 归一化约束（权重和为1）
        X_candidates = X_candidates / X_candidates.sum(axis=1, keepdims=True)

        # 计算采集值
        acquisition_values = self._acquisition_function(X_candidates, mode='ei')

        # 选择最大采集值的点
        best_idx = np.argmax(acquisition_values)
        return X_candidates[best_idx]

    def observe(self, X: np.ndarray, y: float):
        """
        添加观测点

        Args:
            X: 权重配置 [n_dimensions]
            y: 性能得分（越大越好）
        """
        self.X_observed.append(X)
        self.y_observed.append(y)

        # 更新高斯过程
        if len(self.X_observed) > 0:
            X_array = np.array(self.X_observed)
            y_array = np.array(self.y_observed)
            self.gp.fit(X_array, y_array)

    def suggest(self) -> np.ndarray:
        """
        建议下一个要评估的权重配置

        Returns:
            权重向量 [n_dimensions]
        """
        if len(self.X_observed) < 3:
            # 初始随机探索
            weights = np.random.dirichlet(np.ones(self.n_dimensions))
            return weights
        else:
            # 使用采集函数
            return self._suggest_next_point()

    def get_best(self) -> Tuple[np.ndarray, float]:
        """
        获取当前最佳权重配置

        Returns:
            (best_weights, best_score)
        """
        if len(self.y_observed) == 0:
            raise ValueError("没有观测数据")

        best_idx = np.argmax(self.y_observed)
        return self.X_observed[best_idx], self.y_observed[best_idx]


class BayesianEnsemblePredictor:
    """
    基于贝叶斯优化的动态集成预测器

    自动寻找最优策略权重组合
    """

    def __init__(
        self,
        unified_engine,
        n_iterations: int = 20,
        backtest_periods: int = 30,
        training_window: int = 80
    ):
        """
        Args:
            unified_engine: UnifiedPredictionEngine 实例
            n_iterations: 贝叶斯优化迭代次数
            backtest_periods: 回测期数
            training_window: 训练窗口大小
        """
        self.engine = unified_engine
        self.n_iterations = n_iterations
        self.backtest_periods = backtest_periods
        self.training_window = training_window

        # 策略列表
        self.strategy_methods = {
            'zone_balance': self.engine.zone_balance_predict,
            'odd_even': self.engine.odd_even_balance_predict,
            'frequency': self.engine.frequency_predict,
            'bayesian': self.engine.bayesian_predict,
            'monte_carlo': self.engine.monte_carlo_predict,
            'hot_cold': self.engine.hot_cold_mix_predict,
        }

        self.strategy_names = list(self.strategy_methods.keys())
        self.n_strategies = len(self.strategy_names)

        # 缓存
        self._cached_weights = None
        self._cache_history_hash = None

        # 贝叶斯优化器
        self.optimizer = None

        logger.info(f"BayesianEnsemblePredictor 初始化 (策略数={self.n_strategies})")

    def _calculate_history_hash(self, history: List[Dict]) -> str:
        """计算历史数据哈希"""
        if not history:
            return ""
        return f"{history[0].get('draw', '')}_{len(history)}"

    def _evaluate_weights(
        self,
        weights: np.ndarray,
        history: List[Dict],
        lottery_rules: Dict
    ) -> float:
        """
        评估给定权重的性能

        使用滚动窗口回测计算平均命中率

        Args:
            weights: 策略权重 [n_strategies]
            history: 历史数据
            lottery_rules: 彩票规则

        Returns:
            性能得分（命中率）
        """
        pick_count = lottery_rules.get('pickCount', 6)

        total_matches = 0
        valid_tests = 0

        # 滚动窗口回测
        for i in range(self.backtest_periods):
            test_idx = i
            train_start = test_idx + 1
            train_end = train_start + self.training_window

            if train_end > len(history):
                break

            train_data = history[train_start:train_end]

            # 实际开奖
            actual = set(history[test_idx]['numbers'])
            special = history[test_idx].get('special')
            if special is not None:
                actual.add(int(special))

            # 策略预测
            predictions = []
            for strategy_name, strategy_method in self.strategy_methods.items():
                try:
                    result = strategy_method(train_data, lottery_rules)
                    predictions.append(result.get('numbers', []))
                except:
                    predictions.append([])

            # 加权投票
            number_scores = defaultdict(float)
            for strategy_idx, pred_numbers in enumerate(predictions):
                weight = weights[strategy_idx]
                for num in pred_numbers:
                    number_scores[num] += weight

            # 选择得分最高的号码
            sorted_nums = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)
            predicted = set([num for num, _ in sorted_nums[:pick_count]])

            # 计算命中数
            matches = len(predicted & actual)
            total_matches += matches
            valid_tests += 1

        if valid_tests == 0:
            return 0.0

        # 平均命中率
        avg_matches = total_matches / valid_tests
        # 归一化到 [0, 1]
        score = avg_matches / (pick_count + 1)  # +1 包含特别号

        return score

    def optimize_weights(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict[str, float]:
        """
        使用贝叶斯优化寻找最优权重

        Returns:
            最优策略权重字典
        """
        # 检查缓存
        history_hash = self._calculate_history_hash(history)
        if self._cached_weights and self._cache_history_hash == history_hash:
            logger.info("📦 使用缓存的贝叶斯优化权重")
            return self._cached_weights

        logger.info(f"🔬 开始贝叶斯优化 (迭代={self.n_iterations})")

        if not HAS_BAYESOPT:
            logger.warning("⚠️ 贝叶斯优化不可用，使用均等权重")
            equal_weight = 1.0 / self.n_strategies
            return {name: equal_weight for name in self.strategy_names}

        # 初始化优化器
        bounds = [(0.0, 1.0)] * self.n_strategies
        self.optimizer = BayesianOptimizer(
            n_dimensions=self.n_strategies,
            bounds=bounds,
            random_state=42
        )

        # 贝叶斯优化循环
        best_weights = None
        best_score = -np.inf

        for iteration in range(self.n_iterations):
            # 建议下一个权重配置
            weights = self.optimizer.suggest()

            # 评估性能
            score = self._evaluate_weights(weights, history, lottery_rules)

            # 记录观测
            self.optimizer.observe(weights, score)

            # 更新最佳结果
            if score > best_score:
                best_score = score
                best_weights = weights

            if (iteration + 1) % 5 == 0:
                logger.info(f"  迭代 {iteration+1}/{self.n_iterations}, 当前最佳得分: {best_score:.4f}")

        # 转换为字典
        weights_dict = {
            name: float(best_weights[i])
            for i, name in enumerate(self.strategy_names)
        }

        logger.info("✓ 贝叶斯优化完成，最优权重:")
        for name, weight in sorted(weights_dict.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"   {name}: {weight:.1%}")

        # 更新缓存
        self._cached_weights = weights_dict
        self._cache_history_hash = history_hash

        return weights_dict

    async def predict(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        执行贝叶斯优化集成预测

        Returns:
            预测结果
        """
        pick_count = lottery_rules.get('pickCount', 6)
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 49)

        logger.info("🎯 开始贝叶斯优化集成预测...")

        # 1. 优化权重
        weights = self.optimize_weights(history, lottery_rules)

        # 2. 执行所有策略
        all_predictions = {}
        for strategy_name, strategy_method in self.strategy_methods.items():
            try:
                result = strategy_method(history, lottery_rules)
                all_predictions[strategy_name] = {
                    'numbers': result.get('numbers', []),
                    'weight': weights.get(strategy_name, 0.1)
                }
                logger.info(f"   ✓ {strategy_name}: {result.get('numbers', [])} (权重: {weights.get(strategy_name, 0):.1%})")
            except Exception as e:
                logger.warning(f"   ✗ {strategy_name} 失败: {e}")

        # 3. 加权投票
        number_scores = defaultdict(float)

        for strategy_name, pred in all_predictions.items():
            weight = pred['weight']
            numbers = pred['numbers']

            for rank, num in enumerate(numbers[:pick_count]):
                rank_score = (pick_count - rank) / pick_count
                number_scores[num] += weight * rank_score * 10

        # 4. 选择最高分号码
        sorted_numbers = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)

        # Top 12 用于双注
        top_numbers = [num for num, _ in sorted_numbers[:pick_count * 2]]

        # 确保足够号码
        if len(top_numbers) < pick_count * 2:
            for num in range(min_num, max_num + 1):
                if num not in top_numbers:
                    top_numbers.append(num)
                if len(top_numbers) >= pick_count * 2:
                    break

        # 分成两注
        bet1 = sorted(top_numbers[:pick_count])
        bet2 = sorted(top_numbers[pick_count:pick_count * 2])

        # ⚠️ 大樂透特別號不預測！玩家只選6個主號碼

        # 计算信心度
        bet1_score = sum(number_scores.get(n, 0) for n in bet1) / pick_count
        bet2_score = sum(number_scores.get(n, 0) for n in bet2) / pick_count
        max_score = max(number_scores.values()) if number_scores else 1

        bet1_confidence = min(0.95, bet1_score / max_score)
        bet2_confidence = min(0.90, bet2_score / max_score)

        logger.info(f"✅ 贝叶斯优化预测完成 - 第一注: {bet1}, 第二注: {bet2}")

        return {
            'bet1': {
                'numbers': bet1,
                'confidence': float(bet1_confidence)
            },
            'bet2': {
                'numbers': bet2,
                'confidence': float(bet2_confidence)
            },
            'method': '贝叶斯优化集成',
            'overall_confidence': float((bet1_confidence + bet2_confidence) / 2),
            'optimized_weights': weights
        }


# 工厂函数
def create_bayesian_ensemble_predictor(
    unified_engine,
    n_iterations: int = 20
) -> BayesianEnsemblePredictor:
    """创建贝叶斯优化集成预测器"""
    return BayesianEnsemblePredictor(unified_engine, n_iterations=n_iterations)
