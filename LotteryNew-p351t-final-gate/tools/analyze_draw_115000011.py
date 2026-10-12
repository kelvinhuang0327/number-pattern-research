#!/usr/bin/env python3
"""
Comprehensive analysis of Power Lotto draw 115000011
Numbers: [7, 22, 28, 34, 36, 37], Special: 7
"""
import sqlite3
import json
from collections import Counter, defaultdict

DB_PATH = "lottery_api/data/lottery_v2.db"
TARGET_DRAW = "115000011"
TARGET_NUMBERS = [7, 22, 28, 34, 36, 37]
TARGET_SPECIAL = 7
PREV_DRAW = "115000010"
PREV_NUMBERS = [1, 12, 14, 15, 27, 29]
PREV_SPECIAL = 5

def load_draws(n=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    query = """SELECT draw, date, numbers, special FROM draws 
               WHERE lottery_type='POWER_LOTTO' ORDER BY date DESC"""
    if n:
        query += f" LIMIT {n}"
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    result = []
    for draw, date, nums_str, special in rows:
        nums = json.loads(nums_str)
        result.append((draw, date, nums, special))
    return result

def separator(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

def analyze_features(numbers):
    s = sum(numbers)
    odd_count = sum(1 for n in numbers if n % 2 == 1)
    even_count = 6 - odd_count
    big_count = sum(1 for n in numbers if n >= 20)
    small_count = 6 - big_count
    
    zones = {
        "Z1 (01-09)": [n for n in numbers if 1 <= n <= 9],
        "Z2 (10-19)": [n for n in numbers if 10 <= n <= 19],
        "Z3 (20-29)": [n for n in numbers if 20 <= n <= 29],
        "Z4 (30-38)": [n for n in numbers if 30 <= n <= 38],
    }
    
    sorted_nums = sorted(numbers)
    consecutives = []
    i = 0
    while i < len(sorted_nums):
        group = [sorted_nums[i]]
        while i + 1 < len(sorted_nums) and sorted_nums[i+1] == sorted_nums[i] + 1:
            i += 1
            group.append(sorted_nums[i])
        if len(group) >= 2:
            consecutives.append(group)
        i += 1
    
    tails = Counter(n % 10 for n in numbers)
    span = max(numbers) - min(numbers)
    
    return {
        'sum': s,
        'odd_even': (odd_count, even_count),
        'big_small': (big_count, small_count),
        'zones': zones,
        'consecutives': consecutives,
        'tails': tails,
        'span': span,
    }

# ============================================================
# ============================================================
all_draws = load_draws()
print(f"Total Power Lotto draws in DB: {len(all_draws)}")

# Draw 115000011 is not yet in DB, so we use it as target and compare with history
print(f"Target Draw: {TARGET_DRAW}")
print(f"Target Numbers: {TARGET_NUMBERS}, Special: {TARGET_SPECIAL}")

draws_before = [d for d in all_draws if d[0] <= CUTOFF_DRAW] if 'CUTOFF_DRAW' in locals() else all_draws
# Let's just use all_draws since it likely ends at 115000010
draws_before = all_draws
last_30 = draws_before[:30]
last_100 = draws_before[:100]
last_10 = draws_before[:10]

print(f"Draws before {TARGET_DRAW}: {len(draws_before)}")
print(f"Last 10 draws for context: {last_10[0][0]} ~ {last_10[-1][0]}")

# ============================================================
# 1. Basic Feature Analysis
# ============================================================
separator("1. Basic Feature Analysis (Draw 115000011: [7, 22, 28, 34, 36, 37], Special: 4)")

feat = analyze_features(TARGET_NUMBERS)

print(f"\n  Sum: {feat['sum']}")
print(f"    Theoretical expected: (1+38)/2 * 6 = {(1+38)/2 * 6:.0f}")
print(f"    Deviation: {feat['sum'] - 117:+d} ({'high' if feat['sum'] > 117 else 'low'})")

print(f"\n  Odd:Even ratio: {feat['odd_even'][0]}:{feat['odd_even'][1]}")
odd_nums = [n for n in TARGET_NUMBERS if n % 2 == 1]
even_nums = [n for n in TARGET_NUMBERS if n % 2 == 0]
print(f"    Odd:  {odd_nums}")
print(f"    Even: {even_nums}")

print(f"\n  Big:Small ratio (threshold=19): {feat['big_small'][0]}:{feat['big_small'][1]}")
big_nums = [n for n in TARGET_NUMBERS if n >= 20]
small_nums = [n for n in TARGET_NUMBERS if n < 20]
print(f"    Big (>=20): {big_nums}")
print(f"    Small(<20): {small_nums}")

print(f"\n  Zone distribution:")
for zone, nums in feat['zones'].items():
    print(f"    {zone}: {len(nums)} numbers {nums}")

print(f"\n  Consecutive groups:")
if feat['consecutives']:
    for grp in feat['consecutives']:
        print(f"    {grp} (run of {len(grp)})")
else:
    print(f"    None")

print(f"\n  Tail digit distribution:")
for tail in range(10):
    cnt = feat['tails'].get(tail, 0)
    nums_with_tail = [n for n in TARGET_NUMBERS if n % 10 == tail]
    if cnt > 0:
        print(f"    Tail {tail}: {cnt} number(s) {nums_with_tail}")
dup_tails = [(t, c) for t, c in feat['tails'].items() if c > 1]
if dup_tails:
    print(f"    ** Duplicate tails: {', '.join(f'tail-{t}({c}x)' for t,c in dup_tails)}")

print(f"\n  Span: {feat['span']} (min={min(TARGET_NUMBERS)}, max={max(TARGET_NUMBERS)})")

# ============================================================
# 2. Historical Comparison
# ============================================================
separator("2. Historical Comparison")

def compute_stats_for_draws(draws_list, label):
    sums = []
    odd_even_ratios = []
    big_small_ratios = []
    zone_counts = {z: [] for z in ["Z1 (01-09)", "Z2 (10-19)", "Z3 (20-29)", "Z4 (30-38)"]}
    consec_counts = []
    number_freq = Counter()
    special_freq = Counter()
    
    for draw, date, nums, special in draws_list:
        f = analyze_features(nums)
        sums.append(f['sum'])
        odd_even_ratios.append(f'{f["odd_even"][0]}:{f["odd_even"][1]}')
        big_small_ratios.append(f'{f["big_small"][0]}:{f["big_small"][1]}')
        for z, zn in f['zones'].items():
            zone_counts[z].append(len(zn))
        consec_counts.append(len(f['consecutives']))
        for n in nums:
            number_freq[n] += 1
        special_freq[special] += 1
    
    return {
        'sums': sums,
        'odd_even_ratios': Counter(odd_even_ratios),
        'big_small_ratios': Counter(big_small_ratios),
        'zone_counts': zone_counts,
        'consec_counts': consec_counts,
        'number_freq': number_freq,
        'special_freq': special_freq,
    }

stats_30 = compute_stats_for_draws(last_30, "30")
stats_100 = compute_stats_for_draws(last_100, "100")

# Sum comparison
print(f"\n  [Sum Comparison]")
print(f"    This draw: {feat['sum']}")
avg_30 = sum(stats_30['sums']) / len(stats_30['sums'])
avg_100 = sum(stats_100['sums']) / len(stats_100['sums'])
print(f"    Last 30 avg: {avg_30:.1f} (range: {min(stats_30['sums'])}~{max(stats_30['sums'])})")
print(f"    Last 100 avg: {avg_100:.1f} (range: {min(stats_100['sums'])}~{max(stats_100['sums'])})")
below_30 = sum(1 for s in stats_30['sums'] if s <= feat['sum'])
below_100 = sum(1 for s in stats_100['sums'] if s <= feat['sum'])
print(f"    Sum {feat['sum']} percentile in last 30: {below_30}/{len(stats_30['sums'])} ({below_30/len(stats_30['sums'])*100:.0f}th)")
print(f"    Sum {feat['sum']} percentile in last 100: {below_100}/{len(stats_100['sums'])} ({below_100/len(stats_100['sums'])*100:.0f}th)")

# Odd-even comparison
print(f"\n  [Odd:Even Ratio Distribution]")
our_oe = f'{feat["odd_even"][0]}:{feat["odd_even"][1]}'
print(f"    This draw: {our_oe}")
print(f"    Last 30 draws:")
for ratio, cnt in sorted(stats_30['odd_even_ratios'].items(), key=lambda x: -x[1]):
    marker = " <<<" if ratio == our_oe else ""
    print(f"      {ratio} : {cnt} times ({cnt/30*100:.1f}%){marker}")
print(f"    Last 100 draws:")
for ratio, cnt in sorted(stats_100['odd_even_ratios'].items(), key=lambda x: -x[1]):
    marker = " <<<" if ratio == our_oe else ""
    print(f"      {ratio} : {cnt} times ({cnt/100*100:.1f}%){marker}")

# Big-small comparison
print(f"\n  [Big:Small Ratio Distribution]")
our_bs = f'{feat["big_small"][0]}:{feat["big_small"][1]}'
print(f"    This draw: {our_bs}")
print(f"    Last 30 draws:")
for ratio, cnt in sorted(stats_30['big_small_ratios'].items(), key=lambda x: -x[1]):
    marker = " <<<" if ratio == our_bs else ""
    print(f"      {ratio} : {cnt} times ({cnt/30*100:.1f}%){marker}")
print(f"    Last 100 draws:")
for ratio, cnt in sorted(stats_100['big_small_ratios'].items(), key=lambda x: -x[1]):
    marker = " <<<" if ratio == our_bs else ""
    print(f"      {ratio} : {cnt} times ({cnt/100*100:.1f}%){marker}")

# Zone comparison
print(f"\n  [Zone Distribution Comparison]")
our_zones = {z: len(ns) for z, ns in feat['zones'].items()}
for z in ["Z1 (01-09)", "Z2 (10-19)", "Z3 (20-29)", "Z4 (30-38)"]:
    avg30 = sum(stats_30['zone_counts'][z]) / len(stats_30['zone_counts'][z])
    avg100 = sum(stats_100['zone_counts'][z]) / len(stats_100['zone_counts'][z])
    print(f"    {z}: this={our_zones[z]} | 30avg={avg30:.2f} | 100avg={avg100:.2f}")

# Consecutive comparison
print(f"\n  [Consecutive Number Comparison]")
our_consec = len(feat['consecutives'])
has_consec_30 = sum(1 for c in stats_30['consec_counts'] if c > 0)
has_consec_100 = sum(1 for c in stats_100['consec_counts'] if c > 0)
print(f"    This draw consecutive groups: {our_consec}")
print(f"    Last 30 with consecutives: {has_consec_30}/30 ({has_consec_30/30*100:.1f}%)")
print(f"    Last 100 with consecutives: {has_consec_100}/100 ({has_consec_100/100*100:.1f}%)")

# Number frequency (hot/cold)
print(f"\n  [Number Temperature - Last 30 Draws]")
print(f"    Expected frequency per number: 30 * 6/38 = {30*6/38:.2f}")
print()

for n in sorted(TARGET_NUMBERS):
    freq = stats_30['number_freq'].get(n, 0)
    if freq >= 6:
        status = "VERY HOT"
    elif freq >= 4:
        status = "HOT"
    elif freq < 2:
        status = "VERY COLD"
    elif freq < 3:
        status = "COLD"
    else:
        status = "NORMAL"
    bar = "#" * freq
    print(f"    Number {n:2d}: {freq:2d} times {bar:20s} [{status}]")

print(f"\n    --- Full Hot/Cold Table (Last 30) ---")
print(f"    Very Hot (>=6):", end=" ")
hot = sorted([n for n in range(1, 39) if stats_30['number_freq'].get(n, 0) >= 6])
print(hot if hot else "None")

print(f"    Hot (4-5):", end=" ")
warm = sorted([n for n in range(1, 39) if 4 <= stats_30['number_freq'].get(n, 0) <= 5])
print(warm if warm else "None")

print(f"    Normal (3):", end=" ")
mid = sorted([n for n in range(1, 39) if stats_30['number_freq'].get(n, 0) == 3])
print(mid if mid else "None")

print(f"    Cold (1-2):", end=" ")
cold = sorted([n for n in range(1, 39) if 1 <= stats_30['number_freq'].get(n, 0) <= 2])
print(cold if cold else "None")

print(f"    Ice (0):", end=" ")
ice = sorted([n for n in range(1, 39) if stats_30['number_freq'].get(n, 0) == 0])
print(ice if ice else "None")

hot_in_draw = [n for n in TARGET_NUMBERS if stats_30['number_freq'].get(n, 0) >= 6]
warm_in_draw = [n for n in TARGET_NUMBERS if 4 <= stats_30['number_freq'].get(n, 0) <= 5]
cold_in_draw = [n for n in TARGET_NUMBERS if stats_30['number_freq'].get(n, 0) < 3]
mid_in_draw = [n for n in TARGET_NUMBERS if stats_30['number_freq'].get(n, 0) == 3]
print(f"\n    This draw's numbers classified:")
print(f"      Very Hot (>=6): {hot_in_draw}")
print(f"      Hot (4-5):      {warm_in_draw}")
print(f"      Normal (3):     {mid_in_draw}")
print(f"      Cold (<3):      {cold_in_draw}")

# 100 draws
print(f"\n  [Number Temperature - Last 100 Draws]")
print(f"    Expected frequency: 100 * 6/38 = {100*6/38:.2f}")
for n in sorted(TARGET_NUMBERS):
    freq = stats_100['number_freq'].get(n, 0)
    expected = 100 * 6 / 38
    deviation = (freq - expected) / expected * 100
    print(f"    Number {n:2d}: {freq:2d} times (deviation: {deviation:+.1f}%)")

# ============================================================
# 3. Comparison with Previous Draw
# ============================================================
separator("3. Comparison with Previous Draw (115000010: [1,12,14,15,27,29] sp=5)")

overlap = set(TARGET_NUMBERS) & set(PREV_NUMBERS)
print(f"\n  Number overlap: {len(overlap)} {sorted(overlap) if overlap else 'None'}")
new_nums = sorted(set(TARGET_NUMBERS) - set(PREV_NUMBERS))
gone_nums = sorted(set(PREV_NUMBERS) - set(TARGET_NUMBERS))
print(f"  New numbers:     {new_nums}")
print(f"  Gone numbers:    {gone_nums}")

print(f"\n  Zone transition:")
prev_feat = analyze_features(PREV_NUMBERS)
for z in ["Z1 (01-09)", "Z2 (10-19)", "Z3 (20-29)", "Z4 (30-38)"]:
    prev_c = len(prev_feat['zones'][z])
    curr_c = len(feat['zones'][z])
    change = curr_c - prev_c
    arrow = "+" if change > 0 else str(change) if change < 0 else "="
    print(f"    {z}: {prev_c} -> {curr_c} ({arrow})")
    if prev_feat['zones'][z] or feat['zones'][z]:
        print(f"            prev: {prev_feat['zones'][z]}  curr: {feat['zones'][z]}")

print(f"\n  Sum change:       {prev_feat['sum']} -> {feat['sum']} ({feat['sum']-prev_feat['sum']:+d})")
print(f"  Odd:Even change:  {prev_feat['odd_even'][0]}:{prev_feat['odd_even'][1]} -> {feat['odd_even'][0]}:{feat['odd_even'][1]}")
print(f"  Big:Small change: {prev_feat['big_small'][0]}:{prev_feat['big_small'][1]} -> {feat['big_small'][0]}:{feat['big_small'][1]}")

print(f"\n  Consecutive change:")
print(f"    Prev: {prev_feat['consecutives'] if prev_feat['consecutives'] else 'None'}")
print(f"    Curr: {feat['consecutives'] if feat['consecutives'] else 'None'}")

print(f"\n  Special number change: {PREV_SPECIAL} -> {TARGET_SPECIAL} ({TARGET_SPECIAL-PREV_SPECIAL:+d})")

# Check historical overlap distribution
print(f"\n  [Historical overlap distribution (last 30 consecutive draw pairs)]")
overlap_counts = Counter()
for i in range(min(30, len(draws_before)-1)):
    d1_nums = set(draws_before[i][2])
    d2_nums = set(draws_before[i+1][2])
    ov = len(d1_nums & d2_nums)
    overlap_counts[ov] += 1
print(f"    0 overlap: {overlap_counts.get(0,0)} times")
print(f"    1 overlap: {overlap_counts.get(1,0)} times")
print(f"    2 overlap: {overlap_counts.get(2,0)} times")
print(f"    3 overlap: {overlap_counts.get(3,0)} times")
print(f"    4+ overlap: {sum(v for k,v in overlap_counts.items() if k>=4)} times")
print(f"    This draw: {len(overlap)} overlap (vs prev)")

# ============================================================
# 4. Special Number Analysis
# ============================================================
separator("4. Special Number Analysis (Special: 4)")

sp_4_in_30 = sum(1 for _, _, _, sp in last_30 if sp == TARGET_SPECIAL)
sp_4_in_100 = sum(1 for _, _, _, sp in last_100 if sp == TARGET_SPECIAL)

print(f"\n  Special {TARGET_SPECIAL} frequency:")
print(f"    Last 30:  {sp_4_in_30} times ({sp_4_in_30/30*100:.1f}%)")
print(f"    Last 100: {sp_4_in_100} times ({sp_4_in_100/100*100:.1f}%)")
print(f"    Expected: 1/8 per draw = 12.5%")

print(f"\n  Special number distribution (last 30):")
for sp_num in range(1, 9):
    cnt = stats_30['special_freq'].get(sp_num, 0)
    bar = "#" * cnt
    marker = " <<<" if sp_num == TARGET_SPECIAL else ""
    print(f"    Special {sp_num}: {cnt:2d} times ({cnt/30*100:.1f}%) {bar}{marker}")

print(f"\n  Special {TARGET_SPECIAL} periodicity (including this draw):")
sp4_draws = []
for i, (draw, date, nums, sp) in enumerate(all_draws):
    if sp == TARGET_SPECIAL:
        sp4_draws.append((draw, date, i))
    if len(sp4_draws) >= 15:
        break

if len(sp4_draws) >= 2:
    gaps = []
    for j in range(len(sp4_draws)-1):
        gap = sp4_draws[j+1][2] - sp4_draws[j][2]
        gaps.append(gap)
    
    print(f"    Recent occurrences (up to 15):")
    for j, (draw, date, idx) in enumerate(sp4_draws):
        gap_str = f"  (gap: {gaps[j]} draws)" if j < len(gaps) else ""
        print(f"      {draw} ({date}){gap_str}")
    
    print(f"\n    Gap stats: mean={sum(gaps)/len(gaps):.1f}, min={min(gaps)}, max={max(gaps)}")
    print(f"    Gap distribution: {sorted(gaps)}")

# ============================================================
# 5. Echo Pattern Analysis
# ============================================================
separator("5. Echo Pattern Analysis (Last 10 Draws)")

print(f"\n  Last 10 draws (before this draw):")
for i, (draw, date, nums, sp) in enumerate(last_10):
    print(f"    {i+1} ago | {draw} ({date}): {nums} sp={sp}")

print(f"\n  Echo sources for {TARGET_NUMBERS}:")
echo_sources = defaultdict(list)
no_echo = []

for num in TARGET_NUMBERS:
    found = False
    for i, (draw, date, nums, sp) in enumerate(last_10):
        if num in nums:
            echo_sources[num].append((i+1, draw))
            found = True
    if not found:
        no_echo.append(num)

for num in sorted(TARGET_NUMBERS):
    if num in echo_sources:
        sources = echo_sources[num]
        source_str = ", ".join(f"{ago} ago({did})" for ago, did in sources)
        min_ago = min(s[0] for s in sources)
        if min_ago <= 2:
            echo_type = "SHORT echo (1-2)"
        elif min_ago <= 5:
            echo_type = "MID echo (3-5)"
        else:
            echo_type = "LONG echo (6-10)"
        total_hits = len(sources)
        print(f"    Number {num:2d}: {echo_type} | {total_hits}x in last 10 | {source_str}")
    else:
        print(f"    Number {num:2d}: *** FRESH *** (not in last 10 draws)")

echo_1 = [n for n in TARGET_NUMBERS if n in echo_sources and any(ago == 1 for ago, _ in echo_sources[n])]
echo_2_5 = [n for n in TARGET_NUMBERS if n in echo_sources and any(2 <= ago <= 5 for ago, _ in echo_sources[n])]
echo_6_10 = [n for n in TARGET_NUMBERS if n in echo_sources and all(ago >= 6 for ago, _ in echo_sources[n])]

print(f"\n  Echo Summary:")
print(f"    From prev draw (1 ago):  {echo_1}")
print(f"    From 2-5 draws ago:      {echo_2_5}")
print(f"    From 6-10 draws ago only:{echo_6_10}")
print(f"    Completely fresh:        {no_echo}")
print(f"    Echo rate: {len(TARGET_NUMBERS)-len(no_echo)}/{len(TARGET_NUMBERS)} = "
      f"{(len(TARGET_NUMBERS)-len(no_echo))/len(TARGET_NUMBERS)*100:.1f}%")

# Special echo
print(f"\n  Special {TARGET_SPECIAL} echo:")
sp_echo_main = []
sp_echo_sp = []
for i, (draw, date, nums, sp) in enumerate(last_10):
    if sp == TARGET_SPECIAL:
        sp_echo_sp.append((i+1, draw))
    if TARGET_SPECIAL in nums:
        sp_echo_main.append((i+1, draw))

if sp_echo_sp:
    for ago, src in sp_echo_sp:
        print(f"    As special: {ago} ago ({src})")
else:
    print(f"    As special: not in last 10")
if sp_echo_main:
    for ago, src in sp_echo_main:
        print(f"    As main number: {ago} ago ({src})")
else:
    print(f"    As main number: not in last 10")

# ============================================================
# SUMMARY
# ============================================================
separator("COMPREHENSIVE SUMMARY")

print(f"""
  Draw 115000011: {TARGET_NUMBERS}, Special: {TARGET_SPECIAL}

  1. Structural Features:
     - Sum {feat['sum']} is HIGH (expected 117, {feat['sum']-117:+d})
     - Odd:Even = {feat['odd_even'][0]}:{feat['odd_even'][1]} (odd-heavy)
     - Big:Small = {feat['big_small'][0]}:{feat['big_small'][1]} (big-heavy)
     - Zones: Z1={len(feat['zones']['Z1 (01-09)'])} Z2={len(feat['zones']['Z2 (10-19)'])} Z3={len(feat['zones']['Z3 (20-29)'])} Z4={len(feat['zones']['Z4 (30-38)'])}
       Heavily skewed to Z3+Z4 (5 of 6 numbers >= 20)
     - Consecutives: {feat['consecutives'] if feat['consecutives'] else 'None'}
     - Span: {feat['span']} (moderate)
     - Duplicate tails: {', '.join(f'tail-{t}({c}x)' for t,c in dup_tails) if dup_tails else 'None'}

  2. Temperature Composition (30 draws):
     - Very Hot (>=6): {hot_in_draw}
     - Hot (4-5):      {warm_in_draw}
     - Normal (3):     {mid_in_draw}
     - Cold (<3):      {cold_in_draw}

  3. vs Previous Draw (115000010):
     - ZERO overlap: complete set change
     - Massive shift from small to big numbers
     - Sum jumped: {prev_feat['sum']} -> {feat['sum']} (+{feat['sum']-prev_feat['sum']})
     - Special: {PREV_SPECIAL} -> {TARGET_SPECIAL}

  4. Special Number 4:
     - Appeared {sp_4_in_30}x in last 30 (expected ~3.75)
     - Appeared {sp_4_in_100}x in last 100 (expected ~12.5)

  5. Echo Analysis:
     - Echo numbers: {sorted(set(TARGET_NUMBERS) - set(no_echo))}
     - Fresh numbers: {no_echo}
     - Echo rate: {(len(TARGET_NUMBERS)-len(no_echo))/len(TARGET_NUMBERS)*100:.0f}%
""")
