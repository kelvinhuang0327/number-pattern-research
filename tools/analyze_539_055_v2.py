#!/usr/bin/env python3
"""
今彩539 第115000055期 精確檢討分析
開獎: 03, 12, 20, 21, 27
日期: 115/03/02 (2026-03-02)
使用歷史: 截至 115000054 (2026-03-01)
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
    hist = sorted(all_draws, key=lambda x: (x['date'], x['draw']))
    
    print(f"  資料庫最新期: {hist[-1]['draw']} ({hist[-1]['date']})")
    print(f"  總期數: {len(hist)}")
    print(f"  上期: {hist[-1]['draw']} -> {sorted(hist[-1]['numbers'][:5])}")
    print(f"  前2期: {hist[-2]['draw']} -> {sorted(hist[-2]['numbers'][:5])}")
    
    prev_nums = set(hist[-1]['numbers'][:5])
    prev2_nums = set(hist[-2]['numbers'][:5])
    
    print("\n" + "=" * 80)
    print(f"  今彩539 第115000055期 檢討分析")
    print(f"  開獎號碼: {', '.join(f'{n:02d}' for n in ACTUAL_LIST)}")
    print("=" * 80)
    
    # ==========================================
    # SECTION 1: 各方法預測結果
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 1: 各方法預測 vs 開獎對比")
    print("=" * 80)
    
    results = {}
    
    # 1. ACB 1注
    acb1 = _539_acb_bet(hist)
    acb1_hits = set(acb1) & ACTUAL
    results['ACB_1bet'] = {'bets': [acb1], 'union_hits': acb1_hits, 'max_match': len(acb1_hits)}
    print(f"\n  ★ ACB 1注 (ADOPTED): {acb1}")
    print(f"    命中: {sorted(acb1_hits)} ({len(acb1_hits)}/5) {'✅ M3+' if len(acb1_hits)>=3 else '❌'}")
    
    # 2. MidFreq+ACB 2注
    midfreq1 = _539_midfreq_bet(hist)
    acb2 = _539_acb_bet(hist, exclude=set(midfreq1))
    h1, h2 = set(midfreq1) & ACTUAL, set(acb2) & ACTUAL
    results['MidFreq_ACB_2bet'] = {'bets': [midfreq1, acb2], 'union_hits': h1|h2, 'max_match': max(len(h1),len(h2))}
    print(f"\n  MidFreq+ACB 2注 (PENDING):")
    print(f"    注1 MidFreq: {midfreq1} -> 命中 {sorted(h1)} ({len(h1)})")
    print(f"    注2 ACB:     {acb2} -> 命中 {sorted(h2)} ({len(h2)})")
    print(f"    聯集: {sorted(h1|h2)} ({len(h1|h2)}), max={max(len(h1),len(h2))} {'✅' if max(len(h1),len(h2))>=3 else '❌'}")
    
    # 3. F4Cold 3注 (current production)
    bets_3, strat_3 = predict_539(hist, {}, 3)
    bets_3n = [b['numbers'] for b in bets_3]
    all_h3 = set(); max_h3 = 0
    print(f"\n  F4Cold 3注 (PROVISIONAL):")
    for i, b in enumerate(bets_3n, 1):
        h = set(b) & ACTUAL; all_h3 |= h; max_h3 = max(max_h3, len(h))
        print(f"    注{i}: {b} -> 命中 {sorted(h)} ({len(h)})")
    print(f"    聯集: {sorted(all_h3)} ({len(all_h3)}), max={max_h3} {'✅' if max_h3>=3 else '❌'}")
    results['F4Cold_3bet'] = {'bets': bets_3n, 'union_hits': all_h3, 'max_match': max_h3}
    
    # 4. F4Cold 5注
    bets_5, strat_5 = predict_539(hist, {}, 5)
    bets_5n = [b['numbers'] for b in bets_5]
    all_h5 = set(); max_h5 = 0
    print(f"\n  F4Cold 5注 (PROVISIONAL):")
    for i, b in enumerate(bets_5n, 1):
        h = set(b) & ACTUAL; all_h5 |= h; max_h5 = max(max_h5, len(h))
        print(f"    注{i}: {b} -> 命中 {sorted(h)} ({len(h)})")
    print(f"    聯集: {sorted(all_h5)} ({len(all_h5)}), max={max_h5} {'✅' if max_h5>=3 else '❌'}")
    results['F4Cold_5bet'] = {'bets': bets_5n, 'union_hits': all_h5, 'max_match': max_h5}
    
    # 5. Markov 1注
    markov = _539_markov_bet(hist)
    mh = set(markov) & ACTUAL
    results['Markov_1bet'] = {'bets': [markov], 'union_hits': mh, 'max_match': len(mh)}
    print(f"\n  Markov 1注: {markov} -> 命中 {sorted(mh)} ({len(mh)}) {'✅' if len(mh)>=3 else '❌'}")
    
    # 6. LiftPair 1注
    lp = _539_lift_pair_bet(hist)
    lph = set(lp) & ACTUAL
    results['LiftPair_1bet'] = {'bets': [lp], 'union_hits': lph, 'max_match': len(lph)}
    print(f"\n  LiftPair 1注: {lp} -> 命中 {sorted(lph)} ({len(lph)}) {'✅' if len(lph)>=3 else '❌'}")
    
    # 7. P3a: Markov+MidFreq+ACB 3注
    b1 = _539_markov_bet(hist)
    b2 = _539_midfreq_bet(hist, exclude=set(b1))
    b3 = _539_acb_bet(hist, exclude=set(b1)|set(b2))
    p3a = [b1, b2, b3]
    all_p3a = set(); max_p3a = 0
    print(f"\n  P3a: Markov+MidFreq+ACB 3注 (CANDIDATE):")
    for i, b in enumerate(p3a, 1):
        h = set(b) & ACTUAL; all_p3a |= h; max_p3a = max(max_p3a, len(h))
        print(f"    注{i}: {b} -> 命中 {sorted(h)} ({len(h)})")
    print(f"    聯集: {sorted(all_p3a)} ({len(all_p3a)}), max={max_p3a} {'✅' if max_p3a>=3 else '❌'}")
    results['P3a_MMF_ACB_3bet'] = {'bets': p3a, 'union_hits': all_p3a, 'max_match': max_p3a}
    
    # 8. ACB+Fourier 2注 (理論最優)
    acb_b1 = _539_acb_bet(hist)
    fourier_sc = _539_fourier_scores(hist, window=500)
    fourier_ranked = sorted(fourier_sc, key=lambda x: -fourier_sc[x])
    fbet = sorted([n for n in fourier_ranked if n not in set(acb_b1)][:5])
    bh1 = set(acb_b1) & ACTUAL; bh2 = set(fbet) & ACTUAL
    results['ACB_Fourier_2bet'] = {'bets': [acb_b1, fbet], 'union_hits': bh1|bh2, 'max_match': max(len(bh1),len(bh2))}
    print(f"\n  ACB+Fourier 2注 (理論組合):")
    print(f"    注1 ACB:     {acb_b1} -> 命中 {sorted(bh1)} ({len(bh1)})")
    print(f"    注2 Fourier: {fbet} -> 命中 {sorted(bh2)} ({len(bh2)})")
    print(f"    聯集: {sorted(bh1|bh2)} ({len(bh1|bh2)}), max={max(len(bh1),len(bh2))} {'✅' if max(len(bh1),len(bh2))>=3 else '❌'}")
    
    # ==========================================
    # SECTION 2: 號碼信號深度分析
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 2: 開獎號碼信號深度分析")
    print("=" * 80)
    
    # Fourier rankings
    fourier_ranked_list = [n for n in fourier_ranked]
    
    # Frequency analysis at multiple windows
    freq_windows = {}
    for w in [30, 50, 100, 200, 500]:
        recent = hist[-w:]
        freq = Counter(n for d in recent for n in d['numbers'] if n <= MAX_NUM)
        expected = w * 5 / 39
        freq_windows[w] = {'freq': freq, 'expected': expected}
    
    # Gap analysis
    last_seen = {}
    for i, d in enumerate(hist):
        for n in d['numbers']:
            if n <= MAX_NUM:
                last_seen[n] = i
    gaps = {n: len(hist) - 1 - last_seen.get(n, -1) for n in range(1, 40)}
    
    # ACB scores
    acb_exp = len(hist[-100:]) * 5 / 39
    acb_counter = Counter()
    for n in range(1, 40): acb_counter[n] = 0
    for d in hist[-100:]:
        for n in d['numbers']: acb_counter[n] += 1
    acb_scores = {}
    for n in range(1, 40):
        fd = acb_exp - acb_counter[n]
        gs = gaps[n] / 50
        bb = 1.2 if (n <= 5 or n >= 35) else 1.0
        m3 = 1.1 if n % 3 == 0 else 1.0
        acb_scores[n] = (fd * 0.4 + gs * 0.6) * bb * m3
    acb_ranked = sorted(acb_scores, key=lambda x: -acb_scores[x])
    
    # MidFreq rankings
    f100 = freq_windows[100]['freq']
    exp100 = freq_windows[100]['expected']
    midfreq_dist = {n: abs(f100[n] - exp100) for n in range(1, 40)}
    midfreq_ranked = sorted(midfreq_dist, key=lambda x: midfreq_dist[x])
    
    # Markov scores
    markov_scores = Counter()
    mw = hist[-30:]
    transitions = {}
    for i in range(len(mw) - 1):
        for pn in mw[i]['numbers']:
            if pn > MAX_NUM: continue
            if pn not in transitions: transitions[pn] = Counter()
            for nn in mw[i + 1]['numbers']:
                if nn <= MAX_NUM: transitions[pn][nn] += 1
    for pn in prev_nums:
        if pn > MAX_NUM: continue
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for nn, cnt in trans.items():
                markov_scores[nn] += cnt / total
    markov_ranked = sorted(markov_scores, key=lambda x: -markov_scores[x])
    
    print(f"\n  上期 ({hist[-1]['draw']}): {sorted(prev_nums)}")
    print(f"  前2期 ({hist[-2]['draw']}): {sorted(prev2_nums)}")
    
    print(f"\n  {'#':>3} | {'F_rank':>6} | {'ACB_rank':>8} | {'MF_rank':>7} | {'MK_rank':>7} | {'f30':>4} | {'f50':>4} | {'f100':>4} | {'f200':>4} | {'gap':>4} | {'deficit':>7} | {'Zone':>4} | 特徵")
    print("  " + "-" * 130)
    
    for n in ACTUAL_LIST:
        f_rank = fourier_ranked_list.index(n) + 1 if n in fourier_ranked_list else 99
        a_rank = acb_ranked.index(n) + 1
        m_rank = midfreq_ranked.index(n) + 1
        mk_rank = markov_ranked.index(n) + 1 if n in markov_ranked else 99
        zone = 'Z1' if n <= 13 else ('Z2' if n <= 26 else 'Z3')
        deficit = acb_exp - acb_counter[n]
        
        features = []
        if f_rank <= 5: features.append('★Fourier-Top5')
        elif f_rank <= 10: features.append('Fourier-Top10')
        if a_rank <= 5: features.append('★ACB-Top5')
        elif a_rank <= 10: features.append('ACB-Top10')
        if m_rank <= 10: features.append('MF-Top10')
        if mk_rank <= 5: features.append('★Markov-Top5')
        elif mk_rank <= 10: features.append('Markov-Top10')
        if n in prev_nums: features.append('上期保留')
        if n in prev2_nums: features.append('前2期')
        if gaps[n] >= 15: features.append(f'高Gap({gaps[n]})')
        if f100[n] <= exp100 * 0.6: features.append('COLD')
        if f100[n] >= exp100 * 1.3: features.append('HOT')
        if not features: features.append('無強信號')
        
        f30 = freq_windows[30]['freq'][n]
        f50 = freq_windows[50]['freq'][n]
        f100v = freq_windows[100]['freq'][n]
        f200 = freq_windows[200]['freq'][n]
        
        print(f"  {n:3d} | {f_rank:6d} | {a_rank:8d} | {m_rank:7d} | {mk_rank:7d} | {f30:4d} | {f50:4d} | {f100v:4d} | {f200:4d} | {gaps[n]:4d} | {deficit:7.2f} | {zone:>4} | {', '.join(features)}")
    
    # ==========================================
    # SECTION 3: 結構特徵
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 3: 號碼結構特徵")
    print("=" * 80)
    
    total_sum = sum(ACTUAL_LIST)
    all_sums = [sum(d['numbers'][:5]) for d in hist[-500:]]
    sum_mean, sum_std = np.mean(all_sums), np.std(all_sums)
    sum_z = (total_sum - sum_mean) / sum_std
    
    z1 = [n for n in ACTUAL_LIST if n <= 13]
    z2 = [n for n in ACTUAL_LIST if 14 <= n <= 26]
    z3 = [n for n in ACTUAL_LIST if n >= 27]
    odd = sum(1 for n in ACTUAL_LIST if n % 2 == 1)
    consec = [(ACTUAL_LIST[i], ACTUAL_LIST[i+1]) for i in range(4) if ACTUAL_LIST[i+1]-ACTUAL_LIST[i]==1]
    diffs = [ACTUAL_LIST[i+1]-ACTUAL_LIST[i] for i in range(4)]
    retained = ACTUAL & prev_nums
    retained2 = ACTUAL & prev2_nums
    
    # 歷史保留率
    retain_hist = [len(set(hist[-i]['numbers'][:5]) & set(hist[-i-1]['numbers'][:5])) for i in range(1, 501)]
    retain_mean = np.mean(retain_hist)
    retain_2plus = sum(1 for r in retain_hist if r >= 2) / len(retain_hist) * 100
    
    # 連號歷史率
    consec_hist = sum(1 for d in hist[-500:] if any(sorted(d['numbers'][:5])[i+1]-sorted(d['numbers'][:5])[i]==1 for i in range(4))) / 500 * 100
    
    print(f"\n  Sum={total_sum} (均值={sum_mean:.1f}, σ={sum_std:.1f}, z={sum_z:.2f})")
    print(f"  奇偶={odd}奇{5-odd}偶")
    print(f"  Zone: Z1:{len(z1)} Z2:{len(z2)} Z3:{len(z3)} = {z1},{z2},{z3}")
    print(f"  連號: {consec if consec else '無'} (歷史500期連號率={consec_hist:.1f}%)")
    print(f"  間距: {diffs}")
    print(f"  保留: {sorted(retained)} ({len(retained)}個) (歷史均值={retain_mean:.2f}, ≥2率={retain_2plus:.1f}%)")
    print(f"  前2期保留: {sorted(retained2)} ({len(retained2)}個)")
    
    # ==========================================
    # SECTION 4: 排名矩陣 + 最佳組合
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 4: 各方法 Top-N 覆蓋率")
    print("=" * 80)
    
    for topn in [5, 10, 15, 20, 25]:
        f_cov = len(set(fourier_ranked_list[:topn]) & ACTUAL)
        a_cov = len(set(acb_ranked[:topn]) & ACTUAL)
        m_cov = len(set(midfreq_ranked[:topn]) & ACTUAL)
        mk_cov = len(set(markov_ranked[:topn]) & ACTUAL) if len(markov_ranked) >= topn else len(set(markov_ranked[:topn]) & ACTUAL)
        print(f"  Top-{topn:2d}: Fourier={f_cov}/5  ACB={a_cov}/5  MidFreq={m_cov}/5  Markov={mk_cov}/5")
    
    # ==========================================
    # SECTION 5: 歷史趨勢
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 5: 近10期趨勢")
    print("=" * 80)
    
    for i in range(10, 0, -1):
        d = hist[-i]
        nums = sorted(d['numbers'][:5])
        s = sum(nums)
        o = sum(1 for n in nums if n % 2 == 1)
        z1c = sum(1 for n in nums if n <= 13)
        z2c = sum(1 for n in nums if 14 <= n <= 26)
        z3c = sum(1 for n in nums if n >= 27)
        consec_flag = '★' if any(nums[j+1]-nums[j]==1 for j in range(4)) else ' '
        # 保留數
        if i < 10:
            prev = set(hist[-i-1]['numbers'][:5])
            ret = len(set(nums) & prev)
        else:
            ret = '-'
        print(f"  {d['draw']}: {nums} | sum={s:3d} | {o}奇{5-o}偶 | Z({z1c},{z2c},{z3c}) | 保留={ret} {consec_flag}")
    
    print(f"  ---------- 055 開獎 ----------")
    print(f"  115000055: {ACTUAL_LIST} | sum={total_sum:3d} | {odd}奇{5-odd}偶 | Z({len(z1)},{len(z2)},{len(z3)}) | 保留={len(retained)} {'★' if consec else ' '}")
    
    # ==========================================
    # SECTION 6: 漏號根因 + 可挽救性
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 6: 各號碼漏號根因 + 可挽救性")
    print("=" * 80)
    
    for n in ACTUAL_LIST:
        f_rank = fourier_ranked_list.index(n) + 1 if n in fourier_ranked_list else 99
        a_rank = acb_ranked.index(n) + 1
        m_rank = midfreq_ranked.index(n) + 1
        mk_rank = markov_ranked.index(n) + 1 if n in markov_ranked else 99
        
        top5_count = sum(1 for r in [f_rank, a_rank, m_rank, mk_rank] if r <= 5)
        top10_count = sum(1 for r in [f_rank, a_rank, m_rank, mk_rank] if r <= 10)
        best_method = min([('Fourier', f_rank), ('ACB', a_rank), ('MidFreq', m_rank), ('Markov', mk_rank)], key=lambda x: x[1])
        
        print(f"\n  #{n:02d}: 最佳方法={best_method[0]}(rank {best_method[1]}), Top5有{top5_count}個方法, Top10有{top10_count}個")
        
        # 可挽救性分析
        if a_rank <= 5:
            print(f"    ✅ ACB已捕捉 (rank {a_rank})")
            if acb1 and n in acb1:
                print(f"    ✅ 已被ACB 1注選中")
            else:
                print(f"    ⚠️ 被ACB排名更高者擠出 (zone平衡修正?)")
        elif f_rank <= 5:
            print(f"    ✅ Fourier已捕捉 (rank {f_rank})")
        elif mk_rank <= 5:
            print(f"    ✅ Markov已捕捉 (rank {mk_rank})")
        elif top10_count >= 1:
            print(f"    ⚠️ 位於某方法Top10但未進Top5，2注架構可能挽救")
        else:
            print(f"    ❌ 所有方法排名>10, 當前架構難以捕捉")
            # 分析哪些特徵可能有用
            if n in prev_nums:
                print(f"    💡 上期保留號碼 — 保留機制可挽救")
            if gaps[n] >= 10:
                print(f"    💡 高 gap={gaps[n]} — 冷號機制可挽救")
            if f100[n] >= exp100:
                print(f"    💡 freq100={f100[n]} ≥ 期望 — 但非極端值，難以形成訊號")
    
    # ==========================================
    # SECTION 7: 最終總結表
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 7: 最終總結")
    print("=" * 80)
    
    print(f"\n  {'方法':<35} | {'注數':>4} | {'聯集':>4} | {'最大':>4} | {'M3+':>5} | {'覆蓋號碼數':>10}")
    print("  " + "-" * 75)
    
    for name in sorted(results.keys(), key=lambda k: (-results[k]['max_match'], -len(results[k]['union_hits']))):
        r = results[name]
        union_h = len(r['union_hits'])
        max_h = r['max_match']
        m3 = '✅' if max_h >= 3 else '❌'
        total_nums = len(set(n for b in r['bets'] for n in b))
        print(f"  {name:<35} | {len(r['bets']):>4} | {union_h:>4} | {max_h:>4} | {m3:>5} | {total_nums:>10}")
    
    # ==========================================
    # SECTION 8: 2注/3注可行性深度分析
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 8: 2注/3注最優組合可行性")
    print("=" * 80)
    
    methods = {
        'Fourier': lambda excl: sorted([n for n in fourier_ranked_list if n not in excl][:5]),
        'ACB': lambda excl: _539_acb_bet(hist, exclude=excl),
        'MidFreq': lambda excl: _539_midfreq_bet(hist, exclude=excl),
        'Markov': lambda excl: _539_markov_bet(hist, exclude=excl),
        'LiftPair': lambda excl: _539_lift_pair_bet(hist, exclude=excl),
    }
    
    print(f"\n  === 2注組合排名 ===")
    two_bet = []
    for m1 in methods:
        for m2 in methods:
            if m1 >= m2: continue
            b1 = methods[m1](set())
            b2 = methods[m2](set(b1))
            h1 = len(set(b1) & ACTUAL); h2 = len(set(b2) & ACTUAL)
            union = len((set(b1)|set(b2)) & ACTUAL)
            two_bet.append((f"{m1}+{m2}", h1, h2, union, max(h1,h2)))
    
    two_bet.sort(key=lambda x: (-x[4], -x[3]))
    print(f"\n  {'組合':<25} | {'注1':>3} | {'注2':>3} | {'聯集':>4} | {'max':>4} | M3+")
    print("  " + "-" * 60)
    for name, h1, h2, union, mx in two_bet:
        m3 = '✅' if mx >= 3 else '❌'
        print(f"  {name:<25} | {h1:>3} | {h2:>3} | {union:>4} | {mx:>4} | {m3}")
    
    print(f"\n  === 3注組合排名 ===")
    three_bet = []
    mnames = list(methods.keys())
    for combo in combinations(mnames, 3):
        b1 = methods[combo[0]](set())
        b2 = methods[combo[1]](set(b1))
        b3 = methods[combo[2]](set(b1)|set(b2))
        hits = [len(set(b) & ACTUAL) for b in [b1, b2, b3]]
        union = len((set(b1)|set(b2)|set(b3)) & ACTUAL)
        three_bet.append(('+'.join(combo), hits, union, max(hits)))
    
    three_bet.sort(key=lambda x: (-x[3], -x[2]))
    print(f"\n  {'組合':<35} | {'注1':>3} | {'注2':>3} | {'注3':>3} | {'聯集':>4} | {'max':>4} | M3+")
    print("  " + "-" * 75)
    for name, hits, union, mx in three_bet:
        m3 = '✅' if mx >= 3 else '❌'
        print(f"  {name:<35} | {hits[0]:>3} | {hits[1]:>3} | {hits[2]:>3} | {union:>4} | {mx:>4} | {m3}")
    
    # ==========================================
    # SECTION 9: 未探索特徵空間
    # ==========================================
    print("\n" + "=" * 80)
    print("  SECTION 9: 055期潛在可利用特徵")
    print("=" * 80)
    
    # 1. 保留號碼信號
    print(f"\n  1. 保留號碼信號:")
    print(f"     055期從054保留了 {sorted(retained)} ({len(retained)}個)")
    print(f"     歷史500期: 保留≥2 的機率 = {retain_2plus:.1f}%")
    print(f"     保留平均數 = {retain_mean:.2f}")
    if len(retained) >= 2:
        print(f"     ✅ 055期保留2個，上期號碼信號有價值")
    
    # 2. 連號信號
    print(f"\n  2. 連號信號:")
    print(f"     055期連號: {consec}")
    print(f"     歷史500期連號出現率: {consec_hist:.1f}%")
    
    # 3. Sum偏低信號
    low_sum_rate = sum(1 for s in all_sums if s <= total_sum) / len(all_sums) * 100
    print(f"\n  3. Sum偏低信號:")
    print(f"     Sum={total_sum}, 低於此值的歷史比例={low_sum_rate:.1f}%")
    
    # 4. 號碼集中度 (max-min)
    spread = ACTUAL_LIST[-1] - ACTUAL_LIST[0]
    hist_spreads = [max(d['numbers'][:5])-min(d['numbers'][:5]) for d in hist[-500:]]
    spread_mean = np.mean(hist_spreads)
    print(f"\n  4. 號碼跨度:")
    print(f"     055期跨度={spread} (均值={spread_mean:.1f})")
    
    # 5. mod3集中度
    mod3 = Counter(n % 3 for n in ACTUAL_LIST)
    print(f"\n  5. mod3分佈: {dict(mod3)}")
    if max(mod3.values()) >= 4:
        print(f"     ⚠️ mod3高度集中")
    
    # 6. 上期鄰域分析 (±1, ±2)
    neighbors_1 = set()
    neighbors_2 = set()
    for pn in prev_nums:
        for d in [-1, 1]:
            nn = pn + d
            if 1 <= nn <= 39: neighbors_1.add(nn)
        for d in [-2, -1, 1, 2]:
            nn = pn + d
            if 1 <= nn <= 39: neighbors_2.add(nn)
    
    n1_hits = ACTUAL & neighbors_1
    n2_hits = ACTUAL & neighbors_2
    print(f"\n  6. 上期鄰域:")
    print(f"     ±1 鄰域 ({len(neighbors_1)}個): 命中 {sorted(n1_hits)} ({len(n1_hits)})")
    print(f"     ±2 鄰域 ({len(neighbors_2)}個): 命中 {sorted(n2_hits)} ({len(n2_hits)})")
    
    print("\n" + "=" * 80)
    print("  分析完成")
    print("=" * 80)


if __name__ == '__main__':
    main()
