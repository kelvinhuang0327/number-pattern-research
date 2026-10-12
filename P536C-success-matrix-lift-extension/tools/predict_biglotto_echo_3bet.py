#!/usr/bin/env python3
"""
大樂透 3注 Echo-Aware 混合策略

Phase 1 改進: 基於 115000011 期檢討會議
- 注1 (Hot+Echo): 高溫度 + 回聲加權
- 注2 (Cold+Echo): 低溫度 + 冷回歸回聲加權
- 注3 (Echo+Warm): 回聲候選 + 中溫號覆蓋 (取代舊的結構過濾)

基礎: mixed_3bet (Edge +1.01% ± 0.23%, 1000期+10種子)
改進目標: 第3注從結構過濾改為 echo+中溫，提升覆蓋盲區

使用方式:
    python3 tools/predict_biglotto_echo_3bet.py
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

# Import shared functions from 2bet module
sys.path.insert(0, str(PROJECT_ROOT / 'tools'))
from predict_biglotto_echo_2bet import (
    load_history, echo_detector, continuous_temperature
)


def structural_score(bet):
    """評估一注的結構合理性"""
    s = sum(bet)
    odd = sum(1 for n in bet if n % 2 == 1)
    zones = [0, 0, 0]
    for n in bet:
        if n <= 16:
            zones[0] += 1
        elif n <= 33:
            zones[1] += 1
        else:
            zones[2] += 1
    consec = sum(1 for i in range(len(bet) - 1) if bet[i + 1] - bet[i] == 1)
    spread = bet[-1] - bet[0]

    score = 0
    if 100 <= s <= 200:
        score += 2
    if 120 <= s <= 180:
        score += 2
    if 2 <= odd <= 4:
        score += 2
    if all(z >= 1 for z in zones):
        score += 2
    if consec <= 1:
        score += 1
    if spread >= 25:
        score += 1
    return score


def echo_aware_mixed_3bet(history, window=50, echo_weight=0.25):
    """
    Echo-Aware 混合策略 3注

    注1 (Hot+Echo): 高溫度 + 回聲加權
    注2 (Cold+Echo): 低溫度 + 冷回歸回聲加權
    注3 (Echo+Warm): 回聲候選 + 中溫覆蓋 + 結構品質控制

    Args:
        history: 歷史開獎數據 (舊→新排序)
        window: 統計窗口
        echo_weight: echo 分數權重

    Returns:
        [bet1_hot, bet2_cold, bet3_echo_warm]
    """
    temps = continuous_temperature(history, window)
    echoes = echo_detector(history, max_lag=5)

    # Hot/Cold 評分
    hot_scores = {}
    cold_scores = {}
    for n in range(1, MAX_NUM + 1):
        t = temps.get(n, 0.5)
        e = echoes.get(n, 0.0)
        hot_scores[n] = t * (1 - echo_weight) + e * echo_weight
        cold_scores[n] = (1 - t) * (1 - echo_weight) + e * echo_weight

    # 注1: Hot
    hot_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: hot_scores[n], reverse=True)
    bet1 = sorted(hot_ranked[:PICK])
    used = set(bet1)

    # 注2: Cold
    cold_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: cold_scores[n], reverse=True)
    bet2 = []
    for n in cold_ranked:
        if n not in used and len(bet2) < PICK:
            bet2.append(n)
    bet2 = sorted(bet2[:PICK])
    used.update(bet2)

    # 注3: Echo + Warm (中溫 + 回聲候選)
    # 評分: echo_score * 0.5 + warm_proximity * 0.3 + structural_bonus * 0.2
    # warm_proximity = 1 - |temperature - 0.5| * 2  (越接近0.5越高)
    bet3_scores = {}
    for n in range(1, MAX_NUM + 1):
        if n in used:
            continue
        t = temps.get(n, 0.5)
        e = echoes.get(n, 0.0)
        warm_proximity = 1.0 - abs(t - 0.5) * 2.0
        bet3_scores[n] = e * 0.5 + warm_proximity * 0.5

    # 從候選池中選出最佳結構的 6 個
    bet3_ranked = sorted(bet3_scores.keys(), key=lambda n: bet3_scores[n], reverse=True)

    # 取 top 18 候選，找結構最好的組合
    candidates = bet3_ranked[:18]

    if len(candidates) < PICK:
        candidates = [n for n in range(1, MAX_NUM + 1) if n not in used]

    # 確定性選擇: 貪心+結構評估
    # 用 top candidates 依序組合，保留結構分最高的
    best_bet3 = None
    best_score = -1

    # 確定性: 從 top candidates 按序嘗試所有 C(min(12,len), 6) 組合中結構最好的
    # 為效率限制候選為 top 12
    top_candidates = sorted(candidates[:12])

    if len(top_candidates) >= PICK:
        from itertools import combinations
        for combo in combinations(top_candidates, PICK):
            bet = sorted(combo)
            sc = structural_score(bet)
            # 加入 echo+warm 分數作為 tiebreaker
            avg_bet3_score = sum(bet3_scores.get(n, 0) for n in bet) / PICK
            composite = sc + avg_bet3_score * 0.1
            if composite > best_score:
                best_score = composite
                best_bet3 = bet

    if best_bet3 is None:
        best_bet3 = sorted(candidates[:PICK])

    return [bet1, bet2, best_bet3]


def main():
    history = load_history('BIG_LOTTO')
    if not history:
        print("錯誤: 無法載入大樂透歷史數據")
        sys.exit(1)

    latest = history[-1]
    print(f"大樂透 3注 Echo-Aware 混合策略預測")
    print(f"數據: {len(history)} 期 (最新: {latest['draw']} {latest['date']})")
    print(f"策略: Echo+溫度 2注 + Echo+中溫 1注 | Phase 1 改進版")
    print("=" * 65)

    bets = echo_aware_mixed_3bet(history, window=50)

    temps = continuous_temperature(history, window=50)
    echoes = echo_detector(history, max_lag=5)

    labels = [
        "1-Hot+Echo  趨勢+回聲",
        "2-Cold+Echo 回歸+回聲",
        "3-Echo+Warm 回聲+中溫",
    ]

    for i, (bet, label) in enumerate(zip(bets, labels)):
        avg_temp = sum(temps.get(n, 0) for n in bet) / len(bet)
        echo_nums = [n for n in bet if echoes.get(n, 0) > 0.3]
        sc = structural_score(bet)

        print(f"\n  注 [{label}]: {bet}")
        print(f"    溫度: {avg_temp:.3f} | 結構分: {sc}/10 | 回聲號: {echo_nums if echo_nums else '無'}")

        for n in bet:
            t = temps.get(n, 0)
            e = echoes.get(n, 0)
            tags = []
            if t > 0.7:
                tags.append("HOT")
            elif t < 0.3:
                tags.append("COLD")
            else:
                tags.append("WARM")
            if e > 0.3:
                tags.append(f"ECHO")
            print(f"      {n:2d}: temp={t:.3f} echo={e:.3f} [{', '.join(tags)}]")

    # 覆蓋分析
    all_nums = set()
    for b in bets:
        all_nums.update(b)
    print(f"\n  {'─' * 55}")
    print(f"  覆蓋: {len(all_nums)} 個號碼 ({len(all_nums) / MAX_NUM * 100:.1f}%)")

    for i in range(len(bets)):
        for j in range(i + 1, len(bets)):
            ov = set(bets[i]) & set(bets[j])
            print(f"  注{i + 1} ∩ 注{j + 1} 重疊: {len(ov)} 個 {sorted(ov) if ov else ''}")

    print(f"\n{'=' * 65}")
    print(f"  基礎: 混合 3注 (Edge +1.01% ± 0.23%)")
    print(f"  改進: Echo + 連續溫度 + 中溫覆蓋 (待回測驗證)")
    print()


if __name__ == '__main__':
    main()
