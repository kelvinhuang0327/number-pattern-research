#!/usr/bin/env python3
"""分析115000016期威力彩開獎結果 vs 各預測方法"""
import sys, os, json
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

# === Step 1: Load data ===
db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))

print(f"Total POWER_LOTTO draws: {len(draws)}")
print(f"Latest draw: {draws[-1]['draw']} ({draws[-1]['date']})")
print()

# Draw 115000016 not yet in DB - use user-provided data
target = {
    'draw': '115000016',
    'date': '2026/02/23',
    'numbers': [4, 10, 13, 24, 31, 35],
    'special': None,  # User didn't provide special number
}
target_idx = len(draws)  # It would be next after all existing draws

actual_numbers = set(target['numbers'])
actual_special = target.get('special', None)
print(f"=== 第 {target['draw']}期 ===")
print(f"開獎日期: {target['date']}")
print(f"開獎號碼: {sorted(target['numbers'])}")
print(f"特別號: {actual_special} (未提供)")
print(f"使用 {len(draws)} 期歷史數據進行預測")
print()

# Show recent draws (training context)
print("=== 近期數據 (訓練集末尾) ===")
for d in draws[-8:]:
    print(f"  {d['draw']} ({d['date']}): {sorted(d['numbers'])} sp={d.get('special','')}")
print(f"  115000016 (2026/02/23): {sorted(target['numbers'])} <<<< TARGET")
print()

# === Step 2: What would each method predict? ===
hist = draws  # All existing data is before target
print(f"Training data: {len(hist)} draws (before {target['draw']})")
print()

# --- Method 1: Fourier Rhythm 2-bet ---
print("=" * 70)
print("Method 1: Fourier Rhythm 2注")
print("=" * 70)
try:
    from tools.power_fourier_rhythm import fourier_rhythm_predict
    bets_fr2 = fourier_rhythm_predict(hist, n_bets=2, window=500)
    for i, bet in enumerate(bets_fr2):
        hits = set(bet) & actual_numbers
        print(f"  注{i+1}: {sorted(bet)} → 命中: {sorted(hits)} ({len(hits)}個)")
    all_fr2 = set(n for b in bets_fr2 for n in b)
    total_hits_fr2 = len(all_fr2 & actual_numbers)
    print(f"  2注合計覆蓋: {len(all_fr2)}號, 命中: {total_hits_fr2}")
    m3_fr2 = any(len(set(b) & actual_numbers) >= 3 for b in bets_fr2)
    print(f"  M3+: {'YES' if m3_fr2 else 'NO'}")
except Exception as e:
    print(f"  Error: {e}")
    import traceback; traceback.print_exc()

print()

# --- Method 2: Power Precision 3-bet ---
print("=" * 70)
print("Method 2: Power Precision 3注")
print("=" * 70)
try:
    from tools.predict_power_precision_3bet import generate_power_precision_3bet
    bets_pp3 = generate_power_precision_3bet(hist)
    for i, bet in enumerate(bets_pp3):
        label = ["Fourier Top6", "Fourier 7-12", "Echo/Cold"][i]
        hits = set(bet) & actual_numbers
        print(f"  注{i+1} ({label}): {sorted(bet)} → 命中: {sorted(hits)} ({len(hits)}個)")
    all_pp3 = set(n for b in bets_pp3 for n in b)
    total_hits_pp3 = len(all_pp3 & actual_numbers)
    print(f"  3注合計覆蓋: {len(all_pp3)}號, 命中: {total_hits_pp3}")
    m3_pp3 = any(len(set(b) & actual_numbers) >= 3 for b in bets_pp3)
    print(f"  M3+: {'YES' if m3_pp3 else 'NO'}")
except Exception as e:
    print(f"  Error: {e}")
    import traceback; traceback.print_exc()

print()

