#!/usr/bin/env python3
"""
威力彩 5注堆疊方案回測驗證
===========================
方案 A: Power Precision 3注 + P0 偏差互補 2注 = 5注
方案 B: Power Precision 3注 + Fourier30+Markov30 2注 = 5注

驗證項目:
  1. 號碼重疊率 (越低越好)
  2. 組合 M3+ 率 vs 5注隨機基準 (18.20%)
  3. 三窗口驗證 (150/500/1500期)
  4. 各注獨立貢獻度
  5. 邊際效益 (vs 單獨 3注)

用法:
    python3 tools/backtest_power_5bet_stack.py
"""
import sqlite3
import json
import sys
import os
import random
import numpy as np
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'lottery_api'))

# 威力彩規則
MAX_NUM = 38
PICK = 6
BASELINE_1BET = 0.0387

BASELINES = {
    1: 3.87,
    2: 7.59,
    3: 11.17,
    4: 14.61,
    5: 18.20,
}


def load_history():
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


# ========== Strategy 1: Power Precision 3-bet ==========

def get_fourier_rank(history, window=500):
    from scipy.fft import fft, fftfreq
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    bitstreams = {i: np.zeros(w) for i in range(1, MAX_NUM + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= MAX_NUM:
                bitstreams[n][idx] = 1
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bh = bitstreams[n]
        if sum(bh) < 2:
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            continue
        period = 1 / freq_val
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return np.argsort(scores)[::-1]


def power_precision_3bet(history):
    f_rank = get_fourier_rank(history)
    idx_1 = 0
    while idx_1 < len(f_rank) and f_rank[idx_1] == 0:
        idx_1 += 1
    bet1 = sorted(f_rank[idx_1:idx_1+6].tolist())

    idx_2 = idx_1 + 6
    while idx_2 < len(f_rank) and f_rank[idx_2] == 0:
        idx_2 += 1
    bet2 = sorted(f_rank[idx_2:idx_2+6].tolist())

    exclude = set(bet1) | set(bet2)

    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'] if n <= MAX_NUM and n not in exclude]
    else:
        echo_nums = []

    recent = history[-100:]
    freq = Counter([n for d in recent for n in d['numbers']])
    remaining = [n for n in range(1, MAX_NUM + 1) if n not in exclude and n not in echo_nums]
    remaining.sort(key=lambda x: freq.get(x, 0))
    bet3 = sorted((echo_nums + remaining)[:6])

    return [bet1, bet2, bet3]


# ========== Strategy 2: P0 偏差互補 2-bet ==========

def deviation_complement_p0_2bet(history, window=50, echo_boost=1.5):
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
        scores[n] = f - expected

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

    return [sorted(bet1[:PICK]), sorted(bet2[:PICK])]


# ========== Strategy 3: Fourier30+Markov30 2-bet ==========

def fourier30_markov30_2bet(history):
    # Bet 1: Fourier30
    recent = history[-30:] if len(history) >= 30 else history
    weighted_freq = Counter()
    n = len(recent)
    for i, h in enumerate(recent):
        weight = 1 + 2 * (i / n)
        for num in h['numbers']:
            weighted_freq[num] += weight
    bet1 = sorted([n for n, _ in weighted_freq.most_common(6)])

    # Bet 2: Markov30
    transitions = Counter()
    for i in range(len(recent) - 1):
        prev = set(recent[i]['numbers'])
        curr = recent[i + 1]['numbers']
        for p in prev:
            for c in curr:
                transitions[(p, c)] += 1

    last = recent[-1]['numbers'] if recent else []
    scores = Counter()
    for num in last:
        for (p, c), count in transitions.items():
            if p == num:
                scores[c] += count

    bet2 = [n for n, _ in scores.most_common(6)]
    if len(bet2) < 6:
        all_nums = []
        for h in recent:
            all_nums.extend(h['numbers'])
        freq = Counter(all_nums)
        for n, _ in freq.most_common():
            if n not in bet2 and len(bet2) < 6:
                bet2.append(n)

    # Diversify: max overlap 3
    overlap = set(bet1) & set(bet2)
    if len(overlap) > 3:
        recent50 = history[-50:] if len(history) >= 50 else history
        last_seen = {i: len(recent50) for i in range(1, 39)}
        for idx, h in enumerate(recent50):
            for num in h['numbers']:
                gap = len(recent50) - 1 - idx
                if gap < last_seen[num]:
                    last_seen[num] = gap
        new_bet2 = [n for n in bet2 if n not in overlap][:3]
        cold = sorted(last_seen.items(), key=lambda x: -x[1])
        for n, gap in cold:
            if n not in bet1 and n not in new_bet2 and len(new_bet2) < 6:
                new_bet2.append(n)
        bet2 = sorted(new_bet2[:6])

    return [sorted(bet1), sorted(bet2[:6])]


# ========== Combined 5-bet strategies ==========

def combo_a_5bet(history):
    """方案A: Power Precision 3注 + P0 偏差互補 2注"""
    pp3 = power_precision_3bet(history)
    p0_2 = deviation_complement_p0_2bet(history)
    return pp3 + p0_2


def combo_b_5bet(history):
    """方案B: Power Precision 3注 + Fourier30+Markov30 2注"""
    pp3 = power_precision_3bet(history)
    fm_2 = fourier30_markov30_2bet(history)
    return pp3 + fm_2


# ========== Backtest Engine ==========

def run_backtest(all_draws, strategy_func, n_bets, test_periods, seed=42):
    test_periods = min(test_periods, len(all_draws) - 100)
    m3_count = 0
    per_bet_m3 = [0] * n_bets
    total = 0
    overlap_sum = 0
    unique_nums_sum = 0

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 50:
            continue

        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target_draw['numbers'])

        try:
            bets = strategy_func(hist)
            if len(bets) < n_bets:
                continue

            # Overlap analysis
            all_nums = set()
            for bet in bets[:n_bets]:
                all_nums.update(bet)
            unique_nums_sum += len(all_nums)
            total_nums = sum(len(bet) for bet in bets[:n_bets])
            overlap_sum += (total_nums - len(all_nums))

            best_match = 0
            for b_idx, bet in enumerate(bets[:n_bets]):
                match = len(set(bet) & actual)
                if match >= 3:
                    per_bet_m3[b_idx] += 1
                best_match = max(best_match, match)

            if best_match >= 3:
                m3_count += 1
            total += 1
        except Exception as e:
            continue

    if total == 0:
        return None

    return {
        'm3_count': m3_count,
        'm3_rate': m3_count / total * 100,
        'total': total,
        'per_bet_m3': per_bet_m3,
        'per_bet_rates': [c / total * 100 for c in per_bet_m3],
        'avg_overlap': overlap_sum / total if total > 0 else 0,
        'avg_unique': unique_nums_sum / total if total > 0 else 0,
    }


def marginal_contribution(per_bet_m3_counts, total):
    """計算每注的邊際貢獻 (該注獨家命中的次數)"""
    # This is approximate: we check per-bet hit rates
    return [c / total * 100 for c in per_bet_m3_counts]


def main():
    all_draws = load_history()
    print(f"{'='*75}")
    print(f"  威力彩 5注堆疊方案回測驗證")
    print(f"  歷史數據: {len(all_draws)} 期 | 號碼池: 1-{MAX_NUM}")
    print(f"{'='*75}")

    strategies = {
        'A: PP3 + P0偏差2': (combo_a_5bet, 5, 'Power Precision 3注 + P0 偏差互補 2注'),
        'B: PP3 + FM2': (combo_b_5bet, 5, 'Power Precision 3注 + Fourier30+Markov30 2注'),
        'PP3 alone': (power_precision_3bet, 3, 'Power Precision 3注 (對照組)'),
    }

    windows = [150, 500, 1500]
    results = {}

    for window in windows:
        print(f"\n{'─'*75}")
        print(f"  【{window} 期回測】")
        print(f"{'─'*75}")

        results[window] = {}

        for name, (func, n_bets, desc) in strategies.items():
            result = run_backtest(all_draws, func, n_bets, window)
            if result is None:
                continue
            results[window][name] = result

            baseline = BASELINES.get(n_bets, 0)
            edge = result['m3_rate'] - baseline

            print(f"\n  {desc}")
            print(f"    M3+: {result['m3_count']}/{result['total']} = {result['m3_rate']:.2f}%")
            print(f"    基準({n_bets}注): {baseline:.2f}% | Edge: {edge:+.2f}%")

            if n_bets == 5:
                print(f"    平均重疊號碼: {result['avg_overlap']:.1f} 個 | 平均覆蓋: {result['avg_unique']:.1f}/{n_bets*6} 個")

            # Per-bet breakdown
            labels_a = ["PP-F1", "PP-F2", "PP-Echo", "P0-Hot", "P0-Cold"]
            labels_b = ["PP-F1", "PP-F2", "PP-Echo", "FM-Fou30", "FM-Mkv30"]
            labels_pp = ["PP-F1", "PP-F2", "PP-Echo"]

            if 'A:' in name:
                labels = labels_a
            elif 'B:' in name:
                labels = labels_b
            else:
                labels = labels_pp

            per_bet_str = " | ".join(
                f"{labels[j]}:{result['per_bet_rates'][j]:.1f}%"
                for j in range(n_bets)
            )
            print(f"    各注M3+: {per_bet_str}")

    # ========== Summary ==========
    print(f"\n\n{'='*75}")
    print(f"  跨窗口摘要")
    print(f"{'='*75}")

    print(f"\n  {'策略':<25s}", end="")
    for w in windows:
        print(f" {'%dp Edge' % w:>12s}", end="")
    print(f" {'穩定性':>10s}")
    print(f"  {'─'*70}")

    for name in strategies:
        n_bets = strategies[name][1]
        baseline = BASELINES.get(n_bets, 0)
        print(f"  {name:<25s}", end="")
        edges = []
        for w in windows:
            if w in results and name in results[w]:
                edge = results[w][name]['m3_rate'] - baseline
                edges.append(edge)
                print(f" {edge:>+11.2f}%", end="")
            else:
                print(f" {'N/A':>12s}", end="")

        # Stability check
        if len(edges) >= 3:
            if all(e > 0 for e in edges):
                trend = "ALL_POSITIVE"
            elif edges[-1] < 0:
                trend = "NEGATIVE_LONG"
            elif edges[0] > 0 and edges[-1] < edges[0] * 0.3:
                trend = "DECAY"
            else:
                trend = "MIXED"
            print(f" {trend:>10s}")
        else:
            print()

    # ========== Overlap Analysis ==========
    print(f"\n{'='*75}")
    print(f"  重疊率分析")
    print(f"{'='*75}")

    for name in ['A: PP3 + P0偏差2', 'B: PP3 + FM2']:
        if 1500 in results and name in results[1500]:
            r = results[1500][name]
            ideal = 5 * 6  # 30
            print(f"\n  {name}:")
            print(f"    理想覆蓋: {ideal} 號 | 實際平均: {r['avg_unique']:.1f} 號")
            print(f"    重疊號碼: {r['avg_overlap']:.1f} 個 ({r['avg_overlap']/ideal*100:.1f}%)")
            print(f"    覆蓋效率: {r['avg_unique']/ideal*100:.1f}%")

    # ========== Marginal Value Analysis ==========
    print(f"\n{'='*75}")
    print(f"  邊際效益分析 (1500期)")
    print(f"{'='*75}")

    if 1500 in results:
        pp3_r = results[1500].get('PP3 alone')
        for name in ['A: PP3 + P0偏差2', 'B: PP3 + FM2']:
            r5 = results[1500].get(name)
            if pp3_r and r5:
                pp3_edge = pp3_r['m3_rate'] - BASELINES[3]
                r5_edge = r5['m3_rate'] - BASELINES[5]
                marginal = r5['m3_rate'] - pp3_r['m3_rate']
                marginal_baseline = BASELINES[5] - BASELINES[3]  # 18.20 - 11.17 = 7.03
                marginal_edge = marginal - marginal_baseline

                print(f"\n  {name}:")
                print(f"    3注 M3+: {pp3_r['m3_rate']:.2f}% (Edge {pp3_edge:+.2f}%)")
                print(f"    5注 M3+: {r5['m3_rate']:.2f}% (Edge {r5_edge:+.2f}%)")
                print(f"    增加2注後提升: {marginal:.2f}% (基準應提升: {marginal_baseline:.2f}%)")
                print(f"    額外2注邊際Edge: {marginal_edge:+.2f}%")
                if marginal_edge > 0:
                    print(f"    → 額外2注有正邊際效益")
                elif marginal_edge > -1.0:
                    print(f"    → 額外2注邊際接近零，視預算決定")
                else:
                    print(f"    → 額外2注損害整體效益，不建議")

    # ========== Final Verdict ==========
    print(f"\n{'='*75}")
    print(f"  最終判定")
    print(f"{'='*75}")

    best_name = None
    best_edge = -999

    for name in ['A: PP3 + P0偏差2', 'B: PP3 + FM2']:
        if 1500 in results and name in results[1500]:
            edge = results[1500][name]['m3_rate'] - BASELINES[5]
            if edge > best_edge:
                best_edge = edge
                best_name = name

    if best_name and best_edge > 0:
        r = results[1500][best_name]
        print(f"\n  推薦: {best_name}")
        print(f"  1500期 Edge: {best_edge:+.2f}%")
        print(f"  覆蓋效率: {r['avg_unique']:.1f}/30 號")

        # Check stability
        edges = []
        for w in windows:
            if w in results and best_name in results[w]:
                edges.append(results[w][best_name]['m3_rate'] - BASELINES[5])
        if all(e > 0 for e in edges):
            print(f"  穩定性: 三窗口全正 → ADOPT")
        else:
            print(f"  穩定性: 部分窗口為負 → CONDITIONAL")
    else:
        print(f"\n  無方案通過 5注基準驗證")
        print(f"  建議維持 3注 Power Precision")


if __name__ == '__main__':
    main()
