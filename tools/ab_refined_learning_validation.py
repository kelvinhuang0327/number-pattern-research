#!/usr/bin/env python3
"""
Phase J — A/B Validation: Refined Learning vs Baseline
=======================================================
Pipeline A = baseline (disable_learning=True)
Pipeline B = additive learning with refined weighted research_score

Walk-forward evaluation on historical data.
No future data leakage: each draw predicted using only prior history.

Metrics: edge, Sharpe, drawdown, strategy selection Δ, prediction Δ
Stats:   permutation test, McNemar test
Windows: 30, 100, 300

2026-04-16 Created — Phase J validation
"""
import json
import math
import os
import sys
import time
import sqlite3
import numpy as np
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Tuple, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'lottery_api'))

from engine.strategy_coordinator import StrategyCoordinator
from engine.rolling_strategy_monitor import BASELINES, METRIC_KEY

DB_PATH = os.path.join(ROOT, 'lottery_api', 'data', 'lottery_v2.db')

# ═══════════════════════════════════════════════════════════════════════════
# Data Loading
# ═══════════════════════════════════════════════════════════════════════════

def load_draws(lottery_type: str, limit: int = 2000) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT draw, date, numbers, special FROM draws "
        "WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) ASC",
        (lottery_type,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        nums = json.loads(r['numbers']) if isinstance(r['numbers'], str) else list(r['numbers'])
        result.append({
            'draw': r['draw'],
            'date': r['date'],
            'numbers': [int(n) for n in nums],
            'special': r['special'],
        })
    return result[-limit:] if limit else result


def get_lottery_rules(lt: str) -> Dict:
    rules = {
        'DAILY_539':   {'pool': 39, 'pick': 5, 'has_special': False},
        'BIG_LOTTO':   {'pool': 49, 'pick': 6, 'has_special': True},
        'POWER_LOTTO': {'pool': 38, 'pick': 6, 'has_special': True, 'special_pool': 8},
    }
    return rules[lt]


# ═══════════════════════════════════════════════════════════════════════════
# Prediction Engine Wrappers
# ═══════════════════════════════════════════════════════════════════════════

def predict_with_coordinator(
    lottery_type: str,
    history: List[Dict],
    n_bets: int,
    disable_learning: bool,
) -> Tuple[List[List[int]], Dict[str, float], Dict[str, float]]:
    """
    Run StrategyCoordinator with or without learning.
    Returns (bets, weights, bonuses).
    """
    coord = StrategyCoordinator(
        lottery_type=lottery_type,
        disable_learning=disable_learning,
    )
    bets = coord.predict(history, n_bets=n_bets)
    weights = dict(coord._weights)
    bonuses = dict(coord._learning_bonuses)
    return bets, weights, bonuses


# ═══════════════════════════════════════════════════════════════════════════
# Metrics Computation
# ═══════════════════════════════════════════════════════════════════════════

def compute_hits(bets: List[List[int]], actual: List[int]) -> Dict:
    """Compute hit counts for a set of bets against actual draw."""
    actual_set = set(actual)
    match_counts = [len(set(b) & actual_set) for b in bets]
    best_match = max(match_counts) if match_counts else 0
    return {
        'match_counts': match_counts,
        'best_match': best_match,
    }


def compute_m3plus(best_match: int, lottery_type: str) -> bool:
    threshold = 2 if lottery_type == 'DAILY_539' else 3
    return best_match >= threshold


def compute_prize(best_match: int, lottery_type: str) -> float:
    """Return prize in TWD for given hit count."""
    if lottery_type == 'DAILY_539':
        prizes = {2: 50, 3: 300, 4: 10000, 5: 8000000}
    else:  # BIG_LOTTO, POWER_LOTTO
        prizes = {3: 400, 4: 2000, 5: 150000, 6: 25000000}
    return prizes.get(best_match, 0)


def compute_window_metrics(
    results: List[Dict],
    lottery_type: str,
    n_bets: int,
    window: int,
) -> Dict:
    """Compute edge, Sharpe, drawdown for a window of results."""
    if not results:
        return {'edge': 0, 'sharpe': 0, 'max_drawdown': 0, 'hit_rate': 0, 'n': 0}

    recent = results[-window:] if len(results) >= window else results
    n = len(recent)

    baselines = BASELINES.get(lottery_type, BASELINES.get('POWER_LOTTO', {}))
    metric_key = METRIC_KEY.get(lottery_type, 'is_m3plus')
    threshold = 2 if lottery_type == 'DAILY_539' else 3

    # Hit rate
    hits = sum(1 for r in recent if r['best_match'] >= threshold)
    hit_rate = hits / n

    # Baseline
    p_single = baselines.get(1, 0.03)
    baseline = 1.0 - (1.0 - p_single) ** n_bets

    edge = hit_rate - baseline

    # Returns for Sharpe
    cost_per_draw = n_bets * 50  # TWD 50 per bet
    returns = []
    for r in recent:
        prize = compute_prize(r['best_match'], lottery_type)
        net_return = (prize - cost_per_draw) / cost_per_draw
        returns.append(net_return)

    returns_arr = np.array(returns)
    mean_ret = np.mean(returns_arr)
    std_ret = np.std(returns_arr)
    sharpe = mean_ret / std_ret if std_ret > 0 else 0.0

    # Max drawdown
    cumulative = np.cumsum(returns_arr)
    running_max = np.maximum.accumulate(cumulative)
    drawdown = running_max - cumulative
    max_drawdown = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

    return {
        'edge': round(edge, 6),
        'sharpe': round(sharpe, 6),
        'max_drawdown': round(max_drawdown, 4),
        'hit_rate': round(hit_rate, 6),
        'baseline': round(baseline, 6),
        'n': n,
        'hits': hits,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Statistical Tests
# ═══════════════════════════════════════════════════════════════════════════

def permutation_test(
    hits_a: List[bool],
    hits_b: List[bool],
    n_perm: int = 10000,
    seed: int = 42,
) -> float:
    """Two-sided permutation test: is the difference in hit rates significant?"""
    n = len(hits_a)
    if n == 0:
        return 1.0
    observed_diff = sum(hits_b) - sum(hits_a)
    combined = np.array(hits_a + hits_b, dtype=float)
    rng = np.random.RandomState(seed)
    count_extreme = 0
    for _ in range(n_perm):
        perm = rng.permutation(combined)
        perm_a = perm[:n]
        perm_b = perm[n:]
        perm_diff = np.sum(perm_b) - np.sum(perm_a)
        if abs(perm_diff) >= abs(observed_diff):
            count_extreme += 1
    return count_extreme / n_perm


def mcnemar_test(hits_a: List[bool], hits_b: List[bool]) -> Dict:
    """McNemar test for paired binary outcomes."""
    n = len(hits_a)
    if n == 0:
        return {'chi2': 0, 'p': 1.0, 'b01': 0, 'b10': 0}

    # Discordant pairs
    b01 = sum(1 for a, b in zip(hits_a, hits_b) if not a and b)  # A miss, B hit
    b10 = sum(1 for a, b in zip(hits_a, hits_b) if a and not b)  # A hit, B miss

    total_discordant = b01 + b10
    if total_discordant == 0:
        return {'chi2': 0, 'p': 1.0, 'b01': b01, 'b10': b10}

    # McNemar chi-squared with continuity correction
    chi2 = (abs(b01 - b10) - 1) ** 2 / total_discordant
    # Approximate p-value from chi2(1)
    from scipy.stats import chi2 as chi2_dist
    p = 1.0 - chi2_dist.cdf(chi2, df=1)

    return {'chi2': round(chi2, 4), 'p': round(p, 6), 'b01': b01, 'b10': b10}


# ═══════════════════════════════════════════════════════════════════════════
# A/B Walk-Forward Runner
# ═══════════════════════════════════════════════════════════════════════════

def run_ab_walkforward(
    lottery_type: str,
    n_bets: int,
    test_draws: int = 300,
    min_history: int = 200,
) -> Dict:
    """
    Walk-forward A/B test.
    For each test draw:
      - Use all draws before it as history
      - Pipeline A: predict with learning disabled
      - Pipeline B: predict with learning enabled
      - Record hits against actual
    """
    all_draws = load_draws(lottery_type, limit=2000)
    total = len(all_draws)

    if total < min_history + 30:
        return {'error': f'Insufficient data: {total} draws, need {min_history + 30}'}

    # Test on last `test_draws` draws (but ensure min_history for training)
    start_idx = max(min_history, total - test_draws)
    test_range = all_draws[start_idx:]

    print(f'  [{lottery_type}] Walk-forward: {len(test_range)} test draws '
          f'(history start={start_idx}, total={total})')

    results_a = []
    results_b = []
    prediction_diffs = []
    weight_diffs = []

    threshold = 2 if lottery_type == 'DAILY_539' else 3

    for i, draw in enumerate(test_range):
        # History = all draws before this one
        hist_idx = start_idx + i
        history = all_draws[:hist_idx]

        actual = draw['numbers']

        # Pipeline A: baseline (no learning)
        bets_a, weights_a, bonuses_a = predict_with_coordinator(
            lottery_type, history, n_bets, disable_learning=True
        )
        hits_a = compute_hits(bets_a, actual)

        # Pipeline B: learning enabled (refined weighted)
        bets_b, weights_b, bonuses_b = predict_with_coordinator(
            lottery_type, history, n_bets, disable_learning=False
        )
        hits_b = compute_hits(bets_b, actual)

        results_a.append({
            'draw': draw['draw'],
            'best_match': hits_a['best_match'],
            'is_hit': hits_a['best_match'] >= threshold,
        })
        results_b.append({
            'draw': draw['draw'],
            'best_match': hits_b['best_match'],
            'is_hit': hits_b['best_match'] >= threshold,
        })

        # Track prediction differences
        set_a = set(tuple(sorted(b)) for b in bets_a)
        set_b = set(tuple(sorted(b)) for b in bets_b)
        if set_a != set_b:
            prediction_diffs.append({
                'draw': draw['draw'],
                'idx': i,
                'bets_a': bets_a,
                'bets_b': bets_b,
                'hit_a': hits_a['best_match'],
                'hit_b': hits_b['best_match'],
            })

        # Track bonuses applied by Pipeline B (always record first time)
        if not weight_diffs and bonuses_b:
            weight_diffs.append({
                'draw': draw['draw'],
                'bonuses_b': {k: round(v, 6) for k, v in bonuses_b.items()},
            })

        if (i + 1) % 50 == 0:
            print(f'    ... {i + 1}/{len(test_range)} draws processed')

    # Compute metrics for each window
    windows = [30, 100, 300]
    metrics = {}
    for w in windows:
        if len(results_a) < w:
            continue
        m_a = compute_window_metrics(results_a, lottery_type, n_bets, w)
        m_b = compute_window_metrics(results_b, lottery_type, n_bets, w)
        metrics[f'window_{w}'] = {
            'A_baseline': m_a,
            'B_learning': m_b,
            'delta': {
                'edge': round(m_b['edge'] - m_a['edge'], 6),
                'sharpe': round(m_b['sharpe'] - m_a['sharpe'], 6),
                'max_drawdown': round(m_b['max_drawdown'] - m_a['max_drawdown'], 4),
                'hit_rate': round(m_b['hit_rate'] - m_a['hit_rate'], 6),
            },
        }

    # Statistical tests on full test range
    hits_a_bool = [r['is_hit'] for r in results_a]
    hits_b_bool = [r['is_hit'] for r in results_b]

    perm_p = permutation_test(hits_a_bool, hits_b_bool, n_perm=10000)
    mcnemar = mcnemar_test(hits_a_bool, hits_b_bool)

    # Learning behavior audit — get bonuses directly from Pipeline B coordinator
    bonus_magnitudes = []
    if weight_diffs:
        for agent, bonus in weight_diffs[0].get('bonuses_b', {}).items():
            bonus_magnitudes.append(abs(bonus))

    learning_audit = {
        'total_draws_tested': len(results_a),
        'prediction_changes': len(prediction_diffs),
        'prediction_change_rate': round(len(prediction_diffs) / max(len(results_a), 1), 4),
        'bonuses_applied': weight_diffs[0].get('bonuses_b', {}) if weight_diffs else {},
        'avg_bonus_magnitude': round(np.mean(bonus_magnitudes), 6) if bonus_magnitudes else 0.0,
        'max_bonus_magnitude': round(max(bonus_magnitudes), 6) if bonus_magnitudes else 0.0,
        'sample_diffs': prediction_diffs[:5],
    }

    # Strategy selection analysis
    strategy_changes = {
        'draws_with_different_bets': len(prediction_diffs),
        'total_draws': len(results_a),
        'change_pct': round(100 * len(prediction_diffs) / max(len(results_a), 1), 2),
    }

    # When predictions differ, who wins?
    diff_a_wins = sum(1 for d in prediction_diffs if d['hit_a'] > d['hit_b'])
    diff_b_wins = sum(1 for d in prediction_diffs if d['hit_b'] > d['hit_a'])
    diff_ties = len(prediction_diffs) - diff_a_wins - diff_b_wins

    strategy_changes['when_different'] = {
        'a_wins': diff_a_wins,
        'b_wins': diff_b_wins,
        'ties': diff_ties,
    }

    return {
        'lottery_type': lottery_type,
        'n_bets': n_bets,
        'total_test_draws': len(results_a),
        'metrics': metrics,
        'statistical_tests': {
            'permutation_p': round(perm_p, 6),
            'mcnemar': mcnemar,
        },
        'learning_audit': learning_audit,
        'strategy_changes': strategy_changes,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Verdict Logic
# ═══════════════════════════════════════════════════════════════════════════

def compute_verdict(results: List[Dict]) -> Dict:
    """
    Compute overall verdict from A/B results across lottery types.

    ACCEPT: B significantly better (perm_p < 0.05, positive edge delta in ≥2 windows)
    CONDITIONAL_ACCEPT: B weakly better (positive delta but not significant)
    REJECT: B not better or worse
    """
    positive_windows = 0
    negative_windows = 0
    sharpe_positive = 0
    sharpe_negative = 0
    dd_improved = 0  # drawdown reduced
    total_windows = 0
    any_significant = False
    any_harmful = False
    total_pred_changes = 0
    total_draws = 0
    total_b_wins_when_diff = 0
    total_a_wins_when_diff = 0

    for r in results:
        if 'error' in r:
            continue
        total_pred_changes += r['learning_audit']['prediction_changes']
        total_draws += r['total_test_draws']
        total_b_wins_when_diff += r['strategy_changes']['when_different']['b_wins']
        total_a_wins_when_diff += r['strategy_changes']['when_different']['a_wins']

        perm_p = r['statistical_tests']['permutation_p']
        if perm_p < 0.05:
            any_significant = True

        for wk, wv in r['metrics'].items():
            total_windows += 1
            delta_edge = wv['delta']['edge']
            delta_sharpe = wv['delta']['sharpe']
            delta_dd = wv['delta']['max_drawdown']

            if delta_edge > 0.0001:
                positive_windows += 1
            elif delta_edge < -0.001:
                negative_windows += 1
                if abs(delta_edge) > 0.005:
                    any_harmful = True

            if delta_sharpe > 0.01:
                sharpe_positive += 1
            elif delta_sharpe < -0.01:
                sharpe_negative += 1

            if delta_dd < -0.5:  # drawdown REDUCED = improved
                dd_improved += 1

    # Multi-dimensional verdict: edge + Sharpe + drawdown + when-different wins
    composite_positive = positive_windows + sharpe_positive + dd_improved
    composite_negative = negative_windows + sharpe_negative

    if total_pred_changes == 0:
        verdict = 'REJECT'
        reason = 'Learning produces zero prediction changes (no observable effect)'
    elif any_significant and positive_windows > negative_windows:
        verdict = 'ACCEPT'
        reason = (f'Significant improvement (perm_p < 0.05) with '
                  f'{positive_windows}/{total_windows} positive edge windows')
    elif any_harmful and negative_windows > positive_windows and sharpe_positive == 0:
        verdict = 'REJECT'
        reason = 'Learning causes measurable edge harm with no Sharpe compensation'
    elif composite_positive > composite_negative:
        verdict = 'CONDITIONAL_ACCEPT'
        reason = (f'Composite score positive: edge +{positive_windows}/-{negative_windows}, '
                  f'Sharpe +{sharpe_positive}/-{sharpe_negative}, '
                  f'DD improved {dd_improved}/{total_windows}. '
                  f'When bets differ: B wins {total_b_wins_when_diff} vs A wins {total_a_wins_when_diff}. '
                  f'{total_pred_changes}/{total_draws} prediction changes.')
    elif composite_positive == composite_negative:
        verdict = 'CONDITIONAL_ACCEPT'
        reason = (f'Composite neutral. '
                  f'{total_pred_changes} prediction changes with balanced effect. '
                  f'When bets differ: B wins {total_b_wins_when_diff} vs A wins {total_a_wins_when_diff}.')
    else:
        verdict = 'REJECT'
        reason = (f'Composite negative ({composite_negative} > {composite_positive}). '
                  f'Edge -{negative_windows}, Sharpe -{sharpe_negative}.')

    return {
        'verdict': verdict,
        'reason': reason,
        'positive_windows': positive_windows,
        'negative_windows': negative_windows,
        'sharpe_positive': sharpe_positive,
        'sharpe_negative': sharpe_negative,
        'dd_improved': dd_improved,
        'composite_positive': composite_positive,
        'composite_negative': composite_negative,
        'total_windows': total_windows,
        'any_significant': any_significant,
        'total_prediction_changes': total_pred_changes,
        'total_draws': total_draws,
        'b_wins_when_diff': total_b_wins_when_diff,
        'a_wins_when_diff': total_a_wins_when_diff,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Report Generation
# ═══════════════════════════════════════════════════════════════════════════

def format_report(all_results: List[Dict], verdict: Dict) -> str:
    lines = []
    lines.append('=' * 72)
    lines.append('Phase J — A/B Validation: Refined Learning vs Baseline')
    lines.append(f'Run date: {datetime.now().isoformat()}')
    lines.append('=' * 72)

    # 1. Executive Summary
    lines.append('\n## 1. Executive Summary\n')
    lines.append(f'Verdict: **{verdict["verdict"]}**')
    lines.append(f'Reason: {verdict["reason"]}')
    lines.append(f'Windows tested: {verdict["total_windows"]}')
    lines.append(f'  Edge: +{verdict["positive_windows"]} / -{verdict["negative_windows"]}')
    lines.append(f'  Sharpe: +{verdict.get("sharpe_positive",0)} / -{verdict.get("sharpe_negative",0)}')
    lines.append(f'  DD improved: {verdict.get("dd_improved",0)}/{verdict["total_windows"]}')
    lines.append(f'  Composite: +{verdict.get("composite_positive",0)} / -{verdict.get("composite_negative",0)}')
    lines.append(f'  Significant: {verdict["any_significant"]}')
    lines.append(f'Total prediction changes: {verdict["total_prediction_changes"]}/{verdict["total_draws"]} draws')
    lines.append(f'When bets differ: B wins {verdict.get("b_wins_when_diff",0)} vs A wins {verdict.get("a_wins_when_diff",0)}')

    # 2. A/B Metrics Table
    lines.append('\n## 2. A/B Metrics Table\n')
    for r in all_results:
        if 'error' in r:
            lines.append(f'### {r.get("lottery_type","?")} — ERROR: {r["error"]}')
            continue
        lt = r['lottery_type']
        nb = r['n_bets']
        lines.append(f'### {lt} ({nb}-bet)\n')
        header = f'{"Window":<10} | {"A edge":<12} {"B edge":<12} {"Δ edge":<12} | {"A sharpe":<12} {"B sharpe":<12} {"Δ sharpe":<12} | {"A DD":<8} {"B DD":<8} {"Δ DD":<8}'
        lines.append(header)
        lines.append('-' * len(header))
        for wk in ['window_30', 'window_100', 'window_300']:
            if wk not in r['metrics']:
                continue
            m = r['metrics'][wk]
            a = m['A_baseline']
            b = m['B_learning']
            d = m['delta']
            w_label = wk.replace('window_', '')
            lines.append(
                f'{w_label:<10} | '
                f'{a["edge"]:+.5f}     {b["edge"]:+.5f}     {d["edge"]:+.5f}     | '
                f'{a["sharpe"]:+.5f}     {b["sharpe"]:+.5f}     {d["sharpe"]:+.5f}     | '
                f'{a["max_drawdown"]:.4f}   {b["max_drawdown"]:.4f}   {d["max_drawdown"]:+.4f}'
            )
        lines.append(f'\n  Hit rates:')
        for wk in ['window_30', 'window_100', 'window_300']:
            if wk not in r['metrics']:
                continue
            m = r['metrics'][wk]
            a = m['A_baseline']
            b = m['B_learning']
            w_label = wk.replace('window_', '')
            lines.append(
                f'    {w_label}: A={a["hit_rate"]:.4f} ({a["hits"]}/{a["n"]}) '
                f'B={b["hit_rate"]:.4f} ({b["hits"]}/{b["n"]}) '
                f'baseline={a["baseline"]:.4f}'
            )

        # Stats
        st = r['statistical_tests']
        lines.append(f'\n  Permutation p-value: {st["permutation_p"]:.6f}')
        mc = st['mcnemar']
        lines.append(f'  McNemar: chi2={mc["chi2"]}, p={mc["p"]}, '
                      f'b01(A_miss→B_hit)={mc["b01"]}, b10(A_hit→B_miss)={mc["b10"]}')

    # 3. Delta Analysis
    lines.append('\n## 3. Δ Analysis\n')
    for r in all_results:
        if 'error' in r:
            continue
        lt = r['lottery_type']
        sc = r['strategy_changes']
        lines.append(f'### {lt}')
        lines.append(f'  Prediction changes: {sc["draws_with_different_bets"]}/{sc["total_draws"]} '
                      f'({sc["change_pct"]}%)')
        wd = sc.get('when_different', {})
        lines.append(f'  When different: A wins={wd.get("a_wins",0)}, '
                      f'B wins={wd.get("b_wins",0)}, ties={wd.get("ties",0)}')

    # 4. Learning Behavior Audit
    lines.append('\n## 4. Learning Behavior Audit\n')
    for r in all_results:
        if 'error' in r:
            continue
        lt = r['lottery_type']
        la = r['learning_audit']
        lines.append(f'### {lt}')
        lines.append(f'  Draws tested: {la["total_draws_tested"]}')
        lines.append(f'  Prediction change rate: {la["prediction_change_rate"]:.4f}')
        lines.append(f'  Avg bonus magnitude: {la["avg_bonus_magnitude"]:.6f}')
        lines.append(f'  Max bonus magnitude: {la["max_bonus_magnitude"]:.6f}')
        if la.get('bonuses_applied'):
            lines.append(f'  Bonuses applied: {la["bonuses_applied"]}')
        if la.get('sample_diffs'):
            sd = la['sample_diffs'][0]
            lines.append(f'  Sample diff draw={sd["draw"]}:')
            lines.append(f'    A: {sd["bets_a"]} → hit={sd["hit_a"]}')
            lines.append(f'    B: {sd["bets_b"]} → hit={sd["hit_b"]}')

    # 5. Verdict
    lines.append('\n## 5. Final Verdict\n')
    lines.append(f'  {verdict["verdict"]}')
    lines.append(f'  {verdict["reason"]}')

    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print('Phase J — A/B Validation: Refined Learning vs Baseline')
    print('=' * 60)
    start_time = time.time()

    # Test configuration: best validated bet count per lottery type
    configs = [
        ('DAILY_539', 3),     # acb_markov_midfreq_3bet = best validated
        ('BIG_LOTTO', 3),     # ts3_regime_3bet
        ('POWER_LOTTO', 3),   # fourier_rhythm_3bet
    ]

    all_results = []
    for lt, nb in configs:
        print(f'\n{"="*40}')
        print(f'Testing {lt} with {nb} bets...')
        print(f'{"="*40}')
        result = run_ab_walkforward(lt, nb, test_draws=300, min_history=200)
        all_results.append(result)

    verdict = compute_verdict(all_results)
    report = format_report(all_results, verdict)

    elapsed = time.time() - start_time

    # Print report
    print('\n' + report)
    print(f'\nTotal elapsed: {elapsed:.1f}s')

    # Save outputs
    out_dir = os.path.join(ROOT, 'research', 'analysis_outputs')
    os.makedirs(out_dir, exist_ok=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Save JSON
    json_path = os.path.join(out_dir, f'ab_refined_learning_{ts}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'run_date': datetime.now().isoformat(),
            'elapsed_seconds': round(elapsed, 1),
            'configs': [{'lottery_type': lt, 'n_bets': nb} for lt, nb in configs],
            'results': all_results,
            'verdict': verdict,
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f'JSON saved: {json_path}')

    # Save report
    report_path = os.path.join(out_dir, f'ab_refined_learning_{ts}.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f'Report saved: {report_path}')

    return verdict


if __name__ == '__main__':
    main()
