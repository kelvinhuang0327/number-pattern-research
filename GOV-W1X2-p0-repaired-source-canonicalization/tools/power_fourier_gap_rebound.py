#!/usr/bin/env python3
"""
Power Lotto Fourier + Gap Rebound (威力彩 傅立葉+間隔反彈策略)
==============================================================
基於 power_fourier_rhythm.py 增強:
- 原始 Fourier Rhythm: FFT 週期偵測 + 間隔到期評分
- 新增 Gap Rebound: freq30>=3 且 gap>1.2x平均間隔 的號碼額外加權

邏輯:
1. FFT 偵測每個號碼的主週期
2. 評分 = Fourier到期分 + Gap Rebound加權
3. Gap Rebound: 近30期有出現(非冷號)但最近X期消失 → 反彈候選

來源: 115000011期檢討發現 28號(gap=12, freq30=4)被所有方法漏掉
"""
import os
import sys
import numpy as np
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))


def detect_dominant_period(ball_history):
    """FFT 偵測主週期"""
    n = len(ball_history)
    if sum(ball_history) < 2:
        return None
    yf = fft(ball_history - np.mean(ball_history))
    xf = fftfreq(n, 1)
    idx = np.where(xf > 0)
    pos_xf = xf[idx]
    pos_yf = np.abs(yf[idx])
    peak_idx = np.argmax(pos_yf)
    freq = pos_xf[peak_idx]
    if freq == 0:
        return None
    return 1 / freq


def fourier_gap_rebound_predict(history, n_bets=2, window=500,
                                 gap_threshold=1.2, gap_min_freq=3,
                                 gap_weight=1.5):
    """
    Fourier + Gap Rebound 預測

    Parameters:
        history: 歷史開獎資料 list[dict]
        n_bets: 注數
        window: Fourier 分析窗口
        gap_threshold: gap > threshold * avg_gap 才觸發 rebound
        gap_min_freq: 近30期最低出現次數(排除真冷號)
        gap_weight: gap rebound 加權分數
    """
    h_slice = history[-window:]
    max_num = 38  # Power Lotto

    # 1. Fourier bitstream analysis
    bitstreams = {i: np.zeros(len(h_slice)) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if 1 <= n <= max_num:
                bitstreams[n][idx] = 1

    scores = np.zeros(max_num + 1)
    for n in range(1, max_num + 1):
        period = detect_dominant_period(bitstreams[n])
        if period and 2 < period < len(h_slice) / 2:
            last_hit = np.where(bitstreams[n] == 1)[0][-1]
            gap = (len(h_slice) - 1) - last_hit
            dist_to_peak = abs(gap - period)
            scores[n] = 1.0 / (dist_to_peak + 1.0)

    # 2. Gap Rebound signal (使用近30期)
    recent30 = history[-30:] if len(history) >= 30 else history
    from collections import Counter
    freq30 = Counter()
    for d in recent30:
        for n in d['numbers']:
            freq30[n] += 1

    # 計算每個號碼距上次出現的期數
    num_last_seen_gap = {}
    for i, d in enumerate(recent30):
        for n in d['numbers']:
            num_last_seen_gap[n] = len(recent30) - 1 - i  # 0 = 最近一期

    avg_gap = max_num / 6.0  # ~6.33 for 38 choose 6

    for n in range(1, max_num + 1):
        f = freq30.get(n, 0)
        if f >= gap_min_freq and n in num_last_seen_gap:
            gap = num_last_seen_gap[n]
            if gap > avg_gap * gap_threshold:
                # Gap rebound bonus: 越久未出現 bonus 越大
                bonus = gap_weight * (gap / avg_gap - gap_threshold + 1)
                scores[n] += bonus

    # 3. 排序與分注
    all_indices = np.arange(1, max_num + 1)
    sorted_indices = all_indices[np.argsort(scores[1:])[::-1]]

    bets = []
    for i in range(n_bets):
        start = i * 6
        end = (i + 1) * 6
        bets.append(sorted(sorted_indices[start:end].tolist()))

    return bets


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='威力彩 Fourier + Gap Rebound')
    parser.add_argument('--n', type=int, default=1000, help='回測期數')
    parser.add_argument('--bets', type=int, default=2, help='注數')
    parser.add_argument('--gap-threshold', type=float, default=1.2)
    parser.add_argument('--gap-min-freq', type=int, default=3)
    parser.add_argument('--gap-weight', type=float, default=1.5)
    args = parser.parse_args()

    from tools.verify_strategy_longterm import UnifiedAuditor
    auditor = UnifiedAuditor(lottery_type='POWER_LOTTO')

    def audit_bridge(history, num_bets=2):
        return fourier_gap_rebound_predict(
            history, n_bets=num_bets,
            gap_threshold=args.gap_threshold,
            gap_min_freq=args.gap_min_freq,
            gap_weight=args.gap_weight
        )

    auditor.audit(audit_bridge, n=args.n, num_bets=args.bets)
