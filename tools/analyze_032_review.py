#!/usr/bin/env python3
"""
115000032 期大樂透檢討分析腳本
開獎號碼: 05, 26, 27, 35, 45, 46 | 特別號: 37
開獎日期: 115/03/03 (2026-03-03)
"""
import sys
import os
import json
import numpy as np
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
sys.path.insert(0, os.path.join(project_root, 'tools'))

from database import DatabaseManager

DRAW_032 = {
    'draw': '115000032',
    'date': '2026-03-03',
    'numbers': [5, 26, 27, 35, 45, 46],
    'special': 37,
}

def load_history():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = db.get_all_draws('BIG_LOTTO')
    history = sorted(all_draws, key=lambda x: (x['date'], x['draw']))
    print(f"載入歷史: {len(history)} 期")
    for i in range(min(5, len(history))):
        d = history[-(i+1)]
        print(f"  {d['draw']} {d['date']} {sorted(d['numbers'])} sp={d.get('special','?')}")
    return history

def analyze_signal_features(history, drawn_numbers):
    MAX_NUM = 49
    actual = set(drawn_numbers)
    
    print("\n" + "="*80)
    print("【信號維度分析】")
    print("="*80)
    
    recent_100 = history[-100:]
    freq_100 = Counter(n for d in recent_100 for n in d['numbers'])
    recent_50 = history[-50:]
    freq_50 = Counter(n for d in recent_50 for n in d['numbers'])
    
    gaps = {}
    for n in range(1, MAX_NUM+1):
        for i in range(len(history)-1, -1, -1):
            if n in history[i]['numbers']:
                gaps[n] = len(history) - 1 - i
                break
        else:
            gaps[n] = len(history)
    
    from quick_predict import _bl_fourier_scores, _bl_markov_scores
    fourier = _bl_fourier_scores(history, window=500)
    fourier_ranked = sorted(range(1, MAX_NUM+1), key=lambda n: -fourier.get(n, 0))
    markov = _bl_markov_scores(history, window=30)
    markov_ranked = sorted(range(1, MAX_NUM+1), key=lambda n: -markov.get(n, 0))
    gap_ranked = sorted(range(1, MAX_NUM+1), key=lambda n: -gaps[n])
    freq_ranked = sorted(range(1, MAX_NUM+1), key=lambda n: -freq_100.get(n, 0))
    freq_50_ranked = sorted(range(1, MAX_NUM+1), key=lambda n: -freq_50.get(n, 0))
    
    expected = len(recent_50) * 6 / MAX_NUM
    deviation = {n: freq_50.get(n, 0) - expected for n in range(1, MAX_NUM+1)}
    
    prev_nums = history[-1]['numbers']
    neighbor_pool = set()
    for n in prev_nums:
        for d in [-1, 0, 1]:
            nn = n + d
            if 1 <= nn <= 49:
                neighbor_pool.add(nn)
    
    echo_nums = set(history[-2]['numbers']) if len(history) >= 2 else set()
    
    z1 = [n for n in drawn_numbers if 1 <= n <= 16]
    z2 = [n for n in drawn_numbers if 17 <= n <= 33]
    z3 = [n for n in drawn_numbers if 34 <= n <= 49]
    odd_count = sum(1 for n in drawn_numbers if n % 2 == 1)
    total_sum = sum(drawn_numbers)
    hist_sums = [sum(d['numbers']) for d in history[-300:]]
    sum_mu, sum_sg = np.mean(hist_sums), np.std(hist_sums)
    
    retained = actual & set(history[-1]['numbers'])
    sorted_nums = sorted(drawn_numbers)
    consec = [(sorted_nums[i], sorted_nums[i+1]) for i in range(len(sorted_nums)-1) if sorted_nums[i+1]-sorted_nums[i]==1]
    tails = Counter(n % 10 for n in drawn_numbers)
    span = max(drawn_numbers) - min(drawn_numbers)
    
    print(f"\n上一期 (031): {sorted(history[-1]['numbers'])} sp={history[-1].get('special','?')}")
    if len(history)>=2: print(f"前兩期 (030): {sorted(history[-2]['numbers'])} sp={history[-2].get('special','?')}")
    if len(history)>=3: print(f"前三期 (029): {sorted(history[-3]['numbers'])} sp={history[-3].get('special','?')}")
    print(f"本期 (032): {sorted(drawn_numbers)} sp={DRAW_032['special']}")
    
    print(f"\n--- 基本統計 ---")
    print(f"Sum: {total_sum} (均值={sum_mu:.1f}, σ={sum_sg:.1f}, z={(total_sum-sum_mu)/sum_sg:.2f})")
    print(f"Zone: Z1(1-16)={len(z1)}{z1}, Z2(17-33)={len(z2)}{z2}, Z3(34-49)={len(z3)}{z3}")
    print(f"奇偶: {odd_count}奇{6-odd_count}偶")
    print(f"保留: {len(retained)} ({sorted(retained) if retained else '無'})")
    print(f"連號: {consec}")
    print(f"尾數: {dict(tails)} (唯一{len(set(n%10 for n in drawn_numbers))}種)")
    print(f"跨距: {span} ({min(drawn_numbers)}→{max(drawn_numbers)})")
    
    print(f"\n--- 各號碼信號 ---")
    print(f"{'#':>3} | {'F100':>4} | {'F50':>3} | {'Gap':>4} | {'FourierR':>8} | {'MarkovR':>7} | {'Dev':>6} | {'鄰':>2} | {'Echo':>4} | 信號分類")
    print("-"*100)
    
    for n in sorted(drawn_numbers + [DRAW_032['special']]):
        f100 = freq_100.get(n, 0)
        f50 = freq_50.get(n, 0)
        gap = gaps[n]
        f_rank = fourier_ranked.index(n) + 1
        m_rank = markov_ranked.index(n) + 1
        dev = deviation.get(n, 0)
        in_nb = "✓" if n in neighbor_pool else "✗"
        in_ec = "✓" if n in echo_nums else "✗"
        signals = []
        if f_rank <= 12: signals.append(f"Fourier(R{f_rank})")
        if m_rank <= 12: signals.append(f"Markov(R{m_rank})")
        if gap >= 10: signals.append(f"Cold(g{gap})")
        if f100 >= 15: signals.append(f"Hot(f{f100})")
        if n in neighbor_pool: signals.append("鄰域")
        if n in echo_nums: signals.append("Echo")
        if dev < -2: signals.append("偏低")
        elif dev > 2: signals.append("偏高")
        if not signals: signals.append("無信號")
        label = "★特" if n == DRAW_032['special'] and n not in DRAW_032['numbers'] else ""
        print(f" {n:>2}{label:>2} | {f100:>4} | {f50:>3} | {gap:>4} | {f_rank:>8} | {m_rank:>7} | {dev:>+6.1f} | {in_nb:>2} | {in_ec:>4} | {', '.join(signals)}")
    
    print(f"\n--- 各信號 Top-12 vs 開獎 ---")
    def show_top(name, ranked, n=12):
        top = ranked[:n]
        hits = set(top) & actual
        print(f"  {name:>14}: {top} → 命中 {len(hits)}/6 ({sorted(hits) if hits else []})")
    
    show_top("Fourier", fourier_ranked)
    show_top("Markov", markov_ranked)
    show_top("Hot100", freq_ranked)
    show_top("Hot50", freq_50_ranked)
    show_top("Gap(冷號)", gap_ranked)
    print(f"  {'鄰域':>14}: {sorted(neighbor_pool)} ({len(neighbor_pool)}個) → 命中 {len(neighbor_pool&actual)}/6 ({sorted(neighbor_pool&actual) if neighbor_pool&actual else []})")
    print(f"  {'Echo':>14}: {sorted(echo_nums)} → 命中 {len(echo_nums&actual)}/6 ({sorted(echo_nums&actual) if echo_nums&actual else []})")
    
    dev_hot = sorted(range(1,MAX_NUM+1), key=lambda n: -deviation.get(n,0))[:12]
    dev_cold = sorted(range(1,MAX_NUM+1), key=lambda n: deviation.get(n,0))[:12]
    show_top("偏高Dev", dev_hot)
    show_top("偏低Dev", dev_cold)
    
    return {
        'freq_100': freq_100, 'freq_50': freq_50, 'gaps': gaps,
        'fourier': fourier, 'fourier_ranked': fourier_ranked,
        'markov': markov, 'markov_ranked': markov_ranked,
        'deviation': deviation, 'neighbor_pool': neighbor_pool,
        'echo_nums': echo_nums, 'sum': total_sum,
        'sum_mu': sum_mu, 'sum_sg': sum_sg,
        'gap_ranked': gap_ranked, 'freq_ranked': freq_ranked,
        'freq_50_ranked': freq_50_ranked,
    }

