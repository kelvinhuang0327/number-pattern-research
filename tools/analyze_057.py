#!/usr/bin/env python3
"""
115000057 期檢討分析
開獎號碼: 04, 08, 12, 16, 17
"""
import sys, os, json
import numpy as np
from numpy.fft import fft, fftfreq
from collections import Counter
from itertools import combinations

project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
os.chdir(os.path.join(project_root, 'lottery_api'))
sys.path.insert(0, '.')
from database import DatabaseManager

db = DatabaseManager()
history_raw = db.get_all_draws('DAILY_539')
history = sorted(history_raw, key=lambda x: (x['date'], x['draw']))

ACTUAL = {4, 8, 12, 16, 17}
ACTUAL_LIST = sorted(ACTUAL)

# Find draw 115000057 specifically
target_draw = 115000057
prev_draw = 115000056
target_idx = None
for i, d in enumerate(history):
    if d['draw'] == target_draw:
        target_idx = i
        print(f"  Target: idx={i}, draw={d['draw']}, date={d['date']}, nums={d['numbers']}")
    elif d['draw'] == prev_draw:
        print(f"  Prev:   idx={i}, draw={d['draw']}, date={d['date']}, nums={d['numbers']}")

# Use history up to and including prev_draw (115000056) for prediction
# draw may be int or str
pred_history = []
for d in history:
    try:
        dnum = int(d['draw'])
    except:
        dnum = 0
    if dnum <= prev_draw:
        pred_history.append(d)

print(f"\nData for prediction: {len(pred_history)} draws")
print(f"Last draw used: {pred_history[-1]['draw']} - {pred_history[-1]['date']} - {pred_history[-1]['numbers']}")
print(f"2nd last: {pred_history[-2]['draw']} - {pred_history[-2]['date']} - {pred_history[-2]['numbers']}")
print(f"3rd last: {pred_history[-3]['draw']} - {pred_history[-3]['date']} - {pred_history[-3]['numbers']}")

print(f"\n{'='*70}")
print(f"第115000057期檢討分析")
print(f"開獎號碼: {', '.join(f'{n:02d}' for n in ACTUAL_LIST)}")
print(f"{'='*70}")

# ========== 1. Basic features ==========
print(f"\n{'='*70}")
print("一、開獎號碼基本特徵分析")
print(f"{'='*70}")

total_sum = sum(ACTUAL_LIST)
sums = [sum(d['numbers'][:5]) for d in pred_history[-1500:]]
avg_sum = np.mean(sums)
std_sum = np.std(sums)
print(f"Sum = {total_sum} (歷史均值={avg_sum:.1f}, 標準差={std_sum:.1f}, Z-score={(total_sum - avg_sum)/std_sum:.2f})")

z1 = [n for n in ACTUAL_LIST if n <= 13]
z2 = [n for n in ACTUAL_LIST if 14 <= n <= 26]
z3 = [n for n in ACTUAL_LIST if n >= 27]
print(f"Zone: Z1(1-13)={len(z1)}{z1}, Z2(14-26)={len(z2)}{z2}, Z3(27-39)={len(z3)}{z3}")

odds = [n for n in ACTUAL_LIST if n % 2 == 1]
evens = [n for n in ACTUAL_LIST if n % 2 == 0]
print(f"奇偶: {len(odds)}奇{len(evens)}偶")

consec = []
for i in range(len(ACTUAL_LIST)-1):
    if ACTUAL_LIST[i+1] - ACTUAL_LIST[i] == 1:
        consec.append((ACTUAL_LIST[i], ACTUAL_LIST[i+1]))
print(f"連號: {consec if consec else '無'}")

# Max number
print(f"最大號碼: {max(ACTUAL_LIST)} (全部 ≤ 17, 極端偏小)")

# Tail
tails = [n % 10 for n in ACTUAL_LIST]
print(f"尾數: {dict(Counter(tails))}")

# Previous draw overlap
prev = set(pred_history[-1]['numbers'])
kept = ACTUAL & prev
print(f"\n與上期(056: {sorted(prev)})保留: {sorted(kept) if kept else '無'} ({len(kept)}/5)")

prev2 = set(pred_history[-2]['numbers'])
kept2 = ACTUAL & prev2
print(f"與前期(055: {sorted(prev2)})保留: {sorted(kept2) if kept2 else '無'} ({len(kept2)}/5)")

