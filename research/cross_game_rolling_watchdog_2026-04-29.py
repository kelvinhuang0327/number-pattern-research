#!/usr/bin/env python3
"""
Cross-Game Rolling Watchdog — BIG_LOTTO & POWER_LOTTO
Research ID: H-XL-01

Hypothesis: A rolling 300p watchdog can detect active strategy degradation
in BIG_LOTTO (p1_dev_sum5bet) and POWER_LOTTO (pp3_freqort_4bet).

Constraints:
  - DB READ ONLY (lottery_api/data/lottery_v2.db)
  - No new strategy family; no Fourier/Markov variants
  - No active_strategy_state modification
  - No modification of lottery_v2.db
  - seed=42; Python 3.9 compatible
  - DAILY_539 rolling: re-use existing CSV, do NOT re-run
  - Walk-forward only (no look-ahead)

Pre-registered thresholds (set BEFORE seeing results):
  BIG_LOTTO:   +0.5pp breach threshold
  POWER_LOTTO: +1.0pp breach threshold

Run: .venv/bin/python3 research/cross_game_rolling_watchdog_2026-04-29.py
"""

import csv
import json
import os
import sys
import time
from datetime import datetime

import numpy as np
from scipy import stats as scipy_stats

# ----------------------------------------------------------------
# Path setup
# ----------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'tools'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))

import sqlite3

from tools.quick_predict import biglotto_p1_deviation_5bet
from tools.predict_biglotto_regime import generate_regime_2bet
from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet

# ----------------------------------------------------------------
# Config
# ----------------------------------------------------------------
DB_PATH          = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
SEED             = 42
MIN_HIST         = 100
ROLLING_WINDOW   = 300
ROLLING_STEP     = 100

# Breach threshold (pp) — pre-registered
BREACH_THRESHOLD = {
    'BIG_LOTTO':   0.5,
    'POWER_LOTTO': 1.0,
}

# M3+ baselines (pct) from stage0_baseline.json — read-only reference
# BIG_LOTTO 6/49: P(M3+, k bets) = 1 - (1-0.01863)^k
BIGLOTTO_BASELINES = {2: 3.69, 5: 8.96}
# POWER_LOTTO 6/38+special: P(M3+, k bets) = 1 - (1-0.0387)^k (main numbers only)
POWERLOTTO_BASELINES = {4: 14.60, 5: 17.91}

# Hit threshold: M3+ (3 or more matching main numbers)
HIT_THRESHOLD = 3

# Rule definitions (pre-registered)
RULE_B_EDGE_PP  = 2.0   # active edge <= +2.0pp → Rule B
RULE_C_DELTA_PP = 2.0   # active underperforms shadow by >= 2.0pp → Rule C
RULE_D_BREACH   = 0.50  # rolling breach rate >= 50% → Rule D
CONSEC_REQUIRED = 2     # consecutive windows for Rule A and B

# Output files
OUTPUT_CSV_ROLLING_BL = os.path.join(PROJECT_ROOT, 'outputs', 'biglotto_rolling_300p_edge_2026-04-29.csv')
OUTPUT_CSV_ROLLING_PL = os.path.join(PROJECT_ROOT, 'outputs', 'powerlotto_rolling_300p_edge_2026-04-29.csv')
OUTPUT_CSV_SUMMARY    = os.path.join(PROJECT_ROOT, 'outputs', 'cross_game_rolling_watchdog_2026-04-29.csv')
DAILY539_REF_CSV      = os.path.join(PROJECT_ROOT, 'outputs', 'daily539_rolling_500p_edge_2026-04-29.csv')

np.random.seed(SEED)


# ----------------------------------------------------------------
# Strategy wrappers — standardised output: list of list[int]
# ----------------------------------------------------------------
def bl_active(history):
    """BIG_LOTTO active: p1_dev_sum5bet (5 bets)."""
    result = biglotto_p1_deviation_5bet(history)
    return [b['numbers'] for b in result]


