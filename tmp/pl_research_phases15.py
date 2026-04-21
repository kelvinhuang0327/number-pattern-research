#!/usr/bin/env python3
"""
POWER_LOTTO Full Research Script — Phases 1-5
2026-04-19

Phase 1: Full anti-leakage backtest (5 strategies × all history)
Phase 2: PP3-Z3Gap upgrade threshold analysis
Phase 3: midfreq_fourier_mk_3bet vs fourier_rhythm_3bet eval
Phase 4: 5 new hypotheses 300p scan
Phase 5: Integrated report + lessons.md update
"""
import sys, os, json, random, math
import numpy as np
from datetime import datetime
from collections import Counter
from math import comb
import sqlite3

ROOT = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'lottery_api'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

np.random.seed(42)
random.seed(42)

DB_PATH  = os.path.join(ROOT, 'lottery_api/data/lottery_v2.db')
DATA_DIR = os.path.join(ROOT, 'data')
MEM_DIR  = os.path.join(ROOT, 'memory')

MAX_NUM = 38
BASELINE_1BET = 0.01034   # 38C6 single-bet M3+ prob
BASELINE_2BET = 0.0759
BASELINE_3BET = 0.1117
BASELINE_4BET = 0.1460
BASELINE_5BET = 0.1791
BASELINES = {1: BASELINE_1BET, 2: BASELINE_2BET, 3: BASELINE_3BET,
             4: BASELINE_4BET, 5: BASELINE_5BET}

ERRORS = []

def log_error(phase, msg):
    ERRORS.append({'phase': phase, 'msg': msg, 'ts': datetime.now().isoformat()})
    print(f'  [ERROR] Phase {phase}: {msg}')

# ════════════════════════════════════════════════════════════
# Data Loading
# ════════════════════════════════════════════════════════════
def load_draws():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('''
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type='POWER_LOTTO'
        ORDER BY CAST(draw AS INTEGER) ASC
    ''').fetchall()
    conn.close()
    result = []
    for draw, date, nums_str in rows:
        s = nums_str.strip()
        nums = json.loads(s) if s.startswith('[') else [int(n) for n in s.split(',')]
        result.append({'draw': str(draw), 'date': date, 'numbers': nums})
    return result

# ════════════════════════════════════════════════════════════
# Strategy Definitions
# ════════════════════════════════════════════════════════════
def _get_strategies():
    from tools.power_fourier_rhythm import fourier_rhythm_predict
    from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet
    from tools.power_midfreq_fourier import midfreq_fourier_markov_3bet
    from tools.backtest_power_pp3v2_comprehensive import pp3_z3gap

    return {
        'fourier_rhythm_3bet':      lambda h: fourier_rhythm_predict(h, n_bets=3, window=500),
        'midfreq_fourier_mk_3bet':  lambda h: midfreq_fourier_markov_3bet(h),
        'pp3_freqort_4bet':         lambda h: generate_orthogonal_5bet(h)[:4],
        'orthogonal_5bet':          lambda h: generate_orthogonal_5bet(h),
        'pp3_z3gap':                lambda h: pp3_z3gap(h),
    }

STRATEGY_NBETS = {
    'fourier_rhythm_3bet': 3,
    'midfreq_fourier_mk_3bet': 3,
    'pp3_freqort_4bet': 4,
    'orthogonal_5bet': 5,
    'pp3_z3gap': 3,
}

# ════════════════════════════════════════════════════════════
# Core Backtest Helpers
# ════════════════════════════════════════════════════════════
def is_m3plus(bets, actual):
    actual_set = set(actual)
    for b in bets:
        if sum(1 for n in b if n in actual_set) >= 3:
            return True
    return False

def best_hit_count(bets, actual):
    actual_set = set(actual)
    best = 0
    for b in bets:
        h = sum(1 for n in b if n in actual_set)
        if h > best:
            best = h
    return best

# ════════════════════════════════════════════════════════════
# PHASE 1 — Full Anti-Leakage Backtest
# ════════════════════════════════════════════════════════════
def phase1_backtest(draws):
    print('\n' + '='*60)
    print('PHASE 1: Full Anti-Leakage Backtest')
    print('='*60)

    try:
        strategies = _get_strategies()
    except Exception as e:
        log_error(1, f'Strategy import failed: {e}')
        return []

    strat_names = list(strategies.keys())
    total = len(draws)
    START = 50
    print(f'  Draws: {total}, testing from idx {START} ({draws[START]["draw"]}) to {draws[-1]["draw"]}')
    print(f'  Strategies: {strat_names}')

    # Track errors per strategy
    err_count = {s: 0 for s in strat_names}
    records = []

    out_path = os.path.join(DATA_DIR, 'power_lotto_full_backtest.jsonl')
    with open(out_path, 'w', encoding='utf-8') as fout:
        for idx in range(START, total):
            hist = draws[:idx]
            target = draws[idx]
            actual = target['numbers']

            rec = {
                'draw': target['draw'],
                'date': target['date'],
                'actual': actual,
                'strategies': {},
            }

            for name, func in strategies.items():
                try:
                    raw = func(hist)
                    bets = [b['numbers'] if isinstance(b, dict) else b for b in raw]
                    hit = is_m3plus(bets, actual)
                    hc  = best_hit_count(bets, actual)
                    rec['strategies'][name] = {'is_m3plus': hit, 'hit_count': hc}
                except Exception as e:
                    err_count[name] += 1
                    rec['strategies'][name] = {'is_m3plus': False, 'hit_count': 0, 'error': True}

            records.append(rec)
            fout.write(json.dumps(rec) + '\n')

            if (idx - START + 1) % 300 == 0:
                print(f'    {idx - START + 1}/{total - START}...', flush=True)

    print(f'  Done. Records: {len(records)}')
    for s, e in err_count.items():
        print(f'    {s}: errors={e}')

    return records

