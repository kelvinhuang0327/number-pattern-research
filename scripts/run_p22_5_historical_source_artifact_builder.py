#!/usr/bin/env python3
"""
P22.5 Historical Source Artifact Builder CLI.

Scans source data directories to discover historical artifacts that can
be used to build P15 simulation inputs for missing backfill dates.

Usage:
    python scripts/run_p22_5_historical_source_artifact_builder.py \\
        --date-start 2026-05-01 \\
        --date-end 2026-05-12 \\
        --paper-base-dir outputs/predictions/PAPER \\
        --scan-base-path data \\
        --scan-base-path outputs \\
        --scan-base-path 00-BettingPlan \\
        --p22-summary outputs/predictions/PAPER/backfill/p22_historical_availability_2026-05-01_2026-05-12/historical_availability_summary.json \\
        --output-dir outputs/predictions/PAPER/backfill/p22_5_source_artifact_builder_2026-05-01_2026-05-12 \\
        --paper-only true \\
        --dry-run true

Exit codes:
    0 — P22_5_SOURCE_ARTIFACT_BUILDER_READY
    1 — P22_5_BLOCKED_*
    2 — P22_5_FAIL_*
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from wbc_backend.recommendation.p22_5_source_artifact_contract import (
    P22_5_BLOCKED_CONTRACT_VIOLATION,
    P22_5_BLOCKED_NO_SOURCE_CANDIDATES,
    P22_5_BLOCKED_UNSAFE_SOURCE_MAPPING,
    P22_5_FAIL_INPUT_MISSING,
    P22_5_FAIL_NON_DETERMINISTIC,
    P22_5_SOURCE_ARTIFACT_BUILDER_READY,
    SOURCE_CANDIDATE_USABLE,
    P225ArtifactBuilderGateResult,
)
from wbc_backend.recommendation.p22_5_historical_source_discovery import (
    discover_historical_source_candidates,
    summarize_source_candidates,
)
from wbc_backend.recommendation.p22_5_p15_readiness_planner import (
    build_source_artifact_build_plan,
    evaluate_p15_readiness_for_date,
    generate_safe_next_commands,
    validate_build_plan,
)
from wbc_backend.recommendation.p22_5_p15_input_dry_run_builder import (
    build_p15_input_preview_for_date,
)

import pandas as pd
from datetime import datetime


# ---------------------------------------------------------------------------
# P22 summary gate constant (expected from prior run)
# ---------------------------------------------------------------------------
_P22_EXPECTED_GATE = "P22_HISTORICAL_BACKFILL_AVAILABILITY_READY"
_PAPER_ONLY_MARKER = "P22_5_PAPER_ONLY"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="P22.5 Historical Source Artifact Builder"
    )
    p.add_argument("--date-start", required=True, help="Start date YYYY-MM-DD")
    p.add_argument("--date-end", required=True, help="End date YYYY-MM-DD")
    p.add_argument("--paper-base-dir", required=True, help="PAPER base output dir")
    p.add_argument(
        "--scan-base-path",
        action="append",
        dest="scan_base_paths",
        default=[],
        help="Directory to scan (repeatable)",
    )
    p.add_argument(
        "--p22-summary",
        required=False,
        default="",
        help="Path to P22 historical_availability_summary.json",
    )
    p.add_argument("--output-dir", required=True, help="Output directory for P22.5 results")
    p.add_argument(
        "--paper-only",
        required=True,
        choices=["true", "false"],
        help="Must be 'true'",
    )
    p.add_argument(
        "--dry-run",
        default="true",
        choices=["true", "false"],
        help="Emit dry-run previews for P15-ready dates",
    )
    return p.parse_args()


def _iter_dates(date_start: str, date_end: str):
    """Yield YYYY-MM-DD strings from date_start to date_end inclusive."""
    start = date.fromisoformat(date_start)
    end = date.fromisoformat(date_end)
    cur = start
    while cur <= end:
        yield cur.isoformat()
        cur += timedelta(days=1)


def _write_outputs(
    output_dir: Path,
    candidates,
    date_results,
    plan,
    gate_result: P225ArtifactBuilderGateResult,
    summary: dict,
) -> None:
    """Write all 6 required P22.5 output files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. source_candidate_inventory.json
    inventory = [
        {
            "source_path": c.source_path,
            "source_type": c.source_type,
            "source_date": c.source_date,
            "candidate_status": c.candidate_status,
            "coverage_pct": c.coverage_pct,
            "row_count": c.row_count,
            "has_game_id": c.has_game_id,
            "has_y_true": c.has_y_true,
            "has_odds": c.has_odds,
            "has_p_model_or_p_oof": c.has_p_model_or_p_oof,
            "mapping_risk": c.mapping_risk,
            "paper_only": c.paper_only,
            "production_ready": c.production_ready,
            "error_message": c.error_message,
        }
        for c in candidates
    ]
    with (output_dir / "source_candidate_inventory.json").open("w") as fh:
        json.dump(inventory, fh, indent=2)

    # 2. source_candidate_inventory.md
    lines = [
        "# P22.5 Source Candidate Inventory",
        "",
        f"**Total candidates scanned**: {summary['n_total']}",
        f"**Usable**: {summary['n_usable']}",
        f"**Partial**: {summary['n_partial']}",
        f"**Unsafe mapping**: {summary['n_unsafe']}",
        f"**Missing/unreadable**: {summary['n_missing']}",
        "",
        "## Candidate Details",
        "",
    ]
    for c in candidates:
        lines.append(f"### `{Path(c.source_path).name}`")
        lines.append(f"- **Path**: `{c.source_path}`")
        lines.append(f"- **Status**: `{c.candidate_status}`")
        lines.append(f"- **Type**: `{c.source_type}`")
        lines.append(f"- **Source date**: `{c.source_date or 'unknown'}`")
        lines.append(f"- **Mapping risk**: `{c.mapping_risk}`")
        lines.append(
            f"- **Fields**: game_id={c.has_game_id}, y_true={c.has_y_true}, "
            f"odds={c.has_odds}, p_model/p_oof={c.has_p_model_or_p_oof}"
        )
        if c.error_message:
            lines.append(f"- **Error**: `{c.error_message}`")
        lines.append("")
    with (output_dir / "source_candidate_inventory.md").open("w") as fh:
        fh.write("\n".join(lines))

    # 3. date_source_availability.csv
    rows = []
    for r in date_results:
        rows.append({
            "run_date": r.run_date,
            "candidate_status": r.candidate_status,
            "is_p15_ready": r.is_p15_ready,
            "has_predictions": r.has_predictions,
            "has_odds": r.has_odds,
            "has_outcomes": r.has_outcomes,
            "has_identity": r.has_identity,
            "blocked_reason": r.blocked_reason,
            "paper_only": r.paper_only,
            "production_ready": r.production_ready,
        })
    pd.DataFrame(rows).to_csv(output_dir / "date_source_availability.csv", index=False)

    # 4. p15_readiness_plan.json
    plan_dict = {
        "date_start": plan.date_start,
        "date_end": plan.date_end,
        "dates_ready_to_build_p15_inputs": list(plan.dates_ready_to_build_p15_inputs),
        "dates_partial_missing_odds": list(plan.dates_partial_missing_odds),
        "dates_partial_missing_predictions": list(plan.dates_partial_missing_predictions),
        "dates_partial_missing_outcomes": list(plan.dates_partial_missing_outcomes),
        "dates_unsafe_identity_mapping": list(plan.dates_unsafe_identity_mapping),
        "dates_missing_all_sources": list(plan.dates_missing_all_sources),
        "recommended_safe_commands": list(plan.recommended_safe_commands),
        "blocked_reason_by_date": list(plan.blocked_reason_by_date),
        "paper_only": plan.paper_only,
        "production_ready": plan.production_ready,
    }
    with (output_dir / "p15_readiness_plan.json").open("w") as fh:
        json.dump(plan_dict, fh, indent=2)

    # 5. p15_readiness_plan.md
    md_lines = [
        "# P22.5 P15 Readiness Plan",
        "",
        f"**Date range**: {plan.date_start} → {plan.date_end}",
        f"**Dates ready to build P15 inputs**: {len(plan.dates_ready_to_build_p15_inputs)}",
        "",
        "## Ready Dates",
        "",
    ]
    if plan.dates_ready_to_build_p15_inputs:
        for d in plan.dates_ready_to_build_p15_inputs:
            md_lines.append(f"- ✅ `{d}`")
    else:
        md_lines.append("_None_")
    md_lines.append("")
    md_lines.append("## Blocked / Partial Dates")
    md_lines.append("")
    for reason_str in plan.blocked_reason_by_date:
        md_lines.append(f"- `{reason_str}`")
    md_lines.append("")
    md_lines.append("## Recommended Next Commands")
    md_lines.append("")
    for cmd in plan.recommended_safe_commands:
        md_lines.append(f"```")
        md_lines.append(cmd)
        md_lines.append(f"```")
        md_lines.append("")
    with (output_dir / "p15_readiness_plan.md").open("w") as fh:
        fh.write("\n".join(md_lines))

    # 6. p22_5_gate_result.json
    gate_dict = {
        "p22_5_gate": gate_result.p22_5_gate,
        "date_start": gate_result.date_start,
        "date_end": gate_result.date_end,
        "n_source_candidates": gate_result.n_source_candidates,
        "n_usable_candidates": gate_result.n_usable_candidates,
        "n_dates_ready_to_build": gate_result.n_dates_ready_to_build,
        "n_dates_partial": gate_result.n_dates_partial,
        "n_dates_unsafe": gate_result.n_dates_unsafe,
        "n_dates_missing": gate_result.n_dates_missing,
        "dry_run_preview_count": gate_result.dry_run_preview_count,
        "recommended_next_action": gate_result.recommended_next_action,
        "paper_only": gate_result.paper_only,
        "production_ready": gate_result.production_ready,
        "generated_at": gate_result.generated_at,
    }
    with (output_dir / "p22_5_gate_result.json").open("w") as fh:
        json.dump(gate_dict, fh, indent=2)


