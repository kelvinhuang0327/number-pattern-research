#!/usr/bin/env python3
"""
威力彩 5注「分層正交」方案回測 — 驗證 Gemini 聲稱
================================================
Gemini 聲稱: 5注零重疊, 1500期 Edge +8.05% (25.96% vs 17.91%)
本腳本獨立復現, 用正確基準 18.20%

方案: PP3 前3注 + 從剩餘號碼中選2注 (零重疊)
"""
import sqlite3
import json
import sys
import numpy as np
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'lottery_api'))

MAX_NUM = 38
PICK = 6
BASELINES = {3: 11.17, 5: 18.20}


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


def orthogonal_5bet_gray_cold(history):
    """Gemini 方案: PP3 + 從剩餘號碼用灰區頻率+冷熱補償選2注 (零重疊)"""
    pp3 = power_precision_3bet(history)
    used = set()
    for bet in pp3:
        used.update(bet)

    remaining = [n for n in range(1, MAX_NUM + 1) if n not in used]

    # Gray zone frequency + cold/hot compensation
    recent50 = history[-50:] if len(history) >= 50 else history
    total = len(recent50)
    expected = total * PICK / MAX_NUM

    freq = Counter()
    for d in recent50:
        for n in d['numbers']:
            freq[n] += 1

    # Score remaining numbers: gray zone (close to expected) + gap-based cold boost
    scored = []
    for n in remaining:
        f = freq.get(n, 0)
        dev = abs(f - expected)
        # Gap from last appearance
        gap = 0
        for j in range(len(history) - 1, -1, -1):
            if n in history[j]['numbers']:
                gap = len(history) - 1 - j
                break
            gap = len(history) - j
        # Gray zone score: prefer numbers near expected frequency
        gray_score = 1.0 / (dev + 0.5)
        # Cold bonus: longer gap = higher score
        cold_score = min(gap / 20.0, 1.0)
        scored.append((n, gray_score + cold_score * 0.5))

    scored.sort(key=lambda x: x[1], reverse=True)
    available = [n for n, _ in scored]

    bet4 = sorted(available[:6])
    bet5 = sorted(available[6:12])

    return pp3 + [bet4, bet5]


def orthogonal_5bet_simple(history):
    """最簡單的零重疊: PP3 + 剩餘號碼按頻率排序選2注"""
    pp3 = power_precision_3bet(history)
    used = set()
    for bet in pp3:
        used.update(bet)

    remaining = [n for n in range(1, MAX_NUM + 1) if n not in used]

    recent100 = history[-100:] if len(history) >= 100 else history
    freq = Counter()
    for d in recent100:
        for n in d['numbers']:
            freq[n] += 1

    # Sort by frequency (most frequent first for bet4, least for bet5)
    remaining.sort(key=lambda x: freq.get(x, 0), reverse=True)

    bet4 = sorted(remaining[:6])   # Hot remaining
    bet5 = sorted(remaining[6:12]) # Cold remaining

    return pp3 + [bet4, bet5]


def orthogonal_5bet_random(history):
    """對照: PP3 + 剩餘號碼隨機選2注"""
    import random
    pp3 = power_precision_3bet(history)
    used = set()
    for bet in pp3:
        used.update(bet)
    remaining = [n for n in range(1, MAX_NUM + 1) if n not in used]
    rng = random.Random(42 + len(history))
    rng.shuffle(remaining)
    bet4 = sorted(remaining[:6])
    bet5 = sorted(remaining[6:12])
    return pp3 + [bet4, bet5]


def run_backtest(all_draws, strategy_func, n_bets, test_periods):
    test_periods = min(test_periods, len(all_draws) - 100)
    m3_count = 0
    per_bet_m3 = [0] * n_bets
    total = 0
    unique_sum = 0

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

            all_nums = set()
            for bet in bets[:n_bets]:
                all_nums.update(bet)
            unique_sum += len(all_nums)

            best_match = 0
            for b_idx, bet in enumerate(bets[:n_bets]):
                match = len(set(bet) & actual)
                if match >= 3:
                    per_bet_m3[b_idx] += 1
                best_match = max(best_match, match)
            if best_match >= 3:
                m3_count += 1
            total += 1
        except:
            continue

    if total == 0:
        return None
    return {
        'm3_count': m3_count,
        'm3_rate': m3_count / total * 100,
        'total': total,
        'per_bet_m3': per_bet_m3,
        'per_bet_rates': [c / total * 100 for c in per_bet_m3],
        'avg_unique': unique_sum / total if total > 0 else 0,
    }


