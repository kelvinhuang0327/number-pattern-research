#!/usr/bin/env python3
"""
大樂透 Quad Strike 4注預測
=========================
策略組成:
  注1: Fourier Rhythm (FFT 週期分析)
  注2: Cold Numbers (冷號逆向思維)
  注3: Tail Balance (尾數平衡覆蓋)
  注4: Gray Zone Gap (灰色地帶長遺漏)

設計目標:
  - 四注完全不重疊 (24 個號碼, 49% 覆蓋率)
  - 突破長期回測 (1500期) 的 Edge 瓶頸
  - 避免 SHORT_MOMENTUM 衰減
"""
import os
import sys
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

np.random.seed(42)

# ========== 策略實作 ==========

def fourier_rhythm_bet(history, window=500):
    """注1: Fourier Rhythm - FFT 週期分析"""
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    max_num = 49

    bitstreams = {i: np.zeros(w) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= max_num:
                bitstreams[n][idx] = 1

    scores = np.zeros(max_num + 1)
    for n in range(1, max_num + 1):
        bh = bitstreams[n]
        if sum(bh) < 2:
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        if len(idx_pos[0]) == 0:
            continue
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        if len(pos_yf) == 0:
            continue
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit_idx = np.where(bh == 1)[0]
            if len(last_hit_idx) > 0:
                last_hit = last_hit_idx[-1]
                gap = (w - 1) - last_hit
                dist_to_peak = abs(gap - period)
                scores[n] = 1.0 / (dist_to_peak + 1.0)

    all_idx = np.arange(1, max_num + 1)
    sorted_idx = all_idx[np.argsort(scores[1:])[::-1]]
    return sorted(sorted_idx[:6].tolist())


def cold_numbers_bet(history, window=100, exclude=None):
    """注2: Cold Numbers - 冷號逆向思維"""
    if exclude is None:
        exclude = set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    candidates = [n for n in range(1, 50) if n not in exclude]
    sorted_cold = sorted(candidates, key=lambda x: freq.get(x, 0))
    return sorted(sorted_cold[:6])


def tail_balance_bet(history, window=100, exclude=None):
    """注3: Tail Balance - 尾數平衡覆蓋"""
    if exclude is None:
        exclude = set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)

    tail_groups = {i: [] for i in range(10)}
    for n in range(1, 50):
        if n not in exclude:
            tail = n % 10
            tail_groups[tail].append((n, freq.get(n, 0)))

    for tail in tail_groups:
        tail_groups[tail].sort(key=lambda x: x[1], reverse=True)

    selected = []
    available_tails = [t for t in range(10) if tail_groups[t]]
    available_tails.sort(key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0, reverse=True)

    idx_in_group = {t: 0 for t in range(10)}
    round_num = 0

    while len(selected) < 6:
        for tail in available_tails:
            if len(selected) >= 6:
                break
            group = tail_groups[tail]
            idx = idx_in_group[tail]
            if idx < len(group):
                num, _ = group[idx]
                if num not in selected:
                    selected.append(num)
                    idx_in_group[tail] += 1
        round_num += 1
        if round_num > 10:
            break

    if len(selected) < 6:
        remaining = [n for n in range(1, 50) if n not in selected and n not in exclude]
        remaining.sort(key=lambda x: freq.get(x, 0), reverse=True)
        selected.extend(remaining[:6 - len(selected)])

    return sorted(selected[:6])


def gray_zone_gap_bet(history, window=50, exclude=None):
    """注4: Gray Zone Gap - 灰色地帶選取遺漏期數較長的號碼"""
    if exclude is None:
        exclude = set()
    
    recent = history[-window:] if len(history) >= window else history
    total_w = len(recent)
    expected = total_w * 6 / 49

    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1

    gray_candidates = []
    for n in range(1, 50):
        if n in exclude:
            continue
        dev = freq.get(n, 0) - expected
        if -1.5 <= dev <= 1.5:
            # 計算遺漏期數 (Gap)
            gap = 0
            for j in range(len(history) - 1, -1, -1):
                if n in history[j]['numbers']:
                    gap = len(history) - 1 - j
                    break
                gap = len(history) - j
            gray_candidates.append((n, gap))

    # 按 Gap 降序排列 (遺漏越久越好，屬於均值回歸的潛在爆發點)
    gray_candidates.sort(key=lambda x: x[1], reverse=True)
    
    selected = [n for n, _ in gray_candidates[:6]]
    
    # 補足 6 個號碼
    if len(selected) < 6:
        remaining = [n for n in range(1, 50) if n not in selected and n not in exclude]
        # 剩餘的補高中期頻率的號碼
        freq_100 = Counter()
        for d in history[-100:]:
            for n in d['numbers']:
                freq_100[n] += 1
        remaining.sort(key=lambda x: freq_100.get(x, 0), reverse=True)
        selected.extend(remaining[:6 - len(selected)])

    return sorted(selected[:6])


def generate_quad_strike(history):
    """生成 4 注預測"""
    bet1 = fourier_rhythm_bet(history, window=500)
    exclude1 = set(bet1)
    bet2 = cold_numbers_bet(history, window=100, exclude=exclude1)
    exclude2 = exclude1 | set(bet2)
    bet3 = tail_balance_bet(history, window=100, exclude=exclude2)
    exclude3 = exclude2 | set(bet3)
    bet4 = gray_zone_gap_bet(history, window=50, exclude=exclude3)
    return [bet1, bet2, bet3, bet4]


def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))

    last_draw = draws[-1]
    next_draw = int(last_draw['draw']) + 1

    # 生成預測
    bets = generate_quad_strike(draws)

    # 輸出
    print("=" * 70)
    print(f"  大樂透 BIG LOTTO 4注預測 (Quad Strike) — 第 {next_draw} 期")
    print("=" * 70)
    print(f"  策略: Quad Strike (Fourier + Cold + Tail + Gray Gap)")
    print(f"  上期開獎: {last_draw['draw']} → {last_draw['numbers']}")
    print("=" * 70)
    print()

    strategy_names = [
        "Fourier Rhythm (FFT 週期分析)",
        "Cold Numbers (冷號逆向思維)",
        "Tail Balance (尾數平衡覆蓋)",
        "Gray Zone Gap (灰色地帶長遺漏)"
    ]

    all_nums = set()
    for i, (bet, name) in enumerate(zip(bets, strategy_names)):
        num_str = ", ".join(f"{n:02d}" for n in bet)
        print(f"  注 {i+1}:  [{num_str}]")
        print(f"         └─ {name}")
        all_nums.update(bet)
        print()

    print("-" * 70)
    print(f"  總覆蓋號碼: {len(all_nums)}/49 ({len(all_nums)/49*100:.1f}%)")
    print("=" * 70)


if __name__ == "__main__":
    main()