def simulate_predictions(history):
    actual = set(DRAW_032['numbers'])
    print("\n" + "="*80)
    print("【各預測方法 vs 032期開獎】")
    print("="*80)
    results = {}
    
    from quick_predict import (biglotto_p0_2bet, biglotto_p1_neighbor_cold_2bet,
                                biglotto_triple_strike, biglotto_p1_deviation_5bet,
                                biglotto_5bet_orthogonal)
    
    methods = [
        ('A_P0偏差互補回聲_2注', lambda: biglotto_p0_2bet(history)),
        ('B_P1鄰號冷號v2_2注★定案', lambda: biglotto_p1_neighbor_cold_2bet(history)),
        ('C_TripleStrike_3注★定案', lambda: biglotto_triple_strike(history)),
        ('D_P1偏差互補Sum_5注★定案', lambda: biglotto_p1_deviation_5bet(history)),
        ('E_5注正交TS3Markov', lambda: biglotto_5bet_orthogonal(history)),
    ]
    
    for name, func in methods:
        try:
            results[name] = func()
        except Exception as e:
            print(f"{name} 錯誤: {e}")
    
    print(f"\n實際開獎: {sorted(DRAW_032['numbers'])} | 特別號: {DRAW_032['special']}")
    
    best_method = None
    best_match = 0
    best_single = 0
    
    for name, bets in results.items():
        union_hit = set()
        max_single = 0
        print(f"\n--- {name} ---")
        for i, bet in enumerate(bets):
            nums = set(bet['numbers'])
            hits = nums & actual
            union_hit.update(hits)
            max_single = max(max_single, len(hits))
            m = "✅" if len(hits)>=3 else ""
            print(f"  注{i+1}: {sorted(bet['numbers'])} → 命中{len(hits)} {sorted(hits) if hits else []} {m}")
        
        m3 = "✅ M3+" if max_single >= 3 else "❌"
        print(f"  → 聯集 {len(union_hit)}/6 {sorted(union_hit)} | 最佳單注 {max_single}/6 | {m3}")
        
        if len(union_hit) > best_match or (len(union_hit) == best_match and max_single > best_single):
            best_match = len(union_hit)
            best_single = max_single
            best_method = name
    
    print(f"\n★ 最接近方法: {best_method} (聯集 {best_match}/6, 最佳單注 {best_single}/6)")
    return results

