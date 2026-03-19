#!/usr/bin/env python3
"""
第115000058期 今彩539 開獎檢討分析
開獎號碼: 01, 04, 08, 12, 36
日期: 115/03/05

分析項目:
1. 各預測方法對比 - 哪個最接近
2. 未命中原因深度分析
3. 號碼特徵分析 (頻率、間隔、尾數、區間、Fourier、Markov)
4. 2注/3注覆蓋可行性
5. 短中長期特徵識別
"""
import sys, os
import numpy as np
from numpy.fft import fft, fftfreq
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from tools.quick_predict import (
    _539_acb_bet, _539_midfreq_bet, _539_markov_bet,
    _539_fourier_scores, _539_lift_pair_bet,
    enforce_tail_diversity
)

ACTUAL = {1, 4, 8, 12, 36}
ACTUAL_LIST = sorted(ACTUAL)
TARGET_DRAW = '115000058'

def load_history_before_draw(db, draw_id):
    """載入目標期之前的所有歷史數據
    115000058 尚未入庫，使用全部歷史(至115000057)作為預測基礎"""
    history = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(history, key=lambda x: (x['date'], x['draw']))
    
    # 115000058 尚未入庫，使用所有資料作為歷史
    last = history[-1]
    print(f"📌 目標期: {draw_id} (開獎號碼: {ACTUAL_LIST})")
    print(f"📌 上一期: {last['draw']} -> 號碼: {sorted(last['numbers'])}")
    print(f"📊 歷史期數: {len(history)} 期 (用於預測)")
    
    # 檢查上期與本期重疊
    prev_set = set(last['numbers'])
    overlap = ACTUAL & prev_set
    if overlap:
        print(f"🔴 重要發現: 與上期重複 {len(overlap)} 個號碼: {sorted(overlap)}")
    
    # 建立虛擬 target
    target = {'draw': draw_id, 'date': '2026/03/05', 'numbers': ACTUAL_LIST}
    return history, target


def analyze_predictions(history):
    """運行所有預測方法並比較"""
    print("\n" + "=" * 70)
    print("  📊 各預測方法對比分析")
    print("=" * 70)
    print(f"  實際開獎: {ACTUAL_LIST}")
    print()

    results = {}

    # 1. ACB 異常捕捉
    acb = _539_acb_bet(history)
    hits_acb = len(set(acb) & ACTUAL)
    results['ACB異常捕捉'] = {'numbers': acb, 'hits': hits_acb}

    # 2. MidFreq 均值回歸
    midfreq = _539_midfreq_bet(history)
    hits_mid = len(set(midfreq) & ACTUAL)
    results['MidFreq均值回歸'] = {'numbers': midfreq, 'hits': hits_mid}

    # 3. Markov 轉移
    markov = _539_markov_bet(history)
    hits_markov = len(set(markov) & ACTUAL)
    results['Markov轉移'] = {'numbers': markov, 'hits': hits_markov}

    # 4. Fourier 週期 Top-5
    f_scores = _539_fourier_scores(history, window=500)
    f_ranked = sorted(f_scores, key=lambda x: -f_scores[x])
    fourier_top5 = sorted(f_ranked[:5])
    hits_fourier = len(set(fourier_top5) & ACTUAL)
    results['Fourier週期Top5'] = {'numbers': fourier_top5, 'hits': hits_fourier}

    # 5. Lift Pair 共現
    lift = _539_lift_pair_bet(history)
    hits_lift = len(set(lift) & ACTUAL)
    results['LiftPair共現'] = {'numbers': lift, 'hits': hits_lift}

    # 6. 2注組合: MidFreq + ACB
    acb_2 = _539_acb_bet(history, exclude=set(midfreq))
    combined_2bet = set(midfreq) | set(acb_2)
    hits_2bet = len(combined_2bet & ACTUAL)
    results['2注MidFreq+ACB'] = {'numbers': sorted(combined_2bet), 'hits': hits_2bet,
                                  'bet1': midfreq, 'bet2': acb_2}

    # 7. 3注組合: ACB + Markov + Fourier
    markov_3 = _539_markov_bet(history, exclude=set(acb))
    excl3 = set(acb) | set(markov_3)
    f_bet3 = [n for n in f_ranked if f_scores[n] > 0 and n not in excl3][:5]
    combined_3bet = set(acb) | set(markov_3) | set(f_bet3)
    hits_3bet = len(combined_3bet & ACTUAL)
    results['3注ACB+Markov+Fourier'] = {'numbers': sorted(combined_3bet), 'hits': hits_3bet,
                                         'bet1': acb, 'bet2': markov_3, 'bet3': sorted(f_bet3)}

    # 排序顯示
    sorted_results = sorted(results.items(), key=lambda x: -x[1]['hits'])
    for i, (name, data) in enumerate(sorted_results, 1):
        hit_nums = sorted(set(data['numbers']) & ACTUAL)
        miss_nums = sorted(ACTUAL - set(data['numbers']))
        marker = "⭐" if data['hits'] >= 2 else "  "
        print(f"  {marker} {i}. {name}")
        print(f"     預測: {sorted(data['numbers'][:10])}{'...' if len(data['numbers']) > 10 else ''}")
        print(f"     命中: {data['hits']}/5 → {hit_nums}")
        print(f"     遺漏: {miss_nums}")
        if 'bet1' in data:
            print(f"     注1: {data['bet1']}")
            print(f"     注2: {data['bet2']}")
            if 'bet3' in data:
                print(f"     注3: {data['bet3']}")
        print()

    return results


