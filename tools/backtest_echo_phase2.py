#!/usr/bin/env python3
"""
Echo-Aware Phase 2 嚴格回測

比較:
1. 原始偏差互補 2注 (baseline, Edge +0.90%)
2. Phase 1 Echo-Aware 2注/3注 (固定 echo_weight=0.25)
3. Phase 2 自適應 Echo 2注/3注 (動態 echo_weight)
4. 隨機 N 注 (基準線)

驗證標準:
- 1000期滾動回測
- 10種子穩定性驗證 (隨機基準用)
- Edge vs 隨機基準
- 無數據洩漏: 每期只用該期之前的數據
"""

import sqlite3
import json
import sys
import math
import random
import argparse
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'lottery_api'))
sys.path.insert(0, str(PROJECT_ROOT / 'tools'))

MAX_NUM = 49
PICK = 6


def load_history(lottery_type='BIG_LOTTO'):
    db_path = PROJECT_ROOT / 'lottery_api' / 'data' / 'lottery_v2.db'
    if not db_path.exists():
        db_path = PROJECT_ROOT / 'lottery_api' / 'data' / 'lottery.db'
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT draw, date, numbers, special FROM draws WHERE lottery_type=? ORDER BY date ASC",
        (lottery_type,)
    )
    draws = []
    for row in cursor.fetchall():
        nums = json.loads(row[2]) if row[2] else []
        draws.append({'draw': row[0], 'date': row[1], 'numbers': sorted(nums), 'special': row[3] or 0})
    conn.close()
    return draws


# ============================================================
# 策略函數 (內聯，避免滾動回測中的 import 問題)
# ============================================================

def echo_detector(history, max_lag=5):
    if len(history) < max_lag + 1:
        return {}
    latest = set(history[-1]['numbers'])
    echo_scores = Counter()
    for lag in range(1, max_lag + 1):
        past = set(history[-(lag + 1)]['numbers'])
        overlap = latest & past
        overlap_count = len(overlap)
        if overlap_count >= 2:
            weight = overlap_count / PICK * (1.0 / lag)
            for n in overlap:
                echo_scores[n] += weight * 0.5
            for n in past - latest:
                echo_scores[n] += weight * 1.0
    if echo_scores:
        mx = max(echo_scores.values())
        if mx > 0:
            for n in echo_scores:
                echo_scores[n] /= mx
    return dict(echo_scores)


def continuous_temperature(history, window=50):
    recent = history[-window:] if len(history) > window else history
    short_window = min(20, len(recent))
    short_recent = history[-short_window:] if len(history) > short_window else history
    freq_long = Counter()
    for d in recent:
        for n in d['numbers']:
            freq_long[n] += 1
    freq_short = Counter()
    for d in short_recent:
        for n in d['numbers']:
            freq_short[n] += 1
    gaps = {}
    for n in range(1, MAX_NUM + 1):
        gap = 0
        for d in reversed(history):
            if n in d['numbers']:
                break
            gap += 1
        gaps[n] = gap
    temperatures = {}
    freq_values = [freq_long.get(n, 0) for n in range(1, MAX_NUM + 1)]
    freq_sorted = sorted(freq_values)
    for n in range(1, MAX_NUM + 1):
        f = freq_long.get(n, 0)
        rank = sum(1 for v in freq_sorted if v <= f) / MAX_NUM
        median_gap = MAX_NUM / PICK
        gap_comp = math.exp(-gaps[n] / median_gap)
        expected_short = short_window * PICK / MAX_NUM
        expected_long = len(recent) * PICK / MAX_NUM
        short_ratio = freq_short.get(n, 0) / max(expected_short, 0.1)
        long_ratio = f / max(expected_long, 0.1)
        trend_comp = min(1.0, max(0.0, 0.5 + (short_ratio - long_ratio) * 0.5))
        temperatures[n] = 0.40 * rank + 0.30 * gap_comp + 0.30 * trend_comp
    return temperatures


def structural_score(bet):
    s = sum(bet)
    odd = sum(1 for n in bet if n % 2 == 1)
    zones = [0, 0, 0]
    for n in bet:
        if n <= 16: zones[0] += 1
        elif n <= 33: zones[1] += 1
        else: zones[2] += 1
    consec = sum(1 for i in range(len(bet) - 1) if bet[i + 1] - bet[i] == 1)
    spread = bet[-1] - bet[0]
    score = 0
    if 100 <= s <= 200: score += 2
    if 120 <= s <= 180: score += 2
    if 2 <= odd <= 4: score += 2
    if all(z >= 1 for z in zones): score += 2
    if consec <= 1: score += 1
    if spread >= 25: score += 1
    return score


