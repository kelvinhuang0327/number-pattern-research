#!/usr/bin/env python3
"""
=============================================================================
今彩539 結構特徵升級 — 全階段實作 + 標準回測
=============================================================================
Phase 1: Zone跳躍偵測器, 等差偵測器, 異常捕捉注 (ACB)
Phase 2: Multi-Signal Fusion v2, 最佳2注/3注正交組合
Phase 3: Sliding Window Auto-Tune, Combinatorial Feature ML

回測標準: 三窗口 (150/500/1500), Permutation Test, McNemar
=============================================================================
"""

import json, math, sqlite3, sys, os, time
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations
import math as _math

class _NormDist:
    """Minimal normal distribution (no scipy needed)"""
    @staticmethod
    def cdf(x):
        return 0.5 * _math.erfc(-x / _math.sqrt(2))

_base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_base, '..', 'lottery_api'))
sys.path.insert(0, os.path.join(_base, '..'))

# ═══════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════
POOL = 39
PICK = 5

from math import comb
C39_5 = comb(39, 5)

def _p_match_exactly(k):
    return comb(5, k) * comb(34, 5 - k) / C39_5

P_MATCH = {k: _p_match_exactly(k) for k in range(6)}
P_GE2_1 = sum(P_MATCH[k] for k in range(2, 6))   # ~0.1140
P_GE3_1 = sum(P_MATCH[k] for k in range(3, 6))   # ~0.01004

def baseline_n_bet(n, min_hits=2):
    p1 = P_GE2_1 if min_hits == 2 else P_GE3_1
    return 1 - (1 - p1) ** n

# ═══════════════════════════════════════════════════════════════════
#  DATA
# ═══════════════════════════════════════════════════════════════════
DB_PATH = os.path.join(_base, '..', 'lottery_api', 'data', 'lottery_v2.db')
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(_base, '..', 'lottery_v2.db')

def load_draws():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = 'DAILY_539'
        ORDER BY date ASC, draw ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    draws = []
    for draw_id, date, numbers_str in rows:
        nums = json.loads(numbers_str)
        draws.append({'draw': draw_id, 'date': date, 'numbers': sorted(nums)})
    return draws

def get_numbers(draw):
    return draw['numbers']

# ═══════════════════════════════════════════════════════════════════
#  EXISTING BASELINE METHODS (for comparison)
# ═══════════════════════════════════════════════════════════════════

def method_state_space(hist, window=300):
    """State space model (best single method from research)"""
    recent = hist[-window:] if len(hist) >= window else hist
    scores = {}
    for n in range(1, POOL + 1):
        series = [1 if n in d['numbers'] else 0 for d in recent]
        trans = {'00': 0, '01': 0, '10': 0, '11': 0}
        for i in range(1, len(series)):
            key = f"{series[i-1]}{series[i]}"
            trans[key] += 1
        last_state = series[-1]
        total_from = trans[f'{last_state}0'] + trans[f'{last_state}1']
        scores[n] = trans[f'{last_state}1'] / total_from if total_from > 0 else 0.5
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK])

def method_markov(hist, window=30):
    """Markov transition"""
    recent = hist[-window:] if len(hist) >= window else hist
    if len(recent) < 5:
        return list(range(1, PICK + 1))
    transition = np.zeros((POOL, POOL))
    for i in range(len(recent) - 1):
        for a in recent[i]['numbers']:
            for b in recent[i + 1]['numbers']:
                transition[a - 1][b - 1] += 1
    row_sums = transition.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    transition /= row_sums
    scores = np.zeros(POOL)
    for n in recent[-1]['numbers']:
        scores += transition[n - 1]
    ranked = np.argsort(-scores)
    return sorted([int(idx + 1) for idx in ranked[:PICK]])

def method_fourier(hist, window=500):
    """Fourier rhythm"""
    recent = hist[-window:] if len(hist) >= window else hist
    scores = {}
    for n in range(1, POOL + 1):
        series = np.array([1 if n in d['numbers'] else 0 for d in recent], dtype=float)
        fft_vals = np.fft.rfft(series)
        power = np.abs(fft_vals) ** 2
        if len(power) > 1:
            dom = np.argmax(power[1:]) + 1
            phase = np.angle(fft_vals[dom])
            freq = dom / len(series)
            t_next = len(series)
            predicted = np.abs(fft_vals[dom]) * np.cos(2 * np.pi * freq * t_next + phase)
            base = series.mean()
            scores[n] = base + 0.3 * predicted / (len(series) ** 0.5)
        else:
            scores[n] = 0
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK])