# ════════════════════════════════════════════════════════════
# PHASE 2 — PP3-Z3Gap Upgrade Analysis
# ════════════════════════════════════════════════════════════
def mcnemar_exact_p(b, c):
    n = b + c
    if n == 0: return 1.0
    lo = min(b, c)
    p = sum(comb(n, k) * (0.5 ** n) for k in range(lo + 1))
    return min(1.0, 2 * p)

def perm_test_edge(hits, baseline, n_perm=200, seed=42):
    """
    One-sided permutation test: H0 = each draw is M3+ with prob=baseline.
    Simulate n_perm sequences under H0 and count how many have edge >= observed.
    """
    rng = random.Random(seed)
    n = len(hits)
    obs = sum(hits) / n - baseline
    count_ge = 0
    for _ in range(n_perm):
        sim = sum(1 for _ in range(n) if rng.random() < baseline)
        if (sim / n - baseline) >= obs:
            count_ge += 1
    return obs, count_ge / n_perm

def compute_edge_at_windows(records, key, baseline, windows=None):
    if windows is None:
        windows = [150, 300, 500, 1500]
    n = len(records)
    result = {}
    for w in windows:
        if n < w:
            result[w] = None
            continue
        last = records[-w:]
        hr = sum(1 for r in last if r['strategies'].get(key, {}).get('is_m3plus', False)) / w
        result[w] = round(hr - baseline, 4)
    return result

def phase2_z3gap(records):
    print('\n' + '='*60)
    print('PHASE 2: PP3-Z3Gap Upgrade Analysis')
    print('='*60)

    BASELINE = BASELINE_3BET
    UPGRADE_THRESHOLD = 0.0243
    KEY = 'pp3_z3gap'
    KEY4 = 'pp3_freqort_4bet'

    n = len(records)
    z3_hits = [r['strategies'].get(KEY, {}).get('is_m3plus', False) for r in records]
    pp4_hits = [r['strategies'].get(KEY4, {}).get('is_m3plus', False) for r in records]

    # A. Rolling Window Edge Trend (step 50)
    rolling_trend = []
    step = 50
    for end_idx in range(1500, n + 1, step):
        snap = records[:end_idx]
        w300 = snap[-300:] if len(snap) >= 300 else snap
        w500 = snap[-500:] if len(snap) >= 500 else snap
        w1500 = snap[-1500:] if len(snap) >= 1500 else snap
        def edge(recs, k):
            if not recs: return None
            return round(sum(1 for r in recs if r['strategies'].get(k, {}).get('is_m3plus', False)) / len(recs) - BASELINE, 4)
        rolling_trend.append({
            'end_idx': end_idx,
            'draw': records[end_idx - 1]['draw'],
            'e300': edge(w300, KEY),
            'e500': edge(w500, KEY),
            'e1500': edge(w1500, KEY),
        })

    current_1500p = rolling_trend[-1]['e1500']
    gap = round(UPGRADE_THRESHOLD - current_1500p, 4) if current_1500p is not None else None
    print(f'  Current 1500p edge: {current_1500p:.4f}')
    print(f'  Upgrade threshold: {UPGRADE_THRESHOLD:.4f}')
    print(f'  Gap: {gap:.4f}')

    # B. ETA Estimation (linear projection from recent 300p)
    # Use last 3 rolling steps × 300p edge to estimate slope
    recent_300p = [t['e300'] for t in rolling_trend[-6:] if t['e300'] is not None]
    if len(recent_300p) >= 3:
        # Linear regression: y = a + bx
        xs = list(range(len(recent_300p)))
        ys = recent_300p
        x_mean = sum(xs) / len(xs)
        y_mean = sum(ys) / len(ys)
        num = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(len(xs)))
        den = sum((xs[i] - x_mean) ** 2 for i in range(len(xs)))
        slope_per_50 = num / den if den != 0 else 0
        print(f'  300p slope per 50 draws: {slope_per_50:.4f}')

        if slope_per_50 <= 0:
            eta = "REGRESSING"
        elif current_1500p is not None:
            # Each step = 50 draws; 1500p edge lags behind 300p edge
            # Approximate: 1500p edge shifts at ~slope/5 per 50 draws (diluted by 5x window ratio)
            eta_steps = math.ceil(gap / max(slope_per_50 / 5, 1e-6))
            eta = eta_steps * 50 if eta_steps < 500 else "UNLIKELY_WITHIN_1000"
        else:
            eta = None
    else:
        slope_per_50 = 0
        eta = "INSUFFICIENT_DATA"

    print(f'  ETA: {eta}')

    # C. Permutation Test
    obs_edge, perm_p = perm_test_edge(z3_hits, BASELINE, n_perm=200, seed=42)
    print(f'  Perm test: obs_edge={obs_edge:.4f}, p={perm_p:.3f}')

    # D. McNemar vs pp3_freqort_4bet (both 3 vs 4 bet comparison — compare M3+ hit rates)
    # Note: pp3_z3gap is 3-bet, pp3_freqort_4bet is 4-bet; McNemar on M3+ boolean
    b = sum(1 for i in range(n) if z3_hits[i] and not pp4_hits[i])
    c = sum(1 for i in range(n) if pp4_hits[i] and not z3_hits[i])
    mc_p = mcnemar_exact_p(b, c)
    mc_net = b - c
    print(f'  McNemar vs pp3_4bet: b={b}, c={c}, net={mc_net}, p={mc_p:.4f}')

    # Verdict
    if isinstance(eta, str) and 'REGRESS' in str(eta):
        verdict = 'REGRESSING'
        rec = 'CLOSE'
    elif current_1500p is not None and current_1500p >= UPGRADE_THRESHOLD:
        verdict = 'ON_TRACK'
        rec = f'RUN_MCNEMAR_NOW'
    elif isinstance(eta, int) and eta < 300:
        verdict = 'ON_TRACK'
        rec = f'WAIT_{eta}_DRAWS'
    elif perm_p > 0.15:
        verdict = 'STALLED'
        rec = 'EXTEND_WATCH_300'
    else:
        verdict = 'STALLED'
        rec = 'EXTEND_WATCH_300'

    result = {
        'current_1500p_edge': current_1500p,
        'upgrade_threshold': UPGRADE_THRESHOLD,
        'gap_to_threshold': gap,
        'rolling_trend': rolling_trend[-20:],  # last 20 snapshots
        'rolling_trend_full_len': len(rolling_trend),
        'estimated_draws_to_threshold': eta,
        'perm_p': round(perm_p, 4),
        'mcnemar_vs_pp3_4bet': {'b': b, 'c': c, 'net': mc_net, 'p': round(mc_p, 4)},
        'verdict': verdict,
        'recommendation': rec,
        'slope_per_50_draws': round(slope_per_50, 6),
        'n_total': n,
    }

    out = os.path.join(DATA_DIR, 'pp3_z3gap_upgrade_analysis.json')
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f'  Saved: {out}')
    print(f'  Verdict: {verdict} | Recommendation: {rec}')
    return result

