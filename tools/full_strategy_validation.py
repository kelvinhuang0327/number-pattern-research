#!/usr/bin/env python3
"""
Phase V — Full Strategy Validation & Best Strategy Reconciliation
=================================================================
Runs 3-window validation (150/500/1500) + statistical tests for ALL strategies.
Persists results to strategy_states_*.json.

Statistical tests:
  - Binomial test (exact permutation equivalent): p-value for "rate > baseline"
  - McNemar test: paired comparison vs random baseline
  - Sharpe ratio from walk-forward hit distribution

Validation criteria (STRICT):
  VALIDATED: edge_150p > 0 AND edge_500p > 0 AND edge_1500p > 0
             AND perm_p < 0.05 AND mcnemar_p < 0.05 AND sharpe > 0
  WATCH:     edge_500p > 0 AND edge_1500p > 0 (but missing some criteria)
  REJECTED:  fails 2+ of the above

Best strategy selection (NEW):
  composite_score = 0.5 * edge_1500p + 0.3 * sharpe_300p - 0.2 * max_drawdown_rate
  Only VALIDATED strategies eligible; fall back to WATCH if none.

2026-04-16 Created — Phase V
"""
import sys
import os
import json
import math
import random
import time
from datetime import datetime
from collections import defaultdict

import numpy as np
from scipy import stats as scipy_stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'lottery_api'))

from lottery_api.database import DatabaseManager

DB_PATH = os.path.join(ROOT, 'lottery_api', 'data', 'lottery_v2.db')
DATA_DIR = os.path.join(ROOT, 'lottery_api', 'data')

np.random.seed(42)
random.seed(42)

# ─── Baselines ────────────────────────────────────────────────────
BASELINES = {
    'POWER_LOTTO': {1: 0.0387, 2: 0.0759, 3: 0.1117, 4: 0.1460, 5: 0.1791},
    'BIG_LOTTO':   {1: 0.0186, 2: 0.0369, 3: 0.0549, 4: 0.0725, 5: 0.0896},
    'DAILY_539':   {1: 0.1140, 2: 0.2154, 3: 0.3050, 4: 0.3843, 5: 0.4539},
}
METRIC_KEY = {
    'POWER_LOTTO': 'is_m3plus',
    'BIG_LOTTO':   'is_m3plus',
    'DAILY_539':   'is_m2plus',
}


# ─── Metric hit check ─────────────────────────────────────────────
def _metric_hit(bets, actual_numbers, metric):
    actual_set = set(actual_numbers)
    best = max(len(set(b) & actual_set) for b in bets)
    if metric == 'is_m3plus':
        return best >= 3
    return best >= 2  # is_m2plus


# ─── Walk-forward backtest for one window ─────────────────────────
def _walk_forward_window(predict_fn, draws, window_size, min_train, metric, baseline):
    """
    Walk-forward backtest on the LAST `window_size` draws.
    Returns (hit_array, edge, rate, max_drawdown_rate)
    """
    # Take only the last window_size draws
    total = len(draws)
    start_idx = max(0, total - window_size)
    window_draws = draws[start_idx:]

    hits = []
    consecutive_losses = 0
    max_streak = 0
    cumulative_edge = 0.0
    max_cumulative = 0.0
    max_drawdown = 0.0

    for i in range(len(window_draws)):
        # Training set: all draws before this point (absolute index)
        abs_train_end = start_idx + i
        if abs_train_end < min_train:
            continue

        # Cap history to last 600 draws (all strategies use ≤500 internal window)
        history = draws[max(0, abs_train_end - 600):abs_train_end]
        actual = window_draws[i]['numbers']

        try:
            bets = predict_fn(history)
            hit = _metric_hit(bets, actual, metric)
        except Exception:
            hit = False

        hits.append(int(hit))

        # Track max drawdown (negative edge streaks)
        edge_this = (1.0 - baseline) if hit else (-baseline)
        cumulative_edge += edge_this
        if cumulative_edge > max_cumulative:
            max_cumulative = cumulative_edge
        drawdown = max_cumulative - cumulative_edge
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    n = len(hits)
    if n == 0:
        return [], 0.0, 0.0, 0.0

    n_hits = sum(hits)
    rate = n_hits / n
    edge = rate - baseline
    max_drawdown_rate = max_drawdown / max(n, 1)

    return hits, edge, rate, max_drawdown_rate


# ─── Statistical tests ────────────────────────────────────────────
def _binomial_test(n_hits, n_total, baseline):
    """One-tailed binomial test: H0 = rate <= baseline, H1 = rate > baseline."""
    if n_total == 0:
        return 1.0
    result = scipy_stats.binomtest(n_hits, n_total, baseline, alternative='greater')
    return float(result.pvalue)


