#!/usr/bin/env python3
"""
威力彩 P18 檢討分析腳本
第115000018期 開獎: [07, 09, 11, 23, 25, 29] 特別號: 05
"""
import sys, os, numpy as np
from collections import Counter
from numpy.fft import fft, fftfreq
from itertools import combinations

sys.path.insert(0, '.')
sys.path.insert(0, 'lottery_api')
from database import DatabaseManager

db_path = os.path.join('lottery_api', 'data', 'lottery_v2.db')
db = DatabaseManager(db_path)
draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
print(f"Total draws: {len(draws)}, last: {draws[-1]['draw']}")

# ======== Actual P18 result ========
actual = [7, 9, 11, 23, 25, 29]
actual_special = 5
actual_sum = sum(actual)
print(f"\n{'='*70}")
print(f"  第115000018期 實際開獎: {actual}  特別號: {actual_special}")
print(f"  號碼總和: {actual_sum}")
print(f"{'='*70}")

# ======== Method 1: Fourier Rhythm 2-bet ========
from tools.power_fourier_rhythm import fourier_rhythm_predict
bets_fr2 = fourier_rhythm_predict(draws, n_bets=2, window=500)
print(f"\n[Method 1] Fourier Rhythm 2注:")
for i, bet in enumerate(bets_fr2):
    match = sorted(set(bet) & set(actual))
    print(f"  注{i+1}: {bet} -> 命中: {match} ({len(match)}個)")
all_fr2 = set()
for b in bets_fr2:
    all_fr2.update(b)
total_match_fr2 = len(all_fr2 & set(actual))
print(f"  2注總覆蓋命中: {total_match_fr2}/6")

# ======== Method 2: Power Precision 3-bet ========
from tools.predict_power_precision_3bet import generate_power_precision_3bet
bets_pp3 = generate_power_precision_3bet(draws)
print(f"\n[Method 2] Power Precision 3注:")
for i, bet in enumerate(bets_pp3):
    match = sorted(set(bet) & set(actual))
    print(f"  注{i+1}: {bet} -> 命中: {match} ({len(match)}個)")
all_pp3 = set()
for b in bets_pp3:
    all_pp3.update(b)
total_match_pp3 = len(all_pp3 & set(actual))
print(f"  3注總覆蓋命中: {total_match_pp3}/6")

# ======== Method 3: P0 偏差互補 ========
def power_p0_2bet(history, window=50, echo_boost=1.5):
    MAX_NUM, PICK = 38, 6
    recent = history[-window:] if len(history) > window else history
    expected = len(recent) * PICK / MAX_NUM
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM:
                freq[n] += 1
    scores = {}
    for n in range(1, MAX_NUM + 1):
        scores[n] = freq.get(n, 0) - expected
    if len(history) >= 3:
        for n in history[-2]['numbers']:
            if n <= MAX_NUM:
                scores[n] += echo_boost
    hot = sorted([(n, s) for n, s in scores.items() if s > 0.5],
                 key=lambda x: x[1], reverse=True)
    cold = sorted([(n, abs(s)) for n, s in scores.items() if s < -0.5],
                  key=lambda x: x[1], reverse=True)
    bet1 = [n for n, _ in hot[:PICK]]
    used = set(bet1)
    if len(bet1) < PICK:
        mid = sorted(range(1, MAX_NUM + 1), key=lambda n: abs(scores[n]))
        for n in mid:
            if n not in used and len(bet1) < PICK:
                bet1.append(n)
                used.add(n)
    bet2 = []
    for n, _ in cold:
        if n not in used and len(bet2) < PICK:
            bet2.append(n)
            used.add(n)
    if len(bet2) < PICK:
        for n in range(1, MAX_NUM + 1):
            if n not in used and len(bet2) < PICK:
                bet2.append(n)
                used.add(n)
    return [sorted(bet1[:PICK]), sorted(bet2[:PICK])]

bets_p0 = power_p0_2bet(draws)
print(f"\n[Method 3] P0 偏差互補 2注:")
for i, bet in enumerate(bets_p0):
    match = sorted(set(bet) & set(actual))
    print(f"  注{i+1}: {bet} -> 命中: {match} ({len(match)}個)")
all_p0 = set()
for b in bets_p0:
    all_p0.update(b)
total_match_p0 = len(all_p0 & set(actual))
print(f"  2注總覆蓋命中: {total_match_p0}/6")