# ════════════════════════════════════════════════════════════
# PHASE 3 — midfreq_fourier_mk_3bet Upgrade Eval
# ════════════════════════════════════════════════════════════
def phase3_mk3bet(records):
    print('\n' + '='*60)
    print('PHASE 3: midfreq_fourier_mk_3bet vs fourier_rhythm_3bet')
    print('='*60)

    BASELINE = BASELINE_3BET
    KEY_MK = 'midfreq_fourier_mk_3bet'
    KEY_FR = 'fourier_rhythm_3bet'
    n = len(records)

    mk_hits = [r['strategies'].get(KEY_MK, {}).get('is_m3plus', False) for r in records]
    fr_hits = [r['strategies'].get(KEY_FR, {}).get('is_m3plus', False) for r in records]

    # A. Full OOS McNemar
    b = sum(1 for i in range(n) if mk_hits[i] and not fr_hits[i])
    c = sum(1 for i in range(n) if fr_hits[i] and not mk_hits[i])
    mc_p = mcnemar_exact_p(b, c)
    mc_net = b - c
    print(f'  McNemar: b={b}, c={c}, net={mc_net}, p={mc_p:.4f}')

    # Rolling McNemar every 100 draws
    rolling_mc = []
    step = 100
    for end in range(step, n + 1, step):
        seg = range(max(0, end - step), end)
        b_r = sum(1 for i in seg if mk_hits[i] and not fr_hits[i])
        c_r = sum(1 for i in seg if fr_hits[i] and not mk_hits[i])
        rolling_mc.append({
            'end_idx': end,
            'draw': records[end - 1]['draw'],
            'b': b_r, 'c': c_r, 'net': b_r - c_r,
        })

    # B. Four-window edge comparison
    def win_edges(hits, label):
        edges = {}
        for w in [150, 300, 500, 1500]:
            if n < w: edges[f'w{w}'] = None; continue
            last = hits[-w:]
            edges[f'w{w}'] = round(sum(last) / w - BASELINE, 4)
        return edges

    mk_edges = win_edges(mk_hits, 'mk')
    fr_edges = win_edges(fr_hits, 'fr')
    print(f'  MK edges: {mk_edges}')
    print(f'  FR edges: {fr_edges}')

    # C. Phi coefficient
    # Phi = (ad - bc) / sqrt((a+b)(c+d)(a+c)(b+d))
    both  = sum(1 for i in range(n) if mk_hits[i] and fr_hits[i])
    b_only = sum(1 for i in range(n) if mk_hits[i] and not fr_hits[i])
    c_only = sum(1 for i in range(n) if not mk_hits[i] and fr_hits[i])
    neither = sum(1 for i in range(n) if not mk_hits[i] and not fr_hits[i])

    denom_phi = math.sqrt(
        (both + b_only) * (c_only + neither) *
        (both + c_only) * (b_only + neither)
    ) if all(x > 0 for x in [both + b_only, c_only + neither, both + c_only, b_only + neither]) else 1e-6
    phi = (both * neither - b_only * c_only) / denom_phi
    print(f'  Phi coefficient: {phi:.4f}')

    # Verdict
    if mc_p < 0.05 and mc_net > 0:
        if mk_edges['w1500'] is not None and mk_edges['w1500'] > fr_edges['w1500']:
            verdict = 'PROMOTE_MK'
        else:
            verdict = 'KEEP_MONITORING'
    elif mc_net < -10 and mc_p < 0.1:
        verdict = 'RETIRE_MK'
    else:
        verdict = 'KEEP_MONITORING'

    phi_note = 'HIGH_CORRELATION' if phi > 0.7 else ('LOW_CORRELATION' if phi < 0.4 else 'MODERATE_CORRELATION')

    result = {
        'mk_3bet_full_1500p': mk_edges.get('w1500'),
        'fourier_3bet_full_1500p': fr_edges.get('w1500'),
        'mcnemar': {'b': b, 'c': c, 'net': mc_net, 'p': round(mc_p, 4)},
        'rolling_mcnemar_trend': rolling_mc,
        'four_window_mk': mk_edges,
        'four_window_fr': fr_edges,
        'phi_correlation': round(phi, 4),
        'phi_interpretation': phi_note,
        'verdict': verdict,
        'notes': f'Phi={phi:.3f} ({phi_note}). MK 1500p={mk_edges.get("w1500")}, FR 1500p={fr_edges.get("w1500")}.',
    }

    out = os.path.join(DATA_DIR, 'mk3bet_upgrade_report.json')
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f'  Saved: {out}')
    print(f'  Verdict: {verdict}')
    return result

