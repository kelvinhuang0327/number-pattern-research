#!/usr/bin/env python3
"""
今彩539 檢討回測: 基於 115000052 期分析結果的新策略方向驗證
目標: 測試 SumRange, Markov, ACB+Markov+SumRange 等候選組合的歷史表現
"""
import sys, os, json
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations
from numpy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
from database import DatabaseManager

MAX_NUM = 39
PICK = 5
BASELINE_1BET = 5 / 39 * 100  # ~12.82% for M2+
# M2+: C(5,2)*C(34,3)/C(39,5) ≈ probability of at least 2 matches
# Actually for 539, M2+ => P(≥2 match in 5/39) 
# Exact: 1 - P(0) - P(1)
# P(0) = C(34,5)/C(39,5) = 278256/575757 ≈ 0.4832
# P(1) = C(5,1)*C(34,4)/C(39,5) = 5*46376/575757 ≈ 0.4026
# P(≥2) = 1 - 0.4832 - 0.4026 ≈ 0.1142 = 11.42%
P_M2_SINGLE = 11.42

def calc_baselines(n_bets):
    """N注隨機基準 M2+"""
    return (1 - (1 - P_M2_SINGLE/100)**n_bets) * 100

# ========== 特徵函數 (每個返回 Top-K 號碼) ==========

def feat_acb(history, k=PICK, window=100):
    recent = history[-window:] if len(history) >= window else history
    counter = Counter()
    for n in range(1, MAX_NUM + 1): counter[n] = 0
    for d in recent:
        for n in d['numbers']: counter[n] += 1
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']: last_seen[n] = i
    current = len(recent)
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, MAX_NUM + 1)}
    expected = len(recent) * PICK / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM + 1):
        fd = expected - counter[n]
        gs = gaps[n] / (len(recent) / 2)
        bb = 1.2 if (n <= 5 or n >= 35) else 1.0
        mb = 1.1 if n % 3 == 0 else 1.0
        scores[n] = (fd * 0.4 + gs * 0.6) * bb * mb
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:k])

def feat_fourier(history, k=PICK, window=500):
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    scores = {}
    for n in range(1, MAX_NUM + 1):
        bh = np.zeros(w)
        for idx, d in enumerate(h):
            if n in d['numbers']: bh[idx] = 1
        if sum(bh) < 2: scores[n] = 0.0; continue
        yf = fft(bh - np.mean(bh)); xf = fftfreq(w, 1)
        ip = np.where(xf > 0); py = np.abs(yf[ip]); px = xf[ip]
        pk = np.argmax(py); fv = px[pk]
        if fv == 0: scores[n] = 0.0; continue
        period = 1 / fv
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:k])

def feat_cold(history, k=PICK, window=100):
    freq = Counter(n for d in history[-window:] for n in d['numbers'])
    ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: freq.get(n, 0))
    return sorted(ranked[:k])

def feat_hot(history, k=PICK, window=50):
    freq = Counter(n for d in history[-window:] for n in d['numbers'])
    ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: -freq.get(n, 0))
    return sorted(ranked[:k])

def feat_markov(history, k=PICK, window=30):
    recent = history[-window:] if len(history) >= window else history
    transitions = defaultdict(Counter)
    for i in range(len(recent) - 1):
        for cn in recent[i]['numbers']:
            for nn in recent[i + 1]['numbers']:
                transitions[cn][nn] += 1
    prev = history[-1]['numbers']
    scores = Counter()
    for pn in prev:
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for n, cnt in trans.items():
                scores[n] += cnt / total
    ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: -scores.get(n, 0))
    return sorted(ranked[:k])

def feat_echo_lag2(history, k=PICK):
    if len(history) < 3: return list(range(1, k+1))
    lag2 = set(history[-2]['numbers'])
    freq = Counter(n for d in history[-50:] for n in d['numbers'])
    scores = {n: (2.0 if n in lag2 else 0.0) + freq.get(n, 0)/50.0 for n in range(1, MAX_NUM+1)}
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:k])

def feat_ema_cross(history, k=PICK):
    freq_s = Counter(n for d in history[-10:] for n in d['numbers'])
    freq_l = Counter(n for d in history[-50:] for n in d['numbers'])
    scores = {n: freq_s.get(n,0)/10 - freq_l.get(n,0)/50 for n in range(1, MAX_NUM+1)}
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:k])

