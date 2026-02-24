#!/usr/bin/env python3
"""
39樂合彩 v2 — 全面回測腳本
=========================
移植 Top-5 驗證策略 + 6 個 Baseline 至 39 Lotto (Daily 539 數據)

嚴格防數據洩漏：history = draws[:i], actual = draws[i]

指標:
  M1: 命中數均值
  M2: ≥2命中率, ≥3命中率
  M3: Edge vs Random
  M4: Jaccard 相似度均值
  M7: 覆蓋效率 (多注)

回測窗口: 150 / 500 / 1500 / 3000 / 全期
"""

import json
import math
import sqlite3
import sys
import os
import numpy as np
from collections import Counter, defaultdict
from datetime import datetime

# ═══════════════════════════════════════════════
#  資料載入
# ═══════════════════════════════════════════════

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_api', 'data', 'lottery_v2.db')
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_v2.db')

def load_draws():
    """載入 DAILY_539 所有歷史開獎，按日期排序 (old→new)"""
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
        draws.append({
            'draw': draw_id,
            'date': date,
            'numbers': sorted(nums)  # 確保排序
        })
    return draws


# ═══════════════════════════════════════════════
#  數學工具
# ═══════════════════════════════════════════════

def comb(n, k):
    return math.comb(n, k)

# 精確基準
POOL = 39
PICK = 5

def exact_baseline_single(min_hits):
    """單注預測5個號碼，≥min_hits 命中的精確機率"""
    total = comb(POOL, PICK)
    p = 0.0
    for k in range(min_hits, PICK + 1):
        p += comb(PICK, k) * comb(POOL - PICK, PICK - k) / total
    return p

def n_bet_baseline(n_bets, min_hits):
    """N注獨立近似: 1 - (1-p_single)^N"""
    p1 = exact_baseline_single(min_hits)
    return 1.0 - (1.0 - p1) ** n_bets

BASELINE_1BET_GE2 = exact_baseline_single(2)  # ~11.40%
BASELINE_1BET_GE3 = exact_baseline_single(3)  # ~1.00%


# ═══════════════════════════════════════════════
#  策略實作 (嚴格使用 history[:i] 做為輸入)
# ═══════════════════════════════════════════════

class Strategy:
    """策略基類"""
    name = "base"

    def predict(self, history, n=PICK):
        """
        history: list of dicts with 'numbers' key, 時間順序 old→new
        返回: list of integers (sorted), 長度 = n
        """
        raise NotImplementedError


class RandomStrategy(Strategy):
    """B1: 純隨機"""
    name = "B1_Random"

    def __init__(self, seed=None):
        self.rng = np.random.RandomState(seed)

    def predict(self, history, n=PICK):
        return sorted(self.rng.choice(range(1, POOL + 1), size=n, replace=False).tolist())


class HotStrategy(Strategy):
    """B3: 熱號策略 - 近 window 期最高頻"""
    name = "B3_Hot"

    def __init__(self, window=50):
        self.window = window
        self.name = f"B3_Hot_w{window}"

    def predict(self, history, n=PICK):
        recent = history[-self.window:] if len(history) >= self.window else history
        counter = Counter()
        for d in recent:
            for num in d['numbers']:
                counter[num] += 1
        # 取最高頻的 n 個
        top = [x[0] for x in counter.most_common(n)]
        if len(top) < n:
            # 補齊
            remaining = [x for x in range(1, POOL + 1) if x not in top]
            top.extend(remaining[:n - len(top)])
        return sorted(top[:n])


class ColdStrategy(Strategy):
    """B4: 冷號策略 - 近 window 期最低頻/最久未出"""
    name = "B4_Cold"

    def __init__(self, window=100):
        self.window = window
        self.name = f"B4_Cold_w{window}"

    def predict(self, history, n=PICK):
        recent = history[-self.window:] if len(history) >= self.window else history
        counter = Counter()
        for num in range(1, POOL + 1):
            counter[num] = 0
        for d in recent:
            for num in d['numbers']:
                counter[num] += 1
        # 取最低頻的 n 個
        bottom = [x[0] for x in counter.most_common()[::-1][:n]]
        return sorted(bottom[:n])


class RepeatStrategy(Strategy):
    """B5: 前期重複"""
    name = "B5_Repeat"

    def predict(self, history, n=PICK):
        if not history:
            return list(range(1, n + 1))
        return sorted(history[-1]['numbers'][:n])


class MeanReversionStrategy(Strategy):
    """B6: 均勻頻率回歸 - 選最接近期望頻率 1/39 的號碼"""
    name = "B6_MeanReversion"

    def predict(self, history, n=PICK):
        if len(history) < 10:
            return list(range(1, n + 1))
        counter = Counter()
        for num in range(1, POOL + 1):
            counter[num] = 0
        for d in history:
            for num in d['numbers']:
                counter[num] += 1
        expected = len(history) * PICK / POOL
        # 按距離期望值的距離排序 (最接近的優先)
        scored = [(abs(counter[num] - expected), num) for num in range(1, POOL + 1)]
        scored.sort(key=lambda x: (x[0], x[1]))
        return sorted([x[1] for x in scored[:n]])


# ───── 核心策略 ─────

