#!/usr/bin/env python3
"""
威力彩 115000020 期檢討分析
開獎: [01, 11, 14, 17, 29, 32] 特別號: 08

目標:
1. 各預測方法對比 — 哪個最接近
2. 特徵分析 — 遺漏了什麼
3. 2注/3注方案 — 可行性研究
4. 自動學習機制 — 提升可能性
"""
import os
import sys
import numpy as np
from collections import Counter, defaultdict
from scipy.fft import fft, fftfreq
from itertools import combinations
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))

from lottery_api.database import DatabaseManager

MAX_NUM = 38
PICK = 6
ACTUAL = [1, 11, 14, 17, 29, 32]
ACTUAL_SPECIAL = 8
TARGET_DRAW = '115000020'

# ===== 載入數據 (排除020期) =====
db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
db = DatabaseManager(db_path)
all_draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))

# 找到 020 期的位置，只用之前的數據做預測
# 115000020 可能尚未入庫 (今日開獎)，使用 115000019 之前的全部數據
cut_idx = None
for i, d in enumerate(all_draws):
    if str(d['draw']) == TARGET_DRAW:
        cut_idx = i
        break

if cut_idx is not None:
    history = all_draws[:cut_idx]
    print(f"✅ 找到 {TARGET_DRAW} 期 (index={cut_idx})")
    print(f"  使用前 {len(history)} 期做預測模擬")
else:
    # 020 期還沒入庫，用全部資料 (截至019期)
    history = all_draws
    print(f"⚠️ {TARGET_DRAW} 期尚未入庫，使用全部 {len(all_draws)} 期做事後分析")

print(f"  最新期號: {history[-1]['draw']} ({history[-1]['date']})")
print(f"  上期開獎: {history[-1]['draw']} → {history[-1]['numbers']} 特{history[-1].get('special','?')}")

print(f"\n🎯 實際開獎: {ACTUAL}  特別號: {ACTUAL_SPECIAL}")
print("=" * 80)


# ===== 1. 各方法預測模擬 =====
def fourier_rank(hist, window=500):
    h = hist[-window:] if len(hist) >= window else hist
    w = len(h)
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bh = np.zeros(w)
        for idx, d in enumerate(h):
            if n in d['numbers']:
                bh[idx] = 1
        if sum(bh) < 2:
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            continue
        period = 1 / freq_val
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return scores


def markov_scores(hist, window=30):
    recent = hist[-window:] if len(hist) >= window else hist
    transitions = {}
    for i in range(len(recent) - 1):
        for cn in recent[i]['numbers']:
            if cn > MAX_NUM:
                continue
            if cn not in transitions:
                transitions[cn] = Counter()
            for nn in recent[i + 1]['numbers']:
                if nn <= MAX_NUM:
                    transitions[cn][nn] += 1
    prev_nums = hist[-1]['numbers']
    scores = Counter()
    for pn in prev_nums:
        if pn > MAX_NUM:
            continue
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for n, cnt in trans.items():
                scores[n] += cnt / total
    return scores


def frequency_scores(hist, window=100):
    recent = hist[-window:] if len(hist) >= window else hist
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM:
                freq[n] += 1
    return freq


def cold_scores(hist, window=100):
    """冷號分數 (現在gap越大分數越高)"""
    recent = hist[-window:] if len(hist) >= window else hist
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            if n <= MAX_NUM:
                last_seen[n] = i
    current = len(recent)
    gaps = {}
    for n in range(1, MAX_NUM + 1):
        gaps[n] = current - last_seen.get(n, -1)
    return gaps


def lag_echo_scores(hist, lag_weights=None):
    """Lag-k 回聲分數"""
    if lag_weights is None:
        lag_weights = {1: 0.5, 2: 2.0, 3: 1.0}
    scores = {n: 0.0 for n in range(1, MAX_NUM + 1)}
    for k, w in lag_weights.items():
        if len(hist) >= k:
            for n in hist[-k]['numbers']:
                if 1 <= n <= MAX_NUM:
                    scores[n] += w
    return scores


def deviation_scores(hist, window=50):
    """偏差分數"""
    recent = hist[-window:] if len(hist) > window else hist
    expected = len(recent) * PICK / MAX_NUM
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM:
                freq[n] += 1
    return {n: freq.get(n, 0) - expected for n in range(1, MAX_NUM + 1)}