prev3 = set(pred_history[-3]['numbers'])
kept3 = ACTUAL & prev3
print(f"與前前期(054: {sorted(prev3)})保留: {sorted(kept3) if kept3 else '無'} ({len(kept3)}/5)")

# Neighbor analysis
neighbors = set()
for n in prev:
    if n > 1: neighbors.add(n-1)
    if n < 39: neighbors.add(n+1)
neighbor_hits = ACTUAL & neighbors
print(f"\n上期鄰號(±1)池: {sorted(neighbors)}")
print(f"鄰號命中: {sorted(neighbor_hits) if neighbor_hits else '無'} ({len(neighbor_hits)}/5)")

# ========== 2. Prediction method comparison ==========
print(f"\n{'='*70}")
print("二、各預測方法結果比較")
print(f"{'='*70}")

os.chdir(project_root)
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'tools'))
from quick_predict import (
    _539_acb_bet, _539_markov_bet, _539_fourier_scores,
    _539_midfreq_bet, _539_lift_pair_bet, predict_539
)

# Individual methods
acb = _539_acb_bet(pred_history)
acb_hits = set(acb) & ACTUAL
print(f"\n1. ACB 異常捕捉: {acb} → 命中: {sorted(acb_hits)} ({len(acb_hits)}/5)")

midfreq = _539_midfreq_bet(pred_history)
midfreq_hits = set(midfreq) & ACTUAL
print(f"2. MidFreq 均值回歸: {midfreq} → 命中: {sorted(midfreq_hits)} ({len(midfreq_hits)}/5)")

markov = _539_markov_bet(pred_history)
markov_hits = set(markov) & ACTUAL
print(f"3. Markov 轉移: {markov} → 命中: {sorted(markov_hits)} ({len(markov_hits)}/5)")

fscores = _539_fourier_scores(pred_history, window=500)
f_ranked = sorted(fscores, key=lambda x: -fscores[x])
fourier_top5 = sorted(f_ranked[:5])
fourier_hits = set(fourier_top5) & ACTUAL
print(f"4. Fourier 週期 Top5: {fourier_top5} → 命中: {sorted(fourier_hits)} ({len(fourier_hits)}/5)")

lift = _539_lift_pair_bet(pred_history)
lift_hits = set(lift) & ACTUAL
print(f"5. Lift Pair 共現: {lift} → 命中: {sorted(lift_hits)} ({len(lift_hits)}/5)")

# Composite strategies
print(f"\n--- 組合策略 ---")
bets_2, name_2 = predict_539(pred_history, {}, 2)
all_2 = set()
for i, b in enumerate(bets_2):
    hits = set(b['numbers']) & ACTUAL
    all_2 |= set(b['numbers'])
    print(f"\n2注策略 注{i+1}: {b['numbers']} → 命中: {sorted(hits)} ({len(hits)}/5)")
all_2_hits = all_2 & ACTUAL
m2_2 = any(len(set(b['numbers']) & ACTUAL) >= 2 for b in bets_2)
m3_2 = any(len(set(b['numbers']) & ACTUAL) >= 3 for b in bets_2)
print(f"2注聯集命中: {sorted(all_2_hits)} ({len(all_2_hits)}/5) M2+:{'✅' if m2_2 else '❌'} M3+:{'✅' if m3_2 else '❌'}")

bets_3, name_3 = predict_539(pred_history, {}, 3)
all_3 = set()
for i, b in enumerate(bets_3):
    hits = set(b['numbers']) & ACTUAL
    all_3 |= set(b['numbers'])
    print(f"\n3注策略 注{i+1}: {b['numbers']} → 命中: {sorted(hits)} ({len(hits)}/5)")
all_3_hits = all_3 & ACTUAL
m2_3 = any(len(set(b['numbers']) & ACTUAL) >= 2 for b in bets_3)
m3_3 = any(len(set(b['numbers']) & ACTUAL) >= 3 for b in bets_3)
print(f"3注聯集命中: {sorted(all_3_hits)} ({len(all_3_hits)}/5) M2+:{'✅' if m2_3 else '❌'} M3+:{'✅' if m3_3 else '❌'}")

# ========== 3. Signal attribution ==========
print(f"\n{'='*70}")
print("三、各開獎號碼信號歸屬")
print(f"{'='*70}")

# Compute scores for all numbers
r100 = pred_history[-100:]
c100 = Counter()
for n in range(1, 40): c100[n] = 0
for d in r100:
    for n in d['numbers']: c100[n] += 1

