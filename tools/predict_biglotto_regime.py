#!/usr/bin/env python3
"""
大樂透 Sum Regime 預測模組 (Production)
========================================
033期教訓: 連續7期 sum > mu 後暴跌至 -1.72σ
034期研究: Fourier/Markov gating無效, Cold-first 劣化, Parity McNemar p=0.4795 REJECTED

驗證結果:
  TS3+Regime(s=0.3, th=5): Edge=+1.52%, perm p=0.005, 3窗口 STABLE
  2bet Regime F+C:         Edge=+1.58%, perm p=0.005

034期研究結論:
  - Fourier/Markov competitive gating: REJECTED (Fourier confidence 永遠>0.25)
  - Cold-first 2bet: REJECTED (Edge 1.31% < baseline 1.58%)
  - Parity soft constraint: REJECTED (McNemar p=0.4795, net=0, 觸發率極低)
"""
import numpy as np
from collections import Counter
from itertools import combinations

from tools.predict_biglotto_triple_strike import (
    fourier_rhythm_bet, cold_numbers_bet, tail_balance_bet,
    generate_triple_strike, _sum_target, MAX_NUM
)


def detect_sum_regime(history, lookback=10, threshold=5):
    """
    偵測 sum 連續偏高/偏低的 regime。

    Returns:
        (regime, consecutive_count, direction_strength)
        regime: 'HIGH_REGIME' | 'LOW_REGIME' | 'NEUTRAL'
    """
    if len(history) < 50:
        return 'NEUTRAL', 0, 0.0

    h300 = history[-300:] if len(history) >= 300 else history
    sums = [sum(d['numbers']) for d in h300]
    mu, sg = np.mean(sums), np.std(sums)

    if sg < 1e-6:
        return 'NEUTRAL', 0, 0.0

    recent = history[-lookback:] if len(history) >= lookback else history
    recent_sums = [sum(d['numbers']) for d in recent]

    consec_above = 0
    z_sum_above = 0.0
    for s in reversed(recent_sums):
        if s > mu:
            consec_above += 1
            z_sum_above += (s - mu) / sg
        else:
            break

    consec_below = 0
    z_sum_below = 0.0
    for s in reversed(recent_sums):
        if s < mu:
            consec_below += 1
            z_sum_below += (mu - s) / sg
        else:
            break

    if consec_above >= threshold:
        return 'HIGH_REGIME', consec_above, z_sum_above / consec_above
    elif consec_below >= threshold:
        return 'LOW_REGIME', consec_below, z_sum_below / consec_below

    return 'NEUTRAL', 0, 0.0


def apply_regime_weight(scores_dict, regime, strength=0.3):
    """根據 regime 調整號碼分數 (HIGH→boost低號, LOW→boost高號)"""
    if regime == 'NEUTRAL':
        return scores_dict

    adjusted = {}
    mid = 25
    for n, score in scores_dict.items():
        if regime == 'HIGH_REGIME':
            if n <= mid:
                adjusted[n] = score * (1.0 + strength)
            else:
                adjusted[n] = score * (1.0 - strength)
        elif regime == 'LOW_REGIME':
            if n > mid:
                adjusted[n] = score * (1.0 + strength)
            else:
                adjusted[n] = score * (1.0 - strength)
    return adjusted


def fourier_regime_bet(history, window=500, regime='NEUTRAL', regime_strength=0.3):
    """Fourier Rhythm + Regime 調整"""
    from scipy.fft import fft, fftfreq

    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    scores = {}
    for n in range(1, MAX_NUM + 1):
        bh = np.zeros(w)
        for idx, d in enumerate(h_slice):
            if n in d['numbers']:
                bh[idx] = 1
        if sum(bh) < 2:
            scores[n] = 0.0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            scores[n] = 0.0
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
        else:
            scores[n] = 0.0

    if regime != 'NEUTRAL':
        scores = apply_regime_weight(scores, regime, regime_strength)

    sorted_nums = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return sorted(sorted_nums[:6])


