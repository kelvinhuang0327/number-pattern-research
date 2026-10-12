#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
綜合所有預測方法，推薦最佳單注
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import db_manager
from models.unified_predictor import prediction_engine
from models.entropy_transformer import EntropyTransformerModel
from models.anti_consensus_sampler import AntiConsensusFilter
from common import get_lottery_rules
from collections import Counter
import numpy as np


def recommend_single_bet(lottery_type='BIG_LOTTO'):
    """綜合所有方法推薦最佳單注"""
    
    # Normalize type
    from common import normalize_lottery_type
    lottery_type = normalize_lottery_type(lottery_type)
    lottery_rules = get_lottery_rules(lottery_type)
    pick_count = lottery_rules['pickCount']
    max_num = lottery_rules['maxNumber']

    print('=' * 100)
    print(f'🎯 最佳單注推薦（綜合所有預測方法）- {lottery_type}')
    print('=' * 100)
    print()

    # 載入數據
    all_draws = db_manager.get_all_draws(lottery_type)
    
    print(f"📊 Using {len(all_draws)} draws")
    history = all_draws[:100]

    print('📊 整合以下預測方法（包含3個新方法）：')
    print('-' * 100)

    all_predictions = {}
    
    # Helper to print result
    def print_viz(name, nums, conf, weight):
        print(f'✓ {name}: {sorted(nums)} (信心度: {conf:.2%})')
        all_predictions[name] = {
            'numbers': nums,
            'confidence': conf,
            'weight': weight
        }

    # ===== 新增的創新方法 =====

    # 1. 元學習集成（最高權重）
    try:
        result = prediction_engine.meta_learning_predict(history, lottery_rules)
        print_viz('元學習集成', result['numbers'], result['confidence'], 2.0)
    except Exception as e:
        print(f'✗ 元學習集成失敗: {e}')

    # 2. 偏差分析（回測冠軍）
    try:
        result = prediction_engine.deviation_predict(history, lottery_rules)
        print_viz('偏差分析', result['numbers'], result['confidence'], 1.5)
    except Exception as e:
        print(f'✗ 偏差分析失敗: {e}')

    # 3. 熵驅動 Transformer
    try:
        result = prediction_engine.entropy_transformer_predict(history, lottery_rules)
        print_viz('熵驅動AI', result['numbers'], result['confidence'], 1.4)
    except Exception as e:
        print(f'✗ 熵驅動AI失敗: {e}')

    # 4. 社群智慧（新增）
    try:
        result = prediction_engine.social_wisdom_predict(history, lottery_rules)
        print_viz('社群智慧', result['numbers'], result['confidence'], 1.2)
    except Exception as e:
        print(f'✗ 社群智慧失敗: {e}')

    # 5. 異常檢測（新增）
    try:
        result = prediction_engine.anomaly_detection_predict(history, lottery_rules)
        print_viz('異常檢測', result['numbers'], result['confidence'], 1.0)
    except Exception as e:
        print(f'✗ 異常檢測失敗: {e}')

    # ===== 傳統方法（權重降低） =====

    # 6. 頻率分析
    try:
        result = prediction_engine.frequency_predict(history, lottery_rules)
        print_viz('頻率分析', result['numbers'], result['confidence'], 0.8)
    except Exception as e:
        print(f'✗ 頻率分析失敗: {e}')

    # 7. 貝葉斯機率
    try:
        result = prediction_engine.bayesian_predict(history, lottery_rules)
        print_viz('貝葉斯機率', result['numbers'], result['confidence'], 0.9)
    except Exception as e:
        print(f'✗ 貝葉斯機率失敗: {e}')

    # 8. 量子隨機（新增，基準線）
    try:
        result = prediction_engine.quantum_random_predict(history, lottery_rules)
        print_viz('量子隨機', result['numbers'], result['confidence'], 0.5)
    except Exception as e:
        print(f'✗ 量子隨機失敗: {e}')

    print()

    # 統計所有號碼的加權分數
    print('=' * 100)
    print('📊 號碼綜合評分（加權投票）')
    print('=' * 100)
    print()

    number_scores = {}

    for method, data in all_predictions.items():
        for num in data['numbers']:
            if num not in number_scores:
                number_scores[num] = 0
            # 加權分數 = 方法權重 * 信心度
            number_scores[num] += data['weight'] * data['confidence']

    # 排序
    sorted_numbers = sorted(number_scores.items(), key=lambda x: -x[1])

    print(f'📈 Top {pick_count + 5} 號碼排名：')
    print('-' * 100)
    for rank, (num, score) in enumerate(sorted_numbers[:pick_count + 10], 1):
        # 計算出現在幾個方法中
        appear_count = sum(1 for data in all_predictions.values() if num in data['numbers'])

        bar_length = int(score * 10)
        bar = '█' * min(bar_length, 50)

        print(f'{rank:2d}. 號碼 {num:02d}: {score:6.3f} {bar} ({appear_count}/{len(all_predictions)}個方法推薦)')

    print()

    # 生成最佳單注
    print('=' * 100)
    print('🌟 最佳單注推薦')
    print('=' * 100)
    print()

    # 選擇 Top N
    top_n_numbers = sorted([num for num, _ in sorted_numbers[:pick_count]])

    print('【方案1】綜合投票法（推薦）⭐ 升級版')
    print('-' * 100)
    print(f'號碼: {" ".join(f"{n:02d}" for n in top_n_numbers)}')
    print()
    print('特點：')
    print(f'  ✓ 綜合 {len(all_predictions)} 種預測方法的投票結果')
    print(f'  ✓ 針對 {lottery_type} 規則優化 (選 {pick_count} 碼)')
    
    # 分析這注的質量
    analysis = analyze_bet_quality(top_n_numbers, all_predictions, pick_count)

    print('品質分析：')
    print(f'  • 出現在 {analysis["consensus_count"]}/{len(all_predictions)} 個方法中')
    print(f'  • 共識號碼: {", ".join(f"{n:02d}" for n in analysis["consensus_numbers"])} ({len(analysis["consensus_numbers"])}個)')
    print(f'  • 獨特號碼: {", ".join(f"{n:02d}" for n in analysis["unique_numbers"])} ({len(analysis["unique_numbers"])}個)')
    print(f'  • 奇偶比: {analysis["odd_count"]}:{pick_count-analysis["odd_count"]}')
    print(f'  • 號碼和值: {sum(top_n_numbers)}')
    print()

    # 替代方案
    print('=' * 100)
    print('🎯 替代方案')
    print('=' * 100)
    print()

    # 方案2：元學習集成
    if '元學習集成' in all_predictions:
        meta_nums = sorted(all_predictions['元學習集成']['numbers'])
        print('【方案2】元學習集成（推薦）⭐ 新方法')
        print('-' * 100)
        print(f'號碼: {" ".join(f"{n:02d}" for n in meta_nums)}')
        print(f'特點: 整合5大創新方法（熵驅動+偏差+社群+異常+量子）')
        print()

    # 方案3：社群智慧
    if '社群智慧' in all_predictions:
        social_nums = sorted(all_predictions['社群智慧']['numbers'])
        print('【方案3】社群智慧（獨得獎金）⭐ 新方法')
        print('-' * 100)
        print(f'號碼: {" ".join(f"{n:02d}" for n in social_nums)}')
        print(f'特點: 避開熱門號碼，適合追求獨得獎金')
        print()

    # 最終建議
    print('=' * 100)
    print('💡 最終建議')
    print('=' * 100)
    print()

    print(f'如果您只買 1注，我推薦：')
    print()
    print('┌─────────────────────────────────────────────────────────┐')
    print('│                                                         │')
    print(f'│  🌟 方案1：{" ".join(f"{n:02d}" for n in top_n_numbers)}  🌟  │')
    print('│                                                         │')
    print('└─────────────────────────────────────────────────────────┘')
    print()

    return {
        'consensus': top_n_numbers,
        'meta_learning': meta_nums if '元學習集成' in all_predictions else [],
        'social_wisdom': social_nums if '社群智慧' in all_predictions else [],
        'deviation': [] if '偏差分析' not in all_predictions else sorted(all_predictions['偏差分析']['numbers']),
        'all_methods': list(all_predictions.keys())
    }


def analyze_bet_quality(numbers, all_predictions, pick_count=6):
    """分析這注號碼的質量"""
    # 統計出現在幾個方法中
    appearance_count = {}
    for num in numbers:
        count = sum(1 for data in all_predictions.values() if num in data['numbers'])
        appearance_count[num] = count

    # 共識號碼（出現在多數方法中）
    consensus = [num for num, count in appearance_count.items() if count >= len(all_predictions) / 2]
    unique = [num for num, count in appearance_count.items() if count < len(all_predictions) / 2]

    # 奇偶
    odd_count = sum(1 for num in numbers if num % 2 == 1)

    return {
        'consensus_count': max(appearance_count.values()) if appearance_count else 0,
        'consensus_numbers': sorted(consensus),
        'unique_numbers': sorted(unique),
        'odd_count': odd_count
    }


if __name__ == '__main__':
    target = 'BIG_LOTTO'
    if len(sys.argv) > 1:
        target = sys.argv[1]
    recommend_single_bet(target)
