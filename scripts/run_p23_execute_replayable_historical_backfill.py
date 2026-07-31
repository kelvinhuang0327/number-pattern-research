#!/usr/bin/env python3
"""
scripts/run_p23_execute_replayable_historical_backfill.py

P23 Execute Replayable Historical Backfill CLI.

Chains the P22.5 source artifact plan → per-date P15 materializer →
P16.6 → P19 → P17-replay → P20 pipeline for each date in the requested range.

For dates that already have a valid P20_DAILY_PAPER_ORCHESTRATOR_READY result,
the existing artifacts are reused without overwriting (unless --force true).

Exit codes:
  0 — P23_HISTORICAL_REPLAY_BACKFILL_READY
  1 — BLOCKED_* (at least one date ready, some blocked — or all blocked)
  2 — FAIL_* (fatal input/contract error)

PAPER_ONLY — no production systems, no real bets.

Usage:
    python scripts/run_p23_execute_replayable_historical_backfill.py \\
        --date-start 2026-05-01 \\
        --date-end 2026-05-12 \\
        --p22-5-dir outputs/predictions/PAPER/backfill/p22_5_source_artifact_builder_2026-05-01_2026-05-12 \\
        --output-dir outputs/predictions/PAPER/backfill/p23_historical_replay_2026-05-01_2026-05-12 \\
        --paper-only true \\
        --force false
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repo root is importable regardless of cwd
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from wbc_backend.recommendation.p23_historical_replay_aggregator import (
    aggregate_replay_results,
    build_gate_result,
    validate_aggregate_summary,
    write_replay_outputs,
)
from wbc_backend.recommendation.p23_historical_replay_contract import (
    P23_BLOCKED_CONTRACT_VIOLATION,
    P23_BLOCKED_NO_READY_DATES,
    P23_FAIL_INPUT_MISSING,
    P23_HISTORICAL_REPLAY_BACKFILL_READY,
)
from wbc_backend.recommendation.p23_p15_source_materializer import (
    build_replay_date_tasks,
    list_replayable_dates,
    load_p22_5_readiness_plan,
)
from wbc_backend.recommendation.p23_per_date_replay_runner import run_date_replay

# Base PAPER output dir
_PAPER_BASE_DIR = _REPO_ROOT / "outputs" / "predictions" / "PAPER"


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes")


def _generate_date_range(date_start: str, date_end: str) -> list[str]:
    """Generate sorted list of YYYY-MM-DD strings inclusive."""
    from datetime import date, timedelta
    start = date.fromisoformat(date_start)
    end = date.fromisoformat(date_end)
    if start > end:
        return []
    result = []
    current = start
    while current <= end:
        result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="P23 Execute Replayable Historical Backfill")
    p.add_argument("--date-start", required=True, help="Start date YYYY-MM-DD (inclusive)")
    p.add_argument("--date-end", required=True, help="End date YYYY-MM-DD (inclusive)")
    p.add_argument(
        "--p22-5-dir",
        required=True,
        help="P22.5 source artifact builder output directory",
    )
    p.add_argument(
        "--output-dir",
        required=True,
        help="Output directory for P23 aggregate artifacts",
    )
    p.add_argument(
        "--paper-only",
        default="true",
        help="Must be 'true'. Any other value exits immediately. (default: true)",
    )
    p.add_argument(
        "--force",
        default="false",
        help="If 'true', re-run even for dates with existing P20 results. (default: false)",
    )
    return p


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    # ── Safety guard ─────────────────────────────────────────────────────────
    paper_only = _parse_bool(args.paper_only)
    if not paper_only:
        print(
            "ERROR: --paper-only must be 'true'. P23 is PAPER_ONLY.",
            file=sys.stderr,
        )
        print(f"[P23] Gate: {P23_FAIL_INPUT_MISSING}")
        return 2

    force = _parse_bool(args.force)

    date_start = args.date_start
    date_end = args.date_end
    p22_5_dir = Path(args.p22_5_dir)
    output_dir = Path(args.output_dir)

    print(f"[P23] Starting replayable historical backfill: {date_start} → {date_end}")
    print(f"[P23] P22.5 dir: {p22_5_dir}")
    print(f"[P23] Output dir: {output_dir}")
    print(f"[P23] Force re-run: {force}")
    print(f"[P23] PAPER_ONLY=True, PRODUCTION_READY=False")

    # ── Step 1: Validate P22.5 dir ──────────────────────────────────────────
    if not p22_5_dir.exists():
        print(f"[P23] FATAL: --p22-5-dir does not exist: {p22_5_dir}", file=sys.stderr)
        print(f"[P23] Gate: {P23_FAIL_INPUT_MISSING}")
        return 2

    plan_path = p22_5_dir / "p15_readiness_plan.json"
    if not plan_path.exists():
        print(f"[P23] FATAL: P22.5 readiness plan not found: {plan_path}", file=sys.stderr)
        print(f"[P23] Gate: {P23_FAIL_INPUT_MISSING}")
        return 2

    # ── Step 2: Load P22.5 plan ──────────────────────────────────────────────
    try:
        plan = load_p22_5_readiness_plan(plan_path)
    except Exception as exc:
        print(f"[P23] FATAL: Failed to load P22.5 plan: {exc}", file=sys.stderr)
        print(f"[P23] Gate: {P23_FAIL_INPUT_MISSING}")
        return 2

    # ── Step 3: Generate date range ──────────────────────────────────────────
    all_dates = _generate_date_range(date_start, date_end)
    if not all_dates:
        print(f"[P23] FATAL: No dates in range {date_start} to {date_end}", file=sys.stderr)
        print(f"[P23] Gate: {P23_FAIL_INPUT_MISSING}")
        return 2

    n_dates_requested = len(all_dates)
    print(f"[P23] Dates requested: {n_dates_requested} ({date_start} to {date_end})")

    # ── Step 4: Build replay tasks ────────────────────────────────────────────
    replayable_from_plan = list_replayable_dates(plan)
    print(f"[P23] Dates ready from P22.5 plan: {len(replayable_from_plan)}")

    # Use all_dates (not just plan-ready) so we can mark missing dates as blocked
    tasks = build_replay_date_tasks(
        dates=all_dates,
        p22_5_output_dir=p22_5_dir,
        paper_base_dir=_PAPER_BASE_DIR,
    )

    # ── Step 5: Run per-date replay ──────────────────────────────────────────
    date_results = []
    for i, task in enumerate(tasks, 1):
        run_date = task.run_date
        print(f"[P23] [{i}/{n_dates_requested}] {run_date} source_type={task.source_type}")
        result = run_date_replay(
            task=task,
            p22_5_output_dir=p22_5_dir,
            paper_base_dir=_PAPER_BASE_DIR,
            force=force,
        )
        gate_icon = "✓" if result.date_gate in {
            "P23_DATE_REPLAY_READY", "P23_DATE_ALREADY_READY"
        } else "✗"
        print(
            f"[P23]   {gate_icon} {result.date_gate}"
            + (f" — {result.blocker_reason[:80]}" if result.blocker_reason else "")
        )
        date_results.append(result)

    if not date_results:
        print(f"[P23] FATAL: No dates attempted", file=sys.stderr)
        print(f"[P23] Gate: {P23_BLOCKED_NO_READY_DATES}")
        return 1

    # ── Step 6: Aggregate ────────────────────────────────────────────────────
    summary = aggregate_replay_results(
        date_results=date_results,
        date_start=date_start,
        date_end=date_end,
        n_dates_requested=n_dates_requested,
    )

    # ── Step 7: Validate aggregate summary ───────────────────────────────────
    violations = validate_aggregate_summary(summary)
    if violations:
        print(f"[P23] FATAL: Contract violations: {violations}", file=sys.stderr)
        print(f"[P23] Gate: {P23_BLOCKED_CONTRACT_VIOLATION}")
        return 2

    # ── Step 8: Build gate result ─────────────────────────────────────────────
    gate_result = build_gate_result(summary)

    # ── Step 9: Write outputs ────────────────────────────────────────────────
    try:
        written = write_replay_outputs(
            summary=summary,
            gate_result=gate_result,
            date_results=date_results,
            output_dir=output_dir,
        )
    except Exception as exc:
        print(f"[P23] FATAL: Failed to write outputs: {exc}", file=sys.stderr)
        print(f"[P23] Gate: {P23_FAIL_INPUT_MISSING}")
        return 2

    # ── Step 10: Print summary ───────────────────────────────────────────────
    roi_pct = summary.aggregate_roi_units * 100
    hit_pct = summary.aggregate_hit_rate * 100
    cov_pct = summary.min_game_id_coverage * 100

    print()
    print(f"[P23] ── Summary ──────────────────────────────────────────")
    print(f"[P23] Gate:                 {summary.p23_gate}")
    print(f"[P23] date_start:           {summary.date_start}")
    print(f"[P23] date_end:             {summary.date_end}")
    print(f"[P23] n_dates_requested:    {summary.n_dates_requested}")
    print(f"[P23] n_dates_attempted:    {summary.n_dates_attempted}")
    print(f"[P23] n_dates_ready:        {summary.n_dates_ready}")
    print(f"[P23] n_dates_blocked:      {summary.n_dates_blocked}")
    print(f"[P23] total_active_entries: {summary.total_active_entries}")
    print(f"[P23] total_settled_win:    {summary.total_settled_win}")
    print(f"[P23] total_settled_loss:   {summary.total_settled_loss}")
    print(f"[P23] total_stake_units:    {summary.total_stake_units:.2f}")
    print(f"[P23] total_pnl_units:      {summary.total_pnl_units:.4f}")
    print(f"[P23] aggregate_roi:        {roi_pct:+.2f}%")
    print(f"[P23] aggregate_hit_rate:   {hit_pct:.2f}%")
    print(f"[P23] min_game_id_coverage: {cov_pct:.1f}%")
    print(f"[P23] production_ready:     {summary.production_ready}")
    print(f"[P23] paper_only:           {summary.paper_only}")
    print(f"[P23] ──────────────────────────────────────────────────────")
    print(f"[P23] Next action: {gate_result.recommended_next_action}")
    print()
    print(f"[P23] Output files ({len(written)}):")
    for f in written:
        print(f"[P23]   {f}")
    print()
    print(f"[P23] Gate: {summary.p23_gate}")

    # Exit code
    if summary.p23_gate == P23_HISTORICAL_REPLAY_BACKFILL_READY:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
