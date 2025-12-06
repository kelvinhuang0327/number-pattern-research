"""
高级模型性能测试脚本

测试新实现的高级模型：
1. Transformer (PatchTST)
2. 贝叶斯优化集成
3. 元学习 (MAML)

与现有模型对比性能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import asyncio
import json
import logging
from typing import List, Dict
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入数据库和模型
from database import db_manager
from models.unified_predictor import prediction_engine
from models.transformer_model import create_transformer_predictor
from models.bayesian_ensemble import create_bayesian_ensemble_predictor
from models.meta_learning import create_meta_learning_predictor
from models.optimized_ensemble import OptimizedEnsemblePredictor


class ModelTester:
    """模型测试器"""

    def __init__(self, lottery_type: str = 'BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.history = []
        self.lottery_rules = {}

    async def load_data(self, limit: int = 200):
        """加载历史数据"""
        logger.info(f"加载 {self.lottery_type} 历史数据...")

        # 从数据库加载
        all_data = db_manager.get_all_draws(lottery_type=self.lottery_type)

        # 取最近的 limit 期
        self.history = all_data[:limit]

        if len(self.history) < 50:
            raise ValueError(f"数据不足，仅有 {len(self.history)} 期")

        # 设置彩票规则
        if self.lottery_type == 'BIG_LOTTO':
            self.lottery_rules = {
                'minNumber': 1,
                'maxNumber': 49,
                'pickCount': 6,
                'hasSpecial': True
            }
        elif self.lottery_type == 'POWER_LOTTO':
            self.lottery_rules = {
                'minNumber': 1,
                'maxNumber': 38,
                'pickCount': 6,
                'hasSpecial': True
            }
        else:
            self.lottery_rules = {
                'minNumber': 1,
                'maxNumber': 49,
                'pickCount': 6,
                'hasSpecial': False
            }

        logger.info(f"✓ 加载完成: {len(self.history)} 期数据")

    def calculate_hit_rate(
        self,
        predicted: List[int],
        actual: List[int],
        special_predicted: int = None,
        special_actual: int = None
    ) -> Dict:
        """
        计算命中率

        Returns:
            {
                'main_hits': 主号命中数,
                'special_hit': 特别号是否命中,
                'total_hits': 总命中数（含特别号）
            }
        """
        predicted_set = set(predicted)
        actual_set = set(actual)

        main_hits = len(predicted_set & actual_set)
        special_hit = (special_predicted == special_actual) if special_actual else False
        total_hits = main_hits + (1 if special_hit else 0)

        return {
            'main_hits': main_hits,
            'special_hit': special_hit,
            'total_hits': total_hits
        }

    async def test_model(
        self,
        model_name: str,
        predict_func,
        backtest_periods: int = 30,
        training_window: int = 100
    ) -> Dict:
        """
        测试单个模型

        Args:
            model_name: 模型名称
            predict_func: 预测函数
            backtest_periods: 回测期数
            training_window: 训练窗口

        Returns:
            测试结果统计
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"测试模型: {model_name}")
        logger.info(f"{'='*60}")

        results = {
            'model': model_name,
            'total_tests': 0,
            'total_main_hits': 0,
            'total_special_hits': 0,
            'hit_details': [],
            'avg_main_hits': 0.0,
            'special_hit_rate': 0.0
        }

        for i in range(backtest_periods):
            test_idx = i
            train_start = test_idx + 1
            train_end = train_start + training_window

            if train_end > len(self.history):
                break

            # 训练数据
            train_data = self.history[train_start:train_end]
            # 实际结果
            actual_draw = self.history[test_idx]
            actual_numbers = actual_draw['numbers']
            actual_special = actual_draw.get('special')

            try:
                # 执行预测
                prediction = await predict_func(train_data, self.lottery_rules)

                predicted_numbers = prediction.get('numbers', [])
                predicted_special = prediction.get('special')

                # 计算命中
                hits = self.calculate_hit_rate(
                    predicted_numbers,
                    actual_numbers,
                    predicted_special,
                    actual_special
                )

                results['total_main_hits'] += hits['main_hits']
                if hits['special_hit']:
                    results['total_special_hits'] += 1

                results['hit_details'].append({
                    'draw': actual_draw.get('draw'),
                    'predicted': predicted_numbers,
                    'actual': actual_numbers,
                    'main_hits': hits['main_hits'],
                    'special_hit': hits['special_hit']
                })

                results['total_tests'] += 1

                if (i + 1) % 10 == 0:
                    logger.info(f"  进度: {i+1}/{backtest_periods}")

            except Exception as e:
                logger.error(f"  测试失败 (期号 {test_idx}): {e}")
                continue

        # 计算统计
        if results['total_tests'] > 0:
            results['avg_main_hits'] = results['total_main_hits'] / results['total_tests']
            results['special_hit_rate'] = results['total_special_hits'] / results['total_tests']

        logger.info(f"\n{model_name} 测试结果:")
        logger.info(f"  测试期数: {results['total_tests']}")
        logger.info(f"  平均主号命中: {results['avg_main_hits']:.2f}")
        logger.info(f"  特别号命中率: {results['special_hit_rate']:.1%}")

        return results

    async def run_all_tests(self, backtest_periods: int = 30):
        """运行所有模型测试"""

        all_results = []

        # 1. 测试原有优化集成
        logger.info("\n" + "="*80)
        logger.info("1. 测试原有优化集成")
        logger.info("="*80)

        optimized_ensemble = OptimizedEnsemblePredictor(prediction_engine)
        result1 = await self.test_model(
            "优化集成 (Original)",
            lambda h, r: asyncio.coroutine(lambda: optimized_ensemble.predict_single(h, r))(),
            backtest_periods=backtest_periods
        )
        all_results.append(result1)

        # 2. 测试 Transformer
        logger.info("\n" + "="*80)
        logger.info("2. 测试 Transformer (PatchTST)")
        logger.info("="*80)

        transformer = create_transformer_predictor()
        result2 = await self.test_model(
            "Transformer (PatchTST)",
            transformer.predict,
            backtest_periods=backtest_periods
        )
        all_results.append(result2)

        # 3. 测试贝叶斯优化集成
        logger.info("\n" + "="*80)
        logger.info("3. 测试贝叶斯优化集成")
        logger.info("="*80)

        bayesian_ensemble = create_bayesian_ensemble_predictor(
            prediction_engine,
            n_iterations=15  # 减少迭代以加快测试
        )
        result3 = await self.test_model(
            "贝叶斯优化集成",
            bayesian_ensemble.predict,
            backtest_periods=min(backtest_periods, 20)  # 贝叶斯优化较慢，减少测试期数
        )
        all_results.append(result3)

        # 4. 测试元学习
        logger.info("\n" + "="*80)
        logger.info("4. 测试元学习 (MAML)")
        logger.info("="*80)

        meta_learning = create_meta_learning_predictor()
        result4 = await self.test_model(
            "元学习 (MAML)",
            meta_learning.predict,
            backtest_periods=backtest_periods
        )
        all_results.append(result4)

        # 5. 输出对比总结
        self.print_comparison(all_results)

        # 6. 保存结果
        self.save_results(all_results)

        return all_results

    def print_comparison(self, results: List[Dict]):
        """打印对比结果"""

        logger.info("\n" + "="*80)
        logger.info("性能对比总结")
        logger.info("="*80)

        # 按平均命中数排序
        sorted_results = sorted(results, key=lambda x: x['avg_main_hits'], reverse=True)

        print("\n{:<30} {:<15} {:<15} {:<15}".format(
            "模型", "测试期数", "平均主号命中", "特别号命中率"
        ))
        print("-" * 80)

        for result in sorted_results:
            print("{:<30} {:<15} {:<15.2f} {:<15.1%}".format(
                result['model'],
                result['total_tests'],
                result['avg_main_hits'],
                result['special_hit_rate']
            ))

        print("\n" + "="*80)

        # 找出最佳模型
        best_model = sorted_results[0]
        improvement = (best_model['avg_main_hits'] - sorted_results[-1]['avg_main_hits']) / sorted_results[-1]['avg_main_hits'] * 100

        logger.info(f"\n🏆 最佳模型: {best_model['model']}")
        logger.info(f"   平均命中: {best_model['avg_main_hits']:.2f}")
        logger.info(f"   相比最差提升: {improvement:.1f}%")

    def save_results(self, results: List[Dict]):
        """保存测试结果到文件"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"advanced_models_test_{self.lottery_type}_{timestamp}.json"
        filepath = os.path.join(
            os.path.dirname(__file__),
            '..',
            'data',
            filename
        )

        # 移除 hit_details（数据太大）
        results_to_save = []
        for r in results:
            r_copy = r.copy()
            r_copy.pop('hit_details', None)
            results_to_save.append(r_copy)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'lottery_type': self.lottery_type,
                'timestamp': timestamp,
                'results': results_to_save
            }, f, indent=2, ensure_ascii=False)

        logger.info(f"\n✓ 结果已保存到: {filepath}")


async def main():
    """主函数"""

    logger.info("="*80)
    logger.info("高级模型性能测试")
    logger.info("="*80)

    # 创建测试器
    tester = ModelTester(lottery_type='BIG_LOTTO')

    # 加载数据
    await tester.load_data(limit=150)

    # 运行测试（减少回测期数以加快速度）
    await tester.run_all_tests(backtest_periods=20)

    logger.info("\n" + "="*80)
    logger.info("测试完成！")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
