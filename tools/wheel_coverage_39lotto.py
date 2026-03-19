#!/usr/bin/env python3
"""
39樂合彩 v2 — Wheel Coverage 分析 + 多種子穩定性 + 二合專項
============================================================
1. Wheel Coverage: 用 N 注覆蓋最多二合/三合組合
2. 多種子穩定性: 10 seeds × Top 策略
3. 二合預測: pair-level 預測精準度分析
"""

import json
import math
import sqlite3
import os
import numpy as np
from collections import Counter
from datetime import datetime
from itertools import combinations

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_api', 'data', 'lottery_v2.db')
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_v2.db')

POOL = 39
PICK = 5

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
#  策略複製 (保持一致性)
# ═══════════════════════════════════════════════

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


def main():
    print("=" * 80)
    print("39樂合彩 v2 — Wheel Coverage + 多種子穩定性 + 二合專項")
    print(f"啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    draws = load_draws()
    N = len(draws)
    print(f"📊 載入 {N} 期資料\n")

    # ══════════════════════════════════════════
    # PART 1: Wheel Coverage 分析
    # ══════════════════════════════════════════
    print("═" * 80)
    print("PART 1: Wheel Coverage 分析")
    print("═" * 80)

    # 每注 5 個號碼 → C(5,2)=10 個二合, C(5,3)=10 個三合
    # N 注的覆蓋率取決於號碼重疊
    print("\n理論 Wheel Coverage:")

    for n_bets in [1, 2, 3, 5]:
        # 最佳情況: 號碼完全不重疊
        max_unique = min(n_bets * PICK, POOL)
        max_2he = comb(max_unique, 2)
        max_3he = comb(max_unique, 3)
        total_2he = comb(POOL, 2)  # 741
        total_3he = comb(POOL, 3)  # 9139

        # 每注涵蓋的二合: C(5,2)=10
        bet_2he = comb(PICK, 2)
        bet_3he = comb(PICK, 3)

        # 計算覆蓋率 (不重疊情況)
        if n_bets * PICK <= POOL:
            # 完全不重疊
            covered_2he = n_bets * bet_2he
            covered_3he = n_bets * bet_3he
        else:
            covered_2he = comb(POOL, 2)
            covered_3he = comb(POOL, 3)

        # 隨機覆蓋的中獎機率
        # P(至少一個二合中獎) = 1 - Π(1 - P(bet_i 二合中獎))
        p_2he_per_bet = comb(PICK, 2) / comb(POOL, 2)  # P(隨機2個全中) 不對...

        # 重新計算: 每注選5個號碼，開獎5個號碼
        # 某注中二合 = 該注的5個號碼中有≥2個出現在開獎5個號碼中
        # = P(≥2 hits) = BASELINE_1BET_GE2

        p_any_ge2 = 1 - (1 - BASELINE_1BET_GE2) ** n_bets

        print(f"\n  {n_bets}注:")
        print(f"    最大不重疊號碼: {max_unique}/{POOL}")
        print(f"    覆蓋二合數 (不重疊): {covered_2he}/{total_2he} = {covered_2he/total_2he*100:.2f}%")
        print(f"    覆蓋三合數 (不重疊): {covered_3he}/{total_3he} = {covered_3he/total_3he*100:.2f}%")
        print(f"    隨機≥2命中率 (獨立): {p_any_ge2*100:.3f}%")

    # ══════════════════════════════════════════
    # PART 2: 多種子穩定性檢驗
    # ══════════════════════════════════════════
    print("\n" + "═" * 80)
    print("PART 2: 多種子穩定性檢驗 (Top 3 確定性策略)")
    print("═" * 80)

    # 確定性策略不受種子影響 — 驗證此特性
    strategies_to_test = {
        'S2_P0_DevEcho': lambda h: p0_devecho_predict(h),
        'S4_Markov_w30': lambda h: markov_predict(h),
        'S1_Fourier_w500': lambda h: fourier_predict(h),
    }

    TEST_PERIODS = 1500
    start_idx = max(100, N - TEST_PERIODS)

    for sname, sfn in strategies_to_test.items():
        print(f"\n▶ {sname}")

        # 確定性策略: 多次運行應得到完全相同結果
        rates = []
        for seed in range(10):
            # 策略本身不使用隨機 (確定性)
            ge2_count = 0
            test_count = 0
            for i in range(start_idx, N):
                history = draws[:i]
                prediction = sfn(history)
                actual = set(draws[i]['numbers'])
                if len(set(prediction) & actual) >= 2:
                    ge2_count += 1
                test_count += 1
            rate = ge2_count / test_count
            rates.append(rate)

        rates = np.array(rates)
        print(f"  率值: {rates[0]*100:.4f}% (確定性，10次均相同)")
        print(f"  標準差: {np.std(rates)*100:.6f}%")
        print(f"  Edge: {(rates[0] - BASELINE_1BET_GE2)*100:+.4f}%")

        # 確認確定性
        if np.std(rates) < 1e-10:
            print(f"  ✅ 確定性策略確認 (σ=0)")
        else:
            print(f"  ⚠️ 非確定性! σ={np.std(rates)*100:.6f}%")

    # ══════════════════════════════════════════
    # PART 3: 二合專項 pair-level 分析
    # ══════════════════════════════════════════
    print("\n" + "═" * 80)
    print("PART 3: 二合 (pair-level) 預測分析")
    print("═" * 80)

    # 對每期: 預測 5 個號碼 → 產生 C(5,2)=10 個二合
    # 計算這 10 個二合中是否有在實際開獎二合中命中
    # 實際開獎 5 個號碼 → C(5,2)=10 個二合

    print("\n分析: 預測號碼產生的二合 vs 開獎二合 的匹配率")

    for sname, sfn in strategies_to_test.items():
        hit_pairs = 0
        total_pred_pairs = 0
        total_test = 0

        for i in range(start_idx, N):
            history = draws[:i]
            prediction = sfn(history)
            actual = draws[i]['numbers']

            pred_pairs = set(combinations(sorted(prediction), 2))
            actual_pairs = set(combinations(sorted(actual), 2))

            matched = pred_pairs & actual_pairs
            hit_pairs += len(matched)
            total_pred_pairs += len(pred_pairs)
            total_test += 1

        # 隨機基準: 每注 10 個二合 × P(specific pair hits) = C(37,3)/C(39,5)
        p_specific_pair = comb(POOL - 2, PICK - 2) / comb(POOL, PICK)
        expected_pairs_per_draw = 10 * p_specific_pair
        expected_rate = expected_pairs_per_draw / 10  # 每個二合的命中率

        actual_rate = hit_pairs / total_pred_pairs
        edge_pair = actual_rate - p_specific_pair

        print(f"\n  {sname}:")
        print(f"    命中二合總數: {hit_pairs}/{total_pred_pairs}")
        print(f"    二合命中率: {actual_rate*100:.4f}%")
        print(f"    隨機基準: {p_specific_pair*100:.4f}%")
        print(f"    Edge: {edge_pair*100:+.4f}%")

    # ══════════════════════════════════════════
    # PART 4: 二合高頻組合追蹤
    # ══════════════════════════════════════════
    print("\n" + "═" * 80)
    print("PART 4: 歷史高頻二合組合 (Top 20)")
    print("═" * 80)

    pair_counter = Counter()
    for d in draws:
        nums = d['numbers']
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                pair_counter[(nums[i], nums[j])] += 1

    expected_pair = N * comb(PICK, 2) / comb(POOL, 2)
    print(f"\n  期望每對出現次數: {expected_pair:.1f}")
    print(f"\n  Top 20 最高頻二合:")
    for rank, ((a, b), count) in enumerate(pair_counter.most_common(20)):
        ratio = count / expected_pair
        print(f"    #{rank+1:2d} ({a:2d}, {b:2d}): {count}次 ({ratio:.2f}x 期望)")

    print(f"\n  Bottom 10 最低頻二合:")
    for rank, ((a, b), count) in enumerate(pair_counter.most_common()[-10:]):
        ratio = count / expected_pair
        print(f"    ({a:2d}, {b:2d}): {count}次 ({ratio:.2f}x 期望)")

    # ══════════════════════════════════════════
    # PART 5: 時間衰減穩定性 (Edge 隨時間變化)
    # ══════════════════════════════════════════
    print("\n" + "═" * 80)
    print("PART 5: Edge 時間衰減分析 (滾動 300 期窗口)")
    print("═" * 80)

    for sname, sfn in strategies_to_test.items():
        print(f"\n▶ {sname} 滾動 Edge:")

        rolling_window = 300
        edges_over_time = []

        for start in range(max(200, N - 3000), N - rolling_window, rolling_window):
            end = start + rolling_window
            ge2 = 0
            for i in range(start, end):
                history = draws[:i]
                prediction = sfn(history)
                actual = set(draws[i]['numbers'])
                if len(set(prediction) & actual) >= 2:
                    ge2 += 1
            rate = ge2 / rolling_window
            edge = rate - BASELINE_1BET_GE2
            period_label = f"{draws[start]['date']}~{draws[min(end-1, N-1)]['date']}"
            edges_over_time.append((period_label, edge))

        for label, edge in edges_over_time:
            marker = "✅" if edge > 0 else "❌"
            bar = "█" * max(0, int(edge * 200)) if edge > 0 else "░" * max(0, int(-edge * 200))
            print(f"    {label:30s} Edge={edge*100:+.3f}% {marker} {bar}")

        pos_count = sum(1 for _, e in edges_over_time if e > 0)
        total_windows = len(edges_over_time)
        print(f"    正 Edge 比例: {pos_count}/{total_windows} = {pos_count/max(total_windows,1)*100:.1f}%")

    # ══════════════════════════════════════════
    # Summary
    # ══════════════════════════════════════════
    print("\n" + "═" * 80)
    print("完成。所有結果已輸出至終端。")
    print("═" * 80)


if __name__ == '__main__':
    main()
