#!/usr/bin/env python3
"""
真正正交的組合策略研究
將 Cluster Pivot 與完全不同邏輯的方法結合
"""
import sqlite3
import json
import os
from collections import Counter, defaultdict
from typing import List, Dict, Set, Tuple
from itertools import combinations
import random

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_all_draws(db_path: str, lottery_type: str = 'BIG_LOTTO') -> List[Dict]:
    """讀取開獎數據"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = ? ORDER BY date ASC
    """, (lottery_type,))
    draws = []
    for row in cursor.fetchall():
        numbers = json.loads(row[2]) if row[2] else []
        draws.append({
            'draw': row[0],
            'date': row[1],
            'numbers': numbers
        })
    conn.close()
    return draws


# ============== 方法類型 A: 共現關係 (Cluster Pivot) ==============

def cluster_pivot_predict(history: List[Dict], max_num: int = 49, pick_count: int = 6,
                          window: int = None) -> List[int]:
    """Cluster Pivot 預測"""
    if len(history) < 30:
        return []

    recent = history[-window:] if window and len(history) >= window else history

    cooccur = Counter()
    for draw in recent:
        nums = draw['numbers']
        for pair in combinations(sorted(nums), 2):
            cooccur[pair] += 1

    num_scores = Counter()
    for (a, b), count in cooccur.items():
        num_scores[a] += count
        num_scores[b] += count

    centers = [num for num, _ in num_scores.most_common(3)]
    if not centers:
        return []

    anchor = centers[0]
    candidates = Counter()
    for (a, b), count in cooccur.items():
        if a == anchor:
            candidates[b] += count
        elif b == anchor:
            candidates[a] += count

    selected = [anchor]
    for num, _ in candidates.most_common(pick_count - 1):
        if num not in selected:
            selected.append(num)
        if len(selected) >= pick_count:
            break

    while len(selected) < pick_count:
        for n in range(1, max_num + 1):
            if n not in selected:
                selected.append(n)
                break

    return sorted(selected[:pick_count])


# ============== 方法類型 B: 純頻率 (獨立於共現) ==============

def pure_frequency_predict(history: List[Dict], max_num: int = 49, pick_count: int = 6,
                           window: int = 50) -> List[int]:
    """純頻率預測（不考慮共現）"""
    if len(history) < 10:
        return []

    recent = history[-window:] if len(history) >= window else history

    freq = Counter()
    for draw in recent:
        for num in draw['numbers']:
            freq[num] += 1

    selected = [n for n, _ in freq.most_common(pick_count)]
    return sorted(selected)


# ============== 方法類型 C: 純遺漏 (獨立於共現) ==============

