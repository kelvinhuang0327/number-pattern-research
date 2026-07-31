#!/usr/bin/env python3
"""
獨立驗證 Gemini 雙注 V1 方案宣稱的 4.00% Match-3+ 率
嚴格滾動回測，防止任何數據洩漏
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


def generate_2bet_v1(engine, history, rules):
    """
    完全按照 Gemini V1 方案生成雙注
    - 收集 Top 3 方法的候選號碼
    - 偏差分析權重 2.0
    - 馬可夫鏈權重 1.5
    - 統計綜合權重 1.0
    - 取 Top 12 候選
    - 注1: 候選 0-5
    - 注2: 候選 3-8（重疊 3 個）
    """
    candidates = Counter()

    # 偏差分析 (權重 2.0)
    try:
        dev_result = engine.deviation_predict(history, rules)
        for num in dev_result['numbers']:
            candidates[num] += 2.0
    except:
        pass

    # 馬可夫鏈 (權重 1.5)
    try:
        markov_result = engine.markov_predict(history, rules)
        for num in markov_result['numbers']:
            candidates[num] += 1.5
    except:
        pass

    # 統計綜合 (權重 1.0)
    try:
        stat_result = engine.statistical_predict(history, rules)
        for num in stat_result['numbers']:
            candidates[num] += 1.0
    except:
        pass

    # 取 Top 12
    top_candidates = [n for n, _ in candidates.most_common(12)]

    if len(top_candidates) < 9:
        return None

    # 生成雙注
    bet1 = sorted(top_candidates[:6])
    bet2 = sorted(top_candidates[3:9])

    return [bet1, bet2]


def strict_rolling_backtest(test_periods=150):
    """嚴格滾動回測"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))

    # 取得所有數據，按期號排序（舊到新）
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')

    # 確認排序：按 draw_number 排序
    all_draws = sorted(all_draws, key=lambda x: x.get('draw_number', x.get('draw_date', '')))

    print(f"總數據量: {len(all_draws)} 期")
    print(f"最舊一期: {all_draws[0].get('draw_number', 'N/A')} - {all_draws[0].get('numbers', [])}")
    print(f"最新一期: {all_draws[-1].get('draw_number', 'N/A')} - {all_draws[-1].get('numbers', [])}")

    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()

    # 統計
    results = {
        '2bet_v1': {'match3_plus': 0, 'total': 0, 'details': []},
        'deviation': {'match3_plus': 0, 'total': 0},
        'markov': {'match3_plus': 0, 'total': 0},
    }

    # 從後往前測試最近 test_periods 期
    start_idx = len(all_draws) - test_periods

    print(f"\n回測範圍: 第 {start_idx} 到 {len(all_draws)-1} 期 (共 {test_periods} 期)")
    print(f"第一個測試目標: {all_draws[start_idx].get('draw_number', 'N/A')}")
    print(f"最後一個測試目標: {all_draws[-1].get('draw_number', 'N/A')}")
    print("-" * 60)

    for target_idx in range(start_idx, len(all_draws)):
        # 嚴格切片：只用 target_idx 之前的數據
        history = all_draws[:target_idx]
        target = all_draws[target_idx]

        if len(history) < 50:  # 至少需要 50 期訓練數據
            continue

        actual = set(target['numbers'])
        draw_num = target.get('draw_number', f'idx_{target_idx}')

        # 測試雙注 V1
        bets = generate_2bet_v1(engine, history, rules)
        if bets:
            max_match = 0
            for bet in bets:
                match_count = len(set(bet) & actual)
                max_match = max(max_match, match_count)

            results['2bet_v1']['total'] += 1
            if max_match >= 3:
                results['2bet_v1']['match3_plus'] += 1
                results['2bet_v1']['details'].append({
                    'draw': draw_num,
                    'actual': sorted(list(actual)),
                    'bets': bets,
                    'match': max_match
                })

        # 測試單注偏差分析
        try:
            dev = engine.deviation_predict(history, rules)
            match_dev = len(set(dev['numbers']) & actual)
            results['deviation']['total'] += 1
            if match_dev >= 3:
                results['deviation']['match3_plus'] += 1
        except:
            pass

        # 測試單注馬可夫
        try:
            mar = engine.markov_predict(history, rules)
            match_mar = len(set(mar['numbers']) & actual)
            results['markov']['total'] += 1
            if match_mar >= 3:
                results['markov']['match3_plus'] += 1
        except:
            pass

    return results


def main():
    print("=" * 70)
    print("🔬 獨立驗證 Gemini 雙注 V1 方案 (嚴格滾動回測)")
    print("=" * 70)

    results = strict_rolling_backtest(test_periods=150)

    print("\n" + "=" * 70)
    print("📊 驗證結果")
    print("=" * 70)

    # 計算百分比
    if results['2bet_v1']['total'] > 0:
        rate_2bet = results['2bet_v1']['match3_plus'] / results['2bet_v1']['total'] * 100
    else:
        rate_2bet = 0

    if results['deviation']['total'] > 0:
        rate_dev = results['deviation']['match3_plus'] / results['deviation']['total'] * 100
    else:
        rate_dev = 0

    if results['markov']['total'] > 0:
        rate_mar = results['markov']['match3_plus'] / results['markov']['total'] * 100
    else:
        rate_mar = 0

    print(f"\n{'方案':<25} {'Match-3+ 次數':<15} {'總期數':<10} {'Match-3+ 率':<15}")
    print("-" * 70)
    print(f"{'單注偏差分析 (基準)':<25} {results['deviation']['match3_plus']:<15} {results['deviation']['total']:<10} {rate_dev:.2f}%")
    print(f"{'單注馬可夫鏈':<25} {results['markov']['match3_plus']:<15} {results['markov']['total']:<10} {rate_mar:.2f}%")
    print(f"{'🎯 雙注 V1 (Gemini)':<25} {results['2bet_v1']['match3_plus']:<15} {results['2bet_v1']['total']:<10} {rate_2bet:.2f}%")

    print("\n" + "=" * 70)
    print("📋 與 Gemini 報告對比")
    print("=" * 70)
    print(f"Gemini 宣稱雙注 V1: 4.00%")
    print(f"我們獨立驗證:       {rate_2bet:.2f}%")

    diff = rate_2bet - 4.00
    if abs(diff) < 0.5:
        print(f"✅ 結果相符（差異 {diff:+.2f}%）")
    elif diff > 0.5:
        print(f"⚠️ 我們的結果更高（差異 {diff:+.2f}%）")
    else:
        print(f"❌ 我們的結果更低（差異 {diff:+.2f}%）")

    # 顯示 Match-3+ 詳情
    if results['2bet_v1']['details']:
        print("\n" + "=" * 70)
        print(f"🎉 Match-3+ 命中詳情 ({len(results['2bet_v1']['details'])} 次)")
        print("=" * 70)
        for d in results['2bet_v1']['details'][:10]:  # 只顯示前 10 個
            print(f"期號: {d['draw']}")
            print(f"  實際: {d['actual']}")
            print(f"  注1:  {d['bets'][0]}")
            print(f"  注2:  {d['bets'][1]}")
            print(f"  最高匹配: {d['match']}")
            print()


if __name__ == '__main__':
    main()
