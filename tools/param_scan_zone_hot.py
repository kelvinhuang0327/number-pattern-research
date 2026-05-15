#!/usr/bin/env python3
"""
Zone Cascade + Hot-Streak 參數掃描
========================================
掃描：
  1. Zone boost: [0.03, 0.06, 0.09, 0.12]
  2. HS boost rate: [0.02, 0.04, 0.06, 0.08]
  3. 單獨 Zone / 單獨 HS / 兩者組合
  4. 每個組合跑 3-bet 1500期回測

目標：找到 三窗口全正 + 整體edge最大 的最佳參數
"""
import sys, os, math, json
import numpy as np
from collections import Counter
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
from database import DatabaseManager
from numpy.fft import fft, fftfreq

# ---- 精簡 agents (同 backtest) ----

def _normalize(scores):
    vals = list(scores.values())
    mn, mx = min(vals), max(vals)
    r = mx - mn
    if r == 0: return {n: 0.5 for n in scores}
    return {n: (v - mn) / r for n, v in scores.items()}

def _fourier_score(h, w=500, mx=49):
    hh = h[-w:] if len(h) >= w else h; ww = len(hh); sc = {}
    for n in range(1, mx+1):
        bh = np.zeros(ww)
        for i, d in enumerate(hh):
            if n in d['numbers']: bh[i] = 1
        if sum(bh) < 2: sc[n] = 0.0; continue
        yf = fft(bh - np.mean(bh)); xf = fftfreq(ww, 1)
        ip = np.where(xf > 0); py = np.abs(yf[ip]); px = xf[ip]
        if len(py) == 0: sc[n] = 0.0; continue
        pi = np.argmax(py); fv = px[pi]
        if fv == 0: sc[n] = 0.0; continue
        la = np.where(bh == 1)[0]; li = la[-1] if len(la) else -1
        sc[n] = 1.0 / (abs((ww-1-li) - 1.0/fv) + 1.0)
    return sc

def _cold_score(h, w=100, mx=49):
    r = h[-w:] if len(h) >= w else h; ls = {}
    for i, d in enumerate(r):
        for n in d['numbers']: ls[n] = i
    sc = {n: float(len(r) - ls.get(n, -1)) for n in range(1, mx+1)}
    m = max(sc.values()) or 1.0
    return {n: s/m for n, s in sc.items()}

def _neighbor_score(h, mx=49):
    sc = {n: 0.0 for n in range(1, mx+1)}
    for pn in h[-1]['numbers']:
        for d in (-1, 0, 1):
            nn = pn+d
            if 1 <= nn <= mx: sc[nn] += 1.0 if d == 0 else 0.7
    return sc

def _markov_score(h, w=30, mx=49):
    r = h[-w:] if len(h) >= w else h; tr = {}
    for i in range(len(r)-1):
        for pn in r[i]['numbers']:
            if pn not in tr: tr[pn] = Counter()
            for nn in r[i+1]['numbers']: tr[pn][nn] += 1
    sc = {n: 0.0 for n in range(1, mx+1)}
    for pn in h[-1]['numbers']:
        t = tr.get(pn, Counter()); tot = sum(t.values())
        if tot > 0:
            for n, c in t.items(): sc[n] += c/tot
    return sc

def _consensus_score(h, mx=49):
    s1 = _normalize(_cold_score(h, mx=mx))
    s2 = _normalize(_fourier_score(h, mx=mx))
    s3 = _normalize(_markov_score(h, mx=mx))
    s4 = _normalize(_neighbor_score(h, mx=mx))
    out = {}
    for n in range(1, mx+1):
        v = [s1.get(n,0), s2.get(n,0), s3.get(n,0), s4.get(n,0)]
        out[n] = max(0.0, float(np.mean(v)) - 0.5*float(np.std(v)))
    return out

AGENTS = {
    'fourier': lambda h: _fourier_score(h),
    'cold': lambda h: _cold_score(h),
    'neighbor': lambda h: _neighbor_score(h),
    'markov': lambda h: _markov_score(h),
    'consensus': lambda h: _consensus_score(h),
}

