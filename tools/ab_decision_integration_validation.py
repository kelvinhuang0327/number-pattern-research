#!/usr/bin/env python3
"""
Phase L — Learning → Decision Integration A/B Validation
==========================================================
Test whether learning-aware decision modifications improve outcomes
over baseline decision layer.

Pipeline A = baseline decision (disable_learning=True, no decision mods)
Pipeline B = learning-aware decision (learning bonuses + confidence shift
             + portfolio concentration adjustment + UCB1 reward adjustment)

Measures: Sharpe, drawdown, hit rate, edge, B vs A wins
Statistical: permutation test, McNemar test

2026-04-16 Created — Phase L decision integration validation
"""
import json
import os
import sys
import time
import sqlite3
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'lottery_api'))

from engine.strategy_coordinator import StrategyCoordinator
from engine.rolling_strategy_monitor import BASELINES

DB_PATH = os.path.join(ROOT, 'lottery_api', 'data', 'lottery_v2.db')

# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════
TEST_DRAWS = 300
MIN_HISTORY = 200
N_PERM = 10000
CONFIGS = [
    ('DAILY_539', 3),
    ('BIG_LOTTO', 3),
    ('POWER_LOTTO', 3),
]

# ═══════════════════════════════════════════════════════════════════════════
# Import decision layer
# ═══════════════════════════════════════════════════════════════════════════
sys.path.insert(0, os.path.join(ROOT, 'analysis'))
from decision_engine_v2 import (
    LearningAwareDecision, ConfidenceEngine, VarNPolicy, PortfolioBuilder,
    LEARNING_AMP,
)

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


# ═══════════════════════════════════════════════════════════════════════════
# Pipeline A: Baseline (no learning)
# ═══════════════════════════════════════════════════════════════════════════

def predict_baseline(
    lottery_type: str,
    history: List[Dict],
    n_bets: int,
) -> Tuple[List[List[int]], int, float]:
    """Pipeline A: no learning, standard decision."""
    coord = StrategyCoordinator(lottery_type=lottery_type, disable_learning=True)
    bets = coord.predict(history, n_bets=n_bets)
    return bets, n_bets, 0.5  # fixed confidence for baseline


# ═══════════════════════════════════════════════════════════════════════════
# Pipeline B: Learning-Aware Decision
# ═══════════════════════════════════════════════════════════════════════════

def predict_learning_decision(
    lottery_type: str,
    history: List[Dict],
    n_bets: int,
) -> Tuple[List[List[int]], int, float, Dict]:
    """
    Pipeline B: learning-aware decision layer.
    Uses all Phase L integration points:
    1. Learning score computation (with per-lottery amp)
    2. Confidence adjustment for Var-N
    3. Portfolio concentration adjustment
    4. Prediction via coordinator with learning bonuses
    """
    coord = StrategyCoordinator(lottery_type=lottery_type, disable_learning=False)

    # Phase L integration point 1: compute learning score
    learning_score = LearningAwareDecision.compute_learning_score(coord)

    # Phase L integration point 2: adjust confidence for Var-N
    base_confidence = 0.5  # neutral baseline
    adjusted_conf = LearningAwareDecision.adjust_confidence(base_confidence, learning_score)

    # Phase L integration point 2b: determine n_bets from adjusted confidence
    varn = VarNPolicy()
    effective_n = varn.decide(lottery_type, adjusted_conf)
    actual_n = min(effective_n, n_bets)  # cap to requested max

    # Phase L integration point 3: portfolio concentration
    concentration_top_n = LearningAwareDecision.get_concentration_top_n(learning_score)

    # Build portfolio
    portfolio = PortfolioBuilder()
    try:
        bets, portfolio_type = portfolio.build(
            lottery_type, history, actual_n, coord,
            concentration_top_n=concentration_top_n,
        )
    except Exception:
        bets = coord.predict(history, n_bets=actual_n)
        portfolio_type = "coverage_only"

    decision_info = {
        'learning_score': round(learning_score, 6),
        'base_confidence': base_confidence,
        'adjusted_confidence': round(adjusted_conf, 4),
        'effective_n_bets': effective_n,
        'actual_n_bets': actual_n,
        'concentration_top_n': concentration_top_n,
        'portfolio_type': portfolio_type,
        'bonuses': {k: round(v, 6) for k, v in coord._learning_bonuses.items()},
        'amp_factor': LEARNING_AMP.get(lottery_type, 1.0),
    }

    return bets, actual_n, adjusted_conf, decision_info


