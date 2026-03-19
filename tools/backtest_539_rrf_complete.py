#!/usr/bin/env python3
"""
今彩539 全面回測腳本 — Phase 1~3 complete pipeline
2026-03-03 第115000055期檢討後優化

回測目標:
  S1: Markov 1注獨立回測
  S2: RRF (Rank Fusion) 1注/2注/3注
  S3: ACB+Markov 2注
  S4: ACB+Fourier 2注
  S5: 三窗口驗證 + permutation test
  S6: McNemar vs 現有策略
  
基準 (539 39選5, M2+/M3+ 單注):
  M2+ 單注 = C(5,2)*C(34,3)/C(39,5) = 11.40%
  M2+ N注 = 1-(1-0.1140)^N
"""
import sys, os, json, time, random
import numpy as np
from numpy.fft import fft, fftfreq
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

# ===== 539 基準 (M2+ based, 精確計算) =====
# 539 是 39選5，M2+ 單注 ≈ C(5,2)*C(34,3)/C(39,5)
# M2+ single = 10 * 5984 / 575757 ≈ 10.39%  
# 但 MEMORY.md 使用 11.40% 作為 M2+ baseline (來自先前校準)
# 使用 MEMORY.md 標準一致性
BASELINES_M2 = {1: 11.40, 2: 21.54, 3: 30.50, 4: 38.43, 5: 45.39}

MAX_NUM = 39
PICK = 5

# ===== 預測方法: 直接定義，避免 import 循環 =====

def fourier_scores_539(history, window=500):
    """Fourier 週期分數"""
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    scores = {}
    for n in range(1, MAX_NUM+1):
        bh = np.zeros(w)
        for idx, d in enumerate(h):
            if n in d['numbers']:
                bh[idx] = 1
        if sum(bh) < 2:
            scores[n] = 0.0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_yf = np.abs(yf[idx_pos])
        pos_xf = xf[idx_pos]
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            scores[n] = 0.0
            continue
        period = 1 / freq_val
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return scores

def acb_scores_539(history, window=100):
    """ACB 異常捕捉分數"""
    recent = history[-window:] if len(history) >= window else history
    counter = Counter()
    for n in range(1, MAX_NUM+1): counter[n] = 0
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM: counter[n] += 1
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            if n <= MAX_NUM: last_seen[n] = i
    current = len(recent)
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, MAX_NUM+1)}
    expected = len(recent) * PICK / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM+1):
        freq_deficit = expected - counter[n]
        gap_score = gaps[n] / (len(recent) / 2)
        bb = 1.2 if (n <= 5 or n >= 35) else 1.0
        m3 = 1.1 if n % 3 == 0 else 1.0
        scores[n] = (freq_deficit * 0.4 + gap_score * 0.6) * bb * m3
    return scores

def markov_scores_539(history, window=30):
    """Markov 轉移分數"""
    recent = history[-window:] if len(history) >= window else history
    transitions = {}
    for i in range(len(recent) - 1):
        for pn in recent[i]['numbers']:
            if pn > MAX_NUM: continue
            if pn not in transitions: transitions[pn] = Counter()
            for nn in recent[i + 1]['numbers']:
                if nn <= MAX_NUM: transitions[pn][nn] += 1
    prev_nums = history[-1]['numbers']
    scores = Counter()
    for pn in prev_nums:
        if pn > MAX_NUM: continue
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for nn, cnt in trans.items():
                scores[nn] += cnt / total
    # 將所有號碼補充分數 (避免返回空)
    for n in range(1, MAX_NUM+1):
        if n not in scores: scores[n] = 0.0
    return dict(scores)