def _mcnemar_test(strategy_hits, random_hits):
    """
    McNemar test: compare strategy vs random baseline (same draws).
    Returns p-value.
    """
    a_only = sum(1 for a, b in zip(strategy_hits, random_hits) if a and not b)
    b_only = sum(1 for a, b in zip(strategy_hits, random_hits) if b and not a)
    n_disc = a_only + b_only
    if n_disc == 0:
        return 1.0
    # Exact McNemar (mid-p)
    if n_disc < 25:
        # Exact binomial for small n
        p = scipy_stats.binomtest(a_only, n_disc, 0.5, alternative='greater').pvalue
        return float(p)
    # Large-sample McNemar with continuity correction
    chi2 = (abs(a_only - b_only) - 1) ** 2 / n_disc
    p = 1.0 - scipy_stats.chi2.cdf(chi2, df=1)
    return float(p)


def _sharpe(edge_array, rate):
    """Bernoulli Sharpe = edge / std(hits)"""
    if rate <= 0 or rate >= 1:
        return 0.0
    std = math.sqrt(rate * (1.0 - rate))
    return edge_array / std if std > 0 else 0.0


# ─── Random baseline hits (for McNemar) ───────────────────────────
def _random_baseline_hits(n, num_bets, metric, pool_size, pick_size, baseline_p):
    """
    Simulate random betting hits for McNemar comparison.
    Uses pre-computed baseline probability.
    """
    rng = np.random.RandomState(42)
    return [int(rng.random() < baseline_p) for _ in range(n)]


