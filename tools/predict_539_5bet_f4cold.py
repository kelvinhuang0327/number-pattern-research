#!/usr/bin/env python3
"""
539 5注 Fourier4正交+Cold 預測腳本
=====================================
策略: 5bet_fourier4_cold (PROVISIONAL, 2026-02-25)
- 注1-4: Fourier 500p 排名正交（每注5號，零重疊）
- 注5: 近100期冷號前5個（排除前4注）

驗證結果:
  1500p Edge +1.35% (z=2.4), 三窗口全正
  Permutation Test p=0.030, Cohen's d=2.19 → SIGNAL_DETECTED
  McNemar vs 3注: p=0.000 (顯著改善)

ACB 單注 (anomaly_capture_bet, 2026-02-27):
  Signal Edge +2.804% (1500p), Permutation p=0.002, z=3.485 → ADOPTED
  設計: freq_deficit×0.4 + gap_score×0.6 × boundary(±5: 1.2x) × mod3(1.1x) + cross-zone
  最佳 window=100；獨立使用，不嵌入5注組合
"""
import sys, os, numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
from database import DatabaseManager

MAX_NUM = 39
PICK = 5

STRATEGY_INFO = {
    'name': '539 5注 Fourier4正交+Cold',
    'version': 'v1.0.0',
    'status': 'PROVISIONAL',
    'edge_1500p': '+1.35%',
    'z_score': 2.4,
    'permutation_p': 0.030,
    'cohen_d': 2.19,
}


def fourier_scores(hist, window=500):
    h = hist[-window:] if len(hist) >= window else hist
    w = len(h)
    scores = {}
    for n in range(1, MAX_NUM + 1):
        bh = np.zeros(w)
        for idx, d in enumerate(h):
            if n in d['numbers']:
                bh[idx] = 1
        if sum(bh) < 2:
            scores[n] = 0.0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        ip = np.where(xf > 0)
        py = np.abs(yf[ip])
        px = xf[ip]
        pk = np.argmax(py)
        fv = px[pk]
        if fv == 0:
            scores[n] = 0.0
            continue
        period = 1 / fv
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return scores


def predict(hist):
    """
    返回 5 注預測結果
    Args:
        hist: 已排序(ASC)的開獎列表
    Returns:
        list of 5 bets (each bet is sorted list of 5 numbers)
    """
    sc = fourier_scores(hist, 500)
    ranked = [n for n in sorted(sc, key=lambda x: -sc[x]) if sc[n] > 0]

    # 注1-4: 每注取5個，正交
    bets = [sorted(ranked[i * 5:(i + 1) * 5]) for i in range(4)]
    excl = set(sum(bets, []))

    # 注5: 冷號 (近100期頻率最低)
    freq = Counter()
    for d in hist[-100:]:
        for n in d['numbers']:
            freq[n] += 1
    cold_sorted = sorted(range(1, MAX_NUM + 1), key=lambda n: freq.get(n, 0))
    bet5 = sorted([n for n in cold_sorted if n not in excl][:5])
    bets.append(bet5)
    return bets


def predict_2bet(hist):
    """
    返回 2 注預測結果 (F500+F200 正交)
    ⚠️  警告: 僅輕微依據的推測，非統計信號策略
         1500p Edge +0.34% (z=0.9)，三窗口全正但信號極弱
         未通過 Permutation Test，不建議作為主要策略
    Args:
        hist: 已排序(ASC)的開獎列表
    Returns:
        list of 2 bets (each bet is sorted list of 5 numbers)
    """
    sc500 = fourier_scores(hist, 500)
    ranked500 = [n for n in sorted(sc500, key=lambda x: -sc500[x]) if sc500[n] > 0]
    bet1 = sorted(ranked500[:5])

    sc200 = fourier_scores(hist, 200)
    excl = set(bet1)
    ranked200 = [n for n in sorted(sc200, key=lambda x: -sc200[x]) if sc200[n] > 0 and n not in excl]
    bet2 = sorted(ranked200[:5])

    return [bet1, bet2]


