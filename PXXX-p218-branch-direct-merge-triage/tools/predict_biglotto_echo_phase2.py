#!/usr/bin/env python3
"""
大樂透 Echo-Aware Phase 2: 自適應 Echo 權重

Phase 2 改進:
- 動態 echo_weight: 根據信號強度 + 滾動命中率自動調整
  - 信號強 + 歷史準 → 權重上升 (max ~0.45)
  - 信號弱 / 歷史差 → 權重下降 (min ~0.05)
- 完全確定性: 無隨機成分

Phase 1 結果: 3注 Echo-Aware Edge +1.01% (確定性, 取代舊 mixed_3bet)
Phase 2 目標: 通過動態權重進一步提升 Edge

使用方式:
    python3 tools/predict_biglotto_echo_phase2.py
"""

import sqlite3
import json
import sys
import math
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'lottery_api'))
sys.path.insert(0, str(PROJECT_ROOT / 'tools'))

MAX_NUM = 49
PICK = 6

from predict_biglotto_echo_2bet import (
    load_history, echo_detector, continuous_temperature
)
from predict_biglotto_echo_3bet import structural_score


def echo_signal_strength(history, max_lag=5):
    """
    計算當前 Echo 信號的強度 (0~1)

    強度 = 回聲事件的密度和品質
    - 多個 lag 有重疊 → 強
    - 高重疊數 (3+) → 強
    - 短 lag (1-2) 有重疊 → 強
    """
    if len(history) < max_lag + 1:
        return 0.0

    latest = set(history[-1]['numbers'])

    total_score = 0.0
    max_possible = 0.0

    for lag in range(1, max_lag + 1):
        past = set(history[-(lag + 1)]['numbers'])
        overlap = len(latest & past)
        weight = 1.0 / lag

        # 每個 lag 的最大可能 = PICK 個重疊
        max_possible += PICK * weight
        total_score += overlap * weight

    if max_possible == 0:
        return 0.0

    return min(1.0, total_score / max_possible)


def rolling_echo_accuracy(history, lookback=50, echo_threshold=0.3):
    """
    計算滾動 Echo 命中率

    往回看 lookback 期，每期計算:
    - 用前面的數據算 echo_detector
    - 檢查 echo 預測是否命中

    Returns: 命中率 (0~1)
    """
    if len(history) < lookback + 10:
        return 0.5  # 數據不足時返回中性值

    hits = 0
    events = 0

    start = max(10, len(history) - lookback)

    for idx in range(start, len(history)):
        train = history[:idx]
        actual = set(history[idx]['numbers'])

        echoes = echo_detector(train, max_lag=5)
        echo_nums = {n for n, s in echoes.items() if s > echo_threshold}

        if echo_nums:
            events += 1
            if len(echo_nums & actual) > 0:
                hits += 1

    if events == 0:
        return 0.5

    return hits / events


def adaptive_echo_weight(history, base_weight=0.25, lookback=50):
    """
    Phase 2 核心: 自適應 Echo 權重

    adaptive_weight = base_weight * strength_factor * accuracy_factor

    - strength_factor: 0.3 ~ 1.5 (based on current signal strength)
    - accuracy_factor: 0.3 ~ 1.5 (based on rolling hit rate)

    最終範圍: ~0.02 ~ ~0.56, 通常 0.05 ~ 0.45
    """
    strength = echo_signal_strength(history)
    accuracy = rolling_echo_accuracy(history, lookback)

    # strength_factor: 信號弱時抑制, 強時放大
    # strength 通常在 0.1~0.5 範圍
    strength_factor = 0.3 + strength * 2.4  # 0.3 ~ 1.5
    strength_factor = min(1.5, max(0.3, strength_factor))

    # accuracy_factor: 歷史準確度校正
    # accuracy 通常在 0.5~0.7
    accuracy_factor = 0.3 + accuracy * 1.7  # ~0.5 ~ ~1.5
    accuracy_factor = min(1.5, max(0.3, accuracy_factor))

    weight = base_weight * strength_factor * accuracy_factor

    # 硬限制
    weight = min(0.50, max(0.05, weight))

    return weight, strength, accuracy


def phase2_echo_2bet(history, window=50, lookback=50):
    """
    Phase 2 自適應 Echo-Aware 2注
    """
    temps = continuous_temperature(history, window)
    echoes = echo_detector(history, max_lag=5)
    ew, strength, accuracy = adaptive_echo_weight(history, lookback=lookback)

    hot_scores = {}
    cold_scores = {}
    for n in range(1, MAX_NUM + 1):
        t = temps.get(n, 0.5)
        e = echoes.get(n, 0.0)
        hot_scores[n] = t * (1 - ew) + e * ew
        cold_scores[n] = (1 - t) * (1 - ew) + e * ew

    hot_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: hot_scores[n], reverse=True)
    cold_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: cold_scores[n], reverse=True)

    bet1 = sorted(hot_ranked[:PICK])
    used = set(bet1)

    bet2 = []
    for n in cold_ranked:
        if n not in used and len(bet2) < PICK:
            bet2.append(n)
    bet2 = sorted(bet2[:PICK])

    return [bet1, bet2], ew, strength, accuracy


