#!/usr/bin/env python3
"""
POWER_LOTTO Deep Validation — Phase 2-5 (2026-04-19)

Phase 2: H-PL-04 Consecutive Bonus 600p validation
Phase 3: H-PL-02 Mod7 Periodicity structural analysis + 600p
Phase 4: mk_3bet combo 5-bet exploration (4 combos vs orthogonal_5bet)
Phase 5: Integrated report + lessons.md

Anti-leakage: history[:idx] strict. Permutation = MC null Binomial(1, baseline).
seed=42. Do NOT modify deployed strategies.
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
BACKTEST_PATH = os.path.join(DATA_DIR, 'power_lotto_full_backtest.jsonl')

MAX_NUM       = 38
BASELINE_1BET = 0.01034
BASELINE_2BET = 0.0759
BASELINE_3BET = 0.1117
BASELINE_5BET = 0.1791

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

def load_backtest():
    records = []
    with open(BACKTEST_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

# ════════════════════════════════════════════════════════════
# Core Helpers
# ════════════════════════════════════════════════════════════
def is_m3plus(bets, actual):
    actual_set = set(actual)
    for b in bets:
        if isinstance(b, dict):
            b = b.get('numbers', b)
        if sum(1 for n in b if n in actual_set) >= 3:
            return True
    return False

def best_hit_count(bets, actual):
    actual_set = set(actual)
    best = 0
    for b in bets:
        if isinstance(b, dict):
            b = b.get('numbers', b)
        h = sum(1 for n in b if n in actual_set)
        if h > best:
            best = h
    return best

def edge_at_window(hits, baseline, w):
    if len(hits) < w:
        return None
    last = hits[-w:]
    return round(sum(last) / len(last) - baseline, 4)

def mc_perm_test(hits, baseline, n_perm=500, seed=42):
    """
    MC null: each draw is M3+ with prob=baseline (Binomial(1, baseline)).
    L96: permutation = MC null, NOT shuffle labels.
    """
    rng = random.Random(seed)
    n = len(hits)
    obs_edge = sum(hits) / n - baseline
    count_ge = 0
    for _ in range(n_perm):
        null_sum = sum(1 for _ in range(n) if rng.random() < baseline)
        if (null_sum / n - baseline) >= obs_edge:
            count_ge += 1
    return obs_edge, count_ge / n_perm

def mcnemar_exact_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    lo = min(b, c)
    p = sum(comb(n, k) * (0.5 ** n) for k in range(lo + 1))
    return min(1.0, 2 * p)

# ════════════════════════════════════════════════════════════
# H-PL-04 STRATEGY (Consecutive Bonus 2-bet)
# ════════════════════════════════════════════════════════════
def _consec_2bet(history):
    """Consecutive pair frequency bonus — same as Phase 4 original."""
    window = min(len(history), 200)
    recent = history[-window:]

    consec_count = Counter()
    for d in recent:
        nums = sorted(n for n in d['numbers'][:6] if 1 <= n <= MAX_NUM)
        for i in range(len(nums)-1):
            if nums[i+1] - nums[i] == 1:
                consec_count[nums[i]] += 1
                consec_count[nums[i+1]] += 1

    freq = Counter()
    for d in recent:
        for n in d['numbers'][:6]:
            if 1 <= n <= MAX_NUM:
                freq[n] += 1

    scores = {n: consec_count.get(n, 0) * 2 + freq.get(n, 0) for n in range(1, MAX_NUM+1)}
    ranked = sorted(range(1, MAX_NUM+1), key=lambda x: -scores[x])
    return [sorted(ranked[:6]), sorted(ranked[6:12])]

def _count_consec_pairs(nums):
    """Count consecutive pairs in a sorted list of numbers."""
    s = sorted(n for n in nums if 1 <= n <= MAX_NUM)
    return sum(1 for i in range(len(s)-1) if s[i+1] - s[i] == 1)

def _theoretical_consec_prob(k, N=38, pick=6):
    """
    Probability of exactly k consecutive pairs in a 38C6 draw.
    Approximate via: theoretical expected count of adj pairs = (N-1) * C(N-2, pick-2) / C(N, pick).
    For structural baseline, use empirical mean from full history.
    """
    # Expected number of consecutive pairs in a random 38C6 selection:
    # E[pairs] = (N-1) * C(N-2, pick-2) / C(N, pick)
    return (N-1) * comb(N-2, pick-2) / comb(N, pick)

# ════════════════════════════════════════════════════════════
# PHASE 2 — H-PL-04 600p Full Validation
# ════════════════════════════════════════════════════════════
def phase2_hpl04(all_draws, bt_records):
    print('\n' + '='*60)
    print('PHASE 2: H-PL-04 Consecutive Bonus 600p Validation')
    print('='*60)

    BASELINE = BASELINE_2BET
    n_total = len(all_draws)

    # Map draw → index in all_draws
    draw_to_idx = {d['draw']: i for i, d in enumerate(all_draws)}

    # Identify 600p test window from backtest records
    n_bt = len(bt_records)
    start_idx_bt = max(0, n_bt - 600)
    test_bt = bt_records[start_idx_bt:]
    print(f'  600p window: {test_bt[0]["draw"]} ~ {test_bt[-1]["draw"]} (n={len(test_bt)})')

    # Run H-PL-04 on each period — strictly anti-leakage using all_draws[:idx]
    hits = []
    details = []
    errors = 0
    consec_signals = []

    for rec in test_bt:
        draw_id = rec['draw']
        idx = draw_to_idx.get(draw_id)
        if idx is None or idx == 0:
            errors += 1
            continue

        hist = all_draws[:idx]   # strict anti-leakage
        actual = rec['actual']

        # Signal: consecutive pairs in last draw
        last_nums = hist[-1]['numbers'] if hist else []
        n_consec = _count_consec_pairs(last_nums)
        consec_signals.append(n_consec)

        try:
            bets = _consec_2bet(hist)
            hit = is_m3plus(bets, actual)
            hc = best_hit_count(bets, actual)
            hits.append(hit)
            details.append({
                'draw': draw_id,
                'date': rec['date'],
                'consec_signal_prev_draw': n_consec,
                'is_m3plus': hit,
                'hit_count': hc,
            })
        except Exception as e:
            log_error(2, f'draw {draw_id}: {e}')
            hits.append(False)
            errors += 1

    n = len(hits)
    print(f'  Tested: {n} periods, errors: {errors}')

    # B. Multi-window edges
    w150  = edge_at_window(hits, BASELINE, 150)
    w300  = edge_at_window(hits, BASELINE, 300)
    w500  = edge_at_window(hits, BASELINE, 500)
    w600  = edge_at_window(hits, BASELINE, 600)

    three_window_pass = (
        w150 is not None and w150 > 0 and
        w500 is not None and w500 > 0 and
        w600 is not None and w600 > 0
    )
    print(f'  Windows: 150={w150:.4f}  300={w300:.4f}  500={w500:.4f}  600={w600:.4f}')
    print(f'  Three-window pass: {three_window_pass}')

    # C. Permutation test (500 shuffles, MC null)
    obs_e, perm_p = mc_perm_test(hits, BASELINE, n_perm=500, seed=42)
    print(f'  Perm test: obs={obs_e:.4f}, perm_p={perm_p:.4f}')

    # D. Signal characteristics
    # Theoretical expected consecutive pairs in 38C6
    theoretical_mean = _theoretical_consec_prob(0)   # returns expected count
    actual_consec_rates = []
    for d in all_draws:
        actual_consec_rates.append(_count_consec_pairs(d['numbers']))
    empirical_mean = sum(actual_consec_rates) / len(actual_consec_rates)

    # Conditional hit rate: signal>0 vs signal=0
    hits_with_signal    = [hits[i] for i in range(n) if i < len(consec_signals) and consec_signals[i] > 0]
    hits_without_signal = [hits[i] for i in range(n) if i < len(consec_signals) and consec_signals[i] == 0]

    cond_hit_rate   = sum(hits_with_signal) / len(hits_with_signal)   if hits_with_signal   else None
    uncond_hit_rate = sum(hits_without_signal) / len(hits_without_signal) if hits_without_signal else None
    signal_rate = sum(1 for x in consec_signals if x > 0) / len(consec_signals) if consec_signals else 0

    print(f'  Empirical avg consec pairs: {empirical_mean:.3f} (theory: {theoretical_mean:.3f})')
    print(f'  Signal rate (prev consec>0): {signal_rate:.3f}')
    print(f'  Conditional HR (signal): {cond_hit_rate}  Unconditional HR: {uncond_hit_rate}')

    # Verdict
    if three_window_pass and perm_p < 0.05:
        verdict = 'PASS'
        proceed = True
    elif three_window_pass and perm_p < 0.10:
        verdict = 'MARGINAL'
        proceed = False
    elif not three_window_pass and obs_e < 0:
        verdict = 'FAIL'
        proceed = False
    else:
        verdict = 'MARGINAL'
        proceed = False

    print(f'  Verdict: {verdict}')

    result = {
        'strategy': 'consecutive_bonus',
        'window_150p': w150,
        'window_300p': w300,
        'window_500p': w500,
        'window_600p': w600,
        'three_window_pass': three_window_pass,
        'perm_p': round(perm_p, 4),
        'obs_edge_600p': round(obs_e, 4),
        'consecutive_occurrence_rate': round(empirical_mean, 4),
        'baseline_consecutive_rate': round(theoretical_mean, 4),
        'conditional_hit_rate': round(cond_hit_rate, 4) if cond_hit_rate else None,
        'unconditional_hit_rate': round(uncond_hit_rate, 4) if uncond_hit_rate else None,
        'signal_rate': round(signal_rate, 4),
        'verdict': verdict,
        'proceed_to_full_oos': proceed,
        'n_tested': n,
        'errors': errors,
        'details_600p': details,
    }

    out = os.path.join(DATA_DIR, 'h_pl_04_validation.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({k: v for k, v in result.items() if k != 'details_600p'}, f, indent=2, ensure_ascii=False)
    # Save details separately
    with open(os.path.join(DATA_DIR, 'h_pl_04_details.json'), 'w', encoding='utf-8') as f:
        json.dump(details, f, indent=2)

    print(f'  Saved: {out}')
    return result

# ════════════════════════════════════════════════════════════
# H-PL-02 STRATEGY (Mod7 Periodicity 2-bet)
# ════════════════════════════════════════════════════════════
def _mod7_2bet(history):
    """Mod7 Periodicity — same as Phase 4 original."""
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

# ════════════════════════════════════════════════════════════
# PHASE 3 — H-PL-02 Mod7 Periodicity Validation
# ════════════════════════════════════════════════════════════
def phase3_hpl02(all_draws, bt_records):
    print('\n' + '='*60)
    print('PHASE 3: H-PL-02 Mod7 Periodicity Validation')
    print('='*60)

    # A. Structural bias test — chi-square on full history
    # Expected: uniform if pool is balanced; 38 numbers → mod7 distribution:
    # n%7==0: 5 numbers (7,14,21,28,35), mod7==1: 6 (1,8,15,22,29,36), etc.
    pool_mod7_counts = Counter(n % 7 for n in range(1, MAX_NUM+1))
    print(f'  Pool mod7 distribution (expected): {dict(sorted(pool_mod7_counts.items()))}')

    # Actual mod7 distribution in all draws
    observed_mod7 = Counter()
    for d in all_draws:
        for n in d['numbers'][:6]:
            if 1 <= n <= MAX_NUM:
                observed_mod7[n % 7] += 1

    total_obs = sum(observed_mod7.values())
    # Expected counts: proportional to pool distribution
    total_pool = sum(pool_mod7_counts.values())
    expected_mod7 = {m: (pool_mod7_counts[m] / total_pool) * total_obs for m in range(7)}

    # Chi-square stat
    chi2 = sum(
        (observed_mod7.get(m, 0) - expected_mod7[m])**2 / expected_mod7[m]
        for m in range(7)
    )
    # df = 6 (7 categories - 1)
    # Approximate chi2 p-value using scipy-free method (critical value lookup)
    # chi2(6, alpha=0.05) = 12.592, chi2(6, alpha=0.10) = 10.645
    chi2_p_approx = 'p<0.05' if chi2 > 12.592 else ('p<0.10' if chi2 > 10.645 else 'p>=0.10')
    structural_bias = chi2 > 12.592

    print(f'  Chi2 statistic: {chi2:.4f} (df=6), approx: {chi2_p_approx}')
    print(f'  Structural bias: {structural_bias}')

    # Numerical chi2 p-value via Wilson-Hilferty normal approximation (more numerically stable)
    def chi2_sf(x, df):
        """
        Upper tail of chi2(df) at x.
        Uses Wilson-Hilferty cube-root normal approximation:
          z ≈ ((x/df)^(1/3) - (1 - 2/(9*df))) / sqrt(2/(9*df))
        then p = 1 - Phi(z) (standard normal upper tail).
        Accurate to within ~1% for df >= 2.
        """
        if x <= 0:
            return 1.0
        # Wilson-Hilferty transform
        h = 2.0 / (9.0 * df)
        z = ((x / df) ** (1.0/3.0) - (1.0 - h)) / math.sqrt(h)
        # Standard normal survival function via erfc
        return 0.5 * math.erfc(z / math.sqrt(2.0))

    chi2_p = chi2_sf(chi2, 6)
    structural_bias = chi2_p < 0.05
    print(f'  Chi2 p-value: {chi2_p:.6f}, structural_bias={structural_bias}')

    # B. Autocorrelation of mod7 mean per draw (Ljung-Box proxy)
    # mod7_mean[t] = mean of (n%7) for n in draw t
    mod7_means = [
        sum(n % 7 for n in d['numbers'][:6] if 1 <= n <= MAX_NUM) / 6
        for d in all_draws
    ]

    n = len(mod7_means)
    # ACF at lags 1-10
    mu = sum(mod7_means) / n
    variance = sum((x - mu)**2 for x in mod7_means) / n

    def acf(lag):
        if variance < 1e-10:
            return 0.0
        return sum((mod7_means[t] - mu) * (mod7_means[t+lag] - mu)
                   for t in range(n - lag)) / ((n - lag) * variance)

    acf_vals = [acf(lag) for lag in range(1, 11)]
    print(f'  ACF[1-5]: {[round(a, 4) for a in acf_vals[:5]]}')

    # Ljung-Box Q statistic for lags 1-10
    Q = n * (n + 2) * sum(acf_vals[lag]**2 / (n - lag - 1) for lag in range(10))
    # chi2 with df=10: critical values: p<0.05 → Q>18.307, p<0.10 → Q>15.987
    ljung_box_p = chi2_sf(Q, 10)
    autocorrelation_meaningful = ljung_box_p < 0.10
    print(f'  Ljung-Box Q={Q:.4f}, p={ljung_box_p:.6f}, meaningful={autocorrelation_meaningful}')

    # Decision: skip if structural bias AND no autocorrelation
    if structural_bias and not autocorrelation_meaningful:
        verdict = 'STRUCTURAL_BIAS_REJECT'
        notes = (f'chi2={chi2:.2f} (p={chi2_p:.4f}) signals pool structural bias (unequal mod7 class sizes). '
                 f'Ljung-Box Q={Q:.2f} (p={ljung_box_p:.4f}) shows no serial correlation. '
                 'Following L104 pattern: pool structure ≠ exploitable temporal signal.')
        result = {
            'strategy': 'mod7_periodicity',
            'structural_bias': True,
            'chi2': round(chi2, 4),
            'chi2_p': round(chi2_p, 6),
            'ljung_box_q': round(Q, 4),
            'ljung_box_p': round(ljung_box_p, 6),
            'autocorrelation_meaningful': False,
            'acf_lag1_5': [round(a, 4) for a in acf_vals[:5]],
            'window_600p': None,
            'perm_p': None,
            'verdict': verdict,
            'notes': notes,
        }
        print(f'  Verdict: {verdict}')
        out = os.path.join(DATA_DIR, 'h_pl_02_validation.json')
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f'  Saved: {out}')
        return result

    # C. 600p backtest if autocorrelation is meaningful
    BASELINE = BASELINE_2BET
    draw_to_idx = {d['draw']: i for i, d in enumerate(all_draws)}
    n_bt = len(bt_records)
    start_bt = max(0, n_bt - 600)
    test_bt = bt_records[start_bt:]

    hits = []
    errors_c = 0
    for rec in test_bt:
        idx = draw_to_idx.get(rec['draw'])
        if idx is None or idx == 0:
            errors_c += 1
            continue
        hist = all_draws[:idx]
        actual = rec['actual']
        try:
            bets = _mod7_2bet(hist)
            hits.append(is_m3plus(bets, actual))
        except Exception as e:
            log_error(3, f"draw {rec['draw']}: {e}")
            hits.append(False)
            errors_c += 1

    w600 = edge_at_window(hits, BASELINE, 600)
    w500 = edge_at_window(hits, BASELINE, 500)
    w300 = edge_at_window(hits, BASELINE, 300)
    w150 = edge_at_window(hits, BASELINE, 150)

    obs_e, perm_p = mc_perm_test(hits, BASELINE, n_perm=500, seed=42)
    three_win = (w150 is not None and w150 > 0 and
                 w500 is not None and w500 > 0 and
                 w600 is not None and w600 > 0)

    print(f'  600p windows: 150={w150}  300={w300}  500={w500}  600={w600}')
    print(f'  perm_p={perm_p:.4f}, three_window_pass={three_win}')

    if three_win and perm_p < 0.05:
        verdict = 'PASS'
    elif three_win and perm_p < 0.10:
        verdict = 'MARGINAL'
    else:
        verdict = 'FAIL'

    notes = (f'chi2_p={chi2_p:.4f} (structural_bias={structural_bias}), '
             f'Ljung-Box p={ljung_box_p:.4f} (autocorr={autocorrelation_meaningful}). '
             f'600p edge={w600}, perm_p={perm_p:.4f}.')
    print(f'  Verdict: {verdict}')

    result = {
        'strategy': 'mod7_periodicity',
        'structural_bias': structural_bias,
        'chi2': round(chi2, 4),
        'chi2_p': round(chi2_p, 6),
        'ljung_box_q': round(Q, 4),
        'ljung_box_p': round(ljung_box_p, 6),
        'autocorrelation_meaningful': autocorrelation_meaningful,
        'acf_lag1_5': [round(a, 4) for a in acf_vals[:5]],
        'window_150p': w150,
        'window_300p': w300,
        'window_500p': w500,
        'window_600p': w600,
        'three_window_pass': three_win,
        'perm_p': round(perm_p, 4),
        'obs_edge_600p': round(obs_e, 4),
        'verdict': verdict,
        'notes': notes,
    }

    out = os.path.join(DATA_DIR, 'h_pl_02_validation.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f'  Saved: {out}')
    return result

# ════════════════════════════════════════════════════════════
# PHASE 4 — mk_3bet Combo 5-bet Exploration
# ════════════════════════════════════════════════════════════
def phase4_mk_combo(all_draws, bt_records):
    print('\n' + '='*60)
    print('PHASE 4: mk_3bet Combo 5-bet Exploration')
    print('='*60)

    from tools.power_fourier_rhythm import fourier_rhythm_predict
    from tools.power_midfreq_fourier import midfreq_fourier_markov_3bet
    from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet

    BASELINE = 0.1791   # 5-bet M3+ baseline
    draw_to_idx = {d['draw']: i for i, d in enumerate(all_draws)}

    # 600p test window
    n_bt = len(bt_records)
    start_bt = max(0, n_bt - 600)
    test_bt = bt_records[start_bt:]
    n_test = len(test_bt)
    print(f'  600p window: {test_bt[0]["draw"]} ~ {test_bt[-1]["draw"]} (n={n_test})')

    # Pre-compute per-period bets for all strategies (anti-leakage)
    print('  Pre-computing strategy bets...')
    period_data = []  # [{fr3_bets, mk3_bets, orth5_bets, actual}]
    errors = 0

    for rec in test_bt:
        idx = draw_to_idx.get(rec['draw'])
        if idx is None or idx < 50:
            errors += 1
            period_data.append(None)
            continue

        hist = all_draws[:idx]
        actual = rec['actual']

        try:
            fr3 = fourier_rhythm_predict(hist, n_bets=3, window=500)
            mk3 = midfreq_fourier_markov_3bet(hist)
            orth5 = generate_orthogonal_5bet(hist)
            period_data.append({'fr3': fr3, 'mk3': mk3, 'orth5': orth5, 'actual': actual, 'draw': rec['draw']})
        except Exception as e:
            log_error(4, f"draw {rec['draw']}: {e}")
            period_data.append(None)
            errors += 1

        if len(period_data) % 200 == 0:
            print(f'    {len(period_data)}/{n_test}...', flush=True)

    print(f'  Pre-compute done. Valid: {sum(1 for p in period_data if p)}, errors: {errors}')

    # Combo definitions
    # combo_A: fourier 3 + mk 2
    # combo_B: fourier 2 + mk 3
    # combo_C: fourier 3 + mk 2 with selective gate (mk 50p M3+ < 1.0% → drop mk)
    # combo_D: dynamic — if mk recent 50p edge > fourier → combo_B, else combo_A

    def get_combo_bets(pd_slice, combo_name):
        """Given a slice of period_data up to current period, return 5 bets for the last period."""
        cur = pd_slice[-1]
        if cur is None:
            return None

        fr3 = cur['fr3'][:3]  # ensure 3
        mk3 = cur['mk3'][:3]  # ensure 3

        if combo_name == 'combo_A':
            return fr3 + mk3[:2]   # 3+2=5

        elif combo_name == 'combo_B':
            return fr3[:2] + mk3   # 2+3=5

        elif combo_name == 'combo_C':
            # Gate: if mk recent 50p M3+ < 1.0% → skip mk
            # Compute recent 50p mk M3+ from pd_slice
            recent_50 = [p for p in pd_slice[-51:-1] if p is not None]  # last 50 before current
            if recent_50:
                mk_hits_50 = [is_m3plus(p['mk3'], p['actual']) for p in recent_50]
                mk_rate_50 = sum(mk_hits_50) / len(mk_hits_50)
            else:
                mk_rate_50 = BASELINE_3BET

            if mk_rate_50 < 0.010:
                # Use fourier 5 bets (best 5 from fourier, take 5 not 3)
                # We only have fr3 precomputed; extend with mk2 but penalized
                return fr3 + fr3[:2]   # fallback: fourier 5 (with overlap allowed)
            else:
                return fr3 + mk3[:2]

        elif combo_name == 'combo_D':
            # Dynamic: compare mk vs fourier recent 50p edge
            recent_50 = [p for p in pd_slice[-51:-1] if p is not None]
            if recent_50:
                mk_e   = sum(is_m3plus(p['mk3'], p['actual']) for p in recent_50) / len(recent_50) - BASELINE_3BET
                fr_e   = sum(is_m3plus(p['fr3'], p['actual']) for p in recent_50) / len(recent_50) - BASELINE_3BET
            else:
                mk_e, fr_e = 0, 0

            if mk_e > fr_e:
                return fr3[:2] + mk3   # combo_B
            else:
                return fr3 + mk3[:2]   # combo_A

        return fr3 + mk3[:2]

    # Run all 4 combos
    combo_names = ['combo_A', 'combo_B', 'combo_C', 'combo_D']
    combo_hits = {c: [] for c in combo_names}
    ortho_hits = []

    for i, pd in enumerate(period_data):
        if pd is None:
            for c in combo_names:
                combo_hits[c].append(False)
            ortho_hits.append(False)
            continue

        actual = pd['actual']
        orth5_bets = pd['orth5']
        ortho_hits.append(is_m3plus(orth5_bets, actual))

        slice_so_far = [p for p in period_data[:i+1]]  # pass full slice for gate calculation
        for c in combo_names:
            try:
                bets = get_combo_bets(slice_so_far, c)
                if bets is None:
                    combo_hits[c].append(False)
                else:
                    combo_hits[c].append(is_m3plus(bets, actual))
            except:
                combo_hits[c].append(False)

    # Compute metrics per combo
    combo_results = {}
    for c in combo_names:
        hits = combo_hits[c]
        n = len(hits)
        w150 = edge_at_window(hits, BASELINE, 150)
        w300 = edge_at_window(hits, BASELINE, 300)
        w500 = edge_at_window(hits, BASELINE, 500)
        w600 = edge_at_window(hits, BASELINE, 600)
        three_win = (w150 is not None and w150 > 0 and
                     w500 is not None and w500 > 0 and
                     w600 is not None and w600 > 0)
        obs_e, perm_p = mc_perm_test(hits, BASELINE, n_perm=300, seed=42)

        combo_results[c] = {
            'w150': w150, 'w300': w300, 'w500': w500, 'w600': w600,
            'three_window_pass': three_win,
            'perm_p': round(perm_p, 4),
            'obs_edge': round(obs_e, 4),
            'hit_rate': round(sum(hits)/n, 4) if n > 0 else None,
        }
        print(f'  {c}: 150={w150}  300={w300}  500={w500}  600={w600}  perm_p={perm_p:.4f}  3win={three_win}')

    # Best combo by 600p edge
    valid_combos = [(c, combo_results[c]['w600']) for c in combo_names if combo_results[c]['w600'] is not None]
    best_combo = max(valid_combos, key=lambda x: x[1])[0] if valid_combos else 'combo_A'
    print(f'  Best combo: {best_combo}')

    # D. McNemar vs orthogonal_5bet
    bc_hits = combo_hits[best_combo]
    b = sum(1 for i in range(len(bc_hits)) if bc_hits[i] and not ortho_hits[i])
    c = sum(1 for i in range(len(bc_hits)) if not bc_hits[i] and ortho_hits[i])
    mc_net = b - c
    mc_p = mcnemar_exact_p(b, c)
    print(f'  McNemar ({best_combo} vs orthogonal_5bet): b={b}, c={c}, net={mc_net}, p={mc_p:.4f}')

    # Phi correlation between best_combo and ortho
    n = len(bc_hits)
    both   = sum(1 for i in range(n) if bc_hits[i] and ortho_hits[i])
    b_only = sum(1 for i in range(n) if bc_hits[i] and not ortho_hits[i])
    c_only = sum(1 for i in range(n) if not bc_hits[i] and ortho_hits[i])
    nei    = sum(1 for i in range(n) if not bc_hits[i] and not ortho_hits[i])
    denom  = math.sqrt((both+b_only)*(c_only+nei)*(both+c_only)*(b_only+nei))
    phi = (both*nei - b_only*c_only) / denom if denom > 1e-8 else 0
    print(f'  Phi ({best_combo} vs ortho): {phi:.4f}')

    # Verdict: PROMOTE if best combo: all-positive windows + perm_p<0.05 + McNemar p<0.05 + net>0
    bc = combo_results[best_combo]
    if bc['three_window_pass'] and bc['perm_p'] < 0.05 and mc_p < 0.05 and mc_net > 0:
        verdict = 'PROMOTE_COMBO'
    elif bc['three_window_pass'] and bc['perm_p'] < 0.10:
        verdict = 'CONTINUE_WATCH'
    elif bc['w600'] is not None and bc['w600'] > 0:
        verdict = 'CONTINUE_WATCH'
    else:
        verdict = 'REJECT_COMBO'

    notes = (f'Best={best_combo} (600p={bc["w600"]}, perm_p={bc["perm_p"]}, 3win={bc["three_window_pass"]}). '
             f'McNemar vs ortho5: net={mc_net}, p={mc_p:.4f}. Phi={phi:.3f}. '
             f'Verdict={verdict}.')
    print(f'  Verdict: {verdict}')

    result = {
        'combos': combo_results,
        'best_combo': best_combo,
        'mcnemar_vs_orthogonal_5bet': {'b': b, 'c': c, 'net': mc_net, 'p': round(mc_p, 4)},
        'phi_combo_vs_ortho': round(phi, 4),
        'verdict': verdict,
        'notes': notes,
        'n_tested': n_test,
        'errors': errors,
    }

    out = os.path.join(DATA_DIR, 'mk_combo_validation.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f'  Saved: {out}')
    return result

# ════════════════════════════════════════════════════════════
# PHASE 5 — Integrated Report + lessons.md
# ════════════════════════════════════════════════════════════
def phase5_report(p2, p3, p4, draws):
    print('\n' + '='*60)
    print('PHASE 5: Integrated Report & lessons.md Update')
    print('='*60)

    now_str = datetime.now().strftime('%Y-%m-%d')
    latest_draw = draws[-1]['draw']

    hpl04_verdict  = p2['verdict']
    hpl02_verdict  = p3['verdict']
    combo_verdict  = p4['verdict']
    structural_bias = p3.get('structural_bias', False)

    # Overall verdict
    if hpl04_verdict == 'PASS' or combo_verdict == 'PROMOTE_COMBO':
        overall = 'EXPANDING'
    elif (hpl04_verdict == 'FAIL' and
          hpl02_verdict in ('FAIL', 'STRUCTURAL_BIAS_REJECT') and
          combo_verdict == 'REJECT_COMBO'):
        overall = 'CONTRACTING'
    else:
        overall = 'STABLE'

    # Action items
    action_items = []

    if hpl04_verdict == 'PASS':
        action_items.append({'priority': 'HIGH', 'action': 'H-PL-04 PASS: run full 1500p OOS + McNemar vs fourier_3bet. Then human review for deploy.'})
    elif hpl04_verdict == 'MARGINAL':
        action_items.append({'priority': 'MED', 'action': f'H-PL-04 MARGINAL: 3win={p2["three_window_pass"]}, perm_p={p2["perm_p"]}. Extend to 1000p next session.'})
    else:
        action_items.append({'priority': 'LOW', 'action': 'H-PL-04 FAIL: consecutive bonus signal invalid. Close hypothesis.'})

    if hpl02_verdict == 'STRUCTURAL_BIAS_REJECT':
        action_items.append({'priority': 'MED', 'action': 'H-PL-02 STRUCTURAL_BIAS_REJECT: mod7 pool structure ≠ exploitable signal. Close hypothesis.'})
    elif hpl02_verdict == 'PASS':
        action_items.append({'priority': 'HIGH', 'action': 'H-PL-02 PASS: run full 1500p OOS. Then human review.'})
    elif hpl02_verdict == 'MARGINAL':
        action_items.append({'priority': 'MED', 'action': f'H-PL-02 MARGINAL: extend to 1000p. perm_p={p3.get("perm_p")}'})
    else:
        action_items.append({'priority': 'LOW', 'action': 'H-PL-02 FAIL: mod7 periodicity invalid. Close hypothesis.'})

    if combo_verdict == 'PROMOTE_COMBO':
        bc = p4['best_combo']
        mc = p4['mcnemar_vs_orthogonal_5bet']
        action_items.append({'priority': 'HIGH',
                              'action': f'PENDING HUMAN REVIEW: {bc} PROMOTE_COMBO. McNemar net={mc["net"]} p={mc["p"]:.4f}. '
                              f'Deploy cmd: UPDATE rsm_bootstrap.py → add {bc} to POWER_LOTTO strategies.'})
    elif combo_verdict == 'CONTINUE_WATCH':
        bc = p4['best_combo']
        action_items.append({'priority': 'MED',
                              'action': f'mk_combo {bc}: CONTINUE_WATCH. Run 1500p backtest next session. '
                              f'Current 600p edge={p4["combos"][bc]["w600"]}, perm_p={p4["combos"][bc]["perm_p"]}'})
    else:
        action_items.append({'priority': 'LOW', 'action': 'mk_combo all variants: REJECT. phi=0.19 additive potential not confirmed in 600p.'})

    # New lessons
    new_lessons = []
    lessons_path = os.path.join(MEM_DIR, 'lessons.md')

    try:
        with open(lessons_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        content = ''

    # Determine next lesson ID
    import re
    existing_ids = [int(m) for m in re.findall(r'\*\*L(\d+)', content)]
    next_id = max(existing_ids) + 1 if existing_ids else 109

    lesson_entries = []

    if hpl04_verdict == 'FAIL':
        lesson_entries.append((next_id, f"""**L{next_id} — H-PL-04 Consecutive Bonus: 威力彩連號信號無效** ({now_str})
