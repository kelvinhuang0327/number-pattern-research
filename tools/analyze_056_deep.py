#!/usr/bin/env python3
"""Deep analysis for draw 056 missed numbers"""
import sys, os, json
import numpy as np
from collections import Counter

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lottery_api'))
sys.path.insert(0, '.')
from database import DatabaseManager
db = DatabaseManager()
history = sorted(db.get_all_draws('DAILY_539'), key=lambda x: (x['date'], x['draw']))

ACTUAL = {2, 19, 21, 32, 35}

# === Neighbor hits distribution ===
print('=== Neighbor(+/-1) hit distribution (last 1500 draws) ===')
neighbor_hits_dist = []
for i in range(len(history)-1500, len(history)-1):
    prev = set(history[i]['numbers'])
    curr = set(history[i+1]['numbers'])
    neighbors = set()
    for n in prev:
        if n > 1: neighbors.add(n-1)
        if n < 39: neighbors.add(n+1)
    hits = len(curr & neighbors)
    neighbor_hits_dist.append(hits)

for h in range(6):
    pct = neighbor_hits_dist.count(h) / len(neighbor_hits_dist) * 100
    print(f'  Neighbor hit {h}: {neighbor_hits_dist.count(h)} times ({pct:.1f}%)')
avg_nh = np.mean(neighbor_hits_dist)
print(f'  Average neighbor hits: {avg_nh:.2f}')
print(f'  This draw: 3 (above average)')

nh3plus = sum(1 for h in neighbor_hits_dist if h >= 3)
print(f'  Neighbor hits >= 3: {nh3plus}/{len(neighbor_hits_dist)} ({nh3plus/len(neighbor_hits_dist)*100:.1f}%)')

# === Keep distribution ===
print()
print('=== Keep (overlap with prev draw) distribution ===')
keep_dist = []
for i in range(len(history)-1500, len(history)-1):
    prev = set(history[i]['numbers'])
    curr = set(history[i+1]['numbers'])
    keep_dist.append(len(curr & prev))

for h in range(6):
    pct = keep_dist.count(h) / len(keep_dist) * 100
    print(f'  Keep {h}: {keep_dist.count(h)} times ({pct:.1f}%)')
print(f'  Average keep: {np.mean(keep_dist):.2f}')

# === All Warm analysis ===
print()
print('=== All-Warm draw frequency ===')
warm_count = 0
total_checked = 0
for i in range(len(history)-1500, len(history)):
    nums = history[i]['numbers']
    freq100 = Counter()
    for d in history[max(0,i-100):i]:
        for n in d['numbers']:
            if n <= 39: freq100[n] += 1
    exp = max(1, (i - max(0, i-100))) * 5 / 39
    if exp == 0: continue
    all_warm = all(0.7 <= freq100.get(n, 0)/exp <= 1.3 for n in nums if n <= 39)
    total_checked += 1
    if all_warm:
        warm_count += 1

print(f'  All-5 Warm ratio: {warm_count}/{total_checked} ({warm_count/total_checked*100:.1f}%)')

# === Neighbor pool stats ===
print()
print('=== Neighbor pool feasibility ===')
neighbor_pool_sizes = []
neighbor_only_bets_hits = []
for i in range(len(history)-1500, len(history)-1):
    prev = set(history[i]['numbers'])
    curr = set(history[i+1]['numbers'])
    neighbors = set()
    for n in prev:
        if n > 1: neighbors.add(n-1)
        if n < 39: neighbors.add(n+1)
    pool_size = len(neighbors)
    hits = len(curr & neighbors)
    neighbor_pool_sizes.append(pool_size)
    neighbor_only_bets_hits.append(hits)

print(f'  Avg pool size: {np.mean(neighbor_pool_sizes):.1f}')
print(f'  Neighbor hit >= 2: {sum(1 for h in neighbor_only_bets_hits if h >= 2)/len(neighbor_only_bets_hits)*100:.1f}%')
print(f'  Neighbor hit >= 3: {sum(1 for h in neighbor_only_bets_hits if h >= 3)/len(neighbor_only_bets_hits)*100:.1f}%')

# === Duplicate tail analysis ===
print()
print('=== Duplicate tail analysis (draw 056 has tail=2 twice) ===')
dup_tail_count = 0
for i in range(len(history)-1500, len(history)):
    tails = [n % 10 for n in history[i]['numbers'] if n <= 39]
    tc = Counter(tails)
    if any(v >= 2 for v in tc.values()):
        dup_tail_count += 1
print(f'  Draws with duplicate tails: {dup_tail_count}/1500 ({dup_tail_count/1500*100:.1f}%)')

# === Neighbor-Aware strategy backtest (quick) ===
print()
print('=== Neighbor-Aware 1-bet strategy (last 500 draws) ===')
# Strategy: pick Top 5 from neighbor pool (sorted by ACB score)
nh_m2_count = 0
nh_total = 0
for i in range(len(history)-500, len(history)-1):
    prev = set(history[i]['numbers'])
    curr = set(history[i+1]['numbers'])
    neighbors = set()
    for n in prev:
        if n > 1: neighbors.add(n-1)
        if n < 39: neighbors.add(n+1)
    
    # ACB scoring within neighbor pool
    r100 = history[max(0,i-100):i+1]
    c = Counter()
    for n in range(1, 40): c[n] = 0
    for d in r100:
        for n in d['numbers']: c[n] += 1
    ls = {}
    for j, d in enumerate(r100):
        for n in d['numbers']: ls[n] = j
    cur = len(r100)
    exp = len(r100) * 5 / 39
    
    pool = list(neighbors)
    if len(pool) < 5:
        pool = list(range(1, 40))
    
    scores = {}
    for n in pool:
        fd = exp - c[n]
        gs = (cur - ls.get(n, -1)) / (cur/2)
        scores[n] = fd * 0.4 + gs * 0.6
    
    ranked = sorted(scores, key=lambda x: -scores[x])
    bet = sorted(ranked[:5])
    hits = len(set(bet) & curr)
    if hits >= 2:
        nh_m2_count += 1
    nh_total += 1

