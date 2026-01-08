#!/usr/bin/env python3
"""
分析哪个预测方法最接近目标号码
"""
import sys
import os

# 添加 lottery-api 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lottery-api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import prediction_engine

def calculate_match_score(predicted_numbers, predicted_special, target_numbers, target_special):
    """计算预测结果与目标的匹配度"""
    main_matches = len(set(predicted_numbers) & set(target_numbers))
    special_match = 1 if predicted_special == target_special else 0
    return {
        'main_matches': main_matches,
        'special_match': special_match,
        'total_score': main_matches + special_match * 0.5  # 特别号权重为0.5
    }

def analyze_predictions_for_target():
    """分析各预测方法对目标号码的表现"""

    # 目标号码
    target_numbers = [1, 3, 12, 33, 39, 41]
    target_special = 29

    print("="*80)
    print(f"🎯 目标号码分析")
    print(f"   一般号码: {sorted(target_numbers)}")
    print(f"   特别号: {target_special}")
    print("="*80)

    # 获取历史数据（使用正确的数据库路径）
    db_path = os.path.join(os.path.dirname(__file__), 'lottery-api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    draws = db.get_all_draws('BIG_LOTTO')

    if len(draws) < 100:
        print("❌ 数据不足，至少需要100期历史数据")
        return

    print(f"\n📊 数据库共有 {len(draws)} 期大乐透记录")
    print(f"   最新期号: {draws[0]['draw']} ({draws[0]['date']})")

    # 查找是否为历史开奖号码
    print(f"\n🔍 在历史记录中搜索此号码组合...")
    found_draw = None
    for draw in draws:
        if sorted(draw['numbers']) == sorted(target_numbers) and draw['special'] == target_special:
            found_draw = draw
            break

    if found_draw:
        print(f"✅ 找到匹配: 期号 {found_draw['draw']} ({found_draw['date']})")
        # 使用该期之前的数据作为训练集
        train_index = draws.index(found_draw)
        if train_index < len(draws) - 100:
            history = draws[train_index + 1:train_index + 301]  # 使用后续300期作为历史
            print(f"   使用期号 {history[-1]['draw']} - {history[0]['draw']} 的数据进行预测")
        else:
            print(f"⚠️  该期号太早，没有足够的历史数据")
            history = draws[:300]
    else:
        print(f"❌ 未在历史记录中找到此号码组合")
        print(f"   将使用最新300期数据进行模拟预测")
        history = draws[:300]

    # 获取规则
    rules = get_lottery_rules('BIG_LOTTO')

    # 使用全局预测引擎单例
    predictor = prediction_engine

    # 定义要测试的预测方法（包含所有可用方法）
    prediction_methods = [
        # 基礎方法
        ('frequency_predict', '頻率預測'),
        ('trend_predict', '趨勢預測'),
        ('deviation_predict', '偏差預測'),

        # 進階統計方法
        ('bayesian_predict', 'Bayesian預測'),
        ('monte_carlo_predict', '蒙特卡洛預測'),
        ('markov_predict', 'Markov鏈預測'),

        # 平衡策略
        ('odd_even_balance_predict', '奇偶平衡預測'),
        ('zone_balance_predict', '區域平衡預測'),
        ('hot_cold_mix_predict', '冷熱混合預測'),
        ('sum_range_predict', '總和範圍預測'),

        # 模式識別
        ('pattern_recognition_predict', '模式識別預測'),
        ('cycle_analysis_predict', '週期分析預測'),
        ('number_pairs_predict', '號碼對預測'),

        # 集成方法
        ('ensemble_predict', '集成預測'),
        ('ensemble_advanced_predict', '進階集成預測'),
        ('dynamic_ensemble_predict', '動態集成預測'),

        # AI 方法
        ('sota_predict', 'SOTA Transformer預測'),
        ('entropy_predict', '熵預測'),
        ('clustering_predict', '聚類預測'),
    ]

    results = []

    print(f"\n{'='*80}")
    print(f"📈 预测方法对比分析")
    print(f"{'='*80}\n")

    for method_name, display_name in prediction_methods:
        try:
            # 执行预测
            method = getattr(predictor, method_name)
            prediction = method(history, rules)

            # 计算匹配度
            score = calculate_match_score(
                prediction['numbers'],
                prediction.get('special'),
                target_numbers,
                target_special
            )

            results.append({
                'method': display_name,
                'method_name': method_name,
                'predicted_numbers': sorted(prediction['numbers']),
                'predicted_special': prediction.get('special'),
                'main_matches': score['main_matches'],
                'special_match': score['special_match'],
                'total_score': score['total_score'],
                'confidence': prediction.get('confidence', 0)
            })

            # 打印详细结果
            print(f"🔹 {display_name}")
            print(f"   預測號碼: {sorted(prediction['numbers'])} + {prediction.get('special')}")
            print(f"   匹配情況: {score['main_matches']}/6 個一般號碼")
            if target_special:
                match_symbol = "✅" if score['special_match'] else "❌"
                print(f"   特別號: {match_symbol} (預測 {prediction.get('special')} vs 目標 {target_special})")
            print(f"   總分: {score['total_score']:.1f} 分")
            print(f"   置信度: {prediction.get('confidence', 0):.2%}\n")

        except Exception as e:
            print(f"❌ {display_name} 執行失敗: {e}\n")

    # 排序并显示最佳方法
    results.sort(key=lambda x: x['total_score'], reverse=True)

    print(f"{'='*80}")
    print(f"🏆 预测方法排名")
    print(f"{'='*80}\n")

    for i, result in enumerate(results, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        print(f"{medal} {result['method']}")
        print(f"   匹配: {result['main_matches']}/6 一般號碼")
        if result['special_match']:
            print(f"   特別號: ✅ 匹配")
        print(f"   總分: {result['total_score']:.1f} 分")
        print(f"   預測: {result['predicted_numbers']} + {result['predicted_special']}\n")

    # 显示共识号码
    print(f"{'='*80}")
    print(f"📊 号码共识分析")
    print(f"{'='*80}\n")

    from collections import Counter
    all_predicted_numbers = []
    for result in results:
        all_predicted_numbers.extend(result['predicted_numbers'])

    consensus = Counter(all_predicted_numbers)

    # 找出在目标号码中的共识号码
    target_set = set(target_numbers)
    consensus_in_target = [(num, count) for num, count in consensus.most_common() if num in target_set]

    if consensus_in_target:
        print("✅ 被多個方法預測且在目標號碼中的號碼:")
        for num, count in consensus_in_target:
            print(f"   號碼 {num:2d}: 被 {count}/{len(results)} 個方法預測")
    else:
        print("❌ 沒有號碼被多個方法共同預測到")

    print(f"\n🔹 所有方法的共識號碼 (按預測頻率排序):")
    for num, count in consensus.most_common(10):
        in_target = "✅" if num in target_set else "  "
        print(f"   {in_target} 號碼 {num:2d}: 被 {count}/{len(results)} 個方法預測")

    return results

if __name__ == '__main__':
    analyze_predictions_for_target()
