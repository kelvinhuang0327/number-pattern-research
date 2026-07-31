#!/usr/bin/env python3
"""
研究 Cluster Pivot 增強方案
探索類似方法和組合策略
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


# ============== 基礎工具 ==============

def build_cooccurrence_matrix(history: List[Dict], max_num: int = 49) -> Dict[Tuple[int, int], int]:
    """建立號碼共現矩陣"""
    cooccur = Counter()
    for draw in history:
        nums = draw['numbers']
        for pair in combinations(sorted(nums), 2):
            cooccur[pair] += 1
    return cooccur


def find_cluster_centers(cooccur: Dict, max_num: int = 49, top_k: int = 5) -> List[int]:
    """找出聚類中心"""
    num_scores = Counter()
    for (a, b), count in cooccur.items():
        num_scores[a] += count
        num_scores[b] += count
    return [num for num, _ in num_scores.most_common(top_k)]


def expand_from_anchor(anchor: int, cooccur: Dict, max_num: int = 49,
                       pick_count: int = 6, exclude: Set[int] = None) -> List[int]:
    """從錨點擴展選號"""
    if exclude is None:
        exclude = set()

    candidates = Counter()
    for (a, b), count in cooccur.items():
        if a == anchor and b not in exclude:
            candidates[b] += count
        elif b == anchor and a not in exclude:
            candidates[a] += count

    selected = [anchor]
    for num, _ in candidates.most_common(pick_count - 1):
        if num not in selected:
            selected.append(num)
        if len(selected) >= pick_count:
            break

    while len(selected) < pick_count:
        for n in range(1, max_num + 1):
            if n not in selected and n not in exclude:
                selected.append(n)
                break

    return sorted(selected[:pick_count])


# ============== 方法 1: 反共現 (Negative Co-occurrence) ==============

def find_anti_cooccur_numbers(history: List[Dict], max_num: int = 49, top_k: int = 10) -> List[int]:
    """
    找出「很少一起出現」的號碼
    理論：這些號碼可能在某期「集體爆發」
    """
    cooccur = build_cooccurrence_matrix(history, max_num)

    # 計算每個號碼的總共現次數
    num_scores = Counter()
    for (a, b), count in cooccur.items():
        num_scores[a] += count
        num_scores[b] += count

    # 選擇共現最少的號碼（冷門組合）
    least_common = [n for n, _ in num_scores.most_common()[:-top_k-1:-1]]
    return least_common


def anti_cooccur_predict(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[int]:
    """反共現預測"""
    anti_nums = find_anti_cooccur_numbers(history, max_num, top_k=pick_count + 4)
    return sorted(anti_nums[:pick_count])


# ============== 方法 2: 三元組分析 (Triplet Analysis) ==============

def build_triplet_matrix(history: List[Dict], max_num: int = 49) -> Dict[Tuple[int, int, int], int]:
    """建立三元組共現矩陣"""
    triplets = Counter()
    for draw in history:
        nums = sorted(draw['numbers'])
        for triplet in combinations(nums, 3):
            triplets[triplet] += 1
    return triplets


def triplet_predict(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[int]:
    """基於三元組的預測"""
    if len(history) < 50:
        return []

    triplets = build_triplet_matrix(history[-200:], max_num)  # 用近200期

    # 找出最常出現的三元組
    top_triplets = triplets.most_common(10)

    # 從最強三元組擴展
    if not top_triplets:
        return []

    base_triplet = list(top_triplets[0][0])
    selected = set(base_triplet)

    # 補足到 pick_count
    cooccur = build_cooccurrence_matrix(history[-200:], max_num)
    for anchor in base_triplet:
        if len(selected) >= pick_count:
            break
        for (a, b), _ in sorted(cooccur.items(), key=lambda x: -x[1]):
            if a == anchor and b not in selected:
                selected.add(b)
            elif b == anchor and a not in selected:
                selected.add(a)
            if len(selected) >= pick_count:
                break

    return sorted(list(selected)[:pick_count])


# ============== 方法 3: 時序共現 (Temporal Co-occurrence) ==============

def temporal_cooccur_predict(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[int]:
    """
    時序共現：找出「連續兩期都出現」的號碼
    """
    if len(history) < 10:
        return []

    # 計算連續出現的號碼
    consecutive_scores = Counter()
    for i in range(len(history) - 1):
        curr = set(history[i]['numbers'])
        next_draw = set(history[i + 1]['numbers'])
        overlap = curr & next_draw
        for num in overlap:
            consecutive_scores[num] += 1

    # 選擇最常連續出現的號碼
    selected = [n for n, _ in consecutive_scores.most_common(pick_count)]

    # 補足
    if len(selected) < pick_count:
        freq = Counter()
        for d in history[-50:]:
            for n in d['numbers']:
                freq[n] += 1
        for n, _ in freq.most_common():
            if n not in selected:
                selected.append(n)
            if len(selected) >= pick_count:
                break

    return sorted(selected[:pick_count])


# ============== 方法 4: 圖社區檢測 (Graph Community) ==============

def graph_community_predict(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[int]:
    """
    簡化的圖社區檢測
    找出「緊密連接」的號碼群
    """
    if len(history) < 50:
        return []

    cooccur = build_cooccurrence_matrix(history[-150:], max_num)

    # 建立鄰接表
    adj = defaultdict(Counter)
    for (a, b), count in cooccur.items():
        adj[a][b] = count
        adj[b][a] = count

    # 找出連接最緊密的號碼（度數最高）
    degree = {n: sum(adj[n].values()) for n in range(1, max_num + 1)}
    top_nodes = sorted(degree.keys(), key=lambda x: -degree[x])[:10]

    # 從最高度數節點開始，選擇其最強鄰居
    selected = [top_nodes[0]]
    for neighbor, _ in adj[top_nodes[0]].most_common(pick_count - 1):
        if neighbor not in selected:
            selected.append(neighbor)
        if len(selected) >= pick_count:
            break

    return sorted(selected[:pick_count])


# ============== 方法 5: 遺漏補償 (Gap Compensation) ==============

def gap_compensation_predict(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[int]:
    """
    遺漏補償：選擇長期未出現但歷史上常與近期號碼共現的號碼
    """
    if len(history) < 50:
        return []

    # 計算遺漏值
    gap = {}
    for num in range(1, max_num + 1):
        gap[num] = len(history)
        for i, draw in enumerate(reversed(history)):
            if num in draw['numbers']:
                gap[num] = i
                break

    # 找出長期未出現的號碼（遺漏值 > 20）
    long_gap = [n for n in range(1, max_num + 1) if gap[n] > 20]

    if not long_gap:
        long_gap = sorted(gap.keys(), key=lambda x: -gap[x])[:10]

    # 從這些冷號中，選擇歷史上共現頻率高的
    cooccur = build_cooccurrence_matrix(history, max_num)

    cold_scores = Counter()
    for num in long_gap:
        for (a, b), count in cooccur.items():
            if a == num or b == num:
                cold_scores[num] += count

    selected = [n for n, _ in cold_scores.most_common(pick_count)]

    # 補足
    if len(selected) < pick_count:
        for n in long_gap:
            if n not in selected:
                selected.append(n)
            if len(selected) >= pick_count:
                break

    return sorted(selected[:pick_count])


# ============== 組合策略 ==============

def cluster_pivot_base(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[int]:
    """基礎 Cluster Pivot"""
    if len(history) < 30:
        return []
    cooccur = build_cooccurrence_matrix(history, max_num)
    centers = find_cluster_centers(cooccur, max_num, top_k=3)
    if not centers:
        return []
    return expand_from_anchor(centers[0], cooccur, max_num, pick_count)


def orthogonal_4bet(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[List[int]]:
    """
    正交4注組合：每注使用不同邏輯
    """
    bets = []
    used = set()

    # 注1: Cluster Pivot (共現中心)
    bet1 = cluster_pivot_base(history, max_num, pick_count)
    if bet1:
        bets.append(bet1)
        used.update(bet1[:2])

    # 注2: Triplet (三元組)
    bet2 = triplet_predict(history, max_num, pick_count)
    if bet2 and bet2 != bet1:
        bets.append(bet2)
        used.update(bet2[:2])

    # 注3: Gap Compensation (遺漏補償)
    bet3 = gap_compensation_predict(history, max_num, pick_count)
    if bet3:
        bets.append(bet3)
        used.update(bet3[:2])

    # 注4: Temporal (時序共現)
    bet4 = temporal_cooccur_predict(history, max_num, pick_count)
    if bet4:
        bets.append(bet4)

    return bets[:4]


def hybrid_5bet(history: List[Dict], max_num: int = 49, pick_count: int = 6) -> List[List[int]]:
    """
    混合5注：Cluster Pivot 變體 + 互補方法
    """
    bets = []

    # 使用不同窗口的 Cluster Pivot
    windows = [50, 100, 200]
    for w in windows:
        if len(history) >= w:
            recent = history[-w:]
            cooccur = build_cooccurrence_matrix(recent, max_num)
            centers = find_cluster_centers(cooccur, max_num, top_k=3)
            if centers:
                bet = expand_from_anchor(centers[0], cooccur, max_num, pick_count)
                if bet and bet not in bets:
                    bets.append(bet)

    # 補充其他方法
    if len(bets) < 5:
        bet = triplet_predict(history, max_num, pick_count)
        if bet and bet not in bets:
            bets.append(bet)

    if len(bets) < 5:
        bet = gap_compensation_predict(history, max_num, pick_count)
        if bet and bet not in bets:
            bets.append(bet)

    return bets[:5]


# ============== 回測 ==============

def run_backtest(test_periods: int = 150):
    """運行回測"""
    print("=" * 80)
    print("🔬 Cluster Pivot 增強方案研究")
    print("=" * 80)

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    all_draws = get_all_draws(db_path, lottery_type='BIG_LOTTO')

    print(f"總數據量: {len(all_draws)} 期")
    print(f"回測期數: {test_periods}")

    max_num = 49
    pick_count = 6
    start_idx = len(all_draws) - test_periods

    # 測試策略
    strategies = {
        # 單注方法
        '1注 Cluster Pivot': lambda h: [cluster_pivot_base(h, max_num, pick_count)],
        '1注 Triplet': lambda h: [triplet_predict(h, max_num, pick_count)],
        '1注 Temporal': lambda h: [temporal_cooccur_predict(h, max_num, pick_count)],
        '1注 Gap Comp': lambda h: [gap_compensation_predict(h, max_num, pick_count)],
        '1注 Graph Community': lambda h: [graph_community_predict(h, max_num, pick_count)],
        '1注 Anti-Cooccur': lambda h: [anti_cooccur_predict(h, max_num, pick_count)],
        # 多注組合
        '4注 Orthogonal': lambda h: orthogonal_4bet(h, max_num, pick_count),
        '5注 Hybrid': lambda h: hybrid_5bet(h, max_num, pick_count),
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
    rand4 = test_random(4)
    rand5 = test_random(5)

    print(f"\n隨機 1 注: {rand1:.2f}%")
    print(f"隨機 4 注: {rand4:.2f}%")
    print(f"隨機 5 注: {rand5:.2f}%")

    print("\n" + "=" * 80)
    print("📊 策略 vs 隨機")
    print("=" * 80)

    for name, r in sorted(results.items(), key=lambda x: -x[1]['m3']):
        total = r['total']
        rate = r['m3'] / total * 100 if total > 0 else 0

        if '1注' in name:
            rand = rand1
        elif '4注' in name:
            rand = rand4
        else:
            rand = rand5

        diff = rate - rand
        status = "✅" if diff > 0 else "❌"
        print(f"{name}: {rate:.2f}% vs 隨機 {rand:.2f}% ({diff:+.2f}%) {status}")

    return results


if __name__ == '__main__':
    run_backtest(test_periods=150)
