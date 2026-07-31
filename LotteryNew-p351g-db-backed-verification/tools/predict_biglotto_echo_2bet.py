#!/usr/bin/env python3
"""
大樂透 2注 Echo-Aware 偏差互補策略

Phase 1 改進: 基於 115000011 期檢討會議
- Echo Detector: 偵測 lag-1~lag-5 回聲號碼
- 連續溫度評分: 取代 binary hot/cold 分類
- 中溫號覆蓋: 消除 gap=8~15 的盲區

基礎: deviation_complement_2bet (Edge +0.91%, 1000期+10種子確定性)
改進目標: 保持確定性，提升 echo 覆蓋率

使用方式:
    python3 tools/predict_biglotto_echo_2bet.py
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


def load_history(lottery_type='BIG_LOTTO'):
    """載入歷史數據"""
    db_path = PROJECT_ROOT / 'lottery_api' / 'data' / 'lottery_v2.db'
    if not db_path.exists():
        db_path = PROJECT_ROOT / 'lottery_api' / 'data' / 'lottery.db'

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT draw, date, numbers, special FROM draws WHERE lottery_type=? ORDER BY date ASC",
        (lottery_type,)
    )
    draws = []
    for row in cursor.fetchall():
        nums = json.loads(row[2]) if row[2] else []
        draws.append({'draw': row[0], 'date': row[1], 'numbers': sorted(nums), 'special': row[3] or 0})
    conn.close()
    return draws


def echo_detector(history, max_lag=5):
    """
    Echo Detector: 偵測近期 lag-1~lag-k 的號碼回聲

    原理: 如果 lag-k 期有多個號碼與最近一期重疊，
          這些「回聲號碼」在下一期重現的條件機率可能偏高。

    Args:
        history: 歷史開獎數據 (舊→新排序)
        max_lag: 最大回看期數

    Returns:
        dict: {number: echo_score} 每個號碼的回聲分數 (0~1)
    """
    if len(history) < max_lag + 1:
        return {}

    latest = set(history[-1]['numbers'])
    echo_scores = Counter()

    for lag in range(1, max_lag + 1):
        past = set(history[-(lag + 1)]['numbers'])
        overlap = latest & past
        overlap_count = len(overlap)

        if overlap_count >= 2:
            # 有顯著重疊 → 這些號碼 + 該期其他號碼都可能回聲
            # 重疊越多、lag 越短，分數越高
            weight = overlap_count / PICK * (1.0 / lag)

            # 已重疊的號碼: 它們可能繼續延續
            for n in overlap:
                echo_scores[n] += weight * 0.5

            # 該期中未重疊的號碼: 它們可能隨回聲一起出現
            echo_candidates = past - latest
            for n in echo_candidates:
                echo_scores[n] += weight * 1.0

    # 標準化到 0~1
    if echo_scores:
        max_score = max(echo_scores.values())
        if max_score > 0:
            for n in echo_scores:
                echo_scores[n] /= max_score

    return dict(echo_scores)


def continuous_temperature(history, window=50):
    """
    連續溫度評分: 每個號碼 1~49 得到一個 0~1 的溫度分數

    組成:
    - freq_component (40%): 近 window 期的出現頻率百分位
    - gap_component (30%): gap 的指數衰減 (gap 小=熱, gap 大=冷)
    - trend_component (30%): 短窗口 vs 長窗口的頻率變化趨勢

    Args:
        history: 歷史開獎數據 (舊→新排序)
        window: 主統計窗口

    Returns:
        dict: {number: temperature} 每個號碼的溫度 (0=極冷, 1=極熱)
    """
    recent = history[-window:] if len(history) > window else history
    short_window = min(20, len(recent))
    short_recent = history[-short_window:] if len(history) > short_window else history

    # 頻率統計
    freq_long = Counter()
    for d in recent:
        for n in d['numbers']:
            freq_long[n] += 1

    freq_short = Counter()
    for d in short_recent:
        for n in d['numbers']:
            freq_short[n] += 1

    # Gap 計算 (距上次出現的期數)
    gaps = {}
    for n in range(1, MAX_NUM + 1):
        gap = 0
        for d in reversed(history):
            if n in d['numbers']:
                break
            gap += 1
        gaps[n] = gap

    # 各分量計算
    temperatures = {}

    # 頻率排名
    freq_values = [freq_long.get(n, 0) for n in range(1, MAX_NUM + 1)]
    freq_sorted = sorted(freq_values)

    for n in range(1, MAX_NUM + 1):
        f = freq_long.get(n, 0)

        # freq_component: 頻率百分位 (0~1)
        rank = sum(1 for v in freq_sorted if v <= f) / MAX_NUM
        freq_component = rank

        # gap_component: 指數衰減 (gap 小→接近1, gap 大→接近0)
        # 使用 median gap 作為基準 (49/6 ≈ 8.17 期)
        median_gap = MAX_NUM / PICK
        gap_component = math.exp(-gaps[n] / median_gap)

        # trend_component: 短期頻率 vs 長期頻率的比值
        expected_short = short_window * PICK / MAX_NUM
        expected_long = len(recent) * PICK / MAX_NUM
        short_ratio = freq_short.get(n, 0) / max(expected_short, 0.1)
        long_ratio = f / max(expected_long, 0.1)
        # 短期比長期高 → 上升趨勢 → 接近1
        trend_component = min(1.0, max(0.0, 0.5 + (short_ratio - long_ratio) * 0.5))

        # 加權合成
        temp = (0.40 * freq_component +
                0.30 * gap_component +
                0.30 * trend_component)

        temperatures[n] = temp

    return temperatures


def echo_aware_deviation_2bet(history, window=50, echo_weight=0.25):
    """
    Echo-Aware 偏差互補 2注

    注1 (Hot+Echo): 高溫度號碼 + 回聲加權
    注2 (Cold+Echo): 低溫度號碼 + 冷回歸回聲加權

    完全確定性: 無隨機成分

    Args:
        history: 歷史開獎數據 (舊→新排序)
        window: 統計窗口
        echo_weight: echo 分數在最終評分中的權重

    Returns:
        [bet1_hot, bet2_cold] 各為 sorted list of 6 numbers
    """
    # 計算溫度和回聲
    temps = continuous_temperature(history, window)
    echoes = echo_detector(history, max_lag=5)

    # 合成評分: 熱注和冷注各自的排序依據
    # Hot 注: temperature * (1 - echo_weight) + echo_score * echo_weight
    # Cold 注: (1 - temperature) * (1 - echo_weight) + echo_score * echo_weight
    hot_scores = {}
    cold_scores = {}

    for n in range(1, MAX_NUM + 1):
        t = temps.get(n, 0.5)
        e = echoes.get(n, 0.0)

        hot_scores[n] = t * (1 - echo_weight) + e * echo_weight
        cold_scores[n] = (1 - t) * (1 - echo_weight) + e * echo_weight

    # 排序選號
    hot_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: hot_scores[n], reverse=True)
    cold_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: cold_scores[n], reverse=True)

    # 注1: Hot — 取 hot_scores 最高的 6 個
    bet1 = sorted(hot_ranked[:PICK])
    used = set(bet1)

    # 注2: Cold — 取 cold_scores 最高的，排除已用
    bet2 = []
    for n in cold_ranked:
        if n not in used and len(bet2) < PICK:
            bet2.append(n)
    bet2 = sorted(bet2[:PICK])

    return [bet1, bet2]


def main():
    history = load_history('BIG_LOTTO')
    if not history:
        print("錯誤: 無法載入大樂透歷史數據")
        sys.exit(1)

    latest = history[-1]
    print(f"大樂透 2注 Echo-Aware 偏差互補預測")
    print(f"數據: {len(history)} 期 (最新: {latest['draw']} {latest['date']})")
    print(f"策略: Echo Detector + 連續溫度評分 | Phase 1 改進版")
    print("=" * 60)

    bets = echo_aware_deviation_2bet(history, window=50)

    # 溫度和回聲分析
    temps = continuous_temperature(history, window=50)
    echoes = echo_detector(history, max_lag=5)

    for i, bet in enumerate(bets):
        label = "Hot+Echo (趨勢+回聲)" if i == 0 else "Cold+Echo (回歸+回聲)"
        avg_temp = sum(temps.get(n, 0) for n in bet) / len(bet)
        echo_nums = [n for n in bet if echoes.get(n, 0) > 0.3]

        print(f"\n  注{i+1} [{label}]: {bet}")
        print(f"       平均溫度: {avg_temp:.3f}")
        if echo_nums:
            print(f"       回聲號碼: {echo_nums}")

        # 各號碼詳情
        for n in bet:
            t = temps.get(n, 0)
            e = echoes.get(n, 0)
            status = []
            if t > 0.7:
                status.append("HOT")
            elif t < 0.3:
                status.append("COLD")
            else:
                status.append("WARM")
            if e > 0.3:
                status.append(f"ECHO={e:.2f}")
            print(f"         {n:2d}: temp={t:.3f} echo={e:.3f} [{', '.join(status)}]")

    # 覆蓋分析
    all_nums = set(bets[0]) | set(bets[1])
    overlap = set(bets[0]) & set(bets[1])
    print(f"\n  覆蓋: {len(all_nums)} 個號碼 ({len(all_nums)/MAX_NUM*100:.1f}%)")
    print(f"  重疊: {len(overlap)} 個")

    # 回聲偵測總結
    echo_all = {n: s for n, s in echoes.items() if s > 0.1}
    if echo_all:
        print(f"\n  回聲偵測: {len(echo_all)} 個候選號碼")
        for n in sorted(echo_all, key=echo_all.get, reverse=True)[:10]:
            covered = "<<已覆蓋>>" if n in all_nums else ""
            print(f"    {n:2d}: echo={echo_all[n]:.3f} {covered}")

    print(f"\n{'='*60}")
    print(f"  基礎: 偏差互補 2注 (Edge +0.91%)")
    print(f"  改進: Echo Detector + 連續溫度 (待回測驗證)")
    print()


if __name__ == '__main__':
    main()
