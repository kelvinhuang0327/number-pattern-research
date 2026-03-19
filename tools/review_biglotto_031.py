#!/usr/bin/env python3
import sys, os, numpy as np
from collections import Counter, defaultdict
from itertools import combinations
from numpy.fft import fft, fftfreq

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath('.')), 'lottery_api'))
sys.path.insert(0, 'lottery_api')

from database import DatabaseManager
db = DatabaseManager(db_path='lottery_api/data/lottery_v2.db')
draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: str(x['draw']))
history = draws  # ASC order, last = 030

actual = {19, 25, 27, 28, 33, 39}
special = 37
actual_sum = sum(actual)
print(f"031 actual: {sorted(actual)} special:{special} Sum={actual_sum}")
print(f"Last draw (030): {sorted(history[-1]['numbers'])} special:{history[-1].get('special')}")
print()

# === Method A: P1鄰號+冷號 v2 (2注) ===
sys.path.insert(0, '.')
from tools.quick_predict import biglotto_p1_neighbor_cold_2bet, biglotto_p1_deviation_5bet

bets_a = biglotto_p1_neighbor_cold_2bet(history)
nums_a = [set(b['numbers']) for b in bets_a]
union_a = set().union(*nums_a)
hit_a = union_a & actual
print("=== A: P1鄰號+冷號 v2 (2注) ===")
for i, b in enumerate(bets_a):
    hit = set(b['numbers']) & actual
    print(f"  注{i+1}: {sorted(b['numbers'])} → hit {len(hit)}/6 {sorted(hit)}")
print(f"  聯集: {len(hit_a)}/6 {sorted(hit_a)}")
m3_a = any(len(set(b['numbers']) & actual) >= 3 for b in bets_a)
print(f"  M3+: {'✅' if m3_a else '❌'}")
print()

# === Method B: P1+偏差互補+Sum (5注) ===
bets_b = biglotto_p1_deviation_5bet(history)
nums_b = [set(b['numbers']) for b in bets_b]
union_b = set().union(*nums_b)
hit_b = union_b & actual
print("=== B: P1+偏差互補+Sum (5注) ===")
for i, b in enumerate(bets_b):
    hit = set(b['numbers']) & actual
    print(f"  注{i+1}: {sorted(b['numbers'])} → hit {len(hit)}/6 {sorted(hit)}")
print(f"  聯集: {len(hit_b)}/6 {sorted(hit_b)}")
m3_b = any(len(set(b['numbers']) & actual) >= 3 for b in bets_b)
print(f"  M3+: {'✅' if m3_b else '❌'}")
print()

# === Method C: Triple Strike (3注) ===
try:
    from tools.predict_biglotto_triple_strike import generate_triple_strike
    bets_c_raw = generate_triple_strike(history)
    bets_c = [set(b) for b in bets_c_raw]
    union_c = set().union(*bets_c)
    hit_c = union_c & actual
    print("=== C: Triple Strike (3注) ===")
    for i, b in enumerate(bets_c):
        hit = b & actual
        print(f"  注{i+1}: {sorted(b)} → hit {len(hit)}/6 {sorted(hit)}")
    print(f"  聯集: {len(hit_c)}/6 {sorted(hit_c)}")
    m3_c = any(len(b & actual) >= 3 for b in bets_c)
    print(f"  M3+: {'✅' if m3_c else '❌'}")
except Exception as e:
    print(f"  Triple Strike error: {e}")
print()

# === Method D: 偏差互補+回聲 P0 (2注) ===
from tools.quick_predict import biglotto_p0_2bet
bets_d = biglotto_p0_2bet(history)
nums_d = [set(b['numbers']) for b in bets_d]
union_d = set().union(*nums_d)
hit_d = union_d & actual
print("=== D: 偏差互補+回聲P0 (2注) ===")
for i, b in enumerate(bets_d):
    hit = set(b['numbers']) & actual
    print(f"  注{i+1}: {sorted(b['numbers'])} → hit {len(hit)}/6 {sorted(hit)}")
print(f"  聯集: {len(hit_d)}/6 {sorted(hit_d)}")
m3_d = any(len(set(b['numbers']) & actual) >= 3 for b in bets_d)
print(f"  M3+: {'✅' if m3_d else '❌'}")
print()

