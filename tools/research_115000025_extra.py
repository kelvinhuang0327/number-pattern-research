#!/usr/bin/env python3
"""追加研究: 鄰號、和值回歸、區間、盲區分析"""
import sys, os, json, numpy as np
from collections import Counter, defaultdict
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew')
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')
from lottery_api.database import DatabaseManager

db = DatabaseManager(db_path='lottery_api/data/lottery_v2.db')
raw = db.get_all_draws('BIG_LOTTO')
history = sorted(raw, key=lambda x: (x['date'], x['draw']))

# Research 1: Neighbor strategy backtest
print('='*70)
print('  R1: Neighbor strategy backtest (200 periods)')
print('='*70)

m3_count = 0
total = 0
neighbor_hit_counts = Counter()

for i in range(200):
    target_idx = len(history) - 200 + i
    if target_idx < 50:
        continue
    target = history[target_idx]
    prev = history[target_idx - 1]
    actual = set(target['numbers'])
    
    neighbors = set()
    for n in prev['numbers']:
        for d in [-1, 0, 1]:
            nn = n + d
            if 1 <= nn <= 49:
                neighbors.add(nn)
    
    hit = len(actual & neighbors)
    neighbor_hit_counts[hit] += 1
    
    neighbor_list = sorted(neighbors)
    if len(neighbor_list) >= 12:
        bet1 = set(neighbor_list[:6])
        bet2 = set(neighbor_list[6:12])
        hit1 = len(bet1 & actual)
        hit2 = len(bet2 & actual)
        if hit1 >= 3 or hit2 >= 3:
            m3_count += 1
    total += 1

rate = m3_count / total * 100
baseline_2bet = 3.69
edge = rate - baseline_2bet
print(f'  M3+: {m3_count}/{total} ({rate:.2f}%)')
print(f'  Baseline: {baseline_2bet}%, Edge: {edge:+.2f}%')
print(f'  Neighbor hit dist: {dict(sorted(neighbor_hit_counts.items()))}')
avg_hit = sum(k*v for k,v in neighbor_hit_counts.items()) / sum(neighbor_hit_counts.values())
print(f'  Avg neighbor hit: {avg_hit:.2f}/6')

# Research 2: Neighbor + Cold hybrid
print()
print('='*70)
print('  R2: Neighbor+Cold hybrid 2-bet (200 periods)')
print('='*70)

m3_mix = 0
for i in range(200):
    target_idx = len(history) - 200 + i
    if target_idx < 50:
        continue
    target = history[target_idx]
    prev = history[target_idx - 1]
    actual = set(target['numbers'])
    hist_i = history[:target_idx]
    
    neighbors = set()
    for n in prev['numbers']:
        for d in [-1, 0, 1]:
            nn = n + d
            if 1 <= nn <= 49: neighbors.add(nn)
    pure_neighbors = neighbors - set(prev['numbers'])
    bet1 = sorted(pure_neighbors)[:6] if len(pure_neighbors) >= 6 else sorted(neighbors)[:6]
    
    gap = {}
    for n in range(1, 50):
        found = False
        for j in range(len(hist_i)-1, -1, -1):
            if n in hist_i[j]['numbers']:
                gap[n] = len(hist_i) - 1 - j
                found = True
                break
        if not found:
            gap[n] = len(hist_i)
    cold_ranked = sorted(gap.items(), key=lambda x: -x[1])
    bet2 = sorted([n for n, _ in cold_ranked if n not in set(bet1)][:6])
    
    hit1 = len(set(bet1) & actual)
    hit2 = len(set(bet2) & actual)
    if hit1 >= 3 or hit2 >= 3:
        m3_mix += 1

rate_mix = m3_mix / 200 * 100
print(f'  M3+: {m3_mix}/200 ({rate_mix:.2f}%)')
print(f'  Edge: {rate_mix - baseline_2bet:+.2f}%')

# Research 3: Sum mean reversion
print()
print('='*70)
print('  R3: Sum mean reversion analysis')
print('='*70)

sums = [sum(d['numbers']) for d in history]
recent_10 = sums[-10:]
print(f'  Last 10 sums: {recent_10}')
print(f'  Last 10 mean: {np.mean(recent_10):.1f}, Global mean: {np.mean(sums):.1f}')
print(f'  Target sum: 139 (deviation: {139 - np.mean(sums):.1f})')

