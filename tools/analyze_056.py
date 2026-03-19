#!/usr/bin/env python3
"""
第115000056期檢討分析腳本
開獎號碼: 02, 19, 21, 32, 35
"""
import sys, os, json
import numpy as np
from numpy.fft import fft, fftfreq
from collections import Counter
from itertools import combinations

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lottery_api'))
sys.path.insert(0, '.')
from database import DatabaseManager

# Load data
db = DatabaseManager()
history_raw = db.get_all_draws('DAILY_539')
history = sorted(history_raw, key=lambda x: (x['date'], x['draw']))

ACTUAL = {2, 19, 21, 32, 35}
ACTUAL_LIST = sorted(ACTUAL)
print(f"="*70)
print(f"第115000056期檢討分析")
print(f"開獎號碼: {', '.join(f'{n:02d}' for n in ACTUAL_LIST)}")
print(f"="*70)
print(f"\n上期 (055): {history[-1]['numbers']}")
print(f"前期 (054): {history[-2]['numbers']}")
print(f"前前期 (053): {history[-3]['numbers']}")
print(f"歷史數據量: {len(history)} 期")

# ======== 基本分析 ========
print(f"\n{'='*70}")
print("一、開獎號碼基本特徵分析")
print(f"{'='*70}")

# Sum
total_sum = sum(ACTUAL_LIST)
print(f"Sum = {total_sum}")
# 歷史 Sum 統計
sums = [sum(d['numbers']) for d in history[-1500:]]
avg_sum = np.mean(sums)
std_sum = np.std(sums)
print(f"近1500期 Sum 均值 = {avg_sum:.1f}, 標準差 = {std_sum:.1f}")
print(f"Sum Z-score = {(total_sum - avg_sum) / std_sum:.2f}")

# Zone distribution
z1 = [n for n in ACTUAL_LIST if n <= 13]
z2 = [n for n in ACTUAL_LIST if 14 <= n <= 26]
z3 = [n for n in ACTUAL_LIST if n >= 27]
print(f"Zone分佈: Z1(1-13)={len(z1)}{z1}, Z2(14-26)={len(z2)}{z2}, Z3(27-39)={len(z3)}{z3}")

# 奇偶
odds = [n for n in ACTUAL_LIST if n % 2 == 1]
evens = [n for n in ACTUAL_LIST if n % 2 == 0]
print(f"奇偶: {len(odds)}奇{len(evens)}偶 ({odds} | {evens})")

# 連號
consec = []
for i in range(len(ACTUAL_LIST)-1):
    if ACTUAL_LIST[i+1] - ACTUAL_LIST[i] == 1:
        consec.append((ACTUAL_LIST[i], ACTUAL_LIST[i+1]))
print(f"連號: {consec if consec else '無'}")

# 尾數
tails = [n % 10 for n in ACTUAL_LIST]
tail_counts = Counter(tails)
print(f"尾數分佈: {dict(tail_counts)}")
dup_tails = {k: v for k, v in tail_counts.items() if v > 1}
if dup_tails:
    print(f"  重複尾數: {dup_tails}")

# 與上期保留
prev = set(history[-1]['numbers'])
kept = ACTUAL & prev
print(f"\n與上期(055: {sorted(prev)})保留: {sorted(kept) if kept else '無'} ({len(kept)}/5)")

prev2 = set(history[-2]['numbers'])
kept2 = ACTUAL & prev2
print(f"與前期(054: {sorted(prev2)})保留: {sorted(kept2) if kept2 else '無'} ({len(kept2)}/5)")

prev3 = set(history[-3]['numbers'])
kept3 = ACTUAL & prev3
print(f"與前前期(053: {sorted(prev3)})保留: {sorted(kept3) if kept3 else '無'} ({len(kept3)}/5)")

# 鄰號分析 (與上期 ±1)
neighbors = set()
for n in prev:
    if n > 1: neighbors.add(n-1)
    if n < 39: neighbors.add(n+1)
neighbor_hits = ACTUAL & neighbors
print(f"\n上期鄰號(±1)池: {sorted(neighbors)}")
print(f"鄰號命中: {sorted(neighbor_hits) if neighbor_hits else '無'} ({len(neighbor_hits)}/5)")

# ======== 各方法預測結果 ========
print(f"\n{'='*70}")
print("二、各預測方法結果比較")
print(f"{'='*70}")

project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
os.chdir(project_root)
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'tools'))
from quick_predict import (
    _539_acb_bet, _539_markov_bet, _539_fourier_scores,
    _539_midfreq_bet, _539_lift_pair_bet, predict_539
)

