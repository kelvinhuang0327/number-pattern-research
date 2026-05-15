#!/usr/bin/env python3
"""
Phase M — Winning Quality Integration A/B Validation
======================================================
Test whether anti-crowd + payout quality scoring improves expected value
over baseline scoring (prediction + learning only).

Pipeline A = baseline (no quality scoring, disable_quality=True)
Pipeline B = quality-aware (anti-crowd + payout quality bonuses)

Measures:
  - Prediction changes: how many draws produce different top-N selections
  - EV ratio: estimated expected value improvement via lower split risk
  - Popularity shift: avg popularity of selected numbers (lower = better)
  - Hit rate / Sharpe / edge: standard walk-forward metrics
  - Anti-crowd effect: birthday count, sequence density in selections

Statistical: permutation test, McNemar test

2026-04-16 Created — Phase M winning quality validation
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
from engine.winning_quality import (
    WinningQualityScorer, popularity_score, compute_anti_crowd_scores,
    estimate_ev_ratio, _per_number_popularity,
)

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
# Pipeline A: Baseline (no quality scoring)
# ═══════════════════════════════════════════════════════════════════════════

def predict_baseline(
    lottery_type: str,
    history: List[Dict],
    n_bets: int,
) -> Tuple[List[List[int]], Dict]:
    """Pipeline A: prediction + learning, NO quality scoring."""
    coord = StrategyCoordinator(
        lottery_type=lottery_type,
        disable_learning=False,
        disable_quality=True,
    )
    bets = coord.predict(history, n_bets=n_bets)
    return bets, {'pipeline': 'A_no_quality'}


# ═══════════════════════════════════════════════════════════════════════════
# Pipeline B: Quality-Aware (anti-crowd + payout quality)
# ═══════════════════════════════════════════════════════════════════════════

def predict_quality(
    lottery_type: str,
    history: List[Dict],
    n_bets: int,
) -> Tuple[List[List[int]], Dict]:
    """Pipeline B: prediction + learning + quality scoring."""
    coord = StrategyCoordinator(
        lottery_type=lottery_type,
        disable_learning=False,
        disable_quality=False,
    )
    bets = coord.predict(history, n_bets=n_bets)

    # Compute quality metrics for the selected bets
    scorer = WinningQualityScorer(lottery_type)
    bet_qualities = []
    for bet in bets:
        bet_qualities.append(scorer.score_bet(bet))

    avg_pop = np.mean([q['pop_score'] for q in bet_qualities]) if bet_qualities else 0
    avg_ev = np.mean([q['ev_ratio'] for q in bet_qualities]) if bet_qualities else 1.0
    avg_birthday = np.mean([q['birthday_count'] for q in bet_qualities]) if bet_qualities else 0

    return bets, {
        'pipeline': 'B_quality',
        'avg_pop_score': round(float(avg_pop), 2),
        'avg_ev_ratio': round(float(avg_ev), 4),
        'avg_birthday_count': round(float(avg_birthday), 2),
        'bet_qualities': bet_qualities,
    }


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
# Walk-forward Runner
# ═══════════════════════════════════════════════════════════════════════════

def run_quality_walkforward(
    lottery_type: str,
    n_bets: int,
    all_draws: List[Dict],
) -> Dict:
    """
    Walk-forward A/B: baseline (no quality) vs quality-aware scoring.
    """
    total = len(all_draws)
    start_idx = max(MIN_HISTORY, total - TEST_DRAWS)
    test_range = all_draws[start_idx:]
    threshold = 2 if lottery_type == 'DAILY_539' else 3

    results_a = []
    results_b = []
    prediction_diffs = []
    quality_info_snapshot = None

    # Aggregate quality metrics across draws
    all_pop_a = []
    all_pop_b = []
    all_ev_b = []
    all_birthday_a = []
    all_birthday_b = []

    scorer = WinningQualityScorer(lottery_type)

    for i, draw in enumerate(test_range):
        hist_idx = start_idx + i
        history = all_draws[:hist_idx]
        actual = draw['numbers']
        draw_key = draw['draw']

        # Pipeline A: no quality scoring
        bets_a, info_a = predict_baseline(lottery_type, history, n_bets)
        hit_a = compute_hits(bets_a, actual)

        # Pipeline B: quality-aware
        bets_b, info_b = predict_quality(lottery_type, history, n_bets)
        hit_b = compute_hits(bets_b, actual)

        if quality_info_snapshot is None and info_b.get('bet_qualities'):
            quality_info_snapshot = info_b

        # Track popularity / EV for both pipelines
        for bet in bets_a:
            pop_a = popularity_score(bet, lottery_type)
            all_pop_a.append(pop_a)
            all_birthday_a.append(sum(1 for n in bet if n <= 31))
        for bet in bets_b:
            pop_b = popularity_score(bet, lottery_type)
            all_pop_b.append(pop_b)
            all_ev_b.append(estimate_ev_ratio(lottery_type, bet))
            all_birthday_b.append(sum(1 for n in bet if n <= 31))

        results_a.append({
            'draw': draw_key, 'best_match': hit_a,
            'is_hit': hit_a >= threshold, 'n_bets': n_bets,
        })
        results_b.append({
            'draw': draw_key, 'best_match': hit_b,
            'is_hit': hit_b >= threshold, 'n_bets': n_bets,
        })

        set_a = set(tuple(sorted(b)) for b in bets_a)
        set_b = set(tuple(sorted(b)) for b in bets_b)
        if set_a != set_b:
            prediction_diffs.append({
                'draw': draw_key, 'idx': i,
                'bets_a': bets_a, 'bets_b': bets_b,
                'hit_a': hit_a, 'hit_b': hit_b,
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

    # Quality metrics summary
    quality_metrics = {
        'avg_pop_a': round(float(np.mean(all_pop_a)), 2) if all_pop_a else 0,
        'avg_pop_b': round(float(np.mean(all_pop_b)), 2) if all_pop_b else 0,
        'pop_delta': round(float(np.mean(all_pop_b) - np.mean(all_pop_a)), 2) if all_pop_a else 0,
        'avg_ev_ratio_b': round(float(np.mean(all_ev_b)), 4) if all_ev_b else 1.0,
        'avg_birthday_a': round(float(np.mean(all_birthday_a)), 2) if all_birthday_a else 0,
        'avg_birthday_b': round(float(np.mean(all_birthday_b)), 2) if all_birthday_b else 0,
    }

    return {
        'lottery_type': lottery_type,
        'n_bets': n_bets,
        'total_draws': len(results_a),
        'metrics': metrics,
        'stats': {'perm_p': round(perm_p, 6), 'mcnemar': mcnemar},
        'pred_changes': len(prediction_diffs),
        'pred_change_rate': round(len(prediction_diffs) / max(len(results_a), 1), 4),
        'when_diff': {'a_wins': diff_a_wins, 'b_wins': diff_b_wins, 'ties': diff_ties},
        'quality_metrics': quality_metrics,
        'quality_info': quality_info_snapshot or {},
        'hit_distribution': {'A': hit_dist_a, 'B': hit_dist_b},
        'sample_diffs': prediction_diffs[:3],
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

    per_lottery = {}
    for r in all_results:
        lt = r['lottery_type']
        bw = r['when_diff']['b_wins']
        aw = r['when_diff']['a_wins']
        b_ratio = bw / max(bw + aw, 1)
        p_value = r['stats']['perm_p']
        qm = r.get('quality_metrics', {})

        # Verdict per lottery type
        # For Phase M we also check quality improvement
        pop_improved = qm.get('pop_delta', 0) < 0  # lower popularity = better
        ev_improved = qm.get('avg_ev_ratio_b', 1.0) > 1.0

        if bw + aw < 10:
            verdict = 'INSUFFICIENT_DATA'
        elif b_ratio > 0.55 and p_value < 0.10:
            verdict = 'ACCEPT'
        elif b_ratio > 0.50 and (pop_improved or ev_improved):
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
            'pop_improved': pop_improved,
            'ev_improved': ev_improved,
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
        '# Phase M — Winning Quality Integration A/B Report',
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
        qm = r.get('quality_metrics', {})
        v = verdict['per_lottery'].get(lt, {})

        lines.append(f'## {lt}')
        lines.append(f'**Verdict**: {v.get("verdict", "N/A")}')
        lines.append(f'- Popularity improved: {v.get("pop_improved", "N/A")}')
        lines.append(f'- EV improved: {v.get("ev_improved", "N/A")}')
        lines.append(f'- Prediction changes: {r["pred_changes"]}/{r["total_draws"]} '
                      f'({r["pred_change_rate"]:.1%})')
        lines.append(f'- B wins: {r["when_diff"]["b_wins"]} vs A wins: {r["when_diff"]["a_wins"]}')
        lines.append(f'- Perm p-value: {r["stats"]["perm_p"]:.4f}')
        lines.append(f'- McNemar: chi2={r["stats"]["mcnemar"]["chi2"]}, '
                      f'p={r["stats"]["mcnemar"]["p"]:.4f}')
        lines.append('')

        # Quality metrics
        lines.append('**Quality Metrics**')
        lines.append(f'- Avg popularity A: {qm.get("avg_pop_a", "N/A")}')
        lines.append(f'- Avg popularity B: {qm.get("avg_pop_b", "N/A")}')
        lines.append(f'- Popularity delta: {qm.get("pop_delta", "N/A")} '
                      f'(negative = less popular = better EV)')
        lines.append(f'- Avg EV ratio B: {qm.get("avg_ev_ratio_b", "N/A")} '
                      f'(>1.0 = better than random)')
        lines.append(f'- Avg birthday nums A: {qm.get("avg_birthday_a", "N/A")}')
        lines.append(f'- Avg birthday nums B: {qm.get("avg_birthday_b", "N/A")}')
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

    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    t0 = time.time()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    print('=' * 70)
    print('Phase M — Winning Quality Integration A/B Validation')
    print('=' * 70)
    print(f'Configs: {CONFIGS}')
    print(f'Test draws: {TEST_DRAWS}, Perm tests: {N_PERM}')
    print()

    all_results = []

    for lottery_type, n_bets in CONFIGS:
        print(f'  [{lottery_type}] Loading draws...')
        draws = load_draws(lottery_type)
        print(f'    Total draws: {len(draws)}')

        # Show anti-crowd profile
        anti_crowd = compute_anti_crowd_scores(lottery_type)
        top_bonus = sorted(anti_crowd.items(), key=lambda x: x[1], reverse=True)[:5]
        top_penalty = sorted(anti_crowd.items(), key=lambda x: x[1])[:5]
        print(f'    Anti-crowd profile:')
        print(f'      Top bonus (unpopular): {[(n, round(b, 4)) for n, b in top_bonus]}')
        print(f'      Top penalty (popular): {[(n, round(b, 4)) for n, b in top_penalty]}')

        print(f'  [{lottery_type}] Running walk-forward A/B...')
        result = run_quality_walkforward(lottery_type, n_bets, draws)
        all_results.append(result)

        # Quick summary
        qm = result.get('quality_metrics', {})
        print(f'    Pred changes: {result["pred_changes"]}/{result["total_draws"]} '
              f'({result["pred_change_rate"]:.1%})')
        print(f'    B wins: {result["when_diff"]["b_wins"]} vs A: {result["when_diff"]["a_wins"]}')
        print(f'    Pop delta: {qm.get("pop_delta", "N/A")}')
        print(f'    Avg EV ratio B: {qm.get("avg_ev_ratio_b", "N/A")}')
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

    json_path = os.path.join(out_dir, f'ab_quality_integration_{timestamp}.json')
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
    md_path = os.path.join(out_dir, f'ab_quality_integration_{timestamp}.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f'Report: {md_path}')


if __name__ == '__main__':
    main()
