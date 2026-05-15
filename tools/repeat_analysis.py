#!/usr/bin/env python3
"""Analysis of repeat patterns and zone distributions"""
import sys, os
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew')
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')
from database import DatabaseManager
from collections import Counter
import numpy as np

db = DatabaseManager(db_path='/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db')
history = db.get_all_draws(lottery_type='DAILY_539')
history = sorted(history, key=lambda x: (x['date'], x['draw']))

# 1. Repeat pattern
repeat_counts = Counter()
for i in range(1, len(history)):
    prev = set(history[i-1]['numbers'])
    curr = set(history[i]['numbers'])
    overlap = len(prev & curr)
    repeat_counts[overlap] += 1
total = len(history) - 1
print('=== Repeat Number Distribution ===')
for k in sorted(repeat_counts.keys()):
    pct = repeat_counts[k] / total * 100
    print(f'  Repeat {k}: {repeat_counts[k]} times ({pct:.1f}%)')

# 2. Zone pattern
zone_dist = Counter()
for d in history:
    ns = sorted(d['numbers'])
    z = [0,0,0]
    for n in ns:
        if n <= 13: z[0] += 1
        elif n <= 26: z[1] += 1
        else: z[2] += 1
    zone_dist[f'{z[0]}L{z[1]}M{z[2]}H'] += 1
total_d = len(history)
print('\n=== Zone Pattern Distribution (full history) ===')
for pat, cnt in sorted(zone_dist.items(), key=lambda x: -x[1])[:15]:
    pct = cnt / total_d * 100
    marker = ' <-- THIS DRAW' if pat == '4L0M1H' else ''
    print(f'  {pat}: {cnt} times ({pct:.1f}%){marker}')

# 3. Low sum
low_sum = sum(1 for d in history if sum(d['numbers']) <= 65)
print(f'\nSum <= 65: {low_sum}/{total_d} ({low_sum/total_d*100:.1f}%)')

# 4. Repeat >= 3 cases
repeat3_cases = []
for i in range(1, len(history)):
    prev = set(history[i-1]['numbers'])
    curr = set(history[i]['numbers'])
    if len(prev & curr) >= 3:
        repeat3_cases.append(history[i]['draw'])
print(f'\nRepeat >= 3: {len(repeat3_cases)} times ({len(repeat3_cases)/total*100:.1f}%)')

# 5. #08 recent streak analysis
print('\n=== #08 Recent Appearance Pattern ===')
cnt_08 = 0
for d in history[-30:]:
    if 8 in d['numbers']:
        cnt_08 += 1
        print(f'  {d["draw"]}: {sorted(d["numbers"])}')
print(f'  #08 appeared {cnt_08}/30 recent draws')

# 6. Momentum / streak analysis
print('\n=== Momentum Analysis (repeat from prev) ===')
# When prev draw has hot numbers (8, 12 appeared in many recent), do they repeat?
hot_repeat_cnt = 0
hot_total = 0
for i in range(30, len(history)):
    prev = set(history[i-1]['numbers'])
    curr = set(history[i]['numbers'])
    # Check if any prev number had appeared in 3+ of last 5 draws
    recent5 = [set(history[j]['numbers']) for j in range(i-6, i-1)]
    for n in prev:
        streak = sum(1 for r in recent5 if n in r)
        if streak >= 2:  # appeared in 2+ of prev 5
            hot_total += 1
            if n in curr:
                hot_repeat_cnt += 1
if hot_total > 0:
    print(f'  Hot number repeat rate: {hot_repeat_cnt}/{hot_total} ({hot_repeat_cnt/hot_total*100:.1f}%)')
    print(f'  Baseline repeat rate: {5/39*100:.1f}%')
    print(f'  Edge: {hot_repeat_cnt/hot_total*100 - 5/39*100:+.1f}%')

# 7. Odd-even ratio
oe_dist = Counter()
for d in history:
    odd = sum(1 for n in d['numbers'] if n % 2 == 1)
    oe_dist[f'{odd}O{5-odd}E'] += 1
print('\n=== Odd/Even Distribution ===')
for pat, cnt in sorted(oe_dist.items(), key=lambda x: -x[1]):
    pct = cnt / total_d * 100
    marker = ' <-- THIS DRAW' if pat == '1O4E' else ''
    print(f'  {pat}: {cnt} ({pct:.1f}%){marker}')
