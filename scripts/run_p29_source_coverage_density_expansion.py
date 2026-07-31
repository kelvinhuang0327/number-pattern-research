#!/usr/bin/env python3
"""
scripts/run_p29_source_coverage_density_expansion.py

CLI for P29 Source Coverage & Active Entry Density Expansion.

Usage:
  PYTHONPATH=. python scripts/run_p29_source_coverage_density_expansion.py \\
    --p27-dir outputs/predictions/PAPER/backfill/p27_full_true_date_backfill_2025-05-08_2025-09-28 \\
    --p25-dir outputs/predictions/PAPER/backfill/p25_true_date_source_separation_2025-05-08_2025-09-28 \\
    --scan-base-path data \\
    --scan-base-path outputs \\
    --output-dir outputs/predictions/PAPER/backfill/p29_source_coverage_density_expansion_2025-05-08_2025-09-28 \\
    --target-active-entries 1500 \\
    --paper-only true

Exit codes:
  0  P29_DENSITY_EXPANSION_PLAN_READY
  1  P29_BLOCKED_*
  2  P29_FAIL_*
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure PYTHONPATH includes repo root
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from wbc_backend.recommendation.p29_density_expansion_contract import (
    P29_DENSITY_EXPANSION_PLAN_READY,
    P29_FAIL_INPUT_MISSING,
    P29_FAIL_NON_DETERMINISTIC,
)
from wbc_backend.recommendation.p29_density_expansion_planner import (
    run_p29_density_expansion_plan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P29 Source Coverage & Active Entry Density Expansion"
    )
    parser.add_argument(
        "--p27-dir",
        required=True,
        type=Path,
        help="Path to P27 full true-date backfill output directory",
    )
    parser.add_argument(
        "--p25-dir",
        required=True,
        type=Path,
        help="Path to P25 true-date source separation output directory",
    )
    parser.add_argument(
        "--scan-base-path",
        action="append",
        dest="scan_base_paths",
        type=Path,
        default=[],
        metavar="PATH",
        help="Additional base directory to scan for source coverage (repeatable)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to write all P29 output files",
    )
    parser.add_argument(
        "--target-active-entries",
        type=int,
        default=1500,
        help="Target active entry count (default: 1500)",
    )
    parser.add_argument(
        "--paper-only",
        type=str,
        default="true",
        choices=["true", "false"],
        help="Must be 'true'. Production mode is not supported.",
    )
    return parser.parse_args(argv)


def _validate_args(args: argparse.Namespace) -> str | None:
    """Return error message string if validation fails, else None."""
    if args.paper_only.lower() != "true":
        return "P29_FAIL_INPUT_MISSING: --paper-only must be 'true' (production mode not supported)"
    if not args.p27_dir.exists():
        return f"P29_FAIL_INPUT_MISSING: --p27-dir does not exist: {args.p27_dir}"
    if not args.p25_dir.exists():
        return f"P29_FAIL_INPUT_MISSING: --p25-dir does not exist: {args.p25_dir}"
    date_results = args.p27_dir / "date_results.csv"
    if not date_results.exists():
        return f"P29_FAIL_INPUT_MISSING: date_results.csv not found in p27-dir: {date_results}"
    slices_dir = args.p25_dir / "true_date_slices"
    if not slices_dir.exists():
        return f"P29_FAIL_INPUT_MISSING: true_date_slices/ not found in p25-dir: {slices_dir}"
    if args.target_active_entries <= 0:
        return "P29_FAIL_INPUT_MISSING: --target-active-entries must be positive"
    return None


def _print_gate_summary(gate_result: object) -> None:
    """Print standardized gate summary to stdout."""
    print(f"p29_gate={gate_result.p29_gate}")
    print(f"current_active_entries={gate_result.current_active_entries}")
    print(f"target_active_entries={gate_result.target_active_entries}")
    print(f"density_gap={gate_result.density_gap}")
    print(f"best_policy_candidate_active_entries={gate_result.best_policy_candidate_active_entries}")
    print(f"source_expansion_estimated_entries={gate_result.source_expansion_estimated_entries}")
    print(f"recommended_next_action={gate_result.recommended_next_action}")
    print(f"audit_status={gate_result.audit_status}")
    print(f"production_ready=false")
    print(f"paper_only=true")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # Validate inputs
    err = _validate_args(args)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        print(err)  # also to stdout for caller
        return 2

    # Set default scan paths if none provided
    scan_base_paths: list[Path] = args.scan_base_paths
    if not scan_base_paths:
        scan_base_paths = [Path("data"), Path("outputs")]

    # First run (for actual gate result)
    try:
        gate_result_1 = run_p29_density_expansion_plan(
            p27_dir=args.p27_dir,
            p25_dir=args.p25_dir,
            scan_base_paths=scan_base_paths,
            output_dir=args.output_dir,
            target_active_entries=args.target_active_entries,
        )
    except FileNotFoundError as exc:
        msg = f"{P29_FAIL_INPUT_MISSING}: {exc}"
        print(f"ERROR: {msg}", file=sys.stderr)
        print(msg)
        return 2
    except Exception as exc:
        msg = f"P29_FAIL_UNEXPECTED: {type(exc).__name__}: {exc}"
        print(f"ERROR: {msg}", file=sys.stderr)
        print(msg)
        return 2

    # Determinism check — second run must match gate
    try:
        gate_result_2 = run_p29_density_expansion_plan(
            p27_dir=args.p27_dir,
            p25_dir=args.p25_dir,
            scan_base_paths=scan_base_paths,
            output_dir=args.output_dir,
            target_active_entries=args.target_active_entries,
        )
    except Exception as exc:
        msg = f"{P29_FAIL_NON_DETERMINISTIC}: second run failed: {exc}"
        print(f"ERROR: {msg}", file=sys.stderr)
        print(msg)
        return 2

    if gate_result_1.p29_gate != gate_result_2.p29_gate:
        msg = (
            f"{P29_FAIL_NON_DETERMINISTIC}: "
            f"run1={gate_result_1.p29_gate}, run2={gate_result_2.p29_gate}"
        )
        print(f"ERROR: {msg}", file=sys.stderr)
        print(msg)
        return 2

    # Print gate summary
    _print_gate_summary(gate_result_1)

    # Terminal status marker (for CI/audit log grep)
    if gate_result_1.p29_gate == P29_DENSITY_EXPANSION_PLAN_READY:
        print("P29_SOURCE_COVERAGE_DENSITY_EXPANSION_PLAN_READY")
        return 0
    else:
        print(f"P29_SOURCE_COVERAGE_DENSITY_EXPANSION_BLOCKED: {gate_result_1.p29_gate}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
