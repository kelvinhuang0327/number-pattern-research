#!/usr/bin/env python3
import sqlite3, json, numpy as np
from collections import Counter

conn = sqlite3.connect('lottery_api/data/lottery_v2.db')
c = conn.cursor()
c.execute('SELECT draw, date, numbers FROM draws WHERE lottery_type="BIG_LOTTO" ORDER BY date ASC, draw ASC')
rows = c.fetchall()
conn.close()

history = []
for r in rows:
    nums = json.loads(r[2])
    history.append({'draw': r[0], 'date': r[1], 'numbers': sorted(nums[:6])})

ACTUAL = [9, 11, 12, 14, 23, 25]
actual_sum = sum(ACTUAL)

sums = [sum(d['numbers']) for d in history]
low_sum_count = sum(1 for s in sums if s <= 100)
print(f'sum<=100: {low_sum_count}/{len(sums)} ({low_sum_count/len(sums)*100:.1f}%)')
print(f'sum<=94: {sum(1 for s in sums if s <= 94)}/{len(sums)} ({sum(1 for s in sums if s <= 94)/len(sums)*100:.2f}%)')

all_low = sum(1 for d in history if all(n <= 25 for n in d['numbers']))
print(f'\nAll 6 nums <=25: {all_low}/{len(history)} ({all_low/len(history)*100:.2f}%)')

for i, d in enumerate(reversed(history)):
    if all(n <= 25 for n in d['numbers']):
        print(f'Last all-low: {d["draw"]} ({d["date"]}) = {i} draws ago')
        break

prev_sum = sum(history[-1]['numbers'])
print(f'\nPrev sum: {prev_sum}, Actual sum: {actual_sum}, Gap: {actual_sum - prev_sum}')
print(f'Last 10 sums: {[sum(d["numbers"]) for d in history[-10:]]}')

recent5_sums = [sum(d['numbers']) for d in history[-5:]]
mu300 = np.mean(sums[-300:])
sg300 = np.std(sums[-300:])
print(f'\nLast 5 sums: {recent5_sums} avg: {np.mean(recent5_sums):.1f}')
print(f'Sum 94 vs mu={mu300:.1f}, deviation: {(94 - mu300) / sg300:.2f} sigma')

# Check how many times 6/6 numbers were in bottom half historically
bottom_half_6 = sum(1 for d in history if sum(1 for n in d['numbers'] if n <= 25) == 6)
bottom_half_5 = sum(1 for d in history if sum(1 for n in d['numbers'] if n <= 25) >= 5)
print(f'\n6/6 in bottom half: {bottom_half_6} ({bottom_half_6/len(history)*100:.2f}%)')
print(f'>=5/6 in bottom half: {bottom_half_5} ({bottom_half_5/len(history)*100:.2f}%)')

# Regime detection - consecutive high sums before low bounce
print(f'\n--- Sum Regime ---')
for i in range(10):
    s = sum(history[-(i+1)]['numbers'])
    print(f'  {history[-(i+1)]["draw"]}: sum={s} (z={(s-mu300)/sg300:+.2f})')
print(f'  >>> 033: sum=94 (z={(94-mu300)/sg300:+.2f})')

# What if we had a "low sum predictor" - count consecutive above-mean sums
consec_above = 0
for d in reversed(history):
    if sum(d['numbers']) > mu300:
        consec_above += 1
    else:
        break
print(f'\nConsecutive draws with sum > mean: {consec_above}')

# Number cluster density
print(f'\n--- Cluster analysis ---')
for d in history[-5:]:
    nums = sorted(d['numbers'])
    max_cluster = max(nums[i+1]-nums[i] for i in range(5))
    min_gap = min(nums[i+1]-nums[i] for i in range(5))
    span = nums[-1] - nums[0]
    print(f'  {d["draw"]}: {nums} span={span} min_gap={min_gap} max_gap={max_cluster}')
print(f'  033: {ACTUAL} span={ACTUAL[-1]-ACTUAL[0]} min_gap={min([ACTUAL[i+1]-ACTUAL[i] for i in range(5)])} max_gap={max([ACTUAL[i+1]-ACTUAL[i] for i in range(5)])}')