def main():
    all_draws = load_history()
    print(f"{'='*75}")
    print(f"  威力彩 5注「分層正交」方案驗證 — 復現 Gemini 聲稱")
    print(f"  Gemini 聲稱: 25.96%, Edge +8.05%")
    print(f"  正確5注基準: 18.20%")
    print(f"  歷史數據: {len(all_draws)} 期")
    print(f"{'='*75}")

    strategies = {
        '正交(灰區+冷熱)': (orthogonal_5bet_gray_cold, 'Gemini 描述的方法'),
        '正交(頻率排序)': (orthogonal_5bet_simple, '簡單頻率排序'),
        '正交(隨機補位)': (orthogonal_5bet_random, '隨機從剩餘選取'),
        'PP3 (3注對照)': (power_precision_3bet, '基準對照'),
    }

    windows = [150, 500, 1500]

    all_results = {}
    for window in windows:
        print(f"\n{'─'*75}")
        print(f"  【{window} 期】")
        print(f"{'─'*75}")

        all_results[window] = {}
        for name, (func, desc) in strategies.items():
            n_bets = 3 if 'PP3' in name else 5
            result = run_backtest(all_draws, func, n_bets, window)
            if not result:
                continue
            all_results[window][name] = result

            baseline = BASELINES[n_bets]
            edge = result['m3_rate'] - baseline

            labels_5 = ["PP-F1", "PP-F2", "PP-Echo", "Ort-4", "Ort-5"]
            labels_3 = ["PP-F1", "PP-F2", "PP-Echo"]
            labels = labels_3 if n_bets == 3 else labels_5

            per_str = " | ".join(f"{labels[j]}:{result['per_bet_rates'][j]:.1f}%" for j in range(n_bets))

            print(f"\n  {name} ({desc})")
            print(f"    M3+: {result['m3_count']}/{result['total']} = {result['m3_rate']:.2f}%")
            print(f"    基準({n_bets}注): {baseline:.2f}% | Edge: {edge:+.2f}%")
            if n_bets == 5:
                print(f"    覆蓋: {result['avg_unique']:.1f}/38 號")
            print(f"    各注: {per_str}")

    # Summary
    print(f"\n\n{'='*75}")
    print(f"  跨窗口 Edge 摘要")
    print(f"{'='*75}")
    print(f"\n  {'策略':<22s}", end="")
    for w in windows:
        print(f" {f'{w}p Edge':>12s}", end="")
    print(f" {'判定':>12s}")
    print(f"  {'─'*70}")

    for name in strategies:
        n_bets = 3 if 'PP3' in name else 5
        baseline = BASELINES[n_bets]
        print(f"  {name:<22s}", end="")
        edges = []
        for w in windows:
            if w in all_results and name in all_results[w]:
                edge = all_results[w][name]['m3_rate'] - baseline
                edges.append(edge)
                print(f" {edge:>+11.2f}%", end="")
            else:
                print(f" {'N/A':>12s}", end="")
        if edges:
            if all(e > 0 for e in edges):
                verdict = "ALL_POS"
            elif edges[-1] < 0:
                verdict = "NEG_LONG"
            else:
                verdict = "MIXED"
            print(f" {verdict:>12s}")
        else:
            print()

    # Gemini claim comparison
    print(f"\n{'='*75}")
    print(f"  Gemini 聲稱 vs 獨立復現")
    print(f"{'='*75}")
    if 1500 in all_results and '正交(灰區+冷熱)' in all_results[1500]:
        our = all_results[1500]['正交(灰區+冷熱)']
        print(f"\n  {'':>20s} {'Gemini聲稱':>14s} {'獨立復現':>14s}")
        print(f"  {'─'*50}")
        print(f"  {'M3+率':>20s} {'25.96%':>14s} {our['m3_rate']:>13.2f}%")
        print(f"  {'基準':>20s} {'17.91%':>14s} {'18.20%':>14s}")
        print(f"  {'Edge':>20s} {'+8.05%':>14s} {our['m3_rate']-18.20:>+13.2f}%")
        gap = 25.96 - our['m3_rate']
        print(f"\n  差距: {gap:.2f}% — {'Gemini 聲稱無法復現' if gap > 2 else '接近'}")

    # Orthogonal vs random control
    print(f"\n{'='*75}")
    print(f"  正交策略 vs 隨機補位 (1500期)")
    print(f"{'='*75}")
    if 1500 in all_results:
        for name in ['正交(灰區+冷熱)', '正交(頻率排序)', '正交(隨機補位)']:
            if name in all_results[1500]:
                r = all_results[1500][name]
                edge = r['m3_rate'] - BASELINES[5]
                # Only bet 4-5 rates
                b45_avg = (r['per_bet_rates'][3] + r['per_bet_rates'][4]) / 2
                print(f"  {name}: M3+={r['m3_rate']:.2f}% Edge={edge:+.2f}% | 注4-5平均: {b45_avg:.2f}%")

        rand_r = all_results[1500].get('正交(隨機補位)')
        gray_r = all_results[1500].get('正交(灰區+冷熱)')
        if rand_r and gray_r:
            diff = gray_r['m3_rate'] - rand_r['m3_rate']
            print(f"\n  灰區策略 vs 隨機: {diff:+.2f}% 差異")
            if abs(diff) < 1.0:
                print(f"  → 差異微小，「灰區+冷熱」選號法無顯著優勢")


if __name__ == '__main__':
    main()
