#!/usr/bin/env python3
"""
威力彩 P0+P1 升級版回測驗證
============================
P0: Lag-2 回聲加分機制 (偏差互補 2注升級版)
P1: 灰色地帶取樣器 (混合策略 3注升級版)

適配威力彩規則: 1-38 選 6 (主號), 1-8 選 1 (特別號)

回測 150/500/1000/1500 期 + 10 種子穩定性測試
對比原版 vs 升級版 + 正確 N 注隨機基準

用法:
    python3 tools/backtest_p0p1_power.py
    python3 tools/backtest_p0p1_power.py --periods 1000
    python3 tools/backtest_p0p1_power.py --all
    python3 tools/backtest_p0p1_power.py --sensitivity
"""
import sqlite3
import json
import sys
import os
import random
import argparse
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'lottery_api'))

# 威力彩規則: 1-38 選 6
MAX_NUM = 38
PICK = 6

# 正確的 N 注隨機基準 (威力彩 1-38 選 6)
# P(1注 M3+) = 3.87%
BASELINE_1BET = 0.0387
BASELINES = {
    1: 3.87,
    2: 7.59,
    3: 11.17,
    4: 14.60,
    7: 24.14,
}


def load_history():
    """載入威力彩歷史數據 (舊→新排序)"""
    db_path = PROJECT_ROOT / 'lottery_api' / 'data' / 'lottery_v2.db'
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT draw, date, numbers, special FROM draws WHERE lottery_type=? ORDER BY date ASC",
        ('POWER_LOTTO',)
    )
    draws = []
    for row in cursor.fetchall():
        nums = json.loads(row[2]) if row[2] else []
        draws.append({
            'draw': row[0], 'date': row[1],
            'numbers': nums, 'special': row[3] or 0
        })
    conn.close()
    return draws


# ========== 原版策略 (適配威力彩) ==========

def deviation_complement_2bet_original(history, window=50):
    """原版偏差互補 2注 (無 Echo 加分)"""
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


def structural_score(bet):
    """結構分數 (適配威力彩 1-38)"""
    s = sum(bet)
    odd = sum(1 for n in bet if n % 2 == 1)
    # 三區間: 1-12, 13-25, 26-38
    zones = [0, 0, 0]
    for n in bet:
        if n <= 12:
            zones[0] += 1
        elif n <= 25:
            zones[1] += 1
        else:
            zones[2] += 1
    consec = sum(1 for i in range(len(bet) - 1) if bet[i + 1] - bet[i] == 1)
    spread = bet[-1] - bet[0]
    score = 0
    # 威力彩和值期望: 38*7/2 ≈ 117 (理論中位)
    if 80 <= s <= 155:
        score += 2
    if 95 <= s <= 140:
        score += 2
    if 2 <= odd <= 4:
        score += 2
    if all(z >= 1 for z in zones):
        score += 2
    if consec <= 1:
        score += 1
    if spread >= 20:
        score += 1
    return score


def mixed_3bet_original(history, window=50, sample_attempts=200, seed=42):
    """原版混合策略 3注 (適配威力彩)"""
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

    # Bet 3: structural filter
    freq_100 = Counter()
    for d in history[-100:]:
        for n in d['numbers']:
            freq_100[n] += 1
    ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: freq_100.get(n, 0), reverse=True)
    available = [n for n in ranked if n not in used][:18]
    if len(available) < PICK:
        available = [n for n in range(1, MAX_NUM + 1) if n not in used]

    rng = random.Random(seed + len(history))
    best_bet, best_score = None, -1
    for _ in range(sample_attempts):
        if len(available) < PICK:
            break
        bet = sorted(rng.sample(available, PICK))
        sc = structural_score(bet)
        if sc > best_score:
            best_score = sc
            best_bet = bet

    if best_bet is None:
        best_bet = sorted(available[:PICK])

    return [sorted(bet1[:PICK]), sorted(bet2[:PICK]), best_bet]


