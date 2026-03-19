#!/usr/bin/env python3
"""
Zone Cascade Guard ONLY (zb=0.12) — 高效完整驗證
=================================================
優化：Perm test 只跑最後 500 期 × 100 shuffles
"""
import sys, os, math, random, json
import numpy as np
from collections import Counter
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
from database import DatabaseManager
from numpy.fft import fft, fftfreq

# ---- Agents (compact) ----
def _norm(sc):
    vals = list(sc.values()); mn, mx = min(vals), max(vals); r = mx - mn
    return {n: 0.5 for n in sc} if r == 0 else {n: (v-mn)/r for n, v in sc.items()}

def _fourier(h, w=500, mx=49):
    hh = h[-w:]; ww = len(hh); sc = {}
    for n in range(1, mx+1):
        bh = np.zeros(ww)
        for i, d in enumerate(hh):
            if n in d['numbers']: bh[i] = 1
        if sum(bh) < 2: sc[n] = 0.0; continue
        yf = fft(bh - np.mean(bh)); xf = fftfreq(ww, 1)
        ip = np.where(xf > 0); py = np.abs(yf[ip]); px = xf[ip]
        if len(py) == 0: sc[n] = 0.0; continue
        fv = px[np.argmax(py)]
        if fv == 0: sc[n] = 0.0; continue
        la = np.where(bh == 1)[0]; li = la[-1] if len(la) else -1
        sc[n] = 1.0 / (abs((ww-1-li) - 1.0/fv) + 1.0)
    return sc

def _cold(h, w=100, mx=49):
    r = h[-w:]; ls = {}
    for i, d in enumerate(r):
        for n in d['numbers']: ls[n] = i
    sc = {n: float(len(r) - ls.get(n, -1)) for n in range(1, mx+1)}
    m = max(sc.values()) or 1.0
    return {n: s/m for n, s in sc.items()}

def _neigh(h, mx=49):
    sc = {n: 0.0 for n in range(1, mx+1)}
    for pn in h[-1]['numbers']:
        for d in (-1, 0, 1):
            nn = pn+d
            if 1 <= nn <= mx: sc[nn] += 1.0 if d == 0 else 0.7
    return sc

def _markov(h, w=30, mx=49):
    r = h[-w:]; tr = {}
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

def _cons(h, mx=49):
    s = [_norm(_cold(h,mx=mx)), _norm(_fourier(h,mx=mx)), _norm(_markov(h,mx=mx)), _norm(_neigh(h,mx=mx))]
    out = {}
    for n in range(1, mx+1):
        v = [si.get(n,0) for si in s]
        out[n] = max(0.0, float(np.mean(v)) - 0.5*float(np.std(v)))
    return out

_AG = [_fourier, _cold, _neigh, _markov, _cons]
_ZB = [(1,16),(17,32),(33,49)]

def _pred(h, nb, zone=True, zb=0.12):
    final = {n: 0.0 for n in range(1, 50)}
    w = 1.0 / len(_AG)
    for fn in _AG:
        raw = fn(h); nm = _norm(raw)
        for n, s in nm.items(): final[n] += w * s
    if zone:
        ms = max(final.values()) or 1.0
        pn = set(h[-1]['numbers'])
        zc = [sum(1 for n in pn if lo <= n <= hi) for lo, hi in _ZB]
        for i, (lo, hi) in enumerate(_ZB):
            if zc[i] == 0:
                for n in range(lo, hi+1): final[n] += zb * ms
            elif zc[i] >= 4:
                for n in range(lo, hi+1): final[n] = max(0.0, final[n] - zb*0.4*ms)
    rk = sorted(final, key=lambda n: -final[n])
    return [sorted(rk[i*6:(i+1)*6]) for i in range(nb)]

def _bt(history, nb, zone, start):
    hits = []
    for i in range(start, len(history)):
        actual = set(history[i]['numbers'])
        bets = _pred(history[:i], nb, zone)
        best = max(len(set(b) & actual) for b in bets)
        hits.append(best >= 3)
    return hits

def _rate(h): return sum(h)/len(h) if h else 0.0