def echo_signal_strength(history, max_lag=5):
    if len(history) < max_lag + 1:
        return 0.0
    latest = set(history[-1]['numbers'])
    total_score = 0.0
    max_possible = 0.0
    for lag in range(1, max_lag + 1):
        past = set(history[-(lag + 1)]['numbers'])
        overlap = len(latest & past)
        weight = 1.0 / lag
        max_possible += PICK * weight
        total_score += overlap * weight
    if max_possible == 0:
        return 0.0
    return min(1.0, total_score / max_possible)


def rolling_echo_accuracy(history, lookback=50, echo_threshold=0.3):
    if len(history) < lookback + 10:
        return 0.5
    hits = 0
    events = 0
    start = max(10, len(history) - lookback)
    for idx in range(start, len(history)):
        train = history[:idx]
        actual = set(history[idx]['numbers'])
        echoes = echo_detector(train, max_lag=5)
        echo_nums = {n for n, s in echoes.items() if s > echo_threshold}
        if echo_nums:
            events += 1
            if len(echo_nums & actual) > 0:
                hits += 1
    if events == 0:
        return 0.5
    return hits / events


def adaptive_echo_weight(history, base_weight=0.25, lookback=50):
    strength = echo_signal_strength(history)
    accuracy = rolling_echo_accuracy(history, lookback)
    strength_factor = min(1.5, max(0.3, 0.3 + strength * 2.4))
    accuracy_factor = min(1.5, max(0.3, 0.3 + accuracy * 1.7))
    weight = base_weight * strength_factor * accuracy_factor
    weight = min(0.50, max(0.05, weight))
    return weight


# ============================================================
# 原始偏差互補 (baseline)
# ============================================================
def original_deviation_2bet(history, window=50):
    recent = history[-window:] if len(history) > window else history
    total = len(recent)
    expected = total * PICK / MAX_NUM
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    hot, cold = [], []
    for n in range(1, MAX_NUM + 1):
        f = freq.get(n, 0)
        dev = f - expected
        if dev > 1: hot.append((n, dev))
        elif dev < -1: cold.append((n, abs(dev)))
    hot.sort(key=lambda x: x[1], reverse=True)
    cold.sort(key=lambda x: x[1], reverse=True)
    bet1 = [n for n, _ in hot[:PICK]]
    used = set(bet1)
    if len(bet1) < PICK:
        mid = sorted(range(1, MAX_NUM + 1), key=lambda n: abs(freq.get(n, 0) - expected))
        for n in mid:
            if n not in used and len(bet1) < PICK:
                bet1.append(n); used.add(n)
    bet2 = []
    for n, _ in cold:
        if n not in used and len(bet2) < PICK:
            bet2.append(n); used.add(n)
    if len(bet2) < PICK:
        for n in range(1, MAX_NUM + 1):
            if n not in used and len(bet2) < PICK:
                bet2.append(n); used.add(n)
    return [sorted(bet1[:PICK]), sorted(bet2[:PICK])]


# ============================================================
# Phase 1 固定權重
# ============================================================
def phase1_echo_2bet(history, window=50):
    return _echo_nbets(history, window, echo_weight=0.25, n_bets=2)

def phase1_echo_3bet(history, window=50):
    return _echo_nbets(history, window, echo_weight=0.25, n_bets=3)


# ============================================================
# Phase 2 自適應權重
# ============================================================
def phase2_echo_2bet(history, window=50):
    ew = adaptive_echo_weight(history)
    return _echo_nbets(history, window, echo_weight=ew, n_bets=2)

def phase2_echo_3bet(history, window=50):
    ew = adaptive_echo_weight(history)
    return _echo_nbets(history, window, echo_weight=ew, n_bets=3)


