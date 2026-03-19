#!/usr/bin/env python3
"""Supplementary statistics for 020 review"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api'))
from database import DatabaseManager
from collections import Counter
import numpy as np

db = DatabaseManager(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api', 'data', 'lottery_v2.db'))
draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))

# 1. Lag-1 repeat statistics
print('=== Lag-1 Repeat Rate Stats ===')
repeats = []
for i in range(1, len(draws)):
    prev = set(draws[i-1]['numbers'][:6])
    curr = set(draws[i]['numbers'][:6])
    overlap = len(prev & curr)
    repeats.append(overlap)

repeat_counter = Counter(repeats)
total = len(repeats)
print(f'Total periods: {total}')
for k in sorted(repeat_counter.keys()):
    pct = repeat_counter[k] / total * 100
    print(f'  Repeat {k}: {repeat_counter[k]} times ({pct:.1f}%)')
print(f'  Avg repeat: {np.mean(repeats):.2f}')
r3plus = sum(1 for r in repeats if r >= 3)
print(f'  Repeat>=3: {r3plus}/{total} ({r3plus/total*100:.1f}%)')

# 2. Lag-1 injection backtest
print()
print('=== Lag-1 Injection Backtest (last 200) ===')
start = max(1, len(draws) - 200)
inject_hits_total = 0
for i in range(start, len(draws)):
    prev = set(draws[i-1]['numbers'][:6])
    curr = set(draws[i]['numbers'][:6])
    inject_hits_total += len(prev & curr)
n_periods = len(draws) - start
baseline_per_period = 6 * 6 / 38
print(f'Last {n_periods} periods:')
print(f'  Prev 6 nums as 1 bet: avg hit {inject_hits_total/n_periods:.2f} (random baseline={baseline_per_period:.2f})')
print(f'  Edge ratio: {(inject_hits_total/n_periods) / baseline_per_period:.2f}x')

# 3. Special number cold gap analysis
print()
print('=== Special Number Cold Gap Analysis ===')
sp_gaps_at_hit = []
for i in range(1, len(draws)):
    sp = draws[i].get('special', 0)
    if sp == 0:
        continue
    gap = 0
    for j in range(i-1, -1, -1):
        gap += 1
        if draws[j].get('special', 0) == sp:
            break
    sp_gaps_at_hit.append(gap)

gap_counter = Counter()
for g in sp_gaps_at_hit:
    if g <= 5: gap_counter['1-5'] += 1
    elif g <= 10: gap_counter['6-10'] += 1
    elif g <= 15: gap_counter['11-15'] += 1
    elif g <= 20: gap_counter['16-20'] += 1
    else: gap_counter['21+'] += 1

print(f'Special number gap distribution when drawn:')
for k in ['1-5', '6-10', '11-15', '16-20', '21+']:
    pct = gap_counter.get(k, 0) / len(sp_gaps_at_hit) * 100
    print(f'  Gap {k}: {gap_counter.get(k, 0)} times ({pct:.1f}%)')
print(f'  Avg gap: {np.mean(sp_gaps_at_hit):.1f}')
g20 = sum(1 for g in sp_gaps_at_hit if g >= 20)
print(f'  Gap>=20: {g20}/{len(sp_gaps_at_hit)} ({g20/len(sp_gaps_at_hit)*100:.1f}%)')

# 4. Deviation(w50) performance
print()
print('=== Deviation(w50) Performance (last 200) ===')
dev_hits_list = []
for i in range(max(51, len(draws)-200), len(draws)):
    window = 50
    recent = draws[max(0,i-window):i]
    expected = len(recent) * 6 / 38
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            if n <= 38:
                freq[n] += 1
    devs = {n: freq.get(n,0) - expected for n in range(1, 39)}
    ranked = sorted(range(1,39), key=lambda n: devs[n], reverse=True)
    actual = set(draws[i]['numbers'][:6])
    hits = len(set(ranked[:6]) & actual)
    dev_hits_list.append(hits)
avg_dev_hit = np.mean(dev_hits_list)
h2 = sum(1 for h in dev_hits_list if h >= 2)/len(dev_hits_list)*100
h3 = sum(1 for h in dev_hits_list if h >= 3)/len(dev_hits_list)*100
print(f'  Last {len(dev_hits_list)} periods Dev(w50) Top6 avg hits: {avg_dev_hit:.2f}')
print(f'  Hit>=2: {h2:.1f}%')
print(f'  Hit>=3: {h3:.1f}%')

# 5. Lag-1+Deviation hybrid
print()
print('=== Lag-1+Dev(w50) Hybrid (last 200) ===')
hybrid_hits = []
for i in range(max(51, len(draws)-200), len(draws)):
    prev_nums = set(draws[i-1]['numbers'][:6])
    # Dev scores
    window = 50
    recent = draws[max(0,i-window):i]
    expected = len(recent) * 6 / 38
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            if n <= 38:
                freq[n] += 1
    devs = {n: freq.get(n,0) - expected for n in range(1, 39)}
    # Hybrid: prev_nums get bonus
    hybrid_scores = {}
    for n in range(1, 39):
        hybrid_scores[n] = devs[n] + (3.0 if n in prev_nums else 0)
    ranked = sorted(range(1,39), key=lambda n: hybrid_scores[n], reverse=True)
    actual = set(draws[i]['numbers'][:6])
    hits = len(set(ranked[:6]) & actual)
    hybrid_hits.append(hits)
avg_hybrid = np.mean(hybrid_hits)
hh2 = sum(1 for h in hybrid_hits if h >= 2)/len(hybrid_hits)*100
hh3 = sum(1 for h in hybrid_hits if h >= 3)/len(hybrid_hits)*100
print(f'  Hybrid Top6 avg hits: {avg_hybrid:.2f}')
print(f'  Hit>=2: {hh2:.1f}%')
print(f'  Hit>=3: {hh3:.1f}%')

# 6. Fourier window comparison
print()
print('=== Fourier Window Top6 Performance (last 200) ===')
from scipy.fft import fft, fftfreq
for wnd in [30, 50, 100, 200, 500]:
    f_hits = []
    for i in range(max(wnd+1, len(draws)-200), len(draws)):
        h_slice = draws[max(0,i-wnd):i]
        w = len(h_slice)
        if w < 10:
            continue
        scores = {}
        for n in range(1, 39):
            bh = np.zeros(w)
            for idx, d in enumerate(h_slice):
                if n in d['numbers']:
                    bh[idx] = 1
            if sum(bh) < 2:
                scores[n] = 0
                continue
            yf = fft(bh - np.mean(bh))
            xf = fftfreq(w, 1)
            idx_pos = np.where(xf > 0)
            pos_yf = np.abs(yf[idx_pos])
            pos_xf = xf[idx_pos]
            peak_idx = np.argmax(pos_yf)
            freq_val = pos_xf[peak_idx]
            if freq_val == 0:
                scores[n] = 0
                continue
            period = 1 / freq_val
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
        ranked = sorted(range(1,39), key=lambda n: scores.get(n,0), reverse=True)
        actual = set(draws[i]['numbers'][:6])
        hits = len(set(ranked[:6]) & actual)
        f_hits.append(hits)
    if f_hits:
        avg = np.mean(f_hits)
        p2 = sum(1 for h in f_hits if h >= 2)/len(f_hits)*100
        print(f'  Fourier w={wnd}: avg={avg:.2f}, hit>=2: {p2:.1f}% (n={len(f_hits)})')