def feat_sum_range(history, k=PICK, window=300):
    h = history[-window:] if len(history) >= window else history
    sums = [sum(d['numbers']) for d in h]
    mu = np.mean(sums)
    freq = Counter(n for d in history[-100:] for n in d['numbers'])
    pool = sorted(range(1, MAX_NUM+1), key=lambda n: -freq.get(n, 0))[:15]
    best, best_dist = None, float('inf')
    for combo in combinations(pool, PICK):
        dist = abs(sum(combo) - mu)
        if dist < best_dist:
            best, best_dist = combo, dist
    return sorted(best) if best else sorted(pool[:PICK])

def feat_gap(history, k=PICK):
    last_seen = {}
    for i, d in enumerate(history):
        for n in d['numbers']: last_seen[n] = i
    current = len(history)
    scores = {n: current - last_seen.get(n, -1) for n in range(1, MAX_NUM+1)}
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:k])

def feat_neighbor(history, k=PICK):
    prev = set(history[-1]['numbers'])
    pool = set()
    for n in prev:
        for d in range(-1, 2):
            nn = n + d
            if 1 <= nn <= MAX_NUM: pool.add(nn)
    freq = Counter(n for d in history[-50:] for n in d['numbers'])
    scores = {n: (1.5 if n in pool else 0.0) + freq.get(n,0)/50 for n in range(1, MAX_NUM+1)}
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:k])

def feat_bayesian(history, k=PICK, window=100):
    recent = history[-window:] if len(history) >= window else history
    total = len(recent)
    scores = {}
    for n in range(1, MAX_NUM + 1):
        hits = sum(1 for d in recent if n in d['numbers'])
        scores[n] = (1.0 + hits) / (2.0 + total)
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:k])

def feat_deviation_hot(history, k=PICK, window=50):
    freq = Counter(n for d in history[-window:] for n in d['numbers'])
    expected = window * PICK / MAX_NUM
    scores = {n: freq.get(n,0) - expected for n in range(1, MAX_NUM+1)}
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:k])

def feat_freq_deficit(history, k=PICK, window=100):
    freq = Counter(n for d in history[-window:] for n in d['numbers'])
    expected = window * PICK / MAX_NUM
    scores = {n: expected - freq.get(n,0) for n in range(1, MAX_NUM+1)}
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:k])

# ========== N注生成 (正交拼接) ==========

def generate_nbets(feat_funcs, history, k=PICK):
    """用多特徵函數生成N注（零重疊正交）"""
    bets = []
    used = set()
    for func in feat_funcs:
        if callable(func):
            raw = func(history, k=k*2)  # 多取一些候選
        else:
            raw = func
        bet = []
        for n in raw:
            if n not in used and len(bet) < k:
                bet.append(n)
                used.add(n)
        # 補齊
        if len(bet) < k:
            for n in range(1, MAX_NUM + 1):
                if n not in used and len(bet) < k:
                    bet.append(n)
                    used.add(n)
        bets.append(sorted(bet))
    return bets

# ========== 回測引擎 ==========

def backtest(history, predict_func, n_bets, periods=1500, warmup=200):
    """Walk-forward backtest"""
    start = max(warmup, len(history) - periods)
    hits = 0
    total = 0
    for i in range(start, len(history)):
        h = history[:i]
        bets = predict_func(h)
        actual = set(history[i]['numbers'])
        any_hit = False
        for bet in bets[:n_bets]:
            matches = len(actual & set(bet))
            if matches >= 2:  # M2+
                any_hit = True
                break
        if any_hit:
            hits += 1
        total += 1
    rate = hits / total * 100 if total > 0 else 0
    baseline = calc_baselines(n_bets)
    edge = rate - baseline
    z = (rate/100 - baseline/100) / ((baseline/100 * (1-baseline/100) / total)**0.5) if total > 0 else 0
    return {'hits': hits, 'total': total, 'rate': round(rate, 2), 'baseline': round(baseline, 2), 
            'edge': round(edge, 2), 'z': round(z, 2)}

def three_window(history, predict_func, n_bets, warmup=200):
    """三窗口驗證"""
    results = {}
    for window in [150, 500, 1500]:
        start = max(warmup, len(history) - window)
        actual_window = len(history) - start
        if actual_window < 50:
            results[f'{window}p'] = None
            continue
        results[f'{window}p'] = backtest(history, predict_func, n_bets, window, warmup)
    return results

