#!/usr/bin/env python3
"""
scripts/run_p28_true_date_backfill_stability_audit.py

P28 True-Date Backfill Performance Stability Audit — CLI entry point.

Usage:
    python scripts/run_p28_true_date_backfill_stability_audit.py \\
        --p27-dir outputs/predictions/PAPER/backfill/p27_full_true_date_backfill_2025-05-08_2025-09-28 \\
        --output-dir outputs/predictions/PAPER/backfill/p28_true_date_stability_audit_2025-05-08_2025-09-28 \\
        --min-sample-size 1500 \\
        --paper-only true

Exit codes:
    0  — P28_TRUE_DATE_STABILITY_AUDIT_READY
    1  — P28_BLOCKED_* (sample size, drawdown, variance)
    2  — P28_FAIL_* (missing input, non-deterministic)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from repo root with PYTHONPATH=.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wbc_backend.recommendation.p28_true_date_stability_contract import (
    MIN_SAMPLE_SIZE_ADVISORY,
    P28_TRUE_DATE_STABILITY_AUDIT_READY,
)
from wbc_backend.recommendation.p28_true_date_stability_auditor import (
    run_p28_true_date_stability_audit,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P28 True-Date Backfill Performance Stability Audit"
    )
    parser.add_argument(
        "--p27-dir",
        required=True,
        help="Path to the P27 output directory (contains date_results.csv, etc.)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Path to write P28 output files",
    )
    parser.add_argument(
        "--min-sample-size",
        type=int,
        default=MIN_SAMPLE_SIZE_ADVISORY,
        help=f"Advisory minimum sample size (default: {MIN_SAMPLE_SIZE_ADVISORY})",
    )
    parser.add_argument(
        "--paper-only",
        default="true",
        help="Must be 'true'. Any other value is rejected.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.paper_only.strip().lower() != "true":
        print(
            "ERROR: --paper-only must be 'true'. "
            "This audit module does not support live/production mode.",
            file=sys.stderr,
        )
        return 2

    p27_dir = Path(args.p27_dir)
    output_dir = Path(args.output_dir)

    if not p27_dir.exists():
        print(f"ERROR: P27 directory not found: {p27_dir}", file=sys.stderr)
        return 2

    try:
        result = run_p28_true_date_stability_audit(
            p27_dir=p27_dir,
            output_dir=output_dir,
            min_sample_size=args.min_sample_size,
        )
    except FileNotFoundError as exc:
        print(f"P28_FAIL_INPUT_MISSING: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"P28_FAIL_UNEXPECTED: {exc}", file=sys.stderr)
        return 2

    # Print results
    print(f"p28_gate:                    {result.p28_gate}")
    print(f"audit_status:                {result.audit_status}")
    print(f"total_active_entries:        {result.total_active_entries}")
    print(f"min_sample_size_advisory:    {result.min_sample_size_advisory}")
    print(f"sample_size_pass:            {result.sample_size_pass}")
    print(f"aggregate_roi_units:         {result.aggregate_roi_units:.6f}")
    print(f"aggregate_hit_rate:          {result.aggregate_hit_rate:.6f}")
    print(f"bootstrap_roi_ci_low_95:     {result.bootstrap_roi_ci_low_95:.6f}")
    print(f"bootstrap_roi_ci_high_95:    {result.bootstrap_roi_ci_high_95:.6f}")
    print(f"segment_roi_std:             {result.segment_roi_std:.6f}")
    print(f"max_drawdown_pct:            {result.max_drawdown_pct:.4f}%")
    print(f"max_consecutive_losing_days: {result.max_consecutive_losing_days}")
    print(f"production_ready:            {result.production_ready}")
    print(f"paper_only:                  {result.paper_only}")
    if result.blocker_reason:
        print(f"blocker_reason:              {result.blocker_reason}")
    print(f"outputs written to:          {output_dir}")

    if result.p28_gate == P28_TRUE_DATE_STABILITY_AUDIT_READY:
        return 0
    if result.p28_gate.startswith("P28_BLOCKED_"):
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