# ════════════════════════════════════════════════════════════
# PHASE 4 — New Hypothesis Scan
# ════════════════════════════════════════════════════════════

# Existing strategy M3+ hits for correlation
def _ref_hits(records, key='fourier_rhythm_3bet'):
    return [r['strategies'].get(key, {}).get('is_m3plus', False) for r in records]

def _phi_with_ref(new_hits, ref_hits):
    n = len(new_hits)
    if n == 0: return 0
    both   = sum(1 for i in range(n) if new_hits[i] and ref_hits[i])
    b_only = sum(1 for i in range(n) if new_hits[i] and not ref_hits[i])
    c_only = sum(1 for i in range(n) if not new_hits[i] and ref_hits[i])
    nei    = sum(1 for i in range(n) if not new_hits[i] and not ref_hits[i])
    d = math.sqrt((both+b_only)*(c_only+nei)*(both+c_only)*(b_only+nei))
    return (both*nei - b_only*c_only) / d if d > 1e-8 else 0

# ── H-PL-01: Gap Pattern Lag-1 ──────────────────────────────
def _gap_lag1_2bet(history):
    """
    Lag-1 gap pattern: 計算上一期6個號碼形成的連續間隔（排序後差值），
    預測下一期號碼偏向相似間隔分布。
    Signal: 近30期中，gap_mean 最穩定的 6個號碼選為 bet1；
            其次穩定的 6個號碼選為 bet2。
    """
    if len(history) < 10:
        return [[1,2,3,4,5,6], [7,8,9,10,11,12]]

    window = min(len(history), 100)
    recent = history[-window:]

    # Gap variance per number: how consistent is this number's gap to previous appearance
    last_seen = {}
    gaps_by_num = {n: [] for n in range(1, MAX_NUM+1)}

    for i, d in enumerate(recent):
        for n in d['numbers'][:6]:
            if n < 1 or n > MAX_NUM: continue
            if n in last_seen:
                gaps_by_num[n].append(i - last_seen[n])
            last_seen[n] = i

    # Stable gap = low CV (coefficient of variation), and gap close to expected (~window/freq)
    expected_gap = window * 6 / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM+1):
        g = gaps_by_num[n]
        if len(g) < 3:
            scores[n] = 0
            continue
        mean_g = sum(g) / len(g)
        std_g = (sum((x - mean_g)**2 for x in g) / len(g)) ** 0.5
        cv = std_g / mean_g if mean_g > 0 else 999
        # Low CV = stable gap pattern → higher score
        # Also: if gap is near expected and last gap is close to mean
        last_gap = (len(recent) - 1 - last_seen.get(n, 0)) if n in last_seen else window
        dist_to_pattern = abs(last_gap - mean_g) / max(mean_g, 1)
        scores[n] = (1 / (cv + 0.1)) * (1 / (dist_to_pattern + 0.5))

    ranked = sorted(range(1, MAX_NUM+1), key=lambda x: -scores[x])
    return [sorted(ranked[:6]), sorted(ranked[6:12])]

# ── H-PL-02: Mod7 Pattern ───────────────────────────────────
def _mod7_2bet(history):
    """
    Mod7 週期性: 計算近500期各 mod7 殘差類別(0-6)的出現率，
    選高機率 mod7 類別的號碼。
    """
    window = min(len(history), 300)
    recent = history[-window:]
    mod7_counts = Counter()
    total_draws = len(recent)

    for d in recent:
        for n in d['numbers'][:6]:
            if 1 <= n <= MAX_NUM:
                mod7_counts[n % 7] += 1

    # Expected: 38 numbers, each mod7 class has ~5-6 numbers
    # Classes with above-average hits are "hot mod7"
    expected_per_class = total_draws * 6 / 7
    hot_mods = sorted(range(7), key=lambda m: -mod7_counts[m])[:3]

    # Bet1: top mod7 class numbers sorted by individual frequency
    num_freq = Counter()
    for d in recent:
        for n in d['numbers'][:6]:
            if 1 <= n <= MAX_NUM:
                num_freq[n] += 1

    bet1_pool = [n for n in range(1, MAX_NUM+1) if n % 7 in set(hot_mods[:2])]
    bet1_pool.sort(key=lambda x: -num_freq.get(x, 0))
    bet1 = sorted(bet1_pool[:6])

    bet2_pool = [n for n in range(1, MAX_NUM+1) if n not in set(bet1)]
    bet2_pool.sort(key=lambda x: -num_freq.get(x, 0))
    bet2 = sorted(bet2_pool[:6])

    return [bet1, bet2]