# ======== Method 4: Markov transition ========
def markov_predict(history, max_num=38, n_bets=2, window=30):
    recent = history[-window:]
    transitions = {}
    for i in range(len(recent) - 1):
        for cn in recent[i]['numbers']:
            if cn > max_num:
                continue
            if cn not in transitions:
                transitions[cn] = Counter()
            for nn in recent[i + 1]['numbers']:
                if nn <= max_num:
                    transitions[cn][nn] += 1
    prev = history[-1]['numbers']
    scores = Counter()
    for pn in prev:
        if pn > max_num:
            continue
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for n, cnt in trans.items():
                scores[n] += cnt / total
    ranked = sorted(scores, key=lambda x: scores[x], reverse=True)
    bets = []
    used = set()
    for i in range(n_bets):
        bet = []
        for n in ranked:
            if n not in used and len(bet) < 6:
                bet.append(n)
                used.add(n)
        if len(bet) < 6:
            for n in range(1, max_num + 1):
                if n not in used and len(bet) < 6:
                    bet.append(n)
                    used.add(n)
        bets.append(sorted(bet))
    return bets

bets_mk = markov_predict(draws)
print(f"\n[Method 4] Markov Transition 2注:")
for i, bet in enumerate(bets_mk):
    match = sorted(set(bet) & set(actual))
    print(f"  注{i+1}: {bet} -> 命中: {match} ({len(match)}個)")
all_mk = set()
for b in bets_mk:
    all_mk.update(b)
total_match_mk = len(all_mk & set(actual))
print(f"  2注總覆蓋命中: {total_match_mk}/6")

# ======== Method 5: Cold Number Reversion ========
def cold_predict(history, max_num=38, recent_window=100):
    recent = history[-recent_window:]
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            if n <= max_num:
                freq[n] += 1
    coldest = sorted(range(1, max_num + 1), key=lambda x: freq.get(x, 0))
    bet1 = sorted(coldest[:6])
    bet2 = sorted(coldest[6:12])
    return [bet1, bet2]

bets_cold = cold_predict(draws)
print(f"\n[Method 5] Cold Reversion 2注:")
for i, bet in enumerate(bets_cold):
    match = sorted(set(bet) & set(actual))
    print(f"  注{i+1}: {bet} -> 命中: {match} ({len(match)}個)")
all_cold = set()
for b in bets_cold:
    all_cold.update(b)
total_match_cold = len(all_cold & set(actual))
print(f"  2注總覆蓋命中: {total_match_cold}/6")

# ======== Method 6: Hot Number ========
def hot_predict(history, max_num=38, recent_window=50):
    recent = history[-recent_window:]
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            if n <= max_num:
                freq[n] += 1
    hottest = sorted(freq, key=lambda x: freq[x], reverse=True)
    bet1 = sorted(hottest[:6])
    bet2 = sorted(hottest[6:12])
    return [bet1, bet2]

bets_hot = hot_predict(draws)
print(f"\n[Method 6] Hot Numbers 2注:")
for i, bet in enumerate(bets_hot):
    match = sorted(set(bet) & set(actual))
    print(f"  注{i+1}: {bet} -> 命中: {match} ({len(match)}個)")
all_hot = set()
for b in bets_hot:
    all_hot.update(b)
total_match_hot = len(all_hot & set(actual))
print(f"  2注總覆蓋命中: {total_match_hot}/6")

# ======== Special Number Analysis ========
print(f"\n{'='*70}")
print(f"  特別號分析 (實際: {actual_special})")
print(f"{'='*70}")
try:
    from models.special_predictor import PowerLottoSpecialPredictor
    rules = {'name': 'POWER_LOTTO', 'specialMinNumber': 1, 'specialMaxNumber': 8}
    sp = PowerLottoSpecialPredictor(rules)
    combined_nums = list(set())
    for b in bets_fr2:
        combined_nums.extend(b)
    combined_nums = list(set(combined_nums))
    sp_top = sp.predict_top_n(draws, n=3, main_numbers=combined_nums)
    print(f"  V3 MAB Top3: {sp_top} -> 命中: {'是' if actual_special in sp_top else '否'}")
except Exception as e:
    print(f"  V3 預測失敗: {e}")

recent_sp = [d.get('special', 0) for d in draws[-20:]]
print(f"  近20期特別號: {recent_sp}")
sp_freq = Counter(recent_sp)
print(f"  近20期特別號頻率: {dict(sorted(sp_freq.items()))}")

# ======== Deep Feature Analysis of P18 ========
print(f"\n{'='*70}")
print(f"  P18 深度特徵分析")
print(f"{'='*70}")

# 1. Sum analysis
sums_300 = [sum(d['numbers']) for d in draws[-300:]]
mean_sum = np.mean(sums_300)
std_sum = np.std(sums_300)
print(f"\n  號碼總和分析:")
print(f"    P18 sum = {actual_sum}")
print(f"    近300期 mean = {mean_sum:.1f}, std = {std_sum:.1f}")
print(f"    z-score = {(actual_sum - mean_sum) / std_sum:.2f}")
print(f"    P17 sum = {sum(draws[-1]['numbers'])}")

# 2. Gap analysis (each number's gap before P17)
print(f"\n  各號碼間距分析 (上次出現到P17):")
for num in actual:
    gap = 0
    for i in range(len(draws) - 1, -1, -1):
        if num in draws[i]['numbers']:
            gap = len(draws) - 1 - i
            break
    else:
        gap = len(draws)
    print(f"    號碼 {num:2d}: 間距 = {gap} 期")