def method_cold(hist, window=100):
    """Cold numbers"""
    recent = hist[-window:] if len(hist) >= window else hist
    counter = Counter()
    for n in range(1, POOL + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    bottom = [x[0] for x in counter.most_common()[::-1][:PICK]]
    return sorted(bottom)

def method_gap(hist, window=200):
    """Gap analysis"""
    recent = hist[-window:] if len(hist) >= window else hist
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(recent)
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, POOL + 1)}
    ranked = sorted(gaps, key=lambda x: -gaps[x])
    return sorted(ranked[:PICK])

def method_frequency(hist, window=100):
    """Hot frequency"""
    recent = hist[-window:]
    counter = Counter()
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    return sorted([x[0] for x in counter.most_common(PICK)])

# ═══════════════════════════════════════════════════════════════════
#  PHASE 1: NEW STRUCTURAL METHODS
# ═══════════════════════════════════════════════════════════════════

def method_zone_jump_detector(hist, window=100):
    """
    P1-1: Zone跳躍偵測器
    偵測近期zone缺席趨勢，選擇「即將回歸」的zone中的號碼
    Zones: Z1(1-13), Z2(14-26), Z3(27-39)
    """
    recent = hist[-window:] if len(hist) >= window else hist
    
    # 計算近期每10期的zone分佈
    zone_history = []
    chunk_size = 10
    for start in range(0, len(recent), chunk_size):
        chunk = recent[start:start+chunk_size]
        zc = Counter()
        for d in chunk:
            for n in d['numbers']:
                if n <= 13: zc[0] += 1
                elif n <= 26: zc[1] += 1
                else: zc[2] += 1
        zone_history.append(zc)
    
    # 計算最近3個chunk中各zone的頻率趨勢
    if len(zone_history) < 3:
        return method_cold(hist, window)
    
    last3 = zone_history[-3:]
    zone_deficit = {}
    for z in range(3):
        recent_freq = sum(ch.get(z, 0) for ch in last3) / 3
        total_freq = sum(ch.get(z, 0) for ch in zone_history) / len(zone_history)
        zone_deficit[z] = total_freq - recent_freq  # 正=近期偏低
    
    # 找出最缺席的zone，從中選號
    zones = {0: range(1, 14), 1: range(14, 27), 2: range(27, 40)}
    
    # 分配: 最缺席zone多選，其他少選
    ranked_zones = sorted(zone_deficit, key=lambda z: -zone_deficit[z])
    allocations = {ranked_zones[0]: 3, ranked_zones[1]: 1, ranked_zones[2]: 1}
    
    # 在每個zone內用gap排序
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(recent)
    
    result = []
    for z in ranked_zones:
        zone_nums = list(zones[z])
        zone_gaps = {n: current - last_seen.get(n, -1) for n in zone_nums}
        # 按gap大小排列 (最久未出的優先)
        ranked_in_zone = sorted(zone_gaps, key=lambda n: -zone_gaps[n])
        result.extend(ranked_in_zone[:allocations[z]])
    
    return sorted(result[:PICK])

def method_arithmetic_detector(hist, window=200):
    """
    P1-2: 等差/等比序列偵測器
    偵測近期等差子序列的出現頻率，選擇可能組成等差的號碼
    """
    recent = hist[-window:] if len(hist) >= window else hist
    
    # 統計所有公差d的等差對出現頻率
    diff_freq = Counter()  # (start_num, diff) -> count
    for d in recent:
        nums = sorted(d['numbers'])
        for i in range(len(nums)):
            for j in range(i+1, len(nums)):
                diff = nums[j] - nums[i]
                diff_freq[diff] += 1
    
    # 找出最活躍的公差
    top_diffs = [d for d, _ in diff_freq.most_common(5)]
    
    # 用Markov預測下一期最可能的「起始號碼」
    last_nums = set(recent[-1]['numbers'])
    
    # 對每個號碼計算「等差友好分數」
    scores = {}
    for n in range(1, POOL + 1):
        score = 0
        for d in top_diffs:
            # 檢查 n 能否與pool中其他號碼構成等差
            partners = 0
            for k in range(1, 4):  # 最多3步等差
                if 1 <= n + k * d <= POOL: partners += 1
                if 1 <= n - k * d >= 1: partners += 1
            score += partners * diff_freq[d]
        
        # 冷號加權 (久未出的號碼如果等差分數高，選擇價值更大)
        gap = 0
        for i in range(len(recent) - 1, -1, -1):
            if n in recent[i]['numbers']:
                gap = len(recent) - 1 - i
                break
            gap = len(recent)
        
        scores[n] = score * (1 + 0.01 * gap)
    
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK])

