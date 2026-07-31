"""
scripts/run_p25_true_date_source_separation.py

P25 True-Date Source Separation CLI — discovers true game_date source slices
and separates them per requested date.

Usage:
  ./.venv/bin/python scripts/run_p25_true_date_source_separation.py \
    --date-start 2026-05-01 \
    --date-end 2026-05-12 \
    --scan-base-path data \
    --scan-base-path outputs \
    --output-dir outputs/predictions/PAPER/backfill/p25_true_date_source_separation_2026-05-01_2026-05-12 \
    --paper-only true

Exit codes:
  0  P25_TRUE_DATE_SOURCE_SEPARATION_READY
  1  P25_BLOCKED_*
  2  P25_FAIL_*

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root on PYTHONPATH when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wbc_backend.recommendation.p25_true_date_source_contract import (
    P25_BLOCKED_NO_TRUE_DATE_SOURCE,
    P25_FAIL_INPUT_MISSING,
    P25_TRUE_DATE_SOURCE_SEPARATION_READY,
    P25SourceSeparationGateResult,
)
from wbc_backend.recommendation.p25_true_game_date_source_slicer import (
    discover_true_date_source_files,
)
from wbc_backend.recommendation.p25_source_separation_planner import (
    build_true_date_separation_plan,
    generate_next_backfill_commands,
    summarize_true_date_separation_results,
    validate_source_separation_summary,
)
from wbc_backend.recommendation.p25_true_date_artifact_writer import (
    build_artifact_manifest,
    validate_written_artifacts,
    write_true_date_artifacts,
)


# ---------------------------------------------------------------------------
# Output filenames
# ---------------------------------------------------------------------------
OUT_SUMMARY_JSON = "true_date_source_separation_summary.json"
OUT_SUMMARY_MD = "true_date_source_separation_summary.md"
OUT_DATE_SLICE_CSV = "date_slice_results.csv"
OUT_MANIFEST_JSON = "true_date_artifact_manifest.json"
OUT_RECOMMENDED_JSON = "recommended_backfill_range.json"
OUT_GATE_JSON = "p25_gate_result.json"

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------
EXIT_READY = 0
EXIT_BLOCKED = 1
EXIT_FAIL = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P25 True-Date Source Separation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--date-start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--date-end", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--scan-base-path",
        action="append",
        dest="scan_base_paths",
        default=[],
        metavar="PATH",
        help="Base path(s) to scan for source CSVs (repeat for multiple).",
    )
    parser.add_argument("--output-dir", required=True, help="Directory for outputs.")
    parser.add_argument(
        "--paper-only",
        required=True,
        choices=["true"],
        help="Must be 'true' — this is a PAPER_ONLY operation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Guard: paper_only must be "true"
    if args.paper_only.lower() != "true":
        print("FAIL: --paper-only must be 'true'. Aborting.", file=sys.stderr)
        return EXIT_FAIL

    date_start = args.date_start
    date_end = args.date_end
    output_dir = Path(args.output_dir)
    scan_base_paths = args.scan_base_paths or ["data", "outputs"]

    # Validate base paths exist
    missing_bases = [b for b in scan_base_paths if not Path(b).exists()]
    if missing_bases:
        print(
            f"FAIL ({P25_FAIL_INPUT_MISSING}): scan-base-path(s) not found:"
            f" {missing_bases}",
            file=sys.stderr,
        )
        return EXIT_FAIL

    # -----------------------------------------------------------------------
    # Step 1: Discover source candidates
    # -----------------------------------------------------------------------
    source_candidates = discover_true_date_source_files(scan_base_paths)

    # -----------------------------------------------------------------------
    # Step 2: Build per-date separation plan
    # -----------------------------------------------------------------------
    date_results = build_true_date_separation_plan(
        date_start, date_end, source_candidates
    )

    # -----------------------------------------------------------------------
    # Step 3: Summarise
    # -----------------------------------------------------------------------
    summary = summarize_true_date_separation_results(
        date_results, date_start, date_end, source_candidates
    )

    # -----------------------------------------------------------------------
    # Step 4: Write artifacts for READY dates
    # -----------------------------------------------------------------------
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = write_true_date_artifacts(date_results, output_dir)
    artifacts_valid = validate_written_artifacts(output_dir)

    # -----------------------------------------------------------------------
    # Step 5: Determine gate
    # -----------------------------------------------------------------------
    gate = _determine_gate(summary)
    generated_at = datetime.now(timezone.utc).isoformat()

    gate_result = P25SourceSeparationGateResult(
        p25_gate=gate,
        date_start=date_start,
        date_end=date_end,
        n_dates_requested=summary.n_dates_requested,
        n_true_date_ready=summary.n_true_date_ready,
        n_empty_dates=summary.n_empty_dates,
        n_partial_dates=summary.n_partial_dates,
        n_blocked_dates=summary.n_blocked_dates,
        detected_source_game_date_min=summary.detected_source_game_date_min,
        detected_source_game_date_max=summary.detected_source_game_date_max,
        recommended_backfill_date_start=summary.recommended_backfill_date_start,
        recommended_backfill_date_end=summary.recommended_backfill_date_end,
        blocker_reason=_blocker_reason(gate, summary),
        paper_only=True,
        production_ready=False,
        generated_at=generated_at,
    )

    # -----------------------------------------------------------------------
    # Step 6: Write all 6 output files
    # -----------------------------------------------------------------------
    _write_outputs(
        output_dir=output_dir,
        date_results=date_results,
        summary=summary,
        manifest=manifest,
        gate_result=gate_result,
        next_cmds=generate_next_backfill_commands(summary),
        generated_at=generated_at,
    )

    # -----------------------------------------------------------------------
    # Step 7: Print summary to stdout
    # -----------------------------------------------------------------------
    _print_summary(gate_result, summary)

    # -----------------------------------------------------------------------
    # Exit code
    # -----------------------------------------------------------------------
    if gate == P25_TRUE_DATE_SOURCE_SEPARATION_READY:
        return EXIT_READY
    elif gate.startswith("P25_BLOCKED_"):
        return EXIT_BLOCKED
    else:
        return EXIT_FAIL


# ---------------------------------------------------------------------------
# Gate logic
# ---------------------------------------------------------------------------


def _determine_gate(summary) -> str:
    from wbc_backend.recommendation.p25_true_date_source_contract import (
        P25_TRUE_DATE_SOURCE_SEPARATION_READY,
        P25_BLOCKED_NO_TRUE_DATE_SOURCE,
    )

    if summary.n_true_date_ready > 0:
        return P25_TRUE_DATE_SOURCE_SEPARATION_READY
    # No ready dates — check why
    return P25_BLOCKED_NO_TRUE_DATE_SOURCE


def _blocker_reason(gate: str, summary) -> str:
    if gate == P25_TRUE_DATE_SOURCE_SEPARATION_READY:
        return ""
    if gate == P25_BLOCKED_NO_TRUE_DATE_SOURCE:
        if summary.detected_source_game_date_min:
            return (
                f"Requested range {summary.date_start} to {summary.date_end} has"
                f" no true-date source rows. True source data spans"
                f" {summary.detected_source_game_date_min} to"
                f" {summary.detected_source_game_date_max}."
                f" Recommend re-running with detected range."
            )
        return (
            f"No true-date source rows found for {summary.date_start}"
            f" to {summary.date_end}. No source game_date data detected."
        )
    return ""


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def _write_outputs(
    output_dir: Path,
    date_results,
    summary,
    manifest,
    gate_result: P25SourceSeparationGateResult,
    next_cmds,
    generated_at: str,
) -> None:
    # 1. Gate result JSON
    gate_dict = dataclasses.asdict(gate_result)
    _write_json(output_dir / OUT_GATE_JSON, gate_dict)

    # 2. Summary JSON
    summary_dict = dataclasses.asdict(summary)
    summary_dict["generated_at"] = generated_at
    summary_dict["next_backfill_commands"] = next_cmds
    _write_json(output_dir / OUT_SUMMARY_JSON, summary_dict)

    # 3. Summary Markdown
    _write_summary_md(output_dir / OUT_SUMMARY_MD, summary, gate_result, generated_at)

    # 4. Date slice CSV
    _write_date_slice_csv(output_dir / OUT_DATE_SLICE_CSV, date_results)

    # 5. Artifact manifest JSON
    manifest_dict = dataclasses.asdict(manifest)
    # Convert tuples to lists for JSON
    manifest_dict["written_dates"] = list(manifest.written_dates)
    manifest_dict["skipped_dates"] = list(manifest.skipped_dates)
    _write_json(output_dir / OUT_MANIFEST_JSON, manifest_dict)

    # 6. Recommended backfill range JSON
    rec_dict = {
        "recommended_backfill_date_start": summary.recommended_backfill_date_start,
        "recommended_backfill_date_end": summary.recommended_backfill_date_end,
        "detected_source_game_date_min": summary.detected_source_game_date_min,
        "detected_source_game_date_max": summary.detected_source_game_date_max,
        "reason": _blocker_reason(gate_result.p25_gate, summary),
        "paper_only": True,
        "production_ready": False,
        "generated_at": generated_at,
    }
    _write_json(output_dir / OUT_RECOMMENDED_JSON, rec_dict)


def _write_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)


def _write_date_slice_csv(path: Path, date_results) -> None:
    fieldnames = [
        "run_date",
        "status",
        "source_path",
        "n_rows",
        "n_unique_game_ids",
        "game_date_min",
        "game_date_max",
        "has_required_columns",
        "blocker_reason",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in date_results:
            writer.writerow(r)


def _write_summary_md(
    path: Path,
    summary,
    gate_result: P25SourceSeparationGateResult,
    generated_at: str,
) -> None:
    lines = [
        "# P25 True-Date Source Separation Summary",
        "",
        f"Generated: {generated_at}",
        "",
        "## Gate Decision",
        "",
        f"| Key | Value |",
        f"|-----|-------|",
        f"| p25_gate | `{gate_result.p25_gate}` |",
        f"| date_start | {gate_result.date_start} |",
        f"| date_end | {gate_result.date_end} |",
        f"| n_dates_requested | {gate_result.n_dates_requested} |",
        f"| n_true_date_ready | {gate_result.n_true_date_ready} |",
        f"| n_empty_dates | {gate_result.n_empty_dates} |",
        f"| n_partial_dates | {gate_result.n_partial_dates} |",
        f"| n_blocked_dates | {gate_result.n_blocked_dates} |",
        f"| detected_source_game_date_min | {gate_result.detected_source_game_date_min} |",
        f"| detected_source_game_date_max | {gate_result.detected_source_game_date_max} |",
        f"| recommended_backfill_date_start | {gate_result.recommended_backfill_date_start} |",
        f"| recommended_backfill_date_end | {gate_result.recommended_backfill_date_end} |",
        f"| paper_only | {gate_result.paper_only} |",
        f"| production_ready | {gate_result.production_ready} |",
        "",
        "## Blocker Reason",
        "",
        gate_result.blocker_reason or "(none — gate is READY)",
        "",
        "---",
        "",
        "*PAPER_ONLY — no production systems, no real bets.*",
    ]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Stdout print
# ---------------------------------------------------------------------------


def _print_summary(gate_result: P25SourceSeparationGateResult, summary) -> None:
    print(f"p25_gate:                         {gate_result.p25_gate}")
    print(f"date_start:                       {gate_result.date_start}")
    print(f"date_end:                         {gate_result.date_end}")
    print(f"n_dates_requested:                {gate_result.n_dates_requested}")
    print(f"n_true_date_ready:                {gate_result.n_true_date_ready}")
    print(f"n_empty_dates:                    {gate_result.n_empty_dates}")
    print(f"n_partial_dates:                  {gate_result.n_partial_dates}")
    print(f"n_blocked_dates:                  {gate_result.n_blocked_dates}")
    print(f"detected_source_game_date_min:    {gate_result.detected_source_game_date_min}")
    print(f"detected_source_game_date_max:    {gate_result.detected_source_game_date_max}")
    print(f"recommended_backfill_date_start:  {gate_result.recommended_backfill_date_start}")
    print(f"recommended_backfill_date_end:    {gate_result.recommended_backfill_date_end}")
    print(f"production_ready:                 {gate_result.production_ready}")
    print(f"paper_only:                       {gate_result.paper_only}")


if __name__ == "__main__":
    sys.exit(main())