def analyze_number_features(history):
    """分析每個開獎號碼的特徵，找出為何被遺漏"""
    print("\n" + "=" * 70)
    print("  🔍 開獎號碼個別特徵分析")
    print("=" * 70)

    recent100 = history[-100:]
    recent50 = history[-50:]
    recent30 = history[-30:]
    all_freq = Counter()
    freq100 = Counter()
    freq50 = Counter()
    freq30 = Counter()

    for d in history:
        for n in d['numbers']:
            all_freq[n] += 1
    for d in recent100:
        for n in d['numbers']:
            freq100[n] += 1
    for d in recent50:
        for n in d['numbers']:
            freq50[n] += 1
    for d in recent30:
        for n in d['numbers']:
            freq30[n] += 1

    expected_100 = 100 * 5 / 39
    expected_50 = 50 * 5 / 39
    expected_30 = 30 * 5 / 39

    # 計算每個號碼的 gap
    last_seen = {}
    for i, d in enumerate(history):
        for n in d['numbers']:
            last_seen[n] = i
    current = len(history)
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, 40)}

    # ACB scores
    acb_scores = {}
    for n in range(1, 40):
        freq_deficit = expected_100 - freq100[n]
        gap_score = gaps[n] / (100 / 2)
        boundary_bonus = 1.2 if (n <= 5 or n >= 35) else 1.0
        mod3_bonus = 1.1 if n % 3 == 0 else 1.0
        acb_scores[n] = (freq_deficit * 0.4 + gap_score * 0.6) * boundary_bonus * mod3_bonus
    acb_ranked = sorted(acb_scores, key=lambda x: -acb_scores[x])

    # Fourier scores
    f_scores = _539_fourier_scores(history, window=500)
    f_ranked = sorted(f_scores, key=lambda x: -f_scores[x])

    # Markov scores
    markov_scores = Counter()
    recent_mk = history[-30:]
    transitions = {}
    for i in range(len(recent_mk) - 1):
        for pn in recent_mk[i]['numbers']:
            if pn not in transitions:
                transitions[pn] = Counter()
            for nn in recent_mk[i + 1]['numbers']:
                transitions[pn][nn] += 1
    prev_nums = history[-1]['numbers']
    for pn in prev_nums:
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for n, cnt in trans.items():
                markov_scores[n] += cnt / total
    mk_ranked = sorted(range(1, 40), key=lambda x: -markov_scores.get(x, 0))

    # MidFreq scores (距離期望值)
    midfreq_dist = {n: abs(freq100[n] - expected_100) for n in range(1, 40)}
    mf_ranked = sorted(midfreq_dist, key=lambda x: midfreq_dist[x])

    print(f"\n  {'號碼':>4} | {'頻率100':>7} | {'頻率50':>6} | {'頻率30':>6} | {'期望':>5} | {'偏差':>6} | {'Gap':>4} | {'ACB排名':>6} | {'Fourier排':>8} | {'Markov排':>7} | {'MidFreq排':>8} | {'區間':>4} | {'尾數':>4}")
    print("  " + "-" * 120)

    for n in ACTUAL_LIST:
        acb_rank = acb_ranked.index(n) + 1
        f_rank = f_ranked.index(n) + 1 if n in f_ranked else 39
        mk_rank = mk_ranked.index(n) + 1
        mf_rank = mf_ranked.index(n) + 1
        zone = "低" if n <= 13 else ("中" if n <= 26 else "高")
        tail = n % 10
        deviation = freq100[n] - expected_100

        marker = ""
        if acb_rank <= 5: marker += "[ACB✓]"
        if f_rank <= 5: marker += "[FFT✓]"
        if mk_rank <= 5: marker += "[MK✓]"
        if mf_rank <= 5: marker += "[MF✓]"

        print(f"  #{n:02d}  | {freq100[n]:7.1f} | {freq50[n]:6.1f} | {freq30[n]:6.1f} | {expected_100:5.1f} | {deviation:+6.1f} | {gaps[n]:4d} | {acb_rank:6d} | {f_rank:8d} | {mk_rank:7d} | {mf_rank:8d} | {zone:>4} | {tail:4d}  {marker}")

    print()

    # 各方法的 Top-10 排名
    print("  📊 各方法 Top-10:")
    print(f"  ACB Top10:     {acb_ranked[:10]}")
    print(f"  Fourier Top10: {f_ranked[:10]}")
    print(f"  Markov Top10:  {mk_ranked[:10]}")
    print(f"  MidFreq Top10: {mf_ranked[:10]}")
    print()

    # 分析每個號碼為何被遺漏
    print("  📋 個別號碼遺漏原因:")
    for n in ACTUAL_LIST:
        acb_rank = acb_ranked.index(n) + 1
        f_rank = f_ranked.index(n) + 1 if n in f_ranked else 39
        mk_rank = mk_ranked.index(n) + 1
        mf_rank = mf_ranked.index(n) + 1
        deviation = freq100[n] - expected_100

        reasons = []
        if acb_rank > 5:
            if deviation > 0:
                reasons.append(f"頻率偏高(+{deviation:.1f})，ACB不選熱號")
            elif gaps[n] < 5:
                reasons.append(f"最近才出現(gap={gaps[n]})，ACB gap分不足")
            else:
                reasons.append(f"ACB排名{acb_rank}，僅差{acb_rank-5}名")

        if f_rank > 5:
            reasons.append(f"Fourier週期未共振(排名{f_rank})")

        if mk_rank > 5:
            reasons.append(f"上期→本期轉移弱(Markov排名{mk_rank})")

        if mf_rank > 5:
            reasons.append(f"MidFreq距期望遠(排名{mf_rank})")

        print(f"\n  #{n:02d}: {'、'.join(reasons) if reasons else '至少一個方法可捕捉'}")

    return {
        'acb_ranked': acb_ranked,
        'f_ranked': f_ranked,
        'mk_ranked': mk_ranked,
        'mf_ranked': mf_ranked,
        'freq100': freq100,
        'gaps': gaps,
        'acb_scores': acb_scores,
        'f_scores': f_scores,
        'markov_scores': markov_scores,
    }