def method_spacing_profile(hist, window=300):
    """
    P1-3: 間距Profile匹配
    分析歷史間距分佈，選擇符合常見間距模式的號碼組合
    """
    recent = hist[-window:] if len(hist) >= window else hist
    
    # 計算歷史間距模式分佈
    spacing_counter = Counter()
    for d in recent:
        nums = sorted(d['numbers'])
        spacings = tuple(nums[i+1] - nums[i] for i in range(len(nums)-1))
        spacing_counter[spacings] += 1
    
    # 找出最常見的間距模式(取Top 20)
    common_patterns = spacing_counter.most_common(20)
    
    # 用頻率+gap混合分數選候選號碼
    counter = Counter()
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(recent)
    
    # 混合分數: 頻率(normalized) + gap(normalized)
    max_freq = max(counter.values()) if counter else 1
    hybrid_scores = {}
    for n in range(1, POOL + 1):
        freq_norm = counter.get(n, 0) / max_freq
        gap = current - last_seen.get(n, -1)
        gap_norm = gap / current
        hybrid_scores[n] = 0.5 * freq_norm + 0.5 * gap_norm
    
    # 從候選中找出最符合常見間距模式的組合
    candidates = sorted(hybrid_scores, key=lambda x: -hybrid_scores[x])[:20]
    
    best_combo = None
    best_score = -1
    
    for combo in combinations(candidates, PICK):
        nums = sorted(combo)
        spacings = tuple(nums[i+1] - nums[i] for i in range(len(nums)-1))
        
        # 計算與常見模式的相似度
        sim_score = 0
        for pat, cnt in common_patterns:
            dist = sum(abs(a - b) for a, b in zip(spacings, pat))
            sim_score += cnt / (1 + dist)
        
        # 加上號碼本身的分數
        num_score = sum(hybrid_scores[n] for n in combo)
        total = sim_score * 0.3 + num_score * 0.7
        
        if total > best_score:
            best_score = total
            best_combo = combo
    
    return sorted(list(best_combo)) if best_combo else sorted(candidates[:PICK])

def method_anomaly_capture(hist, window=100):
    """
    P1-4: 異常捕捉注 (Anomaly Capture Bet, ACB)
    專門捕捉「不太可能」的組合：冷號+邊界號+跳zone
    """
    recent = hist[-window:] if len(hist) >= window else hist
    
    # 號碼頻率
    counter = Counter()
    for n in range(1, POOL + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    
    # Gap
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(recent)
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, POOL + 1)}
    
    # 異常分數: 頻率越低 + gap越大 = 越「異常」但可能回歸
    expected_freq = len(recent) * PICK / POOL
    scores = {}
    for n in range(1, POOL + 1):
        freq_deficit = expected_freq - counter[n]  # 正=偏低
        gap_score = gaps[n] / (len(recent) / 2)    # 正規化
        
        # 邊界號碼加權 (1-5, 35-39)
        boundary_bonus = 1.2 if (n <= 5 or n >= 35) else 1.0
        
        # 3的倍數加權 (根據分析)
        mod3_bonus = 1.1 if n % 3 == 0 else 1.0
        
        scores[n] = (freq_deficit * 0.4 + gap_score * 0.6) * boundary_bonus * mod3_bonus
    
    # 選Top，但確保跨zone
    ranked = sorted(scores, key=lambda x: -scores[x])
    
    # 強制跨zone: 至少從2個不同zone選取
    zones_selected = set()
    result = []
    for n in ranked:
        zone = 0 if n <= 13 else (1 if n <= 26 else 2)
        if len(result) < PICK:
            result.append(n)
            zones_selected.add(zone)
        if len(result) >= PICK:
            break
    
    # 如果只有1個zone，強制替換
    if len(zones_selected) < 2 and len(result) >= PICK:
        missing_zones = set(range(3)) - zones_selected
        for mz in missing_zones:
            zone_range = range(1, 14) if mz == 0 else (range(14, 27) if mz == 1 else range(27, 40))
            zone_candidates = sorted([n for n in zone_range], key=lambda x: -scores[x])
            if zone_candidates:
                result[-1] = zone_candidates[0]
                break
    
    return sorted(result[:PICK])

# ═══════════════════════════════════════════════════════════════════
#  PHASE 2: FUSION & ORTHOGONAL STRATEGIES
# ═══════════════════════════════════════════════════════════════════

