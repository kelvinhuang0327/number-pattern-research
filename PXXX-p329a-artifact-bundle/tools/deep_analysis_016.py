#!/usr/bin/env python3
"""深度分析: 什麼方法能預測到 115000016 的號碼 [4,10,13,24,31,35]"""
import sys, os
import numpy as np
from collections import Counter, defaultdict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
from database import DatabaseManager

db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
hist = draws  # All 1887 draws before 115000016

actual = {4, 10, 13, 24, 31, 35}
actual_sorted = [4, 10, 13, 24, 31, 35]

print("=" * 70)
print("  深度方法對比分析: 第115000016期 [4,10,13,24,31,35]")
print("=" * 70)
print()

# === Method A: Cold Number Rebound (冷號回歸) ===
print("--- Method A: 冷號回歸 (Cold Rebound) ---")
for window in [30, 50, 100, 200]:
    recent = hist[-window:]
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    # Coldest 12 numbers
    all_nums = list(range(1, 39))
    all_nums.sort(key=lambda x: freq.get(x, 0))
    coldest_12 = all_nums[:12]
    bet1 = sorted(coldest_12[:6])
    bet2 = sorted(coldest_12[6:12])
    hits1 = len(set(bet1) & actual)
    hits2 = len(set(bet2) & actual)
    total_hits = len(set(coldest_12) & actual)
    print(f"  Window={window}: 冷12={coldest_12} → 命中={sorted(set(coldest_12) & actual)} ({total_hits}個)")
    print(f"    注1:{bet1}→{hits1}, 注2:{bet2}→{hits2}")
print()

# === Method B: Gap Period Analysis ===
print("--- Method B: Gap 週期分析 ---")
for n in actual_sorted:
    # Find all gaps for this number
    appearances = []
    for i, d in enumerate(hist):
        if n in d['numbers']:
            appearances.append(i)
    if len(appearances) < 3:
        print(f"  號碼{n:02d}: 出現次數太少")
        continue
    gaps_ = [appearances[i+1] - appearances[i] for i in range(len(appearances)-1)]
    avg_gap = np.mean(gaps_)
    std_gap = np.std(gaps_)
    last_app = appearances[-1]
    current_gap = len(hist) - last_app
    gap_ratio = current_gap / avg_gap if avg_gap > 0 else 0
    print(f"  號碼{n:02d}: 平均gap={avg_gap:.1f}±{std_gap:.1f}, 現gap={current_gap}, 比率={gap_ratio:.2f}")
print()

# === Method C: Deviation from Expected (偏差分析) ===
print("--- Method C: 偏差分析 (近50/100期) ---")
for window in [50, 100]:
    recent = hist[-window:]
    expected = window * 6 / 38
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    # Most underrepresented numbers
    deviations = {n: freq.get(n, 0) - expected for n in range(1, 39)}
    sorted_dev = sorted(deviations.items(), key=lambda x: x[1])
    under_12 = [n for n, _ in sorted_dev[:12]]
    bet1 = sorted(under_12[:6])
    bet2 = sorted(under_12[6:12])
    hits = len(set(under_12) & actual)
    print(f"  Window={window}: 最低偏差12={under_12} → 命中={sorted(set(under_12) & actual)} ({hits}個)")
    print(f"    注1:{bet1}, 注2:{bet2}")
print()

# === Method D: Markov Transition (馬可夫轉移) ===
print("--- Method D: 馬可夫轉移 ---")
# For each number, P(appear next | appeared in N-k draws)
prev_nums = set(hist[-1]['numbers'])
prev2_nums = set(hist[-2]['numbers'])
prev3_nums = set(hist[-3]['numbers'])
recent_context = prev_nums | prev2_nums | prev3_nums

# Build transition matrix: P(n appears | context)
transition_scores = {}
lookback = 500
for n in range(1, 39):
    transitions = 0
    opportunities = 0
    for i in range(len(hist) - lookback, len(hist)):
        context = set()
        if i >= 1: context |= set(hist[i-1]['numbers'])
        if i >= 2: context |= set(hist[i-2]['numbers'])
        if i >= 3: context |= set(hist[i-3]['numbers'])
        # Did any of current context numbers appear before n?
        shared = context & recent_context
        if len(shared) >= 2:
            opportunities += 1
            if n in hist[i]['numbers']:
                transitions += 1
    if opportunities > 0:
        transition_scores[n] = transitions / opportunities
    else:
        transition_scores[n] = 0

ranked = sorted(transition_scores.items(), key=lambda x: -x[1])
top12 = [n for n, _ in ranked[:12]]
hits_markov = len(set(top12) & actual)
print(f"  Top 12 Markov: {top12} → 命中={sorted(set(top12) & actual)} ({hits_markov}個)")
for n in actual_sorted:
    rank = [i+1 for i, (nn, _) in enumerate(ranked) if nn == n][0]
    print(f"    號碼{n:02d}: Markov排名 #{rank} (P={transition_scores[n]:.3f})")