ls100 = {}
for i, d in enumerate(r100):
    for n in d['numbers']: ls100[n] = i
cur100 = len(r100)
exp100 = len(r100) * 5 / 39

# Full gaps
last_seen_full = {}
for i, d in enumerate(pred_history):
    for n in d['numbers']: last_seen_full[n] = i
current_full = len(pred_history)
gaps = {n: current_full - last_seen_full.get(n, -1) for n in range(1, 40)}

# ACB scores
acb_scores = {}
g100 = {n: cur100 - ls100.get(n, -1) for n in range(1, 40)}
for n in range(1, 40):
    fd = exp100 - c100[n]
    gs = g100[n] / (cur100/2)
    bb = 1.2 if (n <= 5 or n >= 35) else 1.0
    mb = 1.1 if n % 3 == 0 else 1.0
    acb_scores[n] = (fd * 0.4 + gs * 0.6) * bb * mb
acb_ranked = sorted(acb_scores, key=lambda x: -acb_scores[x])
acb_rank = {n: i+1 for i, n in enumerate(acb_ranked)}

# Fourier ranks
f_rank = {n: i+1 for i, n in enumerate(f_ranked)}

# Markov scores
transitions = {}
r30 = pred_history[-30:]
for i in range(len(r30) - 1):
    for pn in r30[i]['numbers']:
        if pn > 39: continue
        if pn not in transitions: transitions[pn] = Counter()
        for nn in r30[i+1]['numbers']:
            if nn <= 39: transitions[pn][nn] += 1
prev_nums = pred_history[-1]['numbers']
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

# MidFreq
mf_dist = {n: abs(c100[n] - exp100) for n in range(1, 40)}
mf_ranked = sorted(mf_dist, key=lambda x: mf_dist[x])
mf_rank = {n: i+1 for i, n in enumerate(mf_ranked)}

print(f"\n{'号码':>4} | {'ACB':>6} | {'Fourier':>8} | {'Markov':>7} | {'MidFreq':>8} | {'freq100':>7} | {'gap':>4} | 信号归类")
print("-"*90)
for n in ACTUAL_LIST:
    sig = []
    if acb_rank[n] <= 5: sig.append(f"ACB(R{acb_rank[n]})")
    if f_rank[n] <= 10: sig.append(f"Fourier(R{f_rank[n]})")
    if mk_rank[n] <= 5: sig.append(f"Markov(R{mk_rank[n]})")
    if mf_rank[n] <= 10: sig.append(f"MidFreq(R{mf_rank[n]})")
    if c100[n] >= exp100 * 1.3: sig.append("Hot")
    if c100[n] <= exp100 * 0.7: sig.append("Cold")
    if gaps[n] >= 10: sig.append(f"HighGap({gaps[n]})")
    sig_str = ", ".join(sig) if sig else "无明确信号"
    print(f"  {n:02d}  | R{acb_rank[n]:>4} | R{f_rank[n]:>6} | R{mk_rank[n]:>5} | R{mf_rank[n]:>6} | {c100[n]:>6} | {gaps[n]:>3} | {sig_str}")

# ========== 4. Full rankings ==========
print(f"\n{'='*70}")
print("四、各方法 Top-15 排名")
print(f"{'='*70}")

print(f"\nACB Top-15:")
for i, n in enumerate(acb_ranked[:15]):
    marker = " ★" if n in ACTUAL else ""
    print(f"  R{i+1:>2}: {n:02d} (score={acb_scores[n]:.3f}){marker}")

print(f"\nFourier Top-15:")
for i, n in enumerate(f_ranked[:15]):
    marker = " ★" if n in ACTUAL else ""
    print(f"  R{i+1:>2}: {n:02d} (score={fscores[n]:.3f}){marker}")

print(f"\nMarkov Top-15:")
for i, n in enumerate(mk_ranked[:15]):
    marker = " ★" if n in ACTUAL else ""
    print(f"  R{i+1:>2}: {n:02d} (score={mk_scores.get(n, 0):.3f}){marker}")

print(f"\nMidFreq Top-15:")
for i, n in enumerate(mf_ranked[:15]):
    marker = " ★" if n in ACTUAL else ""
    print(f"  R{i+1:>2}: {n:02d} (dist={mf_dist[n]:.2f}, f100={c100[n]}){marker}")

