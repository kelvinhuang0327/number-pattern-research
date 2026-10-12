#!/usr/bin/env python3
"""
Cluster Pivot 策略 - 大樂透版本

核心理念：
1. 找出「聚類中心」- 歷史上經常一起出現的號碼群
2. 以中心為錨點，擴展到周邊號碼
3. 多注覆蓋不同的聚類中心

與「中值選號」的差異：
- 中值選號：基於個別號碼的頻率/遺漏
- Cluster Pivot：基於號碼之間的「共現關係」
"""
import sqlite3
import json
import os
from collections import Counter, defaultdict
from typing import List, Dict, Set, Tuple
from itertools import combinations

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
        numbers = json.loads(row[1 + 1]) if row[1 + 1] else []
        draws.append({'draw_number': row[0], 'numbers': numbers})
    conn.close()
    return draws


def build_cooccurrence_matrix(history: List[Dict], max_num: int = 49) -> Dict[Tuple[int, int], int]:
    """建立號碼共現矩陣"""
    cooccur = Counter()
    for draw in history:
        nums = draw['numbers']
        for pair in combinations(sorted(nums), 2):
            cooccur[pair] += 1
    return cooccur


def find_cluster_centers(cooccur: Dict, max_num: int = 49, top_k: int = 5) -> List[int]:
    """
    找出聚類中心 - 與其他號碼共現次數最高的號碼
    """
    num_scores = Counter()
    for (a, b), count in cooccur.items():
        num_scores[a] += count
        num_scores[b] += count

    # 返回最高分的 top_k 個號碼
    return [num for num, _ in num_scores.most_common(top_k)]


def expand_from_anchor(anchor: int, cooccur: Dict, max_num: int = 49,
                        pick_count: int = 6, exclude: Set[int] = None) -> List[int]:
    """
    從錨點擴展選號
    選擇與錨點共現次數最高的號碼
    """
    if exclude is None:
        exclude = set()

    # 找出與錨點共現次數最高的號碼
    candidates = Counter()
    for (a, b), count in cooccur.items():
        if a == anchor and b not in exclude:
            candidates[b] += count
        elif b == anchor and a not in exclude:
            candidates[a] += count

    # 確保錨點在內
    selected = [anchor]
    for num, _ in candidates.most_common(pick_count - 1):
        if num not in selected:
            selected.append(num)
        if len(selected) >= pick_count:
            break

    # 如果不夠，補充高共現分的號碼
    while len(selected) < pick_count:
        for num in range(1, max_num + 1):
            if num not in selected and num not in exclude:
                selected.append(num)
                break

    return sorted(selected[:pick_count])


