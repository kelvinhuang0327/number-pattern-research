#!/usr/bin/env python3
"""
快速策略評估 - 測試所有可用的預測策略
"""

import json
from database import DatabaseManager
from models.unified_predictor import prediction_engine
from datetime import datetime
from predictors import MODEL_DISPATCH
import asyncio

def calculate_match_score(predicted, actual):
    """計算匹配分數"""
    if not predicted or not actual:
        return 0
    predicted_set = set(predicted)
    actual_set = set(actual)
    return len(predicted_set & actual_set)


async def evaluate_strategy(strategy_name, strategy_func, train_data, test_data, lottery_rules):
    """評估單個策略"""
    print(f"\n{'='*60}")
    print(f"評估策略: {strategy_name}")
    print(f"{'='*60}")

    results = {
        'strategy_name': strategy_name,
        'total_tests': 0,
        'match_distribution': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0},
        'total_matches': 0,
        'predictions': [],
        'errors': 0
    }

    try:
        # 測試預測（最近30期）
        for i, test_draw in enumerate(test_data[:30]):
            try:
                # 使用到測試期之前的所有數據進行預測
                history_until_test = train_data + test_data[i+1:]

                # 預測
                prediction = strategy_func(history_until_test, lottery_rules)
                predicted_numbers = prediction.get('numbers', [])

                # 實際號碼
                actual_numbers = test_draw.get('numbers', [])

                # 計算匹配
                matches = calculate_match_score(predicted_numbers, actual_numbers)

                # 記錄結果
                results['total_tests'] += 1
                results['match_distribution'][matches] += 1
                results['total_matches'] += matches

                # 保存詳細預測記錄（只保存前5筆）
                if i < 5:
                    results['predictions'].append({
                        'draw': test_draw.get('draw'),
                        'date': test_draw.get('date'),
                        'predicted': predicted_numbers,
                        'actual': actual_numbers,
                        'matches': matches
                    })

                # 進度顯示
                if (i + 1) % 5 == 0:
                    print(f"  進度: {i + 1}/30")

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
        print(f"  - 測試次數: {results['total_tests']}")
        print(f"  - 平均匹配數: {results.get('avg_matches', 0):.2f}")
        print(f"  - 2+匹配率: {results.get('accuracy_2+', 0):.1f}%")
        print(f"  - 3+匹配率: {results.get('accuracy_3+', 0):.1f}%")
        print(f"  - 錯誤數: {results['errors']}")

    except Exception as e:
        print(f"❌ 策略評估失敗: {e}")
        results['error'] = str(e)

    return results


async def main():
    """主函數"""
    print("="*60)
    print("快速策略評估")
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
    test_size = 30
    test_data = all_data[:test_size]
    train_data = all_data[test_size:]

    print(f"📚 訓練集: {len(train_data)} 期")
    print(f"🧪 測試集: {len(test_data)} 期")
    print()

    # 彩券規則
    lottery_rules = {
        'pickCount': 6,
        'minNumber': 1,
        'maxNumber': 49,
        'lotteryType': lottery_type
    }

    # 測試所有策略
    print(f"將測試 {len(MODEL_DISPATCH)} 個策略\n")

    all_results = []

    for strategy_name, strategy_func in MODEL_DISPATCH.items():
        try:
            result = await evaluate_strategy(
                strategy_name,
                strategy_func,
                train_data,
                test_data,
                lottery_rules
            )
            all_results.append(result)
        except Exception as e:
            print(f"❌ {strategy_name} 評估失敗: {e}")
            all_results.append({
                'strategy_name': strategy_name,
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
    print("📊 策略排名（按平均匹配數）:")
    print()
    print(f"{'排名':<5} {'策略名稱':<25} {'平均匹配':<12} {'2+率':<10} {'3+率':<10} {'4+率':<10}")
    print("-" * 80)

    for i, result in enumerate(valid_results, 1):
        strategy_name = result.get('strategy_name', 'Unknown')
        avg_matches = result.get('avg_matches', 0)
        acc_2 = result.get('accuracy_2+', 0)
        acc_3 = result.get('accuracy_3+', 0)
        acc_4 = result.get('accuracy_4+', 0)

        print(f"{i:<5} {strategy_name:<25} {avg_matches:<12.2f} {acc_2:<10.1f}% {acc_3:<10.1f}% {acc_4:<10.1f}%")

    # 顯示失敗的策略
    failed_results = [r for r in all_results if 'error' in r and 'avg_matches' not in r]
    if failed_results:
        print("\n⚠️ 評估失敗的策略:")
        for result in failed_results:
            error_msg = result.get('error', '')[:100]
            print(f"  - {result.get('strategy_name')}: {error_msg}")

    # 顯示匹配分布（Top 5）
    print("\n📊 Top 5 策略的匹配分布:")
    for i, result in enumerate(valid_results[:5], 1):
        dist = result.get('match_distribution', {})
        print(f"{i}. {result.get('strategy_name')}")
        print(f"   0個: {dist.get(0, 0):2d} | 1個: {dist.get(1, 0):2d} | 2個: {dist.get(2, 0):2d} | 3個: {dist.get(3, 0):2d} | 4個: {dist.get(4, 0):2d} | 5個: {dist.get(5, 0):2d} | 6個: {dist.get(6, 0):2d}")

    # 保存詳細結果到 JSON
    output_file = f"quick_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
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

    # 推薦最佳策略
    if valid_results:
        print("\n🏆 Top 3 推薦策略:")
        for i, result in enumerate(valid_results[:3], 1):
            print(f"{i}. {result.get('strategy_name')}")
            print(f"   - 平均匹配數: {result.get('avg_matches', 0):.2f}")
            print(f"   - 2+匹配率: {result.get('accuracy_2+', 0):.1f}%")
            print(f"   - 3+匹配率: {result.get('accuracy_3+', 0):.1f}%")

    print("\n" + "="*60)
    print("評估完成！")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