def analyze_missed_patterns(history, features):
    actual = set(DRAW_032['numbers'])
    MAX_NUM = 49
    
    print("\n" + "="*80)
    print("【遺漏特徵深度分析】")
    print("="*80)
    
    # 連號
    consec_count = sum(1 for d in history[-500:] if any(sorted(d['numbers'])[i+1]-sorted(d['numbers'])[i]==1 for i in range(5)))
    print(f"\n1. 連號出現率: {consec_count/500*100:.1f}% (近500期)")
    c2627 = sum(1 for d in history[-500:] if 26 in d['numbers'] and 27 in d['numbers'])
    print(f"   (26,27)共現: {c2627}次/{500}期 ({c2627/500*100:.2f}%)")
    
    # 多連號
    multi_consec = 0
    for d in history[-500:]:
        s = sorted(d['numbers'])
        cc = sum(1 for i in range(5) if s[i+1]-s[i]==1)
        if cc >= 2:
            multi_consec += 1
    print(f"   含2+連號對: {multi_consec}次 ({multi_consec/500*100:.1f}%)")
    print(f"   本期: (26,27) + (45,46) = 2對連號")
    
    # Zone
    zone_dist = Counter()
    for d in history[-500:]:
        z1 = sum(1 for n in d['numbers'] if 1<=n<=16)
        z2 = sum(1 for n in d['numbers'] if 17<=n<=33)
        z3 = sum(1 for n in d['numbers'] if 34<=n<=49)
        zone_dist[(z1,z2,z3)] += 1
    print(f"\n2. Zone分布 (Z1:1,Z2:2,Z3:3):")
    z_count = zone_dist.get((1,2,3), 0)
    print(f"   此分布近500期: {z_count}次 ({z_count/500*100:.1f}%)")
    for d, c in zone_dist.most_common(5):
        print(f"   {d}: {c}次 ({c/500*100:.1f}%)")
    
    # 尾數聚集
    tails = [n%10 for n in sorted(DRAW_032['numbers'])]
    print(f"\n3. 尾數: {tails} → 3個尾數5 + 2個尾數6 + 1個尾數7")
    t5_hist = [sum(1 for n in d['numbers'] if n%10==5) for d in history[-500:]]
    print(f"   近500期每期尾數5出現數: mean={np.mean(t5_hist):.2f}, P(>=3)={sum(1 for x in t5_hist if x>=3)/500*100:.1f}%")
    
    # 號碼週期
    print(f"\n4. 號碼出現週期:")
    for n in sorted(DRAW_032['numbers']):
        apps = [i for i,d in enumerate(history) if n in d['numbers']]
        if len(apps) >= 3:
            rg = [apps[j]-apps[j-1] for j in range(max(1,len(apps)-5), len(apps))]
            ag = np.mean(rg)
            lg = len(history) - apps[-1]
            st = '超期▲' if lg > ag*1.5 else ('到期→' if lg >= ag*0.8 else '正常')
            print(f"   #{n:>2}: avg_gap={ag:.1f}, cur_gap={lg}, {st}")
    
    # 期間保留
    print(f"\n5. 與前期關係:")
    for i in range(1, 6):
        overlap = actual & set(history[-i]['numbers'])
        print(f"   前{i}期: 保留{len(overlap)} {sorted(overlap) if overlap else []}")
    
    # 低號孤立
    sa = sorted(DRAW_032['numbers'])
    print(f"\n6. #5孤立: 間距到次號{sa[1]-sa[0]}，正常每期first-second距離={np.mean([sorted(d['numbers'])[1]-sorted(d['numbers'])[0] for d in history[-300:]]):.1f}")

