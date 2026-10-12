#!/usr/bin/env python3
"""
大樂透 TS3+Markov4 增強方案全面回測
======================================
基於 115000015 檢討會議決議，實作並驗證所有優化方案。

Base:  TS3+Markov4 (4注, 已驗證 +1.23% edge)
P1-A:  Regime Indicator — 偵測冷/熱期，動態調權
P1-B:  Consecutive Pair Post-processing — 連號伴侶注入
P2-A:  Rank Diversity Constraint — 強制 rank 分散
P2-B:  5th Bet: Anti-consensus Gray Zone — 反共識灰色地帶注
P3-A:  Auto-Learning Feedback Loop — 自動學習權重迴路
P3-B:  LSTM Sequence Model — 基礎序列模型 (NumPy 手寫, 無外部依賴)

每個方案做 150/500/1500 期三窗口回測 + 邊際分析。

Usage:
    python3 tools/backtest_biglotto_enhancements.py
    python3 tools/backtest_biglotto_enhancements.py --only P1-A
"""
import os
import sys
import time
import json
import argparse
import numpy as np
from collections import Counter, defaultdict
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

# ============================================================
# Constants
# ============================================================
MAX_NUM = 49
PICK = 6
SEED = 42

P_SINGLE = 0.0186
BASELINES = {n: 1 - (1 - P_SINGLE) ** n for n in range(1, 8)}

WINDOWS = [150, 500, 1500]
MIN_HISTORY = 200

# ============================================================
# Base Components (exact copy from verified backtest)
# ============================================================
def fourier_rhythm_bet(history, window=500):
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
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
    sorted_idx = np.argsort(scores[1:])[::-1] + 1
    return sorted(sorted_idx[:6].tolist())


def cold_numbers_bet(history, window=100, exclude=None):
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    candidates = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
    sorted_cold = sorted(candidates, key=lambda x: freq.get(x, 0))
    return sorted(sorted_cold[:6])


def tail_balance_bet(history, window=100, exclude=None):
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    tail_groups = {i: [] for i in range(10)}
    for n in range(1, MAX_NUM + 1):
        if n not in exclude:
            tail_groups[n % 10].append((n, freq.get(n, 0)))
    for t in tail_groups:
        tail_groups[t].sort(key=lambda x: x[1], reverse=True)
    selected = []
    available_tails = sorted(
        [t for t in range(10) if tail_groups[t]],
        key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0,
        reverse=True
    )
    idx_in_group = {t: 0 for t in range(10)}
    while len(selected) < 6:
        added = False
        for tail in available_tails:
            if len(selected) >= 6:
                break
            if idx_in_group[tail] < len(tail_groups[tail]):
                num, _ = tail_groups[tail][idx_in_group[tail]]
                if num not in selected:
                    selected.append(num)
                    added = True
                idx_in_group[tail] += 1
        if not added:
            break
    if len(selected) < 6:
        remaining = [n for n in range(1, MAX_NUM + 1)
                     if n not in selected and n not in exclude]
        remaining.sort(key=lambda x: freq.get(x, 0), reverse=True)
        selected.extend(remaining[:6 - len(selected)])
    return sorted(selected[:6])


def markov_orthogonal_bet(history, exclude=None, markov_window=30):
    exclude = exclude or set()
    window = min(markov_window, len(history))
    recent = history[-window:]
    transitions = Counter()
    for i in range(len(recent) - 1):
        prev_nums = recent[i]['numbers']
        next_nums = recent[i + 1]['numbers']
        for p in prev_nums:
            for n in next_nums:
                transitions[(p, n)] += 1
    if len(history) < 2:
        candidates = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
        return sorted(candidates[:PICK])
    last_draw_nums = history[-1]['numbers']
    scores = Counter()
    for prev_num in last_draw_nums:
        for n in range(1, MAX_NUM + 1):
            scores[n] += transitions.get((prev_num, n), 0)
    candidates = [(n, scores[n]) for n in range(1, MAX_NUM + 1) if n not in exclude]
    candidates.sort(key=lambda x: -x[1])
    selected = [n for n, _ in candidates[:PICK]]
    if len(selected) < PICK:
        remaining = [n for n in range(1, MAX_NUM + 1)
                     if n not in exclude and n not in selected]
        selected.extend(remaining[:PICK - len(selected)])
    return sorted(selected[:PICK])