def method_multi_signal_fusion_v2(hist, window=200):
    """
    P2-1: Multi-Signal Fusion v2
    四維融合: 頻率 + Gap + Markov + 結構(zone+間距)
    """
    recent = hist[-window:] if len(hist) >= window else hist
    
    # Dim 1: Frequency score
    counter = Counter()
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    max_freq = max(counter.values()) if counter else 1
    freq_scores = {n: counter.get(n, 0) / max_freq for n in range(1, POOL + 1)}
    
    # Dim 2: Gap score
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(recent)
    gap_scores = {}
    for n in range(1, POOL + 1):
        gap = current - last_seen.get(n, -1)
        # 用歷史平均gap正規化
        appearances = [i for i, d in enumerate(recent) if n in d['numbers']]
        if len(appearances) >= 2:
            avg_gap = np.mean(np.diff(appearances))
            gap_scores[n] = gap / avg_gap if avg_gap > 0 else 1.0
        else:
            gap_scores[n] = 1.0
    max_gap = max(gap_scores.values()) if gap_scores else 1
    gap_scores = {n: v / max_gap for n, v in gap_scores.items()}
    
    # Dim 3: Markov score
    markov_recent = hist[-30:] if len(hist) >= 30 else hist
    transition = np.zeros((POOL, POOL))
    for i in range(len(markov_recent) - 1):
        for a in markov_recent[i]['numbers']:
            for b in markov_recent[i + 1]['numbers']:
                transition[a - 1][b - 1] += 1
    row_sums = transition.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    transition /= row_sums
    markov_raw = np.zeros(POOL)
    for n in markov_recent[-1]['numbers']:
        markov_raw += transition[n - 1]
    max_markov = markov_raw.max() if markov_raw.max() > 0 else 1
    markov_scores = {n + 1: markov_raw[n] / max_markov for n in range(POOL)}
    
    # Dim 4: Zone balance score
    zone_counter = Counter()
    for d in recent[-50:]:
        for n in d['numbers']:
            zone_counter[0 if n <= 13 else (1 if n <= 26 else 2)] += 1
    total_z = sum(zone_counter.values())
    expected_z = total_z / 3
    zone_deficit = {z: (expected_z - zone_counter.get(z, 0)) / expected_z for z in range(3)}
    struct_scores = {}
    for n in range(1, POOL + 1):
        z = 0 if n <= 13 else (1 if n <= 26 else 2)
        struct_scores[n] = max(0, zone_deficit[z])
    max_struct = max(struct_scores.values()) if max(struct_scores.values()) > 0 else 1
    struct_scores = {n: v / max_struct for n, v in struct_scores.items()}
    
    # Fusion: weighted sum
    combined = {}
    for n in range(1, POOL + 1):
        combined[n] = (0.30 * freq_scores[n] +
                       0.25 * gap_scores[n] +
                       0.25 * markov_scores[n] +
                       0.20 * struct_scores[n])
    
    ranked = sorted(combined, key=lambda x: -combined[x])
    return sorted(ranked[:PICK])

def method_sliding_window_auto(hist):
    """
    P3-1: Sliding Window Auto-Tune
    動態選擇最佳窗口 — 用最近30期的表現做為proxy
    """
    if len(hist) < 200:
        return method_state_space(hist, 100)
    
    windows = [50, 100, 200, 300]
    best_window = 100
    best_score = -1
    
    # 在最近30期做mini-backtest
    test_start = max(100, len(hist) - 30)
    for w in windows:
        hits_total = 0
        for i in range(test_start, len(hist)):
            pred = method_state_space(hist[:i], w)
            actual = hist[i]['numbers']
            hits_total += len(set(pred) & set(actual))
        if hits_total > best_score:
            best_score = hits_total
            best_window = w
    
    return method_state_space(hist, best_window)

def method_combo_feature_ml(hist, window=300):
    """
    P3-2: Combinatorial Feature ML (lightweight)
    使用組合特徵(zone+sum+AC+spacing)的歷史分佈來選號
    """
    recent = hist[-window:] if len(hist) >= window else hist
    
    # 學習歷史組合特徵分佈
    sum_mean = np.mean([sum(d['numbers']) for d in recent])
    sum_std = np.std([sum(d['numbers']) for d in recent])
    
    ac_values = []
    for d in recent:
        nums = sorted(d['numbers'])
        diffs = set()
        for i in range(len(nums)):
            for j in range(i+1, len(nums)):
                diffs.add(nums[j] - nums[i])
        ac_values.append(len(diffs) - (PICK - 1))
    ac_mean = np.mean(ac_values)
    
    odd_counts = [sum(1 for n in d['numbers'] if n % 2 == 1) for d in recent]
    odd_mode = Counter(odd_counts).most_common(1)[0][0]
    
    zone_patterns = Counter()
    for d in recent:
        z = tuple(sorted([0 if n <= 13 else (1 if n <= 26 else 2) for n in d['numbers']]))
        zone_patterns[z] += 1
    top_zone_pattern = zone_patterns.most_common(1)[0][0]
    
    # 頻率+gap混合候選
    counter = Counter()
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(recent)
    
    hybrid = {}
    for n in range(1, POOL + 1):
        freq = counter.get(n, 0) / len(recent)
        gap = current - last_seen.get(n, -1)
        avg_gap = len(recent) / max(counter.get(n, 1), 1)
        hybrid[n] = freq * 0.4 + (gap / avg_gap) * 0.6
    
    candidates = sorted(hybrid, key=lambda x: -hybrid[x])[:20]
    
    # 用組合約束篩選最優組合
    best_combo = None
    best_score = -float('inf')
    
    for combo in combinations(candidates, PICK):
        nums = sorted(combo)
        s = sum(nums)
        
        # Sum score
        sum_score = -abs(s - sum_mean) / max(sum_std, 1)
        
        # AC score
        diffs = set()
        for i in range(len(nums)):
            for j in range(i+1, len(nums)):
                diffs.add(nums[j] - nums[i])
        ac = len(diffs) - (PICK - 1)
        ac_score = -abs(ac - ac_mean)
        
        # Odd/even score
        odd = sum(1 for n in nums if n % 2 == 1)
        odd_score = -abs(odd - odd_mode)
        
        # Zone balance score
        z_pattern = tuple(sorted([0 if n <= 13 else (1 if n <= 26 else 2) for n in nums]))
        zone_score = zone_patterns.get(z_pattern, 0) / len(recent)
        
        # Hybrid score of numbers
        num_score = sum(hybrid[n] for n in combo)
        
        total = sum_score * 0.15 + ac_score * 0.10 + odd_score * 0.10 + zone_score * 0.15 + num_score * 0.50
        
        if total > best_score:
            best_score = total
            best_combo = combo
    
    return sorted(list(best_combo)) if best_combo else sorted(candidates[:PICK])

