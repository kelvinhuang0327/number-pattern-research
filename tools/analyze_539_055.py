#!/usr/bin/env python3
"""
今彩539 第115000055期 檢討分析
開獎: 03, 12, 20, 21, 27
日期: 115/03/02 (2026-03-02)
"""
import sys, os, json
import numpy as np
from numpy.fft import fft, fftfreq
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

# Import prediction functions
sys.path.insert(0, os.path.join(project_root, 'tools'))
from quick_predict import (
    _539_fourier_scores, _539_acb_bet, _539_markov_bet,
    _539_midfreq_bet, _539_lift_pair_bet, predict_539
)

ACTUAL = {3, 12, 20, 21, 27}
ACTUAL_LIST = sorted(ACTUAL)
MAX_NUM = 39
PICK = 5

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='DAILY_539')
    all_draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))

    # Find draw 055
    target_idx = None
    for i, d in enumerate(all_draws):
        draw_str = str(d['draw'])
        if draw_str.endswith('055') and '115' in draw_str:
            target_idx = i
            break

    if target_idx is None:
        # Try finding by approximate position (latest draws)
        print("找不到確切的 115000055 期，使用最新期作為參考")
        # Find the draw closest to 2026-03-02
        for i, d in enumerate(all_draws):
            if d.get('date', '') >= '2026-03-02':
                target_idx = i
                break
        if target_idx is None:
            target_idx = len(all_draws) - 1

    target = all_draws[target_idx]
    hist = all_draws[:target_idx]  # Only use data before this draw
    
    print("=" * 80)
    print(f"  今彩539 第115000055期 檢討分析")
    print(f"  開獎號碼: {', '.join(f'{n:02d}' for n in ACTUAL_LIST)}")
    print(f"  實際找到: draw={target.get('draw')}, date={target.get('date')}, numbers={target.get('numbers')}")
    print(f"  可用歷史期數: {len(hist)}")
    print("=" * 80)
    
    # ==========================================
    # SECTION 1: 各方法預測結果 vs 開獎
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 1: 各方法預測 vs 開獎對比")
    print("=" * 80)
    
    results = {}
    
    # Method 1: ACB 1注
    acb1 = _539_acb_bet(hist)
    acb1_hits = set(acb1) & ACTUAL
    results['ACB_1bet'] = {'bets': [acb1], 'hits': acb1_hits, 'max_match': len(acb1_hits)}
    print(f"\n  ACB 1注: {acb1}")
    print(f"    命中: {sorted(acb1_hits)} ({len(acb1_hits)}/{PICK})")
    
    # Method 2: MidFreq+ACB 2注
    midfreq1 = _539_midfreq_bet(hist)
    acb2 = _539_acb_bet(hist, exclude=set(midfreq1))
    results['MidFreq_ACB_2bet'] = {
        'bets': [midfreq1, acb2],
        'hits_per_bet': [set(midfreq1) & ACTUAL, set(acb2) & ACTUAL],
        'union_hits': (set(midfreq1) | set(acb2)) & ACTUAL,
        'max_match': max(len(set(midfreq1) & ACTUAL), len(set(acb2) & ACTUAL))
    }
    print(f"\n  MidFreq+ACB 2注:")
    print(f"    注1 MidFreq: {midfreq1} -> 命中 {sorted(set(midfreq1) & ACTUAL)} ({len(set(midfreq1) & ACTUAL)})")
    print(f"    注2 ACB:     {acb2} -> 命中 {sorted(set(acb2) & ACTUAL)} ({len(set(acb2) & ACTUAL)})")
    print(f"    聯集命中: {sorted((set(midfreq1)|set(acb2)) & ACTUAL)} ({len((set(midfreq1)|set(acb2)) & ACTUAL)})")
    
    # Method 3: F4Cold 3注
    bets_3, strategy_3 = predict_539(hist, {}, 3)
    bets_3_nums = [b['numbers'] for b in bets_3]
    print(f"\n  F4Cold 3注 ({strategy_3}):")
    all_3_hits = set()
    max_3 = 0
    for i, b in enumerate(bets_3_nums, 1):
        hits = set(b) & ACTUAL
        all_3_hits |= hits
        max_3 = max(max_3, len(hits))
        print(f"    注{i}: {b} -> 命中 {sorted(hits)} ({len(hits)})")
    print(f"    聯集命中: {sorted(all_3_hits)} ({len(all_3_hits)}), 最大單注: {max_3}")
    results['F4Cold_3bet'] = {'bets': bets_3_nums, 'union_hits': all_3_hits, 'max_match': max_3}
    
    # Method 4: F4Cold 5注
    bets_5, strategy_5 = predict_539(hist, {}, 5)
    bets_5_nums = [b['numbers'] for b in bets_5]
    print(f"\n  F4Cold 5注 ({strategy_5}):")
    all_5_hits = set()
    max_5 = 0
    for i, b in enumerate(bets_5_nums, 1):
        hits = set(b) & ACTUAL
        all_5_hits |= hits
        max_5 = max(max_5, len(hits))
        print(f"    注{i}: {b} -> 命中 {sorted(hits)} ({len(hits)})")
    print(f"    聯集命中: {sorted(all_5_hits)} ({len(all_5_hits)}), 最大單注: {max_5}")
    results['F4Cold_5bet'] = {'bets': bets_5_nums, 'union_hits': all_5_hits, 'max_match': max_5}
    
    # Method 5: Markov 單注
    markov = _539_markov_bet(hist)
    markov_hits = set(markov) & ACTUAL
    results['Markov_1bet'] = {'bets': [markov], 'hits': markov_hits, 'max_match': len(markov_hits)}
    print(f"\n  Markov 1注: {markov}")
    print(f"    命中: {sorted(markov_hits)} ({len(markov_hits)})")
    
    # Method 6: LiftPair 單注
    liftpair = _539_lift_pair_bet(hist)
    liftpair_hits = set(liftpair) & ACTUAL
    results['LiftPair_1bet'] = {'bets': [liftpair], 'hits': liftpair_hits, 'max_match': len(liftpair_hits)}
    print(f"\n  LiftPair 1注: {liftpair}")
    print(f"    命中: {sorted(liftpair_hits)} ({len(liftpair_hits)})")
    
    # Method 7: Markov+MidFreq+ACB 3注 (P3a candidate)
    markov_bet = _539_markov_bet(hist)
    excl1 = set(markov_bet)
    midfreq_bet = _539_midfreq_bet(hist, exclude=excl1)
    excl2 = excl1 | set(midfreq_bet)
    acb_bet = _539_acb_bet(hist, exclude=excl2)
    p3a_bets = [markov_bet, midfreq_bet, acb_bet]
    all_p3a = set()
    max_p3a = 0
    print(f"\n  P3a: Markov+MidFreq+ACB 3注:")
    for i, b in enumerate(p3a_bets, 1):
        hits = set(b) & ACTUAL
        all_p3a |= hits
        max_p3a = max(max_p3a, len(hits))
        print(f"    注{i}: {b} -> 命中 {sorted(hits)} ({len(hits)})")
    print(f"    聯集命中: {sorted(all_p3a)} ({len(all_p3a)}), 最大單注: {max_p3a}")
    results['P3a_Markov_MidFreq_ACB'] = {'bets': p3a_bets, 'union_hits': all_p3a, 'max_match': max_p3a}
    
    # ==========================================
    # SECTION 2: 開獎號碼信號分析
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 2: 開獎號碼詳細信號分析")
    print("=" * 80)
    
    # Fourier scores
    fourier_sc = _539_fourier_scores(hist, window=500)
    fourier_ranked = sorted(fourier_sc, key=lambda x: -fourier_sc[x])
    
    # Frequency analysis
    recent_100 = hist[-100:]
    recent_50 = hist[-50:]
    recent_30 = hist[-30:]
    freq_100 = Counter(n for d in recent_100 for n in d['numbers'] if n <= MAX_NUM)
    freq_50 = Counter(n for d in recent_50 for n in d['numbers'] if n <= MAX_NUM)
    freq_30 = Counter(n for d in recent_30 for n in d['numbers'] if n <= MAX_NUM)
    expected_100 = 100 * 5 / 39
    expected_50 = 50 * 5 / 39
    expected_30 = 30 * 5 / 39

    # Gap analysis
    last_seen = {}
    for i, d in enumerate(hist):
        for n in d['numbers']:
            if n <= MAX_NUM:
                last_seen[n] = i
    gaps = {n: len(hist) - 1 - last_seen.get(n, -1) for n in range(1, 40)}
    
    # ACB scores
    acb_recent = hist[-100:]
    acb_counter = Counter()
    for n in range(1, 40):
        acb_counter[n] = 0
    for d in acb_recent:
        for n in d['numbers']:
            acb_counter[n] += 1
    acb_exp = len(acb_recent) * 5 / 39
    acb_scores_dict = {}
    for n in range(1, 40):
        freq_deficit = acb_exp - acb_counter[n]
        gap_score = gaps[n] / (len(acb_recent) / 2)
        boundary_bonus = 1.2 if (n <= 5 or n >= 35) else 1.0
        mod3_bonus = 1.1 if n % 3 == 0 else 1.0
        acb_scores_dict[n] = (freq_deficit * 0.4 + gap_score * 0.6) * boundary_bonus * mod3_bonus
    acb_ranked = sorted(acb_scores_dict, key=lambda x: -acb_scores_dict[x])
    
    # MidFreq scores (distance from expected)
    midfreq_dist = {n: abs(freq_100[n] - expected_100) for n in range(1, 40)}
    midfreq_ranked = sorted(midfreq_dist, key=lambda x: midfreq_dist[x])
    
    # Previous draw numbers
    prev_draw = hist[-1]
    prev_nums = set(prev_draw['numbers'])
    prev2_draw = hist[-2]
    prev2_nums = set(prev2_draw['numbers'])
    
    print(f"\n  上期 (054): {sorted(prev_nums)}")
    print(f"  前2期 (053): {sorted(prev2_nums)}")
    
    print(f"\n  {'號碼':>4} | {'Fourier排名':>10} | {'ACB排名':>8} | {'MidFreq排名':>10} | {'freq100':>7} | {'freq50':>6} | {'freq30':>6} | {'gap':>4} | {'freq_deficit':>12} | {'zone':>4} | {'特徵':>20}")
    print("  " + "-" * 120)
    
    for n in ACTUAL_LIST:
        f_rank = fourier_ranked.index(n) + 1 if n in fourier_ranked else 99
        a_rank = acb_ranked.index(n) + 1
        m_rank = midfreq_ranked.index(n) + 1
        zone = 'Z1' if n <= 13 else ('Z2' if n <= 26 else 'Z3')
        deficit = acb_exp - acb_counter[n]
        
        features = []
        if f_rank <= 10: features.append(f'Fourier-Top10')
        if f_rank <= 5: features[-1] = 'Fourier-Top5'
        if a_rank <= 5: features.append('ACB-Top5')
        if m_rank <= 10: features.append('MidFreq-Top10')
        if freq_100[n] >= expected_100 * 1.3: features.append('HOT')
        if freq_100[n] <= expected_100 * 0.7: features.append('COLD')
        if gaps[n] >= 10: features.append('HighGap')
        if n in prev_nums: features.append('鄰域')
        if n in prev2_nums: features.append('EchoLag2')
        if not features: features.append('中性/無信號')
        
        print(f"  {n:4d} | {f_rank:10d} | {a_rank:8d} | {m_rank:10d} | {freq_100[n]:7d} | {freq_50[n]:6d} | {freq_30[n]:6d} | {gaps[n]:4d} | {deficit:12.2f} | {zone:>4} | {', '.join(features)}")
    
    # ==========================================
    # SECTION 3: 號碼結構特徵分析
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 3: 號碼結構特徵分析")
    print("=" * 80)
    
    total_sum = sum(ACTUAL_LIST)
    expected_sum = 5 * 40 / 2  # E[sum] = 5 * (1+39)/2 = 100
    odd_count = sum(1 for n in ACTUAL_LIST if n % 2 == 1)
    even_count = 5 - odd_count
    
    # Zone distribution
    z1 = [n for n in ACTUAL_LIST if n <= 13]
    z2 = [n for n in ACTUAL_LIST if 14 <= n <= 26]
    z3 = [n for n in ACTUAL_LIST if n >= 27]
    
    # Consecutive pairs
    consec_pairs = [(ACTUAL_LIST[i], ACTUAL_LIST[i+1]) for i in range(len(ACTUAL_LIST)-1) 
                    if ACTUAL_LIST[i+1] - ACTUAL_LIST[i] == 1]
    
    # Tail distribution (last digit)
    tails = [n % 10 for n in ACTUAL_LIST]
    tail_counter = Counter(tails)
    
    # Gap between consecutive numbers
    diffs = [ACTUAL_LIST[i+1] - ACTUAL_LIST[i] for i in range(len(ACTUAL_LIST)-1)]
    
    # 歷史統計 Sum
    all_sums = [sum(d['numbers'][:5]) for d in hist[-500:] if len(d['numbers']) >= 5]
    sum_mean = np.mean(all_sums)
    sum_std = np.std(all_sums)
    
    print(f"\n  Sum = {total_sum} (期望 ≈ {expected_sum:.0f}, 歷史500期均值={sum_mean:.1f}±{sum_std:.1f})")
    print(f"  奇偶 = {odd_count}奇{even_count}偶")
    print(f"  Zone: Z1={z1}, Z2={z2}, Z3={z3} (Z1:{len(z1)} Z2:{len(z2)} Z3:{len(z3)})")
    print(f"  連號: {consec_pairs if consec_pairs else '無'}")
    print(f"  號碼間距: {diffs}")
    print(f"  尾數分佈: {dict(tail_counter)}")
    
    # Sum z-score
    sum_z = (total_sum - sum_mean) / sum_std if sum_std > 0 else 0
    print(f"  Sum Z-score: {sum_z:.2f} ({'偏低' if sum_z < -1 else '偏高' if sum_z > 1 else '正常'})")
    
    # 上期保留分析
    retained = ACTUAL & prev_nums
    retained2 = ACTUAL & prev2_nums
    print(f"\n  上期保留: {sorted(retained) if retained else '無'} ({len(retained)}個)")
    print(f"  前2期保留: {sorted(retained2) if retained2 else '無'} ({len(retained2)}個)")
    
    # 歷史保留率統計
    retain_counts = []
    for i in range(1, min(501, len(hist))):
        r = set(hist[-i]['numbers'][:5]) & set(hist[-i-1]['numbers'][:5]) if i < len(hist) else set()
        retain_counts.append(len(r))
    retain_mean = np.mean(retain_counts)
    print(f"  歷史平均保留數: {retain_mean:.2f}")
    
    # ==========================================
    # SECTION 4: 各方法排名中開獎號碼的位置
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 4: 各方法排名矩陣 (Top 20)")
    print("=" * 80)
    
    print(f"\n  {'排名':>4} | {'Fourier':>10} | {'ACB':>10} | {'MidFreq':>10} | {'Markov':>10}")
    print("  " + "-" * 60)
    
    # Markov scores
    markov_scores = Counter()
    markov_w = hist[-30:]
    transitions = {}
    for i in range(len(markov_w) - 1):
        for pn in markov_w[i]['numbers']:
            if pn > MAX_NUM: continue
            if pn not in transitions: transitions[pn] = Counter()
            for nn in markov_w[i + 1]['numbers']:
                if nn <= MAX_NUM: transitions[pn][nn] += 1
    for pn in prev_nums:
        if pn > MAX_NUM: continue
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for nn, cnt in trans.items():
                markov_scores[nn] += cnt / total
    markov_ranked = sorted(markov_scores, key=lambda x: -markov_scores[x])
    
    for rank in range(20):
        f_num = fourier_ranked[rank] if rank < len(fourier_ranked) else '-'
        a_num = acb_ranked[rank] if rank < len(acb_ranked) else '-'
        m_num = midfreq_ranked[rank] if rank < len(midfreq_ranked) else '-'
        mk_num = markov_ranked[rank] if rank < len(markov_ranked) else '-'
        
        f_mark = ' ★' if f_num in ACTUAL else ''
        a_mark = ' ★' if a_num in ACTUAL else ''
        m_mark = ' ★' if m_num in ACTUAL else ''
        mk_mark = ' ★' if mk_num in ACTUAL else ''
        
        print(f"  {rank+1:4d} | {str(f_num)+f_mark:>10} | {str(a_num)+a_mark:>10} | {str(m_num)+m_mark:>10} | {str(mk_num)+mk_mark:>10}")
    
    # 總結每個方法前N名中有多少開獎號碼
    print(f"\n  === 各方法 Top-N 覆蓋開獎號碼數 ===")
    for topn in [5, 10, 15, 20, 25]:
        f_cov = len(set(fourier_ranked[:topn]) & ACTUAL)
        a_cov = len(set(acb_ranked[:topn]) & ACTUAL)
        m_cov = len(set(midfreq_ranked[:topn]) & ACTUAL)
        mk_cov = len(set(markov_ranked[:topn]) & ACTUAL) if len(markov_ranked) >= topn else len(set(markov_ranked) & ACTUAL)
        print(f"  Top-{topn:2d}: Fourier={f_cov}/5, ACB={a_cov}/5, MidFreq={m_cov}/5, Markov={mk_cov}/5")
    
    # ==========================================
    # SECTION 5: 歷史趨勢分析 (近5期)
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 5: 近5期趨勢")
    print("=" * 80)
    
    for i in range(5, 0, -1):
        d = hist[-i]
        nums = sorted(d['numbers'][:5])
        s = sum(nums)
        odd = sum(1 for n in nums if n % 2 == 1)
        z1c = sum(1 for n in nums if n <= 13)
        z2c = sum(1 for n in nums if 14 <= n <= 26)
        z3c = sum(1 for n in nums if n >= 27)
        print(f"  {d['draw']}: {nums} | sum={s:3d} | {odd}奇{5-odd}偶 | Z({z1c},{z2c},{z3c})")
    
    # 055 target
    print(f"  ---------- 開獎 ----------")
    print(f"  {'055':>12}: {ACTUAL_LIST} | sum={total_sum:3d} | {odd_count}奇{even_count}偶 | Z({len(z1)},{len(z2)},{len(z3)})")
    
    # ==========================================
    # SECTION 6: 2注/3注最優理論組合分析
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 6: 理論最優2注/3注組合 (事後分析)")
    print("=" * 80)
    
    # 哪些方法的排名中，開獎號碼 rank加總最小？
    # 找出如果結合多個方法的排名，哪個組合最能覆蓋
    print(f"\n  如果能完美組合，哪個 2注組合最接近？")
    
    # Simulate: for each method pair, take top-5 from each (with exclusion)
    methods = {
        'Fourier': lambda excl: [n for n in fourier_ranked if n not in excl][:5],
        'ACB': lambda excl: [n for n in acb_ranked if n not in excl][:5], 
        'MidFreq': lambda excl: [n for n in midfreq_ranked if n not in excl][:5],
        'Markov': lambda excl: [n for n in markov_ranked if n not in excl][:5],
        'LiftPair': lambda excl: _539_lift_pair_bet(hist, exclude=excl),
    }
    
    print(f"\n  {'2注組合':<25} | {'注1命中':>6} | {'注2命中':>6} | {'聯集':>4} | {'最大單注':>8}")
    print("  " + "-" * 70)
    
    best_2bet = None
    best_2bet_union = 0
    best_2bet_max = 0
    
    for m1_name, m1_fn in methods.items():
        for m2_name, m2_fn in methods.items():
            if m1_name >= m2_name:
                continue
            bet1 = m1_fn(set())
            bet2 = m2_fn(set(bet1))
            h1 = len(set(bet1) & ACTUAL)
            h2 = len(set(bet2) & ACTUAL)
            union = len((set(bet1) | set(bet2)) & ACTUAL)
            max_single = max(h1, h2)
            print(f"  {m1_name+'+'+m2_name:<25} | {h1:>6} | {h2:>6} | {union:>4} | {max_single:>8}")
            
            if union > best_2bet_union or (union == best_2bet_union and max_single > best_2bet_max):
                best_2bet = f"{m1_name}+{m2_name}"
                best_2bet_union = union
                best_2bet_max = max_single
    
    print(f"\n  ★ 最佳2注組合: {best_2bet} (聯集命中={best_2bet_union}, 最大單注={best_2bet_max})")
    
    # 3注組合分析
    print(f"\n  {'3注組合':<35} | {'注1':>3} | {'注2':>3} | {'注3':>3} | {'聯集':>4} | {'max':>4}")
    print("  " + "-" * 70)
    
    best_3bet = None
    best_3bet_union = 0
    best_3bet_max = 0
    
    method_names = list(methods.keys())
    for combo in combinations(method_names, 3):
        bet1 = methods[combo[0]](set())
        bet2 = methods[combo[1]](set(bet1))
        bet3 = methods[combo[2]](set(bet1) | set(bet2))
        h1 = len(set(bet1) & ACTUAL)
        h2 = len(set(bet2) & ACTUAL)
        h3 = len(set(bet3) & ACTUAL)
        union = len((set(bet1) | set(bet2) | set(bet3)) & ACTUAL)
        max_single = max(h1, h2, h3)
        print(f"  {'+'.join(combo):<35} | {h1:>3} | {h2:>3} | {h3:>3} | {union:>4} | {max_single:>4}")
        
        if union > best_3bet_union or (union == best_3bet_union and max_single > best_3bet_max):
            best_3bet = '+'.join(combo)
            best_3bet_union = union
            best_3bet_max = max_single
    
    print(f"\n  ★ 最佳3注組合: {best_3bet} (聯集命中={best_3bet_union}, 最大單注={best_3bet_max})")

    # ==========================================
    # SECTION 7: 漏號根因分析
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 7: 各開獎號碼為何被遺漏")
    print("=" * 80)
    
    for n in ACTUAL_LIST:
        f_rank = fourier_ranked.index(n) + 1 if n in fourier_ranked else 99
        a_rank = acb_ranked.index(n) + 1
        m_rank = midfreq_ranked.index(n) + 1
        mk_rank = markov_ranked.index(n) + 1 if n in markov_ranked else 99
        
        reasons = []
        if f_rank > 15: reasons.append(f'Fourier排名過低({f_rank})，週期信號弱')
        elif f_rank > 10: reasons.append(f'Fourier處中段({f_rank})，被前10名擠出')
        else: reasons.append(f'Fourier排名OK({f_rank})')
        
        if a_rank > 15: reasons.append(f'ACB排名過低({a_rank})，非異常候選')
        elif a_rank > 5: reasons.append(f'ACB中段({a_rank})')
        else: reasons.append(f'ACB信號強({a_rank})')
        
        if m_rank > 15: reasons.append(f'MidFreq排名低({m_rank})，偏離均值')
        elif m_rank > 5: reasons.append(f'MidFreq中段({m_rank})')
        else: reasons.append(f'MidFreq信號OK({m_rank})')
        
        if mk_rank > 15: reasons.append(f'Markov排名低({mk_rank})，轉移弱')
        elif mk_rank > 5: reasons.append(f'Markov中段({mk_rank})')
        else: reasons.append(f'Markov信號強({mk_rank})')
        
        # 結論
        top5_count = sum(1 for r in [f_rank, a_rank, m_rank, mk_rank] if r <= 5)
        top10_count = sum(1 for r in [f_rank, a_rank, m_rank, mk_rank] if r <= 10)
        
        print(f"\n  #{n:02d}: 在{top5_count}個方法Top5, {top10_count}個方法Top10")
        for r in reasons:
            print(f"    - {r}")
        
        if top5_count == 0:
            print(f"    ⚠️ 結論: 所有方法均未將此號列入強信號區")
        elif top5_count >= 2:
            print(f"    ✓ 結論: 多方法共識但未命中，屬覆蓋範圍內")
    
    # ==========================================
    # SECTION 8: 尚未探索的特徵空間
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 8: 潛在未利用特徵分析")
    print("=" * 80)
    
    # Feature 1: 號碼間距模式
    print(f"\n  1. 號碼間距模式:")
    print(f"     055期間距: {diffs}")
    hist_diffs = []
    for d in hist[-200:]:
        nums = sorted(d['numbers'][:5])
        hist_diffs.append([nums[i+1]-nums[i] for i in range(4)])
    avg_diffs = [np.mean([hd[i] for hd in hist_diffs]) for i in range(4)]
    print(f"     歷史200期平均間距: [{', '.join(f'{d:.1f}' for d in avg_diffs)}]")
    
    # Feature 2: 連號特徵
    consec_rate = sum(1 for hd in hist_diffs if min(hd) == 1) / len(hist_diffs) * 100
    print(f"\n  2. 連號出現率: {consec_rate:.1f}% (055期: {'有' if consec_pairs else '無'}連號)")
    print(f"     055期連號: {consec_pairs}")
    
    # Feature 3: Sum regime
    print(f"\n  3. Sum regime分析:")
    recent_sums = [sum(d['numbers'][:5]) for d in hist[-20:]]
    print(f"     近20期Sum: {recent_sums}")
    print(f"     055期Sum={total_sum}, 近20期均值={np.mean(recent_sums):.1f}, 趨勢={'上升' if recent_sums[-1] > recent_sums[0] else '下降'}")
    
    # Feature 4: 尾數聚集度
    print(f"\n  4. 尾數聚集度:")
    print(f"     055期尾數: {tails}, 重複尾數: {[t for t,c in tail_counter.items() if c > 1]}")
    
    # Feature 5: 跨期特徵
    print(f"\n  5. 跨期保留/移動:")
    if len(hist) >= 3:
        prev_set = set(hist[-1]['numbers'][:5])
        prev2_set = set(hist[-2]['numbers'][:5])
        shifted = [(n, min(abs(n-p) for p in prev_set)) for n in ACTUAL_LIST]
        print(f"     各號碼到上期最近距離: {[(n, d) for n, d in shifted]}")
    
    # Feature 6: 奇偶/大小組合碼
    big_count = sum(1 for n in ACTUAL_LIST if n >= 20)
    small_count = 5 - big_count
    print(f"\n  6. 大小比: {big_count}大{small_count}小")
    
    # Feature 7: 質數分析
    primes = {2,3,5,7,11,13,17,19,23,29,31,37}
    prime_count = sum(1 for n in ACTUAL_LIST if n in primes)
    print(f"\n  7. 質數: {sorted(set(ACTUAL_LIST) & primes)} ({prime_count}個)")
    
    # Feature 8: 號碼模式(mod3, mod5)
    mod3_dist = Counter(n % 3 for n in ACTUAL_LIST)
    mod5_dist = Counter(n % 5 for n in ACTUAL_LIST)
    print(f"\n  8. mod3分佈: {dict(mod3_dist)}, mod5分佈: {dict(mod5_dist)}")
    
    # ==========================================
    # 最終總結
    # ==========================================
    print("\n" + "=" * 80)
    print("  最終比較總結")
    print("=" * 80)
    
    summary = []
    for name, r in results.items():
        union_h = len(r.get('union_hits', r.get('hits', set())))
        max_h = r.get('max_match', 0)
        bets_count = len(r['bets'])
        m3_hit = '✅' if max_h >= 3 else '❌'
        summary.append((name, bets_count, union_h, max_h, m3_hit))
    
    print(f"\n  {'方法':<35} | {'注數':>4} | {'聯集命中':>8} | {'最大單注':>8} | {'M3+':>4}")
    print("  " + "-" * 70)
    for name, bets_count, union_h, max_h, m3 in sorted(summary, key=lambda x: (-x[3], -x[2])):
        print(f"  {name:<35} | {bets_count:>4} | {union_h:>8} | {max_h:>8} | {m3:>4}")
    
    print("\n" + "=" * 80)
    print("  分析完成")
    print("=" * 80)


if __name__ == '__main__':
    main()