def permutation_test(history, predict_func, n_bets, periods=1500, warmup=200, n_perm=200):
    """Permutation test"""
    import random
    real = backtest(history, predict_func, n_bets, periods, warmup)
    real_rate = real['rate']
    
    perm_rates = []
    for _ in range(n_perm):
        # 打亂開獎號碼
        start = max(warmup, len(history) - periods)
        shuffled = list(history)
        actuals = [d['numbers'][:] for d in shuffled[start:]]
        random.shuffle(actuals)
        for j, idx in enumerate(range(start, len(shuffled))):
            shuffled[idx] = dict(shuffled[idx])
            shuffled[idx]['numbers'] = actuals[j]
        perm_result = backtest(shuffled, predict_func, n_bets, periods, warmup)
        perm_rates.append(perm_result['rate'])
    
    perm_mean = np.mean(perm_rates)
    perm_std = np.std(perm_rates) if np.std(perm_rates) > 0 else 1e-6
    z = (real_rate - perm_mean) / perm_std
    p = np.mean([1 for pr in perm_rates if pr >= real_rate])
    
    return {
        'real_rate': real_rate,
        'perm_mean': round(float(perm_mean), 2),
        'perm_std': round(float(perm_std), 2),
        'z': round(float(z), 2),
        'p': round(float(p), 3),
        'signal': p < 0.05,
    }

# ========== 候選策略 ==========

STRATEGIES = {
    # 1注策略
    'ACB_1bet': {
        'func': lambda h: [feat_acb(h)],
        'n_bets': 1,
    },
    'Fourier_1bet': {
        'func': lambda h: [feat_fourier(h)],
        'n_bets': 1,
    },
    'Markov_1bet': {
        'func': lambda h: [feat_markov(h)],
        'n_bets': 1,
    },
    'SumRange_1bet': {
        'func': lambda h: [feat_sum_range(h)],
        'n_bets': 1,
    },
    # 2注策略
    'ACB+SumRange_2bet': {
        'func': lambda h: generate_nbets([feat_acb, feat_sum_range], h),
        'n_bets': 2,
    },
    'ACB+Markov_2bet': {
        'func': lambda h: generate_nbets([feat_acb, feat_markov], h),
        'n_bets': 2,
    },
    'Markov+SumRange_2bet': {
        'func': lambda h: generate_nbets([feat_markov, feat_sum_range], h),
        'n_bets': 2,
    },
    'ACB+Echo_2bet': {
        'func': lambda h: generate_nbets([feat_acb, feat_echo_lag2], h),
        'n_bets': 2,
    },
    'Fourier+Cold_2bet': {
        'func': lambda h: generate_nbets([feat_fourier, feat_cold], h),
        'n_bets': 2,
    },
    'Fourier+Markov_2bet': {
        'func': lambda h: generate_nbets([feat_fourier, feat_markov], h),
        'n_bets': 2,
    },
    'Echo+Hot_2bet': {
        'func': lambda h: generate_nbets([feat_echo_lag2, feat_hot], h),
        'n_bets': 2,
    },
    'Cold+SumRange_2bet': {
        'func': lambda h: generate_nbets([feat_cold, feat_sum_range], h),
        'n_bets': 2,
    },
    # 3注策略
    'ACB+Markov+SumRange_3bet': {
        'func': lambda h: generate_nbets([feat_acb, feat_markov, feat_sum_range], h),
        'n_bets': 3,
    },
    'ACB+Fourier+Cold_3bet': {
        'func': lambda h: generate_nbets([feat_acb, feat_fourier, feat_cold], h),
        'n_bets': 3,
    },
    'ACB+Echo+SumRange_3bet': {
        'func': lambda h: generate_nbets([feat_acb, feat_echo_lag2, feat_sum_range], h),
        'n_bets': 3,
    },
    'Markov+Echo+Hot_3bet': {
        'func': lambda h: generate_nbets([feat_markov, feat_echo_lag2, feat_hot], h),
        'n_bets': 3,
    },
    'Fourier+Markov+Cold_3bet': {
        'func': lambda h: generate_nbets([feat_fourier, feat_markov, feat_cold], h),
        'n_bets': 3,
    },
    'Fourier+Echo+SumRange_3bet': {
        'func': lambda h: generate_nbets([feat_fourier, feat_echo_lag2, feat_sum_range], h),
        'n_bets': 3,
    },
    'ACB+Hot+Neighbor_3bet': {
        'func': lambda h: generate_nbets([feat_acb, feat_hot, feat_neighbor], h),
        'n_bets': 3,
    },
    'ACB+Markov+Echo_3bet': {
        'func': lambda h: generate_nbets([feat_acb, feat_markov, feat_echo_lag2], h),
        'n_bets': 3,
    },
}


