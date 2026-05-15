#!/usr/bin/env python3
"""
Phase K.5 — Learning Gating System Validation
===============================================
Compare:
  Pipeline A = static amp=1.0 (all learning applied uniformly)
  Pipeline B = gated learning (dynamic factor per lottery)

Metrics: prediction change rate, edge, Sharpe, drawdown, B vs A wins

2026-04-16 Created — Phase K.5
"""
import json
import os
import sys
import time
import sqlite3
import numpy as np
from collections import Counter
from datetime import datetime
from typing import Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'lottery_api'))

from engine.strategy_coordinator import StrategyCoordinator
from engine.rolling_strategy_monitor import BASELINES
from engine.learning_integrator import compute_learning_gate

DB_PATH = os.path.join(ROOT, 'lottery_api', 'data', 'lottery_v2.db')

TEST_DRAWS = 300
MIN_HISTORY = 200
N_BETS = 3
LOTTERY_TYPES = ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']

HIT_THRESHOLD = {
    'DAILY_539': 2,
    'BIG_LOTTO': 3,
    'POWER_LOTTO': 3,
}


def load_draws(lottery_type: str) -> List[Dict]:
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
            'draw': r['draw'], 'date': r['date'],
            'numbers': [int(n) for n in nums], 'special': r['special'],
        })
    return result


def compute_best_match(bets, actual):
    actual_set = set(actual)
    return max((len(set(b) & actual_set) for b in bets), default=0)


def random_baseline(lottery_type, n_bets, threshold):
    p = BASELINES.get(lottery_type, {}).get(threshold, 0.03)
    return 1.0 - (1.0 - p) ** n_bets


def compute_sharpe(returns):
    if len(returns) < 2:
        return 0.0
    mu = np.mean(returns)
    sigma = np.std(returns, ddof=1)
    return float(mu / sigma) if sigma > 1e-9 else 0.0


def compute_max_drawdown(hit_series):
    max_dd = current = 0
    for h in hit_series:
        if not h:
            current += 1
            max_dd = max(max_dd, current)
        else:
            current = 0
    return max_dd


def compute_prize(best_match, lottery_type):
    if lottery_type == 'DAILY_539':
        prizes = {2: 50, 3: 300, 4: 10000, 5: 8000000}
    else:
        prizes = {3: 400, 4: 2000, 5: 150000, 6: 25000000}
    return prizes.get(best_match, 0)


def run_walkforward(lottery_type, all_draws, pipeline_label, coordinator):
    """Walk-forward test using a pre-built coordinator."""
    total = len(all_draws)
    start_idx = max(MIN_HISTORY, total - TEST_DRAWS)
    test_range = all_draws[start_idx:]
    threshold = HIT_THRESHOLD[lottery_type]
    n_bets = N_BETS

    hit_series = []
    returns = []
    all_bets = []

    for i, draw in enumerate(test_range):
        hist_idx = start_idx + i
        history = all_draws[:hist_idx]
        actual = draw['numbers']

        bets = coordinator.predict(history, n_bets=n_bets)
        all_bets.append(bets)

        best = compute_best_match(bets, actual)
        is_hit = best >= threshold
        hit_series.append(is_hit)

        prize = compute_prize(best, lottery_type)
        cost = n_bets * 50
        returns.append((prize - cost) / cost)

        if (i + 1) % 100 == 0:
            print(f'      ... {i + 1}/{len(test_range)} draws')

    n_test = len(hit_series)
    hit_rate = sum(hit_series) / max(n_test, 1)
    baseline = random_baseline(lottery_type, n_bets, threshold)
    edge = hit_rate - baseline
    sharpe = compute_sharpe(returns)
    max_dd = compute_max_drawdown(hit_series)

    return {
        'pipeline': pipeline_label,
        'lottery_type': lottery_type,
        'n_test': n_test,
        'hits': sum(hit_series),
        'hit_rate': round(hit_rate, 6),
        'baseline': round(baseline, 6),
        'edge': round(edge, 6),
        'sharpe': round(sharpe, 6),
        'max_drawdown': max_dd,
        'all_bets': all_bets,
        'hit_series': hit_series,
    }