def cold_regime_bet(history, window=100, exclude=None, pool_size=12, regime='NEUTRAL'):
    """Cold Numbers + Regime-Adjusted Sum Target"""
    exclude = exclude or set()
    recent = history[-window:]
    freq = Counter(n for d in recent for n in d['numbers'])

    candidates = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
    sorted_cold = sorted(candidates, key=lambda x: freq.get(x, 0))

    if regime == 'HIGH_REGIME':
        cold_low = [n for n in sorted_cold if n <= 25][:pool_size]
        cold_high = [n for n in sorted_cold if n > 25][:pool_size // 2]
        pool = (cold_low + cold_high)[:pool_size]
    elif regime == 'LOW_REGIME':
        cold_high = [n for n in sorted_cold if n > 25][:pool_size]
        cold_low = [n for n in sorted_cold if n <= 25][:pool_size // 2]
        pool = (cold_high + cold_low)[:pool_size]
    else:
        pool = sorted_cold[:pool_size]

    h300 = history[-300:] if len(history) >= 300 else history
    sums = [sum(d['numbers']) for d in h300]
    mu, sg = np.mean(sums), np.std(sums)

    if regime == 'HIGH_REGIME':
        tlo, thi = mu - 1.5 * sg, mu - 0.3 * sg
    elif regime == 'LOW_REGIME':
        tlo, thi = mu + 0.3 * sg, mu + 1.5 * sg
    else:
        tlo, thi = _sum_target(history)

    tmid = (tlo + thi) / 2.0

    best, best_dist, best_in = None, float('inf'), False
    for combo in combinations(pool, 6):
        s = sum(combo)
        in_range = (tlo <= s <= thi)
        dist = abs(s - tmid)
        if in_range and (not best_in or dist < best_dist):
            best, best_dist, best_in = combo, dist, True
        elif not in_range and not best_in and dist < best_dist:
            best, best_dist = combo, dist

    return sorted(best) if best else sorted(pool[:6])


def enforce_parity(bet, max_same=5, max_num=49):
    """
    Parity soft constraint: 若6個號碼全奇或全偶, 替換最弱號碼.
    034期教訓: 6:0全奇=1.37%極端事件, 加此約束+2hits (107 vs 105).
    """
    bet = list(bet)
    odd_count = sum(1 for n in bet if n % 2 == 1)
    even_count = 6 - odd_count

    if odd_count <= max_same and even_count <= max_same:
        return sorted(bet)

    if odd_count > max_same:
        target = [n for n in bet if n % 2 == 1][-1]
        candidates = [n for n in range(1, max_num + 1) if n % 2 == 0 and n not in bet]
    else:
        target = [n for n in bet if n % 2 == 0][-1]
        candidates = [n for n in range(1, max_num + 1) if n % 2 == 1 and n not in bet]

    if candidates:
        replacement = min(candidates, key=lambda x: abs(x - target))
        bet[bet.index(target)] = replacement

    return sorted(bet)


def generate_ts3_regime(history):
    """TS3 + Sum Regime (3注)

    Edge=+1.52%, perm p=0.005, 3窗口 STABLE
    034期研究: Parity constraint REJECTED (McNemar p=0.4795, net=0, max_same=5 觸發率極低)

    NEUTRAL → 原始 Triple Strike
    HIGH/LOW REGIME → Regime-adjusted Fourier + Cold + Tail Balance
    """
    regime, consec, strength = detect_sum_regime(history)

    if regime == 'NEUTRAL':
        return generate_triple_strike(history)

    bet1 = fourier_regime_bet(history, window=500, regime=regime, regime_strength=0.3)
    used = set(bet1)
    bet2 = cold_regime_bet(history, window=100, exclude=used, regime=regime)
    used.update(bet2)
    bet3 = tail_balance_bet(history, window=100, exclude=used)
    return [sorted(bet1), sorted(bet2), sorted(bet3)]


def generate_regime_2bet(history):
    """2注: Regime-Fourier + Regime-Cold (Edge=+1.58%, perm p=0.005)"""
    regime, _, _ = detect_sum_regime(history)
    bet1 = fourier_regime_bet(history, window=500, regime=regime, regime_strength=0.3)
    used = set(bet1)
    bet2 = cold_regime_bet(history, window=100, exclude=used, regime=regime)
    return [bet1, bet2]