high_then_low = 0
high_count = 0
for i in range(1, len(sums)):
    if sums[i-1] > 155:
        high_count += 1
        if sums[i] < 145:
            high_then_low += 1
if high_count > 0:
    print(f'  P(sum<145 | prev_sum>155): {high_then_low}/{high_count} ({high_then_low/high_count*100:.1f}%)')

# Research 4: Overlap distribution
print()
print('='*70)
print('  R4: Adjacent period overlap distribution')
print('='*70)

overlap_dist = Counter()
for i in range(1, len(history)):
    s1 = set(history[i-1]['numbers'])
    s2 = set(history[i]['numbers'])
    overlap_dist[len(s1 & s2)] += 1

total_pairs = sum(overlap_dist.values())
for k in sorted(overlap_dist.keys()):
    pct = overlap_dist[k] / total_pairs * 100
    print(f'    Overlap {k}: {overlap_dist[k]:5d} ({pct:.1f}%)')
print(f'  This draw overlap: 1 [27]')

# Research 5: Consecutive number stats
print()
print('='*70)
print('  R5: Consecutive number pairs distribution')
print('='*70)

consec_dist = Counter()
for d in history:
    nums = sorted(d['numbers'])
    consec = sum(1 for j in range(len(nums)-1) if nums[j+1] - nums[j] == 1)
    consec_dist[consec] += 1
total_d = sum(consec_dist.values())
for k in sorted(consec_dist.keys()):
    pct = consec_dist[k] / total_d * 100
    print(f'    {k} pairs: {consec_dist[k]:5d} ({pct:.1f}%)')

# Research 6: Zone distribution
print()
print('='*70)
print('  R6: Zone distribution 0-2-3-1-0 analysis')
print('='*70)

zone_counter = Counter()
for d in history:
    nums = d['numbers']
    z = (sum(1 for n in nums if 1<=n<=10),
         sum(1 for n in nums if 11<=n<=20),
         sum(1 for n in nums if 21<=n<=30),
         sum(1 for n in nums if 31<=n<=40),
         sum(1 for n in nums if 41<=n<=49))
    zone_counter[z] += 1

target_zone = (0, 2, 3, 1, 0)
target_pct = zone_counter.get(target_zone, 0) / len(history) * 100
print(f'  Target zone: {target_zone}')
print(f'  Historical count: {zone_counter.get(target_zone, 0)} ({target_pct:.2f}%)')

z1_zero = sum(v for k,v in zone_counter.items() if k[0] == 0)
print(f'  Z1=0: {z1_zero}/{len(history)} ({z1_zero/len(history)*100:.1f}%)')
z5_zero = sum(v for k,v in zone_counter.items() if k[4] == 0)
print(f'  Z5=0: {z5_zero}/{len(history)} ({z5_zero/len(history)*100:.1f}%)')
z15_zero = sum(v for k,v in zone_counter.items() if k[0] == 0 and k[4] == 0)
print(f'  Z1&Z5=0: {z15_zero}/{len(history)} ({z15_zero/len(history)*100:.1f}%)')

# Research 7: Number 27 blind spot analysis
print()
print('='*70)
print('  R7: Number 27 blind spot analysis')
print('='*70)

print('  Number 27 last 20 draws:')
for i in range(20):
    idx = len(history) - 20 + i
    d = history[idx]
    hit = 'X' if 27 in d['numbers'] else ' '
    print(f'    {d["draw"]} {hit} {sorted(d["numbers"])}')

# Count 27 frequency in different windows
for w in [10, 20, 50, 100, 200]:
    recent = history[-w:]
    freq = sum(1 for d in recent if 27 in d['numbers'])
    expected = w * 6 / 49
    print(f'  27 in last {w:3d}: {freq} (expected: {expected:.1f}, dev: {freq - expected:+.1f})')

# Research 8: Cross-domain fusion potential
print()
print('='*70)
print('  R8: Cross-domain fusion potential (Fourier+Neighbor+Cold)')
print('='*70)

from scipy.fft import fft, fftfreq