def phase2_echo_3bet(history, window=50, lookback=50):
    """
    Phase 2 自適應 Echo-Aware 3注
    """
    temps = continuous_temperature(history, window)
    echoes = echo_detector(history, max_lag=5)
    ew, strength, accuracy = adaptive_echo_weight(history, lookback=lookback)

    # 注1: Hot+Echo
    hot_scores = {}
    cold_scores = {}
    for n in range(1, MAX_NUM + 1):
        t = temps.get(n, 0.5)
        e = echoes.get(n, 0.0)
        hot_scores[n] = t * (1 - ew) + e * ew
        cold_scores[n] = (1 - t) * (1 - ew) + e * ew

    hot_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: hot_scores[n], reverse=True)
    bet1 = sorted(hot_ranked[:PICK])
    used = set(bet1)

    # 注2: Cold+Echo
    cold_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: cold_scores[n], reverse=True)
    bet2 = []
    for n in cold_ranked:
        if n not in used and len(bet2) < PICK:
            bet2.append(n)
    bet2 = sorted(bet2[:PICK])
    used.update(bet2)

    # 注3: Echo+Warm (自適應權重也影響 bet3 的 echo 偏好)
    bet3_scores = {}
    for n in range(1, MAX_NUM + 1):
        if n in used:
            continue
        t = temps.get(n, 0.5)
        e = echoes.get(n, 0.0)
        warm_proximity = 1.0 - abs(t - 0.5) * 2.0
        # Phase 2: echo 在 bet3 中的權重也根據信號強度調整
        echo_share = min(0.7, ew * 2)  # echo 強時 bet3 更偏 echo
        bet3_scores[n] = e * echo_share + warm_proximity * (1 - echo_share)

    bet3_ranked = sorted(bet3_scores.keys(), key=lambda n: bet3_scores[n], reverse=True)
    candidates = sorted(bet3_ranked[:12])

    if len(candidates) < PICK:
        candidates = sorted([n for n in range(1, MAX_NUM + 1) if n not in used])

    # 確定性結構選擇
    from itertools import combinations
    best_bet3 = None
    best_score = -1

    if len(candidates) >= PICK:
        for combo in combinations(candidates, PICK):
            bet = sorted(combo)
            sc = structural_score(bet)
            avg_s = sum(bet3_scores.get(n, 0) for n in bet) / PICK
            composite = sc + avg_s * 0.1
            if composite > best_score:
                best_score = composite
                best_bet3 = bet

    if best_bet3 is None:
        best_bet3 = sorted(candidates[:PICK])

    return [bet1, bet2, best_bet3], ew, strength, accuracy


def main():
    history = load_history('BIG_LOTTO')
    if not history:
        print("錯誤: 無法載入大樂透歷史數據")
        sys.exit(1)

    latest = history[-1]
    print(f"大樂透 Echo-Aware Phase 2 預測")
    print(f"數據: {len(history)} 期 (最新: {latest['draw']} {latest['date']})")
    print(f"策略: 自適應 Echo 權重 | Phase 2")
    print("=" * 65)

    # 2注預測
    bets_2, ew_2, str_2, acc_2 = phase2_echo_2bet(history)
    print(f"\n[2注 Phase 2]")
    print(f"  自適應權重: {ew_2:.3f} (信號強度={str_2:.3f}, 命中率={acc_2:.3f})")
    for i, bet in enumerate(bets_2):
        label = "Hot+Echo" if i == 0 else "Cold+Echo"
        print(f"  注{i+1} [{label}]: {bet}")

    # 3注預測
    bets_3, ew_3, str_3, acc_3 = phase2_echo_3bet(history)
    print(f"\n[3注 Phase 2]")
    print(f"  自適應權重: {ew_3:.3f} (信號強度={str_3:.3f}, 命中率={acc_3:.3f})")
    labels = ["Hot+Echo", "Cold+Echo", "Echo+Warm"]
    for i, (bet, label) in enumerate(zip(bets_3, labels)):
        sc = structural_score(bet)
        print(f"  注{i+1} [{label}]: {bet}  結構分: {sc}/10")

    # 覆蓋分析
    all_nums_3 = set()
    for b in bets_3:
        all_nums_3.update(b)
    print(f"\n  3注覆蓋: {len(all_nums_3)} 個號碼 ({len(all_nums_3)/MAX_NUM*100:.1f}%)")

    # 與 Phase 1 固定權重對比
    from predict_biglotto_echo_2bet import echo_aware_deviation_2bet
    from predict_biglotto_echo_3bet import echo_aware_mixed_3bet

    p1_2bet = echo_aware_deviation_2bet(history)
    p1_3bet = echo_aware_mixed_3bet(history)

    print(f"\n{'─' * 65}")
    print(f"  Phase 1 vs Phase 2 選號差異:")
    print(f"  2注 Phase 1: {p1_2bet}")
    print(f"  2注 Phase 2: {bets_2}")
    diff_2 = sum(1 for a, b in zip(p1_2bet, bets_2) if a != b)
    print(f"  差異注數: {diff_2}/{len(bets_2)}")

    print(f"  3注 Phase 1: {p1_3bet}")
    print(f"  3注 Phase 2: {bets_3}")
    diff_3 = sum(1 for a, b in zip(p1_3bet, bets_3) if a != b)
    print(f"  差異注數: {diff_3}/{len(bets_3)}")

    print(f"\n{'=' * 65}")
    print(f"  Phase 2: 自適應 Echo 權重 (待回測驗證)")
    print()


if __name__ == '__main__':
    main()