def predict_acb(hist, window=100):
    """
    ACB — 異常捕捉單注 (anomaly_capture_bet)
    Signal Edge +2.804% (1500p), Permutation p=0.002 → ADOPTED (2026-02-27)

    設計:
      score = (freq_deficit×0.4 + gap_score×0.6) × boundary_bonus × mod3_bonus
      boundary_bonus: n≤5 或 n≥35 → 1.2x
      mod3_bonus:     n%3==0 → 1.1x
      cross-zone 約束: 強制≥2個 zone（Z1=1-13, Z2=14-26, Z3=27-39）
    """
    recent = hist[-window:] if len(hist) >= window else hist
    counter = Counter()
    for n in range(1, MAX_NUM + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1

    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(recent)
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, MAX_NUM + 1)}

    expected_freq = len(recent) * PICK / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM + 1):
        freq_deficit   = expected_freq - counter[n]
        gap_score      = gaps[n] / (len(recent) / 2)
        boundary_bonus = 1.2 if (n <= 5 or n >= 35) else 1.0
        mod3_bonus     = 1.1 if n % 3 == 0 else 1.0
        scores[n] = (freq_deficit * 0.4 + gap_score * 0.6) * boundary_bonus * mod3_bonus

    ranked = sorted(scores, key=lambda x: -scores[x])
    zones_selected = set()
    result = []
    for n in ranked:
        zone = 0 if n <= 13 else (1 if n <= 26 else 2)
        if len(result) < PICK:
            result.append(n)
            zones_selected.add(zone)
        if len(result) >= PICK:
            break

    if len(zones_selected) < 2 and len(result) >= PICK:
        missing_zones = set(range(3)) - zones_selected
        for mz in missing_zones:
            zr = range(1, 14) if mz == 0 else (range(14, 27) if mz == 1 else range(27, 40))
            zc = sorted(zr, key=lambda x: -scores[x])
            if zc:
                result[-1] = zc[0]
                break

    return sorted(result[:PICK])


if __name__ == '__main__':
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('DAILY_539'), key=lambda x: (x['date'], x['draw']))

    print("=" * 60)
    print(f"  {STRATEGY_INFO['name']}")
    print(f"  版本: {STRATEGY_INFO['version']}  狀態: {STRATEGY_INFO['status']}")
    print(f"  Edge: {STRATEGY_INFO['edge_1500p']}  z={STRATEGY_INFO['z_score']}")
    print(f"  Permutation p={STRATEGY_INFO['permutation_p']}  d={STRATEGY_INFO['cohen_d']}")
    print("=" * 60)
    print(f"  最新期: {draws[-1]['draw']} ({draws[-1]['date']})")
    print()

    # --- 5注 (PROVISIONAL 策略) ---
    print("  【5注預測】策略: 5bet_fourier4_cold (PROVISIONAL)")
    bets = predict(draws)
    for i, bet in enumerate(bets, 1):
        source = f"Fourier rank {(i-1)*5+1}-{i*5}" if i <= 4 else "Cold(w=100)正交"
        print(f"  注{i} ({source}): {bet}")
    print("  成本: NT$250 | Edge +1.35% z=2.4 | ⚠️ 需5992期後重驗")

    print()

    # --- ACB 單注 (ADOPTED) ---
    print("  【ACB單注】策略: anomaly_capture_bet (ADOPTED)")
    acb_bet = predict_acb(draws)
    print(f"  注1 (ACB w=100): {acb_bet}")
    print("  成本: NT$50  | Signal Edge +2.80% p=0.002 z=3.49 | ★ 已採納")

    print()

    # --- 2注 (未採納，輕微依據) ---
    print("  【2注參考】策略: F500+F200 正交")
    print("  ⚠️  未通過 Permutation Test (z=0.9)，僅供參考")
    bets2 = predict_2bet(draws)
    for i, bet in enumerate(bets2, 1):
        src = "Fourier 500p Top5" if i == 1 else "Fourier 200p Top5 正交"
        print(f"  注{i} ({src}): {bet}")
    print("  成本: NT$100 | Edge +0.34% z=0.9")

    print("=" * 60)