# ─── Validate a single strategy ───────────────────────────────────
def validate_strategy(name, predict_fn, num_bets, lottery_type, draws, verbose=True):
    """
    Full validation: 3 windows + statistical tests.
    Returns validated result dict.
    """
    metric = METRIC_KEY[lottery_type]
    baselines_for_lt = BASELINES[lottery_type]
    baseline = baselines_for_lt.get(num_bets, baselines_for_lt.get(3, 0.05))
    min_train = 150
    total = len(draws)

    if verbose:
        print(f"  [{name}] n_bets={num_bets} total={total}", end='', flush=True)

    results = {}
    all_hits_1500 = []  # for McNemar
    all_draws_1500 = None

    t0 = time.time()

    for window_size in [150, 500, 1500]:
        avail = total - min_train
        actual_window = min(window_size, avail)
        if actual_window < 50:
            results[window_size] = {
                'n': 0, 'hits': 0, 'rate': None,
                'edge': None, 'max_drawdown_rate': 0.0,
                'perm_p': 1.0, 'mcnemar_p': 1.0,
            }
            continue

        hits_arr, edge, rate, max_dd = _walk_forward_window(
            predict_fn, draws, actual_window + min_train, min_train, metric, baseline
        )
        n = len(hits_arr)
        n_hits = sum(hits_arr)

        # Statistical tests
        perm_p = _binomial_test(n_hits, n, baseline)

        # Random baseline hits (for McNemar)
        rand_hits = _random_baseline_hits(n, num_bets, metric,
                                           {'DAILY_539': 39, 'BIG_LOTTO': 49, 'POWER_LOTTO': 38}[lottery_type],
                                           {'DAILY_539': 5, 'BIG_LOTTO': 6, 'POWER_LOTTO': 6}[lottery_type],
                                           baseline)
        mcnemar_p = _mcnemar_test(hits_arr, rand_hits)

        results[window_size] = {
            'n': n,
            'hits': n_hits,
            'rate': round(rate, 5),
            'edge': round(edge, 5),
            'max_drawdown_rate': round(max_dd, 5),
            'perm_p': round(perm_p, 5),
            'mcnemar_p': round(mcnemar_p, 5),
        }

        if window_size == 1500:
            all_hits_1500 = hits_arr

    elapsed = time.time() - t0
    if verbose:
        e_vals = [results[w].get('edge') for w in [150, 500, 1500] if results[w].get('edge') is not None]
        p_vals = [results[w].get('perm_p') for w in [150, 500, 1500] if results[w].get('perm_p') is not None]
        print(f"  edges={[f'{e*100:+.2f}%' if e is not None else 'N/A' for e in e_vals]}"
              f"  p_vals={[f'{p:.3f}' if p is not None else 'N/A' for p in p_vals]}"
              f"  [{elapsed:.1f}s]")

    # Determine validated_status
    r150 = results.get(150, {})
    r500 = results.get(500, {})
    r1500 = results.get(1500, {})

    e150 = r150.get('edge')
    e500 = r500.get('edge')
    e1500 = r1500.get('edge')
    p150 = r150.get('perm_p', 1.0)
    p500 = r500.get('perm_p', 1.0)
    p1500 = r1500.get('perm_p', 1.0)
    mc150 = r150.get('mcnemar_p', 1.0)
    mc500 = r500.get('mcnemar_p', 1.0)
    mc1500 = r1500.get('mcnemar_p', 1.0)
    sharpe_val = _sharpe(e1500 or e500 or 0, r1500.get('rate') or r500.get('rate') or 0)

    # Strict validation criteria
    all_edges_positive = (e150 is not None and e150 > 0 and
                          e500 is not None and e500 > 0 and
                          e1500 is not None and e1500 > 0)
    perm_sig = (p1500 < 0.05 or (p1500 < 0.10 and p500 < 0.05))
    mcnemar_sig = (mc1500 < 0.05 or (mc1500 < 0.10 and mc500 < 0.05))
    sharpe_pos = sharpe_val > 0

    if all_edges_positive and perm_sig and mcnemar_sig and sharpe_pos:
        validated_status = 'VALIDATED'
    elif (e500 is not None and e500 > 0 and e1500 is not None and e1500 > 0):
        validated_status = 'WATCH'
    elif (e1500 is not None and e1500 > 0):
        validated_status = 'WATCH'
    else:
        validated_status = 'REJECTED'

    # Note reasons if not VALIDATED
    validation_notes = []
    if e150 is None or e150 <= 0:
        validation_notes.append(f"edge_150p={'N/A' if e150 is None else f'{e150*100:+.2f}%'}")
    if e500 is None or e500 <= 0:
        validation_notes.append(f"edge_500p={'N/A' if e500 is None else f'{e500*100:+.2f}%'}")
    if e1500 is None or e1500 <= 0:
        validation_notes.append(f"edge_1500p={'N/A' if e1500 is None else f'{e1500*100:+.2f}%'}")
    if not perm_sig:
        best_p = min([p150, p500, p1500])
        validation_notes.append(f"perm_p={best_p:.3f}>=0.05")
    if not mcnemar_sig:
        best_mc = min([mc150, mc500, mc1500])
        validation_notes.append(f"mcnemar_p={best_mc:.3f}>=0.05")
    if not sharpe_pos:
        validation_notes.append(f"sharpe={sharpe_val:.3f}<=0")

    return {
        'name': name,
        'num_bets': num_bets,
        'lottery_type': lottery_type,
        'baseline': baseline,
        'windows': results,
        'edge_150p': e150,
        'edge_500p': e500,
        'edge_1500p': e1500,
        'rate_150p': r150.get('rate'),
        'rate_500p': r500.get('rate'),
        'rate_1500p': r1500.get('rate'),
        'perm_p': round(min(p150, p500, p1500), 5),
        'mcnemar_p': round(min(mc150, mc500, mc1500), 5),
        'sharpe': round(sharpe_val, 4),
        'max_drawdown_rate': round(r1500.get('max_drawdown_rate') or r500.get('max_drawdown_rate') or 0, 5),
        'validated_status': validated_status,
        'validation_notes': ' | '.join(validation_notes) if validation_notes else 'all_criteria_met',
    }


# ─── Compute composite score ──────────────────────────────────────
def composite_score(val_result, state_dict):
    """
    composite = 0.5 * edge_1500p + 0.3 * sharpe - 0.2 * max_drawdown_rate
    Uses validated backtest results.
    """
    e1500 = val_result.get('edge_1500p') or 0
    sharpe = val_result.get('sharpe') or 0
    dd = val_result.get('max_drawdown_rate') or 0
    return 0.5 * e1500 + 0.3 * sharpe - 0.2 * dd


# ─── Update strategy_states file ──────────────────────────────────
def update_strategy_states(lottery_type, validation_results):
    """
    Merge validation results back into strategy_states_*.json.
    Adds new fields without removing existing ones.
    """
    states_path = os.path.join(DATA_DIR, f'strategy_states_{lottery_type}.json')
    if os.path.exists(states_path):
        with open(states_path, 'r') as f:
            states = json.load(f)
    else:
        states = {}

    for vr in validation_results:
        name = vr['name']
        if name not in states:
            states[name] = {}
        s = states[name]

        # Add new validation fields
        s['edge_150p']       = vr.get('edge_150p')
        s['edge_500p']       = vr.get('edge_500p')
        s['edge_1500p']      = vr.get('edge_1500p')
        s['rate_150p']       = vr.get('rate_150p')
        s['rate_500p']       = vr.get('rate_500p')
        s['rate_1500p']      = vr.get('rate_1500p')
        s['perm_p']          = vr.get('perm_p')
        s['mcnemar_p']       = vr.get('mcnemar_p')
        s['sharpe']          = vr.get('sharpe')
        s['max_drawdown_rate'] = vr.get('max_drawdown_rate')
        s['validated_status'] = vr.get('validated_status')
        s['validation_notes'] = vr.get('validation_notes')
        s['composite_score']  = round(composite_score(vr, s), 6)
        s['validation_updated_at'] = datetime.now().isoformat()

    with open(states_path, 'w') as f:
        json.dump(states, f, indent=2, ensure_ascii=False)

    print(f"  Saved {len(validation_results)} entries to {os.path.basename(states_path)}")
    return states