class FourierRhythmStrategy(Strategy):
    """S1: 傅立葉節奏 (FFT) — 移植自威力彩 Fourier Rhythm"""
    name = "S1_Fourier"

    def __init__(self, window=500):
        self.window = window
        self.name = f"S1_Fourier_w{window}"

    def predict(self, history, n=PICK):
        recent = history[-self.window:] if len(history) >= self.window else history
        if len(recent) < 30:
            return list(range(1, n + 1))

        scores = {}
        for num in range(1, POOL + 1):
            # 建構二值時序: 1 出現, 0 未出現
            series = np.array([1 if num in d['numbers'] else 0 for d in recent], dtype=float)

            # FFT
            fft_vals = np.fft.rfft(series)
            power = np.abs(fft_vals) ** 2

            # 排除 DC 分量 (index 0)
            if len(power) > 1:
                # 取最強非零頻率的相位
                dominant_idx = np.argmax(power[1:]) + 1
                phase = np.angle(fft_vals[dominant_idx])
                freq = dominant_idx / len(series)

                # 預測下一時間步的值
                t_next = len(series)
                predicted_value = np.abs(fft_vals[dominant_idx]) * np.cos(2 * np.pi * freq * t_next + phase)

                # 綜合分數: FFT 預測 + 基礎頻率
                base_freq = series.mean()
                scores[num] = base_freq + 0.3 * predicted_value / (len(series) ** 0.5)
            else:
                scores[num] = 0

        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return sorted([x[0] for x in ranked[:n]])


class DeviationEchoStrategy(Strategy):
    """S2: 偏差+Lag-2 回聲 (P0) — 移植自大樂透/威力彩 P0"""
    name = "S2_P0_DevEcho"

    def __init__(self, window=100):
        self.window = window

    def predict(self, history, n=PICK):
        if len(history) < 10:
            return list(range(1, n + 1))

        recent = history[-self.window:] if len(history) >= self.window else history

        # 頻率偏差分數
        counter = Counter()
        for num in range(1, POOL + 1):
            counter[num] = 0
        for d in recent:
            for num in d['numbers']:
                counter[num] += 1

        expected = len(recent) * PICK / POOL
        deviation_scores = {}
        for num in range(1, POOL + 1):
            deviation_scores[num] = counter[num] - expected

        # Lag-2 回聲: 前兩期出現的號碼獲得 1.5x 提升
        lag2_numbers = set()
        if len(history) >= 2:
            lag2_numbers = set(history[-2]['numbers'])

        final_scores = {}
        for num in range(1, POOL + 1):
            score = deviation_scores[num]
            if num in lag2_numbers:
                score *= 1.5  # Lag-2 echo boost
            final_scores[num] = score

        ranked = sorted(final_scores.items(), key=lambda x: -x[1])
        return sorted([x[0] for x in ranked[:n]])


class ColdTwinStrategy(Strategy):
    """S3: 冷號互補 — 移植自威力彩 Cold Number Twin"""
    name = "S3_ColdTwin"

    def __init__(self, window=100):
        self.window = window

    def predict(self, history, n=PICK):
        if len(history) < 10:
            return list(range(1, n + 1))

        recent = history[-self.window:] if len(history) >= self.window else history

        # 計算每個號碼的缺席期數 (gap)
        last_seen = {}
        for i, d in enumerate(recent):
            for num in d['numbers']:
                last_seen[num] = i

        current = len(recent)
        gaps = {}
        for num in range(1, POOL + 1):
            if num in last_seen:
                gaps[num] = current - last_seen[num]
            else:
                gaps[num] = current + 1  # 從未出現 = 最大 gap

        # 選擇 gap 最大的 n 個 (最冷)
        ranked = sorted(gaps.items(), key=lambda x: (-x[1], x[0]))
        return sorted([x[0] for x in ranked[:n]])


class MarkovStrategy(Strategy):
    """S4: Markov 轉移矩陣 (w=30) — 移植自大樂透 Markov"""
    name = "S4_Markov"

    def __init__(self, window=30):
        self.window = window
        self.name = f"S4_Markov_w{window}"

    def predict(self, history, n=PICK):
        recent = history[-self.window:] if len(history) >= self.window else history
        if len(recent) < 5:
            return list(range(1, n + 1))

        # 建構 39×39 轉移矩陣
        transition = np.zeros((POOL, POOL))
        for i in range(len(recent) - 1):
            current_nums = recent[i]['numbers']
            next_nums = recent[i + 1]['numbers']
            for a in current_nums:
                for b in next_nums:
                    transition[a - 1][b - 1] += 1

        # 正規化
        row_sums = transition.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1
        transition = transition / row_sums

        # 用最近一期的號碼做為狀態，計算下一期各號碼的轉移機率
        last_nums = recent[-1]['numbers']
        scores = np.zeros(POOL)
        for num in last_nums:
            scores += transition[num - 1]

        # 排序取 Top n
        ranked_indices = np.argsort(-scores)
        top_nums = [int(idx + 1) for idx in ranked_indices[:n]]
        return sorted(top_nums)