print(f'  Neighbor-ACB 1bet M2+ rate: {nh_m2_count}/{nh_total} ({nh_m2_count/nh_total*100:.1f}%)')
print(f'  Random 1bet M2+ baseline: 11.4%')
print(f'  Edge: {nh_m2_count/nh_total*100 - 11.4:.2f}%')

# === Lag-2 Echo + Neighbor hybrid ===
print()
print('=== Lag-2 echo + neighbor hybrid analysis ===')
lag2_neighbor_hits = []
for i in range(len(history)-1500, len(history)-1):
    if i < 2: continue
    prev = set(history[i]['numbers'])
    lag2 = set(history[i-1]['numbers'])
    curr = set(history[i+1]['numbers'])
    
    neighbors = set()
    for n in prev:
        if n > 1: neighbors.add(n-1)
        if n < 39: neighbors.add(n+1)
    
    combined = neighbors | lag2
    hits = len(curr & combined)
    lag2_neighbor_hits.append(hits)

avg_combined = np.mean(lag2_neighbor_hits)
print(f'  Combined pool (neighbor + lag-2) avg hits: {avg_combined:.2f}')
print(f'  Combined >= 3: {sum(1 for h in lag2_neighbor_hits if h >= 3)/len(lag2_neighbor_hits)*100:.1f}%')

# === Check: if ACB Top-8 instead of Top-5 ===
print()
print('=== ACB Top-N sensitivity (this draw) ===')
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, '.')
from quick_predict import _539_acb_bet

# Manually compute Top-N
r100 = history[-100:]
c = Counter()
for n in range(1, 40): c[n] = 0
for d in r100:
    for n in d['numbers']: c[n] += 1
ls = {}
for j, d in enumerate(r100):
    for n in d['numbers']: ls[n] = j
cur = len(r100)
exp = len(r100) * 5 / 39
acb_scores = {}
for n in range(1, 40):
    fd = exp - c[n]
    gs = (cur - ls.get(n, -1)) / (cur/2)
    bb = 1.2 if (n <= 5 or n >= 35) else 1.0
    mb = 1.1 if n % 3 == 0 else 1.0
    acb_scores[n] = (fd * 0.4 + gs * 0.6) * bb * mb
acb_ranked = sorted(acb_scores, key=lambda x: -acb_scores[x])

for top_n in [5, 6, 7, 8, 9, 10]:
    sel = set(acb_ranked[:top_n])
    hits = sel & ACTUAL
    print(f'  ACB Top-{top_n}: {sorted(sel)} -> hits: {sorted(hits)} ({len(hits)}/5)')

# === Neighborhood-based 2-bet backtest (500p) ===
print()
print('=== Neighbor-Based 2-bet backtest (500p) ===')
# Bet1: neighbor pool + ACB scoring; Bet2: ACB from remaining
nb_m2_count = 0
nb_total = 0
for i in range(len(history)-500, len(history)-1):
    prev = set(history[i]['numbers'])
    curr = set(history[i+1]['numbers'])
    neighbors = set()
    for n in prev:
        if n > 1: neighbors.add(n-1)
        if n < 39: neighbors.add(n+1)
    
    r100 = history[max(0,i-100):i+1]
    c = Counter()
    for n in range(1, 40): c[n] = 0
    for d in r100:
        for n in d['numbers']: c[n] += 1
    ls = {}
    for j, d in enumerate(r100):
        for n in d['numbers']: ls[n] = j
    cur = len(r100)
    exp = len(r100) * 5 / 39
    
    # Bet1: from neighbor pool, ACB scored
    pool = list(neighbors)
    scores = {}
    for n in pool:
        fd = exp - c[n]
        gs = (cur - ls.get(n, -1)) / (cur/2)
        scores[n] = fd * 0.4 + gs * 0.6
    ranked_nh = sorted(scores, key=lambda x: -scores[x])
    bet1 = sorted(ranked_nh[:5])
    
    # Bet2: ACB from remaining
    excl = set(bet1)
    scores2 = {}
    for n in range(1, 40):
        if n in excl: continue
        fd = exp - c[n]
        gs = (cur - ls.get(n, -1)) / (cur/2)
        bb = 1.2 if (n <= 5 or n >= 35) else 1.0
        mb = 1.1 if n % 3 == 0 else 1.0
        scores2[n] = (fd * 0.4 + gs * 0.6) * bb * mb
    ranked_acb = sorted(scores2, key=lambda x: -scores2[x])
    bet2 = sorted(ranked_acb[:5])
    
    m2_b1 = len(set(bet1) & curr) >= 2
    m2_b2 = len(set(bet2) & curr) >= 2
    if m2_b1 or m2_b2:
        nb_m2_count += 1
    nb_total += 1

baseline_2bet = 21.54
rate_2bet = nb_m2_count/nb_total*100
print(f'  Neighbor+ACB 2bet M2+ rate: {nb_m2_count}/{nb_total} ({rate_2bet:.1f}%)')
print(f'  Random 2bet baseline: {baseline_2bet}%')
print(f'  Edge: {rate_2bet - baseline_2bet:.2f}%')

print()
print('=== Analysis complete ===')