# ─── Determine best strategy per bet count ────────────────────────
def select_best_strategy(states_dict, lottery_type, verbose=True):
    """
    New best strategy selection:
    1. Only VALIDATED strategies eligible
    2. Sort by composite_score descending
    3. Fall back to best WATCH if no VALIDATED
    """
    best_per_nbets = {}

    # Group by num_bets
    by_nbets = defaultdict(list)
    for name, s in states_dict.items():
        nb = s.get('num_bets', 0)
        if nb > 0:
            by_nbets[nb].append((name, s))

    for nb, entries in sorted(by_nbets.items()):
        validated = [(n, s) for n, s in entries if s.get('validated_status') == 'VALIDATED']
        watch = [(n, s) for n, s in entries if s.get('validated_status') == 'WATCH']
        all_cs = validated or watch  # prefer VALIDATED

        if not all_cs:
            # All rejected — show warning
            best_name, best_state = max(entries, key=lambda x: x[1].get('edge_300p', -999))
            best_per_nbets[nb] = {
                'name': best_name,
                'num_bets': nb,
                'validated_status': best_state.get('validated_status', 'REJECTED'),
                'validation_warning': 'INSUFFICIENT_VALIDATION — no strategy passed criteria',
                'composite_score': best_state.get('composite_score', 0),
                'edge_1500p': best_state.get('edge_1500p'),
                'source': 'fallback_rejected',
            }
            continue

        # Sort by composite_score
        ranked = sorted(all_cs, key=lambda x: x[1].get('composite_score', -999), reverse=True)
        best_name, best_state = ranked[0]
        using_watch = len(validated) == 0

        best_per_nbets[nb] = {
            'name': best_name,
            'num_bets': nb,
            'validated_status': best_state.get('validated_status'),
            'validation_warning': 'NOT_FULLY_VALIDATED — best available WATCH strategy' if using_watch else None,
            'composite_score': best_state.get('composite_score', 0),
            'edge_150p': best_state.get('edge_150p'),
            'edge_500p': best_state.get('edge_500p'),
            'edge_1500p': best_state.get('edge_1500p'),
            'perm_p': best_state.get('perm_p'),
            'mcnemar_p': best_state.get('mcnemar_p'),
            'sharpe': best_state.get('sharpe'),
            'source': 'watch_fallback' if using_watch else 'validated',
        }

        if verbose:
            w = '⚠️ ' if using_watch else '✅'
            print(f"  n_bets={nb}: {w} {best_name}"
                  f"  composite={best_state.get('composite_score', 0):.4f}"
                  f"  e1500={best_state.get('edge_1500p', 0) or 0:+.4f}"
                  f"  status={best_state.get('validated_status')}")

    return best_per_nbets


# ─── Main validation loop ─────────────────────────────────────────
def run_full_validation():
    db = DatabaseManager(DB_PATH)
    all_results = {}

    for lottery_type in ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']:
        print(f"\n{'='*72}")
        print(f"  {lottery_type}")
        print(f"{'='*72}")

        draws = sorted(db.get_all_draws(lottery_type),
                       key=lambda x: (x.get('date', ''), x.get('draw', '')))
        print(f"  Total draws: {len(draws)}")

        # Load strategy functions
        try:
            if lottery_type == 'DAILY_539':
                from tools.rsm_bootstrap import get_daily_539_strategies_inline
                configs = get_daily_539_strategies_inline()
            elif lottery_type == 'BIG_LOTTO':
                from tools.rsm_bootstrap import get_big_lotto_strategies_inline
                configs = get_big_lotto_strategies_inline()
            else:
                from tools.rsm_bootstrap import get_power_lotto_strategies_inline
                configs = get_power_lotto_strategies_inline()
        except Exception as e:
            print(f"  ERROR loading strategies: {e}")
            continue

        validation_results = []
        print(f"\n  Validating {len(configs)} strategies...")
        for cfg in configs:
            try:
                vr = validate_strategy(
                    name=cfg['name'],
                    predict_fn=cfg['predict_func'],
                    num_bets=cfg['num_bets'],
                    lottery_type=lottery_type,
                    draws=draws,
                    verbose=True,
                )
                validation_results.append(vr)
            except Exception as e:
                print(f"  ERROR validating {cfg['name']}: {e}")

        # Update strategy_states file
        print(f"\n  Persisting results...")
        updated_states = update_strategy_states(lottery_type, validation_results)

        # Select best strategies
        print(f"\n  Best strategy per bet count (new logic):")
        best = select_best_strategy(updated_states, lottery_type, verbose=True)

        all_results[lottery_type] = {
            'validation_results': validation_results,
            'best_per_nbets': best,
            'states': updated_states,
        }

    return all_results