def analyze_pattern_features(history, target_draw):
    """分析本期的整體特徵模式"""
    print("\n" + "=" * 70)
    print("  🧩 本期整體特徵模式分析")
    print("=" * 70)

    nums = ACTUAL_LIST

    # 1. 區間分布
    zones = {'低(1-13)': 0, '中(14-26)': 0, '高(27-39)': 0}
    for n in nums:
        if n <= 13: zones['低(1-13)'] += 1
        elif n <= 26: zones['中(14-26)'] += 1
        else: zones['高(27-39)'] += 1
    print(f"\n  區間分布: {zones}")

    # 2. 奇偶比
    odd = sum(1 for n in nums if n % 2 == 1)
    even = 5 - odd
    print(f"  奇偶比: {odd}:{even}")

    # 3. 尾數分布
    tails = Counter(n % 10 for n in nums)
    print(f"  尾數分布: {dict(tails)}")

    # 4. 號碼間距
    diffs = [nums[i+1] - nums[i] for i in range(len(nums)-1)]
    print(f"  相鄰間距: {diffs} (平均: {np.mean(diffs):.1f}, 最大: {max(diffs)})")

    # 5. 號碼和
    total = sum(nums)
    print(f"  號碼和: {total}")

    # 6. 歷史號碼和分布
    recent_sums = [sum(d['numbers']) for d in history[-100:]]
    mean_sum = np.mean(recent_sums)
    std_sum = np.std(recent_sums)
    z_sum = (total - mean_sum) / std_sum if std_sum > 0 else 0
    print(f"  號碼和統計: 期望={mean_sum:.1f}, σ={std_sum:.1f}, z={z_sum:.2f}")

    # 7. 連號分析
    consecutive = sum(1 for i in range(len(nums)-1) if nums[i+1] - nums[i] == 1)
    print(f"  連號對數: {consecutive}")

    # 8. 與上期重複
    prev_nums = set(history[-1]['numbers'])
    overlap = ACTUAL & prev_nums
    print(f"  與上期重複: {sorted(overlap)} ({len(overlap)}個)")

    # 9. 號碼在近期出現頻率分類
    freq100 = Counter()
    for d in history[-100:]:
        for n in d['numbers']:
            freq100[n] += 1
    expected = 100 * 5 / 39

    hot = [n for n in nums if freq100[n] > expected * 1.3]
    warm = [n for n in nums if expected * 0.7 <= freq100[n] <= expected * 1.3]
    cold = [n for n in nums if freq100[n] < expected * 0.7]
    print(f"\n  溫度分類 (100期基準):")
    print(f"    熱號(>期望*1.3): {hot}")
    print(f"    溫號(期望±30%):  {warm}")
    print(f"    冷號(<期望*0.7): {cold}")

    # 10. 歷史區間分布統計
    zone_hist = {'4低0中1高': 0, '3低1中1高': 0, '其他': 0}
    for d in history[-200:]:
        ns = sorted(d['numbers'])
        z = [0, 0, 0]
        for n in ns:
            if n <= 13: z[0] += 1
            elif n <= 26: z[1] += 1
            else: z[2] += 1
        key = f"{z[0]}低{z[1]}中{z[2]}高"
        if key in zone_hist:
            zone_hist[key] += 1
        else:
            zone_hist['其他'] += 1

    this_zone = f"{zones['低(1-13)']}低{zones['中(14-26)']}中{zones['高(27-39)']}高"
    print(f"\n  本期區間模式: {this_zone}")

    # 全面的區間模式統計
    zone_patterns = Counter()
    for d in history[-500:]:
        ns = sorted(d['numbers'])
        z = [0, 0, 0]
        for n in ns:
            if n <= 13: z[0] += 1
            elif n <= 26: z[1] += 1
            else: z[2] += 1
        zone_patterns[f"{z[0]}低{z[1]}中{z[2]}高"] += 1

    total_draws = min(500, len(history))
    print(f"  區間模式頻率 (近500期):")
    for pat, cnt in sorted(zone_patterns.items(), key=lambda x: -x[1])[:8]:
        pct = cnt / total_draws * 100
        marker = " ← 本期" if pat == this_zone else ""
        print(f"    {pat}: {cnt}次 ({pct:.1f}%){marker}")

    return {
        'zones': zones,
        'odd_even': (odd, even),
        'tails': tails,
        'diffs': diffs,
        'total_sum': total,
        'z_sum': z_sum,
        'consecutive': consecutive,
        'overlap': overlap,
        'hot': hot, 'warm': warm, 'cold': cold,
        'this_zone': this_zone,
    }