def cluster_pivot_single_bet(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[int]:
    """單注 Cluster Pivot"""
    if len(history) < 30:
        return []

    cooccur = build_cooccurrence_matrix(history, max_num)
    centers = find_cluster_centers(cooccur, max_num, top_k=3)

    if not centers:
        return []

    # 以最強的中心為錨點
    return expand_from_anchor(centers[0], cooccur, max_num, pick_count)


def cluster_pivot_2bet(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[List[int]]:
    """
    雙注 Cluster Pivot
    - 注1：以最強聚類中心為錨
    - 注2：以第二強聚類中心為錨，排除注1的號碼
    """
    if len(history) < 30:
        return []

    cooccur = build_cooccurrence_matrix(history, max_num)
    centers = find_cluster_centers(cooccur, max_num, top_k=5)

    if len(centers) < 2:
        return []

    bet1 = expand_from_anchor(centers[0], cooccur, max_num, pick_count)
    bet2 = expand_from_anchor(centers[1], cooccur, max_num, pick_count, exclude=set(bet1[:2]))

    return [bet1, bet2]


def cluster_pivot_3bet(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[List[int]]:
    """
    三注 Cluster Pivot
    - 注1：最強聚類中心
    - 注2：次強聚類中心
    - 注3：第三強聚類中心 + 擾動
    """
    if len(history) < 30:
        return []

    cooccur = build_cooccurrence_matrix(history, max_num)
    centers = find_cluster_centers(cooccur, max_num, top_k=6)

    if len(centers) < 3:
        return []

    bet1 = expand_from_anchor(centers[0], cooccur, max_num, pick_count)
    bet2 = expand_from_anchor(centers[1], cooccur, max_num, pick_count, exclude=set(bet1[:2]))
    bet3 = expand_from_anchor(centers[2], cooccur, max_num, pick_count, exclude=set(bet1[:1] + bet2[:1]))

    return [bet1, bet2, bet3]


def cluster_pivot_windowed(history: List[Dict], window: int = 100,
                           max_num: int = 49, pick_count: int = 6,
                           num_bets: int = 2) -> List[List[int]]:
    """
    帶窗口的 Cluster Pivot
    只使用最近 N 期數據建立共現矩陣
    """
    if len(history) < window:
        recent = history
    else:
        recent = history[-window:]

    if len(recent) < 30:
        return []

    cooccur = build_cooccurrence_matrix(recent, max_num)
    centers = find_cluster_centers(cooccur, max_num, top_k=num_bets + 3)

    if len(centers) < num_bets:
        return []

    bets = []
    used = set()
    for i in range(num_bets):
        bet = expand_from_anchor(centers[i], cooccur, max_num, pick_count, exclude=used)
        bets.append(bet)
        used.update(bet[:2])  # 排除前兩個號碼

    return bets


def cluster_pivot_hybrid(history: List[Dict], max_num: int = 49,
                         pick_count: int = 6, num_bets: int = 3) -> List[List[int]]:
    """
    混合策略：結合長期共現 + 近期共現
    - 注1：基於全部歷史
    - 注2：基於最近 50 期
    - 注3：基於最近 100 期（如果 num_bets >= 3）
    - 注4：基於最近 30 期（如果 num_bets >= 4）
    """
    if len(history) < 50:
        return []

    # 全部歷史
    cooccur_all = build_cooccurrence_matrix(history, max_num)
    centers_all = find_cluster_centers(cooccur_all, max_num, top_k=3)

    # 近 50 期
    cooccur_50 = build_cooccurrence_matrix(history[-50:], max_num)
    centers_50 = find_cluster_centers(cooccur_50, max_num, top_k=3)

    bets = []
    used = set()

    # 注1：全歷史最強中心
    if centers_all:
        bet1 = expand_from_anchor(centers_all[0], cooccur_all, max_num, pick_count)
        bets.append(bet1)
        used.update(bet1[:2])

    # 注2：近期最強中心
    if centers_50 and num_bets >= 2:
        bet2 = expand_from_anchor(centers_50[0], cooccur_50, max_num, pick_count, exclude=used)
        bets.append(bet2)
        used.update(bet2[:2])

    # 注3：近100期
    if num_bets >= 3 and len(history) >= 100:
        cooccur_100 = build_cooccurrence_matrix(history[-100:], max_num)
        centers_100 = find_cluster_centers(cooccur_100, max_num, top_k=3)
        if centers_100:
            bet3 = expand_from_anchor(centers_100[0], cooccur_100, max_num, pick_count, exclude=used)
            bets.append(bet3)
            used.update(bet3[:2])

    # 注4：近30期（最短期趨勢）
    if num_bets >= 4 and len(history) >= 30:
        cooccur_30 = build_cooccurrence_matrix(history[-30:], max_num)
        centers_30 = find_cluster_centers(cooccur_30, max_num, top_k=3)
        if centers_30:
            bet4 = expand_from_anchor(centers_30[0], cooccur_30, max_num, pick_count, exclude=used)
            bets.append(bet4)

    return bets


def cluster_pivot_4bet(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[List[int]]:
    """
    四注 Cluster Pivot - 多中心覆蓋
    """
    if len(history) < 30:
        return []

    cooccur = build_cooccurrence_matrix(history, max_num)
    centers = find_cluster_centers(cooccur, max_num, top_k=8)

    if len(centers) < 4:
        return []

    bets = []
    used = set()
    for i in range(4):
        bet = expand_from_anchor(centers[i], cooccur, max_num, pick_count, exclude=used)
        bets.append(bet)
        used.update(bet[:1])  # 只排除錨點

    return bets


def run_backtest(test_periods: int = 150):
    """執行回測"""
    print("=" * 80)
    print("🔬 Cluster Pivot 策略回測 (大樂透)")
    print("=" * 80)

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    all_draws = get_all_draws(db_path, lottery_type='BIG_LOTTO')

    print(f"總數據量: {len(all_draws)} 期")
    print(f"回測期數: {test_periods}")

    start_idx = len(all_draws) - test_periods

    # 測試策略
    strategies = {
        '單注 Cluster Pivot': lambda h: [cluster_pivot_single_bet(h)],
        '雙注 Cluster Pivot': cluster_pivot_2bet,
        '三注 Cluster Pivot': cluster_pivot_3bet,
        '四注 Cluster Pivot': cluster_pivot_4bet,
        # 窗口變體
        '雙注 Win50': lambda h: cluster_pivot_windowed(h, window=50, num_bets=2),
        # 混合策略
        '三注 Hybrid': lambda h: cluster_pivot_hybrid(h, num_bets=3),
        '四注 Hybrid': lambda h: cluster_pivot_hybrid(h, num_bets=4),
    }

    results = {name: {'m3': 0, 'm4': 0, 'total': 0, 'details': []} for name in strategies}

    for target_idx in range(start_idx, len(all_draws)):
        history = all_draws[:target_idx]
        target = all_draws[target_idx]

        if len(history) < 50:
            continue

        actual = set(target['numbers'])
        draw_num = target['draw_number']

        for name, strategy_fn in strategies.items():
            bets = strategy_fn(history)
            if not bets or not bets[0]:
                continue

            max_match = 0
            best_bet = None
            for bet in bets:
                match_count = len(set(bet) & actual)
                if match_count > max_match:
                    max_match = match_count
                    best_bet = bet

            results[name]['total'] += 1
            if max_match >= 3:
                results[name]['m3'] += 1
            if max_match >= 4:
                results[name]['m4'] += 1
                results[name]['details'].append({
                    'draw': draw_num,
                    'actual': sorted(list(actual)),
                    'bet': best_bet,
                    'match': max_match
                })

    # 輸出結果
    print("\n" + "=" * 80)
    print("📊 回測結果")
    print("=" * 80)

    print(f"\n{'策略':<25} {'Match-3+':<12} {'Match-4+':<12} {'M3率':<10} {'每注效益':<10}")
    print("-" * 75)

    for name, r in results.items():
        total = r['total']
        rate3 = r['m3'] / total * 100 if total > 0 else 0
        rate4 = r['m4'] / total * 100 if total > 0 else 0

        if '單注' in name:
            bet_count = 1
        elif '四注' in name:
            bet_count = 4
        elif '三注' in name:
            bet_count = 3
        elif '雙注' in name:
            bet_count = 2
        else:
            bet_count = 2

        efficiency = rate3 / bet_count

        print(f"{name:<25} {r['m3']:<12} {r['m4']:<12} {rate3:.2f}%{'':<5} {efficiency:.2f}%")

    # 隨機基準對比
    import random
    random.seed(42)

    def test_random(num_bets, trials=50):
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

    print("\n" + "=" * 80)
    print("📊 vs 隨機基準")
    print("=" * 80)

    rand1 = test_random(1)
    rand2 = test_random(2)
    rand3 = test_random(3)
    rand4 = test_random(4)

    for name, r in results.items():
        total = r['total']
        rate3 = r['m3'] / total * 100 if total > 0 else 0

        if '單注' in name:
            rand = rand1
        elif '四注' in name:
            rand = rand4
        elif '三注' in name:
            rand = rand3
        elif '雙注' in name:
            rand = rand2
        else:
            rand = rand3

        diff = rate3 - rand
        status = "✅" if diff > 0 else "❌"
        print(f"{name}: {rate3:.2f}% vs 隨機 {rand:.2f}% ({diff:+.2f}%) {status}")

    return results


def overfitting_check(test_periods: int = 200):
    """
    過擬合檢測：分時段驗證
    """
    print("\n" + "=" * 80)
    print("🔍 過擬合檢測 (分4時段穩定性)")
    print("=" * 80)

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    all_draws = get_all_draws(db_path, lottery_type='BIG_LOTTO')

    # 取最近 test_periods 期，分成4段
    start_idx = len(all_draws) - test_periods
    segment_size = test_periods // 4

    strategies = {
        '三注 Hybrid': lambda h: cluster_pivot_hybrid(h, num_bets=3),
        '四注 Cluster Pivot': cluster_pivot_4bet,
    }

    for name, strategy_fn in strategies.items():
        print(f"\n📊 {name}")
        print("-" * 50)

        segment_rates = []
        for seg in range(4):
            seg_start = start_idx + seg * segment_size
            seg_end = seg_start + segment_size

            wins = 0
            total = 0
            for target_idx in range(seg_start, seg_end):
                history = all_draws[:target_idx]
                target = all_draws[target_idx]

                if len(history) < 50:
                    continue

                actual = set(target['numbers'])
                bets = strategy_fn(history)

                if not bets or not bets[0]:
                    continue

                max_match = 0
                for bet in bets:
                    match_count = len(set(bet) & actual)
                    if match_count > max_match:
                        max_match = match_count

                total += 1
                if max_match >= 3:
                    wins += 1

            rate = wins / total * 100 if total > 0 else 0
            segment_rates.append(rate)
            print(f"  段{seg+1}: {rate:.2f}% ({wins}/{total})")

        # 計算穩定性
        if segment_rates:
            avg_rate = sum(segment_rates) / len(segment_rates)
            max_rate = max(segment_rates)
            min_rate = min(segment_rates)
            variance = max_rate - min_rate

            # 計算衰減（最近段 vs 其他段平均）
            recent_rate = segment_rates[-1]
            earlier_avg = sum(segment_rates[:-1]) / len(segment_rates[:-1]) if len(segment_rates) > 1 else segment_rates[0]
            decay = earlier_avg - recent_rate

            print(f"\n  📈 平均: {avg_rate:.2f}%")
            print(f"  📉 變異: {variance:.2f}% (最高 {max_rate:.2f}% - 最低 {min_rate:.2f}%)")
            print(f"  📊 衰減: {decay:+.2f}%")

            # 風險評估
            if variance < 3 and decay < 2:
                print(f"  ✅ 風險: 低 (穩定)")
            elif variance < 6 or decay < 4:
                print(f"  ⚠️ 風險: 中 (需監控)")
            else:
                print(f"  🔴 風險: 高 (可能過擬合)")


if __name__ == '__main__':
    run_backtest(test_periods=150)
    overfitting_check(test_periods=200)