# --- Method 3: Special Number V3 ---
print("=" * 70)
print("Method 3: 特別號 V3 MAB")
print("=" * 70)
try:
    from models.special_predictor import PowerLottoSpecialPredictor
    rules = {'name': 'POWER_LOTTO', 'specialMinNumber': 1, 'specialMaxNumber': 8}
    sp_pred = PowerLottoSpecialPredictor(rules)
    sp_result = sp_pred.predict_v3(hist)
    sp_top3 = sp_pred.predict_top_n(hist, n=3)
    print(f"  V3 預測: {sp_result}")
    print(f"  Top 3: {sp_top3}")
    print(f"  實際特別號: {actual_special}")
    print(f"  命中: {'YES' if sp_result == actual_special else 'NO'}")
    print(f"  在Top3中: {'YES' if actual_special in sp_top3 else 'NO'}")
except Exception as e:
    print(f"  Error: {e}")
    import traceback; traceback.print_exc()

print()

# === Step 3: Number analysis ===
print("=" * 70)
print("開獎號碼特徵分析")
print("=" * 70)
actual_sorted = sorted(target['numbers'])
sum_val = sum(actual_sorted)
odd_count = sum(1 for n in actual_sorted if n % 2 == 1)
big_count = sum(1 for n in actual_sorted if n >= 20)
gaps = [actual_sorted[i+1] - actual_sorted[i] for i in range(len(actual_sorted)-1)]
zones = {
    'Z1(1-10)': sum(1 for n in actual_sorted if 1 <= n <= 10),
    'Z2(11-20)': sum(1 for n in actual_sorted if 11 <= n <= 20),
    'Z3(21-30)': sum(1 for n in actual_sorted if 21 <= n <= 30),
    'Z4(31-38)': sum(1 for n in actual_sorted if 31 <= n <= 38),
}
tails = Counter([n % 10 for n in actual_sorted])

print(f"  號碼: {actual_sorted}")
print(f"  和值: {sum_val}")
print(f"  奇偶比: {odd_count}:{6-odd_count}")
print(f"  大小比: {big_count}:{6-big_count} (>=20為大)")
print(f"  號碼間距: {gaps}")
print(f"  區間分布: {zones}")
print(f"  尾數分布: {dict(tails)}")
print()

# === Step 4: Historical frequency analysis ===
print("=" * 70)
print("歷史頻率分析 (近100期)")
print("=" * 70)
recent100 = hist[-100:]
freq100 = Counter()
for d in recent100:
    for n in d['numbers']:
        freq100[n] += 1

expected_freq = 100 * 6 / 38
print(f"  期望頻率: {expected_freq:.2f}")
print()
print("  開獎號碼在近100期的頻率:")
for n in actual_sorted:
    f = freq100.get(n, 0)
    deviation = f - expected_freq
    status = "過熱" if deviation > 3 else ("冰冷" if deviation < -3 else "正常")
    print(f"    號碼{n:02d}: 出現{f}次 (偏差{deviation:+.1f}) [{status}]")

print()

# Lag analysis
print("  Lag 分析 (距上次出現幾期):")
for n in actual_sorted:
    lag = None
    for j in range(len(hist)-1, -1, -1):
        if n in hist[j]['numbers']:
            lag = len(hist) - j
            break
    if lag is None:
        print(f"    號碼{n:02d}: 從未出現")
    else:
        print(f"    號碼{n:02d}: Lag={lag}")

print()

# === Step 5: Echo analysis (N-2) ===
print("=" * 70)
print("回聲分析 (Lag-2)")
print("=" * 70)
if len(hist) >= 2:
    prev1 = hist[-1]
    prev2 = hist[-2]
    print(f"  N-1期 ({prev1['draw']}): {sorted(prev1['numbers'])}")
    print(f"  N-2期 ({prev2['draw']}): {sorted(prev2['numbers'])}")
    echo_from_n2 = set(prev2['numbers']) & actual_numbers
    echo_from_n1 = set(prev1['numbers']) & actual_numbers
    print(f"  回聲自N-1: {sorted(echo_from_n1)} ({len(echo_from_n1)}個)")
    print(f"  回聲自N-2: {sorted(echo_from_n2)} ({len(echo_from_n2)}個)")