# ═══════════════════════════════════════════════════════════════════
#  MULTI-BET STRATEGIES (2-bet, 3-bet)
# ═══════════════════════════════════════════════════════════════════

def strategy_existing_2bet(hist):
    """Existing best: state_space + markov"""
    return [method_state_space(hist), method_markov(hist)]

def strategy_existing_3bet(hist):
    """Existing best: state_space + markov + regime"""
    # regime = method_state_space with different window
    return [method_state_space(hist), method_markov(hist), method_fourier(hist)]

def strategy_new_2bet_v1(hist):
    """New 2bet: state_space + anomaly_capture"""
    return [method_state_space(hist), method_anomaly_capture(hist)]

def strategy_new_2bet_v2(hist):
    """New 2bet: markov + zone_jump"""
    return [method_markov(hist), method_zone_jump_detector(hist)]

def strategy_new_2bet_v3(hist):
    """New 2bet: multi_fusion_v2 + anomaly_capture"""
    return [method_multi_signal_fusion_v2(hist), method_anomaly_capture(hist)]

def strategy_new_2bet_v4(hist):
    """New 2bet: combo_feature_ml + anomaly_capture"""
    return [method_combo_feature_ml(hist), method_anomaly_capture(hist)]

def strategy_new_2bet_v5(hist):
    """New 2bet: state_space + zone_jump"""
    return [method_state_space(hist), method_zone_jump_detector(hist)]

def strategy_new_3bet_v1(hist):
    """New 3bet: state_space + markov + anomaly_capture"""
    return [method_state_space(hist), method_markov(hist), method_anomaly_capture(hist)]

def strategy_new_3bet_v2(hist):
    """New 3bet: fourier + gap + anomaly_capture"""
    return [method_fourier(hist), method_gap(hist), method_anomaly_capture(hist)]

def strategy_new_3bet_v3(hist):
    """New 3bet: multi_fusion_v2 + zone_jump + anomaly_capture"""
    return [method_multi_signal_fusion_v2(hist), method_zone_jump_detector(hist), method_anomaly_capture(hist)]

def strategy_new_3bet_v4(hist):
    """New 3bet: combo_ml + spacing + anomaly_capture"""
    return [method_combo_feature_ml(hist), method_spacing_profile(hist), method_anomaly_capture(hist)]

def strategy_new_3bet_v5(hist):
    """New 3bet: state_space + zone_jump + arithmetic"""
    return [method_state_space(hist), method_zone_jump_detector(hist), method_arithmetic_detector(hist)]

def strategy_new_3bet_v6(hist):
    """New 3bet: sliding_auto + zone_jump + anomaly_capture"""
    return [method_sliding_window_auto(hist), method_zone_jump_detector(hist), method_anomaly_capture(hist)]

# ═══════════════════════════════════════════════════════════════════
#  BACKTEST ENGINE (Walk-Forward, Leakage-Free)
# ═══════════════════════════════════════════════════════════════════

def backtest_single(method, all_draws, test_periods, min_train=100, seed=42):
    """Single bet backtest"""
    total = len(all_draws)
    start_idx = max(min_train, total - test_periods)
    ge2 = 0
    ge3 = 0
    test_count = 0
    for i in range(start_idx, total):
        hist = all_draws[:i]
        pred = method(hist)
        actual = set(all_draws[i]['numbers'])
        hits = len(set(pred) & actual)
        if hits >= 2: ge2 += 1
        if hits >= 3: ge3 += 1
        test_count += 1
    if test_count == 0:
        return {'ge2': 0, 'ge3': 0, 'edge2': 0, 'edge3': 0, 'n': 0}
    ge2_rate = ge2 / test_count
    ge3_rate = ge3 / test_count
    return {
        'ge2': ge2_rate, 'ge3': ge3_rate,
        'edge2': ge2_rate - P_GE2_1,
        'edge3': ge3_rate - P_GE3_1,
        'n': test_count,
        'ge2_count': ge2, 'ge3_count': ge3
    }

