#!/usr/bin/env python3
"""
POWER_LOTTO Final Research Script — Phases 1-5 (2026-04-19)

Phase 1: combo_B 1500p complete validation
Phase 2: H-PL-01 Gap Pattern 600p deep validation
Phase 3: H-PL-03 Zone Concentration 600p deep validation
Phase 4: Ensemble weak signal exploration (H-PL-01 + H-PL-02 + H-PL-03)
Phase 5: POWER_LOTTO signal space final conclusion + lessons.md

Anti-leakage: history[:idx] strict.
Perm test: MC null Binomial(1, baseline), NOT shuffle labels (L96).
seed=42. Do NOT modify deployed strategies.
"""
import sys, os, json, random, math
import numpy as np
from datetime import datetime
from collections import Counter, defaultdict
from math import comb
import sqlite3

ROOT    = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew'
TOOLS   = os.path.join(ROOT, 'tools')
API_DIR = os.path.join(ROOT, 'lottery_api')
sys.path.insert(0, ROOT)
sys.path.insert(0, API_DIR)
sys.path.insert(0, TOOLS)

np.random.seed(42)
random.seed(42)

DB_PATH       = os.path.join(ROOT, 'lottery_api/data/lottery_v2.db')
DATA_DIR      = os.path.join(ROOT, 'data')
MEM_DIR       = os.path.join(ROOT, 'memory')
BACKTEST_PATH = os.path.join(DATA_DIR, 'power_lotto_full_backtest.jsonl')

MAX_NUM       = 38
BASELINE_1BET = 0.01034
BASELINE_2BET = 0.0759
BASELINE_3BET = 0.1117
BASELINE_5BET = 0.1791

# Deployed strategy 1500p edges (from previous research)
ORTHO_1500P_EDGE = 0.0389

ERRORS = []

def log_error(phase, msg):
    ERRORS.append({'phase': phase, 'msg': msg, 'ts': datetime.now().isoformat()})
    print(f'  [ERROR] Phase {phase}: {msg}')

# ═══════════════════════════════════════════════════════════
# Data Loading
# ═══════════════════════════════════════════════════════════
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