def acb_scores(hist, window=100):
    """ACB 異常捕捉分數"""
    recent = hist[-window:] if len(hist) >= window else hist
    counter = Counter()
    for n in range(1, MAX_NUM + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM:
                counter[n] += 1
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            if n <= MAX_NUM:
                last_seen[n] = i
    current = len(recent)
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, MAX_NUM + 1)}
    expected_freq = len(recent) * PICK / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM + 1):
        freq_deficit = expected_freq - counter[n]
        gap_score = gaps[n] / (len(recent) / 2)
        scores[n] = freq_deficit * 0.4 + gap_score * 0.6
    return scores


def constraint_score(combo):
    """約束滿足分數"""
    score = 0
    total = sum(combo)
    # 和值 (威力彩常見 90-140)
    if 90 <= total <= 140:
        score += 1
    # 奇偶
    odd = sum(1 for n in combo if n % 2 == 1)
    if 2 <= odd <= 4:
        score += 1
    # 區間 (1-13, 14-25, 26-38)
    z = [0, 0, 0]
    for n in combo:
        if n <= 13: z[0] += 1
        elif n <= 25: z[1] += 1
        else: z[2] += 1
    if all(c >= 1 for c in z):
        score += 1
    # 尾數
    tails = set(n % 10 for n in combo)
    if len(tails) >= 4:
        score += 1
    # 連號
    s = sorted(combo)
    consec = sum(1 for i in range(len(s) - 1) if s[i + 1] - s[i] == 1)
    if consec <= 1:
        score += 1
    return score


# ===== 計算所有方法的號碼排名 =====
print("\n" + "=" * 80)
print("【一】各預測方法對實際開獎號碼的排名分析")
print("=" * 80)

f_scores = fourier_rank(history, 500)
m_scores = markov_scores(history, 30)
freq = frequency_scores(history, 100)
cold = cold_scores(history, 100)
echo = lag_echo_scores(history)
dev = deviation_scores(history, 50)
acb = acb_scores(history, 100)

methods = {
    'Fourier(w500)': f_scores,
    'Markov(w30)': m_scores,
    'Frequency(w100)': dict(freq),
    'Cold Gap(w100)': cold,
    'Lag Echo': echo,
    'Deviation(w50)': dev,
    'ACB(w100)': acb,
}

# 對每個方法做排名
all_rankings = {}
for method_name, scores_dict in methods.items():
    if isinstance(scores_dict, np.ndarray):
        ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: scores_dict[n], reverse=True)
    elif isinstance(scores_dict, Counter):
        ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: scores_dict.get(n, 0), reverse=True)
    else:
        ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: scores_dict.get(n, 0), reverse=True)

    actual_ranks = {}
    for n in ACTUAL:
        actual_ranks[n] = ranked.index(n) + 1 if n in ranked else MAX_NUM

    all_rankings[method_name] = {
        'ranked': ranked,
        'actual_ranks': actual_ranks,
        'top6': ranked[:6],
        'top12': ranked[:12],
        'top18': ranked[:18],
        'hits_top6': len(set(ranked[:6]) & set(ACTUAL)),
        'hits_top12': len(set(ranked[:12]) & set(ACTUAL)),
        'hits_top18': len(set(ranked[:18]) & set(ACTUAL)),
        'avg_rank': np.mean(list(actual_ranks.values())),
    }

# 輸出排名結果
print(f"\n{'方法':<20} {'Top6命中':>8} {'Top12命中':>9} {'Top18命中':>9} {'平均排名':>8}")
print("-" * 60)
for name, r in sorted(all_rankings.items(), key=lambda x: -x[1]['hits_top6']):
    print(f"{name:<20} {r['hits_top6']:>8} {r['hits_top12']:>9} {r['hits_top18']:>9} {r['avg_rank']:>8.1f}")

print(f"\n各方法 Top6 預測:")
for name, r in all_rankings.items():
    hits = set(r['top6']) & set(ACTUAL)
    print(f"  {name}: {r['top6']}  命中: {sorted(hits) if hits else '無'}")

print(f"\n各號碼在各方法的排名:")
print(f"{'號碼':>4}", end="")
for name in all_rankings:
    print(f" {name[:12]:>12}", end="")
