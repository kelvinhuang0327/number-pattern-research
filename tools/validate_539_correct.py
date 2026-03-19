#!/usr/bin/env python3
"""
539 策略正確驗證腳本 (2026-02-28)

修正先前三個致命缺陷:
1. p=0.000 mathematically impossible → 使用 (count+1)/(n+1) 公式
2. ACB 1-bet proxy 無效 → 為每個注數跑專屬 multi-bet shuffle
3. P0 3bet 沒有 permutation → 每個候選策略都必須有自己的 permutation

正確方法論 (L37-aware):
- 多注 permutation: 每次洗牌生成 N 組隨機零重疊 5 碼注，
  對真實開獎檢查 M2+，建立 null distribution
- Signal Edge = 策略真實 M2+ rate - shuffle mean
- p = (count_exceed + 1) / (n_perm + 1)
- shuffle mean ≈ 32.58% for 3-bet (15/39 coverage, NOT 30.44%)
"""
import sys, os, json, time, random
import numpy as np
from collections import Counter, defaultdict
from numpy.fft import fft, fftfreq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api'))
from database import DatabaseManager

MAX_NUM, PICK = 39, 5

# ========== Feature Functions (deterministic, no randomness) ==========

def feat_acb(h, k=5, w=100):
    """ACB: freq_deficit + gap + boundary/modulus boosts"""
    r = h[-w:]
    c = Counter()
    for n in range(1, 40): c[n] = 0
    for d in r:
        for n in d['numbers']: c[n] += 1
    ls = {}
    for i, d in enumerate(r):
        for n in d['numbers']: ls[n] = i
    cur = len(r); exp = len(r) * 5 / 39
    sc = {}
    for n in range(1, 40):
        fd = exp - c[n]
        gs = (cur - ls.get(n, -1)) / (len(r) / 2)
        bb = 1.2 if n <= 5 or n >= 35 else 1.0
        mb = 1.1 if n % 3 == 0 else 1.0
        sc[n] = (fd * 0.4 + gs * 0.6) * bb * mb
    return sorted(sorted(sc, key=lambda x: -sc[x])[:k])

def feat_fourier(h, k=5, w=500):
    """Fourier: FFT period alignment score"""
    sl = h[-w:] if len(h) >= w else h
    wl = len(sl); sc = {}
    for n in range(1, 40):
        bh = np.zeros(wl)
        for i, d in enumerate(sl):
            if n in d['numbers']: bh[i] = 1
        if sum(bh) < 2: sc[n] = 0.0; continue
        yf = fft(bh - np.mean(bh)); xf = fftfreq(wl, 1)
        ip = np.where(xf > 0); py = np.abs(yf[ip]); px = xf[ip]
        pk = np.argmax(py); fv = px[pk]
        if fv == 0: sc[n] = 0.0; continue
        p = 1 / fv; lh = np.where(bh == 1)[0][-1]; g = (wl - 1) - lh
        sc[n] = 1.0 / (abs(g - p) + 1.0)
    return sorted(sorted(sc, key=lambda x: -sc[x])[:k])

def feat_cold(h, k=5, w=100):
    """Cold: lowest frequency numbers"""
    f = Counter(n for d in h[-w:] for n in d['numbers'])
    return sorted(sorted(range(1, 40), key=lambda n: f.get(n, 0))[:k])

def feat_echo_lag3(h, k=5, w=50):
    """Echo Lag-3: N-3 period numbers + gap scoring"""
    if len(h) < 4: return list(range(1, k + 1))
    lag3_nums = set(h[-3]['numbers'])
    f = Counter(n for d in h[-w:] for n in d['numbers'])
    last_seen = {}
    recent = h[-w:]
    for i, d in enumerate(recent):
        for n in d['numbers']: last_seen[n] = i
    cur = len(recent)
    sc = {}
    for n in range(1, 40):
        base = f.get(n, 0) / max(w, 1)
        gap_score = (cur - last_seen.get(n, -1)) / (w / 2) if n in last_seen else 1.5
        lag3_boost = 2.0 if n in lag3_nums else 0
        sc[n] = base * 0.3 + gap_score * 0.3 + lag3_boost * 0.4
    return sorted(sorted(sc, key=lambda x: -sc[x])[:k])