def load_backtest():
    records = []
    with open(BACKTEST_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

# ═══════════════════════════════════════════════════════════
# Core Helpers
# ═══════════════════════════════════════════════════════════
def is_m3plus(bets, actual):
    actual_set = set(actual)
    for b in bets:
        if isinstance(b, dict):
            b = b.get('numbers', b)
        if sum(1 for n in b if n in actual_set) >= 3:
            return True
    return False

def edge_at_window(hits, baseline, w):
    if len(hits) < w:
        return None
    last = hits[-w:]
    return round(sum(last) / len(last) - baseline, 4)

def mc_perm_test(hits, baseline, n_perm=500, seed=42):
    """MC null: Binomial(1, baseline) per draw. L96 compliant."""
    rng = random.Random(seed)
    n   = len(hits)
    obs = sum(hits) / n - baseline
    ge  = sum(1 for _ in range(n_perm)
              if (sum(1 for _ in range(n) if rng.random() < baseline) / n - baseline) >= obs)
    return obs, ge / n_perm

def mcnemar_exact_p(b, c):
    n = b + c
    if n == 0: return 1.0
    lo = min(b, c)
    p  = sum(comb(n, k) * (0.5 ** n) for k in range(lo + 1))
    return min(1.0, 2 * p)

def chi2_sf(x, df):
    """Chi2 survival via Wilson-Hilferty normal approx. Accurate for df>=2."""
    if x <= 0: return 1.0
    h = 2.0 / (9.0 * df)
    z = ((x / df) ** (1.0/3.0) - (1.0 - h)) / math.sqrt(h)
    return 0.5 * math.erfc(z / math.sqrt(2.0))

# ═══════════════════════════════════════════════════════════
# Strategy implementations (copied from pl_research_phases15.py)
# ═══════════════════════════════════════════════════════════
def _gap_lag1_2bet(history):
    """H-PL-01: Lag-1 gap stability pattern."""
    if len(history) < 10:
        return [[1,2,3,4,5,6], [7,8,9,10,11,12]]
    window = min(len(history), 100)
    recent = history[-window:]
    last_seen  = {}
    gaps_by_num = {n: [] for n in range(1, MAX_NUM+1)}
    for i, d in enumerate(recent):
        for n in d['numbers'][:6]:
            if 1 <= n <= MAX_NUM:
                if n in last_seen:
                    gaps_by_num[n].append(i - last_seen[n])
                last_seen[n] = i
    scores = {}
    for n in range(1, MAX_NUM+1):
        g = gaps_by_num[n]
        if len(g) < 3:
            scores[n] = 0; continue
        mean_g = sum(g) / len(g)
        std_g  = (sum((x - mean_g)**2 for x in g) / len(g)) ** 0.5
        cv     = std_g / mean_g if mean_g > 0 else 999
        last_gap = (len(recent) - 1 - last_seen.get(n, 0)) if n in last_seen else window
        dist  = abs(last_gap - mean_g) / max(mean_g, 1)
        scores[n] = (1 / (cv + 0.1)) * (1 / (dist + 0.5))
    ranked = sorted(range(1, MAX_NUM+1), key=lambda x: -scores[x])
    return [sorted(ranked[:6]), sorted(ranked[6:12])]

def _zone_conc_2bet(history):
    """H-PL-03: Zone concentration (1-13 / 14-26 / 27-38)."""
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
    best_pattern = zone_patterns.most_common(1)[0][0] if zone_patterns else None
    zone_targets = dict(best_pattern) if best_pattern else {0: 2, 1: 2, 2: 2}
    zone_freq = {0: Counter(), 1: Counter(), 2: Counter()}
    for d in recent:
        for n in d['numbers'][:6]:
            if 1 <= n <= MAX_NUM:
                zone_freq[get_zone(n)][n] += 1
    bet1 = []
    for z, count in zone_targets.items():
        zone_nums = sorted(zone_freq[z].keys(), key=lambda x: -zone_freq[z][x])
        bet1.extend(zone_nums[:count])
    bet1 = sorted(set(bet1[:6]))
    if len(bet1) < 6:
        all_freq = Counter()
        for d in recent:
            for n in d['numbers'][:6]:
                if 1 <= n <= MAX_NUM:
                    all_freq[n] += 1
        for n in sorted(range(1, MAX_NUM+1), key=lambda x: -all_freq.get(x, 0)):
            if n not in set(bet1):
                bet1.append(n)
            if len(bet1) == 6:
                break
    bet1 = sorted(bet1[:6])
    all_freq = Counter()
    for d in recent:
        for n in d['numbers'][:6]:
            if 1 <= n <= MAX_NUM:
                all_freq[n] += 1
    bet2_pool = [n for n in range(1, MAX_NUM+1) if n not in set(bet1)]
    bet2_pool.sort(key=lambda x: -all_freq.get(x, 0))
    bet2 = sorted(bet2_pool[:6])
    return [bet1, bet2]

def _mod7_2bet(history):
    """H-PL-02: Mod7 periodicity."""
    window = min(len(history), 300)
    recent = history[-window:]
    mod7_counts = Counter()
    for d in recent:
        for n in d['numbers'][:6]:
            if 1 <= n <= MAX_NUM:
                mod7_counts[n % 7] += 1
    hot_mods = sorted(range(7), key=lambda m: -mod7_counts[m])[:3]
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

# ═══════════════════════════════════════════════════════════
# PHASE 1 — combo_B 1500p Complete Validation
# ═══════════════════════════════════════════════════════════
def phase1_combo_b(all_draws, bt_records):
    print('\n' + '='*60)
    print('PHASE 1: combo_B 1500p Validation')
    print('='*60)

    from tools.power_fourier_rhythm import fourier_rhythm_predict
    from tools.power_midfreq_fourier import midfreq_fourier_markov_3bet
    from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet

    BASELINE = BASELINE_5BET  # 5-bet M3+ baseline
    draw_to_idx = {d['draw']: i for i, d in enumerate(all_draws)}

    n_bt = len(bt_records)
    start_bt = max(0, n_bt - 1500)
    test_bt  = bt_records[start_bt:]
    n_test   = len(test_bt)
    print(f'  1500p window: {test_bt[0]["draw"]} ~ {test_bt[-1]["draw"]} (n={n_test})')

    # combo_B = fourier bets[0,1] + mk bets[0,1,2]
    print('  Pre-computing combo_B bets...')
    combo_hits  = []
    ortho_hits  = []
    errors = 0

    for i, rec in enumerate(test_bt):
        idx = draw_to_idx.get(rec['draw'])
        if idx is None or idx < 50:
            combo_hits.append(False)
            ortho_hits.append(False)
            errors += 1
            continue

        hist   = all_draws[:idx]
        actual = rec['actual']

        try:
            fr_bets = fourier_rhythm_predict(hist, n_bets=3, window=500)
            mk_bets = midfreq_fourier_markov_3bet(hist)
            combo_b = fr_bets[:2] + mk_bets[:3]  # 5 bets
            combo_hits.append(is_m3plus(combo_b, actual))
        except Exception as e:
            log_error(1, f'combo draw {rec["draw"]}: {e}')
            combo_hits.append(False)
            errors += 1

        # Orthogonal from backtest (already stored)
        ortho_hits.append(bool(rec['strategies'].get('orthogonal_5bet', {}).get('is_m3plus', False)))

        if (i + 1) % 500 == 0:
            print(f'    {i+1}/{n_test}...', flush=True)

    n = len(combo_hits)
    print(f'  Valid: {n - errors}, errors: {errors}')

    # B. Multi-window edges
    w150  = edge_at_window(combo_hits, BASELINE, 150)
    w300  = edge_at_window(combo_hits, BASELINE, 300)
    w500  = edge_at_window(combo_hits, BASELINE, 500)
    w1000 = edge_at_window(combo_hits, BASELINE, 1000)
    w1500 = edge_at_window(combo_hits, BASELINE, 1500)
    three_win = (w150 is not None and w150 > 0 and
                 w500 is not None and w500 > 0 and
                 w1500 is not None and w1500 > 0)

    print(f'  Windows: 150={w150}  300={w300}  500={w500}  1000={w1000}  1500={w1500}')
    print(f'  Three-window pass: {three_win}')

    # C. Permutation test (500 shuffles, MC null)
    obs_e, perm_p = mc_perm_test(combo_hits, BASELINE, n_perm=500, seed=42)
    print(f'  Perm test: obs={obs_e:.4f}, perm_p={perm_p:.4f}')

    # D. McNemar vs orthogonal_5bet (1500p)
    b = sum(1 for i in range(n) if combo_hits[i] and not ortho_hits[i])
    c = sum(1 for i in range(n) if not combo_hits[i] and ortho_hits[i])
    mc_net = b - c
    mc_p   = mcnemar_exact_p(b, c)
    print(f'  McNemar vs ortho5: b={b}, c={c}, net={mc_net}, p={mc_p:.4f}')

    # Beats orthogonal?
    ortho_1500p_edge = edge_at_window(ortho_hits, BASELINE, 1500)
    beats_ortho = (w1500 is not None and ortho_1500p_edge is not None and
                   w1500 > ortho_1500p_edge)
    print(f'  ortho_1500p={ortho_1500p_edge}, combo_B_1500p={w1500}, beats_ortho={beats_ortho}')

    # E. Decision
    cond1 = three_win
    cond2 = perm_p < 0.05
    cond3 = mc_p < 0.05 and mc_net > 0
    cond4 = beats_ortho

    if all([cond1, cond2, cond3, cond4]):
        verdict = 'PROMOTE'
    elif (w1500 is not None and w1500 < 0) or (not three_win and perm_p > 0.20):
        verdict = 'RETIRE'
    else:
        verdict = 'CONTINUE_WATCH'

    notes = (f'combo_B=fourier[0:2]+mk[0:3]. '
             f'1500p edge={w1500}, ortho_5bet_1500p={ortho_1500p_edge}. '
             f'three_win={three_win}, perm_p={perm_p:.4f}, McNemar net={mc_net} p={mc_p:.4f}. '
             f'Verdict={verdict}.')
    print(f'  Verdict: {verdict}')

    result = {
        'windows': {'w150': w150, 'w300': w300, 'w500': w500, 'w1000': w1000, 'w1500': w1500},
        'three_window_pass': three_win,
        'perm_p': round(perm_p, 4),
        'mcnemar': {'b': b, 'c': c, 'net': mc_net, 'p': round(mc_p, 4)},
        'ortho_5bet_1500p_edge': ortho_1500p_edge,
        'beats_orthogonal': beats_ortho,
        'promotion_conditions_met': [cond1, cond2, cond3, cond4],
        'verdict': verdict,
        'notes': notes,
        'n_tested': n_test,
        'errors': errors,
    }

    out = os.path.join(DATA_DIR, 'combo_b_1500p_validation.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f'  Saved: {out}')
    return result

# ═══════════════════════════════════════════════════════════
# PHASE 2 — H-PL-01 Gap Pattern 600p Deep Validation
# ═══════════════════════════════════════════════════════════
def phase2_hpl01(all_draws, bt_records):
    print('\n' + '='*60)
    print('PHASE 2: H-PL-01 Gap Pattern 600p Deep Validation')
    print('='*60)

    BASELINE  = BASELINE_2BET
    draw_to_idx = {d['draw']: i for i, d in enumerate(all_draws)}
    n_bt = len(bt_records)
    start_bt = max(0, n_bt - 600)
    test_bt  = bt_records[start_bt:]
    n_test   = len(test_bt)
    print(f'  600p window: {test_bt[0]["draw"]} ~ {test_bt[-1]["draw"]} (n={n_test})')

    # A. Structural check — gap distribution across full history
    # Compute gap between consecutive sorted numbers in each draw
    all_gap_dists = []
    for d in all_draws:
        nums = sorted(n for n in d['numbers'][:6] if 1 <= n <= MAX_NUM)
        if len(nums) >= 2:
            gaps = [nums[i+1] - nums[i] for i in range(len(nums)-1)]
            all_gap_dists.extend(gaps)

    # Theoretical distribution: gap sizes in 38C6 random draws
    # E[gap] ~ (38-1)/(6-1) = 7.4; distribution is not uniform
    gap_counter = Counter(all_gap_dists)
    total_gaps = sum(gap_counter.values())
    max_gap = max(gap_counter.keys()) if gap_counter else 32

    # Theoretical expected frequency of each gap size in 38C6:
    # P(gap = k) = (38-k-4) * C-combinatorial...
    # Simplified: use empirical as reference, chi2 vs uniform
    n_bins = min(max_gap, 20)
    observed = [gap_counter.get(k, 0) for k in range(1, n_bins+1)]
    total_obs = sum(observed)
    if total_obs > 0:
        expected_uniform = [total_obs / n_bins] * n_bins
        chi2_struct = sum((observed[i] - expected_uniform[i])**2 / expected_uniform[i]
                          for i in range(n_bins) if expected_uniform[i] > 0)
        chi2_struct_p = chi2_sf(chi2_struct, n_bins - 1)
    else:
        chi2_struct, chi2_struct_p = 0, 1.0

    structural_bias = chi2_struct_p < 0.05
    print(f'  Gap structural chi2={chi2_struct:.2f}, p={chi2_struct_p:.4f}, structural_bias={structural_bias}')

    # B. 600p backtest
    hits = []
    errors = 0
    for rec in test_bt:
        idx = draw_to_idx.get(rec['draw'])
        if idx is None or idx < 10:
            hits.append(False); errors += 1; continue
        hist   = all_draws[:idx]
        actual = rec['actual']
        try:
            bets = _gap_lag1_2bet(hist)
            hits.append(is_m3plus(bets, actual))
        except Exception as e:
            log_error(2, f"draw {rec['draw']}: {e}")
            hits.append(False); errors += 1

    w150 = edge_at_window(hits, BASELINE, 150)
    w300 = edge_at_window(hits, BASELINE, 300)
    w500 = edge_at_window(hits, BASELINE, 500)
    w600 = edge_at_window(hits, BASELINE, 600)
    obs_e, perm_p = mc_perm_test(hits, BASELINE, n_perm=500, seed=42)

    three_win = (w150 is not None and w150 > 0 and
                 w500 is not None and w500 > 0 and
                 w600 is not None and w600 > 0)
    print(f'  Windows: 150={w150}  300={w300}  500={w500}  600={w600}')
    print(f'  perm_p={perm_p:.4f}, three_win={three_win}')

    # Note: structural_bias in gap distribution is expected (gaps aren't uniform by design)
    # Key question: is the strategy exploiting temporal bias (autocorrelation)?
    # We run Ljung-Box on gap means per draw
    gap_means = []
    for d in all_draws:
        nums = sorted(n for n in d['numbers'][:6] if 1 <= n <= MAX_NUM)
        if len(nums) >= 2:
            gaps = [nums[i+1] - nums[i] for i in range(len(nums)-1)]
            gap_means.append(sum(gaps) / len(gaps))
        else:
            gap_means.append(0)

    n_gm = len(gap_means)
    mu_gm = sum(gap_means) / n_gm
    var_gm = sum((x - mu_gm)**2 for x in gap_means) / n_gm

    def acf_val(lag):
        if var_gm < 1e-10: return 0.0
        return sum((gap_means[t] - mu_gm) * (gap_means[t+lag] - mu_gm)
                   for t in range(n_gm - lag)) / ((n_gm - lag) * var_gm)

    acf_vals = [acf_val(k) for k in range(1, 11)]
    Q_lb = n_gm * (n_gm + 2) * sum(acf_vals[k]**2 / (n_gm - k - 1) for k in range(10))
    ljung_p = chi2_sf(Q_lb, 10)
    autocorr_present = ljung_p < 0.10
    print(f'  Ljung-Box Q={Q_lb:.2f}, p={ljung_p:.4f}, autocorr={autocorr_present}')

    # Verdict
    if three_win and perm_p < 0.05:
        verdict = 'PASS'
    elif structural_bias and chi2_struct_p < 0.001 and perm_p > 0.20:
        verdict = 'STRUCTURAL_BIAS'
    elif w600 is not None and w600 < 0:
        verdict = 'FAIL'
    else:
        verdict = 'FAIL'

    close_signal_space = perm_p > 0.30 and (w600 is None or w600 < 0.005)
    print(f'  Verdict: {verdict}, close_signal_space={close_signal_space}')

    result = {
        'w150': w150, 'w300': w300, 'w500': w500, 'w600': w600,
        'perm_p': round(perm_p, 4),
        'obs_edge_600p': round(obs_e, 4),
        'structural_bias': structural_bias,
        'chi2_p': round(chi2_struct_p, 6),
        'chi2_stat': round(chi2_struct, 4),
        'ljung_box_q': round(Q_lb, 4),
        'ljung_box_p': round(ljung_p, 6),
        'autocorrelation_present': autocorr_present,
        'three_window_pass': three_win,
        'verdict': verdict,
        'close_signal_space': close_signal_space,
        'n_tested': n_test,
        'errors': errors,
    }

    out = os.path.join(DATA_DIR, 'h_pl_01_deep_validation.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f'  Saved: {out}')
    return result

# ═══════════════════════════════════════════════════════════
# PHASE 3 — H-PL-03 Zone Concentration 600p Deep Validation
# ═══════════════════════════════════════════════════════════
def phase3_hpl03(all_draws, bt_records):
    print('\n' + '='*60)
    print('PHASE 3: H-PL-03 Zone Concentration 600p Deep Validation')
    print('='*60)

    BASELINE = BASELINE_2BET
    draw_to_idx = {d['draw']: i for i, d in enumerate(all_draws)}

    # A. Zone autocorrelation analysis (full history)
    def get_zone(n):
        if n <= 13: return 0
        elif n <= 26: return 1
        return 2

    # Encode zone combo as (z0_count, z1_count, z2_count) tuple
    zone_combos = []
    for d in all_draws:
        nums = [n for n in d['numbers'][:6] if 1 <= n <= MAX_NUM]
        zc = Counter(get_zone(n) for n in nums)
        zone_combos.append((zc.get(0, 0), zc.get(1, 0), zc.get(2, 0)))

    # Encode as single number for autocorrelation: dominant zone (0/1/2)
    zone_dom = [max(range(3), key=lambda z: zc[z]) for zc in zone_combos]
    # Also use sum-weighted encoding for continuous-ish ACF
    zone_numeric = [zc[0]*0 + zc[1]*1 + zc[2]*2 for zc in zone_combos]

    n_z = len(zone_numeric)
    mu_z = sum(zone_numeric) / n_z
    var_z = sum((x - mu_z)**2 for x in zone_numeric) / n_z

    def acf_z(lag):
        if var_z < 1e-10: return 0.0
        return sum((zone_numeric[t] - mu_z) * (zone_numeric[t+lag] - mu_z)
                   for t in range(n_z - lag)) / ((n_z - lag) * var_z)

    acf_vals = [acf_z(k) for k in range(1, 11)]
    Q_lb = n_z * (n_z + 2) * sum(acf_vals[k]**2 / (n_z - k - 1) for k in range(10))
    ljung_p = chi2_sf(Q_lb, 10)
    autocorr_present = ljung_p < 0.10
    print(f'  Zone ACF[1-5]: {[round(a, 4) for a in acf_vals[:5]]}')
    print(f'  Ljung-Box Q={Q_lb:.2f}, p={ljung_p:.4f}, autocorr={autocorr_present}')

    # Top 5 zone combos and transition matrix
    all_n = len(all_draws)
    combo_counter = Counter(zone_combos)
    top5 = combo_counter.most_common(5)
    print(f'  Top 5 zone combos: {top5}')

    # Transition matrix: combo[t] → combo[t+1]
    transition = defaultdict(Counter)
    for t in range(all_n - 1):
        transition[zone_combos[t]][zone_combos[t+1]] += 1

    top5_transitions = []
    for combo, cnt in top5:
        trans = transition[combo]
        total_trans = sum(trans.values())
        if total_trans > 0:
            top_next = trans.most_common(3)
            top5_transitions.append({
                'from': list(combo),
                'count': cnt,
                'to_top3': [[list(k), v/total_trans] for k, v in top_next]
            })

    # B. 600p backtest
    n_bt = len(bt_records)
    start_bt = max(0, n_bt - 600)
    test_bt  = bt_records[start_bt:]
    n_test   = len(test_bt)
    print(f'  600p window: {test_bt[0]["draw"]} ~ {test_bt[-1]["draw"]} (n={n_test})')

    hits           = []
    signal_flags   = []  # whether zone signal was "active" (autocorr-based)
    errors = 0

    for rec in test_bt:
        idx = draw_to_idx.get(rec['draw'])
        if idx is None or idx < 10:
            hits.append(False); signal_flags.append(False); errors += 1; continue
        hist   = all_draws[:idx]
        actual = rec['actual']
        try:
            bets = _zone_conc_2bet(hist)
            hits.append(is_m3plus(bets, actual))
            # Signal active: last draw's zone combo matches top3 transition patterns
            last_zc = zone_combos[idx - 1]
            trans   = transition.get(last_zc, Counter())
            total   = sum(trans.values())
            top_prob = trans.most_common(1)[0][1] / total if trans and total > 0 else 0
            signal_flags.append(top_prob >= 0.35)  # confident prediction
        except Exception as e:
            log_error(3, f"draw {rec['draw']}: {e}")
            hits.append(False); signal_flags.append(False); errors += 1

    w150 = edge_at_window(hits, BASELINE, 150)
    w300 = edge_at_window(hits, BASELINE, 300)
    w500 = edge_at_window(hits, BASELINE, 500)
    w600 = edge_at_window(hits, BASELINE, 600)
    obs_e, perm_p = mc_perm_test(hits, BASELINE, n_perm=500, seed=42)

    three_win = (w150 is not None and w150 > 0 and
                 w500 is not None and w500 > 0 and
                 w600 is not None and w600 > 0)
    print(f'  Windows: 150={w150}  300={w300}  500={w500}  600={w600}')
    print(f'  perm_p={perm_p:.4f}, three_win={three_win}')

    # C. Conditional vs unconditional edge (L101 structural dilution check)
    n = len(hits)
    signal_hits    = [hits[i] for i in range(n) if signal_flags[i]]
    no_signal_hits = [hits[i] for i in range(n) if not signal_flags[i]]

    signal_coverage    = sum(signal_flags) / n if n > 0 else 0
    conditional_edge   = (sum(signal_hits) / len(signal_hits) - BASELINE) if signal_hits else None
    unconditional_edge = (sum(hits) / n - BASELINE) if n > 0 else None
    print(f'  Signal coverage={signal_coverage:.3f}, conditional_edge={conditional_edge}, unconditional_edge={unconditional_edge}')

    # Verdict
    if three_win and perm_p < 0.05:
        verdict = 'PASS'
    elif three_win and perm_p < 0.10:
        verdict = 'MARGINAL'
    elif w600 is not None and w600 < 0:
        verdict = 'FAIL'
    else:
        verdict = 'FAIL'

    close_signal_space = perm_p > 0.30 and (w600 is None or w600 < 0.005)
    print(f'  Verdict: {verdict}, close_signal_space={close_signal_space}')

    result = {
        'zone_autocorr_ljung_p': round(ljung_p, 6),
        'autocorrelation_present': autocorr_present,
        'top5_zone_transitions': top5_transitions,
        'w150': w150, 'w300': w300, 'w500': w500, 'w600': w600,
        'perm_p': round(perm_p, 4),
        'obs_edge_600p': round(obs_e, 4),
        'three_window_pass': three_win,
        'signal_coverage': round(signal_coverage, 4),
        'conditional_edge': round(conditional_edge, 4) if conditional_edge is not None else None,
        'unconditional_edge': round(unconditional_edge, 4) if unconditional_edge is not None else None,
        'verdict': verdict,
        'close_signal_space': close_signal_space,
        'n_tested': n_test,
        'errors': errors,
    }

    out = os.path.join(DATA_DIR, 'h_pl_03_deep_validation.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f'  Saved: {out}')
    return result

# ═══════════════════════════════════════════════════════════
# PHASE 4 — Ensemble Weak Signal Exploration
# ═══════════════════════════════════════════════════════════
def phase4_ensemble(all_draws, bt_records):
    print('\n' + '='*60)
    print('PHASE 4: Ensemble Weak Signal Exploration')
    print('='*60)

    from tools.power_fourier_rhythm import fourier_rhythm_predict

    BASELINE = BASELINE_2BET

    draw_to_idx = {d['draw']: i for i, d in enumerate(all_draws)}
    n_bt = len(bt_records)
    start_bt = max(0, n_bt - 600)
    test_bt  = bt_records[start_bt:]
    n_test   = len(test_bt)
    print(f'  600p window: {test_bt[0]["draw"]} ~ {test_bt[-1]["draw"]} (n={n_test})')

    # A. Compute individual signal triggers per period
    print('  Computing individual signals...')
    h01_hits  = []
    h02_hits  = []
    h03_hits  = []
    h01_trig  = []  # signal trigger (always True for baseline strategies)
    h02_trig  = []
    h03_trig  = []
    actuals   = []
    errors    = 0

    for rec in test_bt:
        idx = draw_to_idx.get(rec['draw'])
        if idx is None or idx < 10:
            for lst in [h01_hits, h02_hits, h03_hits, h01_trig, h02_trig, h03_trig, actuals]:
                lst.append(None)
            errors += 1
            continue

        hist   = all_draws[:idx]
        actual = rec['actual']
        actuals.append(actual)

        try:
            b01 = _gap_lag1_2bet(hist)
            h01_hits.append(is_m3plus(b01, actual))
            h01_trig.append(True)  # gap signal always "triggered" (no gate in original strategy)
        except Exception as e:
            h01_hits.append(False); h01_trig.append(False)
            log_error(4, f'h01 draw {rec["draw"]}: {e}')

        try:
            b02 = _mod7_2bet(hist)
            h02_hits.append(is_m3plus(b02, actual))
            # Mod7 trigger: at least one mod7 class is >20% above average
            window = min(len(hist), 300)
            recent = hist[-window:]
            mod7c  = Counter()
            for d in recent:
                for n in d['numbers'][:6]:
                    if 1 <= n <= MAX_NUM:
                        mod7c[n % 7] += 1
            avg    = sum(mod7c.values()) / 7 if mod7c else 0
            h02_trig.append(any(v > avg * 1.20 for v in mod7c.values()))
        except Exception as e:
            h02_hits.append(False); h02_trig.append(False)
            log_error(4, f'h02 draw {rec["draw"]}: {e}')

        try:
            b03 = _zone_conc_2bet(hist)
            h03_hits.append(is_m3plus(b03, actual))
            # Zone trigger: top zone combo has >=35% probability from transition
            def get_zone(n): return 0 if n <= 13 else (1 if n <= 26 else 2)
            # Compute transition on hist
            zone_seq = []
            for d in hist[-50:]:  # use last 50 for trigger
                nums = [n for n in d['numbers'][:6] if 1 <= n <= MAX_NUM]
                zc = Counter(get_zone(n) for n in nums)
                zone_seq.append((zc.get(0,0), zc.get(1,0), zc.get(2,0)))
            trans_local = defaultdict(Counter)
            for t in range(len(zone_seq)-1):
                trans_local[zone_seq[t]][zone_seq[t+1]] += 1
            last_zc = zone_seq[-1] if zone_seq else (0,0,0)
            t_cnts  = trans_local.get(last_zc, Counter())
            total   = sum(t_cnts.values())
            top_p   = t_cnts.most_common(1)[0][1] / total if t_cnts and total > 0 else 0
            h03_trig.append(top_p >= 0.35)
        except Exception as e:
            h03_hits.append(False); h03_trig.append(False)
            log_error(4, f'h03 draw {rec["draw"]}: {e}')

    # Filter out None entries
    valid_idx = [i for i in range(n_test) if
                 h01_hits[i] is not None and h02_hits[i] is not None and h03_hits[i] is not None]

    h01_hits_v  = [h01_hits[i]  for i in valid_idx]
    h02_hits_v  = [h02_hits[i]  for i in valid_idx]
    h03_hits_v  = [h03_hits[i]  for i in valid_idx]
    h01_trig_v  = [h01_trig[i]  for i in valid_idx]
    h02_trig_v  = [h02_trig[i]  for i in valid_idx]
    h03_trig_v  = [h03_trig[i]  for i in valid_idx]
    n = len(valid_idx)

    # Signal trigger rates
    r01 = sum(h01_trig_v) / n
    r02 = sum(h02_trig_v) / n
    r03 = sum(h03_trig_v) / n
    and_trig = [1 if h01_trig_v[i] and h02_trig_v[i] and h03_trig_v[i] else 0
                for i in range(n)]
    and_trig_2 = [1 if (int(h01_trig_v[i]) + int(h02_trig_v[i]) + int(h03_trig_v[i])) >= 2 else 0
                  for i in range(n)]
    and_rate   = sum(and_trig) / n
    and2_rate  = sum(and_trig_2) / n

    print(f'  Trigger rates: H01={r01:.3f}, H02={r02:.3f}, H03={r03:.3f}')
    print(f'  AND-3 trigger: {and_rate:.3f}, AND-2+ trigger: {and2_rate:.3f}')

    # B. Composite gate test if 2+ trigger rate is 5-30%
    if and2_rate < 0.05:
        print(f'  AND-2+ rate {and2_rate:.3f} < 5% → NO_OP (L67)')
        gate_result = None
        no_op = True
    elif and2_rate > 0.30:
        print(f'  AND-2+ rate {and2_rate:.3f} > 30% — running gate test...')
        no_op = False
        gate_result = 'HIGH_COVERAGE'
    else:
        print(f'  AND-2+ rate {and2_rate:.3f} in 5-30% → running composite gate test...')
        no_op = False
        gate_result = None

    conditional_edge = None
    skip_rate        = None
    gate_perm_p      = None
    gate_verdict     = 'NO_OP' if no_op else None

    if not no_op:
        # Gate strategy: 2+ signals firing → bet 2 fourier bets, else skip
        gate_hits     = []
        gate_actuals  = []
        skip_count    = 0

        for i, rec_idx in enumerate(valid_idx):
            rec  = test_bt[rec_idx]
            idx  = draw_to_idx.get(rec['draw'])
            if idx is None:
                continue
            actual = rec['actual']
            if not and_trig_2[i]:
                skip_count += 1
                continue  # gate not fired → skip period
            # Gate fired: bet 2 fourier bets
            hist = all_draws[:idx]
            try:
                fr_bets = fourier_rhythm_predict(hist, n_bets=2, window=500)
                gate_hits.append(is_m3plus(fr_bets, actual))
                gate_actuals.append(actual)
            except Exception as e:
                log_error(4, f'gate draw {rec["draw"]}: {e}')
                gate_hits.append(False)

        n_gate = len(gate_hits)
        skip_rate = skip_count / n if n > 0 else 0
        print(f'  Gate periods: {n_gate}, skip: {skip_count} ({skip_rate:.3f})')

        if n_gate >= 30:
            gate_hr = sum(gate_hits) / n_gate
            conditional_edge = round(gate_hr - BASELINE, 4)
            unconditional_edge_check = round(sum(h01_hits_v) / n - BASELINE, 4)
            print(f'  Conditional edge: {conditional_edge}  Unconditional: {unconditional_edge_check}')
            obs_gate, gate_perm_p = mc_perm_test(gate_hits, BASELINE, n_perm=300, seed=42)
            print(f'  Gate perm_p={gate_perm_p:.4f}')

            if conditional_edge > 0 and gate_perm_p < 0.05:
                gate_verdict = 'PASS'
            elif conditional_edge > 0 and gate_perm_p < 0.10:
                gate_verdict = 'MARGINAL'
            elif conditional_edge is not None and conditional_edge < 0:
                gate_verdict = 'FAIL'
            else:
                gate_verdict = 'FAIL'
        else:
            gate_verdict = 'INSUFFICIENT_SAMPLES'
            conditional_edge = sum(gate_hits) / n_gate - BASELINE if n_gate > 0 else None

        print(f'  Gate verdict: {gate_verdict}')

    result = {
        'signal_trigger_rates': {
            'h_pl_01': round(r01, 4),
            'h_pl_02': round(r02, 4),
            'h_pl_03': round(r03, 4),
        },
        'and_trigger_rate': round(and_rate, 4),
        'and_2plus_trigger_rate': round(and2_rate, 4),
        'no_op_verdict': no_op,
        'conditional_edge': conditional_edge,
        'skip_rate': round(skip_rate, 4) if skip_rate is not None else None,
        'perm_p': round(gate_perm_p, 4) if gate_perm_p is not None else None,
        'verdict': gate_verdict if gate_verdict else 'FAIL',
        'n_tested': n,
        'errors': errors,
    }

    out = os.path.join(DATA_DIR, 'ensemble_weak_signal.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f'  Saved: {out}')
    return result

# ═══════════════════════════════════════════════════════════
# PHASE 5 — Signal Space Final Conclusion + lessons.md
# ═══════════════════════════════════════════════════════════
def phase5_final(p1, p2, p3, p4, all_draws):
    print('\n' + '='*60)
    print('PHASE 5: Signal Space Final Conclusion')
    print('='*60)

    now_str      = '2026-04-19'
    latest_draw  = all_draws[-1]['draw']
    lessons_path = os.path.join(MEM_DIR, 'lessons.md')

    # Current verdict mapping
    verdicts = {
        'combo_B':    p1['verdict'],
        'H-PL-01':   p2['verdict'],
        'H-PL-03':   p3['verdict'],
        'ensemble':  p4['verdict'],
    }

    # Determine signal space verdict
    n_pass  = sum(1 for v in verdicts.values() if v == 'PASS' or v == 'PROMOTE')
    n_watch = sum(1 for v in verdicts.values() if v in ('CONTINUE_WATCH', 'MARGINAL'))

    if n_pass >= 1:
        space_verdict = 'ACTIVE'
        exhaustion_conf = 'LOW'
    elif n_watch >= 2:
        space_verdict = 'MARGINAL_REMAINING'
        exhaustion_conf = 'MEDIUM'
    else:
        space_verdict = 'EXHAUSTED'
        exhaustion_conf = 'HIGH'

    # Remaining open lines
    open_lines = []
    if verdicts['combo_B'] == 'CONTINUE_WATCH':
        open_lines.append({'line': 'combo_B', 'note': f'1500p_edge={p1["windows"]["w1500"]}, perm_p={p1["perm_p"]}. Re-test after 300 more draws.'})
    if verdicts['H-PL-01'] not in ('FAIL', 'STRUCTURAL_BIAS', 'PASS'):
        open_lines.append({'line': 'H-PL-01', 'note': 'Unexpected verdict — manual check needed'})
    if verdicts['H-PL-03'] == 'MARGINAL':
        open_lines.append({'line': 'H-PL-03', 'note': f'600p edge={p3["w600"]}, perm_p={p3["perm_p"]}. Re-test with extended window.'})

    print(f'  Space verdict: {space_verdict} (confidence={exhaustion_conf})')
    print(f'  Open lines: {len(open_lines)}')

    # Action items
    action_items = []

    # combo_B
    if verdicts['combo_B'] == 'PROMOTE':
        action_items.append({'priority': 'HIGH', 'action': 'PENDING HUMAN REVIEW: combo_B PROMOTE. All 4 conditions met.'})
    elif verdicts['combo_B'] == 'CONTINUE_WATCH':
        action_items.append({'priority': 'MED', 'action': f'combo_B CONTINUE_WATCH: 1500p={p1["windows"]["w1500"]}, perm_p={p1["perm_p"]}. Re-test in next cycle.'})
    elif verdicts['combo_B'] == 'RETIRE':
        action_items.append({'priority': 'LOW', 'action': 'combo_B RETIRE: 1500p edge negative. Close mk_combo research line.'})

    # H-PL-01
    if verdicts['H-PL-01'] == 'FAIL':
        action_items.append({'priority': 'LOW', 'action': 'H-PL-01 Gap Pattern FAIL. Close hypothesis.'})
    elif verdicts['H-PL-01'] == 'STRUCTURAL_BIAS':
        action_items.append({'priority': 'LOW', 'action': 'H-PL-01 STRUCTURAL_BIAS. Gap structure ≠ temporal signal. Close.'})

    # H-PL-03
    if verdicts['H-PL-03'] == 'FAIL':
        action_items.append({'priority': 'LOW', 'action': 'H-PL-03 Zone Concentration FAIL. Close hypothesis.'})
    elif verdicts['H-PL-03'] == 'MARGINAL':
        action_items.append({'priority': 'LOW', 'action': f'H-PL-03 MARGINAL: 600p={p3["w600"]}, perm_p={p3["perm_p"]}. Signal too weak — close unless autocorr appears.'})

    # Ensemble
    if verdicts['ensemble'] == 'FAIL' or p4['no_op_verdict']:
        action_items.append({'priority': 'LOW', 'action': 'Ensemble weak signal: NO-OP or FAIL. Composite gate provides no additive value.'})

    # Maintenance mode
    maintenance_mode = space_verdict == 'EXHAUSTED'
    if maintenance_mode:
        action_items.append({'priority': 'HIGH', 'action': '威力彩進入維護模式: 停止新假設掃描，僅監控現役策略 30p/100p 窗口。'})

    # lessons.md updates
    with open(lessons_path, 'r', encoding='utf-8') as f:
        content = f.read()

    import re
    existing_ids = [int(m) for m in re.findall(r'\*\*L(\d+)', content)]
    next_id = max(existing_ids) + 1 if existing_ids else 111

    lesson_entries = []
    new_lessons_written = []

    # L111 — H-PL-01
    if verdicts['H-PL-01'] in ('FAIL', 'STRUCTURAL_BIAS'):
        lid = next_id
        bias_note = f'(chi2_p={p2["chi2_p"]:.4f}, structural_bias={p2["structural_bias"]})' if p2['structural_bias'] else ''
        lesson_entries.append(f"""**L{lid} — H-PL-01 Gap Pattern: 威力彩 Lag-1 間距信號無效** ({now_str})
- 600p edge={p2["w600"]}, perm_p={p2["perm_p"]}, three_window_pass={p2["three_window_pass"]}
- Ljung-Box p={p2["ljung_box_p"]:.4f} → 間距序列無自相關
- structural_bias={p2["structural_bias"]} {bias_note}
- 結論：號碼間距穩定性無法預測下期選號。結案。""")
        new_lessons_written.append(f'L{lid}')
        next_id += 1

    # L112 — H-PL-03
    if verdicts['H-PL-03'] in ('FAIL', 'MARGINAL'):
        lid = next_id
        lesson_entries.append(f"""**L{lid} — H-PL-03 Zone Concentration: 威力彩三區分布信號{'無效' if verdicts['H-PL-03'] == 'FAIL' else '邊際（Close）'}** ({now_str})
- 600p edge={p3["w600"]}, perm_p={p3["perm_p"]}, three_window_pass={p3["three_window_pass"]}
- Zone autocorr Ljung-Box p={p3["zone_autocorr_ljung_p"]:.4f} → {'有' if p3['autocorrelation_present'] else '無'}時序結構
- signal_coverage={p3["signal_coverage"]:.3f}, conditional_edge={p3["conditional_edge"]}
- 結論：三區分布模式{'邊際且覆蓋率不足，關閉研究線' if verdicts['H-PL-03'] == 'MARGINAL' else '無時序可利用信號'}。結案。""")
        new_lessons_written.append(f'L{lid}')
        next_id += 1

    # L_combo_B (if RETIRE)
    if verdicts['combo_B'] == 'RETIRE':
        lid = next_id
        lesson_entries.append(f"""**L{lid} — mk_combo_B RETIRE: fourier×2+mk×3 組合無升格依據** ({now_str})
- 1500p edge={p1["windows"]["w1500"]}, perm_p={p1["perm_p"]}
- three_window_pass={p1["three_window_pass"]}, McNemar net={p1["mcnemar"]["net"]} p={p1["mcnemar"]["p"]}
- 結論：mk_3bet 加入 fourier 組合未能超越獨立的 orthogonal_5bet。結案。""")
        new_lessons_written.append(f'L{lid}')
        next_id += 1

    # L_space_exhausted — if EXHAUSTED
    if space_verdict == 'EXHAUSTED':
        lid = next_id
        lesson_entries.append(f"""**L{lid} — 威力彩信號空間宣告窮盡** ({now_str})
- 測試假設：H9(REJECT), H-PL-01(FAIL), H-PL-02(FAIL), H-PL-03(FAIL), H-PL-04(FAIL), H-PL-05(FAIL), PP3-Z3Gap(CLOSED)
- combo_B verdict={verdicts['combo_B']}（{'未升格' if verdicts['combo_B'] != 'PROMOTE' else 'PROMOTE待人工確認'}）
- Ensemble weak signal: {verdicts['ensemble']}
- 類比 BIG_LOTTO L91：已部署 3 策略（fourier_3bet / pp3_4bet / orthogonal_5bet）持續穩定運行
- 維護模式啟動：停止新假設掃描，僅執行 30p/100p 監控與週期性 drift check
- 重新激活條件：若任一現役策略 1500p edge 下降 > 1.5% 或新資料顯示分布轉移""")
        new_lessons_written.append(f'L{lid}')
        next_id += 1

    if lesson_entries:
        with open(lessons_path, 'a', encoding='utf-8') as lf:
            lf.write('\n\n')
            for entry in lesson_entries:
                lf.write(entry + '\n\n')
        print(f'  Updated lessons.md: {new_lessons_written}')
    else:
        print('  No new lessons required.')

    # Final report
    report = {
        'assessment_date': now_str,
        'latest_draw': latest_draw,
        'tested_hypotheses': [
            {'id': 'H9',         'verdict': 'REJECTED',              'lesson': 'L93'},
            {'id': 'H-PL-01',    'verdict': verdicts['H-PL-01'],     'lesson': new_lessons_written[0] if new_lessons_written else 'L111'},
            {'id': 'H-PL-02',    'verdict': 'FAIL',                  'lesson': 'L110'},
            {'id': 'H-PL-03',    'verdict': verdicts['H-PL-03'],     'lesson': new_lessons_written[1] if len(new_lessons_written) > 1 else 'L112'},
            {'id': 'H-PL-04',    'verdict': 'FAIL',                  'lesson': 'L109'},
            {'id': 'H-PL-05',    'verdict': 'FAIL',                  'lesson': 'L108 (scan)'},
            {'id': 'PP3-Z3Gap',  'verdict': 'CLOSED',                'lesson': 'L108'},
            {'id': 'mk_combo_B', 'verdict': verdicts['combo_B'],
             'lesson': new_lessons_written[-1] if verdicts['combo_B'] == 'RETIRE' else 'pending'},
        ],
        'deployed_strategies': [
            {'name': 'fourier_rhythm_3bet',  '1500p_edge': '+2.56%', 'status': 'STABLE'},
            {'name': 'pp3_freqort_4bet',     '1500p_edge': '+3.27%', 'status': 'STABLE'},
            {'name': 'orthogonal_5bet',      '1500p_edge': '+3.89%', 'status': 'STABLE'},
        ],
        'combo_b_result': {
            'verdict': verdicts['combo_B'],
            'windows': p1['windows'],
            'perm_p': p1['perm_p'],
            'mcnemar_net': p1['mcnemar']['net'],
            'mcnemar_p': p1['mcnemar']['p'],
            'beats_orthogonal': p1['beats_orthogonal'],
        },
        'signal_space_verdict': space_verdict,
        'exhaustion_confidence': exhaustion_conf,
        'remaining_open_lines': open_lines,
        'maintenance_mode_recommendation': maintenance_mode,
        'new_lessons': new_lessons_written,
        'action_items': action_items,
    }

    out = os.path.join(DATA_DIR, 'power_lotto_signal_space_final.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f'  Saved: {out}')

    print('\n' + '='*60)
    print('FINAL SUMMARY')
    print('='*60)
    print(f'  Signal Space: {space_verdict} (confidence={exhaustion_conf})')
    print(f'  combo_B: {verdicts["combo_B"]}')
    print(f'    1500p={p1["windows"]["w1500"]}, perm_p={p1["perm_p"]}, 3win={p1["three_window_pass"]}')
    print(f'    McNemar vs ortho5: net={p1["mcnemar"]["net"]}, p={p1["mcnemar"]["p"]}')
    print(f'  H-PL-01: {verdicts["H-PL-01"]}  (600p={p2["w600"]}, perm_p={p2["perm_p"]})')
    print(f'  H-PL-03: {verdicts["H-PL-03"]}  (600p={p3["w600"]}, perm_p={p3["perm_p"]})')
    print(f'  Ensemble: {verdicts["ensemble"]}')
    print(f'  Maintenance mode: {maintenance_mode}')
    print(f'  New lessons: {new_lessons_written}')
    if open_lines:
        print(f'  Open lines:')
        for ol in open_lines:
            print(f'    [{ol["line"]}] {ol["note"]}')
    print('\n  Action Items:')
    for a in action_items:
        print(f'    [{a["priority"]}] {a["action"]}')

    return report

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def main():
    start_ts = datetime.now()
    print(f'=== POWER_LOTTO FINAL RESEARCH — {start_ts.strftime("%Y-%m-%d %H:%M")} ===')

    draws      = load_draws()
    bt_records = load_backtest()
    print(f'Loaded {len(draws)} draws, {len(bt_records)} backtest records')
    print(f'  Latest draw: {draws[-1]["draw"]} ({draws[-1]["date"]})')

    # Phase 1: combo_B 1500p
    try:
        p1 = phase1_combo_b(draws, bt_records)
    except Exception as e:
        log_error(1, str(e))
        import traceback; traceback.print_exc()
        p1 = {
            'verdict': 'RETIRE', 'windows': {'w150': None, 'w300': None, 'w500': None, 'w1000': None, 'w1500': None},
            'three_window_pass': False, 'perm_p': 1.0,
            'mcnemar': {'b': 0, 'c': 0, 'net': 0, 'p': 1.0},
            'ortho_5bet_1500p_edge': ORTHO_1500P_EDGE,
            'beats_orthogonal': False,
            'promotion_conditions_met': [False]*4, 'notes': 'ERROR', 'n_tested': 0, 'errors': 1,
        }

    # Phase 2: H-PL-01
    try:
        p2 = phase2_hpl01(draws, bt_records)
    except Exception as e:
        log_error(2, str(e))
        import traceback; traceback.print_exc()
        p2 = {
            'w150': None, 'w300': None, 'w500': None, 'w600': None, 'perm_p': 1.0, 'obs_edge_600p': 0,
            'structural_bias': False, 'chi2_p': 1.0, 'chi2_stat': 0,
            'ljung_box_q': 0, 'ljung_box_p': 1.0, 'autocorrelation_present': False,
            'three_window_pass': False, 'verdict': 'FAIL', 'close_signal_space': True,
            'n_tested': 0, 'errors': 1,
        }

    # Phase 3: H-PL-03
    try:
        p3 = phase3_hpl03(draws, bt_records)
    except Exception as e:
        log_error(3, str(e))
        import traceback; traceback.print_exc()
        p3 = {
            'zone_autocorr_ljung_p': 1.0, 'autocorrelation_present': False,
            'top5_zone_transitions': [],
            'w150': None, 'w300': None, 'w500': None, 'w600': None, 'perm_p': 1.0, 'obs_edge_600p': 0,
            'three_window_pass': False, 'signal_coverage': 0,
            'conditional_edge': None, 'unconditional_edge': None,
            'verdict': 'FAIL', 'close_signal_space': True, 'n_tested': 0, 'errors': 1,
        }

    # Phase 4: Ensemble
    try:
        p4 = phase4_ensemble(draws, bt_records)
    except Exception as e:
        log_error(4, str(e))
        import traceback; traceback.print_exc()
        p4 = {
            'signal_trigger_rates': {'h_pl_01': 0, 'h_pl_02': 0, 'h_pl_03': 0},
            'and_trigger_rate': 0, 'and_2plus_trigger_rate': 0,
            'no_op_verdict': True, 'conditional_edge': None, 'skip_rate': None,
            'perm_p': None, 'verdict': 'NO_OP', 'n_tested': 0, 'errors': 1,
        }

    # Phase 5: Final report
    try:
        phase5_final(p1, p2, p3, p4, draws)
    except Exception as e:
        log_error(5, str(e))
        import traceback; traceback.print_exc()

    # Save error log
    if ERRORS:
        with open(os.path.join(DATA_DIR, 'pl_final_agent_errors.json'), 'w') as f:
            json.dump(ERRORS, f, indent=2)
        print(f'\nErrors: {len(ERRORS)} → data/pl_final_agent_errors.json')

    elapsed = (datetime.now() - start_ts).total_seconds()
    print(f'\nTotal elapsed: {elapsed:.0f}s')

if __name__ == '__main__':
    main()