print()
for n in ACTUAL:
    print(f"  {n:02d}", end="")
    for name, r in all_rankings.items():
        rank = r['actual_ranks'][n]
        marker = "★" if rank <= 6 else ("◆" if rank <= 12 else "")
        print(f" {rank:>10}{marker:>2}", end="")
    print()


# ===== 2. 模擬 PP3、Fourier 2bet、5bet Ort =====
print("\n" + "=" * 80)
print("【二】模擬各策略預測結果")
print("=" * 80)

# PP3 模擬
f_rank_indices = np.argsort(f_scores)[::-1]
idx_1 = 0
while idx_1 < len(f_rank_indices) and f_rank_indices[idx_1] == 0:
    idx_1 += 1
pp3_bet1 = sorted(f_rank_indices[idx_1:idx_1+6].tolist())

idx_2 = idx_1 + 6
while idx_2 < len(f_rank_indices) and f_rank_indices[idx_2] == 0:
    idx_2 += 1
pp3_bet2 = sorted(f_rank_indices[idx_2:idx_2+6].tolist())

exclude = set(pp3_bet1) | set(pp3_bet2)
if len(history) >= 2:
    echo_nums = [n for n in history[-2]['numbers'] if n <= MAX_NUM and n not in exclude]
else:
    echo_nums = []
remaining = [n for n in range(1, MAX_NUM + 1) if n not in exclude and n not in echo_nums]
remaining.sort(key=lambda x: freq.get(x, 0))
pp3_bet3 = sorted((echo_nums + remaining)[:6])

# 正交 4-5 注
used = set(pp3_bet1) | set(pp3_bet2) | set(pp3_bet3)
leftover = [n for n in range(1, MAX_NUM + 1) if n not in used]
leftover.sort(key=lambda x: freq.get(x, 0), reverse=True)
pp3_bet4 = sorted(leftover[:6])
pp3_bet5 = sorted(leftover[6:12])

all_bets = [pp3_bet1, pp3_bet2, pp3_bet3, pp3_bet4, pp3_bet5]
labels = ["Fourier 注1", "Fourier 注2", "Echo/Cold 注3", "正交 注4", "正交 注5"]

total_hits = 0
for i, (bet, label) in enumerate(zip(all_bets, labels)):
    hits = set(bet) & set(ACTUAL)
    nhits = len(hits)
    total_hits += nhits
    hit_str = f"命中 {sorted(hits)}" if hits else "未命中"
    print(f"  注{i+1} ({label}): {[f'{n:02d}' for n in bet]}  {hit_str} ({nhits}/6)")

print(f"\n  總覆蓋 {len(set().union(*all_bets))}/38 號")
print(f"  5注總命中: {total_hits}/6")

# 2注 Fourier Rhythm 覆蓋
fr_hits_2 = len((set(pp3_bet1) | set(pp3_bet2)) & set(ACTUAL))
print(f"  2注(Fourier) 命中: {fr_hits_2}/6")

# 3注 PP3 覆蓋
pp3_hits = len((set(pp3_bet1) | set(pp3_bet2) | set(pp3_bet3)) & set(ACTUAL))
print(f"  3注(PP3) 命中: {pp3_hits}/6")

# 特別號分析
print(f"\n  特別號預測:")
sp_freq = Counter(d.get('special', 0) for d in history[-50:] if d.get('special'))
print(f"    近50期特別號頻率: {sp_freq.most_common()}")
print(f"    實際特別號: {ACTUAL_SPECIAL}")


# ===== 3. 特徵深度分析 =====
print("\n" + "=" * 80)
print("【三】開獎特徵分析 — 為什麼沒預測到")
print("=" * 80)

# 3.1 和值分析
actual_sum = sum(ACTUAL)
recent_sums = [sum(d['numbers']) for d in history[-100:]]
sum_mean = np.mean(recent_sums)
sum_std = np.std(recent_sums)
sum_z = (actual_sum - sum_mean) / sum_std
sum_pct = sum(1 for s in recent_sums if s <= actual_sum) / len(recent_sums) * 100
print(f"\n3.1 和值分析:")
print(f"  開獎和值: {actual_sum}")
print(f"  近100期均值: {sum_mean:.1f} ± {sum_std:.1f}")
print(f"  Z-score: {sum_z:+.2f} (百分位: {sum_pct:.1f}%)")
if abs(sum_z) > 1.5:
    print(f"  ⚠️ 和值偏離 > 1.5σ — 需要結構偵測")