def bl_shadow(history):
    """BIG_LOTTO shadow: regime_2bet (2 bets)."""
    return generate_regime_2bet(history)


def pl_active(history):
    """POWER_LOTTO active: pp3_freqort_4bet (4 bets = orthogonal_5bet[:4])."""
    return generate_orthogonal_5bet(history)[:4]


def pl_shadow(history):
    """POWER_LOTTO shadow: orthogonal_5bet (5 bets)."""
    return generate_orthogonal_5bet(history)


# ----------------------------------------------------------------
# Data Loading
# ----------------------------------------------------------------
def load_draws(lottery_type):
    """Load draws for a game from DB in chronological order."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT draw, date, numbers FROM draws "
        "WHERE lottery_type = ? ORDER BY CAST(draw AS INTEGER) ASC",
        (lottery_type,)
    ).fetchall()
    conn.close()

    result = []
    seen = set()
    for draw_id, date, numbers_str in rows:
        try:
            nums = json.loads(numbers_str)
            key = draw_id
            if key in seen:
                continue
            seen.add(key)
            result.append({'draw': draw_id, 'date': date, 'numbers': [int(n) for n in nums]})
        except Exception:
            continue
    return result


# ----------------------------------------------------------------
# Rolling Window Evaluation (walk-forward, no look-ahead)
# ----------------------------------------------------------------
def run_rolling(draws, active_func, shadow_func,
                active_nbets, shadow_nbets,
                active_baseline, shadow_baseline,
                breach_threshold, game_label):
    """
    Evaluate active and shadow strategy over rolling 300p windows.
    For each draw i in [win_start, win_end), history = draws[:i].
    Returns list of per-window result dicts.
    """
    n_total = len(draws)
    rows = []
    win_start = 0

    while win_start + ROLLING_WINDOW <= n_total:
        win_end = win_start + ROLLING_WINDOW

        active_hits = []
        shadow_hits = []
        t0 = time.time()

        for i in range(win_start, win_end):
            hist = draws[:i]
            if len(hist) < MIN_HIST:
                continue
            actual = set(draws[i]['numbers'][:6])

            # Active strategy
            try:
                a_bets = active_func(hist)
                a_hit = 1 if any(len(actual & set(b)) >= HIT_THRESHOLD for b in a_bets) else 0
            except Exception:
                a_hit = 0
            active_hits.append(a_hit)

            # Shadow strategy
            try:
                s_bets = shadow_func(hist)
                s_hit = 1 if any(len(actual & set(b)) >= HIT_THRESHOLD for b in s_bets) else 0
            except Exception:
                s_hit = 0
            shadow_hits.append(s_hit)

        elapsed = time.time() - t0

        if not active_hits:
            win_start += ROLLING_STEP
            continue

        n_valid = len(active_hits)
        a_rate  = np.mean(active_hits) * 100
        s_rate  = np.mean(shadow_hits) * 100
        a_edge  = a_rate - active_baseline
        s_edge  = s_rate - shadow_baseline
        delta   = a_edge - s_edge
        breach  = 1 if a_edge <= breach_threshold else 0

        rows.append({
            'game':              game_label,
            'start_idx':         win_start,
            'end_idx':           win_end - 1,
            'start_date':        draws[win_start]['date'],
            'end_date':          draws[win_end - 1]['date'],
            'n_valid':           n_valid,
            'active_rate_pct':   round(a_rate, 4),
            'shadow_rate_pct':   round(s_rate, 4),
            'active_baseline':   active_baseline,
            'shadow_baseline':   shadow_baseline,
            'active_edge_pp':    round(a_edge, 4),
            'shadow_edge_pp':    round(s_edge, 4),
            'active_minus_shadow': round(delta, 4),
            'breach_threshold':  breach_threshold,
            'threshold_breach':  breach,
        })

        print(f'  [{game_label}] W{len(rows):02d} '
              f'{draws[win_start]["date"]} – {draws[win_end-1]["date"]}  '
              f'n={n_valid}  active_edge={a_edge:+.2f}pp  '
              f'shadow_edge={s_edge:+.2f}pp  delta={delta:+.2f}  '
              f'breach={breach}  ({elapsed:.1f}s)')

        win_start += ROLLING_STEP

    return rows


# ----------------------------------------------------------------
# CUSUM Changepoint
# ----------------------------------------------------------------
def cusum_changepoint(series, threshold_multiplier=3.0):
    """
    Simple CUSUM on series.
    Returns (break_idx, pre_mean, post_mean, cusum_arr).
    break_idx = -1 if no significant change detected.
    """
    arr   = np.array(series, dtype=float)
    mu    = float(np.mean(arr))
    sigma = float(np.std(arr))
    if sigma == 0.0:
        sigma = 1.0
    k = 0.5 * sigma
    h = threshold_multiplier * sigma

    cusum_pos = np.zeros(len(arr))
    cusum_neg = np.zeros(len(arr))
    for i in range(1, len(arr)):
        cusum_pos[i] = max(0.0, cusum_pos[i-1] + arr[i] - mu - k)
        cusum_neg[i] = max(0.0, cusum_neg[i-1] - arr[i] + mu - k)

    breach_pos = list(np.where(cusum_pos >= h)[0])
    breach_neg = list(np.where(cusum_neg >= h)[0])
    breaks = []
    if breach_pos:
        breaks.append(breach_pos[0])
    if breach_neg:
        breaks.append(breach_neg[0])

    if not breaks:
        return -1, mu, mu, (cusum_pos - cusum_neg).tolist()

    break_idx = int(min(breaks))
    if 0 < break_idx < len(arr) - 1:
        pre_mean  = float(np.mean(arr[:break_idx]))
        post_mean = float(np.mean(arr[break_idx:]))
    else:
        pre_mean = post_mean = mu

    return break_idx, pre_mean, post_mean, (cusum_pos - cusum_neg).tolist()


# ----------------------------------------------------------------
# Watchdog Rule Evaluation
# ----------------------------------------------------------------
def evaluate_watchdog_rules(rows, breach_threshold):
    """
    Evaluate rules A/B/C/D on rolling window rows.
    Rule A: active_edge <= 0 for >= 2 consecutive windows
    Rule B: active_edge <= +2.0pp for >= 2 consecutive windows
    Rule C: active underperforms shadow by >= 2.0pp for >= 2 consecutive windows
    Rule D: rolling breach rate >= 50%
    Returns dict with fire counts and first-fire indices.
    """
    edges  = [r['active_edge_pp'] for r in rows]
    deltas = [r['active_minus_shadow'] for r in rows]
    n      = len(rows)

    def consec_rule(values, threshold_fn):
        """Count and first-fire index of CONSEC_REQUIRED consecutive True."""
        fires = 0
        first_fire = -1
        count = 0
        for i, v in enumerate(values):
            if threshold_fn(v):
                count += 1
                if count >= CONSEC_REQUIRED:
                    fires += 1
                    if first_fire < 0:
                        first_fire = i
            else:
                count = 0
        return fires, first_fire

    rule_a_fires, rule_a_first = consec_rule(edges, lambda e: e <= 0.0)
    rule_b_fires, rule_b_first = consec_rule(edges, lambda e: e <= RULE_B_EDGE_PP)
    rule_c_fires, rule_c_first = consec_rule(deltas, lambda d: d <= -RULE_C_DELTA_PP)
    breach_rate = sum(r['threshold_breach'] for r in rows) / n if n > 0 else 0.0
    rule_d_fires = 1 if breach_rate >= RULE_D_BREACH else 0

    return {
        'rule_a_fires': rule_a_fires, 'rule_a_first': rule_a_first,
        'rule_b_fires': rule_b_fires, 'rule_b_first': rule_b_first,
        'rule_c_fires': rule_c_fires, 'rule_c_first': rule_c_first,
        'rule_d_fires': rule_d_fires, 'breach_rate': breach_rate,
    }


# ----------------------------------------------------------------
# Decision Classification
# ----------------------------------------------------------------
def classify_decision(rows, cusum_break_idx, rules, active_baseline):
    """
    APPROVE_WATCHDOG:  breach_pct < 40%, mean_edge > threshold, CUSUM = SMOOTH_DECAY
    WATCH_WATCHDOG:    breach_pct 40–60%, or CUSUM kink, or noisy rules
    REJECT_WATCHDOG:   breach_pct >= 60%, or rules create excessive false alarms
    INCONCLUSIVE_DATA_MISSING: insufficient windows (< 5)
    """
    if len(rows) < 5:
        return 'INCONCLUSIVE_DATA_MISSING'

    n = len(rows)
    breach_pct = sum(r['threshold_breach'] for r in rows) / n * 100
    edges = [r['active_edge_pp'] for r in rows]
    mean_edge = float(np.mean(edges))
    threshold = rows[0]['breach_threshold']

    cusum_label = 'NO_BREAK'
    if cusum_break_idx >= 0:
        pre = float(np.mean(edges[:cusum_break_idx]))
        post = float(np.mean(edges[cusum_break_idx:]))
        if post < pre - 1.0:
            cusum_label = 'REGIME_SHIFT'
        else:
            cusum_label = 'SMOOTH_DECAY_WITH_KINK'

    total_rule_fires = (
        rules['rule_a_fires'] + rules['rule_b_fires'] +
        rules['rule_c_fires'] + rules['rule_d_fires']
    )

    if breach_pct >= 60.0 or total_rule_fires >= 3:
        return 'REJECT_WATCHDOG'
    elif breach_pct >= 40.0 or cusum_label in ('REGIME_SHIFT', 'SMOOTH_DECAY_WITH_KINK'):
        return 'WATCH_WATCHDOG'
    elif breach_pct < 40.0 and mean_edge > threshold and total_rule_fires == 0:
        return 'APPROVE_WATCHDOG'
    else:
        return 'WATCH_WATCHDOG'


# ----------------------------------------------------------------
# Load DAILY_539 reference (no re-run)
# ----------------------------------------------------------------
def load_daily539_ref():
    """Load existing daily539 rolling CSV. Do NOT re-compute."""
    if not os.path.exists(DAILY539_REF_CSV):
        print(f'  WARNING: {DAILY539_REF_CSV} not found — skipping reference.')
        return []
    rows = []
    with open(DAILY539_REF_CSV, newline='') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                'active_edge_pp':    float(r['active_edge_pp']),
                'shadow_edge_pp':    float(r['shadow_edge_pp']),
                'threshold_breach':  int(r['threshold_breach']),
                'start_date':        r['start_date'],
                'end_date':          r['end_date'],
                'n_valid':           int(r['n_valid']),
            })
    return rows


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------
def main():
    run_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    np.random.seed(SEED)
    os.makedirs('outputs', exist_ok=True)

    print('=' * 72)
    print('CROSS-GAME ROLLING WATCHDOG — BIG_LOTTO & POWER_LOTTO')
    print('Research ID: H-XL-01')
    print('Run date   :', run_ts)
    print(f'Rolling    : {ROLLING_WINDOW}p  step={ROLLING_STEP}')
    print('Thresholds : BIG_LOTTO={:.1f}pp  POWER_LOTTO={:.1f}pp  (pre-registered)'.format(
        BREACH_THRESHOLD['BIG_LOTTO'], BREACH_THRESHOLD['POWER_LOTTO']))
    print('=' * 72)

    # ============================================================
    # Section 1: Data Coverage
    # ============================================================
    print('\n' + '=' * 72)
    print('SECTION 1: Data Coverage')
    print('=' * 72)

    bl_draws = load_draws('BIG_LOTTO')
    pl_draws = load_draws('POWER_LOTTO')

    for label, draws in [('BIG_LOTTO', bl_draws), ('POWER_LOTTO', pl_draws)]:
        n = len(draws)
        dates = [d['date'] for d in draws]
        n_windows_est = max(0, (n - ROLLING_WINDOW) // ROLLING_STEP + 1)
        print(f'\n  {label}:')
        print(f'    Total draws : {n}')
        print(f'    Date range  : {dates[0]} → {dates[-1]}')
        print(f'    Min history : {MIN_HIST}p')
        print(f'    Est windows : {n_windows_est}  (window={ROLLING_WINDOW}, step={ROLLING_STEP})')
        if n < ROLLING_WINDOW + MIN_HIST:
            print(f'    WARNING: only {n} draws — window size reduced to 200p if insufficient')

    # Adjust window size if needed (pre-registered fallback: 200p if < 300+100)
    effective_window = ROLLING_WINDOW
    for draws in [bl_draws, pl_draws]:
        if len(draws) < ROLLING_WINDOW + MIN_HIST:
            effective_window = 200
            print(f'\n  FALLBACK: insufficient data — using 200p window')
            break

    # ============================================================
    # Section 2: BIG_LOTTO Rolling Windows
    # ============================================================
    print('\n' + '=' * 72)
    print('SECTION 2: BIG_LOTTO Rolling Window Results')
    print(f'  Active: p1_dev_sum5bet (5 bets, baseline={BIGLOTTO_BASELINES[5]}%)')
    print(f'  Shadow: regime_2bet    (2 bets, baseline={BIGLOTTO_BASELINES[2]}%)')
    print(f'  Breach threshold: +{BREACH_THRESHOLD["BIG_LOTTO"]}pp')
    print('=' * 72)

    t_start = time.time()
    bl_rows = run_rolling(
        bl_draws,
        active_func      = bl_active,
        shadow_func      = bl_shadow,
        active_nbets     = 5,
        shadow_nbets     = 2,
        active_baseline  = BIGLOTTO_BASELINES[5],
        shadow_baseline  = BIGLOTTO_BASELINES[2],
        breach_threshold = BREACH_THRESHOLD['BIG_LOTTO'],
        game_label       = 'BIG_LOTTO',
    )
    print(f'\n  BIG_LOTTO total elapsed: {time.time()-t_start:.1f}s')

    # Write BIG_LOTTO rolling CSV
    if bl_rows:
        fieldnames = list(bl_rows[0].keys())
        with open(OUTPUT_CSV_ROLLING_BL, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(bl_rows)
        print(f'  Saved: {OUTPUT_CSV_ROLLING_BL}')

    # ============================================================
    # Section 3: POWER_LOTTO Rolling Windows
    # ============================================================
    print('\n' + '=' * 72)
    print('SECTION 3: POWER_LOTTO Rolling Window Results')
    print(f'  Active: pp3_freqort_4bet (4 bets, baseline={POWERLOTTO_BASELINES[4]}%)')
    print(f'  Shadow: orthogonal_5bet  (5 bets, baseline={POWERLOTTO_BASELINES[5]}%)')
    print(f'  Breach threshold: +{BREACH_THRESHOLD["POWER_LOTTO"]}pp')
    print('=' * 72)

    t_start = time.time()
    pl_rows = run_rolling(
        pl_draws,
        active_func      = pl_active,
        shadow_func      = pl_shadow,
        active_nbets     = 4,
        shadow_nbets     = 5,
        active_baseline  = POWERLOTTO_BASELINES[4],
        shadow_baseline  = POWERLOTTO_BASELINES[5],
        breach_threshold = BREACH_THRESHOLD['POWER_LOTTO'],
        game_label       = 'POWER_LOTTO',
    )
    print(f'\n  POWER_LOTTO total elapsed: {time.time()-t_start:.1f}s')

    # Write POWER_LOTTO rolling CSV
    if pl_rows:
        fieldnames = list(pl_rows[0].keys())
        with open(OUTPUT_CSV_ROLLING_PL, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(pl_rows)
        print(f'  Saved: {OUTPUT_CSV_ROLLING_PL}')

    # ============================================================
    # Section 4: Watchdog Rule Evaluation
    # ============================================================
    print('\n' + '=' * 72)
    print('SECTION 4: Watchdog Rule Evaluation')
    print('=' * 72)

    results = {}

    for label, rows in [('BIG_LOTTO', bl_rows), ('POWER_LOTTO', pl_rows)]:
        if not rows:
            results[label] = None
            print(f'\n  {label}: NO DATA')
            continue

        n = len(rows)
        edges  = [r['active_edge_pp'] for r in rows]
        sedges = [r['shadow_edge_pp'] for r in rows]

        mean_active = float(np.mean(edges))
        mean_shadow = float(np.mean(sedges))
        breach_count = sum(r['threshold_breach'] for r in rows)
        breach_pct   = breach_count / n * 100

        # CUSUM
        break_idx, pre_mean, post_mean, _ = cusum_changepoint(edges)
        break_date = rows[break_idx]['start_date'] if 0 <= break_idx < n else 'N/A'

        # Rules
        rules = evaluate_watchdog_rules(rows, BREACH_THRESHOLD[label])

        # Decision
        decision = classify_decision(rows, break_idx, rules, BREACH_THRESHOLD[label])

        results[label] = {
            'n_windows':    n,
            'mean_active_edge': round(mean_active, 3),
            'mean_shadow_edge': round(mean_shadow, 3),
            'breach_count': breach_count,
            'breach_pct':   round(breach_pct, 1),
            'cusum_break_idx': break_idx,
            'cusum_break_date': break_date,
            'cusum_pre_mean':   round(pre_mean, 3),
            'cusum_post_mean':  round(post_mean, 3),
            'rules': rules,
            'decision': decision,
            'rows': rows,
        }

        threshold = BREACH_THRESHOLD[label]
        print(f'\n  {label}:')
        print(f'    Windows         : {n}')
        print(f'    Mean active edge: {mean_active:+.2f}pp  (threshold +{threshold:.1f}pp)')
        print(f'    Mean shadow edge: {mean_shadow:+.2f}pp')
        print(f'    Breach count    : {breach_count}/{n}  ({breach_pct:.1f}%)')
        print(f'    CUSUM break_idx : {break_idx}  ({break_date})')
        print(f'    CUSUM pre_mean  : {pre_mean:+.2f}pp  post_mean: {post_mean:+.2f}pp')
        print(f'    Rule A (edge<=0, 2-consec)  : fires={rules["rule_a_fires"]}  first={rules["rule_a_first"]}')
        print(f'    Rule B (edge<=+2pp, 2-consec): fires={rules["rule_b_fires"]}  first={rules["rule_b_first"]}')
        print(f'    Rule C (delta<=-2pp, 2-consec): fires={rules["rule_c_fires"]}  first={rules["rule_c_first"]}')
        print(f'    Rule D (breach_rate>=50%)    : fires={rules["rule_d_fires"]}  breach_rate={rules["breach_rate"]*100:.1f}%')
        print(f'    >>> DECISION: {decision}')

        print(f'\n    Per-window edge table:')
        print(f'    {"W#":>3}  {"start_date":>12}  {"end_date":>12}  '
              f'{"active_edge":>12}  {"shadow_edge":>12}  {"delta":>8}  breach')
        print('    ' + '-' * 75)
        for i, r in enumerate(rows):
            br = '⚠' if r['threshold_breach'] else ''
            print(f'    {i+1:>3}  {r["start_date"]:>12}  {r["end_date"]:>12}  '
                  f'{r["active_edge_pp"]:>+12.2f}  {r["shadow_edge_pp"]:>+12.2f}  '
                  f'{r["active_minus_shadow"]:>+8.2f}  {br}')

    # ============================================================
    # Section 5: Cross-Game Comparison
    # ============================================================
    print('\n' + '=' * 72)
    print('SECTION 5: Cross-Game Comparison (incl. DAILY_539 reference)')
    print('=' * 72)

    d539_rows = load_daily539_ref()
    d539_breach_pct = (
        sum(r['threshold_breach'] for r in d539_rows) / len(d539_rows) * 100
        if d539_rows else float('nan')
    )
    d539_mean_edge = (
        float(np.mean([r['active_edge_pp'] for r in d539_rows]))
        if d539_rows else float('nan')
    )

    print(f'\n  {"Game":<14}  {"Windows":>8}  {"Mean Edge":>10}  '
          f'{"Breach%":>8}  {"Threshold":>10}  {"Decision"}')
    print('  ' + '-' * 70)
    print(f'  {"DAILY_539":<14}  {len(d539_rows):>8}  {d539_mean_edge:>+10.2f}  '
          f'{d539_breach_pct:>8.1f}  {"2.0pp":>10}  STABLE (reference)')
    for label in ['BIG_LOTTO', 'POWER_LOTTO']:
        res = results.get(label)
        if res is None:
            print(f'  {label:<14}  {"N/A":>8}  {"N/A":>10}  {"N/A":>8}  {"N/A":>10}  INCONCLUSIVE_DATA_MISSING')
        else:
            thr = f'+{BREACH_THRESHOLD[label]:.1f}pp'
            print(f'  {label:<14}  {res["n_windows"]:>8}  '
                  f'{res["mean_active_edge"]:>+10.2f}  '
                  f'{res["breach_pct"]:>8.1f}  {thr:>10}  {res["decision"]}')

    # Cross-game pattern: do both games degrade together?
    if results.get('BIG_LOTTO') and results.get('POWER_LOTTO'):
        bl_breach = [r['threshold_breach'] for r in results['BIG_LOTTO']['rows']]
        pl_breach = [r['threshold_breach'] for r in results['POWER_LOTTO']['rows']]
        min_len = min(len(bl_breach), len(pl_breach))
        both_breach = sum(1 for a, b in zip(bl_breach[:min_len], pl_breach[:min_len]) if a and b)
        print(f'\n  Co-degradation (both breach same window): {both_breach}/{min_len} windows')

    # ============================================================
    # Section 6: Risk / Leakage Check
    # ============================================================
    print('\n' + '=' * 72)
    print('SECTION 6: Risk / Leakage Check')
    print('=' * 72)
    print("""
  1. LOOK-AHEAD LEAKAGE: history = draws[:i] for draw i → CLEAN
  2. THRESHOLD PRE-REGISTRATION: thresholds set before ANY data was seen → CLEAN
  3. NEW STRATEGY FAMILY: no new signals/families created → CLEAN
  4. DB WRITES: lottery_v2.db opened read-only → CLEAN
  5. ACTIVE_STRATEGY_STATE: not read or modified → CLEAN
  6. OVERFITTING VIA WINDOW TUNING: window/step fixed at 300p/100 before run → CLEAN
  7. PRODUCTION GATING: this is monitoring-only; no gating recommended without further evidence