def backtest_multi(strategy_func, all_draws, test_periods, min_train=100, seed=42):
    """Multi-bet backtest: any-hit across all bets"""
    total = len(all_draws)
    start_idx = max(min_train, total - test_periods)
    ge2 = 0
    ge3 = 0
    test_count = 0
    n_bets = None
    for i in range(start_idx, total):
        hist = all_draws[:i]
        bets = strategy_func(hist)
        if n_bets is None:
            n_bets = len(bets)
        actual = set(all_draws[i]['numbers'])
        any_ge2 = False
        any_ge3 = False
        for bet in bets:
            hits = len(set(bet) & actual)
            if hits >= 2: any_ge2 = True
            if hits >= 3: any_ge3 = True
        if any_ge2: ge2 += 1
        if any_ge3: ge3 += 1
        test_count += 1
    if test_count == 0 or n_bets is None:
        return {'ge2': 0, 'ge3': 0, 'edge2': 0, 'edge3': 0, 'n': 0, 'n_bets': 0}
    ge2_rate = ge2 / test_count
    ge3_rate = ge3 / test_count
    bl_ge2 = baseline_n_bet(n_bets, 2)
    bl_ge3 = baseline_n_bet(n_bets, 3)
    return {
        'ge2': ge2_rate, 'ge3': ge3_rate,
        'edge2': ge2_rate - bl_ge2,
        'edge3': ge3_rate - bl_ge3,
        'n': test_count, 'n_bets': n_bets,
        'ge2_count': ge2, 'ge3_count': ge3,
        'baseline_ge2': bl_ge2, 'baseline_ge3': bl_ge3
    }

def three_window_test(func, all_draws, is_multi=False, min_train=100):
    """150 / 500 / 1500 三窗口測試"""
    bt = backtest_multi if is_multi else backtest_single
    results = {}
    for w in [150, 500, 1500]:
        r = bt(func, all_draws, w, min_train)
        results[w] = r
    
    # Stability check
    edges = [results[w]['edge2'] for w in [150, 500, 1500]]
    all_positive = all(e > 0 for e in edges)
    if all_positive:
        stability = 'STABLE'
    elif edges[-1] > 0 and edges[0] <= 0:
        stability = 'LATE_BLOOMER'
    elif edges[0] > 0 and edges[-1] <= 0:
        stability = 'SHORT_MOMENTUM'
    else:
        stability = 'MIXED' if any(e > 0 for e in edges) else 'INEFFECTIVE'
    
    return results, stability

def permutation_test(func, all_draws, test_periods=500, n_perms=200, is_multi=False, min_train=100, seed=42):
    """Permutation test: strategy vs random"""
    # Real performance
    bt = backtest_multi if is_multi else backtest_single
    real = bt(func, all_draws, test_periods, min_train, seed)
    real_ge2 = real['ge2']
    
    # Random baseline permutations
    rng = np.random.RandomState(seed)
    perm_ge2s = []
    
    total = len(all_draws)
    start_idx = max(min_train, total - test_periods)
    test_count = total - start_idx
    
    if is_multi:
        n_bets = real.get('n_bets', 2)
    else:
        n_bets = 1
    
    for p in range(n_perms):
        ge2 = 0
        for i in range(start_idx, total):
            actual = set(all_draws[i]['numbers'])
            any_ge2 = False
            for _ in range(n_bets):
                rand_bet = sorted(rng.choice(range(1, POOL + 1), size=PICK, replace=False).tolist())
                if len(set(rand_bet) & actual) >= 2:
                    any_ge2 = True
            if any_ge2:
                ge2 += 1
        perm_ge2s.append(ge2 / test_count)
    
    perm_mean = np.mean(perm_ge2s)
    perm_std = np.std(perm_ge2s) if np.std(perm_ge2s) > 0 else 0.001
    z = (real_ge2 - perm_mean) / perm_std
    p_value = 1 - _NormDist.cdf(z)
    
    return {
        'real_ge2': real_ge2,
        'perm_mean': perm_mean,
        'perm_std': perm_std,
        'z': z,
        'p_value': p_value,
        'significant': p_value < 0.05
    }

# ═══════════════════════════════════════════════════════════════════
#  MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════

