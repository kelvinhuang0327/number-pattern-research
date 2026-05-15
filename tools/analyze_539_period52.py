#!/usr/bin/env python3
"""
今彩539 第115000052期 深度分析腳本
開獎號碼: 01, 22, 23, 37, 39
目標: 用所有現有方法進行回溯預測，比較命中率，分析特徵缺失
"""
import sys, os, json, math
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

# 實際開獎
ACTUAL = {1, 22, 23, 37, 39}
DRAW_NUM = '115000052'
MAX_NUM = 39
PICK = 5

# ========== 方法 1: ACB (anomaly_capture_bet) ==========
def method_acb(history, window=100):
    """ACB 異常捕捉法 (Edge +2.80%, p=0.002)"""
    recent = history[-window:] if len(history) >= window else history
    counter = Counter()
    for n in range(1, MAX_NUM + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers']:
            counter[n] += 1
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(recent)
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, MAX_NUM + 1)}
    expected_freq = len(recent) * PICK / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM + 1):
        freq_deficit = expected_freq - counter[n]
        gap_score = gaps[n] / (len(recent) / 2)
        boundary_bonus = 1.2 if (n <= 5 or n >= 35) else 1.0
        mod3_bonus = 1.1 if n % 3 == 0 else 1.0
        scores[n] = (freq_deficit * 0.4 + gap_score * 0.6) * boundary_bonus * mod3_bonus
    ranked = sorted(scores, key=lambda x: -scores[x])
    # 跨區約束
    zones_selected = set()
    result = []
    for n in ranked:
        zone = 0 if n <= 13 else (1 if n <= 26 else 2)
        result.append(n)
        zones_selected.add(zone)
        if len(result) >= PICK:
            break
    if len(zones_selected) < 2:
        missing_zones = set(range(3)) - zones_selected
        for mz in missing_zones:
            zr = range(1, 14) if mz == 0 else (range(14, 27) if mz == 1 else range(27, 40))
            zc = sorted(zr, key=lambda x: -scores[x])
            if zc:
                result[-1] = zc[0]
                break
    return sorted(result[:PICK]), scores

# ========== 方法 2: Fourier Rhythm ==========
def method_fourier(history, window=500):
    """Fourier 週期分析"""
    from numpy.fft import fft, fftfreq
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    scores = {}
    for n in range(1, MAX_NUM + 1):
        bh = np.zeros(w)
        for idx, d in enumerate(h):
            if n in d['numbers']:
                bh[idx] = 1
        if sum(bh) < 2:
            scores[n] = 0.0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        ip = np.where(xf > 0)
        py = np.abs(yf[ip])
        px = xf[ip]
        pk = np.argmax(py)
        fv = px[pk]
        if fv == 0:
            scores[n] = 0.0
            continue
        period = 1 / fv
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK]), scores

# ========== 方法 3: Cold Numbers ==========
def method_cold(history, window=100):
    """冷號 (近 window 期頻率最低)"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: freq.get(n, 0))
    scores = {n: -freq.get(n, 0) for n in range(1, MAX_NUM + 1)}
    return sorted(ranked[:PICK]), scores

# ========== 方法 4: Hot Numbers ==========
def method_hot(history, window=50):
    """熱號 (近 window 期頻率最高)"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: -freq.get(n, 0))
    scores = {n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)}
    return sorted(ranked[:PICK]), scores