else:
    print(f"  ✅ 和值在正常範圍內")

# 3.2 奇偶分析
odd_count = sum(1 for n in ACTUAL if n % 2 == 1)
even_count = PICK - odd_count
recent_odds = [sum(1 for n in d['numbers'] if n % 2 == 1) for d in history[-100:]]
print(f"\n3.2 奇偶分析:")
print(f"  開獎: {odd_count}奇{even_count}偶")
print(f"  近100期奇數平均: {np.mean(recent_odds):.1f}")

# 3.3 區間分析
zones = [0, 0, 0]
for n in ACTUAL:
    if n <= 13: zones[0] += 1
    elif n <= 25: zones[1] += 1
    else: zones[2] += 1
print(f"\n3.3 區間分析:")
print(f"  低區(1-13): {zones[0]}個 {[n for n in ACTUAL if n<=13]}")
print(f"  中區(14-25): {zones[1]}個 {[n for n in ACTUAL if 14<=n<=25]}")
print(f"  高區(26-38): {zones[2]}個 {[n for n in ACTUAL if n>=26]}")

# 歷史區間分布
zone_hist = []
for d in history[-100:]:
    z = [0, 0, 0]
    for n in d['numbers']:
        if n <= 13: z[0] += 1
        elif n <= 25: z[1] += 1
        elif n <= 38: z[2] += 1
    zone_hist.append(tuple(z))
zone_counter = Counter(zone_hist)
print(f"  歷史區間分布 Top5: {zone_counter.most_common(5)}")
current_zone = tuple(zones)
pct = zone_counter.get(current_zone, 0) / len(zone_hist) * 100
print(f"  本期區間分布 {current_zone} 出現率: {pct:.1f}%")

# 3.4 連號分析
consecutive = []
for i in range(len(ACTUAL) - 1):
    if ACTUAL[i + 1] - ACTUAL[i] == 1:
        consecutive.append((ACTUAL[i], ACTUAL[i + 1]))
print(f"\n3.4 連號分析:")
print(f"  連號組: {consecutive if consecutive else '無'}")

# 3.5 尾數分析
tails = [n % 10 for n in ACTUAL]
tail_counter = Counter(tails)
print(f"\n3.5 尾數分析:")
print(f"  尾數分布: {dict(tail_counter)}")
print(f"  不同尾數數: {len(set(tails))}")

# 3.6 跨度分析
span = max(ACTUAL) - min(ACTUAL)
recent_spans = [max(d['numbers'][:6]) - min(d['numbers'][:6]) for d in history[-100:] if len(d['numbers']) >= 6]
span_mean = np.mean(recent_spans)
span_std = np.std(recent_spans)
print(f"\n3.6 跨度分析:")
print(f"  跨度: {span} (min={ACTUAL[0]}, max={ACTUAL[-1]})")
print(f"  近100期均值: {span_mean:.1f} ± {span_std:.1f}")

# 3.7 上期重複分析
prev_nums = history[-1]['numbers'] if history else []
repeat = set(ACTUAL) & set(prev_nums)
print(f"\n3.7 上期重複:")
print(f"  上期號碼: {prev_nums}")
print(f"  重複號碼: {sorted(repeat) if repeat else '無'}")

# 3.8 Lag-k 出現
print(f"\n3.8 Lag-k 回聲:")
for k in [1, 2, 3, 4, 5]:
    if len(history) >= k:
        lag_nums = history[-k]['numbers']
        overlap = set(ACTUAL) & set([n for n in lag_nums if n <= MAX_NUM])
        if overlap:
            print(f"  Lag-{k}: {sorted(overlap)} (來自{history[-k]['draw']}期 {lag_nums})")

# 3.9 個別號碼冷熱分析
print(f"\n3.9 個別號碼近期態勢:")
for n in ACTUAL:
    f_rank = sorted(range(1, MAX_NUM + 1), key=lambda x: f_scores[x], reverse=True).index(n) + 1
    gap = cold[n]
    recent_freq = freq.get(n, 0)
    echo_val = echo.get(n, 0)
    dev_val = dev.get(n, 0)
    detail = f"#{n:02d}: Fourier排名={f_rank}, Gap={gap}期, 100期頻率={recent_freq}, 偏差={dev_val:+.1f}"
    if echo_val > 0:
        detail += f", Echo={echo_val:.1f}"
    if f_rank <= 6:
        detail += " ★Top6"
    elif f_rank <= 12:
        detail += " ◆Top12"
    print(f"  {detail}")


