#!/usr/bin/env python3
"""
號碼集中度優化器回測腳本

執行 2025 年大樂透滾動式回測，驗證 P0 策略效果
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import DatabaseManager
from common import get_lottery_rules
from models.concentrated_pool_predictor import ConcentratedPoolPredictor
from collections import defaultdict
import json
from datetime import datetime


def run_rolling_backtest(lottery_type: str = 'BIG_LOTTO',
                          test_year: str = '2025',
                          pool_sizes: list = None,
                          strategies: list = None):
    """
    執行滾動式回測

    嚴格遵守數據切片規範：預測第N期時只用第N-1期及之前的數據
    """
    print("=" * 80)
    print(f"號碼集中度優化器回測 - {lottery_type} ({test_year}年)")
    print("=" * 80)

    # 載入數據
    db = DatabaseManager(db_path=os.path.join(os.path.dirname(__file__), '..', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type)
    rules = get_lottery_rules(lottery_type)

    print(f"\n數據總量: {len(all_draws)} 期")

    # 數據是 新→舊 排序，找出2025年的測試數據
    test_draws = []
    for i, draw in enumerate(all_draws):
        date = draw.get('date', '')
        draw_id = draw.get('draw', '')

        # 2025年數據判斷
        if date.startswith(test_year) or draw_id.startswith('114'):
            test_draws.append((i, draw))

    # 反轉為時間順序（從早到晚）
    test_draws = list(reversed(test_draws))
    print(f"{test_year}年測試數據: {len(test_draws)} 期")

    if not test_draws:
        print("無測試數據！")
        return None

    # 預設參數
    if pool_sizes is None:
        pool_sizes = [24, 26, 28, 30, 32]
    if strategies is None:
        strategies = ['balanced', 'top', 'weighted_random']

    # 回測結果
    all_results = {}

    for pool_size in pool_sizes:
        for strategy in strategies:
            config_name = f"pool{pool_size}_{strategy}"
            print(f"\n{'='*60}")
            print(f"測試配置: {config_name}")
            print(f"{'='*60}")

            predictor = ConcentratedPoolPredictor(pool_size=pool_size)

            results = []
            win_count = 0
            total_matches = 0
            match_distribution = defaultdict(int)

            for test_idx, (orig_idx, target_draw) in enumerate(test_draws):
                # 關鍵：只使用比目標更舊的數據
                # 在新→舊排序中，orig_idx + 1 指向更舊的數據
                train_data = all_draws[orig_idx + 1:]

                if len(train_data) < 100:
                    continue

                target_numbers = set(target_draw['numbers'])

                try:
                    # 執行預測
                    prediction = predictor.predict(train_data, rules, strategy=strategy)
                    predicted = set(prediction['numbers'])

                    # 計算匹配
                    matches = len(predicted & target_numbers)
                    total_matches += matches
                    match_distribution[matches] += 1

                    # 中3個以上算中獎
                    won = matches >= 3
                    if won:
                        win_count += 1

                    results.append({
                        'draw': target_draw['draw'],
                        'date': target_draw['date'],
                        'target': sorted(target_numbers),
                        'predicted': sorted(predicted),
                        'matches': matches,
                        'won': won,
                        'pool_coverage': prediction.get('pool_coverage', 0)
                    })

                    # 進度報告
                    if (test_idx + 1) % 20 == 0:
                        current_rate = win_count / len(results) * 100
                        avg_match = total_matches / len(results)
                        print(f"  進度 {test_idx+1}/{len(test_draws)}: "
                              f"中獎率 {current_rate:.2f}%, 平均匹配 {avg_match:.2f}")

                except Exception as e:
                    print(f"  錯誤 ({target_draw['draw']}): {e}")

            # 統計結果
            test_count = len(results)
            if test_count > 0:
                win_rate = win_count / test_count
                avg_matches = total_matches / test_count

                summary = {
                    'config': config_name,
                    'pool_size': pool_size,
                    'strategy': strategy,
                    'test_count': test_count,
                    'win_count': win_count,
                    'win_rate': win_rate,
                    'win_rate_pct': f"{win_rate*100:.2f}%",
                    'avg_matches': avg_matches,
                    'match_distribution': dict(match_distribution),
                    'periods_per_win': 1/win_rate if win_rate > 0 else float('inf')
                }

                all_results[config_name] = summary

                print(f"\n結果摘要:")
                print(f"  測試期數: {test_count}")
                print(f"  中獎次數: {win_count}")
                print(f"  中獎率: {win_rate*100:.2f}%")
                print(f"  平均匹配: {avg_matches:.2f}")
                print(f"  每N期中1次: {summary['periods_per_win']:.1f}")
                print(f"  匹配分佈: {dict(match_distribution)}")

    # 排序並輸出最佳結果
    print("\n" + "=" * 80)
    print("所有配置結果排名")
    print("=" * 80)

    sorted_results = sorted(all_results.values(), key=lambda x: -x['win_rate'])

    print(f"\n{'排名':<4} {'配置':<25} {'中獎率':<10} {'平均匹配':<10} {'每N期中1次':<12}")
    print("-" * 70)

    for rank, result in enumerate(sorted_results, 1):
        print(f"{rank:<4} {result['config']:<25} {result['win_rate_pct']:<10} "
              f"{result['avg_matches']:<10.2f} {result['periods_per_win']:<12.1f}")

    # 與基準比較
    print("\n" + "=" * 80)
    print("與現有最佳方法比較")
    print("=" * 80)
    print(f"現有最佳 (zone_balance): 4.31%")

    if sorted_results:
        best = sorted_results[0]
        improvement = (best['win_rate'] / 0.0431 - 1) * 100
        print(f"本次最佳 ({best['config']}): {best['win_rate_pct']}")
        print(f"提升幅度: {improvement:+.1f}%")

    # 保存結果
    output_file = os.path.join(os.path.dirname(__file__), '..', 'data',
                               f'concentrated_pool_backtest_{test_year}.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'test_year': test_year,
            'lottery_type': lottery_type,
            'timestamp': datetime.now().isoformat(),
            'results': sorted_results,
            'baseline': {'method': 'zone_balance', 'win_rate': 0.0431}
        }, f, ensure_ascii=False, indent=2)

    print(f"\n結果已保存: {output_file}")

    return sorted_results


def run_multi_bet_backtest(lottery_type: str = 'BIG_LOTTO',
                            test_year: str = '2025',
                            num_bets: int = 2):
    """
    多注策略回測
    """
    print("\n" + "=" * 80)
    print(f"號碼集中度 - 多注策略回測 ({num_bets}注)")
    print("=" * 80)

    db = DatabaseManager(db_path=os.path.join(os.path.dirname(__file__), '..', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type)
    rules = get_lottery_rules(lottery_type)

    # 找出測試數據
    test_draws = []
    for i, draw in enumerate(all_draws):
        date = draw.get('date', '')
        draw_id = draw.get('draw', '')
        if date.startswith(test_year) or draw_id.startswith('114'):
            test_draws.append((i, draw))

    test_draws = list(reversed(test_draws))
    print(f"測試數據: {len(test_draws)} 期")

    # 測試不同 pool_size
    for pool_size in [26, 28, 30]:
        print(f"\n候選池大小: {pool_size}")
        print("-" * 50)

        predictor = ConcentratedPoolPredictor(pool_size=pool_size)

        results = []
        win_count = 0
        total_best_matches = 0
        match_distribution = defaultdict(int)

        for test_idx, (orig_idx, target_draw) in enumerate(test_draws):
            train_data = all_draws[orig_idx + 1:]

            if len(train_data) < 100:
                continue

            target_numbers = set(target_draw['numbers'])

            try:
                prediction = predictor.predict_multi_bet(train_data, rules, num_bets=num_bets)

                # 檢查每一注
                best_match = 0
                for bet in prediction['bets']:
                    matches = len(set(bet['numbers']) & target_numbers)
                    if matches > best_match:
                        best_match = matches

                total_best_matches += best_match
                match_distribution[best_match] += 1

                won = best_match >= 3
                if won:
                    win_count += 1

                results.append({
                    'draw': target_draw['draw'],
                    'best_match': best_match,
                    'won': won,
                    'coverage': prediction.get('coverage', 0)
                })

                if (test_idx + 1) % 30 == 0:
                    current_rate = win_count / len(results) * 100
                    print(f"  進度 {test_idx+1}/{len(test_draws)}: 中獎率 {current_rate:.2f}%")

            except Exception as e:
                print(f"  錯誤: {e}")

        test_count = len(results)
        if test_count > 0:
            win_rate = win_count / test_count
            avg_best = total_best_matches / test_count

            print(f"\n  結果:")
            print(f"    中獎率: {win_rate*100:.2f}%")
            print(f"    最佳匹配平均: {avg_best:.2f}")
            print(f"    每N期中1次: {1/win_rate if win_rate > 0 else 999:.1f}")
            print(f"    匹配分佈: {dict(match_distribution)}")

    return results


if __name__ == '__main__':
    # 單注策略回測
    single_results = run_rolling_backtest(
        lottery_type='BIG_LOTTO',
        test_year='2025',
        pool_sizes=[24, 26, 28, 30, 32],
        strategies=['balanced', 'top', 'weighted_random']
    )

    # 2注策略回測
    multi_results = run_multi_bet_backtest(
        lottery_type='BIG_LOTTO',
        test_year='2025',
        num_bets=2
    )
