#!/usr/bin/env python3
"""
2025年大樂透三大最佳方法回測分析
測試方法：Markov鏈預測、奇偶平衡預測、區域平衡預測
"""
import sys
import os
from collections import defaultdict
import json
from datetime import datetime

# 添加 lottery_api 到路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import prediction_engine

def calculate_matches(predicted, actual):
    """計算預測與實際的匹配數"""
    pred_set = set(predicted['numbers'])
    actual_set = set(actual['numbers'])
    main_matches = len(pred_set & actual_set)

    # 特別號匹配
    special_match = 0
    if predicted.get('special') and actual.get('special'):
        special_match = 1 if predicted['special'] == actual['special'] else 0

    return {
        'main_matches': main_matches,
        'special_match': special_match,
        'matched_numbers': sorted(list(pred_set & actual_set))
    }

def backtest_method(method_name, display_name, draws_2025, all_draws, rules):
    """對單一方法進行完整回測"""
    print(f"\n{'='*80}")
    print(f"🔍 回測方法: {display_name}")
    print(f"{'='*80}\n")

    results = []
    predictor = prediction_engine
    method = getattr(predictor, method_name)

    # 統計數據
    match_distribution = defaultdict(int)  # 匹配數分布
    total_main_matches = 0
    total_special_matches = 0
    win_cases = []  # 中獎案例（3個以上匹配）

    for i, target_draw in enumerate(draws_2025):
        # 找到目標期數在完整數據中的位置
        target_index = all_draws.index(target_draw)

        # 使用之前的300期作為訓練數據（如果不足則用全部）
        train_start = min(target_index + 1, len(all_draws))
        train_end = min(target_index + 301, len(all_draws))
        history = all_draws[train_start:train_end]

        if len(history) < 50:
            print(f"⚠️  期號 {target_draw['draw']} 訓練數據不足，跳過")
            continue

        try:
            # 執行預測
            prediction = method(history, rules)

            # 計算匹配
            match_result = calculate_matches(prediction, target_draw)

            results.append({
                'draw': target_draw['draw'],
                'date': target_draw['date'],
                'predicted': sorted(prediction['numbers']),
                'predicted_special': prediction.get('special'),
                'actual': sorted(target_draw['numbers']),
                'actual_special': target_draw.get('special'),
                'main_matches': match_result['main_matches'],
                'special_match': match_result['special_match'],
                'matched_numbers': match_result['matched_numbers'],
                'confidence': prediction.get('confidence', 0)
            })

            # 更新統計
            match_count = match_result['main_matches']
            match_distribution[match_count] += 1
            total_main_matches += match_count
            total_special_matches += match_result['special_match']

            # 記錄中獎案例（3個以上）
            if match_count >= 3:
                win_cases.append({
                    'draw': target_draw['draw'],
                    'date': target_draw['date'],
                    'matches': match_count,
                    'numbers': match_result['matched_numbers']
                })

            # 顯示進度
            if (i + 1) % 20 == 0:
                print(f"✓ 已處理 {i + 1}/{len(draws_2025)} 期")

        except Exception as e:
            print(f"❌ 期號 {target_draw['draw']} 預測失敗: {e}")

    # 計算統計指標
    total_tests = len(results)
    avg_main_matches = total_main_matches / total_tests if total_tests > 0 else 0
    special_accuracy = total_special_matches / total_tests if total_tests > 0 else 0
    win_rate = len(win_cases) / total_tests if total_tests > 0 else 0

    # 顯示結果
    print(f"\n{'='*60}")
    print(f"📊 {display_name} - 回測結果總結")
    print(f"{'='*60}\n")

    print(f"測試期數: {total_tests}")
    print(f"平均匹配: {avg_main_matches:.2f} 個一般號碼")
    print(f"特別號準確率: {special_accuracy:.2%}")
    print(f"中獎率 (≥3個): {win_rate:.2%} ({len(win_cases)}/{total_tests} 期)")

    print(f"\n🎯 匹配數分布:")
    for matches in sorted(match_distribution.keys()):
        count = match_distribution[matches]
        percentage = count / total_tests * 100
        bar = '█' * int(percentage / 2)
        print(f"  {matches}個號碼: {count:3d} 期 ({percentage:5.1f}%) {bar}")

    if win_cases:
        print(f"\n🏆 中獎案例 (≥3個匹配):")
        for case in win_cases[:10]:  # 顯示前10個
            print(f"  期號 {case['draw']} ({case['date']}): {case['matches']}/6 - {case['numbers']}")
        if len(win_cases) > 10:
            print(f"  ... 還有 {len(win_cases) - 10} 個案例")
    else:
        print(f"\n⚠️  無中獎案例 (≥3個匹配)")

    return {
        'method': display_name,
        'method_name': method_name,
        'total_tests': total_tests,
        'avg_main_matches': avg_main_matches,
        'special_accuracy': special_accuracy,
        'win_rate': win_rate,
        'win_count': len(win_cases),
        'match_distribution': dict(match_distribution),
        'win_cases': win_cases,
        'detailed_results': results
    }

