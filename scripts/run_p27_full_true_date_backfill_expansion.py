#!/usr/bin/env python3
"""
scripts/run_p27_full_true_date_backfill_expansion.py

P27 CLI — Full 2025 True-Date Historical Backfill Expansion.

Usage:
  python scripts/run_p27_full_true_date_backfill_expansion.py \
    --date-start 2025-05-08 \
    --date-end 2025-09-28 \
    --segment-days 14 \
    --output-dir outputs/predictions/PAPER/backfill/p27_full_true_date_backfill_2025-05-08_2025-09-28 \
    --paper-only true \
    --max-runtime-seconds 180

Exit codes:
  0 = P27_FULL_TRUE_DATE_BACKFILL_READY
  1 = BLOCKED_*
  2 = FAIL_*
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def _guard_paper_only(paper_only: str) -> None:
    if paper_only.lower() != "true":
        print(
            "[P27] ERROR: --paper-only must be 'true'. "
            "This is a PAPER_ONLY pipeline. Production execution is forbidden.",
            file=sys.stderr,
        )
        sys.exit(2)


def _write_fail_gate(output_dir: Path, gate: str, reason: str) -> None:
    """Write minimal gate result on early failure."""
    from datetime import datetime, timezone
    output_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "p27_gate": gate,
        "blocker_reason": reason,
        "paper_only": True,
        "production_ready": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (output_dir / "p27_gate_result.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False)
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P27 Full 2025 True-Date Backfill Expansion CLI"
    )
    parser.add_argument("--date-start", required=True)
    parser.add_argument("--date-end", required=True)
    parser.add_argument("--segment-days", type=int, default=14)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--paper-only", required=True, choices=["true", "True", "false", "False"]
    )
    parser.add_argument("--max-runtime-seconds", type=float, default=180.0)
    args = parser.parse_args()

    _guard_paper_only(args.paper_only)

    output_dir = Path(args.output_dir)
    t_start = time.monotonic()

    # Import after guard to keep startup fast
    from wbc_backend.recommendation.p27_true_date_range_planner import (
        build_true_date_segments,
        validate_segment_plan,
        summarize_segment_plan,
    )
    from wbc_backend.recommendation.p27_p25_full_range_runner import (
        run_p25_separation_for_range,
        validate_p25_full_range_outputs,
        summarize_p25_full_range_outputs,
    )
    from wbc_backend.recommendation.p27_p26_segmented_replay_runner import (
        run_p26_replay_for_all_segments,
        summarize_segment_replay_results,
    )
    from wbc_backend.recommendation.p27_full_backfill_reconciler import (
        reconcile_segment_outputs,
        validate_full_backfill_summary,
        build_p27_gate_result,
        write_p27_outputs,
    )
    from wbc_backend.recommendation.p27_full_true_date_backfill_contract import (
        P27RuntimeGuardResult,
        P27_FAIL_INPUT_MISSING,
        P27_BLOCKED_P25_FULL_RANGE_NOT_READY,
        P27_BLOCKED_RUNTIME_GUARD,
    )

    print(f"[P27] date_start={args.date_start}  date_end={args.date_end}")
    print(f"[P27] segment_days={args.segment_days}  max_runtime={args.max_runtime_seconds}s")
    print(f"[P27] output_dir={args.output_dir}")
    print(f"[P27] paper_only=true  production_ready=false")

    # -----------------------------------------------------------------------
    # Step 1: Build segment plan
    # -----------------------------------------------------------------------
    segments = build_true_date_segments(
        args.date_start, args.date_end, segment_days=args.segment_days
    )
    if not segments:
        reason = f"No segments produced for {args.date_start} → {args.date_end}"
        _write_fail_gate(output_dir, P27_FAIL_INPUT_MISSING, reason)
        print(f"[P27] FAIL: {reason}", file=sys.stderr)
        return 2

    try:
        validate_segment_plan(segments)
    except ValueError as e:
        reason = f"Segment plan invalid: {e}"
        _write_fail_gate(output_dir, P27_FAIL_INPUT_MISSING, reason)
        print(f"[P27] FAIL: {reason}", file=sys.stderr)
        return 2

    plan_summary = summarize_segment_plan(segments)
    print(f"[P27] segments={plan_summary['n_segments']}  total_dates={plan_summary['total_dates']}")

    # -----------------------------------------------------------------------
    # Step 2: Run P25 full-range separation
    # -----------------------------------------------------------------------
    p25_output_dir = (
        output_dir.parent
        / f"p25_true_date_source_separation_{args.date_start}_{args.date_end}"
    )

    p25_valid, p25_reason = validate_p25_full_range_outputs(p25_output_dir)
    if not p25_valid:
        print(f"[P27] P25 not ready — running P25 separation...")
        try:
            rc, stdout, stderr = run_p25_separation_for_range(
                date_start=args.date_start,
                date_end=args.date_end,
                output_dir=p25_output_dir,
            )
        except FileNotFoundError as e:
            reason = str(e)
            _write_fail_gate(output_dir, P27_FAIL_INPUT_MISSING, reason)
            print(f"[P27] FAIL: {reason}", file=sys.stderr)
            return 2

        p25_valid, p25_reason = validate_p25_full_range_outputs(p25_output_dir)
        if not p25_valid:
            reason = f"P25 separation failed: {p25_reason}"
            _write_fail_gate(output_dir, P27_BLOCKED_P25_FULL_RANGE_NOT_READY, reason)
            print(f"[P27] BLOCKED: {reason}", file=sys.stderr)
            return 1

    p25_summary = summarize_p25_full_range_outputs(p25_output_dir)
    print(
        f"[P27] P25 ready: gate={p25_summary['p25_gate']}  "
        f"n_slice_dates={p25_summary['n_slice_dates']}  "
        f"total_rows={p25_summary['total_rows_across_slices']}"
    )

    # -----------------------------------------------------------------------
    # Step 3: Runtime guard check before running all segments
    # -----------------------------------------------------------------------
    elapsed_before_replay = time.monotonic() - t_start
    if elapsed_before_replay > args.max_runtime_seconds:
        guard = P27RuntimeGuardResult(
            max_runtime_seconds=args.max_runtime_seconds,
            actual_runtime_seconds=elapsed_before_replay,
            guard_triggered=True,
            guard_reason="Runtime exceeded before segment replay started",
            paper_only=True,
            production_ready=False,
        )
        reason = f"Runtime guard triggered at {elapsed_before_replay:.1f}s"
        _write_fail_gate(output_dir, P27_BLOCKED_RUNTIME_GUARD, reason)
        print(f"[P27] BLOCKED: {reason}", file=sys.stderr)
        return 1

    # -----------------------------------------------------------------------
    # Step 4: Run P26 for all segments (using full-range P25 dir)
    # -----------------------------------------------------------------------
    segment_results = run_p26_replay_for_all_segments(
        segments=segments,
        p25_base_dir=p25_output_dir,
        output_base_dir=output_dir,
    )

    t_end = time.monotonic()
    runtime_seconds = t_end - t_start

    # -----------------------------------------------------------------------
    # Step 5: Runtime guard post-check
    # -----------------------------------------------------------------------
    guard_triggered = runtime_seconds > args.max_runtime_seconds
    runtime_guard = P27RuntimeGuardResult(
        max_runtime_seconds=args.max_runtime_seconds,
        actual_runtime_seconds=runtime_seconds,
        guard_triggered=guard_triggered,
        guard_reason="Runtime exceeded max_runtime_seconds" if guard_triggered else "",
        paper_only=True,
        production_ready=False,
    )

    # -----------------------------------------------------------------------
    # Step 6: Collect per-date rows from segment gate data
    # -----------------------------------------------------------------------
    date_results = _collect_date_results(segment_results, output_dir)

    # -----------------------------------------------------------------------
    # Step 7: Reconcile and build gate
    # -----------------------------------------------------------------------
    summary = reconcile_segment_outputs(segment_results, date_results)
    # Override with proper P25 source dir
    from dataclasses import replace
    summary = P27FullBackfillSummary_with_source(summary, str(p25_output_dir))

    gate_result = build_p27_gate_result(
        summary,
        runtime_seconds=runtime_seconds,
        max_runtime_seconds=args.max_runtime_seconds,
        guard_triggered=guard_triggered,
    )

    # -----------------------------------------------------------------------
    # Step 8: Write outputs
    # -----------------------------------------------------------------------
    write_p27_outputs(
        summary=summary,
        gate_result=gate_result,
        segment_results=segment_results,
        date_results=date_results,
        runtime_guard=runtime_guard,
        output_dir=output_dir,
    )

    # -----------------------------------------------------------------------
    # Step 9: Print summary and exit
    # -----------------------------------------------------------------------
    print(f"[P27] gate={gate_result.p27_gate}")
    print(f"[P27] n_segments={gate_result.n_segments}")
    print(
        f"[P27] dates_requested={gate_result.n_dates_requested}  "
        f"dates_ready={gate_result.n_dates_ready}  "
        f"dates_empty={gate_result.n_dates_empty}  "
        f"dates_blocked={gate_result.n_dates_blocked}"
    )
    print(f"[P27] total_active={gate_result.total_active_entries}  "
          f"wins={gate_result.total_settled_win}  losses={gate_result.total_settled_loss}  "
          f"unsettled={gate_result.total_unsettled}")
    print(
        f"[P27] total_stake={gate_result.total_stake_units:.4f}  "
        f"total_pnl={gate_result.total_pnl_units:.4f}  "
        f"ROI={gate_result.aggregate_roi_units:.4f}  "
        f"hit_rate={gate_result.aggregate_hit_rate:.4f}"
    )
    print(f"[P27] runtime_seconds={runtime_seconds:.2f}  guard_triggered={guard_triggered}")
    print(f"[P27] paper_only=true  production_ready=false")

    if gate_result.p27_gate == "P27_FULL_TRUE_DATE_BACKFILL_READY":
        return 0
    elif gate_result.p27_gate.startswith("P27_BLOCKED"):
        return 1
    else:
        return 2


def _collect_date_results(segment_results, output_dir: Path):
    """Collect per-date rows from each segment's date_replay_results.csv."""
    import csv as csv_mod
    all_rows = []
    for r in segment_results:
        if r.get("blocked"):
            continue
        seg_out = Path(r.get("output_dir", ""))
        csv_path = seg_out / "date_replay_results.csv"
        if not csv_path.exists():
            continue
        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv_mod.DictReader(f)
                for row in reader:
                    row["segment_index"] = r.get("segment_index", "")
                    all_rows.append(row)
        except Exception:
            pass
    return all_rows


