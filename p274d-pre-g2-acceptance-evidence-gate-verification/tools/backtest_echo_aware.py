#!/usr/bin/env python3
"""
Echo-Aware 策略嚴格回測

驗證標準 (來自 CLAUDE.md):
- 1000期滾動回測
- 10種子穩定性驗證
- Edge vs 隨機基準 (非絕對勝率)
- 無數據洩漏: 每期只用該期之前的數據

比較對象:
1. 原始偏差互補 2注 (baseline: Edge +0.91%)
2. Echo-Aware 偏差互補 2注 (新)
3. 原始混合 3注 (baseline: Edge +1.01%)
4. Echo-Aware 混合 3注 (新)
5. 隨機 N 注 (基準)

使用方式:
    python3 tools/backtest_echo_aware.py
    python3 tools/backtest_echo_aware.py --periods 500    # 快速測試
    python3 tools/backtest_echo_aware.py --seeds 3        # 快速種子測試
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
    """載入歷史數據"""
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
# 原始偏差互補 (baseline, from predict_biglotto_deviation_2bet.py)
# ============================================================
def original_deviation_2bet(history, window=50):
    """原始偏差互補 2注 (確定性)"""
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
        if dev > 1:
            hot.append((n, dev))
        elif dev < -1:
            cold.append((n, abs(dev)))

    hot.sort(key=lambda x: x[1], reverse=True)
    cold.sort(key=lambda x: x[1], reverse=True)

    bet1 = [n for n, _ in hot[:PICK]]
    used = set(bet1)

    if len(bet1) < PICK:
        mid = sorted(range(1, MAX_NUM + 1), key=lambda n: abs(freq.get(n, 0) - expected))
        for n in mid:
            if n not in used and len(bet1) < PICK:
                bet1.append(n)
                used.add(n)

    bet2 = []
    for n, _ in cold:
        if n not in used and len(bet2) < PICK:
            bet2.append(n)
            used.add(n)

    if len(bet2) < PICK:
        for n in range(1, MAX_NUM + 1):
            if n not in used and len(bet2) < PICK:
                bet2.append(n)
                used.add(n)

    return [sorted(bet1[:PICK]), sorted(bet2[:PICK])]


# ============================================================
# 原始混合 3注 (baseline, from predict_biglotto_mixed_3bet.py)
# ============================================================
def structural_score(bet):
    """評估結構合理性"""
    s = sum(bet)
    odd = sum(1 for n in bet if n % 2 == 1)
    zones = [0, 0, 0]
    for n in bet:
        if n <= 16:
            zones[0] += 1
        elif n <= 33:
            zones[1] += 1
        else:
            zones[2] += 1
    consec = sum(1 for i in range(len(bet) - 1) if bet[i + 1] - bet[i] == 1)
    spread = bet[-1] - bet[0]

    score = 0
    if 100 <= s <= 200:
        score += 2
    if 120 <= s <= 180:
        score += 2
    if 2 <= odd <= 4:
        score += 2
    if all(z >= 1 for z in zones):
        score += 2
    if consec <= 1:
        score += 1
    if spread >= 25:
        score += 1
    return score


def original_mixed_3bet(history, window=50, seed=42):
    """原始混合 3注 (注3有隨機性)"""
    bets_2 = original_deviation_2bet(history, window)
    bet1, bet2 = bets_2
    used = set(bet1) | set(bet2)

    # 注3: 結構過濾
    freq_100 = Counter()
    recent_100 = history[-100:] if len(history) > 100 else history
    for d in recent_100:
        for n in d['numbers']:
            freq_100[n] += 1
    ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: freq_100.get(n, 0), reverse=True)
    available = [n for n in ranked if n not in used][:24]

    if len(available) < PICK:
        available = [n for n in range(1, MAX_NUM + 1) if n not in used]

    rng = random.Random(seed + len(history))
    best_bet = None
    best_score = -1

    for _ in range(200):
        if len(available) < PICK:
            break
        bet = sorted(rng.sample(available, PICK))
        sc = structural_score(bet)
        if sc > best_score:
            best_score = sc
            best_bet = bet

    if best_bet is None:
        best_bet = sorted(available[:PICK])

    return [bet1, bet2, best_bet]


# ============================================================
# Echo-Aware 新策略
# ============================================================
def echo_detector(history, max_lag=5):
    """Echo Detector"""
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
            echo_candidates = past - latest
            for n in echo_candidates:
                echo_scores[n] += weight * 1.0

    if echo_scores:
        max_score = max(echo_scores.values())
        if max_score > 0:
            for n in echo_scores:
                echo_scores[n] /= max_score

    return dict(echo_scores)


def continuous_temperature(history, window=50):
    """連續溫度評分"""
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
        freq_component = rank

        median_gap = MAX_NUM / PICK
        gap_component = math.exp(-gaps[n] / median_gap)

        expected_short = short_window * PICK / MAX_NUM
        expected_long = len(recent) * PICK / MAX_NUM
        short_ratio = freq_short.get(n, 0) / max(expected_short, 0.1)
        long_ratio = f / max(expected_long, 0.1)
        trend_component = min(1.0, max(0.0, 0.5 + (short_ratio - long_ratio) * 0.5))

        temp = (0.40 * freq_component +
                0.30 * gap_component +
                0.30 * trend_component)
        temperatures[n] = temp

    return temperatures


def echo_aware_2bet(history, window=50, echo_weight=0.25):
    """Echo-Aware 偏差互補 2注"""
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

    return [bet1, bet2]


def echo_aware_3bet(history, window=50, echo_weight=0.25):
    """Echo-Aware 混合 3注"""
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
    used.update(bet2)

    # 注3: Echo + Warm
    bet3_scores = {}
    for n in range(1, MAX_NUM + 1):
        if n in used:
            continue
        t = temps.get(n, 0.5)
        e = echoes.get(n, 0.0)
        warm_proximity = 1.0 - abs(t - 0.5) * 2.0
        bet3_scores[n] = e * 0.5 + warm_proximity * 0.5

    bet3_ranked = sorted(bet3_scores.keys(), key=lambda n: bet3_scores[n], reverse=True)
    candidates = sorted(bet3_ranked[:12])

    if len(candidates) < PICK:
        candidates = sorted([n for n in range(1, MAX_NUM + 1) if n not in used])

    # 確定性結構選擇
    from itertools import combinations
    best_bet3 = None
    best_score = -1

    if len(candidates) >= PICK:
        for combo in combinations(candidates, PICK):
            bet = sorted(combo)
            sc = structural_score(bet)
            avg_bet3_score = sum(bet3_scores.get(n, 0) for n in bet) / PICK
            composite = sc + avg_bet3_score * 0.1
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
    """產生 n 注隨機號碼"""
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
    """評估 N 注的最佳匹配數"""
    actual = set(actual_numbers)
    best_match = 0
    for bet in bets:
        match = len(set(bet) & actual)
        best_match = max(best_match, match)
    return best_match


def run_backtest(all_history, strategy_fn, test_periods, seed=42, n_bets=2):
    """
    執行滾動回測

    無數據洩漏: 每期只使用該期之前的數據
    """
    total = len(all_history)
    start_idx = max(50, total - test_periods)  # 至少需要 50 期訓練數據

    m3_plus = 0
    m4_plus = 0
    tested = 0
    match_dist = Counter()

    for idx in range(start_idx, total):
        train_history = all_history[:idx]
        actual = all_history[idx]['numbers']

        if len(train_history) < 50:
            continue

        try:
            if strategy_fn.__name__ == 'random_nbets':
                bets = strategy_fn(n_bets, seed + idx)
            elif 'seed' in strategy_fn.__code__.co_varnames:
                bets = strategy_fn(train_history, seed=seed)
            else:
                bets = strategy_fn(train_history)
        except Exception:
            continue

        best_match = evaluate_bets(bets, actual)
        match_dist[best_match] += 1

        if best_match >= 3:
            m3_plus += 1
        if best_match >= 4:
            m4_plus += 1
        tested += 1

    if tested == 0:
        return {'m3_rate': 0, 'm4_rate': 0, 'tested': 0, 'dist': {}}

    return {
        'm3_rate': m3_plus / tested * 100,
        'm4_rate': m4_plus / tested * 100,
        'tested': tested,
        'm3_count': m3_plus,
        'm4_count': m4_plus,
        'dist': dict(match_dist),
    }


def run_multi_seed_backtest(all_history, strategy_fn, test_periods, seeds, n_bets=2):
    """多種子回測"""
    results = []
    for seed in seeds:
        r = run_backtest(all_history, strategy_fn, test_periods, seed=seed, n_bets=n_bets)
        results.append(r)

    m3_rates = [r['m3_rate'] for r in results]
    avg_m3 = sum(m3_rates) / len(m3_rates)
    std_m3 = (sum((r - avg_m3) ** 2 for r in m3_rates) / len(m3_rates)) ** 0.5
    min_m3 = min(m3_rates)
    max_m3 = max(m3_rates)

    return {
        'avg_m3': avg_m3,
        'std_m3': std_m3,
        'min_m3': min_m3,
        'max_m3': max_m3,
        'all_m3': m3_rates,
        'tested': results[0]['tested'],
        'detail': results,
    }


def main():
    parser = argparse.ArgumentParser(description='Echo-Aware 策略回測')
    parser.add_argument('--periods', type=int, default=1000, help='回測期數 (default: 1000)')
    parser.add_argument('--seeds', type=int, default=10, help='種子數量 (default: 10)')
    args = parser.parse_args()

    test_periods = args.periods
    num_seeds = args.seeds
    seeds = [42, 123, 456, 789, 1024, 2048, 3333, 5555, 7777, 9999][:num_seeds]

    all_history = load_history('BIG_LOTTO')
    if not all_history:
        print("錯誤: 無法載入數據")
        sys.exit(1)

    print(f"{'='*75}")
    print(f"  Echo-Aware 策略嚴格回測")
    print(f"  數據: {len(all_history)} 期 | 回測: {test_periods} 期 | 種子: {num_seeds} 個")
    print(f"{'='*75}")

    # ========================
    # 2注策略比較
    # ========================
    print(f"\n{'─'*75}")
    print(f"  [2注策略比較]")
    print(f"{'─'*75}")

    # 2注隨機基準
    print(f"\n  計算 2注隨機基準...", end='', flush=True)
    baseline_2 = run_multi_seed_backtest(
        all_history, lambda h, seed=42: random_nbets(2, seed), test_periods, seeds, n_bets=2
    )
    print(f" M3+: {baseline_2['avg_m3']:.2f}% ± {baseline_2['std_m3']:.2f}%")

    # 原始偏差互補 2注
    print(f"  計算原始偏差互補 2注...", end='', flush=True)
    original_2 = run_backtest(all_history, original_deviation_2bet, test_periods, seed=42, n_bets=2)
    print(f" M3+: {original_2['m3_rate']:.2f}% (確定性)")

    # Echo-Aware 2注
    print(f"  計算 Echo-Aware 2注...", end='', flush=True)
    echo_2 = run_backtest(all_history, echo_aware_2bet, test_periods, seed=42, n_bets=2)
    print(f" M3+: {echo_2['m3_rate']:.2f}% (確定性)")

    # 2注結果表
    edge_orig_2 = original_2['m3_rate'] - baseline_2['avg_m3']
    edge_echo_2 = echo_2['m3_rate'] - baseline_2['avg_m3']
    improvement_2 = echo_2['m3_rate'] - original_2['m3_rate']

    print(f"\n  {'策略':<30} {'M3+ 勝率':<12} {'基準':<12} {'Edge':<12} {'vs原始':<12}")
    print(f"  {'─'*66}")
    print(f"  {'隨機 2注 (基準)':<30} {baseline_2['avg_m3']:>8.2f}%    {'─':>10}    {'─':>10}    {'─':>10}")
    print(f"  {'原始偏差互補 2注':<30} {original_2['m3_rate']:>8.2f}%    {baseline_2['avg_m3']:>8.2f}%    {edge_orig_2:>+8.2f}%    {'─':>10}")
    print(f"  {'Echo-Aware 2注':<24} {echo_2['m3_rate']:>8.2f}%    {baseline_2['avg_m3']:>8.2f}%    {edge_echo_2:>+8.2f}%    {improvement_2:>+8.2f}%")

    # 2注匹配分佈
    print(f"\n  匹配分佈:")
    print(f"  {'Match':<8} {'原始':<15} {'Echo-Aware':<15}")
    for m in range(7):
        o = original_2['dist'].get(m, 0)
        e = echo_2['dist'].get(m, 0)
        tested = original_2['tested']
        if tested > 0:
            print(f"  M{m}       {o:>4d} ({o/tested*100:>5.1f}%)    {e:>4d} ({e/tested*100:>5.1f}%)")

    # ========================
    # 3注策略比較
    # ========================
    print(f"\n{'─'*75}")
    print(f"  [3注策略比較]")
    print(f"{'─'*75}")

    # 3注隨機基準
    print(f"\n  計算 3注隨機基準...", end='', flush=True)
    baseline_3 = run_multi_seed_backtest(
        all_history, lambda h, seed=42: random_nbets(3, seed), test_periods, seeds, n_bets=3
    )
    print(f" M3+: {baseline_3['avg_m3']:.2f}% ± {baseline_3['std_m3']:.2f}%")

    # 原始混合 3注 (多種子)
    print(f"  計算原始混合 3注 (多種子)...", end='', flush=True)
    original_3 = run_multi_seed_backtest(
        all_history, lambda h, seed=42: original_mixed_3bet(h, seed=seed), test_periods, seeds, n_bets=3
    )
    print(f" M3+: {original_3['avg_m3']:.2f}% ± {original_3['std_m3']:.2f}%")

    # Echo-Aware 3注 (確定性)
    print(f"  計算 Echo-Aware 3注...", end='', flush=True)
    echo_3 = run_backtest(all_history, echo_aware_3bet, test_periods, seed=42, n_bets=3)
    print(f" M3+: {echo_3['m3_rate']:.2f}% (確定性)")

    # 3注結果表
    edge_orig_3 = original_3['avg_m3'] - baseline_3['avg_m3']
    edge_echo_3 = echo_3['m3_rate'] - baseline_3['avg_m3']
    improvement_3 = echo_3['m3_rate'] - original_3['avg_m3']

    print(f"\n  {'策略':<30} {'M3+ 勝率':<12} {'基準':<12} {'Edge':<12} {'vs原始':<12}")
    print(f"  {'─'*66}")
    print(f"  {'隨機 3注 (基準)':<30} {baseline_3['avg_m3']:>8.2f}%    {'─':>10}    {'─':>10}    {'─':>10}")
    print(f"  {'原始混合 3注':<30} {original_3['avg_m3']:>8.2f}%    {baseline_3['avg_m3']:>8.2f}%    {edge_orig_3:>+8.2f}%    {'─':>10}")
    print(f"  {'Echo-Aware 3注':<24} {echo_3['m3_rate']:>8.2f}%    {baseline_3['avg_m3']:>8.2f}%    {edge_echo_3:>+8.2f}%    {improvement_3:>+8.2f}%")

    # ========================
    # Echo 統計分析
    # ========================
    print(f"\n{'─'*75}")
    print(f"  [Echo 統計分析]")
    print(f"{'─'*75}")

    # 計算回聲事件在測試期間的統計
    total = len(all_history)
    start_idx = max(50, total - test_periods)
    echo_events = 0
    echo_hits = 0
    echo_hit_improvement = 0

    for idx in range(start_idx, total):
        train = all_history[:idx]
        actual = set(all_history[idx]['numbers'])

        echoes = echo_detector(train, max_lag=5)
        echo_nums = {n for n, s in echoes.items() if s > 0.3}

        if echo_nums:
            echo_events += 1
            hits = len(echo_nums & actual)
            if hits > 0:
                echo_hits += 1

    tested = total - start_idx
    print(f"  回聲事件數: {echo_events}/{tested} ({echo_events/tested*100:.1f}%)")
    if echo_events > 0:
        print(f"  回聲命中率: {echo_hits}/{echo_events} ({echo_hits/echo_events*100:.1f}%)")

    # ========================
    # 總結
    # ========================
    print(f"\n{'='*75}")
    print(f"  回測總結")
    print(f"{'='*75}")

    print(f"\n  2注策略:")
    print(f"    原始偏差互補: M3+ {original_2['m3_rate']:.2f}%, Edge {edge_orig_2:+.2f}%")
    print(f"    Echo-Aware:    M3+ {echo_2['m3_rate']:.2f}%, Edge {edge_echo_2:+.2f}%")
    if improvement_2 > 0:
        print(f"    改進: {improvement_2:+.2f}% ✓")
    else:
        print(f"    改進: {improvement_2:+.2f}% (未超越原始)")

    print(f"\n  3注策略:")
    print(f"    原始混合 3注:  M3+ {original_3['avg_m3']:.2f}% ± {original_3['std_m3']:.2f}%, Edge {edge_orig_3:+.2f}%")
    print(f"    Echo-Aware 3注: M3+ {echo_3['m3_rate']:.2f}%, Edge {edge_echo_3:+.2f}%")
    if improvement_3 > 0:
        print(f"    改進: {improvement_3:+.2f}% ✓")
    else:
        print(f"    改進: {improvement_3:+.2f}% (未超越原始)")

    # 採納建議
    print(f"\n  採納建議:")
    if edge_echo_2 > edge_orig_2 and edge_echo_2 > 0:
        print(f"    2注: Echo-Aware 建議採納 (Edge {edge_echo_2:+.2f}% > 原始 {edge_orig_2:+.2f}%)")
    elif edge_echo_2 > 0:
        print(f"    2注: Echo-Aware 有正 Edge 但未超越原始，建議保留原始策略")
    else:
        print(f"    2注: Echo-Aware Edge 為負，不建議採納")

    if edge_echo_3 > edge_orig_3 and edge_echo_3 > 0:
        print(f"    3注: Echo-Aware 建議採納 (Edge {edge_echo_3:+.2f}% > 原始 {edge_orig_3:+.2f}%)")
    elif edge_echo_3 > 0:
        print(f"    3注: Echo-Aware 有正 Edge 但未超越原始，建議保留原始策略")
    else:
        print(f"    3注: Echo-Aware Edge 為負，不建議採納")

    print()


if __name__ == '__main__':
    main()
