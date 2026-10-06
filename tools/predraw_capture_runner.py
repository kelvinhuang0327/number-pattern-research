#!/usr/bin/env python3
"""
P364: explicit opt-in predraw ledger capture runner.

Why this exists (P363 follow-on): P363 established that no automatic
post-draw hook is safe today -- `tools/post_draw_pipeline.py` does not exist
on this branch, and `lottery_api/routes/ingest.py`'s post-insert hooks are
shared identically by live-fetch and backfill/replay with no distinguishing
context. Explicit operator invocation IS therefore the live/backfill
boundary: this runner is only ever executed deliberately, before a genuinely
upcoming draw, by an operator (or an operator-configured scheduler).

Safety properties:
  - Explicit opt-in only: without --write-predraw-ledger this runner reads
    nothing, generates nothing, writes nothing, and exits with code 2. The
    LOTTERY_PREDRAW_LEDGER_PATH env var alone is NOT accepted as opt-in here
    (unlike tools/quick_predict.py): a dedicated capture command must be
    invoked deliberately, never armed by inherited environment. Once the
    flag is given, the env var still participates in ledger PATH resolution.
  - The source DB is opened strictly read-only: history via
    quick_predict.load_history_readonly (sqlite mode=ro) and the liveness
    witness via predraw_ledger.compute_max_source_draw (mode=ro + PRAGMA
    query_only). This module never opens the canonical lottery_v2.db for
    write and never uses the read-write database-manager code path.
  - All ledger writes go through the existing P360B entrypoint
    quick_predict.write_predraw_ledger_for_prediction(), which only calls
    the P360A live-prediction writer API. LIVE_PREDRAW witness conditions
    are enforced and fail closed: a stale or backfill-era source DB (whose
    derived next-draw close time is already in the past) yields ZERO
    records rather than a mislabeled one, and this runner then exits
    non-zero.
  - No replay/backfill surface: there is no argument to target a past draw,
    backdate the prediction timestamp, choose a generation mode, or set a
    history cutoff. The retrospective/backfill writer API is never
    referenced by this module.
  - Safe output: stdout carries capture metadata only (lottery type, bet
    counts, record counts, chain status, ledger path). Predicted numbers
    are never printed by this runner; quick_predict's display path is not
    invoked.
  - Capturing a LIVE_PREDRAW record is NOT a predictive claim, a bet
    recommendation, or evidence that any strategy has edge. It only enables
    a FUTURE honest OOS audit once the pre-registered minimum N of live
    records accumulates (docs/p360a_predraw_metadata_preregistration.md).

Usage:
  python3 tools/predraw_capture_runner.py --write-predraw-ledger \
      [--lottery BIG_LOTTO|POWER_LOTTO|DAILY_539|ALL] [--bets N] \
      [--predraw-ledger-path PATH]

Exit codes:
  0 = every requested lottery captured and the ledger hash chain verified
  1 = capture incomplete/failed (including refused ledger paths)
  2 = refused: --write-predraw-ledger not given (nothing was done)
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import tools.quick_predict as qp  # noqa: E402
from lottery_api.engine import predraw_ledger as pl  # noqa: E402

EXIT_OK = 0
EXIT_CAPTURE_INCOMPLETE = 1
EXIT_NO_OPT_IN = 2

GENERATION_SOURCE = 'tools/predraw_capture_runner.py'
ALL_LOTTERY_TYPES = ('BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539')
MIN_HISTORY_ROWS = 50  # mirrors tools/quick_predict.py main()

_RULES_MAP = {
    'BIG_LOTTO': {'pickCount': 6, 'minNumber': 1, 'maxNumber': 49, 'specialMaxNumber': 49},
    'POWER_LOTTO': {'pickCount': 6, 'minNumber': 1, 'maxNumber': 38, 'specialMaxNumber': 8},
    'DAILY_539': {'pickCount': 5, 'minNumber': 1, 'maxNumber': 39, 'specialMaxNumber': 0},
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            'P364 explicit opt-in predraw ledger capture runner. Appends '
            'LIVE_PREDRAW records for the upcoming draw to the P360A append-only '
            'sidecar ledger via the existing quick_predict/P360B write path. '
            'Refuses to do anything without --write-predraw-ledger. Never opens '
            'the canonical DB for write. Prints capture metadata only, never '
            'predicted numbers. Not a prediction or betting recommendation tool.'
        )
    )
    parser.add_argument('--lottery', choices=list(ALL_LOTTERY_TYPES) + ['ALL'], default='ALL',
                        help='lottery type to capture (default: ALL)')
    parser.add_argument('--bets', type=int, default=None,
                        help='bets per lottery (default: per-lottery production default)')
    parser.add_argument('--write-predraw-ledger', action='store_true',
                        help='REQUIRED explicit opt-in. Without this flag the runner writes '
                             'nothing and exits 2 (the LOTTERY_PREDRAW_LEDGER_PATH env var '
                             'alone is NOT accepted as opt-in by this runner).')
    parser.add_argument('--predraw-ledger-path', default=None,
                        help='override the ledger JSONL path (never the canonical DB). '
                             'Resolution: this flag > LOTTERY_PREDRAW_LEDGER_PATH env > '
                             'P360A module default sidecar.')
    return parser


def capture_one(lottery_type, requested_bets, run_id, ledger_path_arg, resolved_ledger_path):
    """
    Generate bets with the existing quick_predict strategy dispatch, append
    them via the existing P360B opt-in writer, then verify by re-reading the
    ledger. The returned dict carries metadata only -- never predicted
    numbers.
    """
    history = qp.load_history_readonly(lottery_type)
    if not history or len(history) < MIN_HISTORY_ROWS:
        return {
            'lottery_type': lottery_type,
            'status': 'SKIPPED_INSUFFICIENT_HISTORY',
            'history_rows': len(history) if history else 0,
            'bets_generated': 0,
            'records_written': 0,
            'strategy_id': None,
        }

    num_bets = requested_bets or qp.DEFAULT_CONFIG.get(lottery_type, {}).get('bets', 3)
    rules = _RULES_MAP[lottery_type]
    if lottery_type == 'BIG_LOTTO':
        bets, _strategy = qp.predict_biglotto(history, rules, num_bets)
    elif lottery_type == 'POWER_LOTTO':
        bets, _strategy = qp.predict_power(history, rules, num_bets)
    else:
        bets, _strategy = qp.predict_539(history, rules, num_bets)

    qp.write_predraw_ledger_for_prediction(
        lottery_type, bets, num_bets, history, run_id, ledger_path_arg,
        generation_source=GENERATION_SOURCE,
    )

    written = [
        rec for rec in pl.read_all_records(resolved_ledger_path)
        if rec.get('run_id') == run_id
        and rec.get('lottery_type') == lottery_type
        and rec.get('record_kind', 'PREDICTION') == 'PREDICTION'
    ]
    captured = len(bets) > 0 and len(written) == len(bets)
    return {
        'lottery_type': lottery_type,
        'status': 'CAPTURED' if captured else 'NOT_CAPTURED',
        'history_rows': len(history),
        'bets_generated': len(bets),
        'records_written': len(written),
        'strategy_id': written[0].get('strategy_id') if written else None,
    }


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.bets is not None and args.bets < 1:
        parser.error('--bets must be >= 1')

    if not args.write_predraw_ledger:
        print('[predraw-capture] REFUSED: --write-predraw-ledger was not given. '
              'This runner is explicit-opt-in only and has done nothing '
              '(no DB read, no prediction generation, no ledger write; '
              'environment variables are not accepted as opt-in here).')
        return EXIT_NO_OPT_IN

    ledger_path_arg = qp.resolve_predraw_ledger_path(args)
    resolved_ledger_path = Path(ledger_path_arg) if ledger_path_arg else Path(pl.DEFAULT_LEDGER_PATH)

    try:
        # Applies the P360A non-canonical-path guard before any capture is
        # attempted; a forbidden path aborts the whole run with zero writes.
        pl.read_all_records(resolved_ledger_path)
    except pl.LedgerPathError as exc:
        print(f'[predraw-capture] REFUSED ledger path: {exc}')
        return EXIT_CAPTURE_INCOMPLETE

    lottery_types = list(ALL_LOTTERY_TYPES) if args.lottery == 'ALL' else [args.lottery]
    run_id = f'predraw_capture-{uuid.uuid4()}'
    print(f'[predraw-capture] run_id={run_id}')
    print(f'[predraw-capture] ledger_path={resolved_ledger_path}')
    print(f'[predraw-capture] source_db={qp.DB_PATH} (opened read-only)')

    results = []
    for lottery_type in lottery_types:
        try:
            results.append(
                capture_one(lottery_type, args.bets, run_id, ledger_path_arg, resolved_ledger_path)
            )
        except Exception as exc:  # per-lottery isolation; failure surfaces via exit code
            results.append({
                'lottery_type': lottery_type,
                'status': f'ERROR:{type(exc).__name__}',
                'history_rows': None,
                'bets_generated': 0,
                'records_written': 0,
                'strategy_id': None,
            })

    chain = pl.verify_chain(resolved_ledger_path)
    total_written = sum(r['records_written'] for r in results)
    for r in results:
        print('[predraw-capture] {lt}: {status} records_written={n} strategy_id={sid}'.format(
            lt=r['lottery_type'], status=r['status'], n=r['records_written'],
            sid=r.get('strategy_id')))
    print(f'[predraw-capture] chain_ok={chain.ok} ledger_total_records={chain.total_records}')

    all_captured = bool(results) and all(r['status'] == 'CAPTURED' for r in results)
    ok = all_captured and chain.ok and total_written > 0
    verdict = 'CAPTURE_OK' if ok else 'CAPTURE_INCOMPLETE'
    print(f'[predraw-capture] result={verdict} '
          '(metadata only; predicted numbers are never printed; capturing a record is '
          'not a prediction, betting recommendation, or edge claim)')
    return EXIT_OK if ok else EXIT_CAPTURE_INCOMPLETE


if __name__ == '__main__':
    sys.exit(main())