def analyze_short_mid_long_term(history):
    """短中長期特徵對比"""
    print("\n" + "=" * 70)
    print("  📈 短/中/長期特徵對比")
    print("=" * 70)

    windows = [('短期(30期)', 30), ('中期(100期)', 100), ('長期(500期)', 500)]

    for label, w in windows:
        recent = history[-w:] if len(history) >= w else history
        freq = Counter()
        for d in recent:
            for n in d['numbers']:
                freq[n] += 1

        expected = len(recent) * 5 / 39

        # 各開獎號碼在此窗口的表現
        print(f"\n  {label}:")
        for n in ACTUAL_LIST:
            dev = freq[n] - expected
            dev_pct = dev / expected * 100 if expected > 0 else 0
            status = "🔥熱" if dev > expected * 0.3 else ("❄️冷" if dev < -expected * 0.3 else "🌤溫")
            all_ranks = sorted(range(1, 40), key=lambda x: -freq[x])
            rank = all_ranks.index(n) + 1
            print(f"    #{n:02d}: 頻率={freq[n]:.0f} 期望={expected:.1f} 偏差={dev:+.1f}({dev_pct:+.0f}%) {status} 排名={rank}")

    # 趨勢分析：近10期每個號碼出現次數
    print(f"\n  🔄 極短期動量 (近10期):")
    recent10 = history[-10:]
    freq10 = Counter()
    for d in recent10:
        for n in d['numbers']:
            freq10[n] += 1
    for n in ACTUAL_LIST:
        expected_10 = 10 * 5 / 39
        status = "上升" if freq10[n] > expected_10 else ("下降" if freq10[n] < expected_10 * 0.5 else "平穩")
        print(f"    #{n:02d}: 出現{freq10[n]}次 (期望{expected_10:.1f}) → {status}")


