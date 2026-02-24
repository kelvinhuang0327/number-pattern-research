#!/usr/bin/env python3
"""
39樂合彩 v2 — P3 Shuffle Permutation Test
==========================================
200 次打亂 × 全期回測 × seed=42
方法：隨機打亂開獎順序，保留號碼分布，破壞時序結構。
若 edge 消失 → 有時序訊號

嚴格防數據洩漏: history = draws[:i]
"""

import json
import math
import sqlite3
import os
import numpy as np
from collections import Counter
from datetime import datetime
import copy

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_api', 'data', 'lottery_v2.db')
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_v2.db')

POOL = 39
PICK = 5
N_SHUFFLES = 200
TEST_PERIODS = 1500  # 使用 1500 期做為標準驗證窗口
MIN_TRAIN = 100

def comb(n, k):
    return math.comb(n, k)

BASELINE_1BET_GE2 = sum(comb(PICK, k) * comb(POOL - PICK, PICK - k) / comb(POOL, PICK)
                        for k in range(2, PICK + 1))

def load_draws():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = 'DAILY_539'
        ORDER BY date ASC, draw ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    draws = []
    for draw_id, date, numbers_str in rows:
        nums = json.loads(numbers_str)
        draws.append({'draw': draw_id, 'date': date, 'numbers': sorted(nums)})
    return draws

# ═══════════════════════════════════════════════
#  策略 (只測 Top 5)
# ═══════════════════════════════════════════════

def fourier_predict(history, window=500, n=PICK):
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 30:
        return list(range(1, n + 1))
    scores = {}
    for num in range(1, POOL + 1):
        series = np.array([1 if num in d['numbers'] else 0 for d in recent], dtype=float)
        fft_vals = np.fft.rfft(series)
        power = np.abs(fft_vals) ** 2
        if len(power) > 1:
            dominant_idx = np.argmax(power[1:]) + 1
            phase = np.angle(fft_vals[dominant_idx])
            freq = dominant_idx / len(series)
            t_next = len(series)
            predicted = np.abs(fft_vals[dominant_idx]) * np.cos(2 * np.pi * freq * t_next + phase)
            base = series.mean()
            scores[num] = base + 0.3 * predicted / (len(series) ** 0.5)
        else:
            scores[num] = 0
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return sorted([x[0] for x in ranked[:n]])


def p0_devecho_predict(history, window=100, n=PICK):
    if len(history) < 10:
        return list(range(1, n + 1))
    recent = history[-window:] if len(history) >= window else history
    counter = Counter()
    for num in range(1, POOL + 1):
        counter[num] = 0
    for d in recent:
        for num in d['numbers']:
            counter[num] += 1
    expected = len(recent) * PICK / POOL
    scores = {}
    for num in range(1, POOL + 1):
        scores[num] = counter[num] - expected
    lag2_nums = set()
    if len(history) >= 2:
        lag2_nums = set(history[-2]['numbers'])
    for num in lag2_nums:
        if num in scores:
            scores[num] *= 1.5
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return sorted([x[0] for x in ranked[:n]])


def cold_twin_predict(history, window=100, n=PICK):
    if len(history) < 10:
        return list(range(1, n + 1))
    recent = history[-window:] if len(history) >= window else history
    last_seen = {}
    for i, d in enumerate(recent):
        for num in d['numbers']:
            last_seen[num] = i
    current = len(recent)
    gaps = {}
    for num in range(1, POOL + 1):
        gaps[num] = current - last_seen.get(num, -1)
    ranked = sorted(gaps.items(), key=lambda x: (-x[1], x[0]))
    return sorted([x[0] for x in ranked[:n]])


def markov_predict(history, window=30, n=PICK):
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 5:
        return list(range(1, n + 1))
    transition = np.zeros((POOL, POOL))
    for i in range(len(recent) - 1):
        for a in recent[i]['numbers']:
            for b in recent[i + 1]['numbers']:
                transition[a - 1][b - 1] += 1
    row_sums = transition.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    transition = transition / row_sums
    last_nums = recent[-1]['numbers']
    scores = np.zeros(POOL)
    for num in last_nums:
        scores += transition[num - 1]
    ranked_indices = np.argsort(-scores)
    return sorted([int(idx + 1) for idx in ranked_indices[:n]])


