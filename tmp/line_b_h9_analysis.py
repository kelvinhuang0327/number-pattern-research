#!/usr/bin/env python3
"""
Line B: POWER_LOTTO H9 Pure MidFreq 2bet McNemar Promotion Analysis
Runs full OOS backtest, McNemar test vs midfreq_fourier_2bet baseline,
permutation test, power analysis, and generates promotion decision report.

Outputs:
  data/h9_strategy_spec.json
  data/h9_vs_midfreq_full_backtest.jsonl
  data/h9_mcnemar_report.json
"""
import sys, os, json, sqlite3, random, math
from datetime import datetime
from collections import Counter

ROOT = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'lottery_api'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

DB_PATH  = os.path.join(ROOT, 'lottery_api/data/lottery_v2.db')
DATA_DIR = os.path.join(ROOT, 'data')

# ──────────────────────────────────────────────
# BASELINES
# ──────────────────────────────────────────────
BASELINE_PL_2BET = 0.0759   # POWER_LOTTO M3+ 2注
MIN_HIT_PL = 3               # M3+

# ──────────────────────────────────────────────
# Previous H9 metrics from L93 (for reference)
# ──────────────────────────────────────────────
PREV_H9 = {
    'perm_p': 0.030,
    'mcnemar_net': 25,
    'mcnemar_p': 0.119,
    'e30p': 0.0241, 'e100p': 0.0041, 'e300p': 0.0041, 'e1500p': 0.0128,
    'retest_condition': 'McNemar net>=32 AND p<0.05 at draw 115000122',
    'retest_draw': '115000122',
}

# ──────────────────────────────────────────────
# H9 Pure MidFreq 2bet implementation
# ──────────────────────────────────────────────
def pure_midfreq_2bet(history):
    """
    H9 Pure MidFreq 2注:
    - 使用近100期最接近期望頻率的12個號碼
    - bet1 = top 6 mid_scores (sorted)
    - bet2 = next 6 (sorted)
    純 MidFreq，不使用 Fourier
    """
    from tools.power_midfreq_fourier import _midfreq_scores
    mid_scores = _midfreq_scores(history, window=100)
    # Sort by score descending
    ranked = sorted(range(1, 39), key=lambda n: -mid_scores.get(n, 0))
    bet1 = sorted(ranked[:6])
    bet2 = sorted(ranked[6:12])
    return [bet1, bet2]

# ──────────────────────────────────────────────
# Helper: load draws
# ──────────────────────────────────────────────
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

def check_m3plus(bets, actual):
    actual_set = set(actual)
    for bet in bets:
        if sum(1 for n in bet if n in actual_set) >= MIN_HIT_PL:
            return True
    return False

# ──────────────────────────────────────────────
# B1: H9 strategy spec
# ──────────────────────────────────────────────
def b1_spec():
    print('\n=== B1: H9 Strategy Spec ===')
    spec = {
        'strategy_id': 'H9',
        'name': 'Pure MidFreq 2bet',
        'lottery_type': 'POWER_LOTTO',
        'n_bets': 2,
        'description': '近100期最接近期望頻率的12個號碼分2注 (純MidFreq，不使用Fourier)',
        'implementation': {
            'score_function': '_midfreq_scores(window=100)',
            'bet1': 'top 6 mid_scores (sorted)',
            'bet2': 'next 6 mid_scores (sorted)',
            'no_fourier': True,
        },
        'baseline_strategy': 'midfreq_fourier_2bet',
        'baseline_m3plus_2bet': BASELINE_PL_2BET,
        'previous_validation': PREV_H9,
        'promotion_conditions': {
            'mcnemar_p': '< 0.05',
            'mcnemar_net': '> 0 (H9 strictly better)',
            'perm_p': '< 0.05',
            'all_windows_positive': True,
            'new_edge_vs_baseline': 'H9 edge_1500p > midfreq_fourier_2bet edge_1500p',
            'ALL_MUST_PASS': True,
        },
        'retest_draw': PREV_H9['retest_draw'],
        'generated_at': datetime.now().isoformat(),
    }
    out_path = os.path.join(DATA_DIR, 'h9_strategy_spec.json')
    with open(out_path, 'w') as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)
    print(f'  Saved: {out_path}')
    return spec

