#!/usr/bin/env python3
"""
大樂透 115000025 期完整檢討分析
================================
開獎號碼: 12, 19, 22, 27, 28, 31 | 特別號: 45
日期: 115/02/24

分析內容:
1. 所有預測方法的預測結果 vs 實際開獎
2. 各方法命中分析
3. 號碼特徵深度分析（和值、奇偶、尾數、區間、連號、Gap等）
4. 未能預測的原因分析
5. 各方法覆蓋率與盲區分析
6. 多注策略可行性評估
"""
import os
import sys
import json
import numpy as np
from collections import Counter, defaultdict
from scipy.fft import fft, fftfreq
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

# ============ 開獎結果 ============
DRAW_ID = '115000025'
ACTUAL_NUMBERS = [12, 19, 22, 27, 28, 31]
SPECIAL = 45
ACTUAL_SET = set(ACTUAL_NUMBERS)
MAX_NUM = 49
PICK = 6

# ============ 載入歷史數據 ============
db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
raw = db.get_all_draws('BIG_LOTTO')
history = sorted(raw, key=lambda x: (x['date'], x['draw']))

# 找到目標期的位置 — 用 115000024 作為「最新已知期」
# 115000025 可能還沒入庫，所以用到 115000024 為止的歷史
cutoff_idx = None
for i, d in enumerate(history):
    if str(d['draw']) == '115000024':
        cutoff_idx = i + 1
        break

if cutoff_idx is None:
    # 如果找不到，就用全部歷史
    cutoff_idx = len(history)
    print(f"⚠️ 找不到 115000024，使用全部 {len(history)} 期歷史")
else:
    print(f"✅ 使用截至 115000024 的歷史: {cutoff_idx} 期")

hist = history[:cutoff_idx]
print(f"最後一期: {hist[-1]['draw']} ({hist[-1]['date']})")
print(f"目標期: {DRAW_ID} — 開獎號碼: {ACTUAL_NUMBERS} | 特別號: {SPECIAL}")
print()

# ============ 1. 執行所有預測方法 ============
print("=" * 80)
print("  1. 各預測方法結果 vs 實際開獎")
print("=" * 80)

results = {}

# --- 方法 A: P0 偏差互補+回聲 (2注) ---
def biglotto_p0_2bet(history, window=50, echo_boost=1.5):
    recent = history[-window:] if len(history) > window else history
    expected = len(recent) * PICK / MAX_NUM
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    scores = {}
    for n in range(1, MAX_NUM + 1):
        scores[n] = freq.get(n, 0) - expected
    if len(history) >= 3:
        for n in history[-2]['numbers']:
            if n <= MAX_NUM:
                scores[n] += echo_boost
    hot = sorted([(n, s) for n, s in scores.items() if s > 1], key=lambda x: x[1], reverse=True)
    cold = sorted([(n, abs(s)) for n, s in scores.items() if s < -1], key=lambda x: x[1], reverse=True)
    bet1 = [n for n, _ in hot[:PICK]]
    used = set(bet1)
    if len(bet1) < PICK:
        mid = sorted(range(1, MAX_NUM + 1), key=lambda n: abs(scores[n]))
        for n in mid:
            if n not in used and len(bet1) < PICK:
                bet1.append(n); used.add(n)
    bet2 = []
    for n, _ in cold:
        if n not in used and len(bet2) < PICK:
            bet2.append(n); used.add(n)
    if len(bet2) < PICK:
        for n in range(1, MAX_NUM + 1):
            if n not in used and len(bet2) < PICK:
                bet2.append(n); used.add(n)
    return [sorted(bet1[:PICK]), sorted(bet2[:PICK])]

try:
    p0_bets = biglotto_p0_2bet(hist)
    results['P0偏差互補+回聲(2注)'] = p0_bets
except Exception as e:
    print(f"P0 失敗: {e}")

# --- 方法 B: Triple Strike (3注) ---
try:
    from tools.predict_biglotto_triple_strike import generate_triple_strike
    ts3_bets = generate_triple_strike(hist)
    results['TripleStrike(3注)'] = ts3_bets
except Exception as e:
    print(f"TS3 失敗: {e}")
    import traceback; traceback.print_exc()

# --- 方法 C: 5注正交 TS3+Markov+FreqOrt ---
try:
    from tools.backtest_biglotto_markov_4bet import (
        fourier_rhythm_bet, cold_numbers_bet, tail_balance_bet, markov_orthogonal_bet
    )
    bet1_f = fourier_rhythm_bet(hist, window=500)
    used = set(bet1_f)
    bet2_c = cold_numbers_bet(hist, window=100, exclude=used)
    used.update(bet2_c)
    bet3_t = tail_balance_bet(hist, window=100, exclude=used)
    used.update(bet3_t)
    bet4_m = markov_orthogonal_bet(hist, exclude=used, markov_window=30)
    used.update(bet4_m)
    recent_100 = hist[-100:] if len(hist) >= 100 else hist
    freq_100 = Counter(n for d in recent_100 for n in d['numbers'])
    remaining = sorted([n for n in range(1, MAX_NUM+1) if n not in used],
                       key=lambda x: -freq_100.get(x, 0))
    bet5_o = sorted(remaining[:6])
    results['5注正交'] = [bet1_f, bet2_c, bet3_t, bet4_m, bet5_o]
    results['Fourier單注'] = [bet1_f]
    results['Cold單注'] = [bet2_c]
    results['Tail單注'] = [bet3_t]
    results['Markov單注'] = [bet4_m]
    results['FreqOrt單注'] = [bet5_o]
