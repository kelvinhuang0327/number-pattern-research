"""
快速模型测试脚本 - 简化版

仅测试10期数据，快速验证模型是否正常工作
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import asyncio
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

from database import db_manager
from models.unified_predictor import prediction_engine
from models.transformer_model import create_transformer_predictor
from models.bayesian_ensemble import create_bayesian_ensemble_predictor
from models.meta_learning import create_meta_learning_predictor
from models.optimized_ensemble import OptimizedEnsemblePredictor


async def quick_test():
    """快速测试"""

    print("\n" + "="*80)
    print("快速模型测试")
    print("="*80)

    # 加载数据
    lottery_type = 'BIG_LOTTO'
    all_data = db_manager.get_all_draws(lottery_type=lottery_type)
    history = all_data[:100]  # 使用最近100期

    if len(history) < 50:
        print(f"❌ 数据不足：仅有 {len(history)} 期")
        return

    print(f"✓ 加载完成: {len(history)} 期数据")

    # 彩票规则
    lottery_rules = {
        'minNumber': 1,
        'maxNumber': 49,
        'pickCount': 6,
        'hasSpecial': True
    }

    # 测试数据（最近10期）
    test_periods = 10
    results = {}

    print(f"\n开始测试 {test_periods} 期...")

    for i in range(test_periods):
        test_idx = i
        train_start = test_idx + 1
        train_data = history[train_start:]

        actual = set(history[test_idx]['numbers'])
        actual_special = history[test_idx].get('special')

        print(f"\n期号 {history[test_idx].get('draw')}:")
        print(f"  实际开奖: {sorted(actual)} + {actual_special}")

        # 1. 测试 Transformer（轻量级）
        try:
            transformer = create_transformer_predictor()
            pred = await transformer.predict(train_data, lottery_rules)
            pred_set = set(pred['numbers'])
            hits = len(pred_set & actual)

            if 'Transformer' not in results:
                results['Transformer'] = []
            results['Transformer'].append(hits)

            print(f"  Transformer: {pred['numbers']} (命中: {hits})")
        except Exception as e:
            print(f"  Transformer 失败: {e}")

        # 2. 测试元学习（轻量级）
        try:
            maml = create_meta_learning_predictor()
            pred = await maml.predict(train_data, lottery_rules)
            pred_set = set(pred['numbers'])
            hits = len(pred_set & actual)

            if '元学习' not in results:
                results['元学习'] = []
            results['元学习'].append(hits)

            print(f"  元学习    : {pred['numbers']} (命中: {hits})")
        except Exception as e:
            print(f"  元学习 失败: {e}")

        # 3. 测试优化集成
        try:
            optimized = OptimizedEnsemblePredictor(prediction_engine)
            pred = optimized.predict_single(train_data, lottery_rules)
            pred_set = set(pred['numbers'])
            hits = len(pred_set & actual)

            if '优化集成' not in results:
                results['优化集成'] = []
            results['优化集成'].append(hits)

            print(f"  优化集成  : {pred['numbers']} (命中: {hits})")
        except Exception as e:
            print(f"  优化集成 失败: {e}")

    # 统计结果
    print("\n" + "="*80)
    print("测试结果统计")
    print("="*80)

    for model_name, hits_list in results.items():
        avg_hits = sum(hits_list) / len(hits_list) if hits_list else 0
        print(f"{model_name:<15} 平均命中: {avg_hits:.2f} ({sum(hits_list)}/{len(hits_list)*6})")

    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(quick_test())
