#!/usr/bin/env python3
"""
Phase K — Learning Amplification Test
======================================
Test whether increasing learning bonus magnitude improves predictions
WITHOUT changing hypothesis, validator, or refined_status.

Pipeline A = baseline (disable_learning=True)
Pipeline B = amplified learning (bonuses × amplification_factor)

Tests amplification_factor ∈ [1.0, 2.0, 3.0]
Compares: prediction change rate, edge Δ, Sharpe Δ, drawdown Δ, B vs A wins

2026-04-16 Created — Phase K amplification test
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
AMPLIFICATION_FACTORS = [1.0, 2.0, 3.0]
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
# Prediction with amplified learning
# ═══════════════════════════════════════════════════════════════════════════

def predict_amplified(
    lottery_type: str,
    history: List[Dict],
    n_bets: int,
    amplification_factor: float,
) -> Tuple[List[List[int]], Dict[str, float], Dict[str, float]]:
    """
    Create StrategyCoordinator with learning enabled, then amplify bonuses.
    amplification_factor=0 → baseline (no learning)
    amplification_factor=1.0 → current learning (Phase J baseline)
    amplification_factor=2.0 → doubled learning signal
    """
    if amplification_factor == 0:
        coord = StrategyCoordinator(lottery_type=lottery_type, disable_learning=True,
                                    profile='balanced')
    else:
        coord = StrategyCoordinator(lottery_type=lottery_type, disable_learning=False,
                                    profile='balanced')
        # Amplify bonuses in-place (does NOT touch hypothesis/validator/refined_status)
        if amplification_factor != 1.0:
            coord._learning_bonuses = {
                agent: bonus * amplification_factor
                for agent, bonus in coord._learning_bonuses.items()
            }

    bets = coord.predict(history, n_bets=n_bets)
    bonuses = dict(coord._learning_bonuses)
    return bets, bonuses


def predict_baseline(
    lottery_type: str,
    history: List[Dict],
    n_bets: int,
) -> List[List[int]]:
    """Pipeline A: no learning (balanced profile for clean isolation)."""
    coord = StrategyCoordinator(lottery_type=lottery_type, disable_learning=True,
                                profile='balanced')
    return coord.predict(history, n_bets=n_bets)


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
# Walk-forward runner for ONE amplification factor
# ═══════════════════════════════════════════════════════════════════════════

def run_amplified_walkforward(
    lottery_type: str,
    n_bets: int,
    amp_factor: float,
    all_draws: List[Dict],
    baseline_cache: Dict[str, List[List[int]]],  # draw_key → baseline bets
) -> Dict:
    """
    Walk-forward A/B test for a given amplification factor.
    Uses baseline_cache to avoid redundant Pipeline A runs.
    """
    total = len(all_draws)
    start_idx = max(MIN_HISTORY, total - TEST_DRAWS)
    test_range = all_draws[start_idx:]
    threshold = 2 if lottery_type == 'DAILY_539' else 3

    results_a = []
    results_b = []
    prediction_diffs = []
    bonuses_snapshot = None

    # Create coordinators ONCE and reuse across draws for speed
    coord_a = StrategyCoordinator(lottery_type=lottery_type, disable_learning=True,
                                  profile='balanced')
    coord_b = StrategyCoordinator(lottery_type=lottery_type, disable_learning=False,
                                  profile='balanced')
    if amp_factor != 1.0:
        coord_b._learning_bonuses = {
            agent: bonus * amp_factor
            for agent, bonus in coord_b._learning_bonuses.items()
        }

    for i, draw in enumerate(test_range):
        hist_idx = start_idx + i
        history = all_draws[:hist_idx]
        actual = draw['numbers']
        draw_key = draw['draw']

        # Pipeline A: use cache
        if draw_key in baseline_cache:
            bets_a = baseline_cache[draw_key]
        else:
            bets_a = coord_a.predict(history, n_bets=n_bets)
            baseline_cache[draw_key] = bets_a

        hit_a = compute_hits(bets_a, actual)

        # Pipeline B: amplified learning (reuse coordinator)
        bets_b = coord_b.predict(history, n_bets=n_bets)
        bonuses_b = dict(coord_b._learning_bonuses)
        hit_b = compute_hits(bets_b, actual)

        if bonuses_snapshot is None and bonuses_b:
            bonuses_snapshot = {k: round(v, 6) for k, v in bonuses_b.items()}

        results_a.append({'draw': draw_key, 'best_match': hit_a, 'is_hit': hit_a >= threshold})
        results_b.append({'draw': draw_key, 'best_match': hit_b, 'is_hit': hit_b >= threshold})

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

    # Metrics
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

    # Stats
    hits_a_bool = [r['is_hit'] for r in results_a]
    hits_b_bool = [r['is_hit'] for r in results_b]
    perm_p = permutation_test(hits_a_bool, hits_b_bool, N_PERM)
    mcnemar = mcnemar_test(hits_a_bool, hits_b_bool)

    # Diff wins
    diff_a_wins = sum(1 for d in prediction_diffs if d['hit_a'] > d['hit_b'])
    diff_b_wins = sum(1 for d in prediction_diffs if d['hit_b'] > d['hit_a'])
    diff_ties = len(prediction_diffs) - diff_a_wins - diff_b_wins

    # Bonus magnitudes
    bonus_mags = [abs(v) for v in (bonuses_snapshot or {}).values()]

    return {
        'lottery_type': lottery_type,
        'n_bets': n_bets,
        'amp_factor': amp_factor,
        'total_draws': len(results_a),
        'metrics': metrics,
        'stats': {'perm_p': round(perm_p, 6), 'mcnemar': mcnemar},
        'pred_changes': len(prediction_diffs),
        'pred_change_rate': round(len(prediction_diffs) / max(len(results_a), 1), 4),
        'when_diff': {'a_wins': diff_a_wins, 'b_wins': diff_b_wins, 'ties': diff_ties},
        'bonuses_applied': bonuses_snapshot or {},
        'avg_bonus_mag': round(np.mean(bonus_mags), 6) if bonus_mags else 0.0,
        'max_bonus_mag': round(max(bonus_mags), 6) if bonus_mags else 0.0,
        'sample_diffs': prediction_diffs[:3],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Comparative Analysis
# ═══════════════════════════════════════════════════════════════════════════

def analyze_stability(results_by_factor: Dict[float, List[Dict]]) -> Dict:
    """Check for over-amplification instability."""
    stability = {}
    for amp, results in results_by_factor.items():
        total_pred_changes = sum(r['pred_changes'] for r in results)
        total_draws = sum(r['total_draws'] for r in results)
        total_b_wins = sum(r['when_diff']['b_wins'] for r in results)
        total_a_wins = sum(r['when_diff']['a_wins'] for r in results)

        # Edge deltas at W300
        edge_deltas_300 = []
        sharpe_deltas_300 = []
        dd_deltas_300 = []
        for r in results:
            if 'window_300' in r['metrics']:
                edge_deltas_300.append(r['metrics']['window_300']['delta']['edge'])
                sharpe_deltas_300.append(r['metrics']['window_300']['delta']['sharpe'])
                dd_deltas_300.append(r['metrics']['window_300']['delta']['max_drawdown'])

        stability[amp] = {
            'pred_change_rate': round(total_pred_changes / max(total_draws, 1), 4),
            'b_win_ratio': round(total_b_wins / max(total_b_wins + total_a_wins, 1), 4),
            'avg_edge_delta_300': round(np.mean(edge_deltas_300), 6) if edge_deltas_300 else 0.0,
            'avg_sharpe_delta_300': round(np.mean(sharpe_deltas_300), 6) if sharpe_deltas_300 else 0.0,
            'avg_dd_delta_300': round(np.mean(dd_deltas_300), 4) if dd_deltas_300 else 0.0,
            'total_pred_changes': total_pred_changes,
            'total_draws': total_draws,
            'total_b_wins': total_b_wins,
            'total_a_wins': total_a_wins,
        }
    return stability


def detect_instability(stability: Dict) -> List[str]:
    """Detect signs of over-amplification."""
    warnings = []
    factors = sorted(stability.keys())
    if len(factors) < 2:
        return warnings

    for i in range(1, len(factors)):
        prev_f = factors[i - 1]
        curr_f = factors[i]
        prev = stability[prev_f]
        curr = stability[curr_f]

        # Instability: prediction change rate jumps > 50% absolute
        if curr['pred_change_rate'] > 0.50:
            warnings.append(
                f'amp={curr_f}: pred_change_rate={curr["pred_change_rate"]:.1%} '
                f'(>50% — over-amplification risk)')

        # Instability: B win ratio drops below 0.4 (learning hurts)
        if curr['total_b_wins'] + curr['total_a_wins'] > 5 and curr['b_win_ratio'] < 0.40:
            warnings.append(
                f'amp={curr_f}: B win ratio={curr["b_win_ratio"]:.1%} '
                f'(<40% — amplification is counterproductive)')

        # Instability: edge delta becomes more negative with higher amplification
        if (curr['avg_edge_delta_300'] < prev['avg_edge_delta_300']
                and curr['avg_edge_delta_300'] < -0.005):
            warnings.append(
                f'amp={curr_f}: avg_edge_delta_300={curr["avg_edge_delta_300"]:.4f} '
                f'(worse than amp={prev_f} — diminishing returns)')

    return warnings


# ═══════════════════════════════════════════════════════════════════════════
# Report Formatter
# ═══════════════════════════════════════════════════════════════════════════

def format_report(results_by_factor: Dict, stability: Dict, instability_warnings: List[str]) -> str:
    lines = []
    lines.append('=' * 72)
    lines.append('Phase K — Learning Amplification Test')
    lines.append(f'Run date: {datetime.now().isoformat()}')
    lines.append(f'Amplification factors tested: {sorted(results_by_factor.keys())}')
    lines.append('=' * 72)

    # ── 1. Amplification Comparison Table ──
    lines.append('\n## 1. Amplification Factor Comparison\n')
    lines.append(f'{"Factor":<8} | {"Pred Changes":<14} | {"Change Rate":<12} | '
                 f'{"B wins":<8} {"A wins":<8} {"B ratio":<8} | '
                 f'{"Avg Edge Δ@300":<16} {"Avg Sharpe Δ@300":<18} {"Avg DD Δ@300":<14}')
    lines.append('-' * 120)
    for amp in sorted(stability.keys()):
        s = stability[amp]
        lines.append(
            f'{amp:<8.1f} | {s["total_pred_changes"]:>5}/{s["total_draws"]:<8} | '
            f'{s["pred_change_rate"]:<12.4f} | '
            f'{s["total_b_wins"]:<8} {s["total_a_wins"]:<8} {s["b_win_ratio"]:<8.4f} | '
            f'{s["avg_edge_delta_300"]:+<16.6f} {s["avg_sharpe_delta_300"]:+<18.6f} {s["avg_dd_delta_300"]:+<14.4f}'
        )

    # ── 2. Per-Lottery Detailed Metrics ──
    lines.append('\n## 2. Per-Lottery × Per-Factor Metrics\n')
    for amp in sorted(results_by_factor.keys()):
        lines.append(f'### Amplification Factor = {amp:.1f}\n')
        for r in results_by_factor[amp]:
            lt = r['lottery_type']
            lines.append(f'#### {lt} (amp={amp})')
            lines.append(f'  Pred changes: {r["pred_changes"]}/{r["total_draws"]} '
                          f'({r["pred_change_rate"]:.1%})')
            wd = r['when_diff']
            lines.append(f'  When diff: B wins={wd["b_wins"]}, A wins={wd["a_wins"]}, ties={wd["ties"]}')
            lines.append(f'  Bonuses (amp×{amp}): avg={r["avg_bonus_mag"]:.6f}, max={r["max_bonus_mag"]:.6f}')

            for wk in ['window_30', 'window_100', 'window_300']:
                if wk not in r['metrics']:
                    continue
                m = r['metrics'][wk]
                w_label = wk.replace('window_', 'W')
                d = m['delta']
                lines.append(
                    f'    {w_label}: edge Δ={d["edge"]:+.5f}  '
                    f'sharpe Δ={d["sharpe"]:+.5f}  '
                    f'DD Δ={d["max_drawdown"]:+.4f}  '
                    f'(A hit={m["A"]["hits"]}/{m["A"]["n"]}, '
                    f'B hit={m["B"]["hits"]}/{m["B"]["n"]})')

            st = r['stats']
            lines.append(f'  Permutation p={st["perm_p"]:.6f}')
            mc = st['mcnemar']
            lines.append(f'  McNemar: b01={mc["b01"]}, b10={mc["b10"]}, p={mc["p"]}')

            if r['sample_diffs']:
                sd = r['sample_diffs'][0]
                lines.append(f'  Sample diff draw={sd["draw"]}:')
                lines.append(f'    A: {sd["bets_a"]} → hit={sd["hit_a"]}')
                lines.append(f'    B: {sd["bets_b"]} → hit={sd["hit_b"]}')
            lines.append('')

    # ── 3. Instability Analysis ──
    lines.append('\n## 3. Over-Amplification Instability Check\n')
    if instability_warnings:
        lines.append('⚠️  WARNINGS DETECTED:\n')
        for w in instability_warnings:
            lines.append(f'  - {w}')
    else:
        lines.append('✅ No instability detected across all amplification factors.')

    # ── 4. Key Questions Answered ──
    lines.append('\n## 4. Key Questions\n')

    # Q1: Is ranking actually shifting?
    factors = sorted(stability.keys())
    lines.append('### Q1: Is ranking actually shifting?')
    for amp in factors:
        s = stability[amp]
        lines.append(f'  amp={amp}: {s["total_pred_changes"]}/{s["total_draws"]} predictions differ '
                      f'({s["pred_change_rate"]:.1%})')
    q1_trend = stability[factors[-1]]['pred_change_rate'] > stability[factors[0]]['pred_change_rate']
    lines.append(f'  → {"YES" if q1_trend else "NO"}: '
                 f'Higher amplification {"increases" if q1_trend else "does not increase"} ranking changes.\n')

    # Q2: Does Sharpe improve further?
    lines.append('### Q2: Does Sharpe improve further?')
    best_sharpe_amp = max(factors, key=lambda f: stability[f]['avg_sharpe_delta_300'])
    for amp in factors:
        s = stability[amp]
        marker = ' ← best' if amp == best_sharpe_amp else ''
        lines.append(f'  amp={amp}: avg Sharpe Δ@300 = {s["avg_sharpe_delta_300"]:+.6f}{marker}')
    lines.append(f'  → Best Sharpe at amp={best_sharpe_amp}\n')

    # Q3: Any over-amplification instability?
    lines.append('### Q3: Any over-amplification instability?')
    if instability_warnings:
        lines.append(f'  → YES: {len(instability_warnings)} warning(s) detected.')
    else:
        lines.append('  → NO: All factors are stable.')

    # ── 5. Verdict ──
    lines.append('\n## 5. Amplification Verdict\n')
    best_composite_amp = max(factors, key=lambda f: (
        stability[f]['avg_sharpe_delta_300'] * 3 +  # Sharpe weighted highest
        stability[f]['avg_edge_delta_300'] * 2 +
        (stability[f]['b_win_ratio'] - 0.5) * 2 +
        (-stability[f]['avg_dd_delta_300']) * 0.5
    ))
    best = stability[best_composite_amp]

    if instability_warnings and best_composite_amp == factors[-1]:
        lines.append(f'  RECOMMEND: amp={factors[-2]} (highest stable factor)')
        lines.append(f'  REASON: amp={best_composite_amp} shows instability warnings')
    elif best['avg_sharpe_delta_300'] > 0 or best['b_win_ratio'] > 0.55:
        lines.append(f'  RECOMMEND: amp={best_composite_amp}')
        lines.append(f'  REASON: Best composite score '
                      f'(Sharpe Δ={best["avg_sharpe_delta_300"]:+.6f}, '
                      f'B ratio={best["b_win_ratio"]:.1%}, '
                      f'Edge Δ={best["avg_edge_delta_300"]:+.6f})')
    else:
        lines.append(f'  RECOMMEND: amp=1.0 (keep current)')
        lines.append(f'  REASON: No amplification factor shows clear improvement')

    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print('Phase K — Learning Amplification Test')
    print('=' * 60)
    print(f'Amplification factors: {AMPLIFICATION_FACTORS}')
    print(f'Lottery configs: {CONFIGS}')
    print(f'Test draws: {TEST_DRAWS}, Min history: {MIN_HISTORY}')
    print()
    start_time = time.time()

    # Pre-load draws for each lottery type (shared across all factors)
    draws_cache: Dict[str, List[Dict]] = {}
    for lt, _ in CONFIGS:
        if lt not in draws_cache:
            draws_cache[lt] = load_draws(lt, limit=2000)
            print(f'  Loaded {lt}: {len(draws_cache[lt])} draws')

    results_by_factor: Dict[float, List[Dict]] = {}

    for amp in AMPLIFICATION_FACTORS:
        print(f'\n{"="*60}')
        print(f'  Testing amplification_factor = {amp:.1f}')
        print(f'{"="*60}')

        baseline_cache: Dict[str, List[List[int]]] = {}
        factor_results = []

        for lt, nb in CONFIGS:
            print(f'    [{lt}] amp={amp:.1f}, {nb}-bet, {TEST_DRAWS} draws...')
            result = run_amplified_walkforward(
                lt, nb, amp, draws_cache[lt], baseline_cache
            )
            factor_results.append(result)
            print(f'      → pred_changes={result["pred_changes"]}, '
                  f'B wins={result["when_diff"]["b_wins"]}, '
                  f'A wins={result["when_diff"]["a_wins"]}')

        results_by_factor[amp] = factor_results

    # Analysis
    stability = analyze_stability(results_by_factor)
    instability_warnings = detect_instability(stability)

    report = format_report(results_by_factor, stability, instability_warnings)

    elapsed = time.time() - start_time
    print('\n' + report)
    print(f'\nTotal elapsed: {elapsed:.1f}s')

    # Save outputs
    out_dir = os.path.join(ROOT, 'research', 'analysis_outputs')
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    json_path = os.path.join(out_dir, f'ab_amplified_learning_{ts}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'run_date': datetime.now().isoformat(),
            'elapsed_seconds': round(elapsed, 1),
            'amplification_factors': AMPLIFICATION_FACTORS,
            'configs': [{'lottery_type': lt, 'n_bets': nb} for lt, nb in CONFIGS],
            'results_by_factor': {str(k): v for k, v in results_by_factor.items()},
            'stability': {str(k): v for k, v in stability.items()},
            'instability_warnings': instability_warnings,
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f'JSON saved: {json_path}')

    report_path = os.path.join(out_dir, f'ab_amplified_learning_{ts}.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f'Report saved: {report_path}')


if __name__ == '__main__':
    main()