# ========== 5. Special pattern: all Z1 ==========
print(f"\n{'='*70}")
print("五、極端模式分析: 全部5碼 ≤ 17 (Z1集中)")
print(f"{'='*70}")

# How often do all 5 numbers fall in 1-17?
all_low_count = 0
z1_heavy_count = 0  # >=4 in Z1
for d in pred_history[-1500:]:
    nums = sorted([n for n in d['numbers'] if n <= 39])
    if all(n <= 17 for n in nums):
        all_low_count += 1
    if sum(1 for n in nums if n <= 13) >= 4:
        z1_heavy_count += 1

print(f"近1500期，全5碼 ≤ 17: {all_low_count} 期 ({all_low_count/1500*100:.2f}%)")
print(f"近1500期，Z1(1-13) ≥ 4碼: {z1_heavy_count} 期 ({z1_heavy_count/1500*100:.2f}%)")

# Theoretical probability: C(17,5)/C(39,5)
from math import comb
p_all_17 = comb(17, 5) / comb(39, 5)
print(f"理論概率 (全5碼 ≤ 17): C(17,5)/C(39,5) = {p_all_17*100:.2f}%")
# Sum distribution for these
print(f"本期 Sum={total_sum}, 全在前半 (≤17) 的最小Sum = 1+2+3+4+5=15, 最大 = 13+14+15+16+17=75")

# ========== 6. Zone bias analysis ==========
print(f"\n{'='*70}")
print("六、Zone偏重歷史統計")
print(f"{'='*70}")

zone_counts = []
for d in pred_history[-1500:]:
    nums = [n for n in d['numbers'] if n <= 39]
    z1c = sum(1 for n in nums if n <= 13)
    z2c = sum(1 for n in nums if 14 <= n <= 26)
    z3c = sum(1 for n in nums if n >= 27)
    zone_counts.append((z1c, z2c, z3c))

# Z1 >=3 
z1_3plus = sum(1 for z in zone_counts if z[0] >= 3)
z1_4plus = sum(1 for z in zone_counts if z[0] >= 4)
z1_5 = sum(1 for z in zone_counts if z[0] >= 5)
print(f"Z1 ≥ 3碼: {z1_3plus}/1500 ({z1_3plus/1500*100:.1f}%)")
print(f"Z1 ≥ 4碼: {z1_4plus}/1500 ({z1_4plus/1500*100:.1f}%)")
print(f"Z1 = 5碼: {z1_5}/1500 ({z1_5/1500*100:.2f}%)")
print(f"本期 Z1=3, Z2=2, Z3=0 → Z3完全空缺")

z3_zero = sum(1 for z in zone_counts if z[2] == 0)
print(f"Z3 = 0碼: {z3_zero}/1500 ({z3_zero/1500*100:.1f}%)")

# ========== 7. Consecutive number analysis ==========
print(f"\n{'='*70}")
print("七、連號模式分析")
print(f"{'='*70}")

consec_count = 0
consec_2plus = 0
for d in pred_history[-1500:]:
    nums = sorted([n for n in d['numbers'] if n <= 39])
    pairs = 0
    for i in range(len(nums)-1):
        if nums[i+1] - nums[i] == 1:
            pairs += 1
    if pairs >= 1: consec_count += 1
    if pairs >= 2: consec_2plus += 1

print(f"含連號(≥1對): {consec_count}/1500 ({consec_count/1500*100:.1f}%)")
print(f"含2+對連號: {consec_2plus}/1500 ({consec_2plus/1500*100:.1f}%)")
print(f"本期連號: (16,17) — 1對")

# ========== 8. Short/Mid/Long freq ==========
print(f"\n{'='*70}")
print("八、長中短期頻率特徵")
print(f"{'='*70}")

for wname, wsize in [('短期20期', 20), ('中期50期', 50), ('中長期100期', 100), ('長期500期', 500)]:
    wh = pred_history[-wsize:]
    wf = Counter()
    for d in wh:
        for n in d['numbers']:
            if n <= 39: wf[n] += 1
    wexp = len(wh) * 5 / 39
    print(f"\n  {wname} (期望={wexp:.1f}):")
    for n in ACTUAL_LIST:
        ratio = wf[n] / wexp if wexp > 0 else 0
        status = "Hot" if ratio > 1.3 else ("Cold" if ratio < 0.7 else "Warm")
        print(f"    {n:02d}: {wf[n]:>3}次 (ratio={ratio:.2f} {status})")