def feat_consec_pair(h, k=5, w=100):
    """Consecutive Pair: numbers likely to form (n, n+1) pairs"""
    recent = h[-w:]
    pair_count = Counter()
    for d in recent:
        nums = sorted(d['numbers'])
        for i in range(len(nums) - 1):
            if nums[i + 1] == nums[i] + 1:
                pair_count[(nums[i], nums[i + 1])] += 1
    f = Counter(n for d in recent for n in d['numbers'])
    sc = {}
    for n in range(1, 40):
        base = f.get(n, 0) / max(w, 1)
        pc_lower = pair_count.get((n, n + 1), 0) if n < 39 else 0
        pc_upper = pair_count.get((n - 1, n), 0) if n > 1 else 0
        consec_score = (pc_lower + pc_upper) / max(w, 1)
        sc[n] = base * 0.4 + consec_score * 3.0
    return sorted(sorted(sc, key=lambda x: -sc[x])[:k])

# ========== Orthogonal N-bet Generator ==========

def gen_nbets(fns, h, k=5):
    """Zero-overlap orthogonal bet generation (deterministic)"""
    bets = []; used = set()
    for fn in fns:
        raw = fn(h, k=k * 2)
        bet = [n for n in raw if n not in used][:k]
        while len(bet) < k:
            for n in range(1, 40):
                if n not in used and n not in bet:
                    bet.append(n); break
        used.update(bet)
        bets.append(sorted(bet))
    return bets

# ========== Walk-Forward Backtest ==========

def backtest(hist, pfunc, nb, periods=1500, warmup=200):
    """Walk-forward backtest: M2+ threshold for 539 (5/39)"""
    start = max(warmup, len(hist) - periods)
    hits = total = 0
    for i in range(start, len(hist)):
        h = hist[:i]
        bets = pfunc(h)
        actual = set(hist[i]['numbers'])
        if any(len(actual & set(b)) >= 2 for b in bets[:nb]):
            hits += 1
        total += 1
    rate = hits / total * 100 if total else 0
    return rate, total

# ========== Correct Multi-Bet Permutation Test ==========

def random_zero_overlap_bets(n_bets, k=5, max_num=39, rng=None):
    """Generate n_bets zero-overlap random bets of k numbers each"""
    if rng is None:
        rng = random
    pool = list(range(1, max_num + 1))
    rng.shuffle(pool)
    bets = []
    for i in range(n_bets):
        start = i * k
        end = start + k
        if end <= len(pool):
            bets.append(sorted(pool[start:end]))
        else:
            # Shouldn't happen for 539: 5*5=25 < 39
            remaining = [n for n in range(1, max_num + 1) if not any(n in b for b in bets)]
            rng.shuffle(remaining)
            bets.append(sorted(remaining[:k]))
    return bets