print()

# === Step 6: Fourier score details per ball ===
print("=" * 70)
print("Fourier 節奏分析 (各號碼得分)")
print("=" * 70)
try:
    from scipy.fft import fft as scipy_fft, fftfreq as scipy_fftfreq
    window = 500
    h_slice = hist[-window:] if len(hist) >= window else hist
    w = len(h_slice)
    max_num = 38
    
    bitstreams = {i: np.zeros(w) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= max_num:
                bitstreams[n][idx] = 1
    
    fourier_scores = {}
    for n in range(1, max_num + 1):
        bh = bitstreams[n]
        if sum(bh) < 2:
            fourier_scores[n] = 0
            continue
        yf = scipy_fft(bh - np.mean(bh))
        xf = scipy_fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            fourier_scores[n] = 0
            continue
        period = 1 / freq_val
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        score = 1.0 / (abs(gap - period) + 1.0)
        fourier_scores[n] = score
    
    ranked = sorted(fourier_scores.items(), key=lambda x: -x[1])
    for rank, (n, s) in enumerate(ranked, 1):
        marker = " ★ ACTUAL" if n in actual_numbers else ""
        print(f"  Rank {rank:2d}: 號碼{n:02d} (score={s:.4f}){marker}")
        if rank >= 24: break  # Top 24
    
    # Where do actual numbers rank?
    print()
    print("  開獎號碼的 Fourier 排名:")
    rank_map = {n: rank+1 for rank, (n, _) in enumerate(ranked)}
    for n in actual_sorted:
        r = rank_map.get(n, 99)
        in_bet = ""
        if r <= 6: in_bet = " [注1]"
        elif r <= 12: in_bet = " [注2]"
        elif r <= 18: in_bet = " [注3-PP3 Fourier]"
        print(f"    號碼{n:02d}: 排名 #{r}{in_bet}")

except Exception as e:
    print(f"  Error: {e}")
    import traceback; traceback.print_exc()

print()

# === Step 7: What features did this draw have that were unusual? ===
print("=" * 70)
print("異常特徵檢測")
print("=" * 70)

# Sum value distribution
recent_sums = [sum(d['numbers']) for d in hist[-200:]]
mean_sum = np.mean(recent_sums)
std_sum = np.std(recent_sums)
z_sum = (sum_val - mean_sum) / std_sum
print(f"  和值 {sum_val}: z-score = {z_sum:.2f} (mean={mean_sum:.1f}, std={std_sum:.1f})")

# Consecutive/gap patterns
has_consecutive = any(g == 1 for g in gaps)
max_gap = max(gaps)
print(f"  有連號: {'是' if has_consecutive else '否'}")
print(f"  最大間距: {max_gap}")

# Tail repeat
tail_counts = Counter(n % 10 for n in actual_sorted)
max_tail_repeat = max(tail_counts.values())
print(f"  同尾數最多: {max_tail_repeat}個")

# Zone balance
zone_vals = list(zones.values())
zone_std = np.std(zone_vals)
print(f"  區間標準差: {zone_std:.2f} (越小越均勻)")

# Prior hot/cold
recent50 = hist[-50:]
freq50 = Counter()
for d in recent50:
    for n in d['numbers']:
        freq50[n] += 1
hot_nums = {n for n, c in freq50.most_common(10)}
cold_nums = set(range(1, 39)) - set(freq50.keys()) | {n for n, c in freq50.items() if c <= 3}
hot_hit = actual_numbers & hot_nums
cold_hit = actual_numbers & cold_nums
print(f"  熱號(Top10近50期) 命中: {sorted(hot_hit)} ({len(hot_hit)}個)")
print(f"  冷號(近50期<=3次) 命中: {sorted(cold_hit)} ({len(cold_hit)}個)")

print()
print("=== 分析完成 ===")