def _echo_nbets(history, window, echo_weight, n_bets):
    """通用 Echo-Aware N注生成"""
    temps = continuous_temperature(history, window)
    echoes = echo_detector(history, max_lag=5)

    hot_scores = {}
    cold_scores = {}
    for n in range(1, MAX_NUM + 1):
        t = temps.get(n, 0.5)
        e = echoes.get(n, 0.0)
        hot_scores[n] = t * (1 - echo_weight) + e * echo_weight
        cold_scores[n] = (1 - t) * (1 - echo_weight) + e * echo_weight

    hot_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: hot_scores[n], reverse=True)
    cold_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: cold_scores[n], reverse=True)

    bet1 = sorted(hot_ranked[:PICK])
    used = set(bet1)

    bet2 = []
    for n in cold_ranked:
        if n not in used and len(bet2) < PICK:
            bet2.append(n)
    bet2 = sorted(bet2[:PICK])

    if n_bets == 2:
        return [bet1, bet2]

    used.update(bet2)

    # 注3: Echo+Warm
    echo_share = min(0.7, echo_weight * 2)
    bet3_scores = {}
    for n in range(1, MAX_NUM + 1):
        if n in used:
            continue
        t = temps.get(n, 0.5)
        e = echoes.get(n, 0.0)
        warm_proximity = 1.0 - abs(t - 0.5) * 2.0
        bet3_scores[n] = e * echo_share + warm_proximity * (1 - echo_share)

    bet3_ranked = sorted(bet3_scores.keys(), key=lambda n: bet3_scores[n], reverse=True)
    candidates = sorted(bet3_ranked[:12])

    if len(candidates) < PICK:
        candidates = sorted([n for n in range(1, MAX_NUM + 1) if n not in used])

    from itertools import combinations
    best_bet3 = None
    best_score = -1
    if len(candidates) >= PICK:
        for combo in combinations(candidates, PICK):
            bet = sorted(combo)
            sc = structural_score(bet)
            avg_s = sum(bet3_scores.get(n, 0) for n in bet) / PICK
            composite = sc + avg_s * 0.1
            if composite > best_score:
                best_score = composite
                best_bet3 = bet

    if best_bet3 is None:
        best_bet3 = sorted(candidates[:PICK])

    return [bet1, bet2, best_bet3]


# ============================================================
# 隨機基準
# ============================================================
def random_nbets(n_bets, seed):
    rng = random.Random(seed)
    bets = []
    used = set()
    for _ in range(n_bets):
        available = [n for n in range(1, MAX_NUM + 1) if n not in used]
        if len(available) < PICK:
            available = list(range(1, MAX_NUM + 1))
            used = set()
        bet = sorted(rng.sample(available, PICK))
        bets.append(bet)
        used.update(bet)
    return bets


# ============================================================
# 回測引擎
# ============================================================
def evaluate_bets(bets, actual_numbers):
    actual = set(actual_numbers)
    return max(len(set(b) & actual) for b in bets)


def run_backtest(all_history, strategy_fn, test_periods, n_bets=2, collect_weights=False):
    total = len(all_history)
    start_idx = max(100, total - test_periods)  # Phase 2 需要更多歷史算 rolling accuracy

    m3_plus = 0
    tested = 0
    match_dist = Counter()
    weights_log = []

    for idx in range(start_idx, total):
        train = all_history[:idx]
        actual = all_history[idx]['numbers']

        if len(train) < 100:
            continue

        try:
            bets = strategy_fn(train)
        except Exception:
            continue

        if collect_weights:
            ew = adaptive_echo_weight(train)
            weights_log.append(ew)

        best_match = evaluate_bets(bets, actual)
        match_dist[best_match] += 1
        if best_match >= 3:
            m3_plus += 1
        tested += 1

    if tested == 0:
        return {'m3_rate': 0, 'tested': 0, 'dist': {}, 'weights': []}

    result = {
        'm3_rate': m3_plus / tested * 100,
        'tested': tested,
        'm3_count': m3_plus,
        'dist': dict(match_dist),
    }
    if collect_weights:
        result['weights'] = weights_log
    return result


def run_random_baseline(all_history, test_periods, n_bets, seeds):
    total = len(all_history)
    start_idx = max(100, total - test_periods)
    m3_rates = []

    for seed in seeds:
        m3 = 0
        tested = 0
        rng_base = seed
        for idx in range(start_idx, total):
            actual = all_history[idx]['numbers']
            bets = random_nbets(n_bets, rng_base + idx)
            best = evaluate_bets(bets, actual)
            if best >= 3:
                m3 += 1
            tested += 1
        if tested > 0:
            m3_rates.append(m3 / tested * 100)

    avg = sum(m3_rates) / len(m3_rates) if m3_rates else 0
    std = (sum((r - avg) ** 2 for r in m3_rates) / len(m3_rates)) ** 0.5 if m3_rates else 0
    return {'avg_m3': avg, 'std_m3': std, 'tested': tested}