def multi_bet_permutation_test(hist, pfunc, nb, periods=1500, warmup=200,
                                n_perm=500, seed=42):
    """
    Correct multi-bet permutation test (L37-aware).
    
    Null hypothesis: strategy is no better than random zero-overlap N-bet selection.
    
    For each permutation iteration:
    - Generate N random zero-overlap bets for each period
    - Check M2+ against real actuals
    - This captures the geometric coverage benefit of zero-overlap structure
    
    p = (count_exceed + 1) / (n_perm + 1)  ← correct formula, min p = 1/(n_perm+1)
    """
    rng = random.Random(seed)
    start = max(warmup, len(hist) - periods)
    total_periods = len(hist) - start

    # Step 1: Get real strategy rate
    real_rate, real_total = backtest(hist, pfunc, nb, periods, warmup)
    print(f'  Real rate: {real_rate:.2f}% ({int(real_rate * real_total / 100)}/{real_total})')

    # Step 2: Get actual draws for the test window
    actuals = [set(hist[i]['numbers']) for i in range(start, len(hist))]

    # Step 3: Random shuffle permutation
    perm_rates = []
    for p_iter in range(n_perm):
        perm_hits = 0
        for actual in actuals:
            random_bets = random_zero_overlap_bets(nb, k=PICK, max_num=MAX_NUM, rng=rng)
            if any(len(actual & set(b)) >= 2 for b in random_bets):
                perm_hits += 1
        perm_rate = perm_hits / len(actuals) * 100
        perm_rates.append(perm_rate)
        if (p_iter + 1) % 100 == 0:
            print(f'    perm {p_iter + 1}/{n_perm}...')

    # Step 4: Correct p-value calculation
    pm = np.mean(perm_rates)
    ps = np.std(perm_rates)
    count_exceed = sum(1 for pr in perm_rates if pr >= real_rate)
    p_value = (count_exceed + 1) / (n_perm + 1)  # CORRECT: min = 1/501 ≈ 0.002
    signal_edge = real_rate - pm
    z = signal_edge / ps if ps > 0 else 0

    return {
        'real_rate': real_rate,
        'shuffle_mean': pm,
        'shuffle_std': ps,
        'signal_edge': signal_edge,
        'z': z,
        'p': p_value,
        'count_exceed': count_exceed,
        'n_perm': n_perm,
        'n_periods': total_periods,
    }

# ========== Current Strategy (SumRange+Bayesian+ZoneBalance) ==========

def current_539_3bet(h):
    """Wrap existing predict_539 strategy for comparison"""
    from models.unified_predictor import UnifiedPredictionEngine
    engine = UnifiedPredictionEngine()
    rules = {'pickCount': 5, 'minNumber': 1, 'maxNumber': 39}
    methods = ['sum_range_predict', 'bayesian_predict', 'zone_balance_predict']
    bets = []
    for method in methods:
        try:
            func = getattr(engine, method)
            result = func(h, rules)
            bets.append(result['numbers'])
        except Exception:
            continue
    return bets


# ========== Strategy Definitions ==========

STRATEGIES = {
    'ACB_1bet': {
        'func': lambda h: [feat_acb(h)],
        'nb': 1,
        'desc': 'ACB single bet',
    },
    'CURRENT_SumRange+Bayesian+ZoneBalance_3bet': {
        'func': current_539_3bet,
        'nb': 3,
        'desc': 'Current production: SumRange+Bayesian+ZoneBalance',
    },
    'ACB+Fourier+Cold_3bet': {
        'func': lambda h: gen_nbets([feat_acb, feat_fourier, feat_cold], h),
        'nb': 3,
        'desc': 'P0: ACB+Fourier+Cold orthogonal 3-bet',
    },
    'ACB+Fourier+Cold+EchoLag3_4bet': {
        'func': lambda h: gen_nbets([feat_acb, feat_fourier, feat_cold, feat_echo_lag3], h),
        'nb': 4,
        'desc': 'P1: +EchoLag3 as 4th bet',
    },
    'ACB+Fourier+Cold+EchoLag3+ConsecPair_5bet': {
        'func': lambda h: gen_nbets([feat_acb, feat_fourier, feat_cold, feat_echo_lag3, feat_consec_pair], h),
        'nb': 5,
        'desc': 'P2: +ConsecPair as 5th bet',
    },
}

# ========== Main Validation ==========