def analyze_feasibility(history, features):
    actual = set(DRAW_032['numbers'])
    MAX_NUM = 49
    
    print("\n" + "="*80)
    print("【2注/3注可行性】")
    print("="*80)
    
    f_ranked = features['fourier_ranked']
    m_ranked = features['markov_ranked']
    g_ranked = features['gap_ranked']
    fr = features['freq_ranked']
    f50r = features['freq_50_ranked']
    
    pools = {
        'Fourier': f_ranked[:6],
        'Markov': m_ranked[:6],
        'Hot100': fr[:6],
        'Hot50': f50r[:6],
        'Cold100': fr[-6:],
        'Gap(冷)': g_ranked[:6],
        'Neighbor': sorted(features['neighbor_pool'])[:6],
        'DevHot': sorted(range(1,MAX_NUM+1), key=lambda n: -features['deviation'][n])[:6],
        'DevCold': sorted(range(1,MAX_NUM+1), key=lambda n: features['deviation'][n])[:6],
    }
    
    print("\n信號 Top-6 命中:")
    for name, pool in pools.items():
        hits = set(pool) & actual
        print(f"  {name:>12}: {pool} → {len(hits)}/6 {sorted(hits) if hits else []}")
    
    print("\n2注組合(Oracle):")
    sn = list(pools.keys())
    c2 = []
    for i in range(len(sn)):
        for j in range(i+1, len(sn)):
            u = set(pools[sn[i]]) | set(pools[sn[j]])
            h = u & actual
            c2.append((sn[i], sn[j], len(h), sorted(h)))
    c2.sort(key=lambda x: -x[2])
    for c in c2[:8]:
        print(f"  {c[0]:>10}+{c[1]:<12} → {c[2]}/6 {c[3]}")

def main():
    print("="*80)
    print("115000032 期大樂透全方位檢討")
    print(f"開獎: {sorted(DRAW_032['numbers'])} | 特別號: {DRAW_032['special']}")
    print("="*80)
    
    history = load_history()
    if len(history) < 100:
        print("數據不足")
        return
    
    features = analyze_signal_features(history, DRAW_032['numbers'])
    results = simulate_predictions(history)
    analyze_missed_patterns(history, features)
    analyze_feasibility(history, features)
    print("\n" + "="*80 + "\n分析完成\n" + "="*80)

if __name__ == '__main__':
    main()