def main():
    parser = argparse.ArgumentParser(description='Echo Phase 2 回測')
    parser.add_argument('--periods', type=int, default=1000)
    parser.add_argument('--seeds', type=int, default=10)
    args = parser.parse_args()

    seeds = [42, 123, 456, 789, 1024, 2048, 3333, 5555, 7777, 9999][:args.seeds]
    all_history = load_history('BIG_LOTTO')
    if not all_history:
        print("錯誤: 無法載入數據")
        sys.exit(1)

    print(f"{'='*75}")
    print(f"  Echo-Aware Phase 2 嚴格回測")
    print(f"  數據: {len(all_history)} 期 | 回測: {args.periods} 期 | 種子: {args.seeds}")
    print(f"{'='*75}")

    # ========================
    # 2注比較
    # ========================
    print(f"\n{'─'*75}")
    print(f"  [2注策略比較]")
    print(f"{'─'*75}")

    print(f"\n  隨機 2注 基準...", end='', flush=True)
    bl_2 = run_random_baseline(all_history, args.periods, 2, seeds)
    print(f" M3+: {bl_2['avg_m3']:.2f}% ± {bl_2['std_m3']:.2f}%")

    print(f"  原始偏差互補 2注...", end='', flush=True)
    orig_2 = run_backtest(all_history, original_deviation_2bet, args.periods, n_bets=2)
    print(f" M3+: {orig_2['m3_rate']:.2f}%")

    print(f"  Phase 1 Echo 2注 (固定0.25)...", end='', flush=True)
    p1_2 = run_backtest(all_history, phase1_echo_2bet, args.periods, n_bets=2)
    print(f" M3+: {p1_2['m3_rate']:.2f}%")

    print(f"  Phase 2 Echo 2注 (自適應)...", end='', flush=True)
    p2_2 = run_backtest(all_history, phase2_echo_2bet, args.periods, n_bets=2, collect_weights=True)
    print(f" M3+: {p2_2['m3_rate']:.2f}%")

    # 2注 edge 表
    edge_orig_2 = orig_2['m3_rate'] - bl_2['avg_m3']
    edge_p1_2 = p1_2['m3_rate'] - bl_2['avg_m3']
    edge_p2_2 = p2_2['m3_rate'] - bl_2['avg_m3']

    print(f"\n  {'策略':<32} {'M3+':<10} {'Edge':<10} {'vs原始':<10}")
    print(f"  {'─'*60}")
    print(f"  {'隨機 2注 (基準)':<32} {bl_2['avg_m3']:>6.2f}%    {'─':<10} {'─':<10}")
    print(f"  {'原始偏差互補':<32} {orig_2['m3_rate']:>6.2f}%    {edge_orig_2:>+6.2f}%    {'─':<10}")
    print(f"  {'Phase 1 固定 0.25':<32} {p1_2['m3_rate']:>6.2f}%    {edge_p1_2:>+6.2f}%    {p1_2['m3_rate']-orig_2['m3_rate']:>+6.2f}%")
    print(f"  {'Phase 2 自適應':<28} {p2_2['m3_rate']:>6.2f}%    {edge_p2_2:>+6.2f}%    {p2_2['m3_rate']-orig_2['m3_rate']:>+6.2f}%")

    # 2注 權重分佈
    if p2_2.get('weights'):
        ws = p2_2['weights']
        print(f"\n  Phase 2 自適應權重分佈:")
        print(f"    min={min(ws):.3f}  avg={sum(ws)/len(ws):.3f}  max={max(ws):.3f}")
        # 分桶
        buckets = Counter()
        for w in ws:
            if w < 0.10: buckets['<0.10'] += 1
            elif w < 0.20: buckets['0.10-0.20'] += 1
            elif w < 0.30: buckets['0.20-0.30'] += 1
            elif w < 0.40: buckets['0.30-0.40'] += 1
            else: buckets['0.40+'] += 1
        for k in ['<0.10', '0.10-0.20', '0.20-0.30', '0.30-0.40', '0.40+']:
            cnt = buckets.get(k, 0)
            pct = cnt / len(ws) * 100
            bar = '█' * int(pct / 2)
            print(f"    {k:>10}: {cnt:>4d} ({pct:>5.1f}%) {bar}")

    # ========================
    # 3注比較
    # ========================
    print(f"\n{'─'*75}")
    print(f"  [3注策略比較]")
    print(f"{'─'*75}")

    print(f"\n  隨機 3注 基準...", end='', flush=True)
    bl_3 = run_random_baseline(all_history, args.periods, 3, seeds)
    print(f" M3+: {bl_3['avg_m3']:.2f}% ± {bl_3['std_m3']:.2f}%")

    print(f"  Phase 1 Echo 3注 (固定0.25)...", end='', flush=True)
    p1_3 = run_backtest(all_history, phase1_echo_3bet, args.periods, n_bets=3)
    print(f" M3+: {p1_3['m3_rate']:.2f}%")

    print(f"  Phase 2 Echo 3注 (自適應)...", end='', flush=True)
    p2_3 = run_backtest(all_history, phase2_echo_3bet, args.periods, n_bets=3, collect_weights=True)
    print(f" M3+: {p2_3['m3_rate']:.2f}%")

    edge_p1_3 = p1_3['m3_rate'] - bl_3['avg_m3']
    edge_p2_3 = p2_3['m3_rate'] - bl_3['avg_m3']

    print(f"\n  {'策略':<32} {'M3+':<10} {'Edge':<10} {'vs Phase1':<10}")
    print(f"  {'─'*60}")
    print(f"  {'隨機 3注 (基準)':<32} {bl_3['avg_m3']:>6.2f}%    {'─':<10} {'─':<10}")
    print(f"  {'Phase 1 固定 0.25':<32} {p1_3['m3_rate']:>6.2f}%    {edge_p1_3:>+6.2f}%    {'─':<10}")
    print(f"  {'Phase 2 自適應':<28} {p2_3['m3_rate']:>6.2f}%    {edge_p2_3:>+6.2f}%    {p2_3['m3_rate']-p1_3['m3_rate']:>+6.2f}%")

    # 3注匹配分佈
    print(f"\n  3注匹配分佈:")
    print(f"  {'Match':<8} {'Phase 1':<15} {'Phase 2':<15}")
    t1, t2 = p1_3['tested'], p2_3['tested']
    for m in range(7):
        c1 = p1_3['dist'].get(m, 0)
        c2 = p2_3['dist'].get(m, 0)
        if t1 > 0 and t2 > 0:
            print(f"  M{m}       {c1:>4d} ({c1/t1*100:>5.1f}%)    {c2:>4d} ({c2/t2*100:>5.1f}%)")

    # ========================
    # 總結
    # ========================
    print(f"\n{'='*75}")
    print(f"  Phase 2 回測總結")
    print(f"{'='*75}")

    print(f"\n  2注:")
    print(f"    原始偏差互補:    Edge {edge_orig_2:>+.2f}%")
    print(f"    Phase 1 (固定):  Edge {edge_p1_2:>+.2f}%")
    print(f"    Phase 2 (自適應): Edge {edge_p2_2:>+.2f}%")

    best_2 = max([(edge_orig_2, '原始'), (edge_p1_2, 'P1'), (edge_p2_2, 'P2')], key=lambda x: x[0])
    print(f"    最佳: {best_2[1]} ({best_2[0]:+.2f}%)")

    print(f"\n  3注:")
    print(f"    Phase 1 (固定):  Edge {edge_p1_3:>+.2f}%")
    print(f"    Phase 2 (自適應): Edge {edge_p2_3:>+.2f}%")

    improvement_3 = p2_3['m3_rate'] - p1_3['m3_rate']
    if improvement_3 > 0:
        print(f"    Phase 2 改進: {improvement_3:>+.2f}% ✓")
    else:
        print(f"    Phase 2 改進: {improvement_3:>+.2f}% (未超越 Phase 1)")

    # 採納建議
    print(f"\n  採納建議:")
    if edge_p2_2 > edge_orig_2 + 0.1:
        print(f"    2注: Phase 2 建議採納")
    else:
        print(f"    2注: 保留原始偏差互補 (Phase 2 無顯著改善)")

    if edge_p2_3 > edge_p1_3 + 0.1:
        print(f"    3注: Phase 2 建議採納 (Edge {edge_p2_3:+.2f}% > P1 {edge_p1_3:+.2f}%)")
    elif edge_p2_3 > edge_p1_3:
        print(f"    3注: Phase 2 微幅改善 ({improvement_3:+.2f}%), 可考慮採納")
    else:
        print(f"    3注: 保留 Phase 1 (Phase 2 未改善)")

    print()


if __name__ == '__main__':
    main()