class TripleStrikeStrategy(Strategy):
    """S5: Triple Strike 移植 (Fourier + Cold + TailBalance) — 大樂透冠軍"""
    name = "S5_TripleStrike"

    def __init__(self, fourier_window=500, cold_window=100):
        self.fourier_window = fourier_window
        self.cold_window = cold_window

    def predict(self, history, n=PICK):
        if len(history) < 30:
            return list(range(1, n + 1))

        # ── 訊號 1: 傅立葉 ──
        recent_f = history[-self.fourier_window:] if len(history) >= self.fourier_window else history
        fourier_scores = {}
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

        # ── 訊號 2: 冷號 (gap) ──
        recent_c = history[-self.cold_window:] if len(history) >= self.cold_window else history
        last_seen = {}
        for i, d in enumerate(recent_c):
            for num in d['numbers']:
                last_seen[num] = i
        current = len(recent_c)
        cold_scores = {}
        for num in range(1, POOL + 1):
            if num in last_seen:
                cold_scores[num] = (current - last_seen[num]) / current
            else:
                cold_scores[num] = 1.0

        # ── 訊號 3: 尾數平衡 ──
        recent_tail = history[-100:] if len(history) >= 100 else history
        tail_counter = Counter()
        for d in recent_tail:
            for num in d['numbers']:
                tail_counter[num % 10] += 1
        total_tails = sum(tail_counter.values())
        if total_tails == 0:
            total_tails = 1
        tail_deficit = {}
        for tail in range(10):
            expected_ratio = 1.0 / 10
            actual_ratio = tail_counter[tail] / total_tails
            tail_deficit[tail] = expected_ratio - actual_ratio  # 正值 = 偏低

        tail_scores = {}
        for num in range(1, POOL + 1):
            tail_scores[num] = tail_deficit[num % 10]

        # ── 綜合 ──
        combined = {}
        for num in range(1, POOL + 1):
            combined[num] = (
                0.5 * fourier_scores.get(num, 0) +
                0.3 * cold_scores.get(num, 0) +
                0.2 * tail_scores.get(num, 0)
            )

        ranked = sorted(combined.items(), key=lambda x: -x[1])
        return sorted([x[0] for x in ranked[:n]])


class BayesianStrategy(Strategy):
    """S6: Bayesian Dirichlet-Multinomial"""
    name = "S6_Bayesian"

    def __init__(self, alpha=1.0, window=200):
        self.alpha = alpha
        self.window = window

    def predict(self, history, n=PICK):
        recent = history[-self.window:] if len(history) >= self.window else history
        if len(recent) < 5:
            return list(range(1, n + 1))

        # Dirichlet 先驗 alpha + 觀測計數
        counter = Counter()
        for num in range(1, POOL + 1):
            counter[num] = 0
        for d in recent:
            for num in d['numbers']:
                counter[num] += 1

        # 後驗期望: (alpha + count_i) / (39*alpha + total_count)
        total = sum(counter.values())
        posterior = {}
        for num in range(1, POOL + 1):
            posterior[num] = (self.alpha + counter[num]) / (POOL * self.alpha + total)

        ranked = sorted(posterior.items(), key=lambda x: -x[1])
        return sorted([x[0] for x in ranked[:n]])


class ConditionalEntropyStrategy(Strategy):
    """S7: 條件熵策略 - 選擇條件熵最低(最可預測)的號碼"""
    name = "S7_CondEntropy"

    def __init__(self, window=200):
        self.window = window

    def predict(self, history, n=PICK):
        recent = history[-self.window:] if len(history) >= self.window else history
        if len(recent) < 20:
            return list(range(1, n + 1))

        # 對每個號碼，計算 H(X_t | X_{t-1}) — 是否出現的條件熵
        scores = {}
        for num in range(1, POOL + 1):
            series = [1 if num in d['numbers'] else 0 for d in recent]

            # 計算 P(X_t | X_{t-1}) 的四個轉移機率
            trans = {'00': 0, '01': 0, '10': 0, '11': 0}
            for i in range(1, len(series)):
                key = f"{series[i-1]}{series[i]}"
                trans[key] += 1

            # 條件熵
            h_cond = 0.0
            for prev in [0, 1]:
                total = trans[f'{prev}0'] + trans[f'{prev}1']
                if total == 0:
                    continue
                for curr in [0, 1]:
                    p = trans[f'{prev}{curr}'] / total
                    if p > 0:
                        h_cond -= (total / (len(series) - 1)) * p * np.log2(p)

            # 低條件熵 = 更可預測
            # 同時考慮上一期的狀態預測
            last_state = series[-1]
            total_from_last = trans[f'{last_state}0'] + trans[f'{last_state}1']
            if total_from_last > 0:
                p_appear = trans[f'{last_state}1'] / total_from_last
            else:
                p_appear = 0.5

            scores[num] = p_appear  # 出現機率

        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return sorted([x[0] for x in ranked[:n]])


class GapAnalysisStrategy(Strategy):
    """S8: Gap 分析策略 - 基於缺席長度的回歸預測"""
    name = "S8_GapAnalysis"

    def __init__(self, window=300):
        self.window = window

    def predict(self, history, n=PICK):
        if len(history) < 20:
            return list(range(1, n + 1))

        recent = history[-self.window:] if len(history) >= self.window else history

        # 計算每個號碼的歷史 gap 分布
        scores = {}
        for num in range(1, POOL + 1):
            appearances = []
            for i, d in enumerate(recent):
                if num in d['numbers']:
                    appearances.append(i)

            if len(appearances) < 2:
                # 太少出現 → 高 gap 分數
                scores[num] = 1.0
                continue

            # 計算平均 gap
            gaps = [appearances[i+1] - appearances[i] for i in range(len(appearances) - 1)]
            avg_gap = np.mean(gaps)

            # 當前 gap
            current_gap = len(recent) - appearances[-1]

            # 分數: current_gap / avg_gap — 比值越大，越"過期"
            if avg_gap > 0:
                scores[num] = current_gap / avg_gap
            else:
                scores[num] = 0

        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return sorted([x[0] for x in ranked[:n]])


