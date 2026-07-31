#!/usr/bin/env python3
"""
scripts/run_p21_multi_day_paper_backfill.py

P21 Multi-Day PAPER Backfill Orchestrator CLI.

Exit codes:
  0 — P21_MULTI_DAY_PAPER_BACKFILL_READY
  1 — BLOCKED_*
  2 — FAIL_*

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repo root is in path when invoked as a script
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from wbc_backend.recommendation.p21_daily_artifact_discovery import (
    discover_p20_daily_artifacts,
    summarize_missing_artifacts,
)
from wbc_backend.recommendation.p21_multi_day_backfill_aggregator import (
    aggregate_backfill_results,
    validate_backfill_summary,
    write_backfill_outputs,
)
from wbc_backend.recommendation.p21_multi_day_backfill_contract import (
    P21_BLOCKED_NO_READY_DAILY_RUNS,
    P21_FAIL_INPUT_MISSING,
    P21_MULTI_DAY_PAPER_BACKFILL_READY,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="P21 Multi-Day PAPER Backfill Orchestrator"
    )
    p.add_argument("--date-start", required=True, help="Start date YYYY-MM-DD (inclusive)")
    p.add_argument("--date-end", required=True, help="End date YYYY-MM-DD (inclusive)")
    p.add_argument(
        "--paper-base-dir",
        required=True,
        help="Base directory containing per-date PAPER artifacts (e.g. outputs/predictions/PAPER)",
    )
    p.add_argument("--output-dir", required=True, help="Output directory for P21 artifacts")
    p.add_argument(
        "--paper-only",
        default="true",
        help="Must be 'true'. Any other value aborts immediately.",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    # Hard guard — paper-only must be true
    if args.paper_only.lower() != "true":
        print(f"[P21] FATAL: --paper-only must be 'true'. Got: {args.paper_only!r}")
        print(f"[P21] Gate: {P21_FAIL_INPUT_MISSING}")
        return 2

    base_dir = Path(args.paper_base_dir)
    if not base_dir.exists():
        print(f"[P21] FATAL: --paper-base-dir does not exist: {base_dir}")
        print(f"[P21] Gate: {P21_FAIL_INPUT_MISSING}")
        return 2

    date_start = args.date_start
    date_end = args.date_end
    output_dir = Path(args.output_dir)

    print(f"[P21] Starting multi-day PAPER backfill: {date_start} → {date_end}")
    print(f"[P21] Base dir: {base_dir}")
    print(f"[P21] Output dir: {output_dir}")

    # Step 1: Discover daily artifacts
    try:
        date_results = discover_p20_daily_artifacts(
            base_dir=base_dir,
            date_range=(date_start, date_end),
        )
    except Exception as exc:
        print(f"[P21] FATAL: artifact discovery failed: {exc}")
        print(f"[P21] Gate: {P21_FAIL_INPUT_MISSING}")
        return 2

    # Step 2: Summarize missing artifacts
    missing_reports = summarize_missing_artifacts((date_start, date_end), date_results)

    # Step 3: Aggregate
    try:
        summary = aggregate_backfill_results(date_results)
    except Exception as exc:
        print(f"[P21] FATAL: aggregation failed: {exc}")
        print(f"[P21] Gate: {P21_FAIL_INPUT_MISSING}")
        return 2

    # Step 4: Validate
    validation = validate_backfill_summary(summary)

    # Step 5: Write outputs (always, even on BLOCKED)
    try:
        written = write_backfill_outputs(
            summary=summary,
            date_results=date_results,
            missing_reports=missing_reports,
            output_dir=output_dir,
        )
    except Exception as exc:
        print(f"[P21] FATAL: failed to write outputs: {exc}")
        print(f"[P21] Gate: {P21_FAIL_INPUT_MISSING}")
        return 2

    # Step 6: Print summary
    roi_pct = summary.aggregate_roi_units * 100
    hit_pct = summary.aggregate_hit_rate * 100
    coverage_pct = summary.min_game_id_coverage * 100

    print()
    print(f"[P21] ── Summary ──────────────────────────────────────")
    print(f"[P21] Gate:               {summary.p21_gate}")
    print(f"[P21] date_start:         {summary.date_start}")
    print(f"[P21] date_end:           {summary.date_end}")
    print(f"[P21] n_dates_requested:  {summary.n_dates_requested}")
    print(f"[P21] n_dates_ready:      {summary.n_dates_ready}")
    print(f"[P21] n_dates_missing:    {summary.n_dates_missing}")
    print(f"[P21] n_dates_blocked:    {summary.n_dates_blocked}")
    print(f"[P21] total_active:       {summary.total_active_entries}")
    print(f"[P21] total_settled_win:  {summary.total_settled_win}")
    print(f"[P21] total_settled_loss: {summary.total_settled_loss}")
    print(f"[P21] total_unsettled:    {summary.total_unsettled}")
    print(f"[P21] total_stake_units:  {summary.total_stake_units:.2f}")
    print(f"[P21] total_pnl_units:    {summary.total_pnl_units:.4f}")
    print(f"[P21] aggregate_roi:      {roi_pct:+.2f}%")
    print(f"[P21] aggregate_hit_rate: {hit_pct:.2f}%")
    print(f"[P21] min_game_coverage:  {coverage_pct:.1f}%")
    print(f"[P21] production_ready:   {summary.production_ready}")
    print(f"[P21] paper_only:         {summary.paper_only}")
    print(f"[P21] ─────────────────────────────────────────────────")

    if missing_reports:
        print(f"[P21] Missing dates ({len(missing_reports)}):")
        for mr in missing_reports:
            print(f"  {mr['run_date']}: {mr['error_message']}")

    print()
    print(f"[P21] Outputs written ({len(written)}):")
    for w in written:
        print(f"  {w}")

    # Exit codes
    if summary.p21_gate == P21_MULTI_DAY_PAPER_BACKFILL_READY:
        print(f"\n[P21] SUCCESS: {summary.p21_gate}")
        return 0
    elif summary.p21_gate.startswith("P21_BLOCKED_"):
        print(f"\n[P21] BLOCKED: {summary.p21_gate}")
        return 1
    else:
        print(f"\n[P21] FAIL: {summary.p21_gate}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