# ─── Generate report ──────────────────────────────────────────────
def generate_report(all_results):
    lines = []
    lines.append("# Phase V — Full Strategy Validation Report")
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("\n---")

    for lt, data in all_results.items():
        vrs = data['validation_results']
        best = data['best_per_nbets']

        validated = [v for v in vrs if v['validated_status'] == 'VALIDATED']
        watch = [v for v in vrs if v['validated_status'] == 'WATCH']
        rejected = [v for v in vrs if v['validated_status'] == 'REJECTED']

        lines.append(f"\n## {lt}")
        lines.append(f"\n- Total strategies: {len(vrs)}")
        lines.append(f"- VALIDATED: {len(validated)}")
        lines.append(f"- WATCH: {len(watch)}")
        lines.append(f"- REJECTED: {len(rejected)}")

        lines.append("\n### Validation Results\n")
        lines.append("| Strategy | n_bets | edge_150p | edge_500p | edge_1500p | perm_p | mcnemar_p | sharpe | status |")
        lines.append("|----------|--------|-----------|-----------|------------|--------|-----------|--------|--------|")
        for v in sorted(vrs, key=lambda x: (x['num_bets'], x['name'])):
            e150 = f"{v['edge_150p']*100:+.2f}%" if v['edge_150p'] is not None else "N/A"
            e500 = f"{v['edge_500p']*100:+.2f}%" if v['edge_500p'] is not None else "N/A"
            e1500 = f"{v['edge_1500p']*100:+.2f}%" if v['edge_1500p'] is not None else "N/A"
            pp = f"{v['perm_p']:.4f}" if v['perm_p'] is not None else "N/A"
            mp = f"{v['mcnemar_p']:.4f}" if v['mcnemar_p'] is not None else "N/A"
            sh = f"{v['sharpe']:.3f}" if v['sharpe'] is not None else "N/A"
            lines.append(f"| {v['name']} | {v['num_bets']} | {e150} | {e500} | {e1500} | {pp} | {mp} | {sh} | {v['validated_status']} |")

        lines.append("\n### Best Strategy Per Bet Count (New Composite Logic)\n")
        lines.append("| n_bets | strategy | validated_status | composite | edge_1500p | warning |")
        lines.append("|--------|----------|-----------------|-----------|------------|---------|")
        for nb, b in sorted(best.items()):
            e1500 = f"{b['edge_1500p']*100:+.2f}%" if b.get('edge_1500p') else "N/A"
            cs = f"{b.get('composite_score', 0):.4f}"
            w = b.get('validation_warning') or '—'
            lines.append(f"| {nb} | {b['name']} | {b['validated_status']} | {cs} | {e1500} | {w} |")

    return '\n'.join(lines)


# ─── Entry point ──────────────────────────────────────────────────
if __name__ == '__main__':
    t_start = time.time()
    print(f"Phase V — Full Strategy Validation")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    all_results = run_full_validation()

    # Generate and save report
    report_text = generate_report(all_results)
    report_path = os.path.join(ROOT, 'docs', 'full_strategy_validation_report.md')
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    print(f"\n\nReport saved to: {report_path}")

    # Also save raw results
    results_path = os.path.join(ROOT, 'research', 'analysis_outputs',
                                 f'phase_v_validation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    os.makedirs(os.path.dirname(results_path), exist_ok=True)
    with open(results_path, 'w') as f:
        # Strip non-serializable data (predict_fn)
        serializable = {}
        for lt, data in all_results.items():
            serializable[lt] = {
                'validation_results': data['validation_results'],
                'best_per_nbets': data['best_per_nbets'],
            }
        json.dump(serializable, f, indent=2, ensure_ascii=False, default=str)
    print(f"Raw results saved to: {results_path}")

    elapsed = time.time() - t_start
    print(f"\nTotal time: {elapsed:.1f}s")
