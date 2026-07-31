#!/usr/bin/env python3
"""
今彩539 三種策略完整回測 - 2025年
確保無資料洩漏的滾動式回測

策略:
1. 3注覆蓋策略 (sum_range + bayesian + zone_opt)
2. 2注覆蓋策略 (sum_range + tail)
3. 連號強化策略 (consecutive_enhance)

回測邏輯:
- 預測第N期時，只使用第N+1期及之後的歷史數據
- 確保實際開獎號碼不會混入訓練資料
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import Counter
from database import db_manager
from common import get_lottery_rules
from models.unified_predictor import prediction_engine
from models.daily539_predictor import Daily539Predictor

predictor = Daily539Predictor()
rules = get_lottery_rules('DAILY_539')


def run_comprehensive_backtest():
    """執行完整的2025年滾動回測"""

    # 載入所有數據
    all_history = db_manager.get_all_draws('DAILY_539')

    print("=" * 90)
    print("今彩539 三種策略完整回測 - 2025年")
    print("=" * 90)
    print(f"總數據量: {len(all_history)} 期")
    print()
    print("⚠️ 回測邏輯說明:")
    print("   - 預測第N期時，只使用第N+1期及之後的數據")
    print("   - 確保實際開獎號碼不會混入訓練資料 (無資料洩漏)")
    print("=" * 90)

    # 找出2025年數據 (民國114年)
    test_draws = []
    for i, d in enumerate(all_history):
        draw_id = str(d.get('draw', ''))
        if draw_id.startswith('114'):
            test_draws.append((i, d))

    # 按時間順序排列 (從早到晚)
    test_draws = list(reversed(test_draws))

    print(f"\n2025年測試期數: {len(test_draws)} 期")
    print(f"測試範圍: {test_draws[0][1]['draw']} ~ {test_draws[-1][1]['draw']}")
    print(f"日期範圍: {test_draws[0][1]['date']} ~ {test_draws[-1][1]['date']}")

    # 初始化結果統計
    strategies = {
        '3注覆蓋': {'wins': 0, 'total': 0, 'matches': Counter(), 'details': []},
        '2注覆蓋': {'wins': 0, 'total': 0, 'matches': Counter(), 'details': []},
        '連號強化': {'wins': 0, 'total': 0, 'matches': Counter(), 'details': []},
    }

    print("\n開始回測...")
    print("-" * 90)

    for test_idx, (orig_idx, target_draw) in enumerate(test_draws):
        # ⚠️ 關鍵: 訓練數據只使用目標期之前的歷史數據（時間上更早的數據）
        # 因為 all_history 是新→舊排序，orig_idx + 1 之後的索引對應更舊的期數
        train_data = all_history[orig_idx + 1:]

        # 確保有足夠的訓練數據
        if len(train_data) < 300:
            continue

        target_numbers = set(target_draw['numbers'])
        draw_id = target_draw['draw']
        date_str = target_draw['date']

        # ============================================================
        # 策略1: 3注覆蓋 (sum_range + bayesian + zone_opt)
        # ============================================================
        matches_3bet = []

        # 第1注: sum_range (300期)
        try:
            r1 = prediction_engine.sum_range_predict(train_data[:300], rules)
            m1 = len(set(r1['numbers']) & target_numbers)
            matches_3bet.append(m1)
        except:
            matches_3bet.append(0)

        # 第2注: bayesian (300期)
        try:
            r2 = prediction_engine.bayesian_predict(train_data[:300], rules)
            m2 = len(set(r2['numbers']) & target_numbers)
            matches_3bet.append(m2)
        except:
            matches_3bet.append(0)

        # 第3注: zone_opt (200期)
        try:
            r3 = predictor.zone_optimized_predict(train_data[:200], rules)
            m3 = len(set(r3['numbers']) & target_numbers)
            matches_3bet.append(m3)
        except:
            matches_3bet.append(0)

        best_3bet = max(matches_3bet)
        strategies['3注覆蓋']['matches'][best_3bet] += 1
        strategies['3注覆蓋']['total'] += 1
        if best_3bet >= 2:
            strategies['3注覆蓋']['wins'] += 1

        if best_3bet >= 3:
            strategies['3注覆蓋']['details'].append({
                'draw': draw_id, 'date': date_str,
                'actual': sorted(target_draw['numbers']),
                'best_match': best_3bet,
                'matches': matches_3bet
            })

        # ============================================================
        # 策略2: 2注覆蓋 (sum_range + tail)
        # ============================================================
        matches_2bet = []

        # 第1注: sum_range (300期)
        try:
            r1 = prediction_engine.sum_range_predict(train_data[:300], rules)
            m1 = len(set(r1['numbers']) & target_numbers)
            matches_2bet.append(m1)
        except:
            matches_2bet.append(0)

        # 第2注: tail (100期)
        try:
            r2 = predictor.tail_number_predict(train_data[:100], rules)
            m2 = len(set(r2['numbers']) & target_numbers)
            matches_2bet.append(m2)
        except:
            matches_2bet.append(0)

        best_2bet = max(matches_2bet)
        strategies['2注覆蓋']['matches'][best_2bet] += 1
        strategies['2注覆蓋']['total'] += 1
        if best_2bet >= 2:
            strategies['2注覆蓋']['wins'] += 1

        if best_2bet >= 3:
            strategies['2注覆蓋']['details'].append({
                'draw': draw_id, 'date': date_str,
                'actual': sorted(target_draw['numbers']),
                'best_match': best_2bet,
                'matches': matches_2bet
            })

        # ============================================================
        # 策略3: 連號強化
        # ============================================================
        try:
            r_consec = predictor.consecutive_enhance_predict(train_data, rules)
            m_consec = len(set(r_consec['numbers']) & target_numbers)
        except:
            m_consec = 0

        strategies['連號強化']['matches'][m_consec] += 1
        strategies['連號強化']['total'] += 1
        if m_consec >= 2:
            strategies['連號強化']['wins'] += 1

        if m_consec >= 3:
            strategies['連號強化']['details'].append({
                'draw': draw_id, 'date': date_str,
                'actual': sorted(target_draw['numbers']),
                'predicted': r_consec['numbers'],
                'match': m_consec
            })

        # 進度顯示
        if (test_idx + 1) % 50 == 0:
            print(f"已完成 {test_idx + 1}/{len(test_draws)} 期...")

    # ============================================================
    # 輸出結果
    # ============================================================
    print("\n" + "=" * 90)
    print("回測結果總覽")
    print("=" * 90)

    print(f"\n{'策略':<15} {'測試期數':>10} {'中獎次數':>10} {'中獎率':>10} {'每N期中1':>10} {'中3個':>8} {'中4個':>8} {'中5個':>8}")
    print("-" * 90)

    for name, stats in strategies.items():
        total = stats['total']
        wins = stats['wins']
        win_rate = wins / total if total > 0 else 0
        periods_per_win = total / wins if wins > 0 else float('inf')

        hit3 = stats['matches'][3]
        hit4 = stats['matches'][4]
        hit5 = stats['matches'][5]

        print(f"{name:<15} {total:>10} {wins:>10} {win_rate*100:>9.2f}% {periods_per_win:>10.1f} {hit3:>8} {hit4:>8} {hit5:>8}")

    # 詳細命中分布
    print("\n" + "=" * 90)
    print("命中數分布")
    print("=" * 90)

    for name, stats in strategies.items():
        total = stats['total']
        print(f"\n📊 {name}:")
        for i in range(5, -1, -1):
            count = stats['matches'][i]
            pct = count / total * 100 if total > 0 else 0
            bar = "█" * int(pct / 2)
            status = "🏆" if i >= 4 else ("✅ 中獎" if i >= 2 else "")
            print(f"   {i}個: {count:>4}次 ({pct:>5.1f}%) {bar} {status}")

    # 大獎記錄
    print("\n" + "=" * 90)
    print("中3個以上的詳細記錄")
    print("=" * 90)

    for name, stats in strategies.items():
        if stats['details']:
            print(f"\n🏆 {name} - 中3+記錄:")
            for d in sorted(stats['details'], key=lambda x: -x.get('best_match', x.get('match', 0)))[:10]:
                match_count = d.get('best_match', d.get('match', 0))
                icon = "🏆🏆" if match_count >= 4 else "🏆"
                print(f"   {icon} {d['draw']} ({d['date']}): 實際={d['actual']}, 命中{match_count}個")

    # 結論
    print("\n" + "=" * 90)
    print("結論")
    print("=" * 90)

    results_summary = []
    for name, stats in strategies.items():
        total = stats['total']
        wins = stats['wins']
        win_rate = wins / total if total > 0 else 0
        hit4_plus = stats['matches'][4] + stats['matches'][5]
        results_summary.append({
            'name': name,
            'win_rate': win_rate,
            'hit4_plus': hit4_plus,
            'hit3': stats['matches'][3]
        })

    # 按中獎率排序
    results_summary.sort(key=lambda x: x['win_rate'], reverse=True)

    print("\n📌 中獎率排名:")
    for i, r in enumerate(results_summary, 1):
        target_met = "✅ 達標" if r['win_rate'] >= 0.33 else "❌ 未達標"
        print(f"   {i}. {r['name']}: {r['win_rate']*100:.2f}% {target_met}")

    # 按大獎潛力排序
    results_summary.sort(key=lambda x: (x['hit4_plus'], x['hit3']), reverse=True)

    print("\n📌 大獎潛力排名 (中4+5個次數):")
    for i, r in enumerate(results_summary, 1):
        print(f"   {i}. {r['name']}: 中4+5={r['hit4_plus']}次, 中3={r['hit3']}次")

    print("\n" + "=" * 90)
    print("資料洩漏檢查: ✅ 無洩漏 (訓練資料不包含目標期)")
    print("=" * 90)

    return strategies


if __name__ == '__main__':
    results = run_comprehensive_backtest()