# Method 1: ACB (1注)
acb = _539_acb_bet(history)
acb_hits = set(acb) & ACTUAL
print(f"\n1. ACB 異常捕捉 (1注)")
print(f"   預測: {acb}")
print(f"   命中: {sorted(acb_hits)} ({len(acb_hits)}/5)")

# Method 2: MidFreq (單獨)
midfreq = _539_midfreq_bet(history)
midfreq_hits = set(midfreq) & ACTUAL
print(f"\n2. MidFreq 均值回歸 (單獨)")
print(f"   預測: {midfreq}")
print(f"   命中: {sorted(midfreq_hits)} ({len(midfreq_hits)}/5)")

# Method 3: Markov (單獨)
markov = _539_markov_bet(history)
markov_hits = set(markov) & ACTUAL
print(f"\n3. Markov 轉移 (單獨)")
print(f"   預測: {markov}")
print(f"   命中: {sorted(markov_hits)} ({len(markov_hits)}/5)")

# Method 4: Fourier (Top5)
fscores = _539_fourier_scores(history, window=500)
f_ranked = sorted(fscores, key=lambda x: -fscores[x])
fourier_top5 = sorted(f_ranked[:5])
fourier_hits = set(fourier_top5) & ACTUAL
print(f"\n4. Fourier 週期 (Top5)")
print(f"   預測: {fourier_top5}")
print(f"   命中: {sorted(fourier_hits)} ({len(fourier_hits)}/5)")

# Method 5: Lift Pair
lift = _539_lift_pair_bet(history)
lift_hits = set(lift) & ACTUAL
print(f"\n5. Lift Pair 共現 (1注)")
print(f"   預測: {lift}")
print(f"   命中: {sorted(lift_hits)} ({len(lift_hits)}/5)")

# Composite strategies
print(f"\n--- 組合策略 ---")

# 2注: MidFreq + ACB
bets_2, name_2 = predict_539(history, {}, 2)
all_2 = set()
for i, b in enumerate(bets_2):
    hits = set(b['numbers']) & ACTUAL
    all_2 |= set(b['numbers'])
    print(f"\n6a. 2注策略 注{i+1}: {b['numbers']}")
    print(f"    命中: {sorted(hits)} ({len(hits)}/5)")
all_2_hits = all_2 & ACTUAL
print(f"   2注聯集覆蓋: {sorted(all_2)}")
print(f"   2注聯集命中: {sorted(all_2_hits)} ({len(all_2_hits)}/5)")
m2_any = any(len(set(b['numbers']) & ACTUAL) >= 2 for b in bets_2)
m3_any = any(len(set(b['numbers']) & ACTUAL) >= 3 for b in bets_2)
print(f"   M2+: {'✅' if m2_any else '❌'}  M3+: {'✅' if m3_any else '❌'}")

# 3注: ACB + Markov + Fourier
bets_3, name_3 = predict_539(history, {}, 3)
all_3 = set()
for i, b in enumerate(bets_3):
    hits = set(b['numbers']) & ACTUAL
    all_3 |= set(b['numbers'])
    print(f"\n6b. 3注策略 注{i+1}: {b['numbers']}")
    print(f"    命中: {sorted(hits)} ({len(hits)}/5)")
all_3_hits = all_3 & ACTUAL
print(f"   3注聯集覆蓋: {sorted(all_3)}")
print(f"   3注聯集命中: {sorted(all_3_hits)} ({len(all_3_hits)}/5)")
m2_any_3 = any(len(set(b['numbers']) & ACTUAL) >= 2 for b in bets_3)
m3_any_3 = any(len(set(b['numbers']) & ACTUAL) >= 3 for b in bets_3)
print(f"   M2+: {'✅' if m2_any_3 else '❌'}  M3+: {'✅' if m3_any_3 else '❌'}")

# ======== 號碼信號分析 ========
print(f"\n{'='*70}")
print("三、各開獎號碼的信號歸屬分析")
print(f"{'='*70}")

# 計算每個開獎號碼在各信號源的排名
recent100 = history[-100:]
recent500 = history[-500:]
freq100 = Counter()
for d in recent100:
    for n in d['numbers']:
        if n <= 39:
            freq100[n] += 1

freq500 = Counter()
for d in recent500:
    for n in d['numbers']:
        if n <= 39:
            freq500[n] += 1

# Gap
last_seen = {}
for i, d in enumerate(history):
    for n in d['numbers']:
        last_seen[n] = i
current_idx = len(history)
gaps = {n: current_idx - last_seen.get(n, -1) for n in range(1, 40)}