def _zp(rate, bl, n):
    se = math.sqrt(bl*(1-bl)/n) if n > 0 else 1.0
    z = (rate-bl)/se if se > 0 else 0.0
    return z, 0.5 * math.erfc(z / math.sqrt(2))

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    hist = sorted(db.get_all_draws(lottery_type='BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    print(f'BIG_LOTTO: {len(hist)} draws')

    BL = {2: 0.0369, 3: 0.0549}; START = 200
    report = {}

    for nb in [2, 3]:
        bl = BL[nb]
        print(f'\n{"="*70}')
        print(f'  {nb}-BET Zone Cascade Guard ONLY (zb=0.12)')
        print(f'{"="*70}')

        # [1] Full backtest
        print('[1] Full backtest...')
        rn = _bt(hist, nb, False, START); ry = _bt(hist, nb, True, START)
        rn_r = _rate(rn); ry_r = _rate(ry)
        print(f'  NoGuard: {sum(rn)}/{len(rn)} = {rn_r*100:.2f}%  edge={((rn_r-bl)*100):+.2f}%')
        print(f'  ZoneG:   {sum(ry)}/{len(ry)} = {ry_r*100:.2f}%  edge={((ry_r-bl)*100):+.2f}%')
        print(f'  Diff: {sum(ry)-sum(rn):+d} hits')

        # [2] Three-Window
        print('[2] Three-Window:')
        tw = {}; ok = True
        for name, w in [('150p',150),('500p',500),('1500p',1500)]:
            en = (_rate(rn[-w:])-bl)*100 if len(rn)>=w else None
            ey = (_rate(ry[-w:])-bl)*100 if len(ry)>=w else None
            tw[name] = ey
            if ey is not None and ey <= 0: ok = False
            s_n = f'{en:+.2f}%' if en is not None else 'N/A'
            s_y = f'{ey:+.2f}%' if ey is not None else 'N/A'
            print(f'  {name:>6s}: NoGuard={s_n:>8s}  ZoneG={s_y:>8s}')
        print(f'  Three-Window: {"PASS" if ok else "FAIL"}')

        # [3] Z / p
        z, p = _zp(ry_r, bl, len(ry))
        print(f'[3] Significance: z={z:.3f} p={p:.4f} {"PASS" if p < 0.05 else "FAIL"}')

        # [4] Sharpe
        sr = (ry_r - bl) / math.sqrt(ry_r*(1-ry_r)) if ry_r > 0 else 0
        print(f'[4] Sharpe: {sr:.4f} {"PASS" if sr > 0 else "FAIL"}')

        # [5] Permutation Test — 只對最後 500 期做，100 shuffles
        print('[5] Permutation Test (last 500 draws, 100 shuffles)...')
        perm_hist = hist[-700:]  # 500 test + 200 warmup
        real_hits = _bt(perm_hist, nb, True, 200)
        real_rate = _rate(real_hits)
        rng = random.Random(42); ge = 0
        for pi in range(100):
            sh = list(perm_hist); rng.shuffle(sh)
            ph = _bt(sh, nb, True, 200)
            if _rate(ph) >= real_rate: ge += 1
            if (pi+1) % 25 == 0: print(f'    perm {pi+1}/100 ge={ge}')
        pp = (ge+1)/101
        print(f'  Perm p={pp:.4f} {"PASS" if pp < 0.05 else "FAIL"}')

        # [6] Walk-Forward OOS (5 fold)
        print('[6] Walk-Forward OOS (5 fold):')
        total = len(hist); fs = (total - START) // 5
        oos_pos = True; oos_rates = []
        for f in range(5):
            ts = START + f * fs; te = min(ts + fs, total)
            if ts >= total: break
            fh = []
            for i in range(ts, te):
                actual = set(hist[i]['numbers'])
                bets = _pred(hist[:i], nb, True)
                best = max(len(set(b) & actual) for b in bets)
                fh.append(best >= 3)
            fr = _rate(fh); oos_rates.append(fr)
            e = (fr - bl) * 100
            if e <= 0: oos_pos = False
            print(f'  F{f+1}: n={len(fh)} rate={fr*100:.2f}% edge={e:+.2f}%')
        avg_oos = sum(oos_rates)/len(oos_rates) if oos_rates else 0
        print(f'  Avg OOS edge: {((avg_oos-bl)*100):+.2f}%')
        print(f'  All folds positive: {"PASS" if oos_pos else "FAIL"}')

        # [7] McNemar
        bc = sum(1 for a, b in zip(ry, rn) if a and not b)  # ZoneG hit, NoGuard miss
        cb = sum(1 for a, b in zip(ry, rn) if b and not a)  # NoGuard hit, ZoneG miss
        n_disc = bc + cb
        chi2 = (abs(bc-cb)-1)**2/n_disc if n_disc > 0 else 0
        mp = 0.5*math.erfc(math.sqrt(chi2/2)) if chi2 > 0 else 1.0
        print(f'[7] McNemar: ZoneG-only={bc} NoGuard-only={cb} chi2={chi2:.3f} p={mp:.4f}')
        print(f'  Direction: {"ZoneG" if bc > cb else "NoGuard" if cb > bc else "Equal"} better')

        # [8] Score
        e1500 = tw.get('1500p', 0) or 0
        if e1500 > 0:
            vals = [tw.get(w,0) or 0 for w in ['150p','500p','1500p']]
            stab = 1 - min(abs(vals[0]-vals[2])/max(abs(vals[2]),0.01), 1.0)
            sig = -math.log10(max(p, 1e-10))
            score = (e1500 * stab * sig) / 30
        else:
            stab = 0; score = 0
        print(f'[8] Score: stability={stab:.3f} score={score:.4f}')

        # Verdict
        checks = {'three_window': ok, 'significance': p < 0.05,
                   'permutation': pp < 0.05, 'sharpe': sr > 0}
        np_ = sum(checks.values())
        verdict = 'ADOPTED' if np_ >= 4 else 'PROVISIONAL' if np_ >= 3 else 'REJECTED'
        print(f'\n*** VERDICT: {nb}-bet Zone Cascade Guard ***')
        for k, v in checks.items():
            print(f'  {k:>15s}: {"PASS" if v else "FAIL"}')
        print(f'  OOS positive: {"PASS" if oos_pos else "WARN"}')
        print(f'  → {verdict} ({np_}/4 mandatory)')

        report[f'{nb}bet'] = {
            'rate': ry_r, 'edge_pct': (ry_r-bl)*100, 'hits': sum(ry),
            'hits_noguard': sum(rn), 'diff': sum(ry)-sum(rn),
            'tw': tw, 'tw_pass': ok, 'z': z, 'p': p,
            'sharpe': sr, 'perm_p': pp,
            'oos_avg_edge': (avg_oos-bl)*100, 'oos_all_pos': oos_pos,
            'mcnemar_bc': bc, 'mcnemar_cb': cb, 'score': score,
            'verdict': verdict,
        }

    with open(os.path.join(project_root, 'backtest_zone_cascade_only_results.json'), 'w') as f:
        json.dump({'ts': datetime.now().isoformat(), 'results': report}, f, indent=2)
    print('\nSaved to backtest_zone_cascade_only_results.json')

if __name__ == '__main__':
    main()