# ========== P0 升級版: Lag-2 回聲加分 (威力彩) ==========

def deviation_complement_2bet_p0(history, window=50, echo_boost=1.5):
    """P0 升級版: 偏差互補 2注 + Lag-2 回聲加分 (威力彩)"""
    recent = history[-window:] if len(history) > window else history
    total = len(recent)
    expected = total * PICK / MAX_NUM

    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1

    scores = {}
    for n in range(1, MAX_NUM + 1):
        f = freq.get(n, 0)
        dev = f - expected
        scores[n] = dev

    # P0: Lag-2 echo boost
    if len(history) >= 3:
        lag2_nums = set(history[-2]['numbers'])
        for n in lag2_nums:
            if n <= MAX_NUM:  # Safety check
                scores[n] += echo_boost

    hot, cold = [], []
    for n in range(1, MAX_NUM + 1):
        s = scores[n]
        if s > 1:
            hot.append((n, s))
        elif s < -1:
            cold.append((n, abs(s)))

    hot.sort(key=lambda x: x[1], reverse=True)
    cold.sort(key=lambda x: x[1], reverse=True)

    bet1 = [n for n, _ in hot[:PICK]]
    used = set(bet1)
    if len(bet1) < PICK:
        mid = sorted(range(1, MAX_NUM + 1), key=lambda n: abs(scores[n]))
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


# ========== P0+P1 升級版 (威力彩) ==========