def triple_strike_predict(history, n=PICK):
    if len(history) < 30:
        return list(range(1, n + 1))
    fourier_scores = {}
    recent_f = history[-500:] if len(history) >= 500 else history
    for num in range(1, POOL + 1):
        series = np.array([1 if num in d['numbers'] else 0 for d in recent_f], dtype=float)
        fft_vals = np.fft.rfft(series)
        power = np.abs(fft_vals) ** 2
        if len(power) > 1:
            dominant_idx = np.argmax(power[1:]) + 1
            phase = np.angle(fft_vals[dominant_idx])
            freq = dominant_idx / len(series)
            t_next = len(series)
            predicted = np.abs(fft_vals[dominant_idx]) * np.cos(2 * np.pi * freq * t_next + phase)
            base = series.mean()
            fourier_scores[num] = base + 0.3 * predicted / (len(series) ** 0.5)
        else:
            fourier_scores[num] = 0

    recent_c = history[-100:] if len(history) >= 100 else history
    last_seen = {}
    for i, d in enumerate(recent_c):
        for num in d['numbers']:
            last_seen[num] = i
    current = len(recent_c)
    cold_scores = {}
    for num in range(1, POOL + 1):
        cold_scores[num] = (current - last_seen.get(num, -1)) / max(current, 1)

    recent_t = history[-100:] if len(history) >= 100 else history
    tail_counter = Counter()
    for d in recent_t:
        for num in d['numbers']:
            tail_counter[num % 10] += 1
    total_tails = sum(tail_counter.values()) or 1
    tail_scores = {}
    for num in range(1, POOL + 1):
        expected_ratio = 0.1
        actual_ratio = tail_counter[num % 10] / total_tails
        tail_scores[num] = expected_ratio - actual_ratio

    combined = {}
    for num in range(1, POOL + 1):
        combined[num] = 0.5 * fourier_scores.get(num, 0) + 0.3 * cold_scores.get(num, 0) + 0.2 * tail_scores.get(num, 0)
    ranked = sorted(combined.items(), key=lambda x: -x[1])
    return sorted([x[0] for x in ranked[:n]])


STRATEGIES = {
    'S1_Fourier': lambda h: fourier_predict(h),
    'S2_P0_DevEcho': lambda h: p0_devecho_predict(h),
    'S3_ColdTwin': lambda h: cold_twin_predict(h),
    'S4_Markov': lambda h: markov_predict(h),
    'S5_TripleStrike': lambda h: triple_strike_predict(h),
}


def backtest_strategy(strategy_fn, draws, test_periods):
    total = len(draws)
    start_idx = max(MIN_TRAIN, total - test_periods)
    ge2_count = 0
    test_count = 0
    for i in range(start_idx, total):
        history = draws[:i]
        prediction = strategy_fn(history)
        actual = set(draws[i]['numbers'])
        hits = len(set(prediction) & actual)
        if hits >= 2:
            ge2_count += 1
        test_count += 1
    return ge2_count / test_count if test_count > 0 else 0