def P27FullBackfillSummary_with_source(summary, source_p25_base_dir: str):
    """Return a new P27FullBackfillSummary with updated source_p25_base_dir."""
    from wbc_backend.recommendation.p27_full_true_date_backfill_contract import (
        P27FullBackfillSummary,
    )
    return P27FullBackfillSummary(
        date_start=summary.date_start,
        date_end=summary.date_end,
        n_segments=summary.n_segments,
        n_dates_requested=summary.n_dates_requested,
        n_dates_ready=summary.n_dates_ready,
        n_dates_empty=summary.n_dates_empty,
        n_dates_blocked=summary.n_dates_blocked,
        total_active_entries=summary.total_active_entries,
        total_settled_win=summary.total_settled_win,
        total_settled_loss=summary.total_settled_loss,
        total_unsettled=summary.total_unsettled,
        total_stake_units=summary.total_stake_units,
        total_pnl_units=summary.total_pnl_units,
        aggregate_roi_units=summary.aggregate_roi_units,
        aggregate_hit_rate=summary.aggregate_hit_rate,
        min_game_id_coverage=summary.min_game_id_coverage,
        max_runtime_seconds=summary.max_runtime_seconds,
        blocked_segment_list=summary.blocked_segment_list,
        blocked_date_list=summary.blocked_date_list,
        source_p25_base_dir=source_p25_base_dir,
        paper_only=True,
        production_ready=False,
        blocker_reason=summary.blocker_reason,
    )


if __name__ == "__main__":
    sys.exit(main())
