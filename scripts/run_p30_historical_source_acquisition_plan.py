#!/usr/bin/env python3
"""
scripts/run_p30_historical_source_acquisition_plan.py

CLI for P30 Historical Season Source Acquisition Plan.

Usage:
    python scripts/run_p30_historical_source_acquisition_plan.py \\
        --target-season 2024 \\
        --scan-base-path data \\
        --scan-base-path outputs \\
        --p29-plan outputs/predictions/PAPER/backfill/p29_source_coverage_density_expansion_2025-05-08_2025-09-28/density_expansion_plan.json \\
        --output-dir outputs/predictions/PAPER/backfill/p30_source_acquisition_plan_2024 \\
        --paper-only true

Exit codes:
    0  P30_SOURCE_ACQUISITION_PLAN_READY
    1  P30_BLOCKED_*
    2  P30_FAIL_* (input errors, contract violations)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import timezone
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure PYTHONPATH=. is set before running
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Imports from modules
# ---------------------------------------------------------------------------

try:
    from wbc_backend.recommendation.p30_source_acquisition_contract import (
        P30_BLOCKED_CONTRACT_VIOLATION,
        P30_BLOCKED_LICENSE_OR_PROVENANCE_UNSAFE,
        P30_BLOCKED_MISSING_REQUIRED_ARTIFACT_SPEC,
        P30_BLOCKED_NO_VERIFIABLE_SOURCE,
        P30_FAIL_INPUT_MISSING,
        P30_FAIL_NON_DETERMINISTIC,
        P30_SOURCE_ACQUISITION_PLAN_READY,
        ARTIFACT_GAME_IDENTITY,
        ARTIFACT_GAME_OUTCOMES,
        ARTIFACT_MARKET_ODDS,
        ARTIFACT_MODEL_PREDICTIONS_OR_OOF,
        ARTIFACT_TRUE_DATE_JOINED_INPUT,
    )
    from wbc_backend.recommendation.p30_historical_season_source_inventory import (
        scan_existing_season_sources,
        summarize_existing_source_inventory,
    )
    from wbc_backend.recommendation.p30_required_artifact_spec_generator import (
        build_required_artifact_specs,
        identify_schema_gaps,
        map_existing_sources_to_specs,
        write_artifact_spec_docs,
    )
    from wbc_backend.recommendation.p30_source_acquisition_plan_builder import (
        build_gate_result,
        build_source_acquisition_plan,
        rank_source_acquisition_options,
    )
    from wbc_backend.recommendation.p30_dry_run_artifact_builder_skeleton import (
        build_dry_run_joined_input_preview,
        summarize_preview,
        write_preview_artifacts,
        validate_joined_input_preview,
    )
except ImportError as exc:
    print(f"P30_FAIL_INPUT_MISSING: Import error: {exc}", flush=True)
    sys.exit(2)

# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def _write_source_inventory(
    output_dir: Path,
    inventory: List[Dict[str, Any]],
    summary: Dict[str, Any],
    target_season: str,
) -> None:
    (output_dir / "source_inventory.json").write_text(
        json.dumps(
            {
                "target_season": target_season,
                "summary": summary,
                "candidates": inventory,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    lines = [
        f"# P30 Source Inventory — Season {target_season}\n",
        "",
        f"**Candidates scanned**: {summary['n_candidates_scanned']}",
        f"**Ready**: {summary['n_ready']}",
        f"**Partial**: {summary['n_partial']}",
        f"**Not available**: {summary['n_not_available']}",
        f"**Seasons found**: {', '.join(summary['seasons_found']) or 'none'}",
        "",
        "## Candidates",
    ]
    for c in inventory:
        lines.append(f"- `{c['path']}` — season={c['target_season']}, status={c['source_status']}, schema={c['schema_coverage']}")
    (output_dir / "source_inventory.md").write_text("\n".join(lines), encoding="utf-8")


def _write_source_acquisition_plan(
    output_dir: Path,
    plan_dict: Dict[str, Any],
    gate_result_dict: Dict[str, Any],
) -> None:
    (output_dir / "source_acquisition_plan.json").write_text(
        json.dumps(plan_dict, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    target_season = plan_dict.get("target_season", "?")
    gate = gate_result_dict.get("p30_gate", "?")
    lines = [
        f"# P30 Source Acquisition Plan — Season {target_season}\n",
        "",
        f"**Gate**: `{gate}`",
        f"**n_source_candidates**: {plan_dict.get('n_source_candidates', 0)}",
        f"**n_partial_sources**: {plan_dict.get('n_partial_sources', 0)}",
        f"**n_ready_sources**: {plan_dict.get('n_ready_sources', 0)}",
        f"**schema_gap_count**: {plan_dict.get('schema_gap_count', 0)}",
        f"**expected_sample_gain**: {plan_dict.get('estimated_sample_gain', 0)}",
        "",
        "## Recommended Next Action",
        "",
        plan_dict.get("recommended_next_action", ""),
        "",
        "## Required Build Steps",
        "",
        plan_dict.get("required_build_steps", ""),
        "",
        "## Required Validation Steps",
        "",
        plan_dict.get("required_validation_steps", ""),
    ]
    (output_dir / "source_acquisition_plan.md").write_text("\n".join(lines), encoding="utf-8")


def _write_gate_result(
    output_dir: Path,
    gate_result_dict: Dict[str, Any],
) -> None:
    (output_dir / "p30_gate_result.json").write_text(
        json.dumps(gate_result_dict, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_dry_run_preview_summary(
    output_dir: Path,
    summary: Dict[str, Any],
) -> None:
    (output_dir / "dry_run_preview_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def _parse_bool_arg(value: str, arg_name: str) -> bool:
    if value.lower() == "true":
        return True
    elif value.lower() == "false":
        return False
    else:
        raise argparse.ArgumentTypeError(f"--{arg_name} must be 'true' or 'false', got '{value}'")


def run(args: argparse.Namespace) -> int:
    """Execute P30 source acquisition plan and return exit code."""
    # Validate paper-only flag
    if not args.paper_only_bool:
        print(
            f"P30_FAIL_INPUT_MISSING: --paper-only must be 'true'. "
            f"This tool is PAPER_ONLY.",
            flush=True,
        )
        return 2

    target_season: str = args.target_season
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load P29 plan to confirm prior gate
    p29_gate = "UNKNOWN"
    if args.p29_plan:
        p29_path = Path(args.p29_plan)
        if p29_path.exists():
            try:
                p29_data = json.loads(p29_path.read_text(encoding="utf-8"))
                p29_gate = p29_data.get("p29_gate", "UNKNOWN")
                logger.info("P29 gate confirmed: %s", p29_gate)
            except Exception as exc:
                logger.warning("Could not read P29 plan: %s", exc)
        else:
            logger.warning("P29 plan path not found: %s", p29_path)
    else:
        logger.warning("No --p29-plan provided; P29 gate not confirmed.")

    # T3: Scan existing season sources
    scan_paths = [Path(p) for p in args.scan_base_path]
    logger.info("Scanning %d base path(s) for sources...", len(scan_paths))
    raw_inventory = scan_existing_season_sources(scan_paths)

    # Filter to target season and adjacent seasons (include all to find related sources)
    target_inventory = raw_inventory  # report all; plan focuses on target season
    summary = summarize_existing_source_inventory(target_inventory)
    logger.info(
        "Inventory: %d candidates, %d ready, %d partial",
        summary["n_candidates_scanned"],
        summary["n_ready"],
        summary["n_partial"],
    )

    _write_source_inventory(output_dir, target_inventory, summary, target_season)

    # T4: Build required artifact specs
    specs = build_required_artifact_specs(target_season)
    mapped_specs = map_existing_sources_to_specs(target_inventory, specs)
    schema_gaps = identify_schema_gaps(mapped_specs)
    write_artifact_spec_docs(output_dir, mapped_specs, schema_gaps, target_season)

    # T5: Build source acquisition plan
    plan = build_source_acquisition_plan(
        inventory=target_inventory,
        artifact_specs=mapped_specs,
        schema_gaps=schema_gaps,
        target_season=target_season,
    )
    gate_result = build_gate_result(plan)

    generated_at = datetime.now(tz=timezone.utc).isoformat()
    plan_dict = {
        "generated_at": generated_at,
        "target_season": plan.target_season,
        "date_start": plan.date_start,
        "date_end": plan.date_end,
        "expected_games": plan.expected_games,
        "expected_min_active_entries": plan.expected_min_active_entries,
        "source_path_or_url": plan.source_path_or_url,
        "provenance_status": plan.provenance_status,
        "license_risk": plan.license_risk,
        "schema_coverage": plan.schema_coverage,
        "n_source_candidates": plan.n_source_candidates,
        "n_partial_sources": plan.n_partial_sources,
        "n_ready_sources": plan.n_ready_sources,
        "schema_gap_count": plan.schema_gap_count,
        "missing_artifact_types": plan.missing_artifact_types,
        "estimated_sample_gain": plan.estimated_sample_gain,
        "recommended_next_action": plan.recommended_next_action,
        "acquisition_feasibility_note": plan.acquisition_feasibility_note,
        "required_build_steps": plan.required_build_steps,
        "required_validation_steps": plan.required_validation_steps,
        "p30_gate": plan.p30_gate,
        "audit_status": plan.audit_status,
        "paper_only": plan.paper_only,
        "production_ready": plan.production_ready,
    }
    gate_result_dict = {
        "generated_at": generated_at,
        "p30_gate": gate_result.p30_gate,
        "target_season": gate_result.target_season,
        "n_source_candidates": gate_result.n_source_candidates,
        "n_partial_sources": gate_result.n_partial_sources,
        "n_ready_sources": gate_result.n_ready_sources,
        "schema_gap_count": gate_result.schema_gap_count,
        "expected_sample_gain": gate_result.expected_sample_gain,
        "recommended_next_action": gate_result.recommended_next_action,
        "audit_status": gate_result.audit_status,
        "blocker_reason": gate_result.blocker_reason,
        "paper_only": gate_result.paper_only,
        "production_ready": gate_result.production_ready,
    }

    _write_source_acquisition_plan(output_dir, plan_dict, gate_result_dict)
    _write_gate_result(output_dir, gate_result_dict)

    # T6: Dry-run artifact builder skeleton
    # Build source_mapping for the preview
    source_mapping: Dict[str, Any] = {}
    for candidate in target_inventory:
        status = candidate.get("source_status", "")
        if status in ("SOURCE_PLAN_READY", "SOURCE_PLAN_PARTIAL"):
            s = candidate.get("target_season", "")
            # Map by artifact type based on available columns
            if candidate.get("has_game_id") and candidate.get("has_game_date"):
                if ARTIFACT_GAME_IDENTITY not in source_mapping:
                    source_mapping[ARTIFACT_GAME_IDENTITY] = candidate["path"]
            if candidate.get("has_y_true"):
                if ARTIFACT_GAME_OUTCOMES not in source_mapping:
                    source_mapping[ARTIFACT_GAME_OUTCOMES] = candidate["path"]
            if candidate.get("has_p_model"):
                if ARTIFACT_MODEL_PREDICTIONS_OR_OOF not in source_mapping:
                    source_mapping[ARTIFACT_MODEL_PREDICTIONS_OR_OOF] = candidate["path"]
            if candidate.get("has_odds_decimal") or candidate.get("has_p_market"):
                if ARTIFACT_MARKET_ODDS not in source_mapping:
                    source_mapping[ARTIFACT_MARKET_ODDS] = candidate["path"]

    preview_df = build_dry_run_joined_input_preview(source_mapping, output_dir)
    preview_summary = summarize_preview(preview_df)
    preview_validation = validate_joined_input_preview(preview_df)
    write_preview_artifacts(output_dir, preview_df, preview_summary, preview_validation)
    _write_dry_run_preview_summary(output_dir, preview_summary)

    # Print final results
    _print_results(plan_dict, gate_result_dict)

    # Determine exit code
    gate = gate_result.p30_gate
    if gate == P30_SOURCE_ACQUISITION_PLAN_READY:
        return 0
    elif gate.startswith("P30_FAIL_"):
        return 2
    else:
        return 1


def _print_results(plan_dict: Dict[str, Any], gate_result_dict: Dict[str, Any]) -> None:
    """Print structured result fields to stdout."""
    gate = gate_result_dict.get("p30_gate", "?")
    print("=" * 60, flush=True)
    print(f"p30_gate:                 {gate}", flush=True)
    print(f"target_season:            {gate_result_dict.get('target_season', '?')}", flush=True)
    print(f"n_source_candidates:      {gate_result_dict.get('n_source_candidates', 0)}", flush=True)
    print(f"n_partial_sources:        {gate_result_dict.get('n_partial_sources', 0)}", flush=True)
    print(f"n_ready_sources:          {gate_result_dict.get('n_ready_sources', 0)}", flush=True)
    print(f"schema_gap_count:         {gate_result_dict.get('schema_gap_count', 0)}", flush=True)
    print(f"expected_sample_gain:     {gate_result_dict.get('expected_sample_gain', 0)}", flush=True)
    print(f"paper_only:               {str(gate_result_dict.get('paper_only', True)).lower()}", flush=True)
    print(f"production_ready:         {str(gate_result_dict.get('production_ready', False)).lower()}", flush=True)
    print(f"recommended_next_action:  {gate_result_dict.get('recommended_next_action', '?')}", flush=True)
    print("=" * 60, flush=True)

    # Terminal marker
    if gate == P30_SOURCE_ACQUISITION_PLAN_READY:
        print(f"P30_HISTORICAL_SOURCE_ACQUISITION_PLAN_READY", flush=True)
    else:
        print(f"P30_HISTORICAL_SOURCE_ACQUISITION_PLAN_BLOCKED: {gate}", flush=True)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P30 Historical Season Source Acquisition Plan CLI"
    )
    parser.add_argument("--target-season", required=True, help="Target season year, e.g. 2024")
    parser.add_argument(
        "--scan-base-path",
        action="append",
        default=[],
        dest="scan_base_path",
        help="Base paths to scan for historical sources (repeatable)",
    )
    parser.add_argument(
        "--p29-plan",
        required=True,
        help="Path to P29 density_expansion_plan.json",
    )
    parser.add_argument("--output-dir", required=True, help="Output directory for P30 artifacts")
    parser.add_argument(
        "--paper-only",
        required=True,
        help="Must be 'true'. This is a paper-only planning tool.",
    )

    args = parser.parse_args()

    # Validate --paper-only
    if args.paper_only.lower() != "true":
        print(
            f"P30_FAIL_INPUT_MISSING: --paper-only must be 'true', got '{args.paper_only}'",
            flush=True,
        )
        return 2

    args.paper_only_bool = True

    if not args.target_season:
        print("P30_FAIL_INPUT_MISSING: --target-season is required", flush=True)
        return 2

    if not args.scan_base_path:
        args.scan_base_path = ["data", "outputs"]
        logger.info("No --scan-base-path provided; defaulting to: %s", args.scan_base_path)

    return run(args)


if __name__ == "__main__":
    sys.exit(main())