def analyze_coverage_feasibility(history):
    """2注和3注覆蓋可行性分析"""
    print("\n" + "=" * 70)
    print("  🎯 多注覆蓋可行性分析")
    print("=" * 70)

    # 理論覆蓋率
    print("\n  理論覆蓋率:")
    for bets in [1, 2, 3]:
        coverage = bets * 5 / 39 * 100
        print(f"    {bets}注: {bets*5}/{39} = {coverage:.1f}% 覆蓋")

    # 用不同方法組合 2注，分析最佳正交組合
    print("\n  📊 2注正交組合分析:")
    methods = [
        ('ACB', _539_acb_bet(history)),
        ('MidFreq', _539_midfreq_bet(history)),
        ('Markov', _539_markov_bet(history)),
        ('Fourier', sorted([n for n in sorted(_539_fourier_scores(history, 500),
                   key=lambda x: -_539_fourier_scores(history, 500)[x])[:5]])),
        ('LiftPair', _539_lift_pair_bet(history)),
    ]

    print(f"\n  {'組合':>20} | {'覆蓋號碼數':>8} | {'命中':>4} | {'命中號碼':>12} | {'重疊':>4}")
    print("  " + "-" * 70)

    best_2bet = None
    best_2bet_hits = 0

    for i in range(len(methods)):
        for j in range(i+1, len(methods)):
            name = f"{methods[i][0]}+{methods[j][0]}"
            combined = set(methods[i][1]) | set(methods[j][1])
            overlap = set(methods[i][1]) & set(methods[j][1])
            hits = len(combined & ACTUAL)
            hit_nums = sorted(combined & ACTUAL)
            print(f"  {name:>20} | {len(combined):8d} | {hits:4d} | {str(hit_nums):>12} | {len(overlap):4d}")
            if hits > best_2bet_hits or (hits == best_2bet_hits and len(overlap) < (len(set(best_2bet[1]) & set(best_2bet[2])) if best_2bet else 99)):
                best_2bet = (name, methods[i][1], methods[j][1])
                best_2bet_hits = hits

    print(f"\n  🏆 最佳2注組合: {best_2bet[0] if best_2bet else 'N/A'} (命中{best_2bet_hits})")

    # 3注組合
    print(f"\n  📊 3注正交組合分析:")
    print(f"\n  {'組合':>30} | {'覆蓋':>4} | {'命中':>4} | {'命中號碼':>18}")
    print("  " + "-" * 75)

    best_3bet = None
    best_3bet_hits = 0

    for i in range(len(methods)):
        for j in range(i+1, len(methods)):
            for k in range(j+1, len(methods)):
                name = f"{methods[i][0]}+{methods[j][0]}+{methods[k][0]}"
                combined = set(methods[i][1]) | set(methods[j][1]) | set(methods[k][1])
                hits = len(combined & ACTUAL)
                hit_nums = sorted(combined & ACTUAL)
                if hits >= 2:
                    print(f"  {name:>30} | {len(combined):4d} | {hits:4d} | {str(hit_nums):>18}")
                if hits > best_3bet_hits:
                    best_3bet = (name, methods[i][1], methods[j][1], methods[k][1])
                    best_3bet_hits = hits

    print(f"\n  🏆 最佳3注組合: {best_3bet[0] if best_3bet else 'N/A'} (命中{best_3bet_hits})")

    # 如果用排除機制的正交組合
    print(f"\n  📊 正交排除法 (有排除) 組合:")
    # 2注: MidFreq + ACB(exclude)
    mf = _539_midfreq_bet(history)
    acb_excl = _539_acb_bet(history, exclude=set(mf))
    combined_2 = set(mf) | set(acb_excl)
    hits_2 = len(combined_2 & ACTUAL)
    print(f"    MidFreq+ACB(排除): 覆蓋{len(combined_2)} 命中{hits_2} → {sorted(combined_2 & ACTUAL)}")

    # 3注: ACB + Markov(排除) + Fourier(排除)
    acb3 = _539_acb_bet(history)
    mk3 = _539_markov_bet(history, exclude=set(acb3))
    excl3 = set(acb3) | set(mk3)
    f_scores = _539_fourier_scores(history, 500)
    f3 = sorted([n for n in sorted(f_scores, key=lambda x: -f_scores[x])
                 if f_scores[n] > 0 and n not in excl3][:5])
    combined_3 = set(acb3) | set(mk3) | set(f3)
    hits_3 = len(combined_3 & ACTUAL)
    print(f"    ACB+Markov+Fourier(排除): 覆蓋{len(combined_3)} 命中{hits_3} → {sorted(combined_3 & ACTUAL)}")
    print(f"      注1(ACB):     {acb3} → 命中 {sorted(set(acb3) & ACTUAL)}")
    print(f"      注2(Markov):  {mk3} → 命中 {sorted(set(mk3) & ACTUAL)}")
    print(f"      注3(Fourier): {f3} → 命中 {sorted(set(f3) & ACTUAL)}")