# ── H-PL-03: Zone Concentration ─────────────────────────────
def _zone_conc_2bet(history):
    """
    Zone concentration: 統計近300期 zone(1-13/14-26/27-38) combo，
    選最優 zone pattern 對應號碼。
    """
    window = min(len(history), 300)
    recent = history[-window:]

    def get_zone(n):
        if n <= 13: return 0
        elif n <= 26: return 1
        return 2

    zone_patterns = Counter()
    for d in recent:
        nums = [n for n in d['numbers'][:6] if 1 <= n <= MAX_NUM]
        pattern = tuple(sorted(Counter(get_zone(n) for n in nums).items()))
        zone_patterns[pattern] += 1

    # Most common pattern
    best_pattern = zone_patterns.most_common(1)[0][0] if zone_patterns else None
    zone_targets = dict(best_pattern) if best_pattern else {0: 2, 1: 2, 2: 2}

    # Individual number frequency within zones
    zone_freq = {0: Counter(), 1: Counter(), 2: Counter()}
    for d in recent:
        for n in d['numbers'][:6]:
            if 1 <= n <= MAX_NUM:
                zone_freq[get_zone(n)][n] += 1

    # Build bet1 from zone targets
    bet1 = []
    for z, count in zone_targets.items():
        zone_nums = sorted(zone_freq[z].keys(), key=lambda x: -zone_freq[z][x])
        bet1.extend(zone_nums[:count])
    bet1 = sorted(set(bet1[:6]))
    if len(bet1) < 6:
        all_nums = sorted(range(1, MAX_NUM+1), key=lambda x: -sum(zone_freq[get_zone(x)].get(x, 0) for z in range(3)))
        for n in all_nums:
            if n not in set(bet1):
                bet1.append(n)
            if len(bet1) == 6:
                break
    bet1 = sorted(bet1[:6])

    bet2_pool = [n for n in range(1, MAX_NUM+1) if n not in set(bet1)]
    for z, count in zone_targets.items():
        zone_nums = sorted(zone_freq[z].keys(), key=lambda x: -zone_freq[z][x])

    all_freq = Counter()
    for d in recent:
        for n in d['numbers'][:6]:
            if 1 <= n <= MAX_NUM:
                all_freq[n] += 1
    bet2_pool.sort(key=lambda x: -all_freq.get(x, 0))
    bet2 = sorted(bet2_pool[:6])

    return [bet1, bet2]

# ── H-PL-04: Consecutive Number Bonus ───────────────────────
def _consec_2bet(history):
    """
    Consecutive numbers: 近50期統計連號對(連續兩號都出現)最頻繁的號碼，
    選高連號出現率號碼。
    """
    window = min(len(history), 200)
    recent = history[-window:]

    consec_count = Counter()
    for d in recent:
        nums = sorted(n for n in d['numbers'][:6] if 1 <= n <= MAX_NUM)
        for i in range(len(nums)-1):
            if nums[i+1] - nums[i] == 1:
                consec_count[nums[i]] += 1
                consec_count[nums[i+1]] += 1

    # Also use regular frequency
    freq = Counter()
    for d in recent:
        for n in d['numbers'][:6]:
            if 1 <= n <= MAX_NUM:
                freq[n] += 1

    # Combined score: consecutive bonus + regular frequency
    scores = {n: consec_count.get(n, 0) * 2 + freq.get(n, 0) for n in range(1, MAX_NUM+1)}
    ranked = sorted(range(1, MAX_NUM+1), key=lambda x: -scores[x])
    return [sorted(ranked[:6]), sorted(ranked[6:12])]

# ── H-PL-05: Frequency Momentum ─────────────────────────────
def _freq_momentum_2bet(history):
    """
    Frequency Momentum: MidFreq(近100期) × (近20期上升頻率)
    比較近100期 vs 近20期的出現頻率差，作為 momentum 加成。
    """
    window_long = min(len(history), 100)
    window_short = min(len(history), 20)
    long_hist = history[-window_long:]
    short_hist = history[-window_short:]

    expected_long = window_long * 6 / MAX_NUM
    expected_short = window_short * 6 / MAX_NUM

    freq_long = Counter()
    for d in long_hist:
        for n in d['numbers'][:6]:
            if 1 <= n <= MAX_NUM:
                freq_long[n] += 1

    freq_short = Counter()
    for d in short_hist:
        for n in d['numbers'][:6]:
            if 1 <= n <= MAX_NUM:
                freq_short[n] += 1

    scores = {}
    for n in range(1, MAX_NUM+1):
        # MidFreq: closeness to expected frequency (low deviation = high score)
        midfreq_score = 1.0 / (abs(freq_long[n] - expected_long) + 0.5)
        # Momentum: if recently more frequent than historically (rising)
        long_rate = freq_long[n] / window_long
        short_rate = freq_short[n] / window_short
        momentum = max(0, short_rate - long_rate)  # positive momentum only
        scores[n] = midfreq_score * (1 + momentum * 10)

    ranked = sorted(range(1, MAX_NUM+1), key=lambda x: -scores[x])
    return [sorted(ranked[:6]), sorted(ranked[6:12])]