def generate_base_ts3m4(history):
    """Base: TS3+Markov(w30) 4注"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    ts3_used = set(bet1) | set(bet2) | set(bet3)
    bet4 = markov_orthogonal_bet(history, exclude=ts3_used, markov_window=30)
    return [bet1, bet2, bet3, bet4]


# ============================================================
# P1-A: Regime Indicator + Adaptive Weight
# ============================================================
def detect_regime(history, lookback=10, freq_window=30):
    """
    偵測近期 regime：計算近 lookback 期的 hot ratio
    Returns: 'HOT', 'COLD', or 'MIXED'
    """
    if len(history) < freq_window + lookback:
        return 'MIXED', 0.33

    freq = Counter(n for d in history[-freq_window:] for n in d['numbers'])
    top10 = set(sorted(range(1, MAX_NUM + 1), key=lambda x: -freq.get(x, 0))[:10])

    hot_ratios = []
    for d in history[-lookback:]:
        ratio = len(set(d['numbers']) & top10) / 6
        hot_ratios.append(ratio)

    avg = np.mean(hot_ratios)
    if avg >= 0.40:
        return 'HOT', avg
    elif avg <= 0.20:
        return 'COLD', avg
    else:
        return 'MIXED', avg


def generate_p1a_regime_adaptive(history):
    """
    P1-A: Regime-aware TS3+Markov4
    - HOT regime 連續3期 → 第4注改用灰色地帶 (anti-hot)
    - COLD regime → 加重冷號覆蓋
    - MIXED → 維持原策略
    """
    regime, avg_hr = detect_regime(history)

    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    ts3_used = set(bet1) | set(bet2) | set(bet3)

    if regime == 'HOT' and avg_hr >= 0.45:
        # Hot regime: 4th bet from gray zone instead of Markov
        freq30 = Counter(n for d in history[-30:] for n in d['numbers'])
        ranked = sorted(range(1, MAX_NUM + 1), key=lambda x: -freq30.get(x, 0))
        gray = [n for n in ranked[12:30] if n not in ts3_used]
        # Pick gray numbers with shortest gap
        last_seen = {}
        for i, d in enumerate(history):
            for n in d['numbers']:
                last_seen[n] = i
        current = len(history)
        gray_scored = sorted(gray, key=lambda x: current - last_seen.get(x, 0))
        bet4 = sorted(gray_scored[:6])
        if len(bet4) < 6:
            remaining = [n for n in range(1, MAX_NUM + 1) if n not in ts3_used and n not in bet4]
            bet4 = sorted((bet4 + remaining)[:6])
    else:
        bet4 = markov_orthogonal_bet(history, exclude=ts3_used, markov_window=30)

    return [bet1, bet2, bet3, bet4]


# ============================================================
# P1-B: Consecutive Pair Post-processing
# ============================================================
def inject_consecutive_pairs(bets, history, window=30):
    """
    對每注做連號伴侶注入：
    如果某注中有號碼 N，且 N±1 在歷史中有連號模式，
    則替換該注最弱號碼為 N±1。
    """
    recent = history[-window:]
    freq = Counter(n for d in recent for n in d['numbers'])

    # Build consecutive pair frequency
    consec_freq = Counter()
    for d in recent:
        nums = sorted(d['numbers'][:6])
        for i in range(len(nums) - 1):
            if nums[i + 1] - nums[i] == 1:
                consec_freq[(nums[i], nums[i + 1])] += 1

    new_bets = []
    all_used = set()
    for bet in bets:
        all_used.update(bet)

    for b_idx, bet in enumerate(bets):
        bet_set = set(bet)
        best_pair = None
        best_score = 0

        for n in bet:
            for neighbor in [n - 1, n + 1]:
                if 1 <= neighbor <= MAX_NUM and neighbor not in bet_set and neighbor not in all_used:
                    pair = (min(n, neighbor), max(n, neighbor))
                    score = consec_freq.get(pair, 0)
                    if score > best_score:
                        best_score = score
                        best_pair = (n, neighbor)

        if best_pair and best_score >= 2:
            anchor, new_num = best_pair
            # Replace weakest number (lowest frequency, not the anchor)
            bet_scored = [(num, freq.get(num, 0)) for num in bet if num != anchor]
            bet_scored.sort(key=lambda x: x[1])
            weakest = bet_scored[0][0]

            new_bet = sorted([n for n in bet if n != weakest] + [new_num])
            new_bets.append(new_bet)
            all_used.update(new_bet)
        else:
            new_bets.append(list(bet))
            all_used.update(bet)

    return new_bets


def generate_p1b_consecutive(history):
    """P1-B: TS3+Markov4 + 連號伴侶後處理"""
    base_bets = generate_base_ts3m4(history)
    return inject_consecutive_pairs(base_bets, history, window=30)


# ============================================================
# P2-A: Rank Diversity Constraint
# ============================================================
def generate_p2a_rank_diversity(history):
    """
    P2-A: 強制 rank 分散的4注
    注1: rank 1-12 (最熱) — Fourier
    注2: rank 13-24 (冷號偏溫) — Cold variant
    注3: rank 25-37 (灰色 + 尾數) — Tail variant
    注4: rank 38-49 (最冷) + Markov 校正 — Markov variant
    """
    freq30 = Counter(n for d in history[-30:] for n in d['numbers'])
    ranked = sorted(range(1, MAX_NUM + 1), key=lambda x: -freq30.get(x, 0))

    rank_zones = {
        'hot': set(ranked[0:12]),
        'warm': set(ranked[12:24]),
        'gray': set(ranked[24:37]),
        'cold': set(ranked[37:49]),
    }

    # Bet 1: Fourier, but restricted to hot zone
    bet1_full = fourier_rhythm_bet(history)
    bet1 = sorted([n for n in bet1_full if n in rank_zones['hot']])
    if len(bet1) < 6:
        # Fill from hot zone by freq
        extras = sorted([n for n in rank_zones['hot'] if n not in bet1],
                       key=lambda x: -freq30.get(x, 0))
        bet1 = sorted((bet1 + extras)[:6])

    # Bet 2: Cold variant from warm zone
    bet2_full = cold_numbers_bet(history, exclude=set(bet1))
    bet2 = sorted([n for n in bet2_full if n in rank_zones['warm']])
    if len(bet2) < 6:
        extras = sorted([n for n in rank_zones['warm'] if n not in set(bet1) | set(bet2)],
                       key=lambda x: freq30.get(x, 0))
        bet2 = sorted((bet2 + extras)[:6])

    # Bet 3: Tail balance from gray zone
    used = set(bet1) | set(bet2)
    bet3_full = tail_balance_bet(history, exclude=used)
    bet3 = sorted([n for n in bet3_full if n in rank_zones['gray']])
    if len(bet3) < 6:
        extras = sorted([n for n in rank_zones['gray'] if n not in used and n not in set(bet3)],
                       key=lambda x: freq30.get(x, 0))
        bet3 = sorted((bet3 + extras)[:6])

    # Bet 4: Markov from cold zone
    used = used | set(bet3)
    bet4_full = markov_orthogonal_bet(history, exclude=used, markov_window=30)
    bet4 = sorted([n for n in bet4_full if n in rank_zones['cold']])
    if len(bet4) < 6:
        extras = sorted([n for n in rank_zones['cold'] if n not in used and n not in set(bet4)],
                       key=lambda x: freq30.get(x, 0))
        bet4 = sorted((bet4 + extras)[:6])

    # Ensure all bets have exactly 6 numbers
    for i, bet in enumerate([bet1, bet2, bet3, bet4]):
        if len(bet) < 6:
            used_all = set(bet1) | set(bet2) | set(bet3) | set(bet4)
            remaining = [n for n in range(1, MAX_NUM + 1) if n not in used_all]
            bet.extend(remaining[:6 - len(bet)])

    return [sorted(bet1[:6]), sorted(bet2[:6]), sorted(bet3[:6]), sorted(bet4[:6])]


# ============================================================
# P2-B: 5th Bet — Anti-consensus Gray Zone
# ============================================================
def generate_p2b_5bet_anti(history):
    """
    P2-B: TS3+Markov4 + 第5注反共識灰色地帶
    第5注從前4注完全未覆蓋的號碼中，選灰色地帶 (rank 15-35) 的 top6
    """
    base_bets = generate_base_ts3m4(history)
    used = set()
    for b in base_bets:
        used.update(b)

    freq30 = Counter(n for d in history[-30:] for n in d['numbers'])
    ranked = sorted(range(1, MAX_NUM + 1), key=lambda x: -freq30.get(x, 0))

    # Gray zone: rank 15-35, excluding used
    gray_candidates = [n for n in ranked[14:35] if n not in used]

    # Score by gap (prefer moderate gap)
    last_seen = {}
    for i, d in enumerate(history):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(history)

    scored = []
    for n in gray_candidates:
        gap = current - last_seen.get(n, 0)
        # Prefer gap in range 3-15 (not too fresh, not too stale)
        gap_score = 1.0 / (abs(gap - 8) + 1.0)
        scored.append((n, gap_score + freq30.get(n, 0) * 0.1))

    scored.sort(key=lambda x: -x[1])
    bet5 = sorted([n for n, _ in scored[:6]])

    if len(bet5) < 6:
        remaining = [n for n in range(1, MAX_NUM + 1) if n not in used and n not in bet5]
        bet5 = sorted((bet5 + remaining)[:6])

    return base_bets + [bet5]


# ============================================================
# P3-A: Auto-Learning Feedback Loop
# ============================================================
class AutoLearner:
    """
    自動學習迴路：根據近期各方法的命中表現動態調整策略。

    原理：
    1. 追蹤近 N 期每個 base method 的命中率
    2. 命中率高的方法權重上升 → 佔更多 candidate pool 位置
    3. 命中率低的方法權重下降 → 被其他方法替代
    """

    def __init__(self, lookback=20):
        self.lookback = lookback
        self.method_weights = {
            'fourier': 1.0,
            'cold': 1.0,
            'tail': 1.0,
            'markov': 1.0,
        }

    def update_weights(self, history):
        """根據近期命中更新權重"""
        if len(history) < self.lookback + 1:
            return

        results = {'fourier': 0, 'cold': 0, 'tail': 0, 'markov': 0}
        total = 0

        for i in range(len(history) - self.lookback, len(history)):
            if i < MIN_HISTORY:
                continue
            target = set(history[i]['numbers'])
            h = history[:i]

            b1 = fourier_rhythm_bet(h)
            b2 = cold_numbers_bet(h, exclude=set(b1))
            b3 = tail_balance_bet(h, exclude=set(b1) | set(b2))
            b4 = markov_orthogonal_bet(h, exclude=set(b1) | set(b2) | set(b3), markov_window=30)

            if len(set(b1) & target) >= 3:
                results['fourier'] += 1
            if len(set(b2) & target) >= 3:
                results['cold'] += 1
            if len(set(b3) & target) >= 3:
                results['tail'] += 1
            if len(set(b4) & target) >= 3:
                results['markov'] += 1
            total += 1

        if total > 0:
            for m in results:
                rate = results[m] / total
                # Adaptive: if method is performing well, boost; if not, reduce
                # But never go below 0.5 or above 2.0
                self.method_weights[m] = max(0.5, min(2.0, 0.7 + rate * 15))

    def generate(self, history):
        """根據權重生成4注"""
        self.update_weights(history)

        freq30 = Counter(n for d in history[-30:] for n in d['numbers'])
        freq100 = Counter(n for d in history[-100:] for n in d['numbers'])

        # Score each number by weighted method contribution
        num_scores = Counter()

        # Fourier contribution
        b1 = fourier_rhythm_bet(history)
        for n in b1:
            num_scores[n] += self.method_weights['fourier'] * 3

        # Cold contribution
        all_nums = [n for d in history[-100:] for n in d['numbers']]
        freq = Counter(all_nums)
        cold_ranked = sorted(range(1, MAX_NUM + 1), key=lambda x: freq.get(x, 0))
        for i, n in enumerate(cold_ranked[:12]):
            num_scores[n] += self.method_weights['cold'] * (2 - i * 0.1)

        # Tail contribution
        b3 = tail_balance_bet(history)
        for n in b3:
            num_scores[n] += self.method_weights['tail'] * 2

        # Markov contribution
        b4 = markov_orthogonal_bet(history, markov_window=30)
        for n in b4:
            num_scores[n] += self.method_weights['markov'] * 2

        # Generate 4 bets from scored pool
        ranked_nums = sorted(num_scores.items(), key=lambda x: -x[1])
        all_candidates = [n for n, _ in ranked_nums]

        bets = []
        used = set()
        for bet_idx in range(4):
            bet = []
            for n in all_candidates:
                if n not in used and len(bet) < 6:
                    bet.append(n)
            if len(bet) < 6:
                remaining = [n for n in range(1, MAX_NUM + 1) if n not in used and n not in bet]
                bet.extend(remaining[:6 - len(bet)])
            bets.append(sorted(bet[:6]))
            used.update(bet[:6])

        return bets


# ============================================================
# P3-B: Simple LSTM-like Sequence Model (NumPy only)
# ============================================================
def generate_p3b_lstm_sequence(history):
    """
    P3-B: 簡易序列模型 — 基於滑動窗口的 weighted recency scoring

    非真實 LSTM (需 PyTorch，此處模擬其核心思想)：
    1. 指數衰減加權近期出現頻率
    2. 二階轉移 (前2期 → 本期) 增強 Markov
    3. 序列 momentum (連續 N 期出現的號碼加分)

    仍輸出4注，前3注用 TS3，第4注用序列模型替代 Markov。
    """
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    ts3_used = set(bet1) | set(bet2) | set(bet3)

    # Exponential decay frequency
    decay_scores = np.zeros(MAX_NUM + 1)
    window = min(100, len(history))
    for offset in range(window):
        idx = len(history) - 1 - offset
        weight = np.exp(-offset / 20.0)  # tau=20
        for n in history[idx]['numbers']:
            if n <= MAX_NUM:
                decay_scores[n] += weight

    # Second-order Markov (前2期)
    markov2_scores = Counter()
    if len(history) >= 3:
        w = min(30, len(history))
        recent = history[-w:]
        for i in range(len(recent) - 2):
            prev2 = set(recent[i]['numbers'])
            prev1 = set(recent[i + 1]['numbers'])
            next_draw = set(recent[i + 2]['numbers'])
            for p2 in prev2:
                for p1 in prev1:
                    for n in next_draw:
                        markov2_scores[(p2, p1, n)] += 1

        last2 = set(history[-2]['numbers'])
        last1 = set(history[-1]['numbers'])
        for n in range(1, MAX_NUM + 1):
            for p2 in last2:
                for p1 in last1:
                    decay_scores[n] += markov2_scores.get((p2, p1, n), 0) * 0.5

    # Momentum: consecutive appearance bonus
    if len(history) >= 3:
        last3_sets = [set(history[-i-1]['numbers']) for i in range(3)]
        for n in range(1, MAX_NUM + 1):
            streak = sum(1 for s in last3_sets if n in s)
            if streak >= 2:
                decay_scores[n] += streak * 0.3

    # Select 4th bet from non-TS3 numbers
    candidates = [(n, decay_scores[n]) for n in range(1, MAX_NUM + 1) if n not in ts3_used]
    candidates.sort(key=lambda x: -x[1])
    bet4 = sorted([n for n, _ in candidates[:6]])

    return [bet1, bet2, bet3, bet4]


# ============================================================
# Combined Enhancements
# ============================================================
def generate_combined_p1(history):
    """P1 組合: Regime Adaptive + Consecutive Post-processing"""
    regime, avg_hr = detect_regime(history)

    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    ts3_used = set(bet1) | set(bet2) | set(bet3)

    if regime == 'HOT' and avg_hr >= 0.45:
        freq30 = Counter(n for d in history[-30:] for n in d['numbers'])
        ranked = sorted(range(1, MAX_NUM + 1), key=lambda x: -freq30.get(x, 0))
        gray = [n for n in ranked[12:30] if n not in ts3_used]
        last_seen = {}
        for i, d in enumerate(history):
            for n in d['numbers']:
                last_seen[n] = i
        current = len(history)
        gray_scored = sorted(gray, key=lambda x: current - last_seen.get(x, 0))
        bet4 = sorted(gray_scored[:6])
        if len(bet4) < 6:
            remaining = [n for n in range(1, MAX_NUM + 1) if n not in ts3_used and n not in bet4]
            bet4 = sorted((bet4 + remaining)[:6])
    else:
        bet4 = markov_orthogonal_bet(history, exclude=ts3_used, markov_window=30)

    bets = [bet1, bet2, bet3, bet4]
    return inject_consecutive_pairs(bets, history, window=30)


def generate_combined_all_4bet(history):
    """全部 P1+P2-A 組合: Regime + Consecutive + Rank Diversity (4注)"""
    regime, avg_hr = detect_regime(history)

    if regime == 'HOT' and avg_hr >= 0.45:
        # In hot regime, use rank diversity to spread coverage
        return generate_p2a_rank_diversity(history)
    else:
        # Normal regime: TS3+Markov with consecutive post-processing
        bets = generate_base_ts3m4(history)
        return inject_consecutive_pairs(bets, history, window=30)


def generate_combined_5bet(history):
    """最強5注: TS3+Markov4 + 連號處理 + 第5注反共識"""
    base = generate_base_ts3m4(history)
    processed = inject_consecutive_pairs(base, history, window=30)

    used = set()
    for b in processed:
        used.update(b)

    freq30 = Counter(n for d in history[-30:] for n in d['numbers'])
    ranked = sorted(range(1, MAX_NUM + 1), key=lambda x: -freq30.get(x, 0))
    gray = [n for n in ranked[14:35] if n not in used]

    last_seen = {}
    for i, d in enumerate(history):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(history)

    scored = []
    for n in gray:
        gap = current - last_seen.get(n, 0)
        gap_score = 1.0 / (abs(gap - 8) + 1.0)
        scored.append((n, gap_score + freq30.get(n, 0) * 0.1))
    scored.sort(key=lambda x: -x[1])
    bet5 = sorted([n for n, _ in scored[:6]])

    if len(bet5) < 6:
        remaining = [n for n in range(1, MAX_NUM + 1) if n not in used and n not in bet5]
        bet5 = sorted((bet5 + remaining)[:6])

    return processed + [bet5]


# ============================================================
# Backtest Engine
# ============================================================
def run_backtest(draws, strategy_func, n_bets, n_periods, seed=42, label=""):
    np.random.seed(seed)
    baseline = BASELINES.get(n_bets, BASELINES[4])
    start_idx = len(draws) - n_periods
    if start_idx < MIN_HISTORY:
        start_idx = MIN_HISTORY

    hits = {3: 0, 4: 0, 5: 0, 6: 0}
    total = 0
    first_half_hits = 0
    second_half_hits = 0
    half_point = start_idx + (len(draws) - start_idx) // 2

    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        history = draws[:i]

        try:
            bets = strategy_func(history)
        except Exception as e:
            total += 1
            continue

        best_match = 0
        any_hit = False
        for b in bets:
            mc = len(set(b) & target)
            if mc > best_match:
                best_match = mc
            if mc >= 3:
                any_hit = True

        if best_match >= 3:
            hits[min(best_match, 6)] += 1
        if any_hit and i < half_point:
            first_half_hits += 1
        elif any_hit and i >= half_point:
            second_half_hits += 1
        total += 1

    m3_plus = sum(hits.values())
    win_rate = m3_plus / total if total > 0 else 0
    edge = win_rate - baseline

    half_n = half_point - start_idx
    second_half_n = total - half_n

    # z-score
    z = (win_rate - baseline) / np.sqrt(baseline * (1 - baseline) / total) if total > 0 else 0

    return {
        'label': label,
        'total': total,
        'n_bets': n_bets,
        'm3_plus': m3_plus,
        'hits': dict(hits),
        'win_rate': win_rate,
        'baseline': baseline,
        'edge': edge,
        'z_score': z,
        'first_half': (first_half_hits, half_n),
        'second_half': (second_half_hits, second_half_n),
    }


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', type=str, default=None,
                       help='Only run specific test (e.g., P1-A)')
    args = parser.parse_args()

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))

    print("=" * 90)
    print("  大樂透 TS3+Markov4 增強方案全面回測")
    print("=" * 90)
    print(f"  Database: {len(draws)} draws ({draws[0]['date']} ~ {draws[-1]['date']})")
    print(f"  Windows: {WINDOWS}")
    print(f"  Seed: {SEED}")
    print("=" * 90)

    # Auto-learner needs to be pre-initialized
    auto_learner = AutoLearner(lookback=20)

    strategies = {
        'Base':    ('TS3+Markov4 (base)',             generate_base_ts3m4, 4),
        'P1-A':    ('P1-A: Regime Adaptive',          generate_p1a_regime_adaptive, 4),
        'P1-B':    ('P1-B: Consecutive Post-proc',    generate_p1b_consecutive, 4),
        'P2-A':    ('P2-A: Rank Diversity',           generate_p2a_rank_diversity, 4),
        'P2-B':    ('P2-B: 5bet Anti-consensus',      generate_p2b_5bet_anti, 5),
        'P3-A':    ('P3-A: Auto-Learning',            auto_learner.generate, 4),
        'P3-B':    ('P3-B: LSTM Sequence',            generate_p3b_lstm_sequence, 4),
        'C-P1':    ('Combined P1 (Regime+Consec)',    generate_combined_p1, 4),
        'C-ALL4':  ('Combined ALL 4bet',              generate_combined_all_4bet, 4),
        'C-5BET':  ('Combined 5bet (Best)',           generate_combined_5bet, 5),
    }

    if args.only:
        keys = [k for k in strategies if k == args.only]
        if not keys:
            print(f"Unknown strategy: {args.only}")
            print(f"Available: {list(strategies.keys())}")
            return
        # Always include base for comparison
        keys = ['Base'] + keys if 'Base' not in keys else keys
    else:
        keys = list(strategies.keys())

    all_results = {}

    for key in keys:
        label, func, n_bets = strategies[key]
        print(f"\n{'='*90}")
        print(f"  {key}: {label} ({n_bets}注)")
        print(f"{'='*90}")

        results = []
        for w in WINDOWS:
            t0 = time.time()
            r = run_backtest(draws, func, n_bets, w, seed=SEED, label=label)
            elapsed = time.time() - t0
            results.append(r)

            wr = r['win_rate'] * 100
            bl = r['baseline'] * 100
            ed = r['edge'] * 100
            z = r['z_score']
            icon = "PASS" if ed > 0 else "FAIL"

            fh, fn = r['first_half']
            sh, sn = r['second_half']
            fhr = fh / fn * 100 if fn > 0 else 0
            shr = sh / sn * 100 if sn > 0 else 0

            print(f"  {w:>4}期: {r['m3_plus']:>3}/{r['total']} = {wr:5.2f}% "
                  f"(base {bl:.2f}%, edge {ed:+5.2f}%, z={z:+.2f}) [{icon}] "
                  f"[{elapsed:.1f}s]")
            print(f"         前半: {fh}/{fn}={fhr:.2f}% | 後半: {sh}/{sn}={shr:.2f}%")

        all_results[key] = results

    # ====== Summary Table ======
    print("\n" + "=" * 90)
    print("  SUMMARY TABLE")
    print("=" * 90)

    header = f"{'Strategy':<30s}"
    for w in WINDOWS:
        header += f" | {w:>4}期 Edge"
    header += " | Status"
    print(header)
    print("-" * 90)

    for key in keys:
        results = all_results[key]
        label, _, n_bets = strategies[key]
        row = f"  {key + ' (' + str(n_bets) + '注)':<28s}"
        all_positive = True
        for r in results:
            ed = r['edge'] * 100
            if ed <= 0:
                all_positive = False
            row += f" | {ed:>+6.2f}%   "
        status = "★ ALL PASS" if all_positive else "MIXED" if any(r['edge'] > 0 for r in results) else "✗ FAIL"
        row += f" | {status}"
        print(row)

    # ====== vs Base Marginal ======
    if 'Base' in all_results:
        print(f"\n{'='*90}")
        print("  MARGINAL vs BASE")
        print(f"{'='*90}")

        base_results = all_results['Base']
        for key in keys:
            if key == 'Base':
                continue
            results = all_results[key]
            label, _, n_bets = strategies[key]
            print(f"\n  {key}: {label}")
            for i, w in enumerate(WINDOWS):
                base_edge = base_results[i]['edge'] * 100
                this_edge = results[i]['edge'] * 100
                diff = this_edge - base_edge
                print(f"    {w:>4}期: base {base_edge:+.2f}% → this {this_edge:+.2f}% (Δ{diff:+.2f}%)")

    # ====== 115000015 Prediction Test ======
    print(f"\n{'='*90}")
    print("  對 115000015 的預測表現")
    print(f"{'='*90}")

    target_idx = None
    for i, d in enumerate(draws):
        if str(d['draw']) == '115000015':
            target_idx = i
            break

    if target_idx:
        actual_15 = set(draws[target_idx]['numbers'])
        hist_15 = draws[:target_idx]

        for key in keys:
            label, func, n_bets = strategies[key]
            try:
                bets = func(hist_15)
                all_covered = set()
                best_m = 0
                for b in bets:
                    all_covered.update(b)
                    mc = len(set(b) & actual_15)
                    if mc > best_m:
                        best_m = mc
                coverage_hit = len(all_covered & actual_15)
                print(f"  {key:<10s}: best=M{best_m}, coverage={coverage_hit}/6, "
                      f"hit={sorted(all_covered & actual_15)}, "
                      f"miss={sorted(actual_15 - all_covered)}")
            except Exception as e:
                print(f"  {key:<10s}: ERROR - {e}")

    print(f"\n{'='*90}")
    print("  DONE")
    print(f"{'='*90}")


if __name__ == '__main__':
    main()