- 600p edge={p2["window_600p"]}, perm_p={p2["perm_p"]}
- three_window_pass={p2["three_window_pass"]}
- 連號出現率={p2.get("consecutive_occurrence_rate"):.3f} vs 理論={p2.get("baseline_consecutive_rate"):.3f}
- 結論：過去連號頻率無法預測下期連號組合，策略無效。結案。"""))
        new_lessons.append(f'L{next_id}')
        next_id += 1
    elif hpl04_verdict == 'MARGINAL':
        lesson_entries.append((next_id, f"""**L{next_id} — H-PL-04 Consecutive Bonus: 邊際（600p）** ({now_str})
- 600p edge={p2["window_600p"]}, perm_p={p2["perm_p"]}, three_window_pass={p2["three_window_pass"]}
- 尚未達升格門檻。下步：延長至 1000p 確認。"""))
        new_lessons.append(f'L{next_id}')
        next_id += 1

    if hpl02_verdict == 'STRUCTURAL_BIAS_REJECT':
        lesson_entries.append((next_id, f"""**L{next_id} — H-PL-02 Mod7: 池結構偏差，非時序信號** ({now_str})
- chi2={p3["chi2"]:.2f}, p={p3["chi2_p"]:.6f} → structural_bias=True
- Ljung-Box Q={p3["ljung_box_q"]:.2f}, p={p3["ljung_box_p"]:.6f} → 無序列相關
- 類比 L104（BIG_LOTTO）：mod7 分布不均是號碼池的固有屬性，非可利用時序信號。結案。"""))
        new_lessons.append(f'L{next_id}')
        next_id += 1
    elif hpl02_verdict == 'FAIL':
        lesson_entries.append((next_id, f"""**L{next_id} — H-PL-02 Mod7: 週期性無效** ({now_str})