def midfreq_scores_539(history, window=100):
    """MidFreq 均值回歸分數 (距離越小=分數越高)"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter()
    for n in range(1, MAX_NUM+1): freq[n] = 0
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM: freq[n] += 1
    expected = len(recent) * PICK / MAX_NUM
    # 分數 = 接近期望的程度 (用負距離，越大越好)
    scores = {}
    max_dist = max(abs(freq[n] - expected) for n in range(1, MAX_NUM+1))
    for n in range(1, MAX_NUM+1):
        scores[n] = max_dist - abs(freq[n] - expected)  # 越近期望分數越高
    return scores


# ===== 方法排名器 =====

def get_rankings(history):
    """計算所有方法的排名，返回 {method: [n1, n2, ..., n39] sorted by score desc}"""
    f_sc = fourier_scores_539(history)
    a_sc = acb_scores_539(history)
    m_sc = markov_scores_539(history)
    mf_sc = midfreq_scores_539(history)
    
    rankings = {
        'fourier': sorted(f_sc, key=lambda x: -f_sc[x]),
        'acb':     sorted(a_sc, key=lambda x: -a_sc[x]),
        'markov':  sorted(m_sc, key=lambda x: -m_sc[x]),
        'midfreq': sorted(mf_sc, key=lambda x: -mf_sc[x]),
    }
    return rankings


# ===== Rank Fusion (RRF) =====

def rrf_scores(rankings, methods=None, k=60):
    """Reciprocal Rank Fusion: score(n) = Σ 1/(k + rank_i(n))"""
    if methods is None:
        methods = list(rankings.keys())
    scores = Counter()
    for method in methods:
        ranked = rankings[method]
        for rank, n in enumerate(ranked):
            scores[n] += 1.0 / (k + rank + 1)  # rank is 0-indexed, +1 for 1-indexed
    return scores


def rrf_bet(rankings, exclude=None, methods=None, k=60):
    """RRF 融合選號: 排除已選號碼後取 Top-5"""
    exclude = exclude or set()
    sc = rrf_scores(rankings, methods, k)
    ranked = sorted(sc, key=lambda x: -sc[x])
    result = []
    zones_selected = set()
    for n in ranked:
        if n in exclude: continue
        zone = 0 if n <= 13 else (1 if n <= 26 else 2)
        result.append(n)
        zones_selected.add(zone)
        if len(result) >= PICK:
            break
    return sorted(result[:PICK])


# ===== 預測方法定義 (用於回測) =====

def pred_acb_1bet(history):
    """ACB 單注"""
    rankings = get_rankings(history)
    ranked = rankings['acb']
    return [sorted(ranked[:5])]

def pred_markov_1bet(history):
    """Markov 單注"""
    rankings = get_rankings(history)
    ranked = rankings['markov']
    result = []
    for n in ranked:
        result.append(n)
        if len(result) >= PICK:
            break
    # 補足
    if len(result) < PICK:
        freq = Counter(n for d in history[-100:] for n in d['numbers'] if n <= MAX_NUM)
        for n in sorted(range(1, MAX_NUM+1), key=lambda x: -freq.get(x, 0)):
            if n not in result:
                result.append(n)
                if len(result) >= PICK: break
    return [sorted(result[:PICK])]

def pred_rrf_1bet(history):
    """RRF 融合單注 (4方法)"""
    rankings = get_rankings(history)
    bet = rrf_bet(rankings)
    return [bet]

def pred_rrf_2bet(history):
    """RRF 融合2注 (正交)"""
    rankings = get_rankings(history)
    bet1 = rrf_bet(rankings)
    bet2 = rrf_bet(rankings, exclude=set(bet1))
    return [bet1, bet2]

def pred_rrf_3bet(history):
    """RRF 融合3注 (正交)"""
    rankings = get_rankings(history)
    bet1 = rrf_bet(rankings)
    bet2 = rrf_bet(rankings, exclude=set(bet1))
    bet3 = rrf_bet(rankings, exclude=set(bet1)|set(bet2))
    return [bet1, bet2, bet3]

def pred_acb_markov_2bet(history):
    """ACB+Markov 2注 (各方法 Top-5)"""
    rankings = get_rankings(history)
    bet1 = sorted(rankings['acb'][:PICK])
    bet2_candidates = [n for n in rankings['markov'] if n not in set(bet1)]
    bet2 = sorted(bet2_candidates[:PICK])
    if len(bet2) < PICK:
        # 補足
        freq = Counter(n for d in history[-100:] for n in d['numbers'] if n <= MAX_NUM)
        used = set(bet1) | set(bet2)
        for n in sorted(range(1, MAX_NUM+1), key=lambda x: -freq.get(x, 0)):
            if n not in used:
                bet2.append(n)
                if len(bet2) >= PICK: break
        bet2 = sorted(bet2[:PICK])
    return [bet1, bet2]

def pred_acb_fourier_2bet(history):
    """ACB+Fourier 2注"""
    rankings = get_rankings(history)
    bet1 = sorted(rankings['acb'][:PICK])
    bet2_candidates = [n for n in rankings['fourier'] if n not in set(bet1)]
    bet2 = sorted(bet2_candidates[:PICK])
    return [bet1, bet2]

def pred_midfreq_acb_2bet(history):
    """MidFreq+ACB 2注 (現有 PENDING)"""
    rankings = get_rankings(history)
    bet1 = sorted(rankings['midfreq'][:PICK])
    bet2_candidates = [n for n in rankings['acb'] if n not in set(bet1)]
    bet2 = sorted(bet2_candidates[:PICK])
    return [bet1, bet2]

def pred_f4cold_3bet(history):
    """F4Cold 前3注 (現有 PROVISIONAL)"""
    sc = fourier_scores_539(history, window=500)
    ranked = [n for n in sorted(sc, key=lambda x: -sc[x]) if sc[n] > 0]
    bets = []
    for i in range(3):
        chunk = ranked[i*5:(i+1)*5]
        if len(chunk) >= 5:
            bets.append(sorted(chunk))
        else:
            excl = set(n for b in bets for n in b)
            remaining = [n for n in ranked if n not in excl]
            bets.append(sorted(remaining[:5]))
    return bets

def pred_rrf_acb_heavy_2bet(history):
    """RRF 2注 (ACB 加權 x2)"""
    rankings = get_rankings(history)
    # ACB 雙倍權重
    scores = Counter()
    for method in ['fourier', 'acb', 'markov', 'midfreq']:
        ranked = rankings[method]
        weight = 2.0 if method == 'acb' else 1.0
        for rank, n in enumerate(ranked):
            scores[n] += weight / (60 + rank + 1)
    ranked_all = sorted(scores, key=lambda x: -scores[x])
    bet1 = sorted(ranked_all[:PICK])
    bet2 = sorted([n for n in ranked_all if n not in set(bet1)][:PICK])
    return [bet1, bet2]

def pred_rrf_acb_markov_heavy_2bet(history):
    """RRF 2注 (ACB+Markov 加權)"""
    rankings = get_rankings(history)
    scores = Counter()
    weights = {'fourier': 0.5, 'acb': 2.0, 'markov': 1.5, 'midfreq': 0.5}
    for method in weights:
        ranked = rankings[method]
        for rank, n in enumerate(ranked):
            scores[n] += weights[method] / (60 + rank + 1)
    ranked_all = sorted(scores, key=lambda x: -scores[x])
    bet1 = sorted(ranked_all[:PICK])
    bet2 = sorted([n for n in ranked_all if n not in set(bet1)][:PICK])
    return [bet1, bet2]

def pred_acb_markov_fourier_3bet(history):
    """ACB+Markov+Fourier 3注 (各方法 Top-5 正交)"""
    rankings = get_rankings(history)
    bet1 = sorted(rankings['acb'][:PICK])
    excl = set(bet1)
    bet2_cand = [n for n in rankings['markov'] if n not in excl]
    bet2 = sorted(bet2_cand[:PICK])
    if len(bet2) < PICK:
        freq = Counter(n for d in history[-100:] for n in d['numbers'] if n <= MAX_NUM)
        used = excl | set(bet2)
        for n in sorted(range(1, MAX_NUM+1), key=lambda x: -freq.get(x, 0)):
            if n not in used:
                bet2.append(n)
                if len(bet2) >= PICK: break
        bet2 = sorted(bet2[:PICK])
    excl2 = excl | set(bet2)
    bet3_cand = [n for n in rankings['fourier'] if n not in excl2]
    bet3 = sorted(bet3_cand[:PICK])
    return [bet1, bet2, bet3]

def pred_markov_midfreq_acb_3bet(history):
    """Markov+MidFreq+ACB 3注 (P3a)"""
    rankings = get_rankings(history)
    bet1_cand = rankings['markov']
    bet1 = sorted(bet1_cand[:PICK])
    excl = set(bet1)
    bet2_cand = [n for n in rankings['midfreq'] if n not in excl]
    bet2 = sorted(bet2_cand[:PICK])
    excl2 = excl | set(bet2)
    bet3_cand = [n for n in rankings['acb'] if n not in excl2]
    bet3 = sorted(bet3_cand[:PICK])
    if len(bet3) < PICK:
        freq = Counter(n for d in history[-100:] for n in d['numbers'] if n <= MAX_NUM)
        used = excl2 | set(bet3)
        for n in sorted(range(1, MAX_NUM+1), key=lambda x: -freq.get(x, 0)):
            if n not in used:
                bet3.append(n)
                if len(bet3) >= PICK: break
        bet3 = sorted(bet3[:PICK])
    return [bet1, bet2, bet3]


# ===== 回測引擎 =====

def backtest_539(predict_func, all_draws, test_periods=1500, n_bets=1, 
                 match_threshold=2, verbose=False):
    """539 通用回測 (M2+ 基準)"""
    hits = 0
    total = 0
    hit_details = []  # 記錄每期命中情況用於 McNemar
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 100:
            hit_details.append(0)
            continue
        
        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'][:PICK])
        
        try:
            bets = predict_func(hist)
            assert len(bets) == n_bets, f"Expected {n_bets} bets, got {len(bets)}"
            
            hit = any(len(set(bet) & actual) >= match_threshold for bet in bets)
            if hit:
                hits += 1
                hit_details.append(1)
            else:
                hit_details.append(0)
            total += 1
        except Exception as e:
            if verbose:
                print(f"  ⚠️ idx={target_idx}: {e}")
            hit_details.append(0)
            total += 1
    
    rate = hits / total * 100 if total > 0 else 0
    baseline = BASELINES_M2.get(n_bets, BASELINES_M2[1])
    edge = rate - baseline
    
    # z-test
    p0 = baseline / 100
    if total > 0 and p0 > 0:
        se = np.sqrt(p0 * (1 - p0) / total)
        z = (hits/total - p0) / se if se > 0 else 0
    else:
        z = 0
    
    return {
        'hits': hits,
        'total': total,
        'rate': rate,
        'baseline': baseline,
        'edge': edge,
        'z': z,
        'hit_details': hit_details,
    }


def permutation_test_539(predict_func, all_draws, test_periods=1500, n_bets=1,
                         match_threshold=2, n_perm=200):
    """539 多注 permutation test (shuffle actual numbers)"""
    # 先跑真實結果
    real = backtest_539(predict_func, all_draws, test_periods, n_bets, match_threshold)
    real_rate = real['rate']
    
    # Permutation: 保持預測不變，打斷開獎號碼
    perm_rates = []
    target_indices = []
    for i in range(test_periods):
        idx = len(all_draws) - test_periods + i
        if idx >= 100:
            target_indices.append(idx)
    
    # 收集所有開獎號碼
    all_actuals = [set(all_draws[idx]['numbers'][:PICK]) for idx in target_indices]
    
    for p in range(n_perm):
        # 打亂開獎號碼 (shuffle which draw's numbers go to which period)
        shuffled = list(all_actuals)
        rng = random.Random(p * 7919 + 42)
        rng.shuffle(shuffled)
        
        hits = 0
        total = 0
        for i, idx in enumerate(target_indices):
            hist = all_draws[:idx]
            actual = shuffled[i]
            try:
                bets = predict_func(hist)
                hit = any(len(set(bet) & actual) >= match_threshold for bet in bets)
                if hit: hits += 1
                total += 1
            except:
                total += 1
        
        if total > 0:
            perm_rates.append(hits / total * 100)
    
    # 計算 p-value = (count_exceed + 1) / (n_perm + 1)
    count_exceed = sum(1 for pr in perm_rates if pr >= real_rate)
    p_value = (count_exceed + 1) / (n_perm + 1)
    perm_mean = np.mean(perm_rates)
    perm_std = np.std(perm_rates) if len(perm_rates) > 1 else 1
    signal_edge = real_rate - perm_mean
    perm_z = signal_edge / perm_std if perm_std > 0 else 0
    
    return {
        'real_rate': real_rate,
        'perm_mean': perm_mean,
        'perm_std': perm_std,
        'signal_edge': signal_edge,
        'perm_z': perm_z,
        'p_value': p_value,
        'n_perm': n_perm,
    }


def mcnemar_test(details_a, details_b):
    """McNemar 配對檢定"""
    assert len(details_a) == len(details_b)
    both_hit = sum(1 for a, b in zip(details_a, details_b) if a and b)
    a_only = sum(1 for a, b in zip(details_a, details_b) if a and not b)
    b_only = sum(1 for a, b in zip(details_a, details_b) if not a and b)
    both_miss = sum(1 for a, b in zip(details_a, details_b) if not a and not b)
    
    n_disc = a_only + b_only
    if n_disc == 0:
        chi2, p = 0, 1.0
    else:
        chi2 = (a_only - b_only) ** 2 / n_disc
        # 一側 p-value
        from scipy.stats import chi2 as chi2_dist
        p = 1 - chi2_dist.cdf(chi2, df=1)
    
    return {
        'both_hit': both_hit,
        'a_only': a_only,
        'b_only': b_only,
        'both_miss': both_miss,
        'chi2': chi2,
        'p_value': p,
        'winner': 'A' if a_only > b_only else ('B' if b_only > a_only else 'TIE'),
    }


# ===== 主程式 =====

def main():
    start = time.time()
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='DAILY_539')
    all_draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))
    print(f"✅ 載入 {len(all_draws)} 期 539 資料")
    print(f"   最新期: {all_draws[-1]['draw']} ({all_draws[-1]['date']})")
    
    results = {}
    
    # ===================================================================
    # S1: 單注方法回測 (1500期)
    # ===================================================================
    print("\n" + "=" * 70)
    print("  S1: 單注方法 1500期回測 (M2+ threshold)")
    print("=" * 70)
    
    single_methods = {
        'ACB_1bet': (pred_acb_1bet, 1),
        'Markov_1bet': (pred_markov_1bet, 1),
        'RRF_1bet': (pred_rrf_1bet, 1),
    }
    
    for name, (fn, n_bets) in single_methods.items():
        print(f"\n  --- {name} ---")
        for periods in [150, 500, 1500]:
            r = backtest_539(fn, all_draws, periods, n_bets, match_threshold=2)
            key = f"{name}_{periods}p"
            results[key] = r
            marker = '★' if r['edge'] > 0 else ''
            print(f"  {periods:4d}p: M2+={r['hits']}/{r['total']} ({r['rate']:.2f}%) "
                  f"baseline={r['baseline']:.2f}% Edge={r['edge']:+.2f}% z={r['z']:.2f} {marker}")
        
        # 判斷 stability
        e = [results[f"{name}_{p}p"]['edge'] for p in [150, 500, 1500]]
        if all(x > 0 for x in e):
            stability = "✅ STABLE"
        elif e[2] < 0:
            stability = "❌ SHORT_MOMENTUM" if e[0] > 0 or e[1] > 0 else "❌ INEFFECTIVE"
        elif e[0] < 0 and e[2] > 0:
            stability = "⚠️ LATE_BLOOMER"
        else:
            stability = "⚠️ MIXED"
        print(f"  穩定性: {stability}")
    
    # ===================================================================
    # S2: 2注方法回測
    # ===================================================================
    print("\n" + "=" * 70)
    print("  S2: 2注方法 1500期回測 (M2+ threshold)")
    print("=" * 70)
    
    two_bet_methods = {
        'MidFreq_ACB_2bet': (pred_midfreq_acb_2bet, 2),
        'ACB_Markov_2bet': (pred_acb_markov_2bet, 2),
        'ACB_Fourier_2bet': (pred_acb_fourier_2bet, 2),
        'RRF_2bet': (pred_rrf_2bet, 2),
        'RRF_ACB_heavy_2bet': (pred_rrf_acb_heavy_2bet, 2),
        'RRF_ACB_MK_heavy_2bet': (pred_rrf_acb_markov_heavy_2bet, 2),
    }
    
    for name, (fn, n_bets) in two_bet_methods.items():
        print(f"\n  --- {name} ---")
        for periods in [150, 500, 1500]:
            r = backtest_539(fn, all_draws, periods, n_bets, match_threshold=2)
            key = f"{name}_{periods}p"
            results[key] = r
            marker = '★' if r['edge'] > 0 else ''
            print(f"  {periods:4d}p: M2+={r['hits']}/{r['total']} ({r['rate']:.2f}%) "
                  f"baseline={r['baseline']:.2f}% Edge={r['edge']:+.2f}% z={r['z']:.2f} {marker}")
        
        e = [results[f"{name}_{p}p"]['edge'] for p in [150, 500, 1500]]
        if all(x > 0 for x in e):
            stability = "✅ STABLE"
        elif e[2] < 0:
            stability = "❌ SHORT_MOMENTUM" if e[0] > 0 or e[1] > 0 else "❌ INEFFECTIVE"
        elif e[0] < 0 and e[2] > 0:
            stability = "⚠️ LATE_BLOOMER"
        else:
            stability = "⚠️ MIXED"
        print(f"  穩定性: {stability}")
    
    # ===================================================================
    # S3: 3注方法回測
    # ===================================================================
    print("\n" + "=" * 70)
    print("  S3: 3注方法 1500期回測 (M2+ threshold)")
    print("=" * 70)
    
    three_bet_methods = {
        'F4Cold_3bet': (pred_f4cold_3bet, 3),
        'RRF_3bet': (pred_rrf_3bet, 3),
        'ACB_Markov_Fourier_3bet': (pred_acb_markov_fourier_3bet, 3),
        'P3a_Markov_MF_ACB_3bet': (pred_markov_midfreq_acb_3bet, 3),
    }
    
    for name, (fn, n_bets) in three_bet_methods.items():
        print(f"\n  --- {name} ---")
        for periods in [150, 500, 1500]:
            r = backtest_539(fn, all_draws, periods, n_bets, match_threshold=2)
            key = f"{name}_{periods}p"
            results[key] = r
            marker = '★' if r['edge'] > 0 else ''
            print(f"  {periods:4d}p: M2+={r['hits']}/{r['total']} ({r['rate']:.2f}%) "
                  f"baseline={r['baseline']:.2f}% Edge={r['edge']:+.2f}% z={r['z']:.2f} {marker}")
        
        e = [results[f"{name}_{p}p"]['edge'] for p in [150, 500, 1500]]
        if all(x > 0 for x in e):
            stability = "✅ STABLE"
        elif e[2] < 0:
            stability = "❌ SHORT_MOMENTUM" if e[0] > 0 or e[1] > 0 else "❌ INEFFECTIVE"
        elif e[0] < 0 and e[2] > 0:
            stability = "⚠️ LATE_BLOOMER"
        else:
            stability = "⚠️ MIXED"
        print(f"  穩定性: {stability}")
    
    # ===================================================================
    # S4: Permutation Test (前幾名策略)
    # ===================================================================
    print("\n" + "=" * 70)
    print("  S4: Permutation Test (200 iterations, 1500期)")
    print("=" * 70)
    
    # 篩選出 1500p Edge > 0 的策略做 permutation
    perm_candidates = {}
    
    # 收集 1500p 結果
    for name in list(single_methods.keys()) + list(two_bet_methods.keys()) + list(three_bet_methods.keys()):
        key_1500 = f"{name}_1500p"
        if key_1500 in results and results[key_1500]['edge'] > 0:
            if name in single_methods:
                perm_candidates[name] = single_methods[name]
            elif name in two_bet_methods:
                perm_candidates[name] = two_bet_methods[name]
            elif name in three_bet_methods:
                perm_candidates[name] = three_bet_methods[name]
    
    perm_results = {}
    for name, (fn, n_bets) in perm_candidates.items():
        print(f"\n  --- Permutation: {name} ---")
        pr = permutation_test_539(fn, all_draws, 1500, n_bets, match_threshold=2, n_perm=200)
        perm_results[name] = pr
        sig = '★★' if pr['p_value'] < 0.01 else ('★' if pr['p_value'] < 0.05 else '')
        print(f"  Real={pr['real_rate']:.2f}% Perm_mean={pr['perm_mean']:.2f}% "
              f"Signal_Edge={pr['signal_edge']:+.2f}% z={pr['perm_z']:.2f} "
              f"p={pr['p_value']:.3f} {sig}")
    
    # ===================================================================
    # S5: McNemar 配對比較
    # ===================================================================
    print("\n" + "=" * 70)
    print("  S5: McNemar 配對比較 (1500期)")
    print("=" * 70)
    
    # 比較 2 注策略之間
    two_bet_names = [n for n in two_bet_methods if f"{n}_1500p" in results]
    
    # 選最佳 2注 vs 其他
    if two_bet_names:
        best_2bet = max(two_bet_names, key=lambda n: results[f"{n}_1500p"]['edge'])
        print(f"\n  最佳2注: {best_2bet} (Edge={results[f'{best_2bet}_1500p']['edge']:+.2f}%)")
        
        for name in two_bet_names:
            if name == best_2bet: continue
            details_a = results[f"{best_2bet}_1500p"]['hit_details']
            details_b = results[f"{name}_1500p"]['hit_details']
            mn = mcnemar_test(details_a, details_b)
            print(f"\n  {best_2bet} vs {name}:")
            print(f"    Both hit={mn['both_hit']}, A_only={mn['a_only']}, B_only={mn['b_only']}, "
                  f"Both miss={mn['both_miss']}")
            print(f"    χ²={mn['chi2']:.2f}, p={mn['p_value']:.4f}, Winner={mn['winner']}")
    
    # 比較 3 注策略
    three_bet_names = [n for n in three_bet_methods if f"{n}_1500p" in results]
    
    if three_bet_names:
        best_3bet = max(three_bet_names, key=lambda n: results[f"{n}_1500p"]['edge'])
        print(f"\n  最佳3注: {best_3bet} (Edge={results[f'{best_3bet}_1500p']['edge']:+.2f}%)")
        
        for name in three_bet_names:
            if name == best_3bet: continue
            details_a = results[f"{best_3bet}_1500p"]['hit_details']
            details_b = results[f"{name}_1500p"]['hit_details']
            mn = mcnemar_test(details_a, details_b)
            print(f"\n  {best_3bet} vs {name}:")
            print(f"    Both hit={mn['both_hit']}, A_only={mn['a_only']}, B_only={mn['b_only']}, "
                  f"Both miss={mn['both_miss']}")
            print(f"    χ²={mn['chi2']:.2f}, p={mn['p_value']:.4f}, Winner={mn['winner']}")
    
    # ===================================================================
    # S6: 總排名
    # ===================================================================
    print("\n" + "=" * 70)
    print("  S6: 全方法 1500期總排名")
    print("=" * 70)
    
    all_methods_1500 = {}
    for name in list(single_methods.keys()) + list(two_bet_methods.keys()) + list(three_bet_methods.keys()):
        key = f"{name}_1500p"
        if key in results:
            r = results[key]
            e150 = results.get(f"{name}_150p", {}).get('edge', 0)
            e500 = results.get(f"{name}_500p", {}).get('edge', 0)
            perm = perm_results.get(name, {})
            all_methods_1500[name] = {
                'n_bets': single_methods.get(name, two_bet_methods.get(name, three_bet_methods.get(name, (None, 0))))[1],
                'rate': r['rate'],
                'edge': r['edge'],
                'z': r['z'],
                'e150': e150,
                'e500': e500,
                'perm_p': perm.get('p_value', None),
                'signal_edge': perm.get('signal_edge', None),
            }
    
    print(f"\n  {'方法':<35} | {'注數':>3} | {'1500p Edge':>10} | {'z':>5} | {'150p':>6} | {'500p':>6} | {'Perm p':>7} | {'Sig Edge':>8} | {'Stability':>15}")
    print("  " + "-" * 120)
    
    for name in sorted(all_methods_1500, key=lambda n: -all_methods_1500[n]['edge']):
        m = all_methods_1500[name]
        e = [m['e150'], m['e500'], m['edge']]
        if all(x > 0 for x in e):
            stab = "STABLE"
        elif m['edge'] < 0:
            stab = "SHORT_MOM" if m['e150'] > 0 or m['e500'] > 0 else "INEFFECTIVE"
        elif m['e150'] < 0 and m['edge'] > 0:
            stab = "LATE_BLOOMER"
        else:
            stab = "MIXED"
        
        pp = f"{m['perm_p']:.3f}" if m['perm_p'] is not None else "N/A"
        se = f"{m['signal_edge']:+.2f}%" if m['signal_edge'] is not None else "N/A"
        sig = ''
        if m['perm_p'] is not None:
            sig = ' ★★' if m['perm_p'] < 0.01 else (' ★' if m['perm_p'] < 0.05 else '')
        
        print(f"  {name:<35} | {m['n_bets']:>3} | {m['edge']:>+9.2f}% | {m['z']:>5.2f} | {m['e150']:>+5.2f}% | {m['e500']:>+5.2f}% | {pp:>7}{sig} | {se:>8} | {stab:>15}")
    
    # ===================================================================
    # Save results
    # ===================================================================
    elapsed = time.time() - start
    
    save_data = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_draws': len(all_draws),
        'methods': {},
        'elapsed_seconds': elapsed,
    }
    
    for name in all_methods_1500:
        m = all_methods_1500[name]
        save_data['methods'][name] = {
            'n_bets': m['n_bets'],
            'edge_150p': m['e150'],
            'edge_500p': m['e500'],
            'edge_1500p': m['edge'],
            'z_1500p': m['z'],
            'perm_p': m['perm_p'],
            'signal_edge': m['signal_edge'],
        }
    
    output_path = os.path.join(project_root, 'backtest_539_rrf_complete.json')
    with open(output_path, 'w') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n  ✅ 結果已存: {output_path}")
    print(f"  ⏱️  耗時: {elapsed:.1f} 秒")
    print("=" * 70)


if __name__ == '__main__':
    main()