def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    history = sorted(db.get_all_draws('DAILY_539'), key=lambda x: (x['date'], x['draw']))
    
    print(f"今彩539 Strategy Backtest | 總期數: {len(history)}")
    print(f"基準: 1注 M2+={P_M2_SINGLE}%, 2注={calc_baselines(2):.2f}%, 3注={calc_baselines(3):.2f}%")
    print()
    
    # Phase 1: 快速1500p回測所有策略
    print("=" * 80)
    print("Phase 1: 1500期 Walk-Forward 回測")
    print("=" * 80)
    
    results = {}
    for name, cfg in STRATEGIES.items():
        bt = backtest(history, cfg['func'], cfg['n_bets'], periods=1500, warmup=200)
        results[name] = bt
        marker = '★' if bt['edge'] > 0 and bt['z'] > 1.64 else ('▲' if bt['edge'] > 0 else '')
        print(f"  {name:<35} Rate={bt['rate']:6.2f}% Edge={bt['edge']:+.2f}% z={bt['z']:.2f} {marker}")
    
    # Phase 2: 排名 Top-6 做三窗口 + permutation
    print()
    print("=" * 80)
    print("Phase 2: Top-6 策略 三窗口 + Permutation 驗證")
    print("=" * 80)
    
    # 按 edge 排序 (同注數比較)
    ranked = sorted(results.items(), key=lambda x: -x[1]['edge'])
    top6 = ranked[:6]
    
    for name, bt in top6:
        cfg = STRATEGIES[name]
        print(f"\n--- {name} ---")
        
        # 三窗口
        tw = three_window(history, cfg['func'], cfg['n_bets'])
        for w, r in tw.items():
            if r:
                print(f"  {w}: Rate={r['rate']:.2f}% Edge={r['edge']:+.2f}% z={r['z']:.2f}")
            else:
                print(f"  {w}: 數據不足")
        
        # 判斷穩定性
        edges = [tw[w]['edge'] for w in tw if tw[w]]
        all_positive = all(e > 0 for e in edges)
        stability = 'STABLE' if all_positive else ('LATE_BLOOMER' if edges[-1] > 0 else 'INEFFECTIVE')
        print(f"  穩定性: {stability}")
        
        # Permutation
        if stability != 'INEFFECTIVE':
            perm = permutation_test(history, cfg['func'], cfg['n_bets'])
            print(f"  Permutation: z={perm['z']:.2f} p={perm['p']:.3f} signal={'✅' if perm['signal'] else '❌'}")
    
    print()
    print("=" * 80)
    print("Phase 3: 現有生產策略 (SumRange+Bayesian+ZoneBalance 3bet) 對比基準")
    print("=" * 80)
    
    # 模擬生產策略
    def production_3bet(h):
        b1 = feat_sum_range(h)
        b2 = feat_bayesian(h)
        b3_zone = []
        freq = Counter(n for d in h[-100:] for n in d['numbers'])
        used = set(b1) | set(b2)
        zones = [range(1,14), range(14,27), range(27,40)]
        for z in zones:
            z_sorted = sorted(z, key=lambda n: freq.get(n, 0))
            for n in z_sorted:
                if n not in used and len(b3_zone) < PICK:
                    b3_zone.append(n)
                    used.add(n)
                    break
        while len(b3_zone) < PICK:
            for n in range(1, MAX_NUM+1):
                if n not in used:
                    b3_zone.append(n)
                    used.add(n)
                    if len(b3_zone) >= PICK: break
        return [b1, b2, sorted(b3_zone)]
    
    prod_bt = backtest(history, production_3bet, 3, periods=1500, warmup=200)
    print(f"  Production 3bet: Rate={prod_bt['rate']:.2f}% Edge={prod_bt['edge']:+.2f}% z={prod_bt['z']:.2f}")
    tw_prod = three_window(history, production_3bet, 3)
    for w, r in tw_prod.items():
        if r:
            print(f"    {w}: Rate={r['rate']:.2f}% Edge={r['edge']:+.2f}%")
    
    print("\n完成！")


if __name__ == '__main__':
    main()