def analyze_what_would_catch(history):
    """分析什麼方法/特徵能捕捉到這組號碼"""
    print("\n" + "=" * 70)
    print("  🔬 潛在可捕捉特徵研究")
    print("=" * 70)

    # 1. 號碼的 gap 分布 — 是否存在 gap 規律
    print("\n  1. Gap 規律分析:")
    for n in ACTUAL_LIST:
        gaps_list = []
        last = -1
        for i, d in enumerate(history[-200:]):
            if n in d['numbers']:
                if last >= 0:
                    gaps_list.append(i - last)
                last = i
        if gaps_list:
            print(f"    #{n:02d}: 近200期gaps = {gaps_list[-5:]} 平均={np.mean(gaps_list):.1f} σ={np.std(gaps_list):.1f}")

    # 2. 共現分析 — 開獎號碼之前是否常一起出現
    print("\n  2. 共現Lift分析 (開獎號碼間):")
    recent500 = history[-500:]
    total = len(recent500)
    freq500 = Counter()
    pair_freq = Counter()
    for d in recent500:
        ns = sorted(d['numbers'])
        for n in ns:
            freq500[n] += 1
        for pair in combinations(ns, 2):
            pair_freq[pair] += 1

    for pair in combinations(ACTUAL_LIST, 2):
        pa = freq500[pair[0]] / total
        pb = freq500[pair[1]] / total
        pab = pair_freq[pair] / total
        lift = pab / (pa * pb) if pa * pb > 0 else 0
        print(f"    ({pair[0]:02d},{pair[1]:02d}): Lift={lift:.2f} 共現{pair_freq[pair]}次 {'⚡高' if lift > 1.5 else ''}")

    # 3. 上期號碼轉移分析
    print("\n  3. 上期轉移路徑分析:")
    prev_nums = sorted(history[-1]['numbers'])
    print(f"    上期號碼: {prev_nums}")
    for pn in prev_nums:
        trans = Counter()
        for i in range(len(history) - 1):
            if pn in history[i]['numbers']:
                for nn in history[i + 1]['numbers']:
                    trans[nn] += 1
        total_trans = sum(trans.values())
        if total_trans > 0:
            hit_trans = [(n, trans[n], trans[n]/total_trans*100) for n in ACTUAL_LIST if trans[n] > 0]
            print(f"    #{pn:02d} → 本期命中: {[(f'#{n:02d}({cnt}次,{pct:.1f}%)') for n, cnt, pct in hit_trans]}")

    # 4. 尾數規律
    print("\n  4. 尾數週期分析:")
    tail_hist = []
    for d in history[-20:]:
        tails = sorted([n % 10 for n in d['numbers']])
        tail_hist.append(tails)
    print(f"    近20期尾數:")
    for i, t in enumerate(tail_hist[-10:]):
        draw_idx = len(history) - 10 + i
        print(f"      {history[draw_idx]['draw']}: {t}")
    print(f"    本期尾數: {sorted([n % 10 for n in ACTUAL_LIST])}")

    # 5. Sum趨勢
    print("\n  5. Sum值趨勢:")
    sums = [sum(d['numbers']) for d in history[-20:]]
    sums.append(sum(ACTUAL_LIST))
    print(f"    近20期Sum: {sums[:-1]}")
    print(f"    本期Sum:   {sums[-1]}")
    print(f"    趨勢: {'上升' if sums[-1] > np.mean(sums[:-1]) else '下降'} (期望={np.mean(sums[:-1]):.1f})")

    # 6. 低頻號碼36的特殊分析
    print("\n  6. #36 (高區極端號) 特殊分析:")
    freq_windows = [30, 50, 100, 200, 500]
    for w in freq_windows:
        recent = history[-w:] if len(history) >= w else history
        cnt = sum(1 for d in recent for n in d['numbers'] if n == 36)
        expected = len(recent) * 5 / 39
        pct = cnt / expected * 100 if expected > 0 else 0
        print(f"    {w}期: 出現{cnt}次 期望{expected:.1f} ({pct:.0f}%)")