# ===== 4. 混合方法評分 =====
print("\n" + "=" * 80)
print("【四】混合方法評分 — 哪種組合能更好預測")
print("=" * 80)

# 正規化所有分數到 [0,1]
def normalize(scores_dict):
    if isinstance(scores_dict, np.ndarray):
        vals = {n: scores_dict[n] for n in range(1, MAX_NUM + 1)}
    elif isinstance(scores_dict, Counter):
        vals = {n: scores_dict.get(n, 0) for n in range(1, MAX_NUM + 1)}
    else:
        vals = {n: scores_dict.get(n, 0) for n in range(1, MAX_NUM + 1)}
    max_v = max(vals.values()) if max(vals.values()) != 0 else 1
    min_v = min(vals.values())
    rng = max_v - min_v if max_v != min_v else 1
    return {n: (v - min_v) / rng for n, v in vals.items()}

norm_fourier = normalize(f_scores)
norm_markov = normalize(m_scores)
norm_freq = normalize(dict(freq))
norm_cold = normalize(cold)
norm_echo = normalize(echo)
norm_dev = normalize(dev)
norm_acb = normalize(acb)

# 嘗試多種權重組合
weight_configs = {
    'F+M (0.5/0.5)': {'fourier': 0.5, 'markov': 0.5},
    'F+Cold (0.5/0.5)': {'fourier': 0.5, 'cold': 0.5},
    'F+M+Echo (0.4/0.3/0.3)': {'fourier': 0.4, 'markov': 0.3, 'echo': 0.3},
    'F+ACB (0.5/0.5)': {'fourier': 0.5, 'acb': 0.5},
    'All Equal': {'fourier': 1/7, 'markov': 1/7, 'freq': 1/7, 'cold': 1/7, 'echo': 1/7, 'dev': 1/7, 'acb': 1/7},
    'F+M+Cold (0.4/0.3/0.3)': {'fourier': 0.4, 'markov': 0.3, 'cold': 0.3},
    'ACB+Cold (0.5/0.5)': {'acb': 0.5, 'cold': 0.5},
    'F+Echo+Cold (0.4/0.3/0.3)': {'fourier': 0.4, 'echo': 0.3, 'cold': 0.3},
    'F-heavy (0.6/0.2/0.2)': {'fourier': 0.6, 'markov': 0.2, 'cold': 0.2},
    'Markov+Echo (0.5/0.5)': {'markov': 0.5, 'echo': 0.5},
}

norm_map = {
    'fourier': norm_fourier,
    'markov': norm_markov,
    'freq': norm_freq,
    'cold': norm_cold,
    'echo': norm_echo,
    'dev': norm_dev,
    'acb': norm_acb,
}

print(f"\n{'配置':<30} {'Top6命中':>8} {'Top12命中':>9} {'平均排名':>8}")
print("-" * 60)
for config_name, weights in weight_configs.items():
    combined = {}
    for n in range(1, MAX_NUM + 1):
        combined[n] = 0
        for method, w in weights.items():
            combined[n] += norm_map[method][n] * w
    ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: combined[n], reverse=True)
    hits6 = len(set(ranked[:6]) & set(ACTUAL))
    hits12 = len(set(ranked[:12]) & set(ACTUAL))
    avg_rank = np.mean([ranked.index(n) + 1 for n in ACTUAL])
    print(f"  {config_name:<28} {hits6:>8} {hits12:>9} {avg_rank:>8.1f}")


# ===== 5. 2注/3注可行性分析 =====
print("\n" + "=" * 80)
print("【五】2注/3注 覆蓋率可行性")
print("=" * 80)

# 計算每注預期命中 (基準)
print(f"\n  隨機基準:")
print(f"    1注: C(6,1)*C(32,5)/C(38,6) ≈ 3.87%  (命中≥1/6)")
print(f"    2注: ~7.59%")
print(f"    3注: ~11.17%")

