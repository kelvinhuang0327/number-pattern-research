#!/usr/bin/env python3
"""
獨立驗證 Gemini 三注策略宣稱的 7.33% Match-3+ 率
嚴格滾動回測，防止數據洩漏
"""
import sys
import os
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine


def generate_3bet_diversified(engine, history, rules):
    """
    完全按照 Gemini 三注策略生成
    - Deviation 權重 2.0
    - Markov 權重 1.5
    - Statistical 權重 1.0
    - Top 18 候選
    - 注1: 0-5, 注2: 4-9, 注3: 8-13 (低重疊)
    """
    candidates = Counter()

    # Deviation (權重 2.0)
    try:
        result = engine.deviation_predict(history, rules)
        for num in result['numbers']:
            candidates[num] += 2.0
    except:
        pass

    # Markov (權重 1.5)
    try:
        result = engine.markov_predict(history, rules)
        for num in result['numbers']:
            candidates[num] += 1.5
    except:
        pass

    # Statistical (權重 1.0)
    try:
        result = engine.statistical_predict(history, rules)
        for num in result['numbers']:
            candidates[num] += 1.0
    except:
        pass

    # Top 18
    top_18 = [num for num, _ in candidates.most_common(18)]

    if len(top_18) < 14:
        return None

    # 三注低重疊
    bet1 = sorted(top_18[0:6])
    bet2 = sorted(top_18[4:10])
    bet3 = sorted(top_18[8:14])

    return [bet1, bet2, bet3]


def strict_rolling_backtest(test_periods=150):
    """嚴格滾動回測"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))

    # 按期號排序（舊到新）
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    all_draws = sorted(all_draws, key=lambda x: x.get('draw_number', x.get('draw_date', '')))

    print(f"總數據量: {len(all_draws)} 期")
    print(f"最新一期: {all_draws[-1].get('numbers', [])}")

    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()

    results = {
        '3bet': {'match3_plus': 0, 'match4_plus': 0, 'total': 0, 'details': []},
        '2bet': {'match3_plus': 0, 'total': 0},
        'deviation': {'match3_plus': 0, 'total': 0},
    }

    start_idx = len(all_draws) - test_periods

    print(f"\n回測 {test_periods} 期...")
    print("-" * 60)

    for target_idx in range(start_idx, len(all_draws)):
        history = all_draws[:target_idx]
        target = all_draws[target_idx]

        if len(history) < 50:
            continue

        actual = set(target['numbers'])
        draw_num = target.get('draw_number', f'idx_{target_idx}')

        # 測試三注
        bets = generate_3bet_diversified(engine, history, rules)
        if bets:
            max_match = 0
            for bet in bets:
                match_count = len(set(bet) & actual)
                max_match = max(max_match, match_count)

            results['3bet']['total'] += 1
            if max_match >= 4:
                results['3bet']['match4_plus'] += 1
            if max_match >= 3:
                results['3bet']['match3_plus'] += 1
                results['3bet']['details'].append({
                    'draw': draw_num,
                    'actual': sorted(list(actual)),
                    'bets': bets,
                    'match': max_match
                })

        # 測試雙注 (作為對照)
        if bets:
            max_match_2bet = 0
            for bet in bets[:2]:  # 只取前兩注
                match_count = len(set(bet) & actual)
                max_match_2bet = max(max_match_2bet, match_count)

            results['2bet']['total'] += 1
            if max_match_2bet >= 3:
                results['2bet']['match3_plus'] += 1

        # 測試單注偏差分析
        try:
            dev = engine.deviation_predict(history, rules)
            match_dev = len(set(dev['numbers']) & actual)
            results['deviation']['total'] += 1
            if match_dev >= 3:
                results['deviation']['match3_plus'] += 1
        except:
            pass

    return results


def main():
    print("=" * 70)
    print("🔬 獨立驗證 Gemini 三注策略 (嚴格滾動回測)")
    print("=" * 70)

    results = strict_rolling_backtest(test_periods=150)

    print("\n" + "=" * 70)
    print("📊 驗證結果")
    print("=" * 70)

    # 計算百分比
    rate_3bet = results['3bet']['match3_plus'] / results['3bet']['total'] * 100 if results['3bet']['total'] > 0 else 0
    rate_4plus = results['3bet']['match4_plus'] / results['3bet']['total'] * 100 if results['3bet']['total'] > 0 else 0
    rate_2bet = results['2bet']['match3_plus'] / results['2bet']['total'] * 100 if results['2bet']['total'] > 0 else 0
    rate_dev = results['deviation']['match3_plus'] / results['deviation']['total'] * 100 if results['deviation']['total'] > 0 else 0

    print(f"\n{'方案':<25} {'Match-3+ 次數':<15} {'總期數':<10} {'Match-3+ 率':<12} {'效益/注':<10}")
    print("-" * 75)
    print(f"{'單注偏差分析 (基準)':<25} {results['deviation']['match3_plus']:<15} {results['deviation']['total']:<10} {rate_dev:.2f}%{'':<7} {rate_dev:.2f}%")
    print(f"{'雙注 (前2注)':<25} {results['2bet']['match3_plus']:<15} {results['2bet']['total']:<10} {rate_2bet:.2f}%{'':<7} {rate_2bet/2:.2f}%")
    print(f"{'🎯 三注智能組合':<25} {results['3bet']['match3_plus']:<15} {results['3bet']['total']:<10} {rate_3bet:.2f}%{'':<7} {rate_3bet/3:.2f}%")

    print(f"\nMatch-4+ 率: {rate_4plus:.2f}% ({results['3bet']['match4_plus']} 次)")

    print("\n" + "=" * 70)
    print("📋 與 Gemini 報告對比")
    print("=" * 70)
    print(f"Gemini 宣稱三注: 7.33%")
    print(f"我們獨立驗證:    {rate_3bet:.2f}%")

    diff = rate_3bet - 7.33
    if abs(diff) < 0.5:
        print(f"✅ 結果相符（差異 {diff:+.2f}%）")
    elif diff > 0.5:
        print(f"⚠️ 我們的結果更高（差異 {diff:+.2f}%）")
    else:
        print(f"❌ 我們的結果更低（差異 {diff:+.2f}%）")

    # 目標達成評估
    print("\n" + "=" * 70)
    print("🎯 目標達成評估")
    print("=" * 70)
    target = 7.67  # 基準 2.67% + 5%
    actual_improvement = rate_3bet - rate_dev
    target_improvement = 5.0

    print(f"目標: Match-3+ 提升 +5%（從 {rate_dev:.2f}% 到 {rate_dev + 5:.2f}%）")
    print(f"實際: 提升 +{actual_improvement:.2f}%（從 {rate_dev:.2f}% 到 {rate_3bet:.2f}%）")
    print(f"達成率: {actual_improvement / target_improvement * 100:.1f}%")

    # 命中詳情
    if results['3bet']['details']:
        print("\n" + "=" * 70)
        print(f"🎉 Match-3+ 命中詳情 ({len(results['3bet']['details'])} 次)")
        print("=" * 70)
        for d in results['3bet']['details']:
            print(f"期號: {d['draw']}, 實際: {d['actual']}, 最高匹配: {d['match']}")


if __name__ == '__main__':
    main()