expected100 = len(recent100) * 5 / 39
expected500 = len(recent500) * 5 / 39

# ACB scores
acb_scores = {}
r100 = history[-100:]
c100 = Counter()
for n in range(1, 40): c100[n] = 0
for d in r100:
    for n in d['numbers']: c100[n] += 1
ls100 = {}
for i, d in enumerate(r100):
    for n in d['numbers']: ls100[n] = i
cur100 = len(r100)
g100 = {n: cur100 - ls100.get(n, -1) for n in range(1, 40)}
exp100 = len(r100) * 5 / 39
for n in range(1, 40):
    fd = exp100 - c100[n]
    gs = g100[n] / (len(r100)/2)
    bb = 1.2 if (n <= 5 or n >= 35) else 1.0
    mb = 1.1 if n % 3 == 0 else 1.0
    acb_scores[n] = (fd * 0.4 + gs * 0.6) * bb * mb

acb_ranked = sorted(acb_scores, key=lambda x: -acb_scores[x])
acb_rank = {n: i+1 for i, n in enumerate(acb_ranked)}

# Fourier ranks
f_rank = {n: i+1 for i, n in enumerate(f_ranked)}

# Markov scores
from tools.quick_predict import _539_markov_bet
# Get Markov transition scores
transitions = {}
r30 = history[-30:]
for i in range(len(r30) - 1):
    for pn in r30[i]['numbers']:
        if pn > 39: continue
        if pn not in transitions:
            transitions[pn] = Counter()
        for nn in r30[i+1]['numbers']:
            if nn <= 39:
                transitions[pn][nn] += 1
prev_nums = history[-1]['numbers']
mk_scores = Counter()
for pn in prev_nums:
    if pn > 39: continue
    trans = transitions.get(pn, Counter())
    total = sum(trans.values())
    if total > 0:
        for n, cnt in trans.items():
            mk_scores[n] += cnt / total
mk_ranked = sorted(range(1, 40), key=lambda x: -mk_scores.get(x, 0))
mk_rank = {n: i+1 for i, n in enumerate(mk_ranked)}

# MidFreq rank (distance to expected)
mf_dist = {n: abs(c100[n] - exp100) for n in range(1, 40)}
mf_ranked = sorted(mf_dist, key=lambda x: mf_dist[x])
mf_rank = {n: i+1 for i, n in enumerate(mf_ranked)}

print(f"\n{'號碼':>4} | {'Fourier':>8} | {'ACB':>5} | {'Markov':>7} | {'MidFreq':>8} | {'freq100':>8} | {'freq500':>8} | {'Gap':>4} | 信號歸類")
print("-" * 90)
for n in ACTUAL_LIST:
    sig = []
    if f_rank[n] <= 10: sig.append(f"Fourier(rank{f_rank[n]})")
    if acb_rank[n] <= 10: sig.append(f"ACB(rank{acb_rank[n]})")
    if mk_rank[n] <= 10: sig.append(f"Markov(rank{mk_rank[n]})")
    if mf_rank[n] <= 10: sig.append(f"MidFreq(rank{mf_rank[n]})")
    if freq100[n] >= exp100 * 1.3: sig.append("Hot")
    if freq100[n] <= exp100 * 0.7: sig.append("Cold")
    if gaps[n] >= 10: sig.append(f"HighGap({gaps[n]})")
    sig_str = ", ".join(sig) if sig else "無明確信號"
    print(f"  {n:02d}  | rank{f_rank[n]:>3} | rank{acb_rank[n]:>2} | rank{mk_rank[n]:>3}  | rank{mf_rank[n]:>4}  | {freq100[n]:>7} | {freq500[n]:>7} | {gaps[n]:>3} | {sig_str}")

# ======== 進階分析 ========
print(f"\n{'='*70}")
print("四、各方法完整排名分析 (開獎號碼在各方法中的排名)")
print(f"{'='*70}")

# 顯示各方法Top10
print(f"\nACB Top-15 排名:")
for i, n in enumerate(acb_ranked[:15]):
    marker = " ★" if n in ACTUAL else ""
    print(f"  rank{i+1:>2}: {n:02d} (score={acb_scores[n]:.3f}){marker}")

print(f"\nFourier Top-15 排名:")
for i, n in enumerate(f_ranked[:15]):
    marker = " ★" if n in ACTUAL else ""
    print(f"  rank{i+1:>2}: {n:02d} (score={fscores[n]:.3f}){marker}")

print(f"\nMarkov Top-15 排名:")
for i, n in enumerate(mk_ranked[:15]):
    marker = " ★" if n in ACTUAL else ""
    print(f"  rank{i+1:>2}: {n:02d} (score={mk_scores.get(n, 0):.3f}){marker}")