# ========== 9. Echo (Lag) analysis ==========
print(f"\n{'='*70}")
print("九、回聲分析 (Lag-1, Lag-2, Lag-3)")
print(f"{'='*70}")

for lag in [1, 2, 3]:
    if len(pred_history) > lag:
        lag_idx = -lag
        lag_nums = set(pred_history[lag_idx]['numbers'])
        lag_hits = ACTUAL & lag_nums
        draw_num = pred_history[lag_idx]['draw']
        print(f"  Lag-{lag} (期{draw_num}): {sorted(lag_nums)} → 命中: {sorted(lag_hits)} ({len(lag_hits)}/5)")

# ========== 10. Sum trend ==========
print(f"\n{'='*70}")
print("十、近10期Sum趨勢")
print(f"{'='*70}")

for d in pred_history[-10:]:
    s = sum(d['numbers'][:5])
    print(f"  {d['draw']}: {d['numbers']} → Sum={s}")
print(f"  057(本期): {ACTUAL_LIST} → Sum={total_sum} (最低!)")

# ========== 11. All combos ==========
print(f"\n{'='*70}")
print("十一、所有2注/3注組合模擬")
print(f"{'='*70}")

all_methods = {
    'ACB': acb,
    'MidFreq': midfreq,
    'Markov': markov,
    'Fourier': fourier_top5,
    'LiftPair': lift,
}

methods_list = list(all_methods.keys())
print("\n--- 2注組合 ---")
for i in range(len(methods_list)):
    for j in range(i+1, len(methods_list)):
        n1, n2 = methods_list[i], methods_list[j]
        b1, b2 = set(all_methods[n1]), set(all_methods[n2])
        union_h = len((b1 | b2) & ACTUAL)
        h1 = len(b1 & ACTUAL)
        h2 = len(b2 & ACTUAL)
        m2 = h1 >= 2 or h2 >= 2
        print(f"  {n1}+{n2}: 各注[{h1},{h2}], 聯集{union_h}/5, M2+={'✅' if m2 else '❌'}")

print("\n--- 3注組合 ---")
for i in range(len(methods_list)):
    for j in range(i+1, len(methods_list)):
        for k in range(j+1, len(methods_list)):
            n1, n2, n3 = methods_list[i], methods_list[j], methods_list[k]
            b1, b2, b3 = set(all_methods[n1]), set(all_methods[n2]), set(all_methods[n3])
            union_h = len((b1 | b2 | b3) & ACTUAL)
            h1 = len(b1 & ACTUAL)
            h2 = len(b2 & ACTUAL)
            h3 = len(b3 & ACTUAL)
            m2 = h1 >= 2 or h2 >= 2 or h3 >= 2
            m3 = h1 >= 3 or h2 >= 3 or h3 >= 3
            print(f"  {n1}+{n2}+{n3}: 各注[{h1},{h2},{h3}], 聯集{union_h}/5, M2+={'✅' if m2 else '❌'} M3+={'✅' if m3 else '❌'}")

# ========== 12. Detailed "why missed" ==========
print(f"\n{'='*70}")
print("十二、各號碼 '為何沒被選中' 詳細分析")
print(f"{'='*70}")

for n in ACTUAL_LIST:
    print(f"\n  --- {n:02d} ---")
    print(f"  ACB R{acb_rank[n]}, Fourier R{f_rank[n]}, Markov R{mk_rank[n]}, MidFreq R{mf_rank[n]}")
    print(f"  freq100={c100[n]} (exp={exp100:.1f}), gap={gaps[n]}")
    
    # ACB reason
    fd = exp100 - c100[n]
    gs = g100[n] / (cur100/2)
    print(f"  ACB detail: freq_deficit={fd:.2f}, gap_score={gs:.2f}, raw={(fd*0.4+gs*0.6):.2f}")
    
    if acb_rank[n] <= 5:
        print(f"  → ACB 已選中 ✅")
    elif acb_rank[n] <= 10:
        print(f"  → ACB 差 {acb_rank[n]-5} 名 (接近)")
    else:
        print(f"  → ACB 排名低 ({acb_rank[n]}/39)")
    
    if f_rank[n] <= 5:
        print(f"  → Fourier 已選中 ✅")
    elif f_rank[n] <= 15:
        print(f"  → Fourier 接近 (R{f_rank[n]}, 3注取R11-15)")
    else:
        print(f"  → Fourier 排名低 ({f_rank[n]}/39)")
    
    if mk_rank[n] <= 5:
        print(f"  → Markov 已選中 ✅")
    else:
        print(f"  → Markov R{mk_rank[n]}: 上期號碼轉移到{n:02d}的歷史概率低")