def pure_gap_predict(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[int]:
    """純遺漏預測（選擇最久未出現的號碼）"""
    if len(history) < 10:
        return []

    gap = {}
    for num in range(1, max_num + 1):
        gap[num] = len(history)
        for i, draw in enumerate(reversed(history)):
            if num in draw['numbers']:
                gap[num] = i
                break

    # 選擇遺漏值最大的
    selected = sorted(gap.keys(), key=lambda x: -gap[x])[:pick_count]
    return sorted(selected)


# ============== 方法類型 D: 區間平衡 (結構性) ==============

def zone_balance_predict(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[int]:
    """區間平衡預測（確保號碼分佈均勻）"""
    if len(history) < 10:
        return []

    # 將號碼分成區間
    zones = [
        list(range(1, 10)),     # 1-9
        list(range(10, 20)),    # 10-19
        list(range(20, 30)),    # 20-29
        list(range(30, 40)),    # 30-39
        list(range(40, 50)),    # 40-49
    ]

    # 計算每個區間的熱門號碼
    freq = Counter()
    for draw in history[-100:]:
        for num in draw['numbers']:
            freq[num] += 1

    selected = []
    nums_per_zone = pick_count // len(zones) + 1

    for zone in zones:
        zone_nums = sorted(zone, key=lambda x: -freq.get(x, 0))
        for num in zone_nums[:nums_per_zone]:
            if len(selected) < pick_count:
                selected.append(num)

    return sorted(selected[:pick_count])


# ============== 方法類型 E: 奇偶平衡 ==============

def odd_even_balance_predict(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[int]:
    """奇偶平衡預測"""
    if len(history) < 10:
        return []

    freq = Counter()
    for draw in history[-100:]:
        for num in draw['numbers']:
            freq[num] += 1

    odds = sorted([n for n in range(1, max_num + 1, 2)], key=lambda x: -freq.get(x, 0))
    evens = sorted([n for n in range(2, max_num + 1, 2)], key=lambda x: -freq.get(x, 0))

    # 3奇3偶
    selected = odds[:3] + evens[:3]
    return sorted(selected[:pick_count])


# ============== 真正正交的組合策略 ==============

def true_orthogonal_2bet(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[List[int]]:
    """
    真正正交 2 注：
    - 注1: Cluster Pivot (共現邏輯)
    - 注2: Pure Gap (遺漏邏輯) - 完全不同的選號方式
    """
    bet1 = cluster_pivot_predict(history, max_num, pick_count)
    bet2 = pure_gap_predict(history, max_num, pick_count)
    return [bet1, bet2] if bet1 and bet2 else []


def true_orthogonal_3bet(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[List[int]]:
    """
    真正正交 3 注：
    - 注1: Cluster Pivot (共現邏輯)
    - 注2: Pure Frequency (頻率邏輯)
    - 注3: Zone Balance (結構邏輯)
    """
    bet1 = cluster_pivot_predict(history, max_num, pick_count)
    bet2 = pure_frequency_predict(history, max_num, pick_count)
    bet3 = zone_balance_predict(history, max_num, pick_count)
    return [b for b in [bet1, bet2, bet3] if b]


def true_orthogonal_4bet(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[List[int]]:
    """
    真正正交 4 注：
    - 注1: Cluster Pivot (共現邏輯)
    - 注2: Pure Gap (遺漏邏輯)
    - 注3: Zone Balance (結構邏輯)
    - 注4: Odd-Even Balance (奇偶邏輯)
    """
    bet1 = cluster_pivot_predict(history, max_num, pick_count)
    bet2 = pure_gap_predict(history, max_num, pick_count)
    bet3 = zone_balance_predict(history, max_num, pick_count)
    bet4 = odd_even_balance_predict(history, max_num, pick_count)
    return [b for b in [bet1, bet2, bet3, bet4] if b]


def cluster_pivot_multi_window(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[List[int]]:
    """
    多窗口 Cluster Pivot：用不同時間窗口
    """
    bets = []
    seen = set()

    for window in [50, 100, 200, None]:  # None = 全部歷史
        bet = cluster_pivot_predict(history, max_num, pick_count, window)
        if bet:
            bet_tuple = tuple(bet)
            if bet_tuple not in seen:
                bets.append(bet)
                seen.add(bet_tuple)

    return bets[:4]


def diversity_enforced_4bet(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[List[int]]:
    """
    強制多樣性 4 注：每注最多重疊 2 個號碼
    """
    methods = [
        lambda: cluster_pivot_predict(history, max_num, pick_count),
        lambda: pure_frequency_predict(history, max_num, pick_count),
        lambda: pure_gap_predict(history, max_num, pick_count),
        lambda: zone_balance_predict(history, max_num, pick_count),
        lambda: odd_even_balance_predict(history, max_num, pick_count),
    ]

    bets = []
    all_used = set()

    for method in methods:
        if len(bets) >= 4:
            break

        bet = method()
        if not bet:
            continue

        # 檢查重疊
        overlap = len(set(bet) & all_used)
        if overlap <= 2:  # 最多重疊 2 個
            bets.append(bet)
            all_used.update(bet)

    return bets


# ============== 回測 ==============

def run_backtest(test_periods: int = 150):
    """運行回測"""
    print("=" * 80)
    print("🔬 真正正交組合策略研究")
    print("=" * 80)

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    all_draws = get_all_draws(db_path, lottery_type='BIG_LOTTO')

    print(f"總數據量: {len(all_draws)} 期")
    print(f"回測期數: {test_periods}")

    max_num = 49
    pick_count = 6
    start_idx = len(all_draws) - test_periods

    strategies = {
        # 基準
        '1注 Cluster Pivot': lambda h: [cluster_pivot_predict(h, max_num, pick_count)],
        '1注 Pure Frequency': lambda h: [pure_frequency_predict(h, max_num, pick_count)],
        '1注 Pure Gap': lambda h: [pure_gap_predict(h, max_num, pick_count)],
        '1注 Zone Balance': lambda h: [zone_balance_predict(h, max_num, pick_count)],
        # 正交組合
        '2注 Orthogonal': lambda h: true_orthogonal_2bet(h, max_num, pick_count),
        '3注 Orthogonal': lambda h: true_orthogonal_3bet(h, max_num, pick_count),
        '4注 Orthogonal': lambda h: true_orthogonal_4bet(h, max_num, pick_count),
        # 其他策略
        '4注 MultiWindow': lambda h: cluster_pivot_multi_window(h, max_num, pick_count),
        '4注 Diversity': lambda h: diversity_enforced_4bet(h, max_num, pick_count),
    }

    results = {name: {'m3': 0, 'm4': 0, 'total': 0, 'bets': 0} for name in strategies}

    for target_idx in range(start_idx, len(all_draws)):
        history = all_draws[:target_idx]
        target = all_draws[target_idx]

        if len(history) < 100:
            continue

        actual = set(target['numbers'])

        for name, strategy_fn in strategies.items():
            bets = strategy_fn(history)
            if not bets or not bets[0]:
                continue

            max_match = 0
            for bet in bets:
                if bet:
                    match_count = len(set(bet) & actual)
                    if match_count > max_match:
                        max_match = match_count
                    results[name]['bets'] += 1

            results[name]['total'] += 1
            if max_match >= 3:
                results[name]['m3'] += 1
            if max_match >= 4:
                results[name]['m4'] += 1

    # 輸出結果
    print("\n" + "=" * 80)
    print("📊 回測結果")
    print("=" * 80)

    print(f"\n{'策略':<25} {'M3+':<8} {'M4+':<8} {'M3率':<10} {'效益/注':<10}")
    print("-" * 70)

    for name, r in sorted(results.items(), key=lambda x: -x[1]['m3']):
        total = r['total']
        rate = r['m3'] / total * 100 if total > 0 else 0
        bets = r['bets']
        efficiency = r['m3'] / bets * 100 if bets > 0 else 0

        print(f"{name:<25} {r['m3']:<8} {r['m4']:<8} {rate:.2f}%{'':<5} {efficiency:.2f}%")

    # 計算號碼重疊度
    print("\n" + "=" * 80)
    print("📊 號碼重疊分析（最後一期）")
    print("=" * 80)

    history = all_draws[:-1]
    for name, strategy_fn in strategies.items():
        if '注' not in name or '1注' in name:
            continue
        bets = strategy_fn(history)
        if bets and len(bets) > 1:
            all_nums = []
            for bet in bets:
                all_nums.extend(bet)
            unique = len(set(all_nums))
            total = len(all_nums)
            overlap_rate = (1 - unique / total) * 100 if total > 0 else 0
            print(f"{name}: 總號碼 {total}, 不重複 {unique}, 重疊率 {overlap_rate:.1f}%")

    # 隨機基準
    print("\n" + "=" * 80)
    print("📊 vs 隨機基準")
    print("=" * 80)

    random.seed(42)

    def test_random(num_bets, trials=30):
        total = 0
        for _ in range(trials):
            count = 0
            for target_idx in range(start_idx, len(all_draws)):
                actual = set(all_draws[target_idx]['numbers'])
                max_m = 0
                for _ in range(num_bets):
                    bet = set(random.sample(range(1, 50), 6))
                    max_m = max(max_m, len(bet & actual))
                if max_m >= 3:
                    count += 1
            total += count
        return total / trials / test_periods * 100

    rand1 = test_random(1)
    rand2 = test_random(2)
    rand3 = test_random(3)
    rand4 = test_random(4)

    print(f"\n隨機 1 注: {rand1:.2f}%")
    print(f"隨機 2 注: {rand2:.2f}%")
    print(f"隨機 3 注: {rand3:.2f}%")
    print(f"隨機 4 注: {rand4:.2f}%")

    print("\n" + "-" * 70)

    for name, r in sorted(results.items(), key=lambda x: -x[1]['m3']):
        total = r['total']
        rate = r['m3'] / total * 100 if total > 0 else 0

        if '1注' in name:
            rand = rand1
        elif '2注' in name:
            rand = rand2
        elif '3注' in name:
            rand = rand3
        else:
            rand = rand4

        diff = rate - rand
        status = "✅" if diff > 0 else "❌"
        print(f"{name}: {rate:.2f}% vs 隨機 {rand:.2f}% ({diff:+.2f}%) {status}")

    return results


if __name__ == '__main__':
    run_backtest(test_periods=150)