except Exception as e:
    print(f"5注正交 失敗: {e}")
    import traceback; traceback.print_exc()

# --- 方法 D: Fourier Rhythm 獨立 (不排除) ---
try:
    from tools.predict_biglotto_triple_strike import fourier_rhythm_bet as ts3_fourier
    fourier_solo = ts3_fourier(hist, window=500)
    results['Fourier獨立(w500)'] = [fourier_solo]
except Exception as e:
    print(f"Fourier獨立失敗: {e}")

# --- 方法 E: 更多工具嘗試 ---
extra_tools = [
    ('predict_biglotto_echo_2bet', 'Echo2注'),
    ('predict_biglotto_echo_3bet', 'Echo3注'),
    ('predict_biglotto_deviation_2bet', 'Deviation2注'),
    ('predict_biglotto_apriori', 'Apriori'),
    ('predict_biglotto_zonal', 'Zonal'),
    ('predict_biglotto_best', 'Best'),
    ('predict_biglotto_mixed_3bet', 'Mixed3注'),
    ('predict_biglotto_radical', 'Radical'),
    ('predict_big_lotto_smart_2bet', 'Smart2注'),
]

for module_name, label in extra_tools:
    try:
        mod = __import__(f'tools.{module_name}', fromlist=[''])
        # 嘗試常見函數名
        for func_name in ['predict', 'generate_prediction', 'generate_bets',
                          'generate_triple_strike', 'generate_echo_2bet',
                          'generate_echo_3bet', 'generate_deviation_2bet',
                          'generate_apriori_bets', 'generate_zonal_bets',
                          'predict_best', 'generate_mixed_3bet',
                          'generate_radical_bets', 'predict_smart_2bet',
                          'main_predict']:
            if hasattr(mod, func_name):
                func = getattr(mod, func_name)
                try:
                    r = func(hist)
                    if r and isinstance(r, list):
                        if isinstance(r[0], dict):
                            bets = [b['numbers'] for b in r if 'numbers' in b]
                        elif isinstance(r[0], list):
                            bets = r
                        else:
                            continue
                        if bets:
                            results[label] = bets
                            break
                except:
                    continue
    except Exception:
        pass

# --- 方法 F: 純頻率 Top 6/12 ---
recent_50 = hist[-50:]
freq_50 = Counter(n for d in recent_50 for n in d['numbers'])
freq_top6 = sorted([n for n, _ in freq_50.most_common(6)])
results['頻率Top6(w50)'] = [freq_top6]

recent_100 = hist[-100:]
freq_100_c = Counter(n for d in recent_100 for n in d['numbers'])
freq_top6_100 = sorted([n for n, _ in freq_100_c.most_common(6)])
freq_top12_100 = [n for n, _ in freq_100_c.most_common(12)]
results['頻率Top6(w100)'] = [sorted(freq_top6_100)]
results['頻率Top12分2注(w100)'] = [sorted(freq_top12_100[:6]), sorted(freq_top12_100[6:12])]

# --- 方法 G: 冷號 Top 6 ---
cold_6 = sorted([n for n, _ in freq_100_c.most_common()[-6:]])
results['冷號Top6(w100)'] = [cold_6]
cold_12 = [n for n, _ in freq_100_c.most_common()[-12:]]
results['冷號Top12分2注(w100)'] = [sorted(cold_12[:6]), sorted(cold_12[6:12])]

# --- 方法 H: 上期號碼鄰號 ±1 ---
prev_nums = hist[-1]['numbers']
neighbor_set = set()
for n in prev_nums:
    for delta in [-1, 0, 1]:
        nn = n + delta
        if 1 <= nn <= MAX_NUM:
            neighbor_set.add(nn)
neighbor_list = sorted(neighbor_set)[:12]
results['上期鄰號±1'] = [sorted(neighbor_list[:6]), sorted(neighbor_list[6:12])] if len(neighbor_list) >= 12 else [sorted(neighbor_list[:6])]

# --- 方法 I: 上2期號碼 (Echo) ---
if len(hist) >= 2:
    echo_nums = sorted(hist[-2]['numbers'])
    results['上2期Echo'] = [echo_nums]

# --- 方法 J: 隨機基準 (10次平均) ---
import random
random.seed(42)
rand_bets = []
for _ in range(10):
    rand_bets.append(sorted(random.sample(range(1, MAX_NUM+1), PICK)))
results['隨機基準(10注)'] = rand_bets

print()