print()

# === Method E: Zone Balance (區間平衡) ===
print("--- Method E: 區間平衡分析 ---")
zones = {
    'Z1': list(range(1, 11)),    # 1-10
    'Z2': list(range(11, 21)),   # 11-20
    'Z3': list(range(21, 31)),   # 21-30
    'Z4': list(range(31, 39)),   # 31-38
}
# Recent zone distribution
recent20 = hist[-20:]
zone_freq = defaultdict(int)
for d in recent20:
    for n in d['numbers']:
        for zname, znums in zones.items():
            if n in znums:
                zone_freq[zname] += 1

expected_zone = {
    'Z1': 20 * 6 * 10/38,
    'Z2': 20 * 6 * 10/38,
    'Z3': 20 * 6 * 10/38,
    'Z4': 20 * 6 * 8/38,
}
print(f"  近20期區間分布:")
for z in ['Z1', 'Z2', 'Z3', 'Z4']:
    dev = zone_freq[z] - expected_zone[z]
    print(f"    {z}: 實際={zone_freq[z]}, 期望={expected_zone[z]:.1f}, 偏差={dev:+.1f}")

# 115000016 zone: Z1=2, Z2=1, Z3=1, Z4=2
print(f"  115000016區間: Z1=2(4,10), Z2=1(13), Z3=1(24), Z4=2(31,35)")
print()

# === Method F: Pairwise Co-occurrence (號碼共現) ===
print("--- Method F: 號碼共現分析 ---")
# Check if any pairs in actual set have notable co-occurrence
from itertools import combinations
pair_freq = Counter()
lookback = 300
for d in hist[-lookback:]:
    nums = d['numbers']
    for pair in combinations(sorted(nums), 2):
        pair_freq[pair] += 1

print(f"  開獎號碼的兩兩共現 (近{lookback}期):")
actual_pairs = list(combinations(actual_sorted, 2))
for pair in actual_pairs:
    freq = pair_freq.get(pair, 0)
    expected_pair = lookback * (6*5)/(38*37) * 2  # Approximate
    print(f"    {pair}: 共現{freq}次 (期望≈{expected_pair:.1f})")
print()

# === Method G: Tail Number Pattern (尾數模式) ===
print("--- Method G: 尾數模式分析 ---")
recent30 = hist[-30:]
tail_freq = Counter()
for d in recent30:
    for n in d['numbers']:
        tail_freq[n % 10] += 1

expected_tail = 30 * 6 / 10
print(f"  近30期尾數分布 (期望={expected_tail:.1f}):")
for t in range(10):
    dev = tail_freq[t] - expected_tail
    in_actual = [n for n in actual_sorted if n % 10 == t]
    marker = f" ← {in_actual}" if in_actual else ""
    print(f"    尾{t}: {tail_freq[t]}次 ({dev:+.1f}){marker}")
print()

# === Method H: Sum Range Filter (和值範圍) ===
print("--- Method H: 和值範圍 ---")
sums = [sum(d['numbers']) for d in hist[-200:]]
mean_s = np.mean(sums)
std_s = np.std(sums)
actual_sum = sum(actual_sorted)
percentile = np.percentile(sums, [10, 25, 50, 75, 90])
print(f"  近200期和值: mean={mean_s:.1f}, std={std_s:.1f}")
print(f"  百分位: P10={percentile[0]:.0f}, P25={percentile[1]:.0f}, P50={percentile[2]:.0f}, P75={percentile[3]:.0f}, P90={percentile[4]:.0f}")
print(f"  開獎和值: {actual_sum} → z={((actual_sum-mean_s)/std_s):.2f}")
print()

# === Method I: Comprehensive Scoring (綜合評分) ===
print("--- Method I: 綜合評分 (組合多信號) ---")
# Combine: deviation, gap_ratio, fourier, cold
final_scores = {}
# 1. Deviation score (50-period)
recent50 = hist[-50:]
expected50 = 50 * 6 / 38
freq50 = Counter()
for d in recent50:
    for n in d['numbers']:
        freq50[n] += 1
for n in range(1, 39):
    dev = freq50.get(n, 0) - expected50
    final_scores[n] = -dev * 0.3  # Negative deviation = positive score

# 2. Gap ratio score
for n in range(1, 39):
    appearances = [i for i, d in enumerate(hist) if n in d['numbers']]
    if len(appearances) >= 3:
        gaps_ = [appearances[i+1] - appearances[i] for i in range(len(appearances)-1)]
        avg_gap = np.mean(gaps_)
        current_gap = len(hist) - appearances[-1]
        ratio = current_gap / avg_gap if avg_gap > 0 else 0
        # Score peaks at ratio = 1.0 (due)
        gap_score = 1.0 / (abs(ratio - 1.0) + 0.5)
        final_scores[n] = final_scores.get(n, 0) + gap_score * 0.3

