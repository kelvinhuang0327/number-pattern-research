#!/usr/bin/env python3
"""
2025年雙注策略滾動回測
驗證單注 vs 雙注各模式的真實成功率
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from common import load_backend_history, get_lottery_rules
import json
from collections import defaultdict
from datetime import datetime

def get_2025_draws(lottery_type='BIG_LOTTO'):
    """獲取2025年所有開獎數據"""
    all_draws = db_manager.get_all_draws(lottery_type)

    # 過濾2025年數據
    draws_2025 = []
    for draw in all_draws:
        date_str = draw.get('date', '')
        if date_str.startswith('2025'):
            draws_2025.append(draw)

    # 按期號排序（從大到小，最新的在前）
    draws_2025.sort(key=lambda x: x.get('draw', ''), reverse=True)

    return draws_2025

def rolling_backtest_single_strategy(draws_2025, rules, strategy_name, min_history=50):
    """
    滾動回測單一策略

    Args:
        draws_2025: 2025年開獎數據（按時間倒序）
        rules: 彩票規則
        strategy_name: 策略名稱
        min_history: 最少歷史數據量

    Returns:
        回測結果列表
    """
    results = []

    # 從第min_history期開始回測（確保有足夠歷史數據）
    for i in range(len(draws_2025) - min_history):
        target_draw = draws_2025[i]
        history = draws_2025[i+1:]  # 使用之後的期數作為歷史（因為是倒序）

        target_numbers = target_draw.get('numbers', [])
        target_id = target_draw.get('draw', '')
        target_date = target_draw.get('date', '')

        # 執行預測
        try:
            if strategy_name == 'frequency':
                result = prediction_engine.frequency_predict(history, rules)
            elif strategy_name == 'bayesian':
                result = prediction_engine.bayesian_predict(history, rules)
            elif strategy_name == 'ensemble':
                result = prediction_engine.ensemble_predict(history, rules)
            elif strategy_name == 'monte_carlo':
                result = prediction_engine.monte_carlo_predict(history, rules)
            else:
                continue

            predicted = result['numbers']
            matches = set(predicted) & set(target_numbers)
            match_count = len(matches)

            results.append({
                'draw_id': target_id,
                'date': target_date,
                'predicted': predicted,
                'actual': target_numbers,
                'matches': sorted(list(matches)),
                'match_count': match_count,
                'hit_rate': match_count / len(target_numbers)
            })

        except Exception as e:
            print(f"  ⚠️ {target_id} 預測失敗: {e}")
            continue

    return results

def rolling_backtest_double_bet(draws_2025, rules, mode='optimal', min_history=50):
    """
    滾動回測雙注策略

    Args:
        draws_2025: 2025年開獎數據（按時間倒序）
        rules: 彩票規則
        mode: 雙注模式
        min_history: 最少歷史數據量

    Returns:
        回測結果列表
    """
    results = []

    for i in range(len(draws_2025) - min_history):
        target_draw = draws_2025[i]
        history = draws_2025[i+1:]

        target_numbers = target_draw.get('numbers', [])
        target_id = target_draw.get('draw', '')
        target_date = target_draw.get('date', '')

        # 執行雙注預測
        try:
            result = prediction_engine.generate_double_bet(history, rules, mode=mode)

            bet1_numbers = result['bet1']['numbers']
            bet2_numbers = result['bet2']['numbers']

            # 計算命中
            bet1_matches = set(bet1_numbers) & set(target_numbers)
            bet2_matches = set(bet2_numbers) & set(target_numbers)
            combined_matches = set(bet1_numbers + bet2_numbers) & set(target_numbers)

            results.append({
                'draw_id': target_id,
                'date': target_date,
                'bet1': {
                    'predicted': bet1_numbers,
                    'matches': sorted(list(bet1_matches)),
                    'match_count': len(bet1_matches)
                },
                'bet2': {
                    'predicted': bet2_numbers,
                    'matches': sorted(list(bet2_matches)),
                    'match_count': len(bet2_matches)
                },
                'combined': {
                    'coverage': len(set(bet1_numbers + bet2_numbers)),
                    'overlap': len(set(bet1_numbers) & set(bet2_numbers)),
                    'matches': sorted(list(combined_matches)),
                    'match_count': len(combined_matches),
                    'hit_rate': len(combined_matches) / len(target_numbers)
                },
                'actual': target_numbers
            })

        except Exception as e:
            print(f"  ⚠️ {target_id} 雙注預測失敗: {e}")
            continue

    return results

def analyze_results(results, strategy_name):
    """分析回測結果"""
    if not results:
        return {}

    total_draws = len(results)
    total_matches = sum(r['match_count'] for r in results)
    avg_match = total_matches / total_draws

    # 統計不同命中數的期數
    match_distribution = defaultdict(int)
    for r in results:
        match_distribution[r['match_count']] += 1

    # 計算中獎期數（3個以上視為中獎）
    win_3plus = sum(1 for r in results if r['match_count'] >= 3)
    win_4plus = sum(1 for r in results if r['match_count'] >= 4)
    win_5plus = sum(1 for r in results if r['match_count'] >= 5)
    win_6 = sum(1 for r in results if r['match_count'] == 6)

    return {
        'strategy': strategy_name,
        'total_draws': total_draws,
        'total_matches': total_matches,
        'avg_match': avg_match,
        'avg_hit_rate': avg_match / 6 * 100,
        'match_distribution': dict(match_distribution),
        'win_3plus': win_3plus,
        'win_4plus': win_4plus,
        'win_5plus': win_5plus,
        'win_6': win_6,
        'win_3plus_rate': win_3plus / total_draws * 100,
        'win_4plus_rate': win_4plus / total_draws * 100
    }

def analyze_double_bet_results(results, mode_name):
    """分析雙注回測結果"""
    if not results:
        return {}

    total_draws = len(results)

    # 統計組合命中
    total_combined_matches = sum(r['combined']['match_count'] for r in results)
    avg_combined_match = total_combined_matches / total_draws

    # 統計單注命中
    total_bet1_matches = sum(r['bet1']['match_count'] for r in results)
    total_bet2_matches = sum(r['bet2']['match_count'] for r in results)

    # 統計覆蓋率和重疊
    avg_coverage = sum(r['combined']['coverage'] for r in results) / total_draws
    avg_overlap = sum(r['combined']['overlap'] for r in results) / total_draws

    # 命中數分布
    match_distribution = defaultdict(int)
    for r in results:
        match_distribution[r['combined']['match_count']] += 1

    # 中獎統計
    win_3plus = sum(1 for r in results if r['combined']['match_count'] >= 3)
    win_4plus = sum(1 for r in results if r['combined']['match_count'] >= 4)
    win_5plus = sum(1 for r in results if r['combined']['match_count'] >= 5)
    win_6 = sum(1 for r in results if r['combined']['match_count'] == 6)

    return {
        'mode': mode_name,
        'total_draws': total_draws,
        'combined': {
            'total_matches': total_combined_matches,
            'avg_match': avg_combined_match,
            'avg_hit_rate': avg_combined_match / 6 * 100,
        },
        'bet1': {
            'total_matches': total_bet1_matches,
            'avg_match': total_bet1_matches / total_draws
        },
        'bet2': {
            'total_matches': total_bet2_matches,
            'avg_match': total_bet2_matches / total_draws
        },
        'coverage': {
            'avg_coverage': avg_coverage,
            'avg_overlap': avg_overlap,
            'complementary_rate': (avg_coverage - avg_overlap) / 12 * 100
        },
        'match_distribution': dict(match_distribution),
        'wins': {
            '3plus': win_3plus,
            '4plus': win_4plus,
            '5plus': win_5plus,
            '6': win_6,
            '3plus_rate': win_3plus / total_draws * 100,
            '4plus_rate': win_4plus / total_draws * 100
        }
    }

def print_comparison_table(single_results, double_results):
    """打印對比表格"""
    print("\n" + "=" * 100)
    print("【2025年滾動回測對比 - 單注 vs 雙注】")
    print("=" * 100)

    print(f"\n{'策略':<20} {'測試期數':<10} {'平均命中':<10} {'命中率':<10} {'3+中獎率':<12} {'4+中獎率':<12}")
    print("-" * 100)

    # 打印單注結果
    for analysis in single_results:
        name = analysis['strategy']
        total = analysis['total_draws']
        avg = analysis['avg_match']
        hit_rate = analysis['avg_hit_rate']
        win3 = analysis['win_3plus_rate']
        win4 = analysis['win_4plus_rate']

        print(f"{name:<20} {total:<10} {avg:<10.2f} {hit_rate:<10.1f}% {win3:<12.1f}% {win4:<12.1f}%")

    print("-" * 100)

    # 打印雙注結果
    for analysis in double_results:
        name = f"雙注-{analysis['mode']}"
        total = analysis['total_draws']
        avg = analysis['combined']['avg_match']
        hit_rate = analysis['combined']['avg_hit_rate']
        win3 = analysis['wins']['3plus_rate']
        win4 = analysis['wins']['4plus_rate']

        marker = " ⭐" if hit_rate > 50 else ""
        print(f"{name:<20} {total:<10} {avg:<10.2f} {hit_rate:<10.1f}%{marker} {win3:<12.1f}% {win4:<12.1f}%")

def print_detailed_analysis(analysis, is_double=False):
    """打印詳細分析"""
    print("\n" + "=" * 80)
    if is_double:
        print(f"【雙注模式詳細分析 - {analysis['mode']}】")
    else:
        print(f"【單注策略詳細分析 - {analysis['strategy']}】")
    print("=" * 80)

    if is_double:
        print(f"\n測試期數: {analysis['total_draws']}期")
        print(f"\n組合表現:")
        print(f"  平均命中: {analysis['combined']['avg_match']:.2f}個/期")
        print(f"  命中率: {analysis['combined']['avg_hit_rate']:.1f}%")

        print(f"\n單注表現:")
        print(f"  注1平均: {analysis['bet1']['avg_match']:.2f}個/期")
        print(f"  注2平均: {analysis['bet2']['avg_match']:.2f}個/期")

        print(f"\n覆蓋效率:")
        print(f"  平均覆蓋: {analysis['coverage']['avg_coverage']:.1f}個號碼")
        print(f"  平均重疊: {analysis['coverage']['avg_overlap']:.1f}個號碼")
        print(f"  互補性: {analysis['coverage']['complementary_rate']:.1f}%")

        print(f"\n命中數分布:")
        for match_count in sorted(analysis['match_distribution'].keys(), reverse=True):
            count = analysis['match_distribution'][match_count]
            rate = count / analysis['total_draws'] * 100
            bar = "█" * int(rate / 2)
            print(f"  {match_count}個: {count:3d}期 ({rate:5.1f}%) {bar}")

        print(f"\n中獎統計:")
        print(f"  3+號碼: {analysis['wins']['3plus']}期 ({analysis['wins']['3plus_rate']:.1f}%)")
        print(f"  4+號碼: {analysis['wins']['4plus']}期 ({analysis['wins']['4plus_rate']:.1f}%)")
        print(f"  5+號碼: {analysis['wins']['5plus']}期")
        print(f"  全中(6): {analysis['wins']['6']}期")
    else:
        print(f"\n測試期數: {analysis['total_draws']}期")
        print(f"總命中數: {analysis['total_matches']}個")
        print(f"平均命中: {analysis['avg_match']:.2f}個/期")
        print(f"命中率: {analysis['avg_hit_rate']:.1f}%")

        print(f"\n命中數分布:")
        for match_count in sorted(analysis['match_distribution'].keys(), reverse=True):
            count = analysis['match_distribution'][match_count]
            rate = count / analysis['total_draws'] * 100
            bar = "█" * int(rate / 2)
            print(f"  {match_count}個: {count:3d}期 ({rate:5.1f}%) {bar}")

        print(f"\n中獎統計:")
        print(f"  3+號碼: {analysis['win_3plus']}期 ({analysis['win_3plus_rate']:.1f}%)")
        print(f"  4+號碼: {analysis['win_4plus']}期 ({analysis['win_4plus_rate']:.1f}%)")
        print(f"  5+號碼: {analysis['win_5plus']}期")
        print(f"  全中(6): {analysis['win_6']}期")

def main():
    """主函數"""
    print("\n")
    print("╔" + "═" * 98 + "╗")
    print("║" + " " * 30 + "2025年雙注策略滾動回測" + " " * 38 + "║")
    print("╚" + "═" * 98 + "╝")

    lottery_type = 'BIG_LOTTO'
    rules = get_lottery_rules(lottery_type)

    # 獲取2025年數據
    print("\n正在載入2025年開獎數據...")
    draws_2025 = get_2025_draws(lottery_type)

    if not draws_2025:
        print("❌ 未找到2025年數據")
        return

    print(f"✓ 找到2025年數據: {len(draws_2025)}期")
    print(f"  期號範圍: {draws_2025[-1]['draw']} ~ {draws_2025[0]['draw']}")
    print(f"  日期範圍: {draws_2025[-1]['date']} ~ {draws_2025[0]['date']}")

    min_history = 50
    testable_draws = len(draws_2025) - min_history

    if testable_draws <= 0:
        print(f"❌ 數據不足，需要至少{min_history}期歷史數據")
        return

    print(f"\n可測試期數: {testable_draws}期（需保留{min_history}期作為初始歷史）")

    # 1. 單注策略回測
    print("\n" + "=" * 100)
    print("階段1: 單注策略回測")
    print("=" * 100)

    single_strategies = [
        ('frequency', '標準熱號'),
        ('bayesian', '貝葉斯分析'),
        ('ensemble', '集成策略'),
        ('monte_carlo', '蒙地卡羅')
    ]

    single_results = []

    for strategy_code, strategy_name in single_strategies:
        print(f"\n正在測試: {strategy_name}...")
        results = rolling_backtest_single_strategy(draws_2025, rules, strategy_code, min_history)

        if results:
            analysis = analyze_results(results, strategy_name)
            single_results.append(analysis)
            print(f"  ✓ 完成 - 平均命中: {analysis['avg_match']:.2f}個 ({analysis['avg_hit_rate']:.1f}%)")

    # 2. 雙注策略回測
    print("\n" + "=" * 100)
    print("階段2: 雙注策略回測")
    print("=" * 100)

    double_modes = [
        ('optimal', '最優模式'),
        ('dynamic', '動態模式'),
        ('balanced', '平衡模式')
    ]

    double_results = []

    for mode_code, mode_name in double_modes:
        print(f"\n正在測試: {mode_name}...")
        results = rolling_backtest_double_bet(draws_2025, rules, mode_code, min_history)

        if results:
            analysis = analyze_double_bet_results(results, mode_code)
            double_results.append(analysis)
            print(f"  ✓ 完成 - 平均命中: {analysis['combined']['avg_match']:.2f}個 ({analysis['combined']['avg_hit_rate']:.1f}%)")

    # 3. 打印對比表格
    print_comparison_table(single_results, double_results)

    # 4. 詳細分析
    print("\n" + "=" * 100)
    print("詳細分析")
    print("=" * 100)

    # 找出表現最好的單注和雙注策略
    if single_results:
        best_single = max(single_results, key=lambda x: x['avg_hit_rate'])
        print_detailed_analysis(best_single, is_double=False)

    if double_results:
        best_double = max(double_results, key=lambda x: x['combined']['avg_hit_rate'])
        print_detailed_analysis(best_double, is_double=True)

    # 5. 結論
    print("\n" + "=" * 100)
    print("【結論】")
    print("=" * 100)

    if single_results and double_results:
        best_single_rate = max(r['avg_hit_rate'] for r in single_results)
        best_double_rate = max(r['combined']['avg_hit_rate'] for r in double_results)
        best_double_mode = max(double_results, key=lambda x: x['combined']['avg_hit_rate'])

        improvement = ((best_double_rate - best_single_rate) / best_single_rate * 100)

        print(f"\n單注最佳表現: {best_single_rate:.1f}%")
        print(f"雙注最佳表現: {best_double_rate:.1f}% ({best_double_mode['mode']}模式)")
        print(f"\n改進幅度: +{improvement:.1f}%")

        if best_double_rate > best_single_rate:
            print(f"\n✅ 雙注策略顯著優於單注策略")
            print(f"   推薦使用: {best_double_mode['mode']}模式")
        else:
            print(f"\n⚠️  雙注策略未達預期效果，需要進一步優化")

    print("\n測試完成！")
    print("=" * 100 + "\n")

if __name__ == "__main__":
    main()