def main() -> int:
    args = _parse_args()

    # --- Hard guard: paper-only enforcement ---
    if args.paper_only != "true":
        print(f"FAIL: --paper-only must be 'true'. Got: {args.paper_only}", file=sys.stderr)
        print(f"gate={P22_5_FAIL_INPUT_MISSING}", file=sys.stderr)
        return 2

    # --- Validate paper_base_dir ---
    paper_base_dir = Path(args.paper_base_dir)
    if not paper_base_dir.exists():
        print(f"FAIL: --paper-base-dir does not exist: {paper_base_dir}", file=sys.stderr)
        print(f"gate={P22_5_FAIL_INPUT_MISSING}", file=sys.stderr)
        return 2

    # --- Read P22 summary if provided ---
    p22_gate_ok = True
    if args.p22_summary:
        p22_summary_path = Path(args.p22_summary)
        if not p22_summary_path.exists():
            print(
                f"WARN: --p22-summary not found: {p22_summary_path}. Continuing without P22 validation.",
                file=sys.stderr,
            )
        else:
            try:
                with p22_summary_path.open() as fh:
                    p22_summary = json.load(fh)
                p22_gate = p22_summary.get("p22_gate", "")
                if p22_gate != _P22_EXPECTED_GATE:
                    print(
                        f"WARN: P22 gate is '{p22_gate}', expected '{_P22_EXPECTED_GATE}'. "
                        "Proceeding anyway for P22.5 source discovery.",
                        file=sys.stderr,
                    )
            except Exception as exc:
                print(f"WARN: Could not read P22 summary: {exc}", file=sys.stderr)

    # --- Date range ---
    all_dates = list(_iter_dates(args.date_start, args.date_end))
    if not all_dates:
        print(f"FAIL: No dates in range [{args.date_start}, {args.date_end}]", file=sys.stderr)
        return 2

    # --- Source discovery ---
    scan_paths = args.scan_base_paths or ["data", "outputs", "00-BettingPlan"]
    print(f"[P22.5] Scanning {len(scan_paths)} base path(s) for source candidates...")
    candidates = discover_historical_source_candidates(
        base_paths=scan_paths,
        date_start=args.date_start,
        date_end=args.date_end,
    )
    summary = summarize_source_candidates(candidates)
    print(
        f"[P22.5] Found {summary['n_total']} candidate files: "
        f"{summary['n_usable']} usable, {summary['n_partial']} partial, "
        f"{summary['n_missing']} missing, {summary['n_unsafe']} unsafe"
    )

    if summary["n_usable"] == 0 and summary["n_partial"] == 0:
        gate_val = P22_5_BLOCKED_NO_SOURCE_CANDIDATES
        # Still write outputs (empty plan)
        date_results = [
            evaluate_p15_readiness_for_date(d, candidates) for d in all_dates
        ]
        plan = build_source_artifact_build_plan(date_results, candidates)
        gate_result = P225ArtifactBuilderGateResult(
            p22_5_gate=gate_val,
            date_start=args.date_start,
            date_end=args.date_end,
            n_source_candidates=summary["n_total"],
            n_usable_candidates=summary["n_usable"],
            n_dates_ready_to_build=0,
            n_dates_partial=len(plan.dates_partial_missing_odds) + len(plan.dates_partial_missing_predictions) + len(plan.dates_partial_missing_outcomes),
            n_dates_unsafe=len(plan.dates_unsafe_identity_mapping),
            n_dates_missing=len(plan.dates_missing_all_sources),
            dry_run_preview_count=0,
            recommended_next_action="Acquire historical source data (MLB 2025 odds CSV, OOF predictions).",
            paper_only=True,
            production_ready=False,
            generated_at=datetime.utcnow().isoformat() + "Z",
        )
        _write_outputs(
            Path(args.output_dir), candidates, date_results, plan, gate_result, summary
        )
        print(f"[P22.5] gate={gate_val}")
        return 1

    # --- P15 readiness per date ---
    print(f"[P22.5] Evaluating P15 readiness for {len(all_dates)} dates...")
    date_results = [
        evaluate_p15_readiness_for_date(d, candidates) for d in all_dates
    ]

    n_ready = sum(1 for r in date_results if r.is_p15_ready)
    n_partial = sum(1 for r in date_results if not r.is_p15_ready and r.blocked_reason not in ("NO_SOURCE_CANDIDATES", ""))
    print(f"[P22.5] P15-ready: {n_ready} / {len(all_dates)} dates")

    # --- Build plan ---
    plan = build_source_artifact_build_plan(date_results, candidates)

    # --- Validate plan ---
    plan_valid, plan_err = validate_build_plan(plan)
    if not plan_valid:
        print(f"FAIL: build plan validation: {plan_err}", file=sys.stderr)
        gate_result = P225ArtifactBuilderGateResult(
            p22_5_gate=P22_5_BLOCKED_CONTRACT_VIOLATION,
            date_start=args.date_start,
            date_end=args.date_end,
            n_source_candidates=summary["n_total"],
            n_usable_candidates=summary["n_usable"],
            n_dates_ready_to_build=n_ready,
            n_dates_partial=n_partial,
            n_dates_unsafe=len(plan.dates_unsafe_identity_mapping),
            n_dates_missing=len(plan.dates_missing_all_sources),
            dry_run_preview_count=0,
            recommended_next_action=f"Fix contract violation: {plan_err}",
            paper_only=True,
            production_ready=False,
            generated_at=datetime.utcnow().isoformat() + "Z",
        )
        _write_outputs(
            Path(args.output_dir), candidates, date_results, plan, gate_result, summary
        )
        return 2

    # --- Dry-run previews ---
    output_dir = Path(args.output_dir)
    preview_count = 0
    if args.dry_run == "true" and plan.dates_ready_to_build_p15_inputs:
        usable_candidates = [c for c in candidates if c.candidate_status == SOURCE_CANDIDATE_USABLE]
        print(f"[P22.5] Building dry-run previews for {len(plan.dates_ready_to_build_p15_inputs)} ready dates...")
        for run_date in plan.dates_ready_to_build_p15_inputs:
            preview_df, blocker = build_p15_input_preview_for_date(
                run_date=run_date,
                source_candidates=usable_candidates,
                output_dir=output_dir,
            )
            if preview_df is not None:
                preview_count += 1
                print(f"[P22.5]   ✅ Preview built for {run_date}: {len(preview_df)} rows")
            else:
                print(f"[P22.5]   ⚠️  Preview blocked for {run_date}: {blocker}")

    # --- Determine overall gate ---
    if n_ready == 0 and len(plan.dates_unsafe_identity_mapping) > 0:
        gate_val = P22_5_BLOCKED_UNSAFE_SOURCE_MAPPING
    elif n_ready == 0:
        gate_val = P22_5_BLOCKED_NO_SOURCE_CANDIDATES
    else:
        gate_val = P22_5_SOURCE_ARTIFACT_BUILDER_READY

    # --- Recommended next action ---
    if n_ready >= 10:
        next_action = (
            f"{n_ready} dates ready for P15 input construction. "
            "Recommended next phase: P23 Execute Replayable Historical Backfill."
        )
    elif n_ready > 0:
        next_action = (
            f"{n_ready} date(s) ready. Remaining {len(all_dates) - n_ready} need additional source acquisition. "
            "Consider P22.6 Historical Source Acquisition for missing dates."
        )
    else:
        next_action = (
            "No dates P15-ready. Acquire historical source data (MLB 2025 odds CSV + OOF predictions)."
        )

    # --- Gate result ---
    gate_result = P225ArtifactBuilderGateResult(
        p22_5_gate=gate_val,
        date_start=args.date_start,
        date_end=args.date_end,
        n_source_candidates=summary["n_total"],
        n_usable_candidates=summary["n_usable"],
        n_dates_ready_to_build=n_ready,
        n_dates_partial=n_partial,
        n_dates_unsafe=len(plan.dates_unsafe_identity_mapping),
        n_dates_missing=len(plan.dates_missing_all_sources),
        dry_run_preview_count=preview_count,
        recommended_next_action=next_action,
        paper_only=True,
        production_ready=False,
        generated_at=datetime.utcnow().isoformat() + "Z",
    )

    # --- Write all outputs ---
    _write_outputs(output_dir, candidates, date_results, plan, gate_result, summary)

    # --- Summary print ---
    print("")
    print("=" * 60)
    print(f"P22.5 HISTORICAL SOURCE ARTIFACT BUILDER — SUMMARY")
    print("=" * 60)
    print(f"  gate                  : {gate_val}")
    print(f"  date_start            : {args.date_start}")
    print(f"  date_end              : {args.date_end}")
    print(f"  n_dates_scanned       : {len(all_dates)}")
    print(f"  n_source_candidates   : {summary['n_total']}")
    print(f"  n_usable_candidates   : {summary['n_usable']}")
    print(f"  n_dates_ready         : {n_ready}")
    print(f"  n_dates_partial       : {n_partial}")
    print(f"  n_dates_unsafe        : {len(plan.dates_unsafe_identity_mapping)}")
    print(f"  n_dates_missing       : {len(plan.dates_missing_all_sources)}")
    print(f"  dry_run_preview_count : {preview_count}")
    print(f"  paper_only            : True")
    print(f"  production_ready      : False")
    print(f"  next_action           : {next_action}")
    print(f"  output_dir            : {output_dir}")
    print("=" * 60)
    print(f"  {_PAPER_ONLY_MARKER}")
    print("=" * 60)

    # Exit codes
    if gate_val == P22_5_SOURCE_ARTIFACT_BUILDER_READY:
        return 0
    elif gate_val.startswith("P22_5_BLOCKED_"):
        return 1
    else:
        return 2


if __name__ == "__main__":
    sys.exit(main())