# 用不同方法生成 2注
print(f"\n  === 2注方案設計 ===")
two_bet_configs = {
    '方案A: F注1 + F注2 (正交Fourier)': (pp3_bet1, pp3_bet2),
    '方案B: F注1 + Echo/Cold': (pp3_bet1, pp3_bet3),
    '方案C: F注1 + ACB注': None,  # 動態生成
}

# 方案C: ACB注
acb_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: acb.get(n, 0), reverse=True)
acb_bet = sorted(acb_ranked[:6])
two_bet_configs['方案C: F注1 + ACB注'] = (pp3_bet1, acb_bet)

# 方案D: Markov + Cold
mk_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: m_scores.get(n, 0), reverse=True)
mk_bet = sorted(mk_ranked[:6])
cold_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: cold.get(n, 0), reverse=True)
cold_bet = sorted([n for n in cold_ranked if n not in mk_bet][:6])
two_bet_configs['方案D: Markov + Cold'] = (mk_bet, cold_bet)

for name, (b1, b2) in two_bet_configs.items():
    h1 = set(b1) & set(ACTUAL)
    h2 = set(b2) & set(ACTUAL)
    total = len(h1 | h2)
    print(f"\n  {name}")
    print(f"    注1: {b1}  命中: {sorted(h1) if h1 else '無'}")
    print(f"    注2: {b2}  命中: {sorted(h2) if h2 else '無'}")
    print(f"    覆蓋: {len(set(b1)|set(b2))}/38  總命中: {total}/6")


# ===== 6. 歷史模式匹配 =====
print("\n" + "=" * 80)
print("【六】歷史模式比對 — 類似開獎結果分析")
print("=" * 80)

actual_set = set(ACTUAL)
best_overlap = 0
best_matches = []
for d in history:
    overlap = len(actual_set & set(d['numbers'][:6]))
    if overlap >= 3:
        best_matches.append((overlap, d))
    best_overlap = max(best_overlap, overlap)

best_matches.sort(key=lambda x: -x[0])
print(f"\n  歷史最高重疊: {best_overlap}/6")
print(f"  重疊≥3的期數: {len(best_matches)}")
for overlap, d in best_matches[:10]:
    common = sorted(actual_set & set(d['numbers'][:6]))
    print(f"    {d['draw']} → {d['numbers'][:6]}  共同: {common} ({overlap}/6)")


# ===== 7. Sum Regime 分析 =====
print("\n" + "=" * 80)
print("【七】Sum Regime 狀態分析")
print("=" * 80)

recent_sums_10 = [sum(d['numbers'][:6]) for d in history[-10:]]
last_sum = recent_sums_10[-1] if recent_sums_10 else 0
above_mean_count = sum(1 for s in recent_sums_10 if s > sum_mean)
below_mean_count = 10 - above_mean_count
print(f"  近10期和值: {recent_sums_10}")
print(f"  均值: {sum_mean:.1f}")
print(f"  連續高於均值: {above_mean_count}/10")
print(f"  連續低於均值: {below_mean_count}/10")

# 檢測 regime
if above_mean_count >= 7:
    print(f"  ⚠️ HIGH REGIME — 預期均值回歸 → 應boost低號")
elif below_mean_count >= 7:
    print(f"  ⚠️ LOW REGIME — 預期均值回歸 → 應boost高號")
else:
    print(f"  ✅ NEUTRAL — 無極端regime")

# 上期分析
if history:
    prev = history[-1]
    prev_sum = sum(prev['numbers'][:6])
    prev_z = (prev_sum - sum_mean) / sum_std
    print(f"\n  上期和值: {prev_sum} (Z={prev_z:+.2f})")
    print(f"  本期和值: {actual_sum} (Z={sum_z:+.2f})")
    print(f"  和值變化: {actual_sum - prev_sum:+d}")


# ===== 8. 特別號深度分析 =====
print("\n" + "=" * 80)
print("【八】特別號分析")
print("=" * 80)

sp_hist_all = [d.get('special', 0) for d in history if d.get('special')]
sp_freq_50 = Counter(d.get('special', 0) for d in history[-50:] if d.get('special'))
sp_freq_20 = Counter(d.get('special', 0) for d in history[-20:] if d.get('special'))
sp_last_seen = {}
for i, d in enumerate(history):
    sp = d.get('special')
    if sp:
        sp_last_seen[sp] = i