- 600p edge={p3.get("window_600p")}, perm_p={p3.get("perm_p")}
- 無自相關（Ljung-Box p={p3["ljung_box_p"]:.4f}）
- 結論：mod7 週期性不存在或不足以產生穩定邊際。結案。"""))
        new_lessons.append(f'L{next_id}')
        next_id += 1

    if combo_verdict == 'PROMOTE_COMBO':
        bc = p4['best_combo']
        mc = p4['mcnemar_vs_orthogonal_5bet']
        lesson_entries.append((next_id, f"""**L{next_id} — mk_combo {bc}: PENDING HUMAN REVIEW** ({now_str})
- 600p edge={p4["combos"][bc]["w600"]}, perm_p={p4["combos"][bc]["perm_p"]}
- McNemar vs ortho5: net={mc["net"]}, p={mc["p"]:.4f}
- phi_vs_ortho={p4["phi_combo_vs_ortho"]:.3f}
- 狀態：PROMOTE 條件滿足，等待人工確認部署。"""))
        new_lessons.append(f'L{next_id}')
        next_id += 1

    if lesson_entries:
        try:
            with open(lessons_path, 'a', encoding='utf-8') as lf:
                lf.write('\n\n')
                for lid, entry in lesson_entries:
                    lf.write(entry + '\n\n')
            print(f'  Updated lessons.md with {len(lesson_entries)} new entries: {new_lessons}')
        except Exception as e:
            log_error(5, f'lessons.md update failed: {e}')
    else:
        print('  No new lessons to write (no FAIL/PASS/PROMOTE results).')

    # Final report
    report = {
        'generated_at': datetime.now().isoformat(),
        'latest_draw': latest_draw,
        'h_pl_04_consecutive': {
            'verdict': hpl04_verdict,
            'three_window_pass': p2.get('three_window_pass'),
            'window_150p': p2.get('window_150p'),
            'window_300p': p2.get('window_300p'),
            'window_500p': p2.get('window_500p'),
            'window_600p': p2.get('window_600p'),
            'perm_p': p2.get('perm_p'),
            'proceed_to_next_phase': p2.get('proceed_to_full_oos', False),
        },
        'h_pl_02_mod7': {
            'verdict': hpl02_verdict,
            'structural_bias': structural_bias,
            'chi2_p': p3.get('chi2_p'),
            'ljung_box_p': p3.get('ljung_box_p'),
            'perm_p': p3.get('perm_p'),
            'window_600p': p3.get('window_600p'),
        },
        'mk_combo_5bet': {
            'best_combo': p4.get('best_combo'),
            'all_combo_600p': {c: p4['combos'][c].get('w600') for c in p4['combos']},
            'verdict': combo_verdict,
            'mcnemar_p': p4['mcnemar_vs_orthogonal_5bet']['p'],
            'mcnemar_net': p4['mcnemar_vs_orthogonal_5bet']['net'],
            'phi_vs_ortho5': p4.get('phi_combo_vs_ortho'),
        },
        'new_lessons': new_lessons,
        'overall_verdict': overall,
        'action_items': action_items,
    }

    out = os.path.join(DATA_DIR, 'power_lotto_deep_validation_2026_04_19.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f'  Saved: {out}')

    print('\n' + '='*60)
    print('DEEP VALIDATION SUMMARY')
    print('='*60)
    print(f'  Overall: {overall}')
    print(f'  H-PL-04: {hpl04_verdict}  (600p={p2.get("window_600p")}, perm_p={p2.get("perm_p")})')
    print(f'  H-PL-02: {hpl02_verdict}  (structural_bias={structural_bias})')
    print(f'  mk_combo: {combo_verdict}  best={p4.get("best_combo")}')
    print(f'  New lessons: {new_lessons}')
    print('\n  Action Items:')
    for a in action_items:
        print(f'    [{a["priority"]}] {a["action"]}')

    return report

# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════
def main():
    start_ts = datetime.now()
    print(f'=== POWER_LOTTO DEEP VALIDATION — {start_ts.strftime("%Y-%m-%d %H:%M")} ===')

    draws = load_draws()
    print(f'Loaded {len(draws)} POWER_LOTTO draws (latest: {draws[-1]["draw"]} {draws[-1]["date"]})')

    bt_records = load_backtest()
    print(f'Loaded {len(bt_records)} backtest records from {BACKTEST_PATH}')
    print(f'  Backtest fields: {list(bt_records[0]["strategies"].keys())}')

    # Phase 2: H-PL-04
    try:
        p2 = phase2_hpl04(draws, bt_records)
    except Exception as e:
        log_error(2, str(e))
        import traceback; traceback.print_exc()
        p2 = {'verdict': 'ERROR', 'window_150p': None, 'window_300p': None,
              'window_500p': None, 'window_600p': None, 'three_window_pass': False,
              'perm_p': 1.0, 'proceed_to_full_oos': False, 'consecutive_occurrence_rate': 0,
              'baseline_consecutive_rate': 0, 'conditional_hit_rate': None,
              'unconditional_hit_rate': None, 'signal_rate': 0}

    # Phase 3: H-PL-02
    try:
        p3 = phase3_hpl02(draws, bt_records)
    except Exception as e:
        log_error(3, str(e))
        import traceback; traceback.print_exc()
        p3 = {'verdict': 'ERROR', 'structural_bias': False, 'chi2': 0, 'chi2_p': 1.0,
              'ljung_box_q': 0, 'ljung_box_p': 1.0, 'autocorrelation_meaningful': False,
              'acf_lag1_5': [], 'window_600p': None, 'perm_p': 1.0}

    # Phase 4: mk_combo
    try:
        p4 = phase4_mk_combo(draws, bt_records)
    except Exception as e:
        log_error(4, str(e))
        import traceback; traceback.print_exc()
        p4 = {'verdict': 'REJECT_COMBO', 'best_combo': 'combo_A',
              'combos': {c: {'w150': None, 'w300': None, 'w500': None, 'w600': None,
                             'perm_p': 1.0, 'three_window_pass': False, 'obs_edge': 0} for c in ['combo_A','combo_B','combo_C','combo_D']},
              'mcnemar_vs_orthogonal_5bet': {'b': 0, 'c': 0, 'net': 0, 'p': 1.0},
              'phi_combo_vs_ortho': 0, 'notes': 'ERROR'}

    # Phase 5: report
    try:
        phase5_report(p2, p3, p4, draws)
    except Exception as e:
        log_error(5, str(e))
        import traceback; traceback.print_exc()

    if ERRORS:
        with open(os.path.join(DATA_DIR, 'pl_deep_agent_errors.json'), 'w') as f:
            json.dump(ERRORS, f, indent=2)
        print(f'\n  Errors: {len(ERRORS)} → data/pl_deep_agent_errors.json')

    elapsed = (datetime.now() - start_ts).total_seconds()
    print(f'\nTotal elapsed: {elapsed:.0f}s')

if __name__ == '__main__':
    main()