def phase4_hypothesis_scan(all_draws):
    print('\n' + '='*60)
    print('PHASE 4: New Hypothesis 300p Scan')
    print('='*60)

    BASELINE = BASELINE_2BET  # All hypotheses generate 2 bets
    N_PERM = 200
    THRESHOLD_EDGE = 0.0
    THRESHOLD_PERM = 0.10
    THRESHOLD_CORR = 0.5

    hypotheses_def = [
        ('H-PL-01', 'Gap Pattern Lag-1',      'Stable gap pattern in recent 100p → predict repeating gap positions', _gap_lag1_2bet),
        ('H-PL-02', 'Mod7 Periodicity',       'Chi-square mod7 → select hot mod7 classes', _mod7_2bet),
        ('H-PL-03', 'Zone Concentration',     'Best zone pattern (1-13/14-26/27-38) in 300p', _zone_conc_2bet),
        ('H-PL-04', 'Consecutive Num Bonus',  'Consecutive pair frequency bonus', _consec_2bet),
        ('H-PL-05', 'Freq Momentum 2bet',     'MidFreq × rising frequency momentum', _freq_momentum_2bet),
    ]

    n_total = len(all_draws)
    # Use last 300p for 300p backtest; need warmup >= 100
    WARMUP = 100
    TEST_START = max(WARMUP, n_total - 300)
    test_range = range(TEST_START, n_total)
    print(f'  Testing on draws {all_draws[TEST_START]["draw"]} ~ {all_draws[-1]["draw"]} (n={len(test_range)})')

    # Pre-compute reference strategy hits for correlation
    ref_hits_300 = []
    ref_strat_hits = {}
    for i in test_range:
        hist = all_draws[:i]
        actual = all_draws[i]['numbers']
        from tools.power_fourier_rhythm import fourier_rhythm_predict
        try:
            bets = fourier_rhythm_predict(hist, n_bets=3, window=500)
            ref_strat_hits[i] = is_m3plus(bets, actual)
        except:
            ref_strat_hits[i] = False

    results = []

    for hyp_id, hyp_name, hyp_desc, hyp_func in hypotheses_def:
        print(f'\n  [{hyp_id}] {hyp_name}')
        hits = []
        errors = 0

        for i in test_range:
            hist = all_draws[:i]
            actual = all_draws[i]['numbers']
            try:
                bets = hyp_func(hist)
                hits.append(is_m3plus(bets, actual))
            except Exception as e:
                hits.append(False)
                errors += 1

        n_test = len(hits)
        if n_test == 0:
            results.append({'id': hyp_id, 'name': hyp_name, 'verdict': 'FAIL', 'error': 'no data'})
            continue

        edge_300p = round(sum(hits) / n_test - BASELINE, 4)

        # Permutation test
        obs_e, perm_p_val = perm_test_edge(hits, BASELINE, n_perm=N_PERM, seed=42)

        # Correlation with best strategy
        ref_hits_list = [ref_strat_hits.get(i, False) for i in test_range]
        phi = _phi_with_ref(hits, ref_hits_list)

        # Verdict
        pass_edge = edge_300p > THRESHOLD_EDGE
        pass_perm = perm_p_val < THRESHOLD_PERM
        pass_corr = abs(phi) < THRESHOLD_CORR

        if pass_edge and pass_perm and pass_corr:
            verdict = 'PASS'
        elif pass_edge and (pass_perm or pass_corr):
            verdict = 'MARGINAL'
        else:
            verdict = 'FAIL'

        hr = sum(hits) / n_test
        print(f'    edge_300p={edge_300p:.4f}  perm_p={perm_p_val:.3f}  phi={phi:.3f}  errors={errors}  → {verdict}')

        results.append({
            'id': hyp_id,
            'name': hyp_name,
            'description': hyp_desc,
            'n_tested': n_test,
            'hit_rate': round(hr, 4),
            'edge_300p': edge_300p,
            'perm_p': round(perm_p_val, 4),
            'correlation_with_fourier_3bet': round(phi, 4),
            'verdict': verdict,
            'errors': errors,
            'notes': f'HR={hr:.3f} vs baseline={BASELINE:.4f}. pass_edge={pass_edge}, pass_perm={pass_perm}, pass_corr={pass_corr}',
        })

    passed = [r for r in results if r['verdict'] == 'PASS']
    marginal = [r for r in results if r['verdict'] == 'MARGINAL']
    best = None
    if passed:
        best = max(passed, key=lambda x: x['edge_300p'])['id']
    elif marginal:
        best = max(marginal, key=lambda x: x['edge_300p'])['id']

    output = {
        'scan_date': datetime.now().isoformat(),
        'n_tested_per_hypothesis': len(test_range),
        'baseline_2bet': BASELINE,
        'hypotheses': results,
        'passed_count': len(passed),
        'marginal_count': len(marginal),
        'best_candidate': best,
    }

    out = os.path.join(DATA_DIR, 'power_lotto_hypothesis_scan.json')
    with open(out, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f'\n  Saved: {out}')
    print(f'  Passed: {len(passed)}, Marginal: {len(marginal)}, Best: {best}')
    return output

