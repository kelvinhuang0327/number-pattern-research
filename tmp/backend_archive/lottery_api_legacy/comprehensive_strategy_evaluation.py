#!/usr/bin/env python3
"""
全面預測策略評估
測試所有預測方法在大樂透數據上的準確度
"""

import sys
import json
from database import DatabaseManager
from common import get_related_lottery_types
from datetime import datetime

# 導入所有可用的預測模型
available_models = {}

model_imports = {
    'LSTMPredictor': 'models.lstm_model',
    'XGBoostPredictor': 'models.xgboost_model',
    'ProphetPredictor': 'models.prophet_model',
    'TransformerPredictor': 'models.transformer_model',
    'BayesianEnsemble': 'models.bayesian_ensemble',
    'MetaLearningPredictor': 'models.meta_learning',
    'UnifiedPredictor': 'models.unified_predictor',
    'OptimizedEnsemble': 'models.optimized_ensemble',
    'AutoGluonPredictor': 'models.autogluon_model',
}

for model_name, module_name in model_imports.items():
    try:
        module = __import__(module_name, fromlist=[model_name])
        available_models[model_name] = getattr(module, model_name)
    except Exception as e:
        print(f"⚠️ {model_name} 導入失敗: {e}")

print(f"✅ 成功導入 {len(available_models)} 個模型")


def calculate_match_score(predicted, actual):
    """
    計算預測匹配分數

    Args:
        predicted: 預測的號碼列表
        actual: 實際開獎號碼列表

    Returns:
        匹配數量
    """
    if not predicted or not actual:
        return 0

    predicted_set = set(predicted)
    actual_set = set(actual)
    matches = len(predicted_set & actual_set)
    return matches


def evaluate_model(model, model_name, train_data, test_data, lottery_type='BIG_LOTTO'):
    """
    評估單個模型的性能

    Args:
        model: 預測模型實例
        model_name: 模型名稱
        train_data: 訓練數據
        test_data: 測試數據
        lottery_type: 彩券類型

    Returns:
        評估結果字典
    """
    print(f"\n{'='*60}")
    print(f"評估模型: {model_name}")
    print(f"{'='*60}")

    results = {
        'model_name': model_name,
        'total_tests': 0,
        'match_distribution': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0},
        'total_matches': 0,
        'predictions': [],
        'errors': 0
    }

    try:
        # 訓練模型
        print(f"📚 訓練數據量: {len(train_data)} 期")
        model.train(train_data, lottery_type=lottery_type)
        print("✅ 模型訓練完成")

        # 測試預測
        print(f"🧪 測試數據量: {len(test_data)} 期")

        for i, test_draw in enumerate(test_data[:50]):  # 測試最近50期
            try:
                # 預測
                prediction = model.predict(lottery_type=lottery_type)
                predicted_numbers = prediction.get('numbers', [])

                # 實際號碼
                actual_numbers = test_draw.get('numbers', [])

                # 計算匹配
                matches = calculate_match_score(predicted_numbers, actual_numbers)

                # 記錄結果
                results['total_tests'] += 1
                results['match_distribution'][matches] += 1
                results['total_matches'] += matches

                # 保存詳細預測記錄（只保存前10筆）
                if i < 10:
                    results['predictions'].append({
                        'draw': test_draw.get('draw'),
                        'date': test_draw.get('date'),
                        'predicted': predicted_numbers,
                        'actual': actual_numbers,
                        'matches': matches
                    })

                # 進度顯示
                if (i + 1) % 10 == 0:
                    print(f"  進度: {i + 1}/50")

            except Exception as e:
                print(f"  ⚠️ 預測失敗 (第 {i+1} 期): {e}")
                results['errors'] += 1
                continue

        # 計算統計指標
        if results['total_tests'] > 0:
            results['avg_matches'] = results['total_matches'] / results['total_tests']
            results['accuracy_2+'] = sum(results['match_distribution'][i] for i in range(2, 7)) / results['total_tests'] * 100
            results['accuracy_3+'] = sum(results['match_distribution'][i] for i in range(3, 7)) / results['total_tests'] * 100
            results['accuracy_4+'] = sum(results['match_distribution'][i] for i in range(4, 7)) / results['total_tests'] * 100

        print(f"✅ 評估完成")
        print(f"  - 平均匹配數: {results.get('avg_matches', 0):.2f}")
        print(f"  - 2+匹配率: {results.get('accuracy_2+', 0):.1f}%")
        print(f"  - 3+匹配率: {results.get('accuracy_3+', 0):.1f}%")

    except Exception as e:
        print(f"❌ 模型評估失敗: {e}")
        results['error'] = str(e)

    return results