def mixed_3bet_p0p1(history, window=50, sample_attempts=200, seed=42, echo_boost=1.5):
    """P0+P1 升級版: 3注混合策略 (威力彩)"""
    recent = history[-window:] if len(history) > window else history
    total_w = len(recent)
    expected = total_w * PICK / MAX_NUM

    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1

    scores = {}
    for n in range(1, MAX_NUM + 1):
        f = freq.get(n, 0)
        dev = f - expected
        scores[n] = dev

    if len(history) >= 3:
        lag2_nums = set(history[-2]['numbers'])
        for n in lag2_nums:
            if n <= MAX_NUM:
                scores[n] += echo_boost

    hot, cold = [], []
    for n in range(1, MAX_NUM + 1):
        s = scores[n]
        if s > 1:
            hot.append((n, s))
        elif s < -1:
            cold.append((n, abs(s)))

    hot.sort(key=lambda x: x[1], reverse=True)
    cold.sort(key=lambda x: x[1], reverse=True)

    bet1 = [n for n, _ in hot[:PICK]]
    used = set(bet1)
    if len(bet1) < PICK:
        mid = sorted(range(1, MAX_NUM + 1), key=lambda n: abs(scores[n]))
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

    # P1: Gray Zone Sampler
    raw_freq = Counter()
    for d in recent:
        for n in d['numbers']:
            raw_freq[n] += 1

    gray_zone = []
    for n in range(1, MAX_NUM + 1):
        if n in used:
            continue
        raw_dev = raw_freq.get(n, 0) - expected
        if -1.5 <= raw_dev <= 1.5:
            gap = 0
            for j in range(len(history) - 1, -1, -1):
                if n in history[j]['numbers']:
                    gap = len(history) - 1 - j
                    break
                gap = len(history) - j
            gray_zone.append((n, gap, raw_dev))

    gray_zone.sort(key=lambda x: x[1], reverse=True)
    available = [n for n, _, _ in gray_zone]

    if len(available) < PICK:
        for n in range(1, MAX_NUM + 1):
            if n not in used and n not in available:
                available.append(n)

    rng = random.Random(seed + len(history))
    best_bet, best_score = None, -1

    for _ in range(sample_attempts):
        if len(available) < PICK:
            break
        pool_size = min(len(available), max(PICK + 6, len(available) // 2))
        sample_pool = available[:pool_size]
        if len(sample_pool) < PICK:
            sample_pool = available
        bet = sorted(rng.sample(sample_pool, PICK))
        sc = structural_score(bet)
        if sc > best_score:
            best_score = sc
            best_bet = bet

    if best_bet is None:
        best_bet = sorted(available[:PICK])

    return [sorted(bet1[:PICK]), sorted(bet2[:PICK]), best_bet]


# ========== 回測引擎 ==========

def run_backtest(all_draws, strategy_func, n_bets, test_periods, seed=42):
    """滾動式回測 (主號 M3+)"""
    test_periods = min(test_periods, len(all_draws) - 100)

    m3_count = 0
    per_bet_m3 = [0] * n_bets
    total = 0

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 50:
            continue

        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]

        actual = set(target_draw['numbers'])

        try:
            bets = strategy_func(hist, seed)
            if len(bets) < n_bets:
                continue

            best_match = 0
            for b_idx, bet in enumerate(bets[:n_bets]):
                match = len(set(bet) & actual)
                if match >= 3:
                    per_bet_m3[b_idx] += 1
                best_match = max(best_match, match)

            if best_match >= 3:
                m3_count += 1

            total += 1
        except Exception:
            continue

    if total == 0:
        return None

    m3_rate = m3_count / total * 100
    per_bet_rates = [c / total * 100 for c in per_bet_m3]

    return {
        'm3_count': m3_count,
        'm3_rate': m3_rate,
        'total': total,
        'per_bet_m3': per_bet_m3,
        'per_bet_rates': per_bet_rates,
    }


def run_full_comparison(test_periods, seeds=None):
    """完整對比回測"""
    if seeds is None:
        seeds = [42, 7, 13, 23, 37, 53, 67, 89, 97, 101]

    all_draws = load_history()
    print(f"\n{'='*70}")
    print(f"  威力彩 P0+P1 升級版回測 | 測試期數: {test_periods}")
    print(f"  歷史數據: {len(all_draws)} 期 | 種子數: {len(seeds)} | 號碼池: 1-{MAX_NUM}")
    print(f"{'='*70}")

    # === 2注策略對比 ===
    print(f"\n{'─'*70}")
    print(f"  【2注策略】原版 vs P0 升級版")
    print(f"{'─'*70}")

    baseline_2 = BASELINES[2]
    print(f"  2注隨機基準: {baseline_2:.2f}%")
    print()

    orig_2_rates = []
    for sd in seeds:
        result = run_backtest(
            all_draws,
            lambda h, s: deviation_complement_2bet_original(h),
            2, test_periods, sd
        )
        if result:
            orig_2_rates.append(result['m3_rate'])

    p0_2_rates = []
    p0_details = []
    for sd in seeds:
        result = run_backtest(
            all_draws,
            lambda h, s: deviation_complement_2bet_p0(h),
            2, test_periods, sd
        )
        if result:
            p0_2_rates.append(result['m3_rate'])
            p0_details.append(result)

    if orig_2_rates and p0_2_rates:
        orig_avg = sum(orig_2_rates) / len(orig_2_rates)
        orig_std = (sum((r - orig_avg) ** 2 for r in orig_2_rates) / len(orig_2_rates)) ** 0.5
        p0_avg = sum(p0_2_rates) / len(p0_2_rates)
        p0_std = (sum((r - p0_avg) ** 2 for r in p0_2_rates) / len(p0_2_rates)) ** 0.5

        print(f"  {'策略':<25s} {'M3+率':>8s} {'基準':>8s} {'Edge':>8s} {'標準差':>8s} {'最差':>8s} {'最好':>8s}")
        print(f"  {'─'*64}")
        print(f"  {'原版偏差互補 2注':<20s} {orig_avg:>7.2f}% {baseline_2:>7.2f}% {orig_avg-baseline_2:>+7.2f}% {orig_std:>7.2f}% {min(orig_2_rates):>7.2f}% {max(orig_2_rates):>7.2f}%")
        print(f"  {'P0 回聲加分 2注':<20s} {p0_avg:>7.2f}% {baseline_2:>7.2f}% {p0_avg-baseline_2:>+7.2f}% {p0_std:>7.2f}% {min(p0_2_rates):>7.2f}% {max(p0_2_rates):>7.2f}%")
        delta = p0_avg - orig_avg
        print(f"\n  P0 vs 原版差異: {delta:+.2f}%")

        if p0_details:
            d = p0_details[0]
            print(f"\n  P0 各注獨立 M3+ (seed=42):")
            for bi, rate in enumerate(d['per_bet_rates']):
                label = "Hot+Echo" if bi == 0 else "Cold"
                print(f"    注{bi+1} [{label}]: {rate:.2f}%")

    # === 3注策略對比 ===
    print(f"\n{'─'*70}")
    print(f"  【3注策略】原版 vs P0+P1 升級版")
    print(f"{'─'*70}")

    baseline_3 = BASELINES[3]
    print(f"  3注隨機基準: {baseline_3:.2f}%")
    print()

    orig_3_rates = []
    orig_3_details = []
    for sd in seeds:
        result = run_backtest(
            all_draws,
            lambda h, s, _sd=sd: mixed_3bet_original(h, seed=_sd),
            3, test_periods, sd
        )
        if result:
            orig_3_rates.append(result['m3_rate'])
            orig_3_details.append(result)

    p0p1_3_rates = []
    p0p1_details = []
    for sd in seeds:
        result = run_backtest(
            all_draws,
            lambda h, s, _sd=sd: mixed_3bet_p0p1(h, seed=_sd),
            3, test_periods, sd
        )
        if result:
            p0p1_3_rates.append(result['m3_rate'])
            p0p1_details.append(result)

    if orig_3_rates and p0p1_3_rates:
        orig3_avg = sum(orig_3_rates) / len(orig_3_rates)
        orig3_std = (sum((r - orig3_avg) ** 2 for r in orig_3_rates) / len(orig_3_rates)) ** 0.5
        p0p1_avg = sum(p0p1_3_rates) / len(p0p1_3_rates)
        p0p1_std = (sum((r - p0p1_avg) ** 2 for r in p0p1_3_rates) / len(p0p1_3_rates)) ** 0.5

        print(f"  {'策略':<25s} {'M3+率':>8s} {'基準':>8s} {'Edge':>8s} {'標準差':>8s} {'最差':>8s} {'最好':>8s}")
        print(f"  {'─'*64}")
        print(f"  {'原版混合 3注':<20s} {orig3_avg:>7.2f}% {baseline_3:>7.2f}% {orig3_avg-baseline_3:>+7.2f}% {orig3_std:>7.2f}% {min(orig_3_rates):>7.2f}% {max(orig_3_rates):>7.2f}%")
        print(f"  {'P0+P1 升級 3注':<20s} {p0p1_avg:>7.2f}% {baseline_3:>7.2f}% {p0p1_avg-baseline_3:>+7.2f}% {p0p1_std:>7.2f}% {min(p0p1_3_rates):>7.2f}% {max(p0p1_3_rates):>7.2f}%")
        delta3 = p0p1_avg - orig3_avg
        print(f"\n  P0+P1 vs 原版差異: {delta3:+.2f}%")

        if p0p1_details:
            d = p0p1_details[0]
            print(f"\n  P0+P1 各注獨立 M3+ (seed=42):")
            for bi, rate in enumerate(d['per_bet_rates']):
                labels = ["Hot+Echo", "Cold", "Gray Zone"]
                print(f"    注{bi+1} [{labels[bi]}]: {rate:.2f}%")

        if orig_3_details:
            d = orig_3_details[0]
            print(f"\n  原版各注獨立 M3+ (seed=42):")
            for bi, rate in enumerate(d['per_bet_rates']):
                labels = ["Hot", "Cold", "Structural"]
                print(f"    注{bi+1} [{labels[bi]}]: {rate:.2f}%")

    # === Lag-2 echo stats for Power Lotto ===
    echo2_hits = 0
    for i in range(2, len(all_draws)):
        common = set(all_draws[i]['numbers']) & set(all_draws[i-2]['numbers'])
        if common:
            echo2_hits += 1
    echo2_rate = echo2_hits / (len(all_draws) - 2) * 100
    print(f"\n  威力彩 Lag-2 回聲歷史基率: {echo2_rate:.1f}% (共 {len(all_draws)} 期)")

    # === 每個種子明細 ===
    print(f"\n{'─'*70}")
    print(f"  各種子結果明細")
    print(f"{'─'*70}")
    print(f"  {'Seed':>6s} | {'原版2注':>8s} {'P0 2注':>8s} {'差異':>7s} | {'原版3注':>8s} {'P0P1 3注':>8s} {'差異':>7s}")
    print(f"  {'─'*64}")
    for i, sd in enumerate(seeds):
        o2 = orig_2_rates[i] if i < len(orig_2_rates) else 0
        p2 = p0_2_rates[i] if i < len(p0_2_rates) else 0
        o3 = orig_3_rates[i] if i < len(orig_3_rates) else 0
        p3 = p0p1_3_rates[i] if i < len(p0p1_3_rates) else 0
        print(f"  {sd:>6d} | {o2:>7.2f}% {p2:>7.2f}% {p2-o2:>+6.2f}% | {o3:>7.2f}% {p3:>7.2f}% {p3-o3:>+6.2f}%")

    # === 結論 ===
    print(f"\n{'='*70}")
    print(f"  結論 ({test_periods} 期)")
    print(f"{'='*70}")

    if orig_2_rates and p0_2_rates:
        o2a = sum(orig_2_rates) / len(orig_2_rates)
        p2a = sum(p0_2_rates) / len(p0_2_rates)
        verdict_2 = "PASS" if p2a > baseline_2 and p2a >= o2a else "FAIL"
        print(f"  2注 P0 回聲加分: Edge {p2a-baseline_2:+.2f}% vs 原版 Edge {o2a-baseline_2:+.2f}% → {verdict_2}")

    if orig_3_rates and p0p1_3_rates:
        o3a = sum(orig_3_rates) / len(orig_3_rates)
        p3a = sum(p0p1_3_rates) / len(p0p1_3_rates)
        verdict_3 = "PASS" if p3a > baseline_3 and p3a >= o3a else "FAIL"
        print(f"  3注 P0+P1 灰色地帶: Edge {p3a-baseline_3:+.2f}% vs 原版 Edge {o3a-baseline_3:+.2f}% → {verdict_3}")

    return {
        'periods': test_periods,
        'orig_2bet_avg': sum(orig_2_rates) / len(orig_2_rates) if orig_2_rates else 0,
        'p0_2bet_avg': sum(p0_2_rates) / len(p0_2_rates) if p0_2_rates else 0,
        'orig_3bet_avg': sum(orig_3_rates) / len(orig_3_rates) if orig_3_rates else 0,
        'p0p1_3bet_avg': sum(p0p1_3_rates) / len(p0p1_3_rates) if p0p1_3_rates else 0,
    }


def run_echo_boost_sensitivity(test_periods=500):
    """Echo boost 參數敏感性分析"""
    all_draws = load_history()
    print(f"\n{'='*70}")
    print(f"  威力彩 Echo Boost 參數敏感性分析 ({test_periods} 期)")
    print(f"{'='*70}")

    baseline_2 = BASELINES[2]
    boosts = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]

    print(f"\n  {'Boost':>8s} {'M3+率':>8s} {'Edge':>8s}")
    print(f"  {'─'*30}")

    for boost in boosts:
        result = run_backtest(
            all_draws,
            lambda h, s, _b=boost: deviation_complement_2bet_p0(h, echo_boost=_b),
            2, test_periods, 42
        )
        if result:
            rate = result['m3_rate']
            edge = rate - baseline_2
            marker = " ← 預設" if boost == 1.5 else (" ← 原版" if boost == 0.0 else "")
            print(f"  {boost:>8.1f} {rate:>7.2f}% {edge:>+7.2f}%{marker}")