class HMMStrategy(Strategy):
    """S9: 簡化 HMM - 冷熱態偵測"""
    name = "S9_HMM_Regime"

    def __init__(self, window=100):
        self.window = window

    def predict(self, history, n=PICK):
        recent = history[-self.window:] if len(history) >= self.window else history
        if len(recent) < 20:
            return list(range(1, n + 1))

        # 偵測當前 regime: 用近期的號碼分散度判斷
        half = len(recent) // 2
        first_half = recent[:half]
        second_half = recent[half:]

        # 計算兩半的號碼分布
        counter1 = Counter()
        counter2 = Counter()
        for d in first_half:
            for num in d['numbers']:
                counter1[num] += 1
        for d in second_half:
            for num in d['numbers']:
                counter2[num] += 1

        # 判斷 regime: 如果近期分布更集中 → hot regime → 選高頻
        # 如果近期分布更分散 → cold regime → 選冷號
        entropy1 = 0
        total1 = sum(counter1.values())
        for num in range(1, POOL + 1):
            p = counter1.get(num, 0) / max(total1, 1)
            if p > 0:
                entropy1 -= p * np.log2(p)

        entropy2 = 0
        total2 = sum(counter2.values())
        for num in range(1, POOL + 1):
            p = counter2.get(num, 0) / max(total2, 1)
            if p > 0:
                entropy2 -= p * np.log2(p)

        # 分數融合
        scores = {}
        if entropy2 < entropy1:
            # 集中化趨勢 → 偏向熱號
            for num in range(1, POOL + 1):
                scores[num] = counter2.get(num, 0) / max(total2, 1)
        else:
            # 分散化趨勢 → 偏向冷號
            for num in range(1, POOL + 1):
                freq = counter2.get(num, 0) / max(total2, 1)
                scores[num] = 1.0 / POOL - freq  # 偏差越大越冷

        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return sorted([x[0] for x in ranked[:n]])


class ZoneBalanceStrategy(Strategy):
    """S10: 區域平衡策略"""
    name = "S10_ZoneBalance"

    def __init__(self, window=100):
        self.window = window

    def predict(self, history, n=PICK):
        recent = history[-self.window:] if len(history) >= self.window else history
        if len(recent) < 10:
            return list(range(1, n + 1))

        # 三區: 1-13, 14-26, 27-39
        zones = {0: range(1, 14), 1: range(14, 27), 2: range(27, 40)}

        # 計算各區最近頻率偏差
        zone_counter = Counter()
        num_counter = Counter()
        for d in recent:
            for num in d['numbers']:
                num_counter[num] += 1
                if num <= 13:
                    zone_counter[0] += 1
                elif num <= 26:
                    zone_counter[1] += 1
                else:
                    zone_counter[2] += 1

        total = sum(zone_counter.values())
        expected_zone = total / 3

        # 偏低的區域應該多選
        zone_deficit = {}
        for z in range(3):
            zone_deficit[z] = expected_zone - zone_counter.get(z, 0)

        # 各區分配名額 (按 deficit 加權)
        total_deficit = sum(max(0, d) for d in zone_deficit.values())
        if total_deficit == 0:
            allocations = {0: 2, 1: 2, 2: 1}  # 預設 2-2-1
        else:
            raw = {z: max(0, zone_deficit[z]) / total_deficit * n for z in range(3)}
            allocations = {z: max(1, round(raw[z])) for z in range(3)}
            # 修正為剛好 n 個
            while sum(allocations.values()) > n:
                max_z = max(allocations, key=allocations.get)
                allocations[max_z] -= 1
            while sum(allocations.values()) < n:
                min_z = min(allocations, key=allocations.get)
                allocations[min_z] += 1

        result = []
        for z in range(3):
            zone_nums = list(zones[z])
            # 排序: 該區中頻率偏差最大的號碼
            expected_num = len(recent) * PICK / POOL
            scored = [(num_counter.get(num, 0) - expected_num, num) for num in zone_nums]
            scored.sort(key=lambda x: -x[0])
            result.extend([x[1] for x in scored[:allocations.get(z, 0)]])

        return sorted(result[:n])


class PairFrequencyStrategy(Strategy):
    """S11: 號碼對頻率策略 - 基於高頻二元組"""
    name = "S11_PairFreq"

    def __init__(self, window=200):
        self.window = window

    def predict(self, history, n=PICK):
        recent = history[-self.window:] if len(history) >= self.window else history
        if len(recent) < 20:
            return list(range(1, n + 1))

        # 計算所有二元組的出現頻率
        pair_counter = Counter()
        for d in recent:
            nums = d['numbers']
            for i in range(len(nums)):
                for j in range(i + 1, len(nums)):
                    pair_counter[(nums[i], nums[j])] += 1

        # 用號碼被高頻 pair 涵蓋的次數做為分數
        num_scores = Counter()
        for (a, b), count in pair_counter.most_common(50):  # Top 50 pairs
            num_scores[a] += count
            num_scores[b] += count

        ranked = num_scores.most_common(n)
        result = [x[0] for x in ranked]

        # 補齊
        if len(result) < n:
            remaining = [x for x in range(1, POOL + 1) if x not in result]
            result.extend(remaining[:n - len(result)])

        return sorted(result[:n])