# ============ 打印結果 ============
def count_hits(bets, actual_set):
    """返回每注命中數和最佳命中"""
    hits_per_bet = []
    for bet in bets:
        bet_set = set(bet)
        hit = bet_set & actual_set
        hits_per_bet.append((sorted(hit), len(hit)))
    best = max(hits_per_bet, key=lambda x: x[1])
    any_m3 = any(h >= 3 for _, h in hits_per_bet)
    return hits_per_bet, best, any_m3

method_scores = []

for method, bets in sorted(results.items(), key=lambda x: x[0]):
    hits_per_bet, best, any_m3 = count_hits(bets, ACTUAL_SET)
    total_coverage = set()
    for b in bets:
        total_coverage.update(b)
    coverage_hit = total_coverage & ACTUAL_SET

    print(f"\n--- {method} ({len(bets)}注) ---")
    for i, bet in enumerate(bets):
        hit_nums, hit_count = hits_per_bet[i]
        marker = " ★" if hit_count >= 3 else ""
        print(f"  注{i+1}: {[f'{n:02d}' for n in bet]} | 命中 {hit_count}: {hit_nums}{marker}")
    print(f"  總覆蓋: {len(total_coverage)} 號碼 | 覆蓋命中: {len(coverage_hit)}/6 {sorted(coverage_hit)}")
    if any_m3:
        print(f"  🎯 M3+ 命中！最佳: {best[1]}中")

    method_scores.append({
        'method': method,
        'n_bets': len(bets),
        'best_hit': best[1],
        'coverage_hit': len(coverage_hit),
        'total_coverage': len(total_coverage),
        'any_m3': any_m3,
        'all_hits': [(h[0], h[1]) for h in hits_per_bet],
    })

# ============ 排名 ============
print("\n" + "=" * 80)
print("  2. 預測方法排名 (按最佳單注命中 & 覆蓋命中)")
print("=" * 80)

method_scores.sort(key=lambda x: (-x['best_hit'], -x['coverage_hit'], x['n_bets']))
for rank, ms in enumerate(method_scores, 1):
    m3_mark = "🎯" if ms['any_m3'] else "  "
    print(f"  {rank:2d}. {m3_mark} {ms['method']:30s} | 最佳命中: {ms['best_hit']} | "
          f"覆蓋命中: {ms['coverage_hit']}/6 | {ms['n_bets']}注 覆蓋{ms['total_coverage']}")

# ============ 3. 號碼特徵深度分析 ============
print("\n" + "=" * 80)
print("  3. 第115000025期號碼特徵深度分析")
print("=" * 80)

print(f"\n  開獎號碼: {ACTUAL_NUMBERS} | 特別號: {SPECIAL}")

# 3.1 基本統計
total_sum = sum(ACTUAL_NUMBERS)
mean_val = total_sum / 6
odd_count = sum(1 for n in ACTUAL_NUMBERS if n % 2 == 1)
even_count = 6 - odd_count
print(f"\n  [基本統計]")
print(f"  和值: {total_sum} (平均 {mean_val:.1f})")
print(f"  奇偶比: {odd_count}:{even_count}")

# 3.2 區間分布 (1-10, 11-20, 21-30, 31-40, 41-49)
zones = {f"Z{i+1}({i*10+1}-{min((i+1)*10, 49)})": 
         sum(1 for n in ACTUAL_NUMBERS if i*10 < n <= (i+1)*10 or (i==0 and 1<=n<=10))
         for i in range(5)}
# Correct zones
z1 = sum(1 for n in ACTUAL_NUMBERS if 1 <= n <= 10)
z2 = sum(1 for n in ACTUAL_NUMBERS if 11 <= n <= 20)
z3 = sum(1 for n in ACTUAL_NUMBERS if 21 <= n <= 30)
z4 = sum(1 for n in ACTUAL_NUMBERS if 31 <= n <= 40)
z5 = sum(1 for n in ACTUAL_NUMBERS if 41 <= n <= 49)
print(f"  區間分布: Z1(1-10)={z1}, Z2(11-20)={z2}, Z3(21-30)={z3}, Z4(31-40)={z4}, Z5(41-49)={z5}")

# 3.3 尾數分布
tails = Counter(n % 10 for n in ACTUAL_NUMBERS)
print(f"  尾數: {dict(sorted(tails.items()))}")
print(f"  尾數種類: {len(tails)}/6")

# 3.4 連號分析
sorted_nums = sorted(ACTUAL_NUMBERS)
consec_pairs = [(sorted_nums[i], sorted_nums[i+1]) for i in range(5) if sorted_nums[i+1] - sorted_nums[i] == 1]
print(f"  連號對: {consec_pairs} ({len(consec_pairs)}對)")

# 3.5 Gap 分析
gaps = [sorted_nums[i+1] - sorted_nums[i] for i in range(5)]
print(f"  號碼間距: {gaps} (min={min(gaps)}, max={max(gaps)}, avg={np.mean(gaps):.1f})")