_ZB = [(1,16),(17,32),(33,49)]

def pred(h, n_bets, zone_boost, hs_rate, use_zone, use_hs):
    final = {n: 0.0 for n in range(1, 50)}
    w = 1.0 / len(AGENTS)
    for _, fn in AGENTS.items():
        raw = fn(h); norm = _normalize(raw)
        for n, s in norm.items(): final[n] += w * s

    ms = max(final.values()) or 1.0

    # Hot Streak
    if use_hs and len(h) >= 10:
        p = 6/49
        max_z = {n: 0.0 for n in range(1, 50)}
        for ww in [8, 10, 12, 15, 20, 30]:
            rec = h[-ww:] if len(h) >= ww else h
            nd = len(rec)
            if nd < 5: continue
            freq = Counter(n for d in rec for n in d['numbers'])
            exp = nd * p; std = math.sqrt(nd * p * (1-p))
            if std <= 0: continue
            for n in range(1, 50):
                z = (freq.get(n,0) - exp) / std
                if z > max_z[n]: max_z[n] = z
        for n in range(1, 50):
            if max_z[n] > 2.0:
                final[n] += (max_z[n] - 2.0) * hs_rate * ms

    # Zone Cascade
    if use_zone:
        pn = set(h[-1]['numbers'])
        zc = [sum(1 for n in pn if lo <= n <= hi) for lo, hi in _ZB]
        for i, (lo, hi) in enumerate(_ZB):
            if zc[i] == 0:
                for n in range(lo, hi+1):
                    final[n] += zone_boost * ms
            elif zc[i] >= 4:
                pen = zone_boost * 0.4 * ms
                for n in range(lo, hi+1):
                    final[n] = max(0.0, final[n] - pen)

    ranked = sorted(final, key=lambda n: -final[n])
    return [sorted(ranked[i*6:(i+1)*6]) for i in range(n_bets)]


def backtest_fast(history, n_bets, zone_boost, hs_rate, use_zone, use_hs, start_idx=200):
    hits = []
    for i in range(start_idx, len(history)):
        h = history[:i]
        actual = set(history[i]['numbers'])
        bets = pred(h, n_bets, zone_boost, hs_rate, use_zone, use_hs)
        best = max(len(set(b) & actual) for b in bets) if bets else 0
        hits.append(best >= 3)
    return hits


def edge_rate(hits):
    return sum(hits) / len(hits) if hits else 0.0


def three_win(hits, bl):
    out = {}
    for name, w in [('150p', 150), ('500p', 500), ('1500p', 1500)]:
        if len(hits) < w: out[name] = None; continue
        out[name] = (edge_rate(hits[-w:]) - bl) * 100
    return out