# ========== 13. Sum-low extreme analysis ==========
print(f"\n{'='*70}")
print("十三、極低Sum期 (≤60) 的歷史回溯")
print(f"{'='*70}")

low_sum_draws = []
for i, d in enumerate(pred_history[-1500:]):
    s = sum(d['numbers'][:5])
    if s <= 60:
        prev_d = pred_history[len(pred_history)-1500+i-1] if i > 0 else None
        low_sum_draws.append((d, s, prev_d))

print(f"近1500期 Sum ≤ 60 的期數: {len(low_sum_draws)}")
print(f"本期 Sum = {total_sum}")
for d, s, prev_d in low_sum_draws[-10:]:
    p_nums = sorted(prev_d['numbers'][:5]) if prev_d else []
    print(f"  {d['draw']}: {d['numbers']} Sum={s}, 前期: {p_nums}")

# Is there any signal before low-sum periods?
print(f"\n低Sum期前一期的特徵:")
prev_sums_before_low = []
for d, s, prev_d in low_sum_draws:
    if prev_d:
        ps = sum(prev_d['numbers'][:5])
        prev_sums_before_low.append(ps)
if prev_sums_before_low:
    print(f"  前一期Sum均值: {np.mean(prev_sums_before_low):.1f} (全體均值={avg_sum:.1f})")
    print(f"  前一期Sum中位數: {np.median(prev_sums_before_low):.1f}")

# ========== 14. Even-number cluster analysis ==========
print(f"\n{'='*70}")
print("十四、偶數重壓分析 (本期4偶1奇)")
print(f"{'='*70}")

even_heavy_count = 0
for d in pred_history[-1500:]:
    nums = [n for n in d['numbers'] if n <= 39]
    evens_cnt = sum(1 for n in nums if n % 2 == 0)
    if evens_cnt >= 4:
        even_heavy_count += 1
print(f"近1500期 偶數 ≥ 4碼: {even_heavy_count}/1500 ({even_heavy_count/1500*100:.1f}%)")
print(f"本期: 4偶(04,08,12,16) 1奇(17)")

# ========== 15. Interval pattern ==========
print(f"\n{'='*70}")
print("十五、號碼間距分析")
print(f"{'='*70}")

intervals = [ACTUAL_LIST[i+1] - ACTUAL_LIST[i] for i in range(len(ACTUAL_LIST)-1)]
print(f"號碼: {ACTUAL_LIST}")
print(f"間距: {intervals}")
print(f"等差特徵: 04→08→12→16 (間距4,4,4) + 17 (間距1)")

# Check arithmetic progression frequency
arith_count = 0
for d in pred_history[-1500:]:
    nums = sorted([n for n in d['numbers'] if n <= 39])
    # Check for 3+ consecutive same-interval
    for i in range(len(nums)-2):
        if nums[i+1] - nums[i] == nums[i+2] - nums[i+1]:
            arith_count += 1
            break

print(f"含等差子序列(≥3碼同間距): {arith_count}/1500 ({arith_count/1500*100:.1f}%)")
print(f"本期: 04,08,12,16 構成間距=4的4碼等差數列 (極罕見!)")

# 4-term arithmetic sequence frequency
arith4_count = 0
for d in pred_history[-1500:]:
    nums = sorted([n for n in d['numbers'] if n <= 39])
    for i in range(len(nums)-3):
        d1 = nums[i+1] - nums[i]
        d2 = nums[i+2] - nums[i+1]
        d3 = nums[i+3] - nums[i+2]
        if d1 == d2 == d3 and d1 > 0:
            arith4_count += 1
            break
print(f"含4碼等差數列: {arith4_count}/1500 ({arith4_count/1500*100:.2f}%)")

# Multiples of 4
mult4 = [n for n in ACTUAL_LIST if n % 4 == 0]
print(f"\n4的倍數: {mult4} ({len(mult4)} 個)")
print(f"正整數1-39中4的倍數: {list(range(4, 40, 4))} (共9個)")

print(f"\n{'='*70}")
print("分析完畢")
print(f"{'='*70}")