# ════════════════════════════════════════════════════════════
# PHASE 5 — Integrated Report + lessons.md
# ════════════════════════════════════════════════════════════
def phase5_report(p2_result, p3_result, p4_result, draws):
    print('\n' + '='*60)
    print('PHASE 5: Integrated Report & lessons.md Update')
    print('='*60)

    latest_draw = draws[-1]['draw']

    # Determine overall health
    has_pass = p4_result['passed_count'] > 0
    has_marginal = p4_result['marginal_count'] > 0
    mk_verdict = p3_result['verdict']
    z3_verdict = p2_result['verdict']

    if has_pass or mk_verdict == 'PROMOTE_MK':
        overall_health = 'EXPANDING'
    elif mk_verdict == 'RETIRE_MK' and not has_pass:
        overall_health = 'CONTRACTING'
    else:
        overall_health = 'STABLE'

    # Build action items
    action_items = []

    # PP3-Z3Gap actions
    if z3_verdict == 'REGRESSING':
        action_items.append({'item': 'PP3-Z3Gap: CLOSE watch. Edge regressing. Update lessons.md.', 'priority': 'HIGH'})
    elif z3_verdict == 'ON_TRACK':
        eta = p2_result.get('estimated_draws_to_threshold', 'N/A')
        action_items.append({'item': f'PP3-Z3Gap: ON TRACK. ETA {eta} draws.', 'priority': 'MED'})
    else:
        action_items.append({'item': f'PP3-Z3Gap: STALLED at {p2_result["current_1500p_edge"]:.4f}. Extend watch 300 draws.', 'priority': 'MED'})

    # mk_3bet actions
    if mk_verdict == 'PROMOTE_MK':
        mc = p3_result['mcnemar']
        action_items.append({
            'item': f'PROMOTE midfreq_fourier_mk_3bet: McNemar net={mc["net"]} p={mc["p"]:.4f}. Run deploy command after manual verify.',
            'priority': 'HIGH'
        })
    elif mk_verdict == 'RETIRE_MK':
        action_items.append({'item': 'RETIRE midfreq_fourier_mk_3bet: McNemar significantly negative. Remove from monitoring.', 'priority': 'HIGH'})
    else:
        action_items.append({'item': f'midfreq_fourier_mk_3bet: KEEP MONITORING. phi={p3_result["phi_correlation"]:.3f}.', 'priority': 'LOW'})

    # Hypothesis actions
    if has_pass:
        best = p4_result['best_candidate']
        action_items.append({'item': f'New hypothesis {best} PASSED screening. Run full 1500p backtest next session.', 'priority': 'HIGH'})
    elif has_marginal:
        mg_ids = [r['id'] for r in p4_result['hypotheses'] if r['verdict'] == 'MARGINAL']
        action_items.append({'item': f'Marginal hypotheses {mg_ids}: extend test to 600p.', 'priority': 'MED'})
    else:
        action_items.append({'item': 'No new hypotheses passed. Continue current portfolio.', 'priority': 'LOW'})

    report = {
        'generated_at': datetime.now().isoformat(),
        'latest_draw': latest_draw,
        'pp3_z3gap': {
            'verdict': z3_verdict,
            'current_1500p': p2_result['current_1500p_edge'],
            'gap_to_threshold': p2_result['gap_to_threshold'],
            'draws_to_threshold_or_close': p2_result.get('estimated_draws_to_threshold'),
            'perm_p': p2_result['perm_p'],
        },
        'mk_3bet': {
            'verdict': mk_verdict,
            'mcnemar_net': p3_result['mcnemar']['net'],
            'mcnemar_p': p3_result['mcnemar']['p'],
            'phi': p3_result['phi_correlation'],
            'mk_1500p': p3_result['mk_3bet_full_1500p'],
            'fr_1500p': p3_result['fourier_3bet_full_1500p'],
        },
        'new_hypotheses': {
            'passed_count': p4_result['passed_count'],
            'marginal_count': p4_result['marginal_count'],
            'best_candidate': p4_result['best_candidate'],
            'details': p4_result['hypotheses'],
        },
        'overall_power_lotto_health': overall_health,
        'action_items': action_items,
    }

    out = os.path.join(DATA_DIR, 'power_lotto_research_report_2026_04_19.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f'  Saved: {out}')

    # ── lessons.md updates ──
    lessons_path = os.path.join(MEM_DIR, 'lessons.md')
    new_entries = []
    now_str = datetime.now().strftime('%Y-%m-%d')

    if z3_verdict == 'REGRESSING':
        new_entries.append(f"""
**L108 — PP3-Z3Gap CLOSED: 邊際衰退，無升格依據** ({now_str})
- 全史 1500p edge = {p2_result['current_1500p_edge']:.4f}，升格門檻 +2.43%
- McNemar vs pp3_4bet: net={p2_result['mcnemar_vs_pp3_4bet']['net']}, p={p2_result['mcnemar_vs_pp3_4bet']['p']:.4f}
- perm_p = {p2_result['perm_p']:.4f}
- 邊際斜率為負（slope={p2_result.get('slope_per_50_draws', 0):.6f}/50p）
- 結論：Z3 high-gap 策略不優於 pp3_freqort_4bet，結案。不再監控。
""".strip())

    if mk_verdict == 'RETIRE_MK':
        mk_mc = p3_result['mcnemar']
        new_entries.append(f"""
**L109 — midfreq_fourier_mk_3bet RETIRED: McNemar 顯著落後 fourier_rhythm_3bet** ({now_str})
- McNemar: net={mk_mc['net']}, p={mk_mc['p']:.4f} (顯著落後)
- MK 1500p={p3_result['mk_3bet_full_1500p']:.4f} vs FR 1500p={p3_result['fourier_3bet_full_1500p']:.4f}
- Phi={p3_result['phi_correlation']:.3f}
- 退役：從 RSM 監控列表移除。
""".strip())

    if has_pass:
        best_hyp = next((h for h in p4_result['hypotheses'] if h['id'] == p4_result['best_candidate']), None)
        if best_hyp:
            new_entries.append(f"""
**L110 — 新假設 {best_hyp['id']} ({best_hyp['name']}) PASS 300p 篩選** ({now_str})
- edge_300p = {best_hyp['edge_300p']:.4f}, perm_p = {best_hyp['perm_p']:.4f}
- Phi with fourier_3bet = {best_hyp['correlation_with_fourier_3bet']:.3f}
- 下步：執行 1500p 全史回測 + McNemar vs 現役策略
- Description: {best_hyp['description']}
""".strip())

    if new_entries:
        try:
            with open(lessons_path, 'a', encoding='utf-8') as lf:
                lf.write('\n\n')
                for entry in new_entries:
                    lf.write(entry + '\n\n')
            print(f'  Updated lessons.md with {len(new_entries)} new entries.')
        except Exception as e:
            log_error(5, f'lessons.md update failed: {e}')

    # Summary
    print('\n' + '='*60)
    print('RESEARCH SUMMARY')
    print('='*60)
    print(f'  Overall Health: {overall_health}')
    print(f'  PP3-Z3Gap: {z3_verdict} (1500p={p2_result["current_1500p_edge"]:.4f}, gap={p2_result["gap_to_threshold"]:.4f})')
    print(f'  MK_3bet: {mk_verdict} (net={p3_result["mcnemar"]["net"]}, p={p3_result["mcnemar"]["p"]:.4f})')
    print(f'  New hypotheses: {p4_result["passed_count"]} PASS, {p4_result["marginal_count"]} MARGINAL')
    print('\n  Action Items:')
    for a in action_items:
        print(f'  [{a["priority"]}] {a["item"]}')

    return report

# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════
def main():
    start_ts = datetime.now()
    print(f'=== POWER_LOTTO RESEARCH — {start_ts.strftime("%Y-%m-%d %H:%M")} ===')

    draws = load_draws()
    print(f'Loaded {len(draws)} POWER_LOTTO draws (latest: {draws[-1]["draw"]} {draws[-1]["date"]})')

    # ── Phase 1 ──
    backtest_path = os.path.join(DATA_DIR, 'power_lotto_full_backtest.jsonl')
    if os.path.exists(backtest_path):
        # Load existing to skip re-computation
        with open(backtest_path) as f:
            records = [json.loads(line) for line in f if line.strip()]
        print(f'\nPhase 1: Loaded existing backtest ({len(records)} records)')
        if len(records) < 1800:
            print('  Re-running (too few records)...')
            records = phase1_backtest(draws)
    else:
        records = phase1_backtest(draws)

    if not records:
        log_error('main', 'Phase 1 produced no records. Aborting.')
        with open(os.path.join(DATA_DIR, 'pl_agent_errors.json'), 'w') as f:
            json.dump(ERRORS, f, indent=2)
        return

    print(f'\nPhase 1 complete: {len(records)} records')

    # ── Phase 2 ──
    try:
        p2 = phase2_z3gap(records)
    except Exception as e:
        log_error(2, str(e))
        p2 = {'current_1500p_edge': None, 'upgrade_threshold': 0.0243,
              'gap_to_threshold': None, 'rolling_trend': [], 'estimated_draws_to_threshold': None,
              'perm_p': 1.0, 'mcnemar_vs_pp3_4bet': {'net': 0, 'p': 1.0},
              'verdict': 'ERROR', 'recommendation': 'RERUN', 'slope_per_50_draws': 0, 'n_total': 0}

    # ── Phase 3 ──
    try:
        p3 = phase3_mk3bet(records)
    except Exception as e:
        log_error(3, str(e))
        p3 = {'mk_3bet_full_1500p': None, 'fourier_3bet_full_1500p': None,
              'mcnemar': {'b': 0, 'c': 0, 'net': 0, 'p': 1.0},
              'rolling_mcnemar_trend': [], 'four_window_mk': {}, 'four_window_fr': {},
              'phi_correlation': 0, 'phi_interpretation': 'ERROR', 'verdict': 'KEEP_MONITORING', 'notes': 'ERROR'}

    # ── Phase 4 ──
    try:
        p4 = phase4_hypothesis_scan(draws)
    except Exception as e:
        log_error(4, str(e))
        p4 = {'scan_date': datetime.now().isoformat(), 'hypotheses': [],
              'passed_count': 0, 'marginal_count': 0, 'best_candidate': None}

    # ── Phase 5 ──
    try:
        phase5_report(p2, p3, p4, draws)
    except Exception as e:
        log_error(5, str(e))

    # Save errors if any
    if ERRORS:
        with open(os.path.join(DATA_DIR, 'pl_agent_errors.json'), 'w') as f:
            json.dump(ERRORS, f, indent=2)
        print(f'\nErrors logged: {len(ERRORS)} → data/pl_agent_errors.json')

    elapsed = (datetime.now() - start_ts).total_seconds()
    print(f'\nTotal elapsed: {elapsed:.0f}s')

if __name__ == '__main__':
    main()