def main():
    t0 = time.time()
    all_draws = load_draws()
    print(f"載入 {len(all_draws)} 期 DAILY_539 數據")
    print(f"最新: {all_draws[-1]['draw']} ({all_draws[-1]['date']})")
    print()
    
    # ─── Phase 1: Single-bet new methods ─────────────────────────
    print("=" * 80)
    print("  PHASE 1: 新結構特徵方法 — 單注回測")
    print("=" * 80)
    
    single_methods = {
        'state_space(baseline)': method_state_space,
        'markov(baseline)': method_markov,
        'fourier(baseline)': method_fourier,
        'cold(baseline)': method_cold,
        'P1_zone_jump': method_zone_jump_detector,
        'P1_arithmetic': method_arithmetic_detector,
        'P1_spacing_profile': method_spacing_profile,
        'P1_anomaly_capture': method_anomaly_capture,
        'P2_fusion_v2': method_multi_signal_fusion_v2,
        'P3_sliding_auto': method_sliding_window_auto,
        'P3_combo_ml': method_combo_feature_ml,
    }
    
    single_results = {}
    for name, method in single_methods.items():
        print(f"\n  測試: {name}...", end='', flush=True)
        tw, stab = three_window_test(method, all_draws, is_multi=False)
        single_results[name] = {'windows': tw, 'stability': stab}
        print(f" {stab}", end='')
        for w in [150, 500, 1500]:
            e = tw[w]['edge2']
            print(f" | {w}p:{e:+.2%}", end='')
        print()
    
    # Rank by 1500p edge
    print(f"\n  {'排名':<4} {'方法':<25} {'150p':>8} {'500p':>8} {'1500p':>8} {'穩定性':<15}")
    print("  " + "-" * 75)
    ranked_single = sorted(single_results.items(), key=lambda x: -x[1]['windows'][1500]['edge2'])
    for i, (name, data) in enumerate(ranked_single, 1):
        e150 = data['windows'][150]['edge2']
        e500 = data['windows'][500]['edge2']
        e1500 = data['windows'][1500]['edge2']
        flag = "★" if data['stability'] == 'STABLE' and e1500 > 0 else " "
        print(f"  {flag}{i:<3} {name:<25} {e150:>+7.2%} {e500:>+7.2%} {e1500:>+7.2%} {data['stability']:<15}")
    
    # ─── Phase 2: Multi-bet strategies ───────────────────────────
    print()
    print("=" * 80)
    print("  PHASE 2: 多注策略回測 (2注 & 3注)")
    print("=" * 80)
    
    multi_strategies = {
        # 2-bet
        'exist_2bet(SS+MK)': strategy_existing_2bet,
        'new_2bet_v1(SS+ACB)': strategy_new_2bet_v1,
        'new_2bet_v2(MK+ZJ)': strategy_new_2bet_v2,
        'new_2bet_v3(Fus+ACB)': strategy_new_2bet_v3,
        'new_2bet_v4(ML+ACB)': strategy_new_2bet_v4,
        'new_2bet_v5(SS+ZJ)': strategy_new_2bet_v5,
        # 3-bet
        'exist_3bet(SS+MK+FR)': strategy_existing_3bet,
        'new_3bet_v1(SS+MK+ACB)': strategy_new_3bet_v1,
        'new_3bet_v2(FR+Gap+ACB)': strategy_new_3bet_v2,
        'new_3bet_v3(Fus+ZJ+ACB)': strategy_new_3bet_v3,
        'new_3bet_v4(ML+SP+ACB)': strategy_new_3bet_v4,
        'new_3bet_v5(SS+ZJ+AR)': strategy_new_3bet_v5,
        'new_3bet_v6(Auto+ZJ+ACB)': strategy_new_3bet_v6,
    }
    
    multi_results = {}
    for name, strategy in multi_strategies.items():
        print(f"\n  測試: {name}...", end='', flush=True)
        tw, stab = three_window_test(strategy, all_draws, is_multi=True)
        multi_results[name] = {'windows': tw, 'stability': stab}
        print(f" {stab}", end='')
        for w in [150, 500, 1500]:
            e = tw[w]['edge2']
            print(f" | {w}p:{e:+.2%}", end='')
        print()
    
    # Separate 2-bet and 3-bet rankings
    for bet_type, prefix in [("2注策略排名", "2bet"), ("3注策略排名", "3bet")]:
        subset = {k: v for k, v in multi_results.items() if prefix in k}
        print(f"\n  === {bet_type} ===")
        print(f"  {'排名':<4} {'策略':<30} {'150p':>8} {'500p':>8} {'1500p':>8} {'穩定性':<15}")
        print("  " + "-" * 80)
        ranked = sorted(subset.items(), key=lambda x: -x[1]['windows'][1500]['edge2'])
        for i, (name, data) in enumerate(ranked, 1):
            e150 = data['windows'][150]['edge2']
            e500 = data['windows'][500]['edge2']
            e1500 = data['windows'][1500]['edge2']
            flag = "★" if data['stability'] == 'STABLE' and e1500 > 0 else " "
            print(f"  {flag}{i:<3} {name:<30} {e150:>+7.2%} {e500:>+7.2%} {e1500:>+7.2%} {data['stability']:<15}")
    
    # ─── Phase 3: Permutation tests for top strategies ───────────
    print()
    print("=" * 80)
    print("  PHASE 3: Permutation Test (Top 策略)")
    print("=" * 80)
    
    # Pick top single methods and top multi strategies for perm test
    top_single = sorted(single_results.items(), 
                        key=lambda x: -x[1]['windows'][1500]['edge2'])[:5]
    top_multi = sorted(multi_results.items(), 
                       key=lambda x: -x[1]['windows'][1500]['edge2'])[:5]
    
    print("\n  Top 單注方法 Permutation:")
    for name, data in top_single:
        method = single_methods[name]
        perm = permutation_test(method, all_draws, 500, 200, False)
        sig = "✅ SIGNIFICANT" if perm['significant'] else "❌ NOT SIG"
        print(f"    {name:<25} real={perm['real_ge2']:.4f} perm_mean={perm['perm_mean']:.4f} z={perm['z']:.2f} p={perm['p_value']:.4f} {sig}")
    
    print("\n  Top 多注策略 Permutation:")
    for name, data in top_multi:
        strategy = multi_strategies[name]
        n_bets = 2 if '2bet' in name else 3
        perm = permutation_test(strategy, all_draws, 500, 200, True)
        sig = "✅ SIGNIFICANT" if perm['significant'] else "❌ NOT SIG"
        print(f"    {name:<30} real={perm['real_ge2']:.4f} perm_mean={perm['perm_mean']:.4f} z={perm['z']:.2f} p={perm['p_value']:.4f} {sig}")
    
    # ─── Summary ─────────────────────────────────────────────────
    elapsed = time.time() - t0
    print()
    print("=" * 80)
    print(f"  總結 (耗時 {elapsed:.0f} 秒)")
    print("=" * 80)
    
    # Best single
    best_single_name, best_single_data = max(single_results.items(), 
                                              key=lambda x: x[1]['windows'][1500]['edge2'])
    print(f"\n  最佳單注: {best_single_name}")
    print(f"    1500p edge: {best_single_data['windows'][1500]['edge2']:+.2%}")
    print(f"    穩定性: {best_single_data['stability']}")
    
    # Best 2-bet
    bet2 = {k: v for k, v in multi_results.items() if '2bet' in k}
    best_2bet_name, best_2bet_data = max(bet2.items(), 
                                          key=lambda x: x[1]['windows'][1500]['edge2'])
    print(f"\n  最佳2注: {best_2bet_name}")
    print(f"    1500p edge: {best_2bet_data['windows'][1500]['edge2']:+.2%}")
    print(f"    穩定性: {best_2bet_data['stability']}")
    
    # Best 3-bet
    bet3 = {k: v for k, v in multi_results.items() if '3bet' in k}
    best_3bet_name, best_3bet_data = max(bet3.items(), 
                                          key=lambda x: x[1]['windows'][1500]['edge2'])
    print(f"\n  最佳3注: {best_3bet_name}")
    print(f"    1500p edge: {best_3bet_data['windows'][1500]['edge2']:+.2%}")
    print(f"    穩定性: {best_3bet_data['stability']}")
    
    # Save results
    output = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_draws': len(all_draws),
        'elapsed_seconds': round(elapsed, 1),
        'single_methods': {},
        'multi_strategies': {},
    }
    for name, data in single_results.items():
        output['single_methods'][name] = {
            'stability': data['stability'],
            'windows': {str(w): {
                'ge2': round(data['windows'][w]['ge2'], 6),
                'edge2': round(data['windows'][w]['edge2'], 6),
                'ge3': round(data['windows'][w]['ge3'], 6),
                'n': data['windows'][w]['n']
            } for w in [150, 500, 1500]}
        }
    for name, data in multi_results.items():
        output['multi_strategies'][name] = {
            'stability': data['stability'],
            'n_bets': data['windows'][1500].get('n_bets', 0),
            'windows': {str(w): {
                'ge2': round(data['windows'][w]['ge2'], 6),
                'edge2': round(data['windows'][w]['edge2'], 6),
                'ge3': round(data['windows'][w]['ge3'], 6),
                'n': data['windows'][w]['n'],
                'baseline_ge2': round(data['windows'][w].get('baseline_ge2', 0), 6),
            } for w in [150, 500, 1500]}
        }
    
    out_path = os.path.join(_base, '..', 'backtest_539_structural_upgrade_results.json')
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n  結果已存: {out_path}")
    print("=" * 80)

if __name__ == '__main__':
    main()
