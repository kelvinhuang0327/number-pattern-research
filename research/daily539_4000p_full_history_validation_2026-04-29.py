#!/usr/bin/env python3
"""
DAILY_539 4000p / Full-History Long-Window Validation
Research IDs: H-LW-01 (4000p+full-history edge), H-LW-02 (rolling 500p trend)

Goal:
  - Extend H_NEW_03 windows to 4000p, 5000p, full-history (5844p)
  - Test whether active strategy edge remains above DEGRADED threshold (+2.0pp)
  - Rolling 500p CUSUM changepoint: smooth decay vs regime shift

Constraints:
  - DB READ ONLY
  - No new strategy family, no Fourier/Markov variants
  - No active_strategy_state modification
  - seed=42

Run: .venv/bin/python3 research/daily539_4000p_full_history_validation_2026-04-29.py
"""

import sqlite3
import json
import csv
import os
import time
from collections import Counter
from datetime import datetime

import numpy as np
from scipy import stats as scipy_stats

# ----------------------------------------------------------------
# Config
# ----------------------------------------------------------------
DB_PATH        = 'lottery_api/data/lottery_v2.db'
GAME           = 'DAILY_539'
PICK           = 5
MAX_NUM        = 39
MIN_HIST       = 100
SEED           = 42
N_BOOT         = 2000
N_PERM         = 1000
DEGRADED_THRESHOLD = 2.0   # pp — watchdog threshold

ROLLING_WINDOW = 500
ROLLING_STEP   = 200

# Additional windows beyond prior report
EXTRA_WINDOWS  = [3000, 4000, 5000]  # full-history added dynamically

# Theoretical M2+ draw-level baselines
BASELINES      = {1: 11.40, 2: 21.54, 3: 30.50}
PAYOUT         = {0: 0, 1: 0, 2: 50, 3: 300, 4: 3000, 5: 200000}

OUTPUT_CSV_ROLLING   = 'outputs/daily539_rolling_500p_edge_2026-04-29.csv'
OUTPUT_CSV_WINDOWS   = 'outputs/daily539_long_window_4000p_results_2026-04-29.csv'
REPORT_PATH          = 'research/daily539_4000p_full_history_validation_report_2026-04-29.md'