def main():
    print("=" * 80)
    print("39樂合彩 v2 — P3 Shuffle Permutation Test")
    print(f"N_SHUFFLES = {N_SHUFFLES}, TEST_PERIODS = {TEST_PERIODS}")
    print(f"啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    draws = load_draws()
    print(f"\n📊 載入 {len(draws)} 期資料")

    results = {}

    for sname, sfn in STRATEGIES.items():
        print(f"\n{'═'*60}")
        print(f"策略: {sname}")
        print(f"{'═'*60}")

        # 1. 真實序列回測
        real_rate = backtest_strategy(sfn, draws, TEST_PERIODS)
        real_edge = real_rate - BASELINE_1BET_GE2
        print(f"  真實 ≥2 Rate: {real_rate*100:.4f}% (Edge {real_edge*100:+.4f}%)")

        # 2. Shuffle 回測
        shuffle_rates = []
        rng = np.random.RandomState(42)
        for s in range(N_SHUFFLES):
            shuffled = copy.deepcopy(draws)
            # 打亂開獎號碼的時序 (保留每期的號碼組合不變，只打亂它們出現的順序)
            numbers_pool = [d['numbers'] for d in shuffled]
            rng.shuffle(numbers_pool)
            for j, d in enumerate(shuffled):
                d['numbers'] = numbers_pool[j]

            shuffle_rate = backtest_strategy(sfn, shuffled, TEST_PERIODS)
            shuffle_rates.append(shuffle_rate)

            if (s + 1) % 50 == 0:
                print(f"    Shuffle {s+1}/{N_SHUFFLES} done...")

        shuffle_rates = np.array(shuffle_rates)
        shuffle_mean = np.mean(shuffle_rates)
        shuffle_std = np.std(shuffle_rates)
        shuffle_edge = shuffle_mean - BASELINE_1BET_GE2

        # P-value: 有多少 shuffle 結果 >= 真實結果
        p_value = np.mean(shuffle_rates >= real_rate)

        # Cohen's d
        if shuffle_std > 0:
            cohens_d = (real_rate - shuffle_mean) / shuffle_std
        else:
            cohens_d = 0

        # Z-score
        if shuffle_std > 0:
            z_score = (real_rate - shuffle_mean) / shuffle_std
        else:
            z_score = 0

        # 時序訊號佔比
        if real_edge > 0 and shuffle_edge >= 0:
            temporal_fraction = max(0, (real_edge - shuffle_edge) / real_edge * 100)
        elif real_edge > 0:
            temporal_fraction = 100.0
        else:
            temporal_fraction = 0

        # 判定
        if p_value < 0.025:  # Bonferroni α/2
            verdict = "🟢 SIGNAL DETECTED (Bonferroni)"
        elif p_value < 0.05:
            verdict = "🟡 MARGINAL SIGNAL"
        elif p_value < 0.10:
            verdict = "🟠 WEAK HINT"
        else:
            verdict = "🔴 NO SIGNAL"

        results[sname] = {
            'real_rate': real_rate,
            'real_edge': real_edge,
            'shuffle_mean': float(shuffle_mean),
            'shuffle_std': float(shuffle_std),
            'shuffle_edge': float(shuffle_edge),
            'p_value': float(p_value),
            'cohens_d': float(cohens_d),
            'z_score': float(z_score),
            'temporal_fraction': temporal_fraction,
            'verdict': verdict
        }

        print(f"  Shuffle Mean ≥2 Rate: {shuffle_mean*100:.4f}% (Edge {shuffle_edge*100:+.4f}%)")
        print(f"  Shuffle Std: {shuffle_std*100:.4f}%")
        print(f"  P-value: {p_value:.4f}")
        print(f"  Cohen's d: {cohens_d:.3f}")
        print(f"  Z-score: {z_score:.3f}")
        print(f"  時序訊號佔比: {temporal_fraction:.1f}%")
        print(f"  判定: {verdict}")

    # 總結表格
    print("\n" + "═" * 80)
    print("P3 Shuffle Permutation Test 總結")
    print("═" * 80)
    print(f"\n{'策略':<25s} | {'Real Edge':>10s} | {'Shuffle E':>10s} | {'p-value':>8s} | {'Cohen d':>8s} | 判定")
    print(f"{'─'*25} | {'─'*10} | {'─'*10} | {'─'*8} | {'─'*8} | {'─'*30}")
    for sname, r in results.items():
        print(f"{sname:<25s} | {r['real_edge']*100:+8.4f}% | {r['shuffle_edge']*100:+8.4f}% | {r['p_value']:8.4f} | {r['cohens_d']:8.3f} | {r['verdict']}")

    # 保存
    output = {
        'meta': {
            'test': 'P3 Shuffle Permutation Test',
            'n_shuffles': N_SHUFFLES,
            'test_periods': TEST_PERIODS,
            'baseline_ge2': BASELINE_1BET_GE2,
            'seed': 42,
            'timestamp': datetime.now().isoformat()
        },
        'results': {k: {kk: float(vv) if isinstance(vv, (np.floating,)) else vv
                        for kk, vv in v.items()} for k, v in results.items()}
    }

    output_path = os.path.join(os.path.dirname(__file__), '..', 'p3_39lotto_shuffle_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n💾 結果已保存至: {output_path}")


if __name__ == '__main__':
    main()