m3_fusion = 0
for i in range(min(500, len(history) - 50)):
    target_idx = len(history) - 500 + i
    if target_idx < 50:
        continue
    target = history[target_idx]
    prev = history[target_idx - 1]
    actual = set(target['numbers'])
    hist_i = history[:target_idx]
    
    # Build Fourier scores
    window = min(500, len(hist_i))
    h_slice = hist_i[-window:]
    w = len(h_slice)
    bitstreams = {n: np.zeros(w) for n in range(1, 50)}
    for idx2, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= 49:
                bitstreams[n][idx2] = 1
    f_scores = {}
    for n in range(1, 50):
        bh = bitstreams[n]
        if sum(bh) < 2:
            f_scores[n] = 0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            f_scores[n] = 0
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            f_scores[n] = 1.0 / (abs(gap - period) + 1.0)
        else:
            f_scores[n] = 0
    
    # Fourier top 8
    f_ranked = sorted(f_scores.items(), key=lambda x: -x[1])
    fourier_pool = set(n for n, _ in f_ranked[:8])
    
    # Neighbor top (pure neighbors, not including prev numbers directly)
    neighbors = set()
    for n in prev['numbers']:
        for d in [-1, 0, 1]:
            nn = n + d
            if 1 <= nn <= 49: neighbors.add(nn)
    neighbor_pool = neighbors - fourier_pool
    
    # Bet1: Fourier top 6
    bet1 = sorted(list(fourier_pool))[:6]
    # Bet2: Best 6 from neighbors (not in bet1)
    bet2 = sorted(list(neighbor_pool - set(bet1)))[:6]
    
    hit1 = len(set(bet1) & actual)
    hit2 = len(set(bet2) & actual)
    if hit1 >= 3 or hit2 >= 3:
        m3_fusion += 1

test_periods = min(500, len(history) - 50)
rate_fusion = m3_fusion / test_periods * 100
print(f'  Fourier+Neighbor 2-bet fusion:')
print(f'  M3+: {m3_fusion}/{test_periods} ({rate_fusion:.2f}%)')
print(f'  Edge: {rate_fusion - baseline_2bet:+.2f}%')

# Now try 3-bet: Fourier + Neighbor + Cold
m3_fusion3 = 0
baseline_3bet = 5.49

for i in range(min(500, len(history) - 50)):
    target_idx = len(history) - 500 + i
    if target_idx < 50:
        continue
    target = history[target_idx]
    prev = history[target_idx - 1]
    actual = set(target['numbers'])
    hist_i = history[:target_idx]
    
    window = min(500, len(hist_i))
    h_slice = hist_i[-window:]
    w = len(h_slice)
    bitstreams = {n: np.zeros(w) for n in range(1, 50)}
    for idx2, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= 49:
                bitstreams[n][idx2] = 1
    f_scores = {}
    for n in range(1, 50):
        bh = bitstreams[n]
        if sum(bh) < 2:
            f_scores[n] = 0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            f_scores[n] = 0
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            f_scores[n] = 1.0 / (abs(gap - period) + 1.0)
        else:
            f_scores[n] = 0
    
    f_ranked = sorted(f_scores.items(), key=lambda x: -x[1])
    bet1 = sorted([n for n, _ in f_ranked[:6]])
    used = set(bet1)
    
    # Bet2: Neighbors
    neighbors = set()
    for n in prev['numbers']:
        for d in [-1, 0, 1]:
            nn = n + d
            if 1 <= nn <= 49: neighbors.add(nn)
    bet2 = sorted(list(neighbors - used))[:6]
    used.update(bet2)
    
    # Bet3: Cold
    gap_local = {}
    for n in range(1, 50):
        if n in used: continue
        found = False
        for j in range(len(hist_i)-1, -1, -1):
            if n in hist_i[j]['numbers']:
                gap_local[n] = len(hist_i) - 1 - j
                found = True
                break
        if not found:
            gap_local[n] = len(hist_i)
    cold_ranked = sorted(gap_local.items(), key=lambda x: -x[1])
    bet3 = sorted([n for n, _ in cold_ranked[:6]])
    
    for bet in [bet1, bet2, bet3]:
        if len(set(bet) & actual) >= 3:
            m3_fusion3 += 1
            break

rate_f3 = m3_fusion3 / test_periods * 100
print(f'\n  Fourier+Neighbor+Cold 3-bet fusion:')
print(f'  M3+: {m3_fusion3}/{test_periods} ({rate_f3:.2f}%)')
print(f'  Edge: {rate_f3 - baseline_3bet:+.2f}%')

print()
print('='*70)
print('  Analysis complete')
print('='*70)