# 3.6 AC值 (complexity)
diffs = set()
for i in range(6):
    for j in range(i+1, 6):
        diffs.add(abs(ACTUAL_NUMBERS[i] - ACTUAL_NUMBERS[j]))
ac = len(diffs) - 5
print(f"  AC值: {ac} (差值種類{len(diffs)}, C(6,2)=15)")

# ============ 4. 歷史對比分析 ============
print("\n" + "=" * 80)
print("  4. 歷史對比 — 此組號碼在歷史中的特殊性")
print("=" * 80)

# 4.1 各號碼在近期的頻率和Gap
windows = [30, 50, 100, 200, 500]
for w in windows:
    recent_w = hist[-w:]
    freq_w = Counter(n for d in recent_w for n in d['numbers'])
    expected_w = len(recent_w) * PICK / MAX_NUM
    print(f"\n  [近{w}期分析]")
    for n in ACTUAL_NUMBERS:
        actual_freq = freq_w.get(n, 0)
        deviation = actual_freq - expected_w
        # Gap: 距離上次出現幾期
        gap = None
        for j in range(len(recent_w)-1, -1, -1):
            if n in recent_w[j]['numbers']:
                gap = len(recent_w) - 1 - j
                break
        if gap is None:
            gap = f">{w}"
        dev_mark = "↑" if deviation > 1 else ("↓" if deviation < -1 else "→")
        print(f"    {n:2d}: freq={actual_freq:3d} (期望{expected_w:.1f}, 偏差{deviation:+.1f}{dev_mark}), 距上次出現: {gap}期")

# 4.2 和值歷史分位數
all_sums = [sum(d['numbers']) for d in hist]
percentile = sum(1 for s in all_sums if s <= total_sum) / len(all_sums) * 100
recent_sums = [sum(d['numbers']) for d in hist[-50:]]
recent_pctl = sum(1 for s in recent_sums if s <= total_sum) / len(recent_sums) * 100
print(f"\n  [和值分析]")
print(f"  本期和值: {total_sum}")
print(f"  歷史百分位: {percentile:.1f}%")
print(f"  近50期百分位: {recent_pctl:.1f}%")
print(f"  歷史均值: {np.mean(all_sums):.1f} ± {np.std(all_sums):.1f}")
print(f"  近50期均值: {np.mean(recent_sums):.1f} ± {np.std(recent_sums):.1f}")

# 4.3 上期與本期的關係
prev = hist[-1]
prev_nums = set(prev['numbers'])
overlap = ACTUAL_SET & prev_nums
print(f"\n  [期間關聯]")
print(f"  上期(115000024): {sorted(prev_nums)} special={prev.get('special', 'N/A')}")
print(f"  本期(115000025): {ACTUAL_NUMBERS} special={SPECIAL}")
print(f"  重疊號碼: {sorted(overlap)} ({len(overlap)}個)")

if len(hist) >= 2:
    prev2 = hist[-2]
    prev2_nums = set(prev2['numbers'])
    overlap2 = ACTUAL_SET & prev2_nums
    print(f"  上2期({prev2['draw']}): {sorted(prev2_nums)}")
    print(f"  與上2期重疊: {sorted(overlap2)} ({len(overlap2)}個)")

if len(hist) >= 3:
    prev3 = hist[-3]
    prev3_nums = set(prev3['numbers'])
    overlap3 = ACTUAL_SET & prev3_nums
    print(f"  上3期({prev3['draw']}): {sorted(prev3_nums)}")
    print(f"  與上3期重疊: {sorted(overlap3)} ({len(overlap3)}個)")

# 4.4 鄰號分析 
prev_neighbors = set()
for n in prev['numbers']:
    for delta in [-1, 0, 1]:
        nn = n + delta
        if 1 <= nn <= MAX_NUM:
            prev_neighbors.add(nn)
neighbor_hit = ACTUAL_SET & prev_neighbors
print(f"  上期鄰號域(±1): {sorted(prev_neighbors)}")
print(f"  鄰號命中: {sorted(neighbor_hit)} ({len(neighbor_hit)}個)")

# 4.5 相同尾數分析
prev_tails = set(n % 10 for n in prev['numbers'])
actual_tails = set(n % 10 for n in ACTUAL_NUMBERS)
tail_overlap = prev_tails & actual_tails
print(f"  上期尾數: {sorted(prev_tails)}")
print(f"  本期尾數: {sorted(actual_tails)}")
print(f"  尾數重疊: {sorted(tail_overlap)} ({len(tail_overlap)}組)")

# ============ 5. Fourier/FFT 號碼個別得分 ============
print("\n" + "=" * 80)
print("  5. Fourier 週期分析 — 各號碼得分")
print("=" * 80)