# ========== 方法 5: Frequency Deficit ==========
def method_freq_deficit(history, window=100):
    """頻率赤字 (偏離期望頻率最大)"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    expected = len(recent) * PICK / MAX_NUM
    scores = {n: expected - freq.get(n, 0) for n in range(1, MAX_NUM + 1)}
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK]), scores

# ========== 方法 6: Gap Score ==========
def method_gap(history):
    """間隔分數 (距上次出現最久)"""
    last_seen = {}
    for i, d in enumerate(history):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(history)
    scores = {n: current - last_seen.get(n, -1) for n in range(1, MAX_NUM + 1)}
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK]), scores

# ========== 方法 7: Echo Lag-2 ==========
def method_echo_lag2(history):
    """Echo Lag-2 (N-2期號碼回聲)"""
    if len(history) < 3:
        return list(range(1, 6)), {}
    lag2_nums = set(history[-2]['numbers'])
    # 排名: lag2中出現的號碼優先，其餘按頻率
    freq = Counter(n for d in history[-50:] for n in d['numbers'])
    scores = {}
    for n in range(1, MAX_NUM + 1):
        scores[n] = (2.0 if n in lag2_nums else 0.0) + freq.get(n, 0) / 50.0
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK]), scores

# ========== 方法 8: EMA Cross ==========
def method_ema_cross(history, short_w=10, long_w=50):
    """EMA 交叉 (短期均線上穿長期均線)"""
    freq_short = Counter(n for d in history[-short_w:] for n in d['numbers'])
    freq_long = Counter(n for d in history[-long_w:] for n in d['numbers'])
    scores = {}
    for n in range(1, MAX_NUM + 1):
        r_short = freq_short.get(n, 0) / short_w
        r_long = freq_long.get(n, 0) / long_w
        scores[n] = r_short - r_long  # 正 = 短期上升
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK]), scores

# ========== 方法 9: Tail Balance ==========
def method_tail_balance(history, window=100):
    """尾數平衡 (平衡各尾數的代表)"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    tail_freq = defaultdict(list)
    for n in range(1, MAX_NUM + 1):
        tail_freq[n % 10].append((n, freq.get(n, 0)))
    # 每個尾數取頻率最低的
    result = []
    scores = {}
    for tail in range(10):
        if tail in tail_freq:
            tail_freq[tail].sort(key=lambda x: x[1])
            for n, f in tail_freq[tail]:
                scores[n] = -f + (0.01 if n % 10 == tail else 0)
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK]), scores

# ========== 方法 10: Markov Transition ==========
def method_markov(history, window=30):
    """Markov 轉移 (根據上期號碼預測)"""
    recent = history[-window:] if len(history) >= window else history
    transitions = defaultdict(Counter)
    for i in range(len(recent) - 1):
        for cn in recent[i]['numbers']:
            for nn in recent[i + 1]['numbers']:
                transitions[cn][nn] += 1
    prev_nums = history[-1]['numbers']
    scores = Counter()
    for pn in prev_nums:
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for n, cnt in trans.items():
                scores[n] += cnt / total
    ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: -scores.get(n, 0))
    return sorted(ranked[:PICK]), dict(scores)

# ========== 方法 11: Neighbor (上期鄰號) ==========
def method_neighbor(history):
    """鄰號 (上期號碼±1)"""
    prev = set(history[-1]['numbers'])
    pool = set()
    for n in prev:
        for d in range(-1, 2):
            nn = n + d
            if 1 <= nn <= MAX_NUM:
                pool.add(nn)
    freq = Counter(n for d in history[-50:] for n in d['numbers'])
    scores = {n: (1.5 if n in pool else 0.0) + freq.get(n, 0) / 50.0 for n in range(1, MAX_NUM + 1)}
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK]), scores