def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = sorted(db.get_all_draws(lottery_type='BIG_LOTTO'),
                     key=lambda x: (x['date'], x['draw']))
    print(f'BIG_LOTTO: {len(history)} draws')

    bl3 = 0.0549
    START = 200

    # ---- Phase 1: Baseline (no guards) ----
    print('\n=== BASELINE (no guards) ===')
    hits_base = backtest_fast(history, 3, 0, 0, False, False, START)
    rate_base = edge_rate(hits_base)
    tw_base = three_win(hits_base, bl3)
    print(f'  Rate={rate_base*100:.2f}%  Edge={((rate_base-bl3)*100):+.2f}%')
    for w, v in tw_base.items():
        print(f'  {w}: {v:+.2f}%' if v is not None else f'  {w}: N/A')
    n_base = sum(hits_base)
    print(f'  Hits={n_base}/{len(hits_base)}')

    # ---- Phase 2: Grid search ----
    zone_boosts = [0.03, 0.05, 0.08, 0.12]
    hs_rates = [0.02, 0.03, 0.05, 0.08]

    results = []

    # Zone only
    print('\n=== ZONE CASCADE ONLY ===')
    for zb in zone_boosts:
        hits = backtest_fast(history, 3, zb, 0, True, False, START)
        rate = edge_rate(hits)
        tw = three_win(hits, bl3)
        all_pos = all(v is not None and v > 0 for v in tw.values())
        diff = sum(hits) - n_base
        results.append(('zone_only', zb, 0, rate, tw, all_pos, diff))
        mark = '✓' if all_pos else '✗'
        print(f'  zb={zb:.2f}: rate={rate*100:.2f}% edge={((rate-bl3)*100):+.2f}% '
              f'150p={tw["150p"]:+.2f}% 500p={tw["500p"]:+.2f}% 1500p={tw["1500p"]:+.2f}% '
              f'3win={mark} diff={diff:+d}')

    # HS only
    print('\n=== HOT-STREAK ONLY ===')
    for hr in hs_rates:
        hits = backtest_fast(history, 3, 0, hr, False, True, START)
        rate = edge_rate(hits)
        tw = three_win(hits, bl3)
        all_pos = all(v is not None and v > 0 for v in tw.values())
        diff = sum(hits) - n_base
        results.append(('hs_only', 0, hr, rate, tw, all_pos, diff))
        mark = '✓' if all_pos else '✗'
        print(f'  hr={hr:.2f}: rate={rate*100:.2f}% edge={((rate-bl3)*100):+.2f}% '
              f'150p={tw["150p"]:+.2f}% 500p={tw["500p"]:+.2f}% 1500p={tw["1500p"]:+.2f}% '
              f'3win={mark} diff={diff:+d}')

    # Combined
    print('\n=== COMBINED (Zone + HS) ===')
    for zb in zone_boosts:
        for hr in hs_rates:
            hits = backtest_fast(history, 3, zb, hr, True, True, START)
            rate = edge_rate(hits)
            tw = three_win(hits, bl3)
            all_pos = all(v is not None and v > 0 for v in tw.values())
            diff = sum(hits) - n_base
            results.append(('combined', zb, hr, rate, tw, all_pos, diff))
            mark = '✓' if all_pos else '✗'
            print(f'  zb={zb:.2f} hr={hr:.2f}: rate={rate*100:.2f}% edge={((rate-bl3)*100):+.2f}% '
                  f'150p={tw["150p"]:+.2f}% 500p={tw["500p"]:+.2f}% 1500p={tw["1500p"]:+.2f}% '
                  f'3win={mark} diff={diff:+d}')

    # ---- Phase 3: Best result ----
    print('\n=== BEST RESULTS ===')
    # Sort by: three-window pass, then by overall edge
    pass_results = [r for r in results if r[5]]  # all_pos=True
    if pass_results:
        pass_results.sort(key=lambda r: r[3], reverse=True)  # by rate
        for mode, zb, hr, rate, tw, _, diff in pass_results[:5]:
            print(f'  [{mode}] zb={zb:.2f} hr={hr:.2f}: '
                  f'edge={((rate-bl3)*100):+.2f}% diff={diff:+d} '
                  f'150p={tw["150p"]:+.2f}% 500p={tw["500p"]:+.2f}% 1500p={tw["1500p"]:+.2f}%')
        print(f'\n  Total configs with 3-win PASS: {len(pass_results)}/{len(results)}')
    else:
        print('  No config passed three-window test!')
        # Find closest
        results.sort(key=lambda r: min(r[4].get('500p', -99) or -99,
                                        r[4].get('150p', -99) or -99,
                                        r[4].get('1500p', -99) or -99), reverse=True)
        for mode, zb, hr, rate, tw, _, diff in results[:5]:
            print(f'  [{mode}] zb={zb:.2f} hr={hr:.2f}: '
                  f'edge={((rate-bl3)*100):+.2f}% diff={diff:+d} '
                  f'150p={tw["150p"]:+.2f}% 500p={tw["500p"]:+.2f}% 1500p={tw["1500p"]:+.2f}%')

    # Also report: does adding guard EVER beat baseline total hits?
    beat_baseline = [r for r in results if r[6] >= 0]
    print(f'\n  Configs with hits >= baseline: {len(beat_baseline)}/{len(results)}')


if __name__ == '__main__':
    main()
