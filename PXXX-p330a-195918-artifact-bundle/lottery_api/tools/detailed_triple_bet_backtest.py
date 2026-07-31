#!/usr/bin/env python3
"""
今彩539 3注覆蓋策略 - 2025年詳細滾動回測
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import Counter
from database import db_manager
from common import get_lottery_rules
from models.daily539_predictor import Daily539Predictor
from models.unified_predictor import prediction_engine

# 初始化
predictor = Daily539Predictor()
rules = get_lottery_rules('DAILY_539')

def run_detailed_backtest():
    """執行詳細的3注覆蓋滾動回測"""

    print("=" * 70)
    print("今彩539 3注覆蓋策略 - 2025年滾動回測")
    print("=" * 70)

    # 載入數據
    history = db_manager.get_all_draws('DAILY_539')
    print(f"\n總數據量: {len(history)} 期")

    # 找出2025年數據 (民國114年)
    test_draws = []
    for i, draw in enumerate(history):
        draw_id = str(draw.get('draw', ''))
        if draw_id.startswith('114'):
            test_draws.append((i, draw))

    # 反轉為時間順序
    test_draws = list(reversed(test_draws))

    print(f"2025年測試期數: {len(test_draws)} 期")
    print(f"測試範圍: {test_draws[0][1]['draw']} ~ {test_draws[-1][1]['draw']}")
    print(f"日期範圍: {test_draws[0][1]['date']} ~ {test_draws[-1][1]['date']}")

    print("\n" + "=" * 70)
    print("3注組合: sum_range(300) + bayesian(300) + zone_opt(200)")
    print("成功標準: 任一注中2個號碼以上")
    print("=" * 70)

    # 統計
    wins = 0
    total = 0
    match_distribution = Counter()  # 最佳命中數分布
    monthly_stats = {}  # 月度統計

    # 詳細結果
    print(f"\n{'期號':<12} {'日期':<12} {'實際號碼':<20} {'注1命中':<8} {'注2命中':<8} {'注3命中':<8} {'結果':<6}")
    print("-" * 90)

    for test_idx, (orig_idx, target_draw) in enumerate(test_draws):
        # 訓練數據
        train_data = history[orig_idx + 1:]

        if len(train_data) < 300:
            continue

        target_numbers = set(target_draw['numbers'])
        draw_id = target_draw['draw']
        date_str = target_draw['date']

        # 執行3注預測
        matches = []

        # 第1注: sum_range
        try:
            result1 = prediction_engine.sum_range_predict(train_data[:300], rules)
            m1 = len(set(result1['numbers']) & target_numbers)
            matches.append(m1)
        except:
            matches.append(0)

        # 第2注: bayesian
        try:
            result2 = prediction_engine.bayesian_predict(train_data[:300], rules)
            m2 = len(set(result2['numbers']) & target_numbers)
            matches.append(m2)
        except:
            matches.append(0)

        # 第3注: zone_opt
        try:
            result3 = predictor.zone_optimized_predict(train_data[:200], rules)
            m3 = len(set(result3['numbers']) & target_numbers)
            matches.append(m3)
        except:
            matches.append(0)

        # 判斷是否中獎 (任一注中2個以上)
        best_match = max(matches)
        hit = best_match >= 2

        if hit:
            wins += 1
        total += 1

        match_distribution[best_match] += 1

        # 月度統計
        month = date_str[:7]  # "2025/01"
        if month not in monthly_stats:
            monthly_stats[month] = {'wins': 0, 'total': 0}
        monthly_stats[month]['total'] += 1
        if hit:
            monthly_stats[month]['wins'] += 1

        # 顯示結果 (每10期或中獎時)
        if test_idx < 20 or hit or test_idx % 50 == 0:
            result_str = "✅ 中" if hit else "❌"
            actual_str = str(sorted(target_draw['numbers']))
            print(f"{draw_id:<12} {date_str:<12} {actual_str:<20} {matches[0]:<8} {matches[1]:<8} {matches[2]:<8} {result_str:<6}")

    # 計算統計
    win_rate = wins / total if total > 0 else 0
    periods_per_win = total / wins if wins > 0 else float('inf')

    print("\n" + "=" * 70)
    print("回測結果統計")
    print("=" * 70)

    print(f"\n📊 整體統計:")
    print(f"   測試期數: {total} 期")
    print(f"   中獎次數: {wins} 次")
    print(f"   中獎率: {win_rate*100:.2f}%")
    print(f"   每N期中1次: {periods_per_win:.1f} 期")
    print(f"   對比隨機提升: {win_rate/0.093:.2f}x (隨機基準9.3%)")

    print(f"\n📈 命中數分布:")
    for match_count in sorted(match_distribution.keys(), reverse=True):
        count = match_distribution[match_count]
        pct = count / total * 100
        bar = "█" * int(pct / 2)
        status = "✅ 中獎" if match_count >= 2 else ""
        print(f"   {match_count}個號碼: {count:>4}次 ({pct:>5.1f}%) {bar} {status}")

    print(f"\n📅 月度統計:")
    for month in sorted(monthly_stats.keys()):
        stats = monthly_stats[month]
        m_rate = stats['wins'] / stats['total'] if stats['total'] > 0 else 0
        bar = "█" * int(m_rate * 20)
        print(f"   {month}: {stats['wins']:>3}/{stats['total']:>3} ({m_rate*100:>5.1f}%) {bar}")

    print("\n" + "=" * 70)
    print("結論")
    print("=" * 70)

    if win_rate >= 0.33:
        print(f"\n🎉 成功達成33%目標！")
        print(f"   實際中獎率: {win_rate*100:.2f}%")
        print(f"   超出目標: {(win_rate - 0.33)*100:.2f}%")
    else:
        print(f"\n⚠️ 未達33%目標")
        print(f"   實際中獎率: {win_rate*100:.2f}%")
        print(f"   差距: {(0.33 - win_rate)*100:.2f}%")

    return {
        'total': total,
        'wins': wins,
        'win_rate': win_rate,
        'periods_per_win': periods_per_win,
        'monthly_stats': monthly_stats,
        'match_distribution': dict(match_distribution)
    }


if __name__ == '__main__':
    results = run_detailed_backtest()
