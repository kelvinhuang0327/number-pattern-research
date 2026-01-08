#!/usr/bin/env python3
"""
今彩539 新預測方法驗證 - Phase 1
1. 共識投票法 (Consensus Voting)
2. 連號強化法 (Consecutive Enhancement)
3. 冷號回歸法 (Cold Number Regression)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import Counter, defaultdict
from database import db_manager
from common import get_lottery_rules
from models.unified_predictor import prediction_engine
from models.daily539_predictor import Daily539Predictor

predictor = Daily539Predictor()
rules = get_lottery_rules('DAILY_539')

# ============================================================
# 新方法定義
# ============================================================

def consensus_voting_predict(history, rules, min_votes=3):
    """
    共識投票法: 統計多個方法的預測，選擇獲得≥min_votes票的號碼
    理論: 多方法共識的號碼更可能出現
    """
    methods = [
        ('sum_range', lambda h: prediction_engine.sum_range_predict(h[:300], rules)),
        ('bayesian', lambda h: prediction_engine.bayesian_predict(h[:300], rules)),
        ('zone_balance', lambda h: prediction_engine.zone_balance_predict(h[:200], rules)),
        ('hot_cold_mix', lambda h: prediction_engine.hot_cold_mix_predict(h[:100], rules)),
        ('trend', lambda h: prediction_engine.trend_predict(h[:100], rules)),
        ('monte_carlo', lambda h: prediction_engine.monte_carlo_predict(h[:200], rules)),
        ('tail', lambda h: predictor.tail_number_predict(h[:100], rules)),
    ]

    votes = Counter()

    for name, method in methods:
        try:
            result = method(history)
            for num in result['numbers']:
                votes[num] += 1
        except:
            pass

    # 選擇高票號碼
    high_vote_nums = [n for n, v in votes.most_common() if v >= min_votes]

    pick_count = rules['pickCount']

    if len(high_vote_nums) >= pick_count:
        # 有足夠的高票號碼
        selected = high_vote_nums[:pick_count]
    else:
        # 補充次高票號碼
        selected = high_vote_nums.copy()
        for n, v in votes.most_common():
            if n not in selected:
                selected.append(n)
            if len(selected) >= pick_count:
                break

    return {
        'numbers': sorted(selected[:pick_count]),
        'confidence': 0.7,
        'method': 'consensus_voting',
        'high_vote_count': len(high_vote_nums),
        'votes': dict(votes.most_common(10))
    }


def consecutive_enhance_predict(history, rules):
    """
    連號強化法: 基於base方法，強制包含1組連續號碼
    理論: 539經常出現連續號碼 (如 11,12 或 27,28)
    """
    # 分析歷史連號頻率
    consecutive_freq = Counter()
    for draw in history[:100]:
        nums = sorted(draw['numbers'])
        for i in range(len(nums) - 1):
            if nums[i+1] - nums[i] == 1:
                consecutive_freq[(nums[i], nums[i+1])] += 1

    # 使用base方法預測
    try:
        base_result = prediction_engine.sum_range_predict(history[:300], rules)
        base_nums = set(base_result['numbers'])
    except:
        base_nums = set()

    # 檢查base是否已有連號
    base_sorted = sorted(base_nums)
    has_consecutive = any(base_sorted[i+1] - base_sorted[i] == 1
                          for i in range(len(base_sorted)-1))

    if has_consecutive:
        # 已有連號，直接返回
        return {
            'numbers': sorted(base_nums),
            'confidence': 0.65,
            'method': 'consecutive_enhance',
            'consecutive_added': False
        }

    # 找最常出現的連號對，且不在base中
    pick_count = rules['pickCount']
    min_num = rules['minNumber']
    max_num = rules['maxNumber']

    best_pair = None
    for pair, freq in consecutive_freq.most_common():
        if pair[0] not in base_nums or pair[1] not in base_nums:
            best_pair = pair
            break

    if not best_pair:
        # 隨機選一個連號對
        import random
        start = random.randint(min_num, max_num - 1)
        best_pair = (start, start + 1)

    # 替換base中的2個號碼為連號對
    result_nums = list(base_nums)

    # 移除2個號碼
    while len(result_nums) > pick_count - 2:
        # 移除離連號對最遠的號碼
        result_nums.sort()
        if abs(result_nums[0] - best_pair[0]) > abs(result_nums[-1] - best_pair[1]):
            result_nums.pop(0)
        else:
            result_nums.pop()

    # 加入連號對
    result_nums.extend(best_pair)
    result_nums = sorted(set(result_nums))[:pick_count]

    return {
        'numbers': result_nums,
        'confidence': 0.65,
        'method': 'consecutive_enhance',
        'consecutive_added': True,
        'consecutive_pair': best_pair
    }


def cold_number_predict(history, rules, cold_threshold=20):
    """
    冷號回歸法: 選擇超過N期未出現的號碼
    理論: 長期未出現的號碼有「回歸」傾向
    """
    min_num = rules['minNumber']
    max_num = rules['maxNumber']
    pick_count = rules['pickCount']

    # 統計每個號碼最後出現的期數
    last_seen = {n: float('inf') for n in range(min_num, max_num + 1)}

    for i, draw in enumerate(history):
        for num in draw['numbers']:
            if last_seen[num] == float('inf'):
                last_seen[num] = i

    # 找出冷號 (超過threshold期未出現)
    cold_numbers = [n for n, seen in last_seen.items() if seen >= cold_threshold]

    # 按冷度排序 (越久沒出現越優先)
    cold_numbers.sort(key=lambda n: last_seen[n], reverse=True)

    if len(cold_numbers) >= pick_count:
        # 有足夠冷號
        selected = cold_numbers[:pick_count]
    else:
        # 補充次冷號碼
        selected = cold_numbers.copy()
        warm_numbers = [(n, seen) for n, seen in last_seen.items() if n not in selected]
        warm_numbers.sort(key=lambda x: x[1], reverse=True)

        for n, seen in warm_numbers:
            selected.append(n)
            if len(selected) >= pick_count:
                break

    return {
        'numbers': sorted(selected[:pick_count]),
        'confidence': 0.6,
        'method': 'cold_number',
        'cold_count': len(cold_numbers),
        'coldest_gap': max(last_seen.values()) if cold_numbers else 0
    }


def cold_hot_mix_predict(history, rules, cold_threshold=15):
    """
    冷熱混合法: 3個冷號 + 2個熱號
    理論: 平衡冷號回歸與熱號延續
    """
    min_num = rules['minNumber']
    max_num = rules['maxNumber']

    # 統計近50期頻率 (熱號)
    hot_freq = Counter()
    for draw in history[:50]:
        hot_freq.update(draw['numbers'])

    # 統計冷號
    last_seen = {n: float('inf') for n in range(min_num, max_num + 1)}
    for i, draw in enumerate(history):
        for num in draw['numbers']:
            if last_seen[num] == float('inf'):
                last_seen[num] = i

    cold_numbers = [n for n, seen in last_seen.items() if seen >= cold_threshold]
    cold_numbers.sort(key=lambda n: last_seen[n], reverse=True)

    hot_numbers = [n for n, freq in hot_freq.most_common(10)]

    # 選3冷2熱
    selected = []

    # 先選3個冷號
    for n in cold_numbers:
        if n not in selected:
            selected.append(n)
        if len(selected) >= 3:
            break

    # 再選2個熱號 (不與冷號重複)
    for n in hot_numbers:
        if n not in selected:
            selected.append(n)
        if len(selected) >= 5:
            break

    # 補足5個
    if len(selected) < 5:
        for n in range(min_num, max_num + 1):
            if n not in selected:
                selected.append(n)
            if len(selected) >= 5:
                break

    return {
        'numbers': sorted(selected[:5]),
        'confidence': 0.65,
        'method': 'cold_hot_mix',
        'cold_count': min(3, len(cold_numbers)),
        'hot_count': 2
    }


# ============================================================
# 回測執行
# ============================================================

def run_backtest():
    """執行2025年滾動回測"""

    history = db_manager.get_all_draws('DAILY_539')

    # 找出2025年數據
    test_draws = []
    for i, d in enumerate(history):
        draw_id = str(d.get('draw', ''))
        if draw_id.startswith('114'):
            test_draws.append((i, d))

    test_draws = list(reversed(test_draws))

    print("=" * 80)
    print("今彩539 新預測方法驗證 - 2025年滾動回測")
    print("=" * 80)
    print(f"測試期數: {len(test_draws)} 期")
    print(f"測試範圍: {test_draws[0][1]['draw']} ~ {test_draws[-1][1]['draw']}")
    print()

    # 定義要測試的方法
    methods = [
        ('共識投票法 (≥3票)', lambda h: consensus_voting_predict(h, rules, min_votes=3)),
        ('共識投票法 (≥4票)', lambda h: consensus_voting_predict(h, rules, min_votes=4)),
        ('連號強化法', lambda h: consecutive_enhance_predict(h, rules)),
        ('冷號回歸法 (20期)', lambda h: cold_number_predict(h, rules, cold_threshold=20)),
        ('冷號回歸法 (15期)', lambda h: cold_number_predict(h, rules, cold_threshold=15)),
        ('冷熱混合法', lambda h: cold_hot_mix_predict(h, rules)),
        # 對照組: 現有最佳方法
        ('sum_range (對照)', lambda h: prediction_engine.sum_range_predict(h[:300], rules)),
    ]

    results = {name: {'wins': 0, 'total': 0, 'matches': Counter()} for name, _ in methods}

    for orig_idx, target in test_draws:
        train_data = history[orig_idx + 1:]

        if len(train_data) < 300:
            continue

        actual = set(target['numbers'])

        for name, method in methods:
            try:
                pred = method(train_data)
                pred_nums = set(pred['numbers'])
                matches = len(pred_nums & actual)

                results[name]['matches'][matches] += 1
                results[name]['total'] += 1

                if matches >= 2:
                    results[name]['wins'] += 1
            except Exception as e:
                pass

    # 輸出結果
    print("=" * 80)
    print("回測結果比較")
    print("=" * 80)
    print()
    print(f"{'方法名稱':<25} {'中獎率':>10} {'每N期中1':>10} {'中3個':>8} {'中4個':>8} {'中5個':>8}")
    print("-" * 80)

    method_stats = []

    for name, stats in results.items():
        if stats['total'] == 0:
            continue

        win_rate = stats['wins'] / stats['total']
        periods_per_win = stats['total'] / stats['wins'] if stats['wins'] > 0 else float('inf')

        hit3 = stats['matches'][3]
        hit4 = stats['matches'][4]
        hit5 = stats['matches'][5]

        method_stats.append({
            'name': name,
            'win_rate': win_rate,
            'periods_per_win': periods_per_win,
            'hit3': hit3,
            'hit4': hit4,
            'hit5': hit5,
            'total': stats['total'],
            'matches': stats['matches']
        })

        print(f"{name:<25} {win_rate*100:>9.2f}% {periods_per_win:>10.1f} {hit3:>8} {hit4:>8} {hit5:>8}")

    # 排序並找出最佳
    method_stats.sort(key=lambda x: (x['hit4'] + x['hit5'], x['hit3'], x['win_rate']), reverse=True)

    print()
    print("=" * 80)
    print("大獎潛力排名 (優先考慮中4-5個的次數)")
    print("=" * 80)

    for i, m in enumerate(method_stats):
        big_prize = m['hit4'] + m['hit5']
        print(f"{i+1}. {m['name']}: 中4+5={big_prize}次, 中3={m['hit3']}次, 中獎率={m['win_rate']*100:.2f}%")

    print()
    print("=" * 80)
    print("命中數詳細分布")
    print("=" * 80)

    for m in method_stats:
        print(f"\n📊 {m['name']}:")
        total = m['total']
        for i in range(5, -1, -1):
            count = m['matches'][i]
            pct = count / total * 100 if total > 0 else 0
            bar = "█" * int(pct / 2)
            status = "🏆" if i >= 4 else ("✅" if i >= 2 else "")
            print(f"   {i}個: {count:>4}次 ({pct:>5.1f}%) {bar} {status}")

    return method_stats


if __name__ == '__main__':
    stats = run_backtest()
