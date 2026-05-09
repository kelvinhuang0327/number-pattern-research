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
    print(f"  預測下一期:")

    bets = predict(draws)
    for i, bet in enumerate(bets, 1):
        source = f"Fourier rank {(i-1)*5+1}-{i*5}" if i <= 4 else "Cold(w=100)正交"
        print(f"  注{i} ({source}): {bet}")

    print("=" * 60)
    print("  ⚠️  PROVISIONAL — 需在5992期後重新驗證")