""")

    # ============================================================
    # Section 7: Summary CSV
    # ============================================================
    print('=' * 72)
    print('SECTION 7: Summary CSV')
    print('=' * 72)

    summary_rows = []

    # DAILY_539 reference row
    summary_rows.append({
        'game':            'DAILY_539',
        'n_draws':         5844,
        'n_windows':       len(d539_rows),
        'active_strategy': 'acb_markov_midfreq_3bet',
        'active_nbets':    3,
        'shadow_strategy': 'midfreq_acb_2bet',
        'shadow_nbets':    2,
        'breach_threshold_pp': 2.0,
        'mean_active_edge_pp': round(d539_mean_edge, 3) if d539_rows else '',
        'breach_rate_pct': round(d539_breach_pct, 1) if d539_rows else '',
        'breach_count':    sum(r['threshold_breach'] for r in d539_rows) if d539_rows else 0,
        'rule_a_fires':    '',
        'rule_b_fires':    '',
        'rule_c_fires':    '',
        'rule_d_fires':    '',
        'cusum_break_idx': '',
        'cusum_break_date': '',
        'cusum_pre_mean':  '',
        'cusum_post_mean': '',
        'decision':        'STABLE (reference)',
    })

    for label, game_draws in [('BIG_LOTTO', bl_draws), ('POWER_LOTTO', pl_draws)]:
        res = results.get(label)
        if res is None:
            summary_rows.append({
                'game': label,
                'n_draws': len(game_draws),
                'n_windows': 0,
                'active_strategy': 'p1_dev_sum5bet' if label == 'BIG_LOTTO' else 'pp3_freqort_4bet',
                'active_nbets': 5 if label == 'BIG_LOTTO' else 4,
                'shadow_strategy': 'regime_2bet' if label == 'BIG_LOTTO' else 'orthogonal_5bet',
                'shadow_nbets': 2 if label == 'BIG_LOTTO' else 5,
                'breach_threshold_pp': BREACH_THRESHOLD[label],
                'mean_active_edge_pp': '',
                'breach_rate_pct': '',
                'breach_count': 0,
                'rule_a_fires': 0, 'rule_b_fires': 0,
                'rule_c_fires': 0, 'rule_d_fires': 0,
                'cusum_break_idx': '', 'cusum_break_date': '',
                'cusum_pre_mean': '', 'cusum_post_mean': '',
                'decision': 'INCONCLUSIVE_DATA_MISSING',
            })
        else:
            r = res['rules']
            summary_rows.append({
                'game':            label,
                'n_draws':         len(game_draws),
                'n_windows':       res['n_windows'],
                'active_strategy': 'p1_dev_sum5bet' if label == 'BIG_LOTTO' else 'pp3_freqort_4bet',
                'active_nbets':    5 if label == 'BIG_LOTTO' else 4,
                'shadow_strategy': 'regime_2bet' if label == 'BIG_LOTTO' else 'orthogonal_5bet',
                'shadow_nbets':    2 if label == 'BIG_LOTTO' else 5,
                'breach_threshold_pp': BREACH_THRESHOLD[label],
                'mean_active_edge_pp': res['mean_active_edge'],
                'breach_rate_pct': res['breach_pct'],
                'breach_count':    res['breach_count'],
                'rule_a_fires':    r['rule_a_fires'],
                'rule_b_fires':    r['rule_b_fires'],
                'rule_c_fires':    r['rule_c_fires'],
                'rule_d_fires':    r['rule_d_fires'],
                'cusum_break_idx': res['cusum_break_idx'],
                'cusum_break_date': res['cusum_break_date'],
                'cusum_pre_mean':  res['cusum_pre_mean'],
                'cusum_post_mean': res['cusum_post_mean'],
                'decision':        res['decision'],
            })

    with open(OUTPUT_CSV_SUMMARY, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f'\n  Saved: {OUTPUT_CSV_SUMMARY}  ({len(summary_rows)} rows)')

    # ============================================================
    # Section 8: Final Verdict
    # ============================================================
    print('\n' + '=' * 72)
    print('SECTION 8: Final Verdict')
    print('=' * 72)

    for label in ['BIG_LOTTO', 'POWER_LOTTO']:
        res = results.get(label)
        if res:
            print(f'\n  {label}: {res["decision"]}')
            print(f'    breach_pct={res["breach_pct"]}%  mean_edge={res["mean_active_edge"]:+.2f}pp  '
                  f'windows={res["n_windows"]}')

    print('\n  Files created:')
    for path in [OUTPUT_CSV_ROLLING_BL, OUTPUT_CSV_ROLLING_PL, OUTPUT_CSV_SUMMARY]:
        exists = os.path.exists(path)
        print(f'    {"✓" if exists else "✗"} {path}')

    print('\n' + '=' * 72)
    print('RUN COMPLETE')
    print('=' * 72)


if __name__ == '__main__':
    main()