# ──────────────────────────────────────────────
# B2: Full OOS backtest (anti-leakage)
# ──────────────────────────────────────────────
def b2_backtest(draws):
    print('\n=== B2: H9 vs midfreq_fourier Full OOS Backtest ===')
    from tools.power_midfreq_fourier import midfreq_fourier_2bet

    total = len(draws)
    # Full history from idx 50 (need at least 50 for window functions)
    start = 50
    print(f'  POWER_LOTTO total: {total}. Running from idx {start} (draw {draws[start]["draw"]}) to {draws[-1]["draw"]}')

    h9_errors = mf_errors = 0
    records = []

    out_path = os.path.join(DATA_DIR, 'h9_vs_midfreq_full_backtest.jsonl')
    with open(out_path, 'w', encoding='utf-8') as out_file:
        for idx in range(start, total):
            hist = draws[:idx]
            target = draws[idx]
            actual = target['numbers']

            # H9 Pure MidFreq
            try:
                h9_bets = pure_midfreq_2bet(hist)
                h9_hit = check_m3plus(h9_bets, actual)
            except Exception as e:
                h9_hit = False
                h9_errors += 1

            # midfreq_fourier_2bet
            try:
                mf_bets = midfreq_fourier_2bet(hist)
                mf_hit = check_m3plus(mf_bets, actual)
            except Exception as e:
                mf_hit = False
                mf_errors += 1

            rec = {
                'draw': target['draw'],
                'date': target['date'],
                'h9_hit': h9_hit,
                'mf_hit': mf_hit,
            }
            records.append(rec)
            out_file.write(json.dumps(rec) + '\n')

            if (idx - start + 1) % 200 == 0:
                print(f'    Progress: {idx - start + 1}/{total - start}')

    print(f'  Done. Records: {len(records)}, H9 errors: {h9_errors}, MF errors: {mf_errors}')
    print(f'  Output: {out_path}')
    return records

# ──────────────────────────────────────────────
# B3: McNemar + Permutation test
# ──────────────────────────────────────────────
def mcnemar_exact_p(b, c):
    """Exact McNemar test p-value (two-tailed via binomial)."""
    from math import comb
    n = b + c
    if n == 0:
        return 1.0
    # p = P(X <= min(b,c)) + P(X >= max(b,c)) under H0: p=0.5
    lo = min(b, c)
    p = 0.0
    for k in range(lo + 1):
        p += comb(n, k) * (0.5 ** n)
    p = min(1.0, 2 * p)
    return p

def permutation_test_edge(records, metric_key='h9_hit', n_perm=10000, seed=42):
    """Test if H9 edge is significantly > random (null: edge=0)."""
    random.seed(seed)
    hits = [r[metric_key] for r in records]
    obs_rate = sum(hits) / len(hits)
    obs_edge = obs_rate - BASELINE_PL_2BET

    count_ge = 0
    n = len(hits)
    for _ in range(n_perm):
        # Shuffle hits under null
        shuffled = random.sample(hits, n)
        perm_edge = sum(shuffled) / n - BASELINE_PL_2BET
        if perm_edge >= obs_edge:
            count_ge += 1

    p = count_ge / n_perm
    return obs_edge, p

def compute_windows_pl(records, metric_key='h9_hit'):
    """Compute edge at 30p, 100p, 300p, 1500p, all-time windows."""
    n = len(records)
    result = {}
    for w_name, w in [('30p', 30), ('100p', 100), ('150p', 150),
                       ('300p', 300), ('500p', 500), ('1500p', 1500), ('all', n)]:
        if n < w:
            result[w_name] = None
            continue
        last_w = records[-w:]
        hr = sum(1 for r in last_w if r.get(metric_key, False)) / w
        result[w_name] = round(hr - BASELINE_PL_2BET, 4)
    return result

