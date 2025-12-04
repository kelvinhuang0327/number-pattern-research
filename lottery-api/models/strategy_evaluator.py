"""
智能策略評估器 - 自動找出最佳預測方法
使用滾動驗證評估所有策略的性能，並自動選擇表現最好的策略
"""
import numpy as np
import logging
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
import json
import os
from datetime import datetime

from .unified_predictor import prediction_engine

logger = logging.getLogger(__name__)

class StrategyEvaluator:
    """
    策略評估器
    自動測試所有可用的預測策略，找出最佳方法
    """

    def __init__(self):
        # 可用的預測策略列表
        self.available_strategies = [
            # 核心統計策略
            ('frequency', '加權頻率分析'),
            ('bayesian', '貝葉斯統計'),
            ('markov', '馬可夫鏈'),
            ('monte_carlo', '蒙地卡羅模擬'),

            # 民間策略
            ('odd_even', '奇偶平衡'),
            ('zone_balance', '區域平衡'),
            ('hot_cold', '冷熱混合'),

            # 高級策略
            ('random_forest', '隨機森林/KNN相似度'),
            ('ensemble', '集成預測')
        ]

        # 評估結果緩存
        self.evaluation_cache = {}
        self.best_strategy_cache = None

        # 結果存儲路徑
        self.results_dir = 'data/strategy_evaluation'
        os.makedirs(self.results_dir, exist_ok=True)

        logger.info("StrategyEvaluator 初始化完成")

    def evaluate_all_strategies(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        test_ratio: float = 0.2,
        min_train_size: int = 30
    ) -> Dict:
        """
        評估所有策略

        Args:
            history: 歷史數據
            lottery_rules: 彩券規則
            test_ratio: 測試集比例 (默認20%)
            min_train_size: 最小訓練集大小

        Returns:
            評估結果字典
        """
        logger.info(f"開始評估所有策略，數據量: {len(history)} 期")

        # 確保數據足夠
        if len(history) < min_train_size + 10:
            raise ValueError(f"數據量不足，至少需要 {min_train_size + 10} 期")

        # 計算測試期數
        test_size = max(int(len(history) * test_ratio), 10)

        # 評估每個策略
        results = {}

        for strategy_id, strategy_name in self.available_strategies:
            try:
                logger.info(f"評估策略: {strategy_name} ({strategy_id})")

                # 使用滾動驗證評估
                metrics = self._rolling_validation(
                    strategy_id,
                    history,
                    lottery_rules,
                    test_size,
                    min_train_size
                )

                results[strategy_id] = {
                    'name': strategy_name,
                    'metrics': metrics,
                    'score': self._calculate_score(metrics)  # 綜合評分
                }

                logger.info(f"✅ {strategy_name}: 成功率 {metrics['success_rate']:.2%}, 評分 {results[strategy_id]['score']:.2f}")

            except Exception as e:
                logger.error(f"❌ 策略 {strategy_name} 評估失敗: {e}")
                results[strategy_id] = {
                    'name': strategy_name,
                    'metrics': None,
                    'score': 0,
                    'error': str(e)
                }

        # 排序結果
        sorted_results = dict(
            sorted(results.items(), key=lambda x: x[1]['score'], reverse=True)
        )

        # 找出最佳策略
        best_strategy_id = list(sorted_results.keys())[0]
        best_strategy = sorted_results[best_strategy_id]

        # 緩存結果
        self.evaluation_cache = sorted_results
        self.best_strategy_cache = {
            'strategy_id': best_strategy_id,
            'strategy_name': best_strategy['name'],
            'metrics': best_strategy['metrics'],
            'score': best_strategy['score'],
            'timestamp': datetime.now().isoformat()
        }

        # 保存到文件
        self._save_evaluation_results(sorted_results, lottery_rules)

        # 返回摘要
        return {
            'total_strategies': len(self.available_strategies),
            'evaluated': len([r for r in results.values() if r['metrics'] is not None]),
            'failed': len([r for r in results.values() if r['metrics'] is None]),
            'best_strategy': self.best_strategy_cache,
            'all_results': sorted_results
        }

    def _rolling_validation(
        self,
        strategy_id: str,
        history: List[Dict],
        lottery_rules: Dict,
        test_size: int,
        min_train_size: int
    ) -> Dict:
        """
        滾動驗證評估策略性能

        對最後 test_size 期進行滾動預測驗證
        """
        pick_count = lottery_rules.get('pickCount', 6)

        # 測試範圍：最後 test_size 期
        test_start_idx = len(history) - test_size

        results = []
        hit_distribution = defaultdict(int)  # 命中數分佈

        for i in range(test_start_idx, len(history)):
            # 訓練數據：該期之前的所有數據
            train_data = history[:i]

            # 確保訓練集足夠大
            if len(train_data) < min_train_size:
                continue

            # 執行預測
            try:
                prediction = self._predict_with_strategy(
                    strategy_id,
                    train_data,
                    lottery_rules
                )

                # 驗證結果
                actual_numbers = history[i]['numbers']
                predicted_numbers = prediction['numbers']

                # 計算命中數
                hits = len(set(actual_numbers) & set(predicted_numbers))
                hit_distribution[hits] += 1

                # 判斷是否成功（中3個以上）
                is_success = hits >= 3

                results.append({
                    'draw': history[i].get('draw', i),
                    'hits': hits,
                    'is_success': is_success,
                    'confidence': prediction.get('confidence', 0)
                })

            except Exception as e:
                logger.warning(f"策略 {strategy_id} 在期數 {i} 預測失敗: {e}")
                continue

        if not results:
            raise ValueError("沒有成功的預測結果")

        # 計算指標
        total_tests = len(results)
        success_count = sum(1 for r in results if r['is_success'])
        success_rate = success_count / total_tests

        # 平均命中數
        avg_hits = np.mean([r['hits'] for r in results])

        # 平均信心度
        avg_confidence = np.mean([r['confidence'] for r in results])

        # 命中率分佈百分比
        hit_dist_pct = {
            hits: count / total_tests * 100
            for hits, count in hit_distribution.items()
        }

        # 理論命中率（大樂透）
        theoretical_3_hits = 1.765  # 中3個的理論概率 (%)

        # 計算 vs 理論倍數
        actual_3_hits_pct = hit_dist_pct.get(3, 0) + hit_dist_pct.get(4, 0) + \
                           hit_dist_pct.get(5, 0) + hit_dist_pct.get(6, 0)
        vs_theory = actual_3_hits_pct / theoretical_3_hits if theoretical_3_hits > 0 else 0

        return {
            'total_tests': total_tests,
            'success_count': success_count,
            'success_rate': success_rate,
            'avg_hits': avg_hits,
            'avg_confidence': avg_confidence,
            'hit_distribution': dict(hit_distribution),
            'hit_dist_pct': hit_dist_pct,
            'vs_theory': vs_theory
        }

    def _predict_with_strategy(
        self,
        strategy_id: str,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """使用指定策略進行預測"""
        # 映射到 unified_predictor 的方法
        strategy_methods = {
            'frequency': prediction_engine.frequency_predict,
            'bayesian': prediction_engine.bayesian_predict,
            'markov': prediction_engine.markov_predict,
            'monte_carlo': prediction_engine.monte_carlo_predict,
            'odd_even': prediction_engine.odd_even_balance_predict,
            'zone_balance': prediction_engine.zone_balance_predict,
            'hot_cold': prediction_engine.hot_cold_mix_predict,
            'random_forest': prediction_engine.random_forest_predict,
            'ensemble': prediction_engine.ensemble_predict
        }

        method = strategy_methods.get(strategy_id)
        if not method:
            raise ValueError(f"未知的策略: {strategy_id}")

        return method(history, lottery_rules)

    def _calculate_score(self, metrics: Dict) -> float:
        """
        計算策略的綜合評分

        考慮因素:
        - 成功率 (權重 50%)
        - 平均命中數 (權重 30%)
        - vs 理論倍數 (權重 20%)
        """
        if not metrics:
            return 0

        success_rate = metrics.get('success_rate', 0)
        avg_hits = metrics.get('avg_hits', 0)
        vs_theory = metrics.get('vs_theory', 0)

        # 歸一化
        # 成功率已經是 0-1
        # 平均命中數 (0-6) 歸一化到 0-1
        norm_avg_hits = avg_hits / 6.0
        # vs 理論倍數，假設最好情況是 3 倍
        norm_vs_theory = min(vs_theory / 3.0, 1.0)

        # 加權平均
        score = (
            success_rate * 0.5 +
            norm_avg_hits * 0.3 +
            norm_vs_theory * 0.2
        ) * 100  # 轉換為 0-100 分

        return score

    def _save_evaluation_results(self, results: Dict, lottery_rules: Dict):
        """保存評估結果到文件"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        lottery_type = lottery_rules.get('lotteryType', 'UNKNOWN')

        filename = f"{self.results_dir}/evaluation_{lottery_type}_{timestamp}.json"

        # 準備可序列化的數據
        serializable_results = {}
        for strategy_id, data in results.items():
            serializable_results[strategy_id] = {
                'name': data['name'],
                'score': float(data['score']),
                'metrics': {
                    k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                    for k, v in (data.get('metrics') or {}).items()
                } if data.get('metrics') else None,
                'error': data.get('error')
            }

        save_data = {
            'timestamp': timestamp,
            'lottery_type': lottery_type,
            'lottery_rules': lottery_rules,
            'results': serializable_results,
            'best_strategy': self.best_strategy_cache
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        logger.info(f"評估結果已保存到: {filename}")

    def get_best_strategy(self) -> Optional[Dict]:
        """獲取當前最佳策略"""
        return self.best_strategy_cache

    def load_latest_evaluation(self, lottery_type: str = None) -> Optional[Dict]:
        """載入最新的評估結果"""
        try:
            # 列出所有評估文件
            files = [f for f in os.listdir(self.results_dir) if f.startswith('evaluation_')]

            if lottery_type:
                # 篩選指定彩券類型
                files = [f for f in files if lottery_type in f]

            if not files:
                return None

            # 按時間排序，取最新
            files.sort(reverse=True)
            latest_file = os.path.join(self.results_dir, files[0])

            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 更新緩存
            self.best_strategy_cache = data.get('best_strategy')
            self.evaluation_cache = data.get('results', {})

            logger.info(f"載入評估結果: {latest_file}")
            return data

        except Exception as e:
            logger.error(f"載入評估結果失敗: {e}")
            return None

    def predict_with_best(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        使用最佳策略進行預測

        如果沒有緩存的最佳策略，先載入最新評估結果
        如果仍然沒有，則使用默認的 ensemble 策略
        """
        # 嘗試獲取最佳策略
        best = self.best_strategy_cache

        if not best:
            # 嘗試載入
            lottery_type = lottery_rules.get('lotteryType')
            latest = self.load_latest_evaluation(lottery_type)
            best = latest.get('best_strategy') if latest else None

        if not best:
            logger.warning("沒有最佳策略緩存，使用默認 ensemble 策略")
            strategy_id = 'ensemble'
        else:
            strategy_id = best['strategy_id']
            logger.info(f"使用最佳策略: {best['strategy_name']} (評分: {best['score']:.2f})")

        # 執行預測
        result = self._predict_with_strategy(strategy_id, history, lottery_rules)

        # 添加策略信息
        result['strategy_used'] = strategy_id
        result['strategy_name'] = best['strategy_name'] if best else '集成預測'
        result['is_best_strategy'] = True

        return result

# 全局評估器實例
strategy_evaluator = StrategyEvaluator()