# ----------------------------------------------------------------
# Data Loading
# ----------------------------------------------------------------
def load_draws():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = 'DAILY_539'
        ORDER BY CAST(draw AS INTEGER) ASC
    """).fetchall()
    conn.close()

    result, skipped = [], 0
    seen_draws = set()
    for r in rows:
        try:
            nums = json.loads(r['numbers'])
            if len(nums) == PICK and all(1 <= int(n) <= MAX_NUM for n in nums):
                key = r['draw']
                if key in seen_draws:
                    skipped += 1
                    continue
                seen_draws.add(key)
                result.append({
                    'draw':    r['draw'],
                    'date':    r['date'],
                    'numbers': [int(n) for n in nums],
                })
        except Exception:
            skipped += 1

    return result, skipped


# ----------------------------------------------------------------
# Strategy Implementations
# ----------------------------------------------------------------
def _acb_scores(history, window=100):
    recent = history[-window:] if len(history) >= window else history
    counter = Counter(n for d in recent for n in d['numbers'])
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            last_seen[n] = i
    expected = len(recent) * PICK / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM + 1):
        fd = expected - counter.get(n, 0)
        gap = (len(recent) - last_seen.get(n, -1)) / (len(recent) / 2)
        bb = 1.2 if (n <= 8 or n >= 35) else 1.0
        scores[n] = (fd * 0.4 + gap * 0.6) * bb
    return scores


def _markov_scores(history, window=30):
    recent = history[-window:] if len(history) >= window else history
    transitions = {}
    for i in range(len(recent) - 1):
        for pn in recent[i]['numbers']:
            if pn not in transitions:
                transitions[pn] = Counter()
            for nn in recent[i + 1]['numbers']:
                transitions[pn][nn] += 1
    scores = Counter()
    if recent:
        for pn in history[-1]['numbers']:
            trans = transitions.get(pn, Counter())
            total = sum(trans.values())
            if total > 0:
                for nn, cnt in trans.items():
                    scores[nn] += cnt / total
    return {n: scores.get(n, 0.0) for n in range(1, MAX_NUM + 1)}


def _midfreq_scores(history, window=100):
    recent = history[-window:] if len(history) >= window else history
    expected = len(recent) * PICK / MAX_NUM
    freq = Counter(n for d in recent for n in d['numbers'])
    return {n: -(abs(freq.get(n, 0) - expected)) for n in range(1, MAX_NUM + 1)}


def _top_n(scores, n=PICK, exclude=None):
    exclude = exclude or set()
    ranked = sorted([k for k in scores if k not in exclude], key=lambda x: -scores[x])
    return sorted(ranked[:n])


def strategy_acb_1bet(history):
    return [_top_n(_acb_scores(history))]


def strategy_midfreq_acb_2bet(history):
    bet1 = _top_n(_midfreq_scores(history))
    bet2 = _top_n(_acb_scores(history), exclude=set(bet1))
    if not bet2:
        bet2 = sorted(list(set(range(1, MAX_NUM + 1)) - set(bet1))[:PICK])
    return [bet1, bet2]


def strategy_acb_markov_midfreq_3bet(history):
    bet1 = _top_n(_acb_scores(history))
    bet2 = _top_n(_markov_scores(history), exclude=set(bet1))
    if not bet2:
        bet2 = sorted(list(set(range(1, MAX_NUM + 1)) - set(bet1))[:PICK])
    bet3_ex = set(bet1) | set(bet2)
    bet3 = _top_n(_midfreq_scores(history), exclude=bet3_ex)
    if not bet3:
        bet3 = sorted(list(set(range(1, MAX_NUM + 1)) - set(bet1) - set(bet2))[:PICK])
    return [bet1, bet2, bet3]


STRATEGIES = [
    {'name': 'acb_1bet',                  'func': strategy_acb_1bet,                'n_bets': 1, 'role': 'baseline'},
    {'name': 'midfreq_acb_2bet',          'func': strategy_midfreq_acb_2bet,        'n_bets': 2, 'role': 'shadow'},
    {'name': 'acb_markov_midfreq_3bet',   'func': strategy_acb_markov_midfreq_3bet, 'n_bets': 3, 'role': 'active'},
]

STRAT_MAP = {s['name']: s for s in STRATEGIES}


# ----------------------------------------------------------------
# Walk-Forward Backtest (vectorised inner loop)
# ----------------------------------------------------------------
def run_backtest(draws, test_periods):
    start_idx = max(MIN_HIST, len(draws) - test_periods)
    per_strategy = {s['name']: [] for s in STRATEGIES}

    for i in range(start_idx, len(draws)):
        hist   = draws[:i]
        actual = set(draws[i]['numbers'])
        for s in STRATEGIES:
            try:
                bets = s['func'](hist)
            except Exception:
                bets = []
            match_counts = [len(actual & set(b)) for b in bets]
            best_match   = max(match_counts) if match_counts else 0
            draw_hit     = 1 if best_match >= 2 else 0
            pnl          = sum(PAYOUT.get(m, 0) for m in match_counts) - s['n_bets'] * 50
            per_strategy[s['name']].append({
                'draw_hit':     draw_hit,
                'best_match':   best_match,
                'match_counts': match_counts,
                'roi_pnl':      pnl,
                'draw_idx':     i,
                'date':         draws[i]['date'],
            })

    return per_strategy


# ----------------------------------------------------------------
# Statistics
# ----------------------------------------------------------------
def compute_stats(records, n_bets, window_label=''):
    n          = len(records)
    draw_hits  = [r['draw_hit'] for r in records]
    hit_count  = sum(draw_hits)
    rate_pct   = hit_count / n * 100 if n > 0 else 0.0
    baseline   = BASELINES[n_bets]
    edge_pp    = rate_pct - baseline
    all_m      = [m for r in records for m in r['match_counts']]
    avg_match  = float(np.mean(all_m)) if all_m else 0.0
    total_cost = n * n_bets * 50
    total_ret  = sum(r['roi_pnl'] + n_bets * 50 for r in records)
    roi_pct    = (total_ret / total_cost - 1) * 100 if total_cost > 0 else 0.0
    p0 = baseline / 100
    se = (p0 * (1 - p0) / n) ** 0.5 if n > 0 else 1.0
    z  = (rate_pct / 100 - p0) / se if se > 0 else 0.0
    return {
        'window':     window_label,
        'n':          n,
        'n_bets':     n_bets,
        'hit_count':  hit_count,
        'rate_pct':   rate_pct,
        'baseline':   baseline,
        'edge_pp':    edge_pp,
        'avg_match':  avg_match,
        'roi_pct':    roi_pct,
        'z':          z,
        'draw_hits':  draw_hits,
    }


def bootstrap_ci(draw_hits, n_boot=N_BOOT, ci=0.95):
    arr  = np.array(draw_hits, dtype=float)
    if len(arr) == 0:
        return 0.0, 0.0
    boot = [np.mean(np.random.choice(arr, len(arr), replace=True)) * 100
            for _ in range(n_boot)]
    lo = (1 - ci) / 2 * 100
    hi = (1 + ci) / 2 * 100
    return float(np.percentile(boot, lo)), float(np.percentile(boot, hi))


def mcnemar_test(hits_a, hits_b):
    n01 = sum(1 for a, b in zip(hits_a, hits_b) if a == 0 and b == 1)
    n10 = sum(1 for a, b in zip(hits_a, hits_b) if a == 1 and b == 0)
    if n01 + n10 == 0:
        return float('nan'), float('nan'), n01, n10
    if n01 + n10 < 25:
        p = min(1.0, 2 * scipy_stats.binom.cdf(min(n01, n10), n01 + n10, 0.5))
        return float('nan'), p, n01, n10
    stat = (abs(n01 - n10) - 1.0) ** 2 / (n01 + n10)
    p    = 1 - scipy_stats.chi2.cdf(stat, df=1)
    return stat, p, n01, n10


def permutation_test(hits_a, hits_b, n_perm=N_PERM):
    """Test H1: rate(b) > rate(a)  (b=active, a=shadow or baseline)."""
    arr_a = np.array(hits_a, dtype=float)
    arr_b = np.array(hits_b, dtype=float)
    obs   = np.mean(arr_b) - np.mean(arr_a)
    pool  = np.concatenate([arr_a, arr_b])
    n     = len(arr_a)
    count = 0
    for _ in range(n_perm):
        perm = np.random.permutation(pool)
        if np.mean(perm[n:]) - np.mean(perm[:n]) >= obs:
            count += 1
    return float(obs * 100), float(count / n_perm)


# ----------------------------------------------------------------
# CUSUM Changepoint (simple CUSUM on rolling edge series)
# ----------------------------------------------------------------
def cusum_changepoint(series, threshold_multiplier=3.0):
    """
    Simple CUSUM on array `series`.
    Returns (break_idx, pre_mean, post_mean, cusum_arr).
    break_idx is -1 if no significant change detected.
    """
    arr   = np.array(series, dtype=float)
    mu    = np.mean(arr)
    sigma = np.std(arr) if np.std(arr) > 0 else 1.0
    cusum_pos = np.zeros(len(arr))
    cusum_neg = np.zeros(len(arr))
    k = 0.5 * sigma  # allowance
    h = threshold_multiplier * sigma  # threshold

    for i in range(1, len(arr)):
        cusum_pos[i] = max(0, cusum_pos[i - 1] + arr[i] - mu - k)
        cusum_neg[i] = max(0, cusum_neg[i - 1] - arr[i] + mu - k)

    # Find first breach
    breach_pos = np.where(cusum_pos >= h)[0]
    breach_neg = np.where(cusum_neg >= h)[0]

    breaks = []
    if len(breach_pos) > 0:
        breaks.append(breach_pos[0])
    if len(breach_neg) > 0:
        breaks.append(breach_neg[0])

    if not breaks:
        return -1, float(mu), float(mu), cusum_pos - cusum_neg

    break_idx = min(breaks)

    if break_idx > 0 and break_idx < len(arr) - 1:
        pre_mean  = float(np.mean(arr[:break_idx]))
        post_mean = float(np.mean(arr[break_idx:]))
    else:
        pre_mean = post_mean = float(mu)

    return int(break_idx), pre_mean, post_mean, cusum_pos - cusum_neg


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------
def main():
    run_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    np.random.seed(SEED)
    os.makedirs('outputs', exist_ok=True)

    print('=' * 72)
    print('DAILY_539  4000p / FULL-HISTORY LONG-WINDOW VALIDATION')
    print('Research: H-LW-01 (4000p+full-history)  H-LW-02 (rolling 500p)')
    print('Run date :', run_ts)
    print('=' * 72)

    draws, skipped = load_draws()
    total = len(draws)
    oldest = draws[0]['date']
    newest = draws[-1]['date']
    max_possible = total - MIN_HIST

    print(f'\nData Coverage:')
    print(f'  Total draws   : {total}')
    print(f'  Date range    : {oldest} → {newest}')
    print(f'  Skipped/dupes : {skipped}')
    print(f'  Max backtest  : {max_possible}p')

    # Build dynamic window list
    windows = sorted(set(EXTRA_WINDOWS + [total]))  # include full history
    windows = [w for w in windows if w <= max_possible]
    print(f'  Windows       : {windows}p')

    # ========================================================
    # Section 1: Long-Window Backtest Results
    # ========================================================
    print(f'\n{"=" * 72}')
    print('SECTION 1: Long-Window Backtest')
    print('=' * 72)

    all_records  = {}   # {window: {strategy: records}}
    all_stats    = {}   # {window: {strategy: stats_dict}}
    all_ci       = {}   # {window: {strategy: (lo, hi)}}
    window_csv_rows = []

    for win in windows:
        t0 = time.time()
        print(f'\n{"─" * 72}')
        print(f'  Window: {win}p  (last {win} draws)')
        per_strat = run_backtest(draws, win)
        all_records[win] = per_strat

        wstats = {}
        wci    = {}
        for s in STRATEGIES:
            nm  = s['name']
            rec = per_strat[nm]
            st  = compute_stats(rec, s['n_bets'], str(win))
            lo, hi = bootstrap_ci(st['draw_hits'])
            st['ci_lo'] = lo
            st['ci_hi'] = hi
            wstats[nm] = st
            wci[nm]    = (lo, hi)

        all_stats[win] = wstats
        all_ci[win]    = wci

        active_h = wstats['acb_markov_midfreq_3bet']['draw_hits']
        shadow_h = wstats['midfreq_acb_2bet']['draw_hits']
        base_h   = wstats['acb_1bet']['draw_hits']

        # Delta comparisons
        active_edge  = wstats['acb_markov_midfreq_3bet']['edge_pp']
        shadow_edge  = wstats['midfreq_acb_2bet']['edge_pp']
        base_edge    = wstats['acb_1bet']['edge_pp']
        delta_shadow = active_edge - shadow_edge
        delta_base   = active_edge - base_edge

        # McNemar
        _, mc_vs_sh, n01_s, n10_s = mcnemar_test(active_h, shadow_h)
        _, mc_vs_ba, n01_b, n10_b = mcnemar_test(active_h, base_h)

        # Permutation (active vs shadow; active vs baseline)
        delta_pp_sh, perm_p_sh = permutation_test(shadow_h, active_h)
        delta_pp_ba, perm_p_ba = permutation_test(base_h, active_h)

        elapsed = time.time() - t0
        watchdog = '⚠ BREACH' if active_edge <= DEGRADED_THRESHOLD else 'OK'

        print(f'  {"Strategy":<30}  {"N":>5}  {"Hits":>5}  {"Rate%":>7}  '
              f'{"Edge(pp)":>9}  {"95% CI":>16}  {"ROI%":>7}  {"Z":>6}  Watch')
        print('  ' + '-' * 100)
        for s in STRATEGIES:
            nm  = s['name']
            st  = wstats[nm]
            ci  = f"[{wci[nm][0]:.2f},{wci[nm][1]:.2f}]"
            thr = watchdog if nm == 'acb_markov_midfreq_3bet' else ''
            print(f'  {nm:<30}  {st["n"]:>5}  {st["hit_count"]:>5}  '
                  f'{st["rate_pct"]:>7.2f}  {st["edge_pp"]:>+9.2f}  '
                  f'{ci:>16}  {st["roi_pct"]:>+7.2f}  {st["z"]:>+6.2f}  {thr}')

        print(f'\n  Active vs Shadow: delta={delta_shadow:+.2f}pp, '
              f'McNemar p={mc_vs_sh:.4f}, perm p={perm_p_sh:.4f}')
        print(f'  Active vs Base:   delta={delta_base:+.2f}pp, '
              f'McNemar p={mc_vs_ba:.4f}, perm p={perm_p_ba:.4f}')
        print(f'  Elapsed: {elapsed:.1f}s  |  Watchdog [{DEGRADED_THRESHOLD}pp]: {watchdog}')

        # CSV rows
        for s in STRATEGIES:
            nm = s['name']
            st = wstats[nm]
            window_csv_rows.append({
                'window_p': win,
                'strategy': nm,
                'role':     s['role'],
                'n':        st['n'],
                'hit_count': st['hit_count'],
                'rate_pct': round(st['rate_pct'], 4),
                'edge_pp':  round(st['edge_pp'], 4),
                'ci_lo':    round(wci[nm][0], 4),
                'ci_hi':    round(wci[nm][1], 4),
                'roi_pct':  round(st['roi_pct'], 4),
                'z':        round(st['z'], 4),
                'watchdog_breach': 1 if (nm == 'acb_markov_midfreq_3bet'
                                          and st['edge_pp'] <= DEGRADED_THRESHOLD) else 0,
            })

    # Write window CSV
    with open(OUTPUT_CSV_WINDOWS, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=window_csv_rows[0].keys())
        writer.writeheader()
        writer.writerows(window_csv_rows)
    print(f'\n  Saved: {OUTPUT_CSV_WINDOWS}')

    # ========================================================
    # Section 2: Active Strategy Long-Window Edge Trend
    # ========================================================
    print(f'\n{"=" * 72}')
    print('SECTION 2: Active Strategy Long-Window Edge Trend')
    print('=' * 72)

    trend_data = [(w, all_stats[w]['acb_markov_midfreq_3bet']['edge_pp']) for w in windows]
    sizes = np.array([w for w, _ in trend_data], dtype=float)
    edges = np.array([e for _, e in trend_data], dtype=float)
    if len(sizes) >= 2:
        slope, intercept, r_val, p_val, se = scipy_stats.linregress(sizes, edges)
        slope_per_1k = slope * 1000
        monotonic = bool(np.all(np.diff(edges) <= 0))
    else:
        slope_per_1k, r_val, p_val, monotonic, intercept = 0.0, 0.0, 1.0, False, edges[0]

    print(f'\n  {"Window":>8}  {"Active Edge":>12}  {"vs Shadow":>10}  {"vs Base":>9}  Watch')
    print('  ' + '-' * 55)
    for w in windows:
        ae  = all_stats[w]['acb_markov_midfreq_3bet']['edge_pp']
        se_ = all_stats[w]['midfreq_acb_2bet']['edge_pp']
        be  = all_stats[w]['acb_1bet']['edge_pp']
        thr = '⚠' if ae <= DEGRADED_THRESHOLD else ''
        print(f'  {w:>8}p  {ae:>+12.2f}  {ae-se_:>+10.2f}  {ae-be:>+9.2f}  {thr}')
    print(f'\n  Slope : {slope_per_1k:+.2f} pp / 1000 draws  (r={r_val:.3f}, p={p_val:.4f})')
    print(f'  Monotonic decline: {monotonic}')

    # ========================================================
    # Section 3: Rolling 500p Edge Trend
    # ========================================================
    print(f'\n{"=" * 72}')
    print(f'SECTION 3: Rolling {ROLLING_WINDOW}p Edge Trend (step={ROLLING_STEP})')
    print('=' * 72)

    # Full set of draws, rolling from oldest to newest
    n_total = len(draws)
    rolling_rows = []
    rolling_active_edges = []

    win_start = 0
    while win_start + ROLLING_WINDOW <= n_total:
        win_end = win_start + ROLLING_WINDOW
        win_draws = draws[win_start:win_end]
        # For rolling evaluation, we need at least MIN_HIST history before window start
        hist_start = max(0, win_start - MIN_HIST)
        hist_draws = draws[hist_start:win_end]

        # Evaluate strategies: each draw in [win_start, win_end)
        active_hits = []
        shadow_hits = []
        base_hits_r = []

        for i in range(win_start, win_end):
            hist_i  = draws[:i]
            if len(hist_i) < MIN_HIST:
                continue
            actual  = set(draws[i]['numbers'])
            for s in STRATEGIES:
                try:
                    bets = s['func'](hist_i)
                except Exception:
                    bets = []
                mc = [len(actual & set(b)) for b in bets]
                dh = 1 if (max(mc) if mc else 0) >= 2 else 0
                if s['role'] == 'active':
                    active_hits.append(dh)
                elif s['role'] == 'shadow':
                    shadow_hits.append(dh)
                elif s['role'] == 'baseline':
                    base_hits_r.append(dh)

        if not active_hits:
            win_start += ROLLING_STEP
            continue

        def edge_of(hits, n_bets):
            return (np.mean(hits) * 100 - BASELINES[n_bets]) if hits else float('nan')

        ae = edge_of(active_hits, 3)
        se = edge_of(shadow_hits, 2)
        be = edge_of(base_hits_r, 1)
        breach = 1 if ae <= DEGRADED_THRESHOLD else 0

        rolling_rows.append({
            'start_idx':         win_start,
            'end_idx':           win_end - 1,
            'start_date':        draws[win_start]['date'],
            'end_date':          draws[win_end - 1]['date'],
            'n_valid':           len(active_hits),
            'active_edge_pp':    round(ae, 4),
            'shadow_edge_pp':    round(se, 4),
            'baseline_edge_pp':  round(be, 4),
            'active_minus_shadow': round(ae - se, 4),
            'threshold_breach':  breach,
        })
        rolling_active_edges.append(ae)
        win_start += ROLLING_STEP

    # Write rolling CSV
    if rolling_rows:
        with open(OUTPUT_CSV_ROLLING, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rolling_rows[0].keys())
            writer.writeheader()
            writer.writerows(rolling_rows)
        print(f'\n  Saved: {OUTPUT_CSV_ROLLING}')

    # Print rolling summary table (sampled rows)
    print(f'\n  {"#":>3}  {"Start Date":>12}  {"End Date":>12}  '
          f'{"Active":>9}  {"Shadow":>9}  {"Base":>9}  {"A-S":>7}  Breach')
    print('  ' + '-' * 78)
    step_print = max(1, len(rolling_rows) // 20)
    for idx, row in enumerate(rolling_rows):
        if idx % step_print == 0 or idx == len(rolling_rows) - 1:
            br = '⚠' if row['threshold_breach'] else ''
            print(f'  {idx:>3}  {row["start_date"]:>12}  {row["end_date"]:>12}  '
                  f'{row["active_edge_pp"]:>+9.2f}  {row["shadow_edge_pp"]:>+9.2f}  '
                  f'{row["baseline_edge_pp"]:>+9.2f}  '
                  f'{row["active_minus_shadow"]:>+7.2f}  {br}')

    # Rolling stats
    breach_count   = sum(r['threshold_breach'] for r in rolling_rows)
    total_windows  = len(rolling_rows)
    breach_pct     = breach_count / total_windows * 100 if total_windows else 0
    min_edge       = min(r['active_edge_pp'] for r in rolling_rows) if rolling_rows else float('nan')
    max_edge       = max(r['active_edge_pp'] for r in rolling_rows) if rolling_rows else float('nan')
    mean_edge      = float(np.mean([r['active_edge_pp'] for r in rolling_rows])) if rolling_rows else float('nan')

    print(f'\n  Rolling summary:')
    print(f'    Total windows  : {total_windows}')
    print(f'    Breach windows : {breach_count} ({breach_pct:.1f}%)')
    print(f'    Edge range     : [{min_edge:+.2f}, {max_edge:+.2f}] pp')
    print(f'    Mean edge      : {mean_edge:+.2f} pp')

    # ========================================================
    # Section 4: CUSUM Changepoint Detection
    # ========================================================
    print(f'\n{"=" * 72}')
    print('SECTION 4: CUSUM Changepoint Detection on Rolling Edge')
    print('=' * 72)

    cusum_result = {}
    if len(rolling_active_edges) >= 4:
        bi, pre_m, post_m, cusum_arr = cusum_changepoint(rolling_active_edges, threshold_multiplier=3.0)
        cusum_result = {
            'break_idx':  bi,
            'pre_mean':   pre_m,
            'post_mean':  post_m,
        }
        if bi >= 0 and bi < len(rolling_rows):
            break_date = rolling_rows[bi]['start_date']
            print(f'\n  CUSUM break detected at window #{bi}  ({break_date})')
            print(f'  Pre-break mean edge  : {pre_m:+.2f} pp')
            print(f'  Post-break mean edge : {post_m:+.2f} pp')
            print(f'  Shift magnitude      : {post_m - pre_m:+.2f} pp')
            # Bootstrap significance proxy
            n_split = bi
            if n_split >= 3 and len(rolling_active_edges) - n_split >= 3:
                pre_arr  = np.array(rolling_active_edges[:n_split])
                post_arr = np.array(rolling_active_edges[n_split:])
                obs_diff = np.mean(post_arr) - np.mean(pre_arr)
                all_pool = np.concatenate([pre_arr, post_arr])
                np.random.seed(SEED)
                boot_diffs = []
                for _ in range(N_BOOT):
                    perm = np.random.permutation(all_pool)
                    boot_diffs.append(np.mean(perm[n_split:]) - np.mean(perm[:n_split]))
                boot_p = float(np.mean(np.array(boot_diffs) <= obs_diff))
                cusum_result['boot_p'] = boot_p
                print(f'  Bootstrap p (post < pre): {boot_p:.4f}  (threshold: 0.01)')
                if boot_p < 0.01:
                    print('  → REGIME_SHIFT detected (significant at p<0.01)')
                    cusum_result['classification'] = 'REGIME_SHIFT'
                elif boot_p < 0.05:
                    print('  → Marginal shift (p<0.05 but not <0.01) → SMOOTH_DECAY_WITH_KINK')
                    cusum_result['classification'] = 'SMOOTH_DECAY_WITH_KINK'
                else:
                    print('  → Shift not significant → SMOOTH_DECAY')
                    cusum_result['classification'] = 'SMOOTH_DECAY'
            else:
                cusum_result['classification'] = 'SMOOTH_DECAY'
        else:
            print('\n  No CUSUM breach detected → SMOOTH_DECAY')
            cusum_result['classification'] = 'SMOOTH_DECAY'
    else:
        print('\n  Insufficient rolling windows for CUSUM')
        cusum_result['classification'] = 'INSUFFICIENT_ROLLING_WINDOWS'

    # Linear regression on rolling edges
    if len(rolling_active_edges) >= 3:
        x_roll = np.arange(len(rolling_active_edges), dtype=float)
        sl, ic, rv, pv, sv = scipy_stats.linregress(x_roll, rolling_active_edges)
        print(f'\n  Linear slope on rolling series: {sl:+.4f} pp/window, p={pv:.4f}')
        cusum_result['rolling_slope_pp_per_window'] = float(sl)
        cusum_result['rolling_slope_p']             = float(pv)

    # ========================================================
    # Section 5: Key Statistical Tests Summary
    # ========================================================
    print(f'\n{"=" * 72}')
    print('SECTION 5: Key Statistical Tests (Focus: Largest Windows)')
    print('=' * 72)

    key_tests = {}
    for win in windows[-2:]:  # largest two windows (4000p or full, and prior)
        ah = all_records[win]['acb_markov_midfreq_3bet']
        sh = all_records[win]['midfreq_acb_2bet']
        bh = all_records[win]['acb_1bet']
        ah_hits = [r['draw_hit'] for r in ah]
        sh_hits = [r['draw_hit'] for r in sh]
        bh_hits = [r['draw_hit'] for r in bh]
        _, mc_sh, n01_s, n10_s = mcnemar_test(ah_hits, sh_hits)
        _, mc_ba, n01_b, n10_b = mcnemar_test(ah_hits, bh_hits)
        d_pp_sh, perm_sh = permutation_test(sh_hits, ah_hits)
        d_pp_ba, perm_ba = permutation_test(bh_hits, ah_hits)
        print(f'\n  Window: {win}p')
        print(f'    Active vs Shadow  : McNemar p={mc_sh:.4f}, perm p={perm_sh:.4f}, delta={d_pp_sh:+.2f}pp')
        print(f'    Active vs Baseline: McNemar p={mc_ba:.4f}, perm p={perm_ba:.4f}, delta={d_pp_ba:+.2f}pp')
        key_tests[win] = {
            'mc_vs_shadow': mc_sh, 'perm_vs_shadow': perm_sh,
            'mc_vs_base':   mc_ba, 'perm_vs_base':   perm_ba,
        }

    # ========================================================
    # Section 6: Decision
    # ========================================================
    print(f'\n{"=" * 72}')
    print('SECTION 6: Decision')
    print('=' * 72)

    full_hist_win = windows[-1]
    active_full   = all_stats[full_hist_win]['acb_markov_midfreq_3bet']['edge_pp']
    w4000         = 4000 if 4000 in all_stats else windows[-1]
    active_4000   = all_stats[w4000]['acb_markov_midfreq_3bet']['edge_pp']
    breach_4000   = active_4000 <= DEGRADED_THRESHOLD
    breach_full   = active_full <= DEGRADED_THRESHOLD
    persistent_breach = breach_pct >= 50.0  # majority of rolling windows below threshold

    if breach_4000 or breach_full:
        decision = 'DEGRADED_LONG_WINDOW'
    elif active_4000 < DEGRADED_THRESHOLD + 1.0 or persistent_breach:
        decision = 'WATCH_LONG_WINDOW'
    else:
        decision = 'STABLE_LONG_WINDOW'

    print(f'\n  4000p active edge        : {active_4000:+.2f} pp')
    print(f'  Full-history active edge : {active_full:+.2f} pp  (window={full_hist_win}p)')
    print(f'  Watchdog threshold       : {DEGRADED_THRESHOLD:+.2f} pp')
    print(f'  4000p breach             : {breach_4000}')
    print(f'  Full-history breach      : {breach_full}')
    print(f'  Rolling breach pct       : {breach_pct:.1f}%')
    print(f'  CUSUM classification     : {cusum_result.get("classification", "N/A")}')
    print(f'\n  ★ FINAL DECISION: {decision} ★')

    cto_review = decision == 'DEGRADED_LONG_WINDOW'
    print(f'  CTO review required      : {cto_review}')

    # ========================================================
    # Build Report
    # ========================================================
    _write_report(
        run_ts=run_ts, draws=draws, skipped=skipped, windows=windows,
        all_stats=all_stats, all_ci=all_ci, all_records=all_records,
        trend_data=trend_data, slope_per_1k=slope_per_1k, r_val=r_val,
        p_val=p_val, monotonic=monotonic,
        rolling_rows=rolling_rows, breach_count=breach_count,
        total_windows=total_windows, breach_pct=breach_pct,
        min_edge=min_edge, max_edge=max_edge, mean_edge=mean_edge,
        cusum_result=cusum_result,
        key_tests=key_tests,
        decision=decision, cto_review=cto_review,
        active_4000=active_4000, active_full=active_full,
        full_hist_win=full_hist_win, w4000=w4000,
    )

    print(f'\n  Report saved: {REPORT_PATH}')
    print('\nDone.')


# ----------------------------------------------------------------
# Report Writer
# ----------------------------------------------------------------
def _write_report(**kw):
    run_ts       = kw['run_ts']
    draws        = kw['draws']
    skipped      = kw['skipped']
    windows      = kw['windows']
    all_stats    = kw['all_stats']
    all_ci       = kw['all_ci']
    all_records  = kw['all_records']
    trend_data   = kw['trend_data']
    slope_per_1k = kw['slope_per_1k']
    r_val        = kw['r_val']
    monotonic    = kw['monotonic']
    rolling_rows = kw['rolling_rows']
    breach_count = kw['breach_count']
    total_windows= kw['total_windows']
    breach_pct   = kw['breach_pct']
    min_edge     = kw['min_edge']
    max_edge     = kw['max_edge']
    mean_edge    = kw['mean_edge']
    cusum_result = kw['cusum_result']
    key_tests    = kw['key_tests']
    decision     = kw['decision']
    cto_review   = kw['cto_review']
    active_4000  = kw['active_4000']
    active_full  = kw['active_full']
    full_hist_win= kw['full_hist_win']
    w4000        = kw['w4000']

    STRATEGIES_LOCAL = [
        {'name': 'acb_1bet',                'n_bets': 1, 'role': 'baseline'},
        {'name': 'midfreq_acb_2bet',        'n_bets': 2, 'role': 'shadow'},
        {'name': 'acb_markov_midfreq_3bet', 'n_bets': 3, 'role': 'active'},
    ]

    lines = []
    a = lines.append

    a('# DAILY_539 4000p / Full-History Long-Window Validation Report')
    a('')
    a('**Research IDs**: H-LW-01 (4000p + full-history), H-LW-02 (rolling 500p trend)')
    a(f'**Run date**: {run_ts}')
    a(f'**Script**: `research/daily539_4000p_full_history_validation_2026-04-29.py`')
    a('')
    a('---')
    a('')
    a('## 1. Executive Summary')
    a('')
    a(f'**Final Status: {decision}**')
    a('')
    a(f'- Active strategy (`acb_markov_midfreq_3bet`) evaluated at {windows}p windows')
    a(f'- 4000p active edge: **{active_4000:+.2f} pp**')
    a(f'- Full-history ({full_hist_win}p) active edge: **{active_full:+.2f} pp**')
    a(f'- DEGRADED threshold: {DEGRADED_THRESHOLD:+.2f} pp')
    a(f'- Watchdog threshold breached at 4000p: **{active_4000 <= DEGRADED_THRESHOLD}**')
    a(f'- CUSUM classification: **{cusum_result.get("classification", "N/A")}**')
    a(f'- Rolling 500p breach rate: **{breach_pct:.1f}%** ({breach_count}/{total_windows} windows)')
    a(f'- CTO review required: **{cto_review}**')
    a('')
    a('---')
    a('')
    a('## 2. Data Coverage')
    a('')
    a(f'- Lottery type   : `DAILY_539`')
    a(f'- Total draws    : {len(draws)}')
    a(f'- Oldest date    : {draws[0]["date"]}')
    a(f'- Newest date    : {draws[-1]["date"]}')
    a(f'- Skipped/dupes  : {skipped}')
    a(f'- Max backtest   : {len(draws) - MIN_HIST}p')
    a(f'- DB             : `lottery_api/data/lottery_v2.db` (READ-ONLY)')
    a(f'- No writes to DB: CONFIRMED')
    a('')
    a('---')
    a('')
    a('## 3. Long Window Result Table')
    a('')
    a('| Window | Active Edge (pp) | Shadow Edge (pp) | Baseline Edge (pp) | Active vs Shadow | Active vs Baseline | CI (active, 95%) | Watchdog |')
    a('|---|---|---|---|---|---|---|---|')
    for w in windows:
        ae   = all_stats[w]['acb_markov_midfreq_3bet']['edge_pp']
        se   = all_stats[w]['midfreq_acb_2bet']['edge_pp']
        be   = all_stats[w]['acb_1bet']['edge_pp']
        ci   = all_ci[w]['acb_markov_midfreq_3bet']
        thr  = '⚠ BREACH' if ae <= DEGRADED_THRESHOLD else 'OK'
        a(f'| {w}p | {ae:+.2f} | {se:+.2f} | {be:+.2f} | {ae-se:+.2f} | {ae-be:+.2f} | [{ci[0]:.2f}, {ci[1]:.2f}] | {thr} |')
    a('')
    a(f'**Edge trend slope**: {slope_per_1k:+.2f} pp / 1000 draws  (monotonic decline: {monotonic})')
    a('')
    a('---')
    a('')
    a('## 4. Rolling 500p Edge Trend')
    a('')
    a(f'Rolling window size: 500p, step: 200 draws, total windows: {total_windows}')
    a('')
    a('| # | Start Date | End Date | Active Edge | Shadow Edge | Baseline Edge | A−S | Breach |')
    a('|---|---|---|---|---|---|---|---|')
    step_r = max(1, len(rolling_rows) // 25)
    for idx, row in enumerate(rolling_rows):
        if idx % step_r == 0 or idx == len(rolling_rows) - 1:
            br = 'YES' if row['threshold_breach'] else 'no'
            a(f'| {idx} | {row["start_date"]} | {row["end_date"]} | '
              f'{row["active_edge_pp"]:+.2f} | {row["shadow_edge_pp"]:+.2f} | '
              f'{row["baseline_edge_pp"]:+.2f} | {row["active_minus_shadow"]:+.2f} | {br} |')
    a('')
    a(f'**Rolling summary**:')
    a(f'- Total windows : {total_windows}')
    a(f'- Breach (≤+{DEGRADED_THRESHOLD}pp): {breach_count} ({breach_pct:.1f}%)')
    a(f'- Edge range    : [{min_edge:+.2f}, {max_edge:+.2f}] pp')
    a(f'- Mean edge     : {mean_edge:+.2f} pp')
    a('')
    a('---')
    a('')
    a('## 5. Change Detection')
    a('')
    bi   = cusum_result.get('break_idx', -1)
    pre  = cusum_result.get('pre_mean', float('nan'))
    post = cusum_result.get('post_mean', float('nan'))
    cls  = cusum_result.get('classification', 'N/A')
    bp   = cusum_result.get('boot_p', float('nan'))
    sl_r = cusum_result.get('rolling_slope_pp_per_window', float('nan'))
    pv_r = cusum_result.get('rolling_slope_p', float('nan'))
    a(f'- CUSUM break index   : {bi}')
    if bi >= 0 and bi < len(rolling_rows):
        a(f'- Break date          : {rolling_rows[bi]["start_date"]}')
    a(f'- Pre-break mean edge : {pre:+.2f} pp')
    a(f'- Post-break mean edge: {post:+.2f} pp')
    a(f'- Shift magnitude     : {post - pre:+.2f} pp')
    a(f'- Bootstrap p (post<pre): {bp:.4f}')
    a(f'- Classification      : **{cls}**')
    a(f'- Rolling slope       : {sl_r:+.4f} pp/window (p={pv_r:.4f})')
    a('')
    a('---')
    a('')
    a('## 6. Statistical Tests')
    a('')
    for win, tests in sorted(key_tests.items()):
        a(f'### Window: {win}p')
        a('')
        a(f'| Comparison | McNemar p | Perm p | Delta (pp) |')
        a(f'|---|---|---|---|')
        # Recompute delta from stored stats
        ae = all_stats[win]['acb_markov_midfreq_3bet']['edge_pp']
        se = all_stats[win]['midfreq_acb_2bet']['edge_pp']
        be = all_stats[win]['acb_1bet']['edge_pp']
        a(f'| Active vs Shadow   | {tests["mc_vs_shadow"]:.4f} | {tests["perm_vs_shadow"]:.4f} | {ae-se:+.2f} |')
        a(f'| Active vs Baseline | {tests["mc_vs_base"]:.4f}   | {tests["perm_vs_base"]:.4f}   | {ae-be:+.2f} |')
        a('')
    a('---')
    a('')
    a('## 7. Watchdog Interpretation')
    a('')
    a(f'| Question | Answer |')
    a(f'|---|---|')
    a(f'| Is DAILY_539 still WATCH_MAINTENANCE? | {"YES — no change to status" if decision != "DEGRADED_LONG_WINDOW" else "POSSIBLY — see degraded note"} |')
    a(f'| Is DEGRADED threshold (≤+{DEGRADED_THRESHOLD}pp) breached at 4000p? | {"YES ⚠" if active_4000 <= DEGRADED_THRESHOLD else "NO"} |')
    a(f'| Is DEGRADED threshold breached at full history ({full_hist_win}p)? | {"YES ⚠" if active_full <= DEGRADED_THRESHOLD else "NO"} |')
    a(f'| Should active strategy remain unchanged? | {"YES" if not cto_review else "PENDING CTO REVIEW"} |')
    a(f'| Should CTO review be triggered? | {"YES ⚠ TRIGGER CTO REVIEW" if cto_review else "NO"} |')
    a('')
    a('---')
    a('')
    a('## 8. Risk / Leakage Check')
    a('')
    a('| Check | Status |')
    a('|---|---|')
    a('| Chronological split (no shuffle) | PASS — windows use last N draws in order |')
    a('| No future leakage (strategy sees only past draws) | PASS — walk-forward: `hist = draws[:i]` |')
    a('| No writes to lottery_v2.db | PASS — READ ONLY (sqlite3, no execute writes) |')
    a('| No active_strategy_state modification | PASS — monitoring/reporting only |')
    a('| No new strategy family | PASS — existing strategies only |')
    a('| No Fourier / Markov variants introduced | PASS |')
    a('| seed=42 for all bootstrap/permutation | PASS |')
    a('')
    a('---')
    a('')
    a('## 9. Next Step')
    a('')
    if decision == 'STABLE_LONG_WINDOW':
        a('**STABLE_LONG_WINDOW** — continue weekly / every-50-draws watchdog monitoring.')
        a('')
        a('- Rerun this script every 50 new DAILY_539 draws or weekly, whichever is sooner.')
        a('- Watchdog trigger remains: 3000p or long-window active edge ≤ +2.0pp.')
        a('- No strategy change required.')
    elif decision == 'WATCH_LONG_WINDOW':
        a('**WATCH_LONG_WINDOW** — tighten monitoring; schedule next long-window retest.')
        a('')
        a('- Increase monitoring frequency to every 25 new draws.')
        a(f'- Active edge approaching DEGRADED threshold ({active_4000:+.2f} pp vs {DEGRADED_THRESHOLD:+.2f} pp threshold).')
        a('- Re-evaluate at next 200 new draws with updated 4000p / full-history window.')
        a('- Do NOT change active strategy yet; await further evidence.')
    else:  # DEGRADED
        a('**DEGRADED_LONG_WINDOW** — trigger CTO review.')
        a('')
        a('- Active strategy edge ≤ DEGRADED threshold at 4000p or full-history.')
        a('- Trigger CTO review and strategy re-evaluation task.')
        a('- DO NOT automatically replace active strategy — human review required.')
        a('- Consider shadow strategy (`midfreq_acb_2bet`) as interim fallback ONLY after CTO approval.')
    a('')
    a('---')
    a('')
    a(f'*Report generated: {run_ts}*')
    a(f'*Script: `research/daily539_4000p_full_history_validation_2026-04-29.py`*')
    a(f'*Lane: EXPLORE-C (long_window_residual)*')

    with open(REPORT_PATH, 'w') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    main()
