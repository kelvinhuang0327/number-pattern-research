#!/usr/bin/env python3
"""CLI runner for MLB Daily Scheduler — Dry-run / Paper-Only MVP.

Usage:
    .venv/bin/python scripts/run_mlb_daily_scheduler.py \\
        --date 2026-05-07 --mode today --source fixture --limit 15 \\
        --run-pregame true --run-postgame true

    .venv/bin/python scripts/run_mlb_daily_scheduler.py \\
        --date 2025-07-01 --mode replay --source replay --limit 15 \\
        --run-pregame true --run-postgame true

    # Daemon-only opt-in: enable daily paper tracking steps explicitly.
    # Both flags default to false so naive CLI callers and offline tests
    # never trigger the live-probe recommendation path.
    .venv/bin/python scripts/run_mlb_daily_scheduler.py \\
        --date 2026-06-05 --mode today --source fixture --limit 15 \\
        --run-paper-recommendation true --run-paper-evaluation true

All output is paper-only / no-real-bet / no-profit-claim.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.mlb_daily_scheduler import (
    run_daily_mlb_scheduler,
    DEFAULT_LEDGER_PATH,
    DEFAULT_FIXTURE_PATH,
    DEFAULT_PREDICTION_JSONL,
    COMPLETION_MARKER,
    VALID_GATES,
)


def _bool_arg(val: str) -> bool:
    """Parse CLI bool argument."""
    return val.strip().lower() in {"true", "1", "yes", "y"}


def _default_manifest_path(date_str: str) -> str:
    return f"reports/mlb_daily_scheduler_manifest_{date_str.replace('-', '')}.json"


def print_summary(payload: dict, manifest_path: str) -> None:
    """Print formatted summary to stdout."""
    sep = "=" * 66
    manifest = payload.get("manifest", {})

    print(f"\n{sep}")
    print("  MLB Daily Scheduler — Dry-run  (PAPER-ONLY / NO REAL BET)")
    print(sep)
    print(f"  run_id                : {payload.get('run_id', '')}")
    print(f"  run_date              : {payload.get('run_date', '')}")
    print(f"  mode                  : {payload.get('mode', '')}")
    print(f"  source                : {payload.get('source', '')}")
    print(f"  scheduler_mode        : {payload.get('scheduler_mode', 'dry_run')}")
    print()
    print(f"  pregame_advisory_status  : {manifest.get('pregame_advisory_status', '')}")
    print(f"  postgame_review_status   : {manifest.get('postgame_review_status', '')}")
    print()
    print(f"  total_advisories         : {manifest.get('total_advisories', 0)}")
    print(f"  total_ledger_entries     : {manifest.get('total_ledger_entries', 0)}")
    print(f"  reviewed_count           : {manifest.get('reviewed_count', 0)}")
    print(f"  pending_count            : {manifest.get('pending_count', 0)}")
    print(f"  failure_notes_count      : {manifest.get('failure_notes_count', 0)}")

    brier = manifest.get("brier_score")
    rec_acc = manifest.get("recommendation_accuracy")
    if brier is not None:
        print(f"  brier_score              : {brier:.4f}")
    if rec_acc is not None:
        print(f"  recommendation_accuracy  : {rec_acc:.2%}")

    print()
    print(f"  gate         : {payload.get('gate', '')}")
    print(f"  gate_rationale: {payload.get('gate_rationale', '')[:70]}")
    print()

    # Pregame job warnings
    jobs = payload.get("jobs", {})
    pg_warnings = jobs.get("pregame_advisory", {}).get("warnings", [])
    pg_errors = jobs.get("pregame_advisory", {}).get("errors", [])
    po_warnings = jobs.get("postgame_review", {}).get("warnings", [])
    po_errors = jobs.get("postgame_review", {}).get("errors", [])

    if pg_warnings:
        print(f"  pregame_warnings    :")
        for w in pg_warnings[:3]:
            print(f"    - {w}")
    if pg_errors:
        print(f"  pregame_errors      :")
        for e in pg_errors[:2]:
            print(f"    - {e[:100]}")
    if po_warnings:
        print(f"  postgame_warnings   :")
        for w in po_warnings[:3]:
            print(f"    - {w}")
    if po_errors:
        print(f"  postgame_errors     :")
        for e in po_errors[:2]:
            print(f"    - {e[:100]}")

    val_errors = payload.get("validation_errors", [])
    if val_errors:
        print(f"  manifest_validation_errors:")
        for e in val_errors:
            print(f"    - {e}")

    print()
    print(f"  manifest_path   : {manifest_path}")
    print(f"  markdown_path   : {payload.get('markdown_path', '')}")
    print()
    print(f"  completion_marker: {COMPLETION_MARKER}")
    print(sep)
    print()
    print("  ⚠️  PAPER-ONLY  NO_REAL_BET=True  NO_PROFIT_CLAIM=True")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MLB Daily Scheduler dry-run CLI"
    )
    parser.add_argument(
        "--date", required=True,
        help="Target date YYYY-MM-DD"
    )
    parser.add_argument(
        "--mode", default="today", choices=["today", "replay"],
        help="Advisory mode: today or replay"
    )
    parser.add_argument(
        "--source", default="fixture", choices=["fixture", "replay", "current"],
        help="Data source: fixture | replay | current"
    )
    parser.add_argument(
        "--limit", type=int, default=15,
        help="Max games to process (default: 15)"
    )
    parser.add_argument(
        "--run-pregame", default="true",
        help="Run pregame advisory job (true/false)"
    )
    parser.add_argument(
        "--run-postgame", default="true",
        help="Run postgame review job (true/false)"
    )
    parser.add_argument(
        "--run-paper-recommendation", default="false",
        help=(
            "Run daily paper recommendation job (true/false; default false). "
            "Explicit opt-in only — may probe live sources when enabled."
        )
    )
    parser.add_argument(
        "--run-paper-evaluation", default="false",
        help=(
            "Run daily paper evaluation job (true/false; default false). "
            "Explicit opt-in only — fully offline (local PAPER rows + local outcomes)."
        )
    )
    parser.add_argument(
        "--ledger-path", default=DEFAULT_LEDGER_PATH,
        help="Path to paper betting ledger JSONL"
    )
    parser.add_argument(
        "--fixture-path", default=DEFAULT_FIXTURE_PATH,
        help="Path to fixture source JSON"
    )
    parser.add_argument(
        "--manifest-path", default=None,
        help="Where to write manifest JSON (default: auto)"
    )
    parser.add_argument(
        "--no-write", action="store_true",
        help="Skip all disk writes (dry-run validation mode)"
    )

    args = parser.parse_args()

    run_pregame = _bool_arg(args.run_pregame)
    run_postgame = _bool_arg(args.run_postgame)
    run_paper_recommendation = _bool_arg(args.run_paper_recommendation)
    run_paper_evaluation = _bool_arg(args.run_paper_evaluation)
    write_reports = not args.no_write

    print(f"\n[run_mlb_daily_scheduler] date={args.date} mode={args.mode} source={args.source}")
    print(f"  ledger_path    : {args.ledger_path}")
    print(f"  fixture_path   : {args.fixture_path}")
    print(f"  run_pregame    : {run_pregame}")
    print(f"  run_postgame   : {run_postgame}")
    print(f"  run_paper_recommendation : {run_paper_recommendation}")
    print(f"  run_paper_evaluation     : {run_paper_evaluation}")
    print(f"  limit          : {args.limit}")
    print(f"  write_reports  : {write_reports}")
    print()

    payload = run_daily_mlb_scheduler(
        run_date=args.date,
        mode=args.mode,
        source=args.source,
        limit=args.limit,
        ledger_path=args.ledger_path,
        fixture_path=args.fixture_path,
        manifest_path=args.manifest_path,
        run_pregame=run_pregame,
        run_postgame=run_postgame,
        run_paper_recommendation=run_paper_recommendation,
        run_paper_evaluation=run_paper_evaluation,
        write_reports=write_reports,
    )

    manifest_path = payload.get("manifest_path", _default_manifest_path(args.date))
    print_summary(payload, manifest_path)

    # Exit 1 if gate is NOT_READY
    gate = payload.get("gate", "")
    if gate not in VALID_GATES:
        print(f"ERROR: gate {gate!r} not in VALID_GATES", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
