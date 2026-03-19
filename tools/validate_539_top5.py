#!/usr/bin/env python3
"""快速三窗口驗證 Top-5 539策略"""
import sys, os, numpy as np, random
from collections import Counter, defaultdict
from numpy.fft import fft, fftfreq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api'))
from database import DatabaseManager

MAX_NUM, PICK = 39, 5
P_M2 = 11.42

def calc_bl(n): return (1 - (1 - P_M2/100)**n) * 100

def feat_acb(h, k=5, w=100):
    r = h[-w:]
    c = Counter()
    for n in range(1,40): c[n] = 0
    for d in r:
        for n in d['numbers']: c[n] += 1
    ls = {}
    for i, d in enumerate(r):
        for n in d['numbers']: ls[n] = i
    cur = len(r); exp = len(r)*5/39
    sc = {}
    for n in range(1, 40):
        fd = exp - c[n]; gs = (cur - ls.get(n,-1))/(len(r)/2)
        bb = 1.2 if n<=5 or n>=35 else 1.0; mb = 1.1 if n%3==0 else 1.0
        sc[n] = (fd*0.4 + gs*0.6)*bb*mb
    return sorted(sorted(sc, key=lambda x:-sc[x])[:k])

def feat_fourier(h, k=5, w=500):
    sl = h[-w:]; wl = len(sl); sc = {}
    for n in range(1, 40):
        bh = np.zeros(wl)
        for i, d in enumerate(sl):
            if n in d['numbers']: bh[i] = 1
        if sum(bh) < 2: sc[n] = 0.0; continue
        yf = fft(bh - np.mean(bh)); xf = fftfreq(wl, 1)
        ip = np.where(xf > 0); py = np.abs(yf[ip]); px = xf[ip]
        pk = np.argmax(py); fv = px[pk]
        if fv == 0: sc[n] = 0.0; continue
        p = 1/fv; lh = np.where(bh==1)[0][-1]; g = (wl-1)-lh
        sc[n] = 1.0/(abs(g-p)+1.0)
    return sorted(sorted(sc, key=lambda x:-sc[x])[:k])

def feat_cold(h, k=5, w=100):
    f = Counter(n for d in h[-w:] for n in d['numbers'])
    return sorted(sorted(range(1, 40), key=lambda n: f.get(n, 0))[:k])

def feat_hot(h, k=5, w=50):
    f = Counter(n for d in h[-w:] for n in d['numbers'])
    return sorted(sorted(range(1, 40), key=lambda n: -f.get(n, 0))[:k])

def feat_markov(h, k=5, w=30):
    r = h[-w:]; tr = defaultdict(Counter)
    for i in range(len(r)-1):
        for cn in r[i]['numbers']:
            for nn in r[i+1]['numbers']: tr[cn][nn] += 1
    prev = h[-1]['numbers']; sc = Counter()
    for pn in prev:
        t = tr.get(pn, Counter()); tot = sum(t.values())
        if tot > 0:
            for n, c in t.items(): sc[n] += c/tot
    return sorted(sorted(range(1, 40), key=lambda n: -sc.get(n, 0))[:k])

def feat_neighbor(h, k=5):
    prev = set(h[-1]['numbers']); pool = set()
    for n in prev:
        for d in range(-1, 2):
            nn = n+d
            if 1 <= nn <= 39: pool.add(nn)
    f = Counter(n for d in h[-50:] for n in d['numbers'])
    sc = {n: (1.5 if n in pool else 0)+f.get(n,0)/50 for n in range(1, 40)}
    return sorted(sorted(sc, key=lambda x:-sc[x])[:k])

def gen_nbets(fns, h, k=5):
    bets = []; used = set()
    for fn in fns:
        raw = fn(h, k=k*2)
        bet = [n for n in raw if n not in used][:k]
        while len(bet) < k:
            for n in range(1, 40):
                if n not in used and n not in bet: bet.append(n); break
        used.update(bet); bets.append(sorted(bet))
    return bets

def backtest(hist, pfunc, nb, periods=1500, warmup=200):
    start = max(warmup, len(hist)-periods); hits = total = 0
    for i in range(start, len(hist)):
        h = hist[:i]; bets = pfunc(h); actual = set(hist[i]['numbers'])
        if any(len(actual & set(b)) >= 2 for b in bets[:nb]): hits += 1
        total += 1
    rate = hits/total*100 if total else 0; bl = calc_bl(nb)
    edge = rate-bl; z = (rate/100-bl/100)/((bl/100*(1-bl/100)/total)**0.5) if total else 0
    return rate, edge, z, total

db = DatabaseManager(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api', 'data', 'lottery_v2.db'))
hist = sorted(db.get_all_draws('DAILY_539'), key=lambda x: (x['date'], x['draw']))

strategies = [
    ('ACB+Fourier+Cold 3bet', lambda h: gen_nbets([feat_acb, feat_fourier, feat_cold], h), 3),
    ('Fourier+Markov+Cold 3bet', lambda h: gen_nbets([feat_fourier, feat_markov, feat_cold], h), 3),
    ('ACB+Hot+Neighbor 3bet', lambda h: gen_nbets([feat_acb, feat_hot, feat_neighbor], h), 3),
    ('Fourier+Cold 2bet', lambda h: gen_nbets([feat_fourier, feat_cold], h), 2),
    ('ACB 1bet', lambda h: [feat_acb(h)], 1),
]

print('=' * 70)
print('539 Top-5 三窗口驗證')
print('=' * 70)

for name, fn, nb in strategies:
    print(f'\n--- {name} ---')
    edges = []
    for wp in [150, 500, 1500]:
        rate, edge, z, total = backtest(hist, fn, nb, wp)
        edges.append(edge)
        marker = '★' if z >= 1.96 else ''
        print(f'  {wp}p: Rate={rate:.2f}% Edge={edge:+.2f}% z={z:.2f} {marker} (n={total})')
    stab = 'STABLE' if all(e > 0 for e in edges) else ('LATE_BLOOMER' if edges[-1] > 0 else 'INEFFECTIVE')
    print(f'  穩定性: {stab}')

# ACB permutation (fast, 1-bet only)
print('\n' + '=' * 70)
print('ACB 1bet Permutation (200 iter)')
print('=' * 70)
random.seed(42)
real_rate, _, _, _ = backtest(hist, lambda h: [feat_acb(h)], 1, 1500)
perm_rates = []
start_idx = max(200, len(hist)-1500)
for p_iter in range(200):
    sh = list(hist)
    acts = [d['numbers'][:] for d in sh[start_idx:]]
    random.shuffle(acts)
    for j, idx in enumerate(range(start_idx, len(sh))):
        sh[idx] = dict(sh[idx]); sh[idx]['numbers'] = acts[j]
    r, _, _, _ = backtest(sh, lambda h: [feat_acb(h)], 1, 1500)
    perm_rates.append(r)
    if (p_iter+1) % 50 == 0: print(f'  ... {p_iter+1}/200')

pm = np.mean(perm_rates); ps = np.std(perm_rates)
pz = (real_rate-pm)/(ps if ps > 0 else 1e-6)
pp = np.mean([1 for pr in perm_rates if pr >= real_rate])
print(f'  Real={real_rate:.2f}% Perm_mean={pm:.2f}% z={pz:.2f} p={pp:.3f}')
print(f'  Signal: {"✅ PASS" if pp < 0.05 else "❌ FAIL"}')
print('\nDone!')