print(f"\nMidFreq Top-15 排名 (距離期望值):")
for i, n in enumerate(mf_ranked[:15]):
    marker = " ★" if n in ACTUAL else ""
    print(f"  rank{i+1:>2}: {n:02d} (距期望={mf_dist[n]:.2f}, freq100={c100[n]}){marker}")

# ======== 055→056 轉移分析 ========
print(f"\n{'='*70}")
print("五、055→056 轉移分析")
print(f"{'='*70}")

prev_055 = history[-1]['numbers']
print(f"055期號碼: {prev_055}")
print(f"056期號碼: {ACTUAL_LIST}")

for pn in prev_055:
    trans = transitions.get(pn, Counter())
    total_trans = sum(trans.values())
    if total_trans > 0:
        top_trans = trans.most_common(5)
        actual_in_trans = [(n, cnt) for n, cnt in trans.items() if n in ACTUAL]
        print(f"\n  {pn:02d} → Top5轉移: {[(n, f'{cnt/total_trans:.2f}') for n, cnt in top_trans]}")
        if actual_in_trans:
            print(f"       命中號碼在轉移矩陣: {[(n, f'{cnt}/{total_trans}={cnt/total_trans:.2f}') for n, cnt in actual_in_trans]}")
        else:
            print(f"       命中號碼在轉移矩陣: 無")

# ======== 歷史模式匹配 ========
print(f"\n{'='*70}")
print("六、歷史模式分析 (近期號碼出現趨勢)")
print(f"{'='*70}")

# 每個開獎號碼近20期出現狀況
for n in ACTUAL_LIST:
    appearances = []
    for i, d in enumerate(history[-20:]):
        if n in d['numbers']:
            appearances.append(len(history) - 20 + i)
    recent_count = sum(1 for d in history[-20:] if n in d['numbers'])
    recent_gap = gaps[n]
    print(f"  {n:02d}: 近20期出現{recent_count}次, 當前gap={recent_gap}")

# ======== 覆蓋率及缺失分析 ========
print(f"\n{'='*70}")
print("七、為何命中率低 — 結構性分析")
print(f"{'='*70}")

# 計算各方法聯集vs實際
all_predicted = set()
all_methods = {
    'ACB': set(acb),
    'MidFreq': set(midfreq),
    'Markov': set(markov),
    'Fourier Top5': set(fourier_top5),
    'LiftPair': set(lift),
}
for name, nums in all_methods.items():
    hits = nums & ACTUAL
    all_predicted |= nums
    print(f"  {name:15s}: 預測{sorted(nums)}, 命中{len(hits)}: {sorted(hits)}")

union_hits = all_predicted & ACTUAL
print(f"\n  所有方法聯集 ({len(all_predicted)}碼): {sorted(all_predicted)}")
print(f"  聯集命中: {sorted(union_hits)} ({len(union_hits)}/5)")
missed = ACTUAL - all_predicted
print(f"  完全未被任何方法選中: {sorted(missed)}")

# ======== 可能改善方向分析 ========
print(f"\n{'='*70}")
print("八、各號碼 '為何沒被選中' 分析")
print(f"{'='*70}")

for n in ACTUAL_LIST:
    print(f"\n  --- {n:02d} ---")
    print(f"  ACB rank={acb_rank[n]}, Fourier rank={f_rank[n]}, Markov rank={mk_rank[n]}, MidFreq rank={mf_rank[n]}")
    print(f"  freq100={c100[n]} (期望={exp100:.1f}), gap={gaps[n]}")
    
    # 人格化分析
    if acb_rank[n] <= 5:
        print(f"  → ACB 已選中此號碼 ✅")
    elif acb_rank[n] <= 10:
        print(f"  → ACB 差{acb_rank[n]-5}名即被選 (排名{acb_rank[n]}, 門檻5)")
    else:
        deficit = exp100 - c100[n]
        gap_val = g100[n] / (len(r100)/2)
        print(f"  → ACB 排名過低: freq_deficit={deficit:.2f}, gap_score={gap_val:.2f}")
        
    if f_rank[n] <= 5:
        print(f"  → Fourier 已選中此號碼 ✅")
    elif f_rank[n] <= 15:
        print(f"  → Fourier 接近入選 (排名{f_rank[n]}, 3注正交中第3注取rank11-15)")
    else:
        print(f"  → Fourier 排名過低 ({f_rank[n]}/39)")

    if mk_rank[n] <= 5:
        print(f"  → Markov 已選中此號碼 ✅")
    elif mk_rank[n] <= 10:
        print(f"  → Markov 差{mk_rank[n]-5}名 (排名{mk_rank[n]})")
    else:
        print(f"  → Markov 排名過低 ({mk_rank[n]}/39): 055期號碼不常轉移到{n:02d}")