def fourier_scores(history, window=500):
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    bitstreams = {i: np.zeros(w) for i in range(1, MAX_NUM+1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= MAX_NUM:
                bitstreams[n][idx] = 1
    scores = {}
    for n in range(1, MAX_NUM+1):
        bh = bitstreams[n]
        if sum(bh) < 2:
            scores[n] = 0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            scores[n] = 0
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
        else:
            scores[n] = 0
    return scores

f_scores = fourier_scores(hist, window=500)
f_ranked = sorted(f_scores.items(), key=lambda x: -x[1])

print(f"\n  Fourier Top 20 (window=500):")
for rank, (n, s) in enumerate(f_ranked[:20], 1):
    marker = " ★ 命中!" if n in ACTUAL_SET else ""
    print(f"  {rank:2d}. 號碼 {n:2d}: score={s:.4f}{marker}")

print(f"\n  開獎號碼的 Fourier 排名:")
for n in ACTUAL_NUMBERS:
    rank = [i for i, (nn, _) in enumerate(f_ranked, 1) if nn == n][0]
    print(f"    {n:2d}: 排名 {rank}/49 (score={f_scores[n]:.4f})")

# ============ 6. 偏差分析 (P0) ============
print("\n" + "=" * 80)
print("  6. 偏差分析 — 各號碼 P0 得分")
print("=" * 80)

for w in [50, 100]:
    recent_w = hist[-w:]
    expected_w = len(recent_w) * PICK / MAX_NUM
    freq_w = Counter(n for d in recent_w for n in d['numbers'])
    dev_scores = {n: freq_w.get(n, 0) - expected_w for n in range(1, MAX_NUM+1)}
    
    # Echo boost
    echo_scores = dict(dev_scores)
    if len(hist) >= 3:
        for n in hist[-2]['numbers']:
            if n <= MAX_NUM:
                echo_scores[n] += 1.5
    
    ranked = sorted(echo_scores.items(), key=lambda x: -x[1])
    print(f"\n  偏差排名 Top 15 (window={w}, echo_boost=1.5):")
    for rank, (n, s) in enumerate(ranked[:15], 1):
        marker = " ★" if n in ACTUAL_SET else ""
        print(f"  {rank:2d}. {n:2d}: dev={dev_scores[n]:+.2f}, echo_score={s:+.2f}{marker}")
    
    print(f"\n  開獎號碼的偏差排名 (w={w}):")
    for n in ACTUAL_NUMBERS:
        rank = [i for i, (nn, _) in enumerate(ranked, 1) if nn == n][0]
        print(f"    {n:2d}: 排名 {rank}/49 (dev={dev_scores[n]:+.2f}, echo={echo_scores[n]:+.2f})")

# ============ 7. 冷號分析 ============
print("\n" + "=" * 80)
print("  7. 冷號狀態 — 各號碼距上次出現的期數 (Gap)")
print("=" * 80)

gap_data = {}
for n in range(1, MAX_NUM+1):
    found = False
    for j in range(len(hist)-1, -1, -1):
        if n in hist[j]['numbers']:
            gap_data[n] = len(hist) - 1 - j
            found = True
            break
    if not found:
        gap_data[n] = len(hist)

gap_ranked = sorted(gap_data.items(), key=lambda x: -x[1])
print(f"\n  最冷號碼 Top 15:")
for rank, (n, g) in enumerate(gap_ranked[:15], 1):
    marker = " ★" if n in ACTUAL_SET else ""
    print(f"  {rank:2d}. {n:2d}: gap={g}期{marker}")

print(f"\n  開獎號碼的 Gap:")
for n in ACTUAL_NUMBERS:
    g = gap_data[n]
    rank = [i for i, (nn, _) in enumerate(gap_ranked, 1) if nn == n][0]
    category = "冷" if g > 15 else ("溫" if g > 5 else "熱")
    print(f"    {n:2d}: gap={g}期 (排名{rank}/49) [{category}]")

# ============ 8. Markov 轉移分析 ============
print("\n" + "=" * 80)
print("  8. Markov 轉移分析 — 上期號碼 → 下期機率")
print("=" * 80)

markov_window = 100
recent_mk = hist[-markov_window:] if len(hist) >= markov_window else hist
transitions = defaultdict(Counter)

for i in range(len(recent_mk)-1):
    curr_nums = recent_mk[i]['numbers']
    next_nums = recent_mk[i+1]['numbers']
    for cn in curr_nums:
        for nn in next_nums:
            transitions[cn][nn] += 1

# 上期號碼的轉移預測
prev_draw_nums = hist[-1]['numbers']
markov_scores = Counter()
for pn in prev_draw_nums:
    trans = transitions.get(pn, Counter())
    total = sum(trans.values())
    if total > 0:
        for n, cnt in trans.items():
            markov_scores[n] += cnt / total

markov_ranked = sorted(markov_scores.items(), key=lambda x: -x[1])
print(f"\n  Markov 從上期 {sorted(prev_draw_nums)} 轉移的 Top 15:")
for rank, (n, s) in enumerate(markov_ranked[:15], 1):
    marker = " ★" if n in ACTUAL_SET else ""
    print(f"  {rank:2d}. {n:2d}: score={s:.4f}{marker}")

print(f"\n  開獎號碼的 Markov 排名:")
for n in ACTUAL_NUMBERS:
    found = False
    for i, (nn, s) in enumerate(markov_ranked, 1):
        if nn == n:
            print(f"    {n:2d}: 排名 {i}/49 (score={s:.4f})")
            found = True
            break
    if not found:
        print(f"    {n:2d}: 未出現在 Markov 候選中")

# ============ 9. 多維能力覆蓋矩陣 ============
print("\n" + "=" * 80)
print("  9. 多維能力覆蓋矩陣 — 各方法能否選中開獎號碼")
print("=" * 80)

# 建立各號碼在各方法中的排名
method_rankings = {}

# Fourier
method_rankings['Fourier(w500)'] = {n: r for r, (n, _) in enumerate(f_ranked, 1)}

# P0 deviation (w50)
recent_50 = hist[-50:]
expected_50 = len(recent_50) * PICK / MAX_NUM
freq_50_d = Counter(n for d in recent_50 for n in d['numbers'])
dev_50 = {n: freq_50_d.get(n, 0) - expected_50 for n in range(1, MAX_NUM+1)}
echo_50 = dict(dev_50)
if len(hist) >= 3:
    for n in hist[-2]['numbers']:
        if n <= MAX_NUM: echo_50[n] += 1.5
ranked_p0_50 = sorted(echo_50.items(), key=lambda x: -x[1])
method_rankings['P0(w50)'] = {n: r for r, (n, _) in enumerate(ranked_p0_50, 1)}

# Cold (gap)
method_rankings['Cold(gap)'] = {n: r for r, (n, _) in enumerate(gap_ranked, 1)}

# Markov
method_rankings['Markov(w100)'] = {n: r for r, (n, _) in enumerate(markov_ranked, 1)}

# Tail balance — 用尾數頻率排名
tail_freq = Counter(n % 10 for d in hist[-100:] for n in d['numbers'])
tail_rank = {}
for n in range(1, MAX_NUM+1):
    tail_rank[n] = tail_freq.get(n % 10, 0)
tail_ranked = sorted(range(1, MAX_NUM+1), key=lambda n: -tail_rank[n])
method_rankings['TailFreq(w100)'] = {n: r+1 for r, n in enumerate(tail_ranked)}

# Frequency (w100)
freq_ranked_100 = sorted(freq_100_c.items(), key=lambda x: -x[1])
method_rankings['Freq(w100)'] = {n: r for r, (n, _) in enumerate(freq_ranked_100, 1)}

print(f"\n  {'號碼':>4} | {'Fourier':>8} | {'P0(w50)':>8} | {'Cold':>8} | {'Markov':>8} | {'TailFreq':>8} | {'Freq100':>8} | {'最佳排名':>8}")
print(f"  {'----':>4} | {'--------':>8} | {'--------':>8} | {'--------':>8} | {'--------':>8} | {'--------':>8} | {'--------':>8} | {'--------':>8}")
for n in ACTUAL_NUMBERS:
    ranks = []
    row = f"  {n:4d} |"
    for method_name in ['Fourier(w500)', 'P0(w50)', 'Cold(gap)', 'Markov(w100)', 'TailFreq(w100)', 'Freq(w100)']:
        r = method_rankings[method_name].get(n, 49)
        ranks.append(r)
        highlight = "◀" if r <= 6 else (" " if r <= 12 else "")
        row += f" {r:6d}{highlight} |"
    best_r = min(ranks)
    row += f" {best_r:6d}"
    print(row)

# 號碼可到達性分析
print(f"\n  可到達性示意 (排名<=6=可選中, <=12=候選池, >12=盲區):")
for n in ACTUAL_NUMBERS:
    reachable = []
    for method_name in ['Fourier(w500)', 'P0(w50)', 'Cold(gap)', 'Markov(w100)', 'TailFreq(w100)', 'Freq(w100)']:
        r = method_rankings[method_name].get(n, 49)
        if r <= 6:
            reachable.append(f"{method_name}✓")
        elif r <= 12:
            reachable.append(f"{method_name}~")
    if reachable:
        print(f"    {n:2d}: {', '.join(reachable)}")
    else:
        print(f"    {n:2d}: ⚠️ 全方法盲區 (所有方法排名>12)")

# ============ 10. 歷史相似期分析 ============
print("\n" + "=" * 80)
print("  10. 歷史相似期分析 — 找出與本期結構最相似的歷史開獎")
print("=" * 80)

def draw_similarity(d_nums, target_nums):
    """計算兩組號碼的綜合相似度"""
    s1, s2 = set(d_nums), set(target_nums)
    # 直接重疊
    overlap = len(s1 & s2)
    # 和值差
    sum_diff = abs(sum(d_nums) - sum(target_nums))
    # 區間分布差
    def zone_dist(nums):
        return [sum(1 for n in nums if i*10 < n <= (i+1)*10) for i in range(5)]
    z1, z2 = zone_dist(d_nums), zone_dist(target_nums)
    zone_diff = sum(abs(a-b) for a, b in zip(z1, z2))
    # 奇偶差
    odd_diff = abs(sum(1 for n in d_nums if n % 2) - sum(1 for n in target_nums if n % 2))
    
    score = overlap * 10 - sum_diff * 0.1 - zone_diff * 2 - odd_diff
    return score, overlap, sum_diff, zone_diff

similarities = []
for d in hist:
    score, overlap, sum_diff, zone_diff = draw_similarity(d['numbers'], ACTUAL_NUMBERS)
    similarities.append((d['draw'], d['date'], d['numbers'], score, overlap, sum_diff, zone_diff))

similarities.sort(key=lambda x: -x[3])

print(f"\n  最相似的10期:")
for rank, (draw, date, nums, score, overlap, sum_diff, zone_diff) in enumerate(similarities[:10], 1):
    print(f"  {rank:2d}. {draw} ({date}): {sorted(nums)} | "
          f"重疊:{overlap} 和差:{sum_diff} 區差:{zone_diff} 分:{score:.1f}")

# ============ 11. 信號域分析 ============
print("\n" + "=" * 80)
print("  11. 信號域分析 — 開獎號碼屬於哪個信號域？")
print("=" * 80)

# Fourier 域: Fourier Top 12
fourier_top12 = set(n for n, _ in f_ranked[:12])
fourier_hit = ACTUAL_SET & fourier_top12

# Cold 域: Cold Top 12  
cold_top12 = set(n for n, _ in gap_ranked[:12])
cold_hit = ACTUAL_SET & cold_top12

# Hot 域: Freq Top 12
hot_top12 = set(n for n, _ in freq_100_c.most_common(12))
hot_hit = ACTUAL_SET & hot_top12

# Markov 域: Markov Top 12
markov_top12 = set(n for n, _ in markov_ranked[:12])
markov_hit = ACTUAL_SET & markov_top12

# Echo 域: 上2期號碼
echo_set = set(hist[-2]['numbers']) if len(hist) >= 2 else set()
echo_hit = ACTUAL_SET & echo_set

# 鄰號域
neighbor_hit_set = ACTUAL_SET & prev_neighbors

print(f"  Fourier Top12: {sorted(fourier_top12)} → 命中 {sorted(fourier_hit)} ({len(fourier_hit)}/6)")
print(f"  Cold Top12:    {sorted(cold_top12)} → 命中 {sorted(cold_hit)} ({len(cold_hit)}/6)")
print(f"  Hot Top12:     {sorted(hot_top12)} → 命中 {sorted(hot_hit)} ({len(hot_hit)}/6)")
print(f"  Markov Top12:  {sorted(markov_top12)} → 命中 {sorted(markov_hit)} ({len(markov_hit)}/6)")
print(f"  Echo(上2期):   {sorted(echo_set)} → 命中 {sorted(echo_hit)} ({len(echo_hit)}/6)")
print(f"  鄰號(上期±1):  {sorted(prev_neighbors)[:12]}... → 命中 {sorted(neighbor_hit_set)} ({len(neighbor_hit_set)}/6)")

# 每個號碼歸屬
print(f"\n  各號碼信號域歸屬:")
for n in ACTUAL_NUMBERS:
    domains = []
    if n in fourier_top12: domains.append("Fourier")
    if n in cold_top12: domains.append("Cold")
    if n in hot_top12: domains.append("Hot")
    if n in markov_top12: domains.append("Markov")
    if n in echo_set: domains.append("Echo")
    if n in prev_neighbors: domains.append("鄰號")
    if domains:
        print(f"    {n:2d}: {', '.join(domains)}")
    else:
        print(f"    {n:2d}: ⚠️ 無信號覆蓋 (Dark Zone)")

# 聯集覆蓋
all_signal = fourier_top12 | cold_top12 | hot_top12 | markov_top12 | echo_set | prev_neighbors
uncovered = ACTUAL_SET - all_signal
print(f"\n  全信號聯集覆蓋: {len(all_signal)}/49 號碼")
print(f"  開獎號碼中未被任何信號覆蓋: {sorted(uncovered)} ({len(uncovered)}個)")

# ============ 12. 2注/3注最佳組合回顧分析 ============
print("\n" + "=" * 80)
print("  12. 2注/3注組合最佳化可行性")
print("=" * 80)

# 如果我們從所有信號的聯集中選，能命中多少？
print(f"\n  [聯集策略分析]")
all_candidates = fourier_top12 | cold_top12 | hot_top12 | markov_top12
total_candidates = len(all_candidates)
candidates_hit = ACTUAL_SET & all_candidates
print(f"  4域 Top12 聯集: {total_candidates} 候選號碼")
print(f"  命中: {sorted(candidates_hit)} ({len(candidates_hit)}/6)")

# 2注12個號碼最佳覆蓋
print(f"\n  [理論最佳2注覆蓋]")
print(f"  12個號碼可能的組合中，最多命中 6 個需要 12 個號碼全部對")
print(f"  實際從各域 Top6 組合2注(12號):")

# 各種2注組合嘗試
two_bet_combos = [
    ("Fourier+Cold", list(fourier_top12)[:6], list(cold_top12 - fourier_top12)[:6]),
    ("Fourier+Hot", list(fourier_top12)[:6], list(hot_top12 - fourier_top12)[:6]),
    ("Fourier+Markov", list(fourier_top12)[:6], list(markov_top12 - fourier_top12)[:6]),
    ("Hot+Cold", list(hot_top12)[:6], list(cold_top12 - hot_top12)[:6]),
    ("Hot+Markov", list(hot_top12)[:6], list(markov_top12 - hot_top12)[:6]),
]

for label, b1, b2 in two_bet_combos:
    if len(b1) < 6 or len(b2) < 6:
        continue
    b1s, b2s = set(sorted(b1)[:6]), set(sorted(b2)[:6])
    hit1 = len(b1s & ACTUAL_SET)
    hit2 = len(b2s & ACTUAL_SET)
    total_hit = len((b1s | b2s) & ACTUAL_SET)
    m3 = "🎯" if hit1 >= 3 or hit2 >= 3 else "  "
    print(f"    {m3} {label}: 注1命中{hit1} 注2命中{hit2} | 覆蓋命中{total_hit}/6")

# ============ 13. 近5期趨勢 ============
print("\n" + "=" * 80)
print("  13. 近5期趨勢分析")
print("=" * 80)

for i in range(min(5, len(hist)), 0, -1):
    d = hist[-i]
    nums = sorted(d['numbers'])
    s = sum(nums)
    odd = sum(1 for n in nums if n % 2)
    z_dist = [sum(1 for n in nums if (j*10) < n <= ((j+1)*10)) for j in range(5)]
    # 修正 Z1
    z_dist[0] = sum(1 for n in nums if 1 <= n <= 10)
    consec = sum(1 for j in range(len(nums)-1) if nums[j+1] - nums[j] == 1)
    print(f"  {d['draw']} ({d['date']}): {nums} sum={s:3d} 奇偶={odd}:{6-odd} "
          f"zone={z_dist} 連號={consec}")

# 本期
print(f"  目標 {DRAW_ID}:        {ACTUAL_NUMBERS} sum={total_sum:3d} 奇偶={odd_count}:{even_count} "
      f"zone=[{z1},{z2},{z3},{z4},{z5}] 連號={len(consec_pairs)}")

# ============ 14. 特徵遺漏原因摘要 ============
print("\n" + "=" * 80)
print("  14. 預測遺漏原因摘要")
print("=" * 80)

print("""
  [總結] 針對每個開獎號碼的預測困難度分析:
""")

for n in ACTUAL_NUMBERS:
    f_rank = method_rankings['Fourier(w500)'].get(n, 49)
    p0_rank = method_rankings['P0(w50)'].get(n, 49)
    cold_rank = method_rankings['Cold(gap)'].get(n, 49)
    mk_rank = method_rankings['Markov(w100)'].get(n, 49)
    freq_rank = method_rankings['Freq(w100)'].get(n, 49)
    
    best_method = min(
        [('Fourier', f_rank), ('P0', p0_rank), ('Cold', cold_rank), ('Markov', mk_rank), ('Freq', freq_rank)],
        key=lambda x: x[1]
    )
    
    difficulty = "容易" if best_method[1] <= 6 else ("中等" if best_method[1] <= 12 else ("困難" if best_method[1] <= 20 else "極困難"))
    
    reasons = []
    if f_rank > 12: reasons.append(f"Fourier週期未到(排名{f_rank})")
    if p0_rank > 12: reasons.append(f"偏差不顯著(排名{p0_rank})")
    if cold_rank > 12: reasons.append(f"非冷號(排名{cold_rank})")
    if mk_rank > 12: reasons.append(f"Markov弱(排名{mk_rank})")
    if freq_rank > 12: reasons.append(f"頻率中等(排名{freq_rank})")
    
    print(f"  號碼 {n:2d}: [{difficulty}] 最佳方法={best_method[0]}(排名{best_method[1]})")
    if reasons:
        print(f"         遺漏原因: {'; '.join(reasons)}")
    else:
        print(f"         各方法均有覆蓋能力")

# Save results to JSON
output = {
    'draw': DRAW_ID,
    'actual': ACTUAL_NUMBERS,
    'special': SPECIAL,
    'method_scores': method_scores,
    'signal_domains': {
        'fourier_hit': sorted(fourier_hit),
        'cold_hit': sorted(cold_hit),
        'hot_hit': sorted(hot_hit),
        'markov_hit': sorted(markov_hit),
        'echo_hit': sorted(echo_hit),
        'neighbor_hit': sorted(neighbor_hit_set),
        'uncovered': sorted(uncovered),
    }
}

with open(os.path.join(project_root, f'retrospective_{DRAW_ID}.json'), 'w') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n  結果已保存至 retrospective_{DRAW_ID}.json")
print("\n" + "=" * 80)
print("  分析完成")
print("=" * 80)