def b3_mcnemar(records):
    print('\n=== B3: McNemar + Permutation Test ===')

    # McNemar b, c counts
    # b = H9 hits AND mf doesn't (H9 advantage)
    # c = mf hits AND H9 doesn't (mf advantage)
    b = sum(1 for r in records if r['h9_hit'] and not r['mf_hit'])
    c = sum(1 for r in records if r['mf_hit'] and not r['h9_hit'])
    both = sum(1 for r in records if r['h9_hit'] and r['mf_hit'])
    neither = sum(1 for r in records if not r['h9_hit'] and not r['mf_hit'])
    total = len(records)

    mc_p = mcnemar_exact_p(b, c)
    net = b - c
    print(f'  McNemar: b={b}, c={c}, net={net}, p={mc_p:.4f}')
    print(f'  Both hit: {both}/{total}, Neither: {neither}/{total}')

    # H9 windows
    h9_windows = compute_windows_pl(records, 'h9_hit')
    mf_windows = compute_windows_pl(records, 'mf_hit')
    print(f'  H9 windows:  {h9_windows}')
    print(f'  MF windows:  {mf_windows}')

    # Permutation test on H9 full history
    h9_obs_edge, perm_p = permutation_test_edge(records, 'h9_hit', n_perm=10000)
    print(f'  Perm test H9: obs_edge={h9_obs_edge:.4f}, perm_p={perm_p:.4f}')

    return {
        'mcnemar': {'b': b, 'c': c, 'net': net, 'p': mc_p},
        'h9_windows': h9_windows,
        'mf_windows': mf_windows,
        'permutation': {'obs_edge': h9_obs_edge, 'perm_p': perm_p},
        'both': both, 'neither': neither, 'total': total,
    }

# ──────────────────────────────────────────────
# B4: Power analysis
# ──────────────────────────────────────────────
def power_analysis(records):
    """
    How many more draws needed to achieve:
    - McNemar p < 0.05 (net > 0)
    Rough estimate: assuming current net / total rate stays constant.
    """
    b = sum(1 for r in records if r['h9_hit'] and not r['mf_hit'])
    c = sum(1 for r in records if r['mf_hit'] and not r['h9_hit'])
    net = b - c
    total_discord = b + c
    n = len(records)

    # Current discord rate
    if total_discord == 0:
        return {'status': 'insufficient_discord', 'needed_draws': None}

    p_h9_wins = b / total_discord  # prob H9 wins in a discord
    discord_rate = total_discord / n  # fraction of draws that are discordant

    # For McNemar p<0.05 (two-tailed), net needs to satisfy binomial.
    # With rate ~ p_h9_wins, need how many discords for significance.
    # Use normal approx: net / sqrt(n_discord) > 1.96
    # => net > 1.96 * sqrt(n_discord)
    # Under current rate, net_new = n_discord * (2*p_h9_wins - 1)
    # => n_discord * (2*p_h9_wins - 1) > 1.96 * sqrt(n_discord)
    # => sqrt(n_discord) > 1.96 / (2*p_h9_wins - 1)
    # => n_discord > (1.96 / (2*p_h9_wins - 1))^2

    p_excess = 2 * p_h9_wins - 1  # net rate per discord
    if p_excess <= 0:
        return {
            'status': 'H9_not_ahead',
            'current_p_h9_wins': p_h9_wins,
            'needed_draws': None,
        }

    needed_discord = math.ceil((1.96 / p_excess) ** 2)
    additional_discord = max(0, needed_discord - total_discord)
    additional_draws = math.ceil(additional_discord / discord_rate) if discord_rate > 0 else None

    return {
        'status': 'insufficient',
        'current_discord': total_discord,
        'current_net': net,
        'current_p_h9_wins': round(p_h9_wins, 4),
        'p_excess': round(p_excess, 4),
        'needed_discord_for_p005': needed_discord,
        'additional_discord_needed': additional_discord,
        'estimated_additional_draws': additional_draws,
        'discord_rate': round(discord_rate, 4),
    }

