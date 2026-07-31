#!/usr/bin/env python3
"""
Echo Weight 精細搜索 + 穩定性驗證

1. 精細搜索: 0.05 ~ 0.20 步長 0.01
2. 穩定性: 前500期 vs 後500期 分段驗證
3. 與原始偏差互補對比
"""

import sqlite3
import json
import sys
import math
import random
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'lottery_api'))

MAX_NUM = 49
PICK = 6


def load_history():
    db_path = PROJECT_ROOT / 'lottery_api' / 'data' / 'lottery_v2.db'
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT draw, date, numbers FROM draws WHERE lottery_type='BIG_LOTTO' ORDER BY date ASC"
    )
    draws = []
    for row in cursor.fetchall():
        nums = json.loads(row[2]) if row[2] else []
        draws.append({'draw': row[0], 'date': row[1], 'numbers': sorted(nums)})
    conn.close()
    return draws


def echo_detector(history, max_lag=5):
    if len(history) < max_lag + 1:
        return {}
    latest = set(history[-1]['numbers'])
    scores = Counter()
    for lag in range(1, max_lag + 1):
        past = set(history[-(lag + 1)]['numbers'])
        overlap = latest & past
        if len(overlap) >= 2:
            w = len(overlap) / PICK * (1.0 / lag)
            for n in overlap:
                scores[n] += w * 0.5
            for n in past - latest:
                scores[n] += w * 1.0
    if scores:
        mx = max(scores.values())
        if mx > 0:
            for n in scores:
                scores[n] /= mx
    return dict(scores)


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
    temps = {}
    fv = [freq_long.get(n, 0) for n in range(1, MAX_NUM + 1)]
    fs = sorted(fv)
    for n in range(1, MAX_NUM + 1):
        f = freq_long.get(n, 0)
        rank = sum(1 for v in fs if v <= f) / MAX_NUM
        gc = math.exp(-gaps[n] / (MAX_NUM / PICK))
        es = short_window * PICK / MAX_NUM
        el = len(recent) * PICK / MAX_NUM
        sr = freq_short.get(n, 0) / max(es, 0.1)
        lr = f / max(el, 0.1)
        tc = min(1.0, max(0.0, 0.5 + (sr - lr) * 0.5))
        temps[n] = 0.40 * rank + 0.30 * gc + 0.30 * tc
    return temps


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
    sc = 0
    if 100 <= s <= 200: sc += 2
    if 120 <= s <= 180: sc += 2
    if 2 <= odd <= 4: sc += 2
    if all(z >= 1 for z in zones): sc += 2
    if consec <= 1: sc += 1
    if spread >= 25: sc += 1
    return sc


def make_bets(history, echo_weight, n_bets):
    temps = continuous_temperature(history)
    echoes = echo_detector(history)
    hot_s, cold_s = {}, {}
    for n in range(1, MAX_NUM + 1):
        t = temps.get(n, 0.5)
        e = echoes.get(n, 0.0)
        hot_s[n] = t * (1 - echo_weight) + e * echo_weight
        cold_s[n] = (1 - t) * (1 - echo_weight) + e * echo_weight
    hot_r = sorted(range(1, MAX_NUM + 1), key=lambda n: hot_s[n], reverse=True)
    cold_r = sorted(range(1, MAX_NUM + 1), key=lambda n: cold_s[n], reverse=True)
    bet1 = sorted(hot_r[:PICK])
    used = set(bet1)
    bet2 = sorted([n for n in cold_r if n not in used][:PICK])
    if n_bets == 2:
        return [bet1, bet2]
    used.update(bet2)
    es = min(0.7, echo_weight * 2)
    b3s = {}
    for n in range(1, MAX_NUM + 1):
        if n in used: continue
        t = temps.get(n, 0.5)
        e = echoes.get(n, 0.0)
        warm = 1.0 - abs(t - 0.5) * 2.0
        b3s[n] = e * es + warm * (1 - es)
    ranked = sorted(b3s.keys(), key=lambda n: b3s[n], reverse=True)
    cands = sorted(ranked[:12])
    if len(cands) < PICK:
        cands = sorted([n for n in range(1, MAX_NUM + 1) if n not in used])
    from itertools import combinations
    best, best_sc = None, -1
    if len(cands) >= PICK:
        for combo in combinations(cands, PICK):
            b = sorted(combo)
            sc = structural_score(b) + sum(b3s.get(n, 0) for n in b) / PICK * 0.1
            if sc > best_sc:
                best_sc = sc; best = b
    if best is None:
        best = sorted(cands[:PICK])
    return [bet1, bet2, best]


def original_deviation_2bet(history, window=50):
    recent = history[-window:] if len(history) > window else history
    expected = len(recent) * PICK / MAX_NUM
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    hot, cold = [], []
    for n in range(1, MAX_NUM + 1):
        dev = freq.get(n, 0) - expected
        if dev > 1: hot.append((n, dev))
        elif dev < -1: cold.append((n, abs(dev)))
    hot.sort(key=lambda x: x[1], reverse=True)
    cold.sort(key=lambda x: x[1], reverse=True)
    bet1 = [n for n, _ in hot[:PICK]]
    used = set(bet1)
    if len(bet1) < PICK:
        mid = sorted(range(1, MAX_NUM + 1), key=lambda n: abs(freq.get(n, 0) - expected))
        for n in mid:
            if n not in used and len(bet1) < PICK: bet1.append(n); used.add(n)
    bet2 = []
    for n, _ in cold:
        if n not in used and len(bet2) < PICK: bet2.append(n); used.add(n)
    if len(bet2) < PICK:
        for n in range(1, MAX_NUM + 1):
            if n not in used and len(bet2) < PICK: bet2.append(n); used.add(n)
    return [sorted(bet1[:PICK]), sorted(bet2[:PICK])]