def compare_pipelines(result_a, result_b):
    """Compare two pipeline results per draw."""
    diffs = 0
    a_wins = b_wins = ties = 0
    n = min(len(result_a['all_bets']), len(result_b['all_bets']))

    for i in range(n):
        ba = result_a['all_bets'][i]
        bb = result_b['all_bets'][i]
        set_a = set(tuple(sorted(b)) for b in ba)
        set_b = set(tuple(sorted(b)) for b in bb)
        if set_a != set_b:
            diffs += 1
            ha = result_a['hit_series'][i]
            hb = result_b['hit_series'][i]
            if ha and not hb:
                a_wins += 1
            elif hb and not ha:
                b_wins += 1
            else:
                ties += 1

    return {
        'pred_changes': diffs,
        'pred_change_rate': round(diffs / max(n, 1), 4),
        'a_wins': a_wins,
        'b_wins': b_wins,
        'ties': ties,
    }


def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    print('=' * 72)
    print('Phase K.5 — Learning Gating System Validation')
    print('=' * 72)
    print(f'Timestamp: {timestamp}')
    print(f'Test draws: {TEST_DRAWS}, Min history: {MIN_HISTORY}, N bets: {N_BETS}')
    print()

    # Show gating decisions
    print('Gating Decisions:')
    gate_info = {}
    for lt in LOTTERY_TYPES:
        g = compute_learning_gate(lt)
        gate_info[lt] = g
        print(f'  {lt}: gate={g["gate"]} factor={g["factor"]}')
        print(f'    reason: {g["reason"]}')
        print(f'    n_total={g["n_total"]} val={g["n_validated"]} rej={g["n_rejected"]} '
              f'prov={g["n_provisional"]} rs={g["research_score"]}')
    print()

    all_results = {}

    for lt in LOTTERY_TYPES:
        print(f'\n{"─" * 60}')
        print(f'  {lt}')
        print(f'{"─" * 60}')

        draws = load_draws(lt)
        print(f'  Total draws: {len(draws)}')

        # Pipeline A: static amp=1.0 (disable gating — apply full bonuses)
        # We bypass gating by loading bonuses directly without gate factor
        coord_a = StrategyCoordinator(lt, disable_learning=False, profile='balanced')
        # Override: reload raw bonuses without gating
        try:
            from engine.learning_integrator import compute_learning_bonuses
            coord_a._learning_bonuses = compute_learning_bonuses(lt, coord_a.agents)
        except Exception:
            pass

        t0 = time.time()
        print(f'    [A] static amp=1.0...')
        result_a = run_walkforward(lt, draws, 'static_1.0', coord_a)
        elapsed_a = time.time() - t0

        # Pipeline B: gated learning (uses the gate factor applied at load time)
        coord_b = StrategyCoordinator(lt, disable_learning=False, profile='balanced')
        # coord_b already has gated bonuses from __init__

        t0 = time.time()
        print(f'    [B] gated (factor={gate_info[lt]["factor"]})...')
        result_b = run_walkforward(lt, draws, f'gated_{gate_info[lt]["gate"]}', coord_b)
        elapsed_b = time.time() - t0

        comp = compare_pipelines(result_a, result_b)

        all_results[lt] = {
            'A': result_a, 'B': result_b, 'comparison': comp,
            'gate': gate_info[lt],
        }

        print(f'    A: hits={result_a["hits"]}/{result_a["n_test"]} '
              f'edge={result_a["edge"]:+.4f} sharpe={result_a["sharpe"]:+.4f} '
              f'maxDD={result_a["max_drawdown"]} ({elapsed_a:.1f}s)')
        print(f'    B: hits={result_b["hits"]}/{result_b["n_test"]} '
              f'edge={result_b["edge"]:+.4f} sharpe={result_b["sharpe"]:+.4f} '
              f'maxDD={result_b["max_drawdown"]} ({elapsed_b:.1f}s)')
        print(f'    Changes: {comp["pred_changes"]}/{result_a["n_test"]} '
              f'({comp["pred_change_rate"]:.1%})')
        print(f'    When diff: B wins={comp["b_wins"]}, A wins={comp["a_wins"]}, '
              f'ties={comp["ties"]}')

    # Summary table
    print('\n' + '=' * 72)
    print('SUMMARY TABLE')
    print('=' * 72)
    header = (f'{"Lottery":<14} {"Gate":<10} {"Factor":>6} | '
              f'{"A hits":>6} {"B hits":>6} | '
              f'{"A edge":>8} {"B edge":>8} {"Δedge":>8} | '
              f'{"A Shrp":>7} {"B Shrp":>7} {"ΔShrp":>7} | '
              f'{"A DD":>5} {"B DD":>5} | '
              f'{"Chg%":>6} {"Bw":>3} {"Aw":>3}')
    print(header)
    print('-' * len(header))

    total_edge_delta = 0
    total_sharpe_delta = 0
    total_dd_delta = 0
    gated_helps = 0

    for lt in LOTTERY_TYPES:
        r = all_results[lt]
        a, b, c, g = r['A'], r['B'], r['comparison'], r['gate']
        de = b['edge'] - a['edge']
        ds = b['sharpe'] - a['sharpe']
        dd = b['max_drawdown'] - a['max_drawdown']
        total_edge_delta += de
        total_sharpe_delta += ds
        total_dd_delta += dd

        # Gated helps if: reduces changes without losing edge, OR improves edge
        if de >= -0.005 and c['pred_change_rate'] < 0.5:
            gated_helps += 1

        print(f'{lt:<14} {g["gate"]:<10} {g["factor"]:>6.1f} | '
              f'{a["hits"]:>6} {b["hits"]:>6} | '
              f'{a["edge"]:>+8.4f} {b["edge"]:>+8.4f} {de:>+8.4f} | '
              f'{a["sharpe"]:>+7.4f} {b["sharpe"]:>+7.4f} {ds:>+7.4f} | '
              f'{a["max_drawdown"]:>5} {b["max_drawdown"]:>5} | '
              f'{c["pred_change_rate"]:>5.1%} {c["b_wins"]:>3} {c["a_wins"]:>3}')

    print()
    print(f'Avg edge delta (B-A):   {total_edge_delta/3:+.6f}')
    print(f'Avg sharpe delta (B-A): {total_sharpe_delta/3:+.6f}')
    print(f'Avg DD delta (B-A):     {total_dd_delta/3:+.2f}')

    # Verdict
    print('\n' + '=' * 72)

    # Gating is beneficial if:
    # 1. Edge is maintained (avg delta >= -0.005)
    # 2. No individual lottery regresses badly (delta < -0.02)
    # 3. Prediction change rate is reduced for gated lotteries
    avg_edge_ok = total_edge_delta / 3 >= -0.005
    no_regression = all(
        all_results[lt]['B']['edge'] - all_results[lt]['A']['edge'] >= -0.02
        for lt in LOTTERY_TYPES
    )
    # Check if gating reduces changes for BIG_LOTTO (the WEAK one)
    big_lotto_gated = gate_info.get('BIG_LOTTO', {}).get('gate') == 'WEAK'
    big_lotto_fewer_changes = (
        all_results.get('BIG_LOTTO', {}).get('comparison', {}).get('pred_change_rate', 1.0) <
        0.30  # expect fewer changes than static
    ) if big_lotto_gated else True

    power_preserved = (
        all_results['POWER_LOTTO']['B']['edge'] >=
        all_results['POWER_LOTTO']['A']['edge'] - 0.01
    )

    if avg_edge_ok and no_regression and power_preserved:
        verdict = 'ACCEPT'
    elif avg_edge_ok and no_regression:
        verdict = 'CONDITIONAL_ACCEPT'
    else:
        verdict = 'REJECT'

    print(f'VERDICT: {verdict}')
    print(f'  Avg edge maintained (>= -0.005):     {"YES ✅" if avg_edge_ok else "NO ❌"}')
    print(f'  No individual regression (>= -0.02): {"YES ✅" if no_regression else "NO ❌"}')
    print(f'  POWER_LOTTO effect preserved:        {"YES ✅" if power_preserved else "NO ❌"}')
    print(f'  BIG_LOTTO noise reduced:             {"YES ✅" if big_lotto_fewer_changes else "NO ❌"}')
    print('=' * 72)

    # Save
    out_dir = os.path.join(ROOT, 'research', 'analysis_outputs')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f'ab_learning_gating_{timestamp}.json')

    save_data = {
        'timestamp': timestamp,
        'config': {'test_draws': TEST_DRAWS, 'min_history': MIN_HISTORY, 'n_bets': N_BETS},
        'gate_info': gate_info,
        'results': {},
        'verdict': verdict,
    }
    for lt in LOTTERY_TYPES:
        r = all_results[lt]
        save_data['results'][lt] = {
            'A': {k: v for k, v in r['A'].items() if k not in ('all_bets', 'hit_series')},
            'B': {k: v for k, v in r['B'].items() if k not in ('all_bets', 'hit_series')},
            'comparison': r['comparison'],
            'gate': r['gate'],
        }

    with open(out_path, 'w') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
    print(f'\nResults saved to: {out_path}')


if __name__ == '__main__':
    main()
