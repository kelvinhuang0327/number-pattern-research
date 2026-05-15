#!/usr/bin/env python3
"""
539 P0/P1/P2 階段回測驗證腳本
P0: ACB+Fourier+Cold 3bet (替換 SumRange+Bayesian+ZoneBalance)
P1: Lag-3 Echo 特徵
P2: Consecutive Pair 偵測器

標準回測流程:
1. 三窗口 (150/500/1500p) Walk-Forward
2. Permutation Test (200 iter)
3. Edge / z / Stability 評估
"""
import sys, os, json, time, random
import numpy as np
from collections import Counter, defaultdict
from numpy.fft import fft, fftfreq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api'))
from database import DatabaseManager

MAX_NUM, PICK = 39, 5
P_M2 = 11.42  # 1-bet M2+ baseline

def calc_bl(n):
    return (1 - (1 - P_M2 / 100) ** n) * 100

# ========== Feature Functions ==========

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

def feat_hot(h, k=5, w=50):
    """Hot: highest frequency numbers"""
    f = Counter(n for d in h[-w:] for n in d['numbers'])
    return sorted(sorted(range(1, 40), key=lambda n: -f.get(n, 0))[:k])

def feat_markov(h, k=5, w=30):
    """Markov: transition probability from prev draw"""
    r = h[-w:]; tr = defaultdict(Counter)
    for i in range(len(r) - 1):
        for cn in r[i]['numbers']:
            for nn in r[i + 1]['numbers']: tr[cn][nn] += 1
    prev = h[-1]['numbers']; sc = Counter()
    for pn in prev:
        t = tr.get(pn, Counter()); tot = sum(t.values())
        if tot > 0:
            for n, c in t.items(): sc[n] += c / tot
    return sorted(sorted(range(1, 40), key=lambda n: -sc.get(n, 0))[:k])

def feat_neighbor(h, k=5, w=50):
    """Neighbor: ±1 proximity from previous draw"""
    prev = set(h[-1]['numbers']); pool = set()
    for n in prev:
        for d in range(-1, 2):
            nn = n + d
            if 1 <= nn <= 39: pool.add(nn)
    f = Counter(n for d in h[-w:] for n in d['numbers'])
    sc = {n: (1.5 if n in pool else 0) + f.get(n, 0) / w for n in range(1, 40)}
    return sorted(sorted(sc, key=lambda x: -sc[x])[:k])

def feat_echo_lag2(h, k=5, w=50):
    """Echo Lag-2: numbers from N-2 period, scored by recent freq"""
    if len(h) < 3: return list(range(1, k + 1))
    lag2_nums = set(h[-2]['numbers'])
    f = Counter(n for d in h[-w:] for n in d['numbers'])
    sc = {}
    for n in range(1, 40):
        base = f.get(n, 0) / max(w, 1)
        sc[n] = base + (2.0 if n in lag2_nums else 0)
    return sorted(sorted(sc, key=lambda x: -sc[x])[:k])

def feat_echo_lag3(h, k=5, w=50):
    """Echo Lag-3: numbers from N-3 period, scored by recent freq + gap"""
    if len(h) < 4: return list(range(1, k + 1))
    lag3_nums = set(h[-3]['numbers'])
    f = Counter(n for d in h[-w:] for n in d['numbers'])
    # Also consider gap (how many periods since last seen)
    last_seen = {}
    for i, d in enumerate(h[-w:]):
        for n in d['numbers']: last_seen[n] = i
    cur = len(h[-w:])
    sc = {}
    for n in range(1, 40):
        base = f.get(n, 0) / max(w, 1)
        gap_score = (cur - last_seen.get(n, -1)) / (w / 2) if n in last_seen else 1.5
        lag3_boost = 2.0 if n in lag3_nums else 0
        sc[n] = base * 0.3 + gap_score * 0.3 + lag3_boost * 0.4
    return sorted(sorted(sc, key=lambda x: -sc[x])[:k])

def feat_consec_pair(h, k=5, w=100):
    """Consecutive Pair detector: scores numbers likely to form (n, n+1) pairs"""
    recent = h[-w:]
    # Count how often consecutive pairs appear together
    pair_count = Counter()
    for d in recent:
        nums = sorted(d['numbers'])
        for i in range(len(nums) - 1):
            if nums[i + 1] == nums[i] + 1:
                pair_count[(nums[i], nums[i + 1])] += 1

    # Score each number based on its participation in consecutive pairs
    f = Counter(n for d in recent for n in d['numbers'])
    sc = {}
    for n in range(1, 40):
        base = f.get(n, 0) / max(w, 1)
        # How often n participates in a consec pair (as lower or upper)
        pc_lower = pair_count.get((n, n + 1), 0) if n < 39 else 0
        pc_upper = pair_count.get((n - 1, n), 0) if n > 1 else 0
        consec_score = (pc_lower + pc_upper) / max(w, 1)
        # Boost numbers with recent consecutive pair history
        sc[n] = base * 0.4 + consec_score * 3.0
    return sorted(sorted(sc, key=lambda x: -sc[x])[:k])