def backtest_range(all_h, strategy_fn, start_idx, end_idx):
    m3 = 0
    tested = 0
    for idx in range(start_idx, end_idx):
        train = all_h[:idx]
        actual = set(all_h[idx]['numbers'])
        if len(train) < 50: continue
        bets = strategy_fn(train)
        best = max(len(set(b) & actual) for b in bets)
        if best >= 3: m3 += 1
        tested += 1
    return m3 / tested * 100 if tested else 0, tested


def random_baseline_range(all_h, start_idx, end_idx, n_bets, seeds):
    rates = []
    for seed in seeds:
        rng = random.Random(seed)
        m3 = 0; tested = 0
        for idx in range(start_idx, end_idx):
            actual = set(all_h[idx]['numbers'])
            bets = []
            used = set()
            for _ in range(n_bets):
                avail = [n for n in range(1, MAX_NUM + 1) if n not in used]
                if len(avail) < PICK: avail = list(range(1, MAX_NUM + 1)); used = set()
                b = sorted(rng.sample(avail, PICK)); bets.append(b); used.update(b)
            best = max(len(set(b) & actual) for b in bets)
            if best >= 3: m3 += 1
            tested += 1
        if tested: rates.append(m3 / tested * 100)
    return sum(rates) / len(rates) if rates else 0


def main():
    all_h = load_history()
    if not all_h:
        print("錯誤"); sys.exit(1)

    total = len(all_h)
    seeds = [42, 123, 456, 789, 1024, 2048, 3333, 5555, 7777, 9999]

    # 精細搜索範圍
    fine_weights = [round(w * 0.01, 2) for w in range(5, 21)]  # 0.05 ~ 0.20

    # 全 1000 期
    full_start = max(50, total - 1000)
    full_end = total
    # 前 500 期
    mid_point = full_start + (full_end - full_start) // 2
    # 段1: full_start ~ mid_point
    # 段2: mid_point ~ full_end

    print(f"{'='*75}")
    print(f"  Echo Weight 精細搜索 + 穩定性驗證")
    print(f"  數據: {total} 期 | 全段: {full_end - full_start} 期")
    print(f"  前半段: 期{full_start}~{mid_point} ({mid_point - full_start}期)")
    print(f"  後半段: 期{mid_point}~{full_end} ({full_end - mid_point}期)")
    print(f"{'='*75}")

    for n_bets in [2, 3]:
        print(f"\n{'─'*75}")
        print(f"  [{n_bets}注 精細搜索]")
        print(f"{'─'*75}")

        # 基準
        bl_full = random_baseline_range(all_h, full_start, full_end, n_bets, seeds)
        bl_h1 = random_baseline_range(all_h, full_start, mid_point, n_bets, seeds)
        bl_h2 = random_baseline_range(all_h, mid_point, full_end, n_bets, seeds)

        # 原始偏差互補 (只 2注)
        if n_bets == 2:
            orig_full, _ = backtest_range(all_h, original_deviation_2bet, full_start, full_end)
            orig_h1, _ = backtest_range(all_h, original_deviation_2bet, full_start, mid_point)
            orig_h2, _ = backtest_range(all_h, original_deviation_2bet, mid_point, full_end)
            print(f"\n  原始偏差互補: 全段 Edge {orig_full - bl_full:+.2f}% | 前半 {orig_h1 - bl_h1:+.2f}% | 後半 {orig_h2 - bl_h2:+.2f}%")

        print(f"\n  {'Weight':<8} {'全段Edge':<12} {'前半Edge':<12} {'後半Edge':<12} {'差距':<8} {'穩定?'}")
        print(f"  {'─'*65}")

        results = []
        for w in fine_weights:
            fn = lambda h, _w=w: make_bets(h, _w, n_bets)
            r_full, _ = backtest_range(all_h, fn, full_start, full_end)
            r_h1, _ = backtest_range(all_h, fn, full_start, mid_point)
            r_h2, _ = backtest_range(all_h, fn, mid_point, full_end)

            e_full = r_full - bl_full
            e_h1 = r_h1 - bl_h1
            e_h2 = r_h2 - bl_h2
            gap = abs(e_h1 - e_h2)
            # 穩定 = 兩段都正 Edge 且差距 < 1.5%
            stable = e_h1 > 0 and e_h2 > 0 and gap < 1.5
            marker = '✓' if stable else '✗'
            results.append((w, e_full, e_h1, e_h2, gap, stable))
            print(f"  {w:<8.2f} {e_full:>+8.2f}%    {e_h1:>+8.2f}%    {e_h2:>+8.2f}%    {gap:>5.2f}%  {marker}")
            sys.stdout.flush()

        # 穩定且 Edge 最高的
        stable_results = [r for r in results if r[5]]
        if stable_results:
            best = max(stable_results, key=lambda x: x[1])
            print(f"\n  最佳穩定權重: {best[0]:.2f} → Edge {best[1]:+.2f}% (前半{best[2]:+.2f}%, 後半{best[3]:+.2f}%)")
        else:
            best = max(results, key=lambda x: x[1])
            print(f"\n  無穩定權重! 最高 Edge: {best[0]:.2f} → {best[1]:+.2f}% (不穩定)")

    print(f"\n{'='*75}")
    print(f"  結論")
    print(f"{'='*75}")
    print()


if __name__ == '__main__':
    main()