# ──────────────────────────────────────────────
# B5: H9 decision report
# ──────────────────────────────────────────────
def b5_report(stats, draws, spec):
    print('\n=== B5: H9 McNemar Report ===')

    mc = stats['mcnemar']
    perm = stats['permutation']
    h9_w = stats['h9_windows']
    mf_w = stats['mf_windows']
    latest_draw = draws[-1]['draw']
    latest_date = draws[-1]['date']

    # Previous data from L93
    prev = PREV_H9

    # Check promotion conditions
    cond1_mcnemar_p = mc['p'] < 0.05
    cond2_mcnemar_net = mc['net'] > 0
    cond3_perm_p = perm['perm_p'] < 0.05
    
    windows_positive = all(
        v is not None and v > 0
        for k, v in h9_w.items()
        if k in ['150p', '300p', '500p', '1500p'] and v is not None
    )

    mf_1500p = mf_w.get('1500p')
    h9_1500p = h9_w.get('1500p')
    cond5_edge = (h9_1500p is not None and mf_1500p is not None and h9_1500p > mf_1500p)

    all_conds_met = cond1_mcnemar_p and cond2_mcnemar_net and cond3_perm_p and windows_positive and cond5_edge

    # Power analysis
    power_info = power_analysis(stats.get('_records', []))

    decision = 'PROMOTE' if all_conds_met else 'CONTINUE_SHADOW'

    report = {
        'strategy': 'H9_pure_midfreq_2bet',
        'lottery_type': 'POWER_LOTTO',
        'generated_at': datetime.now().isoformat(),
        'latest_draw': latest_draw,
        'latest_date': latest_date,
        'n_tested': stats['total'],
        'previous_validation': prev,
        'mcnemar': mc,
        'permutation_test': perm,
        'h9_windows': h9_w,
        'mf_windows': mf_w,
        'promotion_conditions': {
            'mcnemar_p_lt_005': cond1_mcnemar_p,
            'mcnemar_net_gt_0': cond2_mcnemar_net,
            'perm_p_lt_005': cond3_perm_p,
            'all_windows_positive': windows_positive,
            'h9_edge_gt_mf_edge': cond5_edge,
            'ALL_MET': all_conds_met,
        },
        'decision': decision,
        'notes': [],
    }

    # Notes
    if mc['net'] > prev['mcnemar_net']:
        report['notes'].append(f"McNemar net improved: {prev['mcnemar_net']} -> {mc['net']}")
    else:
        report['notes'].append(f"McNemar net unchanged or regressed: {prev['mcnemar_net']} -> {mc['net']}")

    if not cond1_mcnemar_p:
        report['notes'].append(f"McNemar p={mc['p']:.4f} >= 0.05 — insufficient evidence")
    if not cond3_perm_p:
        report['notes'].append(f"Permutation p={perm['perm_p']:.4f} >= 0.05 — permutation test fails")

    # Retest condition
    retest_draw = int(prev['retest_draw'])
    curr_draw = int(latest_draw)
    if curr_draw < retest_draw:
        draws_to_retest = retest_draw - curr_draw
        report['notes'].append(f"Retest condition: draw {retest_draw}, currently at {latest_draw} ({draws_to_retest} draws away)")

    print(f'  McNemar: net={mc["net"]}, p={mc["p"]:.4f}  (prev: net={prev["mcnemar_net"]}, p={prev["mcnemar_p"]})')
    print(f'  Permutation: obs_edge={perm["obs_edge"]:.4f}, perm_p={perm["perm_p"]:.4f}')
    print(f'  H9 windows: 150p={h9_w.get("150p")}, 300p={h9_w.get("300p")}, 1500p={h9_w.get("1500p")}')
    print(f'  MF windows: 150p={mf_w.get("150p")}, 300p={mf_w.get("300p")}, 1500p={mf_w.get("1500p")}')
    print(f'  Promotion conditions: {report["promotion_conditions"]}')
    print(f'  Decision: {decision}')

    out_path = os.path.join(DATA_DIR, 'h9_mcnemar_report.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f'  Saved: {out_path}')
    return report

# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    print('=== LINE B: H9 Pure MidFreq Promotion Analysis ===')

    # B1: Spec
    spec = b1_spec()

    # Load draws
    draws = load_draws()
    print(f'\n  POWER_LOTTO: {len(draws)} draws, latest={draws[-1]["draw"]} ({draws[-1]["date"]})')

    # B2: Full backtest
    records = b2_backtest(draws)

    # B3: Stats
    stats = b3_mcnemar(records)
    stats['_records'] = records  # for power analysis

    # B4: Power analysis
    power_info = power_analysis(records)
    print(f'\n=== B4: Power Analysis ===')
    print(f'  {power_info}')
    stats['power_analysis'] = power_info

    # B5: Decision report
    report = b5_report(stats, draws, spec)

    print('\n=== LINE B COMPLETE ===')
    print(f'Decision: {report["decision"]}')
    if report['decision'] == 'PROMOTE':
        print('  >> Promotion conditions MET. Execute deploy command manually:')
        print('     DEPLOYED_STRATEGY_KEYS["POWER_LOTTO"][2] = "midfreq_fourier_2bet"')
        print('     (or relevant key for H9 pure_midfreq_2bet)')
    else:
        print(f'  >> Continue shadow tracking. Retest conditions not yet met.')
        if power_info.get('estimated_additional_draws'):
            print(f'  >> Estimated additional draws needed: {power_info["estimated_additional_draws"]}')

    return report

if __name__ == '__main__':
    main()