# ═══════════════════════════════════════════════
#  多注策略 (正交)
# ═══════════════════════════════════════════════

class OrthogonalMultiBet:
    """正交多注: 每注使用不同理論來源"""

    def __init__(self, strategies):
        """strategies: list of Strategy instances"""
        self.strategies = strategies
        self.n_bets = len(strategies)
        self.name = f"Ortho_{self.n_bets}bet"

    def predict_all(self, history):
        """返回 list of lists"""
        predictions = []
        for s in self.strategies:
            pred = s.predict(history, PICK)
            predictions.append(pred)
        return predictions


# ═══════════════════════════════════════════════
#  回測引擎
# ═══════════════════════════════════════════════

def evaluate_hits(prediction, actual):
    """計算命中數"""
    return len(set(prediction) & set(actual))

def jaccard(prediction, actual):
    """Jaccard 相似度"""
    s1, s2 = set(prediction), set(actual)
    inter = len(s1 & s2)
    union = len(s1 | s2)
    return inter / union if union > 0 else 0

def run_backtest_single(strategy, draws, test_periods, min_train=100):
    """
    單注策略回測

    draws: 全部開獎資料 (old→new)
    test_periods: 使用最後 N 期做為測試期
    min_train: 最小訓練期數
    """
    total = len(draws)
    start_idx = max(min_train, total - test_periods)

    hits_list = []
    ge2_count = 0
    ge3_count = 0
    ge4_count = 0
    jaccard_list = []
    test_count = 0

    for i in range(start_idx, total):
        history = draws[:i]  # 嚴格: 不包含 i
        prediction = strategy.predict(history, PICK)
        actual = draws[i]['numbers']

        hits = evaluate_hits(prediction, actual)
        hits_list.append(hits)
        jaccard_list.append(jaccard(prediction, actual))

        if hits >= 2:
            ge2_count += 1
        if hits >= 3:
            ge3_count += 1
        if hits >= 4:
            ge4_count += 1
        test_count += 1

    if test_count == 0:
        return None

    ge2_rate = ge2_count / test_count
    ge3_rate = ge3_count / test_count
    ge4_rate = ge4_count / test_count

    return {
        'strategy': strategy.name,
        'test_periods': test_count,
        'avg_hits': np.mean(hits_list),
        'ge2_rate': ge2_rate,
        'ge2_edge': ge2_rate - BASELINE_1BET_GE2,
        'ge3_rate': ge3_rate,
        'ge3_edge': ge3_rate - BASELINE_1BET_GE3,
        'ge4_rate': ge4_rate,
        'avg_jaccard': np.mean(jaccard_list),
        'hits_dist': dict(Counter(hits_list))
    }


def run_backtest_multi(multi_strategy, draws, test_periods, min_train=100):
    """
    多注策略回測
    每期 N 注，只要任一注 ≥K 就算命中
    """
    total = len(draws)
    start_idx = max(min_train, total - test_periods)

    n_bets = multi_strategy.n_bets
    baseline_ge2 = n_bet_baseline(n_bets, 2)
    baseline_ge3 = n_bet_baseline(n_bets, 3)

    any_ge2_count = 0
    any_ge3_count = 0
    best_hits_list = []
    total_coverage_list = []
    test_count = 0

    for i in range(start_idx, total):
        history = draws[:i]
        predictions = multi_strategy.predict_all(history)
        actual = draws[i]['numbers']
        actual_set = set(actual)

        best_hits = 0
        all_nums = set()
        for pred in predictions:
            hits = len(set(pred) & actual_set)
            best_hits = max(best_hits, hits)
            all_nums.update(pred)

        best_hits_list.append(best_hits)
        total_coverage_list.append(len(all_nums))

        if best_hits >= 2:
            any_ge2_count += 1
        if best_hits >= 3:
            any_ge3_count += 1

        test_count += 1

    if test_count == 0:
        return None

    any_ge2_rate = any_ge2_count / test_count
    any_ge3_rate = any_ge3_count / test_count

    return {
        'strategy': multi_strategy.name,
        'n_bets': n_bets,
        'test_periods': test_count,
        'avg_best_hits': np.mean(best_hits_list),
        'any_ge2_rate': any_ge2_rate,
        'any_ge2_edge': any_ge2_rate - baseline_ge2,
        'any_ge3_rate': any_ge3_rate,
        'any_ge3_edge': any_ge3_rate - baseline_ge3,
        'avg_coverage': np.mean(total_coverage_list),
        'coverage_ratio': np.mean(total_coverage_list) / POOL,
        'baseline_ge2': baseline_ge2,
        'baseline_ge3': baseline_ge3,
        'best_hits_dist': dict(Counter(best_hits_list))
    }


# ═══════════════════════════════════════════════
#  主程式
# ═══════════════════════════════════════════════