# === Method E: ACB (1注, 大樂透版本) ===
MAX_NUM, PICK = 49, 6
recent_acb = history[-100:]
counter = Counter()
for n in range(1, MAX_NUM+1): counter[n] = 0
for d in recent_acb:
    for n in d['numbers']: counter[n] += 1
last_seen = {}
for i, d in enumerate(recent_acb):
    for n in d['numbers']: last_seen[n] = i
current = len(recent_acb)
gaps = {n: current - last_seen.get(n, -1) for n in range(1, MAX_NUM+1)}
exp_freq = len(recent_acb) * PICK / MAX_NUM
acb_scores = {}
for n in range(1, MAX_NUM+1):
    fd = exp_freq - counter[n]
    gs = gaps[n] / (len(recent_acb)/2)
    bb = 1.2 if (n<=5 or n>=45) else 1.0
    mb = 1.1 if n%3==0 else 1.0
    acb_scores[n] = (fd*0.4 + gs*0.6) * bb * mb
acb_ranked = sorted(acb_scores, key=lambda x: -acb_scores[x])
acb_bet = sorted(acb_ranked[:6])
hit_e = set(acb_bet) & actual
print("=== E: ACB (1注) ===")
print(f"  注1: {acb_bet} → hit {len(hit_e)}/6 {sorted(hit_e)}")
print()

# === Method F: 舊5注 TS3+Markov+FreqOrt (模擬) ===
try:
    from tools.quick_predict import biglotto_5bet_orthogonal
    bets_f = biglotto_5bet_orthogonal(history)
    nums_f = [set(b['numbers']) for b in bets_f]
    union_f = set().union(*nums_f)
    hit_f = union_f & actual
    print("=== F: 舊5注 TS3+Markov+FreqOrt ===")
    for i, b in enumerate(bets_f):
        hit = set(b['numbers']) & actual
        print(f"  注{i+1}: {sorted(b['numbers'])} → hit {len(hit)}/6 {sorted(hit)}")
    print(f"  聯集: {len(hit_f)}/6 {sorted(hit_f)}")
    m3_f = any(len(set(b['numbers']) & actual) >= 3 for b in bets_f)
    print(f"  M3+: {'✅' if m3_f else '❌'}")
except Exception as e:
    print(f"  舊5注 error: {e}")
print()

# === Signal analysis for each number ===
print("="*60)
print("各開獎號碼信號分析")
print("="*60)

# Fourier scores (500p)
h500 = history[-500:]
w500 = len(h500)
fourier_sc = {}
for n in range(1, MAX_NUM+1):
    bh = np.zeros(w500)
    for idx, d in enumerate(h500):
        if n in d['numbers']: bh[idx] = 1
    if sum(bh) < 2:
        fourier_sc[n] = 0; continue
    yf = fft(bh - np.mean(bh))
    xf = fftfreq(w500, 1)
    ip = np.where(xf > 0)
    py = np.abs(yf[ip]); px = xf[ip]
    pk = np.argmax(py); fv = px[pk]
    if fv == 0: fourier_sc[n] = 0; continue
    per = 1/fv
    if 2 < per < w500/2:
        lh = np.where(bh==1)[0][-1]
        g = (w500-1) - lh
        fourier_sc[n] = 1.0/(abs(g - per)+1.0)
    else:
        fourier_sc[n] = 0
f_ranked = sorted(range(1,MAX_NUM+1), key=lambda x: -fourier_sc[x])
f_rank = {n: i+1 for i, n in enumerate(f_ranked)}

# freq100
freq100 = Counter(n for d in history[-100:] for n in d['numbers'])

# dev50
h50 = history[-50:]
expected50 = len(h50) * PICK / MAX_NUM
dev50_scores = {}
for n in range(1, MAX_NUM+1):
    f = sum(1 for d in h50 for nn in d['numbers'] if nn == n)
    dev50_scores[n] = f - expected50

# gap
last_seen2 = {}
for i, d in enumerate(history):
    for n in d['numbers']: last_seen2[n] = i
total_draws = len(history)
gap_vals = {n: total_draws - last_seen2.get(n, -1) for n in range(1, MAX_NUM+1)}

# neighbor pool
prev_nums = history[-1]['numbers']
neighbor_pool = set()
for n in prev_nums:
    for dd in [-1, 0, 1]:
        nn = n + dd
        if 1 <= nn <= MAX_NUM: neighbor_pool.add(nn)

# ACB rank
acb_rank = {n: i+1 for i, n in enumerate(acb_ranked)}

