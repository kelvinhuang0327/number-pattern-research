#!/usr/bin/env python3
"""
EWMA 頻率預測器 + MAB 方法選擇器 — 今彩539
==============================================
058期檢討行動項:
  - EWMA: 指數加權移動平均頻率預測,比 ACB 更能捕捉近期動量
  - MAB:  Multi-Armed Bandit 動態選擇最優方法組合
  - Momentum Guard: 超熱號強制注入後處理層

作者: 系統自動生成
日期: 2026-03-05
"""
import sys
import os
import numpy as np
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

MAX_NUM = 39
PICK = 5

# ========== EWMA 頻率預測器 ==========

def _539_ewma_scores(history, span=30, long_span=100):
    """EWMA (Exponential Weighted Moving Average) 頻率分數

    vs ACB:
      - ACB 用簡單計數(所有期等權) + gap
      - EWMA 給近期出現更大權重，自然追蹤動量
      - 短 span 捕捉快速動量，長 span 捕捉中期趨勢

    分數 = ewma_short * 0.6 + ewma_long * 0.4
    高分 = 近期頻繁出現且中期也活躍的號碼
    """
    alpha_short = 2.0 / (span + 1)
    alpha_long = 2.0 / (long_span + 1)

    # 使用最近 long_span*2 期計算足夠的 EWMA 歷史
    window = min(long_span * 2, len(history))
    recent = history[-window:]

    scores = {}
    for n in range(1, MAX_NUM + 1):
        # Binary series: 1 if number appeared, 0 otherwise
        ewma_s = 0.0
        ewma_l = 0.0
        for d in recent:
            val = 1.0 if n in d['numbers'] else 0.0
            ewma_s = alpha_short * val + (1 - alpha_short) * ewma_s
            ewma_l = alpha_long * val + (1 - alpha_long) * ewma_l

        scores[n] = ewma_s * 0.6 + ewma_l * 0.4

    return scores


def _539_ewma_bet(history, exclude=None, span=30, long_span=100, mode='hot'):
    """EWMA 頻率預測注

    mode='hot':  選 EWMA 分最高的號碼 (動量追蹤)
    mode='cold': 選 EWMA 分最低的號碼 (冷號回歸)
    mode='warm': 選 EWMA 分最接近期望的號碼 (均值回歸)
    """
    exclude = exclude or set()
    scores = _539_ewma_scores(history, span, long_span)

    candidates = {n: s for n, s in scores.items() if n not in exclude}

    if mode == 'hot':
        ranked = sorted(candidates, key=lambda x: -candidates[x])
    elif mode == 'cold':
        ranked = sorted(candidates, key=lambda x: candidates[x])
    else:  # warm
        expected = PICK / MAX_NUM  # ~0.128
        ranked = sorted(candidates, key=lambda x: abs(candidates[x] - expected))

    # Zone balance: ensure at least 2 zones
    result = []
    zones_selected = set()
    for n in ranked:
        zone = 0 if n <= 13 else (1 if n <= 26 else 2)
        result.append(n)
        zones_selected.add(zone)
        if len(result) >= PICK:
            break

    # Zone balance fix
    if len(zones_selected) < 2 and len(result) >= PICK:
        missing_zones = set(range(3)) - zones_selected
        for mz in missing_zones:
            zr = range(1, 14) if mz == 0 else (range(14, 27) if mz == 1 else range(27, 40))
            zc = sorted([n for n in zr if n not in exclude and n not in set(result[:-1])],
                        key=lambda x: -candidates.get(x, 0) if mode == 'hot' else candidates.get(x, 0))
            if zc:
                result[-1] = zc[0]
                break

    return sorted(result[:PICK])


# ========== Momentum Guard 後處理層 ==========

