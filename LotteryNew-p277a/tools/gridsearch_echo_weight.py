#!/usr/bin/env python3
"""
Echo Weight Grid Search — 找最佳固定 echo_weight

測試範圍: 0.00 ~ 0.50 (步長 0.05)
驗證: 1000期, 確定性 (無隨機成分)
"""

import sqlite3
import json
import sys
import math
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
    freq_values = [freq_long.get(n, 0) for n in range(1, MAX_NUM + 1)]
    freq_sorted = sorted(freq_values)
    for n in range(1, MAX_NUM + 1):
        f = freq_long.get(n, 0)
        rank = sum(1 for v in freq_sorted if v <= f) / MAX_NUM
        gap_comp = math.exp(-gaps[n] / (MAX_NUM / PICK))
        exp_s = short_window * PICK / MAX_NUM
        exp_l = len(recent) * PICK / MAX_NUM
        sr = freq_short.get(n, 0) / max(exp_s, 0.1)
        lr = f / max(exp_l, 0.1)
        trend = min(1.0, max(0.0, 0.5 + (sr - lr) * 0.5))
        temps[n] = 0.40 * rank + 0.30 * gap_comp + 0.30 * trend
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


def make_2bets(history, echo_weight):
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
    return [bet1, bet2]


def make_3bets(history, echo_weight):
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
    used.update(bet2)

    es = min(0.7, echo_weight * 2)
    b3s = {}
    for n in range(1, MAX_NUM + 1):
        if n in used:
            continue
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
                best_sc = sc
                best = b
    if best is None:
        best = sorted(cands[:PICK])
    return [bet1, bet2, best]


def backtest(all_h, weight, n_bets, periods):
    total = len(all_h)
    start = max(50, total - periods)
    m3 = 0
    tested = 0
    for idx in range(start, total):
        train = all_h[:idx]
        actual = set(all_h[idx]['numbers'])
        if len(train) < 50:
            continue
        if n_bets == 2:
            bets = make_2bets(train, weight)
        else:
            bets = make_3bets(train, weight)
        best = max(len(set(b) & actual) for b in bets)
        if best >= 3:
            m3 += 1
        tested += 1
    return m3 / tested * 100 if tested else 0, tested