# 3. Fourier score
from scipy.fft import fft, fftfreq
window = 500
h_slice = hist[-window:]
w = len(h_slice)
bitstreams = {i: np.zeros(w) for i in range(1, 39)}
for idx, d in enumerate(h_slice):
    for n in d['numbers']:
        if n <= 38:
            bitstreams[n][idx] = 1

for n in range(1, 39):
    bh = bitstreams[n]
    if sum(bh) < 2:
        continue
    yf = fft(bh - np.mean(bh))
    xf = fftfreq(w, 1)
    idx_pos = np.where(xf > 0)
    pos_yf = np.abs(yf[idx_pos])
    pos_xf = xf[idx_pos]
    peak_idx = np.argmax(pos_yf)
    freq_val = pos_xf[peak_idx]
    if freq_val == 0: continue
    period = 1 / freq_val
    last_hit = np.where(bh == 1)[0][-1]
    gap = (w - 1) - last_hit
    f_score = 1.0 / (abs(gap - period) + 1.0)
    final_scores[n] = final_scores.get(n, 0) + f_score * 0.4

ranked_final = sorted(final_scores.items(), key=lambda x: -x[1])
top18 = [n for n, _ in ranked_final[:18]]
bet1 = sorted(top18[:6])
bet2 = sorted(top18[6:12])
bet3 = sorted(top18[12:18])
hits_total = len(set(top18) & actual)
print(f"  綜合Top 18: {top18}")
print(f"  注1: {bet1} → 命中={sorted(set(bet1) & actual)} ({len(set(bet1) & actual)}個)")
print(f"  注2: {bet2} → 命中={sorted(set(bet2) & actual)} ({len(set(bet2) & actual)}個)")
print(f"  注3: {bet3} → 命中={sorted(set(bet3) & actual)} ({len(set(bet3) & actual)}個)")
print(f"  合計命中: {hits_total}個")
print()
print("  各開獎號碼的綜合排名:")
rank_map = {n: i+1 for i, (n, _) in enumerate(ranked_final)}
for n in actual_sorted:
    r = rank_map.get(n, 99)
    s = final_scores.get(n, 0)
    in_bet = ""
    if r <= 6: in_bet = " [注1]"
    elif r <= 12: in_bet = " [注2]"
    elif r <= 18: in_bet = " [注3]"
    print(f"    號碼{n:02d}: 排名 #{r} (score={s:.3f}){in_bet}")

print()

# === Summary ===
print("=" * 70)
print("  方法對比摘要")
print("=" * 70)
methods = [
    ("Fourier Rhythm 2注", 2, "2 (10,35)"),
    ("Power Precision 3注", 2, "2 (10,35)"),
    ("冷號回歸 w=50", None, None),
    ("冷號回歸 w=100", None, None),
    ("偏差分析 w=50", None, None),
    ("偏差分析 w=100", None, None),
    ("馬可夫轉移", hits_markov, None),
    ("綜合評分 3注", hits_total, None),
]

# Recompute cold and deviation for summary
for window in [50, 100]:
    recent = hist[-window:]
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    all_nums = list(range(1, 39))
    all_nums.sort(key=lambda x: freq.get(x, 0))
    coldest_12 = set(all_nums[:12])
    print(f"  冷號w={window}: 12號中命中 {len(coldest_12 & actual)}個 → {sorted(coldest_12 & actual)}")

    expected = window * 6 / 38
    deviations = {n: freq.get(n, 0) - expected for n in range(1, 39)}
    sorted_dev = sorted(deviations.items(), key=lambda x: x[1])
    under_12 = set(n for n, _ in sorted_dev[:12])
    print(f"  偏差w={window}: 12號中命中 {len(under_12 & actual)}個 → {sorted(under_12 & actual)}")

print()
print(f"  Fourier Rhythm 2注: 12號中命中 2個 [10, 35]")
print(f"  Power Precision 3注: 18號中命中 2個 [10, 35]")
print(f"  馬可夫轉移: 12號中命中 {hits_markov}個")
print(f"  綜合評分 3注: 18號中命中 {hits_total}個")

print()
print("=== 關鍵發現 ===")
print("1. 號碼 10, 35 被 Fourier 正確排名 #1, #2 但同注，其餘4個號碼排名很低")
print(f"2. 號碼 4, 13, 24 在近100期屬於『冰冷』(低頻)，但冷號回歸策略有機會捕捉")
print(f"3. N-1/N-2 回聲為 0 — 這組號碼完全不含前兩期號碼")
print(f"4. 和值{actual_sum}極度正常(z≈0)，不具異常特徵")
print(f"5. 區間分布均勻(2-1-1-2)，奇偶3:3，大小3:3 — 非常標準")