# ═══════════════════════════════════════════════════════════════════════════
# Metrics
# ═══════════════════════════════════════════════════════════════════════════

def compute_hits(bets: List[List[int]], actual: List[int]) -> int:
    actual_set = set(actual)
    return max(len(set(b) & actual_set) for b in bets) if bets else 0


def compute_prize(best_match: int, lottery_type: str) -> float:
    if lottery_type == 'DAILY_539':
        prizes = {2: 50, 3: 300, 4: 10000, 5: 8000000}
    else:
        prizes = {3: 400, 4: 2000, 5: 150000, 6: 25000000}
    return prizes.get(best_match, 0)


def compute_window_metrics(results: List[Dict], lottery_type: str, n_bets: int, window: int) -> Dict:
    if not results:
        return {'edge': 0, 'sharpe': 0, 'max_drawdown': 0, 'hit_rate': 0, 'n': 0, 'hits': 0, 'baseline': 0}

    recent = results[-window:] if len(results) >= window else results
    n = len(recent)
    threshold = 2 if lottery_type == 'DAILY_539' else 3

    hits = sum(1 for r in recent if r['best_match'] >= threshold)
    hit_rate = hits / n

    baselines = BASELINES.get(lottery_type, BASELINES.get('POWER_LOTTO', {}))
    p_single = baselines.get(1, 0.03)
    baseline = 1.0 - (1.0 - p_single) ** n_bets
    edge = hit_rate - baseline

    cost_per_draw = n_bets * 50
    returns = []
    for r in recent:
        prize = compute_prize(r['best_match'], lottery_type)
        returns.append((prize - cost_per_draw) / cost_per_draw)

    returns_arr = np.array(returns)
    mean_ret = np.mean(returns_arr)
    std_ret = np.std(returns_arr)
    sharpe = mean_ret / std_ret if std_ret > 0 else 0.0

    cumulative = np.cumsum(returns_arr)
    running_max = np.maximum.accumulate(cumulative)
    drawdown = running_max - cumulative
    max_drawdown = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

    return {
        'edge': round(edge, 6), 'sharpe': round(sharpe, 6),
        'max_drawdown': round(max_drawdown, 4), 'hit_rate': round(hit_rate, 6),
        'baseline': round(baseline, 6), 'n': n, 'hits': hits,
    }


def permutation_test(hits_a: List[bool], hits_b: List[bool], n_perm: int = 10000, seed: int = 42) -> float:
    n = len(hits_a)
    if n == 0:
        return 1.0
    observed_diff = sum(hits_b) - sum(hits_a)
    combined = np.array(hits_a + hits_b, dtype=float)
    rng = np.random.RandomState(seed)
    count_extreme = 0
    for _ in range(n_perm):
        perm = rng.permutation(combined)
        perm_diff = np.sum(perm[n:]) - np.sum(perm[:n])
        if abs(perm_diff) >= abs(observed_diff):
            count_extreme += 1
    return count_extreme / n_perm


def mcnemar_test(hits_a: List[bool], hits_b: List[bool]) -> Dict:
    n = len(hits_a)
    if n == 0:
        return {'chi2': 0, 'p': 1.0, 'b01': 0, 'b10': 0}
    b01 = sum(1 for a, b in zip(hits_a, hits_b) if not a and b)
    b10 = sum(1 for a, b in zip(hits_a, hits_b) if a and not b)
    total_discordant = b01 + b10
    if total_discordant == 0:
        return {'chi2': 0, 'p': 1.0, 'b01': b01, 'b10': b10}
    chi2 = (abs(b01 - b10) - 1) ** 2 / total_discordant
    from scipy.stats import chi2 as chi2_dist
    p = 1.0 - chi2_dist.cdf(chi2, df=1)
    return {'chi2': round(chi2, 4), 'p': round(p, 6), 'b01': b01, 'b10': b10}


# ═══════════════════════════════════════════════════════════════════════════
# Walk-forward runner
# ═══════════════════════════════════════════════════════════════════════════

