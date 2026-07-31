#!/usr/bin/env python3
"""
scripts/run_p26_true_date_historical_backfill.py

CLI entry point for P26 True-Date Historical Backfill Replay.

Usage:
  python scripts/run_p26_true_date_historical_backfill.py \
    --date-start 2025-05-08 \
    --date-end 2025-05-14 \
    --p25-dir outputs/predictions/PAPER/backfill/p25_true_date_source_separation_2025-05-08_2025-05-14 \
    --output-dir outputs/predictions/PAPER/backfill/p26_true_date_historical_backfill_2025-05-08_2025-05-14 \
    --paper-only true

Exit codes:
  0 = P26_TRUE_DATE_HISTORICAL_BACKFILL_READY
  1 = P26_BLOCKED_* (no ready dates, contract violations, etc.)
  2 = P26_FAIL_* (missing input, non-determinism, etc.)

Output files (written to output_dir):
  1. p26_gate_result.json
  2. true_date_replay_summary.json
  3. true_date_replay_summary.md
  4. date_replay_results.csv
  5. blocked_dates.json
  6. artifact_manifest.json

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P26 True-Date Historical Backfill Replay",
    )
    parser.add_argument("--date-start", required=True, help="ISO date YYYY-MM-DD")
    parser.add_argument("--date-end", required=True, help="ISO date YYYY-MM-DD")
    parser.add_argument(
        "--p25-dir",
        required=True,
        help="P25 source separation output directory (contains true_date_slices/)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write P26 outputs",
    )
    parser.add_argument(
        "--paper-only",
        type=str,
        default="true",
        choices=["true", "True", "false", "False"],
        help="Must be 'true'. Paper-only research flag.",
    )
    return parser.parse_args()


def _exit_code_for_gate(gate: str) -> int:
    if gate == "P26_TRUE_DATE_HISTORICAL_BACKFILL_READY":
        return 0
    if gate.startswith("P26_FAIL"):
        return 2
    return 1  # BLOCKED_*


def main() -> None:
    args = _parse_args()

    paper_only_str = args.paper_only.lower()
    if paper_only_str != "true":
        print(
            "[P26] ERROR: --paper-only must be 'true'. P26 is PAPER_ONLY research.",
            file=sys.stderr,
        )
        sys.exit(2)

    p25_dir = Path(args.p25_dir)
    output_dir = Path(args.output_dir)

    print(f"[P26] date_start={args.date_start}  date_end={args.date_end}")
    print(f"[P26] p25_dir={p25_dir}")
    print(f"[P26] output_dir={output_dir}")

    if not p25_dir.exists():
        print(
            f"[P26] FAIL: p25_dir does not exist: {p25_dir}",
            file=sys.stderr,
        )
        # Write minimal gate file
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_fail_gate(
            output_dir,
            args.date_start,
            args.date_end,
            "P26_FAIL_INPUT_MISSING",
            f"p25_dir not found: {p25_dir}",
        )
        sys.exit(2)

    # Run the backfill
    try:
        # Import here so import errors surface clearly
        from wbc_backend.recommendation.p26_true_date_replay_aggregator import (
            run_true_date_historical_backfill,
            build_gate_result,
        )

        summary = run_true_date_historical_backfill(
            date_start=args.date_start,
            date_end=args.date_end,
            p25_dir=p25_dir,
            output_dir=output_dir,
        )

        gate_result = build_gate_result(summary)

        print(f"[P26] gate={gate_result.p26_gate}")
        print(f"[P26] dates_requested={gate_result.n_dates_requested}  dates_ready={gate_result.n_dates_ready}  dates_blocked={gate_result.n_dates_blocked}")
        print(f"[P26] total_active={gate_result.total_active_entries}  wins={gate_result.total_settled_win}  losses={gate_result.total_settled_loss}")
        print(f"[P26] total_stake={gate_result.total_stake_units:.4f}  total_pnl={gate_result.total_pnl_units:.4f}  ROI={gate_result.aggregate_roi_units:.4f}  hit_rate={gate_result.aggregate_hit_rate:.4f}")

        if gate_result.blocker_reason:
            print(f"[P26] blocker={gate_result.blocker_reason}", file=sys.stderr)

        exit_code = _exit_code_for_gate(gate_result.p26_gate)
        sys.exit(exit_code)

    except Exception as exc:
        print(f"[P26] EXCEPTION: {exc}", file=sys.stderr)
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_fail_gate(
            output_dir,
            args.date_start,
            args.date_end,
            "P26_FAIL_INPUT_MISSING",
            str(exc),
        )
        sys.exit(2)


def _write_fail_gate(
    output_dir: Path,
    date_start: str,
    date_end: str,
    gate: str,
    reason: str,
) -> None:
    from datetime import datetime, timezone
    gate_path = output_dir / "p26_gate_result.json"
    gate_path.write_text(
        json.dumps(
            {
                "p26_gate": gate,
                "date_start": date_start,
                "date_end": date_end,
                "blocker_reason": reason,
                "paper_only": True,
                "production_ready": False,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