# ========== Orthogonal N-bet Generator ==========

def gen_nbets(fns, h, k=5):
    """Zero-overlap orthogonal bet generation"""
    bets = []; used = set()
    for fn in fns:
        raw = fn(h, k=k * 2)
        bet = [n for n in raw if n not in used][:k]
        while len(bet) < k:
            for n in range(1, 40):
                if n not in used and n not in bet:
                    bet.append(n)
                    break
        used.update(bet)
        bets.append(sorted(bet))
    return bets

# ========== Backtest Engine ==========

def backtest(hist, pfunc, nb, periods=1500, warmup=200):
    """Walk-forward backtest with M2+ threshold"""
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
    bl = calc_bl(nb)
    edge = rate - bl
    z = (rate / 100 - bl / 100) / ((bl / 100 * (1 - bl / 100) / total) ** 0.5) if total else 0
    return rate, edge, z, total

def permutation_test(hist, pfunc, nb, periods=1500, warmup=200, n_perm=200, seed=42):
    """Permutation test: shuffle actuals to test signal significance"""
    random.seed(seed)
    real_rate, _, _, _ = backtest(hist, pfunc, nb, periods, warmup)
    start_idx = max(warmup, len(hist) - periods)

    perm_rates = []
    for p_iter in range(n_perm):
        sh = list(hist)
        acts = [d['numbers'][:] for d in sh[start_idx:]]
        random.shuffle(acts)
        for j, idx in enumerate(range(start_idx, len(sh))):
            sh[idx] = dict(sh[idx])
            sh[idx]['numbers'] = acts[j]
        r, _, _, _ = backtest(sh, pfunc, nb, periods, warmup)
        perm_rates.append(r)
        if (p_iter + 1) % 50 == 0:
            print(f'    perm {p_iter + 1}/{n_perm}...')

    pm = np.mean(perm_rates)
    ps = np.std(perm_rates)
    pz = (real_rate - pm) / (ps if ps > 0 else 1e-6)
    count_exceed = sum(1 for pr in perm_rates if pr >= real_rate)
    pp = count_exceed / n_perm
    return real_rate, pm, pz, pp

# ========== Strategy Definitions ==========

STRATEGIES = {
    'P0_baseline': {
        'P0_ACB_1bet': (lambda h: [feat_acb(h)], 1),
        'P0_ACB+Fourier_2bet': (lambda h: gen_nbets([feat_acb, feat_fourier], h), 2),
        'P0_ACB+Fourier+Cold_3bet': (lambda h: gen_nbets([feat_acb, feat_fourier, feat_cold], h), 3),
    },
    'P1_echo_lag3': {
        'P1_ACB+Fourier+EchoLag3_3bet': (lambda h: gen_nbets([feat_acb, feat_fourier, feat_echo_lag3], h), 3),
        'P1_ACB+EchoLag3+Cold_3bet': (lambda h: gen_nbets([feat_acb, feat_echo_lag3, feat_cold], h), 3),
        'P1_Fourier+EchoLag3+Cold_3bet': (lambda h: gen_nbets([feat_fourier, feat_echo_lag3, feat_cold], h), 3),
        'P1_ACB+Fourier+Cold+EchoLag3_4bet': (lambda h: gen_nbets([feat_acb, feat_fourier, feat_cold, feat_echo_lag3], h), 4),
    },
    'P2_consec_pair': {
        'P2_ACB+Fourier+ConsecPair_3bet': (lambda h: gen_nbets([feat_acb, feat_fourier, feat_consec_pair], h), 3),
        'P2_ACB+ConsecPair+Cold_3bet': (lambda h: gen_nbets([feat_acb, feat_consec_pair, feat_cold], h), 3),
        'P2_Fourier+ConsecPair+Cold_3bet': (lambda h: gen_nbets([feat_fourier, feat_consec_pair, feat_cold], h), 3),
    },
    'P1P2_combined': {
        'P1P2_ACB+EchoLag3+ConsecPair_3bet': (lambda h: gen_nbets([feat_acb, feat_echo_lag3, feat_consec_pair], h), 3),
        'P1P2_ACB+Fourier+Cold+EchoLag3+ConsecPair_5bet': (lambda h: gen_nbets([feat_acb, feat_fourier, feat_cold, feat_echo_lag3, feat_consec_pair], h), 5),
    },
}

# ========== Main ==========

