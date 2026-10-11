#!/usr/bin/env python3
"""
Multi-arm P3 re-validation for BIG_LOTTO 5-bet orthogonal, 2026-07-24.
Reuses tools/p3_shuffle_permutation_test.py's actual functions unmodified
(bl_ts3_markov4_freqortho5, run_permutation_test, shuffle_draws, run_single_backtest)
to isolate 3 independent variables:
  DATA  in {raw (get_all_draws), canonical (get_canonical_draws)}
  CODE  in {frozen (as validated 2026-02-18), production (current quick_predict.py)}
Protocol held fixed at the ORIGINAL: 200 shuffles, 1500 periods, seed=42.

DB snapshot used: lottery_api/data/lottery_v2.db, sha256=0fec7eb37c044b73240d4f8
802ee2576c1e9eb801d40d39726786a4495e052d3 (2127 canonical BIG_LOTTO draws,
matches the same hash independently recorded by the same-day P1-family
revalidation session, confirming no drift between the two investigations).
Results: docs/P3_BL_5BET_PERMUTATION_RETEST_20260724.json
"""
import os
import sys
import time
import json
import argparse

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from tools.p3_shuffle_permutation_test import (
    bl_ts3_markov4_freqortho5, run_permutation_test, BL_P_SINGLE,
)
from tools.quick_predict import biglotto_5bet_orthogonal as production_5bet_dict


def production_5bet(history):
    """Adapter: quick_predict.py's biglotto_5bet_orthogonal returns
    [{'numbers': [...]}, ...]; P3 harness needs [[...], ...]."""
    return [b['numbers'] for b in production_5bet_dict(history)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shuffles', type=int, default=200)
    ap.add_argument('--periods', type=int, default=1500)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--arms', type=str, default='raw_frozen,raw_prod,canon_frozen,canon_prod')
    ap.add_argument('--out', type=str, default=None)
    args = ap.parse_args()

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)

    raw_draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    canon_draws = sorted(db.get_canonical_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    print(f"raw pool={len(raw_draws)}  canonical pool={len(canon_draws)}")

    arm_defs = {
        'raw_frozen':   (raw_draws,   bl_ts3_markov4_freqortho5, 'RAW data / FROZEN (P3-validated) code'),
        'raw_prod':     (raw_draws,   production_5bet,           'RAW data / PRODUCTION (current quick_predict) code'),
        'canon_frozen': (canon_draws, bl_ts3_markov4_freqortho5, 'CANONICAL data / FROZEN code'),
        'canon_prod':   (canon_draws, production_5bet,           'CANONICAL data / PRODUCTION code'),
    }

    wanted = args.arms.split(',')
    results = {}
    for name in wanted:
        draws, strategy_func, label = arm_defs[name]
        print(f"\n{'='*80}\nARM: {name}  ({label})\n{'='*80}")
        t0 = time.time()
        r = run_permutation_test(
            draws, strategy_func, 5, args.periods, BL_P_SINGLE,
            n_shuffles=args.shuffles, seed=args.seed,
        )
        elapsed = time.time() - t0
        p = r['p_value']
        verdict = "SIGNAL DETECTED" if p <= 0.05 else ("MARGINAL" if p <= 0.10 else "NO SIGNAL")
        print(f"  real_edge={r['real_edge']*100:+.2f}%  shuffle_mean={r['shuffle_mean']*100:+.2f}%  "
              f"shuffle_std={r['shuffle_std']*100:.2f}%")
        print(f"  p_value={p:.4f}  cohens_d={r['cohens_d']:.2f}  verdict={verdict}  "
              f"(real hits={r['real_result']['hits']}/{r['real_result']['total']})  [{elapsed:.1f}s]")
        results[name] = {
            'label': label,
            'real_edge_pct': round(r['real_edge'] * 100, 3),
            'shuffle_mean_pct': round(r['shuffle_mean'] * 100, 3),
            'shuffle_std_pct': round(r['shuffle_std'] * 100, 3),
            'p_value': round(p, 4),
            'cohens_d': round(r['cohens_d'], 3),
            'verdict': verdict,
            'real_hits': r['real_result']['hits'],
            'real_total': r['real_result']['total'],
            'elapsed_sec': round(elapsed, 1),
            'shuffle_edges_pct': [round(se * 100, 3) for se in r['shuffle_edges']],
        }

    out = {
        'date': '2026-07-24',
        'protocol': 'P3 Shuffle Permutation Test (multi-arm re-validation)',
        'parameters': {'n_shuffles': args.shuffles, 'n_periods': args.periods, 'seed': args.seed},
        'original_2026_02_18_baseline': {
            'real_edge_pct': 1.77, 'p_value': 0.0299, 'cohens_d': 2.13, 'verdict': 'SIGNAL DETECTED',
        },
        'arms': results,
    }
    if args.out:
        with open(args.out, 'w') as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"\nSaved to {args.out}")


if __name__ == '__main__':
    main()