def main():
    print("=" * 80)
    print("39樂合彩 v2 — 全面回測系統")
    print(f"啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # 載入資料
    draws = load_draws()
    print(f"\n📊 載入 {len(draws)} 期 DAILY_539 歷史資料")
    print(f"   期間: {draws[0]['date']} ~ {draws[-1]['date']}")

    # 定義所有策略
    single_strategies = [
        # Baselines
        RandomStrategy(seed=42),
        HotStrategy(window=30),
        HotStrategy(window=50),
        HotStrategy(window=100),
        ColdStrategy(window=50),
        ColdStrategy(window=100),
        RepeatStrategy(),
        MeanReversionStrategy(),
        # Core strategies
        FourierRhythmStrategy(window=500),
        FourierRhythmStrategy(window=300),
        FourierRhythmStrategy(window=100),
        DeviationEchoStrategy(window=100),
        DeviationEchoStrategy(window=50),
        ColdTwinStrategy(window=100),
        ColdTwinStrategy(window=50),
        MarkovStrategy(window=30),
        MarkovStrategy(window=50),
        TripleStrikeStrategy(fourier_window=500, cold_window=100),
        BayesianStrategy(alpha=1.0, window=200),
        ConditionalEntropyStrategy(window=200),
        GapAnalysisStrategy(window=300),
        HMMStrategy(window=100),
        ZoneBalanceStrategy(window=100),
        PairFrequencyStrategy(window=200),
    ]

    # 定義回測窗口
    windows = [150, 500, 1500, 3000, len(draws) - 100]  # 全期 = 最大 - min_train

    print(f"\n🔬 回測窗口: {windows}")
    print(f"📐 單注基準: ≥2命中={BASELINE_1BET_GE2*100:.4f}%, ≥3命中={BASELINE_1BET_GE3*100:.4f}%")

    all_results = {}

    # ── Phase 1: 單注回測 ──
    print("\n" + "═" * 80)
    print("Phase 1: 單注策略回測")
    print("═" * 80)

    for window in windows:
        print(f"\n{'─'*60}")
        print(f"📏 回測窗口: 最後 {window} 期")
        print(f"{'─'*60}")

        results = []
        for strategy in single_strategies:
            result = run_backtest_single(strategy, draws, window)
            if result:
                results.append(result)
                edge_marker = " ✅" if result['ge2_edge'] > 0 else " ❌"
                edge3_marker = " ✅" if result['ge3_edge'] > 0 else " ❌"
                print(f"  {strategy.name:30s} | ≥2: {result['ge2_rate']*100:6.2f}% (Edge {result['ge2_edge']*100:+.2f}%){edge_marker} | ≥3: {result['ge3_rate']*100:6.3f}% (Edge {result['ge3_edge']*100:+.3f}%){edge3_marker} | Jaccard: {result['avg_jaccard']:.4f}")

        all_results[f'single_{window}'] = results

        # 排序輸出
        print(f"\n  📊 ≥2命中率排名 (窗口={window}):")
        sorted_ge2 = sorted(results, key=lambda x: -x['ge2_edge'])
        for i, r in enumerate(sorted_ge2[:10]):
            marker = "🏆" if r['ge2_edge'] > 0 else "  "
            print(f"    {marker} #{i+1} {r['strategy']:30s} Edge={r['ge2_edge']*100:+.3f}%")

        print(f"\n  📊 ≥3命中率排名 (窗口={window}):")
        sorted_ge3 = sorted(results, key=lambda x: -x['ge3_edge'])
        for i, r in enumerate(sorted_ge3[:10]):
            marker = "🏆" if r['ge3_edge'] > 0 else "  "
            print(f"    {marker} #{i+1} {r['strategy']:30s} Edge={r['ge3_edge']*100:+.4f}%")

    # ── Phase 2: 多注策略回測 ──
    print("\n" + "═" * 80)
    print("Phase 2: 多注正交策略回測")
    print("═" * 80)

    # 定義多注組合
    multi_strategies = [
        OrthogonalMultiBet([  # 2注: P0 + Cold
            DeviationEchoStrategy(window=100),
            ColdTwinStrategy(window=100),
        ]),
        OrthogonalMultiBet([  # 2注: Fourier + Markov
            FourierRhythmStrategy(window=500),
            MarkovStrategy(window=30),
        ]),
        OrthogonalMultiBet([  # 2注: P0 + Fourier
            DeviationEchoStrategy(window=100),
            FourierRhythmStrategy(window=500),
        ]),
        OrthogonalMultiBet([  # 3注: P0 + Cold + Markov
            DeviationEchoStrategy(window=100),
            ColdTwinStrategy(window=100),
            MarkovStrategy(window=30),
        ]),
        OrthogonalMultiBet([  # 3注: Triple Strike 式
            FourierRhythmStrategy(window=500),
            ColdTwinStrategy(window=100),
            ZoneBalanceStrategy(window=100),
        ]),
        OrthogonalMultiBet([  # 3注: Fourier + P0 + Cold
            FourierRhythmStrategy(window=500),
            DeviationEchoStrategy(window=100),
            ColdTwinStrategy(window=100),
        ]),
        OrthogonalMultiBet([  # 5注 正交全家族
            FourierRhythmStrategy(window=500),
            DeviationEchoStrategy(window=100),
            ColdTwinStrategy(window=100),
            MarkovStrategy(window=30),
            TripleStrikeStrategy(),
        ]),
    ]

    # 命名
    multi_strategies[0].name = "2bet_P0+Cold"
    multi_strategies[1].name = "2bet_Fourier+Markov"
    multi_strategies[2].name = "2bet_P0+Fourier"
    multi_strategies[3].name = "3bet_P0+Cold+Markov"
    multi_strategies[4].name = "3bet_Fourier+Cold+Zone"
    multi_strategies[5].name = "3bet_Fourier+P0+Cold"
    multi_strategies[6].name = "5bet_FullOrthogonal"

    for window in windows:
        print(f"\n{'─'*60}")
        print(f"📏 多注回測窗口: 最後 {window} 期")
        print(f"{'─'*60}")

        results = []
        for ms in multi_strategies:
            result = run_backtest_multi(ms, draws, window)
            if result:
                results.append(result)
                edge2_marker = " ✅" if result['any_ge2_edge'] > 0 else " ❌"
                edge3_marker = " ✅" if result['any_ge3_edge'] > 0 else " ❌"
                print(f"  {ms.name:30s} ({ms.n_bets}注) | ≥2: {result['any_ge2_rate']*100:6.2f}% (Edge {result['any_ge2_edge']*100:+.2f}%){edge2_marker} | ≥3: {result['any_ge3_rate']*100:6.3f}% (Edge {result['any_ge3_edge']*100:+.3f}%){edge3_marker} | 覆蓋: {result['coverage_ratio']*100:.1f}%")

        all_results[f'multi_{window}'] = results

    # ── Phase 3: 隨機基準 Monte Carlo 驗證 ──
    print("\n" + "═" * 80)
    print("Phase 3: Monte Carlo 隨機基準驗證 (100,000 次)")
    print("═" * 80)

    MC_RUNS = 100000
    rng = np.random.RandomState(42)
    mc_ge2 = 0
    mc_ge3 = 0
    for _ in range(MC_RUNS):
        pred = sorted(rng.choice(range(1, POOL + 1), size=PICK, replace=False))
        actual_idx = rng.randint(0, len(draws))
        actual = draws[actual_idx]['numbers']
        hits = len(set(pred) & set(actual))
        if hits >= 2:
            mc_ge2 += 1
        if hits >= 3:
            mc_ge3 += 1

    print(f"  Monte Carlo ≥2: {mc_ge2/MC_RUNS*100:.4f}% (理論: {BASELINE_1BET_GE2*100:.4f}%)")
    print(f"  Monte Carlo ≥3: {mc_ge3/MC_RUNS*100:.4f}% (理論: {BASELINE_1BET_GE3*100:.4f}%)")

    # ── Phase 4: Lag-2 回聲率統計 ──
    print("\n" + "═" * 80)
    print("Phase 4: Lag-2 回聲率驗證")
    print("═" * 80)

    lag2_count = 0
    lag2_total = 0
    lag2_avg_overlap = []
    theoretical_lag2 = 1 - math.comb(POOL - PICK, PICK) / math.comb(POOL, PICK)

    for i in range(2, len(draws)):
        lag2_nums = set(draws[i-2]['numbers'])
        current_nums = set(draws[i]['numbers'])
        overlap = len(lag2_nums & current_nums)
        if overlap > 0:
            lag2_count += 1
        lag2_avg_overlap.append(overlap)
        lag2_total += 1

    lag2_rate = lag2_count / lag2_total
    print(f"  實測 Lag-2 回聲率: {lag2_rate*100:.2f}% ({lag2_count}/{lag2_total})")
    print(f"  理論值 (≥1重疊): {theoretical_lag2*100:.2f}%")
    print(f"  差異: {(lag2_rate - theoretical_lag2)*100:+.2f}%")
    print(f"  平均重疊數: {np.mean(lag2_avg_overlap):.3f}")
    print(f"  理論期望重疊: {PICK * PICK / POOL:.3f}")

    # Lag-1 回聲也計算
    lag1_count = 0
    lag1_total = 0
    for i in range(1, len(draws)):
        lag1_nums = set(draws[i-1]['numbers'])
        current_nums = set(draws[i]['numbers'])
        if len(lag1_nums & current_nums) > 0:
            lag1_count += 1
        lag1_total += 1
    lag1_rate = lag1_count / lag1_total
    print(f"\n  實測 Lag-1 回聲率: {lag1_rate*100:.2f}%")
    print(f"  理論值: {theoretical_lag2*100:.2f}% (同公式)")
    print(f"  差異: {(lag1_rate - theoretical_lag2)*100:+.2f}%")

    # ── Phase 5: 穩定性分析 ──
    print("\n" + "═" * 80)
    print("Phase 5: 跨窗口穩定性分析")
    print("═" * 80)

    core_strategies_names = [
        'S1_Fourier_w500', 'S2_P0_DevEcho', 'S3_ColdTwin',
        'S4_Markov_w30', 'S5_TripleStrike'
    ]

    print(f"\n  {'策略':<30s} | {'150p':>8s} | {'500p':>8s} | {'1500p':>8s} | {'3000p':>8s} | {'全期':>8s} | 穩定性")
    print(f"  {'─'*30} | {'─'*8} | {'─'*8} | {'─'*8} | {'─'*8} | {'─'*8} | {'─'*10}")

    for sname in core_strategies_names:
        edges = []
        for window in windows:
            key = f'single_{window}'
            if key in all_results:
                found = [r for r in all_results[key] if r['strategy'] == sname]
                if found:
                    edges.append(found[0]['ge2_edge'] * 100)
                else:
                    edges.append(None)
            else:
                edges.append(None)

        # 穩定性判定
        valid_edges = [e for e in edges if e is not None]
        if len(valid_edges) >= 3:
            all_positive = all(e > 0 for e in valid_edges)
            if all_positive:
                stability = "✅ STABLE"
            elif valid_edges[-1] > 0 and valid_edges[-2] > 0:
                stability = "⚠️ PARTIAL"
            else:
                stability = "❌ UNSTABLE"

            # 檢測 SHORT_MOMENTUM
            if len(valid_edges) >= 3 and valid_edges[0] > 0 and valid_edges[-1] < 0:
                stability = "⚠️ SHORT_MOM"
        else:
            stability = "? INSUFFICIENT"

        edge_strs = []
        for e in edges:
            if e is not None:
                edge_strs.append(f"{e:+.3f}%")
            else:
                edge_strs.append("   N/A  ")

        print(f"  {sname:<30s} | {edge_strs[0]:>8s} | {edge_strs[1]:>8s} | {edge_strs[2]:>8s} | {edge_strs[3]:>8s} | {edge_strs[4]:>8s} | {stability}")

    # ── Phase 6: 二合分析 (pair-level) ──
    print("\n" + "═" * 80)
    print("Phase 6: 二合專項分析")
    print("═" * 80)

    # 每個策略預測的 5 個號碼可形成 C(5,2)=10 個二合組合
    # 只要其中一個二合中獎，就算二合命中
    # 這等效於 ≥2 命中
    print(f"  二合命中 ≡ ≥2命中，因此單注策略的 ≥2 Edge 即為二合 Edge")
    print(f"  二合隨機基準 (選2個號碼): {comb(PICK,2)/comb(POOL,2)*100:.4f}%")
    print(f"  預測5號中≥2命中基準: {BASELINE_1BET_GE2*100:.4f}%")

    # ── 總結 ──
    print("\n" + "═" * 80)
    print("═══ 最終結果彙整 ═══")
    print("═" * 80)

    # 全期結果排名
    full_key = f'single_{windows[-1]}'
    if full_key in all_results:
        print(f"\n📊 全期 ≥2命中 Edge 排名:")
        sorted_results = sorted(all_results[full_key], key=lambda x: -x['ge2_edge'])
        for i, r in enumerate(sorted_results):
            marker = "🏆" if r['ge2_edge'] > 0 else "❌"
            print(f"  {marker} #{i+1:2d} {r['strategy']:30s} | Rate={r['ge2_rate']*100:.3f}% | Edge={r['ge2_edge']*100:+.4f}% | ≥3 Edge={r['ge3_edge']*100:+.4f}%")

    # 多注全期排名
    full_multi_key = f'multi_{windows[-1]}'
    if full_multi_key in all_results:
        print(f"\n📊 全期多注 ≥3命中 Edge 排名:")
        sorted_multi = sorted(all_results[full_multi_key], key=lambda x: -x['any_ge3_edge'])
        for i, r in enumerate(sorted_multi):
            marker = "🏆" if r['any_ge3_edge'] > 0 else "❌"
            print(f"  {marker} #{i+1:2d} {r['strategy']:30s} ({r['n_bets']}注) | Rate={r['any_ge3_rate']*100:.3f}% | Edge={r['any_ge3_edge']*100:+.4f}% | 覆蓋={r['coverage_ratio']*100:.1f}%")

    # 保存結果
    output = {
        'meta': {
            'lottery': '39樂合彩 (DAILY_539)',
            'total_draws': len(draws),
            'date_range': f"{draws[0]['date']} ~ {draws[-1]['date']}",
            'baseline_1bet_ge2': BASELINE_1BET_GE2,
            'baseline_1bet_ge3': BASELINE_1BET_GE3,
            'timestamp': datetime.now().isoformat()
        },
        'lag2_analysis': {
            'measured_rate': lag2_rate,
            'theoretical_rate': theoretical_lag2,
            'delta': lag2_rate - theoretical_lag2,
            'avg_overlap': float(np.mean(lag2_avg_overlap)),
            'expected_overlap': PICK * PICK / POOL
        },
        'lag1_analysis': {
            'measured_rate': lag1_rate,
            'theoretical_rate': theoretical_lag2,
            'delta': lag1_rate - theoretical_lag2
        }
    }

    # Serialize results
    for key, results in all_results.items():
        serializable = []
        for r in results:
            sr = {}
            for k, v in r.items():
                if isinstance(v, (np.floating, np.integer)):
                    sr[k] = float(v)
                elif isinstance(v, dict):
                    sr[k] = {str(kk): int(vv) if isinstance(vv, (np.integer,)) else vv for kk, vv in v.items()}
                else:
                    sr[k] = v
            serializable.append(sr)
        output[key] = serializable

    output_path = os.path.join(os.path.dirname(__file__), '..', 'backtest_39lotto_comprehensive.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n💾 結果已保存至: {output_path}")

    return output


if __name__ == '__main__':
    main()