current_idx = len(history)
sp_gaps = {n: current_idx - sp_last_seen.get(n, -1) for n in range(1, 9)}

print(f"  近50期頻率: {dict(sp_freq_50)}")
print(f"  近20期頻率: {dict(sp_freq_20)}")
print(f"  當前Gap: {sp_gaps}")
print(f"  實際開獎: {ACTUAL_SPECIAL}")
print(f"  #{ACTUAL_SPECIAL} Gap: {sp_gaps.get(ACTUAL_SPECIAL, '?')}期")

# V3 MAB 分析
try:
    from models.special_predictor import PowerLottoSpecialPredictor
    rules = {'name': 'POWER_LOTTO', 'specialMinNumber': 1, 'specialMaxNumber': 8}
    sp_pred = PowerLottoSpecialPredictor(rules)
    sp_top = sp_pred.predict_top_n(history, n=3)
    print(f"  V3 MAB 預測: {sp_top}")
    if ACTUAL_SPECIAL in sp_top:
        print(f"  ✅ 特別號命中!")
    else:
        print(f"  ❌ 特別號未命中")
except Exception as e:
    print(f"  V3 MAB 載入失敗: {e}")


# ===== 9. 短中長期特徵比較 =====
print("\n" + "=" * 80)
print("【九】短中長期特徵窗口比較")
print("=" * 80)

for window in [10, 30, 50, 100, 200, 500]:
    f_sc = fourier_rank(history, window)
    f_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: f_sc[n], reverse=True)
    hits6 = len(set(f_ranked[:6]) & set(ACTUAL))
    hits12 = len(set(f_ranked[:12]) & set(ACTUAL))
    avg_r = np.mean([f_ranked.index(n) + 1 for n in ACTUAL])

    m_sc = markov_scores(history, window)
    m_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: m_sc.get(n, 0), reverse=True)
    m_hits6 = len(set(m_ranked[:6]) & set(ACTUAL))

    freq_w = frequency_scores(history, window)
    freq_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: freq_w.get(n, 0), reverse=True)
    freq_hits6 = len(set(freq_ranked[:6]) & set(ACTUAL))

    print(f"  Window={window:>3}: Fourier h6={hits6} h12={hits12} avgR={avg_r:.1f} | Markov h6={m_hits6} | Freq h6={freq_hits6}")


# ===== 10. 號碼組合結構分析 =====
print("\n" + "=" * 80)
print("【十】號碼結構可識別性分析")
print("=" * 80)

# 10.1 號差序列
diffs = [ACTUAL[i+1] - ACTUAL[i] for i in range(len(ACTUAL) - 1)]
print(f"  號差序列: {diffs}")
print(f"  最大gap: {max(diffs)}, 最小gap: {min(diffs)}")

# 10.2 與歷史差異序列比較
diff_patterns = []
for d in history[-200:]:
    nums = sorted(d['numbers'][:6])
    if len(nums) == 6:
        df = [nums[i+1] - nums[i] for i in range(5)]
        diff_patterns.append(df)
diff_arr = np.array(diff_patterns) if diff_patterns else np.zeros((1, 5))
mean_diff = np.mean(diff_arr, axis=0)
std_diff = np.std(diff_arr, axis=0)
print(f"  歷史平均號差: {[f'{m:.1f}' for m in mean_diff]}")
print(f"  歷史std號差:  {[f'{s:.1f}' for s in std_diff]}")
diff_z = [(d - m) / s if s > 0 else 0 for d, m, s in zip(diffs, mean_diff, std_diff)]
print(f"  本期Z-score:  {[f'{z:+.2f}' for z in diff_z]}")

# 10.3 末位數模式
tail_pattern = [n % 10 for n in ACTUAL]
print(f"\n  末位數模式: {tail_pattern}")

# 10.4 十位數模式
tens_pattern = [n // 10 for n in ACTUAL]
print(f"  十位數模式: {tens_pattern}")

# 10.5 素數分析
primes = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37}
prime_count = sum(1 for n in ACTUAL if n in primes)
print(f"  素數個數: {prime_count}/6 ({[n for n in ACTUAL if n in primes]})")

print("\n" + "=" * 80)
print("【完成】分析結束")
print("=" * 80)