# ========== 方法 12: Deviation Hot ==========
def method_deviation_hot(history, window=50):
    """偏差熱號 (正偏差最大)"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    expected = len(recent) * PICK / MAX_NUM
    scores = {n: freq.get(n, 0) - expected for n in range(1, MAX_NUM + 1)}
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK]), scores

# ========== 方法 13: Sum Range Constraint ==========
def method_sum_range(history, window=300):
    """Sum 範圍約束 (選Sum最接近歷史均值的組合)"""
    h = history[-window:] if len(history) >= window else history
    sums = [sum(d['numbers']) for d in h]
    mu = np.mean(sums)
    sigma = np.std(sums)
    # 用各號碼頻率排序，然後從Top池選Sum最接近mu的組合
    freq = Counter(n for d in history[-100:] for n in d['numbers'])
    pool = sorted(range(1, MAX_NUM + 1), key=lambda n: -freq.get(n, 0))[:15]
    best, best_dist = None, float('inf')
    for combo in combinations(pool, PICK):
        dist = abs(sum(combo) - mu)
        if dist < best_dist:
            best, best_dist = combo, dist
    scores = {n: freq.get(n, 0) for n in range(1, MAX_NUM + 1)}
    return sorted(best) if best else sorted(pool[:PICK]), scores

# ========== 方法 14: Bayesian Posterior ==========
def method_bayesian(history, window=100):
    """Bayesian 後驗 (Beta-Binomial 後驗均值)"""
    recent = history[-window:] if len(history) >= window else history
    alpha0, beta0 = 1.0, 1.0  # 均勻先驗
    total = len(recent)
    scores = {}
    for n in range(1, MAX_NUM + 1):
        hits = sum(1 for d in recent if n in d['numbers'])
        posterior_mean = (alpha0 + hits) / (alpha0 + beta0 + total)
        scores[n] = posterior_mean
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:PICK]), scores

# ========== 方法 15: Zone Balance ==========
def method_zone_balance(history, window=100):
    """區域平衡 (Z1=1-13, Z2=14-26, Z3=27-39 各選代表)"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    zones = [range(1, 14), range(14, 27), range(27, 40)]
    result = []
    for z in zones:
        z_sorted = sorted(z, key=lambda n: freq.get(n, 0))
        # 取冷號代表
        for n in z_sorted:
            if len(result) < (len(result) // (PICK // 3 + 1) + 1) * (PICK // 3 + 1) and n not in result:
                result.append(n)
                if len(result) >= PICK:
                    break
        if len(result) >= PICK:
            break
    # 補齊
    if len(result) < PICK:
        for n in sorted(range(1, MAX_NUM + 1), key=lambda n: freq.get(n, 0)):
            if n not in result:
                result.append(n)
                if len(result) >= PICK:
                    break
    scores = {n: -freq.get(n, 0) for n in range(1, MAX_NUM + 1)}
    return sorted(result[:PICK]), scores

# ========== 方法 16: F500+F200 正交 2注 ==========
def method_fourier_2bet(history):
    """Fourier 500+200 雙窗口正交"""
    from numpy.fft import fft, fftfreq
    def _fscore(hist, window):
        h = hist[-window:] if len(hist) >= window else hist
        w = len(h)
        sc = {}
        for n in range(1, MAX_NUM + 1):
            bh = np.zeros(w)
            for idx, d in enumerate(h):
                if n in d['numbers']:
                    bh[idx] = 1
            if sum(bh) < 2:
                sc[n] = 0.0
                continue
            yf = fft(bh - np.mean(bh))
            xf = fftfreq(w, 1)
            ip = np.where(xf > 0)
            py = np.abs(yf[ip])
            px = xf[ip]
            pk = np.argmax(py)
            fv = px[pk]
            if fv == 0:
                sc[n] = 0.0
                continue
            period = 1 / fv
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            sc[n] = 1.0 / (abs(gap - period) + 1.0)
        return sc
    sc500 = _fscore(history, 500)
    r500 = [n for n in sorted(sc500, key=lambda x: -sc500[x]) if sc500[n] > 0]
    bet1 = sorted(r500[:PICK])
    sc200 = _fscore(history, 200)
    excl = set(bet1)
    r200 = [n for n in sorted(sc200, key=lambda x: -sc200[x]) if sc200[n] > 0 and n not in excl]
    bet2 = sorted(r200[:PICK])
    return [bet1, bet2], {**sc500, **{f'f200_{k}': v for k, v in sc200.items()}}

# ========== 進階分析: 特徵剖析 ==========
def analyze_features(history, actual_nums):
    """對實際開獎號碼進行特徵剖析"""
    results = {}
    
    # 1. 各號碼在不同方法中的排名
    methods_detail = {}
    _, acb_scores = method_acb(history)
    _, fourier_scores = method_fourier(history)
    _, cold_scores = method_cold(history)
    _, hot_scores = method_hot(history)
    _, gap_scores = method_gap(history)
    _, echo_scores = method_echo_lag2(history)
    _, markov_scores = method_markov(history)
    _, ema_scores = method_ema_cross(history)
    _, neighbor_scores = method_neighbor(history)
    _, freq_deficit_scores = method_freq_deficit(history)
    
    # 排名（分數由高到低）
    def get_rank(scores, num):
        ranked = sorted(scores, key=lambda x: -scores.get(x, 0))
        try:
            return ranked.index(num) + 1
        except ValueError:
            return MAX_NUM
    
    for n in sorted(actual_nums):
        methods_detail[n] = {
            'ACB': get_rank(acb_scores, n),
            'Fourier': get_rank(fourier_scores, n),
            'Cold_100': get_rank(cold_scores, n),
            'Hot_50': get_rank(hot_scores, n),
            'Gap': get_rank(gap_scores, n),
            'Echo_Lag2': get_rank(echo_scores, n),
            'Markov': get_rank(markov_scores, n),
            'EMA_Cross': get_rank(ema_scores, n),
            'Neighbor': get_rank(neighbor_scores, n),
            'FreqDeficit': get_rank(freq_deficit_scores, n),
        }
    results['per_number_rank'] = methods_detail
    
    # 2. 組合特徵
    prev_nums = set(history[-1]['numbers'])
    prev2_nums = set(history[-2]['numbers']) if len(history) >= 2 else set()
    
    results['combo_features'] = {
        'sum': sum(actual_nums),
        'spread': max(actual_nums) - min(actual_nums),
        'neighbor_count': sum(1 for n in actual_nums if any(abs(n - p) <= 1 for p in prev_nums)),
        'repeat_count': len(actual_nums & prev_nums),
        'echo_lag2_count': len(actual_nums & prev2_nums),
        'odd_count': sum(1 for n in actual_nums if n % 2 == 1),
        'zone_dist': {
            'Z1(1-13)': sum(1 for n in actual_nums if 1 <= n <= 13),
            'Z2(14-26)': sum(1 for n in actual_nums if 14 <= n <= 26),
            'Z3(27-39)': sum(1 for n in actual_nums if 27 <= n <= 39),
        },
        'tail_dist': Counter(n % 10 for n in actual_nums),
        'consecutive_pairs': sum(1 for a, b in zip(sorted(actual_nums), sorted(actual_nums)[1:]) if b - a == 1),
        'mod3_dist': Counter(n % 3 for n in actual_nums),
        'boundary_count': sum(1 for n in actual_nums if n <= 5 or n >= 35),
    }
    
    # 3. 歷史統計比較
    h_sums = [sum(d['numbers']) for d in history[-300:]]
    h_spreads = [max(d['numbers']) - min(d['numbers']) for d in history[-300:]]
    results['stat_comparison'] = {
        'sum_mu': float(np.mean(h_sums)),
        'sum_sigma': float(np.std(h_sums)),
        'sum_z': float((sum(actual_nums) - np.mean(h_sums)) / np.std(h_sums)),
        'spread_mu': float(np.mean(h_spreads)),
        'spread_z': float((max(actual_nums) - min(actual_nums) - np.mean(h_spreads)) / np.std(h_spreads)),
        'prev_overlap': len(actual_nums & prev_nums),
        'prev2_overlap': len(actual_nums & prev2_nums),
    }
    
    # 4. 近期號碼頻率
    freq_50 = Counter(n for d in history[-50:] for n in d['numbers'])
    freq_100 = Counter(n for d in history[-100:] for n in d['numbers'])
    expected_50 = 50 * PICK / MAX_NUM
    expected_100 = 100 * PICK / MAX_NUM
    
    results['frequency_analysis'] = {}
    for n in sorted(actual_nums):
        results['frequency_analysis'][n] = {
            'freq_50': freq_50.get(n, 0),
            'freq_100': freq_100.get(n, 0),
            'expected_50': round(expected_50, 1),
            'expected_100': round(expected_100, 1),
            'deficit_50': round(expected_50 - freq_50.get(n, 0), 1),
            'deficit_100': round(expected_100 - freq_100.get(n, 0), 1),
            'gap_from_last': next((len(history) - i - 1 for i in range(len(history) - 1, -1, -1) if n in history[i]['numbers']), len(history)),
        }
    
    return results


# ========== 附加方法: 各方法 Top-K 排名分析 ==========
def run_all_topK_analysis(history, actual_nums, k_values=[5, 10, 15, 20]):
    """測試各方法在 Top-K 選取下命中幾個號碼"""
    methods = {
        'ACB': lambda: method_acb(history),
        'Fourier_500': lambda: method_fourier(history, 500),
        'Fourier_200': lambda: method_fourier(history, 200),
        'Cold_100': lambda: method_cold(history, 100),
        'Cold_50': lambda: method_cold(history, 50),
        'Hot_50': lambda: method_hot(history, 50),
        'Hot_30': lambda: method_hot(history, 30),
        'FreqDeficit_100': lambda: method_freq_deficit(history, 100),
        'Gap': lambda: method_gap(history),
        'Echo_Lag2': lambda: method_echo_lag2(history),
        'EMA_Cross': lambda: method_ema_cross(history),
        'TailBalance': lambda: method_tail_balance(history),
        'Markov_30': lambda: method_markov(history, 30),
        'Neighbor': lambda: method_neighbor(history),
        'DevHot_50': lambda: method_deviation_hot(history, 50),
        'SumRange': lambda: method_sum_range(history),
        'Bayesian_100': lambda: method_bayesian(history, 100),
        'ZoneBalance': lambda: method_zone_balance(history),
    }
    
    results = {}
    for name, func in methods.items():
        bet, scores = func()
        ranked = sorted(scores, key=lambda x: -scores.get(x, 0))
        topk_hits = {}
        for k in k_values:
            topk = set(ranked[:k])
            hits = len(actual_nums & topk)
            topk_hits[f'Top{k}'] = hits
        results[name] = {
            'predicted_5': sorted(bet) if isinstance(bet, list) else bet,
            'hits_in_5': len(actual_nums & set(bet)),
            'hit_numbers_5': sorted(actual_nums & set(bet)),
            'miss_numbers': sorted(actual_nums - set(bet)),
            **topk_hits,
        }
    return results


def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('DAILY_539'), key=lambda x: (x['date'], x['draw']))
    
    # Period 52 是今天的開獎，DB中尚無此期數據
    # 使用所有可用數據作為歷史，與已知開獎號碼 {01,22,23,37,39} 比較
    history = all_draws  # 所有到 period 51 的數據
    actual = ACTUAL
    
    print("=" * 70)
    print(f"  今彩539 深度分析: 第{DRAW_NUM}期 (115/02/27)")
    print(f"  開獎號碼: {sorted(ACTUAL)}")
    print(f"  歷史數據截止: {history[-1]['draw']} ({history[-1]['date']})")
    print("=" * 70)
    
    print(f"\n  歷史數據: {len(history)} 期 (最新: {history[-1]['draw']} {history[-1]['date']})")
    print(f"  上期開獎: {sorted(history[-1]['numbers'])}")
    if len(history) >= 2:
        print(f"  前2期開獎: {sorted(history[-2]['numbers'])}")
    
    # ========== Part 1: 單方法命中分析 ==========
    print("\n" + "=" * 70)
    print("  Part 1: 各方法 Top-5 命中分析")
    print("=" * 70)
    
    topk = run_all_topK_analysis(history, actual)
    
    # 排序：按 hits_in_5 → Top10 → Top15
    sorted_methods = sorted(topk.items(), 
                          key=lambda x: (x[1]['hits_in_5'], x[1]['Top10'], x[1]['Top15']),
                          reverse=True)
    
    print(f"\n  {'方法':<20} {'Top5命中':>8} {'命中號碼':>16} {'Top10':>6} {'Top15':>6} {'Top20':>6}")
    print("  " + "-" * 68)
    for name, info in sorted_methods:
        hits5 = info['hits_in_5']
        hit_nums = ', '.join(f'{n:02d}' for n in info['hit_numbers_5']) if info['hit_numbers_5'] else '-'
        miss = ', '.join(f'{n:02d}' for n in info['miss_numbers'])
        print(f"  {name:<20} {hits5:>8} {hit_nums:>16} {info['Top10']:>6} {info['Top15']:>6} {info['Top20']:>6}")
    
    # 最佳方法詳情
    best_name, best_info = sorted_methods[0]
    print(f"\n  ★ 最佳方法: {best_name} (命中 {best_info['hits_in_5']}/5)")
    print(f"    預測: {best_info['predicted_5']}")
    print(f"    命中: {best_info['hit_numbers_5']}")
    print(f"    遺漏: {best_info['miss_numbers']}")
    
    # ========== Part 2: 特徵深度分析 ==========
    print("\n" + "=" * 70)
    print("  Part 2: 開獎號碼特徵深度分析")
    print("=" * 70)
    
    features = analyze_features(history, actual)
    
    # 各號碼在方法中的排名
    print("\n  各號碼排名矩陣 (1=最高優先選擇):")
    print(f"\n  {'號碼':>4}", end='')
    method_names = list(next(iter(features['per_number_rank'].values())).keys())
    for m in method_names:
        print(f"  {m:>12}", end='')
    print(f"  {'平均排名':>8}")
    print("  " + "-" * (4 + 14 * len(method_names) + 10))
    
    for num in sorted(actual):
        ranks = features['per_number_rank'][num]
        avg_rank = np.mean(list(ranks.values()))
        print(f"  {num:>4}", end='')
        for m in method_names:
            r = ranks[m]
            marker = '★' if r <= 5 else ('▲' if r <= 10 else ' ')
            print(f"  {r:>10}{marker}", end='')
        print(f"  {avg_rank:>8.1f}")
    
    # 組合特徵
    cf = features['combo_features']
    sc = features['stat_comparison']
    print(f"\n  組合特徵:")
    print(f"    Sum = {cf['sum']} (歷史μ={sc['sum_mu']:.1f}, σ={sc['sum_sigma']:.1f}, z={sc['sum_z']:.2f})")
    print(f"    Spread = {cf['spread']} (歷史μ={sc['spread_mu']:.1f}, z={sc['spread_z']:.2f})")
    print(f"    鄰號數 = {cf['neighbor_count']} (與上期±1)")
    print(f"    重複數 = {cf['repeat_count']} (與上期重複)")
    print(f"    Echo(N-2) = {cf['echo_lag2_count']}")
    print(f"    奇數比 = {cf['odd_count']}/5")
    print(f"    區域分佈 = {dict(cf['zone_dist'])}")
    print(f"    連號對數 = {cf['consecutive_pairs']}")
    print(f"    邊界號 = {cf['boundary_count']} (≤5 or ≥35)")
    print(f"    mod3分佈 = {dict(cf['mod3_dist'])}")
    print(f"    尾數分佈 = {dict(cf['tail_dist'])}")
    
    # 頻率分析
    print(f"\n  各號碼頻率分析:")
    print(f"  {'號碼':>4} {'50期freq':>8} {'100期freq':>9} {'50期赤字':>8} {'100期赤字':>9} {'距上次':>6}")
    print("  " + "-" * 50)
    for n in sorted(actual):
        fa = features['frequency_analysis'][n]
        print(f"  {n:>4} {fa['freq_50']:>8} {fa['freq_100']:>9} {fa['deficit_50']:>8.1f} {fa['deficit_100']:>9.1f} {fa['gap_from_last']:>6}")
    
    # ========== Part 3: 2注/3注方法組合搜尋 ==========
    print("\n" + "=" * 70)
    print("  Part 3: 2注/3注方法組合命中分析")
    print("=" * 70)
    
    # 收集所有方法的預測
    all_bets = {}
    for name, info in topk.items():
        all_bets[name] = set(info['predicted_5'])
    
    # 2注組合搜尋
    print("\n  2注組合 (Top-10):")
    combo_2 = []
    method_list = list(all_bets.keys())
    for i in range(len(method_list)):
        for j in range(i + 1, len(method_list)):
            m1, m2 = method_list[i], method_list[j]
            combined = all_bets[m1] | all_bets[m2]
            hits = len(actual & combined)
            combo_2.append((f"{m1}+{m2}", hits, len(combined), sorted(actual & combined)))
    combo_2.sort(key=lambda x: (-x[1], x[2]))
    
    print(f"  {'組合':<45} {'命中':>4} {'覆蓋':>4} {'命中號碼':>20}")
    print("  " + "-" * 75)
    for name, hits, cov, hit_nums in combo_2[:10]:
        hn = ', '.join(f'{n:02d}' for n in hit_nums)
        print(f"  {name:<45} {hits:>4} {cov:>4}  {hn}")
    
    # 3注組合搜尋
    print("\n  3注組合 (Top-10):")
    combo_3 = []
    for i in range(len(method_list)):
        for j in range(i + 1, len(method_list)):
            for k in range(j + 1, len(method_list)):
                m1, m2, m3 = method_list[i], method_list[j], method_list[k]
                combined = all_bets[m1] | all_bets[m2] | all_bets[m3]
                hits = len(actual & combined)
                combo_3.append((f"{m1}+{m2}+{m3}", hits, len(combined), sorted(actual & combined)))
    combo_3.sort(key=lambda x: (-x[1], x[2]))
    
    print(f"  {'組合':<65} {'命中':>4} {'覆蓋':>4} {'命中號碼':>20}")
    print("  " + "-" * 95)
    for name, hits, cov, hit_nums in combo_3[:10]:
        hn = ', '.join(f'{n:02d}' for n in hit_nums)
        print(f"  {name:<65} {hits:>4} {cov:>4}  {hn}")
    
    # ========== Part 4: 因何遺漏分析 ==========
    print("\n" + "=" * 70)
    print("  Part 4: 遺漏原因分析 — 為何沒預測到這些號碼")
    print("=" * 70)
    
    for n in sorted(actual):
        fa = features['frequency_analysis'][n]
        ranks = features['per_number_rank'][n]
        avg_rank = np.mean(list(ranks.values()))
        best_method = min(ranks, key=ranks.get)
        worst_method = max(ranks, key=ranks.get)
        
        print(f"\n  號碼 {n:02d}:")
        print(f"    平均排名 = {avg_rank:.1f}/39")
        print(f"    最佳方法 = {best_method} (排名 {ranks[best_method]})")
        print(f"    最差方法 = {worst_method} (排名 {ranks[worst_method]})")
        print(f"    50期頻率 = {fa['freq_50']}, 100期頻率 = {fa['freq_100']}")
        print(f"    赤字(50p) = {fa['deficit_50']:.1f}, 赤字(100p) = {fa['deficit_100']:.1f}")
        print(f"    距上次出現 = {fa['gap_from_last']} 期")
        
        if avg_rank > 20:
            print(f"    ⚠️ 此號碼在大多數方法中排名偏後，屬於「方法盲區」")
        elif avg_rank > 10:
            print(f"    △ 此號碼在多數方法中排名中等，屬於「信號模糊區」")
        else:
            print(f"    ★ 此號碼在多數方法中排名前列，理應被捕捉")
    
    # ========== Part 5: 上期連結分析 ==========
    print("\n" + "=" * 70)
    print("  Part 5: 與上期/近期關聯性分析")
    print("=" * 70)
    
    prev = set(history[-1]['numbers'])
    prev2 = set(history[-2]['numbers']) if len(history) >= 2 else set()
    prev3 = set(history[-3]['numbers']) if len(history) >= 3 else set()
    
    print(f"\n  上期(N-1): {sorted(prev)}")
    print(f"  前2期(N-2): {sorted(prev2)}")
    print(f"  前3期(N-3): {sorted(prev3)}")
    print(f"  本期: {sorted(actual)}")
    print(f"\n  與N-1重複: {sorted(actual & prev)} ({len(actual & prev)}個)")
    print(f"  與N-1鄰號: ", end='')
    neighbors = set()
    for n in prev:
        for d in range(-1, 2):
            nn = n + d
            if 1 <= nn <= MAX_NUM:
                neighbors.add(nn)
    print(f"{sorted(actual & neighbors)} ({len(actual & neighbors)}個)")
    print(f"  與N-2重複(Echo): {sorted(actual & prev2)} ({len(actual & prev2)}個)")
    print(f"  與N-3重複: {sorted(actual & prev3)} ({len(actual & prev3)}個)")
    
    # 連號分析
    sorted_actual = sorted(actual)
    consecutive = [(a, b) for a, b in zip(sorted_actual, sorted_actual[1:]) if b - a == 1]
    if consecutive:
        print(f"\n  連號對: {consecutive}")
    else:
        print(f"\n  無連號對")
    
    # 特殊模式
    print(f"\n  特殊模式檢測:")
    # 尾數重複
    tails = [n % 10 for n in actual]
    tail_counter = Counter(tails)
    dup_tails = {t: c for t, c in tail_counter.items() if c > 1}
    if dup_tails:
        nums_by_tail = defaultdict(list)
        for n in actual:
            nums_by_tail[n % 10].append(n)
        for t, c in dup_tails.items():
            print(f"    尾數 {t} 重複 {c} 次: {nums_by_tail[t]}")
    
    # 同十位
    tens = [n // 10 for n in actual]
    ten_counter = Counter(tens)
    dup_tens = {t: c for t, c in ten_counter.items() if c > 1}
    if dup_tens:
        nums_by_ten = defaultdict(list)
        for n in actual:
            nums_by_ten[n // 10].append(n)
        for t, c in dup_tens.items():
            print(f"    十位 {t} 重複 {c} 次: {nums_by_ten[t]}")
    
    # ========== Part 6: 近期趨勢分析 ==========
    print("\n" + "=" * 70)
    print("  Part 6: 近期趨勢 (近20期)")
    print("=" * 70)
    
    recent20 = history[-20:]
    for n in sorted(actual):
        appearances = []
        for i, d in enumerate(recent20):
            if n in d['numbers']:
                appearances.append(len(recent20) - i)  # 幾期前
        if appearances:
            print(f"  號碼 {n:02d}: 近20期出現 {len(appearances)} 次, 最近 {appearances[0]} 期前, 出現位置: {appearances[::-1]}")
        else:
            print(f"  號碼 {n:02d}: 近20期未出現")
    
    print("\n" + "=" * 70)
    print("  分析完成")
    print("=" * 70)
    
    return {
        'topk': topk,
        'features': features, 
        'sorted_methods': sorted_methods,
        'combo_2': combo_2[:10],
        'combo_3': combo_3[:10],
    }


if __name__ == '__main__':
    main()