def main():
    t0 = time.time()

    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    hist = sorted(db.get_all_draws('DAILY_539'), key=lambda x: (x['date'], x['draw']))
    print(f'Loaded {len(hist)} periods of 539 data')

    # Select strategies
    target = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if target == 'all':
        strat_names = list(STRATEGIES.keys())
    else:
        strat_names = [s for s in STRATEGIES if target.lower() in s.lower()]
        if not strat_names:
            print(f'No strategy matching "{target}". Available: {list(STRATEGIES.keys())}')
            return

    all_results = {}

    for name in strat_names:
        strat = STRATEGIES[name]
        pfunc = strat['func']
        nb = strat['nb']

        print(f'\n{"=" * 70}')
        print(f'  {name} ({strat["desc"]})')
        print(f'{"=" * 70}')

        # Phase 1: Three-window walk-forward
        print('\n  Phase 1: Three-window walk-forward')
        edges = []
        rates = {}
        for wp in [150, 500, 1500]:
            rate, total = backtest(hist, pfunc, nb, wp)
            rates[wp] = rate
            print(f'    {wp}p: Rate={rate:.2f}% (n={total})')

        # Phase 2: Multi-bet permutation (correct method)
        print(f'\n  Phase 2: Multi-bet permutation ({nb}-bet, 500 iter)')
        perm_result = multi_bet_permutation_test(hist, pfunc, nb, n_perm=500)

        shuffle_mean = perm_result['shuffle_mean']
        signal_edge = perm_result['signal_edge']
        z = perm_result['z']
        p = perm_result['p']

        # Compute signal edges for three windows using shuffle mean as baseline
        three_window_edges = {}
        for wp in [150, 500, 1500]:
            three_window_edges[wp] = rates[wp] - shuffle_mean

        stab_edges = [three_window_edges[wp] for wp in [150, 500, 1500]]
        if all(e > 0 for e in stab_edges):
            stability = 'STABLE'
        elif stab_edges[-1] > 0 and stab_edges[0] <= 0:
            stability = 'LATE_BLOOMER'
        elif stab_edges[-1] > 0:
            stability = 'MIXED'
        else:
            stability = 'INEFFECTIVE'

        sig_str = '★' if p < 0.05 else ''
        sig_pass = '✅ PASS' if p < 0.05 else '❌ FAIL'

        print(f'\n  Results:')
        print(f'    Shuffle mean ({nb}-bet): {shuffle_mean:.2f}% (geometric coverage baseline)')
        print(f'    Signal Edge (1500p): {signal_edge:+.2f}%')
        print(f'    z = {z:.2f}{sig_str}, p = {p:.4f} ({perm_result["count_exceed"]}/{perm_result["n_perm"]})')
        print(f'    Signal: {sig_pass}')
        print(f'    Three-window signal edges:')
        for wp in [150, 500, 1500]:
            e = three_window_edges[wp]
            marker = '★' if wp == 1500 and p < 0.05 else ''
            print(f'      {wp}p: Rate={rates[wp]:.2f}% - ShuffleMean={shuffle_mean:.2f}% = SignalEdge={e:+.2f}%{marker}')
        print(f'    Stability: {stability}')

        all_results[name] = {
            'rates': {str(k): v for k, v in rates.items()},
            'shuffle_mean': shuffle_mean,
            'shuffle_std': perm_result['shuffle_std'],
            'signal_edge_1500': signal_edge,
            'three_window_signal_edges': {str(k): v for k, v in three_window_edges.items()},
            'z': z,
            'p': p,
            'count_exceed': perm_result['count_exceed'],
            'n_perm': perm_result['n_perm'],
            'n_periods': perm_result['n_periods'],
            'stability': stability,
            'pass': p < 0.05,
            'nb': nb,
        }

    # Summary
    print(f'\n{"=" * 70}')
    print(f'  SUMMARY')
    print(f'{"=" * 70}')
    for name, r in all_results.items():
        sig = '✅' if r['pass'] else '❌'
        print(f'  {sig} {name}:')
        print(f'     Rate(1500p)={r["rates"]["1500"]:.2f}% ShuffleMean={r["shuffle_mean"]:.2f}% '
              f'SignalEdge={r["signal_edge_1500"]:+.2f}% z={r["z"]:.2f} p={r["p"]:.4f} [{r["stability"]}]')

    # Save results
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'backtest_539_correct_validation.json')
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f'\nResults saved to {out_path}')

    elapsed = time.time() - t0
    print(f'Total time: {elapsed:.1f}s')


if __name__ == '__main__':
    main()