def run_decision_walkforward(
    lottery_type: str,
    n_bets: int,
    all_draws: List[Dict],
) -> Dict:
    """
    Walk-forward A/B test comparing baseline vs learning-aware decision.
    """
    total = len(all_draws)
    start_idx = max(MIN_HISTORY, total - TEST_DRAWS)
    test_range = all_draws[start_idx:]
    threshold = 2 if lottery_type == 'DAILY_539' else 3

    results_a = []
    results_b = []
    prediction_diffs = []
    decision_info_snapshot = None
    n_bets_changes = []

    for i, draw in enumerate(test_range):
        hist_idx = start_idx + i
        history = all_draws[:hist_idx]
        actual = draw['numbers']
        draw_key = draw['draw']

        # Pipeline A: baseline (no learning)
        bets_a, n_a, conf_a = predict_baseline(lottery_type, history, n_bets)
        hit_a = compute_hits(bets_a, actual)

        # Pipeline B: learning-aware decision
        bets_b, n_b, conf_b, d_info = predict_learning_decision(
            lottery_type, history, n_bets,
        )
        hit_b = compute_hits(bets_b, actual)

        if decision_info_snapshot is None and d_info:
            decision_info_snapshot = d_info

        # Track n_bets changes
        if n_a != n_b:
            n_bets_changes.append({
                'draw': draw_key, 'n_a': n_a, 'n_b': n_b,
                'learning_score': d_info.get('learning_score', 0),
            })

        results_a.append({'draw': draw_key, 'best_match': hit_a, 'is_hit': hit_a >= threshold, 'n_bets': n_a})
        results_b.append({'draw': draw_key, 'best_match': hit_b, 'is_hit': hit_b >= threshold, 'n_bets': n_b})

        set_a = set(tuple(sorted(b)) for b in bets_a)
        set_b = set(tuple(sorted(b)) for b in bets_b)
        if set_a != set_b:
            prediction_diffs.append({
                'draw': draw_key, 'idx': i,
                'bets_a': bets_a, 'bets_b': bets_b,
                'hit_a': hit_a, 'hit_b': hit_b,
                'n_a': n_a, 'n_b': n_b,
            })

        if (i + 1) % 100 == 0:
            print(f'      ... {i + 1}/{len(test_range)} draws')

    # Metrics per window
    windows = [30, 100, 300]
    metrics = {}
    for w in windows:
        if len(results_a) < w:
            continue
        m_a = compute_window_metrics(results_a, lottery_type, n_bets, w)
        m_b = compute_window_metrics(results_b, lottery_type, n_bets, w)
        metrics[f'window_{w}'] = {
            'A': m_a, 'B': m_b,
            'delta': {
                'edge': round(m_b['edge'] - m_a['edge'], 6),
                'sharpe': round(m_b['sharpe'] - m_a['sharpe'], 6),
                'max_drawdown': round(m_b['max_drawdown'] - m_a['max_drawdown'], 4),
            },
        }

    # Statistical tests
    hits_a_bool = [r['is_hit'] for r in results_a]
    hits_b_bool = [r['is_hit'] for r in results_b]
    perm_p = permutation_test(hits_a_bool, hits_b_bool, N_PERM)
    mcnemar = mcnemar_test(hits_a_bool, hits_b_bool)

    # Diff analysis
    diff_a_wins = sum(1 for d in prediction_diffs if d['hit_a'] > d['hit_b'])
    diff_b_wins = sum(1 for d in prediction_diffs if d['hit_b'] > d['hit_a'])
    diff_ties = len(prediction_diffs) - diff_a_wins - diff_b_wins

    # Hit distribution
    hit_dist_a = {}
    hit_dist_b = {}
    for r in results_a:
        k = r['best_match']
        hit_dist_a[k] = hit_dist_a.get(k, 0) + 1
    for r in results_b:
        k = r['best_match']
        hit_dist_b[k] = hit_dist_b.get(k, 0) + 1

    return {
        'lottery_type': lottery_type,
        'n_bets': n_bets,
        'total_draws': len(results_a),
        'metrics': metrics,
        'stats': {'perm_p': round(perm_p, 6), 'mcnemar': mcnemar},
        'pred_changes': len(prediction_diffs),
        'pred_change_rate': round(len(prediction_diffs) / max(len(results_a), 1), 4),
        'when_diff': {'a_wins': diff_a_wins, 'b_wins': diff_b_wins, 'ties': diff_ties},
        'n_bets_changes': len(n_bets_changes),
        'decision_info': decision_info_snapshot or {},
        'hit_distribution': {'A': hit_dist_a, 'B': hit_dist_b},
        'sample_diffs': prediction_diffs[:3],
        'sample_n_changes': n_bets_changes[:5],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Verdict Logic
# ═══════════════════════════════════════════════════════════════════════════

def compute_verdict(all_results: List[Dict]) -> Dict:
    """Compute overall verdict across all lottery types."""
    total_b_wins = sum(r['when_diff']['b_wins'] for r in all_results)
    total_a_wins = sum(r['when_diff']['a_wins'] for r in all_results)
    total_pred_changes = sum(r['pred_changes'] for r in all_results)
    total_draws = sum(r['total_draws'] for r in all_results)

    # Per-lottery verdicts
    per_lottery = {}
    for r in all_results:
        lt = r['lottery_type']
        bw = r['when_diff']['b_wins']
        aw = r['when_diff']['a_wins']
        b_ratio = bw / max(bw + aw, 1)
        p_value = r['stats']['perm_p']

        # Verdict per lottery
        if bw + aw < 10:
            verdict = 'INSUFFICIENT_DATA'
        elif b_ratio > 0.55 and p_value < 0.10:
            verdict = 'ACCEPT'
        elif b_ratio > 0.50:
            verdict = 'MARGINAL'
        elif b_ratio < 0.40:
            verdict = 'REJECT'
        else:
            verdict = 'NEUTRAL'

        per_lottery[lt] = {
            'verdict': verdict,
            'b_wins': bw, 'a_wins': aw, 'b_ratio': round(b_ratio, 4),
            'perm_p': p_value,
            'pred_change_rate': r['pred_change_rate'],
        }

    # Global verdict
    verdicts = [v['verdict'] for v in per_lottery.values()]
    n_accept = sum(1 for v in verdicts if v == 'ACCEPT')
    n_reject = sum(1 for v in verdicts if v == 'REJECT')
    n_marginal = sum(1 for v in verdicts if v == 'MARGINAL')

    if n_reject > 0:
        global_verdict = 'CONDITIONAL_REJECT'
    elif n_accept >= 2:
        global_verdict = 'ACCEPT'
    elif n_accept >= 1:
        global_verdict = 'CONDITIONAL_ACCEPT'
    elif n_marginal >= 2:
        global_verdict = 'MARGINAL_ACCEPT'
    else:
        global_verdict = 'NEUTRAL'

    b_ratio = total_b_wins / max(total_b_wins + total_a_wins, 1)

    return {
        'global_verdict': global_verdict,
        'per_lottery': per_lottery,
        'total_b_wins': total_b_wins,
        'total_a_wins': total_a_wins,
        'total_b_ratio': round(b_ratio, 4),
        'total_pred_changes': total_pred_changes,
        'total_draws': total_draws,
        'pred_change_rate': round(total_pred_changes / max(total_draws, 1), 4),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Report Formatting
# ═══════════════════════════════════════════════════════════════════════════

def format_report(all_results: List[Dict], verdict: Dict, elapsed: float) -> str:
    lines = [
        '# Phase L — Learning → Decision Integration A/B Report',
        f'**Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        f'**Elapsed**: {elapsed:.1f}s',
        f'**Draws per lottery**: {TEST_DRAWS}',
        f'**Permutation tests**: {N_PERM}',
        '',
        '## Global Verdict',
        f'**{verdict["global_verdict"]}**',
        f'- Total B wins: {verdict["total_b_wins"]} vs A wins: {verdict["total_a_wins"]} '
        f'(B ratio: {verdict["total_b_ratio"]:.1%})',
        f'- Total pred changes: {verdict["total_pred_changes"]}/{verdict["total_draws"]} '
        f'({verdict["pred_change_rate"]:.1%})',
        '',
    ]

    for r in all_results:
        lt = r['lottery_type']
        d_info = r.get('decision_info', {})
        v = verdict['per_lottery'].get(lt, {})

        lines.append(f'## {lt}')
        lines.append(f'**Verdict**: {v.get("verdict", "N/A")}')
        lines.append(f'- Learning score: {d_info.get("learning_score", "N/A")}')
        lines.append(f'- Amp factor: {d_info.get("amp_factor", "N/A")}')
        lines.append(f'- Adjusted confidence: {d_info.get("adjusted_confidence", "N/A")}')
        lines.append(f'- Concentration top_n: {d_info.get("concentration_top_n", "N/A")}')
        lines.append(f'- Prediction changes: {r["pred_changes"]}/{r["total_draws"]} '
                      f'({r["pred_change_rate"]:.1%})')
        lines.append(f'- B wins: {r["when_diff"]["b_wins"]} vs A wins: {r["when_diff"]["a_wins"]}')
        lines.append(f'- N-bets changes: {r["n_bets_changes"]}')
        lines.append(f'- Perm p-value: {r["stats"]["perm_p"]:.4f}')
        lines.append(f'- McNemar: chi2={r["stats"]["mcnemar"]["chi2"]}, '
                      f'p={r["stats"]["mcnemar"]["p"]:.4f}')
        lines.append('')

        # Metrics table
        lines.append('| Window | A edge | B edge | Δ edge | A Sharpe | B Sharpe | Δ Sharpe |')
        lines.append('|--------|--------|--------|--------|---------|---------|----------|')
        for wk in ['window_30', 'window_100', 'window_300']:
            if wk in r['metrics']:
                m = r['metrics'][wk]
                lines.append(
                    f'| {wk.replace("window_", "W")} '
                    f'| {m["A"]["edge"]:.4f} '
                    f'| {m["B"]["edge"]:.4f} '
                    f'| {m["delta"]["edge"]:+.4f} '
                    f'| {m["A"]["sharpe"]:.4f} '
                    f'| {m["B"]["sharpe"]:.4f} '
                    f'| {m["delta"]["sharpe"]:+.4f} |'
                )
        lines.append('')

        # Hit distribution
        lines.append('**Hit Distribution**')
        lines.append('| Hits | A count | B count |')
        lines.append('|------|---------|---------|')
        all_keys = sorted(set(list(r['hit_distribution']['A'].keys())
                               + list(r['hit_distribution']['B'].keys())))
        for k in all_keys:
            lines.append(f'| {k} | {r["hit_distribution"]["A"].get(k, 0)} '
                          f'| {r["hit_distribution"]["B"].get(k, 0)} |')
        lines.append('')

        # Bonuses
        if d_info.get('bonuses'):
            lines.append('**Applied Bonuses**')
            for agent, bonus in sorted(d_info['bonuses'].items()):
                lines.append(f'- {agent}: {bonus:+.6f}')
            lines.append('')

    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    t0 = time.time()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    print('=' * 70)
    print('Phase L — Learning → Decision Integration A/B Validation')
    print('=' * 70)
    print(f'Configs: {CONFIGS}')
    print(f'Test draws: {TEST_DRAWS}, Perm tests: {N_PERM}')
    print()

    all_results = []

    for lottery_type, n_bets in CONFIGS:
        print(f'  [{lottery_type}] Loading draws...')
        draws = load_draws(lottery_type)
        print(f'    Total draws: {len(draws)}')

        print(f'  [{lottery_type}] Running walk-forward A/B...')
        result = run_decision_walkforward(lottery_type, n_bets, draws)
        all_results.append(result)

        # Quick summary
        d_info = result.get('decision_info', {})
        print(f'    Learning score: {d_info.get("learning_score", "N/A")}')
        print(f'    Pred changes: {result["pred_changes"]}/{result["total_draws"]} '
              f'({result["pred_change_rate"]:.1%})')
        print(f'    B wins: {result["when_diff"]["b_wins"]} vs A: {result["when_diff"]["a_wins"]}')
        print(f'    Perm p: {result["stats"]["perm_p"]:.4f}')
        print()

    # Verdict
    verdict = compute_verdict(all_results)
    elapsed = time.time() - t0

    print('=' * 70)
    print(f'GLOBAL VERDICT: {verdict["global_verdict"]}')
    print(f'  B wins total: {verdict["total_b_wins"]} vs A: {verdict["total_a_wins"]} '
          f'(B ratio: {verdict["total_b_ratio"]:.1%})')
    print(f'  Elapsed: {elapsed:.1f}s')
    print('=' * 70)

    # Save results
    out_dir = os.path.join(ROOT, 'research', 'analysis_outputs')
    os.makedirs(out_dir, exist_ok=True)

    json_path = os.path.join(out_dir, f'ab_decision_integration_{timestamp}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': timestamp,
            'test_draws': TEST_DRAWS,
            'n_perm': N_PERM,
            'configs': CONFIGS,
            'results': all_results,
            'verdict': verdict,
            'elapsed': elapsed,
        }, f, indent=2, ensure_ascii=False, default=str)
    print(f'JSON: {json_path}')

    # Markdown report
    report = format_report(all_results, verdict, elapsed)
    md_path = os.path.join(out_dir, f'ab_decision_integration_{timestamp}.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f'Report: {md_path}')


if __name__ == '__main__':
    main()