def analyze_ensemble_potential(history):
    """分析集成學習和自動特徵發現的可行性"""
    print("\n" + "=" * 70)
    print("  🤖 AI/ML 改進可行性分析")
    print("=" * 70)

    # 1. 特徵覆蓋矩陣
    print("\n  1. 特徵覆蓋矩陣 (每個方法對39個號碼的排名):")

    acb_scores = {}
    freq100 = Counter()
    recent100 = history[-100:]
    for d in recent100:
        for n in d['numbers']:
            freq100[n] += 1
    expected = 100 * 5 / 39
    current = len(recent100)
    last_seen = {}
    for i, d in enumerate(recent100):
        for n in d['numbers']:
            last_seen[n] = i
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, 40)}
    for n in range(1, 40):
        freq_deficit = expected - freq100[n]
        gap_score = gaps[n] / (100 / 2)
        boundary_bonus = 1.2 if (n <= 5 or n >= 35) else 1.0
        mod3_bonus = 1.1 if n % 3 == 0 else 1.0
        acb_scores[n] = (freq_deficit * 0.4 + gap_score * 0.6) * boundary_bonus * mod3_bonus

    f_scores = _539_fourier_scores(history, 500)
    mk_scores = Counter()
    recent_mk = history[-30:]
    transitions = {}
    for i in range(len(recent_mk) - 1):
        for pn in recent_mk[i]['numbers']:
            if pn not in transitions:
                transitions[pn] = Counter()
            for nn in recent_mk[i + 1]['numbers']:
                transitions[pn][nn] += 1
    prev_nums = history[-1]['numbers']
    for pn in prev_nums:
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for n, cnt in trans.items():
                mk_scores[n] += cnt / total

    mf_scores = {n: -abs(freq100[n] - expected) for n in range(1, 40)}

    # 綜合排名
    all_methods = {
        'ACB': acb_scores,
        'Fourier': f_scores,
        'Markov': dict(mk_scores),
        'MidFreq': mf_scores,
    }

    # Borda count ensemble
    print("\n  2. Borda Count 集成排名:")
    borda = Counter()
    for method_name, scores in all_methods.items():
        ranked = sorted(scores, key=lambda x: -scores.get(x, 0))
        for rank, n in enumerate(ranked):
            borda[n] += (39 - rank)  # 排名越高分數越高

    borda_ranked = sorted(borda, key=lambda x: -borda[x])
    print(f"    Borda Top-10: {borda_ranked[:10]}")
    borda_top5 = borda_ranked[:5]
    borda_hits = len(set(borda_top5) & ACTUAL)
    print(f"    Borda Top-5 命中: {borda_hits} → {sorted(set(borda_top5) & ACTUAL)}")

    # Borda Top-10 作為 2注
    borda_top10 = borda_ranked[:10]
    borda_10_hits = len(set(borda_top10) & ACTUAL)
    print(f"    Borda Top-10 命中: {borda_10_hits} → {sorted(set(borda_top10) & ACTUAL)}")

    # Weighted ensemble
    print("\n  3. 加權集成 (根據歷史Edge加權):")
    weights = {'ACB': 3.0, 'Fourier': 1.5, 'Markov': 2.0, 'MidFreq': 2.5}
    weighted = Counter()
    for method_name, scores in all_methods.items():
        w = weights[method_name]
        # 標準化分數
        values = list(scores.values())
        if values:
            min_v = min(values)
            max_v = max(values)
            rng = max_v - min_v if max_v != min_v else 1
            for n, s in scores.items():
                weighted[n] += ((s - min_v) / rng) * w

    weighted_ranked = sorted(weighted, key=lambda x: -weighted[x])
    print(f"    加權 Top-10: {weighted_ranked[:10]}")
    weighted_top5 = weighted_ranked[:5]
    w_hits = len(set(weighted_top5) & ACTUAL)
    print(f"    加權 Top-5 命中: {w_hits} → {sorted(set(weighted_top5) & ACTUAL)}")

    # 4. Entropy-based diversity
    print("\n  4. 信息熵多樣性分析:")
    for method_name, scores in all_methods.items():
        values = np.array(list(scores.values()))
        if values.min() < 0:
            values = values - values.min()
        if values.sum() > 0:
            probs = values / values.sum()
            entropy = -np.sum(probs * np.log2(probs + 1e-10))
            max_entropy = np.log2(39)
            print(f"    {method_name}: 熵={entropy:.2f}/{max_entropy:.2f} 集中度={1-entropy/max_entropy:.2f}")

    # 5. 特徵相關性 (方法間相關係數)
    print("\n  5. 方法間相關性 (Spearman):")
    from scipy.stats import spearmanr
    method_arrays = {}
    for name, scores in all_methods.items():
        arr = np.array([scores.get(n, 0) for n in range(1, 40)])
        method_arrays[name] = arr

    names = list(method_arrays.keys())
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            corr, pval = spearmanr(method_arrays[names[i]], method_arrays[names[j]])
            print(f"    {names[i]} vs {names[j]}: ρ={corr:.3f} (p={pval:.3f})")

    # 6. ML可行性評估
    print("\n  6. 自動學習機制可行性評估:")
    print("    a) Gradient Boosting on 多維特徵:")
    print("       - 特徵: gap, freq(多窗口), 尾數, 區間, sum偏差, 共現lift")
    print("       - 預期: 可捕捉非線性特徵交互")
    print("       - 風險: 過擬合 (39個號碼×少量正例)")
    print("    b) RNN/LSTM 序列建模:")
    print("       - 特徵: 近N期出現序列")
    print("       - 預期: 捕捉時序依賴")
    print("       - 風險: 資料量不足，彩票本質隨機性")
    print("    c) Multi-Armed Bandit 自適應選擇:")
    print("       - 機制: UCB/Thompson Sampling 動態權重")
    print("       - 預期: 自動選擇當期最有效方法")
    print("       - 風險: exploration vs exploitation 平衡")
    print("    d) Feature Engineering Automation:")
    print("       - 機制: 自動生成和測試新特徵組合")
    print("       - 預期: 發現人工未考慮的特徵")
    print("       - 風險: combinatorial explosion")


def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)

    # 載入數據
    history, target = load_history_before_draw(db, TARGET_DRAW)

    if not history:
        print("❌ 無法載入歷史數據")
        return

    # 驗證目標期號碼 (115000058 為手動輸入，不在DB中)
    print(f"  開獎號碼: {ACTUAL_LIST}")

    # 1. 各方法對比
    results = analyze_predictions(history)

    # 2. 號碼特徵分析
    features = analyze_number_features(history)

    # 3. 整體特徵模式
    patterns = analyze_pattern_features(history, target)

    # 4. 短中長期對比
    analyze_short_mid_long_term(history)

    # 5. 多注覆蓋可行性
    analyze_coverage_feasibility(history)

    # 6. 潛在可捕捉特徵
    analyze_what_would_catch(history)

    # 7. AI/ML改進可行性
    analyze_ensemble_potential(history)

    print("\n" + "=" * 70)
    print("  分析完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