def random_baseline(all_h, periods, n_bets, seeds):
    import random
    total = len(all_h)
    start = max(50, total - periods)
    rates = []
    for seed in seeds:
        rng = random.Random(seed)
        m3 = 0
        tested = 0
        for idx in range(start, total):
            actual = set(all_h[idx]['numbers'])
            bets = []
            used = set()
            for _ in range(n_bets):
                avail = [n for n in range(1, MAX_NUM + 1) if n not in used]
                if len(avail) < PICK:
                    avail = list(range(1, MAX_NUM + 1)); used = set()
                b = sorted(rng.sample(avail, PICK))
                bets.append(b); used.update(b)
            best = max(len(set(b) & actual) for b in bets)
            if best >= 3:
                m3 += 1
            tested += 1
        if tested:
            rates.append(m3 / tested * 100)
    avg = sum(rates) / len(rates)
    return avg


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--periods', type=int, default=1000)
    args = parser.parse_args()

    all_h = load_history()
    if not all_h:
        print("錯誤: 無法載入數據"); sys.exit(1)

    weights = [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]

    print(f"{'='*75}")
    print(f"  Echo Weight Grid Search")
    print(f"  數據: {len(all_h)} 期 | 回測: {args.periods} 期 | 權重: {len(weights)} 個")
    print(f"{'='*75}")

    seeds = [42, 123, 456, 789, 1024, 2048, 3333, 5555, 7777, 9999]

    # 隨機基準
    print(f"\n  計算隨機基準...", end='', flush=True)
    bl_2 = random_baseline(all_h, args.periods, 2, seeds)
    bl_3 = random_baseline(all_h, args.periods, 3, seeds)
    print(f" 2注={bl_2:.2f}%, 3注={bl_3:.2f}%")

    # 2注 Grid Search
    print(f"\n{'─'*75}")
    print(f"  [2注 Grid Search]")
    print(f"{'─'*75}")
    print(f"\n  {'Weight':<10} {'M3+':<10} {'Edge':<10} {'Bar'}")
    print(f"  {'─'*55}")

    results_2 = []
    for w in weights:
        rate, tested = backtest(all_h, w, 2, args.periods)
        edge = rate - bl_2
        results_2.append((w, rate, edge, tested))
        bar_len = max(0, int(edge * 10))
        bar = '█' * bar_len if edge > 0 else '░' * max(0, int(-edge * 10))
        marker = ' ◀ BEST' if edge == max(r[2] for r in results_2) and edge > 0 else ''
        print(f"  {w:<10.2f} {rate:>6.2f}%    {edge:>+6.2f}%    {bar}{marker}")
        sys.stdout.flush()

    best_2 = max(results_2, key=lambda x: x[2])
    print(f"\n  最佳 2注: weight={best_2[0]:.2f}, M3+={best_2[1]:.2f}%, Edge={best_2[2]:+.2f}%")

    # 3注 Grid Search
    print(f"\n{'─'*75}")
    print(f"  [3注 Grid Search]")
    print(f"{'─'*75}")
    print(f"\n  {'Weight':<10} {'M3+':<10} {'Edge':<10} {'Bar'}")
    print(f"  {'─'*55}")

    results_3 = []
    for w in weights:
        rate, tested = backtest(all_h, w, 3, args.periods)
        edge = rate - bl_3
        results_3.append((w, rate, edge, tested))
        bar_len = max(0, int(edge * 10))
        bar = '█' * bar_len if edge > 0 else '░' * max(0, int(-edge * 10))
        marker = ' ◀ BEST' if edge == max(r[2] for r in results_3) and edge > 0 else ''
        print(f"  {w:<10.2f} {rate:>6.2f}%    {edge:>+6.2f}%    {bar}{marker}")
        sys.stdout.flush()

    best_3 = max(results_3, key=lambda x: x[2])
    print(f"\n  最佳 3注: weight={best_3[0]:.2f}, M3+={best_3[1]:.2f}%, Edge={best_3[2]:+.2f}%")

    # 總結
    print(f"\n{'='*75}")
    print(f"  Grid Search 總結")
    print(f"{'='*75}")
    print(f"\n  隨機基準: 2注={bl_2:.2f}%, 3注={bl_3:.2f}%")
    print(f"\n  2注最佳: echo_weight={best_2[0]:.2f} → Edge {best_2[2]:+.2f}%")
    print(f"  3注最佳: echo_weight={best_3[0]:.2f} → Edge {best_3[2]:+.2f}%")

    # 穩定性分析: top 3 附近是否一致
    print(f"\n  2注 Top 3:")
    for w, rate, edge, _ in sorted(results_2, key=lambda x: x[2], reverse=True)[:3]:
        print(f"    weight={w:.2f}: Edge {edge:+.2f}%")
    print(f"\n  3注 Top 3:")
    for w, rate, edge, _ in sorted(results_3, key=lambda x: x[2], reverse=True)[:3]:
        print(f"    weight={w:.2f}: Edge {edge:+.2f}%")

    # echo_weight=0 就是純溫度 (Phase 1 等效無 echo)
    pure_temp_2 = next(r for r in results_2 if r[0] == 0.00)
    pure_temp_3 = next(r for r in results_3 if r[0] == 0.00)
    print(f"\n  Echo 貢獻 (最佳 vs 純溫度 w=0.00):")
    print(f"    2注: {best_2[2] - pure_temp_2[2]:+.2f}% (w={best_2[0]:.2f} vs w=0.00)")
    print(f"    3注: {best_3[2] - pure_temp_3[2]:+.2f}% (w={best_3[0]:.2f} vs w=0.00)")

    print()


if __name__ == '__main__':
    main()