def main():
    parser = argparse.ArgumentParser(description='威力彩 P0+P1 升級版回測')
    parser.add_argument('--periods', '-p', type=int, default=0,
                        help='測試期數 (150/500/1000/1500)')
    parser.add_argument('--all', action='store_true',
                        help='跑全部四個期數 (150+500+1000+1500)')
    parser.add_argument('--sensitivity', action='store_true',
                        help='Echo boost 參數敏感性分析')
    parser.add_argument('--seeds', type=int, default=10,
                        help='種子數量 (預設 10)')

    args = parser.parse_args()

    seeds = [42, 7, 13, 23, 37, 53, 67, 89, 97, 101][:args.seeds]

    if args.sensitivity:
        run_echo_boost_sensitivity(500)
        return

    if args.all or args.periods == 0:
        results = {}
        for periods in [150, 500, 1000, 1500]:
            r = run_full_comparison(periods, seeds)
            results[periods] = r

        # 跨期數摘要
        print(f"\n\n{'='*70}")
        print(f"  威力彩 跨期數摘要")
        print(f"{'='*70}")
        baseline_2 = BASELINES[2]
        baseline_3 = BASELINES[3]
        print(f"\n  {'期數':>6s} | {'原版2注Edge':>12s} {'P0 2注Edge':>12s} | {'原版3注Edge':>12s} {'P0P1 3注Edge':>12s}")
        print(f"  {'─'*60}")
        for p in [150, 500, 1000, 1500]:
            r = results[p]
            print(f"  {p:>6d} | {r['orig_2bet_avg']-baseline_2:>+11.2f}% {r['p0_2bet_avg']-baseline_2:>+11.2f}% | {r['orig_3bet_avg']-baseline_3:>+11.2f}% {r['p0p1_3bet_avg']-baseline_3:>+11.2f}%")

        print(f"\n  穩定性評估:")
        all_improve_2 = all(
            results[p]['p0_2bet_avg'] >= results[p]['orig_2bet_avg']
            for p in [150, 500, 1000, 1500]
        )
        all_improve_3 = all(
            results[p]['p0p1_3bet_avg'] >= results[p]['orig_3bet_avg']
            for p in [150, 500, 1000, 1500]
        )
        all_positive_2 = all(
            results[p]['p0_2bet_avg'] > baseline_2
            for p in [500, 1000, 1500]  # Skip 150 for stability
        )
        all_positive_3 = all(
            results[p]['p0p1_3bet_avg'] > baseline_3
            for p in [500, 1000, 1500]
        )

        print(f"    P0 2注: 全期數優於原版? {'YES' if all_improve_2 else 'NO'} | 500+期 Edge>0? {'YES' if all_positive_2 else 'NO'}")
        print(f"    P0+P1 3注: 全期數優於原版? {'YES' if all_improve_3 else 'NO'} | 500+期 Edge>0? {'YES' if all_positive_3 else 'NO'}")

        final_2 = "ADOPT" if all_positive_2 and results[1000]['p0_2bet_avg'] >= results[1000]['orig_2bet_avg'] else "REJECT"
        final_3 = "ADOPT" if all_positive_3 and results[1000]['p0p1_3bet_avg'] >= results[1000]['orig_3bet_avg'] else "REJECT"
        print(f"\n  最終判定:")
        print(f"    P0 回聲加分 2注: {final_2}")
        print(f"    P0+P1 灰色地帶 3注: {final_3}")

    else:
        run_full_comparison(args.periods, seeds)


if __name__ == '__main__':
    main()