# 3. Zone distribution
zones = {'1-9': 0, '10-19': 0, '20-29': 0, '30-38': 0}
for n in actual:
    if n <= 9: zones['1-9'] += 1
    elif n <= 19: zones['10-19'] += 1
    elif n <= 29: zones['20-29'] += 1
    else: zones['30-38'] += 1
print(f"\n  區間分布: {zones}")

# 4. Consecutive analysis
consecutive = []
for i in range(len(actual) - 1):
    if actual[i + 1] - actual[i] <= 2:
        consecutive.append((actual[i], actual[i + 1]))
print(f"  連號/近鄰: {consecutive}")

# 5. Odd/Even
odd_count = sum(1 for n in actual if n % 2 == 1)
print(f"  奇偶比: {odd_count}:{6-odd_count} (奇:偶)")

# 6. Tail number distribution
tails = [n % 10 for n in actual]
print(f"  尾數分布: {sorted(tails)}")
tail_freq = Counter(tails)
print(f"  尾數頻率: {dict(sorted(tail_freq.items()))}")

# 7. P17->P18 repeat check
p17 = draws[-1]['numbers']
repeat = set(p17) & set(actual)
print(f"\n  P17 -> P18 重複號碼: {sorted(repeat)} ({len(repeat)}個)")
print(f"  P17: {p17}")

# 8. Lag-2 echo (P16)
if len(draws) >= 2:
    p16 = draws[-2]['numbers']
    echo = set(p16) & set(actual)
    print(f"  P16 -> P18 回聲號碼: {sorted(echo)} ({len(echo)}個)")
    print(f"  P16: {p16}")

# 9. Lag-3 echo (P15)
if len(draws) >= 3:
    p15 = draws[-3]['numbers']
    echo3 = set(p15) & set(actual)
    print(f"  P15 -> P18 回聲號碼: {sorted(echo3)} ({len(echo3)}個)")
    print(f"  P15: {p15}")

# 10. Number frequency in recent windows
print(f"\n  P18號碼在各窗口的頻率排名:")
for window_size in [30, 50, 100, 200]:
    recent = draws[-window_size:]
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            if n <= 38:
                freq[n] += 1
    all_ranked = sorted(range(1, 39), key=lambda x: freq.get(x, 0), reverse=True)
    for num in actual:
        rank = all_ranked.index(num) + 1 if num in all_ranked else 'N/A'
        print(f"    號碼 {num:2d} 在{window_size}期窗口: 出現{freq.get(num, 0)}次, 排名#{rank}/38")
    print()

# ======== Summary ========
print(f"\n{'='*70}")
print(f"  各方法命中比較總覽")
print(f"{'='*70}")
results = [
    ("Fourier Rhythm 2注", total_match_fr2, bets_fr2),
    ("Power Precision 3注", total_match_pp3, bets_pp3),
    ("P0 偏差互補 2注", total_match_p0, bets_p0),
    ("Markov Transition 2注", total_match_mk, bets_mk),
    ("Cold Reversion 2注", total_match_cold, bets_cold),
    ("Hot Numbers 2注", total_match_hot, bets_hot),
]
results.sort(key=lambda x: -x[1])
for name, hits, bets in results:
    bets_str = " | ".join([str(b) for b in bets])
    print(f"  {name}: {hits}/6 命中  -> {bets_str}")

# ======== Near-miss analysis (numbers off by 1) ========
print(f"\n{'='*70}")
print(f"  近似號碼分析 (差1)")
print(f"{'='*70}")
all_methods = {
    "Fourier Rhythm 2注": bets_fr2,
    "Power Precision 3注": bets_pp3,
    "P0 偏差互補 2注": bets_p0,
    "Markov 2注": bets_mk,
    "Cold 2注": bets_cold,
    "Hot 2注": bets_hot,
}
for name, bets in all_methods.items():
    all_nums = set()
    for b in bets:
        all_nums.update(b)
    near_miss = set()
    for n in all_nums:
        for a in actual:
            if abs(n - a) == 1 and n not in actual:
                near_miss.add((n, a))
    if near_miss:
        print(f"  {name}: {sorted(near_miss)}")

# ======== Fourier individual number scores ========
print(f"\n{'='*70}")
print(f"  Fourier 評分中 P18 號碼的得分")
print(f"{'='*70}")
from tools.predict_power_precision_3bet import get_fourier_rank
f_rank = get_fourier_rank(draws)
print(f"  Fourier 排名 (top 20): {f_rank[:20].tolist()}")
for num in actual:
    rank_pos = list(f_rank).index(num) if num in f_rank else -1
    print(f"  號碼 {num:2d}: Fourier 排名 #{rank_pos + 1}")
