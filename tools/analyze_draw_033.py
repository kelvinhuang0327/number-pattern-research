#!/usr/bin/env python3
"""
大樂透 第115000033期 開獎號碼分析腳本
開獎日期: 115/03/06
開獎號碼: [09, 11, 12, 14, 23, 25] 特別號: 4

分析:
1. 所有預測方法各自的預測結果 vs 實際
2. 號碼特徵分析（結構、分布、統計）
3. 各方法命中/遺漏原因
4. 中短長期改進方向
"""
import sys, os, json, sqlite3
import numpy as np
from collections import Counter
from itertools import combinations

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
sys.path.insert(0, os.path.join(project_root, 'tools'))

from quick_predict import (
    _bl_fourier_scores, _bl_markov_scores, _bl_cold_sum_fixed,
    _bl_dev_complement_2bet, _bl_bet5_sum_conditional,
    biglotto_p1_neighbor_cold_2bet,
    biglotto_p1_deviation_5bet,
    enforce_tail_diversity
)

DB_PATH = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
ACTUAL = [9, 11, 12, 14, 23, 25]
SPECIAL = 4
DRAW_ID = '115000033'
MAX_NUM = 49

def load_history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = 'BIG_LOTTO'
        ORDER BY date ASC, draw ASC
    """)
    rows = c.fetchall()
    conn.close()
    draws = []
    for draw_id, date, numbers_str in rows:
        nums = json.loads(numbers_str)
        draws.append({'draw': draw_id, 'date': date, 'numbers': sorted(nums[:6])})
    return draws

def match_count(pred, actual):
    return len(set(pred) & set(actual))

def analyze_draw_characteristics(history, actual):
    """分析這期號碼的統計特徵"""
    print("=" * 80)
    print(f"  第{DRAW_ID}期 開獎號碼分析")
    print(f"  號碼: {actual}  特別號: {SPECIAL}")
    print("=" * 80)
    
    # 1. 基本結構
    s = sum(actual)
    sums_300 = [sum(d['numbers']) for d in history[-300:]]
    mu, sg = np.mean(sums_300), np.std(sums_300)
    print(f"\n【1. 號碼和】")
    print(f"  本期和值: {s}")
    print(f"  近300期均值: {mu:.1f} ± {sg:.1f}")
    print(f"  Z-score: {(s - mu) / sg:.2f}")
    print(f"  ⚠️ 和值 {s} 落在 {'均值內' if abs(s - mu) < sg else '偏離區'}")
    
    # 2. 奇偶比
    odd = sum(1 for n in actual if n % 2 == 1)
    even = 6 - odd
    print(f"\n【2. 奇偶比】")
    print(f"  奇:偶 = {odd}:{even}")
    
    # 3. 大小比 (1-24 小, 25-49 大)
    small = sum(1 for n in actual if n <= 24)
    big = 6 - small
    print(f"\n【3. 大小比】")
    print(f"  小:大 = {small}:{big} (≤24 vs >24)")
    
    # 4. 區間分布
    zones = {f'{i*10+1}-{(i+1)*10}': 0 for i in range(5)}
    for n in actual:
        idx = min((n - 1) // 10, 4)
        key = list(zones.keys())[idx]
        zones[key] += 1
    print(f"\n【4. 區間分布】")
    for z, cnt in zones.items():
        bar = '█' * cnt
        print(f"  {z}: {cnt} {bar}")
    
    # 5. 尾數分布
    tails = Counter(n % 10 for n in actual)
    print(f"\n【5. 尾數分布】")
    for t in range(10):
        if tails.get(t, 0) > 0:
            print(f"  尾數{t}: {tails[t]}個 → {[n for n in actual if n % 10 == t]}")
    
    # 6. 連號分析
    gaps = [actual[i+1] - actual[i] for i in range(5)]
    consecutive = [(actual[i], actual[i+1]) for i in range(5) if gaps[i] == 1]
    print(f"\n【6. 連號分析】")
    print(f"  號碼間距: {gaps}")
    if consecutive:
        print(f"  ⚠️ 連號對: {consecutive}")
    else:
        print(f"  無連號")
    
    # 7. AC值 (號碼間差值的唯一值數量 - 5)
    diffs = set()
    for i in range(6):
        for j in range(i+1, 6):
            diffs.add(abs(actual[i] - actual[j]))
    ac = len(diffs) - 5
    print(f"\n【7. AC值】")
    print(f"  AC = {ac} (共 {len(diffs)} 種差值)")
    
    # 8. 近期頻率分析
    print(f"\n【8. 號碼近期熱度】")
    for window_name, window in [("近30期", 30), ("近50期", 50), ("近100期", 100)]:
        recent = history[-window:]
        freq = Counter(n for d in recent for n in d['numbers'])
        expected = window * 6 / 49
        print(f"  {window_name} (期望值: {expected:.1f}):")
        for n in actual:
            f = freq.get(n, 0)
            dev = f - expected
            indicator = "🔥" if dev > 2 else ("❄️" if dev < -2 else "  ")
            print(f"    #{n:02d}: {f}次 (偏差{dev:+.1f}) {indicator}")
    
    # 9. Gap analysis (距上次出現)
    print(f"\n【9. 間隔分析 (距上次出現)】")
    for n in actual:
        gap = 0
        for d in reversed(history):
            if n in d['numbers']:
                break
            gap += 1
        status = "極冷" if gap > 30 else ("偏冷" if gap > 15 else ("正常" if gap > 5 else "近期熱"))
        print(f"    #{n:02d}: {gap}期前 ({status})")
    
    # 10. 上期鄰號
    prev_nums = history[-1]['numbers']
    neighbors = set()
    for pn in prev_nums:
        for d in [-1, 0, 1]:
            nn = pn + d
            if 1 <= nn <= 49:
                neighbors.add(nn)
    hits_neighbor = set(actual) & neighbors
    print(f"\n【10. 上期鄰號命中】")
    print(f"  上期號碼: {prev_nums}")
    print(f"  鄰域(±1): {sorted(neighbors)}")
    print(f"  本期命中鄰號: {sorted(hits_neighbor)} ({len(hits_neighbor)}個)")
    
    return {
        'sum': s, 'sum_z': (s-mu)/sg,
        'odd_even': f'{odd}:{even}',
        'big_small': f'{small}:{big}',
        'ac': ac, 'consecutive': consecutive,
        'neighbor_hits': len(hits_neighbor),
        'zones': zones, 'gaps': gaps
    }


def run_all_predictions(history):
    """運行所有預測方法並比較"""
    results = {}
    actual_set = set(ACTUAL)
    
    print("\n" + "=" * 80)
    print("  各預測方法結果 對比")
    print("=" * 80)
    
    # === Method 1: P1 鄰號+冷號 2注 ===
    try:
        bets = biglotto_p1_neighbor_cold_2bet(history)
        for i, b in enumerate(bets):
            nums = b['numbers']
            m = match_count(nums, ACTUAL)
            print(f"\n  [P1鄰號+冷號 注{i+1}] {nums}")
            print(f"    命中: {sorted(set(nums) & actual_set)} ({m}個)")
            results[f'P1_neighbor_cold_bet{i+1}'] = {'numbers': nums, 'match': m}
    except Exception as e:
        print(f"  P1鄰號+冷號 Error: {e}")
    
    # === Method 2: P1+偏差互補 5注 ===
    try:
        bets = biglotto_p1_deviation_5bet(history)
        method_names = ['鄰域Fourier+Markov', '冷號Sum約束', '偏差Hot', '偏差Cold', 'Sum條件剩餘']
        for i, b in enumerate(bets):
            nums = b['numbers']
            m = match_count(nums, ACTUAL)
            print(f"\n  [5注系統 注{i+1}: {method_names[i]}] {nums}")
            print(f"    命中: {sorted(set(nums) & actual_set)} ({m}個)")
            results[f'5bet_sys_bet{i+1}_{method_names[i]}'] = {'numbers': nums, 'match': m}
    except Exception as e:
        print(f"  5注系統 Error: {e}")
    
    # === Method 3: Triple Strike ===
    try:
        from tools.predict_biglotto_triple_strike import generate_triple_strike
        bets_raw = generate_triple_strike(history)
        method_names = ['Fourier', 'Cold+Sum', 'TailBalance']
        for i, nums in enumerate(bets_raw):
            m = match_count(nums, ACTUAL)
            print(f"\n  [Triple Strike 注{i+1}: {method_names[i]}] {nums}")
            print(f"    命中: {sorted(set(nums) & actual_set)} ({m}個)")
            results[f'TS_bet{i+1}_{method_names[i]}'] = {'numbers': nums, 'match': m}
    except Exception as e:
        print(f"  Triple Strike Error: {e}")
    
    # === Method 4: 5注正交 (TS3+Markov+FreqOrt) ===
    try:
        from tools.backtest_biglotto_markov_4bet import (
            fourier_rhythm_bet, cold_numbers_bet, tail_balance_bet, markov_orthogonal_bet
        )
        bet1 = fourier_rhythm_bet(history, window=500)
        used = set(bet1)
        bet2 = cold_numbers_bet(history, window=100, exclude=used)
        used.update(bet2)
        bet3 = tail_balance_bet(history, window=100, exclude=used)
        used.update(bet3)
        bet4 = markov_orthogonal_bet(history, exclude=used, markov_window=30)
        used.update(bet4)
        recent = history[-100:]
        freq = Counter(n for d in recent for n in d['numbers'])
        remaining = sorted([n for n in range(1, 50) if n not in used],
                           key=lambda x: -freq.get(x, 0))
        bet5 = sorted(remaining[:6])
        
        ort_bets = [bet1, bet2, bet3, bet4, bet5]
        ort_names = ['Fourier', 'Cold', 'TailBal', 'Markov(30)', 'FreqOrt']
        for i, nums in enumerate(ort_bets):
            m = match_count(nums, ACTUAL)
            print(f"\n  [正交5注 注{i+1}: {ort_names[i]}] {nums}")
            print(f"    命中: {sorted(set(nums) & actual_set)} ({m}個)")
            results[f'Ort5_bet{i+1}_{ort_names[i]}'] = {'numbers': nums, 'match': m}
    except Exception as e:
        print(f"  正交5注 Error: {e}")
    
    # === Method 5: 偏差互補 2注 ===
    try:
        bet1, bet2 = _bl_dev_complement_2bet(history)
        for i, nums in enumerate([bet1, bet2]):
            m = match_count(nums, ACTUAL)
            label = 'Hot偏差' if i == 0 else 'Cold偏差'
            print(f"\n  [偏差互補 注{i+1}: {label}] {nums}")
            print(f"    命中: {sorted(set(nums) & actual_set)} ({m}個)")
            results[f'DevComp_bet{i+1}_{label}'] = {'numbers': nums, 'match': m}
    except Exception as e:
        print(f"  偏差互補 Error: {e}")
    
    # === Method 6: 純 Fourier 分數 Top-6/12/18 ===
    try:
        f_scores = _bl_fourier_scores(history, window=500)
        f_ranked = sorted(f_scores.items(), key=lambda x: -x[1])
        top6 = [n for n, _ in f_ranked[:6]]
        top12 = [n for n, _ in f_ranked[:12]]
        top18 = [n for n, _ in f_ranked[:18]]
        
        m6 = match_count(top6, ACTUAL)
        m12 = match_count(top12, ACTUAL)
        m18 = match_count(top18, ACTUAL)
        print(f"\n  [純Fourier Top6] {sorted(top6)} → 命中 {m6}")
        print(f"  [純Fourier Top12] {sorted(top12)} → 命中 {m12}")
        print(f"  [純Fourier Top18] {sorted(top18)} → 命中 {m18}")
        results['Fourier_top6'] = {'numbers': sorted(top6), 'match': m6}
        results['Fourier_top12'] = {'numbers': sorted(top12), 'match': m12}
        results['Fourier_top18'] = {'numbers': sorted(top18), 'match': m18}
        
        # 顯示 actual 號碼的 Fourier 分數排名
        print(f"\n  [Fourier 分析 - 實際號碼排名]")
        for n in ACTUAL:
            rank = next((i+1 for i, (num, _) in enumerate(f_ranked) if num == n), 49)
            score = f_scores.get(n, 0)
            print(f"    #{n:02d}: 排名第{rank} (分數 {score:.4f})")
    except Exception as e:
        print(f"  Fourier Error: {e}")
    
    # === Method 7: 純 Markov 分數 Top-6/12 ===
    try:
        mk_scores = _bl_markov_scores(history, window=30)
        mk_ranked = sorted(mk_scores.items(), key=lambda x: -x[1])
        top6 = [n for n, _ in mk_ranked[:6]]
        top12 = [n for n, _ in mk_ranked[:12]]
        m6 = match_count(top6, ACTUAL)
        m12 = match_count(top12, ACTUAL)
        print(f"\n  [純Markov(30) Top6] {sorted(top6)} → 命中 {m6}")
        print(f"  [純Markov(30) Top12] {sorted(top12)} → 命中 {m12}")
        results['Markov_top6'] = {'numbers': sorted(top6), 'match': m6}
        
        print(f"\n  [Markov 分析 - 實際號碼排名]")
        for n in ACTUAL:
            rank = next((i+1 for i, (num, _) in enumerate(mk_ranked) if num == n), 49)
            score = mk_scores.get(n, 0)
            print(f"    #{n:02d}: 排名第{rank} (分數 {score:.4f})")
    except Exception as e:
        print(f"  Markov Error: {e}")
    
    # === Method 8: 頻率最高 (近100期) ===
    try:
        recent = history[-100:]
        freq = Counter(n for d in recent for n in d['numbers'])
        freq_ranked = sorted(freq.items(), key=lambda x: -x[1])
        top6 = [n for n, _ in freq_ranked[:6]]
        m6 = match_count(top6, ACTUAL)
        print(f"\n  [頻率Top6 (100期)] {sorted(top6)} → 命中 {m6}")
        results['Freq100_top6'] = {'numbers': sorted(top6), 'match': m6}
    except Exception as e:
        print(f"  Freq Error: {e}")
    
    # === Method 9: 冷號 Top-6 ===
    try:
        cold6 = _bl_cold_sum_fixed(history, exclude=set(), pool_size=12)
        m = match_count(cold6, ACTUAL)
        print(f"\n  [冷號Sum約束 Top6] {cold6} → 命中 {m}")
        results['Cold_Sum_top6'] = {'numbers': cold6, 'match': m}
    except Exception as e:
        print(f"  Cold Error: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("  命中排行榜")
    print("=" * 80)
    sorted_results = sorted(results.items(), key=lambda x: -x[1]['match'])
    for name, r in sorted_results:
        stars = '★' * r['match']
        print(f"  {r['match']}命中 {stars:6s} | {name}: {r['numbers']}")
    
    # Coverage analysis
    all_predicted = set()
    for name, r in results.items():
        if 'top12' not in name and 'top18' not in name:
            all_predicted.update(r['numbers'])
    actual_covered = set(ACTUAL) & all_predicted
    actual_missed = set(ACTUAL) - all_predicted
    print(f"\n  所有方法合計覆蓋: {len(all_predicted)}/49 號")
    print(f"  實際號碼被覆蓋: {sorted(actual_covered)} ({len(actual_covered)}/6)")
    print(f"  完全遺漏號碼: {sorted(actual_missed)}")
    
    return results


def deep_failure_analysis(history, results):
    """深入分析遺漏原因"""
    print("\n" + "=" * 80)
    print("  遺漏原因深度分析")
    print("=" * 80)
    
    actual_set = set(ACTUAL)
    prev_nums = history[-1]['numbers']
    prev_prev_nums = history[-2]['numbers']
    
    # 各號碼的個別分析
    for n in ACTUAL:
        print(f"\n  ─── #{n:02d} 分析 ───")
        
        # Gap
        gap = 0
        for d in reversed(history):
            if n in d['numbers']:
                break
            gap += 1
        
        # Frequency
        freq_30 = sum(1 for d in history[-30:] if n in d['numbers'])
        freq_100 = sum(1 for d in history[-100:] if n in d['numbers'])
        expected_30 = 30 * 6 / 49
        expected_100 = 100 * 6 / 49
        
        # Neighbor
        is_neighbor = any(abs(n - pn) <= 1 for pn in prev_nums)
        
        # Fourier
        f_scores = _bl_fourier_scores(history, window=500)
        f_ranked = sorted(f_scores.items(), key=lambda x: -x[1])
        f_rank = next((i+1 for i, (num, _) in enumerate(f_ranked) if num == n), 49)
        
        # Markov
        mk_scores = _bl_markov_scores(history, window=30)
        mk_ranked = sorted(mk_scores.items(), key=lambda x: -x[1])
        mk_rank = next((i+1 for i, (num, _) in enumerate(mk_ranked) if num == n), 49)
        
        print(f"    間隔: {gap}期 | 頻率: 30期={freq_30}(期望{expected_30:.1f}), 100期={freq_100}(期望{expected_100:.1f})")
        print(f"    上期鄰號: {'✓' if is_neighbor else '✗'}")
        print(f"    Fourier排名: {f_rank}/49 | Markov排名: {mk_rank}/49")
        
        # 為什麼遺漏？
        reasons = []
        if f_rank > 18:
            reasons.append(f"Fourier排名低({f_rank})")
        if mk_rank > 18:
            reasons.append(f"Markov排名低({mk_rank})")
        if not is_neighbor:
            reasons.append("非上期鄰號")
        if freq_100 < expected_100 - 2:
            reasons.append(f"100期偏冷({freq_100} vs {expected_100:.1f})")
        if freq_100 > expected_100 + 2:
            reasons.append("100期偏熱但可能被過濾")
        if gap > 15:
            reasons.append(f"長時間未出(gap={gap})")
        
        if reasons:
            print(f"    ⚠️ 遺漏原因: {', '.join(reasons)}")
        else:
            print(f"    ✓ 理論上應該被多個方法捕捉到")
    
    # 本期特殊模式分析
    print(f"\n\n  ─── 本期特殊模式 ───")
    
    # 連號密集
    has_cluster = any(ACTUAL[i+1] - ACTUAL[i] <= 3 for i in range(5))
    cluster_zone = [(ACTUAL[i], ACTUAL[i+1]) for i in range(5) if ACTUAL[i+1] - ACTUAL[i] <= 3]
    print(f"  密集區域: {cluster_zone}")
    
    # 檢查是否低號集中
    low_count = sum(1 for n in ACTUAL if n <= 25)
    print(f"  低號(≤25)占比: {low_count}/6 = {low_count/6*100:.0f}%")
    
    # 前5期連號出現率
    print(f"\n  ─── 連號歷史特徵 ───")
    consec_history = []
    for d in history[-20:]:
        nums = sorted(d['numbers'])
        consec = [(nums[i], nums[i+1]) for i in range(5) if nums[i+1] - nums[i] == 1]
        consec_history.append({'draw': d['draw'], 'pairs': consec, 'count': len(consec)})
        if len(consec) > 0:
            print(f"    {d['draw']}: 連號 {consec}")


def pattern_discovery(history):
    """尋找可能被忽略的模式"""
    print("\n" + "=" * 80)
    print("  模式探索 - 可能被遺漏的特徵")
    print("=" * 80)
    
    # 1. 連號組模式
    print(f"\n  【連號組頻率分析】")
    consec_counts = Counter()
    for d in history[-300:]:
        nums = sorted(d['numbers'])
        pairs = sum(1 for i in range(5) if nums[i+1] - nums[i] == 1)
        consec_counts[pairs] += 1
    total = sum(consec_counts.values())
    for pairs in sorted(consec_counts.keys()):
        pct = consec_counts[pairs] / total * 100
        print(f"    {pairs}對連號: {consec_counts[pairs]}次 ({pct:.1f}%)")
    
    # 本期有2對連號 (11-12, 14-?→14和12差2不算，但9-11差2也不算)
    actual_sorted = sorted(ACTUAL)
    actual_pairs = [(actual_sorted[i], actual_sorted[i+1]) for i in range(5) if actual_sorted[i+1] - actual_sorted[i] == 1]
    print(f"  本期連號: {actual_pairs}")
    
    # 2. 號碼重複上期模式
    prev = history[-1]['numbers']
    repeat = set(ACTUAL) & set(prev)
    print(f"\n  【前期重複】上期{prev} → 本期重複: {sorted(repeat)} ({len(repeat)}個)")
    
    # 歷史重複統計
    repeat_counts = Counter()
    for i in range(1, min(301, len(history))):
        curr = set(history[-i]['numbers'])
        prev_d = set(history[-i-1]['numbers'])
        repeat_counts[len(curr & prev_d)] += 1
    total = sum(repeat_counts.values())
    print(f"  近300期前後期重複分布:")
    for r in sorted(repeat_counts.keys()):
        print(f"    重複{r}個: {repeat_counts[r]}次 ({repeat_counts[r]/total*100:.1f}%)")
    
    # 3. 小號密集出現
    print(f"\n  【小號密集分析 (≤25)】")
    small_counts = Counter()
    for d in history[-300:]:
        small = sum(1 for n in d['numbers'] if n <= 25)
        small_counts[small] += 1
    total = sum(small_counts.values())
    for s in sorted(small_counts.keys()):
        pct = small_counts[s] / total * 100
        marker = " ← 本期" if s == sum(1 for n in ACTUAL if n <= 25) else ""
        print(f"    {s}個小號: {small_counts[s]}次 ({pct:.1f}%){marker}")
    
    # 4. Sum 均值回歸信號
    sums = [sum(d['numbers']) for d in history]
    recent_sums = sums[-10:]
    mu = np.mean(sums[-300:])
    print(f"\n  【Sum均值回歸】")
    print(f"  300期均值: {mu:.1f}")
    print(f"  近10期和值: {recent_sums}")
    print(f"  近10期平均: {np.mean(recent_sums):.1f}")
    print(f"  本期和值: {sum(ACTUAL)} (偏差: {sum(ACTUAL) - mu:+.1f})")
    
    # 5. 同尾數分析
    print(f"\n  【同尾號分析】")
    tail_groups = {}
    for n in ACTUAL:
        t = n % 10
        tail_groups.setdefault(t, []).append(n)
    for t, nums in sorted(tail_groups.items()):
        if len(nums) > 1:
            print(f"  ⚠️ 尾數{t}: {nums} ({len(nums)}個同尾)")
    
    # 6. 十位數分析
    print(f"\n  【十位數分析】")
    dec_groups = {}
    for n in ACTUAL:
        d = n // 10
        dec_groups.setdefault(d, []).append(n)
    for d, nums in sorted(dec_groups.items()):
        print(f"    {d}X區: {nums}")
    
    # 7. 跨期對比最近5期
    print(f"\n  【跨期模式 - 最近5期】")
    for i in range(5):
        d = history[-(i+1)]
        inter = sorted(set(ACTUAL) & set(d['numbers']))
        print(f"    {d['draw']} {d['numbers']} → 與本期交集: {inter} ({len(inter)}個)")


def feasibility_analysis():
    """可行性分析: 2注/3注覆蓋策略"""
    print("\n" + "=" * 80)
    print("  2注/3注覆蓋可行性分析")
    print("=" * 80)
    
    # 理論基準
    # 大樂透 C(49,6) = 13,983,816 種組合
    # M3+ (命中≥3) 的隨機機率
    from math import comb
    total = comb(49, 6)
    
    # P(M≥3 | 1注) = Σ C(6,k)*C(43,6-k)/C(49,6) for k=3..6
    p_m3_1bet = sum(comb(6, k) * comb(43, 6-k) for k in range(3, 7)) / total
    p_m3_2bet = 1 - (1 - p_m3_1bet) ** 2
    p_m3_3bet = 1 - (1 - p_m3_1bet) ** 3
    
    print(f"\n  M3+ 隨機基準:")
    print(f"    1注: {p_m3_1bet*100:.2f}%")
    print(f"    2注: {p_m3_2bet*100:.2f}%")
    print(f"    3注: {p_m3_3bet*100:.2f}%")
    
    print(f"\n  現行策略 Edge:")
    print(f"    2注 P1鄰號+冷號: +1.41% (即 {p_m3_2bet*100+1.41:.2f}%)")
    print(f"    3注 Triple Strike: +1.46% (即 {p_m3_3bet*100+1.46:.2f}%)")
    print(f"    5注 P1+偏差互補: +2.71% (即 {(1-(1-p_m3_1bet)**5)*100+2.71:.2f}%)")
    
    print(f"\n  覆蓋率理論極限:")
    print(f"    2注 12號/49 = {12/49*100:.1f}%")
    print(f"    3注 18號/49 = {18/49*100:.1f}%")
    print(f"    5注 30號/49 = {30/49*100:.1f}%")


def main():
    history = load_history()
    print(f"資料庫: {len(history)} 期大樂透歷史")
    print(f"最後一期: {history[-1]['draw']} ({history[-1]['date']})")
    
    # 1. 開獎號碼特徵分析
    chars = analyze_draw_characteristics(history, ACTUAL)
    
    # 2. 各預測方法對比
    results = run_all_predictions(history)
    
    # 3. 遺漏原因分析
    deep_failure_analysis(history, results)
    
    # 4. 模式探索
    pattern_discovery(history)
    
    # 5. 可行性分析
    feasibility_analysis()


if __name__ == '__main__':
    main()