def main():
    """主函數"""
    print("="*60)
    print("全面預測策略評估")
    print("="*60)
    print()

    # 初始化數據庫
    db = DatabaseManager()

    # 獲取大樂透數據（包含加開）
    lottery_type = 'BIG_LOTTO'
    print(f"📊 加載 {lottery_type} 數據（包含相關類型）...")

    all_data = db.get_all_draws(lottery_type)
    print(f"✅ 數據加載完成: {len(all_data)} 期")

    # 統計數據分布
    type_distribution = {}
    for draw in all_data:
        lt = draw.get('lotteryType', 'unknown')
        type_distribution[lt] = type_distribution.get(lt, 0) + 1

    print(f"\n📊 數據分布:")
    for lt, count in sorted(type_distribution.items()):
        print(f"  - {lt}: {count} 期")
    print()

    # 分割訓練集和測試集
    # 使用最新的50期作為測試集，其餘作為訓練集
    test_size = 50
    test_data = all_data[:test_size]
    train_data = all_data[test_size:]

    print(f"📚 訓練集: {len(train_data)} 期")
    print(f"🧪 測試集: {len(test_data)} 期")
    print()

    # 定義要測試的模型
    models_to_test = []

    # 嘗試初始化每個模型
    model_mapping = {
        'XGBoost': 'XGBoostPredictor',
        'Prophet': 'ProphetPredictor',
        'LSTM': 'LSTMPredictor',
        'Transformer': 'TransformerPredictor',
        'Bayesian Ensemble': 'BayesianEnsemble',
        'Meta Learning': 'MetaLearningPredictor',
        'Optimized Ensemble': 'OptimizedEnsemble',
        'Unified Predictor': 'UnifiedPredictor',
        'AutoGluon': 'AutoGluonPredictor',
    }

    for name, model_class_name in model_mapping.items():
        if model_class_name not in available_models:
            continue
        model_class = available_models[model_class_name]
        try:
            model = model_class()
            models_to_test.append((name, model))
            print(f"✅ {name} 已加載")
        except Exception as e:
            print(f"⚠️ {name} 加載失敗: {e}")

    print(f"\n將測試 {len(models_to_test)} 個模型\n")

    # 評估所有模型
    all_results = []

    for model_name, model in models_to_test:
        try:
            result = evaluate_model(model, model_name, train_data, test_data, lottery_type)
            all_results.append(result)
        except Exception as e:
            print(f"❌ {model_name} 評估失敗: {e}")
            all_results.append({
                'model_name': model_name,
                'error': str(e)
            })

    # 生成報告
    print("\n" + "="*60)
    print("評估結果總結")
    print("="*60)
    print()

    # 排序（按平均匹配數）
    valid_results = [r for r in all_results if 'avg_matches' in r]
    valid_results.sort(key=lambda x: x.get('avg_matches', 0), reverse=True)

    # 顯示排名
    print("📊 模型排名（按平均匹配數）:")
    print()
    print(f"{'排名':<5} {'模型名稱':<25} {'平均匹配':<12} {'2+率':<10} {'3+率':<10} {'4+率':<10}")
    print("-" * 80)

    for i, result in enumerate(valid_results, 1):
        model_name = result.get('model_name', 'Unknown')
        avg_matches = result.get('avg_matches', 0)
        acc_2 = result.get('accuracy_2+', 0)
        acc_3 = result.get('accuracy_3+', 0)
        acc_4 = result.get('accuracy_4+', 0)

        print(f"{i:<5} {model_name:<25} {avg_matches:<12.2f} {acc_2:<10.1f}% {acc_3:<10.1f}% {acc_4:<10.1f}%")

    # 顯示失敗的模型
    failed_results = [r for r in all_results if 'error' in r and 'avg_matches' not in r]
    if failed_results:
        print("\n⚠️ 評估失敗的模型:")
        for result in failed_results:
            print(f"  - {result.get('model_name')}: {result.get('error')}")

    # 保存詳細結果到 JSON
    output_file = f"strategy_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'evaluation_time': datetime.now().isoformat(),
            'lottery_type': lottery_type,
            'data_distribution': type_distribution,
            'train_size': len(train_data),
            'test_size': len(test_data),
            'results': all_results
        }, f, indent=2, ensure_ascii=False)

    print(f"\n💾 詳細結果已保存到: {output_file}")

    # 推薦最佳模型
    if valid_results:
        best_model = valid_results[0]
        print(f"\n🏆 推薦使用模型: {best_model.get('model_name')}")
        print(f"  - 平均匹配數: {best_model.get('avg_matches', 0):.2f}")
        print(f"  - 2+匹配率: {best_model.get('accuracy_2+', 0):.1f}%")
        print(f"  - 3+匹配率: {best_model.get('accuracy_3+', 0):.1f}%")
        print(f"  - 4+匹配率: {best_model.get('accuracy_4+', 0):.1f}%")

    print("\n" + "="*60)
    print("評估完成！")
    print("="*60)


if __name__ == "__main__":
    main()