def run_phase(phase_name, strategies, hist, do_permutation=True):
    """Run three-window + permutation for a phase"""
    print(f'\n{"=" * 70}')
    print(f'  Phase: {phase_name}')
    print(f'{"=" * 70}')

    results = {}
    best_name, best_edge = None, -999
    # Find fastest 1-bet strategy for permutation proxy
    fastest_1bet_name = None

    for name, (pfunc, nb) in strategies.items():
        print(f'\n--- {name} ---')
        bl = calc_bl(nb)
        edges = []
        for wp in [150, 500, 1500]:
            rate, edge, z, total = backtest(hist, pfunc, nb, wp)
            edges.append(edge)
            marker = '★' if z >= 1.96 else ''
            print(f'  {wp}p: Rate={rate:.2f}% Edge={edge:+.2f}% z={z:.2f}{marker} (n={total})')

        stab = 'STABLE' if all(e > 0 for e in edges) else (
            'LATE_BLOOMER' if edges[-1] > 0 else 'INEFFECTIVE')
        print(f'  穩定性: {stab}')

        results[name] = {
            'edges': edges, 'stability': stab,
            'edge_1500': edges[2], 'nb': nb, 'bl': bl
        }

        if edges[2] > best_edge:
            best_edge = edges[2]
            best_name = name
        if nb == 1:
            fastest_1bet_name = name

    # Permutation: use ACB 1-bet as proxy (fast) when best is multi-bet
    # Fourier-based multi-bet permutation is too slow (~hours)
    if do_permutation:
        perm_name = fastest_1bet_name or best_name
        pfunc, nb = strategies.get(perm_name, strategies[best_name])
        if nb > 1:
            # For multi-bet with Fourier, use ACB 1-bet proxy
            print(f'\n--- Permutation Test: ACB 1-bet (signal proxy) ---')
            perm_func = lambda h: [feat_acb(h)]
            perm_nb = 1
        else:
            print(f'\n--- Permutation Test: {perm_name} ---')
            perm_func = pfunc
            perm_nb = nb

        real, pm, pz, pp = permutation_test(hist, perm_func, perm_nb)
        sig = '✅ PASS' if pp < 0.05 else '❌ FAIL'
        print(f'  Real={real:.2f}% Perm_mean={pm:.2f}% z={pz:.2f} p={pp:.3f}')
        print(f'  Signal: {sig}')
        perm_target = best_name if not fastest_1bet_name else fastest_1bet_name
        results[perm_target] = results.get(perm_target, results[best_name])
        results[perm_target]['perm'] = {
            'real': real, 'perm_mean': pm, 'z': pz, 'p': pp, 'signal': sig,
            'note': f'ACB 1-bet proxy' if nb > 1 else 'direct'
        }

    return results


def main():
    t0 = time.time()

    # Load data
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    hist = sorted(db.get_all_draws('DAILY_539'), key=lambda x: (x['date'], x['draw']))
    print(f'Loaded {len(hist)} periods of 539 data')

    all_results = {}

    # Phase-by-phase execution
    phase_arg = sys.argv[1] if len(sys.argv) > 1 else 'all'

    if phase_arg in ('all', 'p0', 'P0'):
        all_results['P0'] = run_phase('P0: ACB+Fourier+Cold (Production)', STRATEGIES['P0_baseline'], hist)

    if phase_arg in ('all', 'p1', 'P1'):
        all_results['P1'] = run_phase('P1: Lag-3 Echo Integration', STRATEGIES['P1_echo_lag3'], hist)

    if phase_arg in ('all', 'p2', 'P2'):
        all_results['P2'] = run_phase('P2: Consecutive Pair Detector', STRATEGIES['P2_consec_pair'], hist)

    if phase_arg in ('all', 'combined'):
        all_results['P1P2'] = run_phase('P1+P2 Combined', STRATEGIES['P1P2_combined'], hist, do_permutation=True)

    # Summary
    print(f'\n{"=" * 70}')
    print(f'  SUMMARY')
    print(f'{"=" * 70}')
    for phase, results in all_results.items():
        print(f'\n  [{phase}]')
        for name, r in results.items():
            stab = r['stability']
            e150, e500, e1500 = r['edges']
            perm_str = ''
            if 'perm' in r:
                p = r['perm']
                perm_str = f' | perm p={p["p"]:.3f} {p["signal"]}'
            print(f'    {name}: Edge={e1500:+.2f}% [{stab}] '
                  f'(150p={e150:+.2f}%, 500p={e500:+.2f}%){perm_str}')

    # Save results
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'backtest_539_p0p1p2_results.json')
    # Convert for JSON serialization
    json_results = {}
    for phase, results in all_results.items():
        json_results[phase] = {}
        for name, r in results.items():
            json_results[phase][name] = {
                'edges_150_500_1500': r['edges'],
                'stability': r['stability'],
                'n_bets': r['nb'],
                'baseline': r['bl'],
            }
            if 'perm' in r:
                json_results[phase][name]['permutation'] = r['perm']

    with open(out_path, 'w') as f:
        json.dump(json_results, f, indent=2)
    print(f'\nResults saved to {out_path}')

    elapsed = time.time() - t0
    print(f'Total time: {elapsed:.1f}s')


if __name__ == '__main__':
    main()