def momentum_guard(bets, history, threshold=8, window=30):
    """超熱號強制注入後處理

    058期教訓: #08 近30期出現11次(期望3.8), 但 ACB 排名35完全忽略
    機制: 若上期號碼中有近期超熱號(出現>=threshold次), 強制替換最弱號碼

    只在極端動量時觸發，不干預正常預測
    """
    recent = history[-window:] if len(history) >= window else history
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM:
                freq[n] += 1

    prev_nums = history[-1]['numbers']
    hot_prev = [n for n in prev_nums if n <= MAX_NUM and freq[n] >= threshold]

    if not hot_prev:
        return bets, False  # No momentum trigger

    injected = []
    for hot_n in hot_prev:
        # Check if already in any bet
        placed = any(hot_n in bet['numbers'] for bet in bets)
        if placed:
            continue

        # Find weakest number across all bets to replace
        best_swap = None
        best_swap_freq = float('inf')
        best_bet_idx = None

        for bi, bet in enumerate(bets):
            for n in bet['numbers']:
                if freq.get(n, 0) < freq[hot_n] and freq.get(n, 0) < best_swap_freq:
                    best_swap = n
                    best_swap_freq = freq.get(n, 0)
                    best_bet_idx = bi

        if best_swap is not None and best_bet_idx is not None:
            bets[best_bet_idx]['numbers'] = sorted(
                [n for n in bets[best_bet_idx]['numbers'] if n != best_swap] + [hot_n]
            )
            injected.append(hot_n)

    return bets, len(injected) > 0


# ========== Repeat Momentum 注 ==========

def _539_repeat_momentum_bet(history, exclude=None, window=30, top_k=3):
    """上期號碼動量重複注

    從上期號碼中選近期最熱的 top_k 個，用溫號填充其餘位置。
    捕捉「連續出現」的動量特徵。

    歷史統計: 重複>=3個 出現率 1.1%, 但條件觸發時更高。
    """
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM:
                freq[n] += 1

    prev_nums = [n for n in history[-1]['numbers'] if n <= MAX_NUM and n not in exclude]
    hot_prev = sorted(prev_nums, key=lambda n: -freq[n])[:top_k]

    # Fill remaining with warm numbers (closest to expected)
    expected = len(recent) * PICK / MAX_NUM
    used = set(hot_prev) | exclude | set(history[-1]['numbers'])
    remaining = sorted([n for n in range(1, MAX_NUM + 1) if n not in used],
                       key=lambda n: abs(freq[n] - expected))

    result = list(hot_prev) + remaining[:PICK - len(hot_prev)]

    # Zone balance
    zones = set()
    for n in result:
        zone = 0 if n <= 13 else (1 if n <= 26 else 2)
        zones.add(zone)

    if len(zones) < 2 and len(result) >= PICK:
        missing_zones = set(range(3)) - zones
        for mz in missing_zones:
            zr = range(1, 14) if mz == 0 else (range(14, 27) if mz == 1 else range(27, 40))
            zc = [n for n in zr if n not in set(result) and n not in exclude]
            if zc:
                # Replace the fill number with worst frequency match
                fill_nums = [n for n in result if n not in hot_prev]
                if fill_nums:
                    worst = max(fill_nums, key=lambda n: abs(freq[n] - expected))
                    idx = result.index(worst)
                    result[idx] = sorted(zc, key=lambda n: abs(freq[n] - expected))[0]
                break

    return sorted(result[:PICK])


# ========== MAB 方法選擇器 ==========

class MABMethodSelector:
    """Multi-Armed Bandit 方法選擇器

    使用 UCB1 (Upper Confidence Bound) 動態選擇最優方法組合。
    每個 arm = 一個預測方法/組合，根據歷史表現自適應調整。

    UCB1 score = mean_reward + sqrt(2 * ln(total_plays) / arm_plays)
    - mean_reward: 該方法的歷史 M3+ 命中率
    - exploration bonus: 對嘗試較少的方法給予探索獎勵

    Sliding window UCB: 僅用最近 N 期的表現，避免過早收斂
    """

    def __init__(self, methods, ucb_window=200):
        """
        methods: dict of {name: predict_function}
            predict_function(history) -> list of 5 numbers
        ucb_window: 滑動窗口大小，僅用最近 N 期表現
        """
        self.methods = methods
        self.ucb_window = ucb_window
        self.arm_names = list(methods.keys())
        self.n_arms = len(self.arm_names)

    def _compute_ucb_scores(self, reward_history):
        """計算每個 arm 的 UCB1 分數"""
        # Use sliding window
        window = reward_history[-self.ucb_window:] if len(reward_history) > self.ucb_window else reward_history
        total = len(window)

        if total == 0:
            return {name: float('inf') for name in self.arm_names}

        # Count per-arm stats
        arm_rewards = {name: [] for name in self.arm_names}
        for record in window:
            for name in self.arm_names:
                if name in record:
                    arm_rewards[name].append(record[name])

        scores = {}
        for name in self.arm_names:
            plays = len(arm_rewards[name])
            if plays == 0:
                scores[name] = float('inf')  # Force exploration
            else:
                mean_r = np.mean(arm_rewards[name])
                exploration = np.sqrt(2 * np.log(total) / plays)
                scores[name] = mean_r + exploration

        return scores

    def select_methods(self, reward_history, n_select=3):
        """選擇 Top-N 方法"""
        scores = self._compute_ucb_scores(reward_history)
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return [name for name, _ in ranked[:n_select]]

    def predict_with_mab(self, history, reward_history, n_bets=3):
        """MAB 選擇方法後預測

        1. UCB1 選擇 top-n_bets 方法
        2. 每個方法生成一注
        3. 後續注排除前面已選號碼（正交）
        """
        selected = self.select_methods(reward_history, n_select=n_bets)

        bets = []
        used = set()
        for method_name in selected:
            func = self.methods[method_name]
            nums = func(history, exclude=used)
            bets.append({'numbers': nums})
            used.update(nums)

        return bets, selected

    def evaluate_all(self, history, actual):
        """評估所有方法在本期的表現，返回 reward record"""
        record = {}
        for name, func in self.methods.items():
            try:
                nums = func(history)
                hits = len(set(nums) & set(actual))
                record[name] = 1.0 if hits >= 3 else (hits / 5.0 * 0.3)  # Partial reward
            except Exception:
                record[name] = 0.0
        return record