def main():
    """主程式"""
    print("="*80)
    print("🎯 2025年大樂透三大最佳方法回測分析")
    print("="*80)

    # 載入數據
    db_path = os.path.join(os.path.dirname(__file__), 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = db.get_all_draws('BIG_LOTTO')

    # 篩選2025年數據
    draws_2025 = [d for d in all_draws if d['date'].startswith('2025') or d['date'].startswith('114')]

    print(f"\n📊 數據概況:")
    print(f"  大樂透總期數: {len(all_draws)}")
    print(f"  2025年期數: {len(draws_2025)}")
    print(f"  日期範圍: {draws_2025[-1]['date']} - {draws_2025[0]['date']}")
    print(f"  期號範圍: {draws_2025[-1]['draw']} - {draws_2025[0]['draw']}")

    # 獲取規則
    rules = get_lottery_rules('BIG_LOTTO')

    # 定義要測試的三種方法
    methods = [
        ('markov_predict', 'Markov鏈預測'),
        ('odd_even_balance_predict', '奇偶平衡預測'),
        ('zone_balance_predict', '區域平衡預測'),
    ]

    # 執行回測
    all_results = []
    for method_name, display_name in methods:
        result = backtest_method(method_name, display_name, draws_2025, all_draws, rules)
        all_results.append(result)

    # 生成對比報告
    print(f"\n{'='*80}")
    print(f"🏆 三種方法對比總結")
    print(f"{'='*80}\n")

    # 排序（按平均匹配數）
    all_results.sort(key=lambda x: x['avg_main_matches'], reverse=True)

    print(f"{'方法':<20} {'測試期數':<10} {'平均匹配':<12} {'特別號準確率':<15} {'中獎率(≥3)':<15}")
    print(f"{'-'*80}")

    for result in all_results:
        print(f"{result['method']:<18} "
              f"{result['total_tests']:<10} "
              f"{result['avg_main_matches']:<12.2f} "
              f"{result['special_accuracy']:<15.2%} "
              f"{result['win_rate']:<15.2%}")

    # 儲存詳細報告
    report = {
        'backtest_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'lottery_type': 'BIG_LOTTO',
        'year': '2025',
        'total_periods': len(draws_2025),
        'date_range': f"{draws_2025[-1]['date']} - {draws_2025[0]['date']}",
        'methods_tested': [r['method'] for r in all_results],
        'results': all_results
    }

    report_file = 'BACKTEST_TOP3_METHODS_2025.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 詳細報告已儲存至: {report_file}")

    # 最佳方法推薦
    best = all_results[0]
    print(f"\n{'='*80}")
    print(f"💡 結論與建議")
    print(f"{'='*80}\n")
    print(f"🥇 最佳方法: {best['method']}")
    print(f"   - 平均匹配: {best['avg_main_matches']:.2f} 個號碼")
    print(f"   - 中獎率: {best['win_rate']:.2%} ({best['win_count']}/{best['total_tests']} 期)")
    print(f"   - 特別號準確率: {best['special_accuracy']:.2%}")

    print(f"\n建議使用 {best['method']} 作為大樂透的主要預測方法！")

if __name__ == '__main__':
    main()