print(f"{'號碼':>4} {'Fourier':>8} {'ACB':>6} {'freq100':>8} {'gap':>5} {'dev50':>6} {'鄰域':>4} 信號歸類")
for n in sorted(actual):
    in_nb = '✓' if n in neighbor_pool else ''
    fr = f"rank{f_rank[n]}"
    ar = f"rank{acb_rank[n]}"
    fq = freq100.get(n, 0)
    gp = gap_vals[n]
    dv = f"{dev50_scores[n]:+.1f}"
    
    # signal categorization
    signals = []
    if f_rank[n] <= 12: signals.append('Fourier')
    if acb_rank[n] <= 12: signals.append('ACB')
    if fq >= 15: signals.append('Hot')
    if fq <= 8: signals.append('Cold')
    if gp >= 10: signals.append('HighGap')
    if dev50_scores[n] > 1: signals.append('Dev+')
    if dev50_scores[n] < -1: signals.append('Dev-')
    if in_nb: signals.append('鄰域')
    if not signals: signals.append('中性')
    
    print(f"  #{n:02d}  {fr:>8}  {ar:>6}  {fq:>7}  {gp:>4}  {dv:>5}  {in_nb:>3}  {', '.join(signals)}")

# Special number
n = special
in_nb = '✓' if n in neighbor_pool else ''
signals_sp = []
if acb_rank[n] <= 12: signals_sp.append('ACB')
if freq100.get(n,0) <= 8: signals_sp.append('Cold')
if gap_vals[n] >= 10: signals_sp.append('HighGap')
if n in neighbor_pool: signals_sp.append('鄰域')
print(f"  特#{n:02d}  rank{f_rank[n]:>3}  rank{acb_rank[n]:>2}  {freq100.get(n,0):>7}  {gap_vals[n]:>4}  {dev50_scores[n]:>+5.1f}  {in_nb:>3}  {', '.join(signals_sp) or '中性'}")

# Neighbor pool full ranking
print()
print("鄰域池排名 (030的±1):")
from tools.quick_predict import _bl_fourier_scores, _bl_markov_scores
f_sc = _bl_fourier_scores(history, window=500)
mk_sc = _bl_markov_scores(history, window=30)
f_mx = max(f_sc.values()) or 1
mk_mx = max(mk_sc.values()) or 1
scored_nb = {n: f_sc.get(n,0)/f_mx + 0.5*(mk_sc.get(n,0)/mk_mx) for n in neighbor_pool}
nb_ranked = sorted(neighbor_pool, key=lambda n: scored_nb[n], reverse=True)
for i, n in enumerate(nb_ranked):
    hit_mark = "HIT" if n in actual or n == special else ""
    print(f"  {i+1:>2}. #{n:02d}  score={scored_nb[n]:.4f}  {hit_mark}")

# Odd/Even
odd_count = sum(1 for n in actual if n % 2 == 1)
print(f"\n奇偶: {odd_count}奇{6-odd_count}偶")

# Zone analysis
z1 = [n for n in actual if n <= 16]
z2 = [n for n in actual if 17 <= n <= 32]  
z3 = [n for n in actual if n >= 33]
print(f"Zone: Z1:{len(z1)}({z1}), Z2:{len(z2)}({z2}), Z3:{len(z3)}({z3})")

# Retention from 030→031
prev_set = set(history[-1]['numbers'])
retained = actual & prev_set
print(f"030→031保留: {sorted(retained)} ({len(retained)}個)")

# Sum trend
sums_recent = [sum(d['numbers']) for d in history[-10:]]
print(f"\nSum趨勢 (近10期): {sums_recent}")
s300 = [sum(d['numbers']) for d in history[-300:]]
mu_s, sg_s = np.mean(s300), np.std(s300)
print(f"Sum目標: [{mu_s-0.5*sg_s:.1f}, {mu_s+0.5*sg_s:.1f}], mu={mu_s:.1f}, sigma={sg_s:.1f}")
print(f"031 Sum={actual_sum}, z={(actual_sum-mu_s)/sg_s:.2f}")

# Cold pool analysis (what was in our cold bet)
from tools.quick_predict import _bl_cold_sum_fixed
cold_bet = _bl_cold_sum_fixed(history, exclude=set(nb_ranked[:6]))
print(f"\n冷號注2選號: {cold_bet}")
print(f"冷號注2命中: {sorted(set(cold_bet) & actual)}")