# ========== 組合策略 ==========

def ewma_markov_2bet(history, rules=None):
    """EWMA+Markov 正交2注 (058期最佳2注組合研究結果)"""
    from tools.quick_predict import _539_markov_bet
    bet1 = _539_ewma_bet(history, mode='hot')
    bet2 = _539_markov_bet(history, exclude=set(bet1))
    return [bet1, bet2]


def ewma_midfreq_2bet(history, rules=None):
    """EWMA+MidFreq 正交2注"""
    from tools.quick_predict import _539_midfreq_bet
    bet1 = _539_ewma_bet(history, mode='hot')
    bet2 = _539_midfreq_bet(history, exclude=set(bet1))
    return [bet1, bet2]


def acb_markov_midfreq_3bet(history, rules=None):
    """ACB+Markov+MidFreq 正交3注 (058期最佳3注組合)"""
    from tools.quick_predict import _539_acb_bet, _539_markov_bet, _539_midfreq_bet
    bet1 = _539_acb_bet(history)
    bet2 = _539_markov_bet(history, exclude=set(bet1))
    bet3 = _539_midfreq_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


def ewma_markov_midfreq_3bet(history, rules=None):
    """EWMA+Markov+MidFreq 正交3注"""
    from tools.quick_predict import _539_markov_bet, _539_midfreq_bet
    bet1 = _539_ewma_bet(history, mode='hot')
    bet2 = _539_markov_bet(history, exclude=set(bet1))
    bet3 = _539_midfreq_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


def ewma_acb_markov_3bet(history, rules=None):
    """EWMA+ACB+Markov 正交3注"""
    from tools.quick_predict import _539_acb_bet, _539_markov_bet
    bet1 = _539_ewma_bet(history, mode='hot')
    bet2 = _539_acb_bet(history, exclude=set(bet1))
    bet3 = _539_markov_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


def mab_adaptive_3bet(history, reward_history, rules=None):
    """MAB 自適應3注 (方法由 UCB1 動態選擇)"""
    from tools.quick_predict import (
        _539_acb_bet, _539_markov_bet, _539_midfreq_bet, _539_fourier_scores
    )

    methods = {
        'EWMA_hot': lambda h, exclude=None: _539_ewma_bet(h, exclude, mode='hot'),
        'EWMA_warm': lambda h, exclude=None: _539_ewma_bet(h, exclude, mode='warm'),
        'ACB': lambda h, exclude=None: _539_acb_bet(h, exclude),
        'Markov': lambda h, exclude=None: _539_markov_bet(h, exclude),
        'MidFreq': lambda h, exclude=None: _539_midfreq_bet(h, exclude),
        'Repeat': lambda h, exclude=None: _539_repeat_momentum_bet(h, exclude),
    }

    selector = MABMethodSelector(methods, ucb_window=200)
    bets, selected = selector.predict_with_mab(history, reward_history, n_bets=3)
    return bets, selected, selector, methods
