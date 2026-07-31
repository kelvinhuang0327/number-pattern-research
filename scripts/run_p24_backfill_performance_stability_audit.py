#!/usr/bin/env python3
"""
scripts/run_p24_backfill_performance_stability_audit.py

P24 CLI — Backfill Performance Stability Audit.

Audits the 12-day historical replay from P23 for:
- Source integrity (duplicate source detection)
- Per-date performance variance
- Temporal mismatch (game_date != run_date)

PAPER_ONLY — no production systems, no real bets.

Exit codes:
  0 = P24_BACKFILL_STABILITY_AUDIT_READY
  1 = P24_BLOCKED_*
  2 = P24_FAIL_*
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repo root is importable when run via `PYTHONPATH=. python scripts/...`
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from wbc_backend.recommendation.p24_backfill_stability_contract import (
    P24_BACKFILL_STABILITY_AUDIT_READY,
    P24_BLOCKED_CONTRACT_VIOLATION,
    P24_BLOCKED_DUPLICATE_SOURCE_REPLAY,
    P24_BLOCKED_INSUFFICIENT_INDEPENDENT_DATES,
    P24_FAIL_INPUT_MISSING,
    P24_FAIL_NON_DETERMINISTIC,
)
from wbc_backend.recommendation.p24_backfill_stability_auditor import (
    run_backfill_stability_audit,
    write_p24_outputs,
)

_BLOCKED_GATES = {
    P24_BLOCKED_DUPLICATE_SOURCE_REPLAY,
    P24_BLOCKED_INSUFFICIENT_INDEPENDENT_DATES,
    P24_BLOCKED_CONTRACT_VIOLATION,
}
_FAIL_GATES = {
    P24_FAIL_INPUT_MISSING,
    P24_FAIL_NON_DETERMINISTIC,
}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="P24 Backfill Performance Stability Audit"
    )
    p.add_argument(
        "--date-start",
        required=True,
        help="Start date YYYY-MM-DD (inclusive)",
    )
    p.add_argument(
        "--date-end",
        required=True,
        help="End date YYYY-MM-DD (inclusive)",
    )
    p.add_argument(
        "--p23-dir",
        required=True,
        help="Path to P23 aggregate output directory",
    )
    p.add_argument(
        "--paper-base-dir",
        required=True,
        help="Path to PAPER base dir (outputs/predictions/PAPER)",
    )
    p.add_argument(
        "--output-dir",
        required=True,
        help="Output directory for P24 audit artifacts",
    )
    p.add_argument(
        "--paper-only",
        default="true",
        help="Must be 'true'. Any other value causes immediate exit 2.",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    # Hard guard: only paper-only mode
    if args.paper_only.lower() != "true":
        print(
            "[P24 GUARD] --paper-only must be 'true'. "
            "P24 is paper-only and cannot be run in production mode.",
            file=sys.stderr,
        )
        return 2

    # Validate directories exist
    p23_dir = Path(args.p23_dir)
    if not p23_dir.exists():
        print(
            f"[P24 FAIL] P23 directory not found: {p23_dir}",
            file=sys.stderr,
        )
        return 2

    paper_base_dir = Path(args.paper_base_dir)
    if not paper_base_dir.exists():
        print(
            f"[P24 FAIL] Paper base directory not found: {paper_base_dir}",
            file=sys.stderr,
        )
        return 2

    # Run audit
    try:
        summary, gate_result, raw_audit_data = run_backfill_stability_audit(
            date_start=args.date_start,
            date_end=args.date_end,
            p23_dir=str(p23_dir),
            paper_base_dir=str(paper_base_dir),
        )
    except FileNotFoundError as exc:
        print(f"[P24 FAIL] Input missing: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"[P24 FAIL] Unexpected error: {exc}", file=sys.stderr)
        return 2

    # Write outputs
    try:
        output_files = write_p24_outputs(
            output_dir=args.output_dir,
            summary=summary,
            gate_result=gate_result,
            raw_audit_data=raw_audit_data,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[P24 FAIL] Could not write outputs: {exc}", file=sys.stderr)
        return 2

    # Print results
    print(f"p24_gate:                    {gate_result.p24_gate}")
    print(f"audit_status:                {gate_result.audit_status}")
    print(f"n_dates_audited:             {gate_result.n_dates_audited}")
    print(f"n_independent_source_dates:  {gate_result.n_independent_source_dates}")
    print(f"n_duplicate_source_groups:   {gate_result.n_duplicate_source_groups}")
    print(f"source_hash_unique_count:    {gate_result.source_hash_unique_count}")
    print(f"source_hash_duplicate_count: {gate_result.source_hash_duplicate_count}")
    print(f"roi_std_by_date:             {gate_result.roi_std_by_date:.8f}")
    print(f"hit_rate_std_by_date:        {gate_result.hit_rate_std_by_date:.8f}")
    print(f"production_ready:            {gate_result.production_ready}")
    print(f"paper_only:                  {gate_result.paper_only}")
    if gate_result.blocker_reason:
        print(f"blocker_reason:              {gate_result.blocker_reason}")
    print(f"recommended_next_action:     {gate_result.recommended_next_action}")
    print("")
    print("Output files:")
    for name, path in sorted(output_files.items()):
        print(f"  {name}: {path}")

    # Exit code
    p24_gate = gate_result.p24_gate
    if p24_gate == P24_BACKFILL_STABILITY_AUDIT_READY:
        return 0
    elif p24_gate in _BLOCKED_GATES:
        return 1
    else:
        return 2


if __name__ == "__main__":
    sys.exit(main())
