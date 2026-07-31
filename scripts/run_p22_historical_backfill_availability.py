#!/usr/bin/env python3
"""
P22 Historical Backfill Availability CLI.

Scans a PAPER base directory across a date range, classifies each date by
artifact availability, generates a backfill execution plan, and writes 6
output artifacts.

Exit codes:
  0 — P22_HISTORICAL_BACKFILL_AVAILABILITY_READY
  1 — BLOCKED_*
  2 — FAIL_* (fatal: bad args, missing base dir, paper-only disabled)

PAPER_ONLY: True
PRODUCTION_READY: False
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Allow direct execution from repo root with PYTHONPATH=.
sys.path.insert(0, str(Path(__file__).parent.parent))

from wbc_backend.recommendation.p22_backfill_execution_plan import (
    build_backfill_execution_plan,
    validate_execution_plan,
)
from wbc_backend.recommendation.p22_historical_artifact_scanner import (
    scan_paper_date_range,
    summarize_scan_results,
)
from wbc_backend.recommendation.p22_historical_availability_contract import (
    P22_BLOCKED_NO_AVAILABLE_DATES,
    P22_FAIL_INPUT_MISSING,
    P22_HISTORICAL_BACKFILL_AVAILABILITY_READY,
    P22DateAvailabilityResult,
    P22GateResult,
    P22HistoricalAvailabilitySummary,
    P22BackfillExecutionPlan,
)


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def _to_dict(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        result = {}
        for f in dataclasses.fields(obj):
            val = getattr(obj, f.name)
            result[f.name] = _to_dict(val)
        return result
    if isinstance(obj, tuple):
        return [_to_dict(v) for v in obj]
    return obj


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_p22_outputs(
    summary: P22HistoricalAvailabilitySummary,
    date_results: List[P22DateAvailabilityResult],
    plan: P22BackfillExecutionPlan,
    output_dir: Path,
) -> List[str]:
    """Write all 6 output artifacts and return the list of written paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: List[str] = []

    # 1. historical_availability_summary.json
    summary_json = output_dir / "historical_availability_summary.json"
    summary_dict = _to_dict(summary)
    summary_json.write_text(
        json.dumps(summary_dict, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    written.append(str(summary_json))

    # 2. historical_availability_summary.md
    summary_md = output_dir / "historical_availability_summary.md"
    md_lines = [
        "# P22 Historical Backfill Availability Summary",
        "",
        f"**Gate**: `{summary.p22_gate}`",
        f"**Date range**: {summary.date_start} → {summary.date_end}",
        f"**Scanned**: {summary.n_dates_scanned} dates",
        "",
        "## Counts",
        f"| Category | Count |",
        f"|----------|-------|",
        f"| P20-ready | {summary.n_dates_p20_ready} |",
        f"| Replayable | {summary.n_dates_replayable} |",
        f"| Partial | {summary.n_dates_partial} |",
        f"| Missing | {summary.n_dates_missing} |",
        f"| Blocked | {summary.n_dates_blocked} |",
        f"| Backfill candidates | {summary.n_backfill_candidate_dates} |",
        "",
        "## Backfill Candidate Dates",
        ", ".join(summary.backfill_candidate_dates) if summary.backfill_candidate_dates else "_none_",
        "",
        "## Missing Dates",
        ", ".join(summary.missing_dates) if summary.missing_dates else "_none_",
        "",
        "## Blocked Dates",
        ", ".join(summary.blocked_dates) if summary.blocked_dates else "_none_",
        "",
        "## Recommended Next Action",
        summary.recommended_next_action,
        "",
        f"**paper_only**: {summary.paper_only}",
        f"**production_ready**: {summary.production_ready}",
    ]
    summary_md.write_text("\n".join(md_lines), encoding="utf-8")
    written.append(str(summary_md))

    # 3. date_availability_results.csv
    csv_path = output_dir / "date_availability_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "run_date",
            "availability_status",
            "p20_gate",
            "n_artifacts_found",
            "n_artifacts_required",
            "paper_only",
            "production_ready",
            "error_message",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in sorted(date_results, key=lambda x: x.run_date):
            writer.writerow(
                {
                    "run_date": r.run_date,
                    "availability_status": r.availability_status,
                    "p20_gate": r.p20_gate,
                    "n_artifacts_found": r.n_artifacts_found,
                    "n_artifacts_required": r.n_artifacts_required,
                    "paper_only": r.paper_only,
                    "production_ready": r.production_ready,
                    "error_message": r.error_message,
                }
            )
    written.append(str(csv_path))

    # 4. backfill_execution_plan.json
    plan_json = output_dir / "backfill_execution_plan.json"
    plan_dict = _to_dict(plan)
    plan_json.write_text(
        json.dumps(plan_dict, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    written.append(str(plan_json))

    # 5. backfill_execution_plan.md
    plan_md = output_dir / "backfill_execution_plan.md"
    plan_md_lines = [
        "# P22 Backfill Execution Plan",
        "",
        f"**Date range**: {plan.date_start} → {plan.date_end}",
        "",
        "## Dates to Skip (already P20-ready)",
        "\n".join(f"- {d}" for d in plan.dates_to_skip_already_ready) or "_none_",
        "",
        "## Dates to Replay",
        "\n".join(f"- {d}" for d in plan.dates_to_replay_from_existing_sources) or "_none_",
        "",
        "## Dates Missing Required Sources",
        "\n".join(f"- {d}" for d in plan.dates_missing_required_sources) or "_none_",
        "",
        "## Dates Blocked",
        "\n".join(f"- {d}" for d in plan.dates_blocked) or "_none_",
        "",
        "## Execution Order",
        "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan.execution_order)),
        "",
        "## Recommended Commands",
        "```bash",
        "\n".join(plan.recommended_commands),
        "```",
        "",
        "## Risk Notes",
        "\n".join(f"- {n}" for n in plan.risk_notes),
        "",
        f"**paper_only**: {plan.paper_only}",
        f"**production_ready**: {plan.production_ready}",
    ]
    plan_md.write_text("\n".join(plan_md_lines), encoding="utf-8")
    written.append(str(plan_md))

    # 6. p22_gate_result.json
    gate = P22GateResult(
        p22_gate=summary.p22_gate,
        date_start=summary.date_start,
        date_end=summary.date_end,
        n_dates_scanned=summary.n_dates_scanned,
        n_dates_p20_ready=summary.n_dates_p20_ready,
        n_dates_replayable=summary.n_dates_replayable,
        n_dates_partial=summary.n_dates_partial,
        n_dates_missing=summary.n_dates_missing,
        n_dates_blocked=summary.n_dates_blocked,
        n_backfill_candidate_dates=summary.n_backfill_candidate_dates,
        recommended_next_action=summary.recommended_next_action,
        paper_only=summary.paper_only,
        production_ready=summary.production_ready,
        generated_at=_now_utc(),
    )
    gate_json = output_dir / "p22_gate_result.json"
    gate_dict = _to_dict(gate)
    gate_json.write_text(
        json.dumps(gate_dict, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    written.append(str(gate_json))

    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P22 Historical Backfill Availability Scanner (PAPER_ONLY)"
    )
    parser.add_argument("--date-start", required=True, help="Start date ISO 8601 (e.g. 2026-05-01)")
    parser.add_argument("--date-end", required=True, help="End date ISO 8601 (e.g. 2026-05-12)")
    parser.add_argument(
        "--paper-base-dir",
        required=True,
        help="Base directory containing per-date PAPER prediction artifacts",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write P22 outputs into",
    )
    parser.add_argument(
        "--paper-only",
        default="true",
        help='Must be "true". Any other value causes immediate fatal exit.',
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Hard guard: paper-only
    if args.paper_only.strip().lower() != "true":
        print(
            f"[P22] FATAL: {P22_FAIL_INPUT_MISSING} — "
            "--paper-only must be 'true'. This is a PAPER_ONLY system.",
            file=sys.stderr,
        )
        sys.exit(2)

    base_dir = Path(args.paper_base_dir)
    if not base_dir.exists():
        print(
            f"[P22] FATAL: {P22_FAIL_INPUT_MISSING} — "
            f"paper-base-dir does not exist: {base_dir}",
            file=sys.stderr,
        )
        sys.exit(2)

    output_dir = Path(args.output_dir)

    # Step 1: Scan
    try:
        date_results = scan_paper_date_range(base_dir, args.date_start, args.date_end)
    except Exception as exc:
        print(
            f"[P22] FATAL: {P22_FAIL_INPUT_MISSING} — scan failed: {exc}",
            file=sys.stderr,
        )
        sys.exit(2)

    # Step 2: Summarize
    try:
        summary = summarize_scan_results(date_results, args.date_start, args.date_end)
    except Exception as exc:
        print(
            f"[P22] FATAL: {P22_FAIL_INPUT_MISSING} — summarize failed: {exc}",
            file=sys.stderr,
        )
        sys.exit(2)

    # Step 3: Build execution plan
    try:
        plan = build_backfill_execution_plan(summary, date_results)
    except Exception as exc:
        print(
            f"[P22] FATAL: {P22_FAIL_INPUT_MISSING} — plan generation failed: {exc}",
            file=sys.stderr,
        )
        sys.exit(2)

    # Step 4: Validate plan
    validation = validate_execution_plan(plan)
    if not validation.valid:
        print(
            f"[P22] FATAL: {validation.error_code} — {validation.error_message}",
            file=sys.stderr,
        )
        sys.exit(2)

    # Step 5: Write outputs (always write, even on BLOCKED)
    try:
        written = write_p22_outputs(summary, date_results, plan, output_dir)
    except Exception as exc:
        print(
            f"[P22] FATAL: {P22_FAIL_INPUT_MISSING} — failed to write outputs: {exc}",
            file=sys.stderr,
        )
        sys.exit(2)

    # Step 6: Print summary
    gate = summary.p22_gate
    print(f"[P22] {'SUCCESS' if gate == P22_HISTORICAL_BACKFILL_AVAILABILITY_READY else 'BLOCKED'}: {gate}")
    print(f"  date_start:                {summary.date_start}")
    print(f"  date_end:                  {summary.date_end}")
    print(f"  n_dates_scanned:           {summary.n_dates_scanned}")
    print(f"  n_dates_p20_ready:         {summary.n_dates_p20_ready}")
    print(f"  n_dates_replayable:        {summary.n_dates_replayable}")
    print(f"  n_dates_partial:           {summary.n_dates_partial}")
    print(f"  n_dates_missing:           {summary.n_dates_missing}")
    print(f"  n_dates_blocked:           {summary.n_dates_blocked}")
    print(f"  n_backfill_candidate_dates:{summary.n_backfill_candidate_dates}")
    print(f"  recommended_next_action:   {summary.recommended_next_action}")
    print(f"  production_ready:          {summary.production_ready}")
    print(f"  paper_only:                {summary.paper_only}")
    print(f"  outputs ({len(written)} files):")
    for path in written:
        print(f"    {path}")

    # Exit code
    if gate == P22_HISTORICAL_BACKFILL_AVAILABILITY_READY:
        sys.exit(0)
    elif gate.startswith("P22_BLOCKED"):
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
