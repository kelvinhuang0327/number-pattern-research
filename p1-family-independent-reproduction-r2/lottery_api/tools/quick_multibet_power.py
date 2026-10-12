#!/usr/bin/env python3
"""
POWER_LOTTO 多注策略快速回測
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DatabaseManager
from common import get_lottery_rules
from models.multi_bet_optimizer import MultiBetOptimizer
from collections import Counter
import json
from datetime import datetime

def run_multi_bet_backtest():
    db = DatabaseManager()
    lottery_type = 'POWER_LOTTO'

    draws = db.get_all_draws(lottery_type)
    rules = get_lottery_rules(lottery_type)

    print("=" * 60)
    print("POWER_LOTTO 多注策略回測")
    print("=" * 60)
    print(f"總數據: {len(draws)} 期")

    # 2025年測試數據
    test_draws = [d for d in draws if d['date'].startswith('2025') or d['date'].startswith('114')]
    print(f"2025年測試數據: {len(test_draws)} 期")

    optimizer = MultiBetOptimizer()
    bet_price = 100  # 威力彩每注100元

    results = []

    for num_bets in [1, 2, 3, 4, 6, 8]:
        print(f"\n測試 {num_bets} 注策略...", end=" ", flush=True)

        win_count = 0
        best_matches_list = []
        test_count = 0

        for target in test_draws:
            # 找到目標期位置
            target_idx = None
            for i, d in enumerate(draws):
                if d['draw'] == target['draw']:
                    target_idx = i
                    break

            if target_idx is None:
                continue

            # 使用目標期之前的數據
            available = draws[target_idx + 1:]
            if len(available) < 100:
                continue

            try:
                # 生成多注預測
                result = optimizer.generate_diversified_bets(available[:300], rules, num_bets)
                bets = result['bets']

                # 計算最佳匹配
                actual = set(target['numbers'])
                best_match = 0
                for bet in bets:
                    predicted = set(bet['numbers'])
                    matches = len(predicted & actual)
                    best_match = max(best_match, matches)

                best_matches_list.append(best_match)
                if best_match >= 3:
                    win_count += 1
                test_count += 1

            except Exception as e:
                continue

        if test_count > 0:
            win_rate = win_count / test_count
            avg_best = sum(best_matches_list) / len(best_matches_list)
            periods_per_win = test_count / win_count if win_count > 0 else float('inf')
            cost_per_win = periods_per_win * num_bets * bet_price

            results.append({
                'num_bets': num_bets,
                'win_rate': win_rate,
                'win_count': win_count,
                'test_count': test_count,
                'avg_best_match': avg_best,
                'periods_per_win': periods_per_win,
                'cost_per_win': cost_per_win
            })

            print(f"{win_rate*100:.2f}% ({win_count}/{test_count})")
        else:
            print("無有效測試")

    print("\n" + "=" * 60)
    print("多注策略結果摘要")
    print("=" * 60)
    print(f"{'注數':<6} {'中獎率':<10} {'每N期中1次':<12} {'預期成本':<12}")
    print("-" * 50)
    for r in results:
        print(f"{r['num_bets']:<6} {r['win_rate']*100:.2f}%{'':<5} "
              f"{r['periods_per_win']:.1f}{'':<7} ${r['cost_per_win']:.0f}")

    # 保存結果
    output = {
        'lottery_type': lottery_type,
        'test_year': 2025,
        'test_periods': test_draws[0]['draw'] if test_draws else None,
        'results': results,
        'generated_at': datetime.now().isoformat()
    }

    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                               'data', 'power_lotto_multibet_results.json')
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n結果已保存到: {output_path}")
    return results


if __name__ == '__main__':
    run_multi_bet_backtest()