# ====== 長短期頻率特徵 ======
print(f"\n{'='*70}")
print("九、長中短期頻率特徵分析")
print(f"{'='*70}")

for window_name, window_size in [('短期20期', 20), ('中期50期', 50), ('中長期100期', 100), ('長期500期', 500)]:
    w_hist = history[-window_size:]
    w_freq = Counter()
    for d in w_hist:
        for n in d['numbers']:
            if n <= 39: w_freq[n] += 1
    w_exp = len(w_hist) * 5 / 39
    print(f"\n  {window_name} (期望={w_exp:.1f}):")
    for n in ACTUAL_LIST:
        ratio = w_freq[n] / w_exp if w_exp > 0 else 0
        status = "Hot" if ratio > 1.3 else ("Cold" if ratio < 0.7 else "Warm")
        print(f"    {n:02d}: {w_freq[n]:>3}次 (ratio={ratio:.2f} {status})")

# ====== 額外研究: 回聲分析 (Lag-2) ======
print(f"\n{'='*70}")
print("十、回聲分析 (Lag-1, Lag-2, Lag-3)")
print(f"{'='*70}")

for lag in [1, 2, 3]:
    if len(history) > lag:
        lag_nums = set(history[-lag]['numbers'])
        lag_hits = ACTUAL & lag_nums
        print(f"  Lag-{lag} (期{55-lag+1}): {sorted(lag_nums)}, 命中: {sorted(lag_hits)} ({len(lag_hits)}/5)")

# ====== 3注/2注場景模擬 ======
print(f"\n{'='*70}")
print("十一、其他策略組合模擬")
print(f"{'='*70}")

# 嘗試不同排列組合
combos = [
    ("ACB+MidFreq+Fourier", [acb, midfreq, fourier_top5]),
    ("ACB+Markov+MidFreq", [acb, markov, midfreq]),
    ("MidFreq+Markov+Fourier", [midfreq, markov, fourier_top5]),
    ("ACB+LiftPair+Fourier", [acb, lift, fourier_top5]),
    ("ACB+MidFreq (2注)", [acb, midfreq]),
    ("ACB+Fourier (2注)", [acb, fourier_top5]),
    ("ACB+Markov (2注)", [acb, markov]),
    ("MidFreq+Fourier (2注)", [midfreq, fourier_top5]),
    ("MidFreq+Markov (2注)", [midfreq, markov]),
    ("Markov+Fourier (2注)", [markov, fourier_top5]),
]

for name, bets_list in combos:
    union = set()
    per_bet_hits = []
    for b in bets_list:
        union |= set(b)
        per_bet_hits.append(len(set(b) & ACTUAL))
    u_hits = len(union & ACTUAL)
    m2 = any(h >= 2 for h in per_bet_hits)
    m3 = any(h >= 3 for h in per_bet_hits)
    print(f"  {name:30s}: 聯集{u_hits}/5, 各注{per_bet_hits}, M2+={'✅' if m2 else '❌'} M3+={'✅' if m3 else '❌'}")

# ====== F4Cold 舊策略 ======
print(f"\n--- F4Cold 舊生產策略模擬 ---")
# F4Cold: Fourier Top5 + Fourier 6-10 + Cold Top5 + Cold 6-10 + ...
f_top10 = f_ranked[:10]
f_bet1 = sorted(f_ranked[:5])
f_bet2 = sorted(f_ranked[5:10])

# Cold 注
cold_sorted = sorted(range(1, 40), key=lambda x: c100.get(x, 0))
cold_excl = set(f_top10)
cold_bet = sorted([n for n in cold_sorted if n not in cold_excl][:5])

f4cold_bets = [f_bet1, f_bet2, cold_bet]
for i, b in enumerate(f4cold_bets):
    hits = set(b) & ACTUAL
    print(f"  F4Cold 注{i+1}: {b}, 命中: {sorted(hits)} ({len(hits)}/5)")

f4cold_union = set(f_bet1) | set(f_bet2) | set(cold_bet)
f4cold_hits = f4cold_union & ACTUAL
print(f"  F4Cold 聯集命中: {sorted(f4cold_hits)} ({len(f4cold_hits)}/5)")

print(f"\n{'='*70}")
print("分析完畢")
print(f"{'='*70}")
